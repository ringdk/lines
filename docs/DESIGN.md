# Lines: design note

Step 1 of building an app beside Serafina (serafina/docs/APPS.md): write
this, then ask Dan before building. Replace the sample's answers with the
app's own, and keep the note true as the app changes.

## Who uses it, for what

The household, from Serafina: writing things down and finding them again,
by hand on its page or by asking her.

## What it keeps

| Data | Where | Personal? |
|---|---|---|
| Notes: text, who wrote it, when | `lines.db` (SQLCipher) | Yes: encrypted at rest, backed up hourly |
| Keys and tokens | `secrets.age` | Secret |

Nothing is deleted except a person's own note, by them.

## Pages

| Page | Path | Shows |
|---|---|---|
| Notes | `/` (`?note=<id>` picks one out) | Your notes, a box to add one |

Context for her panel (§53): the notes on screen.

## Tools

| Tool | Does | Result extras |
|---|---|---|
| `lines_list` | The person's notes, newest first | |
| `lines_add` | Adds one, in their words | `_pill`, `_changed` |
| `lines_open` | Shows the notes, or one | `_open` |

Every call is for `_serafina.user_email`, checked against `LINES_USERS`.

## Untrusted content

Note text is what people typed: rendered as text only, and her MCP entry is
`untrusted: true`, so it reaches her model inside the fence.

## Not doing

Sharing notes between people; attachments.
