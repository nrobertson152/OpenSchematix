"""Comprehensive regression tests for scalable arrowhead rendering, orientation, scaling, exports, and transistor symbols."""
import math
import os
import tempfile
import unittest

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
    shape_to_symbol_prim,
    symbol_prim_to_shape,
)
from openschematix.symbols.custom import normalise, to_symdef


class ScalableArrowheadRegressionTests(unittest.TestCase):
    def test_horizontal_vertical_diagonal_orientations(self):
        """Verify arrowheads point accurately along horizontal, vertical, and diagonal lines."""
        cases = [
            ("horizontal_right", (0, 0), (20, 0), (1, 0)),
            ("horizontal_left", (20, 0), (0, 0), (-1, 0)),
            ("vertical_down", (0, 0), (0, 20), (0, 1)),
            ("vertical_up", (0, 20), (0, 0), (0, -1)),
            ("diagonal_dr", (0, 0), (20, 20), (math.sqrt(0.5), math.sqrt(0.5))),
            ("diagonal_ul", (20, 20), (0, 0), (-math.sqrt(0.5), -math.sqrt(0.5))),
        ]
        size = 10.0
        half = size * 0.35
        for name, p0, p1, (ux, uy) in cases:
            with self.subTest(case=name):
                sh = Shape(1, "line", pts=[p0, p1], arrow_end=True, arrow_size=size)
                prims = shape_prims(sh)
                self.assertEqual(len(prims), 2)
                arrow = prims[1]["pts"]
                self.assertEqual(len(arrow), 3)
                # Tip must match end point exactly
                self.assertAlmostEqual(arrow[0][0], p1[0], places=5)
                self.assertAlmostEqual(arrow[0][1], p1[1], places=5)
                # Base center must be tip - u * size
                base_center_x = (arrow[1][0] + arrow[2][0]) / 2.0
                base_center_y = (arrow[1][1] + arrow[2][1]) / 2.0
                expected_bx = p1[0] - ux * size
                expected_by = p1[1] - uy * size
                self.assertAlmostEqual(base_center_x, expected_bx, places=5)
                self.assertAlmostEqual(base_center_y, expected_by, places=5)
                # Base width must be 2 * half
                base_width = math.hypot(arrow[2][0] - arrow[1][0], arrow[2][1] - arrow[1][1])
                self.assertAlmostEqual(base_width, 2 * half, places=5)

    def test_rotation_and_mirroring(self):
        """Verify arrowheads maintain relative orientation under rotation and mirroring."""
        sh = Shape(1, "line", pts=[(10, 10), (30, 10)], arrow_end=True, arrow_size=8.0)
        # Rotate 90 deg CW around (10, 10) -> (10, 10) to (10, 30)
        rotate_shape(sh, (10, 10), 90)
        self.assertAlmostEqual(sh.pts[0][0], 10)
        self.assertAlmostEqual(sh.pts[0][1], 10)
        self.assertAlmostEqual(sh.pts[1][0], 10)
        self.assertAlmostEqual(sh.pts[1][1], 30)

        prims = shape_prims(sh)
        arrow = prims[1]["pts"]
        self.assertAlmostEqual(arrow[0][0], 10)
        self.assertAlmostEqual(arrow[0][1], 30)
        # Base center at (10, 22)
        self.assertAlmostEqual((arrow[1][0] + arrow[2][0]) / 2.0, 10)
        self.assertAlmostEqual((arrow[1][1] + arrow[2][1]) / 2.0, 22)

        # Mirror about vertical line x=0
        mirror_shape(sh, (0, 0), (0, 100))
        self.assertAlmostEqual(sh.pts[0][0], -10)
        self.assertAlmostEqual(sh.pts[0][1], 10)
        self.assertAlmostEqual(sh.pts[1][0], -10)
        self.assertAlmostEqual(sh.pts[1][1], 30)
        arrow_mirrored = shape_prims(sh)[1]["pts"]
        self.assertAlmostEqual(arrow_mirrored[0][0], -10)
        self.assertAlmostEqual(arrow_mirrored[0][1], 30)
        self.assertAlmostEqual((arrow_mirrored[1][0] + arrow_mirrored[2][0]) / 2.0, -10)
        self.assertAlmostEqual((arrow_mirrored[1][1] + arrow_mirrored[2][1]) / 2.0, 22)

    def test_symbol_scale_and_zoom_coordinate_system(self):
        """World-space arrowhead dimensions scale proportionally with geometry scale without distortion."""
        sh = Shape(1, "line", pts=[(0, 0), (20, 0)], arrow_end=True, arrow_size=6.0)
        scale_shape(sh, (0, 0), 2.5)
        self.assertAlmostEqual(sh.arrow_size, 15.0)
        arrow = shape_prims(sh)[1]["pts"]
        self.assertAlmostEqual(arrow[0][0], 50.0)
        self.assertAlmostEqual(arrow[0][1], 0.0)
        base_center_x = (arrow[1][0] + arrow[2][0]) / 2.0
        self.assertAlmostEqual(base_center_x, 35.0)
        base_width = math.hypot(arrow[2][0] - arrow[1][0], arrow[2][1] - arrow[1][1])
        self.assertAlmostEqual(base_width, 15.0 * 0.7)

    def test_small_and_degenerate_geometry(self):
        """Verify short, zero-length lines and small sizes do not crash or produce invalid geometry."""
        # Zero-length line
        sh_zero = Shape(1, "line", pts=[(10, 10), (10, 10)], arrow_start=True, arrow_end=True, arrow_size=5.0)
        prims_zero = shape_prims(sh_zero)
        # Should not produce arrowheads for coincident endpoint neighbors
        self.assertEqual(len(prims_zero), 1)

        # Very short line (shorter than arrowhead size)
        sh_short = Shape(2, "line", pts=[(0, 0), (1, 0)], arrow_end=True, arrow_size=5.0)
        prims_short = shape_prims(sh_short)
        self.assertEqual(len(prims_short), 2)
        arrow_short = prims_short[1]["pts"]
        self.assertEqual(arrow_short[0], (1, 0))
        # Arrow extends backward in line direction (-x)
        self.assertAlmostEqual((arrow_short[1][0] + arrow_short[2][0]) / 2.0, -4.0)

        # Zero size
        self.assertEqual(arrowhead_points((10, 10), (0, 10), 0.0), [])
        # Negative size
        self.assertEqual(arrowhead_points((10, 10), (0, 10), -5.0), [])

    def test_npn_and_pnp_emitter_arrows(self):
        """Verify NPN and PNP transistor emitter arrows point in correct directions across all orientations."""
        for rot in (0, 90, 180, 270):
            for mir in (False, True):
                with self.subTest(rot=rot, mir=mir):
                    c_npn = Component(1, "el.npn", 100, 100, rotation=rot, mirror=mir)
                    c_pnp = Component(2, "el.pnp", 100, 100, rotation=rot, mirror=mir)

                    t_npn = c_npn.terminals()
                    t_pnp = c_pnp.terminals()

                    # Find emitter arrow polygon in scene primitives
                    npn_prims = render.component_prims(c_npn)
                    pnp_prims = render.component_prims(c_pnp)

                    npn_arrow = [p for p in npn_prims if p["k"] == "poly" and len(p.get("pts", [])) == 3 and p.get("fill")][0]
                    pnp_arrow = [p for p in pnp_prims if p["k"] == "poly" and len(p.get("pts", [])) == 3 and p.get("fill")][0]

                    # For NPN: emitter arrow points outward towards emitter pin E
                    npn_tip = npn_arrow["pts"][0]
                    npn_base_center = ((npn_arrow["pts"][1][0] + npn_arrow["pts"][2][0]) / 2.0,
                                      (npn_arrow["pts"][1][1] + npn_arrow["pts"][2][1]) / 2.0)
                    dist_tip_to_E = math.dist(npn_tip, t_npn["E"])
                    dist_base_to_E = math.dist(npn_base_center, t_npn["E"])
                    self.assertLess(dist_tip_to_E, dist_base_to_E, "NPN arrow must point towards emitter terminal E")

                    # For PNP: emitter arrow points inward from emitter branch towards base bar
                    pnp_tip = pnp_arrow["pts"][0]
                    pnp_base_center = ((pnp_arrow["pts"][1][0] + pnp_arrow["pts"][2][0]) / 2.0,
                                      (pnp_arrow["pts"][1][1] + pnp_arrow["pts"][2][1]) / 2.0)
                    dist_tip_to_base = math.dist(pnp_tip, t_pnp["B"])
                    dist_base_to_base = math.dist(pnp_base_center, t_pnp["B"])
                    self.assertLess(dist_tip_to_base, dist_base_to_base, "PNP arrow must point towards base terminal B")

    def test_canvas_vs_svg_pdf_geometry_consistency(self):
        """Verify canvas rendering primitives match SVG and PDF export geometry directly."""
        doc = Document()
        line_shape = Shape(1, "line", pts=[(50, 50), (150, 50)], arrow_start=True, arrow_end=True, arrow_size=12.0)
        doc.add_shape(line_shape)
        c = editing.place(doc, "el.npn", 200, 200)

        # 1. Scene primitives used by canvas
        scene_items = render.scene(doc, screen=True)
        filled_polys = [it for it in scene_items if it.get("k") == "poly" and it.get("fill")]
        self.assertEqual(len(filled_polys), 3)  # 2 for line ends, 1 for NPN emitter

        # 2. Export to SVG
        with tempfile.TemporaryDirectory() as td:
            svg_file = os.path.join(td, "test.svg")
            export.export_svg(doc, svg_file, use_sheet=False)
            with open(svg_file, "r") as f:
                svg_content = f.read()

            # Every filled polygon points in scene_items must match the formatted SVG polygon points
            for poly in filled_polys:
                pts_str = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in poly["pts"])
                self.assertIn(f'<polygon points="{pts_str}"', svg_content)

            # 3. Export to PDF
            pdf_file = os.path.join(td, "test.pdf")
            export.export_pdf(doc, pdf_file, use_sheet=False)
            with open(pdf_file, "rb") as f:
                pdf_data = f.read()
            self.assertGreater(len(pdf_data), 100)

    def test_pin_connectivity_preserved(self):
        """Arrowheads must not affect terminal locations or wire connectivity."""
        doc = Document()
        npn = editing.place(doc, "el.npn", 100, 100)
        e_pin = npn.terminals()["E"]
        w = Wire(doc.new_id(), [e_pin, (e_pin[0], e_pin[1] + 30)], [npn.id, "E"], [None, None])
        doc.add_wire(w)

        # Add a nearby line with a large arrow
        sh = Shape(doc.new_id(), "line", pts=[(110, 110), (110, 140)], arrow_end=True, arrow_size=20.0)
        doc.add_shape(sh)

        conn = connectivity.analyse(doc)
        # Wire end is connected to E terminal, and other end is open
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
                {"k": "line", "pts": [[0, 10], [30, 10]]},  # No arrow
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
