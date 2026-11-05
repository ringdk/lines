"""Reading a script into who says what (parse.py), from pasted text and from a
PDF laid out like a play."""

from __future__ import annotations

import pytest

from lines.parse import ParseError, interrupted, parse_pdf, parse_text

from tests.scene import SCENE, scene_pdf


def said(elements):
    return [(e.kind, e.character, e.text) for e in elements]


def test_a_pasted_play():
    els = parse_text(SCENE)
    assert said(els) == [
        ("line", "Maeve", "You're late again."),
        ("line", "Tom", "The bus didn't come. I waited twenty minutes."),
        ("direction", None, "(She folds her arms.)"),
        ("line", "Maeve", "Twenty minutes. That's what you said last week."),
        ("line", "Tom", "It's true this time—"),
        ("line", "Maeve", "Don't. I can't do this tonight."),
        ("direction", None, "Tom sits."),
        ("line", "Tom", "I'll make the tea, then."),
        ("line", "Maeve", "You always do."),
    ]
    assert els[-1].note == "(quietly)"


def test_a_pdf_play_with_italic_directions_and_wrapped_lines():
    els = parse_pdf(scene_pdf())
    assert said(els) == [
        ("line", "Maeve", "You're late again."),
        ("line", "Tom", "The bus didn't come. I waited twenty minutes, and then I walked the whole way in the rain."),
        ("direction", None, "She folds her arms. A beat."),
        # After a direction, words with no name on them are whoever spoke last.
        ("line", "Tom", "Look at me, I'm soaked through."),
        ("line", "Maeve", "Twenty minutes."),
        ("line", "Tom", "It's true this time --"),
        ("line", "Maeve", "Don't."),
    ]
    assert els[-1].note == "(quietly)"
    assert [e.page for e in els][-2:] == [2, 2]


def test_a_screenplay():
    els = parse_text("INT. KITCHEN - NIGHT\n\nMAEVE\nYou're late.\n\nTOM (V.O.)\nI know.\nI'm sorry.\n")
    assert said(els) == [
        ("heading", None, "INT. KITCHEN - NIGHT"),
        ("line", "Maeve", "You're late."),
        ("line", "Tom", "I know. I'm sorry."),
    ]


def test_a_title_in_capitals_isnt_a_speaker_in_a_play():
    els = parse_text("THE KITCHEN\n" + SCENE)
    assert els[0].kind == "direction" and els[0].text == "THE KITCHEN"
    assert els[1].character == "Maeve"


def test_labels_that_arent_people():
    els = parse_text("Setting: a kitchen at night.\nMAEVE: Hello.\nTOM: Hi.\nMAEVE: Bye.\n")
    assert els[0].kind == "direction" and "Setting" in els[0].text
    assert {e.character for e in els if e.kind == "line"} == {"Maeve", "Tom"}


def test_nothing_to_rehearse_is_refused():
    with pytest.raises(ParseError):
        parse_text("Just some words.\nNo one speaks here.")
    with pytest.raises(ParseError):
        parse_pdf(b"%PDF-1.4 not really")


def test_a_cut_off_line():
    assert interrupted("It's true this time—") and interrupted("Wait --") and interrupted("If you'd -")
    assert not interrupted("Fine.") and not interrupted("well-known")
