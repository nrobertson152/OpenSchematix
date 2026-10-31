"""User-defined (custom) symbols.

A custom symbol is stored as a small JSON document (``.osym``):

    {
      "format": "OpenSchematix Symbol", "version": 1,
      "id": "user:3f2a9c1e5b7d4e10",          # stable identifier, never reused
      "revision": 3,                           # incremented on every save
      "name": "Proximity sensor, PNP", "description": "...",
      "category": "Electrical", "group": "Sensors", "tags": ["sensor", "pnp"],
      "prefix": "B", "convention": "Custom",
      "properties": {"manufacturer": "...", ...},   # default component properties
      "prims": [ {"k": "line", "pts": [[x, y], ...], "w": "normal", "dash": false},
                 {"k": "poly", ...}, {"k": "circle", "c": [x, y], "r": r, "fill": false},
                 {"k": "arc", "c": [x, y], "r": r, "start": deg, "extent": deg},
                 {"k": "text", "p": [x, y], "s": "M", "size": 8, "anchor": "c"} ],
      "pins": [ {"id": "p1", "name": "1", "x": -20, "y": 0, "dir": "l",
                 "type": "elec.passive", "show": true} ]
    }

Coordinates are symbol-local drawing units (0.25 mm) relative to the
insertion point (the origin). Pins must lie on the 10-unit grid. A pin's
``id`` is its permanent key: wires reference pins by id, so renaming or
renumbering a pin never disconnects existing drawings.
"""
from __future__ import annotations

import copy
import uuid

from ..geometry import GRID
from .base import (CATEGORY_DOMAIN, GENERIC, PORT_TYPES, Geometry, SymbolDef, Terminal, flatten_prims,
                   validate_geometry)

SYMBOL_FORMAT = "OpenSchematix Symbol"
SYMBOL_VERSION = 1
USER_PREFIX = "user:"
CATEGORIES = ("Electrical", "Electronic", "Hydraulic", "Pneumatic", "General")
PRIM_KINDS = ("line", "poly", "circle", "arc", "text")


class SymbolFormatError(ValueError):
    pass


def new_symbol_id() -> str:
    return USER_PREFIX + uuid.uuid4().hex[:16]


def blank_symbol(name="New symbol", category="Electrical") -> dict:
    return {"format": SYMBOL_FORMAT, "version": SYMBOL_VERSION, "id": new_symbol_id(), "revision": 0,
            "name": name, "description": "", "category": category, "group": "Custom", "tags": [],
            "prefix": "U", "convention": "Custom", "properties": {}, "prims": [], "pins": []}


def _num(v, what):
    try:
        f = float(v)
    except (TypeError, ValueError) as e:
        raise SymbolFormatError(f"{what}: not a number") from e
    if f != f or abs(f) > 1e6:
        raise SymbolFormatError(f"{what}: out of range")
    return f


def _pt(v, what):
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        raise SymbolFormatError(f"{what}: expected [x, y]")
    return (_num(v[0], what), _num(v[1], what))


def normalise(data) -> dict:
    """Validate and clean a symbol document. Raises SymbolFormatError."""
    if not isinstance(data, dict) or data.get("format") != SYMBOL_FORMAT:
        raise SymbolFormatError("not an OpenSchematix symbol")
    ver = data.get("version", 1)
    if not isinstance(ver, int) or ver > SYMBOL_VERSION:
        raise SymbolFormatError(f"symbol format version {ver} is newer than this program supports")
    sid = str(data.get("id", ""))
    if not sid.startswith(USER_PREFIX) or len(sid) <= len(USER_PREFIX):
        raise SymbolFormatError("custom symbol ids must start with 'user:'")
    out = {"format": SYMBOL_FORMAT, "version": SYMBOL_VERSION, "id": sid,
           "revision": int(data.get("revision", 0) or 0),
           "name": str(data.get("name") or "Unnamed symbol")[:120],
           "description": str(data.get("description", ""))[:2000],
           "category": str(data.get("category") or "General"),
           "group": str(data.get("group") or "Custom")[:80],
           "tags": [str(t)[:40] for t in (data.get("tags") or []) if str(t).strip()][:30],
           "prefix": str(data.get("prefix", "U"))[:8],
           "convention": str(data.get("convention") or "Custom")[:60],
           "properties": {str(k): str(v) for k, v in (data.get("properties") or {}).items()},
           "prims": [], "pins": []}
    for i, p in enumerate(data.get("prims") or []):
        if not isinstance(p, dict) or p.get("k") not in PRIM_KINDS:
            raise SymbolFormatError(f"primitive {i}: unknown kind")
        k = p["k"]
        q = {"k": k}
        w = p.get("w", "normal")
        q["w"] = w if w in ("thin", "normal", "thick") else "normal"
        q["dash"] = bool(p.get("dash", False))
        if k in ("line", "poly"):
            pts = [_pt(v, f"primitive {i}") for v in p.get("pts") or []]
            if len(pts) < 2:
                raise SymbolFormatError(f"primitive {i}: needs at least two points")
            q["pts"] = pts
            if k == "poly":
                q["fill"] = bool(p.get("fill", False))
        elif k in ("circle", "arc"):
            q["c"] = _pt(p.get("c"), f"primitive {i}")
            q["r"] = _num(p.get("r"), f"primitive {i}")
            if q["r"] <= 0:
                raise SymbolFormatError(f"primitive {i}: radius must be positive")
            if k == "circle":
                q["fill"] = bool(p.get("fill", False))
            else:
                q["start"] = _num(p.get("start", 0), f"primitive {i}")
                q["extent"] = _num(p.get("extent", 90), f"primitive {i}")
        else:
            q = {"k": "text", "p": _pt(p.get("p"), f"primitive {i}"), "s": str(p.get("s", ""))[:200],
                 "size": max(2.0, min(80.0, _num(p.get("size", 8), f"primitive {i}"))),
                 "anchor": p.get("anchor", "c") if p.get("anchor") in ("c", "n", "s", "e", "w", "nw", "ne", "sw", "se")
                 else "c"}
        out["prims"].append(q)
    seen = set()
    for i, p in enumerate(data.get("pins") or []):
        if not isinstance(p, dict):
            raise SymbolFormatError(f"pin {i}: invalid")
        pid = str(p.get("id") or f"p{i + 1}")
        if pid in seen:
            raise SymbolFormatError(f"pin {i}: duplicate id {pid}")
        seen.add(pid)
        x, y = _num(p.get("x"), f"pin {pid}"), _num(p.get("y"), f"pin {pid}")
        if abs(x / GRID - round(x / GRID)) > 1e-6 or abs(y / GRID - round(y / GRID)) > 1e-6:
            raise SymbolFormatError(f"pin {p.get('name') or pid} is not on the {GRID}-unit grid")
        d = p.get("dir", "r")
        ptype = p.get("type", "") or ""
        out["pins"].append({"id": pid, "name": str(p.get("name") or pid)[:20], "x": x, "y": y,
                            "dir": d if d in ("l", "r", "u", "d") else "r",
                            "type": ptype if ptype in PORT_TYPES else "",
                            "show": bool(p.get("show", True))})
    return out


def build_geometry(doc: dict) -> Geometry:
    prims = [copy.deepcopy(p) for p in doc["prims"]]
    for p in prims:
        if "pts" in p:
            p["pts"] = [tuple(v) for v in p["pts"]]
        for key in ("c", "p"):
            if key in p:
                p[key] = tuple(p[key])
    prims = flatten_prims(prims)
    # Pin designations are not part of the artwork: like built-in symbols they
    # are drawn once by the renderer (render.terminal_label_prims) according to
    # the project's "show terminal designations" setting. Baking them into the
    # prims here drew them regardless of that setting and twice when it was on.
    terms = [Terminal(p["id"], p["x"], p["y"], p["dir"], label=p["name"], ptype=p.get("type", ""),
                      show=bool(p.get("show", True)))
             for p in doc["pins"]]
    return Geometry(prims, terms)


def to_symdef(doc: dict) -> SymbolDef:
    doc = normalise(doc)
    g = build_geometry(doc)
    problems = validate_geometry(g)
    if problems:
        raise SymbolFormatError("; ".join(problems))
    sd = SymbolDef(doc["id"], doc["name"], doc["category"], doc["group"], doc["convention"] or GENERIC,
                   doc["description"], doc["prefix"], g, keywords=tuple(doc["tags"]))
    sd.custom = doc          # keep the source document (embedded in projects)
    return sd


def default_ptype(category: str, terminal_name: str) -> str:
    """Port type for built-in symbol terminals, derived from the category and
    the conventional port letters/numbers (ISO 1219 / ISO 5599)."""
    dom = CATEGORY_DOMAIN.get(category)
    n = terminal_name.upper()
    if dom == "hyd":
        if n == "P":
            return "hyd.pressure"
        if n == "T":
            return "hyd.tank"
        if n in ("X", "Y"):
            return "hyd.pilot"
        if n == "L":
            return "hyd.drain"
        return "hyd.work"
    if dom == "pneu":
        if n == "1":
            return "pneu.supply"
        if n in ("3", "5"):
            return "pneu.exhaust"
        if n in ("12", "14"):
            return "pneu.pilot"
        return "pneu.work"
    if dom == "elec":
        return "elec.passive"
    return "any"
