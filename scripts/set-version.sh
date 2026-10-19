#!/usr/bin/env bash
# Stamp one version number into every file that carries its own copy.
#
#   ./scripts/set-version.sh 0.2.0
#
# pyproject.toml, src/findarium/__init__.py, frontend/package.json (and its
# lock file, which `npm ci` compares against package.json) and the macOS bundle
# version in packaging/Findarium.spec all have to agree, so the release workflow
# runs this from the pushed tag instead of editing them by hand.
set -euo pipefail

cd "$(dirname "$0")/.."

version="${1:-}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]]; then
  echo "usage: $0 <major.minor.patch> (got: '${version}')" >&2
  exit 2
fi

python3 - "$version" <<'PY'
import json
import re
import sys
from pathlib import Path

version = sys.argv[1]


def sub(path: str, pattern: str, replacement: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"{path}: no line matched {pattern!r}")
    file.write_text(updated, encoding="utf-8")


sub("pyproject.toml", r'^version = ".*"$', f'version = "{version}"')
sub("src/findarium/__init__.py", r'^__version__ = ".*"$', f'__version__ = "{version}"')
sub("packaging/Findarium.spec", r'^        "CFBundleShortVersionString": ".*",$',
    f'        "CFBundleShortVersionString": "{version}",')

# The lock file records the package version twice: once at the root and once
# under packages[""]. A mismatch makes `npm ci` refuse to install.
lock = Path("frontend/package-lock.json")
data = json.loads(lock.read_text(encoding="utf-8"))
data["version"] = version
data["packages"][""]["version"] = version
lock.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

pkg = Path("frontend/package.json")
data = json.loads(pkg.read_text(encoding="utf-8"))
data["version"] = version
pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

echo "version -> $version"
