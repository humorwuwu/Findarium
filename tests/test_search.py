from __future__ import annotations

import time
from pathlib import Path

import pymupdf

from findarium.library import AppContext
from findarium.search.query import parse_query
from tests.conftest import wait_for_idle


def add_source(ctx: AppContext, path: Path) -> int:
    with ctx.db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO sources (path, label, created_at) VALUES (?, ?, ?)",
            (str(path), path.name, int(time.time())),
        )
    return int(cursor.lastrowid)


def test_keyword_search_and_snippets(library: AppContext, docs_dir: Path):
    (docs_dir / "采购合同.md").write_text(
        "# 采购合同\n付款条款和验收安排。\n", encoding="utf-8"
    )
    (docs_dir / "预算.txt").write_text("2025年3月预算 合同付款计划\n", encoding="utf-8")
    source_id = add_source(library, docs_dir)
    library.coordinator.scan_source(source_id)
    wait_for_idle(library)

    response = library.search.search("合同")
    assert response["total"] >= 1
    names = {item["document"]["name"] for item in response["items"]}
    assert "采购合同.md" in names
    item = next(item for item in response["items"] if item["document"]["name"] == "采购合同.md")
    assert item["matches"]
    assert "关键词" in item["tags"]


def test_relative_date_parser():
    parsed = parse_query("上周修改的合同")
    assert parsed.filters.after is not None
    assert "合同" in parsed.content_text
    assert "上周" not in parsed.content_text


def test_extension_filter_parser():
    parsed = parse_query("ext:pdf 验收报告")
    assert ".pdf" in parsed.filters.extensions
    assert "验收报告" in parsed.content_text


def test_encrypted_file_is_marked_and_recoverable(library: AppContext, docs_dir: Path):
    path = docs_dir / "保密报告.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "secret")
    document.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="pw",
        owner_pw="pw",
    )
    document.close()
    source_id = add_source(library, docs_dir)
    library.coordinator.scan_source(source_id)
    wait_for_idle(library)

    row = library.db.fetchone("SELECT * FROM documents WHERE name = '保密报告.pdf'")
    assert row is not None
    assert row["status"] == "encrypted"
    assert (
        library.db.fetchone(
            "SELECT COUNT(*) AS count FROM chunks WHERE document_id = ?", (row["id"],)
        )["count"]
        == 0
    )
    name_search = library.search.search("保密报告")
    assert name_search["total"] == 1
    assert "已加密" in name_search["items"][0]["tags"]
    assert library.search.search("secret")["total"] == 0

    # Simulate the corporate client making the file readable again.
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "now readable contract")
    document.save(str(path))
    document.close()
    library.coordinator.queue_probe(int(row["id"]))
    wait_for_idle(library)

    row = library.db.fetchone("SELECT * FROM documents WHERE id = ?", (row["id"],))
    assert row["status"] == "indexed"
    assert library.search.search("readable")["total"] == 1


def test_rename_keeps_one_document(library: AppContext, docs_dir: Path):
    original = docs_dir / "a.md"
    original.write_text("# 项目合同\n付款条款\n", encoding="utf-8")
    source_id = add_source(library, docs_dir)
    library.coordinator.scan_source(source_id)
    wait_for_idle(library)
    row = library.db.fetchone("SELECT id FROM documents WHERE name = 'a.md'")
    assert row is not None
    document_id = int(row["id"])

    renamed = docs_dir / "b.md"
    original.rename(renamed)
    library.coordinator.scan_source(source_id)
    wait_for_idle(library)

    rows = library.db.fetchall("SELECT id, name, status FROM documents")
    assert len(rows) == 1
    assert rows[0]["id"] == document_id
    assert rows[0]["name"] == "b.md"


def test_deleted_file_becomes_missing(library: AppContext, docs_dir: Path):
    path = docs_dir / "temp.md"
    path.write_text("# 临时文档\n内容\n", encoding="utf-8")
    source_id = add_source(library, docs_dir)
    library.coordinator.scan_source(source_id)
    wait_for_idle(library)
    assert library.search.search("临时文档")["total"] == 1

    path.unlink()
    library.coordinator.scan_source(source_id)
    wait_for_idle(library)

    row = library.db.fetchone("SELECT status FROM documents WHERE name = 'temp.md'")
    assert row["status"] == "missing"
    assert library.search.search("临时文档")["total"] == 0


def test_library_inside_source_is_not_indexed(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "note.md").write_text("# 项目\n内容\n", encoding="utf-8")
    ctx = AppContext()
    ctx.attach(root / "library", embedding_enabled=False)
    try:
        source_id = add_source(ctx, root)
        ctx.coordinator.scan_source(source_id)
        wait_for_idle(ctx)
        names = {row["name"] for row in ctx.db.fetchall("SELECT name FROM documents")}
        assert "note.md" in names
        assert not any(name.startswith("index.sqlite3") for name in names)
    finally:
        ctx.detach()


def test_markdown_link_relation(library: AppContext, docs_dir: Path):
    (docs_dir / "合同.md").write_text(
        "# 合同\n参见 [预算](预算.md)\n", encoding="utf-8"
    )
    (docs_dir / "预算.md").write_text("# 预算\n付款计划\n", encoding="utf-8")
    source_id = add_source(library, docs_dir)
    library.coordinator.scan_source(source_id)
    wait_for_idle(library)

    row = library.db.fetchone("SELECT id FROM documents WHERE name = '合同.md'")
    related = library.search.related(int(row["id"]))
    budget = next((item for item in related if item["name"] == "预算.md"), None)
    assert budget is not None
    assert any("链接" in reason for reason in budget["reasons"])


def test_related_documents_by_keywords(library: AppContext, docs_dir: Path):
    (docs_dir / "合同.md").write_text("# 采购合同\n付款条款和验收安排\n", encoding="utf-8")
    (docs_dir / "预算.md").write_text("# 预算\n采购付款计划\n", encoding="utf-8")
    (docs_dir / "旅行.md").write_text("# 旅行\n酒店和机票\n", encoding="utf-8")
    source_id = add_source(library, docs_dir)
    library.coordinator.scan_source(source_id)
    wait_for_idle(library)

    row = library.db.fetchone("SELECT id FROM documents WHERE name = '合同.md'")
    related = library.search.related(int(row["id"]))
    names = {item["name"] for item in related}
    assert "预算.md" in names
    assert "旅行.md" not in names
