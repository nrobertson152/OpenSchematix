"""Immutable value types returned by the OpenSchematix scripting API.

These are plain snapshots: they never change after they are returned and
modifying the project does not update them. Query again to see the current
state. Coordinates are drawing units (1 unit = 0.25 mm), Y pointing down.
"""
from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float]


@dataclass(frozen=True)
class SymbolTerminal:
    """A connection point of a symbol, in symbol-local coordinates
    (relative to the insertion point, before rotation and mirroring)."""
    name: str          # permanent key used by wires, e.g. "1", "A1", "P"
    label: str         # displayed designation
    x: float
    y: float
    direction: str     # outward lead direction: "l", "r", "u" or "d"
    port_type: str     # e.g. "elec.passive", "hyd.pressure" (see docs/VALIDATION.md)


@dataclass(frozen=True)
class SymbolInfo:
    """Description of a symbol that can be placed."""
    id: str
    name: str
    category: str      # Electrical, Electronic, Hydraulic, Pneumatic, General, ...
    group: str
    convention: str
    description: str
    prefix: str        # default designator prefix, e.g. "K"
    parametric: bool   # True if it accepts params (e.g. directional valves)
    default_params: dict = field(hash=False, compare=False)
    terminals: tuple[SymbolTerminal, ...] = ()
    custom: bool = False


@dataclass(frozen=True)
class Terminal:
    """A connection point of a placed component, in world coordinates."""
    name: str
    label: str
    position: Point
    direction: str     # outward lead direction after rotation/mirroring
    port_type: str


@dataclass(frozen=True)
class TerminalRef:
    """A component terminal anywhere in the project."""
    sheet_uid: str
    sheet_name: str
    component_id: int
    designator: str
    terminal: str


@dataclass(frozen=True)
class Net:
    """An electrically / fluidically connected set of terminals and wires
    (sheet connectors with the same label join nets across sheets)."""
    number: str                               # wire number, "" if not numbered
    terminals: tuple[TerminalRef, ...]
    wires: tuple[tuple[str, int], ...]        # (sheet uid, wire id)
    sheets: tuple[str, ...]                   # sheet uids


@dataclass(frozen=True)
class SheetConnectivity:
    """Connection analysis of one sheet."""
    junctions: tuple[Point, ...]                             # points drawn with a junction dot
    open_wire_ends: tuple[tuple[int, Point], ...]            # (wire id, point)
    open_terminals: tuple[tuple[int, str, Point], ...]       # (component id, terminal, point)
    connected_terminals: frozenset[tuple[int, str]]          # (component id, terminal)


@dataclass(frozen=True)
class BomItem:
    """One line of the bill of materials."""
    item: int
    quantity: int
    designators: tuple[str, ...]
    designator_text: str      # compressed, e.g. "K1-K3, K5"
    description: str
    manufacturer: str
    part_number: str
    rating: str
    symbol: str
    sheets: tuple[str, ...]   # sheet names


@dataclass(frozen=True)
class Issue:
    """A finding of the drawing checker (Check Drawing)."""
    severity: str             # "error", "warning" or "info"
    code: str                 # rule id, e.g. "duplicate-id", "open-terminal"
    message: str
    sheet_uid: str
    object_id: int | None
    suggestion: str
