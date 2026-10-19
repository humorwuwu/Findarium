from __future__ import annotations

from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from tests.conftest import wait_for_client


def test_health_and_status(client: TestClient):
    assert client.get("/api/health").json()["status"] == "ok"
    status = client.get("/api/status").json()
    assert status["library"]["ready"] is True


def test_token_is_required(client: TestClient):
    response = client.get("/api/status", headers={"X-Findarium-Token": "wrong"})
    assert response.status_code == 403


def test_source_search_and_settings(client: TestClient, docs_dir: Path):
    (docs_dir / "合同.md").write_text("# 采购合同\n付款条款\n", encoding="utf-8")
    response = client.post("/api/sources", json={"path": str(docs_dir)})
    assert response.status_code == 200
    wait_for_client(client)

    search = client.get("/api/search", params={"q": "合同"}).json()
    assert search["total"] >= 1
    assert search["items"][0]["document"]["name"] == "合同.md"

    sources = client.get("/api/sources").json()
    assert sources[0]["document_count"] == 1

    settings = client.get("/api/settings").json()
    assert "scan_interval_seconds" in settings
    updated = client.put("/api/settings", json={"scan_interval_seconds": 300}).json()
    assert str(updated["scan_interval_seconds"]) == "300"

    errors = client.get("/api/errors").json()
    assert "jobs" in errors and "documents" in errors


def test_encrypted_endpoint(client: TestClient, docs_dir: Path):
    path = docs_dir / "secret.pdf"
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
    client.post("/api/sources", json={"path": str(docs_dir)})
    wait_for_client(client)

    encrypted = client.get("/api/encrypted").json()
    assert len(encrypted) == 1
    assert encrypted[0]["name"] == "secret.pdf"
    recheck = client.post("/api/encrypted/recheck").json()
    assert recheck["queued"] == 1


def test_language_switch_for_backend_text(client: TestClient, docs_dir: Path):
    (docs_dir / "合同.md").write_text("# 采购合同\n付款条款\n", encoding="utf-8")
    client.post("/api/sources", json={"path": str(docs_dir)})
    wait_for_client(client)

    chinese = client.get("/api/search", params={"q": "合同"}).json()
    assert "关键词" in chinese["items"][0]["tags"]

    english = client.get("/api/search", params={"q": "合同", "lang": "en"}).json()
    assert "Keyword" in english["items"][0]["tags"]
    assert any(item.startswith("Matched by:") for item in english["explanation"])
    assert not any("关键词" in tag for tag in english["items"][0]["tags"])

    # The header works as well as the query parameter.
    via_header = client.get(
        "/api/search", params={"q": "合同"}, headers={"X-Findarium-Lang": "en"}
    ).json()
    assert "Keyword" in via_header["items"][0]["tags"]

    # The stored setting drives requests that do not send a language.
    client.put("/api/settings", json={"language": "en"})
    stored = client.get("/api/search", params={"q": "合同"}).json()
    assert "Keyword" in stored["items"][0]["tags"]
    # "auto" follows the machine's locale, so only check it still returns items.
    client.put("/api/settings", json={"language": "auto"})
    assert client.get("/api/search", params={"q": "合同"}).json()["items"][0]["tags"]


def test_error_details_follow_language(client: TestClient):
    assert client.get("/api/documents/999").json()["detail"] == "文档不存在"
    assert (
        client.get("/api/documents/999", params={"lang": "en"}).json()["detail"]
        == "Document not found"
    )
    assert (
        client.get("/api/documents/999", headers={"X-Findarium-Lang": "en"}).json()["detail"]
        == "Document not found"
    )


def test_settings_include_language(client: TestClient):
    settings = client.get("/api/settings").json()
    assert settings["language"] == "auto"
    assert client.put("/api/settings", json={"language": "en"}).json()["language"] == "en"


def test_location_labels_follow_language(client: TestClient, docs_dir: Path):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "payment terms")
    document.save(str(docs_dir / "report.pdf"))
    document.close()
    client.post("/api/sources", json={"path": str(docs_dir)})
    wait_for_client(client)

    search = client.get("/api/search", params={"q": "payment"}).json()
    match = search["items"][0]["matches"][0]
    assert match["location_label"] == "第 1 页"
    english = client.get("/api/search", params={"q": "payment", "lang": "en"}).json()
    assert english["items"][0]["matches"][0]["location_label"] == "Page 1"


def test_document_detail_and_related(client: TestClient, docs_dir: Path):
    (docs_dir / "a.md").write_text("# 合同\n付款条款\n", encoding="utf-8")
    (docs_dir / "b.md").write_text("# 预算\n付款计划\n", encoding="utf-8")
    client.post("/api/sources", json={"path": str(docs_dir)})
    wait_for_client(client)

    search = client.get("/api/search", params={"q": "付款"}).json()
    document_id = search["items"][0]["document_id"]
    detail = client.get(f"/api/documents/{document_id}").json()
    assert detail["chunks"]
    related = client.get(f"/api/documents/{document_id}/related").json()
    assert isinstance(related, list)
    graph = client.get(f"/api/documents/{document_id}/graph").json()
    assert "nodes" in graph and "edges" in graph
