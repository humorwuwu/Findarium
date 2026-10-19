#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

(cd frontend && npm run dev) &
VITE_PID=$!
trap 'kill $VITE_PID 2>/dev/null || true' EXIT

sleep 2
FINDARIUM_DEV_URL=http://127.0.0.1:5173 uv run findarium "$@"
