"""The symbol editor opens the open project's own definition of a symbol.

Two projects may embed different definitions under the same custom-symbol
id. The process-wide registry holds the symbols of the project activated
last, which need not be the project open in the application (for example
after projectio.open_any() of another file, as scripts and the scripting
API do). Every editor entry point must resolve the symbol through the open
project (App.project_symbol -> Project.symbol_resolver), and editing a copy
must preserve the symbol through save and reopen.

Runs under Tk; skipped when no display is available.
"""
import copy
import os
import tempfile

import pytest

from openschematix import editing, projectio, symbols
from openschematix.connectivity import analyse
from openschematix.model import Wire
from openschematix.project import new_project
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef

SID = "user:editor-scope-shared"


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
    for w in list(a.windows):
        try:
            w.destroy()
        except Exception:  # noqa: BLE001
            pass
    root.destroy()


@pytest.fixture
def quiet(monkeypatch):
    """Record dialogs; answer "No" to "Update drawings?" after saving."""
    from openschematix.gui import app as app_mod, symbol_editor
    shown = []
    for mod in (app_mod, symbol_editor):
        monkeypatch.setattr(mod.messagebox, "showerror", lambda *a, **k: shown.append(("error", a)))
        monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: shown.append(("info", a)))
        monkeypatch.setattr(mod.messagebox, "askyesno", lambda *a, **k: False)
    return shown


def definition(reach, second, name, **meta):
    d = blank_symbol(name)
    d.update(id=SID, description=f"{name} description", prefix="S", category="Electrical", group="Sensors",
             tags=["scope", name.split()[0].lower()], properties={"manufacturer": f"{name} Ltd"}, **meta)
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}, {"k": "line", "pts": [[-reach, 0], [-10, 0]]},
                  {"k": "line", "pts": [[10, 0], [reach, 0]]}]
    d["pins"] = [{"id": "A", "name": "A", "x": -reach, "y": 0, "dir": "l"},
                 {"id": second, "name": second, "x": reach, "y": 0, "dir": "r"}]
    return normalise(d)


def project_file(tmp_path, name, sdoc, wired_pin):
    """A project embedding `sdoc`, with a wire from `wired_pin` to a resistor."""
    symbols.set_project_symbols([to_symdef(sdoc)])
    p = new_project(name)
    p.symbols[SID] = copy.deepcopy(sdoc)
    doc = p.sheets[0]
    c = editing.place(doc, SID, 200, 200)
    r = editing.place(doc, "el.resistor.iec", 500, 200)
    w = Wire(doc.new_id(), [c.terminals()[wired_pin], r.terminals()["1"]], [c.id, wired_pin], [r.id, "1"])
    doc.add_wire(w)
    editing.reroute(doc, w)
    path = str(tmp_path / f"{name}.schematix")
    projectio.save_project(p, path)
    symbols.set_project_symbols([])
    return path, c.id, w.id


@pytest.fixture
def open_a_with_b_registered(app, tmp_path, quiet):
    """The application has project A open; the registry holds B's version."""
    a_def = definition(20, "B", "Alpha")
    b_def = definition(40, "Q", "Bravo")
    path_a, cid, wid = project_file(tmp_path, "Alpha", a_def, "B")
    path_b, _c, _w = project_file(tmp_path, "Bravo", b_def, "Q")
    app.open_path(path_a, confirm=False)
    projectio.open_any(path_b)                       # default: registers B's symbols
    assert symbols.get(SID).custom["description"] == "Bravo description"
    yield app, a_def, cid, wid
    for w in list(app.windows):
        if w.winfo_exists() and w.__class__.__name__ == "SymbolEditor":
            w.dirty = False
            w.destroy()


def pins(meta):
    return [(p["id"], p["x"], p["y"], p["dir"]) for p in meta["pins"]]


def editors(app):
    return [w for w in app.windows if w.__class__.__name__ == "SymbolEditor" and w.winfo_exists()]


# ---------------------------------------------------------------- resolution through the open project
def test_project_symbol_resolves_the_open_projects_definition(open_a_with_b_registered):
    app, a_def, _cid, _wid = open_a_with_b_registered
    sd = app.project_symbol(SID)
    assert sd.custom["description"] == "Alpha description" and [t.name for t in sd.build().terminals] == ["A", "B"]


@pytest.mark.parametrize("entry", ["edit_symbol_copy", "open_symbol_editor", "edit_custom_symbol", "open_existing"])
def test_every_editor_entry_point_opens_the_open_projects_definition(open_a_with_b_registered, entry):
    app, a_def, _cid, _wid = open_a_with_b_registered
    if entry == "edit_symbol_copy":
        ed = app.edit_symbol_copy(SID)
    elif entry == "open_symbol_editor":
        ed = app.open_symbol_editor(copy_of=SID)
    elif entry == "edit_custom_symbol":
        app.edit_custom_symbol(SID)
        ed = editors(app)[-1]
    else:
        start = app.open_symbol_editor()
        ed = start.open_existing(SID)
    assert ed is not None
    assert pins(ed.meta) == pins(a_def)                       # not B's (x = 40, pin Q)
    assert ed.meta["description"] == "Alpha description"
    assert ed.meta["prims"] == a_def["prims"]


def test_entry_points_refuse_a_symbol_the_open_project_cannot_see(open_a_with_b_registered, quiet):
    """A custom id known only to the registered other project is not
    'available' to the open project."""
    app, _a_def, _cid, _wid = open_a_with_b_registered
    other = dict(definition(40, "Q", "Other"), id="user:only-in-other-project")
    symbols.add_project_symbol(to_symdef(other))
    assert app.project_symbol(other["id"]) is None
    assert app.edit_symbol_copy(other["id"]) is None
    start = app.open_symbol_editor()
    assert start.open_existing(other["id"]) is None
    assert any("not available" in str(a) for _kind, a in quiet)


def test_user_library_symbols_still_open(app, tmp_path, quiet, monkeypatch):
    lib_def = dict(definition(30, "B", "Library"), id="user:editor-scope-library")
    symbols.set_user_symbols([to_symdef(lib_def)])
    app.project.symbols.pop(lib_def["id"], None)
    ed = app.edit_symbol_copy(lib_def["id"])
    assert ed is not None and pins(ed.meta) == pins(lib_def)
    ed.dirty = False
    ed.destroy()


def test_built_in_symbols_still_open(app, quiet):
    ed = app.edit_symbol_copy("el.resistor.iec")
    assert ed is not None and {p["id"] for p in ed.meta["pins"]} == {"1", "2"}
    ed.dirty = False
    ed.destroy()


# ---------------------------------------------------------------- fidelity: copy -> save -> place -> save -> reopen
HAS_PR46 = hasattr(symbols, "project_owner")


def save_copy_and_place(app, a_def):
    """Edit a copy of SID, save it to the library, place it next to the
    original with a wire on pin B. Returns (new doc, component id, wire id)."""
    ed = app.edit_symbol_copy(SID)
    assert ed.save() is True
    new = copy.deepcopy(ed.meta)
    ed.dirty = False
    ed.destroy()
    doc = app.project.sheets[0]
    c2 = editing.place(doc, new["id"], 200, 500)
    r2 = editing.place(doc, "el.resistor.iec", 500, 500)
    w2 = Wire(doc.new_id(), [c2.terminals()["B"], r2.terminals()["1"]], [c2.id, "B"], [r2.id, "1"])
    doc.add_wire(w2)
    editing.reroute(doc, w2)
    return new, c2.id, w2.id


def assert_reopened(app, path, a_def, new, wired):
    projectio.open_any(str(os.path.join(os.path.dirname(path), "Bravo.schematix")))   # B registered again
    app.open_path(path, confirm=False)
    p = app.project
    assert p.symbols[SID]["pins"] == a_def["pins"]              # the original kept its own definition
    assert p.symbols[new["id"]]["pins"] == a_def["pins"]        # the copy is embedded with identical geometry
    d = p.sheets[0]
    for comp_id, wire_id in wired:
        w = d.wires[wire_id]
        assert w.start == [comp_id, "B"]                         # attachment kept (PR #37)
        assert w.points[0] == d.components[comp_id].terminals()["B"]
    assert analyse(d).open_wire_ends == []


def test_edited_copy_round_trips_through_library_and_project(open_a_with_b_registered, tmp_path):
    """Normal application state: the open project is the registered one when it is saved."""
    app, a_def, cid, wid = open_a_with_b_registered
    app.project.activate_symbols()                               # as after any action in the application
    new, c2, w2 = save_copy_and_place(app, a_def)
    assert new["id"] != SID and new["revision"] >= 1
    for key in ("prims", "pins", "description", "prefix", "category", "group", "tags", "properties"):
        assert new[key] == a_def[key], key
    assert not new.get("aliases")                                # copies never take the original's aliases
    path = str(tmp_path / "round-trip.schematix")
    projectio.save_project(app.project, path)
    assert_reopened(app, path, a_def, new, [(cid, wid), (c2, w2)])


@pytest.mark.skipif(not HAS_PR46, reason="needs PR #46 (a project never embeds another project's definition)")
def test_saving_while_another_project_is_registered_keeps_the_definitions(open_a_with_b_registered, tmp_path):
    """Same round trip, but B's symbols are still registered when A is saved.
    Without PR #46, Project.embed_symbols writes B's definition into A's file."""
    app, a_def, cid, wid = open_a_with_b_registered
    new, c2, w2 = save_copy_and_place(app, a_def)
    projectio.open_any(str(tmp_path / "Bravo.schematix"))        # B registered at save time
    path = str(tmp_path / "round-trip.schematix")
    projectio.save_project(app.project, path)
    assert_reopened(app, path, a_def, new, [(cid, wid), (c2, w2)])


# ---------------------------------------------------------------- in-place edits never write an older embedded copy into the library
# Review finding on #39 (Issue #56): "Edit symbol" edits a library symbol in place, and UserLibrary.save_symbol()
# stores whatever the editor holds as the library's next revision. Starting from the open project's embedded
# copy (an older revision than the library's) would silently replace the newer library geometry.
LIB_SID = "user:editor-scope-library-vs-embedded"


@pytest.fixture
def library_newer_than_project(app, tmp_path, quiet):
    """The library holds revision 2 of LIB_SID (pin B at x=30); the open
    project embeds revision 1 (pin B at x=20) and draws it."""
    v1 = dict(definition(20, "B", "Older"), id=LIB_SID)
    v2 = dict(definition(30, "B", "Newer"), id=LIB_SID)
    folder = "Scope tests"
    os.makedirs(app.userlib.abs(folder), exist_ok=True)
    app.userlib.save_symbol(copy.deepcopy(v1), folder)                  # library revision 1
    entry = app.userlib.save_symbol(copy.deepcopy(v2), folder)          # library revision 2
    assert entry.doc["revision"] == 2
    embedded = copy.deepcopy(v1)
    embedded["revision"] = 1
    p = new_project("Draws revision 1")
    p.symbols[LIB_SID] = embedded
    p.activate_symbols()
    c = editing.place(p.sheets[0], LIB_SID, 200, 200)
    path = str(tmp_path / "older.schematix")
    projectio.save_project(p, path)
    app.open_path(path, confirm=False)
    assert app.project.symbols[LIB_SID]["pins"][1]["x"] == 20             # the drawing keeps revision 1
    yield app, v2, c.id
    for w in list(app.windows):
        if w.winfo_exists() and w.__class__.__name__ == "SymbolEditor":
            w.dirty = False
            w.destroy()
    if LIB_SID in app.userlib.entries:
        app.userlib.delete_symbol(LIB_SID)


def _assert_library_edit(app, ed, v2):
    """The editor holds the library's revision 2; saving keeps its geometry."""
    assert ed.meta["id"] == LIB_SID and ed.meta["revision"] == 2
    assert pins(ed.meta) == pins(v2) and ed.meta["prims"] == v2["prims"]
    assert ed.save() is True
    lib = app.userlib.entries[LIB_SID].doc
    assert lib["revision"] == 3 and pins(lib) == pins(v2) and lib["prims"] == v2["prims"]
    assert app.project.symbols[LIB_SID]["pins"][1]["x"] == 20             # the drawing still keeps revision 1


def test_edit_symbol_on_a_placed_component_edits_the_library_revision(library_newer_than_project):
    app, v2, _cid = library_newer_than_project
    app.edit_custom_symbol(LIB_SID)
    _assert_library_edit(app, editors(app)[-1], v2)


def test_library_panel_edit_edits_the_library_revision(library_newer_than_project, monkeypatch):
    app, v2, _cid = library_newer_than_project
    # the panel's own selection (registry-backed: it returns the open project's embedded revision 1)
    monkeypatch.setattr(app.library, "selected_symbol_id", lambda: LIB_SID)
    assert app.library.selected_symbol().custom["revision"] == 1
    app.library.edit_selected()
    _assert_library_edit(app, editors(app)[-1], v2)


def test_edit_a_copy_of_a_placed_component_uses_the_embedded_revision(library_newer_than_project):
    """'Edit a copy' copies what the drawing shows; the library is untouched."""
    app, v2, _cid = library_newer_than_project
    ed = app.edit_symbol_copy(LIB_SID)
    assert ed.meta["id"] != LIB_SID and ed.meta["pins"][1]["x"] == 20
    assert ed.save() is True
    lib = app.userlib.entries[LIB_SID].doc
    assert lib["revision"] == 2 and pins(lib) == pins(v2)


def test_edit_symbol_of_a_project_only_symbol_adds_it_to_the_library(app, tmp_path, quiet):
    """No library version exists to overwrite: the embedded definition is
    edited and saving adds it to the library under the same id."""
    sid = "user:editor-scope-project-only"
    sdoc = dict(definition(20, "B", "Project only"), id=sid)
    p = new_project("Project only")
    p.symbols[sid] = copy.deepcopy(sdoc)
    p.activate_symbols()
    editing.place(p.sheets[0], sid, 200, 200)
    path = str(tmp_path / "project-only.schematix")
    projectio.save_project(p, path)
    app.open_path(path, confirm=False)
    assert sid not in app.userlib.entries
    app.edit_custom_symbol(sid)
    ed = editors(app)[-1]
    assert ed.meta["id"] == sid and pins(ed.meta) == pins(sdoc) and ed.is_new
    assert ed.save() is True
    assert pins(app.userlib.entries[sid].doc) == pins(sdoc)
    ed.dirty = False
    ed.destroy()


def test_in_place_and_copy_edits_ignore_another_registered_project(library_newer_than_project, tmp_path):
    """A third definition of the same id, registered by another project, is
    used by neither edit: in place edits the library's revision, a copy uses
    the open project's embedded revision."""
    app, v2, _cid = library_newer_than_project
    other = dict(definition(40, "Q", "Foreign"), id=LIB_SID, revision=7)
    q = new_project("Foreign")
    q.symbols[LIB_SID] = other
    q.activate_symbols()
    editing.place(q.sheets[0], LIB_SID, 100, 100)
    path = str(tmp_path / "foreign.schematix")
    projectio.save_project(q, path)
    projectio.open_any(path)                                   # registers the foreign definition
    assert symbols.get(LIB_SID).custom["description"] == "Foreign description"
    copy_ed = app.edit_symbol_copy(LIB_SID)
    assert copy_ed.meta["pins"][1]["x"] == 20                   # the open project's revision 1
    copy_ed.dirty = False
    copy_ed.destroy()
    app.edit_custom_symbol(LIB_SID)
    _assert_library_edit(app, editors(app)[-1], v2)            # the library's revision 2
