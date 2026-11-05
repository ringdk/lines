"""Serafina's tools: MCP's streamable HTTP at /mcp, which for a tools-only
server is JSON-RPC 2.0 over POST, behind her bearer token (auth.py).

Her config passes `_serafina` with every call (`pass_context: true`): who
it's for is checked on every call, against the same list as the pages
(serafina/docs/APPS.md rule 3), and it's the only owner a tool acts for.
`_serafina` is never in a tool's schema, so her model neither sees nor forges
it.

The rehearsal itself happens on the page, where the words are exact: these
tools let the scene partner beside it see where the person is, read the
script to talk about it, and move the run (from a line, back to the top, a
drill, the settings). Tool names carry the app's prefix. Renaming one breaks
her, so the skill's and the persona's `tools:` lists change in the same
commit. What a result can carry for her (§50.5, §55): `_pill`, a word shown
while she works; `_open`, a page of the app to show, built here from typed
arguments; `_changed`, so a page on screen catches up.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from lines.coach import LEVELS, level_for
from lines.config import Config
from lines.store import NotFound, Store

log = logging.getLogger(__name__)

_SCRIPT = {"type": "integer", "description": "A script's id, from lines_scripts; leave it out for the latest"}
_SETTINGS: dict[str, Any] = {
    "suggestions": {"type": "boolean", "description": "Word suggestions to tap"},
    "cue_view": {"type": "boolean", "description": "Show only the end of each cue line"},
    "directions": {"type": "boolean", "description": "Show stage directions"},
    "input": {"type": "string", "enum": ["words", "letters"], "description": "Type words, or first letters"},
    "level": {
        "description": "Difficulty: auto, or 1 (easiest) to 5",
        "anyOf": [{"type": "string", "enum": ["auto"]}, {"type": "integer", "minimum": 1, "maximum": 5}],
    },
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "lines_scripts",
        "description": "The person's scripts in Lines: title, characters, who they play, how well they know it.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "lines_status",
        "description": (
            "Where the person is in a rehearsal: the line up next and its cue, how well they know the script "
            "(0-1) and its level, their weakest lines, and today's practice."
        ),
        "inputSchema": {"type": "object", "properties": {"script": _SCRIPT}, "additionalProperties": False},
    },
    {
        "name": "lines_read",
        "description": (
            "Read part of a script exactly as written, to talk about it (intentions, beats, a hard speech). "
            "Start at a position, or at the line matching a quote."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": _SCRIPT,
                "start": {"type": "integer", "minimum": 0, "description": "Position to start at (0 is the top)"},
                "quote": {"type": "string", "description": "A few words from the line to start at"},
                "count": {"type": "integer", "minimum": 1, "maximum": 40, "default": 20},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "lines_jump",
        "description": (
            "Move the rehearsal on the page: back to the top, back one exchange, or to the line matching a quote "
            "(their own lines start from the cue). Optionally loop back from another quoted line."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": _SCRIPT,
                "to": {"type": "string", "description": "'top', 'back', or a few words from the line"},
                "loop_until": {"type": "string", "description": "A few words from the line to loop back from"},
            },
            "required": ["to"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lines_drill",
        "description": "Drill the person's weakest lines on the page, each after its cue, repeating the shaky ones.",
        "inputSchema": {
            "type": "object",
            "properties": {"script": _SCRIPT, "count": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}},
            "additionalProperties": False,
        },
    },
    {
        "name": "lines_settings",
        "description": "Change how the rehearsal runs: suggestions, cue view, stage directions, input, difficulty.",
        "inputSchema": {
            "type": "object",
            "properties": {"script": _SCRIPT, **_SETTINGS},
            "additionalProperties": False,
        },
    },
    {
        "name": "lines_open",
        "description": "SHOW a script in Lines itself (the page beside the chat): rehearse, the script, or progress.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": _SCRIPT,
                "view": {"type": "string", "enum": ["rehearse", "script", "progress"], "default": "rehearse"},
            },
            "additionalProperties": False,
        },
    },
]
NAMES = {t["name"] for t in TOOLS}


def _split(arguments: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    args = dict(arguments)
    context = args.pop("_serafina", None)
    return args, context if isinstance(context, dict) else {}


def _id(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _said(e: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"position": e["pos"], "kind": e["kind"], "text": e["text"]}
    if e["kind"] == "line":
        out["character"] = e["character"]
        if e.get("note"):
            out["note"] = e["note"]
        if e.get("interrupted"):
            out["cut_off"] = True
    return out


def _page(sid: int, view: str, label: str) -> dict[str, str]:
    return {"path": f"?script={sid}&view={view}", "label": label}


def call(config: Config, store: Store, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    args, context = _split(arguments)
    # The token says it's Serafina; this says she's asking for someone who may use it.
    email = context.get("user_email")
    if not config.may_use(email):
        return {"error": "Lines isn't open to this account."}
    owner = str(email).strip().lower()

    if name == "lines_scripts":
        found = store.scripts(owner)
        return {
            "count": len(found),
            "scripts": [{k: s[k] for k in ("id", "title", "characters", "mine", "lines", "mastery")} for s in found],
        }
    if name not in NAMES:
        return {"error": f"No such tool: {name}"}

    sid = _id(args.get("script")) or store.latest(owner)
    if sid is None:
        return {"error": "There are no scripts in Lines yet. Add one on the page (a PDF, pasted text or a Google Doc)."}
    try:
        return _script_tool(store, owner, sid, name, args)
    except (NotFound, ValueError) as exc:
        return {"error": str(exc)}


def _script_tool(store: Store, owner: str, sid: int, name: str, args: dict[str, Any]) -> dict[str, Any]:
    detail = store.detail(owner, sid)
    title = detail["title"]

    if name == "lines_status":
        view = store.view(owner, sid)
        progress = store.progress(owner, sid, days=1)
        today = progress["days"][-1] if progress["days"] else {"attempts": 0, "accuracy": 0, "lines_called": 0}
        cue = next((c for c in reversed(view["cues"]) if c.get("kind") == "line"), None)
        prompt = view["prompt"]
        return {
            "script": {"id": sid, "title": title, "you_play": detail["mine"], "characters": detail["characters"]},
            "mode": view["mode"],
            "knows_it": view["mastery"],
            "level": LEVELS[level_for(view["mastery"])],
            "next_line": None if prompt is None else {"position": prompt["pos"], "level": prompt["label"]},
            "cue": None if cue is None else _said(cue),
            "at_the_end": view["end"],
            "needs_character": bool(view.get("needs_character")),
            "weakest": [{"position": w["pos"], "text": w["text"], "knows_it": w["score"]}
                        for w in progress["weakest"][:3]],  # fmt: skip
            "today": today,
        }
    if name == "lines_read":
        start = _id(args.get("start")) or 0
        quote = args.get("quote")
        if isinstance(quote, str) and quote.strip():
            found = store.find(owner, sid, quote)
            if found is None:
                return {"error": "No line in it matches that"}
            start = found["pos"]
        count = _id(args.get("count")) or 20
        return {"script": title, "elements": [_said(e) for e in store.read(owner, sid, start, min(count, 40))]}
    if name == "lines_jump":
        return _jump(store, owner, sid, detail, args)
    if name == "lines_drill":
        view = store.drill(owner, sid, _id(args.get("count")) or 5)
        return {"drilling": view.get("remaining", 0), "_open": _page(sid, "rehearse", title), "_changed": True}
    if name == "lines_settings":
        change = {k: args[k] for k in _SETTINGS if k in args}
        if not change:
            return {"error": "Say which setting to change"}
        store.update(owner, sid, settings=change)
        return {"settings": store.detail(owner, sid)["settings"], "_changed": True}
    view = args.get("view") if args.get("view") in ("rehearse", "script", "progress") else "rehearse"
    return {"shown": True, "_open": _page(sid, str(view), title)}


def _jump(store: Store, owner: str, sid: int, detail: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    to = args.get("to")
    if not isinstance(to, str) or not to.strip():
        return {"error": "Jump to 'top', 'back', or a few words from a line"}
    word = to.strip().lower()
    target: object = word if word in ("top", "back") else None
    if target is None:
        found = store.find(owner, sid, to)
        if found is None:
            return {"error": "No line in it matches that"}
        target = found["id"]
    until = args.get("loop_until")
    if isinstance(until, str) and until.strip():
        end = store.find(owner, sid, until)
        if end is None:
            return {"error": "No line matches where the loop should end"}
        start_id = target if isinstance(target, int) else detail["elements"][0]["id"]
        store.update(owner, sid, settings={"loop": {"from": start_id, "to": end["id"]}})
    view = store.jump(owner, sid, target)
    prompt = view["prompt"]
    return {
        "moved": True,
        "next_line_position": None if prompt is None else prompt["pos"],
        "looping": bool(view["settings"]["loop"]),
        "_open": _page(sid, "rehearse", detail["title"]),
        "_changed": True,
        "_pill": "places",
    }


def handle(config: Config, store: Store, body: dict[str, Any]) -> dict[str, Any]:
    """One JSON-RPC request, answered."""
    method = body.get("method")
    params = body.get("params") or {}

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": body.get("id"), "result": result}

    if method == "initialize":
        return ok(
            {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "lines", "version": "0.1.0"},
            }
        )
    if method in ("notifications/initialized", "ping"):
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments")
        try:
            result = call(config, store, name, arguments if isinstance(arguments, dict) else {})
        except Exception:
            log.exception("tool %s failed", name)
            result = {"error": f"{name} failed"}
        text = json.dumps(result, ensure_ascii=False)
        return ok({"content": [{"type": "text", "text": text}], "isError": "error" in result})
    return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": f"No such method: {method}"}}
