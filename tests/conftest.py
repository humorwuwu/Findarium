from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from findarium.api.app import create_app
from findarium.library import AppContext

TOKEN = "test-token"


@pytest.fixture(autouse=True)
def _isolate_bootstrap(monkeypatch: pytest.MonkeyPatch):
    """Tests must never overwrite the real remembered library pointer."""
    monkeypatch.setattr("findarium.library.remember_library", lambda *args, **kwargs: None)
    monkeypatch.setattr("findarium.library.bootstrap_library_path", lambda: None)


@pytest.fixture()
def library(tmp_path: Path) -> AppContext:
    ctx = AppContext()
    ctx.attach(tmp_path / "library", embedding_enabled=False)
    yield ctx
    ctx.detach()


@pytest.fixture()
def client(library: AppContext, tmp_path: Path):
    app = create_app(token=TOKEN, static_dir=None)
    app.state.ctx = library
    with TestClient(app, headers={"X-Findarium-Token": TOKEN}) as test_client:
        yield test_client


def wait_for_idle(ctx: AppContext, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = ctx.status()
        if (
            status.get("pending", 0) == 0
            and status.get("running", 0) == 0
            and status.get("indexing", 0) == 0
        ):
            return
        time.sleep(0.1)
    raise AssertionError(f"indexing did not become idle: {ctx.status()}")


def wait_for_client(client: TestClient, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    status: dict = {}
    while time.time() < deadline:
        status = client.get("/api/status").json()
        if (
            status.get("pending", 0) == 0
            and status.get("running", 0) == 0
            and status.get("indexing", 0) == 0
        ):
            return status
        time.sleep(0.1)
    raise AssertionError(f"indexing did not become idle: {status}")


@pytest.fixture()
def docs_dir(tmp_path: Path) -> Path:
    path = tmp_path / "docs"
    path.mkdir()
    return path
