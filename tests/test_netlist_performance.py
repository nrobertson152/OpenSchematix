"""Netlist performance and spatial-index equivalence.

``compute_nets`` must agree with a naive O(W^2) reference on small sheets, and
must scale near-linearly so large engineering drawings stay interactive.
"""
from __future__ import annotations

import time

from openschematix import editing, netlist
from openschematix.geometry import point_on_segment
from openschematix.project import new_project
from openschematix.symbols.general import OFFPAGE_IDS


def _key(p):
    return (round(p[0], 2), round(p[1], 2))


def _naive_sheet_nodes(doc, uf: netlist._UF):
    """Reference implementation: full wire scan (pre-index algorithm)."""
    uid = doc.uid
    wires = list(doc.wires.values())
    for w in wires:
        uf.find(("w", uid, w.id))
    term_at = {}
    for c in doc.components.values():
        for name, p in c.terminals().items():
            node = ("t", uid, c.id, name)
            uf.find(node)
            term_at.setdefault(_key(p), []).append(node)
    for nodes in term_at.values():
        for n in nodes[1:]:
            uf.union(nodes[0], n)
    for w in wires:
        for ref in (w.start, w.end):
            if ref and ref[0] in doc.components:
                uf.union(("w", uid, w.id), ("t", uid, ref[0], ref[1]))
        for idx in (0, -1):
            p = w.points[idx]
            for n in term_at.get(_key(p), []):
                uf.union(("w", uid, w.id), n)
            for o in wires:
                if o.id == w.id:
                    continue
                if any(point_on_segment(p, a, b) for a, b in zip(o.points, o.points[1:])):
                    uf.union(("w", uid, w.id), ("w", uid, o.id))


def _nets_from_uf(project, uf: netlist._UF):
    by_label = {}
    for doc in project.sheets:
        for c in doc.components.values():
            if c.symbol in OFFPAGE_IDS and netlist.link_label(c):
                for name in c.terminals():
                    by_label.setdefault(netlist.link_label(c), []).append(("t", doc.uid, c.id, name))
    for nodes in by_label.values():
        for n in nodes[1:]:
            uf.union(nodes[0], n)
    groups = {}
    for node in list(uf.p):
        groups.setdefault(uf.find(node), []).append(node)
    nets = []
    order = {d.uid: i for i, d in enumerate(project.sheets)}
    for nodes in groups.values():
        n = netlist.Net(0)
        for node in nodes:
            if node[0] == "w":
                n.wires.append((node[1], node[2]))
            else:
                n.terminals.append((node[1], node[2], node[3]))
        if len(n.wires) + len(n.terminals) < 2 and not n.wires:
            continue
        n.wires.sort(key=lambda w: (order.get(w[0], 0), w[1]))
        n.terminals.sort(key=lambda t: (order.get(t[0], 0), t[1], t[2]))
        nets.append(n)
    nets.sort(key=lambda n: (n.wires, n.terminals))
    for i, n in enumerate(nets, 1):
        n.index = i
    return nets


def _naive_compute_nets(project):
    uf = netlist._UF()
    for doc in project.sheets:
        _naive_sheet_nodes(doc, uf)
    return _nets_from_uf(project, uf)


def _signature(nets):
    return tuple(sorted(
        (tuple(sorted(n.wires)), tuple(sorted(n.terminals)), tuple(sorted(n.links)))
        for n in nets
    ))


def _grid_project(n_comp: int, extra_vertical: int = 0):
    p = new_project("perf")
    d = p.sheets[0]
    comps = []
    for i in range(n_comp):
        comps.append(editing.place(d, "el.resistor.iec", 100 + i * 100, 200))
    for i in range(n_comp - 1):
        ta, tb = comps[i].terminals(), comps[i + 1].terminals()
        pa = max(ta.values(), key=lambda pt: pt[0])
        pb = min(tb.values(), key=lambda pt: pt[0])
        editing.add_wire(d, [pa, (pa[0] + 20, pa[1]), (pb[0] - 20, pb[1]), pb])
    for i in range(extra_vertical):
        x = 150 + (i % max(n_comp, 1)) * 100
        editing.add_wire(d, [(x, 100), (x, 300)])
    return p


def test_spatial_index_matches_naive_reference_on_varied_sheets():
    """Index only drops wires that cannot touch; net membership must match naive scan."""
    for n in (1, 5, 15, 40):
        p = _grid_project(n, extra_vertical=n // 2)
        assert _signature(netlist.compute_nets(p)) == _signature(_naive_compute_nets(p))


def test_t_junction_and_shared_endpoint_nets():
    p = new_project("tj")
    d = p.sheets[0]
    a = editing.place(d, "el.resistor.iec", 100, 200)
    b = editing.place(d, "el.resistor.iec", 300, 200)
    c = editing.place(d, "el.resistor.iec", 200, 320)
    pa = max(a.terminals().values(), key=lambda pt: pt[0])
    pb = min(b.terminals().values(), key=lambda pt: pt[0])
    # horizontal spine
    spine = editing.add_wire(d, [pa, ((pa[0] + pb[0]) / 2, pa[1]), pb])
    mid = ((pa[0] + pb[0]) / 2, pa[1])
    pc = min(c.terminals().values(), key=lambda pt: pt[1])
    # T-junction branch ends on spine midpoint
    editing.add_wire(d, [pc, (pc[0], mid[1]), mid])
    fast = _signature(netlist.compute_nets(p))
    slow = _signature(_naive_compute_nets(p))
    assert fast == slow
    # all three components share one net
    nets = netlist.compute_nets(p)
    terms = [t for n in nets for t in n.terminals]
    assert len({(t[1], t[2]) for t in terms}) >= 3


def test_compute_nets_scales_near_linearly_on_large_sheets():
    """Regression: a quadratic scan would make n=400 >> 4x slower than n=100."""
    times = {}
    for n in (100, 400):
        p = _grid_project(n, extra_vertical=n // 2)
        t0 = time.perf_counter()
        for _ in range(2):
            netlist.compute_nets(p)
        times[n] = (time.perf_counter() - t0) / 2
    # Near-linear: 4x wires should be well under 10x time (quadratic would be ~16x).
    ratio = times[400] / max(times[100], 1e-6)
    assert ratio < 10.0, f"compute_nets scaling looks quadratic: ratio={ratio:.1f} (t100={times[100]*1000:.1f}ms t400={times[400]*1000:.1f}ms)"
