from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def open_path(path: str | Path) -> bool:
    try:
        subprocess.run(["/usr/bin/open", str(path)], check=False, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("open failed: %s", exc)
        return False


def reveal_path(path: str | Path) -> bool:
    try:
        subprocess.run(["/usr/bin/open", "-R", str(path)], check=False, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("reveal failed: %s", exc)
        return False


def open_privacy_settings() -> bool:
    url = (
        "x-apple.systempreferences:com.apple.preference.security?"
        "Privacy_AllFiles"
    )
    try:
        subprocess.run(["/usr/bin/open", url], check=False, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def choose_folder_via_osascript(prompt: str = "选择文件夹") -> str | None:
    script = f'POSIX path of (choose folder with prompt "{prompt}")'
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = (result.stdout or "").strip()
    if result.returncode != 0 or not path:
        return None
    return str(Path(path).expanduser().resolve())
