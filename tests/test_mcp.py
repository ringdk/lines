"""The tools (APPS.md rule 3): who it's for is checked on every call, and a
tool acts only for them."""

from __future__ import annotations

from tests.conftest import DAN, KATE, mcp, tool


def test_initialize_and_list(client):
    r = mcp(client, "initialize", {"protocolVersion": "2025-06-18"})
    assert r.json()["result"]["serverInfo"]["name"] == "lines"
    names = [t["name"] for t in mcp(client, "tools/list").json()["result"]["tools"]]
    assert names == ["lines_list", "lines_add", "lines_open"]


def test_every_call_needs_someone_on_the_list(client):
    assert "error" in tool(client, "lines_list", email=None)
    assert "error" in tool(client, "lines_list", email="stranger@example.com")
    assert "error" not in tool(client, "lines_list", email=DAN.upper())


def test_a_tool_acts_only_for_who_it_was_called_for(client):
    added = tool(client, "lines_add", {"text": "milk"})
    assert added["_changed"] is True and added["_pill"] == "noted"
    assert tool(client, "lines_list")["count"] == 1
    assert tool(client, "lines_list", email=KATE)["count"] == 0


def test_the_model_cant_name_an_owner(client):
    tool(client, "lines_add", {"text": "milk", "owner": KATE})
    assert tool(client, "lines_list", email=KATE)["count"] == 0


def test_open_builds_the_page_from_typed_arguments(client):
    assert tool(client, "lines_open", {"note": 7})["_open"] == {"path": "?note=7", "label": "Note 7"}
    assert tool(client, "lines_open", {"note": "../../x"})["_open"]["path"] == ""


def test_an_unknown_method_or_tool_is_an_error(client):
    assert mcp(client, "nope").json()["error"]["code"] == -32601
    assert "error" in tool(client, "lines_nope")
