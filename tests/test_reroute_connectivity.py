"""Re-routing a wire after its component moves must not create connections.

A rerouted path that runs over another wire's end point joins the two nets at a
T-junction. Before the fix, rotating a transformer with a short wire on each
terminal shorted S1 to S2 this way.
"""
from __future__ import annotations

import pytest

from openschematix import editing, netlist, symbols
from openschematix.geometry import GRID
from openschematix.project import new_project

OUT = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}
BUILTINS = [s for s in symbols.builtin_symbols() if s.group != "Internal" and s.build(None).terminals]


def _wired(symbol_id, x, y):
    p = new_project("t")
    doc = p.sheets[0]
    c = editing.place(doc, symbol_id, x, y)
    for name, (tx, ty) in c.terminals().items():
        dx, dy = OUT[c.terminal_dirs()[name]]
        assert editing.add_wire(doc, [(tx, ty), (tx + dx * 3 * GRID, ty + dy * 3 * GRID)]) is not None
    return p, doc, c


def _terminal_nets(p):
    return sorted(sorted(t[2] for t in n.terminals) for n in netlist.compute_nets(p))


def test_rotating_a_transformer_does_not_short_its_windings():
    p, doc, c = _wired("el.transformer", -37 * GRID, 23 * GRID)
    before = _terminal_nets(p)
    assert before == [["P1"], ["P2"], ["S1"], ["S2"]]
    editing.rotate_items(doc, [c.id], [], clockwise=True)
    assert _terminal_nets(p) == before


def test_a_pin_turned_onto_a_wire_of_the_same_part_does_not_join_it():
    """Turning a part about one of its pins leaves that pin, and so its wire, in place, but can swing
    another pin onto that wire. The wire must be re-routed, not joined to the other pin."""
    p = new_project("t")
    doc = p.sheets[0]
    r = editing.place(doc, "el.resistor.iec", 0, 0)
    t1 = r.terminals()["1"]
    w = editing.add_wire(doc, [t1, (t1[0] - 6 * GRID, t1[1])])
    assert w is not None and w.start
    before = _terminal_nets(p)
    assert before == [["1"]]
    editing.rotate_items(doc, [r.id], [], clockwise=True, center=t1)
    editing.rotate_items(doc, [r.id], [], clockwise=True, center=t1)
    assert r.terminals()["1"] == t1
    from openschematix.geometry import point_on_segment
    assert not any(point_on_segment(r.terminals()["2"], a, b) for a, b in zip(w.points, w.points[1:])), w.points
    assert _terminal_nets(p) == before


@pytest.mark.parametrize("sd", BUILTINS, ids=lambda s: s.id)
def test_rotating_and_mirroring_never_merges_terminal_nets(sd):
    p, doc, c = _wired(sd.id, -37 * GRID, 23 * GRID)
    before = _terminal_nets(p)
    for op in ("rot", "rot", "rot", "rot", "mirror", "rot", "rot", "rot", "rot", "mirror", "ccw", "mirror", "ccw"):
        if op == "mirror":
            editing.mirror_items(doc, [c.id], [])
        else:
            editing.rotate_items(doc, [c.id], [], clockwise=(op == "rot"))
        assert _terminal_nets(p) == before, (sd.id, op)


def test_rerouting_keeps_a_junction_made_on_the_wire():
    """A wire end joined to the middle of the moved wire (a T-junction) stays joined."""
    p = new_project("t")
    doc = p.sheets[0]
    r = editing.place(doc, "el.resistor.iec", 0, 0)
    lamp = editing.place(doc, "el.lamp.iec", 40 * GRID, 0)
    a = editing.add_wire(doc, [r.terminals()["2"], lamp.terminals()["1"]])
    assert a is not None and a.start and a.end
    mid = ((a.points[0][0] + a.points[-1][0]) / 2, a.points[0][1])
    tap = editing.add_wire(doc, [(snap_x := round(mid[0] / GRID) * GRID, mid[1]), (snap_x, mid[1] + 8 * GRID)])
    assert tap is not None
    before = _terminal_nets(p)
    nets_before = len(netlist.compute_nets(p))
    for clockwise in (True, True, False, True):
        editing.rotate_items(doc, [r.id], [], clockwise=clockwise)
        assert _terminal_nets(p) == before, clockwise
        assert len(netlist.compute_nets(p)) == nets_before, "the tap wire came off the net"
