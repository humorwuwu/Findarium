from __future__ import annotations

from pathlib import Path

import pymupdf

from .base import Block, CorruptDocumentError, ExtractedDocument, count_words


def extract(path: Path) -> ExtractedDocument:
    try:
        document = pymupdf.open(str(path))
    except Exception as exc:
        raise CorruptDocumentError(f"无法打开 PDF：{exc}") from exc

    if document.needs_pass:
        document.close()
        from .base import EncryptedDocumentError

        raise EncryptedDocumentError("PDF 需要密码")

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
                    location_label=f"第 {number} 页",
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
        warnings.append("PDF 没有可提取的文本层，可能是扫描件（首版不做 OCR）")
    elif empty_pages:
        warnings.append(f"{len(empty_pages)} 页没有可提取的文本层（可能是扫描页）")

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
