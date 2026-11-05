# Lines on astarte, behind Serafina

Lines is a **light app** (serafina/docs/APPS.md, "Light apps"): it keeps
nothing personal, so it runs as you, from your checkout, under your own
systemd. Installing, deploying and restarting it need no sudo at all. People
reach its pages only through Serafina's sign-in; her model reaches its tools
only with her token.

| | |
|---|---|
| Runs as | you (`danring`), `systemctl --user` unit `lines.service` |
| Code | `~/workspace/lines`, on `main` |
| Settings | `~/.config/lines/env` (0600): who may use it, its data directory, the passphrase |
| Data | `~/.local/share/lines`: the database and `secrets.age` |
| Listens | `127.0.0.1:8795`: `/ui` for her signed identity, `/mcp` for her token |
| Backups | hourly, encrypted, to `/mnt/media/lines-backup` (`lines-backup.timer`) |

Everything below is copy and paste, in order, on astarte as danring. Your
user units keep running while you're logged out because lingering is on
(`loginctl show-user danring -p Linger` says `yes`).

## 1. Once

```bash
cd ~/workspace && git clone git@github.com:ringdk/lines.git
cd ~/workspace/lines && git config core.hooksPath .githooks

# Its settings and a new passphrase, in a file only you can read.
install -d -m 0700 ~/.config/lines
(umask 077; sed "s|^LINES_AGE_PASSPHRASE=.*|LINES_AGE_PASSPHRASE=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')|" \
  deploy/lines.env.example > ~/.config/lines/env)

# Build it, and make secrets.age with a new database key.
deploy/lines-update
(set -a; . ~/.config/lines/env; .venv/bin/lines secrets init)
```

The two keys Serafina needs pass through files only you can read, and are
shredded once she has them:

```bash
(umask 077; set -a; . ~/.config/lines/env; .venv/bin/lines secrets web-key | tail -1 > ~/lines-web-key)
(umask 077; set -a; . ~/.config/lines/env; .venv/bin/lines secrets mcp-token | tail -1 > ~/lines-mcp-token)
cd ~/workspace/serafina
(set -a; . ~/.config/serafina/env; uv run scripts/set_secret.py LINES_APP_KEY "$(cat ~/lines-web-key)" && shred -u ~/lines-web-key)
(set -a; . ~/.config/serafina/env; uv run scripts/set_secret.py LINES_MCP_TOKEN "$(cat ~/lines-mcp-token)" && shred -u ~/lines-mcp-token)
cd ~/workspace/lines
```

Then the units, linked from the checkout so a pull brings their changes:

```bash
mkdir -p /mnt/media/lines-backup
systemctl --user link ~/workspace/lines/deploy/lines.service \
  ~/workspace/lines/deploy/lines-backup.service ~/workspace/lines/deploy/lines-backup.timer
systemctl --user enable --now lines.service lines-backup.timer
curl -s http://127.0.0.1:8795/health                  # {"ok":true}
```

## 2. Serafina's config (straight after step 1)

Her three entries for the app (`integration/serafina/README.md` has them),
added by her own script: it backs her config up to
`config/backups/<UTC>-pre-lines.yaml`, adds only what's missing, checks
the result loads, and shows the difference.

```bash
cd ~/workspace/serafina

# She has both keys from step 1? Prints "set" or "MISSING", never the value.
(set -a; . ~/.config/serafina/env; uv run python -c 'from serafina import secrets as s; s.load_age(); [print(k, "set" if s.get_secret(k) else "MISSING") for k in ("LINES_APP_KEY", "LINES_MCP_TOKEN")]')

uv run python scripts/add_app.py ~/workspace/lines/serafina-app.toml
```

If both keys say `set` and the difference is only the new entries:

```bash
./scripts/reload.sh
journalctl -u serafina-backend --since "-3 min" --no-pager | grep "'lines'"
```

The last line should say `MCP server 'lines': 3 tool(s) registered`.
If it prints nothing she's still starting: run it again in half a minute.
Then open Serafina: Lines is in her apps row.

If her backend doesn't come back, put her config back (the script printed
the backup's name; `ls config/backups | tail -1` finds it) and reload:

```bash
cp config/backups/<the backup> config/serafina.yaml && ./scripts/reload.sh
```

## After that

```bash
git -C ~/workspace/lines pull --ff-only && ~/workspace/lines/deploy/lines-update   # every deploy
systemctl --user restart lines.service
journalctl --user -u lines -n 50
journalctl -t lines-update                # what was built
ls -la /mnt/media/lines-backup            # the hourly copies
```

The update script reloads your systemd before it restarts, so a changed
unit file takes effect with the deploy. A change to the skill needs
Serafina's reload (`scripts/reload.sh` in her checkout).

## If it ever needs to keep something personal

It stops being a light app first: it becomes a sealed one before the first
personal thing is stored, following serafina/docs/APPS.md ("Light apps"):
its own user and a root-owned checkout, signed deploys, and new keys
throughout. Ask Dan; don't just start storing it.

## Removing it

```bash
cd ~/workspace/serafina
cp config/serafina.yaml config/backups/$(date -u +%Y%m%dT%H%M%SZ)-pre-removing-lines.yaml
# delete the three entries (integration/serafina/README.md), then:
./scripts/reload.sh
systemctl --user disable --now lines.service lines-backup.timer
```

That stops it and takes it out of Serafina; its data, backups and code stay
where they are until you decide otherwise.
