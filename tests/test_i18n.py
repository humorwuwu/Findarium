from __future__ import annotations

import re
from pathlib import Path

import pytest

from findarium import i18n
from findarium.i18n import (
    _MESSAGES,
    DEFAULT_LANG,
    LANGS,
    join_list,
    localize_list,
    localize_stored,
    location_label,
    msg,
    resolve_lang,
    resolve_setting,
    translate,
)

_PLACEHOLDER = re.compile(r"\{([a-z_]+)(?::[^}]*)?\}")

# Chinese is allowed in these modules: query parsing patterns, the CJK
# tokenizer's character ranges, the word counter and the bilingual window title.
_CJK_ALLOWED = {
    "i18n.py",
    "config.py",
    "search/query.py",
    "indexing/tokenizer.py",
    "indexing/protection.py",  # detection tokens matched against parser errors
    "indexing/extractors/base.py",  # CJK range used to count words
    "indexing/extractors/docx.py",  # "标题 1" heading style pattern
}
_CJK = re.compile(r"[一-鿿]")


def test_catalog_covers_every_language():
    assert LANGS == ("zh-CN", "en")
    assert DEFAULT_LANG == "zh-CN"
    for key, entry in _MESSAGES.items():
        assert len(entry) == len(LANGS), key
        for value in entry:
            assert isinstance(value, str) and value.strip(), key


def test_placeholders_match_between_languages():
    for key, (chinese, english) in _MESSAGES.items():
        assert set(_PLACEHOLDER.findall(chinese)) == set(_PLACEHOLDER.findall(english)), key


def test_translate_uses_language_and_params():
    assert translate("tag.keyword", "zh-CN") == "关键词"
    assert translate("tag.keyword", "en") == "Keyword"
    assert translate("explain.folder", "en", value="Reports") == "Folder: Reports"
    assert translate("explain.folder", "zh-CN", value="报告") == "目录：报告"


def test_translate_unknown_key_passes_through():
    assert translate("not.a.key", "en") == "not.a.key"


def test_missing_params_do_not_crash():
    assert translate("explain.folder", "en") == "Folder: {value}"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("zh-Hans", "zh-CN"),
        ("zh_CN", "zh-CN"),
        ("zh", "zh-CN"),
        ("en-US", "en"),
        ("EN", "en"),
        ("fr", "zh-CN"),
        (None, "zh-CN"),
        ("", "zh-CN"),
    ],
)
def test_resolve_lang(value, expected):
    assert resolve_lang(value) == expected


def test_resolve_setting_follows_system_for_auto(monkeypatch):
    monkeypatch.setattr(i18n, "system_lang", lambda: "en")
    assert resolve_setting("auto") == "en"
    assert resolve_setting("zh-CN") == "zh-CN"
    assert resolve_setting("en") == "en"
    # No stored setting keeps the historical default rather than guessing.
    assert resolve_setting(None) == DEFAULT_LANG
    assert resolve_setting("") == DEFAULT_LANG


def test_stored_messages_round_trip():
    stored = msg("error.no_permission", error="denied")
    assert localize_stored(stored, "zh-CN") == "没有读取权限：denied"
    assert localize_stored(stored, "en") == "No read permission: denied"


def test_stored_legacy_text_passes_through():
    # Rows written before i18n hold plain sentences and must stay readable.
    assert localize_stored("检测到 Office 加密包", "en") == "检测到 Office 加密包"
    assert localize_stored(None, "en") is None
    assert localize_stored("{not json", "en") == "{not json"
    assert localize_stored('{"other": 1}', "en") == '{"other": 1}'
    assert localize_list(["检测到 Office 加密包"], "en") == ["检测到 Office 加密包"]


def test_join_list_uses_language_separator():
    assert join_list(["a", "b"], "zh-CN") == "a、b"
    assert join_list(["a", "b"], "en") == "a, b"


@pytest.mark.parametrize(
    ("location", "chinese", "english"),
    [
        ({"page": 3}, "第 3 页", "Page 3"),
        ({"slide": 7}, "第 7 张幻灯片", "Slide 7"),
        (
            {"sheet": "预算", "row_start": 1, "row_end": 35},
            "预算 · 行 1-35",
            "预算 · rows 1-35",
        ),
        ({"row_start": 4, "row_end": 9}, "行 4-9", "Rows 4-9"),
        ({"line_start": 10, "line_end": 20}, "第 10-20 行", "Lines 10-20"),
        ({"paragraph": 5}, "段落 5", "Paragraph 5"),
        ({"table": 2}, "表格 2", "Table 2"),
        ({"part": "header"}, "页眉", "Header"),
        ({"part": "footer"}, "页脚", "Footer"),
        ({"truncated": True}, "截断提示", "Truncation notice"),
        ({"heading_path": ["第二章", "付款"]}, "第二章 / 付款", "第二章 / 付款"),
    ],
)
def test_location_label_both_languages(location, chinese, english):
    assert location_label(location, "zh-CN") == chinese
    assert location_label(location, "en") == english


def test_location_label_falls_back_to_stored_label():
    assert location_label({"unknown": 1}, "en", "第 2 页") == "第 2 页"
    assert location_label(None, "en", "第 2 页") == "第 2 页"
    assert location_label({}, "en") is None


def test_no_stray_chinese_outside_the_catalog():
    root = Path(__file__).resolve().parents[1] / "src" / "findarium"
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative in _CJK_ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _CJK.search(line):
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert not offenders, "user-facing Chinese must live in i18n.py:\n" + "\n".join(offenders)
