from __future__ import annotations

import csv
import io
from pathlib import Path

from ...config import (
    MAX_CSV_ROWS,
    MAX_CSV_ROWS_PER_CHUNK,
    MAX_TEXT_CHARS,
)
from .base import (
    Block,
    DocumentTooLargeError,
    ExtractedDocument,
    count_words,
    read_text,
    truncate_text,
)


def extract_txt(path: Path) -> ExtractedDocument:
    text = read_text(path)
    text, truncated = truncate_text(text)
    lines = text.splitlines()
    blocks: list[Block] = []
    buffer: list[str] = []
    start = 1

    def flush(end: int) -> None:
        nonlocal buffer, start
        if not buffer:
            return
        block_text = "\n".join(buffer).strip()
        if block_text:
            blocks.append(
                Block(
                    kind="text",
                    text=block_text,
                    location_label=f"第 {start}-{end} 行",
                    location_json={"line_start": start, "line_end": end},
                )
            )
        buffer = []
        start = end + 1

    for number, line in enumerate(lines, start=1):
        if line.strip():
            if not buffer:
                start = number
            buffer.append(line)
            if sum(len(item) for item in buffer) > 3000:
                flush(number)
        else:
            flush(number - 1)

    flush(len(lines))
    full_text = "\n\n".join(block.text for block in blocks)
    return ExtractedDocument(
        title=path.stem,
        blocks=blocks,
        warnings=["文档内容超过字符上限，索引已截断"] if truncated else [],
        partial=truncated,
        word_count=count_words(full_text),
    )


def extract_csv(path: Path) -> ExtractedDocument:
    size = path.stat().st_size
    if size > 50 * 1024 * 1024:
        raise DocumentTooLargeError("CSV 超过 50 MB 限制")
    text = read_text(path)
    text, truncated = truncate_text(text)
    reader = csv.reader(io.StringIO(text))
    blocks: list[Block] = []
    header: list[str] = []
    group: list[tuple[int, str]] = []
    all_text: list[str] = []
    partial = truncated

    def flush() -> None:
        nonlocal group
        if not group:
            return
        start = group[0][0]
        end = group[-1][0]
        lines = []
        if header:
            lines.append("列: " + " | ".join(header))
        lines.extend(f"{number}: {line}" for number, line in group)
        body = "\n".join(lines)
        blocks.append(
            Block(
                kind="csv",
                text=body,
                location_label=f"行 {start}-{end}",
                location_json={"row_start": start, "row_end": end},
            )
        )
        all_text.append(body)
        group = []

    for number, row in enumerate(reader, start=1):
        if number > MAX_CSV_ROWS:
            partial = True
            break
        values = [value.strip().replace("\n", " ") for value in row]
        if not any(values):
            continue
        if not header:
            header = values
            continue
        line = " | ".join(values)
        group.append((number, line))
        if len(group) >= MAX_CSV_ROWS_PER_CHUNK:
            flush()

    flush()
    full_text = "\n\n".join(all_text)
    warnings = []
    if truncated or partial:
        warnings.append(
            f"CSV 超过索引上限（最多 {MAX_CSV_ROWS} 行或 {MAX_TEXT_CHARS} 字符），已截断"
        )
    return ExtractedDocument(
        title=path.stem,
        blocks=blocks,
        warnings=warnings,
        partial=bool(warnings),
        word_count=count_words(full_text),
    )
