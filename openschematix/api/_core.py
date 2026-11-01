"""Implementation of the public scripting API (see ``openschematix.api``).

Everything here delegates to the existing engine: placement and wiring to
``editing``, file I/O to ``projectio``, connection analysis to
``connectivity`` / ``netlist``, the BOM to ``bom`` and checking to ``check``.
This module adds argument validation (so invalid input raises instead of
being silently corrected) and stable, documented return types. It never
imports tkinter.
"""
from __future__ import annotations

import copy
import math
import weakref
import zipfile
from typing import Iterable, Optional, Union

from .. import PROJECT_EXTENSION, bom as _bom, check as _check, editing, netlist, projectio, symbols as _symbols
from ..connectivity import analyse
from ..geometry import GRID, is_orthogonal
from ..model import SHEET_SIZES_MM, WIRE_STYLES, Component as _Component, Document, Wire as _Wire
from ..project import Project as _Project, is_terminal_symbol, new_project as _new_project
from ..symbols.base import SymbolDef, validate_geometry
from ..symbols.general import UNKNOWN_ID
from .errors import InvalidOperationError, ObjectNotFoundError, ProjectFileError, SymbolNotFoundError
from .types import (BomItem, Issue, Net, Point, SheetConnectivity, SymbolInfo, SymbolTerminal, Terminal,
                    TerminalRef)

ROTATIONS = (0, 90, 180, 270)

# ---------------------------------------------------------------- symbol registry activation
# The symbol registry is process-wide: opening a project registers the custom
# symbols embedded in it. Every API entry point re-activates its own project
# first, so scripts can work with several projects at once.
_active: Optional[weakref.ref] = None


def _activate(p: _Project) -> None:
    global _active
    if _active is None or _active() is not p:
        p.activate_symbols()
        _active = weakref.ref(p)


def _invalidate() -> None:
    global _active
    _active = None


# ---------------------------------------------------------------- validation helpers
def _num(v, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise InvalidOperationError(f"{what} must be a finite number, got {v!r}")
    return float(v)


def _on_grid(x, y, what: str) -> Point:
    x, y = _num(x, f"{what} x"), _num(y, f"{what} y")
    for v in (x, y):
        if abs(v / GRID - round(v / GRID)) > 1e-9:
            raise InvalidOperationError(
                f"{what} ({x:g}, {y:g}) is not on the {GRID:g}-unit grid; terminals must land on grid points "
                f"so wires can connect (use multiples of {GRID:g})")
    return (x, y)


def _rotation(r) -> int:
    if isinstance(r, bool) or not isinstance(r, (int, float)) or r not in ROTATIONS:
        raise InvalidOperationError(f"rotation must be one of {ROTATIONS} degrees, got {r!r}")
    return int(r)


def _bool(v, what: str) -> bool:
    if not isinstance(v, bool):
        raise InvalidOperationError(f"{what} must be True or False, got {v!r}")
    return v


def _text(v, what: str, allow_empty: bool = True) -> str:
    if not isinstance(v, str):
        raise InvalidOperationError(f"{what} must be a string, got {v!r}")
    if any(ch in v for ch in "\r\n\t\x00"):
        raise InvalidOperationError(f"{what} must be a single line of text")
    v = v.strip()
    if not v and not allow_empty:
        raise InvalidOperationError(f"{what} cannot be empty")
    return v


def _properties(props) -> dict:
    if not isinstance(props, dict):
        raise InvalidOperationError(f"properties must be a dict of str to str, got {props!r}")
    out = {}
    for k, v in props.items():
        key = _text(k, "property name", allow_empty=False)
        out[key] = _text(v, f"property {key!r}")
    return out


def _symbol(sid) -> SymbolDef:
    if not isinstance(sid, str) or not sid:
        raise SymbolNotFoundError(f"symbol identifier must be a non-empty string, got {sid!r}")
    sd = _symbols.get(sid)
    if sd is None or sid == UNKNOWN_ID:
        raise SymbolNotFoundError(
            f"unknown symbol {sid!r}; use openschematix.api.list_symbols() to find valid identifiers "
            "(custom symbols need load_user_library() or must be embedded in the project)")
    return sd


def _validate_params(sd: SymbolDef, changes, base: Optional[dict] = None) -> dict:
    """Full parameter dict for `sd` after applying `changes` to `base` (the
    current or default parameters). Raises InvalidOperationError for unknown
    keys or values the symbol would otherwise silently replace."""
    if not isinstance(changes, dict):
        raise InvalidOperationError(f"params must be a dict, got {changes!r}")
    if not sd.parametric:
        if changes:
            raise InvalidOperationError(f"symbol {sd.id} has no parameters")
        return {}
    unknown = sorted(set(changes) - set(sd.default_params))
    if unknown:
        raise InvalidOperationError(f"symbol {sd.id} has no parameter(s) {', '.join(unknown)}; "
                                    f"valid: {', '.join(sorted(sd.default_params))}")
    merged = copy.deepcopy(base if base is not None else sd.default_params)
    for k, v in sd.default_params.items():
        merged.setdefault(k, copy.deepcopy(v))
    merged.update(copy.deepcopy(changes))
    from ..symbols import fluid
    if sd.builder is fluid.build_valve:
        _validate_valve(sd, changes, merged, fluid)
    else:
        for k, v in merged.items():
            d = sd.default_params.get(k)
            if d is not None and type(v) is not type(d):
                raise InvalidOperationError(f"parameter {k!r} must be a {type(d).__name__}, got {v!r}")
    try:
        g = sd.build(merged)
    except Exception as e:      # a builder rejecting its input
        raise InvalidOperationError(f"invalid parameters for {sd.id}: {e}") from e
    problems = validate_geometry(g)
    if problems:
        raise InvalidOperationError(f"parameters for {sd.id} give an invalid symbol: {'; '.join(problems)}")
    return merged


def _validate_valve(sd, changes, merged, fluid) -> None:
    medium = sd.default_params.get("medium")
    if merged.get("medium") != medium:
        raise InvalidOperationError(f"{sd.id} is a {medium} valve; its medium cannot be changed "
                                    f"(use {'fl.pneu.dcv' if medium == 'hyd' else 'fl.hyd.dcv'})")
    types = fluid.VALVE_TYPES[medium]
    if merged.get("type") not in types:
        raise InvalidOperationError(f"valve type must be one of {', '.join(types)}, got {merged.get('type')!r}")
    nports, npos = types[merged["type"]]
    if "type" in changes and "positions" not in changes:
        merged["positions"] = fluid.default_valve_params(medium, merged["type"])["positions"]
    pos = merged.get("positions")
    patterns = fluid.PATTERNS[nports]
    if not isinstance(pos, list) or len(pos) != npos or any(p not in patterns for p in pos):
        raise InvalidOperationError(f"a {merged['type']} valve needs {npos} positions, each one of "
                                    f"{', '.join(patterns)}; got {pos!r}")
    for side in ("left", "right"):
        ops = merged.get(side)
        if not isinstance(ops, list) or any(o not in fluid.OPERATORS for o in ops):
            raise InvalidOperationError(f"{side} operators must be a list of {', '.join(fluid.OPERATORS)}; "
                                        f"got {ops!r}")


def _layer_locked(project: _Project, obj) -> bool:
    lay = project.layer(obj.layer)
    return bool(getattr(obj, "locked", False) or (lay is not None and lay.locked))


# ---------------------------------------------------------------- symbol library
def _symbol_info(sd: SymbolDef) -> SymbolInfo:
    g = sd.build()
    terms = tuple(SymbolTerminal(t.name, t.label or t.name, float(t.x), float(t.y), t.dir, sd.port_type(t))
                  for t in g.terminals)
    return SymbolInfo(sd.id, sd.name, sd.category, sd.group, sd.convention, sd.description, sd.prefix,
                      sd.parametric, copy.deepcopy(sd.default_params), terms, sd.is_custom)


def list_symbols(query: str = "", category: Optional[str] = None) -> list[SymbolInfo]:
    """Symbols available for placement: built-ins, the loaded user library
    (see load_user_library) and the symbols embedded in the most recently
    used project. `query` matches words in the name, group, description and
    keywords; `category` filters by category name."""
    if not isinstance(query, str):
        raise InvalidOperationError("query must be a string")
    found = _symbols.search(query, category) if query else [
        s for s in _symbols.all_symbols() if category is None or s.category == category]
    return [_symbol_info(s) for s in found if s.id != UNKNOWN_ID]


def get_symbol(symbol_id: str) -> SymbolInfo:
    """Description of one symbol. Raises SymbolNotFoundError."""
    return _symbol_info(_symbol(symbol_id))


def load_user_library(path: Optional[str] = None) -> list[str]:
    """Register the custom symbols of a user library folder so they can be
    placed by id. Defaults to the library of the installed application
    (honours OPENSCHEMATIX_CONFIG_DIR; a missing default folder simply loads
    nothing). Replaces any previously loaded library. Raises
    ObjectNotFoundError if `path` is not a folder. Returns problems found while loading
    (unreadable files, duplicate ids); an empty list means everything loaded.
    Scripts that should behave the same on every computer can skip this and
    use only built-in symbols and symbols embedded in their projects."""
    import os
    from ..userlib import UserLibrary
    if path is not None and not os.path.isdir(path):
        raise ObjectNotFoundError(f"no symbol library folder {path!r}")
    lib = UserLibrary(path)
    lib.scan()
    lib.publish()      # scan() leaves the registry untouched when the folder does not exist
    _invalidate()
    return list(lib.problems)


# ================================================================ handles
class _Handle:
    __slots__ = ()

    def _key(self):
        raise NotImplementedError

    def __eq__(self, other):
        return type(other) is type(self) and other._key() == self._key()

    def __hash__(self):
        return hash((type(self).__name__, self._key()))


class Project(_Handle):
    """An OpenSchematix project (a ``.schematix`` file): one or more sheets
    plus project metadata. Create with :func:`new_project` or
    :func:`open_project`."""
    __slots__ = ("_p", "_path", "_warnings")

    def __init__(self, _internal: _Project, path: Optional[str] = None, warnings=()):
        self._p = _internal
        self._path = path
        self._warnings = tuple(warnings)

    def _key(self):
        return id(self._p)

    def _use(self) -> _Project:
        _activate(self._p)
        return self._p

    def __repr__(self):
        return f"<Project {self.title!r}: {len(self._p.sheets)} sheet(s)>"

    # ---------------------------------------------------------------- metadata
    @property
    def title(self) -> str:
        """Project title (shown in title blocks)."""
        return self._p.meta.get("title", "")

    @title.setter
    def title(self, value: str) -> None:
        self._p.meta["title"] = _text(value, "title")

    @property
    def path(self) -> Optional[str]:
        """File the project was opened from or last saved to; None for a new
        project or one converted from a legacy drawing."""
        return self._path

    @property
    def warnings(self) -> tuple[str, ...]:
        """Messages produced when the project was opened (converted formats,
        unknown symbols shown as placeholders, embedded symbols that could not
        be loaded)."""
        return self._warnings

    # ---------------------------------------------------------------- sheets
    @property
    def sheets(self) -> list["Sheet"]:
        """All sheets in order."""
        return [Sheet(self, d.uid) for d in self._p.sheets]

    def sheet(self, key: Union[str, int]) -> "Sheet":
        """A sheet by uid, by name, or by 1-based number. Raises
        ObjectNotFoundError (also if a name is used by several sheets)."""
        if isinstance(key, int) and not isinstance(key, bool):
            if 1 <= key <= len(self._p.sheets):
                return Sheet(self, self._p.sheets[key - 1].uid)
            raise ObjectNotFoundError(f"no sheet number {key} (the project has {len(self._p.sheets)})")
        if not isinstance(key, str):
            raise ObjectNotFoundError(f"sheet key must be a uid, name or number, got {key!r}")
        d = self._p.find_sheet(key)
        if d is not None:
            return Sheet(self, d.uid)
        named = [d for d in self._p.sheets if d.name == key]
        if len(named) == 1:
            return Sheet(self, named[0].uid)
        if named:
            raise ObjectNotFoundError(f"{len(named)} sheets are named {key!r}; use the sheet uid")
        raise ObjectNotFoundError(f"no sheet {key!r}")

    def add_sheet(self, name: Optional[str] = None) -> "Sheet":
        """Append a sheet (same size and title block as the last one)."""
        name = None if name is None else _text(name, "sheet name", allow_empty=False)
        return Sheet(self, self._p.add_sheet(name).uid)

    def remove_sheet(self, sheet: "Sheet") -> None:
        """Delete a sheet and everything on it. A project keeps at least one sheet."""
        doc = self._sheet_doc(sheet)
        try:
            self._p.delete_sheet(doc.uid)
        except ValueError as e:
            raise InvalidOperationError(str(e)) from e

    def _sheet_doc(self, sheet: "Sheet") -> Document:
        if not isinstance(sheet, Sheet) or sheet._project is not self:
            raise InvalidOperationError("expected a Sheet of this project")
        return sheet._doc()

    # ---------------------------------------------------------------- inspection
    def components(self) -> list["Component"]:
        """Every component on every sheet, sheet by sheet."""
        return [c for s in self.sheets for c in s.components()]

    def find(self, designator: str) -> list["Component"]:
        """Components with the given designator (several symbols may share
        one, e.g. a relay coil K1 and its contacts)."""
        return [c for c in self.components() if c.designator == designator]

    def nets(self) -> list[Net]:
        """Connected sets of terminals and wires across the whole project."""
        p = self._use()
        names = {d.uid: d.name for d in p.sheets}
        out = []
        for n in netlist.compute_nets(p):
            refs = []
            for uid, cid, name in n.terminals:
                c = p.find_sheet(uid).components.get(cid)
                refs.append(TerminalRef(uid, names.get(uid, ""), cid, c.designator if c else "", name))
            out.append(Net(n.number, tuple(refs), tuple((u, w) for u, w in n.wires), tuple(n.sheets)))
        return out

    def number_wires(self, renumber: bool = False) -> int:
        """Assign wire numbers to nets using the project's numbering settings
        (as Tools ▸ Number wires). Manually numbered wires are kept. Returns
        the number of nets numbered."""
        return netlist.assign_wire_numbers(self._use(), _bool(renumber, "renumber"))

    def bom(self, include_excluded: bool = False) -> list[BomItem]:
        """Bill of materials, exactly as the application's BOM report."""
        p = self._use()
        out = []
        for line in _bom.generate(p, include_excluded=_bool(include_excluded, "include_excluded")):
            out.append(BomItem(line.item, line.quantity, tuple(line.designators), line.designator_text(),
                               line.description, line.manufacturer, line.part_number, line.rating, line.symbol,
                               tuple(line.sheets)))
        return out

    def bom_csv(self, include_excluded: bool = False) -> str:
        """The bill of materials as CSV text, identical to the BOM export (same
        columns; starts with a UTF-8 byte-order mark so spreadsheets detect the
        encoding: write it with encoding="utf-8", not "utf-8-sig")."""
        p = self._use()
        return _bom.bom_csv(_bom.generate(p, include_excluded=_bool(include_excluded, "include_excluded")))

    def check(self, rules: Optional[Iterable[str]] = None, require_part_numbers: bool = False) -> list[Issue]:
        """Run the drawing checker (Check Drawing). `rules` limits it to the
        given rule ids (see ``openschematix.check.RULES``)."""
        if rules is not None:
            rules = set(rules)
            bad = sorted(r for r in rules if r not in _check.RULES)
            if bad:
                raise InvalidOperationError(f"unknown check rule(s) {', '.join(bad)}; "
                                            f"valid: {', '.join(sorted(_check.RULES))}")
        p = self._use()
        issues = _check.check(p, rules, _bool(require_part_numbers, "require_part_numbers"))
        return [Issue(i.severity, i.code, i.message, i.sheet_uid, i.obj_id, i.suggestion) for i in issues]

    # ---------------------------------------------------------------- saving
    def save(self, path: Optional[str] = None, snapshot: bool = True) -> str:
        """Save in the native ``.schematix`` format, atomically and verified
        (the file is only replaced after the new content reads back). With
        `snapshot` an automatic revision snapshot is recorded, as when saving
        in the application. Returns the path written."""
        if path is None:
            if self._path is None:
                raise InvalidOperationError("this project has no file yet; pass a path ending in "
                                            f"{PROJECT_EXTENSION}")
            path = self._path
        if not isinstance(path, str) or not path.lower().endswith(PROJECT_EXTENSION):
            raise InvalidOperationError(f"project files must end in {PROJECT_EXTENSION}, got {path!r}")
        p = self._use()
        try:
            projectio.save_project(p, path, snapshot=_bool(snapshot, "snapshot"))
        except (OSError, projectio.ProjectFormatError) as e:
            raise ProjectFileError(f"could not save {path}: {e}") from e
        self._path = path
        return path


class Sheet(_Handle):
    """One drawing sheet of a project. Obtained from :attr:`Project.sheets`,
    :meth:`Project.sheet` or :meth:`Project.add_sheet`."""
    __slots__ = ("_project", "_uid")

    def __init__(self, project: Project, uid: str):
        self._project = project
        self._uid = uid

    def _key(self):
        return (self._project._key(), self._uid)

    def _doc(self) -> Document:
        d = self._project._p.find_sheet(self._uid)
        if d is None:
            raise ObjectNotFoundError(f"sheet {self._uid} has been removed")
        return d

    def _use(self) -> Document:
        self._project._use()
        return self._doc()

    def __repr__(self):
        d = self._project._p.find_sheet(self._uid)
        return f"<Sheet {d.name!r}>" if d else f"<Sheet {self._uid} (removed)>"

    @property
    def project(self) -> Project:
        return self._project

    @property
    def uid(self) -> str:
        """Stable identifier (kept when saved and reopened)."""
        return self._uid

    @property
    def name(self) -> str:
        return self._doc().name

    @name.setter
    def name(self, value: str) -> None:
        self._doc()
        try:
            self._project._p.rename_sheet(self._uid, _text(value, "sheet name", allow_empty=False))
        except ValueError as e:
            raise InvalidOperationError(str(e)) from e

    @property
    def number(self) -> int:
        """1-based position in the project."""
        return self._project._p.sheet_number(self._doc())

    @property
    def size(self) -> str:
        """Paper size name, e.g. "A3" or "ANSI A"."""
        return self._doc().sheet.size

    # ---------------------------------------------------------------- objects
    def components(self) -> list["Component"]:
        return [Component(self, i) for i in self._doc().components]

    def component(self, component_id: int) -> "Component":
        if component_id not in self._doc().components:
            raise ObjectNotFoundError(f"no component {component_id!r} on sheet {self.name!r}")
        return Component(self, component_id)

    def wires(self) -> list["Wire"]:
        return [Wire(self, i) for i in self._doc().wires]

    def wire(self, wire_id: int) -> "Wire":
        if wire_id not in self._doc().wires:
            raise ObjectNotFoundError(f"no wire {wire_id!r} on sheet {self.name!r}")
        return Wire(self, wire_id)

    # ---------------------------------------------------------------- editing
    def place(self, symbol_id: str, x: float, y: float, *, rotation: int = 0, mirror: bool = False,
              params: Optional[dict] = None, designator: Optional[str] = None, label: str = "",
              properties: Optional[dict] = None) -> "Component":
        """Place a symbol with its insertion point at (x, y), which must be on
        the 10-unit grid. Rotation is clockwise in degrees (0, 90, 180, 270);
        mirroring is applied before rotation. `params` sets parameters of a
        parametric symbol (e.g. ``{"type": "4/2"}`` for a valve); omitted
        ones keep their defaults. Without `designator` the next free one is
        assigned (K1, K2, ...; terminal blocks get a strip and number). Free
        wire ends touching the new terminals are connected, as in the
        application. Raises SymbolNotFoundError or InvalidOperationError;
        nothing is changed then."""
        doc = self._use()
        sd = _symbol(symbol_id)
        x, y = _on_grid(x, y, "position")
        rotation = _rotation(rotation)
        mirror = _bool(mirror, "mirror")
        full = _validate_params(sd, params or {}) if (params or sd.parametric) else None
        designator = None if designator is None else _text(designator, "designator")
        label = _text(label, "label")
        props = _properties(properties or {})
        c = editing.place(doc, sd.id, x, y, rotation, mirror, full)
        if designator is not None:
            if is_terminal_symbol(sd.id):
                # a terminal on the named strip gets that strip's next free number
                c.props.pop("terminal", None)
                c.designator = designator
                if designator:
                    c.props["terminal"] = editing.next_terminal(doc, sd.prefix or "X", designator)[1]
            else:
                c.designator = designator
        c.label = label
        for k, v in props.items():
            if v:
                c.props[k] = v
        if sd.is_custom:
            self._project._p.embed_symbols()      # the project keeps its own copy (as on save)
            _invalidate()
        return Component(self, c.id)

    def add_wire(self, points: Iterable[Point], style: str = "solid") -> "Wire":
        """Draw a wire through `points` (at least two). Every segment must be
        horizontal or vertical and coordinates whole drawing units. Ends
        lying on component terminals are connected to them; a wire end that
        only passes over a terminal is not (see docs/SCRIPTING_API.md)."""
        doc = self._use()
        pts = self._points(points)
        if style not in WIRE_STYLES:
            raise InvalidOperationError(f"wire style must be one of {', '.join(WIRE_STYLES)}, got {style!r}")
        w = editing.add_wire(doc, pts, style=style)
        if w is None:
            raise InvalidOperationError("a wire must have two distinct end points")
        return Wire(self, w.id)

    @staticmethod
    def _points(points) -> list[Point]:
        try:
            raw = list(points)
        except TypeError:
            raise InvalidOperationError(f"points must be a list of (x, y) pairs, got {points!r}") from None
        if len(raw) < 2:
            raise InvalidOperationError("a wire needs at least two points")
        pts = []
        for i, p in enumerate(raw):
            if not isinstance(p, (tuple, list)) or len(p) != 2:
                raise InvalidOperationError(f"point {i} must be an (x, y) pair, got {p!r}")
            x, y = _num(p[0], f"point {i} x"), _num(p[1], f"point {i} y")
            if x != round(x) or y != round(y):
                raise InvalidOperationError(f"point {i} ({x:g}, {y:g}): wire coordinates must be whole "
                                            "drawing units")
            pts.append((x, y))
        if not is_orthogonal(pts):
            raise InvalidOperationError("every wire segment must be horizontal or vertical")
        return pts

    def connect(self, a: "Component", a_terminal: str, b: "Component", b_terminal: str,
                style: str = "solid") -> "Wire":
        """Connect two terminals on this sheet with an automatically routed
        wire (the router used when the application re-routes wires: leaves
        each terminal along its lead and avoids component bodies)."""
        doc = self._use()
        ta = self._terminal_on_sheet(a, a_terminal)
        tb = self._terminal_on_sheet(b, b_terminal)
        if (a.id, a_terminal) == (b.id, b_terminal):
            raise InvalidOperationError("cannot connect a terminal to itself")
        if style not in WIRE_STYLES:
            raise InvalidOperationError(f"wire style must be one of {', '.join(WIRE_STYLES)}, got {style!r}")
        w = doc.add_wire(_Wire(id=doc.new_id(), points=[ta, tb], start=[a.id, a_terminal],
                               end=[b.id, b_terminal], style=style))
        editing.reroute(doc, w)
        return Wire(self, w.id)

    def _terminal_on_sheet(self, comp: "Component", name: str) -> Point:
        if not isinstance(comp, Component) or comp._sheet != self:
            raise InvalidOperationError("both components must be on this sheet")
        return comp.terminal(name).position

    def remove(self, obj: Union["Component", "Wire"]) -> None:
        """Remove a component or wire (same as obj.remove())."""
        if not isinstance(obj, (Component, Wire)) or obj._sheet != self:
            raise InvalidOperationError("expected a Component or Wire of this sheet")
        obj.remove()

    def connectivity(self) -> SheetConnectivity:
        """Junctions, unconnected wire ends and terminals of this sheet."""
        r = analyse(self._use())
        return SheetConnectivity(tuple(tuple(p) for p in r.junctions),
                                 tuple((w, tuple(p)) for w, p in r.open_wire_ends),
                                 tuple((c, n, tuple(p)) for c, n, p in r.open_terminals),
                                 frozenset(tuple(t) for t in r.connected_terminals))


class Component(_Handle):
    """A placed symbol. Its :attr:`id` is unique on its sheet and stable when
    the project is saved and reopened; ``(sheet.uid, id)`` identifies it in
    the project."""
    __slots__ = ("_sheet", "_id")

    def __init__(self, sheet: Sheet, component_id: int):
        self._sheet = sheet
        self._id = component_id

    def _key(self):
        return (self._sheet._key(), self._id)

    def _c(self) -> _Component:
        c = self._sheet._doc().components.get(self._id)
        if c is None:
            raise ObjectNotFoundError(f"component {self._id} has been removed from sheet {self._sheet.uid}")
        return c

    def _editable(self) -> tuple[Document, _Component]:
        doc = self._sheet._use()
        c = self._c()
        if _layer_locked(self._sheet._project._p, c):
            raise InvalidOperationError(f"component {c.designator or c.id} is locked (or on a locked layer)")
        return doc, c

    def __repr__(self):
        c = self._sheet._doc().components.get(self._id)
        return f"<Component {c.designator or '?'} {c.symbol} at ({c.x:g}, {c.y:g})>" if c else \
            f"<Component {self._id} (removed)>"

    @property
    def id(self) -> int:
        return self._id

    @property
    def sheet(self) -> Sheet:
        return self._sheet

    @property
    def symbol_id(self) -> str:
        return self._c().symbol

    @property
    def locked(self) -> bool:
        """True if the component or its layer is locked; it cannot be changed then."""
        return _layer_locked(self._sheet._project._p, self._c())

    # ---------------------------------------------------------------- identification
    @property
    def designator(self) -> str:
        """Reference designator, e.g. "K1". Several symbols of one device may
        share a designator (Project.check() reports real clashes)."""
        return self._c().designator

    @designator.setter
    def designator(self, value: str) -> None:
        _doc, c = self._editable()
        c.designator = _text(value, "designator")

    @property
    def label(self) -> str:
        return self._c().label

    @label.setter
    def label(self, value: str) -> None:
        _doc, c = self._editable()
        c.label = _text(value, "label")

    # ---------------------------------------------------------------- placement
    @property
    def position(self) -> Point:
        """Insertion point (x, y)."""
        c = self._c()
        return (c.x, c.y)

    @position.setter
    def position(self, value: Point) -> None:
        doc, c = self._editable()
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise InvalidOperationError(f"position must be an (x, y) pair, got {value!r}")
        x, y = _on_grid(value[0], value[1], "position")
        # Same as dragging in the application: attached wires follow.
        editing.move_items(doc, [c.id], [], x - c.x, y - c.y)

    def move_by(self, dx: float, dy: float) -> None:
        """Move by a grid-aligned offset; attached wires follow."""
        x, y = self.position
        dx, dy = _on_grid(dx, dy, "offset")
        self.position = (x + dx, y + dy)

    @property
    def rotation(self) -> int:
        """Clockwise rotation in degrees: 0, 90, 180 or 270."""
        return self._c().rotation

    @rotation.setter
    def rotation(self, value: int) -> None:
        doc, c = self._editable()
        c.rotation = _rotation(value)
        self._resync(doc, c)

    @property
    def mirror(self) -> bool:
        """Mirrored about the symbol's vertical axis (applied before rotation)."""
        return self._c().mirror

    @mirror.setter
    def mirror(self, value: bool) -> None:
        doc, c = self._editable()
        c.mirror = _bool(value, "mirror")
        self._resync(doc, c)

    @staticmethod
    def _resync(doc: Document, c: _Component) -> None:
        # As the Properties inspector: attached wires follow the terminals.
        editing.sync_wire_ends(doc)
        editing.attach_touching_wires(doc, [c.id])

    # ---------------------------------------------------------------- parameters and properties
    @property
    def params(self) -> dict:
        """Parameters of a parametric symbol (a copy; use set_params to change)."""
        return copy.deepcopy(self._c().params)

    def set_params(self, **changes) -> None:
        """Change parameters, e.g. ``valve.set_params(type="4/2", left=["solenoid"])``.
        Changing a valve type without positions uses that type's default
        positions. Raises InvalidOperationError if a value is invalid or a
        terminal that would disappear has a wire attached."""
        doc, c = self._editable()
        sd = _symbol(c.symbol)
        new = _validate_params(sd, changes, c.params or sd.default_params)
        names = {t.name for t in sd.build(new).terminals}
        wired = sorted({r[1] for w in doc.wires.values() for r in (w.start, w.end)
                        if r and r[0] == c.id and r[1] not in names})
        if wired:
            raise InvalidOperationError(f"terminal(s) {', '.join(wired)} of {c.designator or c.id} have wires "
                                        "attached and would not exist with these parameters; remove the wires first")
        c.params = new
        self._resync(doc, c)

    @property
    def properties(self) -> dict[str, str]:
        """Component properties (a copy): description, manufacturer,
        part_number, rating, terminal and any custom keys."""
        return dict(self._c().props)

    def set_property(self, key: str, value: str) -> None:
        """Set a property; an empty value removes it (as in the application)."""
        _doc, c = self._editable()
        props = _properties({key: value})
        for k, v in props.items():
            if v:
                c.props[k] = v
            else:
                c.props.pop(k, None)

    def remove_property(self, key: str) -> None:
        _doc, c = self._editable()
        if key not in c.props:
            raise ObjectNotFoundError(f"{c.designator or c.id} has no property {key!r}")
        del c.props[key]

    @property
    def in_bom(self) -> bool:
        """Whether the component is counted in the bill of materials."""
        return self._c().in_bom

    @in_bom.setter
    def in_bom(self, value: bool) -> None:
        _doc, c = self._editable()
        c.in_bom = _bool(value, "in_bom")

    # ---------------------------------------------------------------- terminals
    @property
    def terminals(self) -> dict[str, Terminal]:
        """Connection points in world coordinates, keyed by terminal name."""
        self._sheet._use()
        c = self._c()
        sd = c.symdef()
        pos, dirs = c.terminals(), c.terminal_dirs()
        return {t.name: Terminal(t.name, c.terminal_label(t.name), pos[t.name], dirs[t.name],
                                 sd.port_type(t) if sd else "any")
                for t in c.terminal_defs()}

    def terminal(self, name: str) -> Terminal:
        terms = self.terminals
        if name not in terms:
            raise ObjectNotFoundError(f"{self.designator or self.id} ({self.symbol_id}) has no terminal {name!r}; "
                                      f"terminals: {', '.join(terms) or 'none'}")
        return terms[name]

    def remove(self) -> None:
        """Delete the component. Wires stay; their ends become unconnected."""
        doc, c = self._editable()
        editing.delete_items(doc, [c.id])


class Wire(_Handle):
    """A wire: an orthogonal polyline whose ends may be attached to terminals."""
    __slots__ = ("_sheet", "_id")

    def __init__(self, sheet: Sheet, wire_id: int):
        self._sheet = sheet
        self._id = wire_id

    def _key(self):
        return (self._sheet._key(), self._id)

    def _w(self) -> _Wire:
        w = self._sheet._doc().wires.get(self._id)
        if w is None:
            raise ObjectNotFoundError(f"wire {self._id} has been removed from sheet {self._sheet.uid}")
        return w

    def __repr__(self):
        w = self._sheet._doc().wires.get(self._id)
        return f"<Wire {self._id} {w.points[0]}->{w.points[-1]}>" if w else f"<Wire {self._id} (removed)>"

    @property
    def id(self) -> int:
        return self._id

    @property
    def sheet(self) -> Sheet:
        return self._sheet

    @property
    def points(self) -> list[Point]:
        return [tuple(p) for p in self._w().points]

    @property
    def start(self) -> Optional[tuple[int, str]]:
        """(component id, terminal name) the first point is attached to, or None."""
        r = self._w().start
        return (r[0], r[1]) if r else None

    @property
    def end(self) -> Optional[tuple[int, str]]:
        """(component id, terminal name) the last point is attached to, or None."""
        r = self._w().end
        return (r[0], r[1]) if r else None

    @property
    def style(self) -> str:
        return self._w().style

    @property
    def number(self) -> str:
        """Wire number ("" if not numbered; see Project.number_wires)."""
        return self._w().number

    def remove(self) -> None:
        doc = self._sheet._use()
        w = self._w()
        if _layer_locked(self._sheet._project._p, w):
            raise InvalidOperationError(f"wire {w.id} is locked (or on a locked layer)")
        editing.delete_items(doc, [w.id])


# ================================================================ entry points
def new_project(title: str = "", sheet_size: str = "A3") -> Project:
    """A new project with one empty sheet of the given paper size."""
    if sheet_size not in SHEET_SIZES_MM:
        raise InvalidOperationError(f"unknown sheet size {sheet_size!r}; valid: {', '.join(SHEET_SIZES_MM)}")
    p = _new_project(_text(title, "title"), sheet_size)
    _activate(p)
    return Project(p)


def open_project(path: str) -> Project:
    """Open a ``.schematix`` project, or convert a legacy ``.osch`` drawing
    (then :attr:`Project.path` is None and :meth:`Project.save` needs a new
    path). The file is never modified by opening it. Raises ProjectFileError."""
    try:
        res = projectio.open_any(path)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        raise ProjectFileError(f"could not open {path}: {e}") from e
    _invalidate()
    _activate(res.project)
    return Project(res.project, None if res.migrated else path, res.warnings)

