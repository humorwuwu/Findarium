from __future__ import annotations

# Shown as the native window title, so it carries both names.
APP_TITLE = "Findarium · 寻册"
DEFAULT_WINDOW_SIZE = (1320, 860)
MIN_WINDOW_SIZE = (980, 640)

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".md",
    ".markdown",
    ".txt",
    ".csv",
    ".html",
    ".htm",
}

EXT_GROUPS: dict[str, set[str]] = {
    "pdf": {".pdf"},
    "word": {".docx"},
    "excel": {".xlsx"},
    "ppt": {".pptx"},
    "markdown": {".md", ".markdown"},
    "text": {".txt", ".csv"},
    "html": {".html", ".htm"},
}

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "Library",
    ".Trash",
    "Trashes",
    "System",
    "Applications",
    ".Spotlight-V100",
    ".fseventsd",
    ".TemporaryItems",
    "Findarium",
}

DEFAULT_EXCLUDED_FILE_PATTERNS = [
    "~$*",
    ".~lock.*",
    "._*",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.tmp",
    "*.temp",
    "*.swp",
]

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TEXT_CHARS = 5_000_000
MAX_CHUNK_CHARS = 560
MIN_CHUNK_CHARS = 80
CHUNK_OVERLAP_CHARS = 70
MAX_EXCEL_ROWS_PER_SHEET = 25_000
MAX_EXCEL_ROWS_PER_CHUNK = 35
MAX_CSV_ROWS = 100_000
MAX_CSV_ROWS_PER_CHUNK = 30

DEFAULT_SCAN_INTERVAL_SECONDS = 600
DEFAULT_ENCRYPTED_RECHECK_SECONDS = 600
ENCRYPTED_RECHECK_BATCH = 50
WATCH_DEBOUNCE_SECONDS = 2.0
FILE_STABILITY_SECONDS = 2.0
MAX_JOB_ATTEMPTS = 3
SEARCH_LIMIT = 30
CHUNK_CANDIDATE_LIMIT = 200
DOCUMENT_CANDIDATE_LIMIT = 120
SEMANTIC_CANDIDATE_LIMIT = 120
FUZZY_TITLE_LIMIT = 30
FUZZY_THRESHOLD = 68.0

EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIM = 512
EMBEDDING_BATCH_SIZE = 16
EMBEDDING_THREADS_MAX = 4

# Adaptive indexing: more parallel extractors when the machine is idle, fewer
# when the load average or this process's CPU usage is high.
ADAPTIVE_SAMPLE_SECONDS = 2.0
ADAPTIVE_MAX_WORKERS = 4
ADAPTIVE_HIGH_LOAD_RATIO = 0.85
ADAPTIVE_BUSY_LOAD_RATIO = 0.55
ADAPTIVE_HIGH_PROCESS_CPU = 0.90
ADAPTIVE_BUSY_PROCESS_CPU = 0.70
ADAPTIVE_BACKLOG_LARGE = 40
ADAPTIVE_BACKLOG_MEDIUM = 8
EMBEDDING_BATCH_MIN = 4
EMBEDDING_BATCH_MAX = 32

FTS_TOKENIZE = "unicode61 remove_diacritics 2"
