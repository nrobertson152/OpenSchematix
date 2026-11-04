"""OpenSchematix scripting API (headless).

Create, open, edit, inspect, check and save OpenSchematix projects from
Python scripts without starting the graphical interface. Importing this
package never imports tkinter or opens a window, and nothing here uses the
network.

    from openschematix import api

    project = api.new_project("Motor starter")
    sheet = project.sheets[0]
    k1 = sheet.place("el.coil.iec", 200, 200)
    s1 = sheet.place("el.pushbutton.no.iec", 100, 200)
    sheet.connect(s1, "2", k1, "A2")
    project.save("starter.schematix")

The API is a thin layer over the application's own engine (placement,
wiring, connectivity, BOM, checking and the ``.schematix`` format), so a
project made by a script is identical to one drawn by hand. Invalid input
raises an :class:`ApiError` subclass and leaves the project unchanged.

Only the names exported here are public and stable; other modules of the
``openschematix`` package are internal. See docs/SCRIPTING_API.md.
"""
from __future__ import annotations

from ._core import (ROTATIONS, Component, Project, Sheet, Wire, get_symbol, list_symbols, load_user_library,
                    new_project, open_project)
from .errors import ApiError, InvalidOperationError, ObjectNotFoundError, ProjectFileError, SymbolNotFoundError
from .types import (BomItem, Issue, Net, Point, SheetConnectivity, SymbolInfo, SymbolTerminal, Terminal,
                    TerminalRef)

API_VERSION = 1
"""Incremented on incompatible changes to the public API."""

from ..geometry import GRID, UNIT_MM  # noqa: E402  (10 units grid step; 0.25 mm per unit)

__all__ = [
    "API_VERSION", "GRID", "UNIT_MM", "ROTATIONS",
    # entry points
    "new_project", "open_project", "list_symbols", "get_symbol", "load_user_library",
    # handles
    "Project", "Sheet", "Component", "Wire",
    # values
    "SymbolInfo", "SymbolTerminal", "Terminal", "TerminalRef", "Net", "SheetConnectivity", "BomItem", "Issue",
    "Point",
    # errors
    "ApiError", "SymbolNotFoundError", "ObjectNotFoundError", "InvalidOperationError", "ProjectFileError",
]
