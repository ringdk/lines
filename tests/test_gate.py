"""Who gets in (serafina/docs/APPS.md rules 2-4): the pages need Serafina's
signed identity for someone on LINES_USERS, the tools her bearer token, and
nothing else answers but /health. A test for each refusal."""

from __future__ import annotations

import time

import pytest

from lines import secretfile

from tests.conftest import APP_KEY, DAN, PAGE, mcp, signed


def test_health_says_up_and_nothing_more(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_a_signed_request_for_someone_on_the_list_gets_in(client):
    r = client.get(PAGE, headers=signed(PAGE))
    assert r.status_code == 200 and r.json() == []


@pytest.mark.parametrize(
    "change,status",
    [
        ({"key": "x" * 64}, 401),
        ({"stamp": int(time.time()) - 600}, 401),
        ({"stamp": int(time.time()) + 600}, 401),
        ({"email": "stranger@example.com"}, 403),
    ],
    ids=["wrong key", "too old", "from the future", "not on the list"],
)
def test_pages_refuse_a_bad_signature(client, change, status):
    assert client.get(PAGE, headers=signed(PAGE, **change)).status_code == status


def test_pages_refuse_no_headers(client):
    assert client.get(PAGE).status_code == 401


def test_pages_refuse_a_missing_header(client):
    for name in ("X-Serafina-User", "X-Serafina-Time", "X-Serafina-Nonce", "X-Serafina-Signature"):
        headers = signed(PAGE)
        del headers[name]
        assert client.get(PAGE, headers=headers).status_code == 401, name


def test_a_replayed_nonce_is_refused(client):
    headers = signed(PAGE)
    assert client.get(PAGE, headers=headers).status_code == 200
    assert client.get(PAGE, headers=headers).status_code == 401


def test_the_signature_covers_method_path_and_query(client):
    assert client.post(PAGE, json={"text": "x"}, headers=signed(PAGE)).status_code == 401
    assert client.get(PAGE + "?limit=1", headers=signed(PAGE)).status_code == 401
    assert client.get("/ui/api/other", headers=signed(PAGE)).status_code == 401


def test_the_email_is_compared_without_case(client):
    assert client.get(PAGE, headers=signed(PAGE, email=DAN.upper())).status_code == 200


def test_without_the_app_key_nobody_gets_in(client):
    secretfile.use({})
    assert client.get(PAGE, headers=signed(PAGE, key=APP_KEY)).status_code == 503


def test_tools_need_the_bearer_token(client):
    assert mcp(client, "tools/list", token=None).status_code == 401
    assert mcp(client, "tools/list", token="wrong").status_code == 401
    assert mcp(client, "tools/list").status_code == 200


def test_the_token_doesnt_open_the_pages(client):
    from tests.conftest import TOKEN

    assert client.get(PAGE, headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 401


@pytest.mark.parametrize("path", ["/", "/docs", "/openapi.json", "/api/notes", "/uix", "/mcpx", "/health/x"])
def test_nothing_else_answers(client, path):
    assert client.get(path).status_code == 404


def test_no_websocket_gets_in(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ui/ws", headers=signed("/ui/ws")):
        pass
