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
