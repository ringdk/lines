"""The pages and their API (APPS.md rule 5): each person sees only their own,
writes are POST, and every page goes out under the CSP."""

from __future__ import annotations

from fastapi.testclient import TestClient

from lines.config import Config
from lines.server import PAGE_CSP, create_app

from tests.conftest import DAN, KATE, signed

NOTES = "/ui/api/notes"


def add(client, text: str, email: str = DAN):
    return client.post(NOTES, json={"text": text}, headers=signed(NOTES, email=email, method="POST"))


def test_notes_are_their_owners(client):
    assert add(client, "milk").status_code == 200
    assert add(client, "bread", email=KATE).status_code == 200
    mine = client.get(NOTES, headers=signed(NOTES)).json()
    assert [n["body"] for n in mine] == ["milk"]


def test_a_note_needs_text(client):
    assert add(client, "   ").status_code == 400


def test_only_the_owner_deletes_a_note(client):
    note = add(client, "milk").json()
    path = f"{NOTES}/{note['id']}/delete"
    assert client.post(path, headers=signed(path, email=KATE, method="POST")).status_code == 404
    assert client.post(path, headers=signed(path, method="POST")).status_code == 200
    assert client.get(NOTES, headers=signed(NOTES)).json() == []


def test_a_get_never_deletes(client):
    note = add(client, "milk").json()
    path = f"{NOTES}/{note['id']}/delete"
    assert client.get(path, headers=signed(path)).status_code in (404, 405)
    assert len(client.get(NOTES, headers=signed(NOTES)).json()) == 1


def test_every_page_has_the_csp(tmp_path, monkeypatch):
    from lines import secretfile

    from tests.conftest import APP_KEY, DB_KEY

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><script type=module src=./assets/a.js></script>")
    (dist / "assets" / "a.js").write_text("console.log(1)")
    secretfile.use({secretfile.APP_KEY: APP_KEY, secretfile.DB_KEY: DB_KEY})
    try:
        config = Config(data_dir=tmp_path / "data", users=[DAN])
        with TestClient(create_app(config, frontend_dir=dist)) as c:
            for path in ("/ui/", "/ui/anything?note=3"):
                r = c.get(path, headers=signed(path))
                assert r.status_code == 200 and r.headers["content-security-policy"] == PAGE_CSP, path
            assert "script-src 'self';" in PAGE_CSP and "unsafe-inline" not in PAGE_CSP
            assert "frame-ancestors 'self'" in PAGE_CSP and "base-uri 'none'" in PAGE_CSP
            asset = c.get("/ui/assets/a.js", headers=signed("/ui/assets/a.js"))
            assert asset.status_code == 200
            outside = "/ui/../pyproject.toml"
            assert "pyproject" not in c.get(outside, headers=signed(outside)).text
    finally:
        secretfile.use({})
