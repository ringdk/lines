"""A rehearsal through the page's API: cues up to your line, an attempt graded
and the run moving on, jumping about, looping, drilling, and the review
page's edits."""

from __future__ import annotations

from tests.conftest import signed
from tests.scene import SCENE


def get(client, path):
    r = client.get(path, headers=signed(path))
    return r


def post(client, path, body=None):
    return client.post(path, json=body or {}, headers=signed(path, method="POST"))


def make(client, mine=("Tom",)):
    script = post(client, "/ui/api/scripts/text", {"title": "Late", "text": SCENE}).json()
    if mine is not None:
        script = post(client, f"/ui/api/scripts/{script['id']}", {"mine": list(mine)}).json()
    return script


def lines_of(view):
    return [(c.get("character"), c.get("text")) for c in view["cues"]]


def test_choose_a_character_first(client):
    script = make(client, mine=None)
    assert script["characters"] == ["Maeve", "Tom"]
    view = get(client, f"/ui/api/scripts/{script['id']}/run").json()
    assert view["needs_character"] and view["prompt"] is None
    assert post(client, f"/ui/api/scripts/{script['id']}", {"mine": ["Bob"]}).status_code == 400


def test_a_run_gives_your_cue_then_waits_for_your_line(client):
    sid = make(client)["id"]
    view = get(client, f"/ui/api/scripts/{sid}/run").json()
    assert lines_of(view) == [("Maeve", "You're late again.")]
    prompt = view["prompt"]
    assert prompt["character"] == "Tom" and prompt["words"][:3] == ["The", "bus", "didn't"]
    assert len(prompt["decoys"]) == len(prompt["words"]) and prompt["level"] == 1
    # Looking again doesn't move anything.
    assert get(client, f"/ui/api/scripts/{sid}/run").json()["prompt"]["id"] == prompt["id"]


def test_an_attempt_is_graded_and_the_run_moves_on(client):
    sid = make(client)["id"]
    prompt = get(client, f"/ui/api/scripts/{sid}/run").json()["prompt"]
    r = post(client, f"/ui/api/scripts/{sid}/run/attempt", {"line_id": prompt["id"], "text": "The bus didnt"})
    assert r.status_code == 200, r.text
    out = r.json()
    words = [(w["text"], w["status"]) for w in out["graded"]["words"]]
    assert words[:4] == [("The", "ok"), ("bus", "ok"), ("didn't", "ok"), ("come", "missed")]
    assert 0 < out["line"]["score"] < 1
    view = out["view"]
    assert lines_of(view) == [(None, "(She folds her arms.)"), ("Maeve", "Twenty minutes. That's what you said last week.")]
    assert view["prompt"]["interrupted"] is True  # "It's true this time—"
    # The same line again is out of date.
    again = post(client, f"/ui/api/scripts/{sid}/run/attempt", {"line_id": prompt["id"], "text": "x"})
    assert again.status_code == 409


def test_calling_for_the_line_shows_it_all(client):
    sid = make(client)["id"]
    prompt = get(client, f"/ui/api/scripts/{sid}/run").json()["prompt"]
    out = post(client, f"/ui/api/scripts/{sid}/run/attempt",
               {"line_id": prompt["id"], "text": "", "gave_up": True}).json()  # fmt: skip
    assert {w["status"] for w in out["graded"]["words"]} == {"missed"}
    assert out["line"]["score"] == 0


def test_to_the_end_and_back_to_the_top(client):
    sid = make(client)["id"]
    for _ in range(3):
        view = get(client, f"/ui/api/scripts/{sid}/run").json()
        line = " ".join(view["prompt"]["words"])
        view = post(client, f"/ui/api/scripts/{sid}/run/attempt", {"line_id": view["prompt"]["id"], "text": line}).json()
    assert view["view"]["end"] and lines_of(view["view"]) == [("Maeve", "You always do.")]
    top = post(client, f"/ui/api/scripts/{sid}/run/jump", {"to": "top"}).json()
    assert lines_of(top) == [("Maeve", "You're late again.")]


def test_back_replays_the_last_exchange(client):
    sid = make(client)["id"]
    first = get(client, f"/ui/api/scripts/{sid}/run").json()["prompt"]
    post(client, f"/ui/api/scripts/{sid}/run/attempt", {"line_id": first["id"], "text": "The bus"})
    back = post(client, f"/ui/api/scripts/{sid}/run/jump", {"to": "back"}).json()
    assert back["prompt"]["id"] == first["id"] and lines_of(back) == [("Maeve", "You're late again.")]


def test_from_any_line_yours_start_from_their_cue(client):
    script = make(client)
    sid, els = script["id"], script["elements"]
    tea = next(e for e in els if e["text"].startswith("I'll make"))
    view = post(client, f"/ui/api/scripts/{sid}/run/jump", {"to": tea["id"]}).json()
    assert view["prompt"]["id"] == tea["id"]
    assert lines_of(view) == [("Maeve", "Don't. I can't do this tonight."), (None, "Tom sits.")]
    assert post(client, f"/ui/api/scripts/{sid}/run/jump", {"to": 999999}).status_code == 404


def test_a_loop_goes_round(client):
    script = make(client)
    sid, els = script["id"], script["elements"]
    start = next(e for e in els if e["text"].startswith("Twenty"))
    end = next(e for e in els if e["text"].startswith("Don't"))
    post(client, f"/ui/api/scripts/{sid}", {"settings": {"loop": {"from": start["id"], "to": end["id"]}}})
    view = post(client, f"/ui/api/scripts/{sid}/run/jump", {"to": "top"}).json()
    assert view["prompt"]["words"][0] == "It's"
    view = post(client, f"/ui/api/scripts/{sid}/run/attempt",
                {"line_id": view["prompt"]["id"], "text": "it's true this time"}).json()["view"]  # fmt: skip
    # Maeve's "Don't", then round again to her "Twenty minutes", then you.
    assert [c.get("text") for c in view["cues"]][0].startswith("Don't")
    assert {"kind": "loop"} in view["cues"] and view["prompt"]["words"][0] == "It's"


def test_a_drill_takes_the_weakest_and_repeats_the_shaky(client):
    sid = make(client)["id"]
    view = post(client, f"/ui/api/scripts/{sid}/run/drill", {"count": 2}).json()
    assert view["mode"] == "drill" and view["remaining"] == 2
    assert lines_of(view)[-1][0] == "Maeve"  # its cue
    first = view["prompt"]["id"]
    view = post(client, f"/ui/api/scripts/{sid}/run/attempt", {"line_id": first, "text": "no idea"}).json()["view"]
    assert view["remaining"] == 2  # the shaky one goes round again
    view = post(client, f"/ui/api/scripts/{sid}/run/stop-drill").json()
    assert view["mode"] == "run"


def test_settings_are_checked(client):
    sid = make(client)["id"]
    ok = post(client, f"/ui/api/scripts/{sid}", {"settings": {"suggestions": False, "level": 4, "input": "letters"}})
    assert ok.json()["settings"]["level"] == 4
    for bad in ({"level": 9}, {"input": "voice"}, {"suggestions": "yes"}, {"colour": "red"}, {"loop": {"from": 1}}):
        assert post(client, f"/ui/api/scripts/{sid}", {"settings": bad}).status_code == 400, bad
    view = get(client, f"/ui/api/scripts/{sid}/run").json()
    assert view["prompt"]["level"] == 4


def test_the_review_page_fixes_who_says_what(client):
    script = make(client)
    sid = script["id"]
    sits = next(e for e in script["elements"] if e["text"] == "Tom sits.")
    path = f"/ui/api/scripts/{sid}/elements/{sits['id']}"
    edited = post(client, path, {"action": "edit", "kind": "line", "character": "Maeve", "text": "Sit."}).json()
    assert any(e["text"] == "Sit." and e["character"] == "Maeve" for e in edited["elements"])
    assert post(client, path, {"action": "edit", "kind": "line", "character": ""}).status_code == 400

    first = edited["elements"][0]
    split = post(client, f"/ui/api/scripts/{sid}/elements/{first['id']}", {"action": "split", "at": 7}).json()
    assert [e["text"] for e in split["elements"][:2]] == ["You're", "late again."]
    merged = post(client, f"/ui/api/scripts/{sid}/elements/{first['id']}", {"action": "merge"}).json()
    assert merged["elements"][0]["text"] == "You're late again."
    inserted = post(client, f"/ui/api/scripts/{sid}/elements/{first['id']}",
                    {"action": "insert", "kind": "direction", "text": "A pause."}).json()  # fmt: skip
    assert inserted["elements"][1]["text"] == "A pause."
    gone = post(client, f"/ui/api/scripts/{sid}/elements/{inserted['elements'][1]['id']}", {"action": "delete"}).json()
    assert len(gone["elements"]) == len(merged["elements"])
    assert [e["pos"] for e in gone["elements"]] == list(range(len(gone["elements"])))


def test_renaming_a_character_keeps_who_you_play(client):
    sid = make(client)["id"]
    renamed = post(client, f"/ui/api/scripts/{sid}/rename", {"from": "TOM", "to": "Thomas"}).json()
    assert renamed["characters"] == ["Maeve", "Thomas"] and renamed["mine"] == ["Thomas"]


def test_progress_counts_today(client):
    sid = make(client)["id"]
    prompt = get(client, f"/ui/api/scripts/{sid}/run").json()["prompt"]
    post(client, f"/ui/api/scripts/{sid}/run/attempt", {"line_id": prompt["id"], "text": " ".join(prompt["words"])})
    progress = get(client, f"/ui/api/scripts/{sid}/progress").json()
    assert progress["days"][-1]["attempts"] == 1 and progress["mastery"] > 0
    assert len(progress["lines"]) == 3 and progress["weakest"][0]["id"] == prompt["id"]
