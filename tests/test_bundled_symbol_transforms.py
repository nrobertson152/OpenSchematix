"""Rotation, mirroring and attachments for every bundled symbol (Issue #74).

For every built-in symbol (existing and added by the library expansion) this checks, in all eight
orientations reached through the editing commands (``rotate_items`` / ``mirror_items``):

* terminal world positions match an expectation computed here, independently of the engine, from the
  terminal's local coordinates and plain world-space rotation/mirror formulas;
* every wire stays attached to the same component terminal, with its end point on that terminal;
* net membership and terminal identity are unchanged;
* save and reopen keep the transformed geometry and every attachment.

Positions are deliberately negative or mixed-sign, and the group transform uses an explicit centre away
from the component, so a sign or axis mix-up in the transform cannot cancel out.
"""
from __future__ import annotations

import pytest

from openschematix import editing, netlist, projectio, symbols
from openschematix.geometry import GRID
from openschematix.project import new_project
from openschematix.symbols import fluid

BUILTINS = [s for s in symbols.builtin_symbols() if s.group != "Internal"]
WIRED = [s for s in BUILTINS if s.build(None).terminals]
OUT = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}
EPS = 1e-6


# ------------------------------------------------------------------ independent expectations
def rot_cw(x, y):
    """90 degrees clockwise on screen (y grows downward): right -> down -> left -> up."""
    return -y, x


def expect_rotate(p, centre):
    x, y = rot_cw(p[0] - centre[0], p[1] - centre[1])
    return centre[0] + x, centre[1] + y


def expect_mirror(p, centre):
    return 2 * centre[0] - p[0], p[1]


def local_to_world(local, origin, rotation, mirror):
    """World position of a symbol-local point: mirror in x first, then rotate clockwise."""
    x, y = local
    if mirror:
        x = -x
    for _ in range((rotation // 90) % 4):
        x, y = rot_cw(x, y)
    return origin[0] + x, origin[1] + y


def close(a, b):
    return abs(a[0] - b[0]) < EPS and abs(a[1] - b[1]) < EPS


# ------------------------------------------------------------------ helpers
def wire_out(doc, c):
    """Wire every terminal of `c` outward; return {terminal: (wire id, attached end attribute)}."""
    out = {}
    for name, (tx, ty) in c.terminals().items():
        dx, dy = OUT[c.terminal_dirs()[name]]
        w = editing.add_wire(doc, [(tx, ty), (tx + dx * 3 * GRID, ty + dy * 3 * GRID)])
        assert w is not None, (c.symbol, name)
        attr = "start" if w.start and list(w.start) == [c.id, name] else "end"
        assert list(getattr(w, attr) or []) == [c.id, name], (c.symbol, name, w.start, w.end)
        out[name] = (w.id, attr)
    return out


def assert_attached(doc, c, wires, where):
    terms = c.terminals()
    for name, (wid, attr) in wires.items():
        w = doc.wires[wid]
        assert list(getattr(w, attr) or []) == [c.id, name], (where, c.symbol, name, "attachment lost")
        pt = w.points[0] if attr == "start" else w.points[-1]
        assert close(pt, terms[name]), (where, c.symbol, name, pt, terms[name])


def partition(nets, sheet_uid):
    """Nets as a set of frozensets of members, independent of net numbering and order."""
    return {frozenset([("t",) + tuple(t[1:]) for t in n.terminals if t[0] == sheet_uid]
                      + [("w", w[1]) for w in n.wires if w[0] == sheet_uid]) for n in nets}


# ------------------------------------------------------------------ in-place transforms
def _valve_configs():
    """Every directional-valve type with each operator on the left, as placed-component params."""
    out = []
    for sd in BUILTINS:
        if not sd.id.endswith(".dcv"):
            continue
        medium = sd.default_params["medium"]
        for vtype in fluid.VALVE_TYPES[medium]:
            d = fluid.default_valve_params(medium, vtype)
            for op in fluid.OPERATORS:
                out.append(pytest.param(sd, {**d, "left": [op], "right": ["spring"]}, id=f"{sd.id}-{vtype}-{op}"))
    return out


@pytest.mark.parametrize("sd", WIRED, ids=lambda s: s.id)
def test_single_component_transforms_keep_terminals_and_attachments(sd):
    """Rotate/mirror one component in place (attached wires follow, not selected)."""
    _single_transforms(sd, None)


@pytest.mark.parametrize("sd,params", _valve_configs())
def test_configured_valves_transform_like_any_symbol(sd, params):
    """The valve configurator's operators and port patterns rotate and mirror correctly too."""
    _single_transforms(sd, params)


def _single_transforms(sd, params):
    p = new_project("t")
    doc = p.sheets[0]
    c = editing.place(doc, sd.id, -37 * GRID, 23 * GRID, params=params)
    if params is not None:
        assert c.params == params or all(c.params.get(k) == v for k, v in params.items()), sd.id
    wires = wire_out(doc, c)
    ops = ["rot", "rot", "rot", "rot", "mirror", "rot", "rot", "rot", "rot", "mirror", "ccw", "mirror", "ccw"]
    for step, op in enumerate(ops):
        before = c.terminals()
        origin = (c.x, c.y)
        if op == "mirror":
            editing.mirror_items(doc, [c.id], [])
            want = {n: expect_mirror(q, origin) for n, q in before.items()}
        else:
            editing.rotate_items(doc, [c.id], [], clockwise=(op == "rot"))
            if op == "rot":
                want = {n: expect_rotate(q, origin) for n, q in before.items()}
            else:
                want = {n: expect_rotate(expect_rotate(expect_rotate(q, origin), origin), origin)
                        for n, q in before.items()}
        assert (c.x, c.y) == origin, (sd.id, step, "an in-place transform must not move the component")
        got = c.terminals()
        assert set(got) == set(want), (sd.id, step)
        for n in want:
            assert close(got[n], want[n]), (sd.id, step, op, n, got[n], want[n])
        # independent of the step-wise check: the absolute pose formula
        for t in c.geometry().terminals:
            assert close(got[t.name], local_to_world((t.x, t.y), (c.x, c.y), c.rotation, c.mirror)), \
                (sd.id, step, t.name, c.rotation, c.mirror)
        assert_attached(doc, c, wires, f"step {step} ({op})")
    # every terminal's net still contains its own wire, and no two terminals were merged
    nets = netlist.compute_nets(p)
    net_of = {}
    for i, n in enumerate(nets):
        for t in n.terminals:
            net_of[("t", t[2])] = i
        for w in n.wires:
            net_of[("w", w[1])] = i
    for name, (wid, _attr) in wires.items():
        assert net_of[("t", name)] == net_of[("w", wid)], (sd.id, name)
    assert len({net_of[("t", n)] for n in wires}) == len(wires), (sd.id, "terminals merged into one net")


@pytest.mark.parametrize("sd", WIRED, ids=lambda s: s.id)
def test_group_transforms_about_a_remote_centre_keep_nets(sd):
    """Rotate/mirror the component together with its wires about a centre away from it."""
    p = new_project("t")
    doc = p.sheets[0]
    c = editing.place(doc, sd.id, -41 * GRID, -17 * GRID)
    wires = wire_out(doc, c)
    wire_ids = [wid for wid, _ in wires.values()]
    base = partition(netlist.compute_nets(p), doc.uid)
    centre = (13 * GRID, -29 * GRID)
    for step, op in enumerate(["rot", "mirror", "rot", "rot", "mirror", "rot", "ccw", "rot"]):
        before_t = c.terminals()
        before_w = {wid: list(doc.wires[wid].points) for wid in wire_ids}
        if op == "mirror":
            editing.mirror_items(doc, [c.id], wire_ids, center=centre)
            f = lambda q: expect_mirror(q, centre)  # noqa: E731
        elif op == "rot":
            editing.rotate_items(doc, [c.id], wire_ids, clockwise=True, center=centre)
            f = lambda q: expect_rotate(q, centre)  # noqa: E731
        else:
            editing.rotate_items(doc, [c.id], wire_ids, clockwise=False, center=centre)
            f = lambda q: expect_rotate(expect_rotate(expect_rotate(q, centre), centre), centre)  # noqa: E731
        got = c.terminals()
        for n, q in before_t.items():
            assert close(got[n], f(q)), (sd.id, step, op, n, got[n], f(q))
        for wid, pts in before_w.items():
            now = doc.wires[wid].points
            assert close(now[0], f(pts[0])) and close(now[-1], f(pts[-1])), (sd.id, step, op, wid, pts, now)
        assert_attached(doc, c, wires, f"group step {step} ({op})")
        assert partition(netlist.compute_nets(p), doc.uid) == base, (sd.id, step, op, "net membership changed")


# ------------------------------------------------------------------ persistence
def test_transformed_symbols_survive_save_and_reopen(tmp_path):
    """Every symbol in a non-default orientation (all eight used in turn), wired, saved and reopened."""
    p = new_project("Transformed symbols")
    poses = [(r, m) for m in (False, True) for r in (0, 90, 180, 270)]
    placed = []    # (sheet, component, wires, rotation, mirror)
    by_domain = {}
    for sd in BUILTINS:
        by_domain.setdefault(sd.category, []).append(sd)
    first = True
    for cat, lst in sorted(by_domain.items()):
        doc = p.sheets[0] if first else p.add_sheet(cat)
        first = False
        for i, sd in enumerate(lst):
            x, y = (-2000 + (i % 8) * 500), (-1500 + (i // 8) * 500)
            c = editing.place(doc, sd.id, x, y)
            rot, mir = poses[(i + len(cat)) % len(poses)]
            if mir:
                editing.mirror_items(doc, [c.id], [])
            for _ in range(rot // 90):
                editing.rotate_items(doc, [c.id], [], clockwise=True)
            # mirror then k clockwise turns gives mirror=True, rotation=(0 + 90k) since mirror of 0 is 0
            assert (c.rotation, c.mirror) == (rot, mir), (sd.id, c.rotation, c.mirror)
            wires = wire_out(doc, c) if c.geometry().terminals else {}
            placed.append((doc.uid, c.id, sd, wires, rot, mir, (c.x, c.y)))
    nets_before = {s.uid: partition(netlist.compute_nets(p), s.uid) for s in p.sheets}
    path = tmp_path / "transformed.schematix"
    projectio.save_project(p, str(path), snapshot=False)
    res = projectio.open_any(str(path))
    assert not res.recovered, res.warnings
    q = res.project
    sheets = {s.uid: s for s in q.sheets}
    for sheet_uid, cid, sd, wires, rot, mir, origin in placed:
        doc = sheets[sheet_uid]
        c = doc.components[cid]
        assert (c.symbol, c.rotation, c.mirror, (c.x, c.y)) == (sd.id, rot, mir, origin), sd.id
        terms = c.terminals()
        for t in c.geometry().terminals:
            assert close(terms[t.name], local_to_world((t.x, t.y), origin, rot, mir)), (sd.id, t.name)
        assert_attached(doc, c, wires, "after reopen")
    for s in q.sheets:
        assert partition(netlist.compute_nets(q), s.uid) == nets_before[s.uid], s.name


def test_coverage_includes_every_domain():
    """The parametrised checks above run over electrical, hydraulic and pneumatic symbols alike."""
    cats = {s.category.split()[0].lower() for s in WIRED}
    assert {"hydraulic", "pneumatic"} <= cats, cats
    assert len(WIRED) > 400, len(WIRED)
