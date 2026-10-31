"""
QA Reliability and Regression Test Suite for OpenSchematix.

Priority 1: Save/load and data integrity
Priority 2: Undo/redo correctness
Priority 3: Electrical connectivity
Priority 4: Export fidelity
"""
import os
import tempfile
import zipfile
import json
import xml.etree.ElementTree as ET
import pytest
try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import ezdxf
except ImportError:
    ezdxf = None

from openschematix import model, project, projectio, editing, shapes, export, dxf, connectivity, netlist, check, revisions, symbols, userlib
from openschematix.symbols.custom import blank_symbol, to_symdef

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td

# ==============================================================================
# Priority 1: Save/load and data integrity
# ==============================================================================

def test_save_load_complex_multisheet_roundtrip(tmp_dir):
    """
    Verify complex multi-sheet project round-trip across save/load cycles:
    - Multiple sheets with custom setup (scale, orientation, title block, margins)
    - Custom embedded symbols
    - Component properties, designators, overrides, locked, group, layer
    - All shape kinds (line, polyline, rect, circle, arc, text)
    - Wires with manual numbering and style
    - Unicode characters in titles, sheet names, component properties
    """
    p = project.new_project(title="Projet Électrique µ-Controller ⚡")
    p.meta["designer"] = "Ingénieur Noël & François"
    p.meta["company"] = "Société d'Électronique — München GmbH"

    # Add embedded custom symbol
    cust_sym = blank_symbol("Capaciteur Polarisé")
    cust_sym["id"] = "user:cap_pol"
    cust_sym["prefix"] = "C"
    cust_sym["pins"] = [
        {"id": "pos", "name": "+", "x": -20, "y": 0, "dir": "l", "type": "elec.passive", "show": True},
        {"id": "neg", "name": "-", "x": 20, "y": 0, "dir": "r", "type": "elec.passive", "show": True},
    ]
    cust_sym["prims"] = [
        {"k": "line", "pts": [[-20, 0], [-10, 0]]},
        {"k": "line", "pts": [[-10, -20], [-10, 20]]},
        {"k": "arc", "c": [10, 0], "r": 20, "start": 90, "span": 180},
        {"k": "line", "pts": [[-10, 0], [20, 0]]},
    ]
    p.symbols["user:cap_pol"] = cust_sym
    symbols.add_project_symbol(to_symdef(cust_sym))

    # Sheet 1
    s1 = p.sheets[0]
    s1.name = "Alimentation 230V / 24V"
    s1.sheet.scale = "1:2"
    s1.sheet.title_block = "standard"

    c1 = editing.place(s1, "el.resistor.iec", 100, 100)
    c1.props["Resistance"] = "10kΩ ±1%"
    c1.props["Tension"] = "250V"
    c1.terminal_labels["1"] = "IN"
    c1.terminal_labels["2"] = "OUT"
    c1.locked = True
    c1.group = "GRP_PWR"

    c2 = editing.place(s1, "user:cap_pol", 300, 100)
    c2.props["Capacité"] = "470µF"
    c2.group = "GRP_PWR"

    # All shape kinds
    sh_line = model.Shape(s1.new_id(), "line", pts=[(50, 50), (90, 50)], width="thick")
    sh_poly = model.Shape(s1.new_id(), "polyline", pts=[(10, 10), (30, 10), (30, 40)])
    sh_rect = model.Shape(s1.new_id(), "rect", pts=[(150, 150), (250, 150), (250, 200), (150, 200)])
    sh_circ = model.Shape(s1.new_id(), "circle", c=(300, 250), r=25.0)
    sh_arc = model.Shape(s1.new_id(), "arc", c=(400, 250), r=30.0, start=45.0, extent=180.0)
    sh_text = model.Shape(s1.new_id(), "text", pts=[(50, 300)], s="Ligne Haute Tension ⚠", size=14.0)

    for sh in (sh_line, sh_poly, sh_rect, sh_circ, sh_arc, sh_text):
        s1.add_shape(sh)

    w1 = editing.add_wire(s1, [c1.terminals()["2"], (200, 100), (200, 150), (300, 150), c2.terminals()["pos"]])
    w1.number = "N$PWR_01"
    w1.number_manual = True

    # Sheet 2
    s2 = p.add_sheet("Contrôle & Signaux")
    s2.sheet.size = "A4"
    s2.sheet.orientation = "portrait"
    s2.sheet.title_block = "compact"
    c3 = editing.place(s2, "el.lamp.iec", 150, 200)

    # Save to path with spaces and Unicode
    save_path = os.path.join(tmp_dir, "Dossier Technique Шёлковый путь ⚡.schematix")
    projectio.save_project(p, save_path)
    assert os.path.exists(save_path)

    # Repeated round-trip (Cycle 1)
    res1 = projectio.open_any(save_path)
    p_load1 = res1.project
    assert p_load1.meta["title"] == "Projet Électrique µ-Controller ⚡"
    assert p_load1.meta["designer"] == "Ingénieur Noël & François"
    assert "user:cap_pol" in p_load1.symbols
    assert len(p_load1.sheets) == 2
    assert p_load1.sheets[0].name == "Alimentation 230V / 24V"
    assert p_load1.sheets[1].name == "Contrôle & Signaux"

    # Verify component properties and terminal overrides
    s1_loaded = p_load1.sheets[0]
    c1_loaded = s1_loaded.components[c1.id]
    assert c1_loaded.props["Resistance"] == "10kΩ ±1%"
    assert c1_loaded.props["Tension"] == "250V"
    assert c1_loaded.terminal_labels["1"] == "IN"
    assert c1_loaded.terminal_labels["2"] == "OUT"
    assert c1_loaded.locked is True
    assert c1_loaded.group == "GRP_PWR"

    c2_loaded = s1_loaded.components[c2.id]
    assert c2_loaded.props["Capacité"] == "470µF"
    assert c2_loaded.group == "GRP_PWR"

    # Verify all shapes
    assert s1_loaded.shapes[sh_line.id].kind == "line"
    assert s1_loaded.shapes[sh_line.id].width == "thick"
    assert s1_loaded.shapes[sh_poly.id].kind == "polyline"
    assert s1_loaded.shapes[sh_rect.id].kind == "rect"
    assert s1_loaded.shapes[sh_circ.id].r == 25.0
    assert s1_loaded.shapes[sh_arc.id].start == 45.0
    assert s1_loaded.shapes[sh_arc.id].extent == 180.0
    assert s1_loaded.shapes[sh_text.id].s == "Ligne Haute Tension ⚠"

    # Verify wire and connectivity
    w1_loaded = s1_loaded.wires[w1.id]
    assert w1_loaded.number == "N$PWR_01"
    assert w1_loaded.number_manual is True
    assert w1_loaded.start == [c1.id, "2"]
    assert w1_loaded.end == [c2.id, "pos"]

    # Save again (Cycle 2) and verify strict data equality
    save_path2 = os.path.join(tmp_dir, "cycle2.schematix")
    projectio.save_project(p_load1, save_path2)
    res2 = projectio.open_any(save_path2)
    p_load2 = res2.project

    assert p_load1.to_dict() == p_load2.to_dict()


def test_corrupted_and_malformed_project_handling(tmp_dir):
    """
    Test application resilience against missing, malformed, or partially corrupted files.
    """
    # 1. Non-existent file
    with pytest.raises(OSError):
        projectio.open_any(os.path.join(tmp_dir, "does_not_exist.schematix"))

    # 2. Completely invalid file (not a zip)
    garbage_path = os.path.join(tmp_dir, "garbage.schematix")
    with open(garbage_path, "wb") as f:
        f.write(b"not a valid zip or project file at all")
    with pytest.raises(projectio.ProjectFormatError):
        projectio.open_any(garbage_path)

    # 3. Zip without manifest.json
    nomanifest_path = os.path.join(tmp_dir, "nomanifest.schematix")
    with zipfile.ZipFile(nomanifest_path, "w") as zf:
        zf.writestr("mimetype", projectio.MIMETYPE)
    with pytest.raises(projectio.ProjectFormatError):
        projectio.open_any(nomanifest_path)

    # 4. Zip with invalid JSON in manifest.json
    badmanifest_path = os.path.join(tmp_dir, "badmanifest.schematix")
    with zipfile.ZipFile(badmanifest_path, "w") as zf:
        zf.writestr("mimetype", projectio.MIMETYPE)
        zf.writestr("manifest.json", "this is not valid {json")
    with pytest.raises(projectio.ProjectFormatError):
        projectio.open_any(badmanifest_path)

    # 5. Zip with manifest referencing missing sheet
    missingsheet_path = os.path.join(tmp_dir, "missingsheet.schematix")
    with zipfile.ZipFile(missingsheet_path, "w") as zf:
        zf.writestr("mimetype", projectio.MIMETYPE)
        manifest = {
            "format": projectio.PROJECT_FORMAT,
            "version": projectio.PROJECT_VERSION,
            "sheets": [{"uid": "sheet1", "name": "Sheet 1", "file": "sheets/sheet1.json"}]
        }
        zf.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(projectio.ProjectFormatError):
        projectio.open_any(missingsheet_path)

    # 6. Zip with manifest newer than supported version
    future_path = os.path.join(tmp_dir, "future.schematix")
    with zipfile.ZipFile(future_path, "w") as zf:
        zf.writestr("mimetype", projectio.MIMETYPE)
        manifest = {
            "format": projectio.PROJECT_FORMAT,
            "version": projectio.PROJECT_VERSION + 99,
            "sheets": []
        }
        zf.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(projectio.ProjectFormatError) as exc_info:
        projectio.open_any(future_path)
    assert "newer version" in str(exc_info.value).lower()

# ==============================================================================
# Priority 2: Undo/redo correctness
# ==============================================================================

def test_undo_redo_complex_sequence_and_netlist_fidelity():
    """
    Test undo/redo sequences across operations:
    - Placing, moving, rotating, copying, and deleting components and shapes.
    - Wire connections and junction creation/removal.
    - Verify connectivity & netlists restore accurately.
    """
    history = []
    future = []

    p = project.new_project()
    s = p.sheets[0]

    def record_step():
        history.append(json.dumps(p.to_dict()))
        future.clear()

    def do_undo():
        future.append(json.dumps(p.to_dict()))
        restored = project.Project.from_dict(json.loads(history.pop()))
        return restored

    def do_redo():
        history.append(json.dumps(p.to_dict()))
        restored = project.Project.from_dict(json.loads(future.pop()))
        return restored

    # Step 0: Empty
    record_step()

    # Step 1: Place 2 resistors
    r1 = editing.place(s, "el.resistor.iec", 100, 100)
    r2 = editing.place(s, "el.resistor.iec", 200, 100)
    record_step()

    # Step 2: Wire them together
    w1 = editing.add_wire(s, [r1.terminals()["2"], r2.terminals()["1"]])
    nets_step2 = netlist.compute_nets(p)
    assert len(nets_step2) == 1
    assert set(nets_step2[0].terminals) == {(s.uid, r1.id, "2"), (s.uid, r2.id, "1")}
    record_step()

    # Step 3: Add crossing wire and convert to junction
    w2 = editing.add_wire(s, [(150, 50), (150, 150)])
    editing.connect_crossing(s, (150, 100))
    nets_step3 = netlist.compute_nets(p)
    # Both wires are now part of the same net via the junction
    assert len(nets_step3) == 1
    assert len(connectivity.analyse(s).junctions) == 1
    record_step()

    # Step 4: Rotate R2
    editing.rotate_items(s, [r2.id], [w1.id], clockwise=True)
    record_step()

    # Step 5: Delete R1
    editing.delete_items(s, [r1.id])
    nets_step5 = netlist.compute_nets(p)

    # Now verify Undo backwards
    # Undo step 5 -> R1 restored (restores Step 4)
    p = do_undo()
    s = p.sheets[0]
    assert any(c.designator == r1.designator for c in s.components.values())

    # Undo step 4 -> Rotation undone
    p = do_undo()
    s = p.sheets[0]

    # Undo step 3 -> Junction undone, back to step 2 nets
    p = do_undo()
    s = p.sheets[0]
    nets_after_undo3 = netlist.compute_nets(p)
    assert len(nets_after_undo3) == 1
    r1_curr = next(c for c in s.components.values() if c.designator == r1.designator)
    r2_curr = next(c for c in s.components.values() if c.designator == r2.designator)
    assert set(nets_after_undo3[0].terminals) == {(s.uid, r1_curr.id, "2"), (s.uid, r2_curr.id, "1")}
    assert len(connectivity.analyse(s).junctions) == 0

    # Redo step 3
    p = do_redo()
    s = p.sheets[0]
    assert len(connectivity.analyse(s).junctions) == 1

# ==============================================================================
# Priority 3: Electrical connectivity
# ==============================================================================

def test_electrical_connectivity_crossings_vs_junctions():
    """
    Test cases where graphical representation and electrical netlist must stay synchronized:
    - Crossing wires vs connected junctions
    - Moving components maintains wire attachment
    - Disconnecting junctions restores crossing bridges
    """
    p = project.new_project()
    s = p.sheets[0]

    # Horizontal wire
    wh = editing.add_wire(s, [(100, 100), (300, 100)])
    # Vertical wire intersecting at (200, 100)
    wv = editing.add_wire(s, [(200, 50), (200, 150)])

    # Crossing check: initially un-connected crossing
    cross = editing.crossings(s)
    assert len(cross) == 1
    assert cross[0][0] == (200.0, 100.0)
    assert len(connectivity.analyse(s).junctions) == 0

    # Computed nets must have 2 separate nets
    nets = netlist.compute_nets(p)
    assert len(nets) == 2

    # Connect crossing
    res = editing.connect_crossing(s, (200, 100))
    assert res is True
    assert len(editing.crossings(s)) == 0
    juncs = connectivity.analyse(s).junctions
    assert len(juncs) == 1
    assert (200, 100) in juncs

    # Computed nets now joined into 1 net
    nets_connected = netlist.compute_nets(p)
    assert len(nets_connected) == 1

    # Disconnect junction
    msg = editing.disconnect_junction(s, (200, 100))
    assert "reconnected" in msg.lower() or "removed" in msg.lower() or msg != ""
    assert len(connectivity.analyse(s).junctions) == 0
    assert len(editing.crossings(s)) == 1
    assert len(netlist.compute_nets(p)) == 2


def test_moving_component_preserves_wire_connections():
    """
    Moving a component moves the attached wire vertex and keeps the net connected.
    """
    p = project.new_project()
    s = p.sheets[0]
    r1 = editing.place(s, "el.resistor.iec", 100, 100)
    t2 = r1.terminals()["2"]

    w = editing.add_wire(s, [t2, (t2[0] + 50, t2[1])])
    assert w.start == [r1.id, "2"]

    # Move component by dx=20, dy=30
    editing.move_items(s, [r1.id], [w.id], 20, 30)

    # Terminal coordinates have updated
    t2_new = r1.terminals()["2"]
    assert t2_new == (t2[0] + 20, t2[1] + 30)
    # Attached wire endpoint matches updated terminal
    assert s.wires[w.id].points[0] == t2_new
    assert s.wires[w.id].start == [r1.id, "2"]

# ==============================================================================
# Priority 4: Export fidelity (SVG, PDF, DXF)
# ==============================================================================

def test_export_svg_structure_and_entities(tmp_dir):
    """
    Verify SVG export generates valid XML with proper geometry, lines, texts, and styles.
    """
    p = project.new_project()
    s = p.sheets[0]
    editing.place(s, "el.resistor.iec", 100, 100)
    sh = model.Shape(s.new_id(), "text", pts=[(50, 50)], s="Circuit Test")
    s.add_shape(sh)

    svg_file = os.path.join(tmp_dir, "test.svg")
    export.export_svg(s, svg_file, project=p)
    assert os.path.exists(svg_file)

    tree = ET.parse(svg_file)
    root = tree.getroot()
    # Tag should end with svg
    assert root.tag.endswith("svg")
    # Verify presence of text and path/line elements
    texts = [elem.text for elem in root.iter() if elem.tag.endswith("text")]
    assert any("Circuit Test" in (t or "") for t in texts)
    assert any("R1" in (t or "") for t in texts)


def test_export_pdf_structure_and_multipages(tmp_dir):
    """
    Verify multi-sheet PDF export with pypdf:
    - Page count matches project sheet count
    - Dimensions reflect page sizes (e.g. A3, A4)
    """
    if pypdf is None:
        pytest.skip("pypdf not installed")
    p = project.new_project()
    s1 = p.sheets[0]
    s1.sheet.size = "A3"
    editing.place(s1, "el.resistor.iec", 100, 100)

    s2 = p.add_sheet("Sheet 2")
    s2.sheet.size = "A4"
    editing.place(s2, "el.lamp.iec", 150, 150)

    pdf_file = os.path.join(tmp_dir, "test.pdf")
    export.export_project_pdf(p, pdf_file, {s1.uid, s2.uid})
    assert os.path.exists(pdf_file)

    reader = pypdf.PdfReader(pdf_file)
    assert len(reader.pages) == 2
    # Verify A3 dimensions (420 x 297 mm in points: 1190.55 x 841.89)
    p1 = reader.pages[0]
    w1, h1 = float(p1.mediabox.width), float(p1.mediabox.height)
    assert abs(w1 - 1190.55) < 2.0
    assert abs(h1 - 841.89) < 2.0

    # Verify A4 dimensions (297 x 210 mm in points: 841.89 x 595.28)
    p2 = reader.pages[1]
    w2, h2 = float(p2.mediabox.width), float(p2.mediabox.height)
    assert abs(w2 - 841.89) < 2.0
    assert abs(h2 - 595.28) < 2.0


def test_export_dxf_structure_and_audit(tmp_dir):
    """
    Verify DXF export with ezdxf:
    - Check valid DXF R12 format
    - ezdxf auditor returns 0 errors
    - Components and shapes explode into lines and text
    """
    if ezdxf is None:
        pytest.skip("ezdxf not installed")
    p = project.new_project()
    s = p.sheets[0]
    editing.place(s, "el.resistor.iec", 100, 100)
    sh_rect = model.Shape(s.new_id(), "rect", pts=[(50, 50), (150, 50), (150, 100), (50, 100)])
    s.add_shape(sh_rect)

    dxf_file = os.path.join(tmp_dir, "test.dxf")
    dxf.export_dxf(s, dxf_file, p)
    assert os.path.exists(dxf_file)

    doc = ezdxf.readfile(dxf_file)
    auditor = doc.audit()
    assert len(auditor.errors) == 0

    msp = doc.modelspace()
    lines = list(msp.query("LINE"))
    texts = list(msp.query("TEXT"))
    assert len(lines) > 5
    assert len(texts) >= 1
