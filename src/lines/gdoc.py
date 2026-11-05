"""A Google Doc shared with "anyone with the link", fetched as a PDF.

Only the document's id is taken from what the person pastes; the address
fetched is built here, on Google's host, so a link can't point Lines anywhere
else. Redirects are followed only to Google's own document hosts, over
https. A doc that isn't shared that way sends Google's sign-in page, which is
refused with a plain explanation.
"""

from __future__ import annotations

import re

import httpx

MAX_BYTES = 15 * 1024 * 1024
TIMEOUT = 20.0
_DOC_URL = re.compile(
    r"^(?:https?://)?docs\.google\.com/document/(?:u/\d+/)?d/(?P<id>[A-Za-z0-9_-]{20,128})(?:[/?#].*)?$"
)


class DocError(ValueError):
    pass


def doc_id(url: str) -> str:
    m = _DOC_URL.match(url.strip())
    if not m:
        raise DocError("That isn't a Google Docs link (docs.google.com/document/d/…)")
    return m["id"]


def _allowed(url: httpx.URL) -> bool:
    host = url.host or ""
    return url.scheme == "https" and (host == "docs.google.com" or host.endswith(".googleusercontent.com"))


def fetch_pdf(url: str, *, transport: httpx.BaseTransport | None = None) -> bytes:
    target = httpx.URL(f"https://docs.google.com/document/d/{doc_id(url)}/export?format=pdf")
    not_shared = DocError("I can't open that doc. In Google Docs, Share → General access → Anyone with the link")
    with httpx.Client(follow_redirects=False, timeout=TIMEOUT, transport=transport) as client:
        for _ in range(6):
            with client.stream("GET", target) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    target = target.join(location)
                    if not _allowed(target):
                        raise not_shared
                    continue
                if response.status_code in (401, 403, 404):
                    raise not_shared
                if response.status_code != 200:
                    raise DocError(f"Google Docs answered {response.status_code}; try again in a moment")
                if not response.headers.get("content-type", "").startswith("application/pdf"):
                    raise not_shared
                body = bytearray()
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise DocError("That doc is too big to rehearse from; split it up")
                return bytes(body)
    raise DocError("Google Docs kept redirecting; try again in a moment")
