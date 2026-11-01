"""Independent engineering-outcome regressions for project-scoped symbols.

These tests complement (not duplicate) test_project_symbol_scope.py in PR #46.
A and B deliberately have equal symbol IDs, different complete definitions and
different terminal positions. No test changes production code or global settings
outside the existing registry-isolation fixture.
"""
import copy
import hashlib
import json

import pytest

from openschematix import bom, check, connectivity, export, netlist, projectio, revisions, symbols
from openschematix.model import Wire
from openschematix.project import new_project
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef

SID = "user:independent-regression-scope"


def definition(name, reach, revision=1):
    d = blank_symbol(name)
    d.update(id=SID, description=name, revision=revision)
    d["prims"] = [{"k": "line", "pts": [[-reach, -10], [reach, 10]]},
                  {"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "L", "name": "L", "x": -reach, "y": 0, "dir": "l"},
                 {"id": "R", "name": "R", "x": reach, "y": 0, "dir": "r"}]
    return normalise(d)


def make(name, reach, revision=1):
    p = new_project(name)
    p.symbols[SID] = definition(name, reach, revision)
    p.activate_symbols()
    d = p.sheets[0]
    from openschematix import editing
    c = editing.place(d, SID, 200, 200)
    resistor = editing.place(d, "el.resistor.iec", 500, 200)
    w = Wire(d.new_id(), [c.terminals()["R"], resistor.terminals()["1"]],
             [c.id, "R"], [resistor.id, "1"])
    d.add_wire(w)
    editing.reroute(d, w)
    return p, c.id, resistor.id, w.id


def signature(p, custom_id, resistor_id, wire_id):
    d = p.sheets[0]
    nets = netlist.compute_nets(p)
    own = (d.uid, custom_id, "R")
    dest = (d.uid, resistor_id, "1")
    assert any(own in n.terminals and dest in n.terminals for n in nets)
    assert connectivity.analyse(d).open_wire_ends == []
    assert d.wires[wire_id].start == [custom_id, "R"]
    assert d.wires[wire_id].end == [resistor_id, "1"]
    return (
        tuple(sorted((n.code, n.severity) for n in check.check(p))),
        tuple((x.quantity, x.description, x.part_number) for x in bom.generate(p)),
        export.to_svg(d, use_sheet=False, project=p),
    )


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def same_symbol(actual, expected):
    """A JSON round trip converts tuples to lists without changing geometry."""
    return digest(actual) == digest(expected)


def test_nested_scopes_restore_every_layer_and_cache_after_inner_exception():
    a, *_ = make("Nested A", 20)
    b, *_ = make("Nested B", 40)
    c, *_ = make("Nested C", 60)
    assert symbols.project_owner() is c
    with symbols.project_scope(a):
        assert symbols.project_owner() is a
        assert symbols.geometry(SID).terminals[1].x == 20
        with pytest.raises(ZeroDivisionError):
            with symbols.project_scope(b):
                assert symbols.project_owner() is b
                assert symbols.geometry(SID).terminals[1].x == 40
                1 / 0
        assert symbols.project_owner() is a
        assert symbols.geometry(SID).terminals[1].x == 20
    assert symbols.project_owner() is c
    assert symbols.geometry(SID).terminals[1].x == 60


def test_repeated_nonactive_save_preserves_exact_embedded_document_and_reopen(tmp_path):
    a, ac, ar, aw = make("Persistent A", 20)
    b, *_ = make("Persistent B", 40, revision=99)
    original = copy.deepcopy(a.symbols[SID])
    original_hash = digest(original)
    baseline = signature(a, ac, ar, aw)
    assert symbols.project_owner() is b
    for i in range(4):
        target = tmp_path / ("iteration_%s.schematix" % i)
        projectio.save_project(a, str(target), snapshot=False)
        assert same_symbol(a.symbols[SID], original)
        assert digest(a.symbols[SID]) == original_hash
        assert symbols.project_owner() is b
        reopened = projectio.open_any(str(target), activate=False).project
        assert same_symbol(reopened.symbols[SID], original)
        assert digest(reopened.symbols[SID]) == original_hash
        assert signature(reopened, ac, ar, aw) == baseline
        assert symbols.project_owner() is b
        a = reopened


def test_approved_revision_restores_original_geometry_after_foreign_activation(tmp_path):
    a, ac, ar, aw = make("Revision A", 20)
    b, *_ = make("Revision B", 40, revision=99)
    original = copy.deepcopy(a.symbols[SID])
    a.revisions = revisions.RevisionStore()
    first = a.revisions.create(a, "approved", label="A")
    assert first is not None
    assert symbols.project_owner() is b
    assert a.revisions.load(first["n"]).symbols[SID] == original
    a.sheets[0].components[ac].label = "changed after approval"
    second = a.revisions.create(a, "approved", label="B")
    assert second is not None
    saved = tmp_path / "revisions.schematix"
    projectio.save_project(a, str(saved), snapshot=False)
    q = projectio.open_any(str(saved), activate=False).project
    assert same_symbol(q.symbols[SID], original)
    for n in (first["n"], second["n"]):
        old = q.revisions.load(n)
        assert same_symbol(old.symbols[SID], original)
        assert signature(old, ac, ar, aw)[0] == signature(a, ac, ar, aw)[0]
    restored = revisions.restore(q, q.revisions, first["n"])
    assert same_symbol(restored.symbols[SID], original)
    assert restored.sheets[0].components[ac].label != "changed after approval"
    assert symbols.project_owner() is b


@pytest.mark.parametrize("order", [
    ("a", "b", "a", "b", "a"),
    ("b", "a", "b", "a", "b"),
])
def test_interleaving_engine_operations_does_not_change_earlier_results(order):
    a, ac, ar, aw = make("Order A", 20)
    b, bc, br, bw = make("Order B", 40)
    subjects = {"a": (a, ac, ar, aw), "b": (b, bc, br, bw)}
    expected = {}
    before = {key: digest(p.symbols[SID]) for key, (p, *_rest) in subjects.items()}
    for key in order:
        p, custom_id, resistor_id, wire_id = subjects[key]
        result = signature(p, custom_id, resistor_id, wire_id)
        if key in expected:
            assert result == expected[key]
        else:
            expected[key] = result
        assert digest(p.symbols[SID]) == before[key]


def test_user_library_conflict_never_overrides_embedded_source_on_save(tmp_path):
    a, ac, ar, aw = make("Embedded A", 20)
    b, *_ = make("Embedded B", 40)
    library = definition("Conflicting library", 60, revision=100)
    symbols.set_user_symbols([to_symdef(library)])
    original = copy.deepcopy(a.symbols[SID])
    filename = tmp_path / "isolated.schematix"
    projectio.save_project(a, str(filename), snapshot=False)
    q = projectio.open_any(str(filename), activate=False).project
    assert same_symbol(q.symbols[SID], original)
    assert signature(q, ac, ar, aw) == signature(a, ac, ar, aw)
    assert symbols.project_owner() is b


def test_project_pdf_is_identical_whether_or_not_another_project_is_active():
    a, *_ = make("PDF A", 20)
    b, *_ = make("PDF B", 40)
    assert symbols.project_owner() is b
    foreign = export.project_pdf(a)
    assert symbols.project_owner() is b
    a.activate_symbols()
    own = export.project_pdf(a)
    assert foreign == own
    assert own.startswith(b"%PDF")


def test_failed_scoped_operation_restores_state_and_leaves_projects_unchanged(monkeypatch):
    a, *_ = make("Error A", 20)
    b, *_ = make("Error B", 40)
    original = copy.deepcopy(a.to_dict())
    assert symbols.project_owner() is b
    from openschematix import netlist as nl
    def fail(*args, **kwargs):
        raise RuntimeError("injected netlist failure")
    monkeypatch.setattr(nl, "_sheet_nodes", fail)
    with pytest.raises(RuntimeError, match="injected netlist failure"):
        nl.compute_nets(a)
    assert symbols.project_owner() is b
    assert a.to_dict() == original
