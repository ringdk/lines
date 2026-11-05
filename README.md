# Lines

An app beside Serafina for learning lines (serafina/docs/APPS.md). Add a
script (a PDF, pasted text, or a Google Doc shared by link), say who you
play, and Lines reads the other parts: it gives each cue, takes your line
(typed, first letters, or tapped from suggestions that get harder as you
learn it), and shows what you got wrong. The scene partner, a persona of its
own in Serafina's panel beside it, moves the rehearsal and coaches you. A
light app: nothing personal in it, deployed with no signing key. Made from
her app template; [docs/DESIGN.md](docs/DESIGN.md) is how it works.

```mermaid
flowchart LR
  phone["phone / browser"] -->|her origin, her sign-in| serafina["Serafina"]
  serafina -->|"/api/apps/lines/… → /ui, signed identity"| app["lines :8795 (loopback)"]
  serafina -->|"MCP → /mcp, bearer token + _serafina"| app
  app --> db[("lines.db, SQLCipher")]
  app -.->|"a doc shared by link, as PDF (https, Google's hosts only)"| google["docs.google.com"]
  app -.->|hourly, encrypted| backup[("/mnt/media/lines-backup")]
```

## Layout

| | |
|---|---|
| `src/lines/auth.py` | Who gets in: her signed identity on `/ui`, her token on `/mcp` |
| `src/lines/secretfile.py` | `secrets.age` |
| `src/lines/db.py` | The encrypted database file and its backups |
| `src/lines/server.py` | The listener, the pages' API, the CSP |
| `src/lines/mcp.py` | The tools the scene partner uses |
| `src/lines/parse.py` | A script (PDF rows or text) into lines, directions and headings |
| `src/lines/gdoc.py` | A Google Doc shared by link, fetched as a PDF |
| `src/lines/store.py` | Scripts, lines, scores, and runs (cues, attempts, jumps, loops, drills) |
| `src/lines/grade.py` | An attempt, word by word: ok, minor, wrong, the rest |
| `src/lines/coach.py` | Scores, levels and the suggestion chips' decoys |
| `frontend/` | The pages, in her theme: scripts, rehearse, script, progress, fix |
| `integration/serafina/` | The skill, the scene partner persona, her config entries |
| `deploy/` | The unit, backups, deploys, admin |
| `docs/` | Design note, deploy steps, changelog, what's new, TODO |

## Running it locally

```bash
uv sync
export LINES_DATA_DIR=data LINES_USERS=you@example.com LINES_AGE_PASSPHRASE=dev-only
uv run lines secrets init
uv run lines secrets web-key | tail -1      # for the dev proxy below
uv run lines serve                          # 127.0.0.1:8795

cd frontend && npm install
LINES_DEV_APP_KEY=<that key> LINES_DEV_USER=you@example.com npm run dev   # :5174, signs like Serafina
```

Checks: `uv run pytest && uv run ruff check . && (cd frontend && npm run lint)`.
On astarte: [docs/deploy-astarte.md](docs/deploy-astarte.md).

## Serafina's template

Made from Serafina's app template (`serafina/templates/app`; the rules are
her `docs/APPS.md`). From her checkout:

```bash
uv run python scripts/app_template.py new ../lines --name lines --port 8795   # how this repo began
uv run python scripts/app_template.py check ../lines       # where it differs from the template now (--diff, --all)
uv run python scripts/add_app.py /opt/lines/serafina-app.toml   # her config entries (docs/deploy-astarte.md, step 2)
```

`serafina-app.toml` holds this app's values for both, `[paths]` for template
files kept somewhere else here, and `[deviations]` for differences on
purpose, each with its reason. In a file the template shares, the lines
between `this app's own` and `end of this app's own` are this app's (its
other secrets, say); the rest has to match. When the template changes, run
`check` and bring this repo in line.
