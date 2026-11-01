"""Independent, deterministic cross-feature engineering invariants (Issue #53).

These expected outcomes derive from physical topology and declared port domains;
they do not compare against a copy of an implementation algorithm.
"""
import pytest

from openschematix import bom, check, editing, netlist
from openschematix.project import new_project


def _between(doc, left, lpin, right, rpin, via_y=None):
    a = left.terminals()[lpin]
    b = right.terminals()[rpin]
    if via_y is None:
        points = [a, b]
    else:
        points = [a, (a[0], via_y), (b[0], via_y), b]
    wire = editing.add_wire(doc, points)
    assert wire is not None
    assert wire.start == [left.id, lpin]
    assert wire.end == [right.id, rpin]
    return wire


def _net_for(project, sheet, component, pin):
    term = (sheet.uid, component.id, pin)
    matches = [n for n in netlist.compute_nets(project) if term in n.terminals]
    assert len(matches) == 1, (term, [(n.terminals, n.wires) for n in matches])
    return matches[0]


def test_component_transform_preserves_exact_terminal_net_membership_and_bom():
    project = new_project("Transform invariant")
    sheet = project.sheets[0]
    a = editing.place(sheet, "el.resistor.iec", 100, 200)
    b = editing.place(sheet, "el.resistor.iec", 400, 200)
    wire = _between(sheet, a, "2", b, "1")
    expected = {(sheet.uid, a.id, "2"), (sheet.uid, b.id, "1")}
    quantity = sum(row.quantity for row in bom.generate(project))
    assert quantity == 2

    for operation in (
        lambda: editing.move_items(sheet, [a.id], [], 20, 40),
        lambda: editing.rotate_items(sheet, [a.id], [], clockwise=True),
        lambda: editing.mirror_items(sheet, [a.id], []),
        lambda: editing.move_items(sheet, [b.id], [], -30, 20),
    ):
        operation()
        assert set(_net_for(project, sheet, a, "2").terminals) == expected
        assert sheet.wires[wire.id].start == [a.id, "2"]
        assert sheet.wires[wire.id].end == [b.id, "1"]
        assert sheet.wires[wire.id].points[0] == a.terminals()["2"]
        assert sheet.wires[wire.id].points[-1] == b.terminals()["1"]
        assert sum(row.quantity for row in bom.generate(project)) == quantity
        assert not [i for i in check.check(project, rules={"dangling-wire"}) if i.obj_id == wire.id]


def test_wire_segmentation_preserves_physical_connectivity_but_not_wire_count():
    project = new_project("Segmented topology")
    sheet = project.sheets[0]
    a = editing.place(sheet, "el.resistor.iec", 100, 200)
    b = editing.place(sheet, "el.resistor.iec", 400, 200)
    pa, pb = a.terminals()["2"], b.terminals()["1"]
    mid = ((pa[0] + pb[0]) / 2, pa[1])
    first = editing.add_wire(sheet, [pa, mid])
    second = editing.add_wire(sheet, [mid, pb])
    assert first and second
    expected = {(sheet.uid, a.id, "2"), (sheet.uid, b.id, "1")}
    assert set(_net_for(project, sheet, a, "2").terminals) == expected
    assert set(_net_for(project, sheet, a, "2").wires) == {
        (sheet.uid, first.id), (sheet.uid, second.id)
    }
    assert sum(row.quantity for row in bom.generate(project)) == 2
    assert not [i for i in check.check(project, rules={"dangling-wire"})]

    # Replacing two touching segments with a single electrically identical
    # segment must preserve the net's terminal set and device count.
    sheet.wires.clear()
    single = _between(sheet, a, "2", b, "1")
    assert set(_net_for(project, sheet, a, "2").terminals) == expected
    assert _net_for(project, sheet, a, "2").wires == [(sheet.uid, single.id)]
    assert sum(row.quantity for row in bom.generate(project)) == 2


def test_cross_sheet_labels_isolate_unrelated_nets_and_rejoin_only_when_equal():
    project = new_project("Cross-sheet isolation")
    first, second = project.sheets[0], project.add_sheet()
    a = editing.place(first, "el.resistor.iec", 100, 100)
    b = editing.place(second, "el.lamp.iec", 100, 100)
    link_a = editing.place(first, "gen.offpage", 400, 100)
    link_b = editing.place(second, "gen.offpage", 400, 100)
    link_a.label = "NET_ALPHA"
    link_b.label = "NET_BETA"
    _between(first, a, "2", link_a, "1", via_y=40)
    _between(second, b, "2", link_b, "1", via_y=40)
    ta, tb = (first.uid, a.id, "2"), (second.uid, b.id, "2")

    assert tb not in _net_for(project, first, a, "2").terminals
    assert sorted(i.code for i in check.check(project, rules={"xref"})) == ["xref", "xref"]
    link_b.label = "NET_ALPHA"
    assert tb in _net_for(project, first, a, "2").terminals
    assert ta in _net_for(project, second, b, "2").terminals
    assert check.check(project, rules={"xref"}) == []
    link_a.label = "NET_GAMMA"
    assert tb not in _net_for(project, first, a, "2").terminals
    assert len([i for i in check.check(project, rules={"xref"}) if i.severity == "error"]) == 2


@pytest.mark.parametrize(
    ("left", "lpin", "right", "rpin", "expected_domains", "must_error"),
    [
        ("el.resistor.iec", "2", "el.lamp.iec", "1", {"elec"}, False),
        ("fl.hyd.pump", "P", "fl.hyd.tank", "T", {"hyd"}, False),
        ("fl.hyd.pump", "P", "el.resistor.iec", "1", {"hyd", "elec"}, True),
        ("fl.pneu.gauge", "1", "fl.hyd.pump", "P", {"pneu", "hyd"}, True),
    ],
)
def test_erc_domain_consistency_with_netlist(left, lpin, right, rpin, expected_domains, must_error):
    project = new_project("Port-domain agreement")
    sheet = project.sheets[0]
    a = editing.place(sheet, left, 100, 100)
    b = editing.place(sheet, right, 400, 100)
    w = _between(sheet, a, lpin, b, rpin, via_y=0)
    n = _net_for(project, sheet, a, lpin)
    assert (sheet.uid, b.id, rpin) in n.terminals
    assert (sheet.uid, w.id) in n.wires
    assert netlist.net_domain(project, n) == expected_domains
    violations = [i for i in check.check(project, rules={"port-domain"}) if i.code == "port-domain"]
    assert bool(violations) == must_error
    if must_error:
        assert all(i.severity == "error" for i in violations)


def test_bom_is_invariant_under_wire_changes_and_agrees_with_connection_rows():
    project = new_project("BOM independence")
    sheet = project.sheets[0]
    a = editing.place(sheet, "el.resistor.iec", 100, 100)
    b = editing.place(sheet, "el.resistor.iec", 400, 100)
    c = editing.place(sheet, "el.lamp.iec", 700, 100)
    w = _between(sheet, a, "2", b, "1")
    baseline = [(row.quantity, row.description, tuple(row.designators))
                for row in bom.generate(project)]
    assert sum(q for q, *_ in baseline) == 3
    net = _net_for(project, sheet, a, "2")
    expected = {(sheet.uid, a.id, "2"), (sheet.uid, b.id, "1")}
    assert set(net.terminals) == expected
    rows = netlist.connection_rows(project)
    assert len([r for r in rows if r["net"] == net.index]) == 1
    # The unconnected lamp is a purchase item, not a connection-list edge.
    assert c.designator in {d for line in bom.generate(project) for d in line.designators}

    sheet.wires.pop(w.id)
    assert [(r.quantity, r.description, tuple(r.designators)) for r in bom.generate(project)] == baseline
    assert not any(expected <= set(n.terminals) for n in netlist.compute_nets(project))
    wire2 = _between(sheet, a, "2", b, "1", via_y=0)
    assert wire2.id != w.id
    assert set(_net_for(project, sheet, a, "2").terminals) == expected
    assert [(r.quantity, r.description, tuple(r.designators)) for r in bom.generate(project)] == baseline
