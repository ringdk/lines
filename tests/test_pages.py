"""The pages and their API (APPS.md rule 5): each person sees only their own
scripts, writes are POST, uploads are checked, and every page goes out under
the CSP."""

from __future__ import annotations

from fastapi.testclient import TestClient

from lines.config import Config
from lines.server import MAX_PDF_BYTES, PAGE_CSP, create_app

from tests.conftest import DAN, KATE, signed
from tests.scene import SCENE, scene_pdf

SCRIPTS = "/ui/api/scripts"


def add(client, email: str = DAN):
    path = f"{SCRIPTS}/text"
    return client.post(path, json={"title": "Late", "text": SCENE}, headers=signed(path, email=email, method="POST"))


def test_scripts_are_their_owners(client):
    mine = add(client).json()
    add(client, email=KATE)
    listed = client.get(SCRIPTS, headers=signed(SCRIPTS)).json()
    assert [s["id"] for s in listed] == [mine["id"]]
    theirs = f"{SCRIPTS}/{mine['id']}"
    assert client.get(theirs, headers=signed(theirs, email=KATE)).status_code == 404
    run = f"{theirs}/run"
    assert client.get(run, headers=signed(run, email=KATE)).status_code == 404
    rename = f"{theirs}/rename"
    r = client.post(rename, json={"from": "Tom", "to": "X"}, headers=signed(rename, email=KATE, method="POST"))
    assert r.status_code == 404


def test_only_the_owner_deletes_a_script(client):
    script = add(client).json()
    path = f"{SCRIPTS}/{script['id']}/delete"
    assert client.post(path, headers=signed(path, email=KATE, method="POST")).status_code == 404
    assert client.post(path, headers=signed(path, method="POST")).status_code == 200
    assert client.get(SCRIPTS, headers=signed(SCRIPTS)).json() == []


def test_a_get_never_changes_anything(client):
    script = add(client).json()
    path = f"{SCRIPTS}/{script['id']}/delete"
    assert client.get(path, headers=signed(path)).status_code in (404, 405)
    jump = f"{SCRIPTS}/{script['id']}/run/jump"
    assert client.get(jump, headers=signed(jump)).status_code in (404, 405)
    assert len(client.get(SCRIPTS, headers=signed(SCRIPTS)).json()) == 1


def test_a_pdf_upload(client):
    path = f"{SCRIPTS}/pdf?title=From%20a%20PDF"
    headers = {**signed(path, method="POST"), "Content-Type": "application/pdf"}
    r = client.post(path, content=scene_pdf(), headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "From a PDF" and r.json()["characters"] == ["Maeve", "Tom"]


def test_an_upload_that_isnt_a_pdf_or_is_too_big_is_refused(client):
    path = f"{SCRIPTS}/pdf"
    assert client.post(path, content=b"<html>hi</html>", headers=signed(path, method="POST")).status_code == 400
    big = b"%PDF-" + b"0" * (MAX_PDF_BYTES + 1)
    assert client.post(path, content=big, headers=signed(path, method="POST")).status_code == 413


def test_text_with_no_lines_says_why(client):
    path = f"{SCRIPTS}/text"
    r = client.post(path, json={"text": "nobody speaks"}, headers=signed(path, method="POST"))
    assert r.status_code == 400 and "lines" in r.json()["detail"]


def test_a_link_anywhere_else_is_refused_before_anything_is_fetched(client):
    path = f"{SCRIPTS}/gdoc"
    for url in ("https://evil.example/document/d/abcdefghijklmnopqrstuvwxyz/edit", "file:///etc/passwd", ""):
        r = client.post(path, json={"url": url}, headers=signed(path, method="POST"))
        assert r.status_code == 400, url


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
            for path in ("/ui/", "/ui/anything?script=3"):
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
