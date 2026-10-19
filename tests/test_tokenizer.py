from findarium.indexing.tokenizer import (
    build_fts_query,
    search_phrase_terms,
    tokenize_for_fts,
)


def test_cjk_bigrams():
    tokens = tokenize_for_fts("项目合同管理").split()
    assert tokens == ["项目", "目合", "合同", "同管", "管理"]


def test_mixed_text_tokens():
    tokens = tokenize_for_fts("2025 Q3预算 report").split()
    assert "2025" in tokens
    assert "q3" in tokens
    assert "预算" in tokens
    assert "report" in tokens


def test_fts_query_uses_phrase_for_cjk():
    query = build_fts_query("项目合同")
    assert query == '"项目 目合 合同"'


def test_fts_query_and_multiple_segments():
    query = build_fts_query("合同 付款")
    assert query is not None
    assert " AND " in query


def test_highlight_terms_keep_original_segments():
    assert search_phrase_terms("采购合同 2025") == ["采购合同", "2025"]
