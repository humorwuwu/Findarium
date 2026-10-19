from __future__ import annotations

from typing import Any

from ..db import Database
from .query import SearchFilters

VISIBLE_STATUSES = (
    "indexed",
    "indexed_partial",
    "encrypted",
    "encrypted_suspected",
    "failed",
)


def build_filter_sql(filters: SearchFilters) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if filters.extensions:
        placeholders = ", ".join("?" for _ in filters.extensions)
        clauses.append(f"d.ext IN ({placeholders})")
        params.extend(filters.extensions)
    if filters.after is not None:
        column = "d.birthtime_ns" if filters.date_field == "created" else "d.mtime_ns"
        clauses.append(f"{column} >= ?")
        params.append(int(filters.after) * 1_000_000_000)
    if filters.before is not None:
        column = "d.birthtime_ns" if filters.date_field == "created" else "d.mtime_ns"
        clauses.append(f"{column} <= ?")
        params.append(int(filters.before) * 1_000_000_000)
    if filters.folder:
        clauses.append("(d.rel_path LIKE ? OR d.path LIKE ?)")
        pattern = f"%{filters.folder}%"
        params.extend([pattern, pattern])
    if filters.encrypted == "only":
        clauses.append("d.status IN ('encrypted', 'encrypted_suspected')")
    elif filters.encrypted == "exclude":
        clauses.append("d.status NOT IN ('encrypted', 'encrypted_suspected')")
    if filters.size_min is not None:
        clauses.append("d.size_bytes >= ?")
        params.append(filters.size_min)
    if filters.size_max is not None:
        clauses.append("d.size_bytes <= ?")
        params.append(filters.size_max)
    return (" AND ".join(clauses), params)


def visible_status_sql(alias: str = "d") -> str:
    placeholders = ", ".join("?" for _ in VISIBLE_STATUSES)
    return f"{alias}.status IN ({placeholders})"


def search_chunks(
    db: Database,
    match_query: str,
    filters: SearchFilters,
    limit: int = 200,
) -> list[dict[str, Any]]:
    filter_sql, filter_params = build_filter_sql(filters)
    where = [f"{visible_status_sql('d')}", "chunks_fts MATCH ?"]
    params: list[Any] = list(VISIBLE_STATUSES)
    params.append(match_query)
    if filter_sql:
        where.append(filter_sql)
        params.extend(filter_params)
    sql = (
        "SELECT c.id AS chunk_id, c.document_id, c.ordinal, c.kind, c.text, "
        "c.location_label, c.location_json, c.heading_path, bm25(chunks_fts) AS rank "
        "FROM chunks_fts "
        "JOIN chunks c ON c.id = chunks_fts.rowid "
        "JOIN documents d ON d.id = c.document_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY rank LIMIT ?"
    )
    params.append(limit)
    try:
        rows = db.fetchall(sql, params)
    except Exception:
        return []
    return [dict(row) for row in rows]


def search_documents(
    db: Database,
    match_query: str,
    filters: SearchFilters,
    limit: int = 120,
) -> list[dict[str, Any]]:
    filter_sql, filter_params = build_filter_sql(filters)
    where = [f"{visible_status_sql('d')}", "documents_fts MATCH ?"]
    params: list[Any] = list(VISIBLE_STATUSES)
    params.append(match_query)
    if filter_sql:
        where.append(filter_sql)
        params.extend(filter_params)
    sql = (
        "SELECT d.id AS document_id, bm25(documents_fts) AS rank "
        "FROM documents_fts "
        "JOIN documents d ON d.id = documents_fts.rowid "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY rank LIMIT ?"
    )
    params.append(limit)
    try:
        rows = db.fetchall(sql, params)
    except Exception:
        return []
    return [dict(row) for row in rows]


def recent_documents(
    db: Database, filters: SearchFilters, limit: int = 30
) -> list[dict[str, Any]]:
    filter_sql, filter_params = build_filter_sql(filters)
    where = [visible_status_sql("d")]
    if filter_sql:
        where.append(filter_sql)
    order = "d.birthtime_ns DESC" if filters.sort == "created" else "d.mtime_ns DESC"
    sql = (
        "SELECT d.* FROM documents d "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY {order} LIMIT ?"
    )
    params = list(VISIBLE_STATUSES) + filter_params + [limit]
    rows = db.fetchall(sql, params)
    return [dict(row) for row in rows]


def documents_by_ids(db: Database, document_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not document_ids:
        return {}
    placeholders = ", ".join("?" for _ in document_ids)
    rows = db.fetchall(
        f"SELECT * FROM documents WHERE id IN ({placeholders})", document_ids
    )
    return {int(row["id"]): dict(row) for row in rows}


def chunks_for_document(
    db: Database, document_id: int, limit: int = 200
) -> list[dict[str, Any]]:
    rows = db.fetchall(
        "SELECT id, ordinal, kind, location_label, location_json, heading_path, text, "
        "char_start, char_end FROM chunks WHERE document_id = ? ORDER BY ordinal LIMIT ?",
        (document_id, limit),
    )
    return [dict(row) for row in rows]


def chunk_by_id(db: Database, chunk_id: int) -> dict[str, Any] | None:
    row = db.fetchone("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
    return dict(row) if row else None
