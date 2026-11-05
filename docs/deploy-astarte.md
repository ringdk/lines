# Lines on astarte, behind Serafina

Lines runs as its own user, as every app beside Serafina does
(serafina/docs/APPS.md). It's a **light app**: it keeps nothing personal, so
its deployed code belongs to you and deploys need no signing key and no
sudo. People reach its pages only through her sign-in; her model reaches its
tools only with her token.

| | |
|---|---|
| Runs as | `lines` (`lines.service`) |
| Code | `/opt/lines`, yours, deployed from `~/workspace/lines` by `~/.local/bin/lines-update` |
| Data | `/var/lib/lines` (0700): the database and `secrets.age` |
| Passphrase | `/etc/lines/passphrase`, root only, handed to the units by systemd |
| Listens | `127.0.0.1:8795`: `/ui` for her signed identity, `/mcp` for her token |
| Backups | hourly, encrypted, to `/mnt/media/lines-backup` (`lines-backup.timer`) |

Everything below is copy and paste, in order, on astarte as danring.

## 1. Once, with sudo (Dan)

```bash
cd ~/workspace && git clone git@github.com:ringdk/lines.git
cd ~/workspace/lines

# The user, the places its code and Python go (yours), who may use it, the
# admin tool, and the restart rule.
sudo useradd --system --home-dir /var/lib/lines --shell /usr/sbin/nologin lines
sudo install -d -o danring -g danring -m 0755 /opt/lines /opt/lines-python
sudo install -d -o root -g root -m 0755 /etc/lines
sudo install -m 0644 deploy/lines.env.example /etc/lines/lines.env   # who may use it; edit if needed
sudo install -m 0755 -o root -g root deploy/lines-admin /usr/local/sbin/lines-admin
sudo install -m 0440 deploy/lines-reload.sudoers /etc/sudoers.d/lines-reload
sudo visudo -c

# The update script is yours, and so is the first deploy: no sudo.
install -D -m 0755 deploy/lines-update ~/.local/bin/lines-update
~/.local/bin/lines-update

# The units, installed but not started yet, and the backups' home on the
# media disk (systemd won't start the backup without it).
sudo install -m 0644 deploy/lines.service deploy/lines-backup.service deploy/lines-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
mkdir -p /mnt/media/lines-backup

# secrets.age with a new database key, and the passphrase that opens it.
sudo lines-admin init
```

The two keys Serafina needs pass through files only you can read, and are
shredded once she has them:

```bash
(umask 077; sudo lines-admin web-key | tail -1 > ~/lines-web-key)
(umask 077; sudo lines-admin mcp-token | tail -1 > ~/lines-mcp-token)
cd ~/workspace/serafina
(set -a; . ~/.config/serafina/env; uv run scripts/set_secret.py LINES_APP_KEY "$(cat ~/lines-web-key)" && shred -u ~/lines-web-key)
(set -a; . ~/.config/serafina/env; uv run scripts/set_secret.py LINES_MCP_TOKEN "$(cat ~/lines-mcp-token)" && shred -u ~/lines-mcp-token)
cd ~/workspace/lines

sudo systemctl enable --now lines.service lines-backup.timer
curl -s http://127.0.0.1:8795/health                  # {"ok":true}
```

## 2. Serafina's config (straight after step 1)

Her three entries for the app (`integration/serafina/README.md` has them),
added by her own script: it backs her config up to
`config/backups/<UTC>-pre-lines.yaml`, adds only what's missing, checks
the result loads, and shows the difference. No sudo is needed;
`reload.sh`'s restart is already passwordless.

```bash
cd ~/workspace/serafina

# She has both keys from step 1? Prints "set" or "MISSING", never the value.
(set -a; . ~/.config/serafina/env; uv run python -c 'from serafina import secrets as s; s.load_age(); [print(k, "set" if s.get_secret(k) else "MISSING") for k in ("LINES_APP_KEY", "LINES_MCP_TOKEN")]')

uv run python scripts/add_app.py /opt/lines/serafina-app.toml
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
git -C ~/workspace/lines pull --ff-only && ~/.local/bin/lines-update   # every deploy; no sudo
sudo systemctl restart lines.service      # no password either
journalctl -u lines -n 50
journalctl -t lines-update                # deploys and refusals
ls -la /mnt/media/lines-backup            # the hourly copies
```

When `deploy/lines-update` changes, copy it to `~/.local/bin` again (no
sudo). `lines-admin`, the sudoers drop-in and the units reach astarte
only when you reinstall them with sudo, as in step 1. A change to the skill
needs Serafina's reload (`scripts/reload.sh` in her checkout).

## If it ever needs to keep something personal

It stops being a light app first: it becomes a sealed one before the first
personal thing is stored, following serafina/docs/APPS.md ("Light apps"):
stop it, `sudo rm -rf /opt/lines /opt/lines-python` and
`rm ~/.local/bin/lines-update` (nothing danring wrote may be built on),
the sealed files and signed commits, a fresh root-owned clone, and new keys
throughout. Ask Dan; don't just start storing it.

## Removing it

```bash
cd ~/workspace/serafina
cp config/serafina.yaml config/backups/$(date -u +%Y%m%dT%H%M%SZ)-pre-removing-lines.yaml
# delete the three entries (integration/serafina/README.md), then:
./scripts/reload.sh
sudo systemctl disable --now lines.service lines-backup.timer
```

That stops it and takes it out of Serafina; its data, backups and code stay
where they are until you decide otherwise.
