#!/usr/bin/env bash
# 打包单文件可执行版本。中间目录用完即删，成品进 release/macos/。
set -euo pipefail

cd "$(dirname "$0")/.."

(cd frontend && npm install && npm run build)
VERSION="$(grep -m1 '^version' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')"
ARCH="$(uname -m)"
OUT="release/macos/Findarium-${VERSION}-macos-${ARCH}-onefile"

rm -rf build/onefile build/onefile-dist
uv run pyinstaller --noconfirm --clean \
  --distpath build/onefile-dist \
  --workpath build/onefile \
  packaging/Findarium-onefile.spec

mkdir -p release/macos
mv build/onefile-dist/Findarium "$OUT"
chmod +x "$OUT"
rm -rf build/onefile build/onefile-dist dist-onefile build-onefile
echo "Built: $OUT"
