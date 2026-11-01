"""Same-id symbol collision: editing and updating never disconnect wires
without an informed choice (Issue #61, finding D3; test matrix A-J from the
independent specification review).

Scenario: project "Bravo" draws a custom symbol `SID` (connection points A
and Q, a wire on Q). The user library holds a DIFFERENT symbol under the same
id: "Alpha", connection points A and B (for example saved from another
project). Before the fix, "Edit symbol" on Bravo's component silently opened
Alpha, and accepting "Update drawings" replaced Bravo's symbol and detached
the Q wire, reporting it only afterwards.

Pure tests (symbols.compare) need no display; the application tests run the
real App under Tk and are skipped without a display.
"""
import copy
import json
import os
import tempfile

import pytest

from openschematix import bom, check as erc, editing, projectio, revisions, symbols
from openschematix.model import Wire
from openschematix.netlist import compute_nets
from openschematix.project import new_project
from openschematix.symbols import compare
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef

SID = "user:collision-shared"


def definition(name, second, reach=20, second_at=None, **extra):
    d = blank_symbol(name)
    d.update(id=SID, prefix="S", category="Electrical", group="Sensors", properties={"manufacturer": f"{name} Ltd"},
             **extra)
    at = reach if second_at is None else second_at
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}, {"k": "line", "pts": [[-reach, 0], [-10, 0]]},
                  {"k": "line", "pts": [[10, 0], [at, 0]]}]
    d["pins"] = [{"id": "A", "name": "A", "x": -reach, "y": 0, "dir": "l"},
                 {"id": second, "name": second, "x": at, "y": 0, "dir": "r"}]
    return normalise(d)


BRAVO = definition("Bravo", "Q", reach=40)
ALPHA = definition("Alpha", "B", reach=20)


def bravo_project(sdoc=BRAVO):
    """Project drawing `sdoc` as S1, its second pin wired to resistor R1.
    Returns (project, component id, wire id)."""
    symbols.set_project_symbols([to_symdef(sdoc)])
    p = new_project("Bravo")
    p.symbols[SID] = copy.deepcopy(sdoc)
    doc = p.sheets[0]
    c = editing.place(doc, SID, 200, 200)
    r = editing.place(doc, "el.resistor.iec", 500, 200)
    pin = sdoc["pins"][1]["id"]
    w = Wire(doc.new_id(), [c.terminals()[pin], r.terminals()["1"]], [c.id, pin], [r.id, "1"])
    doc.add_wire(w)
    editing.reroute(doc, w)
    symbols.set_project_symbols([])
    return p, c.id, w.id


# ================================================================ pure: symbols.compare
def test_revision_alone_is_not_a_difference():
    newer = dict(copy.deepcopy(BRAVO), revision=7)
    assert compare.diff(BRAVO, newer).identical


def test_diff_names_every_kind_of_difference():
    d = compare.diff(BRAVO, ALPHA)
    assert not d.identical and d.renamed and d.drawing_changed
    assert d.pins_removed == ["Q"] and d.pins_added == ["B"] and d.pins_moved == ["A"]
    text = "\n".join(d.summary())
    assert "different name" in text and "drawn version: Q" in text and "library version: B" in text

    turned = copy.deepcopy(BRAVO)
    turned["pins"][1]["dir"] = "u"
    retyped = copy.deepcopy(BRAVO)
    retyped["pins"][1]["type"] = "elec.output"
    assert compare.diff(BRAVO, turned).pins_turned == ["Q"] and compare.diff(BRAVO, turned).pins_moved == []
    assert compare.diff(BRAVO, retyped).pins_retyped == ["Q"]


def test_update_impact_lists_every_affected_wire_end():
    p, cid, wid = bravo_project()
    impact = compare.update_impact(p, SID, ALPHA)
    assert impact.components == 1 and not impact.harmless
    assert [(e.designator, e.pin, e.wire_id, e.end, e.sheet) for e in impact.detached] == \
        [("S1", "Q", wid, "start", p.sheets[0].name)]
    assert impact.moved == []
    same = compare.update_impact(p, SID, dict(copy.deepcopy(BRAVO), revision=3))
    assert same.harmless and same.diff.identical


# ================================================================ application
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


class Answers:
    """Records the safety prompts and answers them as a test decides."""

    def __init__(self):
        self.collision = None          # "library" | "copy" | None
        self.confirm = False           # answer to "Update drawings anyway?"
        self.update_prompt = False     # answer to the editor's "Update drawings?"
        self.collisions, self.confirms, self.update_questions = [], [], []


@pytest.fixture
def bravo(app, tmp_path, monkeypatch):
    """Bravo open in the application; the library holds Alpha under SID."""
    from openschematix.gui import app as app_mod, symbol_editor
    ans = Answers()
    for mod in (app_mod, symbol_editor):
        monkeypatch.setattr(mod.messagebox, "showerror", lambda *a, **k: None)
        monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(symbol_editor.messagebox, "askyesno",
                        lambda title, msg, **k: ans.update_questions.append(msg) or ans.update_prompt)
    monkeypatch.setattr(app, "ask_symbol_collision",
                        lambda sid, drawn, lib, diffs: ans.collisions.append((sid, drawn, lib, diffs)) or ans.collision)
    monkeypatch.setattr(app, "confirm_symbol_update",
                        lambda impact, drawn, lib: ans.confirms.append((impact, drawn, lib)) or ans.confirm)
    folder = "Collision tests"
    os.makedirs(app.userlib.abs(folder), exist_ok=True)
    if SID in app.userlib.entries:
        app.userlib.delete_symbol(SID)
    app.userlib.save_symbol(copy.deepcopy(ALPHA), folder)
    p, cid, wid = bravo_project()
    path = str(tmp_path / "Bravo.schematix")
    projectio.save_project(p, path)
    app.open_path(path, confirm=False)
    ans.path, ans.cid, ans.wid = path, cid, wid
    yield app, ans
    for w in list(app.windows):
        if w.winfo_exists() and w.__class__.__name__ == "SymbolEditor":
            w.dirty = False
            w.destroy()
    for sid in list(app.userlib.entries):
        if app.userlib.entries[sid].folder == folder:
            app.userlib.delete_symbol(sid)


def editors(app):
    return [w for w in app.windows if w.__class__.__name__ == "SymbolEditor" and w.winfo_exists()]


def state(app):
    """Everything an update may change: embedded definitions, every wire's
    attachment and route, the nets, and the library entry."""
    p = app.project
    wires = {(d.uid, w.id): (copy.deepcopy(w.start), copy.deepcopy(w.end), copy.deepcopy(w.points))
             for d in p.sheets for w in d.wires.values()}
    lib = app.userlib.entries.get(SID)
    return (json.dumps(p.symbols, sort_keys=True), wires, nets(p),
            json.dumps(lib.doc, sort_keys=True) if lib else None)


def nets(p):
    p.activate_symbols()
    return sorted(sorted(map(tuple, n.terminals)) for n in compute_nets(p) if len(n.terminals) > 1)


def reopened(path):
    return projectio.open_any(path, activate=False).project


def q_wired(p, cid):
    return any((p.sheets[0].uid, cid, "Q") in n for n in nets(p))


# ---------------------------------------------------------------- A: matching definitions keep #39 behaviour
def test_A_matching_definitions_open_and_update_without_extra_prompts(app, bravo):
    app, ans = bravo
    app.userlib.save_symbol(copy.deepcopy(BRAVO), "Collision tests")     # library now matches the drawing
    app.edit_custom_symbol(SID)
    ed = editors(app)[-1]
    assert ans.collisions == [] and ed.meta["id"] == SID and ed.meta["name"] == "Bravo"
    ed.meta_vars["description"].set("Edited description")
    ans.update_prompt = True
    assert ed.save() is True
    assert ans.confirms == []                                             # harmless update: no second prompt
    assert app.project.symbols[SID]["description"] == "Edited description"
    assert q_wired(app.project, ans.cid)


# ---------------------------------------------------------------- B: conflict asks first; Cancel changes nothing
def test_B_conflict_asks_before_any_editor_and_cancel_changes_nothing(app, bravo):
    app, ans = bravo
    before, n_editors = state(app), len(editors(app))
    assert app.edit_custom_symbol(SID) is None
    sid, drawn, lib, diffs = ans.collisions[0]
    assert sid == SID and drawn["name"] == "Bravo" and lib["name"] == "Alpha"
    assert any("drawn version: Q" in d for d in diffs)
    assert len(editors(app)) == n_editors and state(app) == before


# ---------------------------------------------------------------- C: copy choice
def test_C_copy_choice_edits_the_projects_version_under_a_new_id(app, bravo, tmp_path):
    app, ans = bravo
    ans.collision = "copy"
    before_lib = state(app)[3]
    ed = app.edit_custom_symbol(SID)
    assert ed.meta["id"] != SID and [p["id"] for p in ed.meta["pins"]] == ["A", "Q"]   # Bravo's, not Alpha's
    assert ed.save() is True
    assert state(app)[3] == before_lib                                    # library SID untouched
    assert app.project.symbols[SID]["name"] == "Bravo"
    path = str(tmp_path / "after-copy.schematix")
    projectio.save_project(app.project, path)
    p = reopened(path)
    assert p.symbols[SID]["name"] == "Bravo" and q_wired(p, ans.cid)


# ---------------------------------------------------------------- D: library choice, update declined
def test_D_library_edit_with_update_declined_keeps_the_project(app, bravo, tmp_path):
    app, ans = bravo
    ans.collision, ans.update_prompt = "library", False
    ed = app.edit_custom_symbol(SID)
    assert ed.meta["name"] == "Alpha"
    before = state(app)
    assert ed.save() is True
    assert app.userlib.entries[SID].doc["revision"] == 2                  # the library changed ...
    assert state(app)[:3] == before[:3]                                   # ... the project did not
    assert "draws “Bravo” (revision 0)" in ans.update_questions[0] and "“Alpha” revision 2" in ans.update_questions[0]
    path = str(tmp_path / "declined.schematix")
    projectio.save_project(app.project, path)
    p = reopened(path)
    assert [x["id"] for x in p.symbols[SID]["pins"]] == ["A", "Q"] and q_wired(p, ans.cid)


# ---------------------------------------------------------------- E: preflight predicts; Cancel is exact
def test_E_update_preflight_predicts_the_loss_and_no_leaves_everything(app, bravo):
    app, ans = bravo
    before, undo_depth = state(app), len(app.undo_stack)
    assert app.update_project_symbol(SID) is False
    impact, drawn, lib = ans.confirms[0]
    assert [(e.designator, e.pin) for e in impact.detached] == [("S1", "Q")]
    assert drawn["name"] == "Bravo" and lib["name"] == "Alpha"
    assert state(app) == before and len(app.undo_stack) == undo_depth   # nothing changed, no undo step


# ---------------------------------------------------------------- F: confirmed update is exact and undoable
def test_F_confirmed_update_detaches_exactly_the_predicted_ends_and_undo_restores(app, bravo, tmp_path):
    app, ans = bravo
    ans.confirm = True
    before = state(app)
    predicted = compare.update_impact(app.project, SID, app.userlib.entries[SID].doc)
    assert app.update_project_symbol(SID) is True
    d = app.project.sheets[0]
    detached = [(d.uid, w.id, end) for w in d.wires.values() for end in ("start", "end")
                if before[1][(d.uid, w.id)][0 if end == "start" else 1] and not getattr(w, end)]
    assert detached == [(e.sheet_uid, e.wire_id, e.end) for e in predicted.detached]
    assert not q_wired(app.project, ans.cid)
    app.undo()
    assert state(app) == before
    app.redo()
    path = str(tmp_path / "updated.schematix")
    projectio.save_project(app.project, path)
    p = reopened(path)
    assert p.symbols[SID]["name"] == "Alpha" and not q_wired(p, ans.cid)


# ---------------------------------------------------------------- G: same pin ids, moved positions
def test_G_moved_pins_are_announced_and_connections_survive(app, bravo):
    app, ans = bravo
    moved = definition("Bravo", "Q", reach=40, second_at=60)            # Q moves from x=40 to x=60
    app.userlib.save_symbol(copy.deepcopy(moved), "Collision tests")
    p = app.project
    n0, b0 = nets(p), [(x.designators, x.quantity) for x in bom.generate(p)]
    e0 = sorted(i.code for i in erc.check(p))
    ans.confirm = True
    assert app.update_project_symbol(SID) is True
    impact = ans.confirms[0][0]
    assert impact.detached == [] and [(e.designator, e.pin) for e in impact.moved] == [("S1", "Q")]
    assert nets(p) == n0 and [(x.designators, x.quantity) for x in bom.generate(p)] == b0
    assert sorted(i.code for i in erc.check(p)) == e0
    w = p.sheets[0].wires[ans.wid]
    assert w.start == [ans.cid, "Q"] and w.points[0] == p.sheets[0].components[ans.cid].terminals()["Q"]


# ---------------------------------------------------------------- H: alternating projects stay separate
def test_H_alternating_open_edit_save_never_mixes_definitions(app, bravo, tmp_path):
    app, ans = bravo
    alpha_p, _c, _w = bravo_project(ALPHA)
    alpha_path = str(tmp_path / "Alpha.schematix")
    projectio.save_project(alpha_p, alpha_path)
    ans.collision = None                                                  # Bravo: cancel the edit
    app.edit_custom_symbol(SID)
    app.save()
    app.open_path(alpha_path, confirm=False)                              # Alpha matches the library: no prompt
    n = len(ans.collisions)
    app.edit_custom_symbol(SID)
    assert len(ans.collisions) == n
    editors(app)[-1].dirty = False
    editors(app)[-1].destroy()
    app.save()
    app.open_path(ans.path, confirm=False)
    app.save()
    assert reopened(ans.path).symbols[SID]["name"] == "Bravo" and q_wired(reopened(ans.path), ans.cid)
    assert reopened(alpha_path).symbols[SID]["name"] == "Alpha"


# ---------------------------------------------------------------- I: revisions and failed saves keep the old definition
def test_I_revision_snapshot_and_failed_save_keep_the_pre_update_definition(app, bravo, monkeypatch):
    app, ans = bravo
    store = revisions.RevisionStore()
    store.create(app.project, "approved", label="A")
    ans.confirm = True
    assert app.update_project_symbol(SID) is True
    snap = store.load(store.latest()["n"])
    assert snap.symbols[SID]["name"] == "Bravo" and q_wired(snap, ans.cid)

    def disk_full(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(projectio, "atomic_write_bytes", disk_full)
    assert app.save() is False
    on_disk = reopened(ans.path)
    assert on_disk.symbols[SID]["name"] == "Bravo" and q_wired(on_disk, ans.cid)


# ---------------------------------------------------------------- J: the words the user reads
def test_J_update_message_names_both_symbols_and_every_disconnected_end(app, bravo):
    from openschematix.gui.app import symbol_update_message
    app, _ans = bravo
    lib = app.userlib.entries[SID].doc
    msg = symbol_update_message(compare.update_impact(app.project, SID, lib), app.project.symbols[SID], lib)
    for part in ("draws “Bravo” revision 0 (connection points A, Q)", "has “Alpha” revision 1 (connection points A, B)",
                 "DISCONNECT 1 wire end(s)", "connection point(s) Q no longer exist", "S1.Q (Sheet 1)",
                 "from “Bravo” to “Alpha”", "Undo", "anyway?"):
        assert part in msg, part


def test_J_collision_dialog_defaults_to_cancel_and_names_both(app, bravo):
    from openschematix.gui.dialogs import SymbolCollisionDialog
    app, _ans = bravo
    drawn, lib = app.project.symbols[SID], app.userlib.entries[SID].doc
    diffs = compare.diff(drawn, lib).summary()
    app.root.deiconify()                      # as in the application: a dialog is mapped with its window
    app.root.update()
    dlg = SymbolCollisionDialog(app, SID, drawn, lib, diffs, wait=False)
    try:
        dlg.focus_force()                     # no window manager gives the test application focus
        dlg.update()
        assert dlg.focus_get() is dlg.cancel_button                       # keyboard focus starts on Cancel
        texts = []

        def collect(w):
            try:
                texts.append(str(w.cget("text")))
            except Exception:  # noqa: BLE001
                pass
            for c in w.winfo_children():
                collect(c)
        collect(dlg)
        joined = "\n".join(texts)
        assert "“Bravo” revision 0" in joined and "“Alpha” revision 1" in joined and SID in joined
        dlg.focus_get().event_generate("<Return>")                        # Return on the focused Cancel
        dlg.update()
        assert not dlg.winfo_exists() and dlg.result is None
    finally:
        if dlg.winfo_exists():
            dlg.destroy()
    for key, expected in (("library", "library"), ("copy", "copy")):
        d2 = SymbolCollisionDialog(app, SID, drawn, lib, diffs, wait=False)
        (d2.library_button if key == "library" else d2.copy_button).invoke()
        assert d2.result == expected
    d3 = SymbolCollisionDialog(app, SID, drawn, lib, diffs, wait=False)
    d3.focus_force()
    d3.update()
    d3.focus_get().event_generate("<Escape>")
    d3.update()
    assert d3.result is None and not d3.winfo_exists()
    app.root.withdraw()
