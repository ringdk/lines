"""The sample's data: notes, each belonging to the person who wrote it.

Replace this with the app's own. What it shows: one encrypted connection,
every query scoped to its owner, a schema that only ever grows (rule 9).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lines import db

MAX_CHARS = 2000

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    owner TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS notes_owner ON notes (owner, id);
"""


class Notes:
    def __init__(self, path: Path, key: str) -> None:
        self._conn = db.open_encrypted(path, key)
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        # FastAPI runs plain `def` routes on a thread pool.
        self._lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    def recent(self, owner: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, body, created_at FROM notes WHERE owner = ? ORDER BY id DESC LIMIT ?",
                (owner, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(r) for r in rows]

    def add(self, owner: str, body: str) -> dict[str, Any]:
        body = body.strip()[:MAX_CHARS]
        if not body:
            raise ValueError("A note needs some text")
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute("INSERT INTO notes (owner, body, created_at) VALUES (?, ?, ?)", (owner, body, now))
            self._conn.commit()
        return {"id": cur.lastrowid, "body": body, "created_at": now}

    def delete(self, owner: str, note_id: int) -> bool:
        """The owner's own deliberate delete: the one way a note goes."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM notes WHERE owner = ? AND id = ?", (owner, note_id))
            self._conn.commit()
        return cur.rowcount > 0
