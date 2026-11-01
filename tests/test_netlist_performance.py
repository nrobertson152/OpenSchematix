"""Netlist performance and spatial-index equivalence.

``compute_nets`` must agree with a naive O(W^2) reference on small and
adversarial sheets (membership, terminal sets, deterministic net indices),
and must scale near-linearly so large engineering drawings stay interactive.
"""
from __future__ import annotations

import time

from openschematix import editing, netlist
from openschematix.connectivity import _CELL, _PAD
from openschematix.geometry import point_on_segment
from openschematix.project import new_project
from openschematix.symbols.general import OFFPAGE_IDS


def _key(p):
    return (round(p[0], 2), round(p[1], 2))


def _naive_sheet_nodes(doc, uf: netlist._UF):
    """Reference implementation: full wire scan (pre-index algorithm)."""
    uid = doc.uid
    wires = list(doc.wires.values())
    for w in wires:
        uf.find(("w", uid, w.id))
    term_at = {}
    for c in doc.components.values():
        for name, p in c.terminals().items():
            node = ("t", uid, c.id, name)
            uf.find(node)
            term_at.setdefault(_key(p), []).append(node)
    for nodes in term_at.values():
        for n in nodes[1:]:
            uf.union(nodes[0], n)
    for w in wires:
        for ref in (w.start, w.end):
            if ref and ref[0] in doc.components:
                uf.union(("w", uid, w.id), ("t", uid, ref[0], ref[1]))
        for idx in (0, -1):
            p = w.points[idx]
            for n in term_at.get(_key(p), []):
                uf.union(("w", uid, w.id), n)
            for o in wires:
                if o.id == w.id:
                    continue
                if any(point_on_segment(p, a, b) for a, b in zip(o.points, o.points[1:])):
                    uf.union(("w", uid, w.id), ("w", uid, o.id))


def _compute_nets_naive(project):
    """Full ``compute_nets`` path with the pre-index sheet-node scan.

    Reuses the production grouping, sorting and index assignment so that
    net membership *and* deterministic identifiers can be compared.
    """
    original = netlist._sheet_nodes
    try:
        netlist._sheet_nodes = _naive_sheet_nodes
        return netlist.compute_nets(project)
    finally:
        netlist._sheet_nodes = original


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
def test_compute_nets_scales_near_linearly_on_large_sheets():
    """Regression: a quadratic scan would make n=400 >> 4x slower than n=100."""
    times = {}
    counts = {}
    for n in (100, 400):
        p = _grid_project(n, extra_vertical=n // 2)
        # warmup
        netlist.compute_nets(p)
        t0 = time.perf_counter()
        for _ in range(3):
            nets = netlist.compute_nets(p)
        times[n] = (time.perf_counter() - t0) / 3
        counts[n] = (len(p.sheets[0].wires), len(nets))
    ratio = times[400] / max(times[100], 1e-6)
    assert ratio < 10.0, (
        f"compute_nets scaling looks quadratic: ratio={ratio:.1f} "
        f"(t100={times[100]*1000:.1f}ms t400={times[400]*1000:.1f}ms "
        f"wires={counts})"
    )


def test_large_workload_direct_benchmark_measured():
    """Directly measured large-workload timings (recorded for PR evidence).

    Not a hard ceiling on absolute ms (machines vary); asserts near-linear
    growth and that the largest case finishes well under a second.
    """
    results = []
    for n in (100, 200, 400, 800):
        p = _grid_project(n, extra_vertical=n // 2)
        nw = len(p.sheets[0].wires)
        netlist.compute_nets(p)  # warmup
        t0 = time.perf_counter()
        for _ in range(3):
            nets = netlist.compute_nets(p)
        elapsed = (time.perf_counter() - t0) / 3
        results.append((n, nw, len(nets), elapsed))
    # Publish numbers into assertion message for CI logs
    summary = ", ".join(
        f"n={n} wires={nw} nets={nn} t={t*1000:.2f}ms" for n, nw, nn, t in results
    )
    # Largest case must stay interactive
    assert results[-1][3] < 1.0, f"n=800 took {results[-1][3]*1000:.1f}ms; {summary}"
    # 8× components should be well under ~20× time (quadratic would be ~64×)
    ratio = results[-1][3] / max(results[0][3], 1e-6)
    assert ratio < 20.0, f"scaling ratio n800/n100={ratio:.1f}; {summary}"
    # Also record mid-size growth
    ratio_mid = results[2][3] / max(results[0][3], 1e-6)
    assert ratio_mid < 12.0, f"scaling ratio n400/n100={ratio_mid:.1f}; {summary}"


def test_large_workload_matches_naive_on_moderate_size():
    """At the largest size where naive is still practical, membership matches."""
    p = _grid_project(80, extra_vertical=40)
    _assert_identical(p, label="moderate-large-grid")
