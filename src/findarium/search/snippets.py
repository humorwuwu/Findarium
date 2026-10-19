from __future__ import annotations

import re
from dataclasses import dataclass

_WS = re.compile(r"\s+")


@dataclass
class Snippet:
    text: str
    spans: list[tuple[int, int]]
    matched: bool


def _find_occurrences(haystack: str, needle: str) -> list[tuple[int, int]]:
    if not needle:
        return []
    results: list[tuple[int, int]] = []
    lower_haystack = haystack.lower()
    lower_needle = needle.lower()
    start = 0
    while True:
        index = lower_haystack.find(lower_needle, start)
        if index < 0:
            break
        results.append((index, index + len(needle)))
        start = index + max(1, len(needle))
    return results


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    spans = sorted(spans)
    merged = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def make_snippet(text: str, terms: list[str], max_length: int = 300) -> Snippet:
    text = _WS.sub(" ", text or "").strip()
    if not text:
        return Snippet("", [], False)

    occurrences: list[tuple[int, int]] = []
    for term in terms:
        if not term:
            continue
        occurrences.extend(_find_occurrences(text, term))
    occurrences = _merge_spans(occurrences)

    if not occurrences:
        if len(text) <= max_length:
            return Snippet(text, [], False)
        return Snippet(text[:max_length].rstrip() + "…", [], False)

    first_start, first_end = occurrences[0]
    center = (first_start + first_end) // 2
    start = max(0, center - max_length // 2)
    end = min(len(text), start + max_length)
    start = max(0, end - max_length)

    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    snippet_text = prefix + text[start:end] + suffix
    offset = len(prefix) - start

    spans: list[tuple[int, int]] = []
    for occ_start, occ_end in occurrences:
        if occ_end <= start or occ_start >= end:
            continue
        spans.append((max(0, occ_start + offset), min(len(snippet_text), occ_end + offset)))
    spans = _merge_spans(spans)
    return Snippet(snippet_text, spans, True)


def plain_snippet(text: str, max_length: int = 300) -> Snippet:
    text = _WS.sub(" ", text or "").strip()
    if len(text) <= max_length:
        return Snippet(text, [], False)
    return Snippet(text[:max_length].rstrip() + "…", [], False)
