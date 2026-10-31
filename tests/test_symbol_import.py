"""Phase 2: open an existing symbol as editable primitives ("import and explode")."""
import copy
import json
import math

import pytest

from openschematix import editing, projectio, symbols, userlib
from openschematix.connectivity import analyse
from openschematix.geometry import GRID, arc_points
from openschematix.project import new_project
from openschematix.shapes import shape_to_symbol_prim, symbol_prim_to_shape
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef
from openschematix.symbols.explode import recognise_arc, symbol_to_doc


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    symbols.set_user_symbols([])
    symbols.set_project_symbols([])


def terminals(sd, params=None):
    return [(t.name, t.x, t.y, t.dir, sd.port_type(t)) for t in sd.build(params).terminals]


def on_prim(p, x, y, tol=0.05):
    """Is (x, y) on primitive p (line/poly/arc/circle)?"""
    if p["k"] in ("arc", "circle"):
        cx, cy = p["c"]
        return abs(math.hypot(x - cx, y - cy) - p["r"]) <= tol
    return any(abs(x - q[0]) <= tol and abs(y - q[1]) <= tol for q in p["pts"])


# ================================================================ arc recognition
@pytest.mark.parametrize("start,extent", [(0, 90), (45, 180), (180, 120), (300, 100), (90, -180), (10, 30)])
def test_sampled_arc_becomes_native_arc(start, extent):
    pts = arc_points(5, -3, 12, start, extent)
    a = recognise_arc({"k": "line", "pts": pts, "w": "thick", "dash": True})
    assert a is not None and a["k"] == "arc"
    assert a["c"] == pytest.approx((5, -3)) and a["r"] == pytest.approx(12)
    assert a["extent"] == pytest.approx(abs(extent)) and a["w"] == "thick" and a["dash"] is True
    back = arc_points(*a["c"], a["r"], a["start"], a["extent"])
    ends = {tuple(round(v, 6) for v in pts[0]), tuple(round(v, 6) for v in pts[-1])}
    assert {tuple(round(v, 6) for v in back[0]), tuple(round(v, 6) for v in back[-1])} == ends


def test_full_sampled_circle_becomes_circle():
    c = recognise_arc({"k": "line", "pts": arc_points(0, 0, 8, 0, 360)})
    assert c["k"] == "circle" and c["r"] == pytest.approx(8)


@pytest.mark.parametrize("pts", [
    [(0, 0), (10, 0), (20, 0), (30, 0), (40, 0)],                                    # straight
    [(0, 0), (2, 4), (6, -4), (10, 4), (14, -4), (16, 0)],                            # zigzag
    [(10 * math.cos(math.radians(a)), 10 * math.sin(math.radians(a))) for a in range(0, 361, 60)],  # hexagon
    [(0, 0), (10, 0)],                                                                # too short
])
def test_non_arcs_are_kept(pts):
    assert recognise_arc({"k": "line", "pts": pts}) is None


# ================================================================ built-in symbols
@pytest.mark.parametrize("sd", symbols.builtin_symbols(), ids=lambda s: s.id)
def test_every_builtin_symbol_explodes_faithfully(sd):
    doc = symbol_to_doc(sd)
    assert doc["id"].startswith("user:") and doc["revision"] == 0
    assert doc["derived_from"]["id"] == sd.id
    copy_def = to_symdef(doc)                               # valid custom symbol
    assert terminals(copy_def) == terminals(sd), "pin ids, positions, leads and port types preserved"
    assert all(abs(p["x"] / GRID - round(p["x"] / GRID)) < 1e-9 for p in doc["pins"])
    orig = sd.build(None).prims
    assert len(doc["prims"]) == len(orig), "one editable primitive per original primitive"
    for p0, p1 in zip(orig, doc["prims"]):
        if p1["k"] == "arc" or (p1["k"] == "circle" and p0["k"] == "line"):
            assert all(on_prim(p1, x, y) for x, y in p0["pts"]), "recovered arc passes through the original points"
        else:
            assert p1["k"] == p0["k"]
            if "pts" in p0:
                assert [tuple(q) for q in p1["pts"]] == [tuple(map(float, q)) for q in p0["pts"]]


def test_builtin_arcs_are_recovered():
    kinds = [p["k"] for p in symbol_to_doc(symbols.get("el.inductor"))["prims"]]
    assert kinds.count("arc") >= 3
    resistor = symbol_to_doc(symbols.get("el.resistor.ansi"))["prims"]
    assert not any(p["k"] == "arc" for p in resistor), "a zigzag stays a polyline"


def test_parametric_variant_is_used():
    sd = symbols.get("fl.hyd.dcv")
    params = copy.deepcopy(sd.default_params)
    params.update(type="4/2", positions=["parallel", "crossed"], left=["solenoid"], right=["spring"])
    doc = symbol_to_doc(sd, params)
    assert terminals(to_symdef(doc)) == terminals(sd, params)
    assert len(doc["prims"]) == len(sd.build(params).prims)


def test_builtin_copy_pins_numbered_like_builtin():
    doc = symbol_to_doc(symbols.get("el.resistor.iec"))
    assert [(p["id"], p["name"], p["show"]) for p in doc["pins"]] == [("1", "1", True), ("2", "2", True)]


# ================================================================ custom symbols
def sensor():
    d = blank_symbol("Sensor")
    d["prims"] = [{"k": "arc", "c": [0, 0], "r": 8, "start": 0, "extent": 180},
                  {"k": "text", "p": [0, 4], "s": "B", "size": 6, "anchor": "c"}]
    d["pins"] = [{"id": "p1", "name": "BN", "x": -20, "y": 0, "dir": "l", "type": "elec.power"},
                 {"id": "p7", "name": "BK", "x": 20, "y": 0, "dir": "r", "type": "elec.output", "show": False}]
    return normalise(d)


def test_custom_copy_has_new_identity_and_same_pins():
    src = sensor()
    before = json.dumps(src, sort_keys=True)
    sd = to_symdef(src)
    doc = symbol_to_doc(sd)
    assert json.dumps(src, sort_keys=True) == before, "source document untouched"
    assert doc["id"] != src["id"] and doc["revision"] == 0 and doc["name"] == "Sensor (copy)"
    assert doc["derived_from"] == {"id": src["id"], "name": "Sensor", "revision": "0"}
    assert doc["pins"] == src["pins"] and doc["prims"] == src["prims"]
    same = symbol_to_doc(sd, as_copy=False)
    assert same["id"] == src["id"] and "derived_from" not in same


def test_saving_a_copy_never_overwrites_the_original(tmp_path):
    lib = userlib.UserLibrary(str(tmp_path / "libs"))
    folder = lib.create_folder("", "Mine")
    orig = lib.save_symbol(sensor(), folder)
    path = orig.path
    with open(path, "rb") as f:
        orig_bytes = f.read()
    symbols.set_user_symbols([to_symdef(orig.doc)])
    doc = symbol_to_doc(symbols.get(orig.id))
    doc["prims"].append({"k": "line", "pts": [[-10, 10], [10, 10]], "w": "normal", "dash": False})
    new = lib.save_symbol(doc, folder)
    assert new.id != orig.id and new.path != path
    with open(path, "rb") as f:
        assert f.read() == orig_bytes
    lib2 = userlib.UserLibrary(str(tmp_path / "libs"))
    lib2.scan()
    assert lib2.entries[orig.id].doc["revision"] == orig.doc["revision"]
    assert lib2.entries[new.id].doc["derived_from"]["id"] == orig.id


def test_exploded_primitives_edit_and_round_trip():
    doc = symbol_to_doc(symbols.get("el.capacitor.pol"))
    shapes = [symbol_prim_to_shape(p, i + 1) for i, p in enumerate(doc["prims"])]
    assert any(s.kind == "arc" for s in shapes), "arcs are editable as arcs"
    arc = next(s for s in shapes if s.kind == "arc")
    arc.r += 2                                     # edit one primitive
    doc["prims"] = [shape_to_symbol_prim(s) for s in shapes]
    out = to_symdef(normalise(doc))
    assert terminals(out) == terminals(symbols.get("el.capacitor.pol"))


# ================================================================ drawings and files
def test_replacing_a_placed_symbol_by_its_copy_keeps_wires():
    p = new_project()
    d = p.sheets[0]
    r = editing.place(d, "el.resistor.iec", 0, 0)
    a = r.terminals()["2"]
    w = editing.add_wire(d, [a, (a[0] + 40, a[1])])
    derived = symbol_to_doc(symbols.get("el.resistor.iec"))
    derived["prims"].append({"k": "circle", "c": [0, 0], "r": 2, "fill": True, "w": "normal", "dash": False})
    symbols.set_user_symbols([to_symdef(derived)])
    r.symbol, r.params = derived["id"], {}
    editing.sync_wire_ends(d)
    assert d.wires[w.id].start == [r.id, "2"]
    assert (r.id, "2") in analyse(d).connected_terminals


def test_project_with_derived_symbol_round_trips(tmp_path):
    derived = symbol_to_doc(symbols.get("fl.hyd.throttle"))
    symbols.set_user_symbols([to_symdef(derived)])
    p = new_project()
    c = editing.place(p.sheets[0], derived["id"], 0, 0)
    path = str(tmp_path / "d.schematix")
    projectio.save_project(p, path)
    symbols.set_user_symbols([])
    q = projectio.open_any(path).project
    assert q.symbols[derived["id"]]["derived_from"]["id"] == "fl.hyd.throttle"
    assert set(q.sheets[0].components[c.id].terminals()) == {t.name for t in symbols.get("fl.hyd.throttle")
                                                               .build(None).terminals}


def test_existing_documents_unchanged_by_normalise():
    """Symbols without derived_from (all existing files) normalise exactly as before."""
    d = sensor()
    assert "derived_from" not in d and normalise(json.loads(json.dumps(d))) == d
    junk = dict(d, derived_from="not a dict")
    assert "derived_from" not in normalise(junk)
    assert "derived_from" not in normalise(dict(d, derived_from={"name": "no id"}))
