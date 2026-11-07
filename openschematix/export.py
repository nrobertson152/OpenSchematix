"""SVG and PDF export. Both draw the same scene as the editor (render.scene)
in black on white, without on-screen-only markers. The PDF writer is
self-contained (standard Helvetica fonts, vector output) so no third-party
library is needed."""
from __future__ import annotations

import os
import tempfile
import zlib
from xml.sax.saxutils import escape

from . import symbols
from .geometry import UNIT_MM, bbox_union
from .model import Document
from .render import scene, scene_bbox

# Helvetica advance widths (Adobe AFM, 1/1000 em) for ASCII 32..126
_HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
         556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
         1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
         667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
         333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
         556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_HELV_BOLD_SCALE = 1.06  # approximation for Helvetica-Bold


def text_width(s: str, size: float, bold: bool = False) -> float:
    total = 0
    for ch in s:
        o = ord(ch)
        total += _HELV[o - 32] if 32 <= o <= 126 else 556
    return total / 1000.0 * size * (_HELV_BOLD_SCALE if bold else 1.0)


def text_origin(item):
    """Baseline-left origin of a text item, honouring its anchor."""
    x, y = item["p"]
    size = item.get("size", 10)
    a = item.get("anchor", "c")
    w = text_width(item["s"], size, item.get("bold", False))
    if "e" in a:
        x -= w
    elif "w" not in a:
        x -= w / 2
    if "n" in a:
        y += 0.72 * size
    elif "s" in a:
        y -= 0.21 * size
    else:
        y += 0.36 * size
    return x, y


@symbols.project_scoped
def paper_items(doc: Document, use_sheet: bool = True, project=None):
    """Scene items converted to paper units (presentation scale applied) and
    the page extent. Line widths are pen widths and are not scaled."""
    items = scene(doc, screen=False, frame=use_sheet, project=project)
    f = doc.sheet.scale_factor()
    if f != 1.0:
        out = []
        for it in items:
            q = dict(it)
            if "pts" in q:
                q["pts"] = [(x * f, y * f) for x, y in q["pts"]]
            if "c" in q:
                q["c"] = (q["c"][0] * f, q["c"][1] * f)
                q["r"] = q["r"] * f
            if "p" in q:
                q["p"] = (q["p"][0] * f, q["p"][1] * f)
                q["size"] = q.get("size", 10) * f
            if "rings" in q:     # uniform scale: bulges are unchanged
                q["rings"] = [[(x * f, y * f, b) for x, y, b in ring] for ring in q["rings"]]
            out.append(q)
        items = out
    if use_sheet:
        W, H = doc.sheet.paper_units()
        return items, (0.0, 0.0, W, H)
    b = scene_bbox(items) or (0, 0, 100, 100)
    pad = 20
    extent = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
    # A frameless export is still a preliminary drawing. Place its designation
    # within the content-based export extent rather than the omitted sheet frame.
    if doc.sheet.drawing_status == "Preliminary":
        x0, y0, x1, y1 = extent
        w, h = x1 - x0, y1 - y0
        cx = (x0 + x1) / 2
        items = list(items) + [
            {"k": "text", "p": (cx, y0 + h * 0.46), "s": "PRELIMINARY",
             "size": min(w / 12, h / 5), "anchor": "c", "angle": 25,
             "bold": True, "role": "watermark", "item": None, "color": "#b8b8b8"},
            {"k": "text", "p": (cx, y0 + h * 0.59), "s": "NOT FOR PRODUCTION",
             "size": min(w / 36, h / 15), "anchor": "c", "angle": 25,
             "role": "watermark", "item": None, "color": "#b8b8b8"},
        ]
    return items, extent


def _fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _atomic_write(path: str, data: bytes):
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ================================================================ regions (boundary fills)
def _fmt4(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def svg_region_path(rings) -> str:
    """SVG path data for a region: one closed sub-path per ring, arcs as
    elliptical-arc commands (exact), filled with fill-rule="evenodd"."""
    from .regions import bulge_arc, ring_edges, split_arcs
    d = []
    for ring in rings:
        ring = split_arcs(ring)
        d.append(f"M{_fmt4(ring[0][0])} {_fmt4(ring[0][1])}")
        for p0, p1, b in ring_edges(ring):
            if b:
                _c, r, _a0, sw = bulge_arc(p0, p1, b)
                # world y points down like SVG's, so a positive sweep is SVG's positive-angle direction
                d.append(f"A{_fmt4(r)} {_fmt4(r)} 0 0 {1 if sw > 0 else 0} {_fmt4(p1[0])} {_fmt4(p1[1])}")
            else:
                d.append(f"L{_fmt4(p1[0])} {_fmt4(p1[1])}")
        d.append("Z")
    return " ".join(d)


def pdf_region_ops(rings) -> list:
    """PDF path operators for a region: arcs as cubic Béziers (pieces of at
    most 90°, radial error < 0.03 %), filled with the even-odd rule (f*)."""
    from .regions import bulge_arc, ring_edges, split_arcs
    ops = []
    for ring in rings:
        ring = split_arcs(ring)
        ops.append(f"{_fmt4(ring[0][0])} {_fmt4(ring[0][1])} m")
        for p0, p1, b in ring_edges(ring):
            if b:
                (cx, cy), _r, _a0, sw = bulge_arc(p0, p1, b)
                k = 4.0 / 3.0 * b            # 4/3 tan(sweep / 4)
                v0 = (p0[0] - cx, p0[1] - cy)
                v1 = (p1[0] - cx, p1[1] - cy)
                c1 = (p0[0] - k * v0[1], p0[1] + k * v0[0])
                c2 = (p1[0] + k * v1[1], p1[1] - k * v1[0])
                ops.append(f"{_fmt4(c1[0])} {_fmt4(c1[1])} {_fmt4(c2[0])} {_fmt4(c2[1])} "
                           f"{_fmt4(p1[0])} {_fmt4(p1[1])} c")
            else:
                ops.append(f"{_fmt4(p1[0])} {_fmt4(p1[1])} l")
        ops.append("h")
    if ops:
        ops.append("f*")
    return ops


# ================================================================ SVG
@symbols.project_scoped
def to_svg(doc: Document, use_sheet: bool = True, project=None) -> str:
    items, (x0, y0, x1, y1) = paper_items(doc, use_sheet, project)
    w, h = x1 - x0, y1 - y0
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(w * UNIT_MM)}mm" height="{_fmt(h * UNIT_MM)}mm" '
        f'viewBox="{_fmt(x0)} {_fmt(y0)} {_fmt(w)} {_fmt(h)}">',
        f'<title>{escape(doc.sheet.title or "Schematic")}</title>',
        f'<rect x="{_fmt(x0)}" y="{_fmt(y0)}" width="{_fmt(w)}" height="{_fmt(h)}" fill="#ffffff"/>',
        '<g fill="none" stroke="#000000" stroke-linecap="round" stroke-linejoin="round">',
    ]
    for it in items:
        k = it["k"]
        dash = ' stroke-dasharray="6 3"' if it.get("dash") else ""
        sw = f' stroke-width="{_fmt(it.get("wpx", 1.4))}"'
        if k == "line":
            pts = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in it["pts"])
            out.append(f'<polyline points="{pts}"{sw}{dash}/>')
        elif k == "poly":
            pts = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in it["pts"])
            fill = ' fill="#000000"' if it.get("fill") else ""
            out.append(f'<polygon points="{pts}"{sw}{dash}{fill}/>')
        elif k == "circle":
            (cx, cy), r = it["c"], it["r"]
            fill = ' fill="#000000"' if it.get("fill") else ""
            out.append(f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(r)}"{sw}{dash}{fill}/>')
        elif k == "region":
            out.append(f'<path d="{svg_region_path(it["rings"])}" fill="#000000" fill-rule="evenodd" stroke="none"/>')
        elif k == "text":
            x, y = text_origin(it)
            weight = ' font-weight="bold"' if it.get("bold") else ""
            rot = ""
            if it.get("angle"):
                ax, ay = it["p"]
                rot = f' transform="rotate({_fmt(-it["angle"])} {_fmt(ax)} {_fmt(ay)})"'
            color = it.get("color", "#000000")
            out.append(f'<text x="{_fmt(x)}" y="{_fmt(y)}" font-family="Helvetica, Arial, sans-serif" '
                       f'font-size="{_fmt(it.get("size", 10))}"{weight}{rot} fill="{escape(color)}" stroke="none">'
                       f'{escape(it["s"])}</text>')
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def export_svg(doc: Document, path: str, use_sheet: bool = True, project=None):
    _atomic_write(path, to_svg(doc, use_sheet, project).encode("utf-8"))


# ================================================================ PDF
_K = 0.5522847498


def _pdf_bytes(b: bytes) -> str:
    """Escaped PDF string body for encoded bytes."""
    out = []
    for ch in b:
        c = chr(ch)
        if c in "()\\":
            out.append("\\" + c)
        elif ch < 32 or ch > 126:
            out.append("\\%03o" % ch)
        else:
            out.append(c)
    return "".join(out)


def _pdf_str(s: str) -> str:
    return _pdf_bytes(s.encode("cp1252", errors="replace"))


# Text is drawn with the standard Helvetica fonts in WinAnsiEncoding (= cp1252). Characters it lacks
# that the standard Symbol font has - Greek letters, maths, arrows, all common on schematics (10 Ω,
# Δp, ≤, →) - are drawn in Symbol (its built-in encoding; no font is embedded). Anything else is
# drawn as "?" and reported to the caller (#81).
_SYMBOL_GREEK = "ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟΠΘΡΣΤΥςΩΞΨΖ"
_SYMBOL = {ch: 0x41 + i for i, ch in enumerate(_SYMBOL_GREEK)}
_SYMBOL.update({ch: 0x61 + i for i, ch in enumerate("αβχδεφγηιϕκλμνοπθρστυϖωξψζ")})
_SYMBOL.update({
    "\u2126": 0x57,   # OHM SIGN -> Omega
    "\u2206": 0x44,   # INCREMENT -> Delta
    "\u03f5": 0x65,   # lunate epsilon
    "\u2200": 0x22, "\u2203": 0x24, "\u220b": 0x27, "\u2217": 0x2A, "\u2212": 0x2D, "\u2245": 0x40,
    "\u2234": 0x5C, "\u22a5": 0x5E, "\u223c": 0x7E, "\u03d2": 0xA1, "\u2032": 0xA2, "\u2264": 0xA3,
    "\u2044": 0xA4, "\u221e": 0xA5, "\u2663": 0xA7, "\u2666": 0xA8, "\u2665": 0xA9, "\u2660": 0xAA,
    "\u2194": 0xAB, "\u2190": 0xAC, "\u2191": 0xAD, "\u2192": 0xAE, "\u2193": 0xAF, "\u2033": 0xB2,
    "\u2265": 0xB3, "\u221d": 0xB5, "\u2202": 0xB6, "\u2260": 0xB9, "\u2261": 0xBA, "\u2248": 0xBB,
    "\u21b5": 0xBF, "\u2135": 0xC0, "\u2111": 0xC1, "\u211c": 0xC2, "\u2118": 0xC3, "\u2297": 0xC4,
    "\u2295": 0xC5, "\u2205": 0xC6, "\u2229": 0xC7, "\u222a": 0xC8, "\u2283": 0xC9, "\u2287": 0xCA,
    "\u2284": 0xCB, "\u2282": 0xCC, "\u2286": 0xCD, "\u2208": 0xCE, "\u2209": 0xCF, "\u2220": 0xD0,
    "\u2207": 0xD1, "\u220f": 0xD5, "\u221a": 0xD6, "\u22c5": 0xD7, "\u2227": 0xD9, "\u2228": 0xDA,
    "\u21d4": 0xDB, "\u21d0": 0xDC, "\u21d1": 0xDD, "\u21d2": 0xDE, "\u21d3": 0xDF, "\u25ca": 0xE0,
    "\u2329": 0xE1, "\u2211": 0xE5, "\u232a": 0xF1, "\u222b": 0xF2,
})


def _pdf_runs(s: str, missing: set | None = None) -> list[tuple[bool, str]]:
    """Split text into (symbol_font, escaped string) runs. Characters neither
    font can draw become "?" and are added to `missing`."""
    runs: list[tuple[bool, bytearray]] = []
    for ch in s:
        try:
            sym, b = False, ch.encode("cp1252")
        except UnicodeEncodeError:
            code = _SYMBOL.get(ch)
            if code is not None:
                sym, b = True, bytes([code])
            else:
                sym, b = False, b"?"
                if missing is not None:
                    missing.add(ch)
        if runs and runs[-1][0] == sym:
            runs[-1][1].extend(b)
        else:
            runs.append((sym, bytearray(b)))
    return [(sym, _pdf_bytes(bytes(b))) for sym, b in runs]


def _pdf_show(runs, font: str, size: str) -> str:
    """Text-showing operators for runs; the text font is already selected."""
    out = []
    current = False
    for sym, body in runs:
        if sym != current:
            out.append(f"/F3 {size} Tf" if sym else f"{font} {size} Tf")
            current = sym
        out.append(f"({body}) Tj")
    return " ".join(out) if out else "() Tj"


def _page_content(items, extent, missing: set | None = None) -> tuple[bytes, float, float]:
    x0, y0, x1, y1 = extent
    k = UNIT_MM * 72.0 / 25.4  # points per drawing unit
    pw, ph = (x1 - x0) * k, (y1 - y0) * k
    ops = ["q", f"{_fmt(k)} 0 0 {_fmt(-k)} {_fmt(-x0 * k)} {_fmt(ph + y0 * k)} cm",
           "1 J 1 j 0 0 0 RG 0 0 0 rg"]
    for it in items:
        kind = it["k"]
        if kind == "text":
            continue
        if kind == "region":
            ops += pdf_region_ops(it["rings"])
            continue
        ops.append(f"{_fmt(it.get('wpx', 1.4))} w")
        ops.append("[6 3] 0 d" if it.get("dash") else "[] 0 d")
        if kind in ("line", "poly"):
            pts = it["pts"]
            ops.append(f"{_fmt(pts[0][0])} {_fmt(pts[0][1])} m")
            ops += [f"{_fmt(x)} {_fmt(y)} l" for x, y in pts[1:]]
            if kind == "poly":
                ops.append("b" if it.get("fill") else "s")
            else:
                ops.append("S")
        elif kind == "circle":
            (cx, cy), r = it["c"], it["r"]
            c = r * _K
            ops.append(f"{_fmt(cx + r)} {_fmt(cy)} m")
            ops.append(f"{_fmt(cx + r)} {_fmt(cy + c)} {_fmt(cx + c)} {_fmt(cy + r)} {_fmt(cx)} {_fmt(cy + r)} c")
            ops.append(f"{_fmt(cx - c)} {_fmt(cy + r)} {_fmt(cx - r)} {_fmt(cy + c)} {_fmt(cx - r)} {_fmt(cy)} c")
            ops.append(f"{_fmt(cx - r)} {_fmt(cy - c)} {_fmt(cx - c)} {_fmt(cy - r)} {_fmt(cx)} {_fmt(cy - r)} c")
            ops.append(f"{_fmt(cx + c)} {_fmt(cy - r)} {_fmt(cx + r)} {_fmt(cy - c)} {_fmt(cx + r)} {_fmt(cy)} c")
            ops.append("b" if it.get("fill") else "s")
    import math
    for it in items:
        if it["k"] != "text":
            continue
        font = "/F2" if it.get("bold") else "/F1"
        if it.get("role") == "watermark":
            ops.append("0.72 0.72 0.72 rg")
        else:
            ops.append("0 0 0 rg")
        ang = it.get("angle", 0) or 0
        if ang:
            # rotate about the anchor point: compute origin in the rotated frame
            ox, oy = text_origin(dict(it, p=(0.0, 0.0)))
            t = math.radians(ang)
            co, si = math.cos(t), math.sin(t)
            ax, ay = it["p"]
            x = ax + ox * co + oy * si
            y = ay - ox * si + oy * co
            matrix = f"{_fmt(co)} {_fmt(-si)} {_fmt(-si)} {_fmt(-co)} {_fmt(x)} {_fmt(y)}"
        else:
            x, y = text_origin(it)
            matrix = f"1 0 0 -1 {_fmt(x)} {_fmt(y)}"
        size = _fmt(it.get("size", 10))
        ops.append(f"BT {font} {size} Tf {matrix} Tm {_pdf_show(_pdf_runs(it['s'], missing), font, size)} ET")
    ops.append("Q")
    return zlib.compress("\n".join(ops).encode("latin-1")), pw, ph


def _pdf_text(s: str) -> str:
    """PDF text string for metadata/outlines (UTF-16BE with BOM if needed)."""
    try:
        s.encode("ascii")
        return "(" + _pdf_str(s) + ")"
    except UnicodeEncodeError:
        return "<FEFF" + s.encode("utf-16-be").hex().upper() + ">"


def build_pdf(pages, title: str = "Schematic", author: str = "", missing: set | None = None) -> bytes:
    """pages: list of (label, items, extent). Writes one PDF page per entry,
    each with its own size, plus bookmarks (outline) and page labels.
    Characters of drawing text that cannot be shown are added to `missing`
    (drawn as "?"); titles and bookmarks are Unicode and always exact."""
    from . import APP_NAME, VERSION
    n = len(pages)
    if n == 0:
        raise ValueError("nothing to export")
    # object numbering
    # 1 catalog, 2 pages, 3 font F1, 4 font F2, 5 info, 6 outlines root, 7 font F3 (Symbol),
    # then per page: page obj, content obj, outline item
    objs: dict[int, bytes] = {}
    first = 8
    page_ids, content_ids, outline_ids = [], [], []
    for i in range(n):
        page_ids.append(first + 3 * i)
        content_ids.append(first + 3 * i + 1)
        outline_ids.append(first + 3 * i + 2)
    for i, (label, items, extent) in enumerate(pages):
        content, pw, ph = _page_content(items, extent, missing)
        objs[page_ids[i]] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_fmt(pw)} {_fmt(ph)}] "
                             f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 7 0 R >> >> /Contents {content_ids[i]} 0 R >>"
                             ).encode()
        objs[content_ids[i]] = (f"<< /Length {len(content)} /Filter /FlateDecode >>\nstream\n".encode() + content +
                                b"\nendstream")
        prev = f"/Prev {outline_ids[i - 1]} 0 R " if i else ""
        nxt = f"/Next {outline_ids[i + 1]} 0 R " if i < n - 1 else ""
        objs[outline_ids[i]] = (f"<< /Title {_pdf_text(label)} /Parent 6 0 R {prev}{nxt}"
                                f"/Dest [{page_ids[i]} 0 R /Fit] >>").encode("latin-1")
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    objs[1] = (b"<< /Type /Catalog /Pages 2 0 R /Outlines 6 0 R /PageMode /UseOutlines "
               b"/PageLabels << /Nums [0 << /S /D /St 1 >>] >> >>")
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode()
    objs[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    objs[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    objs[7] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Symbol >>"
    objs[5] = (f"<< /Title {_pdf_text(title or 'Schematic')} /Author {_pdf_text(author)} "
               f"/Producer ({APP_NAME} {VERSION}) /Creator ({APP_NAME} {VERSION}) >>").encode("latin-1")
    objs[6] = f"<< /Type /Outlines /First {outline_ids[0]} 0 R /Last {outline_ids[-1]} 0 R /Count {n} >>".encode()
    total = max(objs)
    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for i in range(1, total + 1):
        offsets[i] = len(buf)
        buf += f"{i} 0 obj\n".encode() + objs[i] + b"\nendobj\n"
    xref = len(buf)
    buf += f"xref\n0 {total + 1}\n0000000000 65535 f \n".encode()
    for i in range(1, total + 1):
        buf += f"{offsets[i]:010d} 00000 n \n".encode()
    buf += f"trailer\n<< /Size {total + 1} /Root 1 0 R /Info 5 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(buf)


@symbols.project_scoped
def to_pdf(doc: Document, use_sheet: bool = True, project=None, missing: set | None = None) -> bytes:
    items, extent = paper_items(doc, use_sheet, project)
    proj = project if project is not None else getattr(doc, "project", None)
    title = doc.sheet.title or (proj.meta.get("title") if proj is not None else "") or "Schematic"
    return build_pdf([(doc.name or title, items, extent)], title=title, missing=missing)


@symbols.project_scoped
def project_pdf(project, sheet_uids=None, missing: set | None = None, code=None, skipped: list | None = None) -> bytes:
    """All (or the selected) sheets of a project in one PDF, in project
    order, each page at its own sheet size and orientation.

    `code` (revcode.RevisionCode) prints the revision's QR code on every
    sheet, in the drawing area's lower right corner, never over anything
    drawn. A sheet with something there is printed without it and named in
    `skipped`; without `skipped`, it raises revcode.CodeError instead and
    nothing is made."""
    from . import revcode
    pages = []
    for doc in project.sheets:
        if sheet_uids is not None and doc.uid not in sheet_uids:
            continue
        items, extent = paper_items(doc, True, project)
        label = f"{project.sheet_number(doc)}. {doc.name}"
        if code is not None:
            box = revcode.area(doc)
            problem = revcode.why_not(items, box)
            if not problem:
                items = list(items) + revcode.code_items(code, box)
            elif skipped is None:
                raise revcode.CodeError(f"Sheet {label}: {problem}.")
            else:
                skipped.append(label)
        pages.append((label, items, extent))
    return build_pdf(pages, title=project.meta.get("title") or "Schematic", author=project.meta.get("author", ""),
                     missing=missing)


def export_project_pdf(project, path: str, sheet_uids=None, code=None, skipped: list | None = None) -> list[str]:
    """Write the PDF. Returns the characters of drawing text that PDF output
    cannot show (drawn as "?"), sorted; empty if everything was shown.
    `code` and `skipped` as for project_pdf."""
    missing: set = set()
    _atomic_write(path, project_pdf(project, sheet_uids, missing, code, skipped))
    return sorted(missing)


def export_pdf(doc: Document, path: str, use_sheet: bool = True, project=None) -> list[str]:
    """As export_project_pdf, for one sheet."""
    missing: set = set()
    _atomic_write(path, to_pdf(doc, use_sheet, project, missing))
    return sorted(missing)
