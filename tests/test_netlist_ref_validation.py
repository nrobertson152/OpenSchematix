"""Regression: invalid wire pin references must not create phantom netlist terminals."""
from __future__ import annotations

import json

from openschematix import check, editing, netlist, projectio, symbols
from openschematix.model import Wire
from openschematix.project import new_project
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef


def _terminal_pairs(nets):
    return sorted((tuple(sorted((t[1], t[2]) for t in n.terminals)),
                   tuple(sorted(n.wires))) for n in nets)


def test_valid_wire_to_pin_connection():
    p = new_project("v")
    d = p.sheets[0]
    c = editing.place(d, "el.resistor.iec", 100, 100)
    w = editing.add_wire(d, [c.terminals()["1"], (40, 100)])
    assert w.start == [c.id, "1"]
    nets = netlist.compute_nets(p)
    assert any((c.id, "1") in [(t[1], t[2]) for t in n.terminals] and n.wires for n in nets)
    rows = netlist.connection_rows(p, nets)
    assert any("R1" in (r.get("from") or "") or "R1" in (r.get("to") or "") for r in rows)


def test_nonexistent_pin_does_not_create_phantom_terminal():
    p = new_project("ghost")
    d = p.sheets[0]
    c = editing.place(d, "el.resistor.iec", 100, 100)
    w = Wire(id=d.new_id(), points=[(0, 0), (40, 0)], start=[c.id, "ghost"], end=None)
    d.add_wire(w)
    nets = netlist.compute_nets(p)
    assert (c.id, "ghost") not in [(t[1], t[2]) for n in nets for t in n.terminals]
    assert "ghost" not in json.dumps(netlist.connection_rows(p, nets))
    assert netlist.pin_ref_connects(d, [c.id, "ghost"]) is False


def test_nonexistent_component_id_ignored():
    p = new_project("miss")
    d = p.sheets[0]
    d.add_wire(Wire(id=d.new_id(), points=[(0, 0), (40, 0)], start=[9999, "1"]))
    nets = netlist.compute_nets(p)
    assert all(t[1] != 9999 for n in nets for t in n.terminals)
    assert not netlist.pin_ref_connects(d, [9999, "1"])


def test_empty_and_blank_pin_ids_ignored():
    p = new_project("blank")
    d = p.sheets[0]
    c = editing.place(d, "el.resistor.iec", 0, 0)
    for bad in ("", "  ", None):
        assert not netlist.pin_ref_connects(d, [c.id, bad])
    d.add_wire(Wire(id=d.new_id(), points=[(0, 0), (10, 0)],
                    start=[c.id, ""], end=[c.id, "  "]))
    assert all(t[2] not in ("", "  ") for n in netlist.compute_nets(p) for t in n.terminals)


def test_deleted_component_surviving_wire_cleared_by_delete_items():
    p = new_project("del")
    d = p.sheets[0]
    c = editing.place(d, "el.resistor.iec", 100, 100)
    w = editing.add_wire(d, [c.terminals()["1"], (40, 100)])
    editing.delete_items(d, [c.id])
    assert w.start is None
    nets = netlist.compute_nets(p)
    assert all(not n.terminals for n in nets if any(wid == w.id for _, wid in n.wires))


def test_geometric_connection_without_ref_still_nets():
    p = new_project("geom")
    d = p.sheets[0]
    c = editing.place(d, "el.resistor.iec", 100, 100)
    pt = c.terminals()["1"]
    w = Wire(id=d.new_id(), points=[pt, (pt[0] - 40, pt[1])])
    d.add_wire(w)
    nets = netlist.compute_nets(p)
    assert any((c.id, "1") in [(t[1], t[2]) for t in n.terminals]
               and any(wid == w.id for _, wid in n.wires) for n in nets)


def test_t_junction_and_crossing_rules():
    p = new_project("geom_rules")
    d = p.sheets[0]
    editing.add_wire(d, [(0, 0), (100, 0)])
    editing.add_wire(d, [(50, 0), (50, 50)])
    assert any(len(n.wires) >= 2 for n in netlist.compute_nets(p))
    p2 = new_project("cross")
    d2 = p2.sheets[0]
    editing.add_wire(d2, [(0, 0), (100, 0)])
    editing.add_wire(d2, [(50, -50), (50, 50)])
    assert all(len(n.wires) == 1 for n in netlist.compute_nets(p2) if n.wires)


def _custom_symbol():
    doc = blank_symbol("CR")
    doc["prims"] = [{"k": "line", "pts": [[-20, 0], [20, 0]], "w": "normal"}]
    doc["pins"] = [
        {"id": "pA", "name": "A", "x": -20, "y": 0, "dir": "l", "type": "elec.passive", "show": True},
        {"id": "pB", "name": "B", "x": 20, "y": 0, "dir": "r", "type": "elec.passive", "show": True},
    ]
    return normalise(doc)


def test_custom_symbol_valid_pin_connects():
    doc = _custom_symbol()
    sd = to_symdef(doc)
    p = new_project("custom")
    p.symbols[sd.id] = doc
    p.activate_symbols()
    d = p.sheets[0]
    c = editing.place(d, sd.id, 100, 100)
    w = editing.add_wire(d, [c.terminals()["pA"], (50, 100)])
    assert netlist.pin_ref_connects(d, w.start)
    assert any((c.id, "pA") in [(t[1], t[2]) for t in n.terminals]
               for n in netlist.compute_nets(p))


def test_unresolved_custom_symbol_keeps_named_pin_ref():
    doc = _custom_symbol()
    sid = doc["id"]
    p = new_project("unres")
    p.symbols[sid] = doc
    p.activate_symbols()
    d = p.sheets[0]
    c = editing.place(d, sid, 100, 100)
    editing.add_wire(d, [c.terminals()["pA"], (50, 100)])
    # Genuinely unresolved: neither this project, the registry nor a user library defines the symbol
    # (e.g. a damaged embedded definition, or a file opened where its library is missing).
    del p.symbols[sid]
    symbols.set_project_symbols([])
    assert symbols.get(sid) is None and p.symbol_resolver()(sid) is None
    # Its pins are unknown here, so named attachments are kept rather than discarded.
    assert netlist.pin_ref_connects(d, [c.id, "pA"])
    assert netlist.pin_ref_connects(d, [c.id, "ghost"])
    assert any((c.id, "pA") in [(t[1], t[2]) for t in n.terminals]
               for n in netlist.compute_nets(p))


def test_clearing_registry_does_not_hide_projects_own_symbol():
    """The owning project's embedded definition validates its pins even when the process-wide
    registry no longer holds it (it is not "unresolved")."""
    doc = _custom_symbol()
    sid = doc["id"]
    p = new_project("own")
    p.symbols[sid] = doc
    p.activate_symbols()
    d = p.sheets[0]
    c = editing.place(d, sid, 100, 100)
    symbols.set_project_symbols([])
    assert netlist.pin_ref_connects(d, [c.id, "pA"])
    assert not netlist.pin_ref_connects(d, [c.id, "ghost"])


def test_save_load_roundtrip_preserves_valid_nets(tmp_path):
    p = new_project("rt")
    d = p.sheets[0]
    c = editing.place(d, "el.resistor.iec", 100, 100)
    editing.add_wire(d, [c.terminals()["1"], (40, 100)])
    before = _terminal_pairs(netlist.compute_nets(p))
    path = tmp_path / "rt.schematix"
    projectio.save_project(p, str(path), snapshot=False)
    after = _terminal_pairs(netlist.compute_nets(projectio.open_any(str(path)).project))
    assert before == after


def test_erc_reports_invalid_wire_ref():
    p = new_project("erc")
    d = p.sheets[0]
    c = editing.place(d, "el.resistor.iec", 100, 100)
    d.add_wire(Wire(id=d.new_id(), points=[(0, 0), (40, 0)], start=[c.id, "ghost"]))
    issues = [i for i in check.check(p) if i.code == "invalid-wire-ref"]
    assert issues and any("ghost" in i.message for i in issues)


def test_csv_export_has_no_phantom_names():
    p = new_project("csv")
    d = p.sheets[0]
    c = editing.place(d, "el.resistor.iec", 100, 100)
    d.add_wire(Wire(id=d.new_id(), points=[(0, 0), (10, 0)], start=[c.id, "ghost"]))
    editing.add_wire(d, [c.terminals()["1"], (40, 100)])
    nets = netlist.compute_nets(p)
    rows = netlist.connection_rows(p, nets)
    csv = netlist.to_csv(rows, [("from", "from"), ("to", "to"), ("net", "net")])
    assert "ghost" not in csv
