from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import APP_TITLE
from ..i18n import translate
from ..library import AppContext
from .routes import request_lang, router

logger = logging.getLogger(__name__)


def create_app(*, token: str, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title=APP_TITLE, version=__version__, docs_url=None, redoc_url=None)
    app.state.ctx = AppContext()
    app.state.token = token

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        """Translate message keys raised by the routes into the request language."""
        detail = exc.detail
        if isinstance(detail, str):
            detail = translate(detail, request_lang(request))
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=getattr(exc, "headers", None),
        )

    @app.middleware("http")
    async def token_guard(request: Request, call_next):
        if request.url.path.startswith("/api"):
            provided = request.headers.get("x-findarium-token") or request.query_params.get(
                "token"
            )
            if provided != token:
                return JSONResponse(
                    status_code=403,
                    content={"detail": translate("err.invalid_token", request_lang(request))},
                )
        return await call_next(request)

    app.include_router(router)

    if static_dir is not None and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")
    else:

        @app.get("/", response_class=HTMLResponse)
        def index() -> str:
            # Shown before the frontend is built: keep both languages side by side.
            return (
                "<html><body style='font-family:-apple-system;padding:40px'>"
                "<h2>Findarium backend is running</h2>"
                f"<p>{translate('err.frontend_not_built', 'zh-CN')}</p>"
                f"<p>{translate('err.frontend_not_built', 'en')}</p>"
                "</body></html>"
            )

    return app
