#!/usr/bin/env bash
# Remove everything that can be regenerated, so the folder stays small enough
# to sync between machines. Source, tests, lock files and packaging assets stay.
#
# Restore afterwards with ./scripts/setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."

before=$(du -sh . | cut -f1)

rm -rf \
  dist dist-onefile build build-onefile \
  .venv \
  frontend/node_modules frontend/dist frontend/.vite \
  .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov

find . -name '__pycache__' -type d -not -path './.git/*' -prune -exec rm -rf {} +
find . -name '.DS_Store' -delete 2>/dev/null || true

after=$(du -sh . | cut -f1)
echo "cleaned: $before -> $after"
echo "restore with: ./scripts/setup.sh"
