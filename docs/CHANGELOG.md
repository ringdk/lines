# Changelog

Newest first. Each entry has a date and an `rN`; anything someone can see or
do differently also gets a line in [WHATS_NEW.md](WHATS_NEW.md) with the same
date and `rN`.

## 2026-11-05 — r2

- Runs as you, under a systemd user unit, from `~/workspace/lines`: no
  system user, no `/opt`, no sudo to install, deploy or restart (Serafina's
  r282 light kit). `deploy/lines-update` builds `main` as checked out and
  restarts the unit; settings and passphrase in `~/.config/lines/env`, data
  in `~/.local/share/lines`. `lines-admin` and the restart sudoers rule are
  gone, and so is the unit's network deny list (and its deviation note): a
  user unit can't hold one, and the app now has exactly Serafina's exposure.
- The template's own pieces are unchanged; `app_template.py check` is clean.

## 2026-11-05 — r1

- Made from Serafina's app template as a light app (`app_template.py new
  --light`): signed identity on the pages, bearer token and `user_email` on
  the tools, `secrets.age`, an encrypted database with hourly backups, the
  light deploy kit (no signing key, never built as root), her look.
- Scripts in: a PDF upload (`POST /ui/api/scripts/pdf`, ≤15 MB, `%PDF-`
  checked), pasted text, or a Google Doc shared with "anyone with the link"
  (`gdoc.py`: the id only from the link, the export URL built here,
  redirects only to `docs.google.com`/`*.googleusercontent.com` over https,
  ≤15 MB, a sign-in redirect read as "not shared"). `parse.py` reads PDF rows
  (baseline-grouped spans, italics, gaps by font size, page numbers and
  repeated headers dropped) or text lines into lines, directions and
  headings; `(asides)` become a line's note.
- Runs (`store.py`): cues up to your next line; an attempt graded and the run
  moved on; top, back (the last exchange again), from any line (yours from
  its cue); loops; drills of the weakest lines that repeat the shaky ones;
  settings (suggestions, cue view, directions, words or first letters,
  difficulty auto or 1-5). `grade.py` lines words up by edit distance:
  ok, minor (contractions spelled out or not, an apostrophe that makes
  another word, a one-letter slip in a long word), wrong, and the rest.
  `coach.py`: each line's score, discounted for suggestions and fading by
  day, sets its level; decoys near (same first letter, similar length) and
  far, names kept capitalised.
- Pages: scripts, rehearse (transcript, chips, Line!, meter), script (run
  from, loop, fix), progress, fix (who you play, rename and fold names,
  edit, split, join, add, delete). Context to her panel.
- Seven `lines_*` tools and the scene partner persona (Serafina's §58.3:
  offered only beside Lines).
- The unit reaches the internet for the Google Docs fetch, never the LAN,
  the tailnet, link-local or anything private (noted in
  `serafina-app.toml`).
