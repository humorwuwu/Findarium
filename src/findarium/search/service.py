from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from rapidfuzz import fuzz, process

from ..config import (
    CHUNK_CANDIDATE_LIMIT,
    DOCUMENT_CANDIDATE_LIMIT,
    FUZZY_THRESHOLD,
    FUZZY_TITLE_LIMIT,
    SEARCH_LIMIT,
    SEMANTIC_CANDIDATE_LIMIT,
)
from ..db import Database
from ..db.ops import now_ts
from ..i18n import (
    DEFAULT_LANG,
    join_list,
    localize_list,
    localize_stored,
    location_label,
    translate,
)
from ..indexing.embeddings import (
    ChunkVectorIndex,
    EmbeddingProvider,
)
from ..indexing.tokenizer import build_fts_query
from .fts import (
    VISIBLE_STATUSES,
    build_filter_sql,
    chunk_by_id,
    chunks_for_document,
    documents_by_ids,
    recent_documents,
    search_chunks,
    search_documents,
)
from .fusion import (
    feedback_score,
    final_score,
    normalize_scores,
    recency_score,
    rrf_fuse,
    status_factor,
)
from .query import ParsedQuery, SearchFilters, parse_query
from .related import RelatedService, document_summary
from .snippets import make_snippet, plain_snippet

_RECENT_TAG_DAYS = 7


def _iso_from_ns(value: int | None) -> str | None:
    if not value:
        return None
    try:
        return (
            datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)
            .astimezone()
            .isoformat(timespec="seconds")
        )
    except (OverflowError, OSError, ValueError):
        return None


def _summary(row: dict[str, Any], lang: str = DEFAULT_LANG) -> dict[str, Any]:
    summary = document_summary(row, lang)
    summary.update(
        {
            "rel_path": row.get("rel_path"),
            "source_id": row.get("source_id"),
            "mtime": _iso_from_ns(row.get("mtime_ns")),
            "birthtime": _iso_from_ns(row.get("birthtime_ns")),
            "indexed_at": row.get("indexed_at"),
            "last_probe_at": row.get("last_probe_at"),
            "error": localize_stored(row.get("error"), lang),
            "encryption_kind": row.get("encryption_kind"),
        }
    )
    return summary


def _parse_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class SearchService:
    def __init__(
        self,
        db: Database,
        provider: EmbeddingProvider,
        chunk_index: ChunkVectorIndex,
        related_service: RelatedService,
    ):
        self.db = db
        self.provider = provider
        self.chunk_index = chunk_index
        self.related_service = related_service

    # --------------------------------------------------------------- search

    def search(
        self,
        query: str,
        *,
        extensions: list[str] | None = None,
        after: str | None = None,
        before: str | None = None,
        folder: str | None = None,
        encrypted: str | None = None,
        sort: str | None = None,
        limit: int = SEARCH_LIMIT,
        lang: str = DEFAULT_LANG,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        parsed = parse_query(
            query,
            extensions=extensions,
            after=after,
            before=before,
            folder=folder,
            encrypted=encrypted,
            sort=sort,
            lang=lang,
        )
        if not parsed.has_text:
            items = self._recent_items(parsed.filters, limit, lang)
            return {
                "query": parsed.raw,
                "explanation": parsed.explanation
                or [translate("explain.no_query", lang)],
                "filters": parsed.filters.as_dict(),
                "items": items,
                "total": len(items),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "semantic_ready": self.provider.ready,
            }

        chunk_rows: list[dict[str, Any]] = []
        doc_rows: list[dict[str, Any]] = []
        if parsed.match_query:
            chunk_rows = search_chunks(
                self.db, parsed.match_query, parsed.filters, CHUNK_CANDIDATE_LIMIT
            )
            doc_rows = search_documents(
                self.db, parsed.match_query, parsed.filters, DOCUMENT_CANDIDATE_LIMIT
            )
            if len(chunk_rows) < 3:
                relaxed = build_fts_query(parsed.content_text, operator="OR")
                if relaxed and relaxed != parsed.match_query:
                    extra_chunks = search_chunks(
                        self.db, relaxed, parsed.filters, CHUNK_CANDIDATE_LIMIT
                    )
                    extra_docs = search_documents(
                        self.db, relaxed, parsed.filters, DOCUMENT_CANDIDATE_LIMIT
                    )
                    chunk_rows = self._merge_by_key(chunk_rows, extra_chunks, "chunk_id")
                    doc_rows = self._merge_by_key(doc_rows, extra_docs, "document_id")

        semantic_chunks: dict[int, int] = {}
        semantic_docs: list[int] = []
        if self.provider.ready:
            try:
                vector = self.provider.embed_query(parsed.content_text)
                hits = self.chunk_index.search(vector, limit=SEMANTIC_CANDIDATE_LIMIT)
            except Exception:
                hits = []
            best: dict[int, float] = {}
            for hit in hits:
                if hit.document_id not in best or hit.score > best[hit.document_id]:
                    best[hit.document_id] = hit.score
                    semantic_chunks[hit.document_id] = hit.item_id
            semantic_docs = [
                document_id
                for document_id, _ in sorted(best.items(), key=lambda item: -item[1])
            ]

        fuzzy_docs = self._fuzzy_documents(parsed.content_text, parsed.filters)

        chunk_channel = self._ordered_chunk_documents(chunk_rows)
        doc_channel = [int(row["document_id"]) for row in doc_rows]
        channels: list[tuple[str, float, list[int]]] = []
        if chunk_channel:
            channels.append(("keyword", 1.0, chunk_channel))
        if doc_channel:
            channels.append(("file", 0.7, doc_channel))
        if semantic_docs:
            channels.append(("semantic", 0.8, semantic_docs))
        if fuzzy_docs:
            channels.append(("fuzzy", 0.4, [doc_id for doc_id, _ in fuzzy_docs]))

        fused = rrf_fuse(channels)
        normalize_scores(fused)
        if not fused:
            items = self._recent_items(parsed.filters, limit, lang)
            return {
                "query": parsed.raw,
                "explanation": parsed.explanation + [translate("explain.no_match", lang)],
                "filters": parsed.filters.as_dict(),
                "items": items,
                "total": 0,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "semantic_ready": self.provider.ready,
            }

        documents = documents_by_ids(self.db, list(fused.keys()))
        chunk_lookup = {int(row["chunk_id"]): row for row in chunk_rows}
        results: list[dict[str, Any]] = []
        explicit_dates = parsed.filters.after is not None or parsed.filters.before is not None
        recency_weight = 0.0 if explicit_dates else (0.22 if parsed.recency_boost else 0.10)

        for document_id, entry in fused.items():
            row = documents.get(document_id)
            if row is None:
                continue
            relevance = float(entry.get("relevance", 0.0))
            recency = recency_score(row.get("mtime_ns"), recency_intent=parsed.recency_boost > 0)
            title_text = f"{row.get('title') or ''} {row.get('name') or ''}".strip()
            title_match = (
                fuzz.partial_ratio(parsed.content_text.lower(), title_text.lower()) / 100.0
                if title_text
                else 0.0
            )
            title_match = title_match if title_match >= 0.8 else 0.0
            feedback = feedback_score(
                int(row.get("open_count") or 0), row.get("last_opened_at")
            )
            score = final_score(
                relevance=relevance,
                recency=recency,
                title_match=title_match,
                feedback=feedback,
                status_factor=status_factor(row.get("status", "")),
                recency_weight=recency_weight,
            )
            results.append(
                {
                    "document_id": document_id,
                    "row": row,
                    "score": score,
                    "relevance": relevance,
                    "channels": entry.get("channels", []),
                    "recency": recency,
                    "title_match": title_match,
                }
            )

        if parsed.filters.sort == "modified":
            results.sort(key=lambda item: item["row"].get("mtime_ns") or 0, reverse=True)
        elif parsed.filters.sort == "created":
            results.sort(
                key=lambda item: item["row"].get("birthtime_ns") or 0, reverse=True
            )
        else:
            results.sort(key=lambda item: item["score"], reverse=True)

        top = results[:limit]
        items = [
            self._build_item(
                item,
                parsed,
                chunk_lookup=chunk_lookup,
                semantic_chunks=semantic_chunks,
                include_related=True,
                lang=lang,
            )
            for item in top
        ]
        channels_seen = {channel for item in results for channel in item["channels"]}
        sources = join_list(
            [
                translate(f"explain.source.{name}", lang)
                if name in ("keyword", "file", "semantic", "fuzzy")
                else name
                for name in channels_seen
            ],
            lang,
        )
        return {
            "query": parsed.raw,
            "content_query": parsed.content_text,
            "explanation": parsed.explanation
            + [translate("explain.match_sources", lang, sources=sources)]
            if results
            else parsed.explanation,
            "filters": parsed.filters.as_dict(),
            "items": items,
            "total": len(results),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "semantic_ready": self.provider.ready,
        }

    # ------------------------------------------------------------ documents

    def recent(
        self, limit: int = 30, lang: str = DEFAULT_LANG, **filter_kwargs
    ) -> list[dict[str, Any]]:
        parsed = parse_query("", lang=lang, **filter_kwargs)
        return self._recent_items(parsed.filters, limit, lang)

    def get_document(
        self,
        document_id: int,
        include_chunks: bool = True,
        lang: str = DEFAULT_LANG,
    ) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        if row is None:
            return None
        row_dict = dict(row)
        metadata = _parse_json(row_dict.get("metadata_json"), {})
        result = _summary(row_dict, lang)
        result["warnings"] = localize_list(metadata.get("warnings", []), lang)
        result["metadata"] = metadata.get("metadata", {})
        result["keywords"] = [
            {"keyword": item["keyword"], "weight": float(item["weight"])}
            for item in self.db.fetchall(
                "SELECT keyword, weight FROM doc_keywords WHERE document_id = ? "
                "ORDER BY weight DESC LIMIT 20",
                (document_id,),
            )
        ]
        if include_chunks:
            chunks = []
            for chunk in chunks_for_document(self.db, document_id):
                location = _parse_json(chunk["location_json"], {})
                chunks.append(
                    {
                        **dict(chunk),
                        "location_json": location,
                        "location_label": location_label(
                            location, lang, chunk["location_label"]
                        ),
                        "heading_path": _parse_json(chunk["heading_path"], []),
                    }
                )
            result["chunks"] = chunks
        result["related"] = self.related_service.related(document_id, limit=8, lang=lang)
        return result

    def graph(self, document_id: int, lang: str = DEFAULT_LANG) -> dict[str, Any]:
        return self.related_service.graph(document_id, lang=lang)

    def related(
        self, document_id: int, limit: int = 8, lang: str = DEFAULT_LANG
    ) -> list[dict[str, Any]]:
        return self.related_service.related(document_id, limit=limit, lang=lang)

    def feedback(self, query: str, document_id: int, action: str = "click") -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO search_events (query, normalized_query, clicked_document_id, "
                "action, created_at) VALUES (?, ?, ?, ?, ?)",
                (query, query.strip().lower(), document_id, action, now_ts()),
            )
            if action in ("open", "reveal"):
                conn.execute(
                    "UPDATE documents SET open_count = open_count + 1, last_opened_at = ? "
                    "WHERE id = ?",
                    (now_ts(), document_id),
                )

    def suggestions(self, lang: str = DEFAULT_LANG) -> dict[str, Any]:
        queries = [
            row["query"]
            for row in self.db.fetchall(
                "SELECT query, MAX(created_at) AS latest FROM search_events "
                "WHERE query != '' GROUP BY normalized_query ORDER BY latest DESC LIMIT 8"
            )
        ]
        recent = self._recent_items(SearchFilters(), 8, lang)
        return {"queries": queries, "recent": recent}

    # -------------------------------------------------------------- internals

    def _recent_items(
        self, filters: SearchFilters, limit: int, lang: str = DEFAULT_LANG
    ) -> list[dict[str, Any]]:
        rows = recent_documents(self.db, filters, limit=limit)
        return [
            {
                "document_id": int(row["id"]),
                "score": 0.0,
                "relevance": 0.0,
                "channels": [],
                "tags": self._tags(dict(row), set(), lang),
                "matches": [],
                "related": [],
                "document": _summary(dict(row), lang),
            }
            for row in rows
        ]

    def _build_item(
        self,
        item: dict[str, Any],
        parsed: ParsedQuery,
        *,
        chunk_lookup: dict[int, dict[str, Any]],
        semantic_chunks: dict[int, int],
        include_related: bool,
        lang: str = DEFAULT_LANG,
    ) -> dict[str, Any]:
        row = item["row"]
        document_id = item["document_id"]
        matches: list[dict[str, Any]] = []
        seen_chunks: set[int] = set()

        for chunk in [r for r in chunk_lookup.values() if int(r["document_id"]) == document_id][
            :3
        ]:
            chunk_id = int(chunk["chunk_id"])
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)
            snippet = make_snippet(chunk.get("text", ""), parsed.highlight_terms)
            matches.append(
                {
                    "chunk_id": chunk_id,
                    "source": "keyword",
                    "location_label": location_label(
                        _parse_json(chunk.get("location_json"), {}),
                        lang,
                        chunk.get("location_label"),
                    ),
                    "location_json": _parse_json(chunk.get("location_json"), {}),
                    "snippet": snippet.text,
                    "spans": [list(span) for span in snippet.spans],
                    "matched": snippet.matched,
                }
            )

        semantic_chunk_id = semantic_chunks.get(document_id)
        if semantic_chunk_id and semantic_chunk_id not in seen_chunks:
            chunk = chunk_lookup.get(semantic_chunk_id) or chunk_by_id(
                self.db, semantic_chunk_id
            )
            if chunk:
                seen_chunks.add(semantic_chunk_id)
                snippet = plain_snippet(chunk.get("text", ""))
                matches.append(
                    {
                        "chunk_id": semantic_chunk_id,
                        "source": "semantic",
                        "location_label": location_label(
                            _parse_json(chunk.get("location_json"), {}),
                            lang,
                            chunk.get("location_label"),
                        ),
                        "location_json": _parse_json(chunk.get("location_json"), {}),
                        "snippet": snippet.text,
                        "spans": [],
                        "matched": False,
                    }
                )

        if not matches and row.get("status") in ("indexed", "indexed_partial"):
            first_chunks = chunks_for_document(self.db, document_id, limit=1)
            if first_chunks:
                chunk = first_chunks[0]
                snippet = plain_snippet(chunk.get("text", ""))
                matches.append(
                    {
                        "chunk_id": int(chunk["id"]),
                        "source": "document",
                        "location_label": location_label(
                            _parse_json(chunk.get("location_json"), {}),
                            lang,
                            chunk.get("location_label"),
                        ),
                        "location_json": _parse_json(chunk.get("location_json"), {}),
                        "snippet": snippet.text,
                        "spans": [],
                        "matched": False,
                    }
                )

        related: list[dict[str, Any]] = []
        if include_related and row.get("status") not in ("missing",):
            try:
                related = self.related_service.related(document_id, limit=3, lang=lang)
            except Exception:
                related = []

        tags = self._tags(row, set(item.get("channels", [])), lang)
        return {
            "document_id": document_id,
            "score": round(float(item["score"]), 4),
            "relevance": round(float(item["relevance"]), 4),
            "channels": item.get("channels", []),
            "tags": tags,
            "matches": matches,
            "related": related,
            "document": _summary(row, lang),
        }

    def _tags(
        self, row: dict[str, Any], channels: set[str], lang: str = DEFAULT_LANG
    ) -> list[str]:
        tags: list[str] = []
        if "keyword" in channels:
            tags.append(translate("tag.keyword", lang))
        if "file" in channels:
            tags.append(translate("tag.filename", lang))
        if "semantic" in channels:
            tags.append(translate("tag.semantic", lang))
        if "fuzzy" in channels:
            tags.append(translate("tag.fuzzy", lang))
        if row.get("status") in ("encrypted", "encrypted_suspected"):
            tags.append(
                translate(
                    "tag.encrypted" if row["status"] == "encrypted" else "tag.encrypted_suspected",
                    lang,
                )
            )
        if row.get("status") == "indexed_partial":
            tags.append(translate("tag.partial", lang))
        mtime_ns = row.get("mtime_ns") or 0
        if mtime_ns:
            age_days = (
                datetime.now(UTC)
                - datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=UTC)
            ).total_seconds() / 86400.0
            if age_days <= _RECENT_TAG_DAYS:
                tags.append(translate("tag.recent_modified", lang))
        if row.get("last_opened_at"):
            tags.append(translate("tag.recent_opened", lang))
        return tags

    def _ordered_chunk_documents(self, chunk_rows: list[dict[str, Any]]) -> list[int]:
        best: dict[int, float] = {}
        for row in chunk_rows:
            document_id = int(row["document_id"])
            rank = float(row.get("rank", 0.0))
            if document_id not in best or rank < best[document_id]:
                best[document_id] = rank
        return [document_id for document_id, _ in sorted(best.items(), key=lambda item: item[1])]

    def _fuzzy_documents(
        self, query: str, filters: SearchFilters
    ) -> list[tuple[int, float]]:
        if not query.strip():
            return []
        filter_sql, filter_params = build_filter_sql(filters)
        placeholders = ", ".join("?" for _ in VISIBLE_STATUSES)
        where = [f"d.status IN ({placeholders})"]
        params: list[Any] = list(VISIBLE_STATUSES)
        if filter_sql:
            where.append(filter_sql)
            params.extend(filter_params)
        rows = self.db.fetchall(
            f"SELECT d.id, d.name, d.title FROM documents d WHERE {' AND '.join(where)} "
            "ORDER BY d.mtime_ns DESC LIMIT 20000",
            params,
        )
        if not rows:
            return []
        choices = {
            int(row["id"]): f"{row['title'] or ''} {row['name'] or ''}".strip()
            for row in rows
        }
        extracted = process.extract(
            query,
            choices,
            scorer=fuzz.partial_ratio,
            limit=FUZZY_TITLE_LIMIT,
            score_cutoff=FUZZY_THRESHOLD,
        )
        results: list[tuple[int, float]] = []
        for item in extracted:
            if len(item) >= 3:
                _, score, key = item[0], item[1], item[2]
            else:  # pragma: no cover - depends on rapidfuzz version
                _, score = item[0], item[1]
                key = None
            if key is None:
                continue
            results.append((int(key), float(score)))
        return results

    @staticmethod
    def _merge_by_key(
        first: list[dict[str, Any]], second: list[dict[str, Any]], key: str
    ) -> list[dict[str, Any]]:
        seen = {item[key] for item in first}
        merged = list(first)
        for item in second:
            if item[key] not in seen:
                merged.append(item)
                seen.add(item[key])
        return merged
