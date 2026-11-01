"""Phantom-terminal regressions with project-scoped symbol resolution (PR #43 on top of PR #46).

A wire end stores a [component id, terminal name] reference. Before PR #43, any reference to a present
component id created a netlist terminal node for the stored name, even when that pin does not exist,
which silently invented electrical connections in nets, Check, connection lists and CSV exports.

The pin must be validated against the symbol definition of the project that owns the sheet. The symbol
registry is process-wide (it holds the project activated last), and two projects may embed different
definitions under the same custom-symbol id, so validating against the registry would accept a pin that
only the *other* project's symbol defines (or reject one of our own).
"""
from __future__ import annotations

import pytest

from openschematix import check, editing, netlist, projectio, symbols
from openschematix.model import Wire
from openschematix.project import new_project
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef

SID = "user:phantom-shared"


@pytest.fixture(autouse=True)
def clean_registry():
    symbols.set_project_symbols([])
    symbols.set_user_symbols([])
    yield
    symbols.set_project_symbols([])
    symbols.set_user_symbols([])


def shared(reach: int, second_pin: str, name: str) -> dict:
    """Custom symbol `SID`: pin "A" at -reach and pin `second_pin` at +reach."""
    d = blank_symbol(name)
    d["id"] = SID
    d["description"] = name
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "A", "name": "A", "x": -reach, "y": 0, "dir": "l"},
                 {"id": second_pin, "name": second_pin, "x": reach, "y": 0, "dir": "r"}]
    return normalise(d)


def project_with(reach: int, pin: str, name: str):
    """Project embedding shared(reach, pin) with one instance and a resistor R1, wired pin -> R1:1."""
    p = new_project(name)
    p.symbols[SID] = shared(reach, pin, name)
    p.activate_symbols()
    doc = p.sheets[0]
    c = editing.place(doc, SID, 200, 200)
    r = editing.place(doc, "el.resistor.iec", 500, 200)
    w = Wire(doc.new_id(), [c.terminals()[pin], r.terminals()["1"]], [c.id, pin], [r.id, "1"])
    doc.add_wire(w)
    return p, c, r, w


def term_names(nets, cid):
    return {t[2] for n in nets for t in n.terminals if t[1] == cid}


def net_of(nets, wid):
    return next(n for n in nets if any(w[1] == wid for w in n.wires))


def invalid_ref_issues(p):
    return [i for i in check.check(p, rules=["invalid-wire-ref"]) if i.code == "invalid-wire-ref"]


def csv_text(p):
    rows = netlist.connection_rows(p)
    return netlist.to_csv(rows, [("wire", "Wire"), ("from", "From"), ("to", "To"), ("net", "Net")])


def wire_csv_text(p):
    return netlist.to_csv(netlist.wire_rows(p), [("wire", "Wire"), ("from", "From"), ("to", "To")])


# ---------------------------------------------------------------- missing component / blank / unknown pins
def test_missing_component_reference_creates_no_terminal_and_is_reported():
    p = new_project("missing")
    d = p.sheets[0]
    r = editing.place(d, "el.resistor.iec", 100, 100)
    w = Wire(d.new_id(), [(0, 0), (40, 0)], [9999, "1"], None)
    d.add_wire(w)
    assert netlist.classify_pin_ref(d, w.start) == netlist.REF_MISSING_COMPONENT
    nets = netlist.compute_nets(p)
    assert all(t[1] != 9999 for n in nets for t in n.terminals)
    assert not net_of(nets, w.id).terminals
    issues = invalid_ref_issues(p)
    assert len(issues) == 1 and "#9999" in issues[0].message and issues[0].obj_id == w.id
    rows = netlist.wire_rows(p)
    assert rows[0]["from"] == "junction"          # not a terminal tag
    assert "?" not in wire_csv_text(p)


@pytest.mark.parametrize("pin", ["ghost", "", "   ", "2 "])
def test_nonexistent_and_blank_terminal_names_never_join_the_net(pin):
    p = new_project("bad-pin")
    d = p.sheets[0]
    r1 = editing.place(d, "el.resistor.iec", 100, 100)
    r2 = editing.place(d, "el.resistor.iec", 400, 100)
    # the wire is drawn away from every terminal, so only its (bad) reference could connect it
    w = Wire(d.new_id(), [(150, 300), (350, 300)], [r1.id, pin], [r2.id, "1"])
    d.add_wire(w)
    nets = netlist.compute_nets(p)
    assert term_names(nets, r1.id) <= {"1", "2"}
    n = net_of(nets, w.id)
    assert (d.uid, r1.id, pin) not in n.terminals
    assert {(t[1], t[2]) for t in n.terminals} == {(r2.id, "1")}   # the valid end still connects
    issues = invalid_ref_issues(p)
    assert len(issues) == 1 and issues[0].obj_id == w.id
    assert ("blank" in issues[0].message) == (not pin.strip())
    # exports: no row pairs R2:1 with R1 through the phantom pin
    rows = netlist.connection_rows(p, nets)
    assert not any("R1" in r["from"] + r["to"] for r in rows if r["to"] != "(not connected)")
    wires = netlist.wire_rows(p)
    assert wires[0]["from"] == "junction" and wires[0]["to"].startswith("R2")


def test_geometric_joins_junctions_and_crossings_are_preserved():
    p = new_project("geom")
    d = p.sheets[0]
    r = editing.place(d, "el.resistor.iec", 100, 100)
    pt = r.terminals()["1"]
    # end lies on R1:1 geometrically but carries a stale pin name: geometry still connects it to pin 1
    w = Wire(d.new_id(), [pt, (pt[0] - 60, pt[1])], [r.id, "ghost"], None)
    d.add_wire(w)
    t1 = editing.add_wire(d, [(pt[0] - 60, pt[1]), (pt[0] - 60, pt[1] + 80)])   # T junction at the end
    x1 = editing.add_wire(d, [(0, 400), (200, 400)])
    x2 = editing.add_wire(d, [(100, 300), (100, 500)])                            # plain crossing
    nets = netlist.compute_nets(p)
    n = net_of(nets, w.id)
    assert (d.uid, r.id, "1") in n.terminals and (d.uid, r.id, "ghost") not in n.terminals
    assert any(wi[1] == t1.id for wi in n.wires)
    assert net_of(nets, x1.id) is not net_of(nets, x2.id)


# ---------------------------------------------------------------- two projects, same symbol id
def test_validation_uses_owning_project_definition_not_active_registry():
    p1, c1, r1, w1 = project_with(30, "B", "first")     # SID pins: A, B
    p2, c2, r2, w2 = project_with(60, "C", "second")    # SID pins: A, C  (registered last)
    assert symbols.project_owner() is p2
    d1 = p1.sheets[0]
    # direct calls outside any project scope: p1's own definition decides
    assert netlist.pin_ref_connects(d1, [c1.id, "B"])
    assert not netlist.pin_ref_connects(d1, [c1.id, "C"])
    assert netlist.pin_ref_connects(p2.sheets[0], [c2.id, "C"])
    assert not netlist.pin_ref_connects(p2.sheets[0], [c2.id, "B"])
    # engine calls
    nets1 = netlist.compute_nets(p1)
    assert (d1.uid, c1.id, "B") in net_of(nets1, w1.id).terminals
    assert "C" not in term_names(nets1, c1.id)
    assert invalid_ref_issues(p1) == []
    assert symbols.project_owner() is p2                 # the active registration is left as it was


def test_pin_defined_only_by_other_projects_symbol_is_a_phantom():
    p1, c1, r1, w1 = project_with(30, "B", "first")
    d1 = p1.sheets[0]
    # a stale reference to pin "C", which only the *second* project's symbol defines
    stale = Wire(d1.new_id(), [(200, 400), (300, 400)], [c1.id, "C"], None)
    d1.add_wire(stale)
    p2, *_ = project_with(60, "C", "second")
    assert symbols.project_owner() is p2 and symbols.get(SID).custom["description"] == "second"
    assert netlist.classify_pin_ref(d1, stale.start) == netlist.REF_UNKNOWN_PIN
    nets1 = netlist.compute_nets(p1)
    assert "C" not in term_names(nets1, c1.id)
    issues = invalid_ref_issues(p1)
    assert len(issues) == 1 and "'C'" in issues[0].message
    assert all(r["from"] != "" for r in netlist.wire_rows(p1))
    assert ":C" not in csv_text(p1) and ":C" not in wire_csv_text(p1)
    assert symbols.project_owner() is p2


def test_two_projects_save_reopen_keep_their_own_connectivity(tmp_path):
    p1, c1, r1, w1 = project_with(30, "B", "first")
    p2, c2, r2, w2 = project_with(60, "C", "second")
    before1 = sorted(map(repr, (n.terminals for n in netlist.compute_nets(p1))))
    before2 = sorted(map(repr, (n.terminals for n in netlist.compute_nets(p2))))
    csv1, csv2 = csv_text(p1), csv_text(p2)
    f1, f2 = tmp_path / "one.schematix", tmp_path / "two.schematix"
    projectio.save_project(p1, str(f1), snapshot=False)     # p2 is the registered project here
    projectio.save_project(p2, str(f2), snapshot=False)
    q1 = projectio.open_any(str(f1)).project
    q2 = projectio.open_any(str(f2)).project                # q2 registered last
    assert q1.sheets[0].wires[w1.id].start == [c1.id, "B"]
    assert q2.sheets[0].wires[w2.id].start == [c2.id, "C"]
    assert sorted(map(repr, (n.terminals for n in netlist.compute_nets(q1)))) == before1
    assert sorted(map(repr, (n.terminals for n in netlist.compute_nets(q2)))) == before2
    assert csv_text(q1) == csv1 and csv_text(q2) == csv2
    assert invalid_ref_issues(q1) == [] and invalid_ref_issues(q2) == []


# ---------------------------------------------------------------- temporarily unresolved custom symbols
def test_unresolved_custom_symbol_keeps_valid_references_through_save_reopen(tmp_path):
    p, c, r, w = project_with(30, "B", "lib")
    lib_def = to_symdef(p.symbols[SID])
    # the definition lives only in a user library that is not available now
    del p.symbols[SID]
    symbols.set_project_symbols([])
    assert p.symbol_resolver()(SID) is None
    d = p.sheets[0]
    assert netlist.classify_pin_ref(d, w.start) == netlist.REF_UNRESOLVED
    nets = netlist.compute_nets(p)
    assert (d.uid, c.id, "B") in net_of(nets, w.id).terminals
    assert invalid_ref_issues(p) == []                       # the "symbol" rule reports it instead
    f = tmp_path / "unres.schematix"
    projectio.save_project(p, str(f), snapshot=False)
    q = projectio.open_any(str(f)).project
    assert q.sheets[0].wires[w.id].start == [c.id, "B"]      # not discarded on load
    assert (q.sheets[0].uid, c.id, "B") in net_of(netlist.compute_nets(q), w.id).terminals
    # the library becomes available again: the same reference now validates against its pins
    symbols.set_user_symbols([lib_def])
    assert netlist.classify_pin_ref(q.sheets[0], [c.id, "B"]) == netlist.REF_OK
    assert netlist.classify_pin_ref(q.sheets[0], [c.id, "ghost"]) == netlist.REF_UNKNOWN_PIN
    assert invalid_ref_issues(q) == []


# ---------------------------------------------------------------- save / reopen and exports
def test_save_reopen_drops_phantoms_and_preserves_exports(tmp_path):
    p, c, r, w = project_with(30, "B", "rt")
    d = p.sheets[0]
    d.add_wire(Wire(d.new_id(), [(0, 600), (80, 600)], [c.id, "ghost"], None))
    d.add_wire(Wire(d.new_id(), [(0, 700), (80, 700)], [4242, "1"], [r.id, ""]))
    nets = netlist.compute_nets(p)
    assert {"A", "B"} >= term_names(nets, c.id)
    assert len(invalid_ref_issues(p)) == 3
    exported = csv_text(p)
    for bad in (":ghost", "4242"):
        assert bad not in exported and bad not in wire_csv_text(p)
    f = tmp_path / "rt.schematix"
    projectio.save_project(p, str(f), snapshot=False)
    q = projectio.open_any(str(f)).project
    assert csv_text(q) == exported                           # same valid connections after reopen
    assert invalid_ref_issues(q) == []                       # dangling refs are cleared at load (PR #37)
    assert q.sheets[0].wires[w.id].start == [c.id, "B"]


def test_classify_rejects_malformed_references():
    p = new_project("malformed")
    d = p.sheets[0]
    r = editing.place(d, "el.resistor.iec", 0, 0)
    for bad in (None, [], [r.id], [r.id, "1", "x"], ["1", "1"], [True, "1"], "R1:1"):
        assert netlist.classify_pin_ref(d, bad) == netlist.REF_MALFORMED
        assert not netlist.pin_ref_connects(d, bad)
    assert netlist.classify_pin_ref(d, [r.id, "1"]) == netlist.REF_OK
    assert netlist.classify_pin_ref(d, (r.id, "2")) == netlist.REF_OK
