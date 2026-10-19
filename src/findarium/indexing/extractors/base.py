from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from charset_normalizer import from_bytes

from ...config import MAX_FILE_BYTES, MAX_TEXT_CHARS
from ...i18n import msg
from ..tokenizer import normalize_text


class ExtractionError(RuntimeError):
    """Base class for extraction errors that should be visible to the user."""


class EncryptedDocumentError(ExtractionError):
    pass


class UnsupportedDocumentError(ExtractionError):
    pass


class DocumentTooLargeError(ExtractionError):
    pass


class CorruptDocumentError(ExtractionError):
    pass


@dataclass
class LinkRef:
    href: str
    target_path: str | None = None


@dataclass
class Block:
    kind: str
    text: str
    location_label: str = ""
    location_json: dict[str, Any] = field(default_factory=dict)
    heading_path: list[str] = field(default_factory=list)
    links: list[LinkRef] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    title: str
    author: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    blocks: list[Block] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    partial: bool = False
    page_count: int | None = None
    word_count: int | None = None
    sheet_count: int | None = None

    @property
    def full_text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks if block.text.strip())


def read_text(path: Path) -> str:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise DocumentTooLargeError(
            msg("error.too_large", limit=MAX_FILE_BYTES // (1024 * 1024))
        )
    data = path.read_bytes()
    match = from_bytes(data).best()
    if match is None:
        text = data.decode("utf-8", errors="replace")
    else:
        text = str(match)
    return normalize_text(text)


def truncate_text(text: str, limit: int = MAX_TEXT_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def clean_inline_text(text: str) -> str:
    text = normalize_text(text)
    text = text.replace(" ", " ")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def count_words(text: str) -> int:
    import re

    cjk = len(re.findall(r"[㐀-䶿一-鿿]", text))
    latin = len(re.findall(r"[A-Za-z0-9_]+", text))
    return cjk + latin


def resolve_local_link(base_file: Path, href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith(("#", "http://", "https://", "mailto:", "tel:", "data:")):
        return None
    href = href.split("#", 1)[0].split("?", 1)[0]
    if not href:
        return None
    try:
        target = (base_file.parent / href).resolve()
    except OSError:
        return None
    return str(target)
