"""Lines's one HTTP listener, on loopback, for Serafina only.

Behind `auth.GateMiddleware`: `/mcp` takes her bearer token, `/ui` (the pages
and the API behind them) her signed identity for someone on `LINES_USERS`,
and nothing else answers but `/health` (serafina/docs/APPS.md).

The pages run on her origin, inside her frame at /apps/lines/, where her
session cookie lives: an XSS here is an XSS in her. So every page goes out
with PAGE_CSP, nothing in them is inline, and writes are POST (a GET never
changes anything).
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lines import mcp, secretfile
from lines.auth import GateMiddleware
from lines.config import HOST, Config
from lines.notes import Notes

log = logging.getLogger(__name__)

DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
# Scripts and styles only from here, nothing inline. React's style props go
# through the CSSOM, which style-src doesn't govern.
PAGE_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
    "font-src 'self'; form-action 'self'; frame-ancestors 'self'; base-uri 'none'; object-src 'none'"
)
PAGE_HEADERS = {"Content-Security-Policy": PAGE_CSP, "X-Content-Type-Options": "nosniff"}


def create_app(config: Config, *, frontend_dir: Path | None = DEFAULT_FRONTEND_DIR) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        key = secretfile.get(secretfile.DB_KEY)
        if not key:
            raise RuntimeError(f"No {secretfile.DB_KEY} in secrets.age (lines-admin init makes one)")
        app.state.notes = Notes(config.db_path, key)
        try:
            yield
        finally:
            app.state.notes.close()

    app = FastAPI(title="Lines", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.add_middleware(GateMiddleware, get_config=lambda: app.state.config)

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/mcp")
    def mcp_endpoint(request: Request, body: dict[str, Any]) -> JSONResponse:
        return JSONResponse(mcp.handle(config, request.app.state.notes, body))

    if frontend_dir is not None and (frontend_dir / "assets").is_dir():
        app.mount("/ui/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")
    app.include_router(_ui(frontend_dir))
    return app


def _person(request: Request) -> str:
    """Who Serafina vouched for; the gate let nothing else through."""
    return request.scope["state"]["person"]


def _ui(frontend_dir: Path | None) -> APIRouter:
    ui = APIRouter(prefix="/ui")

    @ui.get("/api/notes")
    def list_notes(request: Request) -> list[dict[str, Any]]:
        return request.app.state.notes.recent(_person(request))

    @ui.post("/api/notes")
    def add_note(request: Request, body: dict[str, Any]) -> dict[str, Any]:
        try:
            return request.app.state.notes.add(_person(request), str(body.get("text") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @ui.post("/api/notes/{note_id}/delete")
    def delete_note(request: Request, note_id: int) -> dict[str, bool]:
        if not request.app.state.notes.delete(_person(request), note_id):
            raise HTTPException(status_code=404, detail="No such note")
        return {"deleted": True}

    if frontend_dir is None or not (frontend_dir / "index.html").is_file():

        @ui.get("/{path:path}", include_in_schema=False)
        def not_built(path: str) -> JSONResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404)
            return JSONResponse({"detail": "The pages aren't built (cd frontend && npm run build)"}, status_code=503)

        return ui

    dist = frontend_dir.resolve()

    @ui.get("/{path:path}", include_in_schema=False)
    def page(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate, headers=PAGE_HEADERS)
        return FileResponse(dist / "index.html", headers={**PAGE_HEADERS, "Cache-Control": "no-cache"})

    return ui


def run(config: Config) -> int:
    # log_config=None: uvicorn's loggers reach the root handlers, which carry
    # the secret redaction (secretfile.install_redaction).
    uvicorn.run(create_app(config), host=HOST, port=config.port, log_config=None)
    return 0
