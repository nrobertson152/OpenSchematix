"""Project-scoped custom-symbol resolution.

The symbol registry is process-wide: it holds the embedded symbols of the
project activated last. Two projects may embed different definitions under
the same custom-symbol id. These tests prove that saving, revision
snapshots, the netlist, Check (ERC), connectivity, the BOM, exports and
sheet duplication of one project use that project's own definitions while
another project is active, and that the active registration is left as it
was.

The projects are built in memory, so wire references are intact regardless
of the separate load-time fix in PR #37 (audit F1).
"""
import os

import pytest

from openschematix import bom, check, editing, export, netlist, projectio, revisions, symbols
from openschematix.connectivity import analyse
from openschematix.model import Wire
from openschematix.project import new_project
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef

SID = "user:scope-shared"


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    symbols.set_project_symbols([])
    symbols.set_user_symbols([])


def shared(reach: int, second_pin: str, name: str) -> dict:
    """Same id, different geometry (pin offset) and pin names."""
    d = blank_symbol(name)
    d["id"] = SID
    d["description"] = name
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "A", "name": "A", "x": -reach, "y": 0, "dir": "l"},
                 {"id": second_pin, "name": second_pin, "x": reach, "y": 0, "dir": "r"}]
    return normalise(d)


def make(reach: int, pin: str, name: str):
    """A project embedding `shared(reach, pin)`, with a wire from that pin
    to a resistor. Returns (project, component id, wire id)."""
    sdoc = shared(reach, pin, name)
    p = new_project(name)
    p.symbols[SID] = sdoc
    p.activate_symbols()
    doc = p.sheets[0]
    c = editing.place(doc, SID, 200, 200)
    r = editing.place(doc, "el.resistor.iec", 500, 200)
    w = Wire(doc.new_id(), [c.terminals()[pin], r.terminals()["1"]], [c.id, pin], [r.id, "1"])
    doc.add_wire(w)
    editing.reroute(doc, w)
    return p, c.id, w.id


@pytest.fixture
def ab():
    """A: pin B at x+20. B: pin Q at x+40. B is the active project."""
    a = make(20, "B", "Project A")
    b = make(40, "Q", "Project B")                         # activated last
    return a, b


def embedded_reach(p) -> float:
    return p.symbols[SID]["pins"][1]["x"]


# ---------------------------------------------------------------- saving and snapshots (data corruption)
def test_saving_a_project_never_embeds_another_projects_definition(tmp_path, ab):
    (a, _ca, _wa), (b, _cb, _wb) = ab
    path = str(tmp_path / "a.schematix")
    projectio.save_project(a, path)                        # B is active
    assert embedded_reach(a) == 20 and a.symbols[SID]["pins"][1]["id"] == "B"
    symbols.set_project_symbols([])
    reopened = projectio.open_any(path).project
    assert embedded_reach(reopened) == 20 and reopened.symbols[SID]["description"] == "Project A"
    assert embedded_reach(b) == 40


def test_revision_snapshots_keep_the_projects_own_definition(ab):
    (a, _ca, _wa), _b = ab
    a.revisions = revisions.RevisionStore()
    e = a.revisions.create(a, "approved", label="A")
    head = a.revisions._get(e["head"])
    assert head["symbols"][SID]["pins"][1]["x"] == 20


def test_the_active_project_still_picks_up_its_updated_definition(tmp_path):
    """The registry stays authoritative for its owner: an edited symbol
    published to the open project (as the symbol editor does) is embedded."""
    p, _c, _w = make(20, "B", "Owner")
    newer = dict(shared(30, "B", "Owner"), revision=5)
    symbols.add_project_symbol(to_symdef(newer))
    projectio.save_project(p, str(tmp_path / "o.schematix"))
    assert embedded_reach(p) == 30


def test_unowned_registration_still_embeds_missing_definitions():
    """Code that registers symbols without an owner (scripts, older tests)
    keeps working: a used symbol that is not embedded yet is embedded."""
    symbols.set_project_symbols([to_symdef(shared(20, "B", "Loose"))])
    p = new_project("Loose")
    editing.place(p.sheets[0], SID, 100, 100)
    p.embed_symbols()
    assert embedded_reach(p) == 20


def test_a_symbol_only_another_project_embeds_is_not_borrowed(ab):
    (a, _ca, _wa), _b = ab
    del a.symbols[SID]                                     # A uses the id but does not embed it
    a.embed_symbols()                                      # B (active) embeds it
    assert SID not in a.symbols


def test_user_library_definition_is_embedded_for_a_non_active_project(ab):
    (a, _ca, _wa), _b = ab
    del a.symbols[SID]
    symbols.set_user_symbols([to_symdef(shared(20, "B", "Library"))])
    a.embed_symbols()
    assert a.symbols[SID]["description"] == "Library"


# ---------------------------------------------------------------- engine results use the project's own geometry
def test_connectivity_uses_the_projects_own_pins(ab):
    (a, ca, wa), (b, cb, wb) = ab
    for p in (a, b, a, b):                                 # alternating access, B stays active
        r = analyse(p.sheets[0])
        cid, pin = (ca, "B") if p is a else (cb, "Q")
        assert r.open_wire_ends == []                      # the wire end lies on the project's own pin
        assert (cid, pin) in {tuple(t) for t in r.connected_terminals}
        assert (cid, pin) not in {(c, n) for c, n, _pt in r.open_terminals}
    assert symbols.project_owner() is b


def test_netlist_and_check_use_the_projects_own_definitions(ab):
    (a, ca, wa), (b, cb, wb) = ab
    for p, cid, pin in ((a, ca, "B"), (b, cb, "Q"), (a, ca, "B")):
        nets = netlist.compute_nets(p)
        net = next(n for n in nets if (p.sheets[0].uid, cid, pin) in n.terminals)
        assert any(t[2] == "1" for t in net.terminals)    # joined to the resistor
        issues = [i for i in check.check(p) if i.severity == "error"]
        assert issues == [], [i.message for i in issues]


def test_check_reports_no_wire_end_problems_for_a_non_active_project(ab):
    (a, _ca, _wa), (b, _cb, _wb) = ab
    codes_a = sorted(i.code for i in check.check(a))
    symbols.set_project_symbols([])
    a.activate_symbols()
    assert sorted(i.code for i in check.check(a)) == codes_a   # same as with A active


def test_bom_and_exports_use_the_projects_own_definitions(ab):
    (a, _ca, _wa), (b, _cb, _wb) = ab
    line = next(item for item in bom.generate(a) if "U1" in item.designators)
    assert line.description == "Project A" and line.symbol == "Project A"
    svg_inactive = export.to_svg(a.sheets[0], project=a)
    symbols.set_project_symbols([])
    a.activate_symbols()
    assert export.to_svg(a.sheets[0], project=a) == svg_inactive


def test_wire_numbering_uses_the_projects_own_nets(ab):
    (a, _ca, wa), (b, _cb, _wb) = ab
    netlist.assign_wire_numbers(a, True)
    assert a.sheets[0].wires[wa].number


def test_duplicating_a_sheet_keeps_its_wire_attachments(ab):
    (a, ca, wa), _b = ab
    dup = a.duplicate_sheet(a.sheets[0].uid)              # B (pins A, Q) is active
    assert dup.wires[wa].start == [ca, "B"]


# ---------------------------------------------------------------- the scope itself
def test_scope_restores_the_active_registration_even_on_error(ab):
    (a, _ca, _wa), (b, _cb, _wb) = ab
    assert symbols.project_owner() is b
    before = symbols.project_symbols()
    with pytest.raises(RuntimeError):
        with symbols.project_scope(a):
            assert symbols.project_owner() is a and symbols.get(SID).custom["description"] == "Project A"
            raise RuntimeError("boom")
    assert symbols.project_owner() is b
    after = symbols.project_symbols()
    assert after.keys() == before.keys() and all(after[k] is before[k] for k in before)


def test_scope_is_a_no_op_for_the_active_project(ab, monkeypatch):
    _a, (b, _cb, _wb) = ab
    calls = []
    monkeypatch.setattr(type(b), "activate_symbols", lambda self: calls.append(self))
    netlist.compute_nets(b)
    check.check(b)
    assert calls == []


def test_owner_is_not_kept_alive():
    import gc
    p, _c, _w = make(20, "B", "Temporary")
    del p
    gc.collect()
    assert symbols.project_owner() is None


# ---------------------------------------------------------------- compatibility
def test_existing_projects_are_unchanged(tmp_path):
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples",
                       "demo_project.schematix")
    res = projectio.open_any(src)
    p = res.project
    before = [d.to_dict() for d in p.sheets], netlist.compute_nets(p), p.symbols
    out = str(tmp_path / "demo.schematix")
    projectio.save_project(p, out, snapshot=False)
    q = projectio.open_any(out).project
    assert [d.to_dict() for d in q.sheets] == before[0]
    assert [(n.terminals, n.wires) for n in netlist.compute_nets(q)] == [(n.terminals, n.wires) for n in before[1]]
    assert q.symbols == before[2]
