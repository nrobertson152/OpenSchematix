"""Read-only integrity checks for symbol definitions and libraries.

Inspects SymbolDef instances and (optionally) raw custom-symbol documents
without modifying them. Reuses ``validate_geometry`` from ``base`` where
possible. Findings are structured so callers can report or filter by severity.

This module is intentionally separate from the Symbol Editor and from
load-time normalisation so validation never mutates source data.

Strict validation vs normalisation
----------------------------------
``validate_document`` is a **strict structural audit** of a raw symbol
document (as stored on disk or embedded). It reports problems without
repairing them: missing pin ids, invalid directions, unknown port types,
malformed numbers, and unsupported primitives are all findings.

``normalise`` (in ``custom``) is the **load-time path**. It may repair a
limited set of issues so existing and legacy documents keep loading:

* missing pin ``id`` → generated ``p{n}``
* invalid pin ``dir`` → ``\"r\"``
* unknown line width → ``\"normal\"``
* unknown port type → empty string
* text size clamped; strings truncated

A document that ``normalise`` accepts may still produce findings under
``validate_document`` when the raw form is incomplete or non-canonical.
That is intentional: the validator is for integrity reports; ``normalise``
is for compatibility. Neither mutates the caller's original object when
used as documented (``validate_document`` deep-copies by default;
``normalise`` returns a new dict).
"""
from __future__ import annotations

import copy
import json
import math
import sys
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from ..geometry import GRID
from .base import PORT_TYPES, Geometry, SymbolDef, Terminal, validate_geometry
from .custom import PRIM_KINDS, SYMBOL_FORMAT, SYMBOL_VERSION, USER_PREFIX

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


@dataclass(frozen=True)
class Finding:
    """One integrity problem (or informational note).

    ``location`` identifies the field or primitive (e.g. ``pin[0]``,
    ``prim[2]``). ``source`` is the originating file path when known
    (CLI multi-file mode); it is included in ``as_dict`` for machine-readable
    output.
    """

    symbol_id: str
    problem: str
    severity: str = SEVERITY_ERROR
    location: str = ""
    source: str = ""

    def as_dict(self) -> dict:
        d = {"symbol_id": self.symbol_id, "problem": self.problem, "severity": self.severity}
        if self.location:
            d["location"] = self.location
        if self.source:
            d["source"] = self.source
        return d


def _safe_in(value, container) -> bool:
    """Membership test that never raises on unhashable ``value``."""
    try:
        return value in container
    except TypeError:
        return False


def _finite_number(v) -> bool:
    """True if *v* converts to a finite float. Never raises."""
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return False
    try:
        return math.isfinite(f)
    except (TypeError, ValueError, OverflowError):
        return False


def _as_float(v):
    """Return float(v) or None on any conversion failure / non-finite."""
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        if not math.isfinite(f):
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return f


def _check_coordinates(label: str, x, y, sid: str, findings: list, require_grid: bool = False,
                       source: str = ""):
    fx, fy = _as_float(x), _as_float(y)
    if fx is None or fy is None:
        findings.append(Finding(sid, f"{label}: invalid numeric coordinates ({x!r}, {y!r})",
                                SEVERITY_ERROR, label, source))
        return
    try:
        out_of_range = abs(fx) > 1e6 or abs(fy) > 1e6
    except (TypeError, OverflowError):
        out_of_range = True
    if out_of_range:
        findings.append(Finding(sid, f"{label}: coordinates out of range ({fx}, {fy})",
                                SEVERITY_ERROR, label, source))
        return
    if require_grid:
        try:
            off = (abs(fx / GRID - round(fx / GRID)) > 1e-6 or
                   abs(fy / GRID - round(fy / GRID)) > 1e-6)
        except (TypeError, OverflowError, ZeroDivisionError):
            off = True
        if off:
            findings.append(Finding(sid, f"{label}: not on the {GRID}-unit grid at ({fx}, {fy})",
                                    SEVERITY_ERROR, label, source))


def _check_geometry(g: Geometry, sid: str, findings: list, source: str = ""):
    if g is None:
        findings.append(Finding(sid, "geometry is missing", SEVERITY_ERROR, source=source))
        return
    try:
        for msg in validate_geometry(g):
            findings.append(Finding(sid, msg, SEVERITY_ERROR, source=source))
    except Exception as e:  # noqa: BLE001
        findings.append(Finding(sid, f"geometry validation failed: {e}", SEVERITY_ERROR, source=source))
        return
    prims = getattr(g, "prims", None) or []
    if not isinstance(prims, (list, tuple)):
        findings.append(Finding(sid, "geometry prims is not a sequence", SEVERITY_ERROR, source=source))
        prims = []
    for i, p in enumerate(prims):
        loc = f"prim[{i}]"
        if not isinstance(p, dict):
            findings.append(Finding(sid, f"primitive {i}: not a mapping", SEVERITY_ERROR, loc, source))
            continue
        k = p.get("k")
        if not _safe_in(k, ("line", "poly", "circle", "text")):
            findings.append(Finding(sid, f"primitive {i}: unsupported or malformed kind {k!r}",
                                    SEVERITY_ERROR, loc, source))
        if k in ("line", "poly"):
            pts = p.get("pts") or []
            if not isinstance(pts, (list, tuple)):
                findings.append(Finding(sid, f"primitive {i}: pts is not a sequence",
                                        SEVERITY_ERROR, loc, source))
                continue
            for j, pt in enumerate(pts):
                if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                    findings.append(Finding(sid, f"primitive {i}: point {j} malformed",
                                            SEVERITY_ERROR, loc, source))
                else:
                    _check_coordinates(f"primitive {i} point {j}", pt[0], pt[1], sid, findings,
                                       source=source)
        elif k == "circle":
            c = p.get("c")
            if not (isinstance(c, (list, tuple)) and len(c) == 2):
                findings.append(Finding(sid, f"primitive {i}: circle centre malformed",
                                        SEVERITY_ERROR, loc, source))
            else:
                _check_coordinates(f"primitive {i} centre", c[0], c[1], sid, findings, source=source)
            r = p.get("r")
            rf = _as_float(r)
            if rf is None or rf <= 0:
                findings.append(Finding(sid, f"primitive {i}: invalid radius {r!r}",
                                        SEVERITY_ERROR, loc, source))
        elif k == "text":
            pt = p.get("p")
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                findings.append(Finding(sid, f"primitive {i}: text position malformed",
                                        SEVERITY_ERROR, loc, source))
            else:
                _check_coordinates(f"primitive {i} text", pt[0], pt[1], sid, findings, source=source)
    terminals = getattr(g, "terminals", None) or []
    if not isinstance(terminals, (list, tuple)):
        findings.append(Finding(sid, "geometry terminals is not a sequence", SEVERITY_ERROR, source=source))
        return
    for t in terminals:
        if not isinstance(t, Terminal):
            findings.append(Finding(sid, "terminal entry is not a Terminal", SEVERITY_ERROR, source=source))
            continue
        if not t.name:
            findings.append(Finding(sid, "terminal has empty name/id", SEVERITY_ERROR, "terminal", source))
        _check_coordinates(f"terminal {t.name}", t.x, t.y, sid, findings, require_grid=True, source=source)
        if t.dir not in ("l", "r", "u", "d"):
            findings.append(Finding(sid, f"terminal {t.name}: invalid direction {t.dir!r}",
                                    SEVERITY_ERROR, t.name or "terminal", source))
        if t.ptype and not _safe_in(t.ptype, PORT_TYPES) and t.ptype != "":
            findings.append(Finding(sid, f"terminal {t.name}: unknown port type {t.ptype!r}",
                                    SEVERITY_WARNING, t.name or "terminal", source))


def validate_symbol_def(sd: SymbolDef, *, params: Optional[dict] = None) -> list:
    """Inspect one SymbolDef. Never mutates ``sd``, its geometry, or ``params``.

    For parametric symbols, ``sd.build`` is called with a **deep** copy of
    ``params`` (or ``None``) so a builder cannot mutate nested structures in
    the caller's dict. Built-in builders are expected to return fresh geometry;
    this function does not write back to ``sd.geometry`` or ``sd.default_params``.
    """
    findings = []
    sid = getattr(sd, "id", None) or ""
    if not sid or not isinstance(sid, str):
        findings.append(Finding(sid or "<missing>", "missing or invalid symbol identifier", SEVERITY_ERROR))
        sid = sid or "<missing>"
    if not (getattr(sd, "name", None) or "").strip():
        findings.append(Finding(sid, "symbol name is empty", SEVERITY_WARNING))
    build_params = copy.deepcopy(params) if params is not None else None
    try:
        g = sd.build(build_params)
    except Exception as e:  # noqa: BLE001
        findings.append(Finding(sid, f"failed to build geometry: {e}", SEVERITY_ERROR))
        return findings
    _check_geometry(g, sid, findings)
    custom = getattr(sd, "custom", None)
    if custom is not None and not isinstance(custom, dict):
        findings.append(Finding(sid, "custom metadata is not a dict", SEVERITY_ERROR))
    return findings


def validate_document(doc: dict, *, deep_copy: bool = True, source: str = "") -> list:
    """Strict structural audit of a raw custom-symbol document.

    Does **not** call ``normalise`` and does not repair data. Reports findings
    for issues that ``normalise`` might silently fix (missing pin ids, bad
    directions, etc.). Never raises for malformed field types: unhashable
    values, overflow, and unexpected nested structures become findings.

    When *deep_copy* is True (default), operates on a deep copy so the
    caller's document is unchanged.
    """
    findings = []
    try:
        if deep_copy:
            doc = copy.deepcopy(doc)
    except Exception as e:  # noqa: BLE001
        return [Finding("<unknown>", f"document could not be copied for inspection: {e}",
                        SEVERITY_ERROR, source=source)]

    if not isinstance(doc, dict):
        return [Finding("<unknown>", "symbol document is not a JSON object", SEVERITY_ERROR, source=source)]

    sid = str(doc.get("id") or "") or "<missing-id>"
    if doc.get("format") != SYMBOL_FORMAT:
        findings.append(Finding(sid, f"missing or invalid format field (expected {SYMBOL_FORMAT!r})",
                                SEVERITY_ERROR, source=source))
    ver = doc.get("version", 1)
    if not isinstance(ver, int) or isinstance(ver, bool):
        findings.append(Finding(sid, f"version must be an integer, got {type(ver).__name__}",
                                SEVERITY_ERROR, source=source))
    elif ver < 1:
        findings.append(Finding(sid, f"unsupported schema version {ver}", SEVERITY_ERROR, source=source))
    elif ver > SYMBOL_VERSION:
        findings.append(Finding(sid, f"symbol format version {ver} is newer than supported "
                                f"({SYMBOL_VERSION})", SEVERITY_ERROR, source=source))
    if not isinstance(sid, str) or not sid.startswith(USER_PREFIX) or len(sid) <= len(USER_PREFIX):
        findings.append(Finding(sid, "custom symbol id must start with 'user:' and include a unique suffix",
                                SEVERITY_ERROR, source=source))
    name = doc.get("name", "")
    if name is not None and not isinstance(name, str):
        findings.append(Finding(sid, "name must be a string", SEVERITY_ERROR, source=source))
    if "properties" in doc and doc["properties"] is not None and not isinstance(doc["properties"], dict):
        findings.append(Finding(sid, "properties must be an object/dict", SEVERITY_ERROR, source=source))
    if "tags" in doc and doc["tags"] is not None and not isinstance(doc["tags"], (list, tuple)):
        findings.append(Finding(sid, "tags must be a list", SEVERITY_ERROR, source=source))

    seen_pins = set()
    pins = doc.get("pins")
    if pins is None:
        pass
    elif not isinstance(pins, list):
        findings.append(Finding(sid, "pins must be a list", SEVERITY_ERROR, source=source))
    else:
        for i, p in enumerate(pins):
            loc = f"pin[{i}]"
            if not isinstance(p, dict):
                findings.append(Finding(sid, f"pin {i}: not an object", SEVERITY_ERROR, loc, source))
                continue
            raw_id = p.get("id")
            if raw_id is None or raw_id == "":
                findings.append(Finding(sid, f"pin {i}: missing id", SEVERITY_ERROR, loc, source))
                pid = ""
            else:
                try:
                    pid = str(raw_id)
                except Exception:  # noqa: BLE001
                    findings.append(Finding(sid, f"pin {i}: id is not convertible to string",
                                            SEVERITY_ERROR, loc, source))
                    pid = ""
            if pid:
                if pid in seen_pins:
                    findings.append(Finding(sid, f"duplicate pin id {pid}", SEVERITY_ERROR, pid, source))
                else:
                    seen_pins.add(pid)
            _check_coordinates(f"pin {pid or i}", p.get("x"), p.get("y"), sid, findings,
                               require_grid=True, source=source)
            d = p.get("dir", "r")
            if d not in ("l", "r", "u", "d"):
                findings.append(Finding(sid, f"pin {pid or i}: invalid direction {d!r}",
                                        SEVERITY_ERROR, pid or loc, source))
            ptype = p.get("type") or ""
            if ptype and not _safe_in(ptype, PORT_TYPES):
                findings.append(Finding(sid, f"pin {pid or i}: unknown port type {ptype!r}",
                                        SEVERITY_WARNING, pid or loc, source))

    prims = doc.get("prims")
    if prims is None:
        pass
    elif not isinstance(prims, list):
        findings.append(Finding(sid, "prims must be a list", SEVERITY_ERROR, source=source))
    else:
        for i, p in enumerate(prims):
            loc = f"prim[{i}]"
            if not isinstance(p, dict):
                findings.append(Finding(sid, f"primitive {i}: not an object", SEVERITY_ERROR, loc, source))
                continue
            k = p.get("k")
            if not _safe_in(k, PRIM_KINDS):
                findings.append(Finding(sid, f"primitive {i}: unsupported kind {k!r}",
                                        SEVERITY_ERROR, loc, source))
                continue
            if k in ("line", "poly"):
                pts = p.get("pts")
                if not isinstance(pts, (list, tuple)) or len(pts) < 2:
                    findings.append(Finding(sid, f"primitive {i}: needs at least two points",
                                            SEVERITY_ERROR, loc, source))
                else:
                    for j, pt in enumerate(pts):
                        if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                            findings.append(Finding(sid, f"primitive {i}: point {j} malformed",
                                                    SEVERITY_ERROR, loc, source))
                        else:
                            _check_coordinates(f"primitive {i} pt {j}", pt[0], pt[1], sid, findings,
                                               source=source)
            elif k in ("circle", "arc"):
                c = p.get("c")
                if not (isinstance(c, (list, tuple)) and len(c) == 2):
                    findings.append(Finding(sid, f"primitive {i}: centre malformed",
                                            SEVERITY_ERROR, loc, source))
                else:
                    _check_coordinates(f"primitive {i} centre", c[0], c[1], sid, findings, source=source)
                r = p.get("r")
                rf = _as_float(r)
                if rf is None or rf <= 0:
                    findings.append(Finding(sid, f"primitive {i}: invalid radius {r!r}",
                                            SEVERITY_ERROR, loc, source))
                if k == "arc":
                    for field_name in ("start", "extent"):
                        if field_name in p and _as_float(p.get(field_name)) is None:
                            findings.append(Finding(sid, f"primitive {i}: invalid {field_name}",
                                                    SEVERITY_ERROR, loc, source))
            elif k == "text":
                pt = p.get("p")
                if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                    findings.append(Finding(sid, f"primitive {i}: text position malformed",
                                            SEVERITY_ERROR, loc, source))
                else:
                    _check_coordinates(f"primitive {i} text", pt[0], pt[1], sid, findings, source=source)

    return findings


def validate_library(symbols: Iterable[SymbolDef], *, check_duplicates: bool = True) -> list:
    findings = []
    seen = {}
    for sd in symbols:
        sid = getattr(sd, "id", "") or ""
        if check_duplicates and sid:
            if sid in seen:
                findings.append(Finding(sid, "duplicate symbol identifier (also defined earlier in library)",
                                        SEVERITY_ERROR))
            else:
                seen[sid] = sd
        findings.extend(validate_symbol_def(sd))
    return findings


def validate_builtin_library() -> list:
    from . import builtin_symbols
    return validate_library(builtin_symbols(), check_duplicates=True)


def findings_by_severity(findings: Sequence) -> dict:
    out = {SEVERITY_ERROR: [], SEVERITY_WARNING: [], SEVERITY_INFO: []}
    for f in findings:
        out.setdefault(f.severity, []).append(f)
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: validate built-ins and/or .osym paths.

    Exit code 0 when there are no error-severity findings; 1 otherwise.
    ``--json`` prints a list of finding dicts (includes ``source`` and
    ``location`` when set). Human-readable mode always shows the source
    path for file findings together with the field location.
    """
    argv = list(argv if argv is not None else sys.argv[1:])
    paths = [a for a in argv if not a.startswith("-")]
    json_out = "--json" in argv
    findings = []
    if not paths or "--builtins" in argv:
        findings.extend(validate_builtin_library())
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            if not raw.strip():
                findings.append(Finding(path, "file is empty or truncated", SEVERITY_ERROR,
                                        location="", source=path))
                continue
            data = json.loads(raw)
        except FileNotFoundError:
            findings.append(Finding(path, f"file not found: {path}", SEVERITY_ERROR, source=path))
            continue
        except json.JSONDecodeError as e:
            findings.append(Finding(path, f"invalid JSON: {e.msg} at line {e.lineno} column {e.colno}",
                                    SEVERITY_ERROR, source=path))
            continue
        except OSError as e:
            findings.append(Finding(path, f"could not read file: {e}", SEVERITY_ERROR, source=path))
            continue
        for fnd in validate_document(data, source=path):
            findings.append(Finding(fnd.symbol_id, fnd.problem, fnd.severity,
                                    location=fnd.location, source=path))

    if json_out:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    else:
        if not findings:
            print("No integrity problems found.")
        else:
            for f in findings:
                parts = []
                if f.source:
                    parts.append(f.source)
                if f.location:
                    parts.append(f.location)
                ctx = f" ({', '.join(parts)})" if parts else ""
                print(f"[{f.severity}] {f.symbol_id}{ctx}: {f.problem}")
            print(f"\n{len(findings)} finding(s).")
    errors = sum(1 for f in findings if f.severity == SEVERITY_ERROR)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
