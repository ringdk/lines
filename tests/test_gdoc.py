"""A Google Doc by link (gdoc.py): only the id is taken from the link, and
nothing is fetched from, or followed to, anywhere but Google's document
hosts."""

from __future__ import annotations

import httpx
import pytest

from lines.gdoc import MAX_BYTES, DocError, doc_id, fetch_pdf

ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-"
LINK = f"https://docs.google.com/document/d/{ID}/edit?usp=sharing"


def test_the_id_from_a_link():
    assert doc_id(LINK) == ID
    assert doc_id(f"docs.google.com/document/u/0/d/{ID}/") == ID
    for bad in (
        f"https://docs.google.com.evil.example/document/d/{ID}/edit",
        f"https://evil.example/?docs.google.com/document/d/{ID}",
        f"https://docs.google.com/spreadsheets/d/{ID}/edit",
        "https://docs.google.com/document/d/short/edit",
        f"javascript:alert(1)//docs.google.com/document/d/{ID}",
    ):
        with pytest.raises(DocError):
            doc_id(bad)


def transport(handler):
    seen: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return handler(request)

    return httpx.MockTransport(record), seen


def test_it_fetches_the_export_built_from_the_id_and_follows_googles_redirect():
    def handler(request):
        if request.url.host == "docs.google.com":
            return httpx.Response(307, headers={"location": "https://doc-0s-1c-docs.googleusercontent.com/export/x"})
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.7 fine")

    mock, seen = transport(handler)
    assert fetch_pdf(LINK, transport=mock) == b"%PDF-1.7 fine"
    assert seen[0] == f"https://docs.google.com/document/d/{ID}/export?format=pdf"


def test_a_doc_that_isnt_shared_says_how_to_share_it():
    def to_sign_in(request):
        return httpx.Response(302, headers={"location": "https://accounts.google.com/ServiceLogin?continue=x"})

    mock, seen = transport(to_sign_in)
    with pytest.raises(DocError, match="Anyone with the link"):
        fetch_pdf(LINK, transport=mock)
    assert len(seen) == 1  # the sign-in page itself is never fetched


@pytest.mark.parametrize(
    "location",
    ["http://doc-0s-docs.googleusercontent.com/x", "https://169.254.169.254/latest", "https://evil.example/x",
     "https://googleusercontent.com.evil.example/x"],
)  # fmt: skip
def test_redirects_go_only_to_googles_document_hosts_over_https(location):
    mock, seen = transport(lambda r: httpx.Response(302, headers={"location": location}))
    with pytest.raises(DocError):
        fetch_pdf(LINK, transport=mock)
    assert len(seen) == 1


def test_html_or_too_much_is_refused():
    mock, _ = transport(lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>"))
    with pytest.raises(DocError):
        fetch_pdf(LINK, transport=mock)
    huge = b"%PDF-" + b"0" * (MAX_BYTES + 10)
    mock, _ = transport(lambda r: httpx.Response(200, headers={"content-type": "application/pdf"}, content=huge))
    with pytest.raises(DocError, match="too big"):
        fetch_pdf(LINK, transport=mock)
