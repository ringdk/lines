"""A script, read into the elements Lines rehearses: who says what, the
stage directions between, and the headings that mark a scene.

Two ways in, one set of rules. A PDF (an upload, or a Google Doc exported as
one) is read into rows with where each sits and whether it's in italics; pasted
text is read into rows by line. Then:

- `Name: what they say` (a stage play) or a name alone in capitals above
  what they say (a screenplay) starts a line.
- Italics, or a row in brackets, is a stage direction. A PDF with no
  italics at all, and pasted text, fall back to a row that opens with a
  character's name and a lowercase word ("David sits.").
- A row with neither carries on the line above it; after a direction, or
  a gap, it's a new line for whoever spoke last.
- `(pointing)` inside a line is kept beside it as a note, not as words to say.

The reader is a best guess: the person checks it on the review page before
rehearsing, and fixes who says what there.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

MAX_PDF_PAGES = 300
MAX_TEXT_CHARS = 400_000
MAX_ELEMENTS = 5000
MAX_ELEMENT_CHARS = 4000


class ParseError(ValueError):
    pass


@dataclass
class Element:
    kind: str  # "line" | "direction" | "heading"
    text: str
    character: str | None = None
    note: str | None = None
    page: int | None = None


@dataclass
class Row:
    text: str
    italic: bool = False
    gap: float = 0.0  # space above it, in line heights (a blank line in text is 1)
    page: int | None = None


@dataclass
class _Building:
    kind: str
    parts: list[str] = field(default_factory=list)
    character: str | None = None
    page: int | None = None


_NAME_WORD = r"(?:[A-Z][A-Za-z'’.\-]*|[A-Z]{2,}[0-9]?)"
_NAME = rf"{_NAME_WORD}(?:\s+{_NAME_WORD}){{0,2}}"
# `Name: words`, `NAME (aside): words`, or `Name:` alone on its row.
_LABEL = re.compile(rf"^\s*(?P<name>{_NAME})\s*(?P<paren>\([^)]{{0,40}}\))?\s*:\s*(?P<rest>.*)$")
# A screenplay's cue: the name alone, in capitals, maybe (V.O.) or (CONT'D).
_CUE = re.compile(r"^\s*(?P<name>[A-Z][A-Z'’.\-]+(?:\s+[A-Z][A-Z'’.\-]+){0,2})\s*(?:\([A-Z.'’ ]{1,12}\))?\s*$")
_HEADING = re.compile(r"^\s*(?:(?:ACT|SCENE|Act|Scene)\b|(?:INT|EXT|INT/EXT|I/E)\.)")
_BRACKETED = re.compile(r"^\s*[(\[].*[)\]]\s*$", re.S)
_EMPHASIS = re.compile(r"^\s*([*_])(?P<inner>.+)\1\s*$", re.S)
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s+)?\d{1,4}(?:\s*(?:/|of)\s*\d{1,4})?\.?\s*$", re.I)
_INLINE_NOTE = re.compile(r"\s*[(\[]([^()\[\]]{1,80})[)\]]\s*")
_DASH_END = re.compile(r"(?:—|–|--|-)\s*$")

# Labels that aren't characters.
_NOT_NAMES = {
    "note", "notes", "setting", "time", "place", "scene", "act", "characters", "cast", "page", "draft",
    "title", "author", "by", "location", "date", "written by", "copyright", "fade in", "fade out",
    "cut to", "the end", "end", "int", "ext",
}  # fmt: skip
_CUE_NOT_NAMES = _NOT_NAMES | {"continued", "beat", "pause", "silence", "blackout", "lights up", "lights down"}
_DIRECTION_LEAD = re.compile(r"^(?:Beat|A beat|Pause|A pause|Silence|Lights|Blackout|Enter|Exit|Exeunt)\b")


def interrupted(text: str) -> bool:
    """Ends on a dash: cut off, so the next speaker comes in on it."""
    return bool(_DASH_END.search(text))


def name_key(name: str) -> str:
    return " ".join(name.replace("’", "'").split()).casefold()


def display_name(name: str) -> str:
    name = " ".join(name.split()).replace("’", "'")
    return name.title() if name.isupper() else name


# ------------------------------------------------------------------ rows


def rows_from_text(text: str) -> list[Row]:
    if len(text) > MAX_TEXT_CHARS:
        raise ParseError(f"That's more than {MAX_TEXT_CHARS:,} characters; paste one scene or act at a time")
    rows: list[Row] = []
    blank = 0
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            blank += 1
            continue
        rows.append(Row(line, gap=float(min(blank, 3))))
        blank = 0
    return rows


def rows_from_pdf(data: bytes) -> tuple[list[Row], bool]:
    """The PDF's rows in reading order, and whether it uses italics at all."""
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # pymupdf raises its own types for a bad file
        raise ParseError("That doesn't open as a PDF") from exc
    try:
        if doc.needs_pass:
            raise ParseError("That PDF needs a password")
        if doc.page_count > MAX_PDF_PAGES:
            raise ParseError(f"That PDF has more than {MAX_PDF_PAGES} pages")
        pages: list[list[tuple[float, float, str, int, int, float, float]]] = []
        for page in doc:
            spans = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        text = span["text"]
                        if not text.strip():
                            continue
                        italic = bool(span["flags"] & 2) or bool(re.search(r"italic|oblique", span["font"], re.I))
                        chars = len(text.strip())
                        spans.append(
                            (span["origin"][1], span["bbox"][0], text, chars if italic else 0, chars, span["size"],
                             span["bbox"][2])  # fmt: skip
                        )
            pages.append(spans)
    finally:
        doc.close()

    rows: list[Row] = []
    any_italic = False
    for number, spans in enumerate(pages, start=1):
        spans.sort(key=lambda s: (round(s[0]), s[1]))
        grouped: list[list[tuple[float, float, str, int, int, float, float]]] = []
        for span in spans:
            # One row per baseline, give or take a few points.
            if grouped and abs(grouped[-1][0][0] - span[0]) <= 3:
                grouped[-1].append(span)
            else:
                grouped.append([span])
        previous_y: float | None = None
        sizes = sorted(s[5] for s in spans) or [12.0]
        line_height = sizes[len(sizes) // 2] * 1.2
        for group in grouped:
            group.sort(key=lambda s: s[1])
            text = ""
            for i, s in enumerate(group):
                # Pieces that touch are one run of text ("admonishment" + ".");
                # a gap between them is a space, or a tab after a name.
                if i and s[1] - group[i - 1][6] > s[5] * 0.15:
                    text += " "
                text += s[2]
            text = " ".join(text.split())
            italic_chars = sum(s[3] for s in group)
            total = sum(s[4] for s in group) or 1
            y = group[0][0]
            gap = 0.0 if previous_y is None else max(0.0, (y - previous_y) / line_height - 1.0)
            previous_y = y
            italic = italic_chars / total >= 0.6
            any_italic = any_italic or italic
            rows.append(Row(text, italic=italic, gap=round(gap, 2), page=number))
    return _without_page_furniture(rows, len(pages)), any_italic


def _without_page_furniture(rows: list[Row], page_count: int) -> list[Row]:
    """Page numbers, and a header or footer repeated on most pages."""
    repeated = Counter(r.text for r in rows)
    out = []
    for row in rows:
        if _PAGE_NUMBER.match(row.text):
            continue
        if page_count >= 3 and repeated[row.text] >= max(3, page_count // 2) and len(row.text) < 80:
            continue
        out.append(row)
    return out


# ------------------------------------------------------------------ elements


def parse_text(text: str) -> list[Element]:
    return elements_from_rows(rows_from_text(text), use_italics=False)


def parse_pdf(data: bytes) -> list[Element]:
    rows, any_italic = rows_from_pdf(data)
    return elements_from_rows(rows, use_italics=any_italic)


def _label(text: str) -> tuple[str, str, str] | None:
    """(name, aside, rest) when a row opens with a speaker's name."""
    m = _LABEL.match(text)
    if not m or name_key(m["name"]) in _NOT_NAMES:
        return None
    return m["name"], m["paren"] or "", m["rest"]


def _cue(text: str) -> str | None:
    m = _CUE.match(text)
    if not m or name_key(m["name"]) in _CUE_NOT_NAMES or _HEADING.match(text):
        return None
    return m["name"]


def elements_from_rows(rows: list[Row], *, use_italics: bool) -> list[Element]:
    out: list[Element] = []
    building: _Building | None = None
    speaker: str | None = None
    known: dict[str, str] = {}  # name key -> how it's shown
    pending_cue: str | None = None
    # A play's `Name:` labels and a screenplay's cues don't mix: with labels,
    # a name alone in capitals is a title, not someone about to speak.
    cues_count = sum(1 for r in rows if _label(r.text.strip())) < 3

    def flush() -> None:
        nonlocal building
        if building is not None and building.parts:
            out.append(_finish(building))
        building = None

    def who(name: str) -> str:
        return known.setdefault(name_key(name), display_name(name))

    def opens_with_a_name(text: str) -> bool:
        first = re.match(r"^([A-Z][A-Za-z'’]+)\s+([a-z])", text)
        return bool(first and name_key(first[1]) in known)

    for row in rows:
        text = row.text.strip()
        emphasis = _EMPHASIS.match(text)
        is_direction = (
            (use_italics and row.italic)
            or bool(_BRACKETED.match(text))
            or bool(emphasis)
            or (not use_italics and (bool(_DIRECTION_LEAD.match(text)) or opens_with_a_name(text)))
        )
        label = None if is_direction else _label(text)
        cue = None if (is_direction or label or not cues_count) else _cue(text)

        if _HEADING.match(text) and not label:
            flush()
            pending_cue = None
            out.append(Element("heading", text, page=row.page))
            continue
        if label:
            flush()
            name, aside, rest = label
            speaker = who(name)
            pending_cue = None
            building = _Building("line", [aside, rest] if aside else [rest], speaker, row.page)
            continue
        if cue:
            flush()
            pending_cue = speaker = who(cue)
            continue
        if is_direction:
            body = emphasis["inner"] if emphasis else text
            if building is not None and building.kind == "direction" and row.gap < 0.8:
                building.parts.append(body)
                continue
            flush()
            building = _Building("direction", [body], page=row.page)
            continue
        # Words with no name on them.
        if pending_cue:
            building = _Building("line", [text], pending_cue, row.page)
            pending_cue = None
            continue
        if building is not None and building.kind == "line" and row.gap < 0.8:
            building.parts.append(text)
            continue
        flush()
        if speaker is not None:
            building = _Building("line", [text], speaker, row.page)
        else:
            # Before anyone speaks: a title, a cast list, a setting.
            building = _Building("direction", [text], page=row.page)
    flush()

    if len(out) > MAX_ELEMENTS:
        raise ParseError(f"That's more than {MAX_ELEMENTS:,} lines and directions; try one act at a time")
    if not any(e.kind == "line" for e in out):
        raise ParseError(
            "I couldn't find anyone's lines. Scripts work best as 'Name: line' or a name in capitals above each line"
        )
    return out


def _join(parts: list[str]) -> str:
    text = ""
    for part in (p.strip() for p in parts):
        if not part:
            continue
        if text.endswith("-") and len(text) > 1 and text[-2].isalpha() and part[:1].islower():
            text += part  # a word broken across rows
        else:
            text = f"{text} {part}" if text else part
    return " ".join(text.split())


def _finish(b: _Building) -> Element:
    text = _join(b.parts)[:MAX_ELEMENT_CHARS]
    if b.kind != "line":
        return Element(b.kind, text, page=b.page)
    notes = [f"({n.strip()})" for n in _INLINE_NOTE.findall(text)]
    spoken = " ".join(_INLINE_NOTE.sub(" ", text).split())
    if not spoken:
        # A line that's all aside: it's a direction for them.
        return Element("direction", text, page=b.page)
    return Element("line", spoken, character=b.character, note=" ".join(notes) or None, page=b.page)
