from __future__ import annotations

import hashlib
import json
import logging
import os
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import (
    FILE_STABILITY_SECONDS,
    MAX_FILE_BYTES,
    MAX_TEXT_CHARS,
)
from ..db import Database
from ..db.ops import (
    delete_document_content,
    mark_document_missing,
    now_ts,
    upsert_document_file_fts,
)
from .chunker import build_chunks
from .extractors import (
    CorruptDocumentError,
    DocumentTooLargeError,
    EncryptedDocumentError,
    ExtractionError,
    UnsupportedDocumentError,
    extract_document,
)
from .protection import (
    ProtectionResult,
    is_encryption_exception,
    probe_file,
)
from .tokenizer import (
    extract_keywords,
    normalize_path_for_search,
    tokenize_for_fts,
)

logger = logging.getLogger(__name__)

RETRY = "retry"
DONE = "done"


@dataclass
class JobResult:
    action: str = DONE
    delay: float = 0.0
    error: str | None = None


def _file_stat(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "path_norm": unicodedata.normalize("NFC", str(path)),
        "name": path.name,
        "ext": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "birthtime_ns": int(getattr(stat, "st_birthtime", 0) * 1_000_000_000)
        if getattr(stat, "st_birthtime", 0)
        else None,
        "inode": stat.st_ino,
        "device": stat.st_dev,
    }


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path), str(root)]) == str(root)
    except ValueError:
        return False


def _rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


class IndexPipeline:
    def __init__(
        self,
        db: Database,
        *,
        on_embed: Callable[[int], None] | None = None,
        on_index: Callable[[str, int, bool], None] | None = None,
    ):
        self.db = db
        self.on_embed = on_embed
        self.on_index = on_index

    # ------------------------------------------------------------------ jobs

    def process_index_job(self, payload: dict[str, Any]) -> JobResult:
        raw_path = payload.get("path")
        source_id = payload.get("source_id")
        force = bool(payload.get("force", False))
        if not raw_path or not source_id:
            return JobResult(error="任务缺少路径或来源")
        path = Path(raw_path)
        source = self.db.fetchone("SELECT * FROM sources WHERE id = ?", (source_id,))
        if source is None:
            return JobResult()
        root = Path(source["path"])
        if not root.is_dir():
            return JobResult(action=RETRY, delay=60.0, error="来源目录暂不可用")
        if not _within(path, root):
            return JobResult(error="文件不在已索引目录内")
        if not path.exists() or not path.is_file():
            self._mark_missing_by_path(path)
            return JobResult()

        try:
            stat_info = _file_stat(path)
        except PermissionError as exc:
            self._record_error_by_path(path, source_id, f"没有读取权限：{exc}", purge=False)
            return JobResult()
        except OSError as exc:
            return JobResult(action=RETRY, delay=30.0, error=str(exc))

        if stat_info["size_bytes"] > MAX_FILE_BYTES:
            self._record_error_by_path(
                path,
                source_id,
                f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)} MB 上限，未索引",
                purge=True,
            )
            return JobResult()

        age = datetime.now(UTC).timestamp() - stat_info["mtime_ns"] / 1_000_000_000
        if age < FILE_STABILITY_SECONDS and not force:
            return JobResult(action=RETRY, delay=FILE_STABILITY_SECONDS + 1)

        document_id = self._upsert_document(path, root, source_id, stat_info)

        # Protection detection happens before reading/hashing the body.
        protection = probe_file(path)
        if protection.state == "permission":
            self._record_error(
                document_id, f"没有读取权限：{protection.error or ''}", purge=False
            )
            return JobResult()
        if protection.blocks_indexing:
            self._apply_protected(document_id, path, protection)
            return JobResult()

        try:
            content_hash = _hash_file(path)
        except PermissionError as exc:
            self._record_error(document_id, f"没有读取权限：{exc}", purge=False)
            return JobResult()
        except OSError as exc:
            return JobResult(action=RETRY, delay=10.0, error=str(exc))

        row = self.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        if (
            row is not None
            and not force
            and row["content_hash"] == content_hash
            and row["size_bytes"] == stat_info["size_bytes"]
            and row["status"] in ("indexed", "indexed_partial")
        ):
            self._touch_document(document_id, stat_info)
            return JobResult()

        try:
            extracted = extract_document(path)
        except EncryptedDocumentError as exc:
            self._apply_protected(
                document_id,
                path,
                ProtectionResult("encrypted", "extractor_encrypted", str(exc)),
            )
            return JobResult()
        except DocumentTooLargeError as exc:
            self._record_error(document_id, str(exc), purge=True)
            return JobResult()
        except UnsupportedDocumentError as exc:
            self._record_error(document_id, str(exc), purge=True)
            return JobResult()
        except CorruptDocumentError as exc:
            if is_encryption_exception(exc):
                self._apply_protected(
                    document_id,
                    path,
                    ProtectionResult("encrypted", "corrupt_encrypted", str(exc)),
                )
            else:
                self._record_error(document_id, f"文件损坏或无法解析：{exc}", purge=True)
            return JobResult()
        except PermissionError as exc:
            self._record_error(document_id, f"没有读取权限：{exc}", purge=False)
            return JobResult()
        except ExtractionError as exc:
            self._record_error(document_id, str(exc), purge=True)
            return JobResult()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("extract failed: %s", path)
            if is_encryption_exception(exc):
                self._apply_protected(
                    document_id,
                    path,
                    ProtectionResult("encrypted", "unknown_encrypted", str(exc)),
                )
            else:
                self._record_error(document_id, f"解析失败：{exc}", purge=True)
            return JobResult()

        try:
            after = _file_stat(path)
        except OSError:
            return JobResult(action=RETRY, delay=5.0)
        if after["size_bytes"] != stat_info["size_bytes"] or after["mtime_ns"] != stat_info["mtime_ns"]:
            return JobResult(action=RETRY, delay=2.0)

        self._store_extracted(document_id, path, stat_info, content_hash, extracted)
        return JobResult()

    def process_probe_job(self, payload: dict[str, Any]) -> JobResult:
        document_id = payload.get("document_id")
        if not document_id:
            return JobResult(error="探测任务缺少 document_id")
        row = self.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        if row is None:
            return JobResult()
        path = Path(row["path"])
        if not path.exists():
            mark_document_missing(self.db.connection, int(document_id))
            return JobResult()
        protection = probe_file(path)
        if protection.state == "permission":
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE documents SET last_probe_at = ?, error = ? WHERE id = ?",
                    (now_ts(), protection.error or "没有读取权限", document_id),
                )
            return JobResult()
        if protection.blocks_indexing:
            self._apply_protected(int(document_id), path, protection)
            return JobResult()
        # Readable again: force a full extraction even if mtime is unchanged.
        return self.process_index_job(
            {"path": str(path), "source_id": int(row["source_id"]), "force": True}
        )

    def process_delete_job(self, payload: dict[str, Any]) -> JobResult:
        raw_path = payload.get("path")
        if not raw_path:
            return JobResult()
        path = Path(raw_path)
        if path.exists():
            source_id = payload.get("source_id")
            if source_id and self.on_index is not None:
                self.on_index(str(path), int(source_id), False)
            return JobResult()
        self._mark_missing_by_path(path)
        return JobResult()

    # ------------------------------------------------------------ persistence

    def _upsert_document(
        self, path: Path, root: Path, source_id: int, stat_info: dict[str, Any]
    ) -> int:
        rel = _rel_path(path, root)
        name_tokens = tokenize_for_fts(path.stem)
        path_tokens = tokenize_for_fts(rel)
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE path = ?", (str(path),)
            ).fetchone()
            if row is None and stat_info.get("inode") is not None:
                row = conn.execute(
                    "SELECT * FROM documents WHERE device = ? AND inode = ? "
                    "AND path != ? ORDER BY (status = 'missing') ASC, id ASC LIMIT 1",
                    (stat_info["device"], stat_info["inode"], str(path)),
                ).fetchone()
                if row is not None:
                    # Rename/move within (or between) sources.
                    conn.execute(
                        "UPDATE documents SET path = ?, path_norm = ?, rel_path = ?, "
                        "name = ?, ext = ?, source_id = ?, size_bytes = ?, mtime_ns = ?, "
                        "birthtime_ns = ?, inode = ?, device = ?, name_tokens = ?, "
                        "path_tokens = ? WHERE id = ?",
                        (
                            stat_info["path"],
                            stat_info["path_norm"],
                            rel,
                            path.name,
                            stat_info["ext"],
                            source_id,
                            stat_info["size_bytes"],
                            stat_info["mtime_ns"],
                            stat_info["birthtime_ns"],
                            stat_info["inode"],
                            stat_info["device"],
                            name_tokens,
                            path_tokens,
                            row["id"],
                        ),
                    )
                    upsert_document_file_fts(
                        conn,
                        int(row["id"]),
                        name_tokens=name_tokens,
                        title_tokens=row["title_tokens"] or tokenize_for_fts(path.stem),
                        path_tokens=path_tokens,
                    )
                    conn.execute(
                        "UPDATE document_links SET target_document_id = ? WHERE target_path = ?",
                        (row["id"], stat_info["path_norm"]),
                    )
                    return int(row["id"])
            if row is None:
                cursor = conn.execute(
                    "INSERT INTO documents (source_id, path, path_norm, rel_path, name, ext, "
                    "size_bytes, mtime_ns, birthtime_ns, inode, device, status, "
                    "embedding_status, name_tokens, path_tokens) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'none', ?, ?)",
                    (
                        source_id,
                        stat_info["path"],
                        stat_info["path_norm"],
                        rel,
                        path.name,
                        stat_info["ext"],
                        stat_info["size_bytes"],
                        stat_info["mtime_ns"],
                        stat_info["birthtime_ns"],
                        stat_info["inode"],
                        stat_info["device"],
                        name_tokens,
                        path_tokens,
                    ),
                )
                document_id = int(cursor.lastrowid)
                upsert_document_file_fts(
                    conn,
                    document_id,
                    name_tokens=name_tokens,
                    title_tokens=tokenize_for_fts(path.stem),
                    path_tokens=path_tokens,
                )
                return document_id

            conn.execute(
                "UPDATE documents SET source_id = ?, path_norm = ?, rel_path = ?, name = ?, "
                "ext = ?, size_bytes = ?, mtime_ns = ?, birthtime_ns = ?, inode = ?, device = ?, "
                "name_tokens = ?, path_tokens = ? WHERE id = ?",
                (
                    source_id,
                    stat_info["path_norm"],
                    rel,
                    path.name,
                    stat_info["ext"],
                    stat_info["size_bytes"],
                    stat_info["mtime_ns"],
                    stat_info["birthtime_ns"],
                    stat_info["inode"],
                    stat_info["device"],
                    name_tokens,
                    path_tokens,
                    row["id"],
                ),
            )
            upsert_document_file_fts(
                conn,
                int(row["id"]),
                name_tokens=name_tokens,
                title_tokens=row["title_tokens"] or tokenize_for_fts(path.stem),
                path_tokens=path_tokens,
            )
            return int(row["id"])

    def _touch_document(self, document_id: int, stat_info: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE documents SET size_bytes = ?, mtime_ns = ?, birthtime_ns = ? "
                "WHERE id = ?",
                (
                    stat_info["size_bytes"],
                    stat_info["mtime_ns"],
                    stat_info["birthtime_ns"],
                    document_id,
                ),
            )

    def _store_extracted(
        self,
        document_id: int,
        path: Path,
        stat_info: dict[str, Any],
        content_hash: str,
        extracted,
    ) -> None:
        blocks, truncated = self._limit_blocks(extracted)
        extracted.blocks = blocks
        if truncated:
            extracted.partial = True
            if "文档内容超过单文档字符上限，索引已截断" not in extracted.warnings:
                extracted.warnings.append("文档内容超过单文档字符上限，索引已截断")

        chunks = build_chunks(extracted)
        full_text = extracted.full_text
        keywords = extract_keywords(full_text)
        links = self._collect_links(extracted, path)

        name_tokens = tokenize_for_fts(path.stem)
        title = (extracted.title or path.stem).strip() or path.stem
        title_tokens = tokenize_for_fts(title)
        path_tokens = tokenize_for_fts(self._rel_for_path(path, document_id))

        status = "indexed_partial" if (extracted.partial or not chunks) else "indexed"
        embedding_status = "pending" if chunks else "none"

        with self.db.transaction() as conn:
            delete_document_content(conn, document_id, include_file_fts=False)
            for chunk in chunks:
                heading = "\n".join(chunk.heading_path)
                body_tokens = tokenize_for_fts(
                    f"{heading}\n{chunk.text}" if heading else chunk.text
                )
                cursor = conn.execute(
                    "INSERT INTO chunks (document_id, ordinal, kind, location_label, "
                    "location_json, heading_path, text, char_start, char_end) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        document_id,
                        chunk.ordinal,
                        chunk.kind,
                        chunk.location_label,
                        json.dumps(chunk.location_json, ensure_ascii=False),
                        json.dumps(chunk.heading_path, ensure_ascii=False),
                        chunk.text,
                        chunk.char_start,
                        chunk.char_end,
                    ),
                )
                chunk_id = int(cursor.lastrowid)
                conn.execute(
                    "INSERT INTO chunks_fts(rowid, body_tokens, document_id) VALUES (?, ?, ?)",
                    (chunk_id, body_tokens, document_id),
                )
            for keyword, weight in keywords:
                conn.execute(
                    "INSERT OR REPLACE INTO doc_keywords (document_id, keyword, weight) "
                    "VALUES (?, ?, ?)",
                    (document_id, keyword, weight),
                )
            for href, target_path in links:
                target_document_id = None
                if target_path:
                    target_row = conn.execute(
                        "SELECT id FROM documents WHERE path_norm = ? AND status != 'missing' "
                        "ORDER BY id LIMIT 1",
                        (normalize_path_for_search(target_path),),
                    ).fetchone()
                    if target_row is not None:
                        target_document_id = int(target_row["id"])
                conn.execute(
                    "INSERT OR IGNORE INTO document_links "
                    "(from_document_id, href, target_path, target_document_id) VALUES (?, ?, ?, ?)",
                    (document_id, href, target_path, target_document_id),
                )
            conn.execute(
                "UPDATE documents SET title = ?, author = ?, page_count = ?, word_count = ?, "
                "sheet_count = ?, status = ?, embedding_status = ?, error = NULL, "
                "encryption_kind = NULL, indexed_at = ?, size_bytes = ?, mtime_ns = ?, "
                "birthtime_ns = ?, inode = ?, device = ?, content_hash = ?, "
                "metadata_json = ?, name_tokens = ?, title_tokens = ?, path_tokens = ?, "
                "last_probe_at = NULL WHERE id = ?",
                (
                    title,
                    extracted.author,
                    extracted.page_count,
                    extracted.word_count,
                    extracted.sheet_count,
                    status,
                    embedding_status,
                    now_ts(),
                    stat_info["size_bytes"],
                    stat_info["mtime_ns"],
                    stat_info["birthtime_ns"],
                    stat_info["inode"],
                    stat_info["device"],
                    content_hash,
                    json.dumps(
                        {
                            "metadata": extracted.metadata,
                            "warnings": extracted.warnings,
                        },
                        ensure_ascii=False,
                    ),
                    name_tokens,
                    title_tokens,
                    path_tokens,
                    document_id,
                ),
            )
            upsert_document_file_fts(
                conn,
                document_id,
                name_tokens=name_tokens,
                title_tokens=title_tokens,
                path_tokens=path_tokens,
            )
            # Resolve links from other documents that point at this file.
            conn.execute(
                "UPDATE document_links SET target_document_id = ? WHERE target_path = ?",
                (document_id, stat_info["path_norm"]),
            )

        if chunks and self.on_embed is not None:
            self.on_embed(document_id)

    def _apply_protected(
        self, document_id: int, path: Path, protection: ProtectionResult
    ) -> None:
        status = "encrypted" if protection.state == "encrypted" else "encrypted_suspected"
        detail = protection.detail or protection.error or "检测到受保护内容"
        name_tokens = tokenize_for_fts(path.stem)
        path_tokens = tokenize_for_fts(self._rel_for_path(path, document_id))
        with self.db.transaction() as conn:
            delete_document_content(conn, document_id, include_file_fts=False)
            conn.execute(
                "UPDATE documents SET status = ?, embedding_status = 'none', error = ?, "
                "encryption_kind = ?, last_probe_at = ?, content_hash = NULL, indexed_at = NULL, "
                "title = COALESCE(NULLIF(title, ''), ?), name_tokens = ?, title_tokens = ?, "
                "path_tokens = ? WHERE id = ?",
                (
                    status,
                    detail,
                    protection.kind,
                    now_ts(),
                    path.stem,
                    name_tokens,
                    tokenize_for_fts(path.stem),
                    path_tokens,
                    document_id,
                ),
            )
            upsert_document_file_fts(
                conn,
                document_id,
                name_tokens=name_tokens,
                title_tokens=tokenize_for_fts(path.stem),
                path_tokens=path_tokens,
            )

    def _record_error(
        self, document_id: int, message: str, *, purge: bool
    ) -> None:
        with self.db.transaction() as conn:
            if purge:
                delete_document_content(conn, document_id, include_file_fts=True)
                conn.execute(
                    "UPDATE documents SET status = 'failed', embedding_status = 'none', "
                    "error = ?, content_hash = NULL WHERE id = ?",
                    (message, document_id),
                )
            else:
                row = conn.execute(
                    "SELECT status FROM documents WHERE id = ?", (document_id,)
                ).fetchone()
                current = row["status"] if row else "failed"
                new_status = current if current in ("indexed", "indexed_partial") else "failed"
                conn.execute(
                    "UPDATE documents SET status = ?, error = ? WHERE id = ?",
                    (new_status, message, document_id),
                )

    def _record_error_by_path(
        self, path: Path, source_id: int, message: str, *, purge: bool
    ) -> None:
        row = self.db.fetchone("SELECT id FROM documents WHERE path = ?", (str(path),))
        if row is not None:
            self._record_error(int(row["id"]), message, purge=purge)
            return
        try:
            stat_info = _file_stat(path)
        except OSError:
            return
        source = self.db.fetchone("SELECT path FROM sources WHERE id = ?", (source_id,))
        if source is None:
            return
        root = Path(source["path"])
        document_id = self._upsert_document(path, root, source_id, stat_info)
        self._record_error(document_id, message, purge=purge)

    def _mark_missing_by_path(self, path: Path) -> None:
        row = self.db.fetchone("SELECT id FROM documents WHERE path = ?", (str(path),))
        if row is not None:
            mark_document_missing(self.db.connection, int(row["id"]))

    # --------------------------------------------------------------- helpers

    def _rel_for_path(self, path: Path, document_id: int) -> str:
        row = self.db.fetchone(
            "SELECT rel_path, source_id FROM documents WHERE id = ?", (document_id,)
        )
        if row is None:
            return path.name
        if row["rel_path"]:
            return row["rel_path"]
        source = self.db.fetchone(
            "SELECT path FROM sources WHERE id = ?", (row["source_id"],)
        )
        if source is None:
            return path.name
        return _rel_path(path, Path(source["path"]))

    @staticmethod
    def _limit_blocks(extracted) -> tuple[list, bool]:
        total = 0
        kept = []
        truncated = False
        for block in extracted.blocks:
            if total + len(block.text) > MAX_TEXT_CHARS:
                remaining = MAX_TEXT_CHARS - total
                if remaining > 0:
                    block.text = block.text[:remaining]
                    kept.append(block)
                truncated = True
                break
            total += len(block.text)
            kept.append(block)
        return kept, truncated

    @staticmethod
    def _collect_links(extracted, path: Path) -> list[tuple[str, str | None]]:
        collected: dict[str, str | None] = {}
        for link in extracted.metadata.get("links", []) or []:
            href = str(link.get("href", "")).strip()
            if href:
                collected.setdefault(href, link.get("target_path"))
        for block in extracted.blocks:
            for link in block.links:
                collected.setdefault(link.href, link.target_path)
        return [
            (href, normalize_path_for_search(target) if target else None)
            for href, target in collected.items()
        ]
