"""Lines's data: each person's scripts, every line and direction in them, how
well they know each of their lines, and where they are in a run.

Every query is scoped to its owner (a script's elements, mastery and attempts
through the script). The schema only ever grows (APPS.md rule 9); nothing
goes except down a person's own deliberate delete.

A run is a position (the next element to show) and the settings beside it.
Showing where you are never moves you: only an attempt at your line, a jump
or a drill does, so a reload or another device picks up in the same place.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from lines import coach, db
from lines.grade import grade, grade_letters, tokens
from lines.parse import MAX_ELEMENT_CHARS, Element, interrupted, name_key

TOP = 0  # position: from the start
END = -1  # position: past the last line

DEFAULT_SETTINGS: dict[str, Any] = {
    "suggestions": True,
    "cue_view": False,
    "directions": True,
    "input": "words",
    "level": "auto",
    "loop": None,  # {"from": element id, "to": element id}
}
KINDS = ("line", "direction", "heading")
MAX_TITLE = 120
MAX_NAME = 40
MAX_NOTE = 200
CONTEXT = 4  # elements shown before the cues when a run is opened

SCHEMA = """
CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY,
    owner TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    mine TEXT NOT NULL DEFAULT '[]',
    settings TEXT NOT NULL DEFAULT '{}',
    position INTEGER NOT NULL DEFAULT 0,
    mode TEXT NOT NULL DEFAULT 'run',
    drill TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS scripts_owner ON scripts (owner, updated_at);
CREATE TABLE IF NOT EXISTS elements (
    id INTEGER PRIMARY KEY,
    script_id INTEGER NOT NULL REFERENCES scripts (id),
    pos INTEGER NOT NULL,
    kind TEXT NOT NULL,
    character TEXT,
    text TEXT NOT NULL,
    note TEXT,
    page INTEGER
);
CREATE INDEX IF NOT EXISTS elements_script ON elements (script_id, pos);
CREATE TABLE IF NOT EXISTS mastery (
    element_id INTEGER PRIMARY KEY REFERENCES elements (id),
    score REAL NOT NULL,
    attempts INTEGER NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    script_id INTEGER NOT NULL REFERENCES scripts (id),
    element_id INTEGER NOT NULL,
    at TEXT NOT NULL,
    mode TEXT NOT NULL,
    score REAL NOT NULL,
    helped INTEGER NOT NULL,
    gave_up INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_script ON attempts (script_id, at);
"""


class NotFound(LookupError):
    pass


class Stale(RuntimeError):
    """The page answered a line that isn't the one up next."""


def _clean(text: object, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


class Store:
    def __init__(self, path: Path, key: str) -> None:
        self._conn = db.open_encrypted(path, key)
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        # FastAPI runs plain `def` routes on a thread pool.
        self._lock = threading.RLock()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------ scripts

    def _script(self, owner: str, sid: int) -> dict[str, Any]:
        row = self._conn.execute("SELECT * FROM scripts WHERE id = ? AND owner = ?", (sid, owner)).fetchone()
        if row is None:
            raise NotFound("No such script")
        script = dict(row)
        script["settings"] = {**DEFAULT_SETTINGS, **json.loads(script["settings"] or "{}")}
        script["mine"] = json.loads(script["mine"] or "[]")
        script["drill"] = json.loads(script["drill"] or "[]")
        return script

    def _elements(self, sid: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, pos, kind, character, text, note, page FROM elements WHERE script_id = ? ORDER BY pos, id",
            (sid,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _mastery(self, sid: int) -> dict[int, dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT m.element_id, m.score, m.attempts, m.last_seen FROM mastery m "
            "JOIN elements e ON e.id = m.element_id WHERE e.script_id = ?",
            (sid,),
        ).fetchall()
        return {r["element_id"]: dict(r) for r in rows}

    def _touch(self, sid: int) -> None:
        self._conn.execute("UPDATE scripts SET updated_at = ? WHERE id = ?", (coach.now(), sid))

    def _save_run(self, sid: int, **fields: Any) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = [json.dumps(v) if k in ("settings", "mine", "drill") else v for k, v in fields.items()]
        self._conn.execute(f"UPDATE scripts SET {sets}, updated_at = ? WHERE id = ?", (*values, coach.now(), sid))

    @staticmethod
    def characters(elements: list[dict[str, Any]]) -> list[str]:
        seen: dict[str, str] = {}
        for e in elements:
            if e["kind"] == "line" and e["character"]:
                seen.setdefault(name_key(e["character"]), e["character"])
        return list(seen.values())

    def create(self, owner: str, title: str, source: str, elements: list[Element]) -> int:
        title = _clean(title, MAX_TITLE) or "Untitled script"
        stamp = coach.now()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO scripts (owner, title, source, settings, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (owner, title, source, json.dumps(DEFAULT_SETTINGS), stamp, stamp),
            )
            sid = int(cur.lastrowid)
            self._conn.executemany(
                "INSERT INTO elements (script_id, pos, kind, character, text, note, page) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(sid, i, e.kind, e.character, e.text, e.note, e.page) for i, e in enumerate(elements)],
            )
            self._conn.commit()
        return sid

    def scripts(self, owner: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id FROM scripts WHERE owner = ? ORDER BY updated_at DESC, id DESC", (owner,)
            ).fetchall()
            out = []
            for row in rows:
                s = self._script(owner, row["id"])
                els = self._elements(s["id"])
                out.append(
                    {
                        "id": s["id"],
                        "title": s["title"],
                        "source": s["source"],
                        "characters": self.characters(els),
                        "mine": s["mine"],
                        "lines": sum(1 for e in els if e["kind"] == "line"),
                        "mastery": self._overall(s, els, self._mastery(s["id"])),
                        "updated_at": s["updated_at"],
                    }
                )
        return out

    def latest(self, owner: str) -> int | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM scripts WHERE owner = ? ORDER BY updated_at DESC, id DESC LIMIT 1", (owner,)
            ).fetchone()
        return None if row is None else int(row["id"])

    def detail(self, owner: str, sid: int) -> dict[str, Any]:
        with self._lock:
            s = self._script(owner, sid)
            els = self._elements(sid)
            mastery = self._mastery(sid)
            mine = {name_key(c) for c in s["mine"]}
            lines = {}
            for e in els:
                if self._is_mine(e, mine):
                    lines[e["id"]] = self._line_state(e, mastery, s)
            return {
                "id": s["id"],
                "title": s["title"],
                "source": s["source"],
                "characters": self.characters(els),
                "mine": s["mine"],
                "settings": s["settings"],
                "elements": [{**e, "interrupted": interrupted(e["text"])} for e in els],
                "mastery": self._overall(s, els, mastery),
                "lines": lines,
            }

    def update(self, owner: str, sid: int, *, title: object = None, mine: object = None,
               settings: object = None) -> None:  # fmt: skip
        with self._lock:
            s = self._script(owner, sid)
            fields: dict[str, Any] = {}
            if title is not None:
                fields["title"] = _clean(title, MAX_TITLE) or s["title"]
            if mine is not None:
                if not isinstance(mine, list) or not all(isinstance(m, str) for m in mine):
                    raise ValueError("Choose characters by name")
                known = {name_key(c): c for c in self.characters(self._elements(sid))}
                chosen = [known[name_key(m)] for m in mine if name_key(m) in known]
                if len(chosen) != len(mine):
                    raise ValueError("That character isn't in this script")
                fields["mine"] = list(dict.fromkeys(chosen))
            if settings is not None:
                fields["settings"] = self._settings(s["settings"], settings, sid)
            if fields:
                self._save_run(sid, **fields)
                self._conn.commit()

    def _settings(self, current: dict[str, Any], change: object, sid: int) -> dict[str, Any]:
        if not isinstance(change, dict):
            raise ValueError("Settings are a set of choices")
        out = dict(current)
        for key, value in change.items():
            if key in ("suggestions", "cue_view", "directions"):
                if not isinstance(value, bool):
                    raise ValueError(f"{key} is on or off")
                out[key] = value
            elif key == "input":
                if value not in ("words", "letters"):
                    raise ValueError("Input is words or letters")
                out[key] = value
            elif key == "level":
                if value != "auto" and not (isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5):
                    raise ValueError("Difficulty is auto or 1 to 5")
                out[key] = value
            elif key == "loop":
                out[key] = self._loop(value, sid)
            else:
                raise ValueError(f"No setting called {key}")
        return out

    def _loop(self, value: object, sid: int) -> dict[str, int] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("A loop runs from one line to another")
        ids = {e["id"]: i for i, e in enumerate(self._elements(sid))}
        start, end = value.get("from"), value.get("to")
        if start not in ids or end not in ids:
            raise ValueError("A loop runs between two lines of this script")
        if ids[start] > ids[end]:
            start, end = end, start
        return {"from": start, "to": end}

    def delete(self, owner: str, sid: int) -> None:
        """The person's own deliberate delete: the one way a script goes."""
        with self._lock:
            self._script(owner, sid)
            self._conn.execute(
                "DELETE FROM mastery WHERE element_id IN (SELECT id FROM elements WHERE script_id = ?)", (sid,)
            )
            self._conn.execute("DELETE FROM attempts WHERE script_id = ?", (sid,))
            self._conn.execute("DELETE FROM elements WHERE script_id = ?", (sid,))
            self._conn.execute("DELETE FROM scripts WHERE id = ? AND owner = ?", (sid, owner))
            self._conn.commit()

    # ------------------------------------------------------------ editing

    def _element(self, sid: int, eid: int) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT id, pos, kind, character, text, note, page FROM elements WHERE id = ? AND script_id = ?", (eid, sid)
        ).fetchone()
        if row is None:
            raise NotFound("No such line")
        return dict(row)

    def _renumber(self, sid: int) -> None:
        rows = self._conn.execute("SELECT id FROM elements WHERE script_id = ? ORDER BY pos, id", (sid,)).fetchall()
        self._conn.executemany("UPDATE elements SET pos = ? WHERE id = ?", [(i, r["id"]) for i, r in enumerate(rows)])

    @staticmethod
    def _checked(
        kind: object, character: object, text: object, note: object
    ) -> tuple[str, str | None, str, str | None]:
        if kind not in KINDS:
            raise ValueError("A line, a direction or a heading")
        clean_text = str(text or "").strip()[:MAX_ELEMENT_CHARS]
        if not clean_text:
            raise ValueError("It needs some words")
        who = _clean(character, MAX_NAME) or None
        if kind == "line" and not who:
            raise ValueError("A line needs someone to say it")
        return str(kind), who if kind == "line" else None, clean_text, _clean(note, MAX_NOTE) or None

    def edit(self, owner: str, sid: int, eid: int, change: dict[str, Any]) -> None:
        with self._lock:
            self._script(owner, sid)
            e = self._element(sid, eid)
            kind, who, text, note = self._checked(
                change.get("kind", e["kind"]),
                change.get("character", e["character"]),
                change.get("text", e["text"]),
                change.get("note", e["note"]),
            )
            self._conn.execute(
                "UPDATE elements SET kind = ?, character = ?, text = ?, note = ? WHERE id = ? AND script_id = ?",
                (kind, who, text, note, eid, sid),
            )
            self._touch(sid)
            self._conn.commit()

    def insert_after(self, owner: str, sid: int, eid: int, change: dict[str, Any]) -> int:
        with self._lock:
            self._script(owner, sid)
            e = self._element(sid, eid)
            kind, who, text, note = self._checked(
                change.get("kind"), change.get("character"), change.get("text"), change.get("note")
            )
            self._conn.execute("UPDATE elements SET pos = pos + 1 WHERE script_id = ? AND pos > ?", (sid, e["pos"]))
            cur = self._conn.execute(
                "INSERT INTO elements (script_id, pos, kind, character, text, note, page) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, e["pos"] + 1, kind, who, text, note, e["page"]),
            )
            self._renumber(sid)
            self._touch(sid)
            self._conn.commit()
            return int(cur.lastrowid)

    def merge_next(self, owner: str, sid: int, eid: int) -> None:
        with self._lock:
            self._script(owner, sid)
            e = self._element(sid, eid)
            nxt = self._conn.execute(
                "SELECT id, kind, character, text, note FROM elements WHERE script_id = ? AND pos > ? "
                "ORDER BY pos, id LIMIT 1",
                (sid, e["pos"]),
            ).fetchone()
            if nxt is None:
                raise ValueError("Nothing after it to join")
            if nxt["kind"] != e["kind"] or (e["kind"] == "line" and name_key(nxt["character"] or "")
                                             != name_key(e["character"] or "")):  # fmt: skip
                raise ValueError("Only two of the same kind, by the same person, join")
            text = f"{e['text']} {nxt['text']}"[:MAX_ELEMENT_CHARS]
            note = " ".join(n for n in (e["note"], nxt["note"]) if n)[:MAX_NOTE] or None
            self._conn.execute("UPDATE elements SET text = ?, note = ? WHERE id = ?", (text, note, eid))
            self._forget(nxt["id"])
            self._conn.execute("DELETE FROM elements WHERE id = ? AND script_id = ?", (nxt["id"], sid))
            self._renumber(sid)
            self._touch(sid)
            self._conn.commit()

    def split(self, owner: str, sid: int, eid: int, at: int) -> int:
        with self._lock:
            self._script(owner, sid)
            e = self._element(sid, eid)
            first, second = e["text"][:at].strip(), e["text"][at:].strip()
            if not first or not second:
                raise ValueError("Split it somewhere in the middle")
            self._conn.execute("UPDATE elements SET text = ? WHERE id = ?", (first, eid))
            self._conn.execute("UPDATE elements SET pos = pos + 1 WHERE script_id = ? AND pos > ?", (sid, e["pos"]))
            cur = self._conn.execute(
                "INSERT INTO elements (script_id, pos, kind, character, text, note, page) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, e["pos"] + 1, e["kind"], e["character"], second, None, e["page"]),
            )
            self._renumber(sid)
            self._touch(sid)
            self._conn.commit()
            return int(cur.lastrowid)

    def remove(self, owner: str, sid: int, eid: int) -> None:
        with self._lock:
            self._script(owner, sid)
            self._element(sid, eid)
            self._forget(eid)
            self._conn.execute("DELETE FROM elements WHERE id = ? AND script_id = ?", (eid, sid))
            self._renumber(sid)
            self._touch(sid)
            self._conn.commit()

    def _forget(self, eid: int) -> None:
        self._conn.execute("DELETE FROM mastery WHERE element_id = ?", (eid,))

    def rename(self, owner: str, sid: int, old: str, new: str) -> None:
        """Rename a character, or fold one into another ("DAVID" into "David")."""
        new = _clean(new, MAX_NAME)
        if not new:
            raise ValueError("A character needs a name")
        with self._lock:
            s = self._script(owner, sid)
            rows = [e for e in self._elements(sid) if e["kind"] == "line" and name_key(e["character"] or "")
                    == name_key(old)]  # fmt: skip
            if not rows:
                raise NotFound("No such character")
            self._conn.executemany("UPDATE elements SET character = ? WHERE id = ?", [(new, e["id"]) for e in rows])
            mine = [new if name_key(m) == name_key(old) else m for m in s["mine"]]
            self._save_run(sid, mine=list(dict.fromkeys(mine)))
            self._conn.commit()

    # ------------------------------------------------------------ rehearsing

    @staticmethod
    def _is_mine(e: dict[str, Any], mine: set[str]) -> bool:
        return e["kind"] == "line" and name_key(e["character"] or "") in mine

    def _line_state(self, e: dict[str, Any], mastery: dict[int, dict[str, Any]], s: dict[str, Any]) -> dict:
        m = mastery.get(e["id"])
        eff = coach.effective(m["score"], m["last_seen"]) if m else 0.0
        return {"score": round(eff, 3), "attempts": m["attempts"] if m else 0, "level": coach.level_for(eff)}

    def _overall(self, s: dict[str, Any], els: list[dict[str, Any]], mastery: dict[int, dict[str, Any]]) -> float:
        mine = {name_key(c) for c in s["mine"]}
        total = known = 0.0
        for e in els:
            if self._is_mine(e, mine):
                weight = max(1, len(tokens(e["text"])))
                m = mastery.get(e["id"])
                total += weight
                known += weight * (coach.effective(m["score"], m["last_seen"]) if m else 0.0)
        return round(known / total, 3) if total else 0.0

    def _level(self, s: dict[str, Any], e: dict[str, Any], mastery: dict[int, dict[str, Any]], overall: float) -> int:
        pinned = s["settings"]["level"]
        if pinned != "auto":
            return int(pinned)
        m = mastery.get(e["id"])
        return coach.level_for(coach.effective(m["score"], m["last_seen"]) if m else overall)

    def _public(self, e: dict[str, Any]) -> dict[str, Any]:
        return {**e, "interrupted": interrupted(e["text"])}

    def _view(self, s: dict[str, Any]) -> dict[str, Any]:
        """Where the person is: what's said before their next line, and that line to answer."""
        els = self._elements(s["id"])
        mastery = self._mastery(s["id"])
        mine = {name_key(c) for c in s["mine"]}
        overall = self._overall(s, els, mastery)
        index = {e["id"]: i for i, e in enumerate(els)}
        mine_total = sum(1 for e in els if self._is_mine(e, mine))
        base: dict[str, Any] = {
            "script": s["id"],
            "mode": s["mode"],
            "settings": s["settings"],
            "mine": s["mine"],
            "mastery": overall,
            "total": mine_total,
        }
        if not mine:
            return {**base, "needs_character": True, "context": [], "cues": [], "prompt": None, "end": False}

        if s["mode"] == "drill":
            queue = [q for q in s["drill"] if q["id"] in index]
            if queue:
                at = index[queue[0]["id"]]
                cues = []
                k = at - 1
                # Its cue: back to the last thing someone else said.
                while k >= 0 and len(cues) < 3:
                    cues.insert(0, els[k])
                    if els[k]["kind"] == "line" and not self._is_mine(els[k], mine):
                        break
                    k -= 1
                return {**base, "context": [], "cues": [self._public(c) for c in cues],
                        "prompt": self._prompt(s, els[at], mastery, overall, els, mine), "end": False,
                        "remaining": len(queue)}  # fmt: skip
            self._save_run(s["id"], mode="run", drill=[])
            self._conn.commit()
            base["mode"] = "run"

        loop = s["settings"]["loop"]
        span = (index.get(loop["from"], 0), index.get(loop["to"], len(els) - 1)) if loop else (0, len(els) - 1)
        if s["position"] == END:
            start = len(els)
        elif s["position"] == TOP:
            start = span[0]
        else:
            start = index.get(s["position"], span[0])
        if loop and not span[0] <= start <= span[1]:
            start = span[0]
        cues: list[dict[str, Any]] = []
        prompt = None
        wrapped = False
        k = start
        while True:
            if k > span[1] or k >= len(els):
                if loop and not wrapped:
                    wrapped = True
                    cues.append({"kind": "loop"})
                    k = span[0]
                    continue
                break
            if self._is_mine(els[k], mine):
                prompt = els[k]
                break
            cues.append(self._public(els[k]))
            k += 1
        context = [self._public(e) for e in els[max(span[0], start - CONTEXT) : start]] if start <= len(els) else []
        done = sum(1 for e in els[: index[prompt["id"]]] if self._is_mine(e, mine)) if prompt else mine_total
        return {
            **base,
            "context": context,
            "cues": cues,
            "prompt": self._prompt(s, prompt, mastery, overall, els, mine) if prompt else None,
            "end": prompt is None,
            "done": done,
        }

    def _prompt(self, s: dict[str, Any], e: dict[str, Any], mastery: dict[int, dict[str, Any]], overall: float,
                els: list[dict[str, Any]], mine: set[str]) -> dict[str, Any]:  # fmt: skip
        level = self._level(s, e, mastery, overall)
        m = mastery.get(e["id"])
        vocab = coach.vocabulary(x["text"] for x in els if x["kind"] == "line")
        return {
            "id": e["id"],
            "pos": e["pos"],
            "character": e["character"],
            "note": e["note"],
            "words": [t.text for t in tokens(e["text"])],
            "decoys": coach.decoys(e["text"], vocab, seed=f"{e['id']}:{m['attempts'] if m else 0}"),
            "level": level,
            "label": coach.LEVELS[level],
            "score": round(coach.effective(m["score"], m["last_seen"]), 3) if m else None,
            "interrupted": interrupted(e["text"]),
        }

    def view(self, owner: str, sid: int) -> dict[str, Any]:
        with self._lock:
            return self._view(self._script(owner, sid))

    def attempt(self, owner: str, sid: int, line_id: int, text: str, *, mode: str = "words", helped: int = 0,
                gave_up: bool = False) -> dict[str, Any]:  # fmt: skip
        if mode not in ("words", "letters"):
            raise ValueError("Input is words or letters")
        text = str(text or "")[:MAX_ELEMENT_CHARS]
        with self._lock:
            s = self._script(owner, sid)
            current = self._view(s)
            prompt = current["prompt"]
            if prompt is None or prompt["id"] != line_id:
                raise Stale("That isn't the line up next")
            line = self._element(sid, line_id)
            graded = grade_letters(line["text"], text) if mode == "letters" else grade(line["text"], text)
            words = len(graded.words)
            worth = coach.result(graded.score, helped=max(0, min(int(helped), words)), words=words,
                                 level=prompt["level"], letters=mode == "letters")  # fmt: skip
            m = self._mastery(sid).get(line_id)
            before = coach.effective(m["score"], m["last_seen"]) if m else None
            score = coach.updated(before, worth)
            stamp = coach.now()
            self._conn.execute(
                "INSERT INTO mastery (element_id, score, attempts, last_seen) VALUES (?, ?, 1, ?) "
                "ON CONFLICT (element_id) DO UPDATE SET score = excluded.score, attempts = attempts + 1, "
                "last_seen = excluded.last_seen",
                (line_id, score, stamp),
            )
            self._conn.execute(
                "INSERT INTO attempts (script_id, element_id, at, mode, score, helped, gave_up) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, line_id, stamp, mode, worth, int(helped), int(gave_up)),
            )
            if s["mode"] == "drill":
                ids = {e["id"] for e in self._elements(sid)}
                live = [q for q in s["drill"] if q["id"] in ids]
                head, queue = live[0], live[1:]
                if worth < coach.DRILL_DONE and head["tries"] < 2:
                    queue.append({"id": line_id, "tries": head["tries"] + 1})
                self._save_run(sid, drill=queue)
            else:
                self._save_run(sid, position=self._after(sid, line_id, s["settings"]["loop"]))
            self._conn.commit()
            s = self._script(owner, sid)
            return {
                "graded": {"line_id": line_id, "character": line["character"], "note": line["note"],
                           **graded.as_dict()},  # fmt: skip
                "line": {"id": line_id, "score": score, "level": coach.level_for(score), "label":
                         coach.LEVELS[coach.level_for(score)]},  # fmt: skip
                "view": self._view(s),
            }

    def _after(self, sid: int, eid: int, loop: dict[str, int] | None) -> int:
        """The position after an element: the next one's id, or the end."""
        els = self._elements(sid)
        ids = [e["id"] for e in els]
        k = ids.index(eid) + 1
        if loop and loop["to"] in ids and k > ids.index(loop["to"]):
            return loop["from"]
        return ids[k] if k < len(ids) else END

    def jump(self, owner: str, sid: int, to: object) -> dict[str, Any]:
        """`top`, `back` (to the cue before your last line), or an element's
        id: from there, or from the cue before it when it's yours."""
        with self._lock:
            s = self._script(owner, sid)
            els = self._elements(sid)
            mine = {name_key(c) for c in s["mine"]}
            loop = s["settings"]["loop"]
            if to == "top":
                position = loop["from"] if loop else TOP
            elif to == "back":
                current = self._view(s)
                here = current["prompt"]["pos"] if current["prompt"] else len(els)
                mine_before = [e for e in els[:here] if self._is_mine(e, mine)]
                position = TOP
                if mine_before:
                    target = mine_before[-1]
                    position = self._cue_start(els, target["pos"], mine)
            elif isinstance(to, int) and not isinstance(to, bool):
                e = next((x for x in els if x["id"] == to), None)
                if e is None:
                    raise NotFound("No such line")
                position = self._cue_start(els, e["pos"], mine) if self._is_mine(e, mine) else e["id"]
            else:
                raise ValueError("Jump to top, back, or a line")
            self._save_run(sid, position=position, mode="run", drill=[])
            self._conn.commit()
            return self._view(self._script(owner, sid))

    @staticmethod
    def _cue_start(els: list[dict[str, Any]], pos: int, mine: set[str]) -> int:
        """Where to start so a line of yours comes with what leads into it."""
        k = pos - 1
        while k >= 0:
            e = els[k]
            if e["kind"] == "line":
                if name_key(e["character"] or "") in mine:
                    return els[k + 1]["id"]
                return e["id"]
            k -= 1
        return TOP

    def drill(self, owner: str, sid: int, count: int = 5) -> dict[str, Any]:
        """The person's weakest lines, each after its cue, again if it's still shaky."""
        count = max(1, min(int(count), 20))
        with self._lock:
            s = self._script(owner, sid)
            els = self._elements(sid)
            mastery = self._mastery(sid)
            mine = {name_key(c) for c in s["mine"]}
            if not mine:
                raise ValueError("Choose your character first")
            loop = s["settings"]["loop"]
            ids = [e["id"] for e in els]
            lo, hi = (ids.index(loop["from"]), ids.index(loop["to"])) if loop else (0, len(els) - 1)
            candidates = [e for e in els[lo : hi + 1] if self._is_mine(e, mine)]
            if not candidates:
                raise ValueError("There are no lines of yours to drill here")

            def weakness(e: dict[str, Any]) -> tuple[float, int]:
                m = mastery.get(e["id"])
                return (coach.effective(m["score"], m["last_seen"]) if m else 0.0, e["pos"])

            chosen = sorted(candidates, key=weakness)[:count]
            chosen.sort(key=lambda e: e["pos"])
            self._save_run(sid, mode="drill", drill=[{"id": e["id"], "tries": 0} for e in chosen])
            self._conn.commit()
            return self._view(self._script(owner, sid))

    def stop_drill(self, owner: str, sid: int) -> dict[str, Any]:
        with self._lock:
            self._script(owner, sid)
            self._save_run(sid, mode="run", drill=[])
            self._conn.commit()
            return self._view(self._script(owner, sid))

    def progress(self, owner: str, sid: int, days: int = 14) -> dict[str, Any]:
        with self._lock:
            s = self._script(owner, sid)
            els = self._elements(sid)
            mastery = self._mastery(sid)
            mine = {name_key(c) for c in s["mine"]}
            lines = [{"id": e["id"], "pos": e["pos"], "text": e["text"], **self._line_state(e, mastery, s)}
                     for e in els if self._is_mine(e, mine)]  # fmt: skip
            since = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")
            rows = self._conn.execute(
                "SELECT substr(at, 1, 10) AS day, count(*) AS n, avg(score) AS accuracy, sum(gave_up) AS lines_called "
                "FROM attempts WHERE script_id = ? AND at >= ? GROUP BY day ORDER BY day",
                (sid, since),
            ).fetchall()
            weakest = sorted((x for x in lines if x["attempts"]), key=lambda x: (x["score"], x["pos"]))[:5]
            return {
                "script": sid,
                "mastery": self._overall(s, els, mastery),
                "label": coach.LEVELS[coach.level_for(self._overall(s, els, mastery))],
                "lines": lines,
                "weakest": weakest,
                "days": [{"day": r["day"], "attempts": r["n"], "accuracy": round(r["accuracy"] or 0, 3),
                          "lines_called": r["lines_called"] or 0} for r in rows],  # fmt: skip
            }

    def find(self, owner: str, sid: int, quote: str) -> dict[str, Any] | None:
        """The element that best matches some words from it."""
        want = [t.norm for t in tokens(quote)]
        if not want:
            return None
        with self._lock:
            self._script(owner, sid)
            best, best_score = None, 0.0
            for e in self._elements(sid):
                have = [t.norm for t in tokens(e["text"])]
                if not have:
                    continue
                joined, needle = " ".join(have), " ".join(want)
                if needle in joined:
                    score = 1.0 + len(want) / max(len(have), 1)
                else:
                    hits = sum(1 for w in want if w in have)
                    score = hits / len(want)
                if score > best_score:
                    best, best_score = e, score
            return self._public(best) if best is not None and best_score >= 0.6 else None

    def read(self, owner: str, sid: int, start: int = 0, count: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            self._script(owner, sid)
            els = self._elements(sid)
            return [self._public(e) for e in els[max(0, start) : max(0, start) + max(1, min(count, 60))]]
