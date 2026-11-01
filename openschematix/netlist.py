"""Electrical / fluid-power connectivity across a whole project.

A *net* is a set of wires and component terminals that are connected:
  * wires connect where an end point of one wire lies on another wire;
  * a terminal connects to wires whose end point lies on it (or that
    reference it), and to other terminals at exactly the same point;
  * sheet connectors (gen.offpage) with the same label are connected across
    all sheets of the project.
Wires that merely cross are not connected (see editing.crossings).

The same rules are used by connectivity.analyse (junction dots / open ends on
one sheet), so drawings, reports and checks always agree.

Also provides automatic wire numbering, terminal-strip reports and
connection / wiring lists.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from . import symbols
from .geometry import point_on_segment, same
from .symbols.general import OFFPAGE_IDS


def _key(p):
    return (round(p[0], 2), round(p[1], 2))


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


@dataclass
class Net:
    index: int
    wires: list = field(default_factory=list)       # (sheet_uid, wire_id)
    terminals: list = field(default_factory=list)   # (sheet_uid, comp_id, terminal_name)
    links: list = field(default_factory=list)       # sheet-connector labels joining sheets
    number: str = ""

    @property
    def sheets(self):
        return sorted({w[0] for w in self.wires} | {t[0] for t in self.terminals})


def pin_ref_connects(doc, ref) -> bool:
    """True if *ref* is a wire end that should join the electrical netlist.

    A reference is accepted only when the component exists and the pin name is
    a real terminal of that component's symbol. If the symbol definition is
    temporarily unavailable (``symbols.get`` returns ``None``), a non-empty pin
    name is still accepted so legitimate custom-symbol attachments are not
    dropped merely because the library entry is not registered in this process.
    Nonexistent components, blank pin names, and pin names that the resolved
    symbol does not define never create netlist terminals.
    """
    if not ref or not isinstance(ref, (list, tuple)) or len(ref) < 2:
        return False
    cid, pin = ref[0], ref[1]
    c = doc.components.get(cid)
    if c is None:
        return False
    if pin is None or (isinstance(pin, str) and not pin.strip()):
        return False
    pin = str(pin)
    sd = symbols.get(c.symbol)
    if sd is None:
        # Unresolved definition: keep the named attachment (PR #37 territory).
        return True
    # Resolved symbol: pin must exist on the geometry.
    return pin in c.terminals()


def _sheet_nodes(doc, uf: _UF):
    """Union the nodes of one sheet. Node ids: ('w', uid, wid), ('t', uid, cid, name).

    Wire endpoints join terminals by *validated* pin references and by
    geometry (end point coincides with a terminal). Invalid pin names never
    create fictitious terminals. Geometric wire-to-wire joins are unchanged
    and remain compatible with a spatial candidate index on the wire loop.
    """
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
            if pin_ref_connects(doc, ref):
                uf.union(("w", uid, w.id), ("t", uid, ref[0], str(ref[1])))
        for idx in (0, -1):
            p = w.points[idx]
            for n in term_at.get(_key(p), []):
                uf.union(("w", uid, w.id), n)
            for o in wires:
                if o.id == w.id:
                    continue
                if any(point_on_segment(p, a, b) for a, b in zip(o.points, o.points[1:])):
                    uf.union(("w", uid, w.id), ("w", uid, o.id))


def link_label(c) -> str:
    return (c.label or c.designator or "").strip()


def compute_nets(project) -> list[Net]:
    uf = _UF()
    for doc in project.sheets:
        _sheet_nodes(doc, uf)
    # sheet connectors with equal labels join nets across sheets
    by_label = {}
    for doc in project.sheets:
        for c in doc.components.values():
            if c.symbol in OFFPAGE_IDS and link_label(c):
                for name in c.terminals():
                    by_label.setdefault(link_label(c), []).append(("t", doc.uid, c.id, name))
    for nodes in by_label.values():
        for n in nodes[1:]:
            uf.union(nodes[0], n)
    groups = {}
    for node in list(uf.p):
        groups.setdefault(uf.find(node), []).append(node)
    nets = []
    order = {d.uid: i for i, d in enumerate(project.sheets)}
    for nodes in groups.values():
        n = Net(0)
        for node in nodes:
            if node[0] == "w":
                n.wires.append((node[1], node[2]))
            else:
                n.terminals.append((node[1], node[2], node[3]))
        if len(n.wires) + len(n.terminals) < 2 and not n.wires:
            continue   # an unconnected terminal is not a net
        n.wires.sort(key=lambda w: (order.get(w[0], 0), w[1]))
        n.terminals.sort(key=lambda t: (order.get(t[0], 0), t[1], t[2]))
        labels = set()
        for uid, cid, _name in n.terminals:
            c = project.find_sheet(uid).components.get(cid)
            if c is not None and c.symbol in OFFPAGE_IDS and link_label(c):
                labels.add(link_label(c))
        n.links = sorted(labels)
        nets.append(n)

    def sort_key(n):
        first = n.wires[0] if n.wires else n.terminals[0][:2]
        doc = project.find_sheet(first[0])
        o = doc.wires.get(first[1]) if n.wires else doc.components.get(first[1])
        if n.wires and o is not None:
            p = min(o.points)
        elif o is not None:
            p = (o.x, o.y)
        else:
            p = (0, 0)
        return (order.get(first[0], 0), round(p[1] / 10), p[0])
    nets.sort(key=sort_key)
    for i, n in enumerate(nets, 1):
        n.index = i
        n.number = _net_number(project, n)
    return nets


def _net_number(project, n: Net) -> str:
    nums = []
    for uid, wid in n.wires:
        w = project.find_sheet(uid).wires.get(wid)
        if w is not None and w.number:
            nums.append((not w.number_manual, w.number))
    return min(nums)[1] if nums else ""


def terminal_tag(project, uid, cid, name) -> str:
    doc = project.find_sheet(uid)
    c = doc.components.get(cid) if doc else None
    if c is None:
        return "?"
    from .project import is_terminal_symbol
    if is_terminal_symbol(c.symbol):
        return c.tag()
    sd = symbols.get(c.symbol)
    base = c.designator or (c.label if c.symbol in OFFPAGE_IDS else "") or (sd.name if sd else c.symbol)
    if len(c.terminals()) == 1:
        return base
    return f"{base}:{c.terminal_label(name)}"


def net_domain(project, n: Net) -> set:
    doms = set()
    for uid, cid, name in n.terminals:
        c = project.find_sheet(uid).components.get(cid)
        if c is None:
            continue
        sd = symbols.get(c.symbol)
        if sd is None:
            continue
        for t in c.geometry().terminals:
            if t.name == name:
                doms.add(symbols.port_domain(sd.port_type(t)))
    return doms - {"any"}


# ================================================================ wire numbering
def format_number(conv: dict, n: int, sheet_no: int = 1) -> str:
    digits = int(conv.get("digits", 0) or 0)
    body = str(n).zfill(digits) if digits else str(n)
    return f"{conv.get('prefix', '')}{body}"


def numberable(project, n: Net) -> bool:
    """Wire numbers are assigned to electrical nets (and nets without
    terminals); hydraulic and pneumatic lines are not numbered."""
    if not n.wires:
        return False
    doms = net_domain(project, n)
    # A mixed-domain net is invalid (reported by ERC), not an electrical net.
    # Domain-neutral terminals do not restrict otherwise electrical nets.
    return not doms or doms == {"elec"}


def assign_wire_numbers(project, renumber: bool = False) -> int:
    """Give every electrical net a wire number. Existing numbers are kept
    (stable when wires or components move); manual numbers are never
    changed. With `renumber`, automatic numbers are reassigned in drawing
    order. Returns the number of nets that received a new number."""
    conv = project.settings.get("wire_numbering", {})
    scheme = conv.get("scheme", "sequential")
    start = int(conv.get("start", 1) or 1)
    step = max(1, int(conv.get("step", 1) or 1))
    nets = compute_nets(project)
    wire = lambda uid, wid: project.find_sheet(uid).wires[wid]  # noqa: E731
    if renumber:
        for n in nets:
            for uid, wid in n.wires:
                w = wire(uid, wid)
                if not w.number_manual:
                    w.number = ""
    used = set()
    changed = 0
    pending = []
    for n in nets:
        if not numberable(project, n):
            # A wire can acquire a fluid-domain terminal after being numbered.
            # Remove stale automatic numbers, but never erase user overrides.
            for u, i in n.wires:
                w = wire(u, i)
                if not w.number_manual:
                    w.number = ""
            continue
        manual = sorted({wire(u, i).number for u, i in n.wires if wire(u, i).number_manual and wire(u, i).number})
        autos = sorted({wire(u, i).number for u, i in n.wires if not wire(u, i).number_manual and wire(u, i).number},
                       key=_natural)
        if manual:
            num = manual[0]
        else:
            num = next((a for a in autos if a not in used), "")
        if not num:
            pending.append(n)
            continue
        used.add(num)
        for u, i in n.wires:
            w = wire(u, i)
            if not w.number_manual and w.number != num:
                w.number = num
        n.number = num
    counters = {}
    order = {d.uid: i + 1 for i, d in enumerate(project.sheets)}
    for n in pending:
        sheet_no = order.get(n.wires[0][0], 1)
        if scheme == "sheet":
            k = counters.get(sheet_no, 0)
            while True:
                k += 1
                num = format_number(conv, sheet_no * 100 + k, sheet_no)
                if num not in used:
                    break
            counters[sheet_no] = k
        else:
            k = counters.get(0, start - step)
            while True:
                k += step
                num = format_number(conv, k)
                if num not in used:
                    break
            counters[0] = k
        used.add(num)
        n.number = num
        for u, i in n.wires:
            w = wire(u, i)
            if not w.number_manual:
                w.number = num
        changed += 1
    return changed


def set_net_number(project, sheet_uid: str, wire_id: int, number: str):
    """Manual override: give the whole net of a wire this number (empty
    string clears the override)."""
    nets = compute_nets(project)
    for n in nets:
        if (sheet_uid, wire_id) in n.wires:
            for u, i in n.wires:
                w = project.find_sheet(u).wires[i]
                w.number = number
                w.number_manual = bool(number)
            return n
    return None


def _natural(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


# ================================================================ reports
def connection_rows(project, nets=None) -> list[dict]:
    """From-to connection list. Within each net the terminals are chained
    in drawing order (daisy chain), which is how the net is usually wired."""
    nets = nets if nets is not None else compute_nets(project)
    names = {d.uid: d.name for d in project.sheets}
    rows = []
    for n in nets:
        terms = [t for t in n.terminals
                 if project.find_sheet(t[0]).components[t[1]].symbol not in OFFPAGE_IDS]
        for a, b in zip(terms, terms[1:]):
            rows.append({"wire": n.number, "net": n.index,
                         "from": terminal_tag(project, *a), "from_sheet": names.get(a[0], ""),
                         "to": terminal_tag(project, *b), "to_sheet": names.get(b[0], ""),
                         "links": ", ".join(n.links)})
        if len(terms) == 1:
            rows.append({"wire": n.number, "net": n.index, "from": terminal_tag(project, *terms[0]),
                         "from_sheet": names.get(terms[0][0], ""), "to": "(not connected)", "to_sheet": "",
                         "links": ", ".join(n.links)})
    return rows


def wire_rows(project) -> list[dict]:
    """One row per drawn wire with its number, ends and properties."""
    names = {d.uid: d.name for d in project.sheets}
    rows = []
    for doc in project.sheets:
        for w in sorted(doc.wires.values(), key=lambda w: (_natural(w.number), w.id)):
            def end(ref, p):
                if ref and ref[0] in doc.components:
                    return terminal_tag(project, doc.uid, ref[0], ref[1])
                return "junction" if p else ""
            rows.append({"sheet": names[doc.uid], "wire": w.number, "from": end(w.start, w.points[0]),
                         "to": end(w.end, w.points[-1]), "colour": w.props.get("colour", ""),
                         "size": w.props.get("size", ""), "manual": "yes" if w.number_manual else ""})
    return rows


def terminal_rows(project, nets=None) -> list[dict]:
    """Terminal-strip report: one row per terminal with what is connected on
    each side (side 1 = left/field, side 2 = right/internal)."""
    from .project import is_terminal_symbol
    nets = nets if nets is not None else compute_nets(project)
    where = {}
    for n in nets:
        for t in n.terminals:
            where[t] = n
    names = {d.uid: d.name for d in project.sheets}
    rows = []
    for doc in project.sheets:
        for c in doc.components.values():
            if not is_terminal_symbol(c.symbol):
                continue
            row = {"strip": c.designator, "terminal": c.props.get("terminal", ""), "sheet": names[doc.uid],
                   "description": c.props.get("description", "") or c.label}
            for side, tname in (("1", "1"), ("2", "2")):
                n = where.get((doc.uid, c.id, tname))
                others = []
                if n is not None:
                    others = [terminal_tag(project, *t) for t in n.terminals if t != (doc.uid, c.id, tname)
                              and project.find_sheet(t[0]).components[t[1]].symbol not in OFFPAGE_IDS]
                row[f"side{side}"] = ", ".join(others)
                row[f"wire{side}"] = n.number if n is not None else ""
            rows.append(row)
    rows.sort(key=lambda r: (_natural(r["strip"]), _natural(r["terminal"])))
    return rows


def to_csv(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    """CSV text for spreadsheet programs: UTF-8 with BOM (so Excel detects
    the encoding), comma separated, CRLF line endings, every field quoted when
    needed, and formula-like cells protected against CSV injection."""
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    wr.writerow([label for _k, label in columns])
    for r in rows:
        wr.writerow([_safe_cell(r.get(k, "")) for k, _l in columns])
    return "﻿" + buf.getvalue()


def _safe_cell(v) -> str:
    s = "" if v is None else str(v)
    if s and s[0] in "=+-@\t\r" and not re.fullmatch(r"[-+]?\d+(\.\d+)?", s):
        return "'" + s
    return s


CONNECTION_COLUMNS = [("wire", "Wire no."), ("from", "From"), ("from_sheet", "From sheet"), ("to", "To"),
                      ("to_sheet", "To sheet"), ("links", "Sheet links"), ("net", "Net")]
WIRE_COLUMNS = [("sheet", "Sheet"), ("wire", "Wire no."), ("from", "From"), ("to", "To"), ("colour", "Colour"),
                ("size", "Cross-section"), ("manual", "Manual number")]
TERMINAL_COLUMNS = [("strip", "Strip"), ("terminal", "Terminal"), ("description", "Description"),
                    ("side1", "Side 1 connects to"), ("wire1", "Wire 1"), ("side2", "Side 2 connects to"),
                    ("wire2", "Wire 2"), ("sheet", "Sheet")]


def xref_targets(project, doc, comp) -> list[tuple[str, str]]:
    """For a sheet connector: [(sheet number, zone)] of every other connector
    with the same label, for the automatic cross-reference annotation."""
    from .titleblock import zone_of
    label = link_label(comp)
    if not label or comp.symbol not in OFFPAGE_IDS:
        return []
    out = []
    for i, d in enumerate(project.sheets, 1):
        for c in d.components.values():
            if c.symbol in OFFPAGE_IDS and link_label(c) == label and not (d is doc and c.id == comp.id):
                out.append((str(i), zone_of(d, (c.x, c.y))))
    return sorted(set(out), key=lambda t: (int(t[0]), t[1]))
