from __future__ import annotations

import logging
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from .api.app import create_app
from .config import APP_TITLE, DEFAULT_WINDOW_SIZE, MIN_WINDOW_SIZE

logger = logging.getLogger(__name__)


class ThreadedServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:  # pragma: no cover - thread-only
        pass


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def static_dir() -> Path | None:
    """Locate the built frontend both in development and in frozen bundles."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "frontend" / "dist")
    executable = Path(sys.executable).resolve()
    exe_dir = executable.parent
    candidates.extend(
        [
            exe_dir.parent / "Resources" / "frontend" / "dist",  # macOS .app
            exe_dir.parent / "frontend" / "dist",  # onedir
            exe_dir / "frontend" / "dist",
            Path(__file__).resolve().parents[2] / "frontend" / "dist",  # source tree
        ]
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


class NativeBridge:
    """Small JS API exposed to the webview for native folder dialogs."""

    def __init__(self) -> None:
        self.window: Any = None

    def pick_folder(self) -> str | None:
        import webview

        if self.window is None:
            return None
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        if isinstance(result, (list, tuple)):
            return str(result[0]) if result else None
        return str(result)

    def pick_folders(self) -> list[str]:
        import webview

        if self.window is None:
            return []
        result = self.window.create_file_dialog(
            webview.FOLDER_DIALOG, allow_multiple=True
        )
        if not result:
            return []
        if isinstance(result, (list, tuple)):
            return [str(item) for item in result]
        return [str(result)]


def start_server(app, port: int) -> tuple[ThreadedServer, threading.Thread]:
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
        lifespan="on",
    )
    server = ThreadedServer(config)
    thread = threading.Thread(target=server.run, name="findarium-server", daemon=True)
    thread.start()
    deadline = time.time() + 30
    while not server.started and time.time() < deadline:
        if not thread.is_alive():
            break
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("本地服务启动失败")
    return server, thread


def launch(
    *,
    headless: bool = False,
    port: int | None = None,
    library: Path | None = None,
    dev_url: str | None = None,
    embedding_enabled: bool = True,
    token: str | None = None,
) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Windowed PyInstaller builds may not have valid std streams.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    token = token or secrets.token_urlsafe(32)
    dist = static_dir()
    app = create_app(token=token, static_dir=dist)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    ctx = app.state.ctx

    if library is not None:
        ctx.attach(library, embedding_enabled=embedding_enabled)
    else:
        ctx.attach_default(embedding_enabled=embedding_enabled)

    chosen_port = port or find_free_port()
    server, server_thread = start_server(app, chosen_port)
    base_url = f"http://127.0.0.1:{chosen_port}"
    url = f"{base_url}/?token={token}"
    if dev_url:
        separator = "&" if "?" in dev_url else "?"
        url = f"{dev_url}{separator}token={token}&api={base_url}"

    if headless:
        print(f"Findarium running at {url}", flush=True)
        try:
            while server_thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            ctx.detach()
            server.should_exit = True
            server_thread.join(timeout=10)
        return 0

    try:
        import webview
    except Exception as exc:  # pragma: no cover - only without GUI deps
        print(f"无法启动桌面窗口：{exc}")
        print(f"请改用 --headless 访问 {url}")
        ctx.detach()
        server.should_exit = True
        server_thread.join(timeout=10)
        return 1

    bridge = NativeBridge()
    window = webview.create_window(
        APP_TITLE,
        url,
        width=DEFAULT_WINDOW_SIZE[0],
        height=DEFAULT_WINDOW_SIZE[1],
        min_size=MIN_WINDOW_SIZE,
        js_api=bridge,
    )
    bridge.window = window
    try:
        webview.start()
    finally:
        ctx.detach()
        server.should_exit = True
        server_thread.join(timeout=10)
    return 0
