# Lines: design note

An app beside Serafina for learning lines (serafina/docs/APPS.md). Agreed
with Dan on 2026-11-05; he wanted to learn a scene for acting class, and "a
system that lets me upload a pdf or google doc link and then with a dedicated
persona … helps run through lines with me".

## Who uses it, for what

The person learning a part. They add a script, say who they play, and Lines
reads the other parts: it gives each cue, waits for their line, and shows
what they got wrong. The scene partner (a persona of Lines' own, in
Serafina's panel beside it) moves the rehearsal and coaches between runs.

## A light app

It keeps nothing personal: scripts (someone else's writing, for practice)
and how well each line is known. So it's a **light** app (APPS.md, "Light
apps"): it runs as danring under a systemd user unit from
`~/workspace/lines`, with no system user, no signing key and no sudo. If it
ever needs to keep something personal, it becomes sealed first.

## What it keeps

| Data | Where | Personal? |
|---|---|---|
| Scripts: title, every line and direction, who says it | `lines.db` (SQLCipher) | No; encrypted at rest anyway, backed up hourly |
| How well each line is known, each attempt's score | `lines.db` | No |
| Rehearsal settings and where each run is | `lines.db` | No |
| Keys and tokens | `secrets.age` | Secret |

Nothing is deleted except a person's own script, by them (with its lines,
scores and attempts), or a line they remove on the review page.

## How it works

- **In:** a PDF upload, pasted text, or a Google Doc shared with "anyone
  with the link", fetched as a PDF (`gdoc.py`). `parse.py` reads rows (with
  italics, from a PDF) into lines, directions and headings: `Name: line`, a
  screenplay's name in capitals, italics or brackets for directions, an
  unnamed row after a direction for whoever spoke last, `(asides)` kept as a
  note. The review page fixes anything it got wrong.
- **A run** (`store.py`): a position, and settings. Showing it never moves
  it; an attempt at your line, a jump or a drill does, so a reload or
  another device picks up where you were. Your own lines start from their
  cue. A loop wraps between two lines; a drill takes your weakest lines,
  each after its cue, and goes round again on the shaky ones.
- **Grading** (`grade.py`): your words lined up with the line's by edit
  distance. `ok`; `minor` for what sounds the same or nearly ("I'm"/"I am",
  "its"/"it's", an apostrophe that makes another word, a one-letter slip in
  a long word); `wrong`, in bold; and the rest of the line past where you
  stopped. First-letter mode checks one letter a word.
- **Difficulty** (`coach.py`): each line's score moves toward each attempt,
  less what suggestions gave (worth less at an easy level), and fades
  slowly by day. Its level (1 to 5) sets the chips: a phrase against an
  obvious wrong one at 1, one word against three that look like it at 5.
  The meter shows the level and how much of the part is known; Dan can pin
  a level.

## Pages

| Page | Path | Shows |
|---|---|---|
| Scripts | `/` | Your scripts, add one (PDF, paste, Google Doc) |
| Rehearse | `?script=<id>&view=rehearse` | The run: cues, your graded lines, suggestions, Line!, top, back, drill, settings |
| Script | `?script=<id>&view=script` (`&line=<id>`) | The whole script, your lines' levels; run from, loop, fix a line |
| Progress | `?script=<id>&view=progress` | How much you know, weakest lines, practice by day |
| Fix | `?script=<id>&view=review` (`&line=<id>`) | Who you play, names, every line editable |

Context for her panel (§53): the script and the line up next.

## Tools

| Tool | Does | Result extras |
|---|---|---|
| `lines_scripts` | The person's scripts | |
| `lines_status` | Where they are, the cue, what they know, weakest lines, today | |
| `lines_read` | Part of the script, exactly, from a position or a quote | |
| `lines_jump` | Top, back, or from a quoted line; optionally loop | `_open`, `_changed`, `_pill` |
| `lines_drill` | Drill the weakest lines | `_open`, `_changed` |
| `lines_settings` | Suggestions, cue view, directions, input, difficulty | `_changed` |
| `lines_open` | Show a script's page | `_open` |

Every call is for `_serafina.user_email`, checked against `LINES_USERS`.

## The scene partner

`integration/serafina/scene-partner.persona.md`: Lines' own persona (her
§58.3, r281), offered only in the panel beside Lines, with only the `lines_*`
tools and no memory of the person's life. It quotes the script from
`lines_read`, never from memory.

## Untrusted content

A script is someone else's writing, and an uploaded PDF or a fetched doc is
untrusted input: parsed into text, rendered as text only, and her MCP entry
is `untrusted: true`, so it reaches her model inside the fence. The Google
Docs fetch takes only the document's id from the link and builds the
address itself; redirects are followed only to Google's document hosts over
https.

Lines runs as danring, so a memory bug in MuPDF triggered by a crafted PDF
would reach what danring can: the same exposure Serafina already has, since
she parses uploaded PDFs with the same library as the same user. That's the
light-app trade-off (APPS.md), accepted because nothing in Lines is
personal.

## Not doing (yet)

Voice: hearing cues read aloud, saying your line (later; Serafina has no
speech yet). Sharing scripts between people.
