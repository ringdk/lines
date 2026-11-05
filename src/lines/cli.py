"""`lines`: serve, back up, and manage secrets.age.

On astarte this runs as the app's own user through `lines-admin` (sudo,
with the passphrase from /etc/lines/passphrase); `serve` runs under
systemd with it as a credential.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import secrets as tokens
import sys
from pathlib import Path

from lines import config as config_mod
from lines import db, secretfile

# What `secrets set` may write; keys and tokens Serafina needs are made here
# instead, by `web-key` and `mcp-token`.
SETTABLE: tuple[str, ...] = ()


def _unlock(cfg: config_mod.Config) -> None:
    secretfile.use(secretfile.load(cfg.secrets_path, secretfile.resolve_passphrase()))


def cmd_serve(cfg: config_mod.Config, args: argparse.Namespace) -> int:
    from lines import server

    _unlock(cfg)
    return server.run(cfg)


def cmd_backup(cfg: config_mod.Config, args: argparse.Namespace) -> int:
    _unlock(cfg)
    written = db.backup(cfg.db_path, secretfile.get(secretfile.DB_KEY), cfg.secrets_path, Path(args.dest))
    print("\n".join(str(p) for p in written) or "Unchanged since the last copy; nothing written")
    return 0


def cmd_secrets(cfg: config_mod.Config, args: argparse.Namespace) -> int:
    """Keys are made here and printed once, to be handed to Serafina; only a
    token's hash is kept."""
    path = cfg.secrets_path
    if args.action == "init":
        if path.exists():
            print(f"{path} already exists; nothing changed")
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        secretfile.save(path, {secretfile.DB_KEY: db.new_key()}, secretfile.resolve_passphrase(confirm=True))
        print(f"Made {path}, with a new database key")
        return 0
    passphrase = secretfile.resolve_passphrase()
    values = secretfile.load(path, passphrase)
    printed = None
    if args.action == "names":
        print("\n".join(sorted(values)) or "(none)")
        return 0
    if args.action == "web-key":
        values[secretfile.APP_KEY] = printed = tokens.token_hex(32)
    elif args.action == "mcp-token":
        printed = tokens.token_urlsafe(32)
        values[secretfile.MCP_TOKEN_SHA256] = hashlib.sha256(printed.encode()).hexdigest()
    else:
        if args.name not in SETTABLE:
            print(f"`set` takes one of: {', '.join(SETTABLE) or '(none yet)'}")
            return 2
        value = sys.stdin.readline().strip()
        if not value:
            print("No value on stdin; nothing changed")
            return 1
        values[args.name] = value
    secretfile.save(path, values, passphrase)
    if printed is None:
        print(f"Set {args.name}")
        return 0
    # The last line, alone, so `| tail -1` hands it on without showing it.
    print(f"{args.action}: give this to Serafina (her secrets.age); it is not shown again:")
    print(printed)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lines", description="Lines, beside Serafina")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="listen on loopback for Serafina").set_defaults(func=cmd_serve)
    backup = sub.add_parser("backup", help="an encrypted copy of the database (and secrets.age) in DEST")
    backup.add_argument("dest")
    backup.set_defaults(func=cmd_backup)
    sec = sub.add_parser("secrets", help="manage secrets.age")
    sec.add_argument("action", choices=["init", "names", "web-key", "mcp-token", "set"])
    sec.add_argument("name", nargs="?", help="for `set`: the secret's name; the value is read from stdin")
    sec.set_defaults(func=cmd_secrets)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        return args.func(config_mod.load(), args)
    except (secretfile.SecretsError, db.DatabaseError) as exc:
        print(f"lines: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
