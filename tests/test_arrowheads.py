"""Regression tests for scalable line and polyline arrowheads."""
import math
import unittest

from openschematix.model import Shape
from openschematix.shapes import shape_prims, rotate_shape, move_shape


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

    def test_invalid_arrow_size_rejected(self):
        data = Shape(5, "line", pts=[(0, 0), (20, 0)]).to_dict()
        data["arrow_size"] = -1
        with self.assertRaises(ValueError):
            Shape.from_dict(data)


if __name__ == "__main__":
    unittest.main()
