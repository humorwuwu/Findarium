from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    EMBEDDING_THREADS_MAX,
)
from ..db import Database
from .tokenizer import normalize_text

logger = logging.getLogger(__name__)


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        return vector
    return vector / norm


def vector_to_blob(vector: np.ndarray) -> bytes:
    return normalize_vector(vector).astype(np.float32).tobytes()


def blob_to_vector(blob: bytes, dim: int) -> np.ndarray:
    array = np.frombuffer(blob, dtype=np.float32)
    if array.size != dim:
        return np.zeros(dim, dtype=np.float32)
    return array.astype(np.float32, copy=True)


class EmbeddingProvider:
    """Lazy ONNX embedding provider.

    The model is downloaded on first use and loaded on a background thread so the
    desktop window and keyword search are available immediately.
    """

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL,
        cache_dir: Path | None = None,
        *,
        enabled: bool = True,
    ):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.dim = EMBEDDING_DIM
        self.state = "unloaded" if enabled else "disabled"
        self.error: str | None = None
        self._model = None
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None

    @property
    def ready(self) -> bool:
        return self.state == "ready" and self._model is not None

    def start_loading(self) -> None:
        if not self.enabled or self.state in ("loading", "ready"):
            return
        self.state = "loading"
        self.error = None
        self._thread = threading.Thread(
            target=self._load, name="findarium-embedding-load", daemon=True
        )
        self._thread.start()

    def _load(self) -> None:
        try:
            from fastembed import TextEmbedding

            cache_dir = str(self.cache_dir) if self.cache_dir else None
            cpu_count = os.cpu_count() or 4
            threads = max(1, min(EMBEDDING_THREADS_MAX, cpu_count // 2 or 1))
            model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=cache_dir,
                threads=threads,
            )
            with self._lock:
                self._model = model
                self.state = "ready"
            logger.info("embedding model ready: %s", self.model_name)
        except Exception as exc:  # pragma: no cover - depends on network/model cache
            logger.warning("embedding model unavailable: %s", exc)
            with self._lock:
                self.state = "failed"
                self.error = str(exc)

    def embed_documents(
        self, texts: list[str], batch_size: int | None = None
    ) -> np.ndarray:
        if not self.ready:
            raise RuntimeError("embedding model is not ready")
        cleaned = [normalize_text(text)[:4000] or " " for text in texts]
        with self._lock:
            vectors = list(
                self._model.embed(  # type: ignore[union-attr]
                    cleaned, batch_size=batch_size or EMBEDDING_BATCH_SIZE
                )
            )
        if not vectors:
            return np.zeros((0, self.dim), dtype=np.float32)
        matrix = np.vstack([np.asarray(v, dtype=np.float32) for v in vectors])
        return matrix

    def embed_query(self, text: str) -> np.ndarray:
        if not self.ready:
            raise RuntimeError("embedding model is not ready")
        cleaned = normalize_text(text)[:4000] or " "
        with self._lock:
            vectors = list(self._model.query_embed(cleaned))  # type: ignore[union-attr]
        return np.asarray(vectors[0], dtype=np.float32)


class EmbeddingIndexer:
    def __init__(self, db: Database, provider: EmbeddingProvider):
        self.db = db
        self.provider = provider

    def process_document(
        self, document_id: int, batch_size: int | None = None
    ) -> str:
        """Embed a document's chunks and store chunk/document vectors."""
        if not self.provider.ready:
            return "retry"
        row = self.db.fetchone(
            "SELECT id, title, status FROM documents WHERE id = ?", (document_id,)
        )
        if row is None:
            return "done"
        chunks = self.db.fetchall(
            "SELECT id, text, heading_path FROM chunks WHERE document_id = ? ORDER BY ordinal",
            (document_id,),
        )
        if not chunks:
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE documents SET embedding_status = 'none' WHERE id = ?",
                    (document_id,),
                )
            return "done"

        title = (row["title"] or "").strip()
        texts: list[str] = []
        for chunk in chunks:
            heading = chunk["heading_path"] or ""
            try:
                import json

                parsed = json.loads(heading)
                heading = " / ".join(str(item) for item in parsed) if parsed else ""
            except (TypeError, ValueError):
                heading = str(heading)
            prefix = f"{title}\n{heading}\n" if heading else f"{title}\n"
            texts.append(prefix + (chunk["text"] or ""))

        try:
            matrix = self.provider.embed_documents(texts, batch_size=batch_size)
        except Exception as exc:
            logger.warning("embedding failed for document %s: %s", document_id, exc)
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE documents SET embedding_status = 'failed' WHERE id = ?",
                    (document_id,),
                )
            return "done"

        if matrix.shape[0] != len(chunks):
            return "retry"

        weights = np.asarray(
            [max(1, len(chunk["text"] or "")) for chunk in chunks], dtype=np.float32
        )
        weights = weights / weights.sum()
        doc_vector = normalize_vector((matrix * weights[:, None]).sum(axis=0))

        with self.db.transaction() as conn:
            conn.execute("DELETE FROM chunk_vectors WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id = ?)", (document_id,))
            for chunk, vector in zip(chunks, matrix, strict=False):
                conn.execute(
                    "INSERT OR REPLACE INTO chunk_vectors (chunk_id, model, dim, vector) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        int(chunk["id"]),
                        self.provider.model_name,
                        int(matrix.shape[1]),
                        vector_to_blob(vector),
                    ),
                )
            conn.execute(
                "INSERT OR REPLACE INTO doc_vectors (document_id, model, dim, vector) "
                "VALUES (?, ?, ?, ?)",
                (
                    document_id,
                    self.provider.model_name,
                    int(matrix.shape[1]),
                    vector_to_blob(doc_vector),
                ),
            )
            conn.execute(
                "UPDATE documents SET embedding_status = 'ready' WHERE id = ?",
                (document_id,),
            )
        return "done"


@dataclass
class VectorHit:
    item_id: int
    document_id: int
    score: float


class _BaseVectorIndex:
    def __init__(self, db: Database, model_name: str):
        self.db = db
        self.model_name = model_name
        self._lock = threading.RLock()
        self._matrix: np.ndarray | None = None
        self._ids: np.ndarray | None = None
        self._doc_ids: np.ndarray | None = None
        self._dirty = True

    def invalidate(self) -> None:
        with self._lock:
            self._dirty = True

    def _load(self) -> None:
        raise NotImplementedError

    def _ensure_loaded(self) -> None:
        with self._lock:
            if not self._dirty and self._matrix is not None:
                return
            self._load()
            self._dirty = False

    def search(self, query_vector: np.ndarray, limit: int = 100) -> list[VectorHit]:
        self._ensure_loaded()
        with self._lock:
            if self._matrix is None or self._matrix.shape[0] == 0:
                return []
            query = normalize_vector(query_vector)
            scores = self._matrix @ query
            count = min(limit, scores.shape[0])
            if count <= 0:
                return []
            if count < scores.shape[0]:
                indexes = np.argpartition(-scores, count - 1)[:count]
            else:
                indexes = np.arange(scores.shape[0])
            indexes = indexes[np.argsort(-scores[indexes])]
            return [
                VectorHit(
                    item_id=int(self._ids[index]),
                    document_id=int(self._doc_ids[index]),
                    score=float(scores[index]),
                )
                for index in indexes
            ]


class ChunkVectorIndex(_BaseVectorIndex):
    def _load(self) -> None:
        rows = self.db.fetchall(
            "SELECT cv.chunk_id, cv.dim, cv.vector, c.document_id "
            "FROM chunk_vectors cv "
            "JOIN chunks c ON c.id = cv.chunk_id "
            "JOIN documents d ON d.id = c.document_id "
            "WHERE cv.model = ? AND d.status IN ('indexed', 'indexed_partial')",
            (self.model_name,),
        )
        if not rows:
            self._matrix = np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
            self._ids = np.zeros((0,), dtype=np.int64)
            self._doc_ids = np.zeros((0,), dtype=np.int64)
            return
        dim = int(rows[0]["dim"]) or EMBEDDING_DIM
        matrix = np.vstack([blob_to_vector(row["vector"], dim) for row in rows]).astype(
            np.float32
        )
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix = matrix / norms
        self._ids = np.asarray([int(row["chunk_id"]) for row in rows], dtype=np.int64)
        self._doc_ids = np.asarray([int(row["document_id"]) for row in rows], dtype=np.int64)


class DocumentVectorIndex(_BaseVectorIndex):
    def _load(self) -> None:
        rows = self.db.fetchall(
            "SELECT dv.document_id, dv.dim, dv.vector "
            "FROM doc_vectors dv "
            "JOIN documents d ON d.id = dv.document_id "
            "WHERE dv.model = ? AND d.status IN ('indexed', 'indexed_partial')",
            (self.model_name,),
        )
        if not rows:
            self._matrix = np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
            self._ids = np.zeros((0,), dtype=np.int64)
            self._doc_ids = np.zeros((0,), dtype=np.int64)
            return
        dim = int(rows[0]["dim"]) or EMBEDDING_DIM
        matrix = np.vstack([blob_to_vector(row["vector"], dim) for row in rows]).astype(
            np.float32
        )
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix = matrix / norms
        self._ids = np.asarray([int(row["document_id"]) for row in rows], dtype=np.int64)
        self._doc_ids = self._ids.copy()


def embedding_stats(db: Database) -> dict[str, Any]:
    row = db.fetchone(
        "SELECT "
        "SUM(CASE WHEN embedding_status = 'ready' THEN 1 ELSE 0 END) AS ready, "
        "SUM(CASE WHEN embedding_status = 'pending' THEN 1 ELSE 0 END) AS pending, "
        "SUM(CASE WHEN embedding_status = 'failed' THEN 1 ELSE 0 END) AS failed, "
        "SUM(CASE WHEN status IN ('indexed','indexed_partial') THEN 1 ELSE 0 END) AS indexed "
        "FROM documents"
    )
    return {
        "embedding_ready": int(row["ready"] or 0) if row else 0,
        "embedding_pending": int(row["pending"] or 0) if row else 0,
        "embedding_failed": int(row["failed"] or 0) if row else 0,
        "embedding_indexed": int(row["indexed"] or 0) if row else 0,
    }
