"""A made-up scene for the tests, as pasted text and as a PDF laid out the way
plays usually are (names in the margin, lines beside them, directions in
italics), built here so no PDF lives in the repo."""

from __future__ import annotations

import pymupdf

SCENE = """\
MAEVE: You're late again.
TOM: The bus didn't come. I waited twenty minutes.
(She folds her arms.)
MAEVE: Twenty minutes. That's what you said last week.
TOM: It's true this time—
MAEVE: Don't. I can't do this tonight.
Tom sits.
TOM: I'll make the tea, then.
MAEVE: (quietly) You always do.
"""

# (page, x, y, text, italic): a play as a PDF, over two pages, with a page number.
ROWS = [
    (1, 72, 90, "Maeve:", False),
    (1, 150, 90, "You're late again.", False),
    (1, 72, 118, "Tom:", False),
    (1, 150, 118, "The bus didn't come. I waited twenty minutes, and then", False),
    (1, 150, 132, "I walked the whole way in the rain.", False),
    (1, 90, 160, "She folds her arms. A beat.", True),
    (1, 150, 188, "Look at me, I'm soaked through.", False),
    (1, 72, 216, "Maeve:", False),
    (1, 150, 216, "Twenty minutes.", False),
    (1, 300, 800, "1", False),
    (2, 72, 90, "Tom:", False),
    # Its standard fonts have no em dash; "--" is a cut-off too.
    (2, 150, 90, "It's true this time --", False),
    (2, 72, 118, "Maeve:", False),
    (2, 150, 118, "(quietly) Don't.", False),
    (2, 300, 800, "2", False),
]


def scene_pdf(rows: list[tuple[int, float, float, str, bool]] = ROWS) -> bytes:
    doc = pymupdf.open()
    for number in sorted({r[0] for r in rows}):
        page = doc.new_page(width=595, height=842)
        for _, x, y, text, italic in (r for r in rows if r[0] == number):
            page.insert_text((x, y), text, fontname="heit" if italic else "helv", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data
