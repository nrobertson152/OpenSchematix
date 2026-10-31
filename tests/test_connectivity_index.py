"""Regression tests for the spatial index in connectivity.analyse (Phase 4).

The index must be invisible: for any document, analyse() returns exactly what
the original full-scan algorithm returned (same junctions, open ends and
terminals, in the same order). `reference_analyse` below is a verbatim copy of
the pre-index algorithm and serves as the oracle.
"""
import math
import random

import pytest

from openschematix import connectivity, editing
from openschematix.connectivity import Connectivity, _key, analyse
from openschematix.geometry import point_on_segment, same
from openschematix.model import Document, Wire


def reference_analyse(doc) -> Connectivity:
    """The original O(points x wires) algorithm (main @ dc163ea), unchanged."""
    res = Connectivity()
    wires = list(doc.wires.values())
    terminals = []
    for c in doc.components.values():
        for name, p in c.terminals().items():
            terminals.append((c.id, name, p))
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
                through += 1
        return ends, through

    term_at = {}
    for cid, name, p in terminals:
        term_at.setdefault(_key(p), []).append((cid, name))
    for k, p in candidates.items():
        ends, through = counts_at(p)
        terms = len(term_at.get(k, []))
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


def _fingerprint(c: Connectivity):
    # repr() keeps order and compares NaN coordinates as text
    return repr((c.junctions, c.open_wire_ends, c.open_terminals, sorted(c.connected_terminals)))


def assert_same_as_reference(doc):
    got, want = analyse(doc), reference_analyse(doc)
    assert _fingerprint(got) == _fingerprint(want)
    return got


def raw_wire(doc, pts):
    """Add a wire WITHOUT editing.add_wire normalisation (to reach odd geometry)."""
    w = Wire(doc.new_id(), [tuple(map(float, p)) for p in pts])
    doc.wires[w.id] = w
    return w


# ---------------------------------------------------------------- explicit semantics
def test_t_junction_crossing_and_terminal_rules_unchanged():
    doc = Document()
    editing.add_wire(doc, [(0, 0), (100, 0)])
    editing.add_wire(doc, [(50, 0), (50, 50)])         # T-junction -> dot
    editing.add_wire(doc, [(80, -30), (80, 30)])       # crossing -> no dot
    r = editing.place(doc, "el.resistor.iec", 300, 100)
    editing.add_wire(doc, [(260, 100), (340, 100)])    # passes over both terminals: not connected
    c = assert_same_as_reference(doc)
    assert c.junctions == [(50.0, 0.0)]
    assert {(cid, n) for cid, n, _ in c.open_terminals} == {(r.id, "1"), (r.id, "2")}


@pytest.mark.parametrize("off,connected", [(0.009, True), (0.01, True), (0.011, False), (-0.0099, True),
                                           (-0.0101, False)])
def test_tolerance_boundary_is_exact(off, connected):
    # end point of the stub lies `off` away from the bus; the bus straddles a cell boundary at x=50
    doc = Document()
    bus = raw_wire(doc, [(0, 0), (100, 0)])
    stub = raw_wire(doc, [(50, 40), (50, off)])
    c = assert_same_as_reference(doc)
    open_stub_end = (stub.id, (50.0, off)) in c.open_wire_ends
    assert open_stub_end is (not connected)
    assert (bus.id, (0.0, 0.0)) in c.open_wire_ends


def test_tiny_diagonal_overshoot_across_cell_boundary():
    """point_on_segment accepts points ~tol/length beyond a very short diagonal
    segment. The index padding must cover this (pre-existing behaviour), even
    when the point is in a different grid cell than the segment."""
    a, b, p = (50.3, 50.3), (50.312, 50.312), (49.95, 49.95)
    assert point_on_segment(p, a, b)                   # documents the quirk being preserved
    assert connectivity._cell(p[0]) != connectivity._cell(a[0] - connectivity._TOL)
    doc = Document()
    raw_wire(doc, [a, b])
    w2 = raw_wire(doc, [p, (0.0, 49.95)])
    c = assert_same_as_reference(doc)
    assert (w2.id, p) not in c.open_wire_ends


@pytest.mark.parametrize("x", [-100.0, -50.0, -0.004, 0.0, 49.995, 50.0, 50.004, 99.99, 1e6])
def test_points_on_cell_boundaries(x):
    doc = Document()
    raw_wire(doc, [(x, -200), (x, 200)])               # vertical through the point
    raw_wire(doc, [(x - 70, 0), (x, 0)])               # T onto it
    raw_wire(doc, [(x + 0.006, 0), (x + 90, 0)])       # within tolerance from the other side
    assert_same_as_reference(doc)


def test_long_and_diagonal_segments_use_the_always_list():
    doc = Document()
    rail = raw_wire(doc, [(0, 0), (100000, 0)])        # 2000 cells wide: too many, always examined
    diag = raw_wire(doc, [(0, 0), (5000, 5000)])       # large bbox: always examined
    for x in range(1000, 99000, 7000):
        raw_wire(doc, [(x, 300), (x, 0)])              # T-junctions far along the rail
    raw_wire(doc, [(2500, 2500), (2500, 3000)])        # ends on the diagonal
    c = assert_same_as_reference(doc)
    idx = connectivity._WireIndex(list(doc.wires.values()))
    assert rail in idx.always and diag in idx.always
    assert c.junctions[:-1] == [(float(x), 0.0) for x in range(1000, 99000, 7000)]
    assert c.junctions[-1] == (2500.0, 2500.0)       # T onto the diagonal


def test_degenerate_wires():
    doc = Document()
    raw_wire(doc, [(10, 10), (10, 10)])                # zero length (counts as two ends)
    raw_wire(doc, [(10, 10), (40, 10)])
    raw_wire(doc, [(0, 0), (30, 0), (0, 0)])           # returns to its start
    raw_wire(doc, [(0, 0), (30, 0), (0, 0)])           # duplicate
    raw_wire(doc, [(5, 5)])                            # single point
    w = Wire(doc.new_id(), [(0, 0), (20, 0)])
    doc.wires[w.id] = w
    w.points = [(0, 0), (0, 0), (20, 0)]               # repeated vertex
    assert_same_as_reference(doc)


def test_non_finite_coordinates():
    doc = Document()
    inf = raw_wire(doc, [(math.inf, 0), (0, 0)])
    nan = raw_wire(doc, [(math.nan, 5), (10, 10)])
    raw_wire(doc, [(0, 0), (0, 50)])
    raw_wire(doc, [(10, 10), (10, 60)])
    assert_same_as_reference(doc)
    idx = connectivity._WireIndex(list(doc.wires.values()))
    assert inf in idx.always and nan in idx.always


def test_output_order_is_deterministic():
    doc = _ladder(3, 3)
    a, b = analyse(doc), analyse(doc)
    assert _fingerprint(a) == _fingerprint(b) == _fingerprint(reference_analyse(doc))


# ---------------------------------------------------------------- memory bound
def test_index_memory_is_linear_in_segments():
    doc = Document()
    rnd = random.Random(3)
    for _ in range(2000):     # long diagonals just under the per-segment cell cap
        x, y = rnd.uniform(-1e4, 1e4), rnd.uniform(-1e4, 1e4)
        raw_wire(doc, [(x, y), (x + 700, y + 700)])
    wires = list(doc.wires.values())
    idx = connectivity._WireIndex(wires)
    nseg = len(wires)
    budget = connectivity._ENTRY_BUDGET_PER_SEGMENT * nseg + connectivity._ENTRY_BUDGET_MIN
    assert 0 < idx.entries <= budget
    assert idx.entries == sum(len(v) for v in idx.cells.values())
    assert idx.always                                  # budget exhausted -> rest always examined
    # huge diagonals never touch the grid at all
    big = Document()
    for i in range(200):
        raw_wire(big, [(-1e9, -1e9 + i), (1e9, 1e9 + i)])
    idx = connectivity._WireIndex(list(big.wires.values()))
    assert idx.entries == 0 and len(idx.always) == 200


def test_per_segment_cell_cap():
    assert connectivity._WireIndex._cells_of([(0, 0), (40 * connectivity._CELL, 0)]) is not None
    keys = connectivity._WireIndex._cells_of([(0, 0), (40 * connectivity._CELL, 0)])
    assert len(keys) <= connectivity._MAX_CELLS_PER_SEGMENT
    side = math.sqrt(connectivity._MAX_CELLS_PER_SEGMENT) * connectivity._CELL * 1.5
    assert connectivity._WireIndex._cells_of([(0, 0), (side, side)]) is None


# ---------------------------------------------------------------- index superset property
def test_index_candidates_include_every_matching_wire():
    rnd = random.Random(99)
    for _ in range(200):
        doc = _random_doc(rnd)
        wires = list(doc.wires.values())
        idx = connectivity._WireIndex(wires)
        probes = [p for w in wires for p in w.points]
        probes += [(rnd.uniform(-50, 250), rnd.uniform(-50, 250)) for _ in range(20)]
        for p in probes:
            cand = {id(w) for w in idx.candidates(p, wires)}
            for w in wires:
                pts = w.points
                hit = same(pts[0], p) or same(pts[-1], p) or \
                    any(point_on_segment(p, a, b) for a, b in zip(pts, pts[1:]))
                if hit:
                    assert id(w) in cand, (p, pts)


# ---------------------------------------------------------------- differential, seeded
SYMS = ["el.contact.no.iec", "el.resistor.iec", "el.coil.iec", "el.transformer", "el.npn", "el.earth"]


def _random_doc(rnd):
    d = Document()
    span = rnd.choice([60, 200, 2000])
    step = rnd.choice([10, 5, 1])

    def pt():
        x, y = float(rnd.randrange(-span // 4, span, step)), float(rnd.randrange(-span // 4, span, step))
        r = rnd.random()
        if r < 0.08:
            x += rnd.choice([0.004, -0.009, 0.0101, 0.015, -0.02])
        elif r < 0.12:
            y += rnd.choice([0.004, -0.009, 0.0101, 0.015, -0.02])
        return (x, y)
    for _ in range(rnd.randrange(0, 12)):
        editing.place(d, rnd.choice(SYMS), rnd.randrange(0, span, 10), rnd.randrange(0, span, 10),
                      rnd.choice([0, 90, 180, 270]), rnd.random() < 0.3)
    terms = [tp for c in d.components.values() for tp in c.terminals().values()]
    for _ in range(rnd.randrange(1, 35)):
        n = rnd.choice([2, 2, 2, 3, 4, 6])
        mode = rnd.random()
        if mode < 0.5:        # orthogonal
            pts = [pt()]
            for _ in range(n - 1):
                q = pt()
                pts.append((q[0], pts[-1][1]) if rnd.random() < 0.5 else (pts[-1][0], q[1]))
        elif mode < 0.7:      # general direction
            pts = [pt() for _ in range(n)]
        elif mode < 0.8:      # very short diagonal (along-segment tolerance overshoot)
            a = pt()
            pts = [a, (a[0] + rnd.choice([0.012, 0.02, 0.05, 0.3]), a[1] + rnd.choice([0.011, 0.02, 0.07, 0.3]))]
            if rnd.random() < 0.5:    # a wire ending just before it, along its direction
                dx, dy = pts[1][0] - a[0], pts[1][1] - a[1]
                k = rnd.uniform(0.0, 0.9) / math.hypot(dx, dy)
                raw_wire(d, [(a[0] - dx * k, a[1] - dy * k), pt()])
        elif mode < 0.9 and terms:   # to / over terminals
            a, b = rnd.choice(terms), rnd.choice(terms)
            pts = [a, (b[0], a[1]), b] if rnd.random() < 0.5 else [a, b]
        else:                 # degenerate / duplicate
            a = pt()
            if d.wires and rnd.random() < 0.5:
                pts = list(rnd.choice(list(d.wires.values())).points)
            else:
                pts = [a, a] if rnd.random() < 0.5 else [a, pt(), a]
        raw_wire(d, pts)
    r = rnd.random()
    if r < 0.04:
        raw_wire(d, [(math.inf, 0.0), (0.0, 0.0)])
    elif r < 0.08:
        raw_wire(d, [(math.nan, 5.0), (10.0, 10.0)])
    elif r < 0.12:
        raw_wire(d, [(-1e5, -1e5), (1e5, 1.3e5)])
    return d


@pytest.mark.parametrize("seed", range(6))
def test_differential_random_documents(seed):
    rnd = random.Random(1000 + seed)
    for _ in range(250):
        assert_same_as_reference(_random_doc(rnd))


def _ladder(cols, rows):
    d = Document()
    for bc in range(cols):
        for br in range(rows):
            x0, y0 = 80 + bc * 400, 80 + br * 500
            editing.add_wire(d, [(x0, y0), (x0, y0 + 440)])
            editing.add_wire(d, [(x0 + 300, y0), (x0 + 300, y0 + 440)])
            for r in range(8):
                y = y0 + 20 + r * 50
                k1 = editing.place(d, "el.contact.no.iec", x0 + 60, y)
                k2 = editing.place(d, "el.resistor.iec", x0 + 180, y)
                editing.add_wire(d, [(x0, y), k1.terminals()["1"]])
                editing.add_wire(d, [k1.terminals()["2"], k2.terminals()["1"]])
                editing.add_wire(d, [k2.terminals()["2"], (x0 + 300, y)])
            editing.add_wire(d, [(x0 + 100, y0 - 10), (x0 + 100, y0 + 450)])
    return d


def test_differential_ladder_drawing():
    assert_same_as_reference(_ladder(3, 2))


def test_example_projects_unchanged():
    import glob
    import os
    from openschematix import projectio
    root = os.path.join(os.path.dirname(__file__), "..", "examples")
    n = 0
    for path in sorted(glob.glob(os.path.join(root, "*"))):
        res = projectio.open_any(path)
        for doc in res.project.sheets:
            assert_same_as_reference(doc)
            n += 1
    assert n >= 3
