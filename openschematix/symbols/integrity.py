"""Read-only integrity checks for symbol definitions and libraries.

Inspects SymbolDef instances and (optionally) raw custom-symbol documents
without modifying them. Reuses ``validate_geometry`` from ``base`` where
possible. Findings are structured so callers can report or filter by severity.

This module is intentionally separate from the Symbol Editor and from
load-time normalisation so validation never mutates source data.
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
    """One integrity problem (or informational note)."""

    symbol_id: str
    problem: str
    severity: str = SEVERITY_ERROR
    location: str = ""

    def as_dict(self) -> dict:
        d = {"symbol_id": self.symbol_id, "problem": self.problem, "severity": self.severity}
        if self.location:
            d["location"] = self.location
        return d


def _finite_number(v) -> bool:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def _check_coordinates(label: str, x, y, sid: str, findings: list, require_grid: bool = False):
    if not _finite_number(x) or not _finite_number(y):
        findings.append(Finding(sid, f"{label}: invalid numeric coordinates ({x!r}, {y!r})",
                                SEVERITY_ERROR, label))
        return
    fx, fy = float(x), float(y)
    if abs(fx) > 1e6 or abs(fy) > 1e6:
        findings.append(Finding(sid, f"{label}: coordinates out of range ({fx}, {fy})",
                                SEVERITY_ERROR, label))
    if require_grid:
        if abs(fx / GRID - round(fx / GRID)) > 1e-6 or abs(fy / GRID - round(fy / GRID)) > 1e-6:
            findings.append(Finding(sid, f"{label}: not on the {GRID}-unit grid at ({fx}, {fy})",
                                    SEVERITY_ERROR, label))


def _check_geometry(g: Geometry, sid: str, findings: list):
    if g is None:
        findings.append(Finding(sid, "geometry is missing", SEVERITY_ERROR))
        return
    for msg in validate_geometry(g):
        findings.append(Finding(sid, msg, SEVERITY_ERROR))
    for i, p in enumerate(g.prims or []):
        if not isinstance(p, dict):
            findings.append(Finding(sid, f"primitive {i}: not a mapping", SEVERITY_ERROR, f"prim[{i}]"))
            continue
        k = p.get("k")
        if k not in ("line", "poly", "circle", "text"):
            findings.append(Finding(sid, f"primitive {i}: unsupported or malformed kind {k!r}",
                                    SEVERITY_ERROR, f"prim[{i}]"))
        if k in ("line", "poly"):
            pts = p.get("pts") or []
            for j, pt in enumerate(pts):
                if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                    findings.append(Finding(sid, f"primitive {i}: point {j} malformed",
                                            SEVERITY_ERROR, f"prim[{i}]"))
                else:
                    _check_coordinates(f"primitive {i} point {j}", pt[0], pt[1], sid, findings)
        elif k == "circle":
            c = p.get("c")
            if not (isinstance(c, (list, tuple)) and len(c) == 2):
                findings.append(Finding(sid, f"primitive {i}: circle centre malformed",
                                        SEVERITY_ERROR, f"prim[{i}]"))
            else:
                _check_coordinates(f"primitive {i} centre", c[0], c[1], sid, findings)
            r = p.get("r")
            if not _finite_number(r) or float(r) <= 0:
                findings.append(Finding(sid, f"primitive {i}: invalid radius {r!r}",
                                        SEVERITY_ERROR, f"prim[{i}]"))
        elif k == "text":
            pt = p.get("p")
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                findings.append(Finding(sid, f"primitive {i}: text position malformed",
                                        SEVERITY_ERROR, f"prim[{i}]"))
            else:
                _check_coordinates(f"primitive {i} text", pt[0], pt[1], sid, findings)
    for t in g.terminals or []:
        if not isinstance(t, Terminal):
            findings.append(Finding(sid, "terminal entry is not a Terminal", SEVERITY_ERROR))
            continue
        if not t.name:
            findings.append(Finding(sid, "terminal has empty name/id", SEVERITY_ERROR, "terminal"))
        _check_coordinates(f"terminal {t.name}", t.x, t.y, sid, findings, require_grid=True)
        if t.dir not in ("l", "r", "u", "d"):
            findings.append(Finding(sid, f"terminal {t.name}: invalid direction {t.dir!r}",
                                    SEVERITY_ERROR, t.name))
        if t.ptype and t.ptype not in PORT_TYPES and t.ptype != "":
            findings.append(Finding(sid, f"terminal {t.name}: unknown port type {t.ptype!r}",
                                    SEVERITY_WARNING, t.name))


def validate_symbol_def(sd: SymbolDef, *, params: Optional[dict] = None) -> list:
    """Inspect one SymbolDef. Never mutates ``sd`` or its geometry."""
    findings = []
    sid = getattr(sd, "id", None) or ""
    if not sid or not isinstance(sid, str):
        findings.append(Finding(sid or "<missing>", "missing or invalid symbol identifier", SEVERITY_ERROR))
        sid = sid or "<missing>"
    if not (getattr(sd, "name", None) or "").strip():
        findings.append(Finding(sid, "symbol name is empty", SEVERITY_WARNING))
    try:
        g = sd.build(params)
    except Exception as e:
        findings.append(Finding(sid, f"failed to build geometry: {e}", SEVERITY_ERROR))
        return findings
    _check_geometry(g, sid, findings)
    if sd.custom is not None and not isinstance(sd.custom, dict):
        findings.append(Finding(sid, "custom metadata is not a dict", SEVERITY_ERROR))
    return findings


def validate_document(doc: dict, *, deep_copy: bool = True) -> list:
    """Inspect a raw custom-symbol document without normalising or mutating it."""
    findings = []
    if deep_copy:
        doc = copy.deepcopy(doc)
    if not isinstance(doc, dict):
        return [Finding("<unknown>", "symbol document is not a JSON object", SEVERITY_ERROR)]
    sid = str(doc.get("id") or "") or "<missing-id>"
    if doc.get("format") != SYMBOL_FORMAT:
        findings.append(Finding(sid, f"missing or invalid format field (expected {SYMBOL_FORMAT!r})",
                                SEVERITY_ERROR))
    ver = doc.get("version", 1)
    if not isinstance(ver, int):
        findings.append(Finding(sid, f"version must be an integer, got {type(ver).__name__}",
                                SEVERITY_ERROR))
    elif ver < 1:
        findings.append(Finding(sid, f"unsupported schema version {ver}", SEVERITY_ERROR))
    elif ver > SYMBOL_VERSION:
        findings.append(Finding(sid, f"symbol format version {ver} is newer than supported "
                                f"({SYMBOL_VERSION})", SEVERITY_ERROR))
    if not sid.startswith(USER_PREFIX) or len(sid) <= len(USER_PREFIX):
        findings.append(Finding(sid, "custom symbol id must start with 'user:' and include a unique suffix",
                                SEVERITY_ERROR))
    if not isinstance(doc.get("name", ""), (str, type(None))):
        findings.append(Finding(sid, "name must be a string", SEVERITY_ERROR))
    if "properties" in doc and doc["properties"] is not None and not isinstance(doc["properties"], dict):
        findings.append(Finding(sid, "properties must be an object/dict", SEVERITY_ERROR))
    if "tags" in doc and doc["tags"] is not None and not isinstance(doc["tags"], (list, tuple)):
        findings.append(Finding(sid, "tags must be a list", SEVERITY_ERROR))

    seen_pins = set()
    pins = doc.get("pins")
    if pins is None:
        pass
    elif not isinstance(pins, list):
        findings.append(Finding(sid, "pins must be a list", SEVERITY_ERROR))
    else:
        for i, p in enumerate(pins):
            if not isinstance(p, dict):
                findings.append(Finding(sid, f"pin {i}: not an object", SEVERITY_ERROR, f"pin[{i}]"))
                continue
            pid = str(p.get("id") or "")
            if not pid:
                findings.append(Finding(sid, f"pin {i}: missing id", SEVERITY_ERROR, f"pin[{i}]"))
            elif pid in seen_pins:
                findings.append(Finding(sid, f"duplicate pin id {pid}", SEVERITY_ERROR, pid))
            else:
                seen_pins.add(pid)
            _check_coordinates(f"pin {pid or i}", p.get("x"), p.get("y"), sid, findings, require_grid=True)
            d = p.get("dir", "r")
            if d not in ("l", "r", "u", "d"):
                findings.append(Finding(sid, f"pin {pid or i}: invalid direction {d!r}",
                                        SEVERITY_ERROR, pid or f"pin[{i}]"))
            ptype = p.get("type") or ""
            if ptype and ptype not in PORT_TYPES:
                findings.append(Finding(sid, f"pin {pid or i}: unknown port type {ptype!r}",
                                        SEVERITY_WARNING, pid or f"pin[{i}]"))

    prims = doc.get("prims")
    if prims is None:
        pass
    elif not isinstance(prims, list):
        findings.append(Finding(sid, "prims must be a list", SEVERITY_ERROR))
    else:
        for i, p in enumerate(prims):
            if not isinstance(p, dict):
                findings.append(Finding(sid, f"primitive {i}: not an object", SEVERITY_ERROR, f"prim[{i}]"))
                continue
            k = p.get("k")
            if k not in PRIM_KINDS:
                findings.append(Finding(sid, f"primitive {i}: unsupported kind {k!r}",
                                        SEVERITY_ERROR, f"prim[{i}]"))
                continue
            if k in ("line", "poly"):
                pts = p.get("pts")
                if not isinstance(pts, (list, tuple)) or len(pts) < 2:
                    findings.append(Finding(sid, f"primitive {i}: needs at least two points",
                                            SEVERITY_ERROR, f"prim[{i}]"))
                else:
                    for j, pt in enumerate(pts):
                        if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                            findings.append(Finding(sid, f"primitive {i}: point {j} malformed",
                                                    SEVERITY_ERROR, f"prim[{i}]"))
                        else:
                            _check_coordinates(f"primitive {i} pt {j}", pt[0], pt[1], sid, findings)
            elif k in ("circle", "arc"):
                c = p.get("c")
                if not (isinstance(c, (list, tuple)) and len(c) == 2):
                    findings.append(Finding(sid, f"primitive {i}: centre malformed",
                                            SEVERITY_ERROR, f"prim[{i}]"))
                else:
                    _check_coordinates(f"primitive {i} centre", c[0], c[1], sid, findings)
                r = p.get("r")
                if not _finite_number(r) or float(r) <= 0:
                    findings.append(Finding(sid, f"primitive {i}: invalid radius {r!r}",
                                            SEVERITY_ERROR, f"prim[{i}]"))
                if k == "arc":
                    for field_name in ("start", "extent"):
                        if field_name in p and not _finite_number(p.get(field_name)):
                            findings.append(Finding(sid, f"primitive {i}: invalid {field_name}",
                                                    SEVERITY_ERROR, f"prim[{i}]"))
            elif k == "text":
                pt = p.get("p")
                if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                    findings.append(Finding(sid, f"primitive {i}: text position malformed",
                                            SEVERITY_ERROR, f"prim[{i}]"))
                else:
                    _check_coordinates(f"primitive {i} text", pt[0], pt[1], sid, findings)

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
                findings.append(Finding(path, "file is empty or truncated", SEVERITY_ERROR, path))
                continue
            data = json.loads(raw)
        except FileNotFoundError:
            findings.append(Finding(path, f"file not found: {path}", SEVERITY_ERROR, path))
            continue
        except json.JSONDecodeError as e:
            findings.append(Finding(path, f"invalid JSON: {e.msg} at line {e.lineno} column {e.colno}",
                                    SEVERITY_ERROR, path))
            continue
        except OSError as e:
            findings.append(Finding(path, f"could not read file: {e}", SEVERITY_ERROR, path))
            continue
        doc_findings = validate_document(data)
        for fnd in doc_findings:
            if not fnd.location:
                findings.append(Finding(fnd.symbol_id, fnd.problem, fnd.severity, path))
            else:
                findings.append(fnd)

    if json_out:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    else:
        if not findings:
            print("No integrity problems found.")
        else:
            for f in findings:
                loc = f" ({f.location})" if f.location else ""
                print(f"[{f.severity}] {f.symbol_id}{loc}: {f.problem}")
            print(f"\n{len(findings)} finding(s).")
    errors = sum(1 for f in findings if f.severity == SEVERITY_ERROR)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
