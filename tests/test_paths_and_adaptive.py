from __future__ import annotations

from pathlib import Path

import pytest

from findarium import paths
from findarium.library import AppContext


def test_default_library_is_next_to_program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(paths, "application_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "fallback_library_path", lambda: tmp_path / "fallback")
    root, fallback = paths.default_library_path()
    assert root == tmp_path / "FindariumData"
    assert root.is_dir()
    assert fallback is False


def test_default_library_falls_back_when_unwritable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(paths, "application_dir", lambda: blocker)
    monkeypatch.setattr(paths, "fallback_library_path", lambda: tmp_path / "fallback")
    root, fallback = paths.default_library_path()
    assert root == tmp_path / "fallback"
    assert fallback is True


def test_attach_default_creates_program_directory_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(paths, "application_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "fallback_library_path", lambda: tmp_path / "fallback")
    monkeypatch.setattr("findarium.library.bootstrap_library_path", lambda: None)
    ctx = AppContext()
    assert ctx.attach_default(embedding_enabled=False) is True
    try:
        assert ctx.library_root == tmp_path / "FindariumData"
        assert ctx.used_fallback is False
        assert (tmp_path / "FindariumData" / "index.sqlite3").exists()
    finally:
        ctx.detach()


def test_adaptive_worker_count(library: AppContext):
    coordinator = library.coordinator
    coordinator._max_workers = 4
    coordinator._load_ratio = 0.05
    coordinator._process_cpu = 0.05
    assert coordinator._compute_desired_workers(100) == 4
    assert coordinator._compute_desired_workers(10) >= 2
    assert coordinator._compute_desired_workers(0) >= 1

    coordinator._load_ratio = 0.9
    coordinator._process_cpu = 0.1
    assert coordinator._compute_desired_workers(100) == 1

    coordinator._load_ratio = 0.1
    coordinator._process_cpu = 0.95
    assert coordinator._compute_desired_workers(100) == 1

    coordinator._load_ratio = 0.6
    coordinator._process_cpu = 0.1
    assert coordinator._compute_desired_workers(100) == 2


def test_adaptive_embedding_batch(library: AppContext):
    coordinator = library.coordinator
    coordinator._load_ratio = 0.05
    coordinator._process_cpu = 0.05
    assert coordinator._compute_embed_batch() == 32
    coordinator._load_ratio = 0.9
    assert coordinator._compute_embed_batch() == 4
