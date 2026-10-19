from __future__ import annotations

import shutil
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .schema import MIGRATIONS, SCHEMA_SQL, SCHEMA_VERSION


class DatabaseError(RuntimeError):
    pass


class Database:
    """SQLite connection manager.

    One connection per thread, WAL mode, serialized writes. Reads are not blocked
    by the index worker thanks to WAL.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._local = threading.local()
        self._connections: list[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()
        self._write_lock = threading.RLock()

    # ------------------------------------------------------------------ setup

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.path),
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA temp_store = MEMORY")
        if str(self.path) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -32000")
            conn.execute("PRAGMA mmap_size = 268435456")
        with self._connections_lock:
            self._connections.append(conn)
        return conn

    @property
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = self._connect()
            self._local.connection = conn
        return conn

    def initialize(self, backup_dir: Path | None = None) -> None:
        """Open the database and apply schema/migrations."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.connection
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise DatabaseError(
                f"索引库版本 {version} 高于当前应用支持的版本 {SCHEMA_VERSION}"
            )
        if version == 0:
            # Fresh database. If there is an existing file from a failed run, back it up.
            if self.path.exists() and self.path.stat().st_size > 0 and backup_dir is not None:
                self.backup(backup_dir, label="pre-init")
            self._exec_script(SCHEMA_SQL)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        else:
            if version < SCHEMA_VERSION:
                if backup_dir is not None:
                    self.backup(backup_dir, label=f"pre-v{SCHEMA_VERSION}")
                for index in range(version, SCHEMA_VERSION):
                    sql = MIGRATIONS[index - 1] if index - 1 < len(MIGRATIONS) else ""
                    if sql:
                        self._exec_script(sql)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

        # Fail early with a clear message if FTS5 is unavailable or broken.
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_probe USING fts5(x)"
        )
        conn.execute("DROP TABLE IF EXISTS __fts5_probe")

    def _exec_script(self, sql: str) -> None:
        conn = self.connection
        try:
            conn.executescript(sql)
        except sqlite3.Error as exc:
            raise DatabaseError(f"初始化数据库失败: {exc}") from exc

    # -------------------------------------------------------------- accessors

    def execute(self, sql: str, params: tuple | list | dict = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, params)

    def executemany(self, sql: str, seq) -> sqlite3.Cursor:
        return self.connection.executemany(sql, seq)

    def fetchone(self, sql: str, params: tuple | list | dict = ()) -> sqlite3.Row | None:
        return self.connection.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple | list | dict = ()) -> list[sqlite3.Row]:
        return self.connection.execute(sql, params).fetchall()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """A serialized write transaction.

        Nested calls share the outer transaction (RLock). This keeps FTS and
        document table updates atomic while preventing two worker threads from
        writing simultaneously.
        """
        with self._write_lock:
            conn = self.connection
            outer = conn.in_transaction
            if not outer:
                conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                if not outer and conn.in_transaction:
                    conn.rollback()
                raise
            else:
                if not outer and conn.in_transaction:
                    conn.commit()

    # --------------------------------------------------------------- lifecycle

    def backup(self, backup_dir: Path, label: str = "manual") -> Path:
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = backup_dir / f"index-{stamp}-{label}.sqlite3"
        with self._write_lock:
            dest = sqlite3.connect(target)
            try:
                self.connection.backup(dest)
            finally:
                dest.close()
        return target

    def copy_to(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._write_lock:
            dest = sqlite3.connect(target)
            try:
                self.connection.backup(dest)
            finally:
                dest.close()

    @staticmethod
    def move_database(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(source) + suffix)
            if src.exists():
                shutil.move(str(src), str(target) + suffix)

    def checkpoint(self) -> None:
        try:
            self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass

    def optimize(self) -> None:
        try:
            with self.transaction() as conn:
                conn.execute("PRAGMA optimize")
        except sqlite3.Error:
            pass

    def close(self) -> None:
        with self._connections_lock:
            connections = list(self._connections)
            self._connections.clear()
        for conn in connections:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self._local = threading.local()
