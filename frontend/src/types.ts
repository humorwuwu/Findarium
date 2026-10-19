export interface DocumentSummary {
  id: number;
  name: string;
  path: string;
  rel_path?: string | null;
  source_id?: number | null;
  ext: string;
  status: string;
  size_bytes: number;
  mtime_ns: number;
  birthtime_ns: number;
  mtime?: string | null;
  birthtime?: string | null;
  title: string | null;
  author: string | null;
  page_count: number | null;
  word_count: number | null;
  sheet_count: number | null;
  embedding_status: string;
  error: string | null;
  encryption_kind: string | null;
  open_count: number;
  last_opened_at: number | null;
  indexed_at?: number | null;
  last_probe_at?: number | null;
}

export interface MatchSpan {
  start: number;
  end: number;
}

export interface SearchMatch {
  chunk_id: number;
  source: string;
  location_label: string | null;
  location_json: Record<string, unknown>;
  snippet: string;
  spans: number[][];
  matched: boolean;
}

export interface RelatedDocument extends DocumentSummary {
  score: number;
  reasons: string[];
}

export interface SearchItem {
  document_id: number;
  score: number;
  relevance: number;
  channels: string[];
  tags: string[];
  matches: SearchMatch[];
  related: RelatedDocument[];
  document: DocumentSummary;
}

export interface SearchResponse {
  query: string;
  content_query?: string;
  explanation: string[];
  filters: Record<string, unknown>;
  items: SearchItem[];
  total: number;
  elapsed_ms: number;
  semantic_ready: boolean;
}

export interface Source {
  id: number;
  path: string;
  label: string | null;
  enabled: number;
  exclude_globs: string;
  created_at: number;
  last_scan_at: number | null;
  last_error: string | null;
  document_count: number;
  encrypted_count: number;
  failed_count: number;
}

export interface AppStatus {
  library: {
    ready: boolean;
    path: string | null;
    available: boolean;
    database: string | null;
    fallback?: boolean;
    program_dir?: string;
  };
  sources: number;
  documents: number;
  encrypted: number;
  failed: number;
  indexing: number;
  semantic_ready: boolean;
  embedding_state: string;
  embedding_error?: string | null;
  embedding_model?: string;
  embedding_ready?: number;
  embedding_pending?: number;
  embedding_failed?: number;
  pending?: number;
  running?: number;
  current?: { kind: string; payload: Record<string, unknown> } | null;
  workers?: { max: number; desired: number; active: number };
  load_ratio?: number;
  process_cpu?: number;
  embedding_batch?: number;
}

export interface Chunk {
  id: number;
  ordinal: number;
  kind: string;
  location_label: string | null;
  location_json: Record<string, unknown>;
  heading_path: string[];
  text: string;
  char_start: number | null;
  char_end: number | null;
}

export interface DocumentDetail extends DocumentSummary {
  warnings: string[];
  metadata: Record<string, unknown>;
  keywords: { keyword: string; weight: number }[];
  chunks: Chunk[];
  related: RelatedDocument[];
}

export interface GraphData {
  nodes: {
    id: number;
    label: string;
    ext: string;
    status: string;
    center: boolean;
  }[];
  edges: {
    source: number;
    target: number;
    score: number;
    reason: string;
  }[];
}

export interface EncryptedDocument {
  id: number;
  name: string;
  path: string;
  ext: string;
  size_bytes: number;
  mtime_ns: number;
  status: string;
  encryption_kind: string | null;
  error: string | null;
  last_probe_at: number | null;
}
