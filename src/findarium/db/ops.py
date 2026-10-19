from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any


def now_ts() -> int:
    return int(datetime.now(UTC).timestamp())


def upsert_document_file_fts(
    conn: sqlite3.Connection,
    document_id: int,
    *,
    name_tokens: str,
    title_tokens: str,
    path_tokens: str,
) -> None:
    conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (document_id,))
    conn.execute(
        "INSERT INTO documents_fts(rowid, name_tokens, title_tokens, path_tokens) "
        "VALUES (?, ?, ?, ?)",
        (document_id, name_tokens, title_tokens, path_tokens),
    )


def delete_document_file_fts(conn: sqlite3.Connection, document_id: int) -> None:
    conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (document_id,))


def delete_document_content(
    conn: sqlite3.Connection,
    document_id: int,
    *,
    include_file_fts: bool = False,
) -> None:
    """Remove all content-derived rows for a document, keeping its metadata row."""
    chunk_ids = [
        int(row[0])
        for row in conn.execute(
            "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
        ).fetchall()
    ]
    for chunk_id in chunk_ids:
        conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (chunk_id,))
    # chunk_vectors are removed by the foreign-key cascade when chunks are deleted.
    conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM doc_vectors WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM doc_keywords WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM document_links WHERE from_document_id = ?", (document_id,))
    if include_file_fts:
        delete_document_file_fts(conn, document_id)


def delete_document(conn: sqlite3.Connection, document_id: int) -> None:
    delete_document_content(conn, document_id, include_file_fts=True)
    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


def mark_document_missing(conn: sqlite3.Connection, document_id: int) -> None:
    delete_document_content(conn, document_id, include_file_fts=True)
    conn.execute(
        "UPDATE documents SET status = 'missing', embedding_status = 'none', "
        "error = NULL, encryption_kind = NULL, indexed_at = NULL WHERE id = ?",
        (document_id,),
    )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
