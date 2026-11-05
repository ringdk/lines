"""Settings that aren't secret, from the environment: /etc/lines/lines.env
under systemd, the shell in development. Secrets are in secrets.age
(secretfile.py), never here."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

# Both doors are Serafina's, so it only ever listens on loopback; this isn't
# a setting on purpose.
HOST = "127.0.0.1"
DEFAULT_PORT = 8795


class Config(BaseModel):
    data_dir: Path = Path("data")
    port: int = DEFAULT_PORT
    # Who may use it: the emails Serafina vouches for, from LINES_USERS. The
    # same list holds for the pages and the tools.
    users: list[str] = Field(default_factory=list)

    def may_use(self, email: object) -> bool:
        return isinstance(email, str) and email.strip().lower() in self.users

    @property
    def secrets_path(self) -> Path:
        return self.data_dir / "secrets.age"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "lines.db"


def load() -> Config:
    raw: dict[str, object] = {
        "users": [e.strip().lower() for e in os.environ.get("LINES_USERS", "").split(",") if e.strip()],
    }
    if data_dir := os.environ.get("LINES_DATA_DIR", "").strip():
        raw["data_dir"] = data_dir
    if port := os.environ.get("LINES_PORT", "").strip():
        raw["port"] = int(port)
    return Config.model_validate(raw)
