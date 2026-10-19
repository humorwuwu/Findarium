#!/usr/bin/env bash
# Restore a working checkout on a fresh machine (or after `scripts/clean.sh`).
#
# Installs the Python environment from uv.lock, the frontend dependencies from
# package-lock.json, and builds the UI that the backend serves.
set -euo pipefail

cd "$(dirname "$0")/.."

uv sync --all-groups
(cd frontend && npm ci && npm run build)

echo
echo "Ready. Start the app with:"
echo "  uv run findarium              # desktop window"
echo "  ./scripts/dev.sh              # Vite dev server + window"
