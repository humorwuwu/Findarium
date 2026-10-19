from __future__ import annotations

from pathlib import Path

import pymupdf

from ...i18n import index_lang, msg, translate
from .base import Block, CorruptDocumentError, ExtractedDocument, count_words


def extract(path: Path) -> ExtractedDocument:
    try:
        document = pymupdf.open(str(path))
    except Exception as exc:
        raise CorruptDocumentError(msg("protect.pdf_unreadable", error=str(exc))) from exc

    if document.needs_pass:
        document.close()
        from .base import EncryptedDocumentError

        raise EncryptedDocumentError(msg("error.pdf_password"))

    metadata = document.metadata or {}
    title = (metadata.get("title") or "").strip() or path.stem
    author = (metadata.get("author") or "").strip() or None
    blocks: list[Block] = []
    all_text: list[str] = []
    empty_pages: list[int] = []

    try:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            text = page.get_text("text").strip()
            if not text:
                empty_pages.append(page_index + 1)
                continue
            number = page_index + 1
            blocks.append(
                Block(
                    kind="page",
                    text=text,
                    location_label=translate("location.page", index_lang(), number=number),
                    location_json={"page": number},
                    heading_path=[],
                )
            )
            all_text.append(text)
    finally:
        page_count = document.page_count
        document.close()

    warnings: list[str] = []
    if empty_pages and len(empty_pages) == page_count:
        warnings.append(msg("warn.pdf_no_text_layer"))
    elif empty_pages:
        warnings.append(msg("warn.pdf_empty_pages", count=len(empty_pages)))

    full_text = "\n\n".join(all_text)
    return ExtractedDocument(
        title=title,
        author=author,
        metadata={
            "subject": metadata.get("subject"),
            "keywords": metadata.get("keywords"),
            "creator": metadata.get("creator"),
            "producer": metadata.get("producer"),
            "creationDate": metadata.get("creationDate"),
            "modDate": metadata.get("modDate"),
        },
        blocks=blocks,
        warnings=warnings,
        partial=bool(empty_pages) and bool(blocks),
        page_count=page_count,
        word_count=count_words(full_text),
    )
