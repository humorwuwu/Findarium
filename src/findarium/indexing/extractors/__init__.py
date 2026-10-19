from __future__ import annotations

from pathlib import Path

from ...i18n import msg
from .base import (
    Block,
    CorruptDocumentError,
    DocumentTooLargeError,
    EncryptedDocumentError,
    ExtractedDocument,
    ExtractionError,
    LinkRef,
    UnsupportedDocumentError,
)

EXTENSION_ALIASES = {
    ".markdown": ".md",
    ".htm": ".html",
}


def normalized_extension(path: Path) -> str:
    ext = path.suffix.lower()
    return EXTENSION_ALIASES.get(ext, ext)


def extract_document(path: Path) -> ExtractedDocument:
    ext = normalized_extension(path)
    if ext == ".pdf":
        from . import pdf

        return pdf.extract(path)
    if ext == ".docx":
        from . import docx

        return docx.extract(path)
    if ext == ".xlsx":
        from . import xlsx

        return xlsx.extract(path)
    if ext == ".pptx":
        from . import pptx

        return pptx.extract(path)
    if ext == ".md":
        from . import markdown

        return markdown.extract(path)
    if ext == ".html":
        from . import html

        return html.extract(path)
    if ext == ".txt":
        from . import text

        return text.extract_txt(path)
    if ext == ".csv":
        from . import text

        return text.extract_csv(path)
    raise UnsupportedDocumentError(msg("error.unsupported_type", ext=ext))


__all__ = [
    "Block",
    "CorruptDocumentError",
    "DocumentTooLargeError",
    "EncryptedDocumentError",
    "ExtractedDocument",
    "ExtractionError",
    "LinkRef",
    "UnsupportedDocumentError",
    "extract_document",
    "normalized_extension",
]
