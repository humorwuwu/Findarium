from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

APP_NAME = "Findarium"
BUNDLE_ID = "com.findarium.desktop"
DEFAULT_LIBRARY_DIRNAME = "FindariumData"

BOOTSTRAP_DIR = Path(user_data_dir(APP_NAME, appauthor=False))
BOOTSTRAP_FILE = BOOTSTRAP_DIR / "bootstrap.json"


def load_bootstrap() -> dict[str, Any]:
    try:
        return json.loads(BOOTSTRAP_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_bootstrap(data: dict[str, Any]) -> None:
    BOOTSTRAP_DIR.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="bootstrap-", suffix=".json", dir=BOOTSTRAP_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(name, BOOTSTRAP_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def bootstrap_library_path() -> Path | None:
    raw = load_bootstrap().get("library_path")
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def remember_library(path: Path) -> None:
    save_bootstrap({"library_path": str(path.expanduser().resolve())})


def application_dir() -> Path:
    """Directory that contains the running program.

    For a macOS ``.app`` bundle this is the folder that contains the ``.app``
    (not the read-only bundle interior); for a single-file executable it is the
    folder containing the executable; for a source checkout it is the project
    root.
    """
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        parts = executable.parts
        if len(parts) >= 4 and parts[-3] == "Contents" and parts[-2] == "MacOS":
            return Path(*parts[:-4])
        return executable.parent
    return Path(__file__).resolve().parents[2]


def fallback_library_path() -> Path:
    return Path(user_data_dir(APP_NAME, appauthor=False)) / "data"


def default_library_path() -> tuple[Path, bool]:
    """Return the default library folder and whether the fallback was used.

    Default: ``<program directory>/FindariumData``. If that location is not
    writable (for example an app installed in a system-managed location), fall
    back to ``~/Library/Application Support/Findarium/data``.
    """
    candidate = application_dir() / DEFAULT_LIBRARY_DIRNAME
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return candidate, False
    except OSError:
        fallback = fallback_library_path()
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback, True


class LibraryPaths:
    """All application data that lives inside the user-selected library folder."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.database = self.root / "index.sqlite3"
        self.backups = self.root / "backups"
        self.models = self.root / "models"
        self.logs = self.root / "logs"

    def create(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for directory in (self.backups, self.models, self.logs):
            directory.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        try:
            return self.root.is_dir() and os.access(self.root, os.R_OK | os.W_OK)
        except OSError:
            return False

    def self_exclusions(self) -> list[str]:
        """Absolute paths that must never be indexed if the library is inside a source."""
        paths = [str(self.root)]
        for candidate in (self.database, self.backups, self.models, self.logs):
            paths.append(str(candidate))
        return paths
