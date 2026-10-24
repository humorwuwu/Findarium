#!/usr/bin/env bash
# 打包 onedir .app。PyInstaller 的 dist/、build/ 只是中间目录，
# 可运行产物落到 release/macos/，中间目录随即删掉。
set -euo pipefail

cd "$(dirname "$0")/.."

(cd frontend && npm install && npm run build)

rm -rf build/pyinstaller build/pyinstaller-dist
uv run pyinstaller --noconfirm \
  --distpath build/pyinstaller-dist \
  --workpath build/pyinstaller \
  packaging/Findarium.spec

mkdir -p release/macos
rm -rf "release/macos/Findarium.app"
mv build/pyinstaller-dist/Findarium.app release/macos/
rm -rf build/pyinstaller build/pyinstaller-dist dist build
echo "Built: release/macos/Findarium.app"
