"""Schematic document model (no GUI dependencies).

Object identity
---------------
Every object on a sheet (component, wire, shape) has an integer id that is
unique within its sheet and never reused while the sheet exists; ids are
written to the file, so they persist across sessions. Each sheet has a
persistent ``uid`` (random hex) that is unique within the project, so the pair
``(sheet.uid, object.id)`` identifies any object in a project permanently.
Revision comparison, search navigation and cross-sheet references are all
based on these identifiers, never on screen coordinates.

A :class:`Document` is one schematic sheet. A :class:`~openschematix.project.Project`
holds an ordered list of sheets plus project-wide metadata.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Optional

from . import symbols
from .geometry import Point, bbox_of, bbox_union, clean, norm_rotation, simplify_orthogonal, xform

# ---------------------------------------------------------------- sheet sizes
# (width, height) in millimetres, landscape.
SHEET_SIZES_MM = {
    "A0": (1189, 841), "A1": (841, 594), "A2": (594, 420), "A3": (420, 297), "A4": (297, 210),
    "ANSI A": (279.4, 215.9), "ANSI B": (431.8, 279.4), "ANSI C": (558.8, 431.8),
    "ANSI D": (863.6, 558.8), "ANSI E": (1117.6, 863.6),
    "Letter": (279.4, 215.9), "Legal": (355.6, 215.9), "Tabloid": (431.8, 279.4),
}
SHEET_SIZE_GROUPS = (("ISO A-series", ("A0", "A1", "A2", "A3", "A4")),
                     ("ANSI", ("ANSI A", "ANSI B", "ANSI C", "ANSI D", "ANSI E")),
                     ("North American", ("Letter", "Legal", "Tabloid")))
CUSTOM_SIZE = "Custom"
WIRE_STYLES = ("solid", "dashed")
TEXT_SIDES = ("auto", "above", "below", "left", "right")
TITLE_BLOCKS = ("standard", "compact", "iso", "none")
TITLE_BLOCK_NAMES = {"standard": "Standard", "compact": "Compact", "iso": "ISO 7200 style", "none": "None"}

# Standard component property keys (anything else in Component.props is a
# user-defined custom property).
STANDARD_PROPS = ("description", "manufacturer", "part_number", "rating", "terminal")
PROP_LABELS = {"description": "Description", "manufacturer": "Manufacturer", "part_number": "Part number",
               "rating": "Rating", "terminal": "Terminal no."}

DEFAULT_LAYER_COMPONENTS = "Components"
DEFAULT_LAYER_WIRES = "Wires"
DEFAULT_LAYER_SHAPES = "Drafting"


def new_uid() -> str:
    return uuid.uuid4().hex[:16]


def _str_dict(d) -> dict:
    if not isinstance(d, dict):
        return {}
    return {str(k): str(v) for k, v in d.items() if v is not None}


# ================================================================ component
@dataclass
class Component:
    id: int
    symbol: str
    x: float
    y: float
    rotation: int = 0
    mirror: bool = False
    designator: str = ""
    label: str = ""
    params: dict = field(default_factory=dict)
    text_side: str = "auto"   # auto | above | below | left | right
    props: dict = field(default_factory=dict)            # str -> str (see STANDARD_PROPS)
    terminal_labels: dict = field(default_factory=dict)  # terminal name -> displayed identifier
    layer: str = DEFAULT_LAYER_COMPONENTS
    locked: bool = False
    group: str = ""
    in_bom: bool = True

    def geometry(self):
        return symbols.geometry(self.symbol, self.params or None)

    def symdef(self):
        return symbols.get(self.symbol)

    def local_to_world(self, x, y) -> Point:
        dx, dy = xform(x, y, self.rotation, self.mirror)
        return (clean(self.x + dx), clean(self.y + dy))

    def terminals(self) -> dict[str, Point]:
        return {t.name: self.local_to_world(t.x, t.y) for t in self.geometry().terminals}

    def terminal_defs(self):
        return list(self.geometry().terminals)

    def terminal_label(self, name: str) -> str:
        """Displayed identifier of a terminal (user override, symbol label, or key)."""
        if self.terminal_labels.get(name):
            return self.terminal_labels[name]
        for t in self.geometry().terminals:
            if t.name == name:
                return t.label or t.name
        return name

    def terminal_dirs(self) -> dict[str, str]:
        out = {}
        vec = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}
        for t in self.geometry().terminals:
            dx, dy = xform(*vec[t.dir], self.rotation, self.mirror)
            out[t.name] = "l" if dx < -0.5 else "r" if dx > 0.5 else "u" if dy < -0.5 else "d"
        return out

    def bbox(self):
        b = self.geometry().bbox()
        pts = [self.local_to_world(x, y) for x, y in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
        return bbox_of(pts)

    def prop(self, key: str) -> str:
        return self.props.get(key, "")

    def tag(self) -> str:
        """Reference used in reports: designator, plus terminal number for terminal blocks."""
        t = self.props.get("terminal", "")
        if self.designator and t:
            return f"{self.designator}:{t}"
        return self.designator or "?"

    def to_dict(self):
        d = {"id": self.id, "symbol": self.symbol, "x": self.x, "y": self.y, "rotation": self.rotation,
             "mirror": self.mirror, "designator": self.designator, "label": self.label}
        if self.params:
            d["params"] = copy.deepcopy(self.params)
        if self.text_side != "auto":
            d["text_side"] = self.text_side
        if self.props:
            d["props"] = dict(self.props)
        if self.terminal_labels:
            d["terminal_labels"] = dict(self.terminal_labels)
        if self.layer != DEFAULT_LAYER_COMPONENTS:
            d["layer"] = self.layer
        if self.locked:
            d["locked"] = True
        if self.group:
            d["group"] = self.group
        if not self.in_bom:
            d["in_bom"] = False
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(id=int(d["id"]), symbol=str(d["symbol"]), x=float(d["x"]), y=float(d["y"]),
                   rotation=norm_rotation(d.get("rotation", 0)), mirror=bool(d.get("mirror", False)),
                   designator=str(d.get("designator", "")), label=str(d.get("label", "")),
                   params=copy.deepcopy(d.get("params") or {}),
                   text_side=d.get("text_side", "auto") if d.get("text_side") in TEXT_SIDES else "auto",
                   props=_str_dict(d.get("props")), terminal_labels=_str_dict(d.get("terminal_labels")),
                   layer=str(d.get("layer") or DEFAULT_LAYER_COMPONENTS), locked=bool(d.get("locked", False)),
                   group=str(d.get("group", "") or ""), in_bom=bool(d.get("in_bom", True)))


# ================================================================ wire
@dataclass
class Wire:
    """An orthogonal polyline. `start`/`end` optionally reference a component
    terminal as [component_id, terminal_name]; the end point coordinates are
    kept in sync with that terminal when components move.

    Wire numbers belong to nets: every wire of a net carries the same
    ``number``. ``number_manual`` marks a number typed by the user; automatic
    numbering never changes it."""
    id: int
    points: list
    start: Optional[list] = None
    end: Optional[list] = None
    style: str = "solid"
    auto: bool = False   # path was generated by the router (re-route freely)
    number: str = ""
    number_manual: bool = False
    props: dict = field(default_factory=dict)   # e.g. colour, cross-section
    layer: str = DEFAULT_LAYER_WIRES
    locked: bool = False
    group: str = ""

    def bbox(self):
        return bbox_of(self.points)

    def to_dict(self):
        d = {"id": self.id, "points": [[p[0], p[1]] for p in self.points], "start": self.start,
             "end": self.end, "style": self.style}
        if self.auto:
            d["auto"] = True
        if self.number:
            d["number"] = self.number
        if self.number_manual:
            d["number_manual"] = True
        if self.props:
            d["props"] = dict(self.props)
        if self.layer != DEFAULT_LAYER_WIRES:
            d["layer"] = self.layer
        if self.locked:
            d["locked"] = True
        if self.group:
            d["group"] = self.group
        return d

    @classmethod
    def from_dict(cls, d):
        pts = [(float(p[0]), float(p[1])) for p in d["points"]]
        if len(pts) < 2:
            raise ValueError(f"wire {d.get('id')} has fewer than two points")

        def ref(r):
            if r is None:
                return None
            return [int(r[0]), str(r[1])]
        style = d.get("style", "solid")
        return cls(id=int(d["id"]), points=simplify_orthogonal(pts), start=ref(d.get("start")), end=ref(d.get("end")),
                   style=style if style in WIRE_STYLES else "solid", auto=bool(d.get("auto", False)),
                   number=str(d.get("number", "") or ""), number_manual=bool(d.get("number_manual", False)),
                   props=_str_dict(d.get("props")), layer=str(d.get("layer") or DEFAULT_LAYER_WIRES),
                   locked=bool(d.get("locked", False)), group=str(d.get("group", "") or ""))


# ================================================================ shape
SHAPE_KINDS = ("line", "polyline", "polygon", "rect", "circle", "arc", "text")
SHAPE_WIDTHS = ("thin", "normal", "thick")


@dataclass
class Shape:
    """A free drafting primitive on a sheet (not part of the connectivity
    model). Geometry is stored in world drawing units:

      line/polyline/polygon/rect: pts  (rect = 4 corner points, kept rectangular)
      circle: c, r
      arc:    c, r, start, extent    (degrees, counter-clockwise on screen, 0 = +x)
      text:   p, s, size, anchor, angle
    """
    id: int
    kind: str
    pts: list = field(default_factory=list)
    c: tuple = (0.0, 0.0)
    r: float = 0.0
    start: float = 0.0
    extent: float = 90.0
    s: str = ""
    size: float = 10.0
    anchor: str = "w"
    angle: float = 0.0
    width: str = "normal"
    dash: bool = False
    fill: bool = False
    layer: str = DEFAULT_LAYER_SHAPES
    locked: bool = False
    group: str = ""

    def bbox(self):
        from .shapes import shape_bbox
        return shape_bbox(self)

    def to_dict(self):
        d = {"id": self.id, "kind": self.kind}
        if self.kind in ("line", "polyline", "polygon", "rect"):
            d["pts"] = [[clean(x), clean(y)] for x, y in self.pts]
        elif self.kind == "circle":
            d.update(c=[clean(self.c[0]), clean(self.c[1])], r=clean(self.r))
        elif self.kind == "arc":
            d.update(c=[clean(self.c[0]), clean(self.c[1])], r=clean(self.r), start=clean(self.start),
                     extent=clean(self.extent))
        elif self.kind == "text":
            d.update(p=[clean(self.pts[0][0]), clean(self.pts[0][1])], s=self.s, size=self.size, anchor=self.anchor)
            if self.angle:
                d["angle"] = self.angle
        if self.width != "normal":
            d["width"] = self.width
        if self.dash:
            d["dash"] = True
        if self.fill:
            d["fill"] = True
        if self.layer != DEFAULT_LAYER_SHAPES:
            d["layer"] = self.layer
        if self.locked:
            d["locked"] = True
        if self.group:
            d["group"] = self.group
        return d

    @classmethod
    def from_dict(cls, d):
        kind = d.get("kind")
        if kind not in SHAPE_KINDS:
            raise ValueError(f"unknown shape kind {kind!r}")
        s = cls(id=int(d["id"]), kind=kind)
        if kind in ("line", "polyline", "polygon", "rect"):
            s.pts = [(float(p[0]), float(p[1])) for p in d["pts"]]
            if len(s.pts) < 2:
                raise ValueError(f"shape {s.id} has fewer than two points")
        elif kind in ("circle", "arc"):
            s.c = (float(d["c"][0]), float(d["c"][1]))
            s.r = float(d["r"])
            if kind == "arc":
                s.start, s.extent = float(d.get("start", 0)), float(d.get("extent", 90))
        else:
            s.pts = [(float(d["p"][0]), float(d["p"][1]))]
            s.s = str(d.get("s", ""))
            s.size = float(d.get("size", 10))
            s.anchor = str(d.get("anchor", "w"))
            s.angle = float(d.get("angle", 0))
        w = d.get("width", "normal")
        s.width = w if w in SHAPE_WIDTHS else "normal"
        s.dash, s.fill = bool(d.get("dash", False)), bool(d.get("fill", False))
        s.layer = str(d.get("layer") or DEFAULT_LAYER_SHAPES)
        s.locked = bool(d.get("locked", False))
        s.group = str(d.get("group", "") or "")
        return s


# ================================================================ sheet setup
@dataclass
class Sheet:
    """Page setup and title-block fields of one sheet. Empty title-block
    fields fall back to the project's metadata when rendered."""
    size: str = "A3"
    orientation: str = "landscape"
    title: str = ""
    drawing_number: str = ""
    revision: str = ""
    author: str = ""
    date: str = ""
    organisation: str = ""
    sheet: str = ""            # legacy free text "1 / 1"; empty = automatic numbering
    show_title_block: bool = True
    title_block: str = "standard"
    zones: bool = True         # grid reference zones (A,B,C… / 1,2,3…) on the frame
    scale: str = "1:1"         # presentation scale (paper : drawing)
    custom_w: float = 420.0    # mm, used when size == "Custom"
    custom_h: float = 297.0
    checked_by: str = ""
    approved_by: str = ""
    description: str = ""

    def size_mm(self):
        if self.size == CUSTOM_SIZE:
            w, h = max(50.0, self.custom_w), max(50.0, self.custom_h)
            return (w, h)   # custom sizes are used exactly as entered
        w, h = SHEET_SIZES_MM.get(self.size, SHEET_SIZES_MM["A3"])
        if self.orientation == "portrait":
            return (min(w, h), max(w, h))
        return (max(w, h), min(w, h))

    def paper_units(self):
        """Paper size in drawing units at 1:1."""
        from .geometry import UNIT_MM
        w, h = self.size_mm()
        return (w / UNIT_MM, h / UNIT_MM)

    def scale_factor(self) -> float:
        """Paper length per model length (e.g. 0.5 for 1:2)."""
        return parse_scale(self.scale)

    def size_units(self):
        """Sheet extent in *model* units: the paper size divided by the
        presentation scale. At 1:2 the frame is twice as large around the
        drawing, so the drawing prints at half size."""
        w, h = self.paper_units()
        f = self.scale_factor()
        return (w / f, h / f)

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d):
        s = cls()
        for k, v in (d or {}).items():
            if hasattr(s, k):
                cur = getattr(s, k)
                try:
                    if isinstance(cur, bool):
                        setattr(s, k, bool(v))
                    else:
                        setattr(s, k, type(cur)(v))
                except (TypeError, ValueError):
                    pass
        if s.size not in SHEET_SIZES_MM and s.size != CUSTOM_SIZE:
            s.size = "A3"
        if s.orientation not in ("landscape", "portrait"):
            s.orientation = "landscape"
        if s.title_block not in TITLE_BLOCKS:
            s.title_block = "standard"
        if not s.show_title_block:
            s.title_block = "none"
        try:
            parse_scale(s.scale)
        except ValueError:
            s.scale = "1:1"
        return s


STANDARD_SCALES = ("10:1", "5:1", "2:1", "1:1", "1:2", "1:2.5", "1:5", "1:10", "1:20", "1:25", "1:50", "1:100")


def parse_scale(text: str) -> float:
    """'1:2' -> 0.5, '2:1' -> 2.0, '0.75' -> 0.75. Raises ValueError."""
    t = str(text).strip().replace(" ", "")
    if ":" in t:
        a, b = t.split(":", 1)
        a, b = float(a), float(b)
    else:
        a, b = float(t), 1.0
    if a <= 0 or b <= 0:
        raise ValueError("scale must be positive")
    f = a / b
    if not (0.001 <= f <= 1000):
        raise ValueError("scale out of range")
    return f


def format_scale(f: float) -> str:
    for s in STANDARD_SCALES:
        if abs(parse_scale(s) - f) < 1e-9:
            return s
    if f >= 1:
        return f"{f:g}:1"
    return f"1:{1 / f:.4g}"


# ================================================================ document (one sheet)
class Document:
    """One schematic sheet."""

    def __init__(self, name: str = "Sheet 1", uid: str | None = None):
        self.uid = uid or new_uid()
        self.name = name
        self.components: dict[int, Component] = {}
        self.wires: dict[int, Wire] = {}
        self.shapes: dict[int, Shape] = {}
        self.sheet = Sheet()
        self.next_id = 1
        self.project = None    # owning Project (set by Project), for project-wide designators

    # ---------------------------------------------------------------- ids
    def new_id(self) -> int:
        i = self.next_id
        self.next_id += 1
        return i

    def _taken(self, i) -> bool:
        return i in self.components or i in self.wires or i in self.shapes

    def add_component(self, comp: Component) -> Component:
        if self._taken(comp.id):
            comp.id = self.new_id()
        self.next_id = max(self.next_id, comp.id + 1)
        self.components[comp.id] = comp
        return comp

    def add_wire(self, wire: Wire) -> Wire:
        if self._taken(wire.id):
            wire.id = self.new_id()
        self.next_id = max(self.next_id, wire.id + 1)
        self.wires[wire.id] = wire
        return wire

    def add_shape(self, shape: Shape) -> Shape:
        if self._taken(shape.id):
            shape.id = self.new_id()
        self.next_id = max(self.next_id, shape.id + 1)
        self.shapes[shape.id] = shape
        return shape

    # ---------------------------------------------------------------- queries
    def item(self, ident):
        return self.components.get(ident) or self.wires.get(ident) or self.shapes.get(ident)

    def all_ids(self):
        return set(self.components) | set(self.wires) | set(self.shapes)

    def bbox(self):
        b = None
        for c in self.components.values():
            b = bbox_union(b, c.bbox())
        for w in self.wires.values():
            b = bbox_union(b, w.bbox())
        for s in self.shapes.values():
            b = bbox_union(b, s.bbox())
        return b

    def terminal_pos(self, ref):
        if not ref:
            return None
        c = self.components.get(ref[0])
        if not c:
            return None
        return c.terminals().get(ref[1])

    def used_designators(self) -> set[str]:
        own = {c.designator for c in self.components.values() if c.designator}
        if self.project is not None:
            from .project import is_terminal_symbol
            own = {c.designator for c in self.components.values()
                   if c.designator and not is_terminal_symbol(c.symbol)}
            return own | self.project.used_designators(exclude_sheet=self.uid)
        return own

    def next_designator(self, prefix: str, taken: Optional[set] = None) -> str:
        if not prefix:
            return ""
        taken = self.used_designators() if taken is None else taken
        n = 1
        while f"{prefix}{n}" in taken:
            n += 1
        return f"{prefix}{n}"

    # ---------------------------------------------------------------- serialisation
    def to_dict(self, standalone: bool = True):
        from . import FILE_FORMAT, VERSION
        d = {}
        if standalone:
            d.update(format=FILE_FORMAT, schema=SHEET_SCHEMA, app_version=VERSION)
        d.update({
            "uid": self.uid,
            "name": self.name,
            "next_id": self.next_id,
            "sheet": self.sheet.to_dict(),
            "components": [c.to_dict() for c in self.components.values()],
            "wires": [w.to_dict() for w in self.wires.values()],
        })
        if self.shapes:
            d["shapes"] = [s.to_dict() for s in self.shapes.values()]
        return d

    @classmethod
    def from_dict(cls, d) -> "Document":
        doc = cls(name=str(d.get("name") or "Sheet 1"), uid=str(d.get("uid") or new_uid()))
        doc.sheet = Sheet.from_dict(d.get("sheet"))
        for cd in d.get("components", []):
            c = Component.from_dict(cd)
            if doc._taken(c.id):
                raise ValueError(f"duplicate object id {c.id}")
            doc.components[c.id] = c
        for wd in d.get("wires", []):
            w = Wire.from_dict(wd)
            if doc._taken(w.id):
                raise ValueError(f"duplicate object id {w.id}")
            doc.wires[w.id] = w
        for sd in d.get("shapes", []) or []:
            s = Shape.from_dict(sd)
            if doc._taken(s.id):
                raise ValueError(f"duplicate object id {s.id}")
            doc.shapes[s.id] = s
        ids = doc.all_ids()
        doc.next_id = max(max(ids, default=0) + 1, int(d.get("next_id", 1) or 1))
        # Drop dangling terminal references instead of failing.
        for w in doc.wires.values():
            for attr in ("start", "end"):
                ref = getattr(w, attr)
                if ref and doc.terminal_pos(ref) is None:
                    setattr(w, attr, None)
        return doc

    def copy(self) -> "Document":
        return Document.from_dict(self.to_dict())


# Schema of one sheet's JSON (the .osch "schema" number). 1 = OpenSchematix
# legacy single-drawing files; 2 = 1.0 sheets (shapes, props, layers, uid).
SHEET_SCHEMA = 2
