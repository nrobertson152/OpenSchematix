"""Project-wide search across all sheets."""
from __future__ import annotations

from dataclasses import dataclass

from . import symbols
from .model import PROP_LABELS

FIELDS = {
    "designator": "Identifier", "symbol": "Symbol type", "label": "Label", "description": "Description",
    "manufacturer": "Manufacturer", "part_number": "Part number", "rating": "Rating", "wire": "Wire number",
    "terminal": "Terminal", "custom": "Custom property", "text": "Drawing text",
}


@dataclass
class Hit:
    sheet_uid: str
    sheet_name: str
    sheet_no: int
    kind: str          # component | wire | shape
    obj_id: int
    field: str
    value: str
    title: str         # what to show in the results list

    @property
    def field_label(self):
        return FIELDS.get(self.field, self.field)


def _match(value: str, words, exact: bool) -> bool:
    v = (value or "").lower()
    if not v:
        return False
    if exact:
        return v == " ".join(words)
    return all(w in v for w in words)


def search(project, query: str, fields=None, exact: bool = False, sheet_uids=None) -> list[Hit]:
    """Find objects whose fields match all words of `query` (case-insensitive
    substring match, or whole-value match with `exact`). `fields` limits the
    searched fields (keys of FIELDS)."""
    words = query.lower().split()
    if not words:
        return []
    fields = set(fields or FIELDS)
    hits = []
    for n, doc in enumerate(project.sheets, 1):
        if sheet_uids is not None and doc.uid not in sheet_uids:
            continue

        def add(kind, oid, field, value, title):
            hits.append(Hit(doc.uid, doc.name, n, kind, oid, field, value, title))
        for c in doc.components.values():
            sd = symbols.get(c.symbol)
            sname = sd.name if sd else c.symbol
            title = f"{c.tag()} – {sname}" if c.designator else sname
            cands = []
            if "designator" in fields:
                cands.append(("designator", c.tag()))
            if "symbol" in fields:
                cands += [("symbol", sname), ("symbol", c.symbol)]
            if "label" in fields:
                cands.append(("label", c.label))
            for k in ("description", "manufacturer", "part_number", "rating"):
                if k in fields:
                    cands.append((k, c.props.get(k, "")))
            if "terminal" in fields:
                cands.append(("terminal", c.props.get("terminal", "")))
                for name in c.terminals():
                    cands.append(("terminal", f"{c.designator}:{c.terminal_label(name)}"))
            if "custom" in fields:
                for k, v in c.props.items():
                    if k not in PROP_LABELS:
                        cands.append(("custom", f"{k}={v}"))
            seen = set()
            for f, v in cands:
                if (f, v) in seen:
                    continue
                seen.add((f, v))
                if _match(v, words, exact):
                    add("component", c.id, f, v, title)
                    break
        if "wire" in fields:
            for w in doc.wires.values():
                if _match(w.number, words, exact):
                    add("wire", w.id, "wire", w.number, f"Wire {w.number}")
        if "text" in fields:
            for s in doc.shapes.values():
                if s.kind == "text" and _match(s.s, words, exact):
                    add("shape", s.id, "text", s.s, f"Text “{s.s[:40]}”")
    return hits


def object_point(project, hit: Hit):
    """A point to centre the view on for a hit."""
    doc = project.find_sheet(hit.sheet_uid)
    o = doc.item(hit.obj_id) if doc else None
    if o is None:
        return None
    b = o.bbox()
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
