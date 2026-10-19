from __future__ import annotations

from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from ..db import Database
from ..i18n import DEFAULT_LANG, join_list, localize_stored, translate
from ..indexing.embeddings import (
    DocumentVectorIndex,
    EmbeddingProvider,
    blob_to_vector,
)

_PROTECTED_STATUSES = {"encrypted", "encrypted_suspected"}


def document_summary(row: dict[str, Any], lang: str = DEFAULT_LANG) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "path": row["path"],
        "ext": row["ext"],
        "status": row["status"],
        "size_bytes": int(row["size_bytes"] or 0),
        "mtime_ns": int(row["mtime_ns"] or 0),
        "birthtime_ns": int(row["birthtime_ns"] or 0),
        "title": row["title"],
        "author": row["author"],
        "page_count": row["page_count"],
        "word_count": row["word_count"],
        "sheet_count": row["sheet_count"],
        "embedding_status": row["embedding_status"],
        "error": localize_stored(row["error"], lang),
        "encryption_kind": row["encryption_kind"],
        "open_count": int(row["open_count"] or 0),
        "last_opened_at": row["last_opened_at"],
    }


class RelatedService:
    def __init__(
        self,
        db: Database,
        doc_index: DocumentVectorIndex,
        provider: EmbeddingProvider,
    ):
        self.db = db
        self.doc_index = doc_index
        self.provider = provider

    def related(
        self, document_id: int, limit: int = 8, lang: str = DEFAULT_LANG
    ) -> list[dict[str, Any]]:
        row = self.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        if row is None:
            return []
        candidates: dict[int, dict[str, Any]] = {}

        def add(candidate_id: int, score: float, reason: str) -> None:
            if candidate_id == document_id:
                return
            entry = candidates.setdefault(
                candidate_id, {"document_id": candidate_id, "score": 0.0, "reasons": []}
            )
            entry["score"] = max(float(entry["score"]), float(score))
            if reason and reason not in entry["reasons"]:
                entry["reasons"].append(reason)

        protected = row["status"] in _PROTECTED_STATUSES

        if not protected:
            self._add_semantic(document_id, row, add, lang)
            self._add_keywords(document_id, add, lang)
        self._add_links(document_id, add, lang)
        self._add_duplicates(document_id, row, add, lang)

        ordered = sorted(candidates.values(), key=lambda item: item["score"], reverse=True)
        ordered = ordered[:limit]
        if not ordered:
            return []
        ids = [item["document_id"] for item in ordered]
        placeholders = ", ".join("?" for _ in ids)
        docs = {
            int(item["id"]): item
            for item in self.db.fetchall(
                f"SELECT * FROM documents WHERE id IN ({placeholders})", ids
            )
        }
        results: list[dict[str, Any]] = []
        for item in ordered:
            doc = docs.get(item["document_id"])
            if doc is None:
                continue
            summary = document_summary(dict(doc), lang)
            summary["score"] = round(float(item["score"]), 4)
            summary["reasons"] = item["reasons"]
            results.append(summary)
        return results

    def graph(
        self, document_id: int, depth: int = 1, limit: int = 30, lang: str = DEFAULT_LANG
    ) -> dict[str, Any]:
        center = self.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        if center is None:
            return {"nodes": [], "edges": []}
        related = self.related(document_id, limit=limit, lang=lang)
        nodes: list[dict[str, Any]] = [
            {
                "id": int(center["id"]),
                "label": center["title"] or center["name"],
                "ext": center["ext"],
                "status": center["status"],
                "center": True,
            }
        ]
        edges: list[dict[str, Any]] = []
        for item in related:
            nodes.append(
                {
                    "id": item["id"],
                    "label": item["title"] or item["name"],
                    "ext": item["ext"],
                    "status": item["status"],
                    "center": False,
                }
            )
            edges.append(
                {
                    "source": int(center["id"]),
                    "target": item["id"],
                    "score": item["score"],
                    "reason": join_list(item["reasons"], lang)
                    or translate("related.generic", lang),
                }
            )
        return {"nodes": nodes, "edges": edges}

    # --------------------------------------------------------------- signals

    def _add_semantic(
        self, document_id: int, row: dict[str, Any], add, lang: str = DEFAULT_LANG
    ) -> None:
        vector_row = self.db.fetchone(
            "SELECT vector, dim, model FROM doc_vectors WHERE document_id = ?",
            (document_id,),
        )
        if vector_row is None or not self.provider.ready:
            return
        vector = blob_to_vector(vector_row["vector"], int(vector_row["dim"]))
        hits = self.doc_index.search(vector, limit=20)
        for hit in hits:
            if hit.document_id == document_id:
                continue
            if hit.score >= 0.55:
                add(
                    hit.document_id,
                    hit.score,
                    translate("related.similarity", lang, score=f"{hit.score:.2f}"),
                )

    def _add_keywords(self, document_id: int, add, lang: str = DEFAULT_LANG) -> None:
        own = self.db.fetchall(
            "SELECT keyword FROM doc_keywords WHERE document_id = ? ORDER BY weight DESC LIMIT 20",
            (document_id,),
        )
        own_keywords = {row["keyword"] for row in own}
        if not own_keywords:
            return
        rows = self.db.fetchall(
            "SELECT dk.document_id, dk.keyword FROM doc_keywords dk "
            "WHERE dk.document_id != ? AND dk.keyword IN "
            f"({', '.join('?' for _ in own_keywords)})",
            [document_id, *own_keywords],
        )
        grouped: dict[int, list[str]] = {}
        for row in rows:
            grouped.setdefault(int(row["document_id"]), []).append(row["keyword"])
        for candidate_id, keywords in grouped.items():
            overlap = len(set(keywords))
            score = min(0.85, 0.35 + 0.08 * overlap)
            names = join_list(sorted(set(keywords))[:4], lang)
            add(candidate_id, score, translate("related.shared_keywords", lang, names=names))

    def _add_links(self, document_id: int, add, lang: str = DEFAULT_LANG) -> None:
        rows = self.db.fetchall(
            "SELECT from_document_id, target_document_id, href FROM document_links "
            "WHERE from_document_id = ? OR target_document_id = ?",
            (document_id, document_id),
        )
        for row in rows:
            if row["from_document_id"] == document_id and row["target_document_id"]:
                add(int(row["target_document_id"]), 0.9, translate("related.links_to_this", lang))
            if row["target_document_id"] == document_id and row["from_document_id"]:
                add(int(row["from_document_id"]), 0.9, translate("related.referenced_by", lang))

    def _add_duplicates(
        self, document_id: int, row: dict[str, Any], add, lang: str = DEFAULT_LANG
    ) -> None:
        if row["content_hash"]:
            duplicates = self.db.fetchall(
                "SELECT id FROM documents WHERE content_hash = ? AND id != ? "
                "AND status != 'missing' LIMIT 10",
                (row["content_hash"], document_id),
            )
            for duplicate in duplicates:
                add(int(duplicate["id"]), 0.98, translate("related.duplicate", lang))
        # File-name family: weak signal, only added as a reason for existing
        # candidates and as a standalone low-score relation.
        stem = Path(row["name"]).stem
        candidates = self.db.fetchall(
            "SELECT id, name FROM documents WHERE id != ? AND status != 'missing' "
            "ORDER BY mtime_ns DESC LIMIT 500",
            (document_id,),
        )
        for candidate in candidates:
            candidate_stem = Path(candidate["name"]).stem
            if not candidate_stem:
                continue
            score = fuzz.ratio(stem, candidate_stem) / 100.0
            if score >= 0.88 and stem != candidate_stem:
                add(int(candidate["id"]), 0.45, translate("related.similar_name", lang))
