"""Serafina's tools: MCP's streamable HTTP at /mcp, which for a tools-only
server is JSON-RPC 2.0 over POST, behind her bearer token (auth.py).

Her config passes `_serafina` with every call (`pass_context: true`): who
it's for is checked on every call, against the same list as the pages
(serafina/docs/APPS.md rule 3), and it's the only owner a tool acts for.
`_serafina` is never in a tool's schema, so her model neither sees nor forges
it.

Tool names carry the app's prefix. Renaming one breaks her, so the skill's
`tools:` list (integration/serafina/) changes in the same commit. What a
result can carry for her (§50.5, §55): `_pill`, a word shown while she
works; `_open`, a page of the app to show, built here from typed arguments;
`_changed`, so a page on screen catches up.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from lines.config import Config
from lines.notes import Notes

log = logging.getLogger(__name__)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "lines_list",
        "description": "The person's notes in Lines, newest first.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}},
            "additionalProperties": False,
        },
    },
    {
        "name": "lines_add",
        "description": "Add a note to Lines for the person.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "The note, as they said it"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lines_open",
        "description": "SHOW the notes in Lines itself (the page beside the chat), optionally one note.",
        "inputSchema": {
            "type": "object",
            "properties": {"note": {"type": "integer", "description": "A note's id, from lines_list"}},
            "additionalProperties": False,
        },
    },
]
NAMES = {t["name"] for t in TOOLS}


def _split(arguments: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    args = dict(arguments)
    context = args.pop("_serafina", None)
    return args, context if isinstance(context, dict) else {}


def call(config: Config, notes: Notes, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    args, context = _split(arguments)
    # The token says it's Serafina; this says she's asking for someone who may use it.
    email = context.get("user_email")
    if not config.may_use(email):
        return {"error": "Lines isn't open to this account."}
    owner = str(email).strip().lower()

    if name == "lines_list":
        limit = args.get("limit", 50)
        found = notes.recent(owner, limit=limit if isinstance(limit, int) else 50)
        return {"count": len(found), "notes": found}
    if name == "lines_add":
        try:
            note = notes.add(owner, str(args.get("text") or ""))
        except ValueError as exc:
            return {"error": str(exc)}
        return {"added": note, "_pill": "noted", "_changed": True}
    if name == "lines_open":
        note = args.get("note")
        if isinstance(note, int) and not isinstance(note, bool):
            return {"shown": True, "_open": {"path": f"?note={note}", "label": f"Note {note}"}}
        return {"shown": True, "_open": {"path": "", "label": "Your notes"}}
    return {"error": f"No such tool: {name}"}


def handle(config: Config, notes: Notes, body: dict[str, Any]) -> dict[str, Any]:
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
            result = call(config, notes, name, arguments if isinstance(arguments, dict) else {})
        except Exception:
            log.exception("tool %s failed", name)
            result = {"error": f"{name} failed"}
        text = json.dumps(result, ensure_ascii=False)
        return ok({"content": [{"type": "text", "text": text}], "isError": "error" in result})
    return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": f"No such method: {method}"}}
