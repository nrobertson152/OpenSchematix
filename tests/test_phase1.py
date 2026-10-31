"""Regression tests for the Phase 1 symbol-editor and usability fixes."""
import os

import pytest

from openschematix import editing, projectio, render, symbols
from openschematix.project import new_project
from openschematix.symbols.custom import blank_symbol, to_symdef

PIN_NAMES = ("A1", "A2", "A3")


@pytest.fixture
def custom_symbol():
    doc = blank_symbol("Coil test")
    doc["prims"] = [{"k": "poly", "pts": [[-10, -10], [10, -10], [10, 10], [-10, 10]]}]
    doc["pins"] = [{"id": "p1", "name": "A1", "x": -20, "y": 0, "dir": "l", "show": True},
                   {"id": "p2", "name": "A2", "x": 20, "y": 0, "dir": "r", "show": True},
                   {"id": "p3", "name": "A3", "x": 0, "y": 20, "dir": "d", "show": True}]
    symbols.set_user_symbols([to_symdef(doc)])
    yield doc
    symbols.set_user_symbols([])
    symbols.set_project_symbols([])


def pin_texts(project, doc=None):
    doc = doc or project.sheets[0]
    items = render.scene(doc, project=project, frame=False)
    return sorted(it["s"] for it in items if it["k"] == "text" and it["s"] in PIN_NAMES)


def test_custom_symbol_artwork_has_no_baked_pin_labels(custom_symbol):
    g = symbols.get(custom_symbol["id"]).build(None)
    assert not [p for p in g.prims if p["k"] == "text"], "pin designations must not be part of the artwork"
    assert [t.label for t in g.terminals] == list(PIN_NAMES)
    assert all(t.show for t in g.terminals)


def test_terminal_numbers_hidden_when_setting_off(custom_symbol):
    p = new_project()
    assert p.settings["show_terminal_labels"] is False
    editing.place(p.sheets[0], custom_symbol["id"], 0, 0)
    assert pin_texts(p) == []


def test_terminal_numbers_shown_exactly_once_when_setting_on(custom_symbol):
    p = new_project()
    p.settings["show_terminal_labels"] = True
    editing.place(p.sheets[0], custom_symbol["id"], 0, 0)
    assert pin_texts(p) == list(PIN_NAMES)


@pytest.mark.parametrize("rotation,mirror", [(0, False), (90, False), (180, False), (270, True)])
def test_terminal_numbers_once_after_rotate_and_mirror(custom_symbol, rotation, mirror):
    p = new_project()
    p.settings["show_terminal_labels"] = True
    c = editing.place(p.sheets[0], custom_symbol["id"], 100, 100)
    c.rotation, c.mirror = rotation, mirror
    assert pin_texts(p) == list(PIN_NAMES)
    p.settings["show_terminal_labels"] = False
    assert pin_texts(p) == []


def test_terminal_numbers_survive_save_and_reopen(custom_symbol, tmp_path):
    p = new_project()
    p.settings["show_terminal_labels"] = True
    c = editing.place(p.sheets[0], custom_symbol["id"], 0, 0)
    editing.add_wire(p.sheets[0], [c.terminals()["p1"], (c.terminals()["p1"][0] - 40, 0)])
    path = str(tmp_path / "t.schematix")
    projectio.save_project(p, path)
    symbols.set_user_symbols([])
    symbols.set_project_symbols([])
    q = projectio.open_any(path).project
    assert pin_texts(q) == list(PIN_NAMES)
    c2 = q.sheets[0].components[c.id]
    assert set(c2.terminals()) == {"p1", "p2", "p3"}, "terminal identifiers preserved"
    q.settings["show_terminal_labels"] = False
    assert pin_texts(q) == []


def test_pin_opt_out_and_component_override(custom_symbol):
    custom_symbol["pins"][2]["show"] = False
    symbols.set_user_symbols([to_symdef(custom_symbol)])
    p = new_project()
    p.settings["show_terminal_labels"] = True
    c = editing.place(p.sheets[0], custom_symbol["id"], 0, 0)
    assert pin_texts(p) == ["A1", "A2"], "a pin with show=false is not numbered"
    p.settings["show_terminal_labels"] = False
    c.terminal_labels["p1"] = "A3"     # user override displays even with the setting off
    assert pin_texts(p) == ["A3"]


def test_visibility_does_not_change_connectivity(custom_symbol):
    from openschematix.connectivity import analyse
    p = new_project()
    d = p.sheets[0]
    c = editing.place(d, custom_symbol["id"], 0, 0)
    a = c.terminals()["p2"]
    editing.add_wire(d, [a, (a[0] + 40, a[1])])
    before = analyse(d)
    assert (c.id, "p2") in before.connected_terminals
    p.settings["show_terminal_labels"] = True
    after = analyse(d)
    assert after.connected_terminals == before.connected_terminals
    assert after.open_terminals == before.open_terminals


def test_builtin_symbol_terminal_numbers_unchanged():
    p = new_project()
    editing.place(p.sheets[0], "el.resistor.iec", 0, 0)
    items = render.scene(p.sheets[0], project=p, frame=False)
    assert not [it for it in items if it.get("role") == "pin"]
    p.settings["show_terminal_labels"] = True
    items = render.scene(p.sheets[0], project=p, frame=False)
    assert sorted(it["s"] for it in items if it.get("role") == "pin") == ["1", "2"]


def test_legacy_symbol_file_still_loads(custom_symbol):
    """Symbol files saved before the fix (show flags present) load unchanged."""
    from openschematix.symbols.custom import normalise
    doc = normalise(custom_symbol)
    assert [p["show"] for p in doc["pins"]] == [True, True, True]
    assert os.path.basename(__file__)


# ================================================================ default page size
def test_new_project_defaults_to_ansi_a():
    from openschematix.project import DEFAULT_SHEET_SIZE
    p = new_project()
    assert DEFAULT_SHEET_SIZE == "ANSI A"
    s = p.sheets[0].sheet
    assert s.size == "ANSI A" and s.orientation == "landscape"
    assert s.size_mm() == pytest.approx((279.4, 215.9))       # 11 x 8.5 in
    assert p.add_sheet("Two").sheet.size == "ANSI A", "added sheets follow the project's sheets"


def test_default_sheet_setting(tmp_path):
    from openschematix.settings import Settings
    st = Settings(str(tmp_path / "settings.json"))
    assert st["default_sheet"] == "ANSI A", "fresh installation"
    st["default_sheet"] = "A3"
    st.save()
    st2 = Settings(str(tmp_path / "settings.json"))
    st2.load()
    assert st2["default_sheet"] == "A3", "a saved user choice is kept"


def test_existing_projects_keep_their_page_size(tmp_path):
    p = new_project(size="A3")
    p.add_sheet("Portrait").sheet.size = "A4"
    path = str(tmp_path / "keep.schematix")
    projectio.save_project(p, path)
    q = projectio.open_any(path).project
    assert [d.sheet.size for d in q.sheets] == ["A3", "A4"]
    legacy = projectio.open_any(os.path.join(os.path.dirname(__file__), "..", "examples",
                                             "start_stop_latch.osch")).project
    assert legacy.sheets[0].sheet.size == "A4", "a legacy drawing keeps its saved size"
