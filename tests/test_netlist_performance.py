"""Netlist performance and spatial-index equivalence.

``compute_nets`` must agree with a naive O(W^2) reference on small and
adversarial sheets (membership, terminal sets, deterministic net indices),
and must scale near-linearly so large engineering drawings stay interactive.
"""
from __future__ import annotations

import time

from openschematix import editing, netlist
from openschematix.connectivity import _CELL, _PAD
from openschematix.project import new_project
from openschematix.symbols.general import OFFPAGE_IDS


def _key(p):
    return (round(p[0], 2), round(p[1], 2))


class _FullScan:
    """Stand-in for the spatial index that returns every wire (the pre-index O(W^2) scan)."""

    def __init__(self, wires):
        self.wires = list(wires)

    def candidates(self, p, wires):
        return wires


def _compute_nets_naive(project):
    """Full ``compute_nets`` path with the pre-index sheet-node scan.

    Reuses the production grouping, sorting and index assignment so that
    net membership *and* deterministic identifiers can be compared.
    """
    # The production _sheet_nodes with the index replaced by a full scan: the
    # reference differs in nothing else (pin validation and symbol scope included).
    original = netlist._WireIndex
    try:
        netlist._WireIndex = _FullScan
        return netlist.compute_nets(project)
    finally:
        netlist._WireIndex = original


def _full_signature(nets):
    """Membership + deterministic identifiers (index, number, links)."""
    return tuple(
        (
            n.index,
            n.number,
            tuple(sorted(n.wires)),
            tuple(sorted(n.terminals)),
            tuple(sorted(n.links)),
        )
        for n in nets
    )


def _membership_signature(nets):
    """Order-independent membership only (for debugging failures)."""
    return tuple(sorted(
        (tuple(sorted(n.wires)), tuple(sorted(n.terminals)), tuple(sorted(n.links)))
        for n in nets
    ))


def _assert_identical(project, label=""):
    fast = netlist.compute_nets(project)
    slow = _compute_nets_naive(project)
    assert _full_signature(fast) == _full_signature(slow), (
        f"indexed vs naive netlist mismatch{(' (' + label + ')') if label else ''}:\n"
        f"  membership fast={_membership_signature(fast)}\n"
        f"  membership slow={_membership_signature(slow)}\n"
        f"  full fast={_full_signature(fast)}\n"
        f"  full slow={_full_signature(slow)}"
    )
    return fast


def _grid_project(n_comp: int, extra_vertical: int = 0):
    p = new_project("perf")
    d = p.sheets[0]
    comps = []
    for i in range(n_comp):
        comps.append(editing.place(d, "el.resistor.iec", 100 + i * 100, 200))
    for i in range(n_comp - 1):
        ta, tb = comps[i].terminals(), comps[i + 1].terminals()
        pa = max(ta.values(), key=lambda pt: pt[0])
        pb = min(tb.values(), key=lambda pt: pt[0])
        editing.add_wire(d, [pa, (pa[0] + 20, pa[1]), (pb[0] - 20, pb[1]), pb])
    for i in range(extra_vertical):
        x = 150 + (i % max(n_comp, 1)) * 100
        editing.add_wire(d, [(x, 100), (x, 300)])
    return p


# ---------------------------------------------------------------- equivalence
def test_spatial_index_matches_naive_reference_on_varied_sheets():
    """Index only drops wires that cannot touch; nets (ids + membership) match."""
    for n in (1, 5, 15, 40):
        p = _grid_project(n, extra_vertical=n // 2)
        _assert_identical(p, label=f"grid n={n}")


def test_t_junction_and_shared_endpoint_nets():
    p = new_project("tj")
    d = p.sheets[0]
    a = editing.place(d, "el.resistor.iec", 100, 200)
    b = editing.place(d, "el.resistor.iec", 300, 200)
    c = editing.place(d, "el.resistor.iec", 200, 320)
    pa = max(a.terminals().values(), key=lambda pt: pt[0])
    pb = min(b.terminals().values(), key=lambda pt: pt[0])
    mid = ((pa[0] + pb[0]) / 2, pa[1])
    editing.add_wire(d, [pa, mid, pb])
    pc = min(c.terminals().values(), key=lambda pt: pt[1])
    editing.add_wire(d, [pc, (pc[0], mid[1]), mid])
    nets = _assert_identical(p, label="t-junction")
    terms = [t for n in nets for t in n.terminals]
    assert len({(t[1], t[2]) for t in terms}) >= 3


# ---------------------------------------------------------------- adversarial geometry
def test_adversarial_negative_coordinates_equivalence():
    """Wires entirely in the negative quadrant still index correctly."""
    p = new_project("neg")
    d = p.sheets[0]
    # Chain of horizontal and vertical wires in negative space
    editing.add_wire(d, [(-400, -200), (-200, -200)])
    editing.add_wire(d, [(-200, -200), (-200, -50)])
    editing.add_wire(d, [(-200, -50), (-50, -50)])
    editing.add_wire(d, [(-50, -50), (-50, -200)])  # separate net
    editing.add_wire(d, [(-500, -300), (-500, -100)])  # isolated
    _assert_identical(p, label="negative-coords")


def test_adversarial_cell_boundary_touching():
    """Ends exactly on grid cell boundaries must not miss neighbours."""
    p = new_project("cell")
    d = p.sheets[0]
    cell = float(_CELL)
    # Horizontal spine spanning several cells; vertical stubs end on cell edges
    editing.add_wire(d, [(0.0, 0.0), (3 * cell, 0.0)])
    for i in range(4):
        x = i * cell  # exact cell boundary
        editing.add_wire(d, [(x, 0.0), (x, 40.0)])
    # Near-boundary ends (just inside PAD of a foreign cell)
    editing.add_wire(d, [(cell - _PAD + 0.001, 80.0), (cell - _PAD + 0.001, 0.0)])
    editing.add_wire(d, [(cell + _PAD - 0.001, 80.0), (cell + _PAD - 0.001, 0.0)])
    _assert_identical(p, label="cell-boundary")


def test_adversarial_dense_intersections_and_t_stubs():
    """Many wires meeting at shared points; crossings must not join nets."""
    p = new_project("dense")
    d = p.sheets[0]
    # Hub at (200, 200): several ends meet → one net
    hub = (200.0, 200.0)
    for angle_pts in (
        [(100.0, 200.0), hub],
        [(300.0, 200.0), hub],
        [(200.0, 100.0), hub],
        [(200.0, 300.0), hub],
        [(120.0, 120.0), (160.0, 160.0), hub],
    ):
        editing.add_wire(d, angle_pts)
    # Pure crossings of the hub (mid-segment, no end on hub) → separate nets
    editing.add_wire(d, [(50.0, 250.0), (350.0, 250.0)])   # crosses vertical arm
    editing.add_wire(d, [(250.0, 50.0), (250.0, 350.0)])   # crosses horizontal arm
    nets = _assert_identical(p, label="dense-hub")
    # Hub wires share one net (5 wires); crossing wires stay separate
    sizes = sorted(len(n.wires) for n in nets)
    assert max(sizes) >= 5


def test_adversarial_overlapping_and_collinear_segments():
    """Collinear overlapping segments: ends on another wire join; pure overlap of middles does not."""
    p = new_project("overlap")
    d = p.sheets[0]
    # Collinear horizontal chain joined by end-on-segment
    editing.add_wire(d, [(0.0, 100.0), (100.0, 100.0)])
    editing.add_wire(d, [(100.0, 100.0), (200.0, 100.0)])  # shared endpoint
    editing.add_wire(d, [(150.0, 100.0), (250.0, 100.0)])  # end on first/second segment
    # Fully overlapping middle (no shared end) of a parallel net
    editing.add_wire(d, [(0.0, 200.0), (200.0, 200.0)])
    editing.add_wire(d, [(50.0, 200.0), (150.0, 200.0)])  # ends lie on the long wire → join
    # Zero-length-ish near-duplicate endpoints
    editing.add_wire(d, [(300.0, 300.0), (400.0, 300.0)])
    editing.add_wire(d, [(400.0, 300.0), (500.0, 300.0)])
    _assert_identical(p, label="overlapping-collinear")


def test_adversarial_mixed_positive_negative_and_far_away():
    """Mixed quadrants plus a far-away cluster stress cell enumeration."""
    p = new_project("mixed")
    d = p.sheets[0]
    editing.add_wire(d, [(-1000.0, 50.0), (0.0, 50.0)])
    editing.add_wire(d, [(0.0, 50.0), (0.0, -50.0)])
    editing.add_wire(d, [(0.0, -50.0), (1000.0, -50.0)])
    # Far cluster
    editing.add_wire(d, [(5000.0, 5000.0), (5100.0, 5000.0)])
    editing.add_wire(d, [(5100.0, 5000.0), (5100.0, 5100.0)])
    # Isolated point pair
    editing.add_wire(d, [(-2000.0, -2000.0), (-1900.0, -2000.0)])
    _assert_identical(p, label="mixed-quadrants")


# ---------------------------------------------------------------- performance
def _segment_tests(project):
    """Number of point-on-segment tests compute_nets makes: a measure of work that,
    unlike wall-clock time, does not depend on the machine or its load."""
    count = 0
    original = netlist.point_on_segment

    def counting(*a, **k):
        nonlocal count
        count += 1
        return original(*a, **k)
    netlist.point_on_segment = counting
    try:
        netlist.compute_nets(project)
    finally:
        netlist.point_on_segment = original
    return count


def test_compute_nets_scales_near_linearly_on_large_sheets():
    """Regression: the full wire scan made the work grow with the square of the drawing size.

    Counted, not timed: 4x the drawing must cost about 4x the segment tests (a quadratic scan
    would be about 16x). Wall-clock ratios proved too noisy on shared CI runners."""
    work = {n: _segment_tests(_grid_project(n, extra_vertical=n // 2)) for n in (100, 400, 800)}
    assert work[400] / work[100] < 6.0, work
    assert work[800] / work[100] < 12.0, work


def test_large_workload_direct_benchmark_measured():
    """A large sheet stays interactive (generous absolute bound; best of five runs)."""
    p = _grid_project(800, extra_vertical=400)
    netlist.compute_nets(p)  # warmup
    best = float("inf")
    for _ in range(5):
        t0 = time.perf_counter()
        nets = netlist.compute_nets(p)
        best = min(best, time.perf_counter() - t0)
    assert len(nets) == len(p.sheets[0].wires)
    assert best < 2.0, f"n=800 ({len(p.sheets[0].wires)} wires) took {best * 1000:.1f} ms"


def test_large_workload_matches_naive_on_moderate_size():
    """At the largest size where naive is still practical, membership matches."""
    p = _grid_project(80, extra_vertical=40)
    _assert_identical(p, label="moderate-large-grid")


# ---------------------------------------------------------------- pin validation and symbol scope
def test_index_keeps_invalid_pin_references_out_of_nets():
    """Wire ends that name a pin the symbol does not have never create terminals, indexed or not."""
    from openschematix.model import Wire
    p = new_project("refs")
    d = p.sheets[0]
    r = editing.place(d, "el.resistor.iec", -300, -200)
    lamp = editing.place(d, "el.lamp.iec", 200, -200)
    good = editing.add_wire(d, [r.terminals()["2"], lamp.terminals()["1"]])
    assert good.start and good.end
    t1 = r.terminals()["1"]
    ghost = Wire(d.new_id(), [t1, (t1[0] - 60, t1[1])], [r.id, "ghost"], None)
    d.add_wire(ghost)
    missing = Wire(d.new_id(), [(-500, 100), (-400, 100)], [9999, "1"], None)
    d.add_wire(missing)
    nets = _assert_identical(p, label="invalid refs")
    terms = {t for n in nets for t in n.terminals}
    assert (d.uid, r.id, "ghost") not in terms
    assert not any(t[1] == 9999 for t in terms)


def test_index_respects_project_scoped_custom_symbols():
    """Two projects with a same-id custom symbol of different pin positions keep their own nets."""
    from openschematix.symbols.custom import blank_symbol, normalise

    def make(reach):
        sid = "user:netlist-index-scope"
        doc = blank_symbol("scope")
        doc.update(id=sid)
        doc["prims"] = [{"k": "line", "pts": [[-reach, 0], [reach, 0]]}]
        doc["pins"] = [{"id": "L", "name": "L", "x": -reach, "y": 0, "dir": "l"},
                       {"id": "R", "name": "R", "x": reach, "y": 0, "dir": "r"}]
        pr = new_project(f"reach {reach}")
        pr.symbols[sid] = normalise(doc)
        pr.activate_symbols()
        d = pr.sheets[0]
        c = editing.place(d, sid, -100, -100)
        r = editing.place(d, "el.resistor.iec", 300, -100)
        w = editing.add_wire(d, [c.terminals()["R"], r.terminals()["1"]])
        assert w.start == [c.id, "R"]
        return pr, d, c, r

    a, da, ca, ra = make(40)
    b, db, cb, rb = make(80)
    # b is the active project now; a must still net with its own definition
    for pr, d, c, r in ((a, da, ca, ra), (b, db, cb, rb)):
        nets = _assert_identical(pr, label=pr.meta["title"])
        assert any((d.uid, c.id, "R") in n.terminals and (d.uid, r.id, "1") in n.terminals for n in nets)
