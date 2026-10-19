from __future__ import annotations

import logging
import logging.handlers
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from .db import Database
from .events import EventBus
from .indexing.coordinator import IndexCoordinator
from .paths import (
    LibraryPaths,
    application_dir,
    bootstrap_library_path,
    default_library_path,
    remember_library,
)
from .search.related import RelatedService
from .search.service import SearchService

logger = logging.getLogger(__name__)


class LibraryError(RuntimeError):
    pass


class AppContext:
    """Holds the currently attached library and its services."""

    def __init__(self) -> None:
        self.events = EventBus()
        self.library_root: Path | None = None
        self.paths: LibraryPaths | None = None
        self.db: Database | None = None
        self.coordinator: IndexCoordinator | None = None
        self.search: SearchService | None = None
        self.related: RelatedService | None = None
        self._lock = threading.RLock()
        self._log_handler: logging.Handler | None = None
        self.used_fallback = False

    # ------------------------------------------------------------- lifecycle

    @property
    def ready(self) -> bool:
        return self.db is not None and self.coordinator is not None and self.search is not None

    def attach(
        self,
        root: Path,
        *,
        embedding_enabled: bool = True,
        remember: bool = False,
    ) -> None:
        root = root.expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise LibraryError("索引库位置必须是一个文件夹")
        paths = LibraryPaths(root)
        try:
            paths.create()
        except OSError as exc:
            raise LibraryError(f"无法创建索引库目录：{exc}") from exc
        if not os.access(paths.root, os.R_OK | os.W_OK):
            raise LibraryError("索引库目录不可读写")
        with self._lock:
            self.detach()
        self._install_file_logging(paths)

        db = Database(paths.database)
        try:
            db.initialize(paths.backups)
        except Exception:
            db.close()
            raise

        coordinator = IndexCoordinator(db, paths, embedding_enabled=embedding_enabled)
        related = RelatedService(db, coordinator.doc_index, coordinator.provider)
        search = SearchService(db, coordinator.provider, coordinator.chunk_index, related)

        with self._lock:
            self.library_root = paths.root
            self.paths = paths
            self.db = db
            self.coordinator = coordinator
            self.related = related
            self.search = search
            self.used_fallback = False
        coordinator.start()
        if remember:
            remember_library(paths.root)
        logger.info("library attached: %s", paths.root)

    def _install_file_logging(self, paths: LibraryPaths) -> None:
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler.close()
            self._log_handler = None
        try:
            handler = logging.handlers.RotatingFileHandler(
                paths.logs / "findarium.log",
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
        except OSError:
            return
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(handler)
        self._log_handler = handler

    def detach(self) -> None:
        if self.coordinator is not None:
            try:
                self.coordinator.stop()
            except Exception:
                logger.exception("failed to stop coordinator")
        if self.db is not None:
            try:
                self.db.checkpoint()
                self.db.close()
            except Exception:
                logger.exception("failed to close database")
        self.coordinator = None
        self.db = None
        self.search = None
        self.related = None
        self.paths = None
        self.library_root = None
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler.close()
            self._log_handler = None

    def attach_from_bootstrap(self, *, embedding_enabled: bool = True) -> bool:
        root = bootstrap_library_path()
        if root is None or not root.exists():
            return False
        try:
            self.attach(root, embedding_enabled=embedding_enabled)
            return True
        except Exception:
            logger.exception("cannot attach bootstrap library")
            return False

    def attach_default(self, *, embedding_enabled: bool = True) -> bool:
        """Attach the remembered library, or create the default one.

        Default location is ``<program directory>/FindariumData``; if that is
        not writable the app falls back to application support and records that
        so the UI can explain it.
        """
        if self.attach_from_bootstrap(embedding_enabled=embedding_enabled):
            return True
        try:
            root, used_fallback = default_library_path()
            self.attach(root, embedding_enabled=embedding_enabled)
            self.used_fallback = used_fallback
            return True
        except Exception:
            logger.exception("cannot attach default library")
            return False

    def relocate(self, new_root: Path) -> None:
        """Move the current database to a new folder and re-attach."""
        new_root = new_root.expanduser().resolve()
        if self.paths is None or self.db is None:
            self.attach(new_root, remember=True)
            return
        old_paths = self.paths
        if new_root == old_paths.root:
            return
        new_paths = LibraryPaths(new_root)
        new_paths.create()
        self.detach()
        if old_paths.database.exists():
            Database.move_database(old_paths.database, new_paths.database)
        for directory in (old_paths.backups, old_paths.models, old_paths.logs):
            if directory.exists() and not (new_paths.root / directory.name).exists():
                try:
                    shutil.move(str(directory), str(new_paths.root / directory.name))
                except OSError:
                    logger.warning("could not move %s", directory)
        self.attach(new_root)

    # ---------------------------------------------------------------- status

    def library_status(self) -> dict[str, Any]:
        root = self.library_root
        return {
            "ready": self.ready,
            "path": str(root) if root else None,
            "available": bool(root and root.is_dir()),
            "database": str(self.paths.database) if self.paths else None,
            "fallback": self.used_fallback,
            "program_dir": str(application_dir()),
        }

    def status(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "library": self.library_status(),
            "sources": 0,
            "documents": 0,
            "encrypted": 0,
            "failed": 0,
            "indexing": 0,
            "semantic_ready": False,
            "embedding_state": "disabled",
        }
        if not self.ready or self.db is None or self.coordinator is None:
            return status
        row = self.db.fetchone(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status IN ('encrypted','encrypted_suspected') THEN 1 ELSE 0 END) AS encrypted, "
            "SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed, "
            "SUM(CASE WHEN status IN ('pending','indexing') THEN 1 ELSE 0 END) AS indexing "
            "FROM documents"
        )
        if row is not None:
            status.update(
                {
                    "documents": int(row["total"] or 0),
                    "encrypted": int(row["encrypted"] or 0),
                    "failed": int(row["failed"] or 0),
                    "indexing": int(row["indexing"] or 0),
                }
            )
        source_row = self.db.fetchone("SELECT COUNT(*) AS total FROM sources")
        status["sources"] = int(source_row["total"] or 0) if source_row else 0
        status.update(self.coordinator.status())
        status["semantic_ready"] = self.coordinator.provider.ready
        status["embedding_state"] = self.coordinator.provider.state
        status["embedding_error"] = self.coordinator.provider.error
        status["embedding_model"] = self.coordinator.provider.model_name
        return status
