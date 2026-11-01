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
from ..model import (DEFAULT_LAYER_COMPONENTS, DEFAULT_LAYER_WIRES, SHEET_SIZES_MM, WIRE_STYLES,
                     Component as _Component, Document, Wire as _Wire)
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
    """Register this project's embedded symbols in the process-wide registry.

    Always re-applies the project's symbols so identically named custom
    definitions from another project cannot silently remain active when the
    script switches projects (the registry is process-wide).
    """
    global _active
    p.activate_symbols()
    _active = weakref.ref(p)


def _invalidate() -> None:
    global _active
    _active = None


# ---------------------------------------------------------------- validation helpers
def _num(v, what: str) -> float:
    """Finite float, or InvalidOperationError. Never raises OverflowError."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise InvalidOperationError(f"{what} must be a finite number, got {v!r}")
    try:
        if not math.isfinite(v):
            raise InvalidOperationError(f"{what} must be a finite number, got {v!r}")
    except (TypeError, ValueError, OverflowError) as e:
        raise InvalidOperationError(f"{what} must be a finite number, got {v!r}") from e
    try:
        f = float(v)
    except (OverflowError, ValueError, TypeError) as e:
        raise InvalidOperationError(f"{what} must be a finite number, got {v!r}") from e
    if not math.isfinite(f):
        raise InvalidOperationError(f"{what} must be a finite number, got {v!r}")
    return f
