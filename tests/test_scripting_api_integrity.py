"""Scripting API data integrity: scripted transformations keep wire geometry,
terminal references and the netlist consistent, failed edits change
nothing, and projects recovered from damaged files never overwrite their
original file.

Some tests need behaviour from pull requests that are not merged yet. They
detect it and are skipped until it is present:
- PR #37 (``symbols.lookup``): custom-symbol wire attachments survive reopening;
- PR #40 (``OpenResult.needs_new_name``): damaged files open with the damaged
  parts left out.
"""
import copy
import io
import json
import os
import zipfile

import pytest

from openschematix import api, editing, netlist, projectio, symbols
from openschematix.api import _core
from openschematix.connectivity import analyse
from openschematix.geometry import is_orthogonal, same, xform
from openschematix.symbols.custom import blank_symbol, normalise

HAS_PR37 = hasattr(symbols, "lookup")
HAS_PR40 = hasattr(projectio.OpenResult, "needs_new_name")
needs_pr37 = pytest.mark.skipif(not HAS_PR37, reason="needs PR #37 (custom-symbol attachments kept on reopen)")
needs_pr40 = pytest.mark.skipif(not HAS_PR40, reason="needs PR #40 (damaged parts left out on open)")


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    symbols.set_user_symbols([])
    symbols.set_project_symbols([])
    _core._invalidate()


# ---------------------------------------------------------------- helpers
def custom_symbol(sid="user:integrity-sensor"):
    """Asymmetric pins, so rotation and mirroring move each one differently."""
    d = blank_symbol("Integrity sensor")
    d["id"] = sid
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "pA", "name": "A", "x": -20, "y": 0, "dir": "l"},
                 {"id": "pB", "name": "B", "x": 20, "y": 10, "dir": "r"}]
    return normalise(d)


def circuit(custom: bool = True):
    """A sheet with every kind of attachment the engine handles differently:
    routed wires (connect), a drawn straight wire, a hand-shaped multi-bend
    wire with a T-junction onto it, a valve and (optionally) a custom symbol.
    Its only junction is that T: no wire runs over another wire or pin."""
    p = api.new_project("Integrity")
    s = p.sheets[0]
    k = s.place("el.coil.iec", 200, 200)
    r = s.place("el.resistor.iec", 500, 200)
    if custom:
        sdoc = custom_symbol()
        p._p.symbols[sdoc["id"]] = sdoc
        x = s.place(sdoc["id"], 300, 500)
        xa, xb = "pA", "pB"
    else:
        x = s.place("el.resistor.iec", 300, 500)
        xa, xb = "1", "2"
    v = s.place("fl.hyd.dcv", 700, 500)
    n = s.place("el.contact.no.iec", 100, 800)
    s.connect(k, "A2", r, "1")
    s.connect(r, "2", x, xb)
    s.connect(x, xa, n, "1")
    s.connect(v, sorted(v.terminals)[0], k, "A1")
    t = n.terminal("2").position
    hand = s.add_wire([t, (t[0], t[1] + 60), (t[0] + 80, t[1] + 60), (t[0] + 80, t[1] + 120)])
    s.add_wire([(t[0] + 40, t[1] + 60), (t[0] + 40, t[1] + 150)])          # T-junction onto the hand wire
    q = v.terminal(sorted(v.terminals)[1]).position
    s.add_wire([q, (q[0] + 100, q[1])])
    assert analyse(s._doc()).junctions == [(t[0] + 40, t[1] + 60)], "fixture must have exactly one junction"
    assert hand.start is not None
    return p, s, {"K": k, "R": r, "X": x, "V": v, "N": n}


def problems(sheet: api.Sheet) -> list:
    """Every way wire geometry, references and connectivity can disagree."""
    doc = sheet._doc()
    out = []
    for w in doc.wires.values():
        if not is_orthogonal(w.points):
            out.append(f"wire {w.id} is not orthogonal")
        for attr, idx in (("start", 0), ("end", -1)):
            ref = getattr(w, attr)
            if ref:
                tp = doc.terminal_pos(ref)
                if tp is None:
                    out.append(f"wire {w.id} {attr} references a missing terminal {ref}")
                elif not same(tp, w.points[idx]):
                    out.append(f"wire {w.id} {attr} references {ref} at {tp} but is drawn at {w.points[idx]}")
            else:
                for c in doc.components.values():
                    for name, tp in c.terminals().items():
                        if same(tp, w.points[idx]):
                            out.append(f"wire {w.id} {attr} lies on {c.id}:{name} without being attached")
    open_t = {(c, n) for c, n, _p in analyse(doc).open_terminals}
    for w in doc.wires.values():
        for ref in (w.start, w.end):
            if ref and tuple(ref) in open_t:
                out.append(f"{ref} is attached to wire {w.id} but analysed as unconnected")
    return out


def nets(project: api.Project) -> set:
    """Electrical content: which terminals are connected together (by
    designator and terminal, independent of wire ids and shapes)."""
    p = project._p
    out = set()
    for n in netlist.compute_nets(p):
        terms = frozenset((p.find_sheet(u).components[c].designator, t) for u, c, t in n.terminals)
        if terms:
            out.add(terms)
    return out


def consistent(sheet):
    found = problems(sheet)
    assert not found, found


def pins(c: api.Component) -> dict:
    return {n: t.position for n, t in c.terminals.items()}


def sheet_state(sheet: api.Sheet) -> str:
    return json.dumps(sheet._doc().to_dict(standalone=False), sort_keys=True)


# ---------------------------------------------------------------- transformations keep geometry and nets
def test_circuit_starts_consistent():
    p, s, _c = circuit()
    consistent(s)
    assert len(nets(p)) >= 4


@pytest.mark.parametrize("name", ["K", "R", "X", "V", "N"])
@pytest.mark.parametrize("op", ["position", "move_by", "rotate-90", "rotate-180", "rotate-270", "mirror"])
def test_transform_keeps_wires_on_pins_and_nets_unchanged(name, op):
    """Either the transformation succeeds with every attached wire end on its
    pin and the same nets, or it is refused and nothing changes."""
    p, s, comps = circuit()
    c = comps[name]
    before_nets, before = nets(p), sheet_state(s)
    try:
        if op == "position":
            c.position = (c.position[0] + 300, c.position[1] - 100)
        elif op == "move_by":
            c.move_by(-60, 40)
        elif op == "mirror":
            c.mirror = not c.mirror
        else:
            c.rotation = int(op.split("-")[1])
    except api.InvalidOperationError as e:
        assert "would change the circuit" in str(e)
        assert sheet_state(s) == before
    else:
        assert sheet_state(s) != before
    consistent(s)
    assert nets(p) == before_nets


def test_transform_that_would_short_a_component_is_refused():
    """Rotating S1 by 270 degrees makes the engine adjust its hand-drawn wire
    minimally, so that the wire's first segment runs over S1's other pin:
    the application would silently short S1:1 to S1:2. The API refuses."""
    p, s, comps = circuit()
    n = comps["N"]
    before, before_nets = sheet_state(s), nets(p)
    with pytest.raises(api.InvalidOperationError, match=r"would connect S1:1, S1:2"):
        n.rotation = 270
    assert sheet_state(s) == before and nets(p) == before_nets and n.rotation == 0
    n.rotation = 90                                  # a rotation that keeps the circuit is still allowed
    consistent(s)
    assert nets(p) == before_nets


def test_moving_a_pin_onto_another_net_is_refused():
    p, s, comps = circuit()
    r = comps["R"]
    free = s.add_wire([(900, 100), (1000, 100)])
    free_end_offset = (900 - r.terminal("1").position[0], 100 - r.terminal("1").position[1])
    before, before_nets = sheet_state(s), nets(p)
    with pytest.raises(api.InvalidOperationError, match="would change the circuit"):
        r.move_by(*free_end_offset)                  # pin 1 would land on a wire of another net
    assert sheet_state(s) == before and nets(p) == before_nets and free.start is None


def test_attached_wire_ends_follow_the_exact_pin_positions():
    p, s, comps = circuit()
    x = comps["X"]
    attached = [(w, attr) for w in s.wires() for attr in ("start", "end")
                if getattr(w, attr) and getattr(w, attr)[0] == x.id]
    assert len(attached) == 2
    for op in (lambda: x.move_by(100, 50), lambda: setattr(x, "rotation", 90), lambda: setattr(x, "mirror", True),
               lambda: setattr(x, "rotation", 270)):
        op()
        for w, attr in attached:
            ref = getattr(w, attr)
            end = w.points[0] if attr == "start" else w.points[-1]
            assert end == x.terminal(ref[1]).position


def test_repeated_transformations_stay_consistent():
    p, s, comps = circuit()
    before_nets = nets(p)
    steps = [("K", "move_by", (40, 0)), ("X", "rotation", 90), ("X", "mirror", True), ("R", "move_by", (0, -70)),
             ("V", "rotation", 180), ("X", "move_by", (-30, 20)), ("N", "mirror", True), ("X", "rotation", 0),
             ("K", "rotation", 270), ("X", "mirror", False), ("R", "move_by", (0, 70)), ("K", "rotation", 0)]
    for _round in range(3):
        for name, attr, value in steps:
            c = comps[name]
            if attr == "move_by":
                c.move_by(*value)
            else:
                setattr(c, attr, value)
            consistent(s)
            assert nets(p) == before_nets


def test_moving_back_restores_the_pin_positions():
    p, s, comps = circuit()
    k = comps["K"]
    start = pins(k)
    k.move_by(200, 100)
    k.rotation = 90
    k.rotation = 0
    k.move_by(-200, -100)
    assert pins(k) == start
    consistent(s)


def test_custom_symbol_pin_geometry_follows_rotation_and_mirroring():
    p, s, comps = circuit()
    x = comps["X"]
    local = {"pA": (-20.0, 0.0), "pB": (20.0, 10.0)}
    for rotation in (0, 90, 180, 270):
        for mirror in (False, True):
            x.rotation, x.mirror = rotation, mirror
            for name, (lx, ly) in local.items():
                dx, dy = xform(lx, ly, rotation, mirror)
                assert x.terminal(name).position == (x.position[0] + dx, x.position[1] + dy)
            consistent(s)


def test_valve_parameter_change_keeps_attached_wires_on_pins():
    p, s, comps = circuit()
    v = comps["V"]
    v.set_params(type="4/2")
    consistent(s)
    v.set_params(type="4/3", left=["solenoid"])
    consistent(s)


def test_component_deletion_detaches_wires_and_updates_nets():
    p, s, comps = circuit()
    x = comps["X"]
    wires = [w for w in s.wires() if (w.start and w.start[0] == x.id) or (w.end and w.end[0] == x.id)]
    shapes = {w.id: w.points for w in wires}
    x.remove()
    consistent(s)
    for w in wires:
        assert x.id not in {r[0] for r in (w.start, w.end) if r} and w.points == shapes[w.id]
    assert not any("X1" in {d for d, _t in n} for n in nets(p))
    with pytest.raises(api.ObjectNotFoundError):
        x.rotation = 90


# ---------------------------------------------------------------- failed edits change nothing
FAIL_POINTS = ["sync_wire_ends", "attach_touching_wires", "move_items", "delete_items"]


@pytest.mark.parametrize("fail_in", FAIL_POINTS)
@pytest.mark.parametrize("op", ["position", "move_by", "rotation", "mirror", "set_params", "remove", "wire.remove"])
def test_engine_failure_part_way_leaves_the_sheet_unchanged(monkeypatch, fail_in, op):
    p, s, comps = circuit()
    c = comps["V"]
    w = s.wires()[0]
    real = getattr(editing, fail_in)

    def partial_then_fail(doc, *args, **kw):
        real(doc, *args, **kw)              # modify the sheet first, then fail
        raise RuntimeError("engine failure")
    monkeypatch.setattr(editing, fail_in, partial_then_fail)
    before, before_nets, before_id = sheet_state(s), nets(p), s._doc().next_id
    call = {"position": lambda: setattr(c, "position", (900, 900)), "move_by": lambda: c.move_by(50, 50),
            "rotation": lambda: setattr(c, "rotation", 90), "mirror": lambda: setattr(c, "mirror", True),
            "set_params": lambda: c.set_params(type="4/2"), "remove": c.remove, "wire.remove": w.remove}[op]
    try:
        call()
    except RuntimeError:
        pass                                # the failure point was reached
    else:
        # this operation does not use that engine function: nothing to roll back
        monkeypatch.undo()
        return
    monkeypatch.undo()
    assert sheet_state(s) == before and s._doc().next_id == before_id
    assert nets(p) == before_nets
    consistent(s)


@pytest.mark.parametrize("call, error", [
    (lambda c: setattr(c, "rotation", 45), api.InvalidOperationError),
    (lambda c: setattr(c, "position", (105, 100)), api.InvalidOperationError),
    (lambda c: setattr(c, "mirror", "yes"), api.InvalidOperationError),
    (lambda c: c.move_by(float("nan"), 0), api.InvalidOperationError),
    (lambda c: c.set_params(type="9/9"), api.InvalidOperationError),
])
def test_invalid_transformations_change_nothing(call, error):
    p, s, comps = circuit()
    before, before_nets = sheet_state(s), nets(p)
    with pytest.raises(error):
        call(comps["V"])
    assert sheet_state(s) == before and nets(p) == before_nets


def test_locked_component_cannot_be_transformed_and_stays_consistent():
    p, s, comps = circuit()
    k = comps["K"]
    s._doc().components[k.id].locked = True
    before = sheet_state(s)
    for call in (lambda: setattr(k, "rotation", 90), lambda: k.move_by(10, 0), lambda: setattr(k, "mirror", True)):
        with pytest.raises(api.InvalidOperationError, match="locked"):
            call()
    assert sheet_state(s) == before


# ---------------------------------------------------------------- components whose symbol is not available
def make_placeholder(p, comp):
    """Make `comp`'s symbol unavailable, as when a project is opened on a
    computer without it (or with its embedded definition damaged)."""
    p._p.symbols.pop(comp.symbol_id)


@pytest.mark.parametrize("op", ["position", "move_by", "rotation", "mirror", "connect", "add_wire"])
def test_components_with_unavailable_symbols_cannot_be_moved_or_wired(op):
    p, s, comps = circuit()
    x, k = comps["X"], comps["K"]
    pin = x.terminal("pA").position
    make_placeholder(p, x)
    before, before_nets = sheet_state(s), nets(p)
    call = {"position": lambda: setattr(x, "position", (600, 600)), "move_by": lambda: x.move_by(100, 0),
            "rotation": lambda: setattr(x, "rotation", 90), "mirror": lambda: setattr(x, "mirror", True),
            "connect": lambda: s.connect(k, "A1", x, sorted(x.terminals)[0]),
            "add_wire": lambda: s.add_wire([x.terminal(sorted(x.terminals)[0]).position,
                                            (x.terminal(sorted(x.terminals)[0]).position[0], 900)])}[op]
    with pytest.raises(api.InvalidOperationError, match="not available"):
        call()
    assert sheet_state(s) == before and nets(p) == before_nets
    assert pin == (280.0, 500.0)


def test_component_with_unavailable_symbol_can_still_be_removed():
    p, s, comps = circuit()
    x = comps["X"]
    make_placeholder(p, x)
    x.remove()
    assert x.id not in s._doc().components
    assert all(x.id not in {r[0] for r in (w.start, w.end) if r} for w in s.wires())


# ---------------------------------------------------------------- snapshot restore (the GUI's undo/redo)
def test_undo_snapshot_round_trip_keeps_attachments_and_nets():
    """The application's undo/redo rebuilds the project from to_dict(); an
    API-edited project must come back with the same wires, references and
    nets (custom symbols included, while the project is active)."""
    from openschematix.project import Project as Internal
    p, s, comps = circuit()
    comps["X"].rotation = 90
    comps["K"].move_by(50, 0)
    p._use()
    restored = Internal.from_dict(copy.deepcopy(p._p.to_dict()))
    q = api.Project(restored)
    assert sheet_state(q.sheets[0]) == sheet_state(s)
    assert nets(q) == nets(p)
    consistent(q.sheets[0])
    q.sheets[0].component(comps["X"].id).move_by(-50, 30)       # and transformations still work after it
    consistent(q.sheets[0])


def test_reopened_project_keeps_attachments_for_built_in_symbols(tmp_path):
    p, s, comps = circuit(custom=False)
    comps["K"].rotation = 90
    path = p.save(str(tmp_path / "builtin.schematix"))
    symbols.set_project_symbols([])
    _core._invalidate()
    q = api.open_project(path)
    k = q.sheets[0].component(comps["K"].id)
    before = nets(q)
    k.move_by(100, 0)
    k.rotation = 180
    consistent(q.sheets[0])
    assert nets(q) == before


@needs_pr37
def test_reopened_project_keeps_custom_symbol_attachments(tmp_path):
    """Audit F1: references to custom-symbol pins were dropped on open, so a
    scripted move left the wires behind. Fixed in the loader by PR #37."""
    p, s, comps = circuit()
    path = p.save(str(tmp_path / "custom.schematix"))
    symbols.set_project_symbols([])
    _core._invalidate()
    q = api.open_project(path)
    s2 = q.sheets[0]
    consistent(s2)
    before = nets(q)
    x = s2.component(comps["X"].id)
    x.move_by(100, 0)
    x.rotation = 90
    consistent(s2)
    assert nets(q) == before


# ---------------------------------------------------------------- recovered projects: save protection
def fake_open(monkeypatch, *, migrated=False, recovered=True):
    """open_any returning a result flagged as PR #40 does for damaged files."""
    real = projectio.open_any

    def flagged(path):
        res = real(path)
        res.migrated = migrated
        try:
            res.needs_new_name = migrated or recovered      # plain attribute when PR #40 is absent
        except AttributeError:
            res.recovered = recovered                         # PR #40: needs_new_name is a property
        res.warnings = list(res.warnings) + ["The revision history is damaged (simulated)."]
        return res
    monkeypatch.setattr(projectio, "open_any", flagged)


@pytest.fixture
def original(tmp_path):
    p = api.new_project("Original")
    p.sheets[0].place("el.coil.iec", 100, 100)
    path = p.save(str(tmp_path / "original.schematix"))
    return path, open(path, "rb").read()


def test_recovered_project_cannot_be_saved_over_its_original(tmp_path, monkeypatch, original):
    path, data = original
    fake_open(monkeypatch)
    q = api.open_project(path)
    assert q.needs_new_name and q.path is None and q.source_path == path
    assert any("damaged" in w for w in q.warnings)
    q.sheets[0].place("el.resistor.iec", 300, 100)
    with pytest.raises(api.InvalidOperationError, match="no file yet: it was opened from a damaged file"):
        q.save()
    for same_file in (path, os.path.join(os.path.dirname(path), ".", os.path.basename(path))):
        with pytest.raises(api.InvalidOperationError, match="would overwrite the original"):
            q.save(same_file)
    link = tmp_path / "link.schematix"
    os.symlink(path, link)
    with pytest.raises(api.InvalidOperationError, match="would overwrite the original"):
        q.save(str(link))
    assert open(path, "rb").read() == data


def test_save_as_moves_the_project_to_the_new_file(tmp_path, monkeypatch, original):
    path, data = original
    fake_open(monkeypatch)
    q = api.open_project(path)
    new = str(tmp_path / "rescued.schematix")
    assert q.save(new) == new
    assert q.path == new and not q.needs_new_name and q.source_path == path
    q.sheets[0].place("el.resistor.iec", 300, 100)
    assert q.save() == new                                   # later saves go to the new file
    assert open(path, "rb").read() == data
    monkeypatch.undo()
    assert len(api.open_project(new).components()) == 2


def test_deliberate_replacement_of_the_original(tmp_path, monkeypatch, original):
    path, data = original
    fake_open(monkeypatch)
    q = api.open_project(path)
    with pytest.raises(api.InvalidOperationError):
        q.save(path, overwrite_original="yes")              # must be a real True
    q.sheets[0].place("el.resistor.iec", 300, 100)
    assert q.save(path, overwrite_original=True) == path
    assert open(path, "rb").read() != data and not q.needs_new_name


def test_failed_save_as_keeps_the_recovery_state(tmp_path, monkeypatch, original):
    path, data = original
    fake_open(monkeypatch)
    q = api.open_project(path)
    entries = list(q._p.revisions.entries)
    objects = dict(q._p.revisions.objects)

    def disk_full(target, data_):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(projectio, "atomic_write_bytes", disk_full)
    new = str(tmp_path / "rescued.schematix")
    q.sheets[0].place("el.resistor.iec", 300, 100)            # content changed: save would record a snapshot
    with pytest.raises(api.ProjectFileError, match="No space left"):
        q.save(new)
    assert q.needs_new_name and q.path is None and not os.path.exists(new)
    assert q._p.revisions.entries == entries and q._p.revisions.objects == objects
    assert open(path, "rb").read() == data


def test_migrated_legacy_drawing_needs_a_new_name(tmp_path):
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples",
                       "start_stop_latch.osch")
    q = api.open_project(src)
    assert q.needs_new_name and q.path is None and q.source_path == src
    with pytest.raises(api.InvalidOperationError, match="converted from an older drawing format"):
        q.save()
    out = q.save(str(tmp_path / "latch.schematix"))
    assert q.path == out and not q.needs_new_name


def test_undamaged_projects_save_in_place_as_before(original):
    path, _data = original
    q = api.open_project(path)
    assert not q.needs_new_name and q.path == path == q.source_path
    q.sheets[0].place("el.resistor.iec", 300, 100)
    assert q.save() == path
    assert len(api.open_project(path).components()) == 2
    new = api.new_project("New")
    assert new.source_path is None and not new.needs_new_name


# ---------------------------------------------------------------- recovered projects from real damaged files (PR #40)
def damaged(tmp_path, original, how):
    path, _data = original
    p = api.open_project(path)
    sdoc = custom_symbol()
    p._p.symbols[sdoc["id"]] = sdoc
    p.sheets[0].place(sdoc["id"], 300, 300)
    p.save(path)                                               # two revisions, an embedded symbol
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    if how == "revision-object":
        files[next(n for n in files if n.startswith("revisions/objects/"))] = b"garbage"
    elif how == "revision-index":
        idx = json.loads(files["revisions/index.json"])
        idx["entries"][0]["sheets"] = [[None]]
        files["revisions/index.json"] = json.dumps(idx).encode()
    elif how == "embedded-symbol":
        name = next(n for n in files if n.startswith("symbols/"))
        doc = json.loads(files[name])
        doc["tags"] = True
        files[name] = json.dumps(doc).encode()
    out = tmp_path / f"damaged-{how}.schematix"
    with zipfile.ZipFile(out, "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
    return str(out)


@needs_pr40
@pytest.mark.parametrize("how", ["revision-object", "revision-index", "embedded-symbol"])
def test_real_damaged_files_open_recovered_and_are_protected(tmp_path, original, how):
    path = damaged(tmp_path, original, how)
    data = open(path, "rb").read()
    symbols.set_project_symbols([])
    _core._invalidate()
    q = api.open_project(path)
    assert q.needs_new_name and q.path is None and q.warnings
    with pytest.raises(api.InvalidOperationError):
        q.save()
    with pytest.raises(api.InvalidOperationError, match="would overwrite the original"):
        q.save(path)
    new = q.save(str(tmp_path / f"rescued-{how}.schematix"))
    assert open(path, "rb").read() == data
    r = api.open_project(new)
    assert not r.needs_new_name and len(r.components()) == len(q.components())
