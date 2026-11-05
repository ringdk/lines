"""How close an attempt came (grade.py): wrong words are found where they
happened, what changes the sound or the sense is flagged, and what wasn't
reached is the rest of the line, not a mistake."""

from __future__ import annotations

from lines.grade import grade, grade_letters

LINE = "I'm not going to interrogate him, if he's ignoring your calls."


def statuses(graded):
    return [(w["text"], w["status"]) for w in graded.words]


def test_word_perfect_ignores_capitals_and_punctuation():
    g = grade(LINE, "im NOT going to interrogate him if he's ignoring your calls")
    assert all(s == "ok" for _, s in statuses(g)) and g.complete and g.score == 1.0


def test_the_first_few_words_and_the_rest_is_shown():
    g = grade(LINE, "I'm not going")
    assert statuses(g)[:4] == [("I'm", "ok"), ("not", "ok"), ("going", "ok"), ("to", "missed")]
    assert {s for _, s in statuses(g)[3:]} == {"missed"}
    assert not g.complete and g.reached == 3


def test_nothing_typed_is_all_still_to_come():
    g = grade(LINE, "")
    assert {s for _, s in statuses(g)} == {"missed"} and g.score == 0.0


def test_a_wrong_word_and_a_skipped_one():
    g = grade(LINE, "I'm not going to question him, if ignoring your calls")
    s = dict(statuses(g))
    assert s["interrogate"] == "wrong"
    assert s["he's"] == "wrong"  # skipped
    assert s["calls"] == "ok" and g.complete


def test_spelling_out_a_contraction_is_minor():
    g = grade("I'm not going.", "I am not going")
    assert statuses(g) == [("I'm", "minor"), ("not", "ok"), ("going", "ok")]
    g = grade("I am not going.", "I'm not going")
    assert statuses(g)[:2] == [("I", "minor"), ("am", "minor")]
    g = grade("My dad'll let him in.", "my dad will let him in")
    assert dict(statuses(g))["dad'll"] == "minor"
    g = grade("It's late.", "it has late")
    assert statuses(g)[0] == ("It's", "minor")


def test_an_apostrophe_left_out_counts_only_when_it_changes_the_word():
    assert statuses(grade("Don't swear at me.", "dont swear at me"))[0] == ("Don't", "ok")
    assert statuses(grade("We'll see.", "well see"))[0] == ("We'll", "minor")
    assert statuses(grade("It's yours.", "its yours"))[0] == ("It's", "minor")


def test_a_slip_in_a_long_word_is_minor_a_different_word_isnt():
    assert dict(statuses(grade("You're overreacting.", "you're overracting")))["overreacting"] == "minor"
    assert dict(statuses(grade("A young fella.", "a young fellow")))["fella"] == "wrong"


def test_extra_words_are_kept_to_show():
    g = grade("Holy divine.", "oh holy divine")
    assert statuses(g) == [("Holy", "ok"), ("divine", "ok")]
    assert g.extra == [{"after": -1, "text": "oh"}]


def test_the_line_reads_as_written():
    g = grade("Well, don't.", "well")
    assert [(w["lead"], w["text"]) for w in g.words] == [("", "Well"), (", ", "don't")]
    assert g.tail == "."


def test_first_letters():
    g = grade_letters("He sounded fine, David.", "hsf")
    assert statuses(g) == [("He", "ok"), ("sounded", "ok"), ("fine", "ok"), ("David", "missed")]
    g = grade_letters("He sounded fine, David.", "h s x d")
    assert statuses(g)[2] == ("fine", "wrong") and g.complete
