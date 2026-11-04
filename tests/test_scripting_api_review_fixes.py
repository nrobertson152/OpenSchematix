"""Scripting API: fixes for the Codex review of #33 at 64b07ba.

1. (P1) A transformation must not change the circuit, including which wires
   form a net: moving a component could cut a dangling T-branch off its net
   while no terminal changed net, and the terminal-only check let it through.
2. (P2) An edit of an unlocked component must not re-route or detach a
   locked wire (a locked wire, or one on a locked layer).
3. (P2) A project opened through a relative path stays tied to that file
   after os.chdir(): the protection of a damaged original holds, and later
   saves without a path go to the same file.
"""
import json
import os
import zipfile

import pytest

from openschematix import api, symbols
from openschematix.api import _core


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    symbols.set_project_symbols([])
    symbols.set_user_symbols([])
    _core._invalidate()


def _membership(p):
    return sorted(sorted(map(str, n.wires)) for n in p.nets())


def _wire_state(s):
    return {w.id: (w.points, w.start, w.end) for w in s.wires()}


# ---------------------------------------------------------------- 1. dangling T-branch
def test_a_move_that_would_cut_off_a_dangling_branch_is_refused():
    """Codex's reproduction: resistor at (200, 200), a wire from its terminal 1
    to (80, 200), a branch from (130, 200) to (130, 100); move_by(0, 100)."""
    p = api.new_project("branch")
    s = p.sheets[0]
    r = s.place("el.resistor.iec", 200, 200)
    t1 = r.terminal("1").position
    assert t1 == (180.0, 200.0)
    s.add_wire([t1, (80, 200)])
    s.add_wire([(130, 200), (130, 100)])
    nets_before, wires_before = _membership(p), _wire_state(s)
    assert len(nets_before) == 1 and len(nets_before[0]) == 2       # one net with both wires
    with pytest.raises(api.InvalidOperationError, match="would change the circuit.*disconnect"):
        r.move_by(0, 100)
    assert _membership(p) == nets_before and _wire_state(s) == wires_before
    assert r.position == (200, 200)


def test_a_move_that_keeps_the_branch_on_its_net_is_allowed():
    """The same circuit is fine to move when the branch stays on the wire."""
    p = api.new_project("branch ok")
    s = p.sheets[0]
    r = s.place("el.resistor.iec", 200, 200)
    s.add_wire([r.terminal("1").position, (80, 200)])
    s.add_wire([(130, 200), (130, 100)])
    before = _membership(p)
    r.move_by(20, 0)                                          # the wire stays on y = 200
    assert _membership(p) == before


def test_wire_only_nets_count_too():
    """Two wires joined only to each other (no terminal) must stay joined."""
    p = api.new_project("wire only")
    s = p.sheets[0]
    s.add_wire([(100, 100), (200, 100)])
    s.add_wire([(150, 100), (150, 50)])
    r = s.place("el.resistor.iec", 400, 400)
    before = _core._connections(s._doc())
    assert any(len(net) == 2 and all(m[0] == "w" for m in net) for net in before)
    r.move_by(0, 20)                                          # unrelated: allowed, nothing changes
    assert _core._connections(s._doc()) == before


# ---------------------------------------------------------------- 2. locked wires
def _locked_wire_circuit(tmp_path, how):
    p = api.new_project("locks")
    s = p.sheets[0]
    r = s.place("el.resistor.iec", 200, 200)
    w = s.add_wire([r.terminal("2").position, (400, 200)])
    if how == "layer":
        path = str(tmp_path / "locks.schematix")
        p._p.layer("Wires").locked = True
        p.save(path)
        p = api.open_project(path)                            # as Codex: save and reopen with the layer locked
        s = p.sheets[0]
        r = next(c for c in p.components() if c.symbol_id == "el.resistor.iec")
        w = s.wires()[0]
    else:
        s._doc().wires[w.id].locked = True
    return p, s, r, w


@pytest.mark.parametrize("how", ["layer", "wire"])
@pytest.mark.parametrize("edit", ["move_by", "position", "rotation", "mirror", "remove"])
def test_component_edits_never_change_a_locked_wire(tmp_path, how, edit):
    p, s, r, w = _locked_wire_circuit(tmp_path, how)
    assert w.locked and not r.locked
    before, comp_before = _wire_state(s), (r.position, r.rotation, r.mirror)
    call = {"move_by": lambda: r.move_by(0, 100), "position": lambda: setattr(r, "position", (200, 300)),
            "rotation": lambda: setattr(r, "rotation", 90), "mirror": lambda: setattr(r, "mirror", True),
            "remove": r.remove}[edit]
    with pytest.raises(api.InvalidOperationError, match="locked wire"):
        call()
    assert _wire_state(s) == before
    assert len(p.components()) == 1 and (r.position, r.rotation, r.mirror) == comp_before


def test_edits_that_leave_locked_wires_alone_still_work(tmp_path):
    p, s, r, w = _locked_wire_circuit(tmp_path, "wire")
    other = s.place("el.coil.iec", 600, 600)                  # nothing attached
    other.move_by(20, 0)
    other.rotation = 90
    other.remove()
    r.designator = "R9"                                       # no geometry change
    assert r.designator == "R9" and len(s.wires()) == 1


def test_valve_parameter_change_cannot_reroute_a_locked_wire():
    p = api.new_project("valve")
    s = p.sheets[0]
    v = s.place("fl.hyd.dcv", 300, 300)
    term = sorted(v.terminals)[0]
    pos = v.terminal(term).position
    w = s.add_wire([pos, (pos[0], pos[1] + 200)])
    s._doc().wires[w.id].locked = True
    before = _wire_state(s)
    left = v.params.get("left")
    try:
        v.set_params(left=["lever"] if left != ["lever"] else ["solenoid"])
    except api.InvalidOperationError as e:
        assert "locked wire" in str(e) or "would change the circuit" in str(e)
    assert _wire_state(s) == before                            # whether refused or harmless, the wire is unchanged


# ---------------------------------------------------------------- 3. relative paths
def _damaged_copy(folder):
    p = api.new_project("orig")
    p.sheets[0].place("el.coil.iec", 100, 100)
    path = os.path.join(folder, "damaged.schematix")
    p.save(path)
    p.sheets[0].place("el.resistor.iec", 300, 100)
    p.save(path)                                              # two revisions
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    idx = json.loads(files["revisions/index.json"])
    idx["entries"][0]["sheets"] = [[None]]                    # a damaged revision index entry
    files["revisions/index.json"] = json.dumps(idx).encode()
    with zipfile.ZipFile(path, "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
    return path


def test_damaged_original_opened_by_relative_path_stays_protected_after_chdir(tmp_path, monkeypatch):
    """Codex's reproduction: open 'damaged.schematix' relatively, chdir, save to its absolute path."""
    path = _damaged_copy(str(tmp_path))
    data = open(path, "rb").read()
    (tmp_path / "other").mkdir()
    monkeypatch.chdir(tmp_path)
    q = api.open_project("damaged.schematix")
    assert q.needs_new_name and q.source_path == path
    monkeypatch.chdir(tmp_path / "other")
    with pytest.raises(api.InvalidOperationError, match="would overwrite the original"):
        q.save(path)
    with pytest.raises(api.InvalidOperationError, match="would overwrite the original"):
        q.save(os.path.join("..", "damaged.schematix"))
    with open(path, "rb") as f:
        assert f.read() == data


def test_project_opened_by_relative_path_keeps_saving_to_that_file_after_chdir(tmp_path, monkeypatch):
    p = api.new_project("rel")
    p.sheets[0].place("el.coil.iec", 100, 100)
    p.save(str(tmp_path / "rel.schematix"))
    (tmp_path / "other").mkdir()
    monkeypatch.chdir(tmp_path)
    q = api.open_project("rel.schematix")
    assert q.path == str(tmp_path / "rel.schematix")
    monkeypatch.chdir(tmp_path / "other")
    q.sheets[0].place("el.resistor.iec", 300, 100)
    assert q.save() == str(tmp_path / "rel.schematix")
    assert not (tmp_path / "other" / "rel.schematix").exists()
    assert len(api.open_project(str(tmp_path / "rel.schematix")).components()) == 2


def test_save_as_with_a_relative_path_is_anchored(tmp_path, monkeypatch):
    p = api.new_project("rel2")
    p.sheets[0].place("el.coil.iec", 100, 100)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.chdir(tmp_path / "a")
    assert p.save("x.schematix") == str(tmp_path / "a" / "x.schematix")
    monkeypatch.chdir(tmp_path / "b")
    p.save()
    assert not (tmp_path / "b" / "x.schematix").exists() and (tmp_path / "a" / "x.schematix").exists()
