"""Export to KiCad (openschematix/kicad.py).

KiCad is the judge: where ``kicad-cli`` is installed (CI's Ubuntu jobs install KiCad 7 and set
OPENSCHEMATIX_REQUIRE_KICAD=1, so there they can't skip), KiCad reads every file written here and its netlist
must have exactly the connections OpenSchematix has. Without it, the tests that need KiCad skip and say so; the
rest still run.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from openschematix import editing, kicad, netlist, projectio
from openschematix.geometry import xform
from openschematix.model import Wire
from openschematix.project import new_project

ROOT = Path(__file__).resolve().parent.parent
KICAD_CLI = shutil.which("kicad-cli")
if KICAD_CLI is None and os.environ.get("OPENSCHEMATIX_REQUIRE_KICAD"):
    raise RuntimeError("OPENSCHEMATIX_REQUIRE_KICAD is set but kicad-cli isn't installed")
needs_kicad = pytest.mark.skipif(KICAD_CLI is None, reason="KiCad (kicad-cli) isn't installed")


def kicad_netlist(sch: Path):
    out = sch.with_suffix(".xml")
    r = subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadxml", "-o", str(out), str(sch)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    return ET.parse(out).getroot()


def kicad_nets(root) -> dict:
    return {n.get("name"): frozenset((d.get("ref"), d.get("pin")) for d in n.iter("node")) for n in root.iter("net")}


def our_nets(project, export) -> set:
    out = set()
    for n in netlist.compute_nets(project):
        assert all(t in export.pins or t[:2] in export.links for t in n.terminals)
        nodes = frozenset(export.pins[t] for t in n.terminals if t in export.pins and not export.pins[t][0].startswith("#"))
        if len(nodes) >= 2:
            out.add(nodes)
    return out


def same_connections(project, folder: Path, name="exported"):
    """Write the project, have KiCad read it, and compare the connections. Returns (export, KiCad's root)."""
    export = kicad.write_project(project, str(folder / f"{name}.kicad_sch"))
    root = kicad_netlist(folder / f"{name}.kicad_sch")
    theirs = {nodes for nodes in kicad_nets(root).values() if len(nodes) >= 2}
    ours = our_nets(project, export)
    assert ours == theirs, (sorted(map(sorted, ours - theirs)), sorted(map(sorted, theirs - ours)))
    return export, root


def wire(doc, *points):
    w = editing.add_wire(doc, list(points))
    assert w is not None
    return w


# ------------------------------------------------------------------------------------------------ without KiCad

def test_every_orientation_puts_the_symbol_where_openschematix_draws_it():
    """KiCad has twelve ways of writing an orientation; for each of OpenSchematix's eight, the one chosen must
    move every library point (x, -y) to OpenSchematix's (x, y) turned and mirrored."""
    for rotation in (0, 90, 180, 270):
        for mirror in (False, True):
            c = type("C", (), {"rotation": rotation, "mirror": mirror})()
            angle, m = kicad._orientation(c)
            t = kicad._kicad_transform(angle, m)
            for x, y in ((10, 0), (0, 10), (30, -20), (-7, 13)):
                assert kicad._apply(t, x, -y) == pytest.approx(xform(x, y, rotation, mirror)), (rotation, mirror)


def test_strings_are_written_as_kicad_reads_them():
    assert kicad._s('a "b" \\ c\nd') == '"a \\"b\\" \\\\ c\\nd"'
    assert kicad._n(2.54) == "2.54" and kicad._n(-0.00001) == "0" and kicad._n(1.0) == "1"


def test_one_unit_is_ten_mil_so_the_grid_is_kicads():
    assert kicad.MM * 10 == pytest.approx(2.54)


def test_a_sym_lib_table_is_added_to_never_replaced():
    fresh = kicad.lib_table(None)
    assert fresh.startswith("(sym_lib_table") and '(name "OpenSchematix")' in fresh
    assert kicad.lib_table(fresh) is None                                   # already there: left alone
    theirs = '(sym_lib_table\n  (version 7)\n  (lib (name "Mine")(type "KiCad")(uri "x.kicad_sym")(options "")(descr ""))\n)\n'
    merged = kicad.lib_table(theirs)
    assert '(name "Mine")' in merged and '(name "OpenSchematix")' in merged and merged.count("(lib ") == 2
    with pytest.raises(kicad.KiCadError):
        kicad.lib_table("something else entirely")


def test_files_and_nothing_else_is_touched(tmp_path):
    p = new_project("Pump skid")
    d = p.sheets[0]
    editing.place(d, "el.fuse.iec", 100, 100)
    (tmp_path / "other.txt").write_text("mine")
    (tmp_path / "pump.kicad_pro").write_text("{\"mine\": true}\n")
    export = kicad.write_project(p, str(tmp_path / "pump.kicad_sch"))
    assert sorted(x.name for x in tmp_path.iterdir()) == ["OpenSchematix.kicad_sym", "other.txt", "pump.kicad_pro",
                                                         "pump.kicad_sch", "sym-lib-table"]
    assert (tmp_path / "pump.kicad_pro").read_text() == "{\"mine\": true}\n"    # their project file stays theirs
    assert (tmp_path / "other.txt").read_text() == "mine"
    assert sorted(export.files) == ["OpenSchematix.kicad_sym", "pump.kicad_sch"]
    again = kicad.plan(p, "pump")
    assert again.files == export.files                                        # the same project, the same files
    assert kicad.files_to_replace(str(tmp_path), again, "pump") == ["OpenSchematix.kicad_sym"]


def test_a_new_folder_gets_a_project_file(tmp_path):
    p = new_project("x")
    kicad.write_project(p, str(tmp_path / "board.kicad_sch"))
    assert '"filename": "board.kicad_pro"' in (tmp_path / "board.kicad_pro").read_text()


def test_wire_numbers_shared_by_two_nets_are_not_net_names():
    p = new_project("numbers")
    d = p.sheets[0]
    a, b = wire(d, (0, 0), (100, 0)), wire(d, (0, 100), (100, 100))
    a.number = b.number = "12"
    export = kicad.plan(p, "n")
    assert "(label " not in export.files["n.kicad_sch"]
    assert any("12" in note for note in export.notes)


# ---------------------------------------------------------------------------------------------------- with KiCad

@needs_kicad
@pytest.mark.parametrize("example", ["demo_project.schematix", "start_stop_latch.osch", "hydraulic_cylinder_circuit.osch"])
def test_the_examples_have_the_same_connections_in_kicad(example, tmp_path):
    project = projectio.open_any(str(ROOT / "examples" / example)).project
    export, root = same_connections(project, tmp_path)
    assert export.notes == []
    refs = sorted(c.get("ref") for c in root.iter("comp"))
    assert len(refs) == len(set(refs))


@needs_kicad
def test_the_demo_keeps_its_wire_numbers_parts_and_sheets(tmp_path):
    project = projectio.open_any(str(ROOT / "examples" / "demo_project.schematix")).project
    export, root = same_connections(project, tmp_path)
    nets = kicad_nets(root)
    assert nets["/Motor control/6"] == {("K1", "A1"), ("K1", "2"), ("S2", "2")}   # wire 6 runs into the coil
    assert {("H2", "1"), ("K1", "2.3")} == nets["/Motor control/7"]               # K1's second contact
    assert ("K1", "A2") in nets["0V"]                                             # a sheet connector, on every sheet
    k1 = [c for c in root.iter("comp") if c.get("ref") == "K1"]
    assert len(k1) == 1                                                           # coil and contacts: one part
    sheets = sorted(f for f in export.files if f.endswith(".kicad_sch"))
    assert sheets == ["exported-1-24_V_supply.kicad_sch", "exported-2-Motor_control.kicad_sch",
                      "exported-3-Hydraulics.kicad_sch", "exported.kicad_sch"]


@needs_kicad
def test_every_orientation_connects_in_kicad(tmp_path):
    """A four-terminal block in each of the eight orientations, every terminal wired to its own sheet connector:
    KiCad must find each terminal at the end of its own wire."""
    p = new_project("orientations")
    d = p.sheets[0]
    k = 0
    for rotation in (0, 90, 180, 270):
        for mirror in (False, True):
            k += 1
            x, y = 200 * (k % 4) + 200, 200 * (k // 4) + 200
            c = editing.place(d, "gen.block4", x, y, rotation=rotation, mirror=mirror)
            for name, (tx, ty) in c.terminals().items():
                dx, dy = {"l": (-20, 0), "r": (20, 0), "u": (0, -20), "d": (0, 20)}[c.terminal_dirs()[name]]
                wire(d, (tx, ty), (tx + dx, ty + dy))
                link = editing.place(d, "gen.offpage", tx + dx, ty + dy)
                link.label = f"{c.designator}_{name}"
    export, root = same_connections(p, tmp_path)
    nets = kicad_nets(root)
    for (uid, cid, name), (ref, pin) in export.pins.items():
        if not ref.startswith("#"):
            assert nets[f"{ref}_{name}"] == {(ref, pin)}


@needs_kicad
def test_ts_crossings_and_terminals_on_a_wire(tmp_path):
    """A wire ending on another's middle joins it; wires that only cross don't; a terminal lying on the middle of
    a wire isn't connected to it. The same in both programs."""
    p = new_project("geometry")
    d = p.sheets[0]
    r1 = editing.place(d, "el.resistor.iec", 100, 100)          # terminals at x 70 and 130
    r2 = editing.place(d, "el.resistor.iec", 300, 100)
    r3 = editing.place(d, "el.resistor.iec", 200, 300, rotation=90)
    wire(d, r1.terminals()["2"], r2.terminals()["1"])             # 130 -> 270 along y 100
    wire(d, r3.terminals()["1"], (200, 100))                     # a T onto the middle of that wire
    wire(d, (150, 40), (150, 200))                                # crosses it: not joined
    r4 = editing.place(d, "el.resistor.iec", 100, 200)            # terminals at x 70 and 130, y 200 ...
    wire(d, (40, 200), (160, 200))                                # ... both on the middle of this wire: not joined
    _export, root = same_connections(p, tmp_path)
    nets = kicad_nets(root)
    joined = next(nodes for nodes in nets.values() if (r1.designator, "2") in nodes)
    assert joined == {(r1.designator, "2"), (r2.designator, "1"), (r3.designator, "1")}
    assert not any((r4.designator, "1") in nodes and len(nodes) > 1 for nodes in nets.values())


@needs_kicad
def test_sheet_connectors_join_sheets_and_a_device_spans_them(tmp_path):
    p = new_project("two sheets")
    a, b = p.sheets[0], p.add_sheet("Contacts")
    coil = editing.place(a, "el.coil.iec", 100, 100)
    coil.designator = "K7"
    contact = editing.place(b, "el.contact.no.iec", 100, 100)
    contact.designator = "K7"
    contact.terminal_labels = {"1": "13", "2": "14"}
    for doc, c, name in ((a, coil, "A1"), (b, contact, "13")):
        t = c.terminals()["A1" if c is coil else "1"]
        wire(doc, t, (t[0], t[1] - 60))
        link = editing.place(doc, "gen.offpage", t[0], t[1] - 60)
        link.label = "CTRL"
    export, root = same_connections(p, tmp_path)
    assert kicad_nets(root)["CTRL"] == {("K7", "A1"), ("K7", "13")}
    assert [c.get("ref") for c in root.iter("comp")] == ["K7"]
    sheet = export.files["exported-2-Contacts.kicad_sch"]
    assert "(pin_numbers hide)" not in sheet.split("(symbol (lib_id")[0]   # its designations are shown, as in OpenSchematix


@needs_kicad
def test_designators_that_make_the_same_safe_name_get_their_own_symbols(tmp_path):
    """X1:1 and X1_1 both become the library name X1_1_device; each device must keep its own symbol, or KiCad would
    give both the pins of one."""
    p = new_project("names")
    d = p.sheets[0]
    parts = []
    for i, ref in enumerate(("X1:1", "X1:1", "X1_1", "X1_1")):
        c = editing.place(d, "el.coil.iec" if i % 2 == 0 else "el.contact.no.iec", 100 + 150 * i, 100)
        c.designator = ref
        c.props.pop("terminal", None)
        parts.append(c)
    export, root = same_connections(p, tmp_path)
    names = [line.split('"')[1] for line in export.files["OpenSchematix.kicad_sym"].splitlines()
             if line.startswith("  (symbol ")]
    assert len(names) == len(set(names)) == 2


@needs_kicad
def test_wire_numbers_name_the_nets(tmp_path):
    p = new_project("numbered")
    d = p.sheets[0]
    r1 = editing.place(d, "el.resistor.iec", 100, 100)
    r2 = editing.place(d, "el.resistor.iec", 300, 100)
    w = wire(d, r1.terminals()["2"], r2.terminals()["1"])
    netlist.assign_wire_numbers(p)
    _export, root = same_connections(p, tmp_path)
    assert kicad_nets(root)[f"/{w.number}"] == {(r1.designator, "2"), (r2.designator, "1")}


@needs_kicad
def test_names_kicad_has_to_quote(tmp_path):
    p = new_project('He said "hi" \\ there')
    d = p.sheets[0]
    c = editing.place(d, "el.lamp.iec", 100, 100)
    c.label = 'Lamp "A"\nsecond line'
    c.props["description"] = "back\\slash, semi;colon"
    _export, root = same_connections(p, tmp_path)
    comp = next(x for x in root.iter("comp") if x.get("ref") == c.designator)
    assert comp.findtext("value") == 'Lamp "A"\nsecond line'


@needs_kicad
def test_every_built_in_symbol_is_read_by_kicad(tmp_path):
    """Every symbol OpenSchematix has, placed once: KiCad reads the sheet and the library, and finds every part
    and every connection (terminals that touch)."""
    from openschematix import symbols
    p = new_project("all symbols")
    d = p.sheets[0]
    d.sheet.size = "A0"
    placed = 0
    for i, sd in enumerate(s for s in symbols.builtin_symbols() if s.id not in ("gen.offpage",)):
        editing.place(d, sd.id, 120 + (i % 30) * 150, 120 + (i // 30) * 150)
        placed += 1
    assert placed > 100
    export, root = same_connections(p, tmp_path)
    parts = {c.get("ref") for c in root.iter("comp")}
    assert parts == {ref for ref in export.references.values() if not ref.startswith("#")}
    lib = tmp_path / "OpenSchematix.kicad_sym"
    r = subprocess.run([KICAD_CLI, "sym", "export", "svg", "-o", str(tmp_path / "svg"), str(lib)],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr


@needs_kicad
def test_a_wire_attached_by_name_ends_on_its_terminal(tmp_path):
    """OpenSchematix joins a wire to the terminal it names even when the wire's end is off it (an older file, or
    a symbol changed under it); KiCad only joins what touches, so the end is written on the terminal."""
    p = new_project("attached")
    d = p.sheets[0]
    r1 = editing.place(d, "el.resistor.iec", 100, 100)
    r2 = editing.place(d, "el.resistor.iec", 300, 100)
    t1, t2 = r1.terminals()["2"], r2.terminals()["1"]
    d.add_wire(Wire(id=d.new_id(), points=[(t1[0] + 3, t1[1]), (t2[0] - 3, t2[1])], start=[r1.id, "2"],
                    end=[r2.id, "1"]))
    _export, root = same_connections(p, tmp_path)
    assert frozenset({(r1.designator, "2"), (r2.designator, "1")}) in kicad_nets(root).values()


# ------------------------------------------------------------------------------------------------------- the window

@pytest.fixture(scope="module")
def tk_root():
    import tempfile
    os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", tempfile.mkdtemp())
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Tk GUI display not available: {e}")
    yield root
    root.destroy()


@pytest.fixture
def app(tk_root, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSCHEMATIX_CONFIG_DIR", str(tmp_path / "config"))
    from openschematix.gui.app import App
    a = App(tk_root, check_recovery=False)
    yield a
    a.dirty = False
    a.recovery.end()


@pytest.mark.gui
def test_the_window_exports_and_asks_before_replacing_other_files(app, tmp_path):
    editing.place(app.doc, "el.lamp.iec", 100, 100)
    out = tmp_path / "kicad"
    out.mkdir()
    plan = app.export_kicad(str(out / "Lamp test.kicad_sch"))
    assert plan is not None and (out / "Lamp_test.kicad_sch").exists() and (out / "sym-lib-table").exists()
    before = (out / "OpenSchematix.kicad_sym").read_bytes()
    editing.place(app.doc, "el.fuse.iec", 300, 100)
    asked = []
    assert app.export_kicad(str(out / "Lamp_test.kicad_sch"),
                            confirm=lambda title, text: asked.append(text) or False) is None
    assert "OpenSchematix.kicad_sym" in asked[0]
    assert (out / "OpenSchematix.kicad_sym").read_bytes() == before            # said no: nothing written
    assert app.export_kicad(str(out / "Lamp_test.kicad_sch"), confirm=lambda title, text: True) is not None
    assert (out / "OpenSchematix.kicad_sym").read_bytes() != before


@pytest.mark.gui
def test_export_kicad_is_a_typed_command(app, monkeypatch):
    seen = []
    monkeypatch.setattr(app, "export_kicad", lambda: seen.append(True))
    app.cmd_export("kicad")
    assert seen == [True]
