from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from ..config import MAX_JOB_ATTEMPTS
from ..db import Database
from ..db.ops import now_ts

JOB_SCAN_SOURCE = "scan_source"
JOB_INDEX_DOCUMENT = "index_document"
JOB_PROBE_DOCUMENT = "probe_document"
JOB_DELETE_DOCUMENT = "delete_document"
JOB_EMBED_DOCUMENT = "embed_document"


@dataclass
class Job:
    id: int
    kind: str
    payload: dict[str, Any]
    attempts: int
    dedupe_key: str


class JobQueue:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------- mutations

    def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        dedupe_key: str,
        priority: int = 0,
        delay: float = 0.0,
    ) -> None:
        now = time.time()
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO jobs (kind, dedupe_key, payload_json, state, priority, "
                    "attempts, not_before, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'pending', ?, 0, ?, ?, ?)",
                    (kind, dedupe_key, payload_json, priority, now + delay, now_ts(), now),
                )
                return
            if row["state"] in ("pending", "running"):
                conn.execute(
                    "UPDATE jobs SET payload_json = ?, priority = ?, not_before = ?, "
                    "updated_at = ? WHERE id = ?",
                    (payload_json, max(priority, int(row["priority"])), now + delay, now, row["id"]),
                )
                return
            # done rows are deleted; failed rows can be retried by a new event
            conn.execute(
                "UPDATE jobs SET kind = ?, payload_json = ?, state = 'pending', priority = ?, "
                "attempts = 0, not_before = ?, last_error = NULL, started_at = NULL, "
                "updated_at = ? WHERE id = ?",
                (kind, payload_json, priority, now + delay, now, row["id"]),
            )

    def claim_next(self, kinds: tuple[str, ...] | None = None) -> Job | None:
        now = time.time()
        with self.db.transaction() as conn:
            if kinds:
                placeholders = ", ".join("?" for _ in kinds)
                row = conn.execute(
                    "SELECT * FROM jobs WHERE state = 'pending' AND not_before <= ? "
                    f"AND kind IN ({placeholders}) "
                    "ORDER BY priority DESC, id ASC LIMIT 1",
                    (now, *kinds),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE state = 'pending' AND not_before <= ? "
                    "ORDER BY priority DESC, id ASC LIMIT 1",
                    (now,),
                ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE jobs SET state = 'running', started_at = ?, updated_at = ? WHERE id = ?",
                (now, now, row["id"]),
            )
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            return Job(
                id=int(row["id"]),
                kind=row["kind"],
                payload=payload,
                attempts=int(row["attempts"]),
                dedupe_key=row["dedupe_key"],
            )

    def complete(self, job_id: int) -> None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return
            started = float(row["started_at"] or 0)
            updated = float(row["updated_at"] or 0)
            if updated > started + 0.001:
                # A new event arrived while this job was running. Run it again
                # with the latest payload instead of dropping the change.
                conn.execute(
                    "UPDATE jobs SET state = 'pending', not_before = 0, started_at = NULL, "
                    "updated_at = ? WHERE id = ?",
                    (time.time(), job_id),
                )
            else:
                conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def retry(self, job_id: int, error: str, *, delay: float = 5.0) -> None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()
            attempts = int(row["attempts"]) if row else 0
            next_attempts = attempts + 1
            if next_attempts >= MAX_JOB_ATTEMPTS:
                conn.execute(
                    "UPDATE jobs SET state = 'failed', attempts = ?, last_error = ?, "
                    "updated_at = ? WHERE id = ?",
                    (next_attempts, error[:1000], time.time(), job_id),
                )
            else:
                conn.execute(
                    "UPDATE jobs SET state = 'pending', attempts = ?, last_error = ?, "
                    "not_before = ?, started_at = NULL, updated_at = ? WHERE id = ?",
                    (
                        next_attempts,
                        error[:1000],
                        time.time() + delay * (2**attempts),
                        time.time(),
                        job_id,
                    ),
                )

    def delay(self, job_id: int, seconds: float) -> None:
        """Postpone a job without consuming a retry attempt."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE jobs SET state = 'pending', not_before = ?, started_at = NULL, "
                "updated_at = ? WHERE id = ?",
                (time.time() + max(1.0, seconds), time.time(), job_id),
            )

    def reset_running(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE jobs SET state = 'pending', not_before = 0, started_at = NULL "
                "WHERE state = 'running'"
            )

    def retry_failed(self) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET state = 'pending', attempts = 0, not_before = 0, "
                "last_error = NULL WHERE state = 'failed'"
            )
            return cursor.rowcount

    def requeue_kind(self, kind: str) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET state = 'pending', attempts = 0, not_before = 0 "
                "WHERE kind = ? AND state IN ('failed', 'pending')",
                (kind,),
            )
            return cursor.rowcount

    # --------------------------------------------------------------- queries

    def stats(self) -> dict[str, Any]:
        rows = self.db.fetchall(
            "SELECT state, COUNT(*) AS count FROM jobs GROUP BY state"
        )
        by_state = {row["state"]: int(row["count"]) for row in rows}
        current = self.db.fetchone(
            "SELECT kind, payload_json FROM jobs WHERE state = 'running' ORDER BY id LIMIT 1"
        )
        return {
            "pending": by_state.get("pending", 0),
            "running": by_state.get("running", 0),
            "failed": by_state.get("failed", 0),
            "current": (
                {"kind": current["kind"], "payload": json.loads(current["payload_json"] or "{}")}
                if current
                else None
            ),
        }

    def errors(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT id, kind, payload_json, attempts, last_error, updated_at "
            "FROM jobs WHERE state = 'failed' ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "id": int(row["id"]),
                "kind": row["kind"],
                "payload": json.loads(row["payload_json"] or "{}"),
                "attempts": int(row["attempts"]),
                "error": row["last_error"],
                "updated_at": int(row["updated_at"]),
            }
            for row in rows
        ]
