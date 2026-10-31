"""Regression tests for conservative FILL boundary discovery."""
from openschematix.boundary_fill import find_boundary
from openschematix.model import Shape


def test_disconnected_lines_form_region():
    shapes = [
        Shape(i, "line", pts=[a, b])
        for i, (a, b) in enumerate([
            ((0, 0), (20, 0)), ((20, 0), (20, 10)),
            ((20, 10), (0, 10)), ((0, 10), (0, 0))
        ], 1)
    ]
    assert len(find_boundary(shapes, (5, 5))) == 4
    assert find_boundary(shapes, (30, 5)) is None


def test_open_and_branching_boundaries_rejected():
    edges = [
        Shape(1, "line", pts=[(0, 0), (10, 0)]),
        Shape(2, "line", pts=[(10, 0), (10, 10)]),
        Shape(3, "line", pts=[(10, 10), (0, 10)]),
    ]
    assert find_boundary(edges, (5, 5)) is None
    edges.append(Shape(4, "line", pts=[(0, 10), (0, 0)]))
    edges.append(Shape(5, "line", pts=[(0, 0), (-5, 0)]))
    assert find_boundary(edges, (5, 5)) is None


def test_closed_shapes_and_nested_regions():
    outer = Shape(1, "rect", pts=[(0, 0), (20, 0), (20, 20), (0, 20)])
    inner = Shape(2, "circle", c=(10, 10), r=3)
    assert len(find_boundary([outer], (5, 5))) == 4
    assert find_boundary([outer, inner], (10, 10)) is None


def test_filled_polygon_persists_and_exports_as_vector_primitive():
    from openschematix.shapes import shape_prims
    shape = Shape(8, "polygon", pts=[(0, 0), (10, 0), (10, 10), (0, 10)], fill=True)
    decoded = Shape.from_dict(shape.to_dict())
    assert decoded.fill
    assert shape_prims(decoded)[0]["k"] == "poly"
    assert shape_prims(decoded)[0]["fill"] is True
