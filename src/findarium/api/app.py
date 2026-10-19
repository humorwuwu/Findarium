from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import APP_TITLE
from ..library import AppContext
from .routes import router

logger = logging.getLogger(__name__)


def create_app(*, token: str, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title=APP_TITLE, version=__version__, docs_url=None, redoc_url=None)
    app.state.ctx = AppContext()
    app.state.token = token

    @app.middleware("http")
    async def token_guard(request: Request, call_next):
        if request.url.path.startswith("/api"):
            provided = request.headers.get("x-findarium-token") or request.query_params.get(
                "token"
            )
            if provided != token:
                return JSONResponse(status_code=403, content={"detail": "无效的本地令牌"})
        return await call_next(request)

    app.include_router(router)

    if static_dir is not None and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")
    else:

        @app.get("/", response_class=HTMLResponse)
        def index() -> str:
            return (
                "<html><body style='font-family:-apple-system;padding:40px'>"
                "<h2>Findarium backend is running</h2>"
                "<p>前端尚未构建。运行 <code>cd frontend &amp;&amp; npm install "
                "&amp;&amp; npm run build</code>，或用 <code>FINDARIUM_DEV_URL</code> "
                "指向 Vite 开发服务器。</p>"
                "</body></html>"
            )

    return app
