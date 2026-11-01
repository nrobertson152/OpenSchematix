"""Regression tests for overlapping-wire junction detection and classification.

Tests cover:
  1. Collinear overlapping wires: zero junctions.
  2. End-to-end collinear wires: zero junctions.
  3. True T-junction: one junction.
  4. Four-way connected junction: one junction.
  5. Perpendicular crossing without shared endpoints: zero junctions.
  6. Coincident endpoints and duplicate geometry: no spurious junctions.
  7. Terminal connections: correct junction classification.
  8. Insertion-order invariance.
  9. SVG/PDF exports: no false junction markers.
"""
import itertools
import xml.etree.ElementTree as ET

import pytest

from openschematix import editing, export, render
from openschematix.connectivity import analyse
from openschematix.model import Document, Wire
from openschematix.netlist import compute_nets
from openschematix.project import Project


def test_collinear_overlapping_wires():
    """1. Collinear overlapping wires: zero junctions."""
    d = Document()
    editing.add_wire(d, [(0, 0), (100, 0)])
    editing.add_wire(d, [(40, 0), (80, 0)])
    conn = analyse(d)
    assert conn.junctions == []

    # Also test vertical collinear overlap
    d_v = Document()
    editing.add_wire(d_v, [(50, 0), (50, 200)])
    editing.add_wire(d_v, [(50, 40), (50, 160)])
    assert analyse(d_v).junctions == []

    # Partial overlap extending past one end
    d_p = Document()
    editing.add_wire(d_p, [(0, 0), (100, 0)])
    editing.add_wire(d_p, [(50, 0), (150, 0)])
    assert analyse(d_p).junctions == []


def test_end_to_end_collinear_wires():
    """2. End-to-end collinear wires: zero junctions."""
    d = Document()
    editing.add_wire(d, [(0, 0), (50, 0)])
    editing.add_wire(d, [(50, 0), (100, 0)])
    conn = analyse(d)
    assert conn.junctions == []

    # Vertical end-to-end collinear wires
    d_v = Document()
    editing.add_wire(d_v, [(10, 0), (10, 50)])
    editing.add_wire(d_v, [(10, 50), (10, 100)])
    assert analyse(d_v).junctions == []


def test_true_t_junction():
    """3. True T-junction: one junction."""
    # Branch landing on the interior of a through wire
    d1 = Document()
    editing.add_wire(d1, [(0, 0), (100, 0)])
    editing.add_wire(d1, [(50, 0), (50, 50)])
    conn1 = analyse(d1)
    assert [tuple(p) for p in conn1.junctions] == [(50.0, 0.0)]

    # Two collinear wire ends meeting a perpendicular branch end
    d2 = Document()
    editing.add_wire(d2, [(0, 0), (50, 0)])
    editing.add_wire(d2, [(50, 0), (100, 0)])
    editing.add_wire(d2, [(50, 0), (50, 50)])
    conn2 = analyse(d2)
    assert [tuple(p) for p in conn2.junctions] == [(50.0, 0.0)]


def test_four_way_connected_junction():
    """4. Four-way connected junction: one junction."""
    d = Document()
    editing.add_wire(d, [(0, 50), (100, 50)])
    editing.add_wire(d, [(50, 0), (50, 100)])
    connected = editing.connect_crossing(d, (50, 50))
    assert connected is True
    conn = analyse(d)
    assert [tuple(p) for p in conn.junctions] == [(50.0, 50.0)]

    # 4 distinct wire segments meeting at (50, 50)
    d4 = Document()
    editing.add_wire(d4, [(0, 50), (50, 50)])
    editing.add_wire(d4, [(50, 50), (100, 50)])
    editing.add_wire(d4, [(50, 0), (50, 50)])
    editing.add_wire(d4, [(50, 50), (50, 100)])
    assert [tuple(p) for p in analyse(d4).junctions] == [(50.0, 50.0)]


def test_perpendicular_crossing_without_shared_endpoints():
    """5. Perpendicular crossing without shared endpoints: zero junctions."""
    d = Document()
    editing.add_wire(d, [(0, 50), (100, 50)])
    editing.add_wire(d, [(50, 0), (50, 100)])
    conn = analyse(d)
    assert conn.junctions == []

    # Verify that the crossing is detected as an unconnected crossing
    cross = editing.crossings(d)
    assert len(cross) == 1
    assert tuple(cross[0][0]) == (50.0, 50.0)

    # Netlist semantics: two separate nets
    proj = Project()
    proj.sheets = [d]
    d.project = proj
    nets = compute_nets(proj)
    assert len(nets) == 2


def test_coincident_endpoints_and_duplicate_geometry():
    """6. Coincident endpoints and duplicate geometry: no spurious junctions."""
    # Duplicate identical wires
    d = Document()
    editing.add_wire(d, [(0, 0), (100, 0)])
    editing.add_wire(d, [(0, 0), (100, 0)])
    conn = analyse(d)
    assert conn.junctions == []

    # Coincident corner (2 segments meeting at 90 deg from separate wires)
    d_corner = Document()
    editing.add_wire(d_corner, [(0, 0), (50, 0)])
    editing.add_wire(d_corner, [(50, 0), (50, 50)])
    assert analyse(d_corner).junctions == []

    # Zero-length degenerate wire
    d_degen = Document()
    w_degen = Wire(d_degen.new_id(), [(10.0, 10.0), (10.0, 10.0)])
    d_degen.add_wire(w_degen)
    w_line = Wire(d_degen.new_id(), [(10.0, 10.0), (50.0, 10.0)])
    d_degen.add_wire(w_line)
    assert analyse(d_degen).junctions == []


def test_terminal_connections():
    """7. Terminal connections: correct junction classification."""
    # Wire ending at terminal: 1 wire + 1 terminal = 2 branches -> NO junction
    d = Document()
    r = editing.place(d, "el.resistor.iec", 100, 100)  # terminals at (80, 100) and (120, 100)
    editing.add_wire(d, [(0, 100), (80, 100)])
    conn = analyse(d)
    assert conn.junctions == []
    assert (r.id, "1") in conn.connected_terminals

    # Two wires meeting at a terminal: 2 distinct wire dirs + 1 terminal = 3 branches -> junction dot
    editing.add_wire(d, [(80, 100), (80, 200)])
    conn2 = analyse(d)
    assert [tuple(p) for p in conn2.junctions] == [(80.0, 100.0)]

    # Wire merely passing over terminal: not connected -> NO junction dot
    d3 = Document()
    r3 = editing.place(d3, "el.resistor.iec", 100, 100)
    editing.add_wire(d3, [(60, 100), (140, 100)])
    conn3 = analyse(d3)
    assert conn3.junctions == []
    assert (r3.id, "1") in {t[:2] for t in conn3.open_terminals}
    assert (r3.id, "2") in {t[:2] for t in conn3.open_terminals}


def test_insertion_order_invariance():
    """8. Insertion-order invariance."""
    permutations = [
        ([(0, 0), (100, 0)], [(40, 0), (80, 0)]),
        ([(40, 0), (80, 0)], [(0, 0), (100, 0)]),
    ]
    for w1_pts, w2_pts in permutations:
        d = Document()
        editing.add_wire(d, w1_pts)
        editing.add_wire(d, w2_pts)
        assert analyse(d).junctions == []

    # T-junction with different insertion orders
    t_orders = [
        ([(0, 0), (100, 0)], [(50, 0), (50, 50)]),
        ([(50, 0), (50, 50)], [(0, 0), (100, 0)]),
    ]
    for w1_pts, w2_pts in t_orders:
        d = Document()
        editing.add_wire(d, w1_pts)
        editing.add_wire(d, w2_pts)
        assert [tuple(p) for p in analyse(d).junctions] == [(50.0, 0.0)]


def test_svg_and_pdf_exports_no_false_junction_markers(tmp_path):
    """9. SVG/PDF exports: no false junction markers."""
    doc = Document()
    # Overlapping collinear wires
    editing.add_wire(doc, [(0, 0), (100, 0)])
    editing.add_wire(doc, [(40, 0), (80, 0)])

    # Crossing wires
    editing.add_wire(doc, [(50, -50), (50, 50)])

    # Scene primitives
    prims = render.scene(doc)
    junction_prims = [p for p in prims if p.get("role") == "junction"]
    assert len(junction_prims) == 0

    # SVG export
    svg_file = tmp_path / "test_out.svg"
    export.export_svg(doc, str(svg_file))
    svg_tree = ET.parse(str(svg_file))
    svg_root = svg_tree.getroot()

    # In SVG export, junctions are drawn as circles; ensure no circle exists around (40, 0) or (80, 0)
    for elem in svg_root.iter():
        if elem.tag.endswith("circle"):
            cx = float(elem.attrib.get("cx", 0))
            cy = float(elem.attrib.get("cy", 0))
            assert not (abs(cx - 40.0) < 1.0 and abs(cy - 0.0) < 1.0)
            assert not (abs(cx - 80.0) < 1.0 and abs(cy - 0.0) < 1.0)

    # PDF export
    pdf_bytes = export.to_pdf(doc)
    assert pdf_bytes.startswith(b"%PDF")
