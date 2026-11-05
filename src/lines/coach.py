"""How well the person knows each line, how hard to make it, and the
wrong answers the suggestion chips offer beside the right one.

A line's score runs 0..1 and moves toward each attempt's result, so one bad
run doesn't undo a week. Help is discounted (chips count for less at an easy
level than at a hard one; first letters a little), and a line not seen for a
while fades slowly, so tomorrow starts where today left off, a bit softer.
The level (1 to 5) follows the score unless the person pins one.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterable
from datetime import UTC, datetime

from lines.grade import WORD, tokens

LEVELS = {
    1: "Just starting",
    2: "Getting familiar",
    3: "Getting there",
    4: "Nearly off book",
    5: "Off book",
}
LEARN_RATE = 0.45
DAILY_FADE = 0.98
DRILL_DONE = 0.8

# For a script too small to have its own decoys.
_COMMON = (
    "about", "after", "again", "always", "another", "around", "away", "back", "because", "been", "before", "being",
    "between", "both", "came", "come", "could", "day", "did", "does", "done", "down", "each", "even", "every",
    "first", "from", "give", "going", "good", "great", "have", "here", "home", "just", "know", "last", "left",
    "life", "like", "little", "long", "look", "made", "make", "many", "might", "more", "most", "much", "must",
    "need", "never", "next", "night", "nothing", "now", "only", "other", "over", "people", "place", "right", "said",
    "same", "should", "since", "something", "still", "such", "take", "tell", "than", "that", "their", "them", "then",
    "there", "these", "thing", "think", "those", "though", "thought", "three", "through", "time", "today", "told",
    "under", "until", "very", "want", "well", "went", "were", "what", "when", "where", "which", "while", "white",
    "who", "whole", "why", "will", "with", "without", "word", "work", "world", "would", "year", "young", "your",
)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def result(score: float, *, helped: int, words: int, level: int, letters: bool) -> float:
    """An attempt's worth, 0..1: its words, less what the chips gave."""
    value = score
    if words and helped:
        # Chips are worth 40% of a word at level 1, 80% at level 5.
        share = min(1.0, helped / words)
        value *= 1 - share * (0.6 - 0.1 * (level - 1))
    if letters:
        value *= 0.85
    return max(0.0, min(1.0, value))


def updated(score: float | None, attempt: float) -> float:
    if score is None:
        return round(attempt * 0.8, 4)
    return round(score + LEARN_RATE * (attempt - score), 4)


def effective(score: float, last_seen: str, at: datetime | None = None) -> float:
    try:
        seen = datetime.fromisoformat(last_seen)
    except ValueError:
        return score
    days = max(0.0, ((at or datetime.now(UTC)) - seen).total_seconds() / 86400)
    return score * DAILY_FADE**days


def level_for(score: float) -> int:
    for level, floor in ((5, 0.85), (4, 0.7), (3, 0.5), (2, 0.3)):
        if score >= floor:
            return level
    return 1


def decoys(
    line: str, vocabulary: dict[str, int], seed: str, proper: set[str] | None = None
) -> list[dict[str, list[str]]]:
    """For each word of the line: `near`, three wrong words that look like
    it (same first letter, a similar length), and `far`, three that don't.
    The same seed gives the same choices, so a page reload doesn't reshuffle."""
    words = tokens(line)
    pool = [w for w in vocabulary if len(w) > 1] or list(_COMMON)
    if len(pool) < 12:
        pool = list(dict.fromkeys([*pool, *_COMMON]))
    rng = random.Random(hashlib.sha256(seed.encode()).hexdigest())
    out = []
    for word in words:
        right = word.norm
        others = [w for w in pool if w.replace("'", "") != word.bare]
        near = [w for w in others if w[0] == right[0] and abs(len(w) - len(right)) <= 2]
        near.sort(key=lambda w: (abs(len(w) - len(right)), -vocabulary.get(w, 0), w))
        near = near[:8]
        rng.shuffle(near)
        far = [w for w in others if w[0] != right[0]]
        rng.shuffle(far)
        chosen_near = near[:3]
        if len(chosen_near) < 3:
            chosen_near += [w for w in far if w not in chosen_near][: 3 - len(chosen_near)]
        chosen_far = [w for w in far if w not in chosen_near][:3]
        out.append(
            {
                "near": [_like(word.text, w, proper) for w in chosen_near],
                "far": [_like(word.text, w, proper) for w in chosen_far],
            }
        )
    return out


def _like(model: str, word: str, proper: set[str] | None = None) -> str:
    """A decoy in the right word's case, so the case doesn't give it away; a
    name keeps its capital."""
    if model.isupper() and len(model) > 1:
        return word.upper()
    if model[:1].isupper() or (proper and word in proper):
        return word[:1].upper() + word[1:]
    return word


def proper_nouns(lines: Iterable[str]) -> set[str]:
    """Words written with a capital in the middle of a sentence: names."""
    found: set[str] = set()
    for line in lines:
        end = 0
        for i, m in enumerate(WORD.finditer(line)):
            before = line[end : m.start()]
            end = m.end()
            text = m.group(0)
            if i and text[:1].isupper() and not any(c in before for c in ".!?:") and text.lower() != "i":
                found.add(text.replace("’", "'").lower())
    return found


def vocabulary(lines: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in lines:
        for t in tokens(line):
            counts[t.norm] = counts.get(t.norm, 0) + 1
    return counts
