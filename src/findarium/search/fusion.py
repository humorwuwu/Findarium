from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

RRF_K = 60


def rrf_fuse(channels: list[tuple[str, float, list[int]]]) -> dict[int, dict[str, Any]]:
    """Weighted Reciprocal Rank Fusion.

    channels: list of (name, weight, ordered_document_ids)
    Returns document_id -> {score, channels: [names]}
    """
    fused: dict[int, dict[str, Any]] = {}
    for name, weight, document_ids in channels:
        seen: set[int] = set()
        for rank, document_id in enumerate(document_ids):
            if document_id in seen:
                continue
            seen.add(document_id)
            entry = fused.setdefault(
                document_id, {"score": 0.0, "channels": []}
            )
            entry["score"] += weight / (RRF_K + rank + 1)
            entry["channels"].append(name)
    return fused


def normalize_scores(fused: dict[int, dict[str, Any]]) -> None:
    if not fused:
        return
    maximum = max(entry["score"] for entry in fused.values()) or 1.0
    for entry in fused.values():
        entry["relevance"] = entry["score"] / maximum


def recency_score(mtime_ns: int | None, *, recency_intent: bool) -> float:
    if not mtime_ns:
        return 0.0
    modified = datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=UTC)
    age_days = max(0.0, (datetime.now(UTC) - modified).total_seconds() / 86400.0)
    half_life = 14.0 if recency_intent else 90.0
    return math.exp(-math.log(2) * age_days / half_life)


def final_score(
    *,
    relevance: float,
    recency: float,
    title_match: float,
    feedback: float,
    status_factor: float,
    recency_weight: float,
) -> float:
    score = (
        0.72 * relevance
        + recency_weight * recency
        + 0.08 * title_match
        + 0.04 * feedback
    )
    return max(0.0, min(1.0, score * status_factor))


def status_factor(status: str) -> float:
    return {
        "indexed": 1.0,
        "indexed_partial": 0.9,
        "encrypted": 0.72,
        "encrypted_suspected": 0.68,
        "failed": 0.55,
    }.get(status, 0.5)


def feedback_score(open_count: int, last_opened_at: int | None) -> float:
    if not last_opened_at:
        return min(0.4, open_count * 0.05)
    opened = datetime.fromtimestamp(last_opened_at, tz=UTC)
    age_days = max(0.0, (datetime.now(UTC) - opened).total_seconds() / 86400.0)
    freshness = math.exp(-math.log(2) * age_days / 30.0)
    return min(1.0, 0.2 + 0.6 * freshness + min(0.2, open_count * 0.02))
