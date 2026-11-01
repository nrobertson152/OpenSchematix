"""Regression tests for the indexed editing.crossings() (Phase 4, optimization 2).

The index must be invisible: for any document crossings() returns exactly the
list the original all-pairs algorithm returned, element for element and in the
same order (duplicates included). `reference_crossings` is a verbatim copy of
the original (main @ 81a8da2) and is the oracle.
"""
import math
import random

import pytest

from openschematix import editing
from openschematix.editing import _interior, crossings
from openschematix.geometry import same
from openschematix.model import Document, Wire


def reference_crossings(doc) -> list:
    out = []
    ws = list(doc.wires.values())
    segs = [(w, a, b) for w in ws for a, b in zip(w.points, w.points[1:])]
    for i, (w1, a1, b1) in enumerate(segs):
        for w2, a2, b2 in segs[i + 1:]:
            if w1.id == w2.id:
                continue
            h1, h2 = abs(a1[1] - b1[1]) < 0.01, abs(a2[1] - b2[1]) < 0.01
            if h1 == h2:
                continue  # parallel: overlaps are not crossings
            hs, vs = ((a1, b1), (a2, b2)) if h1 else ((a2, b2), (a1, b1))
            x, y = vs[0][0], hs[0][1]
            if not (min(hs[0][0], hs[1][0]) + 0.01 < x < max(hs[0][0], hs[1][0]) - 0.01):
                continue
            if not (min(vs[0][1], vs[1][1]) + 0.01 < y < max(vs[0][1], vs[1][1]) - 0.01):
                continue
            p = (x, y)
            if not (_interior(p, w1.points) and _interior(p, w2.points)):
                continue
            if any(same(p, q) for q in w1.points + w2.points):
                continue
            wv = w1 if not h1 else w2
            wh = w2 if wv is w1 else w1
            out.append((p, wh.id, wv.id))
    return out


def check(doc):
    got, want = crossings(doc), reference_crossings(doc)
    assert repr(got) == repr(want)          # order, duplicates and NaN-safe
    return got


def wire(doc, *pts):
    """Add a wire as given (no add_wire normalisation)."""
    w = Wire(doc.new_id(), [tuple(map(float, p)) for p in pts])
    doc.wires[w.id] = w
    return w


# ---------------------------------------------------------------- 1-3 basic geometry
def test_orthogonal_crossing_and_bridge_owner():
    d = Document()
    h = wire(d, (0, 50), (100, 50))
    v = wire(d, (50, 0), (50, 100))
    assert check(d) == [((50.0, 50.0), h.id, v.id)]
    d2 = Document()                          # vertical first: same tuple, other order of discovery
    v = wire(d2, (50, 0), (50, 100))
    h = wire(d2, (0, 50), (100, 50))
    assert check(d2) == [((50.0, 50.0), h.id, v.id)]


def test_diagonal_is_treated_as_vertical_at_its_first_x():
    d = Document()
    h = wire(d, (0, 50), (100, 50))
    g = wire(d, (30, 0), (90, 100))            # true intersection at x=60, reported at x=30
    assert check(d) == [((30.0, 50.0), h.id, g.id)]
    d = Document()
    wire(d, (0, 50), (100, 50))
    wire(d, (150, 0), (40, 100))               # first x outside the horizontal: no crossing
    assert check(d) == []
    d = Document()
    wire(d, (0, 50), (100, 50))
    wire(d, (30, 0), (200, 40))                # y range misses the horizontal
    assert check(d) == []


def test_t_junctions_and_shared_endpoints_are_not_crossings():
    d = Document()
    wire(d, (0, 0), (100, 0))
    wire(d, (50, 0), (50, 50))                 # T: ends on the bus
    wire(d, (100, 0), (100, 80))               # shared end point
    wire(d, (0, 30), (50, 30), (50, 60))       # corner
    wire(d, (20, -40), (20, 40))               # through the bus and the corner wire: two crossings
    assert len(check(d)) == 2


# ---------------------------------------------------------------- 4-6 overlaps, duplicates, degenerate
def test_collinear_overlapping_and_parallel_segments():
    d = Document()
    wire(d, (0, 0), (100, 0))
    wire(d, (50, 0), (150, 0))                 # collinear overlap
    wire(d, (40, -50), (40, 50))
    wire(d, (40, -20), (40, 80))               # collinear vertical overlap
    wire(d, (60, 0.005), (60, -0.004))         # "horizontal" (|dy| < 0.01) and very short
    check(d)


def test_duplicate_and_reversed_wires_keep_duplicate_entries():
    d = Document()
    h = wire(d, (0, 50), (100, 50))
    wire(d, (100, 50), (0, 50))                # reversed duplicate
    wire(d, (0, 50), (100, 50))                # exact duplicate
    wire(d, (50, 0), (50, 100))
    wire(d, (50, 100), (50, 0))                # reversed vertical
    got = check(d)
    assert len(got) == 6 and got[0][1] == h.id


def test_zero_length_and_degenerate_segments():
    d = Document()
    wire(d, (0, 50), (100, 50))
    wire(d, (50, 0), (50, 0), (50, 100))       # repeated vertex
    wire(d, (70, 50), (70, 50))                # zero length on the horizontal
    wire(d, (30, 10), (30, 90), (30, 10))      # folds back on itself
    wire(d, (5, 5))                            # single point: no segments
    check(d)


# ---------------------------------------------------------------- 7-8 tolerances, negatives, cells
@pytest.mark.parametrize("dx", [0.0, 0.009, 0.0101, 0.011, -0.0101, 0.02])
def test_range_tolerance_boundaries(dx):
    d = Document()
    wire(d, (0, 50), (100, 50))
    wire(d, (0.0 + dx, 0), (0.0 + dx, 100))    # near the left end of the horizontal
    wire(d, (100 - dx, 0), (100 - dx, 100))    # near the right end
    wire(d, (50, 50 - dx), (50, 120))          # near the top of the vertical
    check(d)


@pytest.mark.parametrize("dy", [0.0, 0.009, 0.0099, 0.01, 0.0101, -0.0099])
def test_horizontal_classification_boundary(dy):
    d = Document()
    wire(d, (0, 50), (100, 50 + dy))
    wire(d, (50, 0), (50, 100))
    check(d)


@pytest.mark.parametrize("c", [-100.0, -50.0, -0.001, 0.0, 49.999, 50.0, 50.001, 1e6, -1e6])
def test_negative_coordinates_and_cell_boundaries(c):
    d = Document()
    wire(d, (c - 75, c), (c + 75, c))
    wire(d, (c, c - 75), (c, c + 75))
    wire(d, (c - 0.5, c - 50), (c - 0.5, c + 50))
    wire(d, (c + 0.5, c + 50), (c + 0.5, c - 50))
    assert len(check(d)) == 3


# ---------------------------------------------------------------- 9, 12 long / pathological / malformed
def test_very_long_segments_fall_back_to_all_pairs():
    d = Document()
    wire(d, (-1e6, 0), (1e6, 0))               # far over the cell cap
    wire(d, (0, -1e9), (0, 1e9))
    for x in range(-900000, 900000, 150000):
        wire(d, (x, -10), (x, 10))
        wire(d, (x - 5, 5), (x + 5, 5))
    got = check(d)
    assert ((0.0, 0.0), 1, 2) in got


def test_non_finite_coordinates_match_original():
    d = Document()
    wire(d, (0, 50), (math.inf, 50))           # infinite horizontal still crosses
    wire(d, (50, 0), (50, 100))
    wire(d, (70, -math.inf), (70, math.inf))
    wire(d, (math.nan, 0), (90, 100))
    wire(d, (0, math.nan), (100, math.nan))
    wire(d, (-math.inf, 20), (math.inf, 20))
    got = check(d)
    assert got                                  # the original reports crossings here too


def _peak(fn):
    import tracemalloc
    tracemalloc.start()
    fn()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return peak


def test_memory_registration_is_bounded():
    """Long segments that never meet: the index must stay within its registration budget,
    and the rest fall back to all-pairs testing (still no crossings)."""
    d = Document()
    rnd = random.Random(5)
    n = 1200
    for i in range(n):                         # just under the per-segment cell cap
        x = rnd.uniform(-1e4, 1e4)
        if i % 2:
            wire(d, (x, -5 - i), (x + 12000, -5 - i))          # horizontals, all at y < 0
        else:
            wire(d, (x, 1e5), (x, 1e5 + 12000))                # verticals, far below them
    assert check(d) == []
    budget = editing._XBUDGET_PER_SEGMENT * n + editing._XBUDGET_MIN
    extra = _peak(lambda: crossings(d)) - _peak(lambda: list(d.wires.values()))
    # every registration costs a list slot plus amortised dict/list/tuple overhead
    assert extra < budget * 250, (extra, budget)


def test_huge_segments_are_never_registered():
    d = Document()
    for i in range(300):
        wire(d, (-1e9, i), (1e9, i))
        wire(d, (1e9 + i, -1e9), (1e9 + i, 1e9))
    assert _peak(lambda: crossings(d)) < 2_000_000


# ---------------------------------------------------------------- 10-11 randomized, ordering
def _random_doc(rnd):
    d = Document()
    span = rnd.choice([80, 300, 3000])
    step = rnd.choice([10, 5, 1])

    def c():
        v = float(rnd.randrange(-span // 3, span, step))
        if rnd.random() < 0.1:
            v += rnd.choice([0.004, -0.009, 0.0101, 0.015, -0.02, 0.0099])
        return v
    for _ in range(rnd.randrange(1, 45)):
        k = rnd.random()
        n = rnd.choice([2, 2, 3, 4, 5])
        if k < 0.6:                           # orthogonal polyline
            pts = [(c(), c())]
            for _ in range(n - 1):
                x, y = pts[-1]
                pts.append((c(), y + rnd.choice([0, 0, 0.005, -0.009, 0.012])) if rnd.random() < 0.5 else (x, c()))
        elif k < 0.8:                         # diagonal / general
            pts = [(c(), c()) for _ in range(n)]
        elif k < 0.9 and d.wires:             # duplicate or reversed
            pts = list(rnd.choice(list(d.wires.values())).points)
            if rnd.random() < 0.5:
                pts.reverse()
        else:                                 # degenerate
            p = (c(), c())
            pts = rnd.choice([[p, p], [p, (c(), p[1]), p], [p, p, (p[0], c())]])
        wire(d, *pts)
    r = rnd.random()
    if r < 0.04:
        wire(d, (0.0, 20.0), (math.inf, 20.0))
    elif r < 0.08:
        wire(d, (math.nan, 0.0), (10.0, 90.0))
    elif r < 0.12:
        wire(d, (-1e7, 15.0), (1e7, 15.0))
    return d


@pytest.mark.parametrize("seed", range(6))
def test_differential_random_documents(seed):
    rnd = random.Random(2000 + seed)
    for _ in range(250):
        check(_random_doc(rnd))


def test_differential_large_dense_grid():
    d = Document()
    for i in range(60):                       # 60 x 60 orthogonal mesh: 3,600 crossings
        wire(d, (0, 10 + i * 20), (1210, 10 + i * 20))
        wire(d, (5 + i * 20, 0), (5 + i * 20, 1210))
    assert len(check(d)) == 3600


def test_example_projects_and_benchmark_drawing_unchanged():
    import glob
    import os
    import sys
    from openschematix import projectio
    root = os.path.join(os.path.dirname(__file__), "..")
    for path in sorted(glob.glob(os.path.join(root, "examples", "*"))):
        for doc in projectio.open_any(path).project.sheets:
            check(doc)
    sys.path.insert(0, os.path.join(root, "tools"))
    try:
        from bench_phase4 import build_project
    finally:
        sys.path.pop(0)
    _p, d = build_project(3, 2, with_fills=False)
    assert len(check(d)) == 48


def test_output_is_deterministic():
    rnd = random.Random(77)
    d = _random_doc(rnd)
    assert repr(crossings(d)) == repr(crossings(d)) == repr(reference_crossings(d))
