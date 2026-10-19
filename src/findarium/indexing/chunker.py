from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..config import CHUNK_OVERLAP_CHARS, MAX_CHUNK_CHARS
from .extractors import ExtractedDocument
from .tokenizer import normalize_text

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*")
_SINGLE_BLOCK_KINDS = {"page", "slide", "sheet", "csv", "table", "heading", "header", "footer"}
_MERGE_KINDS = {"paragraph", "markdown", "html", "text", "code"}


@dataclass
class ChunkData:
    ordinal: int
    kind: str
    text: str
    location_label: str = ""
    location_json: dict[str, Any] = field(default_factory=dict)
    heading_path: list[str] = field(default_factory=list)
    char_start: int = 0
    char_end: int = 0


def _split_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in text.split("\n\n")]
    return [part for part in parts if part]


def _split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    text = normalize_text(text).strip()
    if len(text) <= max_chars:
        return [text] if text else []

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            pieces.append("\n".join(current).strip())
        current = []
        current_len = 0

    for paragraph in _split_paragraphs(text):
        if len(paragraph) > max_chars:
            flush()
            sentences = [s for s in _SENTENCE_SPLIT.split(paragraph) if s.strip()]
            for sentence in sentences:
                if len(sentence) > max_chars:
                    for start in range(0, len(sentence), max_chars - overlap):
                        pieces.append(sentence[start : start + max_chars])
                    continue
                if current_len + len(sentence) > max_chars:
                    flush()
                current.append(sentence)
                current_len += len(sentence)
            flush()
            continue
        if current_len + len(paragraph) + 1 > max_chars:
            flush()
        current.append(paragraph)
        current_len += len(paragraph) + 1
    flush()

    if overlap > 0 and len(pieces) > 1:
        overlapped = [pieces[0]]
        for previous, piece in zip(pieces, pieces[1:], strict=False):
            tail = previous[-overlap:]
            if tail and not piece.startswith(tail):
                overlapped.append(tail + piece)
            else:
                overlapped.append(piece)
        pieces = overlapped
    return pieces


def build_chunks(document: ExtractedDocument, max_chars: int = MAX_CHUNK_CHARS) -> list[ChunkData]:
    chunks: list[ChunkData] = []
    cursor = 0
    buffer: list[str] = []
    buffer_heading: list[str] = []
    buffer_location_label = ""
    buffer_location_json: dict[str, Any] = {}
    buffer_kind = "paragraph"
    ordinal = 0

    def emit(
        text: str,
        kind: str,
        location_label: str,
        location_json: dict[str, Any],
        heading_path: list[str],
    ) -> None:
        nonlocal cursor, ordinal
        text = text.strip()
        if not text:
            return
        start = cursor
        end = start + len(text)
        chunks.append(
            ChunkData(
                ordinal=ordinal,
                kind=kind,
                text=text,
                location_label=location_label,
                location_json=dict(location_json),
                heading_path=list(heading_path),
                char_start=start,
                char_end=end,
            )
        )
        ordinal += 1
        cursor = end + 2

    def flush_buffer() -> None:
        nonlocal buffer, buffer_heading, buffer_location_label, buffer_location_json, buffer_kind
        if not buffer:
            return
        emit(
            "\n".join(buffer),
            buffer_kind,
            buffer_location_label,
            buffer_location_json,
            buffer_heading,
        )
        buffer = []
        buffer_heading = []
        buffer_location_label = ""
        buffer_location_json = {}
        buffer_kind = "paragraph"

    for block in document.blocks:
        text = block.text.strip()
        if not text:
            continue
        if block.kind in _SINGLE_BLOCK_KINDS:
            flush_buffer()
            for piece in _split_long_text(text, max_chars, CHUNK_OVERLAP_CHARS):
                emit(
                    piece,
                    block.kind,
                    block.location_label,
                    block.location_json,
                    block.heading_path,
                )
            continue

        if block.kind not in _MERGE_KINDS:
            flush_buffer()
            for piece in _split_long_text(text, max_chars, CHUNK_OVERLAP_CHARS):
                emit(piece, block.kind, block.location_label, block.location_json, block.heading_path)
            continue

        if buffer and block.heading_path != buffer_heading:
            flush_buffer()
        if not buffer:
            buffer_heading = list(block.heading_path)
            buffer_location_label = block.location_label
            buffer_location_json = dict(block.location_json)
            buffer_kind = block.kind
        projected = sum(len(item) for item in buffer) + len(text) + 1
        if projected > max_chars and buffer:
            flush_buffer()
            buffer_heading = list(block.heading_path)
            buffer_location_label = block.location_label
            buffer_location_json = dict(block.location_json)
            buffer_kind = block.kind
        if len(text) > max_chars:
            flush_buffer()
            for piece in _split_long_text(text, max_chars, CHUNK_OVERLAP_CHARS):
                emit(
                    piece,
                    block.kind,
                    block.location_label,
                    block.location_json,
                    block.heading_path,
                )
        else:
            buffer.append(text)

    flush_buffer()
    return chunks
