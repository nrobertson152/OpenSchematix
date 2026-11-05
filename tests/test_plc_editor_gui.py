"""The PLC block in the real editor: placing it, its program editor, and that a program survives everything a drawing
goes through. Runs under Tk; skipped when there is no display."""
import copy
import json
import os
import tempfile

import pytest

from openschematix import check, netlist, plc, projectio, symbols
from openschematix.model import Component, Wire
from openschematix.project import new_project

tk = pytest.importorskip("tkinter")


@pytest.fixture(scope="module")
def tk_root():
    os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", tempfile.mkdtemp())
    try:
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
    errors = []
    tk_root.report_callback_exception = lambda exc, val, tb: errors.append(val)
    yield a
    for w in list(a.windows):
        w.dirty = False
        w.destroy()
    a.recovery.end()
    assert not errors, errors


def place(app, **params):
    full = {**plc.default_params(), **params}
    c = Component(id=app.doc.new_id(), symbol="el.plc", x=400, y=400, designator="PLC1", params=full)
    app.doc.add_component(c)
    app.refresh()
    return c


def editor(app, c):
    e = app.program_plc(c.id)
    e.update()
    return e


def test_opening_the_editor_changes_nothing_until_apply(app):
    c = place(app)
    before = copy.deepcopy(c.params)
    e = editor(app, c)
    e.add_pou("st")
    e.update()
    assert c.params == before and e.dirty
    e.dirty = False
    e.close()
    assert c.params == before


def test_every_language_page_opens_and_a_program_is_kept(app):
    c = place(app)
    e = editor(app, c)
    for lang in plc.LANGUAGES:
        e.add_pou(lang)
        e.update()
        assert type(e.page).__name__ == {"ld": "LadderPage", "fbd": "FbdPage", "sfc": "SfcPage"}.get(lang, "TextPage")
    e.select_item("io")
    e.update()
    e.select_item("vars")
    e.update()
    assert e.apply()
    langs = [p["lang"] for p in c.params["program"]["pous"]]
    assert set(langs) == set(plc.LANGUAGES)


def test_apply_is_one_undo_step(app):
    c = place(app)
    e = editor(app, c)
    e.page.insert("no")
    e.page.show_props()
    n = len(app.undo_stack)
    assert e.apply()
    assert len(app.undo_stack) == n + 1
    assert c.params["program"]["pous"][0]["source"]["rungs"][0]["items"][0]["t"] == "no"
    app.undo()
    c2 = app.doc.components[c.id]
    assert not c2.params.get("program", {}).get("pous")


def test_text_page_commits_and_checks(app):
    c = place(app, tags={"I0": "Start", "Q0": "Out"})
    e = editor(app, c)
    e.add_pou("st")
    e.page.text.insert("end", "Out := Start;\nNope := 1;\n")
    e.update()
    e.page.commit()
    assert not e.run_check()
    rows = [e.problems.item(i, "values") for i in e.problems.get_children()]
    assert any("Nope" in r[2] for r in rows)
    e.page.text.delete("1.0", "end")
    e.page.text.insert("1.0", "Out := Start;\n")
    e.page.commit()
    assert e.run_check()


def test_highlighting_copes_with_every_language(app, monkeypatch):
    from openschematix.gui import plc_editor
    monkeypatch.setattr(plc_editor.messagebox, "askokcancel", lambda *a, **k: True)
    c = place(app)
    e = editor(app, c)
    for lang in ("st", "c", "python"):
        e.add_pou(lang)
        e.page._example()
        e.page._highlight()
        e.update()
        e.page.commit()
    # the shipped examples are correct programs, given the tags they use
    e.params["tags"] = {"I0": "Start", "I1": "Stop", "Q0": "Run", "Q1": "Y1"}
    e.select_item("pou0")
    e.update()
    assert e.run_check(), [e.problems.item(i, "values") for i in e.problems.get_children()]


def test_ladder_page_builds_a_latch_that_runs(app):
    c = place(app, tags={"I0": "Start", "I1": "Stop", "Q0": "Run"})
    e = editor(app, c)
    p = e.page
    p.insert("no")
    p._selected_element()["a"] = "Start"
    p.branch()
    p.insert("no")
    p._selected_element()["a"] = "Run"
    # back up to the parallel element, then on along the rung
    p.sel = ((0,), 0)
    p.insert("nc")
    p._selected_element()["a"] = "Stop"
    p.insert("coil")
    p._selected_element()["a"] = "Run"
    p.draw()
    e.update()
    assert e.run_check(), [e.problems.item(i, "values") for i in e.problems.get_children()]
    rt = plc.compile_params(e.params)
    rt.set_input("I0", True)
    rt.scan()
    rt.set_input("I0", False)
    rt.scan()
    assert rt.read("Run") is True
    rt.set_input("I1", True)
    rt.scan()
    assert rt.read("Run") is False


def test_ladder_editing_delete_shift_rungs_and_clicks(app):
    c = place(app)
    e = editor(app, c)
    p = e.page
    p.add_rung()
    assert len(p.rungs) == 2
    p.insert("no")
    p.insert("nc")
    p.shift(-1)
    assert [x["t"] for x in p.rungs[1]["items"]] == ["nc", "no"]
    p.sel = ((1,), 0)
    p.branch()
    p.insert("rise")
    assert p.rungs[1]["items"][0]["t"] == "par"
    p.delete()                  # the contact on the new branch
    p._delete_empty_branch()    # and the now empty branch: the parallel collapses
    assert p.rungs[1]["items"][0]["t"] == "nc"
    p.move_rung(-1)
    assert p.rungs[0]["items"][0]["t"] == "nc"
    p.draw()
    x0, y0, x1, y1, ref = next(h for h in p.hits if h[4][1] != "rung")
    p._click(type("E", (), {"x": (x0 + x1) / 2, "y": (y0 + y1) / 2})())
    assert p.sel == ref
    for t in ("cmp", "ton", "tof", "tp", "ctu", "ctd", "move", "st", "coil", "ncoil", "set", "reset", "fall"):
        p.insert(t)
        p.show_props()
        e.update()
    p.del_rung()
    p.del_rung()
    assert p.rungs and not p.rungs[0]["items"]


def test_fbd_page_wires_by_dragging_and_runs(app):
    c = place(app, tags={"I0": "Start", "Q0": "Out"})
    e = editor(app, c)
    e.add_pou("fbd")
    p = e.page
    e.program["pous"].pop(0)        # just this program
    e._fill_tree()
    e.selected = "pou0"
    for t, field, value in (("input", "expr", "Start"), ("NOT", None, None), ("output", "target", "Out")):
        p.palette.selection_set(f"p:{t}")
        p._palette_pick(None)
        if field:
            p.src["blocks"][-1][field] = value
    a, b, o = p.src["blocks"]
    b["x"], o["x"] = 240, 400
    a["y"] = b["y"] = o["y"] = 40
    p.draw()

    def drag(src, pin, side, dst, dst_pin, dst_side):
        x0, y0 = p._pin_xy(src, pin, side)
        x1, y1 = p._pin_xy(dst, dst_pin, dst_side)
        p._press(type("E", (), {"x": x0, "y": y0})())
        p._motion(type("E", (), {"x": x1, "y": y1})())
        p._release(type("E", (), {"x": x1, "y": y1})())
    drag(a, "OUT", "out", b, "IN", "in")
    drag(o, "IN", "in", b, "OUT", "out")        # either way round
    assert {tuple(w["from"]): tuple(w["to"]) for w in p.src["wires"]} == {(a["id"], "OUT"): (b["id"], "IN"), (b["id"], "OUT"): (o["id"], "IN")}
    assert e.run_check(), [e.problems.item(i, "values") for i in e.problems.get_children()]
    rt = plc.compile_params(e.params)
    rt.scan()
    assert rt.read("Out") is True
    rt.set_input("I0", True)
    rt.scan()
    assert rt.read("Out") is False
    # moving a block by dragging, selecting a wire and deleting
    x0, y0, x1, y1 = p._rect(b)
    p._press(type("E", (), {"x": x0 + 5, "y": y0 + 5})())
    p._motion(type("E", (), {"x": x0 + 45, "y": y0 + 105})())
    p._release(type("E", (), {"x": x0 + 45, "y": y0 + 105})())
    assert b["x"] == 280 and b["y"] == 140
    p.show_props()
    e.update()
    path = p._wire_path(p.src["wires"][0])
    p._press(type("E", (), {"x": path[0] + 2, "y": path[1]})()) if False else None
    p.sel = ("wire", p.src["wires"][0])
    p.delete_selected()
    assert len(p.src["wires"]) == 1
    p.sel = ("block", b["id"])
    p.show_props()
    p.delete_selected()
    assert not p.src["wires"] and len(p.src["blocks"]) == 2


def test_sfc_page_builds_a_sequence_that_runs(app):
    c = place(app, tags={"I0": "Start", "Q0": "Out"})
    e = editor(app, c)
    e.add_pou("sfc")
    e.program["pous"].pop(0)
    e._fill_tree()
    e.selected = "pou0"
    p = e.page
    assert p._step(1)["initial"]
    p.sel = ("step", 1)
    p.add_step_after()
    second = p.sel[1]
    p.src["transitions"][0]["cond"] = "Start"
    p._step(second)["actions"].append({"q": "N", "target": "Out"})
    p.add_parallel()
    p.draw()
    p.show_props()
    e.update()
    p.sel = ("trans", p.src["transitions"][0]["id"])
    p.show_props()
    e.update()
    p.sel = ("step", second)
    p.add_transition()
    p.src["transitions"][-1]["to"] = [1]
    p.src["transitions"][-1]["cond"] = "NOT Start"
    p.draw()
    e.update()
    assert e.run_check(), [e.problems.item(i, "values") for i in e.problems.get_children()]
    rt = plc.compile_params(e.params)
    rt.set_input("I0", True)
    rt.scan()
    rt.scan()
    assert rt.read("Out") is True and rt.read(p._step(second)["name"]) is True
    x0, y0, x1, y1, ref = next(h for h in p.hits if h[4][0] == "step")
    p._click(type("E", (), {"x": (x0 + x1) / 2, "y": (y0 + y1) / 2})())
    assert p.sel == ref
    p.sel = ("step", second)
    p.delete_selected()
    assert second not in [s["id"] for s in p.src["steps"]]


def test_io_page_changes_the_block_and_warns_before_dropping_wired_pins(app, monkeypatch):
    c = place(app)
    t = c.terminals()["I5"]
    w = Wire(id=app.doc.new_id(), points=[t, (t[0] - 40, t[1])], start=[c.id, "I5"])
    app.doc.add_wire(w)
    e = editor(app, c)
    e.select_item("io")
    e.update()
    e.page._tag("I0", "Start")
    e.page.counts["di"].set(4)
    e.page._count("di", e.page.counts["di"])
    e.update()
    asked = []
    from openschematix.gui import plc_editor
    monkeypatch.setattr(plc_editor.messagebox, "askokcancel", lambda *a, **k: (asked.append(a), False)[1])
    assert e.apply() is False                   # refused: nothing changes
    assert asked and "I5" in asked[0][1] and len(c.terminal_defs()) > 10 and w.start == [c.id, "I5"]
    monkeypatch.setattr(plc_editor.messagebox, "askokcancel", lambda *a, **k: True)
    assert e.apply()
    assert "I5" not in app.doc.components[c.id].terminals() and app.doc.wires[w.id].start is None
    assert app.doc.components[c.id].params["tags"]["I0"] == "Start"


def test_wires_stay_attached_when_the_block_grows(app):
    c = place(app)
    t = c.terminals()["Q0"]
    w = Wire(id=app.doc.new_id(), points=[t, (t[0] + 60, t[1])], start=[c.id, "Q0"])
    app.doc.add_wire(w)
    e = editor(app, c)
    e.select_item("io")
    e.update()
    e.page.counts["di"].set(16)
    e.page._count("di", e.page.counts["di"])
    assert e.apply()
    c = app.doc.components[c.id]
    assert len([n for n in c.terminals() if n.startswith("I") and n[1:].isdigit()]) == 16
    assert app.doc.wires[w.id].start == [c.id, "Q0"]
    assert tuple(app.doc.wires[w.id].points[0]) == tuple(c.terminals()["Q0"])


def test_test_panel_runs_the_program(app):
    c = place(app, tags={"I0": "Start", "Q0": "Out"})
    e = editor(app, c)
    e.add_pou("st")
    e.page.text.insert("end", "Out := Start;\n")
    e.page.commit()
    e.program["pous"].pop(0)
    e._fill_tree()
    e.selected = "pou0"
    panel = e.test
    panel.start()
    assert panel.running and e.runtime is not None
    panel.in_vars["I0"][1].set(True)
    panel._tick()
    assert e.runtime.read("Out") is True
    assert "ON" in [panel.watch.set(i, "value") for i in panel.watch.get_children()]
    panel.stop()
    assert e.runtime is None and not panel.running


def test_test_panel_refuses_a_broken_program_and_shows_a_fault(app):
    c = place(app)
    e = editor(app, c)
    e.add_pou("st")
    e.page.text.insert("end", "Nope := 1;\n")
    e.page.commit()
    e.program["pous"].pop(0)
    e._fill_tree()
    e.selected = "pou0"
    e.test.start()
    assert not e.test.running
    e.page.text.delete("1.0", "end")
    e.page.text.insert("1.0", "WHILE TRUE DO Q1 := TRUE; END_WHILE;\n")
    e.page.commit()
    e.test.start()
    e.test._tick()
    assert not e.test.running and "watchdog" in e.test.state.cget("text")


def test_live_view_draws_while_testing(app):
    c = place(app, tags={"I0": "Start", "Q0": "Out"})
    e = editor(app, c)
    p = e.page
    p.insert("no")
    p._selected_element()["a"] = "Start"
    p.insert("ton")
    p.insert("coil")
    p._selected_element()["a"] = "Out"
    e.test.start()
    e.test._tick()
    e.update()
    assert p.rt is e.runtime
    e.test.stop()
    assert p.rt is None


def test_problem_list_jumps_to_the_line(app):
    c = place(app)
    e = editor(app, c)
    e.add_pou("st")
    idx = e.current_pou_index()
    e.page.text.insert("1.0", "\n\nNope := 1;\n")
    e.page.commit()
    e.select_item("io")
    e.update()
    e.run_check()
    iid = next(i for i, d in e._problem_map.items() if "Nope" in d.message)
    e.problems.selection_set(iid)
    e._go_to_problem(None)
    assert e.current_pou_index() == idx and e.page.text.index("insert").startswith(str(e._problem_map[iid].line))


def test_inspector_offers_program_plc_and_double_click_opens_it(app):
    c = place(app)
    app.select_only(c.id) if hasattr(app, "select_only") else app.selection.add(c.id)
    app.refresh()
    app.configure_symbol(c.id)
    assert any(type(w).__name__ == "PlcEditor" for w in app.windows)
    first = next(w for w in app.windows if type(w).__name__ == "PlcEditor")
    assert app.program_plc(c.id) is first       # one window per block


def test_block_deleted_while_the_editor_is_open(app, monkeypatch):
    c = place(app)
    e = editor(app, c)
    del app.doc.components[c.id]
    from openschematix.gui import plc_editor
    shown = []
    monkeypatch.setattr(plc_editor.messagebox, "showerror", lambda *a, **k: shown.append(a))
    assert e.apply() is False and shown


# ---------------------------------------------------------------- the block in a drawing, no window needed
def sample_params():
    return {**plc.default_params(), "tags": {"I0": "Start", "Q0": "Out"},
            "program": {"scan_ms": 20, "io": {"AI0": {"signal": "4-20mA", "lo": 0, "hi": 250, "note": "tank"}},
                        "vars": [{"name": "Count", "type": "INT", "init": "3", "note": ""}],
                        "pous": [{"name": "A", "lang": "st", "source": "Out := Start;"},
                                 {"name": "B", "lang": "ld", "source": {"rungs": [{"items": [{"t": "no", "a": "Start"}]}]}},
                                 {"name": "C", "lang": "python", "source": "x = 1\n"}]}}


def sample_project():
    project = new_project()
    doc = project.sheets[0]
    doc.add_component(Component(id=1, symbol="el.plc", x=400, y=400, designator="PLC1", params=sample_params()))
    return project


def test_program_survives_save_reopen_with_every_byte(tmp_path):
    project = sample_project()
    path = str(tmp_path / "p.schematix")
    projectio.save_project(project, path)
    back = projectio.open_any(path, activate=True).project
    assert back.sheets[0].components[1].params == sample_params()


def test_program_survives_legacy_export_and_copy(tmp_path):
    doc = sample_project().sheets[0]
    assert doc.copy().components[1].params == sample_params()
    assert json.loads(json.dumps(doc.to_dict()))["components"][0]["params"] == sample_params()


def test_older_files_and_missing_symbol_keep_the_program(tmp_path):
    """A release that doesn't know el.plc shows a placeholder; its params and wires must still survive a save."""
    d = {"uid": "a", "name": "S", "components": [{"id": 1, "symbol": "el.plc.from.the.future", "x": 0, "y": 0,
                                                  "params": sample_params()}], "wires": []}
    from openschematix.model import Document
    back = Document.from_dict(d)
    assert back.to_dict()["components"][0]["params"] == sample_params()


def test_geometry_ignores_the_program_and_follows_the_io():
    a = symbols.geometry("el.plc", sample_params())
    other = sample_params()
    other["program"]["scan_ms"] = 99
    assert symbols.geometry("el.plc", other) is a               # cached: a program edit doesn't rebuild the symbol
    names = [t.name for t in a.terminals]
    assert {"I0", "I7", "Q5", "AI1", "AO0", "L+", "M"} <= set(names) and "C" not in names
    relay = symbols.geometry("el.plc", {**sample_params(), "do_type": "relay"})
    assert "C" in [t.name for t in relay.terminals]
    text = [p["s"] for p in a.prims if p["k"] == "text"]
    assert "I0 Start" in text and "Out Q0" in text


@pytest.mark.parametrize("bad", [{"di": 10 ** 12}, {"di": -1, "do": -1, "ai": -1, "ao": -1}, {"tags": {"I0": "x" * 500}}, {"do_type": 5}])
def test_block_geometry_copes_with_anything_a_file_says(bad):
    g = symbols.get("el.plc").build(bad)
    assert len(g.terminals) <= 4 * plc.MAX_IO + 3
    from openschematix.symbols.base import validate_geometry
    assert not validate_geometry(g)


def test_pins_join_the_netlist_and_are_typed():
    project = sample_project()
    doc = project.sheets[0]
    c = doc.components[1]
    t = c.terminals()["I0"]
    doc.add_wire(Wire(id=2, points=[t, (t[0] - 40, t[1])], start=[1, "I0"]))
    nets = netlist.compute_nets(project)
    assert any((doc.uid, 1, "I0") in n.terminals for n in nets)
    sd = symbols.get("el.plc")
    types = {x.name: sd.port_type(x) for x in c.geometry().terminals}
    assert types["I0"] == "elec.input" and types["Q0"] == "elec.output" and types["L+"] == "elec.power" and types["M"] == "elec.ground"


def test_check_drawing_reports_program_problems():
    project = sample_project()
    project.sheets[0].components[1].params["program"]["pous"][0]["source"] = "Nope := 1;"
    found = [i for i in check.check(project, rules={"plc"})]
    assert found and found[0].severity == "error" and "Nope" in found[0].message and "PLC1" in found[0].message


def test_check_drawing_is_quiet_about_a_good_program():
    assert not check.check(sample_project(), rules={"plc"})


def test_scripting_api_can_place_and_configure_a_plc(tmp_path):
    from openschematix import api
    project = api.new_project("t")
    sheet = project.sheets[0]
    c = sheet.place("el.plc", 400, 400, params={"di": 2, "do": 2, "ai": 0, "ao": 0, "tags": {"I0": "Go"},
                                                "program": {"pous": [{"name": "M", "lang": "st", "source": "Q0 := Go;"}]}})
    assert c.terminal("I1").position and c.designator.startswith("PLC")
    path = str(tmp_path / "x.schematix")
    project.save(path)
    assert not plc.check(api.open_project(path).sheets[0].components()[0].params)
