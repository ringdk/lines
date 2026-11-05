"""How well a line is known and how hard to make it (coach.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lines import coach

LINE = "He sounded perfectly alright on the phone."
VOCAB = coach.vocabulary([LINE, "You're not the least bit concerned.", "Perfect. Places, please. Phones away."])


def test_decoys_are_never_the_right_word_and_dont_reshuffle():
    first = coach.decoys(LINE, VOCAB, seed="7:0")
    assert len(first) == 7
    for word, options in zip(["he", "sounded", "perfectly", "alright", "on", "the", "phone"], first, strict=True):
        assert len(options["near"]) == 3 and len(options["far"]) == 3
        assert word not in [o.lower() for o in options["near"] + options["far"]]
    assert coach.decoys(LINE, VOCAB, seed="7:0") == first
    assert coach.decoys(LINE, VOCAB, seed="7:1") != first


def test_near_decoys_look_like_the_word():
    options = coach.decoys(LINE, VOCAB, seed="1")[6]  # "phone"
    assert all(o.lower().startswith("p") for o in options["near"])
    assert any(not o.lower().startswith("p") for o in options["far"])


def test_decoys_take_the_words_case():
    assert all(o[0].isupper() for o in coach.decoys(LINE, VOCAB, seed="1")[0]["near"])


def test_help_counts_for_less_at_an_easy_level():
    alone = coach.result(1.0, helped=0, words=10, level=1, letters=False)
    easy = coach.result(1.0, helped=10, words=10, level=1, letters=False)
    hard = coach.result(1.0, helped=10, words=10, level=5, letters=False)
    assert alone == 1.0 and easy < hard < alone
    assert coach.result(1.0, helped=0, words=10, level=3, letters=True) < 1.0


def test_a_score_moves_toward_each_attempt_and_fades_slowly():
    score = coach.updated(None, 1.0)
    assert 0 < score < 1
    better = coach.updated(score, 1.0)
    assert better > score
    assert coach.updated(better, 0.0) < better
    week_ago = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    assert 0.8 < coach.effective(1.0, week_ago) < 0.9


def test_levels_follow_the_score():
    assert [coach.level_for(s) for s in (0.0, 0.35, 0.55, 0.75, 0.9)] == [1, 2, 3, 4, 5]
    assert set(coach.LEVELS) == {1, 2, 3, 4, 5}


def test_a_name_keeps_its_capital_as_a_decoy():
    lines = ["I know, Eavanna.", "Eavanna rings him.", "Tell him, David."]
    proper = coach.proper_nouns(lines)
    assert proper == {"eavanna", "david"}
    options = coach.decoys("tell him now", {"eavanna": 3, "david": 2, "talk": 1}, seed="x", proper=proper)
    assert all(o[0].isupper() for o in options[0]["near"] + options[0]["far"] if o.lower() in proper)
