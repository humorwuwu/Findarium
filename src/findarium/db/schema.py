from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    label TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    exclude_globs TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    last_scan_at INTEGER,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    path TEXT NOT NULL UNIQUE,
    path_norm TEXT NOT NULL DEFAULT '',
    rel_path TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    ext TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    mtime_ns INTEGER NOT NULL DEFAULT 0,
    birthtime_ns INTEGER,
    inode INTEGER,
    device INTEGER,
    content_hash TEXT,
    title TEXT,
    author TEXT,
    page_count INTEGER,
    word_count INTEGER,
    sheet_count INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    embedding_status TEXT NOT NULL DEFAULT 'none',
    error TEXT,
    indexed_at INTEGER,
    encryption_kind TEXT,
    last_probe_at INTEGER,
    last_opened_at INTEGER,
    open_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    name_tokens TEXT NOT NULL DEFAULT '',
    title_tokens TEXT NOT NULL DEFAULT '',
    path_tokens TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_path_norm ON documents(path_norm);
CREATE INDEX IF NOT EXISTS idx_documents_inode ON documents(device, inode);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_mtime ON documents(mtime_ns DESC);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    kind TEXT NOT NULL,
    location_label TEXT,
    location_json TEXT,
    heading_path TEXT,
    text TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, ordinal);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    body_tokens,
    document_id UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    name_tokens,
    title_tokens,
    path_tokens,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS chunk_vectors (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS doc_vectors (
    document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS doc_keywords (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    weight REAL NOT NULL,
    PRIMARY KEY (document_id, keyword)
);

CREATE TABLE IF NOT EXISTS document_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    href TEXT NOT NULL,
    target_path TEXT,
    target_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    UNIQUE(from_document_id, href)
);

CREATE INDEX IF NOT EXISTS idx_links_target_path ON document_links(target_path);
CREATE INDEX IF NOT EXISTS idx_links_target_doc ON document_links(target_document_id);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL DEFAULT '{}',
    state TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    not_before REAL NOT NULL DEFAULT 0,
    started_at REAL,
    last_error TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(state, not_before, priority DESC, id);
CREATE INDEX IF NOT EXISTS idx_jobs_kind ON jobs(kind, state);

CREATE TABLE IF NOT EXISTS search_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    normalized_query TEXT,
    clicked_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    action TEXT NOT NULL DEFAULT 'click',
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_events_created ON search_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_events_query ON search_events(normalized_query);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


MIGRATIONS: list[str] = [
    # v1 is the initial schema. Future migrations append SQL strings here.
]


def current_schema_version() -> int:
    return SCHEMA_VERSION
