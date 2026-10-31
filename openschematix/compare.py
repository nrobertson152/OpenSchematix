"""Revision comparison.

Objects are matched by their persistent identifiers - (sheet uid, object
id) - never by position, so a moved component is reported as *modified
(moved)*, not as removed + added. Connection changes are found by comparing,
for every component terminal present in both versions, the set of terminals
it is connected to (through wires, junctions and sheet connectors).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import symbols
from .model import PROP_LABELS
from .netlist import compute_nets, terminal_tag

ADDED, REMOVED, MODIFIED = "added", "removed", "modified"


@dataclass
class Change:
    status: str            # added | removed | modified
    category: str          # sheet | component | wire | shape | connection | project
    sheet_uid: str
    obj_id: int | None
    title: str
    details: list = field(default_factory=list)


@dataclass
class Diff:
    changes: list = field(default_factory=list)

    def by_sheet(self, uid):
        return [c for c in self.changes if c.sheet_uid == uid]

    def ids(self, uid, status):
        return {c.obj_id for c in self.changes if c.sheet_uid == uid and c.status == status and c.obj_id is not None
                and c.category in ("component", "wire", "shape")}

    def counts(self) -> dict:
        out = {}
        for c in self.changes:
            k = f"{c.category} {c.status}"
            out[k] = out.get(k, 0) + 1
        return out

    @property
    def empty(self):
        return not self.changes


def _sym_name(sid):
    sd = symbols.get(sid)
    return sd.name if sd else sid


def _comp_title(c):
    return f"{c.tag()} ({_sym_name(c.symbol)})" if c.designator else _sym_name(c.symbol)


def _comp_changes(a, b) -> list[str]:
    d = []
    if a.symbol != b.symbol:
        d.append(f"symbol: {_sym_name(a.symbol)} → {_sym_name(b.symbol)}")
    if a.designator != b.designator:
        d.append(f"identifier: {a.designator or '—'} → {b.designator or '—'}")
    if a.label != b.label:
        d.append(f"label: “{a.label}” → “{b.label}”")
    if (a.x, a.y) != (b.x, b.y):
        d.append(f"moved by ({(b.x - a.x) * 0.25:+.1f}, {(b.y - a.y) * 0.25:+.1f}) mm")
    if a.rotation != b.rotation or a.mirror != b.mirror:
        d.append(f"orientation: {a.rotation}°{' mirrored' if a.mirror else ''} → "
                 f"{b.rotation}°{' mirrored' if b.mirror else ''}")
    if a.params != b.params:
        d.append("symbol configuration changed")
    for k in sorted(set(a.props) | set(b.props)):
        va, vb = a.props.get(k, ""), b.props.get(k, "")
        if va != vb:
            d.append(f"{PROP_LABELS.get(k, k)}: “{va}” → “{vb}”")
    if a.terminal_labels != b.terminal_labels:
        d.append("terminal designations changed")
    if a.layer != b.layer:
        d.append(f"layer: {a.layer} → {b.layer}")
    if a.in_bom != b.in_bom:
        d.append("included in BOM" if b.in_bom else "excluded from BOM")
    return d


def _wire_changes(a, b) -> list[str]:
    d = []
    if a.points != b.points:
        d.append("route changed")
    if a.number != b.number:
        d.append(f"wire number: {a.number or '—'} → {b.number or '—'}")
    if a.style != b.style:
        d.append(f"line type: {a.style} → {b.style}")
    if a.props != b.props:
        d.append("wire properties changed")
    return d


def _connection_map(project):
    """terminal key -> frozenset of connected terminal keys."""
    out = {}
    for n in compute_nets(project):
        keys = set(n.terminals)
        for t in n.terminals:
            out[t] = frozenset(keys - {t})
    return out


def compare(a, b) -> Diff:
    """Differences from project revision a (old) to b (new)."""
    diff = Diff()
    add = diff.changes.append
    for k in sorted(set(a.meta) | set(b.meta)):
        if a.meta.get(k, "") != b.meta.get(k, ""):
            add(Change(MODIFIED, "project", "", None, f"Project {k.replace('_', ' ')}",
                       [f"“{a.meta.get(k, '')}” → “{b.meta.get(k, '')}”"]))
    sa = {s.uid: s for s in a.sheets}
    sb = {s.uid: s for s in b.sheets}
    for uid, s in sb.items():
        if uid not in sa:
            add(Change(ADDED, "sheet", uid, None, f"Sheet “{s.name}” added",
                       [f"{len(s.components)} components, {len(s.wires)} wires"]))
    for uid, s in sa.items():
        if uid not in sb:
            add(Change(REMOVED, "sheet", uid, None, f"Sheet “{s.name}” removed",
                       [f"{len(s.components)} components, {len(s.wires)} wires"]))
    order_a = [u for u in (x.uid for x in a.sheets) if u in sb]
    order_b = [u for u in (x.uid for x in b.sheets) if u in sa]
    if order_a != order_b:
        add(Change(MODIFIED, "sheet", "", None, "Sheet order changed",
                   [" → ".join(sb[u].name for u in order_b)]))
    for uid in sb:
        if uid not in sa:
            continue
        x, y = sa[uid], sb[uid]
        det = []
        if x.name != y.name:
            det.append(f"renamed “{x.name}” → “{y.name}”")
        if x.sheet.to_dict() != y.sheet.to_dict():
            for k, v in y.sheet.to_dict().items():
                if x.sheet.to_dict().get(k) != v:
                    det.append(f"{k.replace('_', ' ')}: {x.sheet.to_dict().get(k)!r} → {v!r}")
        if det:
            add(Change(MODIFIED, "sheet", uid, None, f"Sheet “{y.name}” settings", det))
        for cid, c in y.components.items():
            if cid not in x.components:
                add(Change(ADDED, "component", uid, cid, _comp_title(c)))
            else:
                d = _comp_changes(x.components[cid], c)
                if d:
                    add(Change(MODIFIED, "component", uid, cid, _comp_title(c), d))
        for cid, c in x.components.items():
            if cid not in y.components:
                add(Change(REMOVED, "component", uid, cid, _comp_title(c)))
        for wid, w in y.wires.items():
            t = f"Wire {w.number}" if w.number else f"Wire #{wid}"
            if wid not in x.wires:
                add(Change(ADDED, "wire", uid, wid, t))
            else:
                d = _wire_changes(x.wires[wid], w)
                if d:
                    add(Change(MODIFIED, "wire", uid, wid, t, d))
        for wid, w in x.wires.items():
            if wid not in y.wires:
                add(Change(REMOVED, "wire", uid, wid, f"Wire {w.number}" if w.number else f"Wire #{wid}"))
        for sid, s in y.shapes.items():
            if sid not in x.shapes:
                add(Change(ADDED, "shape", uid, sid, f"Drawing {s.kind}"))
            elif x.shapes[sid].to_dict() != s.to_dict():
                add(Change(MODIFIED, "shape", uid, sid, f"Drawing {s.kind}", ["geometry or style changed"]))
        for sid, s in x.shapes.items():
            if sid not in y.shapes:
                add(Change(REMOVED, "shape", uid, sid, f"Drawing {s.kind}"))
    ca, cb = _connection_map(a), _connection_map(b)
    def exists(p, k):
        d = p.find_sheet(k[0])
        return d is not None and k[1] in d.components and k[2] in d.components[k[1]].terminals()
    for key in sorted(set(ca) | set(cb), key=lambda k: (k[0], k[1], k[2])):
        if not (exists(a, key) and exists(b, key)):
            continue  # added/removed components are reported above
        old, new = ca.get(key, frozenset()), cb.get(key, frozenset())
        if old != new:
            def tags(p, keys):
                out = []
                for k in keys:
                    d = p.find_sheet(k[0])
                    if d is not None and k[1] in d.components:
                        out.append(terminal_tag(p, *k))
                return ", ".join(sorted(out)) or "nothing"
            gone = old - new
            came = new - old
            det = []
            if came:
                det.append("now also connected to " + tags(b, came))
            if gone:
                det.append("no longer connected to " + tags(a, gone))
            add(Change(MODIFIED, "connection", key[0], key[1], terminal_tag(b, *key), det))
    return diff
