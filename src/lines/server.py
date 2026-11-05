"""Lines's one HTTP listener, on loopback, for Serafina only.

Behind `auth.GateMiddleware`: `/mcp` takes her bearer token, `/ui` (the pages
and the API behind them) her signed identity for someone on `LINES_USERS`,
and nothing else answers but `/health` (serafina/docs/APPS.md).

The pages run on her origin, inside her frame at /apps/lines/, where her
session cookie lives: an XSS here is an XSS in her. So every page goes out
with PAGE_CSP, nothing in them is inline, and writes are POST (a GET never
changes anything). A script's words are rendered as text, never as HTML.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lines import gdoc, mcp, parse, secretfile
from lines.auth import GateMiddleware
from lines.config import HOST, Config
from lines.store import NotFound, Stale, Store

log = logging.getLogger(__name__)

DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
# Scripts and styles only from here, nothing inline. React's style props go
# through the CSSOM, which style-src doesn't govern.
PAGE_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
    "font-src 'self'; form-action 'self'; frame-ancestors 'self'; base-uri 'none'; object-src 'none'"
)
PAGE_HEADERS = {"Content-Security-Policy": PAGE_CSP, "X-Content-Type-Options": "nosniff"}
MAX_PDF_BYTES = 15 * 1024 * 1024


def create_app(config: Config, *, frontend_dir: Path | None = DEFAULT_FRONTEND_DIR) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        key = secretfile.get(secretfile.DB_KEY)
        if not key:
            raise RuntimeError(f"No {secretfile.DB_KEY} in secrets.age (lines-admin init makes one)")
        app.state.store = Store(config.db_path, key)
        try:
            yield
        finally:
            app.state.store.close()

    app = FastAPI(title="Lines", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.add_middleware(GateMiddleware, get_config=lambda: app.state.config)

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/mcp")
    def mcp_endpoint(request: Request, body: dict[str, Any]) -> JSONResponse:
        return JSONResponse(mcp.handle(config, request.app.state.store, body))

    if frontend_dir is not None and (frontend_dir / "assets").is_dir():
        app.mount("/ui/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")
    app.include_router(_ui(frontend_dir))
    return app


def _person(request: Request) -> str:
    """Who Serafina vouched for; the gate let nothing else through."""
    return request.scope["state"]["person"]


async def _body(request: Request, limit: int) -> bytes:
    """The request body, refused past `limit` before it's all read."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > limit:
            raise HTTPException(status_code=413, detail="That file is too big; try one scene or act")
    return bytes(data)


def _act(fn: Callable[[], Any]) -> Any:
    """A store call, with its refusals as the page should see them."""
    try:
        return fn()
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Stale as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, parse.ParseError, gdoc.DocError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _int(body: dict[str, Any], key: str, default: int | None = None) -> int:
    value = body.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"{key} should be a number")
    return value


def _ui(frontend_dir: Path | None) -> APIRouter:
    ui = APIRouter(prefix="/ui")

    def store(request: Request) -> Store:
        return request.app.state.store

    def made(request: Request, title: str, source: str, elements: list[parse.Element]) -> dict[str, Any]:
        owner = _person(request)
        return store(request).detail(owner, store(request).create(owner, title, source, elements))

    @ui.get("/api/scripts")
    def list_scripts(request: Request) -> list[dict[str, Any]]:
        return store(request).scripts(_person(request))

    @ui.post("/api/scripts/text")
    def from_text(request: Request, body: dict[str, Any]) -> dict[str, Any]:
        text, title = str(body.get("text") or ""), str(body.get("title") or "")
        return _act(lambda: made(request, title or "Pasted script", "text", parse.parse_text(text)))

    @ui.post("/api/scripts/pdf")
    async def from_pdf(request: Request, title: str = "") -> dict[str, Any]:
        data = await _body(request, MAX_PDF_BYTES)
        if not data.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="That isn't a PDF")
        return await run_in_threadpool(_act, lambda: made(request, title or "Script", "pdf", parse.parse_pdf(data)))

    @ui.post("/api/scripts/gdoc")
    def from_gdoc(request: Request, body: dict[str, Any]) -> dict[str, Any]:
        url, title = str(body.get("url") or ""), str(body.get("title") or "")
        return _act(lambda: made(request, title or "Google Doc", "gdoc", parse.parse_pdf(gdoc.fetch_pdf(url))))

    @ui.get("/api/scripts/{sid}")
    def script(request: Request, sid: int) -> dict[str, Any]:
        return _act(lambda: store(request).detail(_person(request), sid))

    @ui.post("/api/scripts/{sid}")
    def update_script(request: Request, sid: int, body: dict[str, Any]) -> dict[str, Any]:
        owner = _person(request)
        _act(lambda: store(request).update(owner, sid, title=body.get("title"), mine=body.get("mine"),
                                           settings=body.get("settings")))  # fmt: skip
        return _act(lambda: store(request).detail(owner, sid))

    @ui.post("/api/scripts/{sid}/delete")
    def delete_script(request: Request, sid: int) -> dict[str, bool]:
        _act(lambda: store(request).delete(_person(request), sid))
        return {"deleted": True}

    @ui.post("/api/scripts/{sid}/elements/{eid}")
    def change_element(request: Request, sid: int, eid: int, body: dict[str, Any]) -> dict[str, Any]:
        owner, s = _person(request), store(request)
        action = body.get("action", "edit")
        if action == "edit":
            _act(lambda: s.edit(owner, sid, eid, body))
        elif action == "insert":
            _act(lambda: s.insert_after(owner, sid, eid, body))
        elif action == "merge":
            _act(lambda: s.merge_next(owner, sid, eid))
        elif action == "split":
            at = _int(body, "at")
            _act(lambda: s.split(owner, sid, eid, at))
        elif action == "delete":
            _act(lambda: s.remove(owner, sid, eid))
        else:
            raise HTTPException(status_code=400, detail="Edit, insert, merge, split or delete")
        return _act(lambda: s.detail(owner, sid))

    @ui.post("/api/scripts/{sid}/rename")
    def rename(request: Request, sid: int, body: dict[str, Any]) -> dict[str, Any]:
        owner = _person(request)
        _act(lambda: store(request).rename(owner, sid, str(body.get("from") or ""), str(body.get("to") or "")))
        return _act(lambda: store(request).detail(owner, sid))

    @ui.get("/api/scripts/{sid}/run")
    def run(request: Request, sid: int) -> dict[str, Any]:
        return _act(lambda: store(request).view(_person(request), sid))

    @ui.post("/api/scripts/{sid}/run/attempt")
    def attempt(request: Request, sid: int, body: dict[str, Any]) -> dict[str, Any]:
        line_id, helped = _int(body, "line_id"), _int(body, "helped", 0)
        text, mode = str(body.get("text") or ""), str(body.get("mode") or "words")
        return _act(lambda: store(request).attempt(_person(request), sid, line_id, text, mode=mode, helped=helped,
                                                   gave_up=body.get("gave_up") is True))  # fmt: skip

    @ui.post("/api/scripts/{sid}/run/jump")
    def jump(request: Request, sid: int, body: dict[str, Any]) -> dict[str, Any]:
        return _act(lambda: store(request).jump(_person(request), sid, body.get("to")))

    @ui.post("/api/scripts/{sid}/run/drill")
    def drill(request: Request, sid: int, body: dict[str, Any]) -> dict[str, Any]:
        count = _int(body, "count", 5)
        return _act(lambda: store(request).drill(_person(request), sid, count))

    @ui.post("/api/scripts/{sid}/run/stop-drill")
    def stop_drill(request: Request, sid: int) -> dict[str, Any]:
        return _act(lambda: store(request).stop_drill(_person(request), sid))

    @ui.get("/api/scripts/{sid}/progress")
    def progress(request: Request, sid: int) -> dict[str, Any]:
        return _act(lambda: store(request).progress(_person(request), sid))

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
