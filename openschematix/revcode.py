"""A revision code on a printed sheet: a QR code holding the FieldWorx label of the revision the print shows,
``FWX:R:<number>@<revision>`` (FieldWorx docs/PROTOCOL.md, section 7). Anyone with FieldWorx on a phone can scan a paper copy and see
whether it's still the released revision, and which one is if it isn't. It holds no web address and nothing else.

The number and revision are RevisionWorx's: the document a project file is in RevisionWorx, and that document's revision. They aren't
the title block's own drawing number or revision fields, which can say anything.

The code goes in one place on every sheet: in the drawing area's lower-right corner, just above the revision table and title block
(or the frame, without them). It is never drawn over anything: `blocked` says what's there, and then the sheet is printed without it.
The QR code comes from fwx_label.py, FieldWorx's encoder, copied in unchanged so every program in the family draws the same code.
Standard library only; no tkinter.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import titleblock
from .fwx_label import QRError, encode, label_code
from .geometry import UNIT_MM

SIZE = 20.0 / UNIT_MM        # 80 paper units: the QR code's square, its quiet zone of 4 modules included
CAPTION = 8.0                # paper units (2 mm): the size of the words under it
GAP = 6.0                    # paper units (1.5 mm) between the code and the revision table, title block or frame
LEVEL = "Q"                  # a quarter of the code can be dirty or torn and it still reads
CLEAR = (SIZE, SIZE + CAPTION * 1.5)     # what it needs, across and down


class CodeError(ValueError):
    """There's no revision code to print, or no room for it. The message is written for the person."""


@dataclass(frozen=True)
class RevisionCode:
    """A RevisionWorx document's number and the label of the revision a print shows."""
    number: str
    revision: str

    @classmethod
    def parse(cls, text: str) -> "RevisionCode":
        """``E-100@B``: the revision is what follows the last @."""
        number, at, revision = text.strip().rpartition("@")
        code = cls(number.strip(), revision.strip())
        if not at:
            raise CodeError(f"A revision code is the document's number and its revision, like E-100@B, not {text.strip()!r}.")
        code.text                                   # checks it, as FieldWorx reads it
        return code

    @property
    def text(self) -> str:
        """What the QR code holds."""
        try:
            return label_code("R", f"{self.number}@{self.revision}")
        except QRError as exc:
            raise CodeError(f"{self.number}@{self.revision} can't be a revision code: {exc}.") from None

    @property
    def caption(self) -> str:
        return f"{self.number} rev {self.revision}"


def area(doc) -> tuple:
    """Where the code and its caption go on a sheet, in paper units (0.25 mm, y down, as export.paper_items gives the sheet):
    (left, top, right, bottom)."""
    f = doc.sheet.scale_factor()
    _x0, _y0, x1, y1 = (v * f for v in titleblock.frame_layout(doc)["drawable"])
    right, bottom = x1 - GAP, y1 - GAP
    return (right - CLEAR[0], bottom - CLEAR[1], right, bottom)


def _segment_hits(ax, ay, bx, by, box) -> bool:
    """Liang-Barsky: does the segment touch the box?"""
    x0, y0, x1, y1 = box
    t0, t1 = 0.0, 1.0
    dx, dy = bx - ax, by - ay
    for d, q0, q1 in ((dx, x0 - ax, x1 - ax), (dy, y0 - ay, y1 - ay)):
        if d == 0.0:
            if q0 > 0.0 or q1 < 0.0:
                return False
        else:
            a, b = q0 / d, q1 / d
            if a > b:
                a, b = b, a
            t0, t1 = max(t0, a), min(t1, b)
            if t0 > t1:
                return False
    return True


def _overlap(a, b) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _touches(it: dict, box) -> bool:
    k = it["k"]
    if k in ("line", "poly"):
        pts = list(it["pts"])
        if k == "poly":
            pts.append(pts[0])
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            if it.get("fill") and _overlap((min(xs), min(ys), max(xs), max(ys)), box):
                return True
        return any(_segment_hits(a[0], a[1], b[0], b[1], box) for a, b in zip(pts, pts[1:])) or \
            any(box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3] for p in pts)
    if k == "circle":
        (cx, cy), r = it["c"], it["r"]
        return _overlap((cx - r, cy - r, cx + r, cy + r), box)
    if k == "text":
        from .export import text_origin, text_width
        size = it.get("size", 10)
        x, y = text_origin(it)
        w = text_width(it["s"], size, it.get("bold", False))
        if it.get("angle"):
            reach = w + size
            return _overlap((it["p"][0] - reach, it["p"][1] - reach, it["p"][0] + reach, it["p"][1] + reach), box)
        return _overlap((x, y - 0.75 * size, x + w, y + 0.25 * size), box)
    if k == "region":
        pts = [(p[0], p[1]) for ring in it["rings"] for p in ring]
        return bool(pts) and _overlap((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts),
                                       max(p[1] for p in pts)), box)
    return False


def blocked(items, box) -> list:
    """The drawn items in the code's place. The frame, title block and revision table aren't drawing, and a PRELIMINARY watermark is
    printed under everything; they don't count."""
    return [it for it in items if it.get("role") not in ("frame", "watermark") and _touches(it, box)]


def why_not(items, box) -> str:
    """Why the code can't go on this sheet, or "" when it can."""
    if blocked(items, box):
        return (f"no room for the revision code: something is drawn in the lower right corner of the drawing area, where it goes "
                f"(it needs {CLEAR[0] * UNIT_MM:g} x {CLEAR[1] * UNIT_MM:g} mm clear)")
    return ""


def code_items(code: RevisionCode, box) -> list:
    """The code as items to print: its dark modules as one filled region, and the number and revision under it."""
    from .export import text_width
    x0, y0, x1, y1 = box
    rows = encode(code.text, LEVEL)
    unit = SIZE / (len(rows) + 8)
    left, top = x0 + 4 * unit, y0 + 4 * unit
    rings = []
    for r, row in enumerate(rows):
        c = 0
        while c < len(row):
            if not row[c]:
                c += 1
                continue
            start = c
            while c < len(row) and row[c]:
                c += 1
            xa, xb = left + start * unit, left + c * unit
            ya, yb = top + r * unit, top + (r + 1) * unit
            rings.append([(xa, ya, 0.0), (xb, ya, 0.0), (xb, yb, 0.0), (xa, yb, 0.0)])
    out = [{"k": "region", "rings": rings, "role": "revision_code", "item": None}]
    words = code.caption
    size = min(CAPTION, CAPTION * SIZE / max(text_width(words, CAPTION), 1e-9))
    if size >= 4.0:                     # 1 mm: smaller can't be read; the title block and the code still say it
        out.append({"k": "text", "p": ((x0 + x1) / 2, y1 - 1.0), "s": words, "size": size, "anchor": "s",
                    "role": "revision_code", "item": None})
    return out


__all__ = ["CAPTION", "CLEAR", "CodeError", "LEVEL", "RevisionCode", "SIZE", "area", "blocked", "code_items", "why_not"]
