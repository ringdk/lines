"""A running app for each test: its secrets in memory, a fresh encrypted
database, and helpers that come in the way Serafina does."""

from __future__ import annotations

import hashlib
import json
import secrets as tokens
import time

import pytest
from fastapi.testclient import TestClient

from lines import secretfile
from lines.auth import signature
from lines.config import Config
from lines.server import create_app

APP_KEY = "k" * 64
TOKEN = "serafina-mcp-token"
DB_KEY = "d" * 64
DAN = "dan@example.com"
KATE = "kate@example.com"
# A page's API a signed GET for DAN may read, for the gate tests.
PAGE = "/ui/api/notes"


@pytest.fixture
def client(tmp_path):
    digest = hashlib.sha256(TOKEN.encode()).hexdigest()
    secretfile.use({secretfile.APP_KEY: APP_KEY, secretfile.MCP_TOKEN_SHA256: digest, secretfile.DB_KEY: DB_KEY})
    config = Config(data_dir=tmp_path, users=[DAN, KATE])
    with TestClient(create_app(config, frontend_dir=None)) as c:
        yield c
    secretfile.use({})


def signed(target: str, *, email: str = DAN, method: str = "GET", key: str = APP_KEY, stamp: int | None = None,
           nonce: str | None = None) -> dict[str, str]:  # fmt: skip
    """The headers Serafina's app proxy adds (her §52)."""
    stamp_s = str(int(time.time()) if stamp is None else stamp)
    nonce = nonce or tokens.token_hex(16)
    return {
        "X-Serafina-User": email,
        "X-Serafina-Time": stamp_s,
        "X-Serafina-Nonce": nonce,
        "X-Serafina-Signature": signature(
            key, timestamp=stamp_s, nonce=nonce, method=method, target=target, email=email
        ),  # fmt: skip
    }


def mcp(client, method: str, params: dict | None = None, token: str | None = TOKEN):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post("/mcp", json=body, headers=headers)


def tool(client, name: str, arguments: dict | None = None, *, email: str | None = DAN) -> dict:
    """A tool call as her MCP client makes it, `_serafina` and all; the result's JSON."""
    args = dict(arguments or {})
    if email is not None:
        args["_serafina"] = {"conversation_id": "c1", "turn_id": 1, "persona_id": None, "user_email": email}
    r = mcp(client, "tools/call", {"name": name, "arguments": args})
    assert r.status_code == 200
    return json.loads(r.json()["result"]["content"][0]["text"])
