#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

(cd frontend && npm install && npm run build)
rm -rf build-onefile dist-onefile
uv run pyinstaller --noconfirm --clean \
  --distpath dist-onefile \
  --workpath build-onefile \
  packaging/Findarium-onefile.spec
echo "Built: dist-onefile/Findarium"
