#!/usr/bin/env bash
# 阶段结束后清掉编译中间产物。默认保留 .venv、frontend/node_modules 和 release/。
#
#   ./scripts/clean.sh            # 中间产物、缓存、PyInstaller 工作目录
#   ./scripts/clean.sh --deep     # 再删 .venv 和 node_modules（换机器同步前用这个）
#   ./scripts/clean.sh --dry-run
#
# 不删 release/（可运行产物和旁边的 FindariumData 索引库）。
set -euo pipefail

cd "$(dirname "$0")/.."

DRY=0
DEEP=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --deep) DEEP=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "未知参数：$arg" >&2; exit 2 ;;
  esac
done

before=$(du -sh . | cut -f1)
remove() {
  for path in "$@"; do
    [ -e "$path" ] || continue
    echo "  $path"
    [ "$DRY" = "1" ] || rm -rf "$path"
  done
}

echo "中间产物："
remove \
  dist dist-onefile build build-onefile \
  frontend/dist frontend/.vite \
  .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov

if [ "$DEEP" = "1" ]; then
  echo "开发依赖："
  remove .venv frontend/node_modules
fi

if [ "$DRY" = "0" ]; then
  find . -name '__pycache__' -type d -not -path './.git/*' -prune -exec rm -rf {} +
  find . -name '.DS_Store' -not -path './.git/*' -delete 2>/dev/null || true
  find . -name '*sync-conflict*' -not -path './.git/*' -delete 2>/dev/null || true
fi

after=$(du -sh . | cut -f1)
echo "cleaned: $before -> $after"
echo "保留：release/、源码、锁文件。恢复开发环境：./scripts/setup.sh"
