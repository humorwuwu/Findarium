from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from .base import (
    Block,
    ExtractedDocument,
    LinkRef,
    count_words,
    read_text,
    resolve_local_link,
    truncate_text,
)

_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_BLOCK_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "tr",
    "pre",
    "blockquote",
    "figcaption",
]


def extract(path: Path) -> ExtractedDocument:
    text = read_text(path)
    text, truncated = truncate_text(text)
    try:
        soup = BeautifulSoup(text, "html.parser")
    except Exception:
        soup = BeautifulSoup(text, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()

    title_tag = soup.find("title")
    first_h1 = soup.find("h1")
    title = (
        (title_tag.get_text(" ", strip=True) if title_tag else "")
        or (first_h1.get_text(" ", strip=True) if first_h1 else "")
        or path.stem
    ).strip()

    body = soup.body or soup
    blocks: list[Block] = []
    heading_stack: list[tuple[int, str]] = []
    all_text: list[str] = []
    links_for_doc: list[LinkRef] = []
    seen_texts: set[str] = set()

    for index, element in enumerate(body.find_all(_BLOCK_TAGS), start=1):
        text_value = " ".join(element.get_text(" ", strip=True).split())
        if not text_value:
            continue
        # Avoid indexing a parent and an identical nested block twice.
        key = text_value[:500]
        if key in seen_texts:
            continue
        seen_texts.add(key)
        name = element.name.lower()
        if name in _HEADING_TAGS:
            level = _HEADING_TAGS[name]
            heading_stack = [item for item in heading_stack if item[0] < level]
            heading_stack.append((level, text_value))
        heading_path = [item[1] for item in heading_stack]
        links: list[LinkRef] = []
        for anchor in element.find_all("a", href=True):
            href = anchor["href"].strip()
            if href and not href.startswith(("#", "javascript:")):
                links.append(
                    LinkRef(href=href, target_path=resolve_local_link(path, href))
                )
        links_for_doc.extend(links)
        kind = "heading" if name in _HEADING_TAGS else "html"
        location_label = (
            " / ".join(heading_path) if heading_path else f"段落 {index}"
        )
        blocks.append(
            Block(
                kind=kind,
                text=text_value,
                location_label=location_label,
                location_json={
                    "block": index,
                    "tag": name,
                    "heading_path": list(heading_path),
                },
                heading_path=list(heading_path),
                links=links,
            )
        )
        all_text.append(text_value)

    # Deduplicate links for the document metadata.
    unique_links: dict[str, LinkRef] = {}
    for link in links_for_doc:
        unique_links.setdefault(link.href, link)

    full_text = "\n\n".join(all_text)
    return ExtractedDocument(
        title=title,
        author=None,
        metadata={
            "links": [
                {"href": link.href, "target_path": link.target_path}
                for link in unique_links.values()
            ]
        },
        blocks=blocks,
        warnings=["文档内容超过字符上限，索引已截断"] if truncated else [],
        partial=truncated,
        word_count=count_words(full_text),
    )
