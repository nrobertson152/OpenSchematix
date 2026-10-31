"""Boundary fill (FILL / HATCH): geometry engine, region maths, the hatch
shape (transforms, hit testing, persistence) and SVG / PDF / DXF output."""
import io
import json
import math
import random
import re
import time
import zipfile

import pytest

from openschematix import editing, export, projectio, regions as rg
from openschematix.boundary_fill import MAX_GAP, SNAP_TOL, find_region, shape_edges
from openschematix.model import Component, Document, Shape
from openschematix.project import new_project
from openschematix.shapes import (mirror_shape, move_shape, rotate_shape, scale_shape, shape_bbox, shape_distance,
                                  shape_prims, trim)


# ---------------------------------------------------------------- helpers
def L(i, a, b):
    return Shape(i, "line", pts=[a, b])


def R(i, x0, y0, x1, y1):
    return Shape(i, "rect", pts=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def C(i, c, r):
    return Shape(i, "circle", c=c, r=r)


def fill_area(shapes, p, **kw):
    res = find_region(shapes, p, **kw)
    assert res.ok, res.message
    return res.area


def square_lines(x0=0, y0=0, w=20, h=10):
    return [L(1, (x0, y0), (x0 + w, y0)), L(2, (x0 + w, y0), (x0 + w, y0 + h)),
            L(3, (x0 + w, y0 + h), (x0, y0 + h)), L(4, (x0, y0 + h), (x0, y0))]


LENS = 2 * (100 * math.acos(0.5) - 5 * math.sqrt(75))     # two r=10 circles 10 apart


# ================================================================ boundaries from different objects
def test_separate_lines_form_a_region():
    res = find_region(square_lines(), (5, 5))
    assert res.ok and res.area == pytest.approx(200) and res.holes == 0
    assert len(res.rings) == 1 and len(res.rings[0]) == 4


def test_point_outside_everything_is_rejected():
    res = find_region(square_lines(), (30, 5))
    assert not res.ok and res.rings is None and "No closed boundary" in res.message


@pytest.mark.parametrize("shape, pick, area", [
    (Shape(1, "polyline", pts=[(0, 0), (30, 0), (30, 20), (0, 20), (0, 0)]), (10, 10), 600),
    (Shape(1, "polygon", pts=[(0, 0), (30, 0), (15, 20)]), (15, 5), 300),
    (R(1, -10, -10, 10, 10), (0, 0), 400),
    (C(1, (5, 5), 7), (5, 5), math.pi * 49),
])
def test_single_closed_objects(shape, pick, area):
    assert fill_area([shape], pick) == pytest.approx(area, rel=1e-12)


def test_arc_and_line_d_shape_is_exact():
    shapes = [Shape(1, "arc", c=(0, 0), r=10, start=-90, extent=180), L(2, (0, -10), (0, 10))]
    res = find_region(shapes, (5, 0))
    assert res.area == pytest.approx(50 * math.pi, rel=1e-12)
    # the arc is kept as an arc (bulge), not flattened
    assert sorted(abs(v[2]) for v in res.rings[0]) == pytest.approx([0.0, 1.0])


def test_negative_extent_arc_and_polyline_boundary():
    shapes = [Shape(1, "arc", c=(0, 0), r=10, start=90, extent=-180),      # same arc, other way round
              Shape(2, "polyline", pts=[(0, 10), (0, 0), (0, -10)])]
    assert fill_area(shapes, (5, 0)) == pytest.approx(50 * math.pi)


def test_full_circle_output_is_two_half_arcs():
    res = find_region([C(1, (0, 0), 4)], (0, 0))
    assert len(res.rings) == 1 and len(res.rings[0]) == 2
    assert all(abs(v[2]) == pytest.approx(1.0) for v in res.rings[0])


# ================================================================ intersections and partial segments
def test_overshooting_lines_hash_pattern():
    shapes = [L(1, (-5, 0), (25, 0)), L(2, (-5, 10), (25, 10)), L(3, (0, -5), (0, 15)), L(4, (20, -5), (20, 15))]
    res = find_region(shapes, (5, 5))
    assert res.area == pytest.approx(200) and len(res.rings[0]) == 4
    assert res.warnings                        # the overshoots were ignored, and said so
    assert not find_region(shapes, (22, 5)).ok


def test_triangle_from_three_long_crossing_lines():
    shapes = [L(1, (-10, 0), (110, 0)), L(2, (-5, -10), (55, 110)), L(3, (105, -10), (45, 110))]
    # lines y=0, through (0,0)-(50,100), through (100,0)-(50,100)
    assert fill_area(shapes, (50, 30)) == pytest.approx(5000, rel=1e-9)


def test_two_overlapping_circles_give_lens_and_crescents():
    shapes = [C(1, (0, 0), 10), C(2, (10, 0), 10)]
    assert fill_area(shapes, (5, 0)) == pytest.approx(LENS, rel=1e-12)
    assert fill_area(shapes, (-5, 0)) == pytest.approx(100 * math.pi - LENS, rel=1e-12)


def test_line_through_circle_splits_it():
    shapes = [C(1, (0, 0), 10), L(2, (-20, 0), (20, 0))]
    assert fill_area(shapes, (0, 3)) == pytest.approx(50 * math.pi)
    assert fill_area(shapes, (0, -3)) == pytest.approx(50 * math.pi)


def test_tangent_circles_inside_rectangle():
    shapes = [R(1, 0, 0, 40, 20), C(2, (10, 10), 10), C(3, (30, 10), 10)]
    # below the two circles, between the tangent points
    assert fill_area(shapes, (20, 2)) == pytest.approx(200 - 50 * math.pi, rel=1e-9)
    assert fill_area(shapes, (10, 10)) == pytest.approx(100 * math.pi, rel=1e-12)


def test_concave_polygon_and_notch():
    poly = Shape(1, "polygon", pts=[(0, 0), (20, 0), (20, 5), (5, 5), (5, 20), (0, 20)])
    assert fill_area([poly], (2, 15)) == pytest.approx(175)
    assert not find_region([poly], (15, 15)).ok           # inside the notch = outside the polygon


def test_star_polygon_self_intersections_create_faces():
    pts = [(math.cos(math.radians(90 + 144 * k)) * 50, math.sin(math.radians(90 + 144 * k)) * 50) for k in range(5)]
    star = Shape(1, "polygon", pts=pts)
    centre = find_region([star], (0, 0))
    tips = [find_region([star], (p[0] * 0.9, p[1] * 0.9)) for p in pts]
    assert centre.ok and len(centre.rings[0]) == 5          # the inner pentagon
    assert all(t.ok and len(t.rings[0]) == 3 for t in tips)  # five triangular points
    assert all(t.area == pytest.approx(tips[0].area, rel=1e-9) for t in tips)


# ================================================================ shared edges, duplicates, overlaps
def test_shared_edge_between_rectangles():
    shapes = [R(1, 0, 0, 10, 10), R(2, 10, 0, 20, 10)]
    a, b = find_region(shapes, (5, 5)), find_region(shapes, (15, 5))
    assert a.area == pytest.approx(100) and b.area == pytest.approx(100)
    assert {v[:2] for v in a.rings[0]} == {(0, 0), (10, 0), (10, 10), (0, 10)}


def test_duplicate_and_partially_overlapping_edges():
    assert fill_area([R(1, 0, 0, 10, 10), R(2, 0, 0, 10, 10)], (5, 5)) == pytest.approx(100)
    assert fill_area([R(1, 0, 0, 10, 10), L(2, (-5, 0), (15, 0)), L(3, (2, 10), (8, 10))], (5, 5)) == \
        pytest.approx(100)


def test_cocircular_overlapping_arcs():
    shapes = [Shape(1, "arc", c=(0, 0), r=10, start=0, extent=200), Shape(2, "arc", c=(0, 0), r=10, start=150,
                                                                          extent=210)]
    assert fill_area(shapes, (0, 0)) == pytest.approx(100 * math.pi, rel=1e-12)


# ================================================================ nested boundaries and holes
def test_rectangle_with_circular_hole():
    shapes = [R(1, 0, 0, 20, 20), C(2, (10, 10), 3)]
    res = find_region(shapes, (2, 2))
    assert res.holes == 1 and res.area == pytest.approx(400 - 9 * math.pi, rel=1e-12)
    assert rg.ring_area(res.rings[0]) > 0 and rg.ring_area(res.rings[1]) < 0
    assert not rg.point_in_rings(res.rings, (10, 10)) and rg.point_in_rings(res.rings, (2, 2))
    assert fill_area(shapes, (10, 10)) == pytest.approx(9 * math.pi)


def test_three_levels_of_nesting():
    shapes = [R(1, 0, 0, 100, 100), R(2, 20, 20, 80, 80), C(3, (50, 50), 10)]
    outer = find_region(shapes, (5, 5))
    middle = find_region(shapes, (25, 25))
    inner = find_region(shapes, (50, 50))
    assert outer.area == pytest.approx(6400) and outer.holes == 1     # only the direct island is a hole
    assert middle.area == pytest.approx(3600 - 100 * math.pi) and middle.holes == 1
    assert inner.area == pytest.approx(100 * math.pi) and inner.holes == 0
    assert not rg.point_in_rings(outer.rings, (50, 50))               # island's island is not filled


def test_annulus_between_concentric_circles():
    assert fill_area([C(1, (0, 0), 10), C(2, (0, 0), 6)], (8, 0)) == pytest.approx(64 * math.pi, rel=1e-12)


def test_island_joined_to_boundary_by_a_line():
    shapes = [R(1, 0, 0, 100, 100), R(2, 40, 40, 60, 60), L(3, (0, 50), (40, 50))]
    res = find_region(shapes, (10, 10))
    assert res.area == pytest.approx(9600) and res.holes == 1
    assert sorted(round(rg.ring_area(r)) for r in res.rings) == [-400, 10000]


def test_two_islands_joined_together():
    shapes = [R(1, 0, 0, 100, 100), R(2, 10, 40, 30, 60), R(3, 70, 40, 90, 60), L(4, (30, 50), (70, 50))]
    res = find_region(shapes, (50, 10))
    assert res.area == pytest.approx(9200) and res.holes == 2


def test_several_islands_and_text_ignored():
    shapes = [R(1, 0, 0, 100, 50)] + [C(10 + k, (15 + 18 * k, 25), 5) for k in range(5)] + \
             [Shape(30, "text", pts=[(50, 5)], s="NOTE")]
    res = find_region(shapes, (50, 45))
    assert res.holes == 5 and res.area == pytest.approx(5000 - 5 * 25 * math.pi, rel=1e-12)


# ================================================================ open, ambiguous and malformed input
def test_open_boundary_rejected():
    assert not find_region(square_lines()[:3], (5, 5)).ok


def test_branch_does_not_break_a_closed_boundary():
    shapes = square_lines() + [L(5, (0, 0), (-5, 0)), L(6, (5, 5), (8, 8))]       # spur outside + stray inside
    res = find_region(shapes, (2, 7))
    assert res.area == pytest.approx(200)


def test_point_on_boundary_rejected():
    for p in [(10, 0), (20, 5), (0, 0), (10, 10.004)]:
        res = find_region(square_lines(), p)
        assert not res.ok and "on a boundary" in res.message, p


def test_no_geometry():
    assert not find_region([], (0, 0)).ok
    assert not find_region([Shape(1, "text", pts=[(0, 0)], s="x")], (0, 0)).ok


def test_near_coincident_end_points_connect():
    shapes = [L(1, (0, 0), (20, 0.004)), L(2, (20.003, 0), (20, 10)), L(3, (20, 10), (0, 10)),
              L(4, (0, 10.002), (0, 0.001))]
    assert fill_area(shapes, (5, 5)) == pytest.approx(200, abs=0.1)


def test_t_junction_near_miss_connects():
    shapes = [L(1, (0, 0), (20, 0)), L(2, (20, 0), (20, 10)), L(3, (20, 10), (0, 10)), L(4, (0, 10), (0, 0)),
              L(5, (10, 0.006), (10, 9.995))]        # splits the square; ends 0.006 / 0.005 from the edges
    assert fill_area(shapes, (5, 5)) == pytest.approx(100, abs=0.1)


def test_gap_tolerance():
    shapes = [L(1, (0, 0), (20, 0)), L(2, (20, 0), (20, 10)), L(3, (20, 10), (0, 10)), L(4, (0, 10), (0, 1))]
    assert not find_region(shapes, (5, 5)).ok                          # 1 unit (0.25 mm) gap: open
    res = find_region(shapes, (5, 5), gap=2)
    assert res.ok and res.bridged == 1 and res.area == pytest.approx(200)
    assert not find_region(shapes, (5, 5), gap=0.5).ok                 # gap larger than the tolerance
    # end point near the middle of an edge (T gap)
    t = [R(1, 0, 0, 20, 10), L(2, (10, 10), (10, 0.8))]
    assert fill_area(t, (5, 5), gap=1) == pytest.approx(100)
    assert find_region(t, (5, 5), gap=1e9).ok                          # clamped to MAX_GAP, still fine
    assert MAX_GAP > 0


def test_malformed_geometry_is_ignored():
    shapes = [R(1, 0, 0, 10, 10), C(2, (5, 5), 0), C(3, (5, 5), -3), L(4, (1, 1), (1, 1)),
              C(5, (float("nan"), 0), 3), Shape(6, "polyline", pts=[(2, 2)]),
              Shape(7, "line", pts=[(0, 0), (float("inf"), 5)]), Shape(8, "arc", c=(5, 5), r=2, start=0, extent=0),
              Shape(9, "hatch", rings=[[(0, 0, 0), (100, 0, 0), (100, 100, 0)]])]
    assert fill_area(shapes, (2, 8)) == pytest.approx(100)
    assert shape_edges(shapes[1]) == [] and shape_edges(shapes[4]) == [] and shape_edges(shapes[8]) == []
    assert not find_region(shapes, (float("nan"), 0)).ok


def test_degenerate_slivers_rejected():
    # zero-area polygon (all points on a line)
    assert not find_region([Shape(1, "polygon", pts=[(0, 0), (10, 0), (20, 0)])], (5, 0.001)).ok


def test_large_coordinates_are_stable():
    off = 1.0e5
    shapes = [R(1, off, off, off + 30, off + 20), C(2, (off + 15, off + 10), 4)]
    res = find_region(shapes, (off + 2, off + 2))
    assert res.area == pytest.approx(600 - 16 * math.pi, rel=1e-9) and res.holes == 1


def test_random_soup_regions_are_consistent():
    random.seed(7)
    shapes = [L(i, (random.uniform(0, 200), random.uniform(0, 200)), (random.uniform(0, 200), random.uniform(0, 200)))
              for i in range(40)] + [C(100 + i, (random.uniform(0, 200), random.uniform(0, 200)), random.uniform(5, 30))
                                     for i in range(15)]
    for _ in range(60):
        p = (random.uniform(0, 200), random.uniform(0, 200))
        res = find_region(shapes, p)
        if res.ok:
            assert res.area > 0 and rg.point_in_rings(res.rings, p)
            assert all(abs(v[2]) <= 1 + 1e-9 for r in res.rings for v in r)


@pytest.mark.parametrize("seed", range(8))
def test_any_point_of_a_region_finds_the_same_region(seed):
    """Consistency: picking anywhere inside a found region yields that region,
    and its exact area matches a finely flattened polygon."""
    random.seed(seed)
    sh = [L(i, (random.uniform(0, 200), random.uniform(0, 200)), (random.uniform(0, 200), random.uniform(0, 200)))
          for i in range(random.randint(3, 20))]
    sh += [C(100 + i, (random.uniform(0, 200), random.uniform(0, 200)), random.uniform(3, 40))
           for i in range(random.randint(0, 8))]
    sh += [Shape(200 + i, "arc", c=(random.uniform(0, 200), random.uniform(0, 200)), r=random.uniform(5, 60),
                 start=random.uniform(0, 360), extent=random.uniform(10, 350)) for i in range(random.randint(0, 6))]
    found = 0
    for _ in range(20):
        p = (random.uniform(0, 200), random.uniform(0, 200))
        res = find_region(sh, p)
        if not res.ok:
            continue
        found += 1
        assert rg.point_in_rings(res.rings, p)
        flat = sum(rg.ring_area([(x, y, 0) for x, y in rg.flatten_ring(r, 0.0005)]) for r in res.rings)
        assert flat == pytest.approx(res.area, rel=1e-3, abs=1e-3)
        b = rg.rings_bbox(res.rings)
        tries = 0
        for _ in range(200):
            q = (random.uniform(b[0], b[2]), random.uniform(b[1], b[3]))
            if rg.point_in_rings(res.rings, q) and rg.boundary_distance(res.rings, q) > 0.05:
                assert find_region(sh, q).area == pytest.approx(res.area, rel=1e-6)
                tries += 1
                if tries == 3:
                    break
    assert found


def test_point_in_rings_matches_flattened_polygon():
    random.seed(3)
    for _ in range(30):
        n = random.randint(3, 7)
        angs = sorted(random.uniform(0, 2 * math.pi) for _ in range(n))
        ring = [(50 * math.cos(a), 50 * math.sin(a), random.uniform(-0.6, 0.6)) for a in angs]
        flat = [(x, y, 0.0) for x, y in rg.flatten_ring(ring, 1e-4)]
        for _ in range(40):
            p = (random.uniform(-80, 80), random.uniform(-80, 80))
            if rg.boundary_distance([ring], p) > 0.01:
                assert rg.point_in_rings([ring], p) == rg.point_in_rings([flat], p)


def test_performance_on_a_dense_grid():
    shapes = [L(i, (0, i * 10), (400, i * 10)) for i in range(41)] + \
             [L(100 + i, (i * 10, 0), (i * 10, 400)) for i in range(41)]
    t = time.perf_counter()
    assert fill_area(shapes, (155, 155)) == pytest.approx(100)
    assert time.perf_counter() - t < 5


def test_snap_tolerance_is_sub_visible():
    assert SNAP_TOL * 0.25 < 0.01     # below 0.01 mm


# ================================================================ region maths
def test_region_area_point_test_and_bbox_with_arcs():
    ring = [(0, -10, 0.0), (0, 10, 1.0)]       # D shape: line up, half circle back (y down frame)
    assert rg.ring_area(ring) == pytest.approx(-50 * math.pi) or rg.ring_area(ring) == pytest.approx(50 * math.pi)
    rr = rg.reverse_ring(ring)
    assert rg.ring_area(rr) == pytest.approx(-rg.ring_area(ring))
    inside = (-5, 0) if rg.point_in_rings([ring], (-5, 0)) else (5, 0)
    assert rg.point_in_rings([rr], inside)
    b = rg.rings_bbox([ring])
    assert b[1] == pytest.approx(-10) and b[3] == pytest.approx(10) and abs(b[0] - b[2]) == pytest.approx(10)


def test_split_arcs_and_flatten_are_exact_on_the_circle():
    ring = [(10, 0, 1.0), (-10, 0, 1.0)]       # full circle r=10
    split = rg.split_arcs(ring, math.pi / 4)
    assert len(split) == 8 and rg.ring_area(split) == pytest.approx(rg.ring_area(ring))
    for x, y in rg.flatten_ring(ring, 0.01):
        assert math.hypot(x, y) == pytest.approx(10)
    poly = rg.flatten_ring(ring, 0.01)
    assert abs(rg.ring_area([(x, y, 0) for x, y in poly])) == pytest.approx(100 * math.pi, rel=2e-3)


def test_clean_rings_validation():
    assert rg.clean_rings([[[0, 0], [1, 0, 0.5], [1, 1]]]) == [[(0.0, 0.0, 0.0), (1.0, 0.0, 0.5), (1.0, 1.0, 0.0)]]
    for bad in (None, [], [[]], [[[0, 0]]], [[[0, 0], [1, 1]]], [[[0, 0], [1, "x"], [2, 2]]],
                [[[0, 0], [1, 1, 5.0], [2, 2]]], [[[0, 0], [float("nan"), 1], [2, 2]]], [[[0, 0], [1], [2, 2]]],
                [[[0, 0], [True, 1], [2, 2]]], "rings"):
        with pytest.raises((ValueError, TypeError)):
            rg.clean_rings(bad)


@pytest.mark.parametrize("shapes, pick", [
    ([R(1, 0, 0, 20, 20), C(2, (10, 10), 3)], (2, 2)),
    ([C(1, (0, 0), 10), C(2, (10, 0), 10)], (5, 0)),
    ([R(1, 0, 0, 100, 100), R(2, 40, 40, 60, 60), L(3, (0, 50), (40, 50))], (10, 10)),
    ([Shape(1, "polygon", pts=[(0, 0), (20, 0), (20, 5), (5, 5), (5, 20), (0, 20)])], (2, 2)),
])
def test_trapezoid_decomposition_matches_region(shapes, pick):
    res = find_region(shapes, pick)
    polys = [rg.flatten_ring(r, 0.001) for r in res.rings]
    quads = rg.trapezoids(polys)
    assert rg.quads_area(quads) == pytest.approx(res.area, rel=5e-4)
    for q in quads:                               # each trapezoid lies inside the region
        cx = sum(p[0] for p in q) / 4
        cy = sum(p[1] for p in q) / 4
        assert rg.point_in_rings(res.rings, (cx, cy))


# ================================================================ the hatch shape
def make_hatch(sid=50):
    res = find_region([R(1, 0, 0, 40, 20), C(2, (20, 10), 5)], (2, 2))
    return Shape(sid, "hatch", rings=res.rings)


def test_hatch_round_trip_and_validation():
    h = make_hatch()
    d = h.to_dict()
    assert d["kind"] == "hatch" and "fill" not in d and len(d["rings"]) == 2
    back = Shape.from_dict(json.loads(json.dumps(d)))
    assert back.kind == "hatch" and back.to_dict() == d
    assert rg.region_area(back.rings) == pytest.approx(800 - 25 * math.pi, rel=1e-9)
    for bad in ({"id": 1, "kind": "hatch"}, {"id": 1, "kind": "hatch", "rings": [[[0, 0], [1, 0]]]},
                {"id": 1, "kind": "hatch", "rings": [[[0, 0], [1, 0], [1, "a"]]]}):
        with pytest.raises(ValueError):
            Shape.from_dict(bad)


def test_hatch_transforms_preserve_shape():
    h = make_hatch()
    area = rg.region_area(h.rings)
    move_shape(h, 100, 50)
    assert rg.point_in_rings(h.rings, (102, 52)) and not rg.point_in_rings(h.rings, (120, 60))
    rotate_shape(h, (100, 50), 90)
    assert rg.region_area(h.rings) == pytest.approx(area, rel=1e-9)
    scale_shape(h, (100, 50), 2)
    assert rg.region_area(h.rings) == pytest.approx(4 * area, rel=1e-9)
    h2 = make_hatch()
    mirror_shape(h2, (0, 0), (0, 10))          # about the y axis
    assert abs(rg.region_area(h2.rings)) == pytest.approx(area, rel=1e-9)
    assert rg.point_in_rings(h2.rings, (-2, 2)) and not rg.point_in_rings(h2.rings, (-20, 10))
    assert rg.point_in_rings(h2.rings, (-20, 15.5))           # just outside the hole circle
    # an arc ring mirrored stays on its circle
    d = Shape(1, "hatch", rings=find_region([C(1, (10, 0), 5)], (10, 0)).rings)
    mirror_shape(d, (0, 0), (10, 0))
    assert rg.rings_bbox(d.rings) == pytest.approx((5, -5, 15, 5))


def test_hatch_bbox_hit_test_snap_and_prims():
    h = make_hatch()
    assert shape_bbox(h) == pytest.approx((0, 0, 40, 20))
    assert shape_distance(h, (2, 2)) == 0
    assert shape_distance(h, (20, 10)) == pytest.approx(5)     # centre of the hole
    assert shape_distance(h, (45, 10)) == pytest.approx(5)
    prims = shape_prims(h, item=h.id)
    assert prims[0]["k"] == "region" and prims[0]["fill"] and len(prims[0]["rings"]) == 2
    assert trim(h, (2, 2), [], lambda: 99) is None


def test_hit_test_puts_fills_underneath():
    doc = Document()
    h = make_hatch(doc.new_id())
    doc.add_shape(h)
    line = Shape(doc.new_id(), "line", pts=[(0, 5), (40, 5)])
    doc.add_shape(line)
    assert editing.hit_test(doc, (10, 5.2), 1) == line.id            # a line over the fill wins
    assert editing.hit_test(doc, (10, 15), 1) == h.id
    assert editing.hit_test(doc, (20, 10), 1) is None                # inside the hole
    small = Shape(doc.new_id(), "hatch", rings=find_region([R(1, 30, 12, 38, 18)], (32, 14)).rings)
    doc.add_shape(small)
    assert editing.hit_test(doc, (32, 14), 1) == small.id            # smaller of two overlapping fills
    c = Component(doc.new_id(), "el.resistor.iec", 10, 10)
    doc.add_component(c)
    assert editing.hit_test(doc, (10, 10), 1) == c.id                # a symbol over the fill wins


def test_copy_paste_and_independence():
    doc = Document()
    rect = R(doc.new_id(), 0, 0, 40, 20)
    doc.add_shape(rect)
    h = Shape(doc.new_id(), "hatch", rings=find_region([rect], (5, 5)).rings)
    doc.add_shape(h)
    clip = editing.copy_items(doc, [h.id])
    new = editing.paste(doc, clip, 100, 0)
    copies = [doc.shapes[i] for i in new if i in doc.shapes]
    assert len(copies) == 1 and copies[0].kind == "hatch" and copies[0].id != h.id
    assert rg.rings_bbox(copies[0].rings) == pytest.approx((100, 0, 140, 20))
    # deleting or moving the boundary does not change the fill
    before = h.to_dict()
    editing.delete_items(doc, [rect.id])
    assert doc.shapes[h.id].to_dict() == before


# ================================================================ persistence
def project_with_fill():
    p = new_project()
    doc = p.sheets[0]
    rect = R(doc.new_id(), 100, 100, 300, 200)
    hole = C(doc.new_id(), (200, 150), 30)
    doc.add_shape(rect)
    doc.add_shape(hole)
    h = Shape(doc.new_id(), "hatch", rings=find_region([rect, hole], (110, 110)).rings, layer="Drawing")
    doc.add_shape(h)
    return p, h


def test_project_save_and_reopen(tmp_path):
    p, h = project_with_fill()
    path = tmp_path / "fill.schematix"
    projectio.save_project(p, str(path))
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
    assert manifest["sheet_schema"] == 3
    back = projectio.open_any(str(path)).project
    h2 = back.sheets[0].shapes[h.id]
    assert h2.kind == "hatch" and h2.to_dict() == h.to_dict()
    assert rg.region_area(h2.rings) == pytest.approx(200 * 100 - math.pi * 900, rel=1e-6)


def test_projects_without_fills_keep_schema_2(tmp_path):
    p = new_project()
    p.sheets[0].add_shape(R(p.sheets[0].new_id(), 0, 0, 10, 10))
    data = projectio.project_bytes(p)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert json.loads(z.read("manifest.json"))["sheet_schema"] == 2
    assert p.sheets[0].to_dict()["schema"] == 2
    p2, _h = project_with_fill()
    assert p2.sheets[0].to_dict()["schema"] == 3


def test_existing_example_projects_still_open():
    import glob
    import os
    here = os.path.dirname(__file__)
    files = glob.glob(os.path.join(here, "..", "examples", "*.schematix"))
    assert files
    for f in files:
        res = projectio.open_any(f)
        data = projectio.project_bytes(res.project)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert json.loads(z.read("manifest.json"))["sheet_schema"] == 2


# ================================================================ exports
def _svg_path_area(d):
    """Independent re-reading of the SVG path (endpoint arc parametrisation,
    SVG spec F.6.5) and exact area of the even-odd region it describes."""
    toks = re.findall(r"[MLAZ]|-?[\d.]+(?:e-?\d+)?", d)
    rings, cur, i = [], None, 0
    while i < len(toks):
        t = toks[i]
        if t == "M":
            cur = [(float(toks[i + 1]), float(toks[i + 2]), 0.0)]
            i += 3
        elif t == "L":
            cur.append((float(toks[i + 1]), float(toks[i + 2]), 0.0))
            i += 3
        elif t == "A":
            r, sweep, x, y = float(toks[i + 1]), int(toks[i + 5]), float(toks[i + 6]), float(toks[i + 7])
            x0, y0, _ = cur[-1]
            chord = math.hypot(x - x0, y - y0)
            ang = 2 * math.asin(min(1.0, chord / (2 * r)))   # small arc (large-arc flag is 0)
            b = math.tan(ang / 4) * (1 if sweep else -1)
            cur[-1] = (x0, y0, b)
            cur.append((x, y, 0.0))
            i += 8
        elif t == "Z":
            if math.dist(cur[0][:2], cur[-1][:2]) < 1e-6:
                cur.pop()                 # the closing vertex repeats the first one
            rings.append(cur)
            i += 1
        else:
            raise AssertionError(t)
    return rings


def test_svg_export_is_exact_vector(tmp_path):
    p, h = project_with_fill()
    path = tmp_path / "fill.svg"
    export.export_svg(p.sheets[0], str(path), project=p)
    svg = path.read_text()
    paths = re.findall(r'<path d="([^"]+)" fill="#000000" fill-rule="evenodd" stroke="none"/>', svg)
    assert len(paths) == 1 and "<image" not in svg
    rings = _svg_path_area(paths[0])
    assert len(rings) == 2 and " A" in paths[0]
    f = p.sheets[0].sheet.scale_factor()
    assert abs(rg.region_area(rings)) == pytest.approx(rg.region_area(h.rings) * f * f, rel=1e-4)
    # the fill is drawn before (underneath) the boundary lines
    assert svg.index("<path") < svg.index('<polygon points="100,100')


def test_pdf_export_fills_with_even_odd_rule(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    p, _h = project_with_fill()
    path = tmp_path / "fill.pdf"
    export.export_pdf(p.sheets[0], str(path), project=p)
    page = pypdf.PdfReader(str(path)).pages[0]
    content = page.get_contents().get_data().decode("latin-1")
    assert "f*" in content and re.search(r"\sc\n", content)


def test_pdf_export_renders_fill_and_hole(tmp_path):
    pdfium = pytest.importorskip("pypdfium2")
    p, _h = project_with_fill()
    doc = p.sheets[0]
    path = tmp_path / "fill.pdf"
    export.export_pdf(p.sheets[0], str(path), project=p)
    pdf = pdfium.PdfDocument(str(path))
    page = pdf[0]
    W, H = doc.sheet.paper_units()
    f = doc.sheet.scale_factor()
    scale = 3
    img = page.render(scale=scale).to_pil().convert("L")

    def px(world):
        x, y = world[0] * f, world[1] * f
        return img.getpixel((int(x / W * img.width), int(y / H * img.height)))
    assert px((150, 120)) < 60           # inside the fill: black
    assert px((200, 150)) > 200          # centre of the hole: white
    assert px((260, 180)) < 60
    assert px((350, 150)) > 200          # outside the boundary: white
    pdf.close()


def test_dxf_export_solids_cover_the_region(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    from openschematix.dxf import export_dxf
    from openschematix.geometry import UNIT_MM
    p, h = project_with_fill()
    path = tmp_path / "fill.dxf"
    export_dxf(p.sheets[0], str(path), project=p)
    d = ezdxf.readfile(str(path))
    auditor = d.audit()
    assert not auditor.has_errors
    inserts = [e for e in d.modelspace() if e.dxftype() == "INSERT"]
    assert len(inserts) == 1 and inserts[0].dxf.layer == "Drawing"
    blk = d.blocks.get(inserts[0].dxf.name)
    solids = [e for e in blk if e.dxftype() == "SOLID"]
    assert solids

    def area(s):
        v = [s.dxf.vtx0, s.dxf.vtx1, s.dxf.vtx3, s.dxf.vtx2]          # SOLID order 1 2 4 3
        return abs(sum(a.x * b.y - b.x * a.y for a, b in zip(v, v[1:] + v[:1]))) / 2
    total = sum(area(s) for s in solids)
    expected = rg.region_area(h.rings) * UNIT_MM * UNIT_MM
    assert total == pytest.approx(expected, rel=3e-4)
    # no solid lies in the hole (hole centre at (200,150) units = 50 mm, sheet height - 37.5 mm)
    W, Hh = p.sheets[0].sheet.size_units()
    cx, cy = 200 * UNIT_MM, (Hh - 150) * UNIT_MM
    for s in solids:
        v = [s.dxf.vtx0, s.dxf.vtx1, s.dxf.vtx3, s.dxf.vtx2]
        mx, my = sum(a.x for a in v) / 4, sum(a.y for a in v) / 4
        assert math.hypot(mx - cx, my - cy) >= 30 * UNIT_MM - 0.01


def test_dxf_without_fills_is_unchanged():
    from openschematix.dxf import to_dxf
    p = new_project()
    p.sheets[0].add_shape(R(p.sheets[0].new_id(), 0, 0, 10, 10))
    text = to_dxf(p.sheets[0], p)
    assert "INSERT" not in text and "BLOCK\n" not in text.replace("BLOCKS", "")
