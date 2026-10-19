from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from ..config import EXT_GROUPS
from ..indexing.tokenizer import (
    build_fts_query,
    normalize_text,
    search_phrase_terms,
)

_EXT_TOKEN = re.compile(r"\b(?:ext|type):([A-Za-z]+)\b", re.IGNORECASE)
_FOLDER_TOKEN = re.compile(r'\bfolder:(?:"([^"]+)"|(\S+))', re.IGNORECASE)
_DATE_TOKEN = re.compile(r"\b(?:modified|mtime|created|ctime|after|before|since)\s*[:=]\s*([<>=]*)\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})", re.IGNORECASE)
_SIZE_TOKEN = re.compile(r"\bsize:([<>]=?)\s*([0-9.]+)\s*(kb|mb|gb|b)?\b", re.IGNORECASE)

_RELATIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"今天|今日"), "today"),
    (re.compile(r"昨天|昨日"), "yesterday"),
    (re.compile(r"前天"), "day_before_yesterday"),
    (re.compile(r"本周|这周|这个星期"), "this_week"),
    (re.compile(r"上周|上个星期|上个周"), "last_week"),
    (re.compile(r"本月|这个月"), "this_month"),
    (re.compile(r"上个月|上月"), "last_month"),
    (re.compile(r"今年|本年"), "this_year"),
    (re.compile(r"去年|上年"), "last_year"),
]
_RECENT_PATTERN = re.compile(r"最近\s*([0-9一二三四五六七八九十两]+)?\s*(天|日|周|星期|个月|月|年)?")
_VAGUE_RECENT = re.compile(r"最近|上次|上回|之前|刚才|这几天|这几天|那天|那个")
_ABSOLUTE_MONTH = re.compile(r"([0-9]{4})\s*年\s*([0-9]{1,2})\s*月")

_FILLER_PATTERNS = [
    re.compile(r"^\s*帮我(找|搜|搜索|查)?(一下|一找)?"),
    re.compile(r"^\s*(找一下|查一下|搜一下|搜索一下)"),
    re.compile(r"^\s*我想(找|要|看看)"),
    re.compile(r"^\s*(请问|麻烦|谢谢)"),
    re.compile(r"^\s*(那个|这个|那些|这些)"),
    re.compile(r"^\s*(关于|有关的|相关的)"),
    re.compile(r"(修改|创建|更新|编辑|保存|整理)的"),
    re.compile(r"的(文件|文档|资料|东西)\s*$"),
    re.compile(r"(一下)\s*$"),
    re.compile(r"^\s*(文件|文档|资料|东西)\s*$"),
]

_CN_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass
class SearchFilters:
    extensions: list[str] = field(default_factory=list)
    after: int | None = None
    before: int | None = None
    date_field: str = "modified"
    folder: str | None = None
    encrypted: str | None = None  # only | exclude | None
    size_min: int | None = None
    size_max: int | None = None
    sort: str = "relevance"

    def as_dict(self) -> dict:
        return {
            "extensions": self.extensions,
            "after": self.after,
            "before": self.before,
            "date_field": self.date_field,
            "folder": self.folder,
            "encrypted": self.encrypted,
            "size_min": self.size_min,
            "size_max": self.size_max,
            "sort": self.sort,
        }


@dataclass
class ParsedQuery:
    raw: str
    content_text: str
    match_query: str | None
    highlight_terms: list[str]
    filters: SearchFilters
    recency_boost: float = 0.0
    explanation: list[str] = field(default_factory=list)

    @property
    def has_text(self) -> bool:
        return bool(self.content_text.strip())


def _parse_cn_number(raw: str) -> int | None:
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if raw in _CN_NUMBERS:
        return _CN_NUMBERS[raw]
    if "十" in raw:
        left, _, right = raw.partition("十")
        tens = _CN_NUMBERS.get(left, 1) if left else 1
        ones = _CN_NUMBERS.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def _day_bounds(moment: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(moment.date(), time.min, tzinfo=moment.tzinfo)
    return start, start + timedelta(days=1)


def _range_for_keyword(keyword: str, now: datetime) -> tuple[datetime, datetime] | None:
    if keyword == "today":
        return _day_bounds(now)
    if keyword == "yesterday":
        return _day_bounds(now - timedelta(days=1))
    if keyword == "day_before_yesterday":
        return _day_bounds(now - timedelta(days=2))
    if keyword == "this_week":
        start = now - timedelta(days=now.weekday())
        return _day_bounds(start)[0], _day_bounds(start + timedelta(days=6))[1]
    if keyword == "last_week":
        start = now - timedelta(days=now.weekday() + 7)
        return _day_bounds(start)[0], _day_bounds(start + timedelta(days=6))[1]
    if keyword == "this_month":
        start = now.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        return _day_bounds(start)[0], _day_bounds(end)[0]
    if keyword == "last_month":
        end = now.replace(day=1)
        start = (end - timedelta(days=1)).replace(day=1)
        return _day_bounds(start)[0], _day_bounds(end)[0]
    if keyword == "this_year":
        start = now.replace(month=1, day=1)
        return _day_bounds(start)[0], _day_bounds(now.replace(year=now.year + 1, month=1, day=1))[0]
    if keyword == "last_year":
        start = now.replace(year=now.year - 1, month=1, day=1)
        return _day_bounds(start)[0], _day_bounds(now.replace(month=1, day=1))[0]
    return None


def _to_epoch(value: datetime) -> int:
    return int(value.timestamp())


def _parse_iso_date(raw: str, end_of_day: bool = False) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            if end_of_day:
                parsed = parsed + timedelta(days=1) - timedelta(seconds=1)
            return parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError:
            continue
    return None


def _apply_relative_dates(text: str, filters: SearchFilters, explanation: list[str]) -> tuple[str, float]:
    now = datetime.now().astimezone()
    recency_boost = 0.0
    for pattern, keyword in _RELATIVE_PATTERNS:
        if pattern.search(text):
            bounds = _range_for_keyword(keyword, now)
            if bounds is not None:
                filters.after = _to_epoch(bounds[0])
                filters.before = _to_epoch(bounds[1])
                filters.date_field = "modified"
                explanation.append(f"时间范围：{pattern.pattern.split('|')[0]}")
                text = pattern.sub(" ", text)

    month_match = _ABSOLUTE_MONTH.search(text)
    if month_match:
        year = int(month_match.group(1))
        month = int(month_match.group(2))
        if 1 <= month <= 12:
            start = datetime(year, month, 1, tzinfo=now.tzinfo)
            end = (start + timedelta(days=32)).replace(day=1)
            filters.after = _to_epoch(start)
            filters.before = _to_epoch(end)
            explanation.append(f"时间范围：{year}年{month}月")
            text = _ABSOLUTE_MONTH.sub(" ", text)

    recent_match = _RECENT_PATTERN.search(text)
    if recent_match and (recent_match.group(1) or recent_match.group(2)):
        amount = _parse_cn_number(recent_match.group(1) or "")
        unit = recent_match.group(2) or "天"
        if amount:
            if unit in ("天", "日"):
                delta = timedelta(days=amount)
            elif unit in ("周", "星期"):
                delta = timedelta(weeks=amount)
            elif unit in ("个月", "月"):
                delta = timedelta(days=amount * 30)
            else:
                delta = timedelta(days=amount)
            filters.after = _to_epoch(now - delta)
            filters.before = _to_epoch(now + timedelta(days=1))
            explanation.append(f"时间范围：最近 {amount}{unit}")
            recency_boost = 1.0
            text = text.replace(recent_match.group(0), " ")

    if _VAGUE_RECENT.search(text) and filters.after is None:
        recency_boost = max(recency_boost, 1.0)
        explanation.append("偏好最近修改或打开过的文档")
        text = _VAGUE_RECENT.sub(" ", text)
    return text, recency_boost


def _clean_fillers(text: str) -> str:
    for pattern in _FILLER_PATTERNS:
        text = pattern.sub(" ", text)
    text = re.sub(r"[，。！？、,.!?;；:：]+", " ", text)
    # Remove particles left dangling after date/filler removal (e.g. 最近7天的报销).
    text = re.sub(r"^[的地得\s]+", "", text)
    text = re.sub(r"[的地得\s]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_query(
    raw: str,
    *,
    extensions: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    folder: str | None = None,
    encrypted: str | None = None,
    sort: str | None = None,
) -> ParsedQuery:
    filters = SearchFilters()
    explanation: list[str] = []
    text = normalize_text(raw or "")

    if extensions:
        filters.extensions = [
            "." + ext.lower().lstrip(".") for ext in extensions if ext.strip()
        ]

    for match in _EXT_TOKEN.finditer(text):
        value = match.group(1).lower()
        if value in EXT_GROUPS:
            filters.extensions.extend(sorted(EXT_GROUPS[value]))
        else:
            filters.extensions.append("." + value)
    text = _EXT_TOKEN.sub(" ", text)

    folder_match = _FOLDER_TOKEN.search(text)
    if folder_match:
        filters.folder = folder_match.group(1) or folder_match.group(2)
        explanation.append(f"目录：{filters.folder}")
        text = _FOLDER_TOKEN.sub(" ", text)

    for match in _DATE_TOKEN.finditer(text):
        operator = match.group(1) or ">="
        parsed = _parse_iso_date(match.group(2), end_of_day=("<" not in operator and ">" not in operator))
        if parsed is None:
            continue
        field_name = match.group(0).split(":", 1)[0].lower()
        filters.date_field = "created" if field_name in ("created", "ctime") else "modified"
        if operator.startswith("<"):
            filters.before = _to_epoch(parsed)
        else:
            filters.after = _to_epoch(parsed)
        explanation.append(f"时间过滤：{match.group(0)}")
    text = _DATE_TOKEN.sub(" ", text)

    for match in _SIZE_TOKEN.finditer(text):
        operator = match.group(1)
        amount = float(match.group(2))
        unit = (match.group(3) or "b").lower()
        multiplier = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}[unit]
        size = int(amount * multiplier)
        if operator.startswith(">"):
            filters.size_min = size
        else:
            filters.size_max = size
        explanation.append(f"大小过滤：{match.group(0)}")
    text = _SIZE_TOKEN.sub(" ", text)

    text, recency_boost = _apply_relative_dates(text, filters, explanation)

    if after:
        parsed = _parse_iso_date(after)
        if parsed:
            filters.after = _to_epoch(parsed)
    if before:
        parsed = _parse_iso_date(before, end_of_day=True)
        if parsed:
            filters.before = _to_epoch(parsed)
    if folder:
        filters.folder = folder
    if encrypted in ("only", "exclude"):
        filters.encrypted = encrypted
    if sort in ("relevance", "modified", "created"):
        filters.sort = sort

    content_text = _clean_fillers(text)
    match_query = build_fts_query(content_text) if content_text else None
    highlight_terms = search_phrase_terms(content_text) if content_text else []

    return ParsedQuery(
        raw=raw,
        content_text=content_text,
        match_query=match_query,
        highlight_terms=highlight_terms,
        filters=filters,
        recency_boost=recency_boost,
        explanation=explanation,
    )
