"""Who may reach Lines on its loopback port, and how that's checked
(serafina/docs/APPS.md rules 2-4).

People come through Serafina's app proxy (her §52): she forwards a request
only for someone signed in to her, with their email in an HMAC-signed header
set (`X-Serafina-User/Time/Nonce/Signature`) keyed by `LINES_APP_KEY`, which
she and the app share. A request is believed only if the signature checks,
it's at most two minutes old, its nonce hasn't been seen, and the email is one
of `LINES_USERS`.

Her MCP client sends a bearer token instead; only the token's SHA-256 is kept.

Everything under /ui needs the first, /mcp the second; anything else is a 404
apart from /health, which says nothing but "up".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from collections.abc import Callable

from lines import secretfile
from lines.config import Config

SIGNATURE_VERSION = "serafina-app-v1"
WINDOW_SECONDS = 120
UI_PREFIX = "/ui"
# this app's own: other paths Serafina reaches with her token, such as
# "/media" for her media proxy (her §56)
OTHER_BEARER_PREFIXES: tuple[str, ...] = ()
# end of this app's own
BEARER_PREFIXES = ("/mcp", *OTHER_BEARER_PREFIXES)
_NONCE_RE = re.compile(r"^[0-9a-f]{16,64}$")
_SIG_RE = re.compile(r"^[0-9a-f]{64}$")


def _token_paths_are_their_own() -> None:
    """A token path never covers the pages or /health: her token would stand
    in for a person, or the one open door would close."""
    for prefix in BEARER_PREFIXES:
        over_pages = UI_PREFIX.startswith(prefix) or prefix.startswith(UI_PREFIX)
        if not prefix.startswith("/") or prefix.rstrip("/") in ("", "/health") or over_pages:
            raise RuntimeError(f"{prefix!r} can't be a token path")


_token_paths_are_their_own()


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def signature(key: str, *, timestamp: str, nonce: str, method: str, target: str, email: str) -> str:
    message = "\n".join((SIGNATURE_VERSION, timestamp, nonce, method.upper(), target, email))
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


class Nonces:
    """Nonces seen in the last two windows; a replay inside its window is refused."""

    def __init__(self) -> None:
        self._seen: dict[str, float] = {}

    def first_time(self, nonce: str, now: float) -> bool:
        if len(self._seen) > 50_000 or any(t < now for t in list(self._seen.values())[:50]):
            self._seen = {n: t for n, t in self._seen.items() if t >= now}
        if nonce in self._seen:
            return False
        self._seen[nonce] = now + 2 * WINDOW_SECONDS
        return True


def verify_person(config: Config, nonces: Nonces, headers: dict[str, str], method: str, target: str) -> str:
    """The signed-in email Serafina vouches for, or AuthError."""
    key = secretfile.get(secretfile.APP_KEY)
    if not key:
        raise AuthError(503, "Lines isn't set up for Serafina yet (lines-admin web-key)")
    email = headers.get("x-serafina-user", "")
    stamp = headers.get("x-serafina-time", "")
    nonce = headers.get("x-serafina-nonce", "")
    sig = headers.get("x-serafina-signature", "")
    if not (email and stamp.isdigit() and _NONCE_RE.match(nonce) and _SIG_RE.match(sig)):
        raise AuthError(401, "Open Lines from Serafina")
    now = time.time()
    if abs(now - int(stamp)) > WINDOW_SECONDS:
        raise AuthError(401, "That request is too old; reload the page")
    want = signature(key, timestamp=stamp, nonce=nonce, method=method, target=target, email=email)
    if not hmac.compare_digest(want, sig) or not nonces.first_time(nonce, now):
        raise AuthError(401, "Open Lines from Serafina")
    if not config.may_use(email):
        raise AuthError(403, "Lines isn't open to this account")
    return email.strip().lower()


def bearer_ok(authorization: str) -> bool:
    expected = secretfile.get(secretfile.MCP_TOKEN_SHA256)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip() or not expected:
        return False
    digest = hashlib.sha256(token.strip().encode()).hexdigest()
    return hmac.compare_digest(digest, expected)


class GateMiddleware:
    """Pure ASGI, so streamed responses pass through untouched."""

    def __init__(self, app, get_config: Callable[[], Config]):
        self.app = app
        self.get_config = get_config
        self.nonces = Nonces()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            # Nothing here checks a websocket; one added later would be open.
            return await send({"type": "websocket.close", "code": 1008})
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        try:
            if path == "/health":
                pass
            elif any(path == p or path.startswith(p + "/") for p in BEARER_PREFIXES):
                if not bearer_ok(_headers(scope).get("authorization", "")):
                    raise AuthError(401, "Not authenticated")
            elif path == UI_PREFIX or path.startswith(UI_PREFIX + "/"):
                # Exactly what Serafina signed: the path and query as sent.
                raw = scope.get("raw_path") or path.encode()
                target = raw.decode("latin-1")
                if scope.get("query_string"):
                    target += "?" + scope["query_string"].decode("latin-1")
                person = verify_person(self.get_config(), self.nonces, _headers(scope), scope["method"], target)
                scope.setdefault("state", {})["person"] = person
            else:
                raise AuthError(404, "Not Found")
        except AuthError as exc:
            return await _reply(send, exc.status_code, exc.detail)
        return await self.app(scope, receive, send)


def _headers(scope) -> dict[str, str]:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}


async def _reply(send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
