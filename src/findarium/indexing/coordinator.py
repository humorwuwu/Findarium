from __future__ import annotations

import logging
import os
import resource
import threading
import time
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..config import (
    ADAPTIVE_BACKLOG_LARGE,
    ADAPTIVE_BACKLOG_MEDIUM,
    ADAPTIVE_BUSY_LOAD_RATIO,
    ADAPTIVE_BUSY_PROCESS_CPU,
    ADAPTIVE_HIGH_LOAD_RATIO,
    ADAPTIVE_HIGH_PROCESS_CPU,
    ADAPTIVE_MAX_WORKERS,
    ADAPTIVE_SAMPLE_SECONDS,
    DEFAULT_ENCRYPTED_RECHECK_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    EMBEDDING_BATCH_MAX,
    EMBEDDING_BATCH_MIN,
    EMBEDDING_BATCH_SIZE,
    SUPPORTED_EXTENSIONS,
    WATCH_DEBOUNCE_SECONDS,
)
from ..db import Database
from ..paths import LibraryPaths
from .embeddings import (
    ChunkVectorIndex,
    DocumentVectorIndex,
    EmbeddingIndexer,
    EmbeddingProvider,
    embedding_stats,
)
from .jobs import (
    JOB_DELETE_DOCUMENT,
    JOB_EMBED_DOCUMENT,
    JOB_INDEX_DOCUMENT,
    JOB_PROBE_DOCUMENT,
    JOB_SCAN_SOURCE,
    JobQueue,
)
from .pipeline import RETRY, IndexPipeline
from .scanner import Scanner

logger = logging.getLogger(__name__)

INDEX_JOB_KINDS = (
    JOB_SCAN_SOURCE,
    JOB_INDEX_DOCUMENT,
    JOB_PROBE_DOCUMENT,
    JOB_DELETE_DOCUMENT,
)
EMBED_JOB_KINDS = (JOB_EMBED_DOCUMENT,)


class _WatchHandler(FileSystemEventHandler):
    def __init__(self, coordinator: IndexCoordinator, source_id: int, root: Path):
        self.coordinator = coordinator
        self.source_id = source_id
        self.root = root

    def _is_relevant(self, path: str) -> bool:
        candidate = Path(path)
        if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        return not self.coordinator._is_library_path(candidate)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if self._is_relevant(event.src_path):
            self.coordinator.queue_index(event.src_path, self.source_id, delay=WATCH_DEBOUNCE_SECONDS)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if self._is_relevant(event.src_path):
            self.coordinator.queue_index(event.src_path, self.source_id, delay=WATCH_DEBOUNCE_SECONDS)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if self._is_relevant(event.src_path):
            self.coordinator.queue_delete(event.src_path, self.source_id)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if self._is_relevant(event.src_path):
            self.coordinator.queue_delete(event.src_path, self.source_id)
        if self._is_relevant(event.dest_path):
            self.coordinator.queue_index(event.dest_path, self.source_id, delay=WATCH_DEBOUNCE_SECONDS)


class IndexCoordinator:
    """Adaptive indexing coordinator.

    A pool of extraction workers scales between 1 and ``ADAPTIVE_MAX_WORKERS``
    based on the system load average and this process's CPU usage. Embedding runs
    on its own worker so semantic backfill never blocks text indexing, and its
    batch size shrinks when the machine is busy.
    """

    def __init__(
        self,
        db: Database,
        library_paths: LibraryPaths,
        *,
        embedding_enabled: bool = True,
    ):
        self.db = db
        self.library_paths = library_paths
        self.queue = JobQueue(db)
        self.scanner = Scanner(
            db,
            library_paths,
            on_index=lambda path, source_id, force: self.queue_index(path, source_id, force=force),
            on_probe=self.queue_probe,
        )
        self.pipeline = IndexPipeline(
            db,
            on_embed=self.queue_embed,
            on_index=lambda path, source_id, force: self.queue_index(path, source_id, force=force),
        )
        self.provider = EmbeddingProvider(
            cache_dir=library_paths.models, enabled=embedding_enabled
        )
        self.embedding_indexer = EmbeddingIndexer(db, self.provider)
        self.chunk_index = ChunkVectorIndex(db, self.provider.model_name)
        self.doc_index = DocumentVectorIndex(db, self.provider.model_name)

        self._stop = threading.Event()
        self._observer: Observer | None = None
        self._next_scan_at = 0.0
        self._lock = threading.RLock()

        self._max_workers = max(
            1, min(ADAPTIVE_MAX_WORKERS, os.cpu_count() or 1)
        )
        self._desired_workers = min(2, self._max_workers)
        self._active_workers = 0
        self._slot_cond = threading.Condition()
        self._index_threads: list[threading.Thread] = []
        self._embed_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None

        self._load_ratio = 0.0
        self._process_cpu = 0.0
        self._last_cpu_seconds = 0.0
        self._last_cpu_wall = time.time()
        self._embed_batch = EMBEDDING_BATCH_SIZE

        self._active_keys: set[str] = set()
        self._keys_lock = threading.Lock()

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        self.queue.reset_running()
        if self.provider.enabled:
            self.provider.start_loading()
        self._sample_load()
        self._desired_workers = self._compute_desired_workers(
            self.queue.stats().get("pending", 0)
        )
        for slot in range(self._max_workers):
            thread = threading.Thread(
                target=self._run_index_worker,
                args=(slot,),
                name=f"findarium-indexer-{slot}",
                daemon=True,
            )
            thread.start()
            self._index_threads.append(thread)
        self._embed_thread = threading.Thread(
            target=self._run_embed_worker, name="findarium-embedder", daemon=True
        )
        self._embed_thread.start()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="findarium-adaptor", daemon=True
        )
        self._monitor_thread.start()
        self.refresh_watchers()
        self.scan_all()
        logger.info(
            "index coordinator started (max workers=%s, cpu=%s)",
            self._max_workers,
            os.cpu_count(),
        )

    def stop(self) -> None:
        self._stop.set()
        with self._slot_cond:
            self._slot_cond.notify_all()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
            self._observer = None
        for thread in self._index_threads:
            thread.join(timeout=10)
        self._index_threads.clear()
        if self._embed_thread is not None:
            self._embed_thread.join(timeout=10)
            self._embed_thread = None
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
        logger.info("index coordinator stopped")

    # ---------------------------------------------------------------- queue

    def queue_index(self, path: str, source_id: int, *, force: bool = False, delay: float = 0.0) -> None:
        self.queue.enqueue(
            JOB_INDEX_DOCUMENT,
            {"path": path, "source_id": int(source_id), "force": force},
            dedupe_key=f"index:{path}",
            priority=10 if force else 0,
            delay=delay,
        )

    def queue_probe(self, document_id: int) -> None:
        self.queue.enqueue(
            JOB_PROBE_DOCUMENT,
            {"document_id": int(document_id)},
            dedupe_key=f"probe:{document_id}",
            priority=5,
        )

    def queue_delete(self, path: str, source_id: int) -> None:
        self.queue.enqueue(
            JOB_DELETE_DOCUMENT,
            {"path": path, "source_id": int(source_id)},
            dedupe_key=f"delete:{path}",
            priority=5,
            delay=WATCH_DEBOUNCE_SECONDS,
        )

    def queue_embed(self, document_id: int) -> None:
        if not self.provider.enabled:
            return
        self.queue.enqueue(
            JOB_EMBED_DOCUMENT,
            {"document_id": int(document_id)},
            dedupe_key=f"embed:{document_id}",
            priority=0,
        )

    def scan_all(self) -> None:
        rows = self.db.fetchall("SELECT id FROM sources WHERE enabled = 1")
        for row in rows:
            self.queue.enqueue(
                JOB_SCAN_SOURCE,
                {"source_id": int(row["id"])},
                dedupe_key=f"scan:{row['id']}",
                priority=20,
            )
        self._next_scan_at = time.time() + self._scan_interval()

    def scan_source(self, source_id: int) -> None:
        self.queue.enqueue(
            JOB_SCAN_SOURCE,
            {"source_id": int(source_id)},
            dedupe_key=f"scan:{source_id}",
            priority=20,
        )

    def requeue_embeddings(self) -> int:
        return self.queue.requeue_kind(JOB_EMBED_DOCUMENT)

    # -------------------------------------------------------------- watchers

    def refresh_watchers(self) -> None:
        with self._lock:
            if self._observer is not None:
                try:
                    self._observer.stop()
                    self._observer.join(timeout=5)
                except Exception:
                    pass
                self._observer = None
            observer = Observer()
            scheduled = 0
            rows = self.db.fetchall("SELECT id, path FROM sources WHERE enabled = 1")
            for row in rows:
                root = Path(row["path"])
                if not root.is_dir():
                    continue
                handler = _WatchHandler(self, int(row["id"]), root)
                try:
                    observer.schedule(handler, str(root), recursive=True)
                    scheduled += 1
                except Exception as exc:
                    logger.warning("cannot watch %s: %s", root, exc)
            if scheduled:
                observer.daemon = True
                observer.start()
                self._observer = observer

    # ------------------------------------------------------------- workers

    def _run_index_worker(self, slot: int) -> None:
        while not self._stop.is_set():
            if not self._acquire_slot():
                break
            try:
                job = self.queue.claim_next(INDEX_JOB_KINDS)
                if job is None:
                    self._stop.wait(0.2)
                    continue
                if not self._begin_job(job):
                    self.queue.delay(job.id, 1.0)
                    continue
                try:
                    self._dispatch(job)
                finally:
                    self._end_job(job)
            except Exception:
                logger.exception("index worker %s error", slot)
                self._stop.wait(1.0)
            finally:
                self._release_slot()

    def _run_embed_worker(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.provider.ready:
                    self._stop.wait(2.0)
                    continue
                if self._should_throttle_embedding():
                    self._stop.wait(3.0)
                    continue
                self._backfill_embeddings()
                job = self.queue.claim_next(EMBED_JOB_KINDS)
                if job is None:
                    self._stop.wait(0.5)
                    continue
                if not self._begin_job(job):
                    self.queue.delay(job.id, 1.0)
                    continue
                try:
                    self._dispatch_embed(job)
                finally:
                    self._end_job(job)
            except Exception:
                logger.exception("embed worker error")
                self._stop.wait(1.0)

    def _dispatch(self, job) -> None:
        try:
            if job.kind == JOB_SCAN_SOURCE:
                report = self.scanner.scan_source(int(job.payload.get("source_id", 0)))
                if report.unavailable:
                    self.queue.delay(job.id, 60)
                else:
                    self.queue.complete(job.id)
                return
            if job.kind == JOB_INDEX_DOCUMENT:
                result = self.pipeline.process_index_job(job.payload)
                self.chunk_index.invalidate()
                self.doc_index.invalidate()
                if result.action == RETRY:
                    self.queue.delay(job.id, result.delay or 3.0)
                else:
                    self.queue.complete(job.id)
                return
            if job.kind == JOB_PROBE_DOCUMENT:
                result = self.pipeline.process_probe_job(job.payload)
                self.chunk_index.invalidate()
                self.doc_index.invalidate()
                if result.action == RETRY:
                    self.queue.delay(job.id, result.delay or 3.0)
                else:
                    self.queue.complete(job.id)
                return
            if job.kind == JOB_DELETE_DOCUMENT:
                result = self.pipeline.process_delete_job(job.payload)
                self.chunk_index.invalidate()
                self.doc_index.invalidate()
                if result.action == RETRY:
                    self.queue.delay(job.id, result.delay or 3.0)
                else:
                    self.queue.complete(job.id)
                return
            self.queue.complete(job.id)
        except Exception as exc:
            logger.exception("job failed: %s", job.kind)
            self.queue.retry(job.id, str(exc))

    def _dispatch_embed(self, job) -> None:
        try:
            outcome = self.embedding_indexer.process_document(
                int(job.payload.get("document_id", 0)), batch_size=self._embed_batch
            )
            self.chunk_index.invalidate()
            self.doc_index.invalidate()
            if outcome == RETRY:
                self.queue.delay(job.id, 30)
            else:
                self.queue.complete(job.id)
        except Exception as exc:
            logger.exception("embed job failed")
            self.queue.retry(job.id, str(exc))

    # ---------------------------------------------------------- adaptivity

    def _monitor_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._sample_load()
                pending = self.queue.stats().get("pending", 0)
                desired = self._compute_desired_workers(pending)
                self._embed_batch = self._compute_embed_batch()
                with self._slot_cond:
                    self._desired_workers = desired
                    self._slot_cond.notify_all()
                if time.time() >= self._next_scan_at:
                    self.scan_all()
            except Exception:
                logger.exception("adaptive monitor error")
            self._stop.wait(ADAPTIVE_SAMPLE_SECONDS)

    def _sample_load(self) -> None:
        try:
            load1 = os.getloadavg()[0]
        except (OSError, AttributeError):
            load1 = 0.0
        cpu_count = max(1, os.cpu_count() or 1)
        self._load_ratio = max(0.0, load1 / cpu_count)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        cpu_seconds = float(usage.ru_utime + usage.ru_stime)
        now = time.time()
        wall = max(1e-6, now - self._last_cpu_wall)
        delta = max(0.0, cpu_seconds - self._last_cpu_seconds)
        self._process_cpu = min(1.0, delta / (wall * cpu_count))
        self._last_cpu_seconds = cpu_seconds
        self._last_cpu_wall = now

    def _compute_desired_workers(self, pending: int) -> int:
        max_workers = self._max_workers
        if max_workers <= 1:
            return 1
        if (
            self._load_ratio >= ADAPTIVE_HIGH_LOAD_RATIO
            or self._process_cpu >= ADAPTIVE_HIGH_PROCESS_CPU
        ):
            return 1
        if (
            self._load_ratio >= ADAPTIVE_BUSY_LOAD_RATIO
            or self._process_cpu >= ADAPTIVE_BUSY_PROCESS_CPU
        ):
            return min(2, max_workers)
        if pending >= ADAPTIVE_BACKLOG_LARGE:
            return max_workers
        if pending >= ADAPTIVE_BACKLOG_MEDIUM:
            return min(max_workers, max(2, max_workers // 2))
        return min(2, max_workers)

    def _compute_embed_batch(self) -> int:
        if (
            self._load_ratio >= ADAPTIVE_HIGH_LOAD_RATIO
            or self._process_cpu >= ADAPTIVE_HIGH_PROCESS_CPU
        ):
            return EMBEDDING_BATCH_MIN
        if (
            self._load_ratio >= ADAPTIVE_BUSY_LOAD_RATIO
            or self._process_cpu >= ADAPTIVE_BUSY_PROCESS_CPU
        ):
            return max(EMBEDDING_BATCH_MIN, EMBEDDING_BATCH_SIZE)
        return EMBEDDING_BATCH_MAX

    def _should_throttle_embedding(self) -> bool:
        pending = self.queue.stats().get("pending", 0)
        if pending <= 0:
            return False
        return (
            self._load_ratio >= ADAPTIVE_BUSY_LOAD_RATIO
            or self._process_cpu >= ADAPTIVE_BUSY_PROCESS_CPU
        )

    def _acquire_slot(self) -> bool:
        with self._slot_cond:
            while (
                not self._stop.is_set()
                and self._active_workers >= self._desired_workers
            ):
                self._slot_cond.wait(0.5)
            if self._stop.is_set():
                return False
            self._active_workers += 1
            return True

    def _release_slot(self) -> None:
        with self._slot_cond:
            self._active_workers = max(0, self._active_workers - 1)
            self._slot_cond.notify_all()

    def _job_key(self, job) -> str:
        payload = job.payload or {}
        if payload.get("path"):
            return f"path:{payload['path']}"
        if payload.get("document_id") is not None:
            row = self.db.fetchone(
                "SELECT path FROM documents WHERE id = ?",
                (int(payload["document_id"]),),
            )
            if row is not None:
                return f"path:{row['path']}"
            return f"doc:{payload['document_id']}"
        if payload.get("source_id") is not None:
            return f"source:{payload['source_id']}"
        return f"job:{job.id}"

    def _begin_job(self, job) -> bool:
        key = self._job_key(job)
        with self._keys_lock:
            if key in self._active_keys:
                return False
            self._active_keys.add(key)
        job._active_key = key  # type: ignore[attr-defined]
        return True

    def _end_job(self, job) -> None:
        key = getattr(job, "_active_key", None)
        if key is None:
            return
        with self._keys_lock:
            self._active_keys.discard(key)

    # --------------------------------------------------------------- helpers

    def _backfill_embeddings(self) -> None:
        rows = self.db.fetchall(
            "SELECT id FROM documents WHERE embedding_status = 'pending' "
            "AND status IN ('indexed', 'indexed_partial') ORDER BY mtime_ns DESC LIMIT 20"
        )
        for row in rows:
            self.queue_embed(int(row["id"]))

    def _scan_interval(self) -> float:
        row = self.db.fetchone("SELECT value FROM settings WHERE key = 'scan_interval_seconds'")
        if row is None:
            return float(DEFAULT_SCAN_INTERVAL_SECONDS)
        try:
            return max(60.0, float(row["value"]))
        except (TypeError, ValueError):
            return float(DEFAULT_SCAN_INTERVAL_SECONDS)

    def _probe_interval(self) -> float:
        row = self.db.fetchone(
            "SELECT value FROM settings WHERE key = 'encrypted_recheck_seconds'"
        )
        if row is None:
            return float(DEFAULT_ENCRYPTED_RECHECK_SECONDS)
        try:
            return max(60.0, float(row["value"]))
        except (TypeError, ValueError):
            return float(DEFAULT_ENCRYPTED_RECHECK_SECONDS)

    def _is_library_path(self, path: Path) -> bool:
        candidate = str(path)
        for exclusion in self.library_paths.self_exclusions():
            if candidate == exclusion or candidate.startswith(exclusion + "/"):
                return True
        return False

    # ---------------------------------------------------------------- status

    def status(self) -> dict[str, Any]:
        stats = self.queue.stats()
        stats.update(embedding_stats(self.db))
        stats["embedding_state"] = self.provider.state
        stats["embedding_error"] = self.provider.error
        stats["embedding_model"] = self.provider.model_name
        stats["workers"] = {
            "max": self._max_workers,
            "desired": self._desired_workers,
            "active": self._active_workers,
        }
        stats["load_ratio"] = round(self._load_ratio, 3)
        stats["process_cpu"] = round(self._process_cpu, 3)
        stats["embedding_batch"] = self._embed_batch
        return stats
