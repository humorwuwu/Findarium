"""Message catalog and language plumbing for the bilingual (zh-CN / en) app.

Two kinds of text live here:

* **Request-time text** — search tags, explanations, related-document reasons,
  HTTP error details. The API resolves a language per request (``?lang=`` then
  ``X-Findarium-Lang`` then the stored ``language`` setting) and calls
  :func:`translate`.
* **Stored text** — messages written into SQLite while indexing (``documents.error``,
  document warnings, ``sources.last_error``). Background threads have no request,
  so those are stored as :func:`msg` payloads (a small JSON envelope holding the
  key and its parameters) and translated when they are read back with
  :func:`localize_stored`. Rows written by older versions hold plain text and are
  passed through unchanged, so no migration is needed.

Language codes are ``"zh-CN"`` and ``"en"``; ``"auto"`` means "follow the system".
"""

from __future__ import annotations

import json
import locale
import os
from collections.abc import Mapping
from typing import Any

LANGS = ("zh-CN", "en")
DEFAULT_LANG = "zh-CN"
AUTO_LANG = "auto"

# key -> (zh-CN, en). Placeholders use str.format syntax.
_MESSAGES: dict[str, tuple[str, str]] = {
    # ----- list separators (language dependent) -----
    "list.separator": ("、", ", "),
    "list.clause_separator": ("；", "; "),
    # ----- result tags -----
    "tag.keyword": ("关键词", "Keyword"),
    "tag.filename": ("文件名", "Filename"),
    "tag.semantic": ("语义相关", "Semantic"),
    "tag.fuzzy": ("模糊匹配", "Fuzzy"),
    "tag.encrypted": ("已加密", "Encrypted"),
    "tag.encrypted_suspected": ("疑似加密", "Possibly encrypted"),
    "tag.partial": ("部分索引", "Partial index"),
    "tag.recent_modified": ("最近修改", "Recently modified"),
    "tag.recent_opened": ("最近打开", "Recently opened"),
    # ----- search explanations -----
    "explain.match_sources": ("匹配来源：{sources}", "Matched by: {sources}"),
    "explain.source.keyword": ("正文关键词", "content keywords"),
    "explain.source.file": ("文件名/路径", "filename/path"),
    "explain.source.semantic": ("语义相似", "semantic similarity"),
    "explain.source.fuzzy": ("模糊匹配", "fuzzy match"),
    "explain.no_query": ("未输入关键词，显示最近修改的文档", "No keywords; showing recently modified documents"),
    "explain.no_match": ("没有匹配结果，显示最近文档", "No matches; showing recent documents"),
    "explain.time_range": ("时间范围：{value}", "Time range: {value}"),
    "explain.prefer_recent": (
        "偏好最近修改或打开过的文档",
        "Favoring recently modified or opened documents",
    ),
    "explain.folder": ("目录：{value}", "Folder: {value}"),
    "explain.time_filter": ("时间过滤：{value}", "Date filter: {value}"),
    "explain.size_filter": ("大小过滤：{value}", "Size filter: {value}"),
    # ----- date words used in explanations -----
    "date.today": ("今天", "today"),
    "date.yesterday": ("昨天", "yesterday"),
    "date.before_yesterday": ("前天", "the day before yesterday"),
    "date.this_week": ("本周", "this week"),
    "date.last_week": ("上周", "last week"),
    "date.this_month": ("本月", "this month"),
    "date.last_month": ("上个月", "last month"),
    "date.this_year": ("今年", "this year"),
    "date.last_year": ("去年", "last year"),
    "date.recent": ("最近 {amount}{unit}", "last {amount} {unit}"),
    "date.month": ("{year}年{month}月", "{year}-{month:02d}"),
    "date.unit.day": ("天", "days"),
    "date.unit.week": ("周", "weeks"),
    "date.unit.month": ("个月", "months"),
    "date.unit.year": ("年", "years"),
    # ----- related documents -----
    "related.similarity": ("内容相似度 {score}", "Content similarity {score}"),
    "related.shared_keywords": ("共同关键词：{names}", "Shared keywords: {names}"),
    "related.links_to_this": ("文档中链接到本文件", "Linked from another document"),
    "related.referenced_by": ("本文件被其他文档引用", "Referenced by another document"),
    "related.duplicate": ("内容完全相同（可能是副本）", "Identical content (possible copy)"),
    "related.similar_name": ("文件名高度相似", "Very similar filename"),
    "related.generic": ("相关", "Related"),
    # ----- locations -----
    "location.page": ("第 {number} 页", "Page {number}"),
    "location.slide": ("第 {number} 张幻灯片", "Slide {number}"),
    "location.sheet_rows": ("{sheet} · 行 {start}-{end}", "{sheet} · rows {start}-{end}"),
    "location.rows": ("行 {start}-{end}", "Rows {start}-{end}"),
    "location.lines": ("第 {start}-{end} 行", "Lines {start}-{end}"),
    "location.line": ("第 {line} 行", "Line {line}"),
    "location.paragraph": ("段落 {index}", "Paragraph {index}"),
    "location.table": ("表格 {index}", "Table {index}"),
    "location.header": ("页眉", "Header"),
    "location.footer": ("页脚", "Footer"),
    "location.truncated": ("截断提示", "Truncation notice"),
    # ----- labels embedded in extracted text (written at index time) -----
    "text.column_header": ("列标题", "Column headers"),
    "text.columns": ("列", "Columns"),
    "text.notes": ("备注", "Notes"),
    "text.slide_number": ("幻灯片 {number}", "Slide {number}"),
    # ----- protected / encrypted documents -----
    "protect.office_encrypted_zip": ("检测到 Office 加密包", "Office encrypted package detected"),
    "protect.office_unexpected_zip": (
        "Office 文件缺少 OOXML 结构，疑似受保护或已损坏",
        "Office file lacks OOXML structure; possibly protected or damaged",
    ),
    "protect.zip_encrypted": ("ZIP 内容已加密", "ZIP contents are encrypted"),
    "protect.office_bad_zip": (
        "无法读取 Office 文件内容，疑似受保护",
        "Could not read the Office file; possibly protected",
    ),
    "protect.office_password": (
        "检测到 Office 密码加密容器",
        "Office password-protected container detected",
    ),
    "protect.office_ole_container": (
        "Office 扩展名对应 OLE 容器，可能是加密文档或旧格式",
        "OLE container with an Office extension; may be encrypted or a legacy format",
    ),
    "protect.high_entropy": (
        "文件头无法识别且熵较高，疑似受保护或加密",
        "Unrecognized header with high entropy; possibly protected or encrypted",
    ),
    "protect.pdf_unrecognized": (
        "PDF 文件头无法识别，疑似受保护",
        "Unrecognized PDF header; possibly protected",
    ),
    "protect.pdf_password": ("PDF 需要密码或权限密码", "PDF requires a password"),
    "protect.pdf_no_decrypt": ("PDF 无法解密", "PDF could not be decrypted"),
    "protect.pdf_unreadable": ("PDF 无法打开：{error}", "Could not open PDF: {error}"),
    "protect.detected": ("检测到受保护内容", "Protected content detected"),
    # ----- extraction warnings -----
    "warn.truncated": (
        "文档内容超过索引字符上限，已截断",
        "Document exceeds the indexing character limit; the index was truncated",
    ),
    "warn.pdf_no_text_layer": (
        "PDF 没有可提取的文本层，可能是扫描件（暂不做 OCR）",
        "PDF has no extractable text layer; it may be a scan (no OCR yet)",
    ),
    "warn.pdf_empty_pages": (
        "{count} 页没有可提取的文本层（可能是扫描页）",
        "{count} pages have no extractable text layer (possibly scanned)",
    ),
    "warn.xlsx_rows_exceeded": (
        "工作表“{sheet}”超过 {limit} 行，仅索引前部分内容",
        "Sheet “{sheet}” exceeds {limit} rows; only the first part is indexed",
    ),
    "warn.markdown_truncated": (
        "文件超过字符上限，后续内容未索引（原始行数：{lines}）",
        "File exceeds the character limit; the rest was not indexed (original lines: {lines})",
    ),
    "warn.csv_truncated": (
        "CSV 超过索引上限（最多 {rows} 行或 {chars} 字符），已截断",
        "CSV exceeds the index limit (at most {rows} rows or {chars} characters); truncated",
    ),
    # ----- extraction errors -----
    "error.too_large": (
        "文件超过 {limit} MB 上限，未索引",
        "File exceeds the {limit} MB limit and was not indexed",
    ),
    "error.csv_too_large": ("CSV 超过 {limit} MB 限制", "CSV exceeds the {limit} MB limit"),
    "error.no_permission": ("没有读取权限：{error}", "No read permission: {error}"),
    "error.no_permission_short": ("没有读取权限", "No read permission"),
    "error.corrupt": (
        "文件损坏或无法解析：{error}",
        "File is damaged or cannot be parsed: {error}",
    ),
    "error.parse_failed": ("解析失败：{error}", "Parsing failed: {error}"),
    "error.open_failed": (
        "无法打开 {format} 文件：{error}",
        "Could not open the {format} file: {error}",
    ),
    "error.unsupported_type": ("暂不支持的文件类型：{ext}", "Unsupported file type: {ext}"),
    "error.pdf_password": ("PDF 需要密码", "PDF requires a password"),
    "error.job_missing_path": (
        "任务缺少路径或来源",
        "The job is missing a path or source",
    ),
    "error.job_missing_document": (
        "探测任务缺少 document_id",
        "The probe job is missing a document_id",
    ),
    "error.source_unavailable": (
        "来源目录暂不可用",
        "The source folder is temporarily unavailable",
    ),
    "error.file_outside_sources": (
        "文件不在已索引目录内",
        "The file is not inside an indexed folder",
    ),
    # ----- sources -----
    "source.unavailable": ("来源目录不可用", "Source folder unavailable"),
    "source.not_cleared": (
        "来源目录不可用，未清理已有索引",
        "Source folder unavailable; the existing index was kept",
    ),
    # ----- API and startup errors -----
    "err.library_not_initialized": (
        "索引库尚未初始化",
        "The index library is not initialized yet",
    ),
    "err.library_init_failed": (
        "初始化索引库失败：{error}",
        "Could not initialize the index library: {error}",
    ),
    "err.library_move_failed": (
        "迁移索引库失败：{error}",
        "Could not move the index library: {error}",
    ),
    "err.folder_picker_failed": (
        "无法打开系统目录选择器",
        "Could not open the system folder picker",
    ),
    "err.folder_unavailable": (
        "目录不存在或不可访问",
        "The folder does not exist or is not accessible",
    ),
    "err.folder_overlap": (
        "该目录与已索引目录重叠，请避免重复添加",
        "This folder overlaps an indexed folder; avoid adding it twice",
    ),
    "err.document_not_found": ("文档不存在", "Document not found"),
    "err.pdf_only": ("只有 PDF 支持应用内预览", "Only PDFs can be previewed in the app"),
    "err.file_missing": ("文件已被移动或删除", "The file was moved or deleted"),
    "err.file_outside_sources": (
        "文件不在已索引目录内",
        "The file is not inside an indexed folder",
    ),
    "err.invalid_token": ("无效的本地令牌", "Invalid local token"),
    "err.frontend_not_built": (
        "前端尚未构建。运行 <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>，"
        "或用 <code>FINDARIUM_DEV_URL</code> 指向 Vite 开发服务器。",
        "The frontend has not been built. Run <code>cd frontend &amp;&amp; npm install "
        "&amp;&amp; npm run build</code>, or point <code>FINDARIUM_DEV_URL</code> at the Vite dev server.",
    ),
    "err.library_not_a_folder": (
        "索引库位置必须是一个文件夹",
        "The library location must be a folder",
    ),
    "err.library_create_failed": (
        "无法创建索引库目录：{error}",
        "Could not create the library folder: {error}",
    ),
    "err.library_not_writable": (
        "索引库目录不可读写",
        "The library folder is not readable or writable",
    ),
    "err.service_failed": ("本地服务启动失败", "Could not start the local service"),
    "err.window_failed": (
        "无法启动桌面窗口：{error}",
        "Could not open the desktop window: {error}",
    ),
    "err.use_headless": (
        "请改用 --headless 访问 {url}",
        "Use --headless and open {url} instead",
    ),
    "err.db_version_too_new": (
        "索引库版本 {version} 高于当前应用支持的版本 {supported}",
        "Library version {version} is newer than this app supports ({supported})",
    ),
    "err.db_init_failed": (
        "初始化数据库失败：{error}",
        "Could not initialize the database: {error}",
    ),
    # ----- native dialogs -----
    "native.choose_folder": ("选择文件夹", "Choose a folder"),
    # ----- CLI help -----
    "cli.headless": ("只启动本地服务，不打开桌面窗口", "Start the local service only, without a window"),
    "cli.port": ("本地服务端口", "Port for the local service"),
    "cli.library": ("指定索引库目录（开发用）", "Use this index library folder (development)"),
    "cli.dev_url": (
        "使用 Vite 开发服务器地址（也可用 FINDARIUM_DEV_URL 环境变量）",
        "Load the UI from a Vite dev server (or set FINDARIUM_DEV_URL)",
    ),
    "cli.no_embedding": ("禁用语义向量，只保留关键词检索", "Disable semantic vectors; keyword search only"),
    "cli.token": ("固定本地 API token（调试用）", "Use a fixed local API token (debugging)"),
    "cli.lang": (
        "界面与终端文案语言：auto、zh-CN 或 en",
        "Language for the UI and terminal text: auto, zh-CN or en",
    ),
}

# Stored messages are JSON envelopes; anything else is legacy plain text.
_ENVELOPE_KEY = "k"
_ENVELOPE_PARAMS = "p"


def resolve_lang(value: str | None) -> str:
    """Normalize a language tag (``zh-Hans``, ``en_US``, ``auto``) to a supported code."""
    if not value:
        return DEFAULT_LANG
    text = value.strip().lower().replace("_", "-")
    if text.startswith("zh"):
        return "zh-CN"
    if text.startswith("en"):
        return "en"
    return DEFAULT_LANG


def system_lang() -> str:
    """Best guess at the user's language from the environment."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return resolve_lang(value.split(".", 1)[0])
    try:
        code = locale.getlocale()[0]
    except (TypeError, ValueError):
        code = None
    return resolve_lang(code)


def resolve_setting(value: str | None) -> str:
    """Resolve the stored ``language`` setting.

    ``auto`` follows the system; an absent setting (a library created before this
    setting existed, or a caller that never chose one) keeps the historical
    Chinese default. The UI always sends an explicit language, so ``auto`` is
    what decides in practice.
    """
    if value is None or not value.strip():
        return DEFAULT_LANG
    if value.strip().lower() == AUTO_LANG:
        return system_lang()
    return resolve_lang(value)


_index_lang: str = DEFAULT_LANG


def set_index_lang(value: str | None) -> None:
    """Set the language used for text baked into the index (``None`` = system)."""
    global _index_lang
    _index_lang = resolve_setting(value)


def index_lang() -> str:
    """Language for text stored while indexing (labels, in-text prefixes)."""
    return _index_lang


def translate(key: str, lang: str = DEFAULT_LANG, **params: Any) -> str:
    """Render ``key`` in ``lang``; unknown keys are returned unchanged."""
    entry = _MESSAGES.get(key)
    if entry is None:
        return key
    template = entry[1] if resolve_lang(lang) == "en" else entry[0]
    if not params:
        return template
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError):
        return template


def msg(key: str, **params: Any) -> str:
    """Serialize a message for storage, to be translated later on read."""
    payload: dict[str, Any] = {_ENVELOPE_KEY: key}
    if params:
        payload[_ENVELOPE_PARAMS] = params
    return json.dumps(payload, ensure_ascii=False)


def localize_stored(value: Any, lang: str = DEFAULT_LANG) -> Any:
    """Translate a stored message payload; legacy plain text passes through."""
    if not isinstance(value, str) or not value.startswith("{"):
        return value
    try:
        payload = json.loads(value)
    except ValueError:
        return value
    if not isinstance(payload, dict) or _ENVELOPE_KEY not in payload:
        return value
    params = payload.get(_ENVELOPE_PARAMS)
    if not isinstance(params, dict):
        params = {}
    return translate(str(payload[_ENVELOPE_KEY]), lang, **params)


def localize_list(values: Any, lang: str = DEFAULT_LANG) -> list[Any]:
    if not isinstance(values, (list, tuple)):
        return []
    return [localize_stored(value, lang) for value in values]


def join_list(values: Any, lang: str = DEFAULT_LANG) -> str:
    separator = translate("list.separator", lang)
    return separator.join(str(value) for value in values)


def location_label(
    location: Mapping[str, Any] | None,
    lang: str = DEFAULT_LANG,
    fallback: str | None = None,
) -> str | None:
    """Build a display label from language-neutral ``location_json``.

    Falls back to ``fallback`` (the label stored at index time) when the shape is
    not recognized, so labels stay correct in both languages without reindexing.
    """

    if not isinstance(location, Mapping):
        return fallback
    if location.get("truncated"):
        return translate("location.truncated", lang)
    if isinstance(location.get("page"), int):
        return translate("location.page", lang, number=location["page"])
    if isinstance(location.get("slide"), int):
        return translate("location.slide", lang, number=location["slide"])
    sheet = location.get("sheet")
    row_start = location.get("row_start")
    if isinstance(sheet, str) and row_start is not None:
        return translate(
            "location.sheet_rows",
            lang,
            sheet=sheet,
            start=row_start,
            end=location.get("row_end", row_start),
        )
    if row_start is not None:
        return translate(
            "location.rows",
            lang,
            start=row_start,
            end=location.get("row_end", row_start),
        )
    line_start = location.get("line_start")
    if line_start is not None:
        return translate(
            "location.lines",
            lang,
            start=line_start,
            end=location.get("line_end", line_start),
        )
    if isinstance(location.get("line"), int):
        return translate("location.line", lang, line=location["line"])
    if isinstance(location.get("paragraph"), int):
        return translate("location.paragraph", lang, index=location["paragraph"])
    if isinstance(location.get("table"), int):
        return translate("location.table", lang, index=location["table"])
    part = location.get("part")
    if part in ("header", "footer"):
        return translate(f"location.{part}", lang)
    heading = location.get("heading_path")
    if isinstance(heading, (list, tuple)) and heading:
        return " / ".join(str(item) for item in heading)
    return fallback
