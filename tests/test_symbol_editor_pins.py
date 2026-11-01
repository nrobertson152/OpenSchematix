"""Symbol editor: pin-number visibility, keyboard editing and aliases (v1.1.0 cycle 2).

Runs the real editor window under Tk; skipped when no display is available.
"""
import os
import tempfile

import pytest

from openschematix import symbols
from openschematix.geometry import GRID
from openschematix.model import Shape


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
def quiet(monkeypatch):
    """Record message boxes instead of showing them."""
    from openschematix.gui import symbol_editor
    shown = []
    monkeypatch.setattr(symbol_editor.messagebox, "showerror", lambda *a, **k: shown.append(("error", a)))
    monkeypatch.setattr(symbol_editor.messagebox, "showinfo", lambda *a, **k: shown.append(("info", a)))
    monkeypatch.setattr(symbol_editor.messagebox, "askyesno", lambda *a, **k: True)
    return shown


def new_editor(app, doc=None, folder=None):
    from openschematix.gui.symbol_editor import SymbolEditor
    ed = SymbolEditor(app, doc=doc, folder=folder)
    app.root.update()
    if doc is None:
        ed.doc.add_shape(Shape(ed.doc.new_id(), "rect", pts=[(-20, -10), (20, -10), (20, 10), (-20, 10)]))
        ed.add_pin((-30, 0))
        ed.add_pin((30, 0))
        ed.meta_vars["name"].set(f"Test {id(ed)}")
        ed.folder_var.set("My symbols")
    return ed


def select_pin(ed, i):
    ed.select_pin_row(ed.pins[i]["id"])
    ed._pin_selected(None)


def redraw(ed):
    ed.canvas._redraw_pending = True
    ed.canvas._redraw_now()


def pin_labels(ed):
    cv = ed.canvas
    return sorted((cv.itemcget(i, "text"), cv.itemcget(i, "fill")) for i in cv.find_withtag("pinlabel"))


def tree_names(ed):
    return [ed.pin_tree.item(i, "values")[0] for i in ed.pin_tree.get_children()]


class E:
    def __init__(self, widget):
        self.widget = widget


# ---------------------------------------------------------------- pin-number visibility
def test_number_checkbox_applies_immediately_and_undoes(app, quiet):
    ed = new_editor(app)
    try:
        select_pin(ed, 0)
        cb = next(w for w in _widgets(ed) if w.winfo_class() == "TCheckbutton"
                  and w.cget("text") == "Number this point on drawings")
        cb.invoke()                                   # a click: toggles the variable and runs its command
        assert ed.pin_show.get() == 0
        assert ed.pins[0]["show"] is False and ed.pins[1]["show"] is True
        assert tree_names(ed) == ["(1)", "2"]
        ed.undo()
        assert ed.pins[0]["show"] is True and tree_names(ed) == ["1", "2"]
        ed.redo()
        assert ed.pins[0]["show"] is False
    finally:
        ed.destroy()


def test_hidden_number_not_drawn_in_editor_except_muted_when_selected(app, quiet):
    ed = new_editor(app)
    try:
        t = app.theme
        select_pin(ed, 0)
        ed.pin_show.set(0)
        ed._pin_apply()
        ed.set_selection(set())
        redraw(ed)
        assert pin_labels(ed) == [("2", t["wire"])]
        select_pin(ed, 0)
        redraw(ed)
        assert pin_labels(ed) == [("(1)", t["pin"]), ("2", t["wire"])]
    finally:
        ed.destroy()


def test_unapplied_form_edits_are_saved_and_survive_reopening(app, quiet):
    ed = new_editor(app)
    try:
        select_pin(ed, 1)
        ed.pin_name.set("13")                      # typed, Apply not pressed
        ed.pin_show.set(0)                         # variable changed without the checkbox command
        assert ed.save()
        sid = ed.meta["id"]
    finally:
        ed.destroy()
    doc = app.userlib.entries[sid].doc
    assert [(p["name"], p["show"]) for p in doc["pins"]] == [("1", True), ("13", False)]
    ed = new_editor(app, doc=doc, folder="My symbols")   # reopen from the library
    try:
        assert tree_names(ed) == ["1", "(13)"]
        select_pin(ed, 1)
        assert ed.pin_show.get() == 0 and ed.pin_name.get() == "13"
    finally:
        ed.destroy()


def test_save_right_after_adding_a_point_does_not_use_an_unloaded_form(app, quiet):
    """add_pin selects the new row; the form is filled only when Tk delivers <<TreeviewSelect>>. Saving
    before that must not treat the still-empty form as an edit."""
    ed = new_editor(app)
    try:
        assert ed.pin_tree.selection() and not ed._pin_form_pending()
        assert ed.save() and not quiet
        assert [p["name"] for p in app.userlib.entries[ed.meta["id"]].doc["pins"]] == ["1", "2"]
    finally:
        ed.destroy()


def test_undo_and_renumber_are_not_reverted_by_the_form_on_save(app, quiet):
    """The form must follow changes made elsewhere; only fields the user edited count as pending."""
    ed = new_editor(app)
    try:
        select_pin(ed, 0)
        ed.pin_show.set(0)
        ed._pin_apply()
        ed.undo()                                   # point numbered again; the form must follow
        assert ed.pins[0]["show"] is True and ed.pin_show.get() == 1
        ed._pin_renumber()                          # names change underneath the form
        select_pin(ed, 1)
        ed.pin_name.set("X9")                       # typed, not applied ...
        ed.doc.add_shape(Shape(ed.doc.new_id(), "line", pts=[(0, 20), (10, 20)]))
        s = ed.begin_change()
        ed.commit_change(s, "unrelated edit")       # ... survives an unrelated edit
        assert ed.pin_name.get() == "X9"
        assert ed.save()
        names = [(p["name"], p["show"]) for p in app.userlib.entries[ed.meta["id"]].doc["pins"]]
        assert names == [("1", True), ("X9", True)]
    finally:
        ed.destroy()


def test_enter_in_name_field_applies(app, quiet):
    ed = new_editor(app)
    try:
        select_pin(ed, 0)
        ed.pin_name.set("A1")
        ed._pin_apply()
        assert ed.pins[0]["name"] == "A1"
        assert not ed._pin_form_pending()
    finally:
        ed.destroy()


# ---------------------------------------------------------------- keyboard and grid
def test_select_all_and_nudge_keep_pins_on_the_grid(app, quiet):
    ed = new_editor(app)
    try:
        for seq in ("<Control-a>", "<Control-Shift-Z>", "<Control-Z>", "<Left>", "<Down>"):
            assert ed.bind(seq), f"{seq} is bound"
        assert ed._select_all_key(E(ed.canvas)) == "break"
        assert len(ed.selection) == 1 + 2
        before = [(p["x"], p["y"]) for p in ed.pins]
        ed._nudge_key(E(ed.canvas), 1, 0)            # selection contains pins: one 2.5 mm grid step
        assert [(p["x"], p["y"]) for p in ed.pins] == [(x + GRID, y) for x, y in before]
        assert all(p["x"] % GRID == 0 and p["y"] % GRID == 0 for p in ed.pins)
        ed.undo()
        assert [(p["x"], p["y"]) for p in ed.pins] == before
        # only artwork selected: the editor's (finer) snap step
        sid = next(iter(ed.doc.shapes))
        ed.set_selection({sid})
        x0 = ed.doc.shapes[sid].pts[0][0]
        ed._nudge_key(E(ed.canvas), 1, 0)
        assert ed.doc.shapes[sid].pts[0][0] == pytest.approx(x0 + ed.snap_step())
        # typing in a field keeps the arrow keys
        assert ed._nudge_key(E(next(w for w in _widgets(ed) if w.winfo_class() == "TEntry")), 1, 0) is None
        ed.build_doc()                               # still a valid symbol (pins on the grid)
    finally:
        ed.destroy()


def _widgets(w):
    for c in w.winfo_children():
        yield c
        yield from _widgets(c)


# ---------------------------------------------------------------- aliases
def test_aliases_saved_validated_and_used_by_insert(app, quiet):
    ed = new_editor(app)
    try:
        ed.aliases.set("PROX-1, prox.b")
        assert ed.save()
        sid = ed.meta["id"]
        assert app.userlib.entries[sid].doc["aliases"] == ["PROX-1", "prox.b"]
    finally:
        ed.destroy()
    symbols.set_user_symbols([__import__("openschematix.symbols.custom", fromlist=["x"]).to_symdef(e.doc)
                              for e in app.userlib.entries.values()])
    assert symbols.resolve("prox-1").id == sid
    # a second symbol may not take the alias, nor a built-in id
    ed = new_editor(app)
    try:
        for bad in ("prox-1", "el.coil.iec", "two words"):
            quiet.clear()
            ed.aliases.set(bad)
            assert ed.save() is False
            assert quiet and quiet[-1][0] == "error"
        ed.aliases.set("")
        assert ed.save()
    finally:
        ed.destroy()
    # INSERT by alias places the canonical symbol
    n = len(app.doc.components)
    app.cmd_insert("PROX.B")
    assert app.canvas.place_symbol == sid
    app.canvas.set_tool("select")
    assert len(app.doc.components) == n
    # removing an alias frees it
    ed = new_editor(app, doc=app.userlib.entries[sid].doc, folder="My symbols")
    try:
        assert ed.aliases.get() == "PROX-1, prox.b"
        ed.aliases.set("prox.b")
        assert ed.save()
        assert app.userlib.entries[sid].doc["aliases"] == ["prox.b"]
    finally:
        ed.destroy()


def test_save_as_new_symbol_does_not_copy_aliases(app, quiet, monkeypatch):
    ed = new_editor(app)
    try:
        ed.aliases.set("ORIGINAL-X")
        assert ed.save()
        orig = ed.meta["id"]
        from tkinter import simpledialog
        monkeypatch.setattr(simpledialog, "askstring", lambda *a, **k: "Copy of it")
        assert ed.save(as_new=True)
        assert ed.meta["id"] != orig
        assert "aliases" not in app.userlib.entries[ed.meta["id"]].doc
        assert app.userlib.entries[orig].doc["aliases"] == ["ORIGINAL-X"]
    finally:
        ed.destroy()
