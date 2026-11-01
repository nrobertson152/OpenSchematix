"""Comprehensive regression tests for scalable arrowhead rendering, orientation, scaling, exports, and transistor symbols."""
import math
import os
import re
import tempfile
import unittest
import zlib

from openschematix import connectivity, editing, export, render, shapes, symbols
from openschematix.export import _fmt
from openschematix.model import Component, Document, Shape, Wire
from openschematix.shapes import (
    arrowhead_points,
    mirror_shape,
    move_shape,
    rotate_shape,
    scale_shape,
    shape_prims,
)
from openschematix.symbols.custom import normalise, to_symdef


def polygon_area(pts):
    """Compute polygon area using the standard shoelace formula."""
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(area) / 2.0


class ScalableArrowheadRegressionTests(unittest.TestCase):
    def test_hand_calculated_fixed_coordinates(self):
        """Verify fixed numerical coordinates against independent hand calculations.

        Hand calculation 1:
        Line from (10, 20) to (50, 20), arrow at end, size = 10.0.
        Direction: vector from (10, 20) to (50, 20) is (40, 0), length = 40.
        Unit direction: u = (1, 0).
        Perpendicular unit: p = (0, 1) or (-uy, ux) = (0, 1).
        Base center: tip - u * size = (50 - 10, 20 - 0) = (40, 20).
        Half width: 10.0 * 0.35 = 3.5.
        Base vertex 1: (40 - 0 * 3.5, 20 + 1 * 3.5) = (40.0, 23.5).
        Base vertex 2: (40 + 0 * 3.5, 20 - 1 * 3.5) = (40.0, 16.5).
        Expected vertices: [(50.0, 20.0), (40.0, 23.5), (40.0, 16.5)].

        Hand calculation 2:
        Diagonal line (3-4-5 triangle scaled):
        Line from (0, 0) to (30, 40).
        dx = 30, dy = 40, length = 50.
        ux = 30 / 50 = 0.6, uy = 40 / 50 = 0.8.
        Arrow at end, size = 10.0.
        Base center: tip - u * 10 = (30 - 6, 40 - 8) = (24.0, 32.0).
        Half width: 3.5.
        Perpendicular offset: (-uy * 3.5, ux * 3.5) = (-0.8 * 3.5, 0.6 * 3.5) = (-2.8, 2.1).
        Base vertex 1: (24.0 - 2.8, 32.0 + 2.1) = (21.2, 34.1).
        Base vertex 2: (24.0 + 2.8, 32.0 - 2.1) = (26.8, 29.9).
        Expected vertices: [(30.0, 40.0), (21.2, 34.1), (26.8, 29.9)].
        """
        # Case 1: horizontal line
        sh1 = Shape(1, "line", pts=[(10, 20), (50, 20)], arrow_end=True, arrow_size=10.0)
        prims1 = shape_prims(sh1)
        self.assertEqual(len(prims1), 2)
        arrow1 = prims1[1]["pts"]
        self.assertAlmostEqual(arrow1[0][0], 50.0, places=6)
        self.assertAlmostEqual(arrow1[0][1], 20.0, places=6)
        self.assertAlmostEqual(arrow1[1][0], 40.0, places=6)
        self.assertAlmostEqual(arrow1[1][1], 23.5, places=6)
        self.assertAlmostEqual(arrow1[2][0], 40.0, places=6)
        self.assertAlmostEqual(arrow1[2][1], 16.5, places=6)

        # Case 2: 3-4-5 diagonal line
        sh2 = Shape(2, "line", pts=[(0, 0), (30, 40)], arrow_end=True, arrow_size=10.0)
        prims2 = shape_prims(sh2)
        self.assertEqual(len(prims2), 2)
        arrow2 = prims2[1]["pts"]
        self.assertAlmostEqual(arrow2[0][0], 30.0, places=6)
        self.assertAlmostEqual(arrow2[0][1], 40.0, places=6)
        self.assertAlmostEqual(arrow2[1][0], 21.2, places=6)
        self.assertAlmostEqual(arrow2[1][1], 34.1, places=6)
        self.assertAlmostEqual(arrow2[2][0], 26.8, places=6)
        self.assertAlmostEqual(arrow2[2][1], 29.9, places=6)

    def test_mathematical_invariants(self):
        """Verify mathematical invariants across diverse angles and sizes without calling helper transforms."""
        angles_deg = [0, 30, 45, 60, 90, 120, 135, 180, 210, 270, 315]
        sizes = [2.0, 5.0, 10.0, 17.5]

        for deg in angles_deg:
            rad = math.radians(deg)
            # Line endpoints
            p0 = (50.0, 50.0)
            dx = 60.0 * math.cos(rad)
            dy = 60.0 * math.sin(rad)
            p1 = (p0[0] + dx, p0[1] + dy)
            ux, uy = dx / 60.0, dy / 60.0

            for size in sizes:
                sh = Shape(1, "line", pts=[p0, p1], arrow_end=True, arrow_size=size)
                prims = shape_prims(sh)
                arrow = prims[1]["pts"]
                tip = arrow[0]
                v1 = arrow[1]
                v2 = arrow[2]

                # Invariant 1: Tip coincidence
                self.assertAlmostEqual(tip[0], p1[0], places=5)
                self.assertAlmostEqual(tip[1], p1[1], places=5)

                # Invariant 2: Base center is exactly tip - u * size
                base_center = ((v1[0] + v2[0]) / 2.0, (v1[1] + v2[1]) / 2.0)
                expected_base_center = (p1[0] - ux * size, p1[1] - uy * size)
                self.assertAlmostEqual(base_center[0], expected_base_center[0], places=5)
                self.assertAlmostEqual(base_center[1], expected_base_center[1], places=5)

                # Invariant 3: Arrowhead base segment (v2 - v1) is perpendicular to line direction (u)
                base_vec = (v2[0] - v1[0], v2[1] - v1[1])
                dot_product = base_vec[0] * ux + base_vec[1] * uy
                self.assertAlmostEqual(dot_product, 0.0, places=5)

                # Invariant 4: Base width is exactly 2 * 0.35 * size = 0.7 * size
                base_width = math.hypot(base_vec[0], base_vec[1])
                self.assertAlmostEqual(base_width, 0.7 * size, places=5)

                # Invariant 5: Arrowhead points along line direction (dot product of (tip - base_center) with u is positive)
                arrow_dir = (tip[0] - base_center[0], tip[1] - base_center[1])
                dir_dot = arrow_dir[0] * ux + arrow_dir[1] * uy
                self.assertAlmostEqual(dir_dot, size, places=5)
                self.assertGreater(dir_dot, 0.0)

                # Invariant 6: Area is exactly 0.5 * base * height = 0.5 * (0.7 * size) * size = 0.35 * size^2
                area = polygon_area(arrow)
                expected_area = 0.35 * (size ** 2)
                self.assertAlmostEqual(area, expected_area, places=5)

    def test_quadratic_area_scaling_and_transforms(self):
        """Verify that scaling the shape geometry scales arrowhead area quadratically."""
        sh = Shape(1, "line", pts=[(0, 0), (40, 0)], arrow_end=True, arrow_size=5.0)
        area_initial = polygon_area(shape_prims(sh)[1]["pts"])
        self.assertAlmostEqual(area_initial, 0.35 * (5.0 ** 2), places=5)

        k = 3.0
        scale_shape(sh, (0, 0), k)
        self.assertAlmostEqual(sh.arrow_size, 15.0)
        area_scaled = polygon_area(shape_prims(sh)[1]["pts"])
        # Area must scale by k^2
        self.assertAlmostEqual(area_scaled, area_initial * (k ** 2), places=5)
        self.assertAlmostEqual(area_scaled, 0.35 * (15.0 ** 2), places=5)

        # Nonuniform reflection / rotation combined test
        # Mirror about y-axis x=0
        mirror_shape(sh, (0, 0), (0, 100))
        # Rotate 90 degrees CW around (0, 0)
        rotate_shape(sh, (0, 0), 90)
        arrow_xformed = shape_prims(sh)[1]["pts"]
        # Expected transformed end point:
        # initial end (40 * 3 = 120, 0).
        # mirror across x=0 -> (-120, 0).
        # rotate 90 CW around (0,0) (x, y) -> (-y, x) -> (0, -120).
        self.assertAlmostEqual(arrow_xformed[0][0], 0.0, places=5)
        self.assertAlmostEqual(arrow_xformed[0][1], -120.0, places=5)
        # Transformed area remains invariant under rigid rotation/reflection
        self.assertAlmostEqual(polygon_area(arrow_xformed), area_scaled, places=5)

    def test_polylines_and_edge_cases(self):
        """Test multi-segment polylines, coincident vertices, degenerate segments, and malformed inputs."""
        # 1. Multi-segment polyline with arrows at both ends
        poly_sh = Shape(1, "polyline", pts=[(0, 0), (30, 0), (30, 40), (70, 40)],
                        arrow_start=True, arrow_end=True, arrow_size=10.0)
        prims = shape_prims(poly_sh)
        self.assertEqual(len(prims), 3)  # polyline + 2 arrows
        arrow_start = prims[1]["pts"]
        arrow_end = prims[2]["pts"]
        # Start arrow tip at (0, 0), points inward along first segment (toward (0, 0) from (30, 0))
        self.assertEqual(arrow_start[0], (0, 0))
        self.assertAlmostEqual((arrow_start[1][0] + arrow_start[2][0]) / 2.0, 10.0)
        self.assertAlmostEqual((arrow_start[1][1] + arrow_start[2][1]) / 2.0, 0.0)
        # End arrow tip at (70, 40), points from (30, 40) toward (70, 40)
        self.assertEqual(arrow_end[0], (70, 40))
        self.assertAlmostEqual((arrow_end[1][0] + arrow_end[2][0]) / 2.0, 60.0)
        self.assertAlmostEqual((arrow_end[1][1] + arrow_end[2][1]) / 2.0, 40.0)

        # 2. Repeated/coincident vertices at endpoints
        coincident_sh = Shape(2, "polyline", pts=[(0, 0), (0, 0), (50, 0), (50, 0)],
                              arrow_start=True, arrow_end=True, arrow_size=8.0)
        c_prims = shape_prims(coincident_sh)
        self.assertEqual(len(c_prims), 3)
        self.assertEqual(c_prims[1]["pts"][0], (0, 0))
        self.assertEqual(c_prims[2]["pts"][0], (50, 0))

        # 3. Arrowhead larger than segment (e.g. size 30 on a segment of length 5)
        long_arrow_sh = Shape(3, "line", pts=[(0, 0), (5, 0)], arrow_end=True, arrow_size=30.0)
        la_prims = shape_prims(long_arrow_sh)
        self.assertEqual(len(la_prims), 2)
        la_arrow = la_prims[1]["pts"]
        self.assertEqual(la_arrow[0], (5, 0))
        # Extends backward past the start to -25
        self.assertAlmostEqual((la_arrow[1][0] + la_arrow[2][0]) / 2.0, -25.0)

        # 4. Zero-length line produces no arrow
        zero_sh = Shape(4, "line", pts=[(15, 20), (15, 20)], arrow_end=True, arrow_size=10.0)
        self.assertEqual(len(shape_prims(zero_sh)), 1)

        # 5. Invalid arrow sizes fall back to default 10.0 in Shape.from_dict
        for bad_val in (-5.0, 0.0, float("nan"), float("inf"), "invalid", None):
            data = Shape(5, "line", pts=[(0, 0), (10, 0)], arrow_end=True).to_dict()
            data["arrow_size"] = bad_val
            restored = Shape.from_dict(data)
            self.assertEqual(restored.arrow_size, 10.0)

    def test_npn_and_pnp_emitter_arrows(self):
        """Verify NPN and PNP transistor emitter arrows point in correct directions across all orientations."""
        for rot in (0, 90, 180, 270):
            for mir in (False, True):
                with self.subTest(rot=rot, mir=mir):
                    c_npn = Component(1, "el.npn", 100, 100, rotation=rot, mirror=mir)
                    c_pnp = Component(2, "el.pnp", 100, 100, rotation=rot, mirror=mir)

                    t_npn = c_npn.terminals()
                    t_pnp = c_pnp.terminals()

                    npn_prims = render.component_prims(c_npn)
                    pnp_prims = render.component_prims(c_pnp)

                    npn_arrow = [p for p in npn_prims if p["k"] == "poly" and len(p.get("pts", [])) == 3 and p.get("fill")][0]
                    pnp_arrow = [p for p in pnp_prims if p["k"] == "poly" and len(p.get("pts", [])) == 3 and p.get("fill")][0]

                    # NPN arrow points outward towards emitter terminal E
                    npn_tip = npn_arrow["pts"][0]
                    npn_base_center = ((npn_arrow["pts"][1][0] + npn_arrow["pts"][2][0]) / 2.0,
                                      (npn_arrow["pts"][1][1] + npn_arrow["pts"][2][1]) / 2.0)
                    dist_tip_to_E = math.dist(npn_tip, t_npn["E"])
                    dist_base_to_E = math.dist(npn_base_center, t_npn["E"])
                    self.assertLess(dist_tip_to_E, dist_base_to_E)

                    # PNP arrow points inward towards base terminal B
                    pnp_tip = pnp_arrow["pts"][0]
                    pnp_base_center = ((pnp_arrow["pts"][1][0] + pnp_arrow["pts"][2][0]) / 2.0,
                                      (pnp_arrow["pts"][1][1] + pnp_arrow["pts"][2][1]) / 2.0)
                    dist_tip_to_base = math.dist(pnp_tip, t_pnp["B"])
                    dist_base_to_base = math.dist(pnp_base_center, t_pnp["B"])
                    self.assertLess(dist_tip_to_base, dist_base_to_base)

    def test_svg_export_independent_geometry(self):
        """Verify SVG export contains expected polygon coordinates and attributes without omission."""
        doc = Document()
        # Horizontal line with hand-calculated expected arrow
        sh = Shape(1, "line", pts=[(100, 200), (140, 200)], arrow_end=True, arrow_size=10.0)
        doc.add_shape(sh)

        # Expected vertices: tip=(140, 200), v1=(130, 203.5), v2=(130, 196.5)
        # Formatted according to SVG export: "140,200 130,203.5 130,196.5"
        expected_pts_str = "140,200 130,203.5 130,196.5"

        with tempfile.TemporaryDirectory() as td:
            svg_file = os.path.join(td, "test.svg")
            export.export_svg(doc, svg_file, use_sheet=False)
            with open(svg_file, "r") as f:
                svg_content = f.read()

            expected_tag = f'<polygon points="{expected_pts_str}" stroke-width="1.4" fill="#000000"/>'
            self.assertIn(expected_tag, svg_content)

    def test_pdf_export_independent_operators(self):
        """Verify PDF export drawing stream directly contains expected transformation, path, and fill operators."""
        doc = Document()
        # Single line with arrow at end: tip=(150, 100), base=(140, 103.5), (140, 96.5)
        sh = Shape(1, "line", pts=[(50, 100), (150, 100)], arrow_end=True, arrow_size=10.0)
        doc.add_shape(sh)

        with tempfile.TemporaryDirectory() as td:
            pdf_file = os.path.join(td, "test.pdf")
            export.export_pdf(doc, pdf_file, use_sheet=False)
            with open(pdf_file, "rb") as f:
                pdf_data = f.read()

            streams = re.findall(b"stream\r?\n(.*?)\r?\nendstream", pdf_data, re.DOTALL)
            found_decompressed = False
            for s in streams:
                try:
                    decomp = zlib.decompress(s).decode("latin1")
                    found_decompressed = True
                    # Look for the arrowhead path commands in PDF:
                    # 150 100 m\n140 103.5 l\n140 96.5 l\nb
                    pattern = r"150 100 m\s+140 103\.5 l\s+140 96\.5 l\s+b"
                    self.assertRegex(decomp, pattern, "PDF stream must contain exact arrowhead polygon and fill operator 'b'")
                except zlib.error:
                    continue
            self.assertTrue(found_decompressed)

    def test_pin_connectivity_preserved(self):
        """Arrowheads must not affect terminal locations or wire connectivity."""
        doc = Document()
        npn = editing.place(doc, "el.npn", 100, 100)
        e_pin = npn.terminals()["E"]
        w = Wire(doc.new_id(), [e_pin, (e_pin[0], e_pin[1] + 30)], [npn.id, "E"], [None, None])
        doc.add_wire(w)

        # Add nearby line with a large arrow
        sh = Shape(doc.new_id(), "line", pts=[(110, 110), (110, 140)], arrow_end=True, arrow_size=20.0)
        doc.add_shape(sh)

        conn = connectivity.analyse(doc)
        self.assertEqual(len(conn.open_wire_ends), 1)
        self.assertFalse(any(cid == npn.id and name == "E" for cid, name, _ in conn.open_terminals))

    def test_serialization_and_compatibility(self):
        """Ensure serialization remains backward compatible with existing schema and symbols."""
        data = {
            "format": "OpenSchematix Symbol",
            "version": 1,
            "id": "user:testarrow000001",
            "name": "Arrow Test",
            "category": "General",
            "prims": [
                {"k": "line", "pts": [[0, 0], [30, 0]], "arrow_end": True, "arrow_size": 8.5},
                {"k": "line", "pts": [[0, 10], [30, 10]]},
            ],
            "pins": [{"id": "p1", "name": "1", "x": 0, "y": 0, "dir": "l"}],
        }
        cleaned = normalise(data)
        self.assertTrue(cleaned["prims"][0]["arrow_end"])
        self.assertEqual(cleaned["prims"][0]["arrow_size"], 8.5)
        self.assertNotIn("arrow_end", cleaned["prims"][1])

        symdef = to_symdef(cleaned)
        geom = symdef.build()
        poly_prims = [p for p in geom.prims if p["k"] == "poly" and p.get("fill")]
        self.assertEqual(len(poly_prims), 1)
        self.assertEqual(poly_prims[0]["pts"][0], (30, 0))


if __name__ == "__main__":
    unittest.main()
