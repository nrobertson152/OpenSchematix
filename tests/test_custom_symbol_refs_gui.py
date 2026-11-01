"""Undo/redo through the real application keeps wire attachments to custom-symbol pins (audit finding F1).

Covers App.import_sheets_from (File > Import sheets) and App.update_project_symbol (update a project's
symbol to the library version), each followed by undo and redo, then checks the net and that moving the
component drags its wire. Runs the real App under Tk; skipped when no display is available.
"""
import os
import tempfile

import pytest

from openschematix import projectio, symbols
from openschematix.project import new_project

from test_custom_symbol_refs import assert_connected_and_follows, sensor, wired_project

pytestmark = pytest.mark.gui      # creates a real Tk root (see tests/conftest.py)


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", tempfile.mkdtemp())
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Tk GUI display not available: {e}")
    from openschematix.gui.app import App
    a = App(root, check_recovery=False)
    yield a
    root.destroy()


@pytest.fixture
def fresh(app, monkeypatch):
    """An empty, activated project; message boxes are recorded instead of shown."""
    from openschematix.gui import app as app_mod
    shown = []
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *a, **k: shown.append(a))
    p = new_project()
    p.activate_symbols()
    app._reset(p, None)
    return shown


def find_sensor_wire(project, sid):
    for d in project.sheets:
        for c in d.components.values():
            if c.symbol == sid:
                for w in d.wires.values():
                    if w.start and w.start[0] == c.id or w.end and w.end[0] == c.id:
                        return d, c, w
    raise AssertionError("sensor wire not found")


def check_project(app, sid):
    """Make the sheet holding the sensor the first one so assert_connected_and_follows can find it."""
    d, c, w = find_sensor_wire(app.project, sid)
    app.project.sheets.remove(d)
    app.project.sheets.insert(0, d)
    u = next(x for x in d.components.values() if x.symbol == "gen.block2")
    assert w.start == [c.id, "pB"]
    assert_connected_and_follows(app.project, c.id, u.id, w.id)


def test_import_sheets_undo_redo_keeps_attachments(app, fresh, tmp_path):
    sdoc = sensor(name="Imported sensor")                 # only in the imported file: not in any library
    other, *_ = wired_project(sdoc)
    path = str(tmp_path / "other.schematix")
    projectio.save_project(other, path)
    symbols.set_project_symbols([])                       # the open project is the empty one again
    assert symbols.get(sdoc["id"]) is None
    assert app.import_sheets_from(path) == 1
    assert fresh == []
    assert len(app.project.sheets) == 2
    d, c, w = find_sensor_wire(app.project, sdoc["id"])
    assert w.start == [c.id, "pB"]
    app.undo()
    assert len(app.project.sheets) == 1
    assert symbols.get(sdoc["id"]) is None, "undo removes the imported symbol again"
    app.redo()
    assert len(app.project.sheets) == 2
    check_project(app, sdoc["id"])


def test_import_sheets_does_not_replace_the_open_projects_symbols(app, fresh, tmp_path):
    sid = "user:00000000000000cc"
    other, *_ = wired_project(sensor(("pA",), sid=sid, revision=5, name="Their version"), pin="pA")
    path = str(tmp_path / "other.schematix")
    projectio.save_project(other, path)
    mine, *_ = wired_project(sensor(sid=sid, revision=1, name="My version"))   # the open project uses it
    app._reset(mine, None)
    logged = []
    orig = app.log
    app.log = lambda msg, kind="info": (logged.append((kind, msg)), orig(msg, kind))
    try:
        app.import_sheets_from(path)
    finally:
        app.log = orig
    assert app.project.symbols[sid]["name"] == "My version"
    assert symbols.project_symbols()[sid].custom["name"] == "My version"
    assert any(k == "warning" and "Their version" in m for k, m in logged), logged


def test_update_symbol_from_library_undo_redo(app, fresh, monkeypatch):
    asked = []                       # the update disconnects pB: the user is asked first and confirms
    monkeypatch.setattr(app, "confirm_symbol_update", lambda impact, drawn, lib: asked.append(impact) or True)
    sid = "user:00000000000000dd"
    old = sensor(sid=sid, revision=0, name="Valve coil")
    p, cid, uid_comp, wid = wired_project(old)
    app._reset(p, None)
    try:
        app.userlib.create_folder("", "My symbols")
    except (OSError, ValueError):
        pass
    app.userlib.save_symbol(sensor(("pA",), sid=sid, name="Valve coil"), "My symbols")   # library drops pB
    try:
        assert app.update_project_symbol(sid) is True
        assert len(asked) == 1 and [e.pin for e in asked[0].detached] == ["pB"]
        assert app.project.sheets[0].wires[wid].start is None, "the update detaches pB (and reports it)"
        app.undo()
        assert app.project.symbols[sid]["revision"] == 0
        assert symbols.get(sid).custom["revision"] == 0
        check_project(app, sid)
        app.redo()
        assert app.project.sheets[0].wires[wid].start is None
        app.undo()
        check_project(app, sid)
    finally:
        app.userlib.delete_symbol(sid)
        app.userlib.scan()
