"""Projects: an ordered set of schematic sheets with shared metadata,
layers, settings and embedded custom symbols.

Designators (reference identifiers such as K1, Y2) are unique across the
whole project; terminal blocks are identified by strip + terminal number
(X1:3) instead. Object identity is (sheet uid, object id).
"""
from __future__ import annotations

import copy
import datetime as _dt
import re
from dataclasses import dataclass

from . import symbols
from .model import (DEFAULT_LAYER_COMPONENTS, DEFAULT_LAYER_SHAPES, DEFAULT_LAYER_WIRES, Document, new_uid)

META_FIELDS = (
    ("title", "Project title"), ("number", "Project number"), ("client", "Client"),
    ("organisation", "Organisation"), ("author", "Drawn by"), ("checked_by", "Checked by"),
    ("approved_by", "Approved by"), ("date", "Date"), ("revision", "Revision"), ("description", "Description"),
)

NUMBERING_SCHEMES = {
    "sequential": "Sequential across the project (1, 2, 3 …)",
    "sheet": "By sheet (sheet 2 → 201, 202 …)",
}
DEFAULT_SETTINGS = {
    "wire_numbering": {"scheme": "sequential", "prefix": "", "start": 1, "step": 1, "digits": 0},
    "show_wire_numbers": True,
    "show_terminal_labels": False,
    "xref_format": "/{sheet}.{zone}",
    "crossing_style": "bridge",      # bridge | gap | plain
    "junction_size": "medium",       # small | medium | large
}

TERMINAL_SYMBOLS = {"el.terminal"}


def is_terminal_symbol(symbol_id: str) -> bool:
    if symbol_id in TERMINAL_SYMBOLS:
        return True
    sd = symbols.get(symbol_id)
    return bool(sd and sd.is_custom and "terminal" in (t.lower() for t in sd.keywords))


@dataclass
class Layer:
    name: str
    color: str = ""          # "" = theme ink colour
    visible: bool = True
    locked: bool = False
    printable: bool = True

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d):
        return cls(name=str(d.get("name") or "Layer"), color=str(d.get("color", "") or ""),
                   visible=bool(d.get("visible", True)), locked=bool(d.get("locked", False)),
                   printable=bool(d.get("printable", True)))


def default_layers():
    return [Layer(DEFAULT_LAYER_COMPONENTS), Layer(DEFAULT_LAYER_WIRES), Layer(DEFAULT_LAYER_SHAPES),
            Layer("Notes"), Layer("Imported")]


class Project:
    def __init__(self, title: str = ""):
        self.uid = new_uid()
        self.meta = {k: "" for k, _ in META_FIELDS}
        self.meta["title"] = title
        self.meta["date"] = _dt.date.today().isoformat()
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        self.layers: list[Layer] = default_layers()
        self.sheets: list[Document] = []
        self.symbols: dict[str, dict] = {}     # embedded custom symbol documents
        self.created = _dt.datetime.now().isoformat(timespec="seconds")
        self.revisions = None                  # set by projectio (RevisionStore)

    # ---------------------------------------------------------------- sheets
    def _adopt(self, doc: Document) -> Document:
        doc.project = self
        while any(s.uid == doc.uid for s in self.sheets if s is not doc):
            doc.uid = new_uid()
        return doc

    def add_sheet(self, name: str | None = None, index: int | None = None, template: Document | None = None) -> Document:
        if template is not None:
            doc = template.copy()
            doc.uid = new_uid()
            doc.components.clear()
            doc.wires.clear()
            doc.shapes.clear()
            doc.next_id = 1
        else:
            doc = Document()
            if self.sheets:
                ref = self.sheets[-1].sheet
                doc.sheet.size, doc.sheet.orientation = ref.size, ref.orientation
                doc.sheet.title_block, doc.sheet.zones = ref.title_block, ref.zones
                doc.sheet.custom_w, doc.sheet.custom_h = ref.custom_w, ref.custom_h
        doc.name = name or self.unique_sheet_name("Sheet")
        doc.sheet.sheet = ""
        doc.sheet.drawing_number = ""
        self._adopt(doc)
        if index is None:
            self.sheets.append(doc)
        else:
            self.sheets.insert(max(0, min(index, len(self.sheets))), doc)
        return doc

    def unique_sheet_name(self, base: str) -> str:
        names = {s.name for s in self.sheets}
        n = len(self.sheets) + 1
        while f"{base} {n}" in names:
            n += 1
        return f"{base} {n}"

    def duplicate_sheet(self, uid: str) -> Document:
        src = self.sheet(uid)
        doc = src.copy()
        doc.uid = new_uid()
        doc.name = self.unique_sheet_name(src.name + " copy").rstrip()
        self._adopt(doc)
        # duplicated components need new designators (project-wide uniqueness)
        taken = self.used_designators(exclude_sheet=doc.uid)
        remap = {}
        for c in doc.components.values():
            if is_terminal_symbol(c.symbol) or not c.designator:
                continue
            sd = symbols.get(c.symbol)
            if c.designator in taken or c.designator in remap:
                if c.designator not in remap:
                    prefix = re.sub(r"\d+$", "", c.designator) or (sd.prefix if sd else "")
                    remap[c.designator] = next_free(prefix, taken)
                    taken.add(remap[c.designator])
                c.designator = remap[c.designator]
        for w in doc.wires.values():
            if not w.number_manual:
                w.number = ""
        self.sheets.insert(self.sheets.index(src) + 1, doc)
        return doc

    def delete_sheet(self, uid: str):
        if len(self.sheets) <= 1:
            raise ValueError("a project must contain at least one sheet")
        self.sheets.remove(self.sheet(uid))

    def move_sheet(self, uid: str, new_index: int):
        doc = self.sheet(uid)
        self.sheets.remove(doc)
        self.sheets.insert(max(0, min(new_index, len(self.sheets))), doc)

    def rename_sheet(self, uid: str, name: str):
        name = name.strip()
        if not name:
            raise ValueError("sheet name cannot be empty")
        self.sheet(uid).name = name

    def sheet(self, uid: str) -> Document:
        for s in self.sheets:
            if s.uid == uid:
                return s
        raise KeyError(uid)

    def find_sheet(self, uid: str):
        for s in self.sheets:
            if s.uid == uid:
                return s
        return None

    def sheet_number(self, doc: Document) -> int:
        return self.sheets.index(doc) + 1

    def sheet_number_text(self, doc: Document) -> str:
        if doc.sheet.sheet:
            return doc.sheet.sheet
        return f"{self.sheet_number(doc)} / {len(self.sheets)}"

    # ---------------------------------------------------------------- designators
    def used_designators(self, exclude_sheet: str | None = None) -> set:
        out = set()
        for s in self.sheets:
            if s.uid == exclude_sheet:
                continue
            for c in s.components.values():
                if c.designator and not is_terminal_symbol(c.symbol):
                    out.add(c.designator)
        return out

    def next_designator(self, prefix: str) -> str:
        return next_free(prefix, self.used_designators()) if prefix else ""

    def all_components(self):
        for s in self.sheets:
            for c in s.components.values():
                yield s, c

    def layer(self, name: str):
        for l in self.layers:
            if l.name == name:
                return l
        return None

    def ensure_layer(self, name: str) -> Layer:
        l = self.layer(name)
        if l is None:
            l = Layer(name)
            self.layers.append(l)
        return l

    def layer_names(self):
        return [l.name for l in self.layers]

    # ---------------------------------------------------------------- custom symbols
    def used_custom_symbols(self) -> set:
        return {c.symbol for _s, c in self.all_components() if c.symbol.startswith("user:")}

    def embed_symbols(self):
        """Store the definition of every custom symbol used in the project,
        so the project opens identically on another computer. Definitions
        already embedded are kept (the drawing keeps the version it was made
        with) unless the registry holds a newer project-level version."""
        used = self.used_custom_symbols()
        for sid in used:
            sd = symbols.get(sid)
            if sd is not None and sd.custom is not None:
                cur = self.symbols.get(sid)
                if cur is None or sd.custom.get("revision", 0) >= cur.get("revision", 0):
                    self.symbols[sid] = copy.deepcopy(sd.custom)
        for sid in list(self.symbols):
            if sid not in used:
                del self.symbols[sid]

    def activate_symbols(self) -> list:
        """Register the embedded symbols for this project. Returns warnings."""
        from .symbols.custom import SymbolFormatError, to_symdef
        defs, warnings = [], []
        for sid, doc in self.symbols.items():
            try:
                defs.append(to_symdef(doc))
            except SymbolFormatError as e:
                warnings.append(f"Embedded symbol {sid} could not be loaded: {e}")
        symbols.set_project_symbols(defs)
        return warnings

    # ---------------------------------------------------------------- serialisation
    def to_dict(self) -> dict:
        self.embed_symbols()
        return {
            "uid": self.uid,
            "created": self.created,
            "meta": dict(self.meta),
            "settings": copy.deepcopy(self.settings),
            "layers": [l.to_dict() for l in self.layers],
            "sheets": [s.to_dict(standalone=False) for s in self.sheets],
            "symbols": copy.deepcopy(self.symbols),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        p = cls()
        p.uid = str(d.get("uid") or new_uid())
        p.created = str(d.get("created") or p.created)
        meta = d.get("meta") or {}
        for k, _ in META_FIELDS:
            p.meta[k] = str(meta.get(k, "") or "")
        for k, v in meta.items():
            if k not in p.meta:
                p.meta[str(k)] = str(v)
        st = copy.deepcopy(DEFAULT_SETTINGS)
        for k, v in (d.get("settings") or {}).items():
            if k == "wire_numbering" and isinstance(v, dict):
                st[k].update({kk: vv for kk, vv in v.items() if kk in st[k]})
            elif k in st and isinstance(v, type(st[k])):
                st[k] = v
        p.settings = st
        if d.get("layers"):
            p.layers = [Layer.from_dict(x) for x in d["layers"] if isinstance(x, dict)]
            for name in (DEFAULT_LAYER_COMPONENTS, DEFAULT_LAYER_WIRES, DEFAULT_LAYER_SHAPES):
                p.ensure_layer(name)
        p.symbols = {str(k): v for k, v in (d.get("symbols") or {}).items() if isinstance(v, dict)}
        p.sheets = []
        for sd in d.get("sheets") or []:
            doc = Document.from_dict(sd)
            p._adopt(doc)
            p.sheets.append(doc)
        if not p.sheets:
            p.add_sheet("Sheet 1")
        # make sure every layer referenced by an object exists
        for s in p.sheets:
            for coll in (s.components, s.wires, s.shapes):
                for o in coll.values():
                    p.ensure_layer(o.layer)
        return p

    def copy(self) -> "Project":
        q = Project.from_dict(self.to_dict())
        q.revisions = self.revisions
        return q


def next_free(prefix: str, taken: set) -> str:
    n = 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


def new_project(title: str = "", size: str = "A3") -> Project:
    p = Project(title)
    doc = p.add_sheet("Sheet 1")
    doc.sheet.size = size
    return p


def project_from_document(doc: Document, title: str = "") -> Project:
    """Wrap a single drawing (legacy .osch) as a one-sheet project.
    Title-block fields that are project-wide move to the project metadata."""
    p = Project(title or doc.sheet.title)
    s = doc.sheet
    p.meta.update(title=s.title or title, organisation=s.organisation, author=s.author,
                  date=s.date or p.meta["date"], revision=s.revision)
    s.organisation = s.author = ""
    if s.sheet in ("1 / 1", "1/1"):
        s.sheet = ""
    if not doc.name or doc.name == "Sheet 1":
        doc.name = "Sheet 1"
    p._adopt(doc)
    p.sheets = [doc]
    return p
