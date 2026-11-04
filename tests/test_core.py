"""Unit tests for the non-GUI core (symbols, model, editing, file I/O, export)."""
import itertools
import json
import os
import xml.etree.ElementTree as ET

import pytest

from openschematix import FILE_SCHEMA, editing, export, fileio, symbols
from openschematix.connectivity import analyse
from openschematix.geometry import GRID, is_orthogonal, same, simplify_orthogonal, xform
from openschematix.model import Component, Document, Wire
from openschematix.settings import Settings
from openschematix.symbols import validate_geometry
from openschematix.symbols.base import is_drafting_element
from openschematix.symbols.fluid import OPERATORS, PATTERNS, VALVE_TYPES, default_valve_params


# ---------------------------------------------------------------- symbols
def test_symbol_ids_unique_and_present():
    ids = [s.id for s in symbols.all_symbols()]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 70


@pytest.mark.parametrize("sym", symbols.all_symbols(), ids=lambda s: s.id)
def test_symbol_geometry_valid(sym):
    g = sym.build(sym.default_params)
    assert validate_geometry(g) == []
    if not is_drafting_element(sym):
        assert g.terminals, "every symbol needs at least one terminal (drafting elements excepted)"
    assert sym.convention and sym.description and sym.category


@pytest.mark.parametrize("sym", symbols.all_symbols(), ids=lambda s: s.id)
def test_transforms_keep_terminals_on_grid_and_distinct(sym):
    for rot, mir in itertools.product((0, 90, 180, 270), (False, True)):
        c = Component(1, sym.id, 100, 200, rot, mir, params=sym.default_params)
        t = c.terminals()
        assert len(t) == len(sym.build(sym.default_params).terminals)
        for x, y in t.values():
            assert x % GRID == 0 and y % GRID == 0, (rot, mir, x, y)
        assert len({(round(x, 3), round(y, 3)) for x, y in t.values()}) == len(t)


def test_rotation_and_mirror_identities():
    for x, y in ((10, 0), (20, -30), (-7, 5)):
        p = (x, y)
        q = p
        for _ in range(4):
            q = xform(*q, 90)
        assert same(q, p)
        assert same(xform(*xform(x, y, 0, True), 0, True), p)


def test_mirror_reflects_terminals_in_world_x():
    doc = Document()
    c = editing.place(doc, "el.potentiometer.iec", 100, 100, rotation=90)
    before = c.terminals()
    editing.mirror_items(doc, [c.id], [])
    after = c.terminals()
    for name, (x, y) in before.items():
        assert same(after[name], (2 * 100 - x, y))


@pytest.mark.parametrize("medium", ["hyd", "pneu"])
def test_every_valve_configuration_builds(medium):
    sid = f"fl.{medium}.dcv"
    ops = [[]] + [[o] for o in OPERATORS] + [["spring", "solenoid"], ["spring", "pilot"]]
    for vt, (nports, npos) in VALVE_TYPES[medium].items():
        for pat in PATTERNS[nports]:
            for left in ops:
                p = default_valve_params(medium, vt)
                p["positions"] = [pat] * npos
                p["left"], p["right"] = left, ["spring"]
                g = symbols.geometry(sid, p)
                assert validate_geometry(g) == [], (vt, pat, left)
                names = {t.name for t in g.terminals}
                assert len([n for n in names if not n[0] in "XY" and not n in ("10", "12", "14") and "." not in n]) == nports


def test_valve_rejects_bad_params_gracefully():
    g = symbols.geometry("fl.hyd.dcv", {"type": "9/9", "positions": ["nonsense"], "left": ["rocket"]})
    assert validate_geometry(g) == []


def test_unknown_symbol_uses_placeholder():
    c = Component(1, "does.not.exist", 0, 0)
    assert c.terminals()


def test_search():
    assert any(s.id == "fl.hyd.relief" for s in symbols.search("relief"))
    assert any(s.id == "el.resistor.ansi" for s in symbols.search("resistor ieee"))
    assert symbols.search("zzzz-not-a-symbol") == []


# ---------------------------------------------------------------- model & files
def _sample_doc():
    doc = Document()
    r = editing.place(doc, "el.resistor.iec", 100, 100)
    k = editing.place(doc, "el.coil.iec", 200, 100)
    v = editing.place(doc, "fl.hyd.dcv", 300, 300)
    r.label = "4k7 ± 5% (test)"
    a, b = r.terminals()["2"], k.terminals()["A1"]
    editing.add_wire(doc, [a, (b[0], a[1]), b])
    doc.sheet.title = "Test (sheet) é"
    return doc, r, k, v


def test_designators_auto_number():
    doc, r, k, v = _sample_doc()
    assert (r.designator, k.designator, v.designator) == ("R1", "K1", "V1")
    assert editing.place(doc, "el.resistor.ansi", 0, 0).designator == "R2"


def test_wire_auto_attaches_to_terminals():
    doc, r, k, _ = _sample_doc()
    w = next(iter(doc.wires.values()))
    assert w.start == [r.id, "2"] and w.end == [k.id, "A1"]


def test_save_load_roundtrip(tmp_path):
    doc, *_ = _sample_doc()
    p = tmp_path / "x.osch"
    fileio.save(doc, str(p))
    res = fileio.load(str(p))
    assert not res.migrated and res.warnings == []
    assert res.document.to_dict() == doc.to_dict()
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]


def test_load_rejects_bad_files(tmp_path):
    p = tmp_path / "bad.osch"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(fileio.FileFormatError):
        fileio.load(str(p))
    with pytest.raises(fileio.FileFormatError):
        fileio.load_data({"format": "Something else"})
    with pytest.raises(fileio.FileFormatError):
        fileio.load_data({"format": "OpenSchematix", "schema": FILE_SCHEMA + 1})
    with pytest.raises(fileio.FileFormatError):
        fileio.load_data({"format": "OpenSchematix", "schema": 1, "components": [{"id": 1}]})
    p.write_bytes(b"\xff\xfe\x00binary")
    with pytest.raises(fileio.FileFormatError):
        fileio.load(str(p))


def test_load_drops_dangling_wire_refs():
    d = {"format": "OpenSchematix", "schema": 1, "components": [],
         "wires": [{"id": 5, "points": [[0, 0], [10, 0]], "start": [99, "1"], "end": None}]}
    doc = fileio.load_data(d).document
    assert doc.wires[5].start is None and doc.next_id == 6


def test_rejects_unsupported_legacy_format():
    import pytest
    with pytest.raises(fileio.FileFormatError, match="Not an OpenSchematix file"):
        fileio.load_data({"format": "Unsupported legacy format", "components": [], "connections": []})


# ---------------------------------------------------------------- editing
def _assert_wires_consistent(doc):
    for w in doc.wires.values():
        assert is_orthogonal(w.points), w.points
        for ref, idx in ((w.start, 0), (w.end, -1)):
            if ref:
                assert same(doc.terminal_pos(ref), w.points[idx])


def test_move_rotate_mirror_keep_wires_attached():
    doc, r, k, v = _sample_doc()
    p, t = v.terminals()["P"], v.terminals()["A"]
    pump = editing.place(doc, "fl.hyd.pump", 200, 450)
    editing.add_wire(doc, [pump.terminals()["P"], (pump.terminals()["P"][0], p[1] + 30), (p[0], p[1] + 30), p])
    for op in range(12):
        if op % 3 == 0:
            editing.move_items(doc, [k.id, v.id], [], 30, -20)
        elif op % 3 == 1:
            editing.rotate_items(doc, [v.id], [], clockwise=op % 2 == 0)
        else:
            editing.mirror_items(doc, [k.id], [])
        _assert_wires_consistent(doc)


def test_group_rotation_moves_rigid_wires():
    doc, r, k, _ = _sample_doc()
    w = next(iter(doc.wires.values()))
    editing.rotate_items(doc, [r.id, k.id], [w.id])
    _assert_wires_consistent(doc)
    assert r.rotation == 90 and k.rotation == 90


def test_delete_detaches_wires():
    doc, r, k, _ = _sample_doc()
    editing.delete_items(doc, [k.id])
    w = next(iter(doc.wires.values()))
    assert w.end is None and w.start is not None


def test_copy_paste_new_ids_and_designators():
    doc, r, k, _ = _sample_doc()
    clip = editing.copy_items(doc, [r.id, k.id])
    assert len(clip["wires"]) == 1
    new = editing.paste(doc, clip, 40, 40)
    assert len(new) == 3
    des = [c.designator for c in doc.components.values()]
    assert len(des) == len(set(des))
    pasted_wire = doc.wires[new[-1]]
    assert pasted_wire.start[0] in new and pasted_wire.end[0] in new
    _assert_wires_consistent(doc)


def test_set_endpoint_and_drag_segment_stay_orthogonal():
    pts = [(0, 0), (50, 0), (50, 40), (100, 40)]
    for target in ((10, 10), (0, -30), (70, 0), (-20, 80)):
        out = editing.set_endpoint(pts, "start", target)
        assert is_orthogonal(out) and same(out[0], target) and same(out[-1], pts[-1])
    out, _ = editing.drag_segment(pts, 0, 20)
    out = simplify_orthogonal(out)
    assert same(out[0], pts[0]) and same(out[-1], pts[-1]) and is_orthogonal(out)


def test_router_follows_terminal_directions():
    pts = editing.route((0, 0), "u", (100, -100), "u")
    assert is_orthogonal(pts)
    assert pts[1][0] == 0 and pts[1][1] < 0          # leaves upward
    assert pts[-2][0] == 100 and pts[-2][1] < -100   # enters q from above


# ---------------------------------------------------------------- connectivity
def test_junctions_and_crossings():
    doc = Document()
    editing.add_wire(doc, [(0, 0), (100, 0)])
    editing.add_wire(doc, [(50, 0), (50, 50)])      # T-junction
    editing.add_wire(doc, [(80, -30), (80, 30)])    # crossing, no junction
    c = analyse(doc)
    assert [tuple(p) for p in c.junctions] == [(50.0, 0.0)]
    ends = {tuple(p) for _, p in c.open_wire_ends}
    assert (80.0, -30.0) in ends and (80.0, 30.0) in ends and (50.0, 50.0) in ends


def test_wire_over_terminal_is_not_a_connection():
    doc = Document()
    r = editing.place(doc, "el.resistor.iec", 100, 100)   # terminals at (80,100), (120,100)
    editing.add_wire(doc, [(60, 100), (140, 100)])         # passes over both terminals
    c = analyse(doc)
    assert {(cid, n) for cid, n, _ in c.open_terminals} == {(r.id, "1"), (r.id, "2")}
    assert c.junctions == []


# ---------------------------------------------------------------- export
def test_svg_export_is_valid_xml(tmp_path):
    doc, *_ = _sample_doc()
    p = tmp_path / "x.svg"
    export.export_svg(doc, str(p))
    root = ET.parse(p).getroot()
    assert root.tag.endswith("svg") and root.attrib["width"].endswith("mm")
    texts = [t.text for t in root.iter() if t.tag.endswith("text")]
    assert "R1" in texts and any("4k7" in (t or "") for t in texts)
    export.export_svg(doc, str(p), use_sheet=False)
    ET.parse(p)


def test_pdf_export_structure(tmp_path):
    doc, *_ = _sample_doc()
    data = export.to_pdf(doc)
    assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")
    xref = int(data.rsplit(b"startxref", 1)[1].split()[0])
    assert data[xref:xref + 4] == b"xref"
    try:
        import pypdf
    except ImportError:
        return
    p = tmp_path / "x.pdf"
    export.export_pdf(doc, str(p))
    rd = pypdf.PdfReader(str(p))
    text = rd.pages[0].extract_text()
    assert "R1" in text and "4k7" in text
    w_mm = float(rd.pages[0].mediabox.width) / 72 * 25.4
    assert abs(w_mm - 420) < 0.5   # A3 landscape


def test_export_empty_document():
    doc = Document()
    assert export.to_pdf(doc)
    assert export.to_svg(doc, use_sheet=False)


# ---------------------------------------------------------------- settings
def test_settings_corrupt_file(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("garbage", encoding="utf-8")
    s = Settings(str(p))
    assert s["theme"] == "modern_light"
    s["theme"] = "dark"   # an old theme name is migrated on load
    s.add_recent(str(tmp_path / "a.osch"))
    s.save()
    s2 = Settings(str(p))
    assert s2["theme"] == "modern_dark" and len(s2["recent_files"]) == 1
    p.write_text(json.dumps({"theme": 5, "show_grid": "yes"}), encoding="utf-8")
    s3 = Settings(str(p))
    assert s3["theme"] == "modern_light" and s3["show_grid"] is True
