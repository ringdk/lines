"""The database file: SQLCipher under a raw key from secrets.age, and its
backups (serafina/docs/APPS.md rule 9: personal data is encrypted at rest).

A copy is made through SQLite (`sqlcipher_export`) inside a read transaction,
so a write in progress can't leave it half-made the way copying the file
could. It goes in under a temporary name and is moved into place only once it
opens with the key.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

import sqlcipher3

KEY_RE = re.compile(r"^[0-9a-f]{64}$")


class DatabaseError(RuntimeError):
    pass


def new_key() -> str:
    return secrets.token_hex(32)


def _key_sql(key: str) -> str:
    # A raw key: no passphrase stretching, so opening is instant. Only ever a
    # checked hex string, so it's safe in the statement.
    if not KEY_RE.match(key or ""):
        raise DatabaseError("The database key must be 64 lowercase hex characters")
    return f"\"x'{key}'\""


def open_encrypted(path: Path, key: str) -> sqlcipher3.Connection:
    """Open (creating if needed) the encrypted database, refusing a wrong key or a plaintext file."""
    key_sql = _key_sql(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlcipher3.connect(str(path), check_same_thread=False)
    conn.execute(f"PRAGMA key = {key_sql}")
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlcipher3.DatabaseError as exc:
        conn.close()
        raise DatabaseError(f"Can't open {path}: wrong key, or it isn't encrypted") from exc
    conn.row_factory = sqlcipher3.Row
    return conn


def backup(db_path: Path, key: str, secrets_path: Path, dest_dir: Path) -> list[Path]:
    """An encrypted copy for the backup disk: `<name>-latest.db`, one dated
    copy a day (never removed here), and the secrets.age that opens them.
    Nothing is written when the database hasn't changed since the last copy."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = db_path.stem
    latest = dest_dir / f"{stem}-latest.db"
    sources = [p for p in (db_path, db_path.with_name(db_path.name + "-wal")) if p.exists()]
    if latest.exists() and all(p.stat().st_mtime <= latest.stat().st_mtime for p in sources):
        return []
    tmp = latest.with_name(latest.name + ".tmp")
    tmp.unlink(missing_ok=True)
    conn = open_encrypted(db_path, key)
    try:
        conn.execute(f"ATTACH DATABASE ? AS copy KEY {_key_sql(key)}", (str(tmp),))
        try:
            conn.execute("SELECT sqlcipher_export('copy')")
        finally:
            conn.execute("DETACH DATABASE copy")
    finally:
        conn.close()
    open_encrypted(tmp, key).close()
    os.replace(tmp, latest)
    written = [latest]
    daily = dest_dir / f"{stem}-{datetime.now(UTC):%Y-%m-%d}.db"
    if not daily.exists():
        shutil.copyfile(latest, daily)
        written.append(daily)
    shutil.copyfile(secrets_path, dest_dir / "secrets.age")
    return written
