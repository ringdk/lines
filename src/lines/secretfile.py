"""`secrets.age`: Lines's keys and tokens (serafina/docs/APPS.md rule 6).

A passphrase-encrypted age file of `NAME=value` lines in the data directory,
decrypted into memory at startup and never written anywhere in plaintext. The
passphrase comes from `LINES_AGE_PASSPHRASE`, a systemd credential
(`LoadCredential=passphrase:…`, which never shows up in the environment or on
a command line), or a prompt. Its own file and passphrase, so a leak of one
app's never opens another's. Nothing falls back to the environment.
"""

from __future__ import annotations

import getpass
import logging
import os
import sys
from pathlib import Path

import pyrage.passphrase as age_pass

PASSPHRASE_ENV = "LINES_AGE_PASSPHRASE"
CREDENTIAL_NAME = "passphrase"

# The key Serafina's app proxy signs with (her §52), shared with her.
APP_KEY = "LINES_APP_KEY"
# Only the SHA-256 of the token her MCP client sends.
MCP_TOKEN_SHA256 = "LINES_MCP_TOKEN_SHA256"
# this app's own secrets, each in OWN
# The database's raw SQLCipher key (db.py).
DB_KEY = "LINES_DB_KEY"
OWN: tuple[str, ...] = (DB_KEY,)
# end of this app's own
KNOWN = (APP_KEY, MCP_TOKEN_SHA256, *OWN)

_SECRETS: dict[str, str] = {}


class SecretsError(RuntimeError):
    pass


def get(name: str) -> str:
    return _SECRETS.get(name, "")


def use(values: dict[str, str]) -> None:
    _SECRETS.clear()
    _SECRETS.update(values)
    install_redaction(values)


def resolve_passphrase(*, confirm: bool = False) -> str:
    if pp := os.environ.get(PASSPHRASE_ENV):
        return pp
    if creds := os.environ.get("CREDENTIALS_DIRECTORY"):
        path = Path(creds) / CREDENTIAL_NAME
        if path.is_file() and (pp := path.read_text(encoding="utf-8").strip()):
            return pp
    if not sys.stdin.isatty():
        raise SecretsError(f"No passphrase: set {PASSPHRASE_ENV}, give the service a credential, or use a terminal")
    pp = getpass.getpass("Lines passphrase: ")
    if confirm and getpass.getpass("Again: ") != pp:
        raise SecretsError("Passphrases did not match")
    if not pp:
        raise SecretsError("Empty passphrase")
    return pp


def parse_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def load(path: Path, passphrase: str) -> dict[str, str]:
    if not path.exists():
        raise SecretsError(f"No secrets file at {path} (lines secrets init makes one)")
    try:
        plaintext = age_pass.decrypt(path.read_bytes(), passphrase)
    except Exception as exc:  # pyrage raises several types; all of them mean "can't open"
        raise SecretsError(f"Could not decrypt {path}: wrong passphrase?") from exc
    return parse_lines(plaintext.decode())


def save(path: Path, values: dict[str, str], passphrase: str) -> None:
    """Write `values` encrypted, checking the round trip before replacing the file."""
    for name, value in values.items():
        if any(c in value for c in ("\n", "\r", "\x00")):
            raise SecretsError(f"Refusing to write {name}: value contains a line break")
    plaintext = "".join(f"{k}={v}\n" for k, v in values.items())
    ciphertext = age_pass.encrypt(plaintext.encode(), passphrase)
    if age_pass.decrypt(ciphertext, passphrase).decode() != plaintext:
        raise SecretsError("Round-trip check failed; secrets file not written")
    tmp = path.with_suffix(".age.tmp")
    tmp.write_bytes(ciphertext)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


class RedactingFilter(logging.Filter):
    """Masks loaded secret values in every log record."""

    def __init__(self, values: dict[str, str]) -> None:
        super().__init__()
        self._values = [v for v in values.values() if v and len(v) >= 8]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = msg
        for value in self._values:
            redacted = redacted.replace(value, "[REDACTED]")
        if redacted != msg:
            record.msg, record.args = redacted, ()
        return True


_redactor: RedactingFilter | None = None


def install_redaction(values: dict[str, str]) -> None:
    """On the root logger's handlers, which everything reaches: `serve` sets
    them up first and runs uvicorn with log_config=None, so its loggers
    propagate here too."""
    global _redactor
    root = logging.getLogger()
    for target in (root, *root.handlers):
        if _redactor is not None:
            target.removeFilter(_redactor)
    _redactor = RedactingFilter(values)
    for target in (root, *root.handlers):
        target.addFilter(_redactor)
