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

CLI (``python -m openschematix.symbols.integrity``)
-------------------------------------------------
* Without paths (or with ``--builtins``): audits the built-in library.
* With paths: audits each ``.osym`` / JSON file (does **not** call
  ``normalise``; a document that loads after repair may still report findings).
* Exit code **0** if there are no error-severity findings; **1** otherwise
  (warnings alone still exit 0).
* ``--json`` prints structured findings including ``source`` and ``location``.
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
