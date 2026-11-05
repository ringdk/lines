"""What Serafina needs of the integration files (APPS.md rule 10, her CLAUDE.md
rule 11): skills she can catalogue, tools that name themselves, and no skill
naming a tool the server doesn't have (renaming one breaks her). A tool needn't
be in a skill's list: its server's group is already its home (her §10.2)."""

from __future__ import annotations

import re
from pathlib import Path

from ruamel.yaml import YAML

from tests.conftest import mcp

INTEGRATION = Path(__file__).resolve().parents[1] / "integration" / "serafina"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text.startswith("---\n"), path.name
    return YAML(typ="safe").load(text.split("---\n")[1])


def skills() -> list[Path]:
    return [p for p in INTEGRATION.glob("*.md") if p.name != "README.md" and not p.name.endswith(".persona.md")]


def test_skill_frontmatter():
    assert skills()
    for path in skills():
        meta = frontmatter(path)
        assert meta["name"] == path.stem
        assert re.fullmatch(r"[a-z][a-z0-9-]*", meta["name"])
        assert meta["description"] and meta["when_to_use"]
        assert len(meta["examples"]) >= 2, f"{path.name}: two or more examples, in the person's voice"


def served(client) -> list[dict]:
    return mcp(client, "tools/list").json()["result"]["tools"]


def test_tools_name_themselves_and_say_what_they_do(client):
    for tool in served(client):
        assert re.fullmatch(r"lines_[a-z_]+", tool["name"])
        assert tool["description"] and tool["inputSchema"]["type"] == "object"
        assert "_serafina" not in tool["inputSchema"].get("properties", {})


def test_every_tool_a_skill_lists_exists(client):
    names = {t["name"] for t in served(client)}
    listed = {name for path in skills() for name in frontmatter(path).get("tools") or []}
    assert listed <= names, f"skills list tools the server doesn't have: {sorted(listed - names)}"


def test_the_readme_has_her_three_config_entries():
    readme = (INTEGRATION / "README.md").read_text(encoding="utf-8")
    for line in [
        "  - name: lines",
        "    upstream: http://127.0.0.1:8795/ui",
        "    secret: LINES_APP_KEY",
        "    url: http://127.0.0.1:8795/mcp",
        "    auth: bearer",
        "    token_secret: LINES_MCP_TOKEN",
        "    pass_context: true",
        "  - /opt/lines/integration/serafina",
    ]:
        assert line in readme, line
