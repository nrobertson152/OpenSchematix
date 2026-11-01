"""Regression tests for electrical, fluid and mixed-domain wire numbering."""

import pytest

from openschematix import check, editing, netlist
from openschematix.model import Document
from openschematix.project import new_project, project_from_document


def _connect(doc, left_symbol, right_symbol):
    left = editing.place(doc, left_symbol, 100, 100)
    right = editing.place(doc, right_symbol, 400, 100)
    a = next(iter(left.terminals().values()))
    b = next(iter(right.terminals().values()))
    y = min(a[1], b[1]) - 80
    wire = editing.add_wire(doc, [a, (a[0], y), (b[0], y), b])
    assert wire is not None
    return wire


@pytest.mark.parametrize(
    ("left", "right", "domains", "eligible"),
    [
        ("el.resistor.iec", "el.coil.iec", {"elec"}, True),
        ("fl.hyd.pump", "fl.hyd.tank", {"hyd"}, False),
        ("fl.pneu.dcv", "fl.pneu.gauge", {"pneu"}, False),
        ("fl.hyd.pump", "el.resistor.iec", {"hyd", "elec"}, False),
        ("fl.pneu.dcv", "el.resistor.iec", {"pneu", "elec"}, False),
        ("fl.hyd.pump", "fl.pneu.dcv", {"hyd", "pneu"}, False),
        ("gen.block2", "gen.block2", set(), True),
        ("gen.block2", "el.resistor.iec", {"elec"}, True),
    ],
)
def test_numbering_respects_all_net_domains(left, right, domains, eligible):
    project = new_project()
    doc = project.sheets[0]
    wire = _connect(doc, left, right)

    nets = [n for n in netlist.compute_nets(project) if (doc.uid, wire.id) in n.wires]
    assert len(nets) == 1
    net = nets[0]
    assert netlist.net_domain(project, net) == domains
    assert netlist.numberable(project, net) is eligible

    changed = netlist.assign_wire_numbers(project)
    assert changed == (1 if eligible else 0)
    assert bool(wire.number) is eligible
    assert netlist.wire_rows(project)[0]["wire"] == wire.number


@pytest.mark.parametrize("medium", ["hyd", "pneu"])
def test_mixed_domain_clears_stale_automatic_number_and_keeps_manual_number(medium):
    project = new_project()
    doc = project.sheets[0]
    fluid = "fl.hyd.pump" if medium == "hyd" else "fl.pneu.dcv"
    wire = _connect(doc, "el.resistor.iec", fluid)
    wire.number = "W017"
    wire.number_manual = False

    assert netlist.assign_wire_numbers(project) == 0
    assert wire.number == ""
    assert netlist.compute_nets(project)[0].number == ""
    assert all(row["wire"] == "" for row in netlist.connection_rows(project))
    assert any(issue.code == "port-domain" for issue in check.check(project))

    wire.number = "USER"
    wire.number_manual = True
    assert netlist.assign_wire_numbers(project, renumber=True) == 0
    assert wire.number == "USER"
    assert wire.number_manual is True


def test_mixed_domains_connected_across_sheets_not_numbered():
    project = new_project()
    first = project.sheets[0]
    second = project.add_sheet()
    electric = editing.place(first, "el.resistor.iec", 100, 100)
    hydraulic = editing.place(second, "fl.hyd.pump", 100, 100)
    first_link = editing.place(first, "gen.offpage", 400, 100)
    second_link = editing.place(second, "gen.offpage", 400, 100)
    first_link.label = second_link.label = "CROSS-DOMAIN"
    a = next(iter(electric.terminals().values()))
    b = next(iter(first_link.terminals().values()))
    c = next(iter(hydraulic.terminals().values()))
    d = next(iter(second_link.terminals().values()))
    wire_a = editing.add_wire(first, [a, (a[0], 0), (b[0], 0), b])
    wire_b = editing.add_wire(second, [c, (c[0], 0), (d[0], 0), d])
    assert wire_a is not None and wire_b is not None

    nets = [n for n in netlist.compute_nets(project) if (first.uid, wire_a.id) in n.wires]
    assert len(nets) == 1
    assert (second.uid, wire_b.id) in nets[0].wires
    assert netlist.net_domain(project, nets[0]) == {"elec", "hyd"}
    assert not netlist.numberable(project, nets[0])
    assert netlist.assign_wire_numbers(project) == 0
    assert wire_a.number == wire_b.number == ""


def test_mixed_domain_numbering_after_legacy_sheet_roundtrip():
    project = new_project()
    doc = project.sheets[0]
    wire = _connect(doc, "el.resistor.iec", "fl.hyd.pump")
    wire.number = "OLD_AUTO"
    restored = project_from_document(Document.from_dict(doc.to_dict()))

    assert netlist.assign_wire_numbers(restored) == 0
    assert next(iter(restored.sheets[0].wires.values())).number == ""
    assert any(issue.code == "port-domain" for issue in check.check(restored))
