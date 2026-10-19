from __future__ import annotations

import re
from pathlib import Path

from .base import (
    Block,
    ExtractedDocument,
    LinkRef,
    count_words,
    read_text,
    resolve_local_link,
    truncate_text,
)

_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_WIKI_LINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
_INLINE_NOISE = re.compile(r"(\*\*|__|\*|_|`{1,3}|~~)")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _strip_inline(text: str) -> str:
    text = _MD_LINK.sub(lambda m: m.group(1), text)
    text = _WIKI_LINK.sub(lambda m: m.group(1), text)
    text = _INLINE_NOISE.sub("", text)
    return text.strip()


def _extract_links(path: Path, text: str) -> list[LinkRef]:
    links: list[LinkRef] = []
    seen: set[str] = set()
    for match in _MD_LINK.finditer(text):
        href = match.group(2).strip()
        if href in seen:
            continue
        seen.add(href)
        target = resolve_local_link(path, href)
        links.append(LinkRef(href=href, target_path=target))
    for match in _WIKI_LINK.finditer(text):
        target_name = match.group(1).strip()
        if target_name in seen:
            continue
        seen.add(target_name)
        target = None
        for suffix in ("", ".md", ".markdown", ".txt"):
            candidate = (path.parent / f"{target_name}{suffix}").resolve()
            if candidate.exists():
                target = str(candidate)
                break
        links.append(LinkRef(href=target_name, target_path=target))
    return links


def extract(path: Path) -> ExtractedDocument:
    text = read_text(path)
    text, truncated = truncate_text(text)
    lines = text.splitlines()
    title = ""
    heading_stack: list[tuple[int, str]] = []
    blocks: list[Block] = []
    buffer: list[str] = []
    buffer_start = 0
    buffer_headings: list[str] = []
    links_for_doc: list[LinkRef] = []
    in_fence = False
    all_text: list[str] = []

    def flush_buffer(end_line: int) -> None:
        nonlocal buffer, buffer_start, buffer_headings
        if not buffer:
            return
        raw = "\n".join(buffer)
        links = _extract_links(path, raw)
        links_for_doc.extend(links)
        cleaned = _strip_inline(raw)
        if cleaned:
            heading_path = list(buffer_headings)
            location = {
                "line_start": buffer_start,
                "line_end": end_line,
                "heading_path": heading_path,
            }
            blocks.append(
                Block(
                    kind="markdown",
                    text=cleaned,
                    location_label=(
                        " / ".join(heading_path) if heading_path else f"第 {buffer_start} 行"
                    ),
                    location_json=location,
                    heading_path=heading_path,
                    links=links,
                )
            )
            all_text.append(cleaned)
        buffer = []
        buffer_start = 0
        buffer_headings = []

    for number, line in enumerate(lines, start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            buffer.append(line)
            if not buffer_start:
                buffer_start = number
            continue
        heading = None if in_fence else _ATX_HEADING.match(line)
        if heading:
            flush_buffer(number - 1)
            level = len(heading.group(1))
            heading_text = _strip_inline(heading.group(2))
            if not title and level == 1:
                title = heading_text
            heading_stack = [item for item in heading_stack if item[0] < level]
            heading_stack.append((level, heading_text))
            buffer_headings = [item[1] for item in heading_stack]
            blocks.append(
                Block(
                    kind="heading",
                    text=heading_text,
                    location_label=" / ".join(buffer_headings),
                    location_json={
                        "line_start": number,
                        "line_end": number,
                        "heading_path": list(buffer_headings),
                    },
                    heading_path=list(buffer_headings),
                )
            )
            all_text.append(heading_text)
            continue
        if not line.strip():
            flush_buffer(number - 1)
            continue
        if not buffer_start:
            buffer_start = number
            buffer_headings = [item[1] for item in heading_stack]
        buffer.append(line)
        if sum(len(item) for item in buffer) > 4000:
            flush_buffer(number)

    flush_buffer(len(lines))
    if truncated:
        blocks.append(
            Block(
                kind="warning",
                text=f"文件超过字符上限，后续内容未索引（原始行数：{len(lines)}）",
                location_label="截断提示",
                location_json={"truncated": True},
            )
        )
    if not title:
        title = path.stem
    full_text = "\n\n".join(all_text)
    return ExtractedDocument(
        title=title,
        author=None,
        metadata={"links": [{"href": link.href, "target_path": link.target_path} for link in links_for_doc]},
        blocks=blocks,
        warnings=["文档内容超过字符上限，索引已截断"] if truncated else [],
        partial=truncated,
        word_count=count_words(full_text),
    )
