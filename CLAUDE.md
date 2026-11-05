# CLAUDE.md — working rules for lines

An app beside Serafina: its own repo, service, user and data, on loopback,
reaching her only through her config. A **light app** (serafina/docs/APPS.md,
"Light apps"): it keeps nothing personal, so it runs as you, from your
checkout, under your own systemd: no system user, no signing key, no sudo. Its pages show inside her, behind her
sign-in; her model uses it through its tools. See [README.md](README.md) and
[docs/DESIGN.md](docs/DESIGN.md). The rules are serafina/docs/APPS.md's,
adapted here.

## Rules

- **Git:** develop on `dev/dan.ring/<short-desc>` branches; never commit to
  `main` directly, never force-push. Merge to `main` once tests, ruff and the
  frontend lint are green, then push `main`. Anything touching auth, tokens,
  keys, crypto, path handling or untrusted content gets `/security-review`
  on the diff first.
- **Stage files by name.** Never `git add -A`, `git add .` or `commit -a`.
  `.githooks/pre-commit` refuses databases, secrets and media outside
  `tests/fixtures/` and `frontend/public/`; enable it with
  `git config core.hooksPath .githooks` and never bypass it.
- **Nothing personal, ever.** That's what lets it be light: no signing key,
  code that's yours. If a change would store anything personal or sensitive
  (money, health, documents, messages, private media, anyone's details), stop
  and ask Dan: it becomes a sealed app first (APPS.md), never by stealth.
- **Data is still kept with care.** The database is encrypted at rest anyway
  (SQLCipher, its key in `secrets.age`) and backed up hourly. Back it up
  before any schema change or bulk write; migrations are additive or
  copy-then-swap. Nothing is deleted except down a deliberate path (a person
  deleting their own).
- **Secrets live in `secrets.age`** in the data directory, its passphrase
  in `~/.config/lines/env` (0600, outside the repo), never in `.env` or
  the repo. New secret names go in `env.template`'s list and
  `secretfile.py`. Never log or commit one; log output is redacted. A light
  app's keys guard only itself: never give it anyone else's credential.
- **Scripts are untrusted input.** An uploaded PDF or a fetched doc is
  parsed and rendered as text only. The Google Docs fetch (`gdoc.py`) builds
  its address from the document id alone and follows redirects only to
  Google's document hosts over https; never fetch a URL someone typed.
- **Never paraphrase a script.** What the page or a tool shows as a line is
  the line, exactly; the scene partner quotes `lines_read`.
- **Who gets in.** Everything under `/ui` needs Serafina's signed identity
  (`auth.py`), `/mcp` her bearer token plus `_serafina.user_email` on every
  call, both held to `LINES_USERS`. Nothing else answers but `/health`.
  Never add an unauthenticated read anywhere, and never a second port without
  asking (APPS.md rule 4).
- **The UI runs on Serafina's origin**, where her session cookie lives: an
  XSS here is an XSS in her. No inline scripts or styles (the page CSP
  forbids them), no raw HTML from data (React children only, never
  `innerHTML`), links from data http(s) only, and a GET never changes
  anything.
- **Serafina's look.** Her theme (ink/rose tokens, Inter, lucide icons, her
  header bar and controls in `frontend/src/ui.tsx`); keep it in step with
  her `tailwind.config.js`. Mobile first, her rule 10: no
  `window.confirm`/`alert`, 44px touch targets, 16px fields on touch, no
  hover-only affordances, nothing tappable top-right, safe areas, `dvh`.
- **Serafina knows nothing about this repo** except through config: the
  `apps:`, `mcp_servers:` and `skill_dirs:` entries and the skill in
  `integration/serafina/`. Tool names carry the `lines_` prefix; renaming
  one is a breaking change for her — update the skill's `tools:` list in the
  same change.
- **Docs:** user-visible changes get a `docs/WHATS_NEW.md` entry beside the
  `docs/CHANGELOG.md` one (same date and `rN`, newest first, first person, no
  module names); keep `docs/TODO.md` and `docs/DESIGN.md` current and the
  README's diagram true.
- `uv` for Python (`uv add`, `uv run`), `npm` in `frontend/`. Minimal
  comments — explain why, not what.

## Checks

```bash
uv run pytest && uv run ruff check . && (cd frontend && npm run lint)
```

## Applying changes on astarte

Lines runs as you, as the user unit `lines.service`, from
`~/workspace/lines` on `main`
([docs/deploy-astarte.md](docs/deploy-astarte.md)). Deploy after every
merge, once `main` is pushed:

```
ssh danring@astarte.local 'git -C ~/workspace/lines pull --ff-only --quiet && ~/workspace/lines/deploy/lines-update'
```

It builds what's checked out and restarts the unit; it refuses a branch
other than `main` or changes that aren't committed, so astarte's checkout is
for deploying, not for working in. If it refuses, stop and tell Dan; don't
work around it. Nothing here needs sudo, and nothing should: never give it
a system user, a sudoers rule or a root-owned piece (that's a sealed app,
APPS.md). The units are linked from the checkout, so a pull brings their
changes and the update script's `daemon-reload` applies them. A change to the
skill or the persona needs Serafina's reload (`scripts/reload.sh` in her
checkout).

## The template

This repo was made from Serafina's app template (`serafina/templates/app`).
In her checkout, `uv run python scripts/app_template.py check ../lines`
shows where it differs from the template. When the template changes (a
security fix, say), run it and bring this repo in line, or note the reason
in `serafina-app.toml` under `[deviations]`.
