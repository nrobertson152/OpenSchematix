"""DXF import and export (self-contained, no third-party library).

Export writes AutoCAD R12 ASCII DXF (AC1009), the most widely readable DXF
dialect (AutoCAD, BricsCAD, DraftSight, LibreCAD, QCAD, FreeCAD, ezdxf…).
Geometry is written in millimetres at true model size with the origin at the
lower-left corner of the sheet; the Y axis points up as in all CAD programs.

Import reads ASCII DXF of any version (R12 to 2018+). Supported entities:
LINE, LWPOLYLINE (including arc bulges), POLYLINE (2D), CIRCLE, ARC, ELLIPSE
(approximated), SPLINE (approximated through its fit/control points),
TEXT, MTEXT, SOLID/TRACE, INSERT (block references are exploded, nested
blocks included) and DIMENSION (exploded from the dimension's block, so the
dimension appears as lines and text). Everything becomes editable drafting
geometry on layers named after the DXF layers. Unsupported entities (HATCH,
IMAGE, 3D entities, …) are skipped and counted in the import report.
Binary DXF and DWG are not supported.

See docs/DXF.md for details and limitations.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .geometry import UNIT_MM
from .model import Shape
from .shapes import arc_norm

# ================================================================ common
INSUNITS_MM = {0: None, 1: 25.4, 2: 304.8, 3: 1609344.0, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 0.0000254, 9: 0.0254,
               10: 914.4, 11: 1e-7, 12: 1e-6, 13: 0.001, 14: 100.0}
UNIT_NAMES = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}

# AutoCAD colour index -> RGB for the standard colours
ACI = {1: "#ff0000", 2: "#ffff00", 3: "#00ff00", 4: "#00ffff", 5: "#0000ff", 6: "#ff00ff", 8: "#808080",
       9: "#c0c0c0"}


def layer_name_for_dxf(name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9_$\-]", "_", name.strip() or "0")
    return n[:31] or "0"


# ================================================================ export
FILL_TOL = 0.02      # chord error for arcs of boundary fills, drawing units (0.005 mm)


def region_solids(rings, tol: float = FILL_TOL) -> list:
    """Decompose a boundary fill into trapezoids (4-point quads in drawing
    units) for R12 SOLID entities. R12 has no HATCH entity; SOLIDs are filled
    by every DXF reader. Straight edges are exact, arcs are flattened with a
    chord error of at most `tol`."""
    from .regions import flatten_ring, trapezoids
    return trapezoids([flatten_ring(r, tol) for r in rings])


class _Writer:
    def __init__(self):
        self.lines = []

    def g(self, code, value):
        if isinstance(value, float):
            value = f"{value:.6f}".rstrip("0").rstrip(".")
            if value in ("-0", ""):
                value = "0"
        self.lines.append(f"{code:>3}\n{value}\n")

    def text(self) -> str:
        return "".join(self.lines)


def _enc_text(s: str) -> str:
    out = []
    for ch in s:
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            out.append(f"\\U+{ord(ch):04X}")
    return "".join(out)


def to_dxf(doc, project=None, include_frame: bool = True, layer_by_role: bool = False) -> str:
    """DXF text for one sheet. Coordinates: mm, Y up, origin at the sheet's
    lower-left corner. Model size (presentation scale not applied)."""
    from .render import scene
    items = scene(doc, screen=False, frame=include_frame, project=project)
    W, H = doc.sheet.size_units()
    k = UNIT_MM

    def X(x):
        return x * k

    def Y(y):
        return (H - y) * k

    role_layer = {"frame": "FRAME", "wire": "WIRES", "junction": "WIRES", "wirenum": "WIRE_NUMBERS",
                  "designator": "TEXT", "text": "TEXT", "xref": "TEXT", "pin": "TEXT"}
    used_layers = {"0"}

    def lay(it):
        if layer_by_role or not it.get("layer"):
            name = role_layer.get(it.get("role"), "SYMBOLS")
        else:
            name = it["layer"]
            if it.get("role") == "frame":
                name = "FRAME"
        name = layer_name_for_dxf(name)
        used_layers.add(name)
        return name

    ents = _Writer()
    blocks = _Writer()
    n_fills = 0
    for it in items:
        layer = lay(it)
        ltype = "DASHED" if it.get("dash") else "CONTINUOUS"
        kind = it["k"]
        if kind == "region":
            quads = region_solids(it["rings"])
            if not quads:
                continue
            n_fills += 1
            name = f"OSX_FILL_{n_fills}"
            blocks.g(0, "BLOCK")
            blocks.g(8, layer)
            blocks.g(2, name)
            blocks.g(70, 0)
            for c in (10, 20, 30):
                blocks.g(c, 0.0)
            blocks.g(3, name)
            for q in quads:
                blocks.g(0, "SOLID")
                blocks.g(8, layer)
                for n, idx in enumerate((0, 1, 3, 2)):       # SOLID corner order: 1 2 4 3
                    blocks.g(10 + n, X(q[idx][0]))
                    blocks.g(20 + n, Y(q[idx][1]))
                    blocks.g(30 + n, 0.0)
            blocks.g(0, "ENDBLK")
            blocks.g(8, layer)
            ents.g(0, "INSERT")
            ents.g(8, layer)
            ents.g(2, name)
            for c in (10, 20, 30):
                ents.g(c, 0.0)
            continue
        if kind in ("line", "poly"):
            pts = it["pts"]
            closed = kind == "poly"
            if kind == "poly" and it.get("fill") and len(pts) in (3, 4):
                ents.g(0, "SOLID")
                ents.g(8, layer)
                order = [0, 1, 2, 2] if len(pts) == 3 else [0, 1, 3, 2]
                for n, idx in enumerate(order):
                    ents.g(10 + n, X(pts[idx][0]))
                    ents.g(20 + n, Y(pts[idx][1]))
                    ents.g(30 + n, 0.0)
                continue
            if len(pts) == 2 and not closed:
                ents.g(0, "LINE")
                ents.g(8, layer)
                ents.g(6, ltype)
                ents.g(10, X(pts[0][0]))
                ents.g(20, Y(pts[0][1]))
                ents.g(30, 0.0)
                ents.g(11, X(pts[1][0]))
                ents.g(21, Y(pts[1][1]))
                ents.g(31, 0.0)
                continue
            ents.g(0, "POLYLINE")
            ents.g(8, layer)
            ents.g(6, ltype)
            ents.g(66, 1)
            ents.g(10, 0.0)
            ents.g(20, 0.0)
            ents.g(30, 0.0)
            ents.g(70, 1 if closed else 0)
            for x, y in pts:
                ents.g(0, "VERTEX")
                ents.g(8, layer)
                ents.g(10, X(x))
                ents.g(20, Y(y))
                ents.g(30, 0.0)
            ents.g(0, "SEQEND")
            ents.g(8, layer)
        elif kind == "circle":
            (cx, cy), r = it["c"], it["r"]
            if it.get("fill"):
                # filled dot: a "donut" (closed 2-vertex polyline with bulges and width)
                ents.g(0, "POLYLINE")
                ents.g(8, layer)
                ents.g(66, 1)
                ents.g(10, 0.0)
                ents.g(20, 0.0)
                ents.g(30, 0.0)
                ents.g(70, 1)
                ents.g(40, r * k)
                ents.g(41, r * k)
                for sx in (-1, 1):
                    ents.g(0, "VERTEX")
                    ents.g(8, layer)
                    ents.g(10, X(cx + sx * r / 2))
                    ents.g(20, Y(cy))
                    ents.g(30, 0.0)
                    ents.g(42, 1.0)
                ents.g(0, "SEQEND")
                ents.g(8, layer)
            else:
                ents.g(0, "CIRCLE")
                ents.g(8, layer)
                ents.g(6, ltype)
                ents.g(10, X(cx))
                ents.g(20, Y(cy))
                ents.g(30, 0.0)
                ents.g(40, r * k)
        elif kind == "text":
            if not it["s"]:
                continue
            size = it.get("size", 10)
            height = size * 0.72 * k          # cap height of the font size
            x, y = it["p"]
            a = it.get("anchor", "c")
            h_al = 1 if a in ("c", "n", "s") else (2 if "e" in a else 0)
            v_al = 3 if a in ("n", "ne", "nw") else (1 if a in ("s", "se", "sw") else 2)
            ents.g(0, "TEXT")
            ents.g(8, layer)
            ents.g(10, X(x))
            ents.g(20, Y(y))
            ents.g(30, 0.0)
            ents.g(40, height)
            ents.g(1, _enc_text(it["s"]))
            if it.get("angle"):
                ents.g(50, float(it["angle"]))
            ents.g(7, "STANDARD")
            if h_al or v_al:
                ents.g(72, h_al)
                ents.g(11, X(x))
                ents.g(21, Y(y))
                ents.g(31, 0.0)
                ents.g(73, v_al)
    # native arcs for drafting shapes (scene() flattens them; re-emit natively
    # is not needed for correctness - flattened polylines are exact enough)
    out = _Writer()
    out.g(0, "SECTION")
    out.g(2, "HEADER")
    out.g(9, "$ACADVER")
    out.g(1, "AC1009")
    out.g(9, "$INSBASE")
    for c in (10, 20, 30):
        out.g(c, 0.0)
    out.g(9, "$EXTMIN")
    out.g(10, 0.0)
    out.g(20, 0.0)
    out.g(30, 0.0)
    out.g(9, "$EXTMAX")
    out.g(10, W * k)
    out.g(20, H * k)
    out.g(30, 0.0)
    out.g(9, "$LIMMIN")
    out.g(10, 0.0)
    out.g(20, 0.0)
    out.g(9, "$LIMMAX")
    out.g(10, W * k)
    out.g(20, H * k)
    out.g(0, "ENDSEC")
    out.g(0, "SECTION")
    out.g(2, "TABLES")
    out.g(0, "TABLE")
    out.g(2, "LTYPE")
    out.g(70, 2)
    for name, desc, pat in (("CONTINUOUS", "Solid line", []), ("DASHED", "Dashed __ __ __", [1.5, -0.75])):
        out.g(0, "LTYPE")
        out.g(2, name)
        out.g(70, 0)
        out.g(3, desc)
        out.g(72, 65)
        out.g(73, len(pat))
        out.g(40, float(sum(abs(p) for p in pat)))
        for p in pat:
            out.g(49, float(p))
    out.g(0, "ENDTAB")
    out.g(0, "TABLE")
    out.g(2, "LAYER")
    out.g(70, len(used_layers))
    for name in sorted(used_layers):
        out.g(0, "LAYER")
        out.g(2, name)
        out.g(70, 0)
        out.g(62, 7)
        out.g(6, "CONTINUOUS")
    out.g(0, "ENDTAB")
    out.g(0, "TABLE")
    out.g(2, "STYLE")
    out.g(70, 1)
    out.g(0, "STYLE")
    out.g(2, "STANDARD")
    out.g(70, 0)
    out.g(40, 0.0)
    out.g(41, 1.0)
    out.g(50, 0.0)
    out.g(71, 0)
    out.g(42, 2.5)
    out.g(3, "txt")
    out.g(4, "")
    out.g(0, "ENDTAB")
    out.g(0, "ENDSEC")
    out.g(0, "SECTION")
    out.g(2, "BLOCKS")
    out.lines += blocks.lines
    out.g(0, "ENDSEC")
    out.g(0, "SECTION")
    out.g(2, "ENTITIES")
    return out.text() + ents.text() + "  0\nENDSEC\n  0\nEOF\n"


def export_dxf(doc, path, project=None, include_frame=True):
    from .export import _atomic_write
    _atomic_write(path, to_dxf(doc, project, include_frame).encode("cp1252", errors="replace"))


# ================================================================ import
class DxfError(ValueError):
    pass


@dataclass
class ImportReport:
    shapes: list = field(default_factory=list)
    layers: dict = field(default_factory=dict)         # name -> colour ("" = default)
    counts: dict = field(default_factory=dict)         # entity type -> imported count
    skipped: dict = field(default_factory=dict)        # entity type -> skipped count
    approximated: dict = field(default_factory=dict)   # entity type -> count
    units_mm: float = 1.0
    units_source: str = ""
    version: str = ""
    bbox: tuple | None = None

    def summary(self) -> str:
        parts = [f"{sum(self.counts.values())} entities imported as {len(self.shapes)} editable objects"]
        if self.approximated:
            parts.append("approximated: " + ", ".join(f"{k} ×{v}" for k, v in sorted(self.approximated.items())))
        if self.skipped:
            parts.append("skipped (unsupported): " + ", ".join(f"{k} ×{v}" for k, v in sorted(self.skipped.items())))
        parts.append(f"units: {self.units_source}")
        return "; ".join(parts) + "."


def _pairs(text: str):
    lines = text.splitlines()
    if len(lines) % 2:
        lines = lines[:-1]
    for i in range(0, len(lines), 2):
        code = lines[i].strip()
        try:
            yield int(code), lines[i + 1].rstrip("\r")
        except ValueError as e:
            raise DxfError(f"malformed group code at line {i + 1}: {code!r}") from e


@dataclass
class _Ent:
    type: str
    tags: list

    def get(self, code, default=None):
        for c, v in self.tags:
            if c == code:
                return v
        return default

    def all(self, code):
        return [v for c, v in self.tags if c == code]

    def f(self, code, default=0.0):
        v = self.get(code)
        try:
            return float(v) if v is not None else default
        except ValueError:
            return default

    def i(self, code, default=0):
        v = self.get(code)
        try:
            return int(float(v)) if v is not None else default
        except ValueError:
            return default


def _parse(text: str):
    """Split a DXF into header variables, layer table, blocks and entities."""
    header, layers, blocks, entities = {}, {}, {}, []
    section = None
    cur = None
    var = None
    block = None
    pairs = list(_pairs(text))
    i = 0
    while i < len(pairs):
        code, val = pairs[i]
        v = val.strip()
        if code == 0 and v == "SECTION":
            section = pairs[i + 1][1].strip() if i + 1 < len(pairs) else None
            i += 2
            cur = None
            continue
        if code == 0 and v == "ENDSEC":
            if cur is not None and section == "ENTITIES":
                entities.append(cur)
            section, cur = None, None
            i += 1
            continue
        if section == "HEADER":
            if code == 9:
                var = v
                header[var] = []
            elif var:
                header[var].append((code, v))
        elif section == "TABLES":
            if code == 0:
                if cur is not None and cur.type == "LAYER":
                    nm = cur.get(2)
                    if nm:
                        layers[nm.strip()] = cur.i(62, 7)
                cur = _Ent(v, [])
            elif cur is not None:
                cur.tags.append((code, val))
        elif section == "BLOCKS":
            if code == 0:
                if cur is not None and block is not None and cur.type not in ("BLOCK", "ENDBLK"):
                    block["ents"].append(cur)
                if v == "BLOCK":
                    cur = _Ent("BLOCK", [])
                    block = {"name": None, "base": (0.0, 0.0), "ents": [], "hdr": cur}
                elif v == "ENDBLK":
                    if block is not None and block["name"]:
                        blocks[block["name"]] = block
                    block = None
                    cur = _Ent("ENDBLK", [])
                else:
                    cur = _Ent(v, [])
            elif cur is not None:
                cur.tags.append((code, val))
                if cur.type == "BLOCK" and block is not None:
                    if code == 2:
                        block["name"] = v
                    elif code == 10:
                        block["base"] = (float(v), block["base"][1])
                    elif code == 20:
                        block["base"] = (block["base"][0], float(v))
        elif section == "ENTITIES":
            if code == 0:
                if cur is not None:
                    entities.append(cur)
                cur = _Ent(v, [])
            elif cur is not None:
                cur.tags.append((code, val))
        i += 1
    return header, layers, blocks, entities


def _group_polylines(ents):
    """Attach VERTEX entities to their POLYLINE (old-style polylines)."""
    out = []
    cur = None
    for e in ents:
        if e.type == "POLYLINE":
            cur = e
            cur.vertices = []
            out.append(e)
        elif e.type == "VERTEX" and cur is not None:
            cur.vertices.append(e)
        elif e.type == "SEQEND":
            cur = None
        else:
            if e.type not in ("VERTEX",):
                out.append(e)
    return out


def _bulge_points(p1, p2, bulge, segs=8):
    """Arc between two points with a DXF bulge (Y-up coordinates)."""
    if abs(bulge) < 1e-9:
        return [p2]
    theta = 4 * math.atan(bulge)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return [p2]
    r = chord / (2 * math.sin(theta / 2))
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    h = r * math.cos(theta / 2)
    nx, ny = -dy / chord, dx / chord
    cx, cy = mx + nx * h, my + ny * h
    a1 = math.atan2(p1[1] - cy, p1[0] - cx)
    n = max(2, int(abs(math.degrees(theta)) / 10) + 1, segs if abs(theta) > 1 else 2)
    pts = []
    for i in range(1, n + 1):
        a = a1 + theta * i / n
        pts.append((cx + abs(r) * math.cos(a), cy + abs(r) * math.sin(a)))
    pts[-1] = p2
    return pts


_MTEXT_FMT = re.compile(r"\\[ACcFfHhQqTtWw][^;]*;|\\[LlOoKk]|[{}]")


def mtext_plain(s: str) -> list[str]:
    s = s.replace("\\P", "\n").replace("\\~", " ").replace("^I", "\t")
    s = re.sub(r"\\S([^;]*?)[#^/]([^;]*);", r"\1/\2", s)
    s = _MTEXT_FMT.sub("", s)
    s = s.replace("\\\\", "\\")
    return [ln for ln in s.split("\n")]


def _unescape(s: str) -> str:
    s = re.sub(r"\\U\+([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), s)
    s = s.replace("%%d", "°").replace("%%D", "°").replace("%%p", "±").replace("%%P", "±")
    s = s.replace("%%c", "Ø").replace("%%C", "Ø").replace("%%%", "%")
    s = re.sub(r"%%[uUoO]", "", s)
    return s


def read_dxf_text(raw: bytes) -> str:
    if raw[:22] == b"AutoCAD Binary DXF\r\n\x1a\x00":
        raise DxfError("binary DXF files are not supported; save the drawing as ASCII DXF")
    if raw[:6] == b"AC1015" or raw[:4] in (b"AC10", b"AC10"):
        raise DxfError("this looks like a DWG file; export it as DXF from your CAD program")
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def import_dxf(raw: bytes, units: str | None = None, scale: float = 1.0, origin=(0.0, 0.0),
               max_entities: int = 200000) -> ImportReport:
    """Parse DXF bytes into drafting shapes (model units, y down).

    `units` overrides the drawing units ("mm", "cm", "m", "in", "ft"); by
    default $INSUNITS is used, or millimetres if the file does not say.
    `origin` is the model point where the DXF origin (0, 0) is placed.
    `scale` is an extra factor applied after unit conversion."""
    text = read_dxf_text(raw)
    header, layer_tab, blocks, entities = _parse(text)
    rep = ImportReport()
    rep.version = (header.get("$ACADVER") or [(1, "")])[0][1]
    if units:
        rep.units_mm = UNIT_NAMES[units]
        rep.units_source = f"{units} (chosen)"
    else:
        iu = None
        for c, v in header.get("$INSUNITS", []):
            if c == 70:
                try:
                    iu = int(v)
                except ValueError:
                    iu = None
        mm = INSUNITS_MM.get(iu) if iu is not None else None
        if mm:
            rep.units_mm = mm
            rep.units_source = {1: "inches", 2: "feet", 4: "millimetres", 5: "centimetres",
                                6: "metres"}.get(iu, f"INSUNITS={iu}") + " ($INSUNITS)"
        else:
            meas = None
            for c, v in header.get("$MEASUREMENT", []):
                if c == 70:
                    meas = v.strip()
            rep.units_mm = 25.4 if meas == "0" else 1.0
            rep.units_source = ("inches ($MEASUREMENT=imperial)" if meas == "0"
                                else "millimetres (not specified in the file; assumed)")
    k = rep.units_mm * scale / UNIT_MM      # DXF unit -> model units
    ox, oy = origin
    ident = [0]

    def nid():
        ident[0] += 1
        return ident[0]

    def tr(m, x, y):
        """Apply 2D affine m=(a,b,c,d,e,f) then DXF->model (y flip)."""
        X = m[0] * x + m[2] * y + m[4]
        Y = m[1] * x + m[3] * y + m[5]
        return (ox + X * k, oy - Y * k)

    def mscale(m):
        return math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))

    def mrot(m):
        return math.degrees(math.atan2(m[1], m[0]))

    def mirrored(m):
        return m[0] * m[3] - m[1] * m[2] < 0

    def color_of(e, inherited):
        ci = e.i(62, 256)
        if ci == 256 or ci == 0:   # BYLAYER / BYBLOCK
            return inherited
        return ACI.get(abs(ci), "")

    def add(kind_name, shape, layer):
        shape.layer = layer
        rep.shapes.append(shape)
        rep.counts[kind_name] = rep.counts.get(kind_name, 0) + 1

    def skip(t):
        rep.skipped[t] = rep.skipped.get(t, 0) + 1

    def approx(t):
        rep.approximated[t] = rep.approximated.get(t, 0) + 1

    def layer_of(e, parent_layer):
        ly = (e.get(8) or "0").strip()
        if ly == "0" and parent_layer:
            ly = parent_layer
        if ly not in rep.layers:
            ci = layer_tab.get(ly, 7)
            rep.layers[ly] = ACI.get(abs(ci), "") if isinstance(ci, int) else ""
        return ly

    count = [0]

    def emit(ents, m, depth, parent_layer):
        for e in _group_polylines(ents):
            count[0] += 1
            if count[0] > max_entities:
                raise DxfError(f"the drawing has more than {max_entities} entities")
            t = e.type
            ly = layer_of(e, parent_layer)
            dash = (e.get(6) or "").upper().startswith(("DASH", "HIDDEN", "CENTER", "PHANTOM", "DOT"))
            if t == "LINE":
                p1 = tr(m, e.f(10), e.f(20))
                p2 = tr(m, e.f(11), e.f(21))
                add(t, Shape(nid(), "line", pts=[p1, p2], dash=dash), ly)
            elif t in ("LWPOLYLINE", "POLYLINE"):
                flags = e.i(70)
                if t == "POLYLINE" and flags & (16 | 64):
                    skip("POLYLINE (3D mesh)")
                    continue
                if t == "LWPOLYLINE":
                    xs = [float(v) for v in e.all(10)]
                    ys = [float(v) for v in e.all(20)]
                    # bulges belong to the preceding vertex; rebuild per vertex
                    bul, vi = [], -1
                    for c, v in e.tags:
                        if c == 10:
                            vi += 1
                            bul.append(0.0)
                        elif c == 42 and vi >= 0:
                            bul[vi] = float(v)
                    verts = list(zip(xs, ys))
                else:
                    verts = [(v.f(10), v.f(20)) for v in getattr(e, "vertices", [])]
                    bul = [v.f(42) for v in getattr(e, "vertices", [])]
                if len(verts) < 2:
                    skip(t + " (degenerate)")
                    continue
                closed = bool(flags & 1)
                pts = [verts[0]]
                seq = verts + ([verts[0]] if closed else [])
                for i in range(len(seq) - 1):
                    b = bul[i] if i < len(bul) else 0.0
                    if b:
                        approx(t + " arc segment")
                    pts += _bulge_points(seq[i], seq[i + 1], b)
                mp = [tr(m, x, y) for x, y in pts]
                if closed:
                    mp = mp[:-1]
                    add(t, Shape(nid(), "polygon", pts=mp, dash=dash), ly)
                else:
                    add(t, Shape(nid(), "line" if len(mp) == 2 else "polyline", pts=mp, dash=dash), ly)
            elif t == "CIRCLE":
                c = tr(m, e.f(10), e.f(20))
                add(t, Shape(nid(), "circle", c=c, r=e.f(40) * k * mscale(m), dash=dash), ly)
            elif t == "ARC":
                c = tr(m, e.f(10), e.f(20))
                st, en = e.f(50), e.f(51)
                ext = (en - st) % 360 or 360.0

                def mapped(a_deg):
                    a = math.radians(a_deg)
                    vx, vy = math.cos(a), math.sin(a)
                    return math.degrees(math.atan2(m[1] * vx + m[3] * vy, m[0] * vx + m[2] * vy)) % 360
                st = mapped(en) if mirrored(m) else mapped(st)
                add(t, Shape(nid(), "arc", c=c, r=e.f(40) * k * mscale(m), start=st, extent=ext, dash=dash), ly)
            elif t == "ELLIPSE":
                cx, cy = e.f(10), e.f(20)
                mx, my = e.f(11), e.f(21)
                ratio = e.f(40, 1.0)
                a0, a1 = e.f(41, 0.0), e.f(42, 2 * math.pi)
                if a1 <= a0:
                    a1 += 2 * math.pi
                n = max(16, int((a1 - a0) / (2 * math.pi) * 72))
                pts = []
                for i in range(n + 1):
                    a = a0 + (a1 - a0) * i / n
                    x = cx + mx * math.cos(a) - my * ratio * math.sin(a)
                    y = cy + my * math.cos(a) + mx * ratio * math.sin(a)
                    pts.append(tr(m, x, y))
                full = abs(a1 - a0 - 2 * math.pi) < 1e-6
                add(t, Shape(nid(), "polygon" if full else "polyline", pts=pts[:-1] if full else pts, dash=dash), ly)
                approx(t)
            elif t == "SPLINE":
                fx, fy = [float(v) for v in e.all(11)], [float(v) for v in e.all(21)]
                cx_, cy_ = [float(v) for v in e.all(10)], [float(v) for v in e.all(20)]
                src = list(zip(fx, fy)) if len(fx) >= 2 else list(zip(cx_, cy_))
                if len(src) < 2:
                    skip(t)
                    continue
                add(t, Shape(nid(), "polyline", pts=[tr(m, x, y) for x, y in src], dash=dash), ly)
                approx(t)
            elif t in ("SOLID", "TRACE"):
                pts = [(e.f(10), e.f(20)), (e.f(11), e.f(21)), (e.f(13, e.f(12)), e.f(23, e.f(22))),
                       (e.f(12), e.f(22))]
                mp = []
                for x, y in pts:
                    q = tr(m, x, y)
                    if not mp or abs(q[0] - mp[-1][0]) > 1e-9 or abs(q[1] - mp[-1][1]) > 1e-9:
                        mp.append(q)
                if len(mp) >= 3:
                    add(t, Shape(nid(), "polygon", pts=mp, fill=True), ly)
            elif t in ("TEXT", "ATTRIB"):
                if t == "ATTRIB" and e.i(70) & 1:
                    continue  # invisible attribute
                s = _unescape(e.get(1) or "")
                if not s.strip():
                    continue
                h = e.f(40, 2.5) * k * mscale(m)
                hal, val = e.i(72), e.i(73)
                if hal or val:
                    x, y = e.f(11, e.f(10)), e.f(21, e.f(20))
                else:
                    x, y = e.f(10), e.f(20)
                anchor = {(0, 0): "sw", (0, 1): "sw", (0, 2): "w", (0, 3): "nw", (1, 0): "s", (1, 1): "s",
                          (1, 2): "c", (1, 3): "n", (2, 0): "se", (2, 1): "se", (2, 2): "e", (2, 3): "ne",
                          (4, 0): "c", (3, 0): "sw", (5, 0): "sw"}.get((hal, val), "sw")
                add(t, Shape(nid(), "text", pts=[tr(m, x, y)], s=s, size=max(1.0, h / 0.72), anchor=anchor,
                             angle=(e.f(50) + mrot(m)) % 360), ly)
            elif t == "MTEXT":
                raw_s = "".join(e.all(3)) + (e.get(1) or "")
                lines = [_unescape(x) for x in mtext_plain(raw_s)]
                h = e.f(40, 2.5) * k * mscale(m)
                att = e.i(71, 1)
                anchor = {1: "nw", 2: "n", 3: "ne", 4: "w", 5: "c", 6: "e", 7: "sw", 8: "s", 9: "se"}.get(att, "nw")
                ang = e.f(50)
                if e.get(11) is not None:
                    ang = math.degrees(math.atan2(e.f(21), e.f(11)))
                ang = (ang + mrot(m)) % 360
                base = tr(m, e.f(10), e.f(20))
                size = max(1.0, h / 0.72)
                lh = size * 1.25
                nl = len(lines)
                # first line position depends on vertical attachment
                if att in (1, 2, 3):
                    y0 = 0.0
                elif att in (4, 5, 6):
                    y0 = -(nl - 1) * lh / 2
                else:
                    y0 = -(nl - 1) * lh
                t_rad = math.radians(ang)
                for n_, ln in enumerate(lines):
                    if not ln.strip():
                        continue
                    off = y0 + n_ * lh
                    p = (base[0] + off * math.sin(t_rad), base[1] + off * math.cos(t_rad))
                    add(t, Shape(nid(), "text", pts=[p], s=ln, size=size, anchor=anchor, angle=ang), ly)
            elif t in ("INSERT", "DIMENSION"):
                name = (e.get(2) or "").strip()
                blk = blocks.get(name)
                if blk is None or depth > 8:
                    skip(t + (" (missing block)" if blk is None else " (nested too deep)"))
                    continue
                if t == "DIMENSION":
                    m2 = m
                else:
                    sx, sy = e.f(41, 1.0), e.f(42, 1.0)
                    rot = math.radians(e.f(50))
                    bx, by = blk["base"]
                    ix, iy = e.f(10), e.f(20)
                    co, si = math.cos(rot), math.sin(rot)
                    # block local -> insert: translate(-base), scale, rotate, translate(ins)
                    a, b, c, d = co * sx, si * sx, -si * sy, co * sy
                    e_, f_ = ix - (a * bx + c * by), iy - (b * bx + d * by)
                    m2 = (m[0] * a + m[2] * b, m[1] * a + m[3] * b, m[0] * c + m[2] * d, m[1] * c + m[3] * d,
                          m[0] * e_ + m[2] * f_ + m[4], m[1] * e_ + m[3] * f_ + m[5])
                rep.counts[t] = rep.counts.get(t, 0) + 1
                cols, rows = (e.i(70, 1) or 1, e.i(71, 1) or 1) if t == "INSERT" else (1, 1)
                if cols * rows > 1:
                    skip("INSERT array (only first item)")
                emit(blk["ents"], m2, depth + 1, ly)
            elif t in ("POINT", "VIEWPORT", "ATTDEF", "SEQEND", "VERTEX", "ENDBLK", "BLOCK"):
                continue
            else:
                skip(t)

    emit(entities, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), 0, None)
    from .shapes import shapes_bbox
    rep.bbox = shapes_bbox(rep.shapes)
    return rep


def place_on_sheet(rep: ImportReport, doc, project=None, layer_prefix: str = "", fit: bool = False):
    """Add imported shapes to a sheet (new ids, layers created in the
    project). Returns the new ids."""
    from .shapes import move_shape
    ids = []
    if fit and rep.bbox:
        from .editing import drawable_area
        x0, y0, x1, y1 = drawable_area(doc)
        b = rep.bbox
        dx = (x0 + x1) / 2 - (b[0] + b[2]) / 2
        dy = (y0 + y1) / 2 - (b[1] + b[3]) / 2
        for s in rep.shapes:
            move_shape(s, dx, dy)
    for s in rep.shapes:
        s.layer = (layer_prefix + s.layer) if layer_prefix else s.layer
        if project is not None:
            lay = project.ensure_layer(s.layer)
            col = rep.layers.get(s.layer[len(layer_prefix):] if layer_prefix else s.layer, "")
            if col and not lay.color:
                lay.color = col
        s.id = doc.new_id()
        doc.add_shape(s)
        ids.append(s.id)
    return ids


__all__ = ["to_dxf", "export_dxf", "import_dxf", "place_on_sheet", "DxfError", "ImportReport", "arc_norm"]
