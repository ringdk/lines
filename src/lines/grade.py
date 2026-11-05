"""How close an attempt at a line came, word by word.

Each word of the line is `ok`, `minor` (the same sound or nearly: "I'm"
for "I am", "its" for "it's", a one-letter slip in a long word), `wrong`
(a different word, or one skipped), or `missed`: past the point the person
got to, which the next message shows them. Capitals and punctuation never
count; an apostrophe left out counts only where it changes the word
("well"/"we'll").

Typed words are lined up with the line's by edit distance, so a skipped
word, an extra one or a swapped one is found where it happened.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

WORD = re.compile(r"[A-Za-z0-9À-ɏ]+(?:['’][A-Za-zÀ-ɏ]+)*")

# Contractions, as the words they stand for. Each part is the set of words it
# may be ("'s" is "is" or "has").
_SUFFIXES: list[tuple[str, tuple[frozenset[str], ...]]] = [
    ("n't", (frozenset({"not"}),)),
    ("'re", (frozenset({"are"}),)),
    ("'ve", (frozenset({"have"}),)),
    ("'ll", (frozenset({"will", "shall"}),)),
    ("'d", (frozenset({"would", "had"}),)),
    ("'m", (frozenset({"am"}),)),
]
_WHOLE: dict[str, tuple[frozenset[str], ...]] = {
    "won't": (frozenset({"will"}), frozenset({"not"})),
    "can't": (frozenset({"can"}), frozenset({"not"})),
    "shan't": (frozenset({"shall"}), frozenset({"not"})),
    "ain't": (frozenset({"is", "am", "are"}), frozenset({"not"})),
    "let's": (frozenset({"let"}), frozenset({"us"})),
    "'tis": (frozenset({"it"}), frozenset({"is"})),
    "y'all": (frozenset({"you"}), frozenset({"all"})),
    "gonna": (frozenset({"going"}), frozenset({"to"})),
    "wanna": (frozenset({"want"}), frozenset({"to"})),
    "gotta": (frozenset({"got"}), frozenset({"to"})),
    "gimme": (frozenset({"give"}), frozenset({"me"})),
    "lemme": (frozenset({"let"}), frozenset({"me"})),
}
_S_IS_HAS = {"it", "that", "he", "she", "what", "there", "here", "who", "where", "how", "when", "why", "everyone"}
# Without its apostrophe, a different word: flagged, not passed.
_COLLISIONS = {
    "its", "were", "well", "shell", "ill", "wed", "hell", "id", "lets", "whos", "cant", "wont", "hed", "shed",
}  # fmt: skip

MINOR_COST = 0.3


@dataclass
class Token:
    text: str  # as written
    norm: str  # lower case, straight apostrophes

    @property
    def bare(self) -> str:
        return self.norm.replace("'", "")


def tokens(text: str) -> list[Token]:
    return [Token(m.group(0), m.group(0).replace("’", "'").lower()) for m in WORD.finditer(text)]


def expand(t: Token) -> tuple[frozenset[str], ...] | None:
    """A contraction as the words it stands for, or None."""
    if t.norm in _WHOLE:
        return _WHOLE[t.norm]
    for suffix, parts in _SUFFIXES:
        if t.norm.endswith(suffix) and len(t.norm) > len(suffix):
            return (frozenset({t.norm[: -len(suffix)]}), *parts)
    if t.norm.endswith("'s") and t.norm[:-2] in _S_IS_HAS:
        return (frozenset({t.norm[:-2]}), frozenset({"is", "has"}))
    return None


def _edit1(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) == len(b):
        diffs = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diffs) == 1 or (len(diffs) == 2 and diffs[1] == diffs[0] + 1 and a[diffs[0]] == b[diffs[1]]
                                   and a[diffs[1]] == b[diffs[0]])  # fmt: skip
    short, long = (a, b) if len(a) < len(b) else (b, a)
    return any(long[:i] + long[i + 1 :] == short for i in range(len(long)))


def compare(want: Token, got: Token) -> str | None:
    """"ok", "minor" or None (a different word)."""
    if want.norm == got.norm:
        return "ok"
    if want.bare == got.bare:
        # An apostrophe left out (or put in): fine unless that's another word.
        return "minor" if (want.bare in _COLLISIONS or got.norm in _COLLISIONS) else "ok"
    if len(want.bare) >= 5 and _edit1(want.bare, got.bare):
        return "minor"
    return None


def _parts_match(parts: tuple[frozenset[str], ...], words: list[Token]) -> bool:
    return len(parts) == len(words) and all(w.norm in p or w.bare in p for p, w in zip(parts, words, strict=True))


@dataclass
class Graded:
    words: list[dict]  # {"lead", "text", "status"} for each word of the line, in order
    extra: list[dict]  # {"after", "text"}: typed words the line doesn't have
    score: float  # 0..1: ok counts 1, minor 0.6
    reached: int  # how many of the line's words the attempt got to
    complete: bool  # it got to the end
    tail: str = ""  # what follows the last word ("?", "—")

    def as_dict(self) -> dict:
        return {"words": self.words, "tail": self.tail, "extra": self.extra, "score": self.score,
                "complete": self.complete}  # fmt: skip


def _shaped(line: str, statuses: list[str]) -> tuple[list[dict], str]:
    """The line's words with what comes before each, so it reads as written."""
    words, end = [], 0
    for m, status in zip(WORD.finditer(line), statuses, strict=True):
        words.append({"lead": line[end : m.start()], "text": m.group(0), "status": status})
        end = m.end()
    return words, line[end:]


def grade(line: str, typed: str) -> Graded:
    want = tokens(line)
    got = tokens(typed)
    n, m = len(want), len(got)
    inf = float("inf")
    # cost[i][j]: the line's first i words against the first j typed.
    cost = [[inf] * (m + 1) for _ in range(n + 1)]
    step: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if cost[i][j] == inf:
                continue
            moves: list[tuple[int, int, float, tuple]] = []
            if i < n and j < m:
                status = compare(want[i], got[j])
                price = {"ok": 0.0, "minor": MINOR_COST}.get(status or "", 1.0)
                moves.append((i + 1, j + 1, price, ("pair", status or "wrong")))
            if i < n and j + 1 < m:
                parts = expand(want[i])
                if parts and _parts_match(parts, got[j : j + 2]):
                    moves.append((i + 1, j + 2, MINOR_COST, ("spelled-out",)))
            if i + 1 < n and j < m:
                parts = expand(got[j])
                if parts and _parts_match(parts, want[i : i + 2]):
                    moves.append((i + 2, j + 1, MINOR_COST * 2, ("contracted",)))
            if i < n:
                moves.append((i + 1, j, 1.0, ("skip",)))
            if j < m:
                moves.append((i, j + 1, 1.0, ("extra",)))
            for ni, nj, price, how in moves:
                if cost[i][j] + price < cost[ni][nj]:
                    cost[ni][nj] = cost[i][j] + price
                    step[ni][nj] = (i, j, how)

    # Every way to the end of what was typed, the line's words after that
    # untried: the cheapest one, counting untried words as free.
    best_i = min(range(n + 1), key=lambda i: (cost[i][m], -i))
    statuses = ["missed"] * n
    extra: list[dict] = []
    i, j = best_i, m
    while (i, j) != (0, 0):
        pi, pj, how = step[i][j]
        kind = how[0]
        if kind == "pair":
            statuses[pi] = how[1]
        elif kind == "spelled-out":
            statuses[pi] = "minor"
        elif kind == "contracted":
            statuses[pi] = statuses[pi + 1] = "minor"
        elif kind == "skip":
            statuses[pi] = "wrong"
        elif kind == "extra":
            extra.append({"after": pi - 1, "text": got[pj].text})
        i, j = pi, pj
    extra.reverse()

    # Words skipped at the very end of what was typed weren't reached.
    reached = best_i
    while reached > 0 and statuses[reached - 1] == "wrong" and _skipped_tail(step, reached, m):
        statuses[reached - 1] = "missed"
        reached -= 1
    ok = statuses.count("ok")
    minor = statuses.count("minor")
    score = (ok + 0.6 * minor) / n if n else 1.0
    words, tail = _shaped(line, statuses)
    return Graded(words, extra, round(score, 3), reached, complete=n > 0 and statuses[-1] != "missed", tail=tail)


def _skipped_tail(step: list[list[tuple | None]], i: int, m: int) -> bool:
    entry = step[i][m]
    return entry is not None and entry[2][0] == "skip"


def grade_letters(line: str, typed: str) -> Graded:
    """First-letter mode: one letter (or digit) per word, nothing else counts."""
    want = tokens(line)
    letters = [c for c in typed.lower() if c.isalnum()]
    statuses = ["missed"] * len(want)
    for k, letter in enumerate(letters[: len(want)]):
        statuses[k] = "ok" if want[k].norm[0] == letter else "wrong"
    extra = [{"after": len(want) - 1, "text": c} for c in letters[len(want) :]]
    reached = min(len(letters), len(want))
    n = len(want)
    score = statuses.count("ok") / n if n else 1.0
    words, tail = _shaped(line, statuses)
    return Graded(words, extra, round(score, 3), reached, complete=n > 0 and statuses[-1] != "missed", tail=tail)
