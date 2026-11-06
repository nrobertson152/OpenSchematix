"""A project as a KiCad schematic (KiCad 7's format, which KiCad 7, 8 and 9 open).

``write_project`` writes, into one folder:

* ``NAME.kicad_sch``: the schematic. A project with several sheets becomes a root sheet that holds one sheet
  per OpenSchematix sheet (``NAME-2-Motor.kicad_sch`` and so on), as KiCad does it;
* ``OpenSchematix.kicad_sym``: the symbols the drawing uses, and a ``sym-lib-table`` that names it, so KiCad
  finds them and they can be placed again;
* ``NAME.kicad_pro`` when there's none, so KiCad opens the folder as a project.

What it keeps, and how:

* **Connections, exactly.** Wires are split wherever another wire ends on them, so every connection is an end
  meeting an end, which is how KiCad connects. A wire attached to a terminal ends exactly on it. Junction dots are
  where OpenSchematix draws them. Wires that only cross stay apart in both programs, and a terminal lying on the
  middle of a wire is connected in neither. Sheet connectors become global labels, which join the same way.
* **Size, nearly.** OpenSchematix draws in 0.25 mm units on a 2.5 mm grid; KiCad uses a 100 mil (2.54 mm) grid.
  One unit is written as 0.254 mm, so every terminal is on KiCad's grid and KiCad's own parts connect to the
  wires. The drawing is 1.6 % larger, centred on the same paper.
* **Parts.** A device drawn in several places under one designator (a contactor's coil and its contacts) is one
  KiCad symbol with a unit for each place. Pin numbers are the terminal designations (A1, 13, 14...).
* **Wire numbers** become the names of the nets in KiCad, as labels, when a number belongs to one net only.

What it can't keep is in ``notes``, and in docs/KICAD.md.
"""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from dataclasses import dataclass, field

from . import symbols
from .connectivity import analyse
from .export import _atomic_write
from .geometry import point_on_segment
from .model import SHEET_SIZES_MM, Component, Document
from .netlist import compute_nets, pin_ref_connects, symbol_resolver_for
from .project import is_terminal_symbol
from .render import component_text
from .symbols import LINE_WIDTHS
from .symbols.general import OFFPAGE_IDS

MM = 0.254                       # one OpenSchematix unit in KiCad: 10 mil, so the 10-unit grid is KiCad's 100 mil
GRID_MM = 2.54
SCH_VERSION = 20230121           # KiCad 7.0
SYM_VERSION = 20220914
LIBRARY = "OpenSchematix"
TEXT_SCALE = 0.72                # OpenSchematix sizes text by its em; KiCad by its capital height
_NS = uuid.UUID("5d0c8a4e-4b1e-4c55-9a3e-7f0e2c1b9d21")

# OpenSchematix's paper -> KiCad's name for it (KiCad's sizes are the same, landscape)
PAPERS = {"A4": "A4", "A3": "A3", "A2": "A2", "A1": "A1", "A0": "A0", "ANSI A": "A", "ANSI B": "B",
          "ANSI C": "C", "ANSI D": "D", "ANSI E": "E", "Letter": "USLetter", "Legal": "USLegal",
          "Tabloid": "USLedger"}


class KiCadError(Exception):
    """The project can't be written as KiCad files (the message says why)."""


# ================================================================ s-expressions
def _s(text) -> str:
    """A KiCad string: quoted, with backslash, quote and line breaks escaped."""
    t = str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\r\n", "\n").replace("\r", "\n")
    return '"' + t.replace("\n", "\\n") + '"'


def _n(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _q(v: float) -> float:
    """A drawing coordinate as OpenSchematix compares them (to 0.01 unit), so points it treats as the same are
    written as the same."""
    r = round(v, 2)
    return 0.0 if r == 0 else r


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", name).strip("_") or "symbol"


def _font(size_mm: float, *extra, bold: bool = False) -> str:
    size = _n(max(0.5, round(size_mm, 2)))
    tail = "".join(" " + e for e in extra if e)
    return f"(effects (font (size {size} {size}){' bold' if bold else ''}){tail})"


def _centre(t: dict):
    """The middle of a text item as OpenSchematix draws it (it places text by an anchor point)."""
    from .export import text_width
    (x, y), size, a = t["p"], t.get("size", 10), t.get("anchor", "c")
    w, h = text_width(t["s"], size, t.get("bold", False)), size * TEXT_SCALE
    if "w" in a:
        x += w / 2
    elif "e" in a:
        x -= w / 2
    if "n" in a:                 # as export.text_origin sets the baseline for each anchor
        y += h / 2
    elif "s" in a:
        y -= 0.21 * size + h / 2
    return x, y


_JUSTIFY = {"c": "", "n": "(justify top)", "s": "(justify bottom)", "e": "(justify right)", "w": "(justify left)",
            "ne": "(justify right top)", "nw": "(justify left top)", "se": "(justify right bottom)",
            "sw": "(justify left bottom)"}


def _stroke(width_units: float, dash: bool = False) -> str:
    return f"(stroke (width {_n(width_units * MM)}) (type {'dash' if dash else 'default'}))"


# ================================================================ symbols
@dataclass
class _Pin:
    name: str        # OpenSchematix terminal name
    number: str      # KiCad pin number: the terminal's designation, made unique in its symbol
    label: str
    x: float         # local units
    y: float
    dir: str


@dataclass
class _Lib:
    name: str
    prefix: str
    description: str
    keywords: str
    units: list = field(default_factory=list)       # [(prims, [_Pin])]
    show_numbers: bool = False

    def numbers(self) -> set:
        return {p.number for _prims, pins in self.units for p in pins}


_PIN_ANGLE = {"l": 0, "r": 180, "u": 270, "d": 90}   # KiCad: the way from the connection point to the body


def _lib_graphics(prims) -> list:
    out = []
    for p in prims:
        k = p.get("k")
        w = LINE_WIDTHS.get(p.get("w", "normal"), LINE_WIDTHS["normal"])
        if k in ("line", "poly"):
            pts = [(x * MM, -y * MM) for x, y in p["pts"]]
            if k == "poly" and pts:
                pts.append(pts[0])
            fill = "outline" if k == "poly" and p.get("fill") else "none"
            out.append(f"(polyline (pts {' '.join(f'(xy {_n(x)} {_n(y)})' for x, y in pts)}) "
                       f"{_stroke(w, p.get('dash', False))} (fill (type {fill})))")
        elif k == "circle":
            (cx, cy), r = p["c"], p["r"]
            fill = "outline" if p.get("fill") else "none"
            out.append(f"(circle (center {_n(cx * MM)} {_n(-cy * MM)}) (radius {_n(r * MM)}) "
                       f"{_stroke(w, p.get('dash', False))} (fill (type {fill})))")
        elif k == "text" and str(p.get("s", "")).strip():
            x, y = _centre(dict(p, size=p.get("size", 8)))
            out.append(f"(text {_s(p['s'])} (at {_n(x * MM)} {_n(-y * MM)} 0) {_font(p.get('size', 8) * MM * TEXT_SCALE)})")
        elif k == "region":
            from .regions import flatten_ring
            for ring in p.get("rings", []):
                pts = [(x * MM, -y * MM) for x, y in flatten_ring(ring)]
                if len(pts) >= 3:
                    pts.append(pts[0])
                    out.append(f"(polyline (pts {' '.join(f'(xy {_n(x)} {_n(y)})' for x, y in pts)}) "
                               f"(stroke (width 0) (type default)) (fill (type outline)))")
    return out


def _lib_text(lib: _Lib, full_name: str) -> str:
    """One symbol, as it appears in a library (``full_name`` without the library) or in a schematic's
    lib_symbols (with it)."""
    numbers = "" if lib.show_numbers else " (pin_numbers hide)"
    head = (f'(symbol {_s(full_name)}{numbers} (pin_names hide) (in_bom yes) (on_board yes)\n'
            f'    (property "Reference" {_s(lib.prefix)} (at 0 0 0) {_font(1.27)})\n'
            f'    (property "Value" {_s(lib.name)} (at 0 0 0) {_font(1.27, "hide")})\n'
            f'    (property "Footprint" "" (at 0 0 0) {_font(1.27, "hide")})\n'
            f'    (property "Datasheet" "" (at 0 0 0) {_font(1.27, "hide")})\n')
    if lib.description:
        head += f'    (property "ki_description" {_s(lib.description)} (at 0 0 0) {_font(1.27, "hide")})\n'
    if lib.keywords:
        head += f'    (property "ki_keywords" {_s(lib.keywords)} (at 0 0 0) {_font(1.27, "hide")})\n'
    body = []
    for unit, (prims, pins) in enumerate(lib.units, 1):
        items = _lib_graphics(prims)
        for p in pins:
            items.append(f"(pin passive line (at {_n(p.x * MM)} {_n(-p.y * MM)} {_PIN_ANGLE.get(p.dir, 0)}) (length 0) "
                         f"(name {_s(p.label)} {_font(1.27)}) (number {_s(p.number)} {_font(1.27)}))")
        body.append(f'    (symbol {_s(f"{lib.name}_{unit}_1")}\n      ' + "\n      ".join(items) + ")")
    return head + "\n".join(body) + ")"


# ================================================================ the plan of what goes where
@dataclass
class _Placed:
    doc: Document
    comp: Component
    lib: _Lib
    unit: int
    reference: str
    pins: dict            # terminal name -> pin number
    virtual: bool         # '#' reference: not a part (KiCad leaves it out of the BOM and the netlist)


@dataclass
class Export:
    """What ``plan`` worked out: the files to write and what was simplified."""
    files: dict                          # file name -> text
    notes: list
    pins: dict                           # (sheet uid, component id, terminal name) -> (reference, pin number)
    references: dict                     # (sheet uid, component id) -> reference
    links: set = field(default_factory=set)   # (sheet uid, component id) of sheet connectors, now global labels


def _reference_of(c: Component) -> str:
    """The reference OpenSchematix shows: the designator, or X1:3 for a terminal."""
    if is_terminal_symbol(c.symbol) and c.designator:
        return c.tag()
    return c.designator.strip()


def _variant(c: Component) -> str:
    """What makes two placed copies of one symbol different symbols in KiCad: parameters and pin designations."""
    labels = {t.name: c.terminal_label(t.name) for t in c.terminal_defs()}
    return json.dumps([c.params or {}, labels], sort_keys=True, default=str)


def _unit_pins(c: Component, used: set, unit: int, terminal_no: str = "") -> list:
    pins = []
    for t in c.terminal_defs():
        label = c.terminal_label(t.name) or t.name
        number = f"{terminal_no}.{label}" if terminal_no else label
        if number in used:
            number = f"{label}.{unit}"
        while number in used:
            number += "'"
        used.add(number)
        pins.append(_Pin(t.name, number, label, t.x, t.y, t.dir))
    return pins


@symbols.project_scoped
def plan(project, name: str) -> Export:
    """Everything ``write_project`` writes, worked out without touching the disk. ``name`` is the file name stem."""
    if not project.sheets:
        raise KiCadError("The project has no sheets.")
    notes = []
    show_all = bool(project.settings.get("show_terminal_labels"))
    libs: dict[str, _Lib] = {}
    by_variant: dict[tuple, _Lib] = {}
    placed: list[_Placed] = []
    labels: list[tuple] = []            # (doc, component) for sheet connectors with a label

    # group the parts: one KiCad symbol for each reference used more than once
    groups: dict[str, list] = {}
    for doc in project.sheets:
        for c in sorted(doc.components.values(), key=lambda c: c.id):
            ref = _reference_of(c)
            if c.symbol in OFFPAGE_IDS and (c.label or c.designator).strip():
                labels.append((doc, c))
                continue
            if ref and c.terminal_defs():
                groups.setdefault(ref, []).append((doc, c))

    def lib_named(base: str) -> str:
        n, k = _safe(base), 2
        while n in libs:
            n, k = f"{_safe(base)}_{k}", k + 1
        return n

    virtual_n = 0
    for doc in project.sheets:
        for c in sorted(doc.components.values(), key=lambda c: c.id):
            if c.symbol in OFFPAGE_IDS and (c.label or c.designator).strip():
                continue
            sd = c.symdef()
            ref = _reference_of(c)
            group = groups.get(ref) if ref and c.terminal_defs() else None
            if group and len(group) > 1:
                lib = libs.get("device:" + ref)
                if lib is None:
                    lib = _Lib(lib_named(ref + "_device"), re.sub(r"[0-9:.]+$", "", ref) or "U",
                               f"{ref}: one device drawn in {len(group)} places", "")
                    lib.show_numbers = show_all or any(cc.terminal_labels for _d, cc in group)
                    libs["device:" + ref] = lib
                    used = set()
                    for d, cc in group:
                        unit_pins = _unit_pins(cc, used, len(lib.units) + 1)
                        lib.units.append((cc.geometry().prims, unit_pins))
                        placed.append(_Placed(d, cc, lib, len(lib.units), ref,
                                              {p.name: p.number for p in unit_pins}, False))
                continue
            key = (c.symbol, _variant(c))
            lib = by_variant.get(key)
            if lib is None:
                base = c.symbol if sd is not None else "missing_" + c.symbol
                lib = _Lib(lib_named(base), (sd.prefix if sd else "") or "U", sd.description if sd else "",
                           " ".join(sd.keywords) if sd else "")
                lib.units.append((c.geometry().prims, _unit_pins(c, set(), 1)))
                lib.show_numbers = show_all or bool(c.terminal_labels)
                libs[lib.name] = by_variant[key] = lib
            pins = {p.name: p.number for p in lib.units[0][1]}
            if ref and c.terminal_defs():
                placed.append(_Placed(doc, c, lib, 1, ref, pins, False))
            else:
                virtual_n += 1
                placed.append(_Placed(doc, c, lib, 1, f"#OSX{virtual_n}", pins, True))
            if sd is None:
                notes.append(f"{c.designator or c.symbol}: its symbol ({c.symbol}) isn't available, so a placeholder "
                             f"was written. Wires attached to it by terminal name may not connect in KiCad.")

    nets = compute_nets(project)
    number_count: dict[str, int] = {}
    for n in nets:
        if n.number:
            number_count[n.number] = number_count.get(n.number, 0) + 1
    shared = sorted(k for k, v in number_count.items() if v > 1)
    if shared:
        notes.append("Wire numbers used by more than one net aren't net names in KiCad (they would join the nets): "
                     + ", ".join(shared[:10]) + ("…" if len(shared) > 10 else "") + ".")
    numbers = {}
    for n in nets:
        if n.number and number_count.get(n.number) == 1:
            for uid, wid in n.wires:
                numbers.setdefault(uid, {}).setdefault(n.number, []).append(wid)

    stem = _safe(name) if name else "schematic"
    root_uuid = _uuid(project, "root")
    files = {}
    multi = len(project.sheets) > 1
    sheet_files = []
    for i, doc in enumerate(project.sheets, 1):
        fname = f"{stem}.kicad_sch" if not multi else f"{stem}-{i}{'-' + _safe(doc.name)[:40] if doc.name else ''}.kicad_sch"
        sheet_uuid = _uuid(project, f"sheet:{doc.uid}")
        path = f"/{root_uuid}" if not multi else f"/{root_uuid}/{sheet_uuid}"
        own_uuid = root_uuid if not multi else _uuid(project, f"file:{doc.uid}")
        files[fname] = _sheet_text(project, doc, own_uuid, path, stem, [p for p in placed if p.doc is doc],
                                   [c for d, c in labels if d is doc], numbers.get(doc.uid, {}), libs,
                                   page=str(i if not multi else i + 1))
        sheet_files.append((doc, fname, sheet_uuid))
    if multi:
        files[f"{stem}.kicad_sch"] = _root_text(project, root_uuid, stem, sheet_files)
    files[f"{LIBRARY}.kicad_sym"] = ("(kicad_symbol_lib (version %d) (generator openschematix)\n  " % SYM_VERSION
                                     + "\n  ".join(_lib_text(l, l.name) for l in sorted(libs.values(), key=lambda l: l.name))
                                     + "\n)\n")
    if any(s.shapes for s in project.sheets) and any(sh.kind == "hatch" for s in project.sheets for sh in s.shapes.values()):
        notes.append("Solid fills are drawn as filled outlines.")
    if any(w.props for s in project.sheets for w in s.wires.values()):
        notes.append("Wire colours and cross-sections aren't kept: KiCad's wires have no such properties.")
    pin_map = {(pl.doc.uid, pl.comp.id, name): (pl.reference, number) for pl in placed for name, number in pl.pins.items()}
    return Export(files, notes, pin_map, {(pl.doc.uid, pl.comp.id): pl.reference for pl in placed},
                  {(d.uid, c.id) for d, c in labels})


def _uuid(project, key: str) -> str:
    return str(uuid.uuid5(_NS, f"{project.uid}|{key}"))


# ================================================================ one sheet
def _paper(doc: Document):
    """KiCad's paper for a sheet, its size in mm and where the drawing's origin goes on it."""
    s = doc.sheet
    wu, hu = s.size_units()
    w_mm, h_mm = wu * MM, hu * MM
    name = PAPERS.get(s.size)
    if name and s.scale_factor() == 1.0:
        pw, ph = SHEET_SIZES_MM[s.size]
        pw, ph = max(pw, ph), min(pw, ph)
        portrait = s.orientation == "portrait"
        if portrait:
            pw, ph = ph, pw
        ox = round((pw - w_mm) / 2 / GRID_MM) * GRID_MM
        oy = round((ph - h_mm) / 2 / GRID_MM) * GRID_MM
        return (f'(paper {_s(name)}{" portrait" if portrait else ""})', ox, oy)
    w = math.ceil(w_mm / GRID_MM) * GRID_MM
    h = math.ceil(h_mm / GRID_MM) * GRID_MM
    return (f'(paper "User" {_n(w)} {_n(h)})', 0.0, 0.0)


def _title_block(project, doc) -> str:
    from .titleblock import field_values
    f = field_values(doc, project)
    lines = [("title", f["title"] or doc.name), ("date", f["date"]), ("rev", f["revision"]),
             ("company", f["organisation"])]
    out = [f"({k} {_s(v)})" for k, v in lines if v]
    people = " · ".join(f"{who} {v}" for who, v in (("Drawn by", f["author"]), ("checked by", f["checked_by"]),
                                                    ("approved by", f["approved_by"])) if v)
    comments = [f"Drawing number {f['drawing_number']}" if f["drawing_number"] else "", people,
                f["client"] and f"Client: {f['client']}", f["subtitle"]]
    out += [f"(comment {i} {_s(c)})" for i, c in enumerate(comments, 1) if c]
    return "(title_block " + " ".join(out) + ")" if out else ""


def _sheet_text(project, doc, own_uuid, path, stem, placed, connectors, numbers, libs, page) -> str:
    paper, ox, oy = _paper(doc)

    def X(v):
        return _n(_q(v) * MM + ox)

    def Y(v):
        return _n(_q(v) * MM + oy)

    def pt(p):
        return f"(xy {X(p[0])} {Y(p[1])})"

    def uid(key):
        return _uuid(project, f"{doc.uid}:{key}")

    out = []
    used_libs = sorted({pl.lib.name for pl in placed})
    by_name = {l.name: l for l in libs.values()}
    lib_symbols = "\n    ".join(_lib_text(by_name[n], f"{LIBRARY}:{n}") for n in used_libs)

    # ---- wires: split wherever another wire ends on one, so every connection is an end on an end
    resolve, cache = symbol_resolver_for(doc), {}
    polylines = []
    for w in sorted(doc.wires.values(), key=lambda w: w.id):
        pts = [(_q(x), _q(y)) for x, y in w.points]
        if len(pts) < 2:
            continue
        for idx, ref in ((0, w.start), (-1, w.end)):
            if pin_ref_connects(doc, ref, resolve, cache):
                c = doc.components.get(ref[0])
                p = c.terminals().get(str(ref[1])) if c else None
                if p is not None:
                    pts[idx] = (_q(p[0]), _q(p[1]))
        polylines.append((w, pts))
    ends = sorted({p for _w, pts in polylines for p in (pts[0], pts[-1])})
    cells: dict = {}
    CELL = 40.0
    for p in ends:
        cells.setdefault((math.floor(p[0] / CELL), math.floor(p[1] / CELL)), []).append(p)
    segments = []          # (a, b, wire)
    for w, pts in polylines:
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            inner = set()
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            for cx in range(math.floor(x0 / CELL), math.floor(x1 / CELL) + 1):
                for cy in range(math.floor(y0 / CELL), math.floor(y1 / CELL) + 1):
                    for p in cells.get((cx, cy), ()):
                        if p != a and p != b and point_on_segment(p, a, b):
                            inner.add(p)
            chain = [a] + sorted(inner, key=lambda p: (p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) + [b]
            for p, q in zip(chain, chain[1:]):
                if p != q:
                    segments.append((p, q, w))
    for k, (a, b, w) in enumerate(segments):
        out.append(f"(wire (pts {pt(a)} {pt(b)}) (stroke (width 0) (type {'dash' if w.style == 'dashed' else 'default'})) "
                   f"(uuid {uid(f'wire:{w.id}:{k}')}))")
    for p in sorted({(_q(x), _q(y)) for x, y in analyse(doc).junctions}):
        out.append(f"(junction (at {X(p[0])} {Y(p[1])}) (diameter 0) (color 0 0 0 0) (uuid {uid(f'junction:{p}')}))")

    # ---- wire numbers as net names, on a point of the net's own wire that no other wire passes through
    by_wire: dict = {}
    for a, b, w in segments:
        by_wire.setdefault(w.id, []).append((a, b))
    for number, wids in sorted(numbers.items()):
        spot = None
        for wid in sorted(wids):
            for a, b in sorted(by_wire.get(wid, []), key=lambda s: -math.dist(s[0], s[1])):
                for f in (0.5, 0.25, 0.75, 0.375, 0.625):
                    p = (_q(a[0] + (b[0] - a[0]) * f), _q(a[1] + (b[1] - a[1]) * f))
                    if not any(o.id not in wids and point_on_segment(p, s, e)
                               for s, e, o in segments):
                        spot = (p, a, b)
                        break
                if spot:
                    break
            if spot:
                break
        if spot:
            (x, y), a, b = spot
            angle = 90 if abs(a[0] - b[0]) < 1e-9 else 0
            out.append(f"(label {_s(number)} (at {X(x)} {Y(y)} {angle}) {_font(1.27, '(justify left bottom)')} "
                       f"(uuid {uid(f'number:{number}')}))")

    # ---- sheet connectors: global labels, which join every label of the same name on every sheet
    for c in sorted(connectors, key=lambda c: c.id):
        text = (c.label or c.designator).strip()
        for tname, p in c.terminals().items():
            body = {"l": 0, "r": 180, "u": 270, "d": 90}.get(c.terminal_dirs().get(tname, "l"), 0)
            out.append(f"(global_label {_s(text)} (shape bidirectional) (at {X(p[0])} {Y(p[1])} {body}) "
                       f"(fields_autoplaced) {_font(1.27, '(justify left)' if body in (0, 90) else '(justify right)')} "
                       f"(uuid {uid(f'link:{c.id}:{tname}')}))")

    # ---- parts
    for pl in sorted(placed, key=lambda pl: pl.comp.id):
        out.append(_instance(project, doc, pl, X, Y, path, stem, uid))

    # ---- drafting
    for s in sorted(doc.shapes.values(), key=lambda s: s.id):
        out += _shape(s, X, Y, uid)

    head = (f"(kicad_sch (version {SCH_VERSION}) (generator openschematix)\n"
            f"  (uuid {own_uuid})\n  {paper}\n")
    tb = _title_block(project, doc)
    if tb:
        head += "  " + tb + "\n"
    head += f"  (lib_symbols\n    {lib_symbols})\n" if lib_symbols else "  (lib_symbols)\n"
    tail = f'  (sheet_instances (path "/" (page {_s(page)})))\n' if path.count("/") == 1 else ""
    return head + "  " + "\n  ".join(out) + "\n" + tail + ")\n"


def _orientation(c: Component):
    """KiCad's angle and mirror for a component: the one of KiCad's twelve whose transform puts every point of
    the symbol where OpenSchematix draws it."""
    from .geometry import xform
    want = [xform(1, 0, c.rotation, c.mirror), xform(0, 1, c.rotation, c.mirror)]
    for angle in (0, 90, 180, 270):
        for mirror in ("", "x", "y"):
            m = _kicad_transform(angle, mirror)
            # library points are (x, -y) of OpenSchematix's local ones
            got = [_apply(m, 1, 0), _apply(m, 0, -1)]
            if all(abs(g[0] - w[0]) < 1e-9 and abs(g[1] - w[1]) < 1e-9 for g, w in zip(got, want)):
                return angle, mirror
    return 0, ""


def _compose(m, t):
    x1, y1, x2, y2 = m
    a1, b1, a2, b2 = t
    return (x1 * a1 + x2 * b1, y1 * a1 + y2 * b1, x1 * a2 + x2 * b2, y1 * a2 + y2 * b2)


def _kicad_transform(angle: int, mirror: str):
    """KiCad's symbol transform (x1, y1, x2, y2) for an orientation, built as KiCad's SCH_SYMBOL::SetOrientation
    builds it: the default flips y, rotations turn it, a mirror comes last."""
    m = (1, 0, 0, -1)
    ccw, cw = (0, 1, -1, 0), (0, -1, 1, 0)
    if angle == 90:
        m = _compose(m, ccw)
    elif angle == 180:
        m = _compose(_compose(m, ccw), ccw)
    elif angle == 270:
        m = _compose(m, cw)
    if mirror == "x":
        m = _compose(m, (1, 0, 0, -1))
    elif mirror == "y":
        m = _compose(m, (-1, 0, 0, 1))
    return m


def _apply(m, x, y):
    x1, y1, x2, y2 = m
    return (x1 * x + y1 * y, x2 * x + y2 * y)


def _instance(project, doc, pl: _Placed, X, Y, path, stem, uid) -> str:
    c = pl.comp
    angle, mirror = _orientation(c)
    texts = {t["role"]: t for t in component_text(c)}
    sd = c.symdef()

    # KiCad turns a field with its symbol: a symbol turned a quarter keeps its fields level when they are
    # stored turned a quarter too. Centred text stays where it is under KiCad's mirroring, so each field is
    # centred on the middle of the text as OpenSchematix places it.
    level = 90 if _kicad_transform(angle, mirror)[1] else 0

    def field(name, value, role, hidden):
        t = texts.get(role)
        if t is None or hidden:
            x, y, size, bold = c.x, c.y, 10, False
            hidden = True
        else:
            (x, y), size, bold = _centre(t), t.get("size", 10), bool(t.get("bold"))
        return (f"(property {_s(name)} {_s(value)} (at {X(x)} {Y(y)} {level}) "
                f"{_font(size * MM * TEXT_SCALE, 'hide' if hidden else '', bold=bold)})")

    value = c.label or (sd.name if sd else c.symbol)
    props = [field("Reference", pl.reference, "designator", pl.virtual),
             field("Value", value, "text", not c.label),
             field("Footprint", "", None, True), field("Datasheet", "", None, True)]
    extra = [("Description", c.prop("description") or (sd.description if sd else "")),
             ("Manufacturer", c.prop("manufacturer")), ("Part number", c.prop("part_number")),
             ("Rating", c.prop("rating")), ("Terminal", c.prop("terminal")),
             ("OpenSchematix symbol", c.symbol)]
    extra += [(k, v) for k, v in sorted(c.props.items()) if k not in ("description", "manufacturer", "part_number",
                                                                         "rating", "terminal")]
    props += [field(k, v, None, True) for k, v in extra if v]
    in_bom = "yes" if c.in_bom and not pl.virtual else "no"
    mirror_s = f" (mirror {mirror})" if mirror else ""
    pins = " ".join(f"(pin {_s(n)} (uuid {uid(f'pin:{c.id}:{n}')}))" for n in pl.pins.values())
    return (f"(symbol (lib_id {_s(f'{LIBRARY}:{pl.lib.name}')}) (at {X(c.x)} {Y(c.y)} {angle}){mirror_s} "
            f"(unit {pl.unit}) (in_bom {in_bom}) (on_board {'no' if pl.virtual else 'yes'}) (dnp no) "
            f"(uuid {uid(f'part:{c.id}')})\n    " + "\n    ".join(props) + f"\n    {pins}\n"
            f"    (instances (project {_s(stem)} (path {_s(path)} (reference {_s(pl.reference)}) (unit {pl.unit})))))")


def _shape(s, X, Y, uid) -> list:
    """A drafting shape as KiCad drawing items."""
    from .shapes import shape_prims
    w = _stroke({"thin": 1.0, "normal": 1.4, "thick": 2.2}.get(s.width, 1.4), s.dash)
    if s.kind == "circle":
        fill = "outline" if s.fill else "none"
        return [f"(circle (center {X(s.c[0])} {Y(s.c[1])}) (radius {_n(s.r * MM)}) {w} (fill (type {fill})) "
                f"(uuid {uid(f'shape:{s.id}')}))"]
    if s.kind == "arc":
        a0, a1 = math.radians(s.start), math.radians(s.start + s.extent)
        am = (a0 + a1) / 2

        def at(a):
            return (s.c[0] + s.r * math.cos(a), s.c[1] - s.r * math.sin(a))
        (sx, sy), (mx, my), (ex, ey) = at(a0), at(am), at(a1)
        return [f"(arc (start {X(sx)} {Y(sy)}) (mid {X(mx)} {Y(my)}) (end {X(ex)} {Y(ey)}) {w} (fill (type none)) "
                f"(uuid {uid(f'shape:{s.id}')}))"]
    out = []
    for k, p in enumerate(shape_prims(s, item=s.id)):
        key = uid(f"shape:{s.id}:{k}")
        if p["k"] in ("line", "poly"):
            pts = list(p["pts"]) + ([p["pts"][0]] if p["k"] == "poly" else [])
            fill = "outline" if p.get("fill") else "none"
            out.append(f"(polyline (pts {' '.join(f'(xy {X(x)} {Y(y)})' for x, y in pts)}) "
                       f"{_stroke(p.get('wpx', 1.4), p.get('dash', False))} (fill (type {fill})) (uuid {key}))")
        elif p["k"] == "region":
            from .regions import flatten_ring
            for j, ring in enumerate(p.get("rings", [])):
                pts = flatten_ring(ring)
                if len(pts) >= 3:
                    pts = pts + [pts[0]]
                    out.append(f"(polyline (pts {' '.join(f'(xy {X(x)} {Y(y)})' for x, y in pts)}) "
                               f"(stroke (width 0) (type default)) (fill (type outline)) (uuid {uid(f'shape:{s.id}:{k}:{j}')}))")
        elif p["k"] == "text" and str(p.get("s", "")).strip():
            (x, y) = p["p"]
            angle = round((p.get("angle") or 0) / 90) * 90 % 360
            out.append(f"(text {_s(p['s'])} (at {X(x)} {Y(y)} {angle}) "
                       f"{_font(p.get('size', 10) * MM * TEXT_SCALE, _JUSTIFY.get(p.get('anchor', 'w'), ''))} (uuid {key}))")
    return out


# ================================================================ the root sheet of a project with several
def _root_text(project, root_uuid, stem, sheet_files) -> str:
    n = len(sheet_files)
    cols = 4 if n <= 16 else 6 if n <= 36 else math.ceil(math.sqrt(n))
    if n <= 16:
        paper = '(paper "A4")'
    elif n <= 36:
        paper = '(paper "A3")'
    else:
        rows = math.ceil(n / cols)
        paper = f'(paper "User" {_n(cols * 63.5 + 50.8)} {_n(rows * 38.1 + 50.8)})'
    out = []
    for i, (doc, fname, sheet_uuid) in enumerate(sheet_files):
        x, y = 25.4 + (i % cols) * 63.5, 25.4 + (i // cols) * 38.1
        out.append(f"(sheet (at {_n(x)} {_n(y)}) (size 50.8 25.4) (fields_autoplaced)\n"
                   f"    (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000)) (uuid {sheet_uuid})\n"
                   f"    (property \"Sheetname\" {_s(doc.name or f'Sheet {i + 1}')} (at {_n(x)} {_n(y - 0.7)} 0) "
                   f"{_font(1.27, '(justify left bottom)')})\n"
                   f"    (property \"Sheetfile\" {_s(fname)} (at {_n(x)} {_n(y + 26.0)} 0) "
                   f"{_font(1.27, '(justify left top)')})\n"
                   f"    (instances (project {_s(stem)} (path \"/{root_uuid}\" (page {_s(str(i + 2))})))))")
    meta = project.meta
    title = f"(title_block (title {_s(meta.get('title') or stem)}))"
    return (f"(kicad_sch (version {SCH_VERSION}) (generator openschematix)\n  (uuid {root_uuid})\n  {paper}\n"
            f"  {title}\n  (lib_symbols)\n  " + "\n  ".join(out) + '\n  (sheet_instances (path "/" (page "1")))\n)\n')


# ================================================================ writing
SYM_LIB_TABLE = "sym-lib-table"


def _lib_table_entry() -> str:
    return (f'  (lib (name {_s(LIBRARY)})(type "KiCad")(uri {_s("${KIPRJMOD}/" + LIBRARY + ".kicad_sym")})'
            f'(options "")(descr "Symbols from OpenSchematix"))\n')


def lib_table(existing: str | None) -> str | None:
    """The project's sym-lib-table with OpenSchematix's library in it: a new table, ``existing`` with the entry
    added, or None when it's already there (the file is left alone)."""
    if existing is None:
        return "(sym_lib_table\n  (version 7)\n" + _lib_table_entry() + ")\n"
    if re.search(r'\(name\s+"?' + re.escape(LIBRARY) + r'"?\s*\)', existing):
        return None
    end = existing.rstrip().rfind(")")
    if not existing.lstrip().startswith("(sym_lib_table") or end < 0:
        raise KiCadError(f"The folder's {SYM_LIB_TABLE} isn't one KiCad wrote, so it was left alone. "
                         f"Export to an empty folder.")
    return existing[:end].rstrip() + "\n" + _lib_table_entry() + ")\n"


def project_file(name: str) -> str:
    return json.dumps({"meta": {"filename": f"{name}.kicad_pro", "version": 1}}, indent=2) + "\n"


def files_to_replace(folder: str, export: Export, name: str) -> list:
    """The files an export would replace, besides the schematic the person picked."""
    picked = f"{_safe(name)}.kicad_sch"
    return sorted(f for f in export.files if f != picked and os.path.exists(os.path.join(folder, f)))


def write_project(project, path: str, export: Export | None = None) -> Export:
    """Write the project as KiCad files beside ``path`` (the root ``.kicad_sch``), from ``export`` when it was
    planned already. Every file is written whole or not at all; the folder's sym-lib-table is added to, never
    replaced, and a project file of the same name is left alone."""
    folder = os.path.dirname(os.path.abspath(path)) or "."
    name = _safe(os.path.splitext(os.path.basename(path))[0])
    export = export or plan(project, name)
    table_path = os.path.join(folder, SYM_LIB_TABLE)
    existing = None
    if os.path.exists(table_path):
        with open(table_path, encoding="utf-8", errors="replace") as f:
            existing = f.read()
    table = lib_table(existing)
    for fname, text in export.files.items():
        _atomic_write(os.path.join(folder, fname), text.encode("utf-8"))
    if table is not None:
        _atomic_write(table_path, table.encode("utf-8"))
    pro = os.path.join(folder, f"{name}.kicad_pro")
    if not os.path.exists(pro):
        _atomic_write(pro, project_file(name).encode("utf-8"))
    return export
