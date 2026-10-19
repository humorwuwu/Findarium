from __future__ import annotations

import fnmatch
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import (
    DEFAULT_ENCRYPTED_RECHECK_SECONDS,
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_FILE_PATTERNS,
    SUPPORTED_EXTENSIONS,
)
from ..db import Database
from ..db.ops import mark_document_missing, now_ts
from ..paths import LibraryPaths

logger = logging.getLogger(__name__)


@dataclass
class ScanReport:
    source_id: int
    discovered: int = 0
    queued: int = 0
    missing: int = 0
    probes: int = 0
    errors: list[str] = field(default_factory=list)
    unavailable: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "discovered": self.discovered,
            "queued": self.queued,
            "missing": self.missing,
            "probes": self.probes,
            "errors": self.errors,
            "unavailable": self.unavailable,
        }


class Scanner:
    def __init__(
        self,
        db: Database,
        library_paths: LibraryPaths,
        *,
        on_index: Callable[[str, int, bool], None],
        on_probe: Callable[[int], None],
    ):
        self.db = db
        self.library_paths = library_paths
        self.on_index = on_index
        self.on_probe = on_probe
        self._self_exclusions = [
            Path(p) for p in library_paths.self_exclusions()
        ]

    # --------------------------------------------------------------- scanning

    def scan_source(self, source_id: int) -> ScanReport:
        report = ScanReport(source_id=source_id)
        source = self.db.fetchone("SELECT * FROM sources WHERE id = ?", (source_id,))
        if source is None or not source["enabled"]:
            report.unavailable = True
            return report
        root = Path(source["path"])
        if not root.is_dir():
            report.unavailable = True
            report.errors.append("来源目录不可用，未清理已有索引")
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE sources SET last_error = ? WHERE id = ?",
                    ("来源目录不可用", source_id),
                )
            return report

        exclude_patterns = [
            item.strip()
            for item in (source["exclude_globs"] or "").replace(";", "\n").splitlines()
            if item.strip()
        ]

        rows = self.db.fetchall(
            "SELECT id, path, size_bytes, mtime_ns, status, last_probe_at, device, inode "
            "FROM documents WHERE source_id = ?",
            (source_id,),
        )
        by_path = {row["path"]: row for row in rows}
        by_inode: dict[tuple[int, int], Any] = {}
        for row in rows:
            if row["inode"] is not None:
                by_inode.setdefault((row["device"], row["inode"]), row)

        seen: set[str] = set()
        walk_errors: list[str] = []

        def onerror(exc: OSError) -> None:
            walk_errors.append(str(exc))

        for current_dir, dirnames, filenames in os.walk(
            root, topdown=True, followlinks=False, onerror=onerror
        ):
            current = Path(current_dir)
            dirnames[:] = [
                name
                for name in dirnames
                if not self._skip_dir(current / name, name)
                and not self._matches_exclude(current / name, root, exclude_patterns)
            ]
            for filename in filenames:
                path = current / filename
                if self._skip_file(path, filename, exclude_patterns, root):
                    continue
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                report.discovered += 1
                try:
                    stat = path.stat()
                except OSError as exc:
                    report.errors.append(f"{path}: {exc}")
                    continue
                path_string = str(path)
                seen.add(path_string)
                row = by_path.get(path_string)
                if row is not None:
                    changed = (
                        int(row["size_bytes"]) != stat.st_size
                        or int(row["mtime_ns"]) != stat.st_mtime_ns
                    )
                    if changed or row["status"] in ("pending", "failed", "missing"):
                        self.on_index(path_string, source_id, False)
                        report.queued += 1
                    elif row["status"] in ("encrypted", "encrypted_suspected"):
                        last = int(row["last_probe_at"] or 0)
                        if now_ts() - last >= self._probe_interval():
                            self.on_probe(int(row["id"]))
                            report.probes += 1
                    continue
                inode_key = (stat.st_dev, stat.st_ino)
                if inode_key in by_inode:
                    # Rename/move detected; pipeline will update the existing row.
                    self.on_index(path_string, source_id, False)
                    report.queued += 1
                else:
                    self.on_index(path_string, source_id, False)
                    report.queued += 1

        # Do not purge when the walk had errors: a permission failure must never
        # delete a user's index.
        if not walk_errors:
            for path_string, row in by_path.items():
                if path_string in seen:
                    continue
                if row["status"] == "missing":
                    continue
                mark_document_missing(self.db.connection, int(row["id"]))
                report.missing += 1
        else:
            report.errors.extend(walk_errors[:10])

        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE sources SET last_scan_at = ?, last_error = ? WHERE id = ?",
                (now_ts(), "; ".join(report.errors[:3]) if report.errors else None, source_id),
            )
        return report

    # --------------------------------------------------------------- helpers

    def _probe_interval(self) -> int:
        row = self.db.fetchone(
            "SELECT value FROM settings WHERE key = 'encrypted_recheck_seconds'"
        )
        if row is None:
            return DEFAULT_ENCRYPTED_RECHECK_SECONDS
        try:
            return max(60, int(row["value"]))
        except (TypeError, ValueError):
            return DEFAULT_ENCRYPTED_RECHECK_SECONDS

    def _skip_dir(self, path: Path, name: str) -> bool:
        if name.startswith("."):
            return True
        if name in DEFAULT_EXCLUDED_DIRS:
            return True
        if name.endswith((".app", ".bundle", ".framework", ".xcodeproj")):
            return True
        if path.is_symlink():
            return True
        return self._is_self_path(path)

    def _skip_file(
        self, path: Path, name: str, exclude_patterns: list[str], root: Path
    ) -> bool:
        if name.startswith("."):
            return True
        if path.is_symlink():
            return True
        for pattern in DEFAULT_EXCLUDED_FILE_PATTERNS:
            if fnmatch.fnmatch(name, pattern):
                return True
        if self._is_self_path(path):
            return True
        return self._matches_exclude(path, root, exclude_patterns)

    def _matches_exclude(self, path: Path, root: Path, patterns: list[str]) -> bool:
        if not patterns:
            return False
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        return any(
            fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern)
            for pattern in patterns
        )

    def _is_self_path(self, path: Path) -> bool:
        path_string = str(path)
        for exclusion in self._self_exclusions:
            exclusion_string = str(exclusion)
            if path_string == exclusion_string:
                return True
            if path_string.startswith(exclusion_string + os.sep):
                return True
            # Prune the parent of the library folder when walking from above it.
            if exclusion_string.startswith(path_string + os.sep):
                return True
        return False
