"""Python scripting API (openschematix.api), phase 1."""
import json
import os
import subprocess
import sys
import zipfile

import pytest

from openschematix import api, projectio, symbols
from openschematix.api import _core
from openschematix.geometry import xform
from openschematix.symbols.custom import blank_symbol, normalise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")                 # drawings
SCRIPTS = os.path.join(ROOT, "docs", "examples")          # example scripts


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    symbols.set_user_symbols([])
    symbols.set_project_symbols([])
    _core._invalidate()


@pytest.fixture
def sheet():
    return api.new_project("Test").sheets[0]


def snapshot(project: api.Project) -> dict:
    """Engineering content of a project, for round-trip comparisons."""
    out = {"title": project.title, "sheets": []}
    for s in project.sheets:
        out["sheets"].append({
            "uid": s.uid, "name": s.name,
            "components": sorted((c.id, c.symbol_id, c.position, c.rotation, c.mirror, c.designator, c.label,
                                  json.dumps(c.params, sort_keys=True), json.dumps(c.properties, sort_keys=True),
                                  c.in_bom) for c in s.components()),
            "wires": sorted((w.id, tuple(w.points), w.start, w.end, w.style, w.number) for w in s.wires()),
        })
    out["nets"] = sorted((n.number, tuple((t.sheet_uid, t.component_id, t.designator, t.terminal)
                                          for t in n.terminals)) for n in project.nets())
    return out


def load_example():
    sys.path.insert(0, SCRIPTS)
    try:
        import motor_starter
        return motor_starter
    finally:
        sys.path.pop(0)


# ================================================================ public surface / headless
def test_public_surface_is_small_and_complete():
    for name in api.__all__:
        assert hasattr(api, name), name
    assert api.GRID == 10 and api.UNIT_MM == 0.25 and api.ROTATIONS == (0, 90, 180, 270)
    assert issubclass(api.SymbolNotFoundError, KeyError) and issubclass(api.InvalidOperationError, ValueError)
    assert all(issubclass(e, api.ApiError) for e in (api.SymbolNotFoundError, api.ObjectNotFoundError,
                                                      api.InvalidOperationError, api.ProjectFileError))


def test_headless_without_tkinter_or_display(tmp_path):
    """Importing and using the API must not need tkinter, a display or the GUI."""
    out = tmp_path / "headless.schematix"
    code = f"""
import sys
sys.modules["tkinter"] = None            # any import of tkinter now fails
sys.path.insert(0, {SCRIPTS!r})
from openschematix import api
import motor_starter
p = motor_starter.build()
p.save({str(out)!r})
assert not [m for m in sys.modules if m.startswith("openschematix.gui")], "GUI imported"
print("ok", len(p.components()))
"""
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    env["OPENSCHEMATIX_CONFIG_DIR"] = str(tmp_path / "config")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("ok") and out.exists()
    assert not (tmp_path / "config").exists()       # the API writes no settings or libraries


# ================================================================ projects and sheets
def test_new_project_and_metadata():
    p = api.new_project("Pump skid", sheet_size="A4")
    assert p.title == "Pump skid" and p.path is None and p.warnings == ()
    assert [s.name for s in p.sheets] == ["Sheet 1"] and p.sheets[0].size == "A4"
    p.title = "Pump skid rev B"
    assert p.title == "Pump skid rev B"
    with pytest.raises(api.InvalidOperationError, match="sheet size"):
        api.new_project(sheet_size="B7")


def test_sheet_operations():
    p = api.new_project()
    s1 = p.sheets[0]
    s2 = p.add_sheet("Hydraulics")
    s3 = p.add_sheet()
    assert [s.name for s in p.sheets] == ["Sheet 1", "Hydraulics", "Sheet 3"]
    assert p.sheet("Hydraulics") == s2 and p.sheet(s3.uid) == s3 and p.sheet(1) == s1
    assert s2.number == 2
    s3.name = "Panel layout"
    assert p.sheet("Panel layout") == s3
    with pytest.raises(api.InvalidOperationError):
        s3.name = "   "
    p.remove_sheet(s3)
    with pytest.raises(api.ObjectNotFoundError):
        _ = s3.name
    with pytest.raises(api.ObjectNotFoundError):
        p.sheet("Panel layout")
    with pytest.raises(api.ObjectNotFoundError):
        p.sheet(9)
    p.remove_sheet(s2)
    with pytest.raises(api.InvalidOperationError, match="at least one sheet"):
        p.remove_sheet(s1)
    s1.name = "Twin"
    p.add_sheet("Twin")
    with pytest.raises(api.ObjectNotFoundError, match="uid"):
        p.sheet("Twin")
    other = api.new_project()
    with pytest.raises(api.InvalidOperationError):
        p.remove_sheet(other.sheets[0])


# ================================================================ symbols
def test_symbol_lookup():
    coil = api.get_symbol("el.coil.iec")
    assert coil.prefix == "K" and [t.name for t in coil.terminals] == ["A1", "A2"]
    assert coil.terminals[0] == api.SymbolTerminal("A1", "A1", 0.0, -20.0, "u", "elec.passive")
    valves = api.list_symbols("valve", category="Hydraulic")
    assert valves and all(v.category == "Hydraulic" for v in valves)
    assert api.get_symbol("fl.hyd.dcv").parametric
    ids = {s.id for s in api.list_symbols()}
    assert "el.coil.iec" in ids and "gen.unknown" not in ids
    with pytest.raises(api.SymbolNotFoundError, match="list_symbols"):
        api.get_symbol("el.flux.capacitor")


# ================================================================ placement and transformations
def test_place_assigns_designators_and_snaps_nothing(sheet):
    k1 = sheet.place("el.coil.iec", 100, 200)
    k2 = sheet.place("el.coil.iec", 200, 200, designator="K7", label="Pump", properties={"rating": "24 V"})
    k3 = sheet.place("el.coil.iec", 300, 200)
    assert (k1.designator, k2.designator, k3.designator) == ("K1", "K7", "K2")
    assert k2.label == "Pump" and k2.properties == {"rating": "24 V"}
    assert k1.position == (100, 200) and k1.rotation == 0 and k1.mirror is False
    assert sheet.component(k1.id) == k1 and k1 in sheet.components()


def test_designators_are_unique_across_sheets():
    p = api.new_project()
    a = p.sheets[0].place("el.coil.iec", 0, 0)
    b = p.add_sheet().place("el.coil.iec", 0, 0)
    assert (a.designator, b.designator) == ("K1", "K2")


def test_terminal_blocks_get_strip_and_number(sheet):
    t1 = sheet.place("el.terminal", 0, 0)
    t2 = sheet.place("el.terminal", 100, 0)
    t3 = sheet.place("el.terminal", 200, 0, designator="X5")
    t4 = sheet.place("el.terminal", 300, 0, designator="X5")
    assert [(t.designator, t.properties["terminal"]) for t in (t1, t2, t3, t4)] == \
        [("X1", "1"), ("X1", "2"), ("X5", "1"), ("X5", "2")]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_terminal_positions_follow_rotation_and_mirroring(sheet, rotation, mirror):
    c = sheet.place("fl.hyd.cyl.double", 300, 300, rotation=rotation, mirror=mirror)
    for t in api.get_symbol("fl.hyd.cyl.double").terminals:
        dx, dy = xform(t.x, t.y, rotation, mirror)
        assert c.terminal(t.name).position == pytest.approx((300 + dx, 300 + dy))
        assert c.terminal(t.name).position[0] % 10 == 0 and c.terminal(t.name).position[1] % 10 == 0


def test_rotate_mirror_and_move_keep_wires_attached(sheet):
    k1 = sheet.place("el.coil.iec", 200, 200)
    s1 = sheet.place("el.pushbutton.no.iec", 100, 300)
    w = sheet.connect(s1, "2", k1, "A2")
    for change in (lambda: setattr(k1, "rotation", 90), lambda: setattr(k1, "mirror", True),
                   lambda: setattr(k1, "position", (400, 100)), lambda: k1.move_by(-50 + 50, 30),
                   lambda: setattr(s1, "rotation", 270)):
        change()
        assert w.start == (s1.id, "2") and w.end == (k1.id, "A2")
        assert w.points[0] == s1.terminal("2").position and w.points[-1] == k1.terminal("A2").position
        assert (k1.id, "A2") in sheet.connectivity().connected_terminals
    assert (k1.rotation, k1.mirror, k1.position) == (90, True, (400, 130))


@pytest.mark.parametrize("call,match", [
    (lambda s: s.place("el.coil.iec", 5, 0), "grid"),
    (lambda s: s.place("el.coil.iec", 0, float("nan")), "finite"),
    (lambda s: s.place("el.coil.iec", "0", 0), "number"),
    (lambda s: s.place("el.coil.iec", 0, 0, rotation=45), "rotation"),
    (lambda s: s.place("el.coil.iec", 0, 0, rotation=True), "rotation"),
    (lambda s: s.place("el.coil.iec", 0, 0, mirror="yes"), "mirror"),
    (lambda s: s.place("el.coil.iec", 0, 0, params={"type": "x"}), "no parameters"),
    (lambda s: s.place("el.coil.iec", 0, 0, properties={"": "x"}), "property name"),
    (lambda s: s.place("el.coil.iec", 0, 0, properties={"rating": 24}), "string"),
    (lambda s: s.place("el.coil.iec", 0, 0, designator="K\n1"), "single line"),
])
def test_invalid_placement_raises_and_changes_nothing(sheet, call, match):
    with pytest.raises(api.InvalidOperationError, match=match):
        call(sheet)
    assert sheet.components() == []


@pytest.mark.parametrize("sid", ["el.nonexistent", "", None, 42, "gen.unknown"])
def test_unknown_symbols_are_rejected(sheet, sid):
    with pytest.raises(api.SymbolNotFoundError):
        sheet.place(sid, 0, 0)
    assert sheet.components() == []


def test_invalid_moves_and_rotations_change_nothing(sheet):
    c = sheet.place("el.coil.iec", 100, 100)
    for bad in ((105, 100), (100,), "here", (None, 0)):
        with pytest.raises(api.InvalidOperationError):
            c.position = bad
    with pytest.raises(api.InvalidOperationError):
        c.rotation = 30
    with pytest.raises(api.InvalidOperationError):
        c.move_by(1, 0)
    assert (c.position, c.rotation) == ((100, 100), 0)


# ================================================================ parameters
def test_valve_parameters(sheet):
    v = sheet.place("fl.hyd.dcv", 300, 300, params={"type": "4/2", "left": ["solenoid"]})
    assert v.params["type"] == "4/2" and v.params["positions"] == ["parallel", "crossed"]
    assert v.params["left"] == ["solenoid"] and v.params["medium"] == "hyd"
    assert sorted(v.terminals) == ["A", "B", "P", "T"]
    v.set_params(type="2/2")
    assert sorted(v.terminals) == ["A", "P"] and v.params["positions"] == ["open", "closed"]
    p = sheet.place("fl.pneu.dcv", 500, 300)
    assert sorted(p.terminals) == ["1", "2", "3", "4", "5"]


@pytest.mark.parametrize("params,match", [
    ({"type": "9/9"}, "valve type"),
    ({"medium": "pneu"}, "medium"),
    ({"positions": ["parallel"]}, "positions"),
    ({"positions": ["parallel", "sideways", "crossed"]}, "positions"),
    ({"left": "solenoid"}, "operators"),
    ({"left": ["laser"]}, "operators"),
    ({"colour": "red"}, "no parameter"),
    ("4/2", "dict"),
])
def test_invalid_valve_parameters_are_rejected(sheet, params, match):
    """The valve builder would silently fall back to defaults; the API refuses."""
    with pytest.raises(api.InvalidOperationError, match=match):
        sheet.place("fl.hyd.dcv", 300, 300, params=params)
    v = sheet.place("fl.hyd.dcv", 300, 300)
    before = v.params
    with pytest.raises(api.InvalidOperationError):
        v.set_params(**params) if isinstance(params, dict) else v.set_params(type=params, positions=1)
    assert v.params == before


def test_parameter_change_that_would_orphan_a_wire_is_refused(sheet):
    v = sheet.place("fl.hyd.dcv", 300, 300, params={"type": "4/2"})
    tank = sheet.place("fl.hyd.tank", 310, 400)
    w = sheet.connect(v, "T", tank, "T")
    with pytest.raises(api.InvalidOperationError, match="T"):
        v.set_params(type="2/2")
    assert v.params["type"] == "4/2" and w.start == (v.id, "T")
    v.set_params(left=["lever"])          # keeps every port: fine
    assert w.start == (v.id, "T") and v.params["left"] == ["lever"]


# ================================================================ wires and connectivity
def test_add_wire_connects_only_at_wire_ends(sheet):
    r1 = sheet.place("el.resistor.iec", 100, 100)
    r2 = sheet.place("el.resistor.iec", 300, 100)
    w = sheet.add_wire([r1.terminal("2").position, (200, 100), r2.terminal("1").position])
    assert w.points == [(120.0, 100.0), (280.0, 100.0)]          # collinear point simplified
    assert w.start == (r1.id, "2") and w.end == (r2.id, "1")
    conn = sheet.connectivity()
    assert {(r1.id, "2"), (r2.id, "1")} <= conn.connected_terminals
    assert {(r1.id, "1"), (r2.id, "2")} == {(c, n) for c, n, _p in conn.open_terminals}
    # a wire passing over a terminal is not connected to it (application rule)
    r3 = sheet.place("el.resistor.iec", 500, 100)
    over = sheet.add_wire([(500, 60), (500, 140)])
    assert over.start is None and over.end is None
    assert (r3.id, "1") not in sheet.connectivity().connected_terminals


def test_tee_junction_and_nets(sheet):
    a = sheet.place("el.resistor.iec", 100, 100)
    b = sheet.place("el.resistor.iec", 300, 100)
    c = sheet.place("el.resistor.iec", 220, 200, rotation=90)
    sheet.add_wire([a.terminal("2").position, b.terminal("1").position])
    sheet.add_wire([c.terminal("1").position, (220, 100)])        # ends on the first wire
    conn = sheet.connectivity()
    assert (220.0, 100.0) in conn.junctions
    nets = sheet.project.nets()
    assert len(nets) == 1
    assert {(t.designator, t.terminal) for t in nets[0].terminals} == {("R1", "2"), ("R2", "1"), ("R3", "1")}


def test_wires_that_merely_cross_are_not_connected(sheet):
    sheet.add_wire([(0, 100), (200, 100)])
    sheet.add_wire([(100, 0), (100, 200)])
    assert sheet.connectivity().junctions == ()


@pytest.mark.parametrize("points,match", [
    ([(0, 0)], "two points"),
    ([(0, 0), (0, 0)], "distinct"),
    ([(0, 0), (100, 50)], "horizontal or vertical"),
    ([(0, 0), (10.5, 0)], "whole"),
    ([(0, 0), (0, float("inf"))], "finite"),
    ([(0, 0), (1, 2, 3)], "pair"),
    (5, "list"),
])
def test_malformed_wires_are_rejected(sheet, points, match):
    with pytest.raises(api.InvalidOperationError, match=match):
        sheet.add_wire(points)
    assert sheet.wires() == []


def test_connect_validation(sheet):
    k1 = sheet.place("el.coil.iec", 100, 100)
    with pytest.raises(api.ObjectNotFoundError, match="A1, A2"):
        sheet.connect(k1, "1", k1, "A2")
    with pytest.raises(api.InvalidOperationError, match="itself"):
        sheet.connect(k1, "A1", k1, "A1")
    other = sheet.project.add_sheet().place("el.coil.iec", 0, 0)
    with pytest.raises(api.InvalidOperationError, match="this sheet"):
        sheet.connect(k1, "A1", other, "A1")
    with pytest.raises(api.InvalidOperationError, match="style"):
        sheet.connect(k1, "A1", k1, "A2", style="wavy")
    assert sheet.wires() == []


def test_remove_component_and_wire(sheet):
    a = sheet.place("el.resistor.iec", 100, 100)
    b = sheet.place("el.resistor.iec", 300, 100)
    w = sheet.connect(a, "2", b, "1")
    b.remove()
    assert w.end is None and b not in sheet.components()
    with pytest.raises(api.ObjectNotFoundError, match="removed"):
        _ = b.designator
    sheet.remove(w)
    assert sheet.wires() == []
    with pytest.raises(api.ObjectNotFoundError):
        _ = w.points
    with pytest.raises(api.ObjectNotFoundError):
        sheet.component(b.id)


def test_locked_objects_cannot_be_changed(sheet):
    c = sheet.place("el.coil.iec", 100, 100)
    w = sheet.add_wire([(0, 0), (50, 0)])
    internal = sheet.project._p
    internal.layer("Components").locked = True
    internal.layer("Wires").locked = True
    assert c.locked
    for change in (lambda: setattr(c, "designator", "K9"), lambda: setattr(c, "position", (200, 200)),
                   lambda: setattr(c, "rotation", 90), lambda: c.set_property("rating", "x"), c.remove,
                   w.remove):
        with pytest.raises(api.InvalidOperationError, match="locked"):
            change()
    assert c.designator == "K1" and c.position == (100, 100) and len(sheet.wires()) == 1


# ================================================================ properties and BOM
def test_component_properties(sheet):
    k1 = sheet.place("el.coil.iec", 100, 100)
    k1.designator = "K10"
    k1.label = "Main contactor"
    k1.set_property("part_number", "AC-9")
    k1.set_property("supplier code", "123")
    assert k1.properties == {"part_number": "AC-9", "supplier code": "123"}
    k1.set_property("supplier code", "")              # empty removes, as in the application
    assert "supplier code" not in k1.properties
    k1.remove_property("part_number")
    with pytest.raises(api.ObjectNotFoundError):
        k1.remove_property("part_number")
    props = k1.properties
    props["x"] = "y"                                  # returned dicts are copies
    assert "x" not in k1.properties
    k1.in_bom = False
    assert (k1.designator, k1.label, k1.in_bom) == ("K10", "Main contactor", False)
    with pytest.raises(api.InvalidOperationError):
        k1.in_bom = 0


def test_bom_matches_the_bom_subsystem(sheet):
    p = sheet.project
    for x in (100, 200, 300):
        sheet.place("el.fuse.iec", x, 100, properties={"part_number": "FU-2A", "manufacturer": "ACME"})
    coil = sheet.place("el.coil.iec", 100, 300, properties={"part_number": "AC-9"})
    sheet.place("el.contact.no.iec", 200, 300, designator=coil.designator)   # same device
    excluded = sheet.place("el.lamp.iec", 300, 300)
    excluded.in_bom = False
    lines = p.bom()
    by_pn = {line.part_number: line for line in lines}
    assert by_pn["FU-2A"].quantity == 3 and by_pn["FU-2A"].designator_text == "F1–F3"
    assert by_pn["AC-9"].quantity == 1 and by_pn["AC-9"].designator_text == "K1"   # coil + contact
    assert all("H1" not in line.designators for line in lines)
    assert any("H1" in line.designators for line in p.bom(include_excluded=True))
    from openschematix import bom
    assert p.bom_csv() == bom.bom_csv(bom.generate(p._p))
    assert p.bom_csv().splitlines()[0].lstrip("\ufeff").startswith("Item,Qty,Designators")


def test_check_and_wire_numbers(sheet):
    p = sheet.project
    a = sheet.place("el.resistor.iec", 100, 100)
    b = sheet.place("el.resistor.iec", 300, 100)
    w = sheet.connect(a, "2", b, "1")
    codes = {i.code for i in p.check()}
    assert "open-terminal" in codes
    assert all(i.code == "open-terminal" for i in p.check(rules=["open-terminal"]))
    with pytest.raises(api.InvalidOperationError, match="unknown check rule"):
        p.check(rules=["spelling"])
    assert p.number_wires() >= 1 and w.number == "1"
    b.designator = "R1"
    assert any(i.code == "duplicate-id" for i in p.check())


# ================================================================ save / open
def test_example_creates_and_saves_a_useful_schematic(tmp_path):
    ms = load_example()
    path = str(tmp_path / "motor_starter.schematix")
    assert ms.main(["motor_starter.py", path]) == 0
    p = api.open_project(path)
    assert [s.name for s in p.sheets] == ["Control", "Hydraulics"] and p.path == path
    assert not [i for i in p.check() if i.severity == "error"]
    nets = {frozenset((t.designator, t.terminal) for t in n.terminals) for n in p.nets()}
    assert frozenset({("S2", "2"), ("K1", "A1"), ("K1", "2"), ("H1", "1")}) in nets       # latch + lamp
    assert frozenset({("P1", "P"), ("V1", "P"), ("V2", "P")}) in nets                    # pressure line
    assert {line.designator_text: line.quantity for line in p.bom()}["K1"] == 1
    with zipfile.ZipFile(path) as z:                                                     # native container
        assert "project.json" in z.namelist()


def test_round_trip_preserves_everything(tmp_path):
    p = load_example().build()
    p.number_wires()
    before = snapshot(p)
    path = p.save(str(tmp_path / "rt.schematix"))
    q = api.open_project(path)
    assert snapshot(q) == before
    # ... and again through the engine's own reader
    r = projectio.open_any(path).project
    assert r.to_dict()["sheets"] == p._p.to_dict()["sheets"]
    # resave the reopened project without changes: content identical
    q.save(snapshot=False)
    assert snapshot(api.open_project(path)) == before


def test_save_validation(tmp_path):
    p = api.new_project()
    with pytest.raises(api.InvalidOperationError, match="no file"):
        p.save()
    with pytest.raises(api.InvalidOperationError, match=".schematix"):
        p.save(str(tmp_path / "x.osch"))
    with pytest.raises(api.ProjectFileError):
        p.save(str(tmp_path / "missing-dir" / "x.schematix"))
    assert p.path is None


def test_open_errors(tmp_path):
    with pytest.raises(api.ProjectFileError, match="could not open"):
        api.open_project(str(tmp_path / "nope.schematix"))
    bad = tmp_path / "bad.schematix"
    bad.write_bytes(b"PK\x03\x04 not really a zip")
    with pytest.raises(api.ProjectFileError):
        api.open_project(str(bad))
    junk = tmp_path / "junk.osch"
    junk.write_text("{}")
    with pytest.raises(api.ProjectFileError):
        api.open_project(str(junk))


# ================================================================ compatibility
def test_existing_project_opens_and_inspects_like_the_application(tmp_path):
    path = os.path.join(EXAMPLES, "demo_project.schematix")
    before = open(path, "rb").read()
    p = api.open_project(path)
    ref = projectio.open_any(path).project
    assert [s.uid for s in p.sheets] == [d.uid for d in ref.sheets]
    assert len(p.components()) == sum(len(d.components) for d in ref.sheets) > 0
    assert len(p.nets()) == len(__import__("openschematix.netlist", fromlist=["x"]).compute_nets(ref))
    for c in p.components():
        assert c.terminals                                   # every symbol resolves
    out = p.save(str(tmp_path / "copy.schematix"), snapshot=False)
    assert open(path, "rb").read() == before                 # the original is untouched
    assert projectio.open_any(out).project.to_dict()["sheets"] == ref.to_dict()["sheets"]


@pytest.mark.parametrize("name", ["start_stop_latch.osch", "hydraulic_cylinder_circuit.osch"])
def test_legacy_drawings_convert(tmp_path, name):
    p = api.open_project(os.path.join(EXAMPLES, name))
    assert p.path is None and any("Converted" in w for w in p.warnings) and p.components()
    with pytest.raises(api.InvalidOperationError, match="no file"):
        p.save()
    out = p.save(str(tmp_path / (name + ".schematix")))
    assert len(api.open_project(out).components()) == len(p.components())


# ================================================================ custom symbols, several projects
def sensor():
    d = blank_symbol("Proximity sensor")
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "BN", "name": "BN", "x": -20, "y": 0, "dir": "l"},
                 {"id": "BK", "name": "BK", "x": 20, "y": 0, "dir": "r"}]
    return normalise(d)


def test_custom_symbols_are_embedded_and_projects_stay_independent(tmp_path):
    lib = tmp_path / "lib" / "Mine"
    lib.mkdir(parents=True)
    s = sensor()
    (lib / "sensor.osym").write_text(json.dumps(s), encoding="utf-8")
    assert api.load_user_library(str(tmp_path / "lib")) == []
    assert api.get_symbol(s["id"]).custom
    p1 = api.new_project("With sensor")
    b1 = p1.sheets[0].place(s["id"], 100, 100)
    path = p1.save(str(tmp_path / "p1.schematix"))
    (tmp_path / "empty").mkdir()
    assert api.load_user_library(str(tmp_path / "empty")) == []   # library gone (another computer)
    with pytest.raises(api.SymbolNotFoundError):
        api.new_project().sheets[0].place(s["id"], 0, 0)
    q1 = api.open_project(path)                             # embedded copy is used
    p2 = api.open_project(os.path.join(EXAMPLES, "demo_project.schematix"))
    assert p2.components()
    sensor_q = q1.components()[0]                           # q1 is re-activated automatically
    assert sorted(sensor_q.terminals) == ["BK", "BN"]
    assert sensor_q.terminal("BK").position == (120.0, 100.0)
    q1.sheets[0].place(s["id"], 300, 100)                   # still placeable in its own project
    assert len(q1.components()) == 2 and b1.designator == q1.components()[0].designator


def test_load_user_library_reports_problems(tmp_path):
    with pytest.raises(api.ObjectNotFoundError, match="library folder"):
        api.load_user_library(str(tmp_path / "missing"))
    (tmp_path / "Bad").mkdir()
    (tmp_path / "Bad" / "broken.osym").write_text("{", encoding="utf-8")
    problems = api.load_user_library(str(tmp_path))
    assert len(problems) == 1 and "broken.osym" in problems[0]
