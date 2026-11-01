"""Symbol aliases and pin-number visibility through the symbol pipeline (v1.1.0 cycle 2).

Aliases are extra identifiers stored in a custom symbol document. They are
found by the library search and INSERT and resolve to the canonical symbol;
drawings always store the canonical id.
"""
import copy
import json
import os
import xml.etree.ElementTree as ET

import pytest

from openschematix import editing, export, projectio, symbols, userlib
from openschematix.connectivity import analyse
from openschematix.project import new_project
from openschematix.render import scene
from openschematix.symbols.custom import (SymbolFormatError, alias_problems, blank_symbol, normalise,
                                          to_symdef)
from openschematix.symbols.explode import symbol_to_doc


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    symbols.set_user_symbols([])
    symbols.set_project_symbols([])


def make_doc(name="Sensor", aliases=None, pins=None):
    d = blank_symbol(name)
    d["prims"] = [{"k": "poly", "pts": [[-20, -10], [20, -10], [20, 10], [-20, 10]], "fill": False}]
    d["pins"] = pins if pins is not None else [
        {"id": "p1", "name": "1", "x": -30, "y": 0, "dir": "l", "type": "elec.passive", "show": True},
        {"id": "p2", "name": "2", "x": 30, "y": 0, "dir": "r", "type": "elec.passive", "show": False}]
    if aliases is not None:
        d["aliases"] = aliases
    return d


# ---------------------------------------------------------------- document format and compatibility
def test_documents_without_aliases_are_unchanged():
    d = make_doc()
    n = normalise(copy.deepcopy(d))
    assert "aliases" not in n                          # older documents normalise exactly as before
    assert to_symdef(n).aliases == ()
    assert normalise(n) == n


def test_alias_field_is_cleaned_leniently_on_load():
    d = make_doc(aliases=["PNP-PROX", " pnp-prox ", "with space", "", 42, True, None, "B.prox/2", "x" * 61])
    n = normalise(d)
    assert n["aliases"] == ["PNP-PROX", "42", "B.prox/2"]   # invalid and repeated (any case) entries dropped
    d["aliases"] = [d["id"], "ok"]
    assert normalise(d)["aliases"] == ["ok"]                 # never the symbol's own id
    d["aliases"] = "not-a-list"
    assert "aliases" not in normalise(d)


def test_older_program_view_ignores_aliases():
    """A symbol with aliases is still a valid version-1 document: the format version is unchanged."""
    n = normalise(make_doc(aliases=["A1"]))
    assert n["version"] == 1 and n["format"] == "OpenSchematix Symbol"


# ---------------------------------------------------------------- collision rules
def test_alias_problems():
    sd = to_symdef(make_doc(aliases=["TAKEN"]))
    others = symbols.alias_pairs(symbols.builtin_symbols()) + [(sd.id, sd.aliases)]
    own = "user:0000000000000001"
    assert alias_problems(["Fresh", "fresh-2"], own, others) == []
    probs = alias_problems(["el.resistor.iec", "EL.RESISTOR.IEC", "taken", "dup", "DUP", own, "bad alias"],
                           own, others)
    assert len(probs) == 7 - 1   # "DUP" after "dup" is one problem; every other entry is one problem
    text = " ".join(probs)
    assert "identifier of another symbol (el.resistor.iec)" in text
    assert f"alias of another symbol ({sd.id})" in text
    assert "listed twice" in text and "own identifier" in text and "not a valid alias" in text
    # another copy of the same symbol (e.g. project and library) is not a conflict
    assert alias_problems(["TAKEN"], sd.id, others) == []


# ---------------------------------------------------------------- lookup and search
def test_resolve_and_search_find_the_canonical_symbol():
    sd = to_symdef(make_doc("Proximity sensor", aliases=["PNP-PROX", "B.prox"]))
    symbols.set_user_symbols([sd])
    assert symbols.resolve("pnp-prox") is sd and symbols.resolve("B.PROX") is sd
    assert symbols.resolve(sd.id) is sd
    assert symbols.resolve("el.resistor.iec").id == "el.resistor.iec"
    assert symbols.resolve("nothing-like-this") is None
    assert symbols.get("PNP-PROX") is None             # get() stays exact: drawings store canonical ids
    assert sd in symbols.search("pnp-prox")
    assert symbols.geometry(sd.id).terminals == sd.build().terminals   # one definition, no duplicate


def test_alias_claimed_by_two_symbols_resolves_to_nothing():
    a = to_symdef(make_doc("A", aliases=["SAME"]))
    b = to_symdef(make_doc("B", aliases=["same"]))      # only possible with files edited by hand
    symbols.set_user_symbols([a, b])
    assert symbols.resolve("same") is None
    assert {s.id for s in symbols.search("same")} >= {a.id, b.id}


# ---------------------------------------------------------------- user library
def test_library_saves_aliases_and_rejects_collisions(tmp_path):
    lib = userlib.UserLibrary(str(tmp_path / "libs"))
    e1 = lib.save_symbol(make_doc("One", aliases=["ONE-A"]), "My symbols")
    assert e1.doc["aliases"] == ["ONE-A"]
    with pytest.raises(ValueError, match="alias of another symbol"):
        lib.save_symbol(make_doc("Two", aliases=["one-a"]), "My symbols")
    with pytest.raises(ValueError, match="identifier of another symbol"):
        lib.save_symbol(make_doc("Three", aliases=["el.coil.iec"]), "My symbols")
    # editing the same symbol keeps its own aliases; removing an alias frees it
    doc = copy.deepcopy(e1.doc)
    doc["aliases"] = ["ONE-A", "ONE-B"]
    assert lib.save_symbol(doc, "My symbols").doc["aliases"] == ["ONE-A", "ONE-B"]
    doc["aliases"] = ["ONE-B"]
    lib.save_symbol(doc, "My symbols")
    e2 = lib.save_symbol(make_doc("Two", aliases=["one-a"]), "My symbols")
    assert e2.doc["aliases"] == ["one-a"]
    # reopened from disk
    lib2 = userlib.UserLibrary(str(tmp_path / "libs"))
    lib2.scan()
    assert lib2.entries[e1.id].doc["aliases"] == ["ONE-B"] and lib2.entries[e2.id].doc["aliases"] == ["one-a"]
    assert [e.id for e in lib2.search("one-b")] == [e1.id]


def test_copies_and_imports_never_duplicate_aliases(tmp_path):
    lib = userlib.UserLibrary(str(tmp_path / "libs"))
    e = lib.save_symbol(make_doc("Orig", aliases=["ORIG-1", "ORIG-2"]), "My symbols")
    c = lib.copy_symbol(e.id, "My symbols")
    assert "aliases" not in c.doc
    dup = lib.import_symbol_doc(copy.deepcopy(e.doc), "My symbols", on_conflict="duplicate")
    assert dup.id != e.id and "aliases" not in dup.doc
    other = make_doc("Imported", aliases=["ORIG-1", "NEW-1"])
    imp = lib.import_symbol_doc(other, "My symbols")
    assert imp.doc["aliases"] == ["NEW-1"]               # colliding alias dropped, the rest kept
    symbols.set_user_symbols([to_symdef(x.doc) for x in lib.entries.values()])
    ex = symbol_to_doc(symbols.get(e.id), as_copy=True)  # symbol editor "Edit a copy"
    assert "aliases" not in ex


# ---------------------------------------------------------------- projects: references stay canonical
def test_project_save_reopen_keeps_canonical_references_and_aliases(tmp_path):
    sd = to_symdef(make_doc("Sensor", aliases=["PROX"]))
    symbols.set_user_symbols([sd])
    p = new_project()
    d = p.sheets[0]
    target = symbols.resolve("prox")
    c = editing.place(d, target.id, 100, 100)
    r = editing.place(d, "el.resistor.iec", 200, 100)
    editing.add_wire(d, [c.terminals()["p2"], r.terminals()["1"]])
    assert c.symbol == sd.id
    path = str(tmp_path / "a.schematix")
    projectio.save_project(p, path)
    symbols.set_user_symbols([])
    res = projectio.open_any(path)
    res.project.activate_symbols()
    d2 = res.project.sheets[0]
    c2 = next(x for x in d2.components.values() if x.symbol == sd.id)
    assert symbols.get(sd.id).aliases == ("PROX",) and symbols.resolve("PROX").id == sd.id
    assert c2.terminals() == c.terminals()               # pins on the same grid points
    conn = analyse(d2)
    assert (c2.id, "p2") in conn.connected_terminals     # still wired


# ---------------------------------------------------------------- pin numbers: render and exports
def _pin_texts(items):
    return sorted(it["s"] for it in items if it.get("role") == "pin")


def test_hidden_pin_numbers_in_scene_and_svg(tmp_path):
    sd = to_symdef(make_doc())                          # pin 1 numbered, pin 2 not
    symbols.set_user_symbols([sd])
    p = new_project()
    d = p.sheets[0]
    c = editing.place(d, sd.id, 200, 200)
    p.settings["show_terminal_labels"] = False
    assert _pin_texts(scene(d, project=p)) == []
    p.settings["show_terminal_labels"] = True
    assert _pin_texts(scene(d, project=p)) == ["1"]       # hidden pin 2 not drawn
    assert _pin_texts(scene(d, screen=False, project=p)) == ["1"]   # print/export path
    svg = tmp_path / "x.svg"
    export.export_svg(d, str(svg), use_sheet=False, project=p)   # no frame: its zone numbers are text too
    texts = [t.text for t in ET.parse(svg).getroot().iter() if t.tag.endswith("text")]
    assert "1" in texts and "2" not in texts
    # an explicit per-component designation is always drawn, even for a hidden pin
    c.terminal_labels = {"p2": "B"}
    assert _pin_texts(scene(d, project=p)) == ["1", "B"]


def test_pins_must_stay_on_the_grid():
    bad = make_doc(pins=[{"id": "p1", "name": "1", "x": -25, "y": 0, "dir": "l"}])
    with pytest.raises(SymbolFormatError, match="grid"):
        normalise(bad)
