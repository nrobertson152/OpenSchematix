"""Connection analysis: junction dots, unconnected wire ends and terminals.

Rules (common schematic practice):
  * Wires are connected where an end point of one wire lies on another wire
    (end, corner or anywhere along a segment).
  * Component terminals connect only to wire END points; a wire that merely
    passes over a terminal is not connected to it (same rule as KiCad).
  * Two wires that merely cross are NOT connected.
  * A junction dot is drawn where three or more branches meet.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import point_on_segment, same
from .model import Document


@dataclass
class Connectivity:
    junctions: list = field(default_factory=list)          # points needing a dot
    open_wire_ends: list = field(default_factory=list)     # (wire_id, point)
    open_terminals: list = field(default_factory=list)     # (comp_id, name, point)
    connected_terminals: set = field(default_factory=set)  # (comp_id, name)


def _key(p):
    return (round(p[0], 2), round(p[1], 2))


def analyse(doc: Document) -> Connectivity:
    res = Connectivity()
    wires = list(doc.wires.values())
    terminals = []  # (cid, name, point)
    for c in doc.components.values():
        for name, p in c.terminals().items():
            terminals.append((c.id, name, p))

    # candidate points: wire end points and wire corners
    candidates = {}
    for w in wires:
        for p in w.points:
            candidates[_key(p)] = p

    def counts_at(p, exclude_wire=None):
        ends = through = 0
        for w in wires:
            if w.id == exclude_wire:
                continue
            pts = w.points
            if same(pts[0], p) or same(pts[-1], p):
                ends += 1 + (1 if len(pts) == 2 and same(pts[0], pts[-1]) else 0)
            elif any(point_on_segment(p, a, b) for a, b in zip(pts, pts[1:])):
                through += 1  # passes through (corner or along a segment)
        return ends, through

    term_at = {}
    for cid, name, p in terminals:
        term_at.setdefault(_key(p), []).append((cid, name))

    for k, p in candidates.items():
        ends, through = counts_at(p)
        terms = len(term_at.get(k, []))
        # A wire that merely passes over a point connects there only if some
        # wire *ends* at that point (T-junction). Terminals connect only to
        # wire end points.
        n = ends + terms + (2 * through if ends else 0)
        if n >= 3:
            res.junctions.append(p)

    for w in wires:
        for idx in (0, -1):
            p = w.points[idx]
            if _key(p) in term_at:
                continue
            ends, through = counts_at(p, exclude_wire=w.id)
            if ends == 0 and through == 0:
                res.open_wire_ends.append((w.id, p))

    end_points = {_key(w.points[i]) for w in wires for i in (0, -1)}
    for cid, name, p in terminals:
        k = _key(p)
        if k in end_points or len(term_at.get(k, [])) > 1:
            res.connected_terminals.add((cid, name))
        else:
            res.open_terminals.append((cid, name, p))
    return res
