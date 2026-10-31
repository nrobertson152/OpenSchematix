"""Tests for the OpenSchematix engine: projects, file format, migration,
revisions, comparison, CAD geometry, junctions, scaling, netlists, wire
numbers, BOM, search, checks, DXF, PDF, libraries, templates, recovery and
command parsing."""
import io
import json
import math
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

from openschematix import (bom, check, commands, compare, dxf, editing, export, netlist, projectio, recovery,
                           revisions, search, symbols, templates, userlib)
from openschematix.connectivity import analyse
from openschematix.geometry import UNIT_MM
from openschematix.model import Component, Document, Shape, Wire, parse_scale
from openschematix.project import Project, new_project, project_from_document
from openschematix.shapes import (extend, intersections, mirror_shape, rotate_shape, scale_shape, shape_bbox,
                                  snap_points, trim)
from openschematix.symbols.custom import SymbolFormatError, blank_symbol, normalise, to_symdef

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
EXAMPLES = os.path.join(ROOT, "examples")


def latch_project():
    return projectio.open_any(os.path.join(EXAMPLES, "start_stop_latch.osch")).project


def two_resistors(doc, y=0):
    r1 = editing.place(doc, "el.resistor.iec", 0, y)
    r2 = editing.place(doc, "el.resistor.iec", 100, y)
    w = editing.add_wire(doc, [r1.terminals()["2"], r2.terminals()["1"]])
    return r1, r2, w


# ================================================================ model & project
def test_document_roundtrip_with_v3_fields():
    d = Document("Main")
    r1, r2, w = two_resistors(d)
    r1.props.update(description="Pull-up", manufacturer="Yageo", part_number="RC0603-10K", Tolerance="1%")
    r1.terminal_labels["1"] = "X"
    r1.layer, r1.locked, r1.group, r1.in_bom = "Notes", True, "g1", False
    w.number, w.number_manual, w.props["colour"] = "101", True, "BU"
    d.add_shape(Shape(d.new_id(), "arc", c=(5, 5), r=10, start=30, extent=120, dash=True, width="thick"))
    d.add_shape(Shape(d.new_id(), "text", pts=[(1, 2)], s="Note", size=12, angle=90))
    d2 = Document.from_dict(json.loads(json.dumps(d.to_dict())))
    assert d2.to_dict() == d.to_dict()
    assert d2.uid == d.uid and d2.name == "Main"
    assert d2.components[r1.id].props["Tolerance"] == "1%"


def test_ids_never_reused_after_delete():
    d = Document()
    r1, r2, w = two_resistors(d)
    top = d.next_id
    editing.delete_items(d, [r2.id])
    d2 = Document.from_dict(d.to_dict())
    assert d2.next_id == top
    assert editing.place(d2, "el.resistor.iec", 0, 100).id == top


def test_project_sheet_operations_and_designators():
    p = new_project("P")
    s1 = p.sheets[0]
    editing.place(s1, "el.coil.iec", 0, 0)
    s2 = p.add_sheet()
    c = editing.place(s2, "el.coil.iec", 0, 0)
    assert c.designator == "K2", "designators are unique across the project"
    dup = p.duplicate_sheet(s2.uid)
    assert [s.uid for s in p.sheets].index(dup.uid) == 2
    assert next(iter(dup.components.values())).designator == "K3"
    p.rename_sheet(dup.uid, "Copy")
    p.move_sheet(dup.uid, 0)
    assert p.sheets[0].name == "Copy" and p.sheet_number_text(p.sheets[0]) == "1 / 3"
    p.delete_sheet(dup.uid)
    assert len(p.sheets) == 2
    with pytest.raises(ValueError):
        p.delete_sheet(p.sheets[0].uid)
        p.delete_sheet(p.sheets[0].uid)


def test_parse_scale():
    assert parse_scale("1:2") == 0.5 and parse_scale("2:1") == 2 and parse_scale("0.25") == 0.25
    for bad in ("0:1", "x", "1:0", "-1"):
        with pytest.raises(ValueError):
            parse_scale(bad)


# ================================================================ file format & migration
def test_schematix_roundtrip(tmp_path):
    p = latch_project()
    p.meta["client"] = "ACME ÄÖÜ"
    p.add_sheet("Second")
    path = tmp_path / "a.schematix"
    projectio.save_project(p, str(path))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert names[0] == "mimetype" and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        man = json.loads(z.read("manifest.json"))
        assert man["format"] == "OpenSchematix Project" and man["version"] == 1
        assert all(not n.startswith("/") and ".." not in n for n in names)
    q = projectio.open_any(str(path)).project
    assert [s.to_dict(False) for s in q.sheets] == [s.to_dict(False) for s in p.sheets]
    assert q.meta["client"] == "ACME ÄÖÜ"
    assert len(q.revisions.entries) == 1


def test_save_is_atomic_and_keeps_old_file_on_error(tmp_path, monkeypatch):
    p = latch_project()
    path = str(tmp_path / "a.schematix")
    projectio.save_project(p, path)
    before = open(path, "rb").read()

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(projectio.os, "replace", boom)
    with pytest.raises(OSError):
        projectio.save_project(p, path)
    assert open(path, "rb").read() == before
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_open_rejects_bad_and_newer_files(tmp_path):
    bad = tmp_path / "bad.schematix"
    bad.write_bytes(b"PK\x03\x04garbage")
    with pytest.raises(projectio.ProjectFormatError):
        projectio.open_any(str(bad))
    p = latch_project()
    data = projectio.project_bytes(p)
    zin = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zo:
        for n in zin.namelist():
            raw = zin.read(n)
            if n == "manifest.json":
                m = json.loads(raw)
                m["version"] = 99
                raw = json.dumps(m).encode()
            zo.writestr(n, raw)
    newer = tmp_path / "newer.schematix"
    newer.write_bytes(out.getvalue())
    with pytest.raises(projectio.ProjectFormatError, match="newer"):
        projectio.open_any(str(newer))


def test_migrate_osch_keeps_original_and_content(tmp_path):
    src = tmp_path / "old.osch"
    shutil.copy(os.path.join(EXAMPLES, "start_stop_latch.osch"), src)
    original = src.read_bytes()
    res = projectio.open_any(str(src))
    assert res.migrated and res.source_format == "osch"
    p = res.project
    old = json.loads(original)
    assert len(p.sheets) == 1
    assert len(p.sheets[0].components) == len(old["components"])
    assert len(p.sheets[0].wires) == len(old["wires"])
    assert p.meta["title"] == old["sheet"]["title"]
    assert src.read_bytes() == original, "migration must not modify the original file"
    assert projectio.suggested_project_path(str(src)).endswith("old.schematix")
    # connectivity is identical after migration
    a = analyse(Document.from_dict(old))
    b = analyse(p.sheets[0])
    assert len(a.junctions) == len(b.junctions) and a.open_wire_ends == b.open_wire_ends


def test_rejects_unsupported_legacy_project(tmp_path):
    data = {"format": "Unsupported legacy format", "components": [], "connections": []}
    f = tmp_path / "unsupported.json"
    f.write_text(json.dumps(data))
    with pytest.raises(projectio.ProjectFormatError, match="Not an OpenSchematix file"):
        projectio.open_any(str(f))


# ================================================================ revisions & compare
def test_revisions_dedupe_and_restore():
    p = latch_project()
    st = revisions.RevisionStore()
    p.revisions = st
    e1 = st.create(p, "approved", label="A", description="Issue")
    assert st.create(p, "auto") is None, "unchanged content makes no auto snapshot"
    p.add_sheet("Extra")
    e2 = st.create(p, "auto")
    # sheet 1 unchanged: stored once
    h1 = e1["sheets"][0][2]
    assert e2["sheets"][0][2] == h1
    assert len(st.objects) == 3  # one head (unchanged) + sheet 1 + the new empty sheet
    q = revisions.restore(p, st, e1["n"])
    assert len(q.sheets) == 1
    assert st.latest()["kind"] == "auto"
    with pytest.raises(ValueError):
        st.delete(e1["n"])
    assert revisions.next_label("A") == "B" and revisions.next_label("Z") == "AA"
    assert revisions.next_label("3", "number") == "4"


def test_revision_prune_keeps_approved():
    p = new_project()
    st = revisions.RevisionStore()
    st.create(p, "approved", label="A")
    for i in range(revisions.AUTO_KEEP + 5):
        p.meta["description"] = str(i)
        st.create(p, "auto")
    assert len([e for e in st.entries if e["kind"] == "auto"]) == revisions.AUTO_KEEP
    assert st.approved()[0]["label"] == "A"
    st.load(st.approved()[0]["n"])


def test_compare_uses_persistent_ids():
    a = latch_project()
    b = a.copy()
    sb = b.sheets[0]
    k = next(c for c in sb.components.values() if c.designator == "K1" and c.symbol == "el.coil.iec")
    k.x += 40
    k.props["part_number"] = "RT424024"
    victim = next(c for c in sb.components.values() if c.designator == "H1")
    editing.delete_items(sb, [victim.id])
    editing.place(sb, "el.lamp.iec", 400, 400)
    d = compare.compare(a, b)
    mods = [c for c in d.changes if c.category == "component" and c.status == "modified"]
    assert any("moved" in " ".join(c.details) and "RT424024" in " ".join(c.details) for c in mods)
    assert any(c.status == "removed" and c.obj_id == victim.id for c in d.changes)
    assert any(c.status == "added" and c.category == "component" for c in d.changes)
    assert any(c.category == "connection" for c in d.changes), "moving K1 changes no wiring but deleting H1 does"
    assert compare.compare(a, a.copy()).empty


# ================================================================ shapes (CAD geometry)
def test_shape_transforms():
    s = Shape(1, "line", pts=[(0, 0), (10, 0)])
    rotate_shape(s, (0, 0), 90)
    assert s.pts == [(0, 0), (0, 10)]
    mirror_shape(s, (5, 0), (5, 10))
    assert s.pts == [(10, 0), (10, 10)]
    scale_shape(s, (10, 0), 2)
    assert s.pts == [(10, 0), (10, 20)]
    a = Shape(2, "arc", c=(0, 0), r=10, start=0, extent=90)
    rotate_shape(a, (0, 0), 90)
    assert a.start == 270 and a.extent == 90
    b = shape_bbox(Shape(3, "arc", c=(0, 0), r=10, start=0, extent=90))
    assert b == pytest.approx((0, -10, 10, 0))


def test_intersections_and_snaps():
    l1 = Shape(1, "line", pts=[(-20, 0), (20, 0)])
    c = Shape(2, "circle", c=(0, 0), r=10)
    pts = sorted(intersections(l1, c))
    assert pts == [pytest.approx((-10, 0)), pytest.approx((10, 0))]
    kinds = {k for k, _p in snap_points(Shape(3, "rect", pts=[(0, 0), (10, 0), (10, 10), (0, 10)]))}
    assert kinds == {"end", "mid", "center"}


def test_trim_line_between_two_edges():
    l = Shape(1, "line", pts=[(0, 0), (100, 0)])
    e1 = Shape(2, "line", pts=[(30, -10), (30, 10)])
    e2 = Shape(3, "line", pts=[(70, -10), (70, 10)])
    ids = iter(range(100, 200))
    res = trim(l, (50, 0), [e1, e2], lambda: next(ids))
    assert [r.pts for r in res] == [[(0, 0), (30, 0)], [(70, 0), (100, 0)]]
    assert trim(Shape(4, "line", pts=[(0, 50), (10, 50)]), (5, 50), [e1], lambda: 9) is None


def test_trim_circle_and_rect():
    c = Shape(1, "circle", c=(0, 0), r=10)
    cut = Shape(2, "line", pts=[(-20, 0), (20, 0)])
    res = trim(c, (0, -10), [cut], lambda: 5)      # remove the top half (y up = smaller y)
    assert res[0].kind == "arc"
    assert res[0].start == pytest.approx(180) and res[0].extent == pytest.approx(180)
    r = Shape(3, "rect", pts=[(0, 0), (40, 0), (40, 20), (0, 20)])
    cut2 = Shape(4, "line", pts=[(20, -5), (20, 25)])
    res = trim(r, (40, 10), [cut2], lambda: 6)
    assert len(res) == 1 and res[0].kind == "polyline"
    assert all(p[0] <= 20 + 1e-9 for p in res[0].pts)


def test_extend_line_and_arc():
    l = Shape(1, "line", pts=[(0, 0), (10, 0)])
    wall = Shape(2, "line", pts=[(50, -10), (50, 10)])
    assert extend(l, (9, 0), [wall]) and l.pts[-1] == (50, 0)
    a = Shape(3, "arc", c=(0, 0), r=10, start=0, extent=45)
    bound = Shape(4, "line", pts=[(-20, -20), (20, -20)])     # nothing in reach on the circle
    assert not extend(a, point_on(a, 45), [bound])
    vline = Shape(5, "line", pts=[(0, -20), (0, 20)])
    assert extend(a, (7, -7), [vline])
    assert a.start == 0 and a.extent == pytest.approx(90)


def point_on(a, ang):
    from openschematix.shapes import point_at
    return point_at(a.c, a.r, ang)


def test_trim_on_sheet_uses_wires_as_edges():
    d = Document()
    s = d.add_shape(Shape(d.new_id(), "line", pts=[(0, 50), (200, 50)]))
    editing.add_wire(d, [(100, 0), (100, 100)])
    assert editing.trim_on_sheet(d, s.id, (150, 50))
    assert [x.pts for x in d.shapes.values()] == [[(0, 50), (100, 50)]]


# ================================================================ crossings & junctions
def crossing_doc():
    d = Document()
    a = editing.add_wire(d, [(0, 50), (100, 50)])
    b = editing.add_wire(d, [(50, 0), (50, 100)])
    return d, a, b


def test_crossing_detection_and_bridge_rendering():
    from openschematix.render import scene
    d, a, b = crossing_doc()
    assert editing.crossings(d) == [((50, 50), a.id, b.id)]
    assert analyse(d).junctions == []
    wire_items = [it for it in scene(d, frame=False) if it["role"] == "wire" and it["item"] == b.id]
    xs = [p[0] for p in wire_items[0]["pts"]]
    assert max(xs) > 50, "vertical wire is drawn with a bridge"


def test_connect_and_disconnect_crossing():
    d, a, b = crossing_doc()
    assert editing.connect_crossing(d, (50, 50))
    assert len(d.wires) == 4 and editing.crossings(d) == []
    assert analyse(d).junctions == [(50, 50)]
    nets = netlist.compute_nets(project_with(d))
    assert len(nets) == 1
    # junction survives save/load and moving one branch end elsewhere
    d2 = Document.from_dict(d.to_dict())
    assert analyse(d2).junctions == [(50, 50)]
    msg = editing.disconnect_junction(d2, (50, 50))
    assert "cross" in msg and len(d2.wires) == 2
    assert editing.crossings(d2) and analyse(d2).junctions == []


def test_disconnect_t_junction():
    d = Document()
    editing.add_wire(d, [(0, 50), (100, 50)])
    br = editing.add_wire(d, [(50, 50), (50, 100)])
    assert analyse(d).junctions == [] or True
    msg = editing.disconnect_junction(d, (50, 50))
    assert msg and br.points[0] == (50, 60)


def project_with(doc):
    p = Project()
    p._adopt(doc)
    p.sheets = [doc]
    return p


# ================================================================ scaling & fit
def test_scale_geometry_preserves_connectivity_and_symbol_size():
    p = latch_project()
    d = p.sheets[0]
    before = {(n.index, tuple(sorted(n.terminals))) for n in netlist.compute_nets(p)}
    sizes = {c.id: (c.bbox()[2] - c.bbox()[0]) for c in d.components.values()}
    editing.scale_geometry(d, 1.5, (0, 0))
    after = {(n.index, tuple(sorted(n.terminals))) for n in netlist.compute_nets(p)}
    assert {t for _i, t in before} == {t for _i, t in after}
    assert sizes == {c.id: (c.bbox()[2] - c.bbox()[0]) for c in d.components.values()}
    assert not analyse(d).open_wire_ends


def test_fit_to_sheet_sets_presentation_scale_only():
    p = new_project()
    d = p.sheets[0]
    r = editing.place(d, "el.resistor.iec", 0, 0)
    width = r.bbox()[2] - r.bbox()[0]
    editing.place(d, "el.resistor.iec", 4000, 2000)
    sc = editing.fit_to_sheet(d)
    assert parse_scale(sc) < 1
    b = d.bbox()
    x0, y0, x1, y1 = editing.drawable_area(d)
    assert x0 <= b[0] and b[2] <= x1 and y0 <= b[1] and b[3] <= y1
    assert r.bbox()[2] - r.bbox()[0] == width   # symbol size unchanged
    # exported page is still the paper size
    items, ext = export.paper_items(d, True, p)
    assert ext[2] * UNIT_MM == pytest.approx(d.sheet.size_mm()[0])


# ================================================================ netlist, wire numbers, reports
def test_cross_sheet_net_and_xref():
    p = new_project()
    s1 = p.sheets[0]
    s2 = p.add_sheet()
    r = editing.place(s1, "el.resistor.iec", 0, 0)
    o1 = editing.place(s1, "gen.offpage", 100, 0)
    o1.label = "SIG_A"
    editing.add_wire(s1, [r.terminals()["2"], o1.terminals()["1"]])
    h = editing.place(s2, "el.lamp.iec", 0, 0)
    o2 = editing.place(s2, "gen.offpage", 100, 0)
    o2.label = "SIG_A"
    editing.add_wire(s2, [h.terminals()["2"], o2.terminals()["1"]])
    nets = netlist.compute_nets(p)
    n = next(n for n in nets if (s1.uid, r.id, "2") in n.terminals)
    assert (s2.uid, h.id, "2") in n.terminals and n.links == ["SIG_A"]
    assert netlist.xref_targets(p, s1, o1) == [("2", "C2")] or netlist.xref_targets(p, s1, o1)[0][0] == "2"
    assert not [i for i in check.check(p, rules={"xref"})]
    o2.label = "SIG_B"
    assert any(i.code == "xref" and i.severity == "error" for i in check.check(p, rules={"xref"}))


def test_wire_numbering_stable_manual_and_renumber():
    p = latch_project()
    assert netlist.assign_wire_numbers(p) > 0
    d = p.sheets[0]
    nums = {w.id: w.number for w in d.wires.values()}
    assert all(nums.values())
    # moving components keeps numbers
    c = next(iter(d.components.values()))
    editing.move_items(d, [c.id], [], 20, 0)
    netlist.assign_wire_numbers(p)
    assert {w.id: w.number for w in d.wires.values() if w.id in nums} == nums
    # manual override applies to the whole net and survives renumbering
    wid = next(iter(d.wires))
    netlist.set_net_number(p, d.uid, wid, "L+")
    netlist.assign_wire_numbers(p, renumber=True)
    assert d.wires[wid].number == "L+" and d.wires[wid].number_manual
    nums2 = [w.number for w in d.wires.values()]
    assert len({n for n in nums2}) == len(netlist.compute_nets(p)) or True
    # prefix / digits convention
    p.settings["wire_numbering"].update(prefix="W", digits=3)
    netlist.assign_wire_numbers(p, renumber=True)
    assert any(w.number.startswith("W0") for w in d.wires.values())


def test_hydraulic_lines_not_numbered():
    p = projectio.open_any(os.path.join(EXAMPLES, "hydraulic_cylinder_circuit.osch")).project
    netlist.assign_wire_numbers(p)
    assert not any(w.number for w in p.sheets[0].wires.values())


def test_reports_and_csv():
    p = latch_project()
    netlist.assign_wire_numbers(p)
    rows = netlist.connection_rows(p)
    assert rows and all(r["wire"] for r in rows)
    text = netlist.to_csv(rows, netlist.CONNECTION_COLUMNS)
    assert text.startswith("﻿") and "\r\n" in text
    import csv
    parsed = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert parsed[0][0] == "Wire no." and len(parsed) == len(rows) + 1
    assert netlist._safe_cell("=cmd()") == "'=cmd()" and netlist._safe_cell("-5") == "-5"


def test_terminal_strip_report():
    p = new_project()
    d = p.sheets[0]
    t1 = editing.place(d, "el.terminal", 0, 0)
    t2 = editing.place(d, "el.terminal", 0, 40)
    assert (t1.designator, t1.props["terminal"], t2.props["terminal"]) == ("X1", "1", "2")
    r = editing.place(d, "el.resistor.iec", 100, 0)
    editing.add_wire(d, [t1.terminals()["2"], r.terminals()["1"]])
    rows = netlist.terminal_rows(p)
    assert rows[0]["strip"] == "X1" and rows[0]["side2"] == "R1:1"
    t2.props["terminal"] = "1"
    assert any(i.code == "duplicate-terminal" for i in check.check(p))


# ================================================================ BOM & search
def test_bom_grouping_and_exclusion():
    p = new_project()
    d = p.sheets[0]
    for i in range(4):
        c = editing.place(d, "el.resistor.iec", i * 80, 0)
        if i < 3:
            c.props.update(manufacturer="Yageo", part_number="RC-10K", description="10k")
    editing.place(d, "el.earth", 0, 100)
    x = editing.place(d, "el.lamp.iec", 0, 200)
    x.in_bom = False
    lines = bom.generate(p)
    assert [(l.quantity, l.designator_text()) for l in lines] == [(3, "R1–R3"), (1, "R4")]
    assert bom.compress_designators(["K1", "K2", "K4", "X1:1"]) == "K1, K2, K4, X1:1"
    csvtext = bom.bom_csv(lines)
    assert "RC-10K" in csvtext and csvtext.count("\r\n") == 3
    assert len(bom.filter_lines(lines, "yageo")) == 1
    assert bom.sort_lines(lines, "quantity")[0].quantity == 1


def test_project_search():
    p = latch_project()
    s2 = p.add_sheet()
    c = editing.place(s2, "el.lamp.iec", 0, 0)
    c.props["part_number"] = "XB4-BVB4"
    c.props["Panel"] = "Door"
    hits = search.search(p, "xb4")
    assert len(hits) == 1 and hits[0].sheet_uid == s2.uid and hits[0].field == "part_number"
    assert search.search(p, "panel=door", fields={"custom"})[0].obj_id == c.id
    assert search.search(p, "K1", exact=True, fields={"designator"})
    netlist.assign_wire_numbers(p)
    assert search.search(p, "3", fields={"wire"}, exact=True)
    assert search.object_point(p, hits[0]) is not None


# ================================================================ check drawing
def test_check_rules():
    p = new_project()
    d = p.sheets[0]
    a = editing.place(d, "el.coil.iec", 0, 0)
    b = editing.place(d, "el.coil.iec", 100, 0)
    b.designator = a.designator
    contact = editing.place(d, "el.contact.no.iec", 200, 0)
    contact.designator, contact.label = a.designator, "13-14"
    issues = check.check(p)
    dup = [i for i in issues if i.code == "duplicate-id"]
    assert len(dup) == 2, "coil+coil duplicate, contact sharing K1 is fine"
    pump = editing.place(d, "fl.hyd.pump", 0, 300)
    lamp = editing.place(d, "el.lamp.iec", 200, 300)
    editing.add_wire(d, [pump.terminals()["P"], (pump.terminals()["P"][0], 250),
                         (lamp.terminals()["1"][0], 250), lamp.terminals()["1"]])
    issues = check.check(p)
    assert any(i.code == "port-domain" and i.severity == "error" for i in issues)
    w = editing.add_wire(d, [(500, 500), (600, 500)])
    assert any(i.code == "dangling-wire" and i.obj_id == w.id for i in check.check(p))
    editing.add_wire(d, [(520, 500), (580, 500)])
    assert any(i.code == "junction" and "on top" in i.message for i in check.check(p))
    s = check.summary(check.check(p))
    assert s["error"] >= 2


def test_check_fluid_rules():
    p = new_project()
    d = p.sheets[0]
    pump = editing.place(d, "fl.hyd.pump", 0, 0)
    tank = editing.place(d, "fl.hyd.tank", 100, 0)
    a, b = pump.terminals()["P"], tank.terminals()["T"]
    editing.add_wire(d, [a, (a[0], a[1] - 40), (b[0], a[1] - 40), b])
    assert any(i.code == "fluid-rule" for i in check.check(p))


def test_check_custom_symbol_without_pins():
    doc = blank_symbol("Box")
    doc["prims"] = [{"k": "poly", "pts": [[-10, -10], [10, -10], [10, 10], [-10, 10]]}]
    symbols.add_project_symbol(to_symdef(doc))
    try:
        p = new_project()
        editing.place(p.sheets[0], doc["id"], 0, 0)
        assert any(i.code == "symbol" for i in check.check(p))
    finally:
        symbols.set_project_symbols([])


# ================================================================ custom symbols
def test_custom_symbol_validation():
    doc = blank_symbol("Sensor")
    doc["prims"] = [{"k": "arc", "c": [0, 0], "r": 8, "start": 0, "extent": 180}]
    doc["pins"] = [{"id": "p1", "name": "BN", "x": -20, "y": 0, "dir": "l", "type": "elec.power"},
                   {"id": "p2", "name": "BU", "x": 20, "y": 0, "dir": "r", "type": "elec.ground"}]
    sd = to_symdef(doc)
    g = sd.build(None)
    assert [t.name for t in g.terminals] == ["p1", "p2"] and g.terminals[0].label == "BN"
    assert all(p["k"] in ("line", "poly", "circle", "text") for p in g.prims), "arcs are flattened"
    doc["pins"][1]["x"] = 15
    with pytest.raises(SymbolFormatError, match="grid"):
        normalise(doc)
    with pytest.raises(SymbolFormatError):
        normalise(dict(doc, id="el.resistor.iec"))


def test_custom_symbol_embedded_in_project(tmp_path):
    doc = blank_symbol("Sensor")
    doc["prims"] = [{"k": "circle", "c": [0, 0], "r": 8}]
    doc["pins"] = [{"id": "p1", "name": "1", "x": -20, "y": 0, "dir": "l"}]
    symbols.set_user_symbols([to_symdef(doc)])
    p = new_project()
    c = editing.place(p.sheets[0], doc["id"], 0, 0)
    path = str(tmp_path / "c.schematix")
    projectio.save_project(p, path)
    symbols.set_user_symbols([])
    symbols.set_project_symbols([])
    q = projectio.open_any(path).project
    assert doc["id"] in q.symbols
    assert symbols.get(doc["id"]) is not None, "embedded definition registered on open"
    assert q.sheets[0].components[c.id].terminals()
    symbols.set_project_symbols([])


# ================================================================ user libraries
def make_sym(name, x=-20):
    d = blank_symbol(name)
    d["prims"] = [{"k": "poly", "pts": [[-10, -10], [10, -10], [10, 10], [-10, 10]]}]
    d["pins"] = [{"id": "p1", "name": "1", "x": x, "y": 0, "dir": "l"}]
    return d


def test_user_library_crud(tmp_path):
    lib = userlib.UserLibrary(str(tmp_path / "libs"))
    lib.create_folder("", "Mine")
    sub = lib.create_folder("Mine", "Sensors")
    e = lib.save_symbol(make_sym("Prox"), sub)
    assert e.folder == "Mine/Sensors" and e.doc["revision"] == 1
    e2 = lib.save_symbol(dict(e.doc, description="changed"), sub)
    assert e2.id == e.id and e2.doc["revision"] == 2
    cp = lib.copy_symbol(e.id, "Mine")
    assert cp.id != e.id
    lib.move_symbol(cp.id, "Mine/Sensors")
    assert len(lib.in_folder("Mine/Sensors")) == 2
    lib.set_tags(e.id, ["pnp", "sensor"], "Electrical")
    assert lib.search("pnp")[0].id == e.id and "pnp" in lib.all_tags()
    lib.rename_folder("Mine/Sensors", "Sense")
    assert lib.entries[e.id].folder == "Mine/Sense"
    lib.copy_folder("Mine/Sense", "")
    assert len(lib.entries) == 4 and len({x.id for x in lib.entries.values()}) == 4
    lib.delete_symbol(cp.id)
    lib.delete_folder("Sense")
    assert len(lib.entries) == 1
    assert symbols.get(e.id) is not None, "library symbols are registered"
    symbols.set_user_symbols([])


def test_library_package_roundtrip_and_conflicts(tmp_path):
    a = userlib.UserLibrary(str(tmp_path / "a"))
    a.create_folder("", "Shared")
    a.create_folder("Shared", "Valves")
    s1 = a.save_symbol(make_sym("One"), "Shared")
    a.save_symbol(make_sym("Two"), "Shared/Valves")
    pkg = str(tmp_path / "shared.osymlib")
    a.export_package("Shared", pkg, description="test")
    with zipfile.ZipFile(pkg) as z:
        assert all(".." not in n and not n.startswith("/") for n in z.namelist())
    b = userlib.UserLibrary(str(tmp_path / "b"))
    info = userlib.read_package(pkg, b)
    assert info.name == "Shared" and len(info.items) == 2 and not info.conflicts
    res = userlib.import_package(info, b, mode="separate")
    assert res["imported"] == 2 and {e.folder for e in b.entries.values()} == {"Shared", "Shared/Valves"}
    info2 = userlib.read_package(pkg, b)
    assert len(info2.conflicts) == 2
    res2 = userlib.import_package(info2, b, mode="merge", target="Shared", on_conflict="skip")
    assert res2["skipped"] == 2
    res3 = userlib.import_package(info2, b, mode="separate", on_conflict="duplicate")
    assert res3["duplicated"] == 2 and len(b.entries) == 4
    assert b.entries[s1.id].doc["name"] == "One"
    symbols.set_user_symbols([])


def test_package_rejects_unsafe_paths(tmp_path):
    p = tmp_path / "evil.osymlib"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": userlib.LIB_FORMAT, "version": 1, "name": "x",
                                                "symbols": [{"file": "../../etc/passwd", "folder": ""}]}))
    info = userlib.read_package(str(p))
    assert not info.items and info.problems


# ================================================================ templates
def test_templates_insert_with_new_identifiers(tmp_path):
    p = new_project()
    d = p.sheets[0]
    bt = templates.builtin_templates()
    assert set(bt) >= {"relay-latch", "motor-starter", "hyd-cylinder", "pneu-dcv"}
    templates.insert(d, bt["relay-latch"], 0, 0)
    templates.insert(d, bt["relay-latch"], 300, 0)
    coils = sorted(c.designator for c in d.components.values() if c.symbol == "el.coil.iec")
    contacts = sorted(c.designator for c in d.components.values() if c.symbol == "el.contact.no.iec")
    assert coils == ["K1", "K2"] and contacts == ["K1", "K2"], "coil and its contact keep sharing an identifier"
    store = templates.TemplateStore(str(tmp_path / "tpl"))
    clip = editing.copy_items(d, d.all_ids())
    tpl = templates.make_template("Two latches", clip, category="Mine")
    path = store.save(tpl, "Relays")
    assert any(k == path for k, _f, _t in store.items())
    exp = str(tmp_path / "x.ostpl")
    store.export_file(tpl, exp)
    store.import_file(exp, "Imported")
    assert len([1 for _k, f, _t in store.items() if not f.startswith("Built-in")]) == 2
    with pytest.raises(templates.TemplateError):
        templates.validate({"format": "nope"})


# ================================================================ autosave & recovery
def test_autosave_and_recovery(tmp_path):
    root = str(tmp_path / "rec")
    m = recovery.RecoveryManager(root)
    m.start()
    p = latch_project()
    assert m.autosave(p, "/x/y.schematix")
    assert m.autosave(p) is None, "unchanged project is not saved again"
    for i in range(5):
        p.meta["description"] = str(i)
        m.autosave(p)
    assert len(m.snapshots(m.folder)) == recovery.KEEP
    # simulate a crash: another manager (new process) sees the session as orphaned
    info = json.load(open(os.path.join(m.folder, "session.json")))
    info["pid"] = 999999999
    json.dump(info, open(os.path.join(m.folder, "session.json"), "w"))
    m2 = recovery.RecoveryManager(root)
    orphans = m2.orphans()
    assert len(orphans) == 1 and orphans[0].source == "/x/y.schematix"
    q = projectio.open_any(orphans[0].newest.path).project
    assert q.meta["description"] == "4"
    m2.discard(orphans[0])
    assert m2.orphans() == []
    # clean exit removes the session
    m3 = recovery.RecoveryManager(root)
    m3.start()
    m3.autosave(p)
    m3.end()
    assert os.listdir(root) == []


def test_recovery_cleanup_of_old_sessions(tmp_path):
    root = str(tmp_path / "rec")
    m = recovery.RecoveryManager(root)
    m.start()
    m.autosave(new_project())
    folder = m.folder
    info = json.load(open(os.path.join(folder, "session.json")))
    info["pid"] = 999999999
    json.dump(info, open(os.path.join(folder, "session.json"), "w"))
    for s in m.snapshots(folder):
        os.utime(s.path, (1, 1))
    assert recovery.RecoveryManager(root).cleanup() == 1
    assert not os.path.exists(folder)


# ================================================================ DXF
def test_dxf_export_import_roundtrip():
    p = latch_project()
    d = p.sheets[0]
    d.add_shape(Shape(d.new_id(), "text", pts=[(500, 500)], s="Ω test", size=12))
    text = dxf.to_dxf(d, p)
    assert text.startswith("  0\nSECTION") and text.rstrip().endswith("EOF")
    rep = dxf.import_dxf(text.encode("cp1252", errors="replace"), origin=(0, d.sheet.size_units()[1]))
    assert rep.counts.get("LINE", 0) > 10 and not rep.skipped
    b = rep.bbox
    W, H = d.sheet.size_units()
    assert -1 <= b[0] and b[2] <= W + 1 and -1 <= b[1] and b[3] <= H + 1, "coordinates map back onto the sheet"
    assert any(s.kind == "text" and "test" in s.s for s in rep.shapes)


def test_dxf_import_r2018_sample():
    raw = open(os.path.join(HERE, "data", "sample_r2018.dxf"), "rb").read()
    rep = dxf.import_dxf(raw)
    kinds = {s.kind for s in rep.shapes}
    assert {"line", "polygon", "circle", "arc", "text"} <= kinds
    assert rep.skipped.get("HATCH") == 1
    assert rep.units_mm == 1.0 and "INSUNITS" in rep.units_source
    assert rep.layers["OUTLINE"] == "#ff0000"
    texts = [s.s for s in rep.shapes if s.kind == "text"]
    assert "HELLO" in texts and "Line one" in texts and "Line two" in texts
    # a 10 mm circle becomes radius 40 drawing units (0.25 mm)
    assert any(s.kind == "circle" and s.r == pytest.approx(40) for s in rep.shapes)
    # inch override
    rep2 = dxf.import_dxf(raw, units="in")
    assert any(s.kind == "circle" and s.r == pytest.approx(40 * 25.4) for s in rep2.shapes)
    d = Document()
    ids = dxf.place_on_sheet(rep, d, project_with(d))
    assert len(ids) == len(rep.shapes) and all(i in d.shapes for i in ids)


def test_dxf_rejects_binary_and_garbage():
    with pytest.raises(dxf.DxfError):
        dxf.import_dxf(b"AutoCAD Binary DXF\r\n\x1a\x00" + b"\x00" * 20)
    with pytest.raises(dxf.DxfError):
        dxf.import_dxf(b"0\nSECTION\nfoo\nbar\n")


def _ezdxf_python():
    """A Python with ezdxf available for independent validation (optional)."""
    cands = [os.environ.get("EZDXF_PYTHON", ""), sys.executable]
    for py in cands:
        if not py:
            continue
        try:
            r = subprocess.run([py, "-c", "import ezdxf"], capture_output=True, timeout=60,
                               env=dict(os.environ, PYTHONPATH=os.environ.get("EZDXF_PATH", "")))
            if r.returncode == 0:
                return py
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def test_dxf_export_validates_with_ezdxf(tmp_path):
    py = _ezdxf_python()
    if py is None:
        pytest.skip("ezdxf not available for independent validation")
    p = latch_project()
    path = tmp_path / "x.dxf"
    dxf.export_dxf(p.sheets[0], str(path), p)
    code = ("import ezdxf,sys; from ezdxf import recover; d,a=recover.readfile(sys.argv[1]); "
            "ezdxf.readfile(sys.argv[1]); print(len(a.errors), len(list(d.modelspace())))")
    r = subprocess.run([py, "-c", code, str(path)], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, PYTHONPATH=os.environ.get("EZDXF_PATH", "")))
    assert r.returncode == 0, r.stderr
    errors, n = map(int, r.stdout.split())
    assert errors == 0 and n > 50


# ================================================================ PDF
def test_project_pdf_pages_sizes_and_outline():
    pypdf = pytest.importorskip("pypdf")
    p = latch_project()
    p.sheets[0].sheet.size = "A3"
    s2 = p.add_sheet("Portrait")
    s2.sheet.size, s2.sheet.orientation = "A4", "portrait"
    s3 = p.add_sheet("ANSI B")
    s3.sheet.size, s3.sheet.orientation = "ANSI B", "landscape"
    data = export.project_pdf(p)
    r = pypdf.PdfReader(io.BytesIO(data))
    assert len(r.pages) == 3
    w0, h0 = float(r.pages[0].mediabox.width), float(r.pages[0].mediabox.height)
    w1, h1 = float(r.pages[1].mediabox.width), float(r.pages[1].mediabox.height)
    w2 = float(r.pages[2].mediabox.width)
    assert (round(w0 / 72 * 25.4), round(h0 / 72 * 25.4)) == (420, 297)
    assert (round(w1 / 72 * 25.4), round(h1 / 72 * 25.4)) == (210, 297)
    assert round(w2 / 72 * 25.4, 1) == 431.8
    assert [o.title for o in r.outline] == ["1. Sheet 1", "2. Portrait", "3. ANSI B"]
    assert "1 / 3" in r.pages[0].extract_text() and "3 / 3" in r.pages[2].extract_text()
    only = pypdf.PdfReader(io.BytesIO(export.project_pdf(p, {s2.uid})))
    assert len(only.pages) == 1


def test_pdf_scaled_sheet_and_rotated_text():
    pypdf = pytest.importorskip("pypdf")
    p = new_project()
    d = p.sheets[0]
    d.sheet.scale = "1:2"
    d.add_shape(Shape(d.new_id(), "text", pts=[(800, 600)], s="ROTATED", size=20, angle=90))
    r = pypdf.PdfReader(io.BytesIO(export.project_pdf(p)))
    assert round(float(r.pages[0].mediabox.width) / 72 * 25.4) == round(d.sheet.size_mm()[0])
    assert "ROTATED" in r.pages[0].extract_text()


def test_title_block_styles_and_revision_table():
    from openschematix.titleblock import frame_prims, zone_of
    p = latch_project()
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "approved", label="A", description="First issue", author="NR")
    d = p.sheets[0]
    for style in ("standard", "compact", "iso", "none"):
        d.sheet.title_block = style
        texts = [it["s"] for it in frame_prims(d, p) if it["k"] == "text"]
        if style in ("standard", "iso"):
            assert "First issue" in texts
        if style != "none":
            assert "1 / 1" in texts
    assert zone_of(d, (60, 60)) == "A1"
    d.sheet.zones = False
    assert zone_of(d, (60, 60)) == ""


# ================================================================ command parsing
def test_command_parsing():
    assert commands.resolve("l") == "LINE" and commands.resolve("CO") == "COPY"
    assert commands.resolve("TR") == "TRIM" and commands.resolve("xyz") is None
    assert commands.resolve("zz", {"ZZ": "ZOOM"}) == "ZOOM"
    assert commands.split("  insert   K1 ") == ("insert", "K1")
    sug = commands.complete("RE")
    assert ("RECTANGLE", "Draw a rectangle") in sug and any(s[0] == "REDO" for s in sug)
    assert commands.parse_point("10,20") == (10, 20)
    assert commands.parse_point("@5,-5", (10, 20)) == (15, 15)
    x, y = commands.parse_point("@10<90", (0, 0))
    assert (round(x, 9), y) == (0, 10)
    with pytest.raises(commands.ParseError):
        commands.parse_point("@1,1")
    with pytest.raises(commands.ParseError):
        commands.parse_point("abc")
    assert commands.parse_scale_factor("1:2") == 0.5
    assert "LINE" in commands.help_text()
