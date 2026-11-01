"""v1.1.0 cycle 2: import and edit existing symbols.

Covers the fidelity guarantees of symbols/explode.py on top of
tests/test_symbol_import.py: no silent loss (unsupported geometry is
rejected with a reason), copies of built-in, library, project-embedded and
``.osym``-file symbols, grid alignment, independence from the original,
save/reopen, and placement, connectivity and BOM of the derived symbol.
"""
import copy
import json
import math

import pytest

from openschematix import bom, editing, projectio, symbols, userlib
from openschematix.connectivity import analyse
from openschematix.geometry import GRID
from openschematix.project import new_project
from openschematix.shapes import shape_to_symbol_prim, symbol_prim_to_shape
from openschematix.symbols.base import SymbolDef, Geometry, Terminal, circle, line, text
from openschematix.symbols.custom import SymbolFormatError, blank_symbol, normalise, to_symdef
from openschematix.symbols.explode import (SymbolImportError, conversion_losses, doc_from_data, doc_from_file,
                                           symbol_to_doc)
from openschematix.symbols.fluid import OPERATORS, VALVE_TYPES

# Representative symbols of every domain (electrical, electronic, hydraulic,
# pneumatic, general), including multi-terminal and arc-heavy ones.
REPRESENTATIVE = ["el.coil.iec", "el.contact.no.nema", "el.motor.3ph", "el.transformer", "el.earth",
                  "el.npn", "el.opamp", "el.inductor", "el.potentiometer.iec", "el.led",
                  "fl.hyd.pump.var", "fl.hyd.cyl.double", "fl.hyd.relief", "fl.hyd.accumulator", "fl.hyd.dcv",
                  "fl.pneu.compressor", "fl.pneu.shuttle", "fl.pneu.regulator", "fl.pneu.dcv",
                  "gen.block4", "gen.offpage"]


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    symbols.set_user_symbols([])
    symbols.set_project_symbols([])


def pins_of(sd, params=None):
    return {t.name: (t.x, t.y, t.dir, t.label or t.name, sd.port_type(t)) for t in sd.build(params).terminals}


def outline(sd, params=None, step=0.5):
    """Points sampled along everything drawn (arcs flattened), for comparing artwork."""
    pts = []
    for p in sd.build(params).prims:
        if p["k"] in ("line", "poly"):
            ring = list(p["pts"]) + ([p["pts"][0]] if p["k"] == "poly" else [])
            for a, b in zip(ring, ring[1:]):
                n = max(1, int(math.dist(a, b) / step))
                pts += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]
        elif p["k"] == "circle":
            (cx, cy), r = p["c"], p["r"]
            pts += [(cx + r * math.cos(t / 32 * math.tau), cy + r * math.sin(t / 32 * math.tau)) for t in range(32)]
        elif p["k"] == "text":
            pts.append(tuple(p["p"]))
    return pts


def max_gap(a, b):
    """Directed distance: furthest point of `a` from its nearest point in `b`."""
    return max(min(math.dist(p, q) for q in b) for p in a)


def fake_builtin(prims, terminals=(Terminal("1", -20, 0, "l"), Terminal("2", 20, 0, "r"))):
    return SymbolDef("test.fake", "Fake symbol", "Electrical", "Test", "Generic", "", "X",
                     Geometry(list(prims), list(terminals)))


# ================================================================ 1/4/5. built-in conversion and geometry
@pytest.mark.parametrize("sid", REPRESENTATIVE)
def test_representative_builtin_converts_with_same_artwork_and_pins(sid):
    sd = symbols.get(sid)
    doc = symbol_to_doc(sd)
    copy_sd = to_symdef(doc)
    assert pins_of(copy_sd) == pins_of(sd)
    # The artwork is the same shape: every drawn point of either lies on the other
    # (arcs are re-sampled, so allow chord sag).
    a, b = outline(sd), outline(copy_sd)
    assert max_gap(a, b) < 0.6 and max_gap(b, a) < 0.6
    assert doc["derived_from"]["id"] == sid and doc["id"].startswith("user:") and doc["revision"] == 0


@pytest.mark.parametrize("medium", ["hyd", "pneu"])
def test_every_valve_type_and_operator_converts(medium):
    sd = symbols.get(f"fl.{medium}.dcv")
    for vtype in VALVE_TYPES[medium]:
        for op in OPERATORS:
            params = copy.deepcopy(sd.default_params)
            params.update(type=vtype, positions=[], left=[op], right=["spring"])
            doc = symbol_to_doc(sd, params)
            assert pins_of(to_symdef(doc)) == pins_of(sd, params), (vtype, op)


def test_every_builtin_has_no_conversion_losses():
    for sd in symbols.builtin_symbols():
        doc = symbol_to_doc(sd)          # raises SymbolImportError on any loss
        assert len(doc["prims"]) == len(sd.build().prims)


def test_text_and_metadata_are_kept():
    sd = symbols.get("el.motor")
    doc = symbol_to_doc(sd)
    src = [p for p in sd.build().prims if p["k"] == "text"]
    got = [p for p in doc["prims"] if p["k"] == "text"]
    assert [(p["s"], tuple(p["p"]), p["size"], p["anchor"]) for p in src] == \
           [(p["s"], tuple(p["p"]), p["size"], p["anchor"]) for p in got]
    assert (doc["category"], doc["group"], doc["prefix"], doc["description"]) == \
           (sd.category, sd.group, sd.prefix, sd.description)


# ================================================================ 6. grid alignment
@pytest.mark.parametrize("sid", REPRESENTATIVE)
def test_imported_pins_stay_on_the_grid(sid):
    for p in symbol_to_doc(symbols.get(sid))["pins"]:
        assert p["x"] % GRID == 0 and p["y"] % GRID == 0


def test_off_grid_pin_is_rejected_not_snapped():
    sd = fake_builtin([line(-20, 0, 20, 0)], [Terminal("1", -20, 0, "l"), Terminal("2", 25, 0, "r")])
    with pytest.raises(SymbolImportError, match="grid"):
        symbol_to_doc(sd)


# ================================================================ 9. no silent loss
@pytest.mark.parametrize("prim,reason", [
    ({"k": "region", "rings": [[(0, 0), (10, 0), (10, 10)]]}, "'region'"),
    ({"k": "ellipse", "c": (0, 0), "rx": 5, "ry": 3}, "'ellipse'"),
    ({**text(0, 0, "X"), "angle": 90}, "'angle'"),
    ({**line(0, 0, 10, 0), "colour": "red"}, "'colour'"),
    (text(0, 0, "X", size=200), "'size'"),
    (text(0, 0, "Y" * 300), "'s'"),
    ({**circle(0, 0, 5), "fill": "maybe"}, "'fill'"),
])
def test_unsupported_geometry_is_rejected_with_a_reason(prim, reason):
    sd = fake_builtin([line(-20, 0, 20, 0), prim])
    with pytest.raises(SymbolImportError) as e:
        symbol_to_doc(sd)
    msg = str(e.value)
    assert "Fake symbol" in msg and reason in msg and "primitive 2" in msg


def test_pin_attributes_that_do_not_fit_are_rejected():
    long_label = Terminal("1", -20, 0, "l", label="X" * 30)
    with pytest.raises(SymbolImportError, match="connection point"):
        symbol_to_doc(fake_builtin([line(-20, 0, 20, 0)], [long_label]))
    bad_type = Terminal("1", -20, 0, "l", ptype="elec.unknown")
    with pytest.raises(SymbolImportError, match="'type'"):
        symbol_to_doc(fake_builtin([line(-20, 0, 20, 0)], [bad_type]))


def test_rejection_is_a_format_error_and_lists_every_problem():
    sd = fake_builtin([{**line(0, 0, 1, 1), "a": 1}, {**line(0, 0, 1, 1), "b": 1}])
    with pytest.raises(SymbolFormatError) as e:      # existing callers catch SymbolFormatError
        symbol_to_doc(sd)
    assert "'a'" in str(e.value) and "'b'" in str(e.value)


def test_harmless_defaults_are_not_reported():
    prims = [{**line(-20, 0, 20, 0), "arrow_start": False, "arrow_size": 10.0}]
    doc = symbol_to_doc(fake_builtin(prims))
    assert doc["prims"][0]["pts"] == [(-20.0, 0.0), (20.0, 0.0)]


def test_conversion_losses_is_empty_for_a_faithful_document():
    doc = symbol_to_doc(symbols.get("el.transformer"))
    assert conversion_losses(doc["prims"], doc["pins"], doc) == []


# ================================================================ 2. custom (library) symbols
def sensor():
    d = blank_symbol("Sensor", "Electronic")
    d["prims"] = [{"k": "arc", "c": [0, 0], "r": 8, "start": 0, "extent": 180},
                  {"k": "line", "pts": [[-20, 0], [-8, 0]], "arrow_end": True, "arrow_size": 4},
                  {"k": "poly", "pts": [[8, -2], [12, 0], [8, 2]], "fill": True},
                  {"k": "text", "p": [0, 4], "s": "B", "size": 6, "anchor": "s"}]
    d["pins"] = [{"id": "p1", "name": "BN", "x": -20, "y": 0, "dir": "l", "type": "elec.power"},
                 {"id": "p7", "name": "BK", "x": 20, "y": 0, "dir": "r", "type": "elec.output", "show": False}]
    d["properties"] = {"manufacturer": "ACME"}
    return normalise(d)


def test_library_symbol_copy_keeps_everything_but_identity(tmp_path):
    lib = userlib.UserLibrary(str(tmp_path))
    lib.create_folder("", "Mine")
    orig = lib.save_symbol(sensor(), "Mine").doc
    lib.publish()
    doc = symbol_to_doc(symbols.get(orig["id"]))
    assert doc["prims"] == orig["prims"] and doc["pins"] == orig["pins"]
    assert doc["properties"] == orig["properties"]
    assert doc["id"] != orig["id"] and doc["derived_from"]["id"] == orig["id"]


# ================================================================ 3. project-embedded symbols
def test_project_embedded_symbol_can_be_imported(tmp_path):
    """A symbol that exists only inside a project file (not in any library)."""
    s = sensor()
    symbols.set_user_symbols([to_symdef(s)])
    p = new_project()
    c = editing.place(p.sheets[0], s["id"], 0, 0)
    path = str(tmp_path / "embedded.schematix")
    projectio.save_project(p, path)
    symbols.set_user_symbols([])                          # not in the library any more
    q = projectio.open_any(path).project
    assert q.activate_symbols() == []
    sd = symbols.get(s["id"])
    assert sd is not None and s["id"] not in symbols.user_symbols()
    doc = symbol_to_doc(sd)
    assert doc["pins"] == s["pins"] and doc["prims"] == s["prims"]
    assert doc["derived_from"]["id"] == s["id"]
    assert q.sheets[0].components[c.id].symbol == s["id"]


# ================================================================ 4. .osym files
def test_osym_file_opens_as_an_independent_copy(tmp_path):
    s = sensor()
    path = tmp_path / "sensor.osym"
    path.write_text(json.dumps(s), encoding="utf-8")
    before = path.read_bytes()
    doc = doc_from_file(str(path))
    assert path.read_bytes() == before                    # the file is only read
    assert doc["prims"] == s["prims"] and doc["pins"] == s["pins"]
    assert doc["id"] != s["id"] and doc["derived_from"] == {"id": s["id"], "name": "Sensor", "revision": "0"}
    same = doc_from_file(str(path), as_copy=False)
    assert same["id"] == s["id"]


def test_osym_file_with_lossy_content_is_rejected(tmp_path):
    s = json.loads(json.dumps(sensor()))
    s["prims"].append({"k": "text", "p": [0, 0], "s": "Z", "size": 8, "anchor": "c", "rotation": 90})
    s["pins"][0]["type"] = "elec.future"
    path = tmp_path / "newer.osym"
    path.write_text(json.dumps(s), encoding="utf-8")
    with pytest.raises(SymbolImportError) as e:
        doc_from_file(str(path))
    assert "'rotation'" in str(e.value) and "BN" in str(e.value)


@pytest.mark.parametrize("content,match", [
    ("{not json", "not a valid symbol file"),
    (json.dumps({"format": "Something else"}), "not an OpenSchematix symbol"),
    (json.dumps([1, 2]), "not an OpenSchematix symbol"),
])
def test_invalid_osym_files_give_clear_errors(tmp_path, content, match):
    path = tmp_path / "bad.osym"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SymbolFormatError, match=match):
        doc_from_file(str(path))


def test_osym_without_pin_ids_is_rejected_as_lossy():
    d = json.loads(json.dumps(sensor()))
    for p in d["pins"]:
        del p["id"]
    with pytest.raises(SymbolImportError, match="missing id"):
        doc_from_data(d)


# ================================================================ 8. independence from the original
def test_editing_a_builtin_copy_does_not_touch_the_builtin():
    sd = symbols.get("fl.hyd.pump")
    snapshot = copy.deepcopy(sd.build().prims), list(sd.build().terminals)
    doc = symbol_to_doc(sd)
    for p in doc["prims"]:
        if "pts" in p:
            p["pts"][0] = (999, 999)
        if "c" in p:
            p["c"] = (999, 999)
    doc["pins"][0]["x"] = 990
    assert (sd.build().prims, list(sd.build().terminals)) == snapshot


def test_editing_a_custom_copy_does_not_touch_the_original():
    s = sensor()
    sd = to_symdef(s)
    before = copy.deepcopy(sd.custom)
    doc = symbol_to_doc(sd)
    doc["prims"][1]["pts"].append((5, 5))
    doc["pins"].pop()
    doc["properties"]["manufacturer"] = "Other"
    assert sd.custom == before
    again = symbol_to_doc(sd, as_copy=False)               # in-place editing also gets its own data
    again["prims"].clear()
    assert sd.custom == before


# ================================================================ 7. edit, save and reopen
def test_edited_copy_saves_reopens_and_keeps_editing(tmp_path):
    lib = userlib.UserLibrary(str(tmp_path))
    lib.create_folder("", "Mine")
    doc = symbol_to_doc(symbols.get("el.contact.no.iec"))
    # Edit the way the symbol editor does: primitives become shapes and back.
    shapes = [symbol_prim_to_shape(p, i) for i, p in enumerate(doc["prims"], 1)]
    shapes.pop()                                           # delete one element
    doc["prims"] = [shape_to_symbol_prim(s) for s in shapes]
    doc["prims"].append({"k": "circle", "c": [0, -10], "r": 3, "fill": False})
    doc["pins"].append({"id": "3", "name": "3", "x": 0, "y": -30, "dir": "u", "type": "elec.passive"})
    doc["pins"][0]["name"] = "13"
    doc["name"] = "Contact with aux"
    entry = lib.save_symbol(normalise(doc), "Mine")
    lib2 = userlib.UserLibrary(str(tmp_path))              # reopen from disk
    lib2.scan()
    saved = lib2.entries[entry.id].doc
    assert saved["name"] == "Contact with aux"
    assert [p["name"] for p in saved["pins"]] == ["13", "2", "3"]
    assert {"k": "circle", "c": (0.0, -10.0), "r": 3.0, "fill": False, "w": "normal", "dash": False} \
        in saved["prims"]
    # Continue editing the saved symbol in place: same id, no derived copy.
    again = symbol_to_doc(to_symdef(saved), as_copy=False)
    assert again["id"] == entry.id and again["prims"] == saved["prims"]
    assert symbols.get("el.contact.no.iec").build().terminals[0].label in ("", "1")   # built-in unchanged


def test_builtin_ids_can_never_be_overwritten(tmp_path):
    doc = symbol_to_doc(symbols.get("el.lamp.iec"))
    assert not symbols.is_builtin(doc["id"])
    forged = dict(doc, id="el.lamp.iec")
    with pytest.raises(SymbolFormatError):
        normalise(forged)
    symbols.set_user_symbols([to_symdef(doc)])
    assert symbols.get("el.lamp.iec").custom is None


# ================================================================ 10. placement, connectivity and BOM
@pytest.mark.parametrize("sid", ["el.coil.iec", "el.npn", "fl.hyd.relief", "fl.pneu.dcv"])
def test_derived_symbol_places_wires_and_appears_in_the_bom(sid):
    orig = symbols.get(sid)
    doc = symbol_to_doc(orig)
    doc["properties"] = {"part_number": "PN-1"}
    derived = to_symdef(doc)
    symbols.set_user_symbols([derived])
    p = new_project()
    d = p.sheets[0]
    a = editing.place(d, sid, 0, 0)
    b = editing.place(d, doc["id"], 200, 0)
    # Same terminals at the same offsets as the original.
    ta, tb = a.terminals(), b.terminals()
    assert set(ta) == set(tb)
    for name in ta:
        assert (tb[name][0] - 200, tb[name][1]) == pytest.approx(ta[name])
    name = sorted(tb)[0]
    end = tb[name]
    w = editing.add_wire(d, [end, (end[0], end[1] + 100)])
    assert w.start == [b.id, name]
    assert (b.id, name) in analyse(d).connected_terminals
    lines = bom.generate(p)
    tags = sorted(t for l in lines for t in l.designators)
    assert b.tag() in tags and a.tag() in tags
    assert symbols.get(sid) is orig and pins_of(orig) == pins_of(symbols.get(sid))


# ================================================================ 11. round-trip regression and edge cases
def test_hidden_terminal_visibility_preserved_and_faithful():
    """Terminal show=False must be faithfully retained across symbol_to_doc conversion."""
    t_hidden = Terminal("1", -20, 0, "l", label="1", ptype="elec.passive", show=False)
    t_visible = Terminal("2", 20, 0, "r", label="2", ptype="elec.passive", show=True)
    sd = fake_builtin([line(-20, 0, 20, 0)], [t_hidden, t_visible])
    doc = symbol_to_doc(sd)
    pins_by_id = {p["id"]: p for p in doc["pins"]}
    assert pins_by_id["1"]["show"] is False
    assert pins_by_id["2"]["show"] is True


def test_alias_stripping_on_copy_and_preservation_in_place(tmp_path):
    """Derived copies strip aliases; canonical in-place editing retains aliases."""
    doc_orig = blank_symbol("Aliased Symbol", "Electrical")
    doc_orig["aliases"] = ["ALIAS-1", "ALIAS-2"]
    doc_orig["prims"] = [{"k": "line", "pts": [[0, 0], [10, 0]]}]
    doc_orig["pins"] = [{"id": "p1", "name": "1", "x": 0, "y": 0, "dir": "l", "type": "elec.passive"}]
    doc_orig = normalise(doc_orig)

    sd = to_symdef(doc_orig)
    symbols.set_user_symbols([sd])

    # Copy should have aliases stripped
    copy_doc = symbol_to_doc(sd, as_copy=True)
    assert "aliases" not in copy_doc
    assert copy_doc["derived_from"]["id"] == sd.id

    # In-place editing should preserve aliases
    inplace_doc = symbol_to_doc(sd, as_copy=False)
    assert inplace_doc.get("aliases") == ["ALIAS-1", "ALIAS-2"]
    assert inplace_doc["id"] == sd.id

    # doc_from_file / doc_from_data copy stripping vs in-place
    osym_path = tmp_path / "aliased.osym"
    osym_path.write_text(json.dumps(doc_orig), encoding="utf-8")

    file_copy = doc_from_file(str(osym_path), as_copy=True)
    assert "aliases" not in file_copy

    file_inplace = doc_from_file(str(osym_path), as_copy=False)
    assert file_inplace.get("aliases") == ["ALIAS-1", "ALIAS-2"]


def test_arc_losses_detects_complementary_and_reversed_spans():
    """_arc_losses rejects sampled curves whose intermediate points don't match the arc span."""
    from openschematix.geometry import arc_points
    from openschematix.symbols.explode import _arc_losses

    pts_90 = arc_points(0, 0, 10, 0, 90)
    src_90 = {"k": "line", "pts": pts_90}

    # Same circle, same endpoints, but 270 degree sweep
    dst_270 = {"k": "arc", "c": [0, 0], "r": 10, "start": 0, "extent": -270}
    losses = _arc_losses("test_arc", src_90, dst_270)
    assert any("does not lie on the arc sweep" in l for l in losses)

    # Valid matching arc
    dst_90 = {"k": "arc", "c": [0, 0], "r": 10, "start": 0, "extent": 90}
    assert _arc_losses("test_arc", src_90, dst_90) == []


def test_scalable_arrowheads_round_trip():
    """Scalable arrowhead attributes on lines survive conversion, normalization, and round-trip."""
    d = blank_symbol("Arrowed", "General")
    d["prims"] = [
        {"k": "line", "pts": [[0, 0], [20, 0]], "arrow_start": True, "arrow_end": False, "arrow_size": 15.0},
        {"k": "line", "pts": [[0, 10], [20, 10]], "arrow_start": False, "arrow_end": True, "arrow_size": 8.0},
    ]
    d["pins"] = [{"id": "p1", "name": "1", "x": 0, "y": 0, "dir": "l", "type": "elec.passive"}]
    d = normalise(d)

    sd = to_symdef(d)
    doc = symbol_to_doc(sd, as_copy=True)

    assert doc["prims"][0]["arrow_start"] is True
    assert doc["prims"][0]["arrow_end"] is False
    assert doc["prims"][0]["arrow_size"] == pytest.approx(15.0)

    assert doc["prims"][1]["arrow_start"] is False
    assert doc["prims"][1]["arrow_end"] is True
    assert doc["prims"][1]["arrow_size"] == pytest.approx(8.0)


def test_symbol_editor_open_existing_error_handling(monkeypatch):
    """SymbolEditor.open_existing cleanly handles unavailable/lossy symbols without closing."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        pytest.skip(f"Tk GUI display not available: {e}")
    from openschematix.gui.app import App
    from openschematix.gui.symbol_editor import SymbolEditor
    from tkinter import messagebox

    try:
        app = App(root, check_recovery=False)
        ed = SymbolEditor(app)

        # Track messagebox calls
        errors = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, msg, **kwargs: errors.append((title, msg)))

        # Attempt to open a non-existent symbol
        result = ed.open_existing(sid="non_existent_symbol_12345")
        assert result is None
        assert len(errors) == 1
        assert "not available" in errors[0][1]

        # Ensure original editor is still open and not destroyed
        assert ed.winfo_exists()

        # Attempt to open an unsupported symbol with lossy geometry
        bad_prim = {**circle(0, 0, 5), "fill": "maybe"}
        bad_sd = fake_builtin([line(-20, 0, 20, 0), bad_prim])
        symbols.set_user_symbols([bad_sd])

        result_bad = ed.open_existing(sid=bad_sd.id)
        assert result_bad is None
        assert len(errors) == 2
        assert "cannot be converted" in errors[1][1]
        assert ed.winfo_exists()
        ed.destroy()
    finally:
        root.destroy()
