"""The tools (APPS.md rule 3): who it's for is checked on every call, a tool
acts only for them, and a page to show is built from typed arguments."""

from __future__ import annotations

from tests.conftest import DAN, KATE, mcp, signed, tool
from tests.scene import SCENE


def make(client, email=DAN):
    path = "/ui/api/scripts/text"
    script = client.post(path, json={"title": "Late", "text": SCENE}, headers=signed(path, email=email, method="POST"))
    sid = script.json()["id"]
    path = f"/ui/api/scripts/{sid}"
    client.post(path, json={"mine": ["Tom"]}, headers=signed(path, email=email, method="POST"))
    return sid


def test_initialize_and_list(client):
    r = mcp(client, "initialize", {"protocolVersion": "2025-06-18"})
    assert r.json()["result"]["serverInfo"]["name"] == "lines"
    names = [t["name"] for t in mcp(client, "tools/list").json()["result"]["tools"]]
    assert names == [
        "lines_scripts", "lines_status", "lines_read", "lines_jump", "lines_drill", "lines_settings", "lines_open",
    ]  # fmt: skip


def test_every_call_needs_someone_on_the_list(client):
    assert "error" in tool(client, "lines_scripts", email=None)
    assert "error" in tool(client, "lines_scripts", email="stranger@example.com")
    assert "error" not in tool(client, "lines_scripts", email=DAN.upper())


def test_a_tool_acts_only_for_who_it_was_called_for(client):
    sid = make(client)
    assert tool(client, "lines_scripts")["count"] == 1
    assert tool(client, "lines_scripts", email=KATE)["count"] == 0
    assert "error" in tool(client, "lines_status", {"script": sid}, email=KATE)
    assert "error" in tool(client, "lines_status", email=KATE)  # no latest of theirs


def test_status_says_where_you_are(client):
    make(client)
    status = tool(client, "lines_status")
    assert status["script"]["you_play"] == ["Tom"]
    assert status["cue"] == {"position": 0, "kind": "line", "text": "You're late again.", "character": "Maeve"}
    assert status["knows_it"] == 0.0 and status["today"]["attempts"] == 0


def test_read_quotes_the_script_exactly(client):
    make(client)
    read = tool(client, "lines_read", {"quote": "twenty minutes that's what", "count": 2})
    assert [e["text"] for e in read["elements"]] == [
        "Twenty minutes. That's what you said last week.",
        "It's true this time—",
    ]
    assert read["elements"][1]["cut_off"] is True
    assert "error" in tool(client, "lines_read", {"quote": "nothing like this at all"})


def test_jump_moves_the_page_and_shows_it(client):
    sid = make(client)
    out = tool(client, "lines_jump", {"to": "I'll make the tea"})
    assert out["_open"] == {"path": f"?script={sid}&view=rehearse", "label": "Late"} and out["_changed"] is True
    assert tool(client, "lines_status")["cue"]["text"] == "Don't. I can't do this tonight."
    looped = tool(client, "lines_jump", {"to": "twenty minutes that's", "loop_until": "can't do this tonight"})
    assert looped["looping"] is True
    assert tool(client, "lines_jump", {"to": "top"})["moved"] is True


def test_drill_and_settings(client):
    make(client)
    assert tool(client, "lines_drill", {"count": 2})["drilling"] == 2
    out = tool(client, "lines_settings", {"suggestions": False, "level": 3})
    assert out["settings"]["suggestions"] is False and out["settings"]["level"] == 3 and out["_changed"]
    assert "error" in tool(client, "lines_settings", {"level": 9})
    assert "error" in tool(client, "lines_settings", {})


def test_open_builds_the_page_from_typed_arguments(client):
    sid = make(client)
    assert tool(client, "lines_open", {"view": "progress"})["_open"]["path"] == f"?script={sid}&view=progress"
    assert tool(client, "lines_open", {"view": "../../x"})["_open"]["path"] == f"?script={sid}&view=rehearse"
    assert "error" in tool(client, "lines_open", {"script": 999})


def test_no_scripts_yet_says_how_to_add_one(client):
    assert "Add one" in tool(client, "lines_status")["error"]


def test_an_unknown_method_or_tool_is_an_error(client):
    assert mcp(client, "nope").json()["error"]["code"] == -32601
    assert "error" in tool(client, "lines_nope")
