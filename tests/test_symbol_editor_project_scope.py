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
    # The project draws a different definition than the library's: "Edit symbol" asks first (Issue #61
    # D3). These tests choose "Edit the library symbol" and check that the dialog was shown.
    app.collision_answers = []
    app.ask_symbol_collision = lambda sid, drawn, lib, diffs: app.collision_answers.append(sid) or "library"
    yield app, v2, c.id
    del app.ask_symbol_collision
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
    assert app.collision_answers == [LIB_SID]
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


# ---------------------------------------------------------------- integration with project-scoped symbols (Issue #61)
# After PR #46 (owner-scoped registry), #47 (save rollback), #48 and #58 were merged into #39: editing in the
# application must never let one project's definition of an id leak into another project's file, revision
# snapshot, BOM, netlist, check or export, and must never write an older or foreign definition into the library.
from openschematix import bom, check as erc, export, revisions  # noqa: E402
from openschematix.netlist import compute_nets  # noqa: E402


def library_state(app):
    return {sid: (e.doc.get("revision"), pins(e.doc), copy.deepcopy(e.doc["prims"]))
            for sid, e in app.userlib.entries.items()}


def drop_library(app, *sids):
    for sid in sids:
        if sid in app.userlib.entries:
            app.userlib.delete_symbol(sid)


def wired_pins(project, sid):
    """Names of the connected terminals of components drawn with `sid`."""
    out = set()
    for n in compute_nets(project):
        if len(n.terminals) < 2:
            continue
        for uid, cid, name in n.terminals:
            if project.find_sheet(uid).components[cid].symbol == sid:
                out.add(name)
    return out


def engine_outputs(project):
    """Everything the engine derives from a project's drawings."""
    d = project.sheets[0]
    items, extent = export.paper_items(d, project=project)
    return {
        "bom": [line.to_row() if hasattr(line, "to_row") else vars(line) for line in bom.generate(project)],
        "nets": sorted(sorted(map(tuple, n.terminals)) for n in compute_nets(project)),
        "check": sorted((i.severity, i.code, i.message, i.obj_id) for i in erc.check(project)),
        "svg": export.to_svg(d, project=project),
        "paper": (repr(items), extent),
    }


@pytest.fixture
def two_projects_edited(app, tmp_path, quiet):
    """Projects Alpha and Bravo both draw SID with different geometry (Alpha:
    pins A/B, reach 20; Bravo: pins A/Q, reach 40). With Alpha open and
    Bravo's definition registered, Alpha's SID is edited in place (it is
    project-only, so saving adds it to the library under SID with Alpha's
    geometry) and a copy is edited, saved and placed; Alpha is then saved."""
    a_def = definition(20, "B", "Alpha")
    b_def = definition(40, "Q", "Bravo")
    path_a, cid, wid = project_file(tmp_path, "Alpha", a_def, "B")
    path_b, _c, _w = project_file(tmp_path, "Bravo", b_def, "Q")
    with open(path_b, "rb") as f:
        b_bytes = f.read()
    drop_library(app, SID)
    app.open_path(path_a, confirm=False)
    projectio.open_any(path_b)                                     # Bravo's definition registered
    before = library_state(app)
    app.edit_custom_symbol(SID)                                    # project-only: in place, embedded source
    ed = editors(app)[-1]
    assert pins(ed.meta) == pins(a_def) and ed.save() is True
    ed.dirty = False
    ed.destroy()
    new, c2, w2 = save_copy_and_place(app, a_def)
    projectio.open_any(path_b)                                     # Bravo registered again at save time
    projectio.save_project(app.project, path_a)
    yield dict(app=app, a_def=a_def, b_def=b_def, path_a=path_a, path_b=path_b, b_bytes=b_bytes,
               before=before, copy=new, wired=[(cid, wid), (c2, w2)])
    for w in list(app.windows):
        if w.winfo_exists() and w.__class__.__name__ == "SymbolEditor":
            w.dirty = False
            w.destroy()
    drop_library(app, SID, new["id"])


def test_project_only_edit_keeps_project_scope_and_only_adds_its_own_library_entry(two_projects_edited):
    t = two_projects_edited
    app, a_def = t["app"], t["a_def"]
    after = library_state(app)
    added = set(after) - set(t["before"])
    assert added == {SID, t["copy"]["id"]}                         # nothing else created
    assert {k: after[k] for k in t["before"]} == t["before"]       # nothing existing replaced
    assert pins(app.userlib.entries[SID].doc) == pins(a_def)       # Alpha's geometry, never Bravo's
    assert app.project.symbols[SID]["pins"] == a_def["pins"]       # drawing kept ("Update drawings?" = No)
    with open(t["path_b"], "rb") as f:
        assert f.read() == t["b_bytes"]                            # the other project's file is untouched


def test_editing_a_copy_never_overwrites_the_original(two_projects_edited):
    t = two_projects_edited
    app, new = t["app"], t["copy"]
    assert new["id"] != SID
    assert app.userlib.entries[SID].doc["revision"] == 1           # the in-place save only; the copy left it alone
    assert pins(app.userlib.entries[SID].doc) == pins(t["a_def"])
    assert app.project.symbols[SID]["pins"] == t["a_def"]["pins"]


def test_two_projects_keep_their_definitions_through_save_reopen_revisions_and_engine(two_projects_edited):
    """Each project, reopened while the other project's definition of SID is
    registered, keeps its own definition in its file, its revision
    snapshots, and every engine output (BOM, netlist, check, SVG/PDF)."""
    t = two_projects_edited
    app = t["app"]
    a = projectio.open_any(t["path_a"], activate=False).project
    b = projectio.open_any(t["path_b"], activate=False).project
    assert a.symbols[SID]["pins"] == t["a_def"]["pins"] and b.symbols[SID]["pins"] == t["b_def"]["pins"]
    assert a.symbols[t["copy"]["id"]]["pins"] == t["a_def"]["pins"]
    assert t["copy"]["id"] not in b.symbols

    reference = {}
    for p in (a, b):
        p.activate_symbols()                                       # only this project registered
        reference[p.uid] = engine_outputs(p)
    assert wired_pins(a, SID) == {"B"} and wired_pins(b, SID) == {"Q"}
    assert reference[a.uid]["svg"] != reference[b.uid]["svg"]       # the comparison below is not vacuous
    assert reference[a.uid]["nets"] != reference[b.uid]["nets"]

    for p, other, own in ((a, b, t["a_def"]), (b, a, t["b_def"])):
        other.activate_symbols()                                   # the other project's SID is registered
        assert symbols.get(SID).custom["pins"] == (t["b_def"] if p is a else t["a_def"])["pins"]
        assert engine_outputs(p) == reference[p.uid], p.meta
        assert export.project_pdf(p).startswith(b"%PDF")
        store = revisions.RevisionStore()
        store.create(p, "approved", label="A")
        snap = store.load(store.latest()["n"])
        assert snap.symbols[SID]["pins"] == own["pins"]
        snap_foreign = engine_outputs(snap)                        # other project still registered
        for key in ("bom", "nets", "check"):                       # symbol-derived: identical to the live project
            assert snap_foreign[key] == reference[p.uid][key], key
        snap.activate_symbols()
        assert snap_foreign == engine_outputs(snap)                # drawings (title block now shows rev. A) too
        other.activate_symbols()
        path = os.path.join(os.path.dirname(t["path_a"]), f"resaved-{p.uid}.schematix")
        projectio.save_project(p, path)                            # saved while the other is registered
        again = projectio.open_any(path, activate=False).project
        assert again.symbols[SID]["pins"] == own["pins"]
        other.activate_symbols()
        assert engine_outputs(again) == reference[p.uid]


def test_reopened_app_project_keeps_wires_attached_after_edits(two_projects_edited):
    t = two_projects_edited
    assert_reopened(t["app"], t["path_a"], t["a_def"], t["copy"], t["wired"])


def test_updating_drawings_from_a_library_edit_never_downgrades(library_newer_than_project, monkeypatch, tmp_path):
    """Answering Yes to "Update drawings?" after an in-place library edit
    puts the library's newest revision into the project, and it survives
    save and reopen while another project's definition is registered."""
    app, v2, cid = library_newer_than_project
    from openschematix.gui import symbol_editor
    monkeypatch.setattr(symbol_editor.messagebox, "askyesno", lambda *a, **k: True)
    confirmed = []                   # revision 2 moves pins A and B: the update is confirmed explicitly
    monkeypatch.setattr(app, "confirm_symbol_update", lambda impact, d, lib: confirmed.append(impact) or True)
    other = dict(definition(40, "Q", "Foreign"), id=LIB_SID, revision=9)
    q = new_project("Foreign")
    q.symbols[LIB_SID] = other
    q_path = str(tmp_path / "foreign-update.schematix")
    projectio.save_project(q, q_path)
    app.edit_custom_symbol(LIB_SID)
    ed = editors(app)[-1]
    assert ed.meta["revision"] == 2 and ed.save() is True
    assert app.project.symbols[LIB_SID]["revision"] == 3 and pins(app.project.symbols[LIB_SID]) == pins(v2)
    assert len(confirmed) == 1 and confirmed[0].diff.pins_moved == ["A", "B"]
    projectio.open_any(q_path)                                     # foreign revision 9 registered at save
    path = str(tmp_path / "updated.schematix")
    projectio.save_project(app.project, path)
    reopened = projectio.open_any(path, activate=False).project
    assert reopened.symbols[LIB_SID]["revision"] == 3 and pins(reopened.symbols[LIB_SID]) == pins(v2)
    assert app.userlib.entries[LIB_SID].doc["revision"] == 3 and pins(app.userlib.entries[LIB_SID].doc) == pins(v2)
    assert reopened.sheets[0].components[cid].symbol == LIB_SID
