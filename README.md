<img src="packaging/icon.png" alt="Findarium" width="120" align="right" />

# Findarium / 寻册

A local-first macOS desktop document indexer with Chinese-friendly full-text and semantic search.

## Features

- Add folders; PDF, DOCX, XLSX, PPTX, Markdown, TXT, CSV and HTML are extracted and indexed.
- **Single SQLite library** stored in a folder you choose on first run. It contains the extracted
  text, FTS5 indexes, local semantic vectors, jobs, settings and search history. The app-support
  directory only holds a small pointer file.
- Chinese search uses overlapping CJK bigrams (so two-character words and substrings work well),
  plus a local `BAAI/bge-small-zh-v1.5` semantic index, fuzzy filename matching, recency weighting
  and local click feedback.
- Results show highlighted snippets, PDF page / Excel sheet / PPT slide / heading locations,
  related documents with explanations, and an interactive relation graph.
- Encrypted or protected files (for example from a company encryption client) are **marked only**:
  their filenames and paths stay searchable, but no content or vectors are stored. Watcher events
  and a periodic recheck detect when a file becomes readable and index it then. The app never tries
  to decrypt, crack or bypass encryption.
- Startup scan, real-time FSEvents watcher, and a periodic reconciliation sweep keep the index fresh.
- Native window via pywebview; open files and reveal them in Finder from the results.

## Development

```bash
uv sync
cd frontend && npm install && npm run build
cd ..
uv run findarium
```

For UI development with hot reload:

```bash
./scripts/dev.sh
```

Headless backend (useful for API work):

```bash
uv run findarium --headless --library /tmp/findarium-dev --no-embedding
```

Run checks:

```bash
uv run ruff check src tests
uv run pytest
cd frontend && npm run typecheck && npm run build
```

## Packaging

Double-clickable app bundle (onedir, faster startup — recommended):

```bash
./scripts/build.sh
open dist/Findarium.app
```

Single-file executable (onefile, one Mach-O file, slower first start because it extracts to a
temporary directory):

```bash
./scripts/build-onefile.sh
./dist-onefile/Findarium                      # opens the desktop window
./dist-onefile/Findarium --headless --port 8811 --library ~/MaterialIndex
```

PyInstaller produces unsigned/ad-hoc builds for local use. Distributing them to other Macs
requires Developer ID signing and notarization.

## Data

By default the index library is created next to the program:

- `dist/FindariumData/` next to `dist/Findarium.app`
- `dist-onefile/FindariumData/` next to the single-file executable
- `./FindariumData/` when running from a source checkout

It contains the only database, `index.sqlite3`, plus `backups/`, `models/` and `logs/`. If the
program directory is not writable (for example an app in a system-managed location), the app falls
back to `~/Library/Application Support/Findarium/data` and says so in the UI. A small pointer file
in `~/Library/Application Support/Findarium/bootstrap.json` remembers a user-chosen location if you
move the library from Settings.

Do not place the library in iCloud/Dropbox-style sync folders (WAL files can be corrupted by sync)
or in a folder that a company encryption client encrypts.

## Adaptive indexing

Indexing uses a small worker pool that scales with the machine:

- More extraction workers when the load average and this process's CPU usage are low.
- Back down to one worker when the machine is busy, so other apps stay responsive.
- Semantic embedding runs on its own worker and shrinks its batch size under load, so vector
  backfill never blocks text indexing.

The current worker count, load ratio and embedding batch are visible in the status bar and Settings.

## Known limitations

- No OCR for scanned PDFs; such files are marked as partial and searchable by filename only.
- No legacy `.doc` / `.xls` support.
- Word/Excel/PPT previews show extracted text and locations rather than pixel-perfect layout;
  use the “Open” action for full fidelity.
- PyMuPDF is AGPL-licensed. This project is intended as a personal local tool. If you distribute
  it, review the PyMuPDF license or replace the PDF extractor (for example with pypdf/pdfplumber).

## License

No license is granted yet — this is a personal project. Note that the PDF extractor depends on
PyMuPDF (AGPL-3.0), so any distribution needs its license reviewed first.
