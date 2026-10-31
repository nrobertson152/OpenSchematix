"""Regression tests for scalable line and polyline arrowheads."""
import math
import unittest

from openschematix.model import Shape
from openschematix.shapes import shape_prims, rotate_shape, move_shape, scale_shape, shape_to_symbol_prim, symbol_prim_to_shape


class ArrowheadTests(unittest.TestCase):
    def test_default_has_no_arrows(self):
        shape = Shape(1, "line", pts=[(0, 0), (30, 0)])
        self.assertEqual(len(shape_prims(shape)), 1)
        self.assertNotIn("arrow_start", shape.to_dict())
        self.assertNotIn("arrow_end", shape.to_dict())

    def test_both_ends_and_persistence(self):
        shape = Shape(1, "line", pts=[(0, 0), (30, 0)],
                      arrow_start=True, arrow_end=True, arrow_size=8)
        primitives = shape_prims(shape)
        self.assertEqual([p["k"] for p in primitives], ["line", "poly", "poly"])
        self.assertTrue(all(p["fill"] for p in primitives[1:]))
        self.assertEqual(primitives[1]["pts"][0], (0, 0))
        self.assertEqual(primitives[2]["pts"][0], (30, 0))
        restored = Shape.from_dict(shape.to_dict())
        self.assertEqual(restored.arrow_size, 8)
        self.assertTrue(restored.arrow_start and restored.arrow_end)
        self.assertEqual(shape_prims(restored), primitives)

    def test_polyline_endpoint_direction(self):
        shape = Shape(2, "polyline", pts=[(0, 0), (20, 0), (20, 20)],
                      arrow_end=True, arrow_size=10)
        arrow = shape_prims(shape)[1]["pts"]
        self.assertEqual(arrow[0], (20, 20))
        self.assertAlmostEqual((arrow[1][1] + arrow[2][1]) / 2, 10)

    def test_duplicate_endpoint_and_degenerate_line(self):
        shape = Shape(3, "polyline", pts=[(0, 0), (10, 0), (10, 0)],
                      arrow_end=True)
        self.assertEqual(len(shape_prims(shape)), 2)
        shape.pts = [(0, 0), (0, 0)]
        self.assertEqual(len(shape_prims(shape)), 1)

    def test_rotation_and_translation(self):
        shape = Shape(4, "line", pts=[(0, 0), (20, 0)], arrow_end=True)
        rotate_shape(shape, (0, 0), 90)
        move_shape(shape, 5, 7)
        arrow = shape_prims(shape)[1]["pts"]
        self.assertAlmostEqual(arrow[0][0], 5)
        self.assertAlmostEqual(arrow[0][1], 27)

    def test_scale_changes_arrowhead_size(self):
        shape = Shape(6, "line", pts=[(0, 0), (20, 0)],
                      arrow_end=True, arrow_size=5)
        scale_shape(shape, (0, 0), 2)
        self.assertEqual(shape.arrow_size, 10)
        arrow = shape_prims(shape)[1]["pts"]
        self.assertEqual(arrow[0], (40, 0))
        self.assertAlmostEqual((arrow[1][0] + arrow[2][0]) / 2, 30)

    def test_bbox_includes_arrowhead(self):
        shape = Shape(7, "line", pts=[(0, 0), (30, 0)],
                      arrow_start=True, arrow_end=True, arrow_size=10)
        x0, y0, x1, y1 = shape.bbox()
        self.assertLess(y0, 0)
        self.assertGreater(y1, 0)
        self.assertEqual((x0, x1), (0, 30))

    def test_custom_symbol_primitive_roundtrip(self):
        shape = Shape(8, "line", pts=[(0, 0), (20, 0)],
                      arrow_start=True, arrow_end=True, arrow_size=7)
        primitive = shape_to_symbol_prim(shape)
        restored = symbol_prim_to_shape(primitive, 9)
        self.assertTrue(restored.arrow_start and restored.arrow_end)
        self.assertEqual(restored.arrow_size, 7)
        self.assertEqual(len(shape_prims(restored)), 3)

    def test_strict_arrow_flag_decoding(self):
        data = Shape(10, "line", pts=[(0, 0), (20, 0)]).to_dict()
        data.update(arrow_start="false", arrow_end=1, arrow_size=True)
        restored = Shape.from_dict(data)
        self.assertFalse(restored.arrow_start)
        self.assertFalse(restored.arrow_end)
        self.assertEqual(restored.arrow_size, 10)

    def test_invalid_arrow_size_falls_back(self):
        data = Shape(5, "line", pts=[(0, 0), (20, 0)]).to_dict()
        data["arrow_size"] = -1
        self.assertEqual(Shape.from_dict(data).arrow_size, 10.0)
        for bad in (0, "abc", None, float("nan"), float("inf")):
            data["arrow_size"] = bad
            self.assertEqual(Shape.from_dict(data).arrow_size, 10.0)


if __name__ == "__main__":
    unittest.main()
