"""Directional-valve configurator additions (symbol-library expansion batch F1).

New operators (detents, spool controls, pilot and solenoid-pilot forms, drives, thermal, servo), the Y32.10
10.11.3 centre conditions, and the proportional / transition options. Existing valve configurations are
covered by the geometry baseline in test_bundled_symbol_library.py; these tests cover the new drawings and the
valve dialog's third operator slot and option checkboxes.
"""
from __future__ import annotations

import itertools
import os
import tempfile

import pytest

from openschematix import editing, netlist, projectio, symbols
from openschematix.geometry import GRID
from openschematix.project import new_project
from openschematix.symbols import fluid
from openschematix.symbols.base import validate_geometry

from test_bundled_symbol_library import _on_drawing

NEW_OPS = sorted(fluid.EXT_OPERATORS)
PILOT_OPS = {"pilot.direct", "pilot.applied", "pilot.remote", "release.remote", "solenoid.or.pilot.ext",
             "solenoid.and.pilot.ext"}


def test_every_new_operator_is_offered_by_the_configurator():
    assert set(NEW_OPS) <= set(fluid.OPERATORS)
    assert list(fluid.OPERATORS)[:6] == ["spring", "solenoid", "pilot", "lever", "pushbutton", "manual"]
    labels = list(fluid.OPERATORS.values())
    assert len(labels) == len(set(labels)), "the dialog maps labels back to operators"


def _valid(g):
    assert not validate_geometry(g), validate_geometry(g)
    for t in g.terminals:
        assert t.x % GRID == 0 and t.y % GRID == 0, (t.name, t.x, t.y)
        assert _on_drawing(g, t.x, t.y), (t.name, t.x, t.y)
    names = [t.name for t in g.terminals]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("medium", ["hyd", "pneu"])
@pytest.mark.parametrize("op", NEW_OPS)
def test_new_operator_draws_on_both_sides_of_every_valve_type(medium, op):
    for vtype in fluid.VALVE_TYPES[medium]:
        d = fluid.default_valve_params(medium, vtype)
        for left, right in (([op], ["spring"]), (["spring"], [op]), ([op], [op]), ([op, "manual"], ["lever", op])):
            g = fluid.build_valve({**d, "left": left, "right": right})
            _valid(g)
            ports = {t.name for t in fluid.build_valve(d).terminals}
            pilots = [t for t in g.terminals if t.name not in ports]
            expected = sum(1 for o in left + right if o in PILOT_OPS)
            assert len(pilots) == expected, (op, vtype, left, right, [t.name for t in pilots])


@pytest.mark.parametrize("op", sorted(PILOT_OPS))
def test_pilot_terminal_has_pilot_port_type_and_names(op):
    sd = symbols.get("fl.hyd.dcv")
    g = sd.build({**fluid.default_valve_params("hyd", "4/3"), "left": [op], "right": ["spring", op]})
    pilots = [t for t in g.terminals if t.name not in ("A", "B", "P", "T")]
    assert sorted(t.name for t in pilots) == ["X", "Y"]
    assert all(sd.port_type(t) == "hyd.pilot" for t in pilots)
    ps = symbols.get("fl.pneu.dcv")
    g = ps.build({**fluid.default_valve_params("pneu", "5/2"), "left": [op], "right": [op]})
    assert {ps.port_type(t) for t in g.terminals if t.name in ("12", "14")} == {"pneu.pilot"}


def test_operator_chain_of_three_keeps_pilot_on_grid_at_the_end():
    d = fluid.default_valve_params("hyd", "4/3")
    for a, b, c in itertools.permutations(["detent", "solenoid.and.pilot.int", "pedal2", "motor.reversing",
                                           "thermal.bulb", "spring"], 3):
        g = fluid.build_valve({**d, "left": [a, b, c, "pilot"], "right": [c, b, a]})
        _valid(g)
        assert any(t.name == "X" for t in g.terminals)


def test_detent_has_one_notch_per_position_and_marks_the_rest_position():
    for vtype, npos in (("4/2", 2), ("4/3", 3)):
        d = fluid.default_valve_params("hyd", vtype)
        prims, width, term = fluid._operator("detent", 0, 1, True, {"npos": npos, "normal": 1})
        rod = prims[0]["pts"]
        notches = [pt for pt in rod if pt[1] == 4.0]
        assert len(notches) == npos and width == 20 and term is None
        mark = prims[1]["pts"]
        assert mark[0][0] == mark[1][0] == sorted(n[0] for n in notches)[1]
        _valid(fluid.build_valve({**d, "left": ["detent", "lever"], "right": ["detent"]}))


@pytest.mark.parametrize("centre", ["b-t", "apt", "ab", "a-t", "ab-pt"])
def test_new_centre_conditions(centre):
    """Y32.10 10.11.3: link pattern and blocked ports as drawn in the source."""
    pat = fluid.PATTERNS[4][centre]
    assert {"b-t": [0, 2], "apt": [1], "ab": [2, 3], "a-t": [1, 2], "ab-pt": []}[centre] == pat["blocked"]
    d = fluid.default_valve_params("hyd", "4/3")
    g = fluid.build_valve({**d, "positions": ["parallel", centre, "crossed"]})
    _valid(g)
    assert sorted(t.name for t in g.terminals) == ["A", "B", "P", "T"]
    assert g.bbox()[1] >= -30 and g.bbox()[3] <= 30


def test_proportional_and_transition_options():
    d = fluid.default_valve_params("hyd", "4/2")
    plain = fluid.build_valve(d)
    prop = fluid.build_valve({**d, "proportional": True})
    assert len(prop.prims) == len(plain.prims) + 2
    assert [(t.name, t.x, t.y) for t in prop.terminals] == [(t.name, t.x, t.y) for t in plain.terminals]
    tr = fluid.build_valve({**d, "transition": True})
    _valid(tr)
    assert tr.bbox()[2] - tr.bbox()[0] == plain.bbox()[2] - plain.bbox()[0] + 20
    assert sum(1 for p in tr.prims if p.get("dash")) == 2
    d3 = fluid.default_valve_params("hyd", "4/3")
    assert fluid.build_valve({**d3, "transition": True}).prims == fluid.build_valve(d3).prims, \
        "transition applies to two-position valves only"
    assert "proportional" in fluid.valve_summary({**d, "proportional": True})
    assert fluid.valve_summary(d) == fluid.valve_summary({**d, "proportional": False})


def test_configured_valve_wires_saves_and_reopens(tmp_path):
    p = new_project("Configurator")
    doc = p.sheets[0]
    params = {**fluid.default_valve_params("hyd", "4/3"), "positions": ["parallel", "apt", "crossed"],
              "left": ["spring", "solenoid.and.pilot.ext", "manual"], "right": ["spring", "detent", "lever"],
              "proportional": True}
    v = editing.place(doc, "fl.hyd.dcv", 400, 400, params=params)
    wires = {}
    for name, (x, y) in v.terminals().items():
        dy = -30 if name in ("A", "B", "X") else 30
        wires[name] = editing.add_wire(doc, [(x, y), (x, y + dy)]).id
    assert set(wires) == {"A", "B", "P", "T", "X"}
    path = tmp_path / "valve.schematix"
    projectio.save_project(p, str(path), snapshot=False)
    q = projectio.open_any(str(path)).project
    qv = q.sheets[0].components[v.id]
    assert qv.params == params
    for name, wid in wires.items():
        assert q.sheets[0].wires[wid].start == [v.id, name]
    nets = netlist.compute_nets(q)
    assert all(any((q.sheets[0].uid, v.id, n) in net.terminals for net in nets) for n in wires)


# ---------------------------------------------------------------- valve dialog (Tk)
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


@pytest.mark.gui
def test_dialog_offers_three_operator_slots_and_options(app):
    from openschematix.gui.dialogs import ValveDialog
    p = new_project()
    p.activate_symbols()
    app._reset(p, None)
    v = editing.place(app.doc, "fl.hyd.dcv", 400, 400)
    original = dict(v.params)
    dlg = ValveDialog(app, v.id)
    try:
        assert {k for k in dlg.op_vars} == {(s, i) for s in ("left", "right") for i in range(3)}
        assert set(dlg.opt_vars) == set(fluid.VALVE_OPTIONS)
        assert dlg._collect() == original, "opening and applying unchanged must not alter an existing valve"
        dlg.op_vars[("right", 2)].set(fluid.OPERATORS["detent"])
        dlg.op_vars[("left", 1)].set(fluid.OPERATORS["solenoid.and.pilot.ext"])
        dlg.opt_vars["proportional"].set(True)
        dlg._update()
        got = dlg._collect()
        assert got["left"] == ["spring", "solenoid.and.pilot.ext"]
        assert got["right"] == ["spring", "solenoid", "detent"]
        assert got["proportional"] is True and "transition" not in got
        dlg.ok()
    finally:
        if dlg.winfo_exists():
            dlg.destroy()
    c = app.doc.components[v.id]
    assert c.params["right"] == ["spring", "solenoid", "detent"] and c.params["proportional"] is True
    assert "X" in c.terminals()
