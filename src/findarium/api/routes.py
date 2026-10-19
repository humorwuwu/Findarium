from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..config import (
    DEFAULT_ENCRYPTED_RECHECK_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
from ..db.ops import delete_document
from ..library import AppContext, LibraryError
from ..native import (
    choose_folder_via_osascript,
    open_path,
    open_privacy_settings,
    reveal_path,
)

router = APIRouter(prefix="/api")


class LibraryBody(BaseModel):
    path: str
    embedding_enabled: bool = True


class SourceBody(BaseModel):
    path: str
    label: str | None = None


class SourcePatch(BaseModel):
    enabled: bool | None = None
    label: str | None = None
    exclude_globs: str | None = None


class FeedbackBody(BaseModel):
    query: str = ""
    document_id: int
    action: str = "click"


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def require_library(request: Request) -> AppContext:
    ctx = get_ctx(request)
    if not ctx.ready:
        raise HTTPException(status_code=409, detail="索引库尚未初始化")
    return ctx


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status")
def status(request: Request) -> dict[str, Any]:
    return get_ctx(request).status()


@router.get("/library")
def library_status(request: Request) -> dict[str, Any]:
    return get_ctx(request).library_status()


@router.post("/library/initialize")
def initialize_library(body: LibraryBody, request: Request) -> dict[str, Any]:
    ctx = get_ctx(request)
    try:
        ctx.attach(
            Path(body.path),
            embedding_enabled=body.embedding_enabled,
            remember=True,
        )
    except LibraryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"初始化索引库失败：{exc}") from exc
    return ctx.status()


@router.put("/library")
def relocate_library(body: LibraryBody, request: Request) -> dict[str, Any]:
    ctx = get_ctx(request)
    try:
        ctx.relocate(Path(body.path))
    except LibraryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"迁移索引库失败：{exc}") from exc
    return ctx.status()


@router.post("/native/pick-folder")
def pick_folder() -> dict[str, Any]:
    path = choose_folder_via_osascript()
    if not path:
        raise HTTPException(status_code=501, detail="无法打开系统目录选择器")
    return {"path": path}


@router.post("/native/open-privacy-settings")
def privacy_settings() -> dict[str, bool]:
    return {"ok": open_privacy_settings()}


# ------------------------------------------------------------------- sources


@router.get("/sources")
def list_sources(request: Request) -> list[dict[str, Any]]:
    ctx = require_library(request)
    assert ctx.db is not None
    rows = ctx.db.fetchall(
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM documents d WHERE d.source_id = s.id) AS document_count, "
        "(SELECT COUNT(*) FROM documents d WHERE d.source_id = s.id "
        " AND d.status IN ('encrypted','encrypted_suspected')) AS encrypted_count, "
        "(SELECT COUNT(*) FROM documents d WHERE d.source_id = s.id AND d.status = 'failed') "
        "AS failed_count "
        "FROM sources s ORDER BY s.id"
    )
    return [dict(row) for row in rows]


@router.post("/sources")
def add_source(body: SourceBody, request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.db is not None
    path = Path(body.path).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="目录不存在或不可访问")
    existing = ctx.db.fetchall("SELECT id, path FROM sources")
    for row in existing:
        old = Path(row["path"])
        if path == old or path.is_relative_to(old) or old.is_relative_to(path):
            raise HTTPException(
                status_code=400, detail="该目录与已索引目录重叠，请避免重复添加"
            )
    with ctx.db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO sources (path, label, created_at) VALUES (?, ?, ?)",
            (str(path), body.label or path.name, int(time.time())),
        )
        source_id = int(cursor.lastrowid)
    assert ctx.coordinator is not None
    ctx.coordinator.refresh_watchers()
    ctx.coordinator.scan_source(source_id)
    return {"id": source_id, "path": str(path)}


@router.patch("/sources/{source_id}")
def patch_source(source_id: int, body: SourcePatch, request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.db is not None
    fields: list[str] = []
    params: list[Any] = []
    if body.enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if body.enabled else 0)
    if body.label is not None:
        fields.append("label = ?")
        params.append(body.label)
    if body.exclude_globs is not None:
        fields.append("exclude_globs = ?")
        params.append(body.exclude_globs)
    if not fields:
        return {"ok": True}
    params.append(source_id)
    with ctx.db.transaction() as conn:
        conn.execute(f"UPDATE sources SET {', '.join(fields)} WHERE id = ?", params)
    assert ctx.coordinator is not None
    ctx.coordinator.refresh_watchers()
    ctx.coordinator.scan_source(source_id)
    return {"ok": True}


@router.delete("/sources/{source_id}")
def remove_source(source_id: int, request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.db is not None and ctx.coordinator is not None
    with ctx.db.transaction() as conn:
        document_ids = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM documents WHERE source_id = ?", (source_id,)
            ).fetchall()
        ]
        for document_id in document_ids:
            delete_document(conn, document_id)
        conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    ctx.coordinator.refresh_watchers()
    return {"ok": True, "removed_documents": len(document_ids)}


@router.post("/sources/{source_id}/scan")
def scan_source(source_id: int, request: Request) -> dict[str, bool]:
    ctx = require_library(request)
    assert ctx.coordinator is not None
    ctx.coordinator.scan_source(source_id)
    return {"ok": True}


# -------------------------------------------------------------------- search


@router.get("/search")
def search(
    request: Request,
    q: str = "",
    ext: Annotated[list[str] | None, Query()] = None,
    after: str | None = None,
    before: str | None = None,
    folder: str | None = None,
    encrypted: str | None = None,
    sort: str | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.search is not None
    return ctx.search.search(
        q,
        extensions=ext,
        after=after,
        before=before,
        folder=folder,
        encrypted=encrypted,
        sort=sort,
        limit=max(1, min(limit, 100)),
    )


@router.get("/search/suggestions")
def suggestions(request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.search is not None
    return ctx.search.suggestions()


@router.post("/search/feedback")
def feedback(body: FeedbackBody, request: Request) -> dict[str, bool]:
    ctx = require_library(request)
    assert ctx.search is not None
    ctx.search.feedback(body.query, body.document_id, body.action)
    return {"ok": True}


# ----------------------------------------------------------------- documents


@router.get("/documents/{document_id}")
def get_document(document_id: int, request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.search is not None
    document = ctx.search.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


@router.get("/documents/{document_id}/chunks")
def get_chunks(document_id: int, request: Request) -> list[dict[str, Any]]:
    ctx = require_library(request)
    assert ctx.search is not None
    document = ctx.search.get_document(document_id, include_chunks=True)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document.get("chunks", [])


@router.get("/documents/{document_id}/related")
def get_related(document_id: int, request: Request) -> list[dict[str, Any]]:
    ctx = require_library(request)
    assert ctx.search is not None
    return ctx.search.related(document_id)


@router.get("/documents/{document_id}/graph")
def get_graph(document_id: int, request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.search is not None
    return ctx.search.graph(document_id)


@router.get("/documents/{document_id}/file")
def get_file(document_id: int, request: Request) -> FileResponse:
    ctx = require_library(request)
    assert ctx.db is not None
    row = ctx.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
    if row is None or row["status"] == "missing":
        raise HTTPException(status_code=404, detail="文档不存在")
    if row["ext"] != ".pdf":
        raise HTTPException(status_code=400, detail="只有 PDF 支持应用内预览")
    path = Path(row["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件已被移动或删除")
    return FileResponse(path, media_type="application/pdf", filename=row["name"])


def _require_document_path(ctx: AppContext, document_id: int) -> tuple[dict[str, Any], Path]:
    assert ctx.db is not None
    row = ctx.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    path = Path(row["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件已被移动或删除")
    source = ctx.db.fetchone("SELECT path FROM sources WHERE id = ?", (row["source_id"],))
    if source is not None:
        root = Path(source["path"])
        try:
            if not path.resolve().is_relative_to(root.resolve()):
                raise HTTPException(status_code=403, detail="文件不在已索引目录内")
        except OSError:
            pass
    return dict(row), path


@router.post("/documents/{document_id}/open")
def open_document(document_id: int, request: Request) -> dict[str, bool]:
    ctx = require_library(request)
    row, path = _require_document_path(ctx, document_id)
    ok = open_path(path)
    if ctx.search is not None:
        ctx.search.feedback("", document_id, "open")
    return {"ok": ok}


@router.post("/documents/{document_id}/reveal")
def reveal_document(document_id: int, request: Request) -> dict[str, bool]:
    ctx = require_library(request)
    row, path = _require_document_path(ctx, document_id)
    ok = reveal_path(path)
    if ctx.search is not None:
        ctx.search.feedback("", document_id, "reveal")
    return {"ok": ok}


@router.post("/documents/{document_id}/reindex")
def reindex_document(document_id: int, request: Request) -> dict[str, bool]:
    ctx = require_library(request)
    assert ctx.db is not None and ctx.coordinator is not None
    row = ctx.db.fetchone("SELECT path, source_id FROM documents WHERE id = ?", (document_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    ctx.coordinator.queue_index(row["path"], int(row["source_id"]), force=True)
    return {"ok": True}


@router.post("/documents/{document_id}/probe")
def probe_document(document_id: int, request: Request) -> dict[str, bool]:
    ctx = require_library(request)
    assert ctx.coordinator is not None
    ctx.coordinator.queue_probe(document_id)
    return {"ok": True}


# ----------------------------------------------------------------- encrypted


@router.get("/encrypted")
def list_encrypted(request: Request) -> list[dict[str, Any]]:
    ctx = require_library(request)
    assert ctx.db is not None
    rows = ctx.db.fetchall(
        "SELECT id, name, path, ext, size_bytes, mtime_ns, status, encryption_kind, "
        "error, last_probe_at FROM documents "
        "WHERE status IN ('encrypted', 'encrypted_suspected') ORDER BY mtime_ns DESC"
    )
    return [dict(row) for row in rows]


@router.post("/encrypted/recheck")
def recheck_encrypted(request: Request) -> dict[str, int]:
    ctx = require_library(request)
    assert ctx.db is not None and ctx.coordinator is not None
    rows = ctx.db.fetchall(
        "SELECT id FROM documents WHERE status IN ('encrypted', 'encrypted_suspected')"
    )
    for row in rows:
        ctx.coordinator.queue_probe(int(row["id"]))
    return {"queued": len(rows)}


# ----------------------------------------------------------------- settings


DEFAULT_SETTINGS: dict[str, Any] = {
    "scan_interval_seconds": DEFAULT_SCAN_INTERVAL_SECONDS,
    "encrypted_recheck_seconds": DEFAULT_ENCRYPTED_RECHECK_SECONDS,
}


@router.get("/settings")
def get_settings(request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.db is not None
    values = dict(DEFAULT_SETTINGS)
    for row in ctx.db.fetchall("SELECT key, value FROM settings"):
        values[row["key"]] = row["value"]
    values["library_path"] = str(ctx.library_root) if ctx.library_root else None
    return values


@router.put("/settings")
def put_settings(
    request: Request, body: Annotated[dict[str, Any], Body()]
) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.db is not None
    allowed = set(DEFAULT_SETTINGS)
    with ctx.db.transaction() as conn:
        for key, value in body.items():
            if key not in allowed:
                continue
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
    return get_settings(request)


@router.post("/index/rebuild")
def rebuild_index(request: Request) -> dict[str, int]:
    ctx = require_library(request)
    assert ctx.db is not None and ctx.coordinator is not None
    rows = ctx.db.fetchall("SELECT id, path, source_id FROM documents WHERE status != 'missing'")
    for row in rows:
        ctx.coordinator.queue_index(row["path"], int(row["source_id"]), force=True)
        if row["id"]:
            ctx.coordinator.queue_embed(int(row["id"]))
    return {"queued": len(rows)}


@router.get("/errors")
def list_errors(request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.db is not None and ctx.coordinator is not None
    failed_docs = ctx.db.fetchall(
        "SELECT id, name, path, status, error, mtime_ns FROM documents "
        "WHERE status = 'failed' ORDER BY mtime_ns DESC LIMIT 100"
    )
    return {
        "jobs": ctx.coordinator.queue.errors(),
        "documents": [dict(row) for row in failed_docs],
    }


@router.post("/model/retry")
def retry_model(request: Request) -> dict[str, Any]:
    ctx = require_library(request)
    assert ctx.coordinator is not None
    ctx.coordinator.provider.start_loading()
    queued = ctx.coordinator.requeue_embeddings()
    return {"ok": True, "queued": queued, "state": ctx.coordinator.provider.state}


# --------------------------------------------------------------------- SSE


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    ctx = get_ctx(request)

    async def generator():
        while True:
            if await request.is_disconnected():
                break
            payload = await run_in_threadpool(ctx.status)
            yield f"event: status\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(generator(), media_type="text/event-stream")
