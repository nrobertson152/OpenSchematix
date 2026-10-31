"""Automatic bill of materials.

Components are grouped into BOM lines by part identity:
  * with a part number: (manufacturer, part number)
  * without:           (symbol, description, rating, parameters)
Items that are not purchasable are left out: components switched off with
"Include in BOM", and symbols that represent no physical part (earth and
ground marks, connection points, sheet connectors, missing-symbol
placeholders, symbols without a designator prefix).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import symbols
from .netlist import CONNECTION_COLUMNS, to_csv  # noqa: F401  (re-exported for convenience)
from .symbols.general import OFFPAGE_IDS, UNKNOWN_ID

NON_PURCHASABLE = {"el.earth", "el.earth.pe", "el.chassis", "el.ground.signal", "el.connector.point",
                   UNKNOWN_ID, *OFFPAGE_IDS}


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def purchasable(c) -> bool:
    if not c.in_bom or c.symbol in NON_PURCHASABLE:
        return False
    sd = symbols.get(c.symbol)
    if sd is None:
        return False
    return bool(sd.prefix) or bool(c.props.get("part_number"))


@dataclass
class BomLine:
    item: int = 0
    quantity: int = 0
    designators: list = field(default_factory=list)
    description: str = ""
    manufacturer: str = ""
    part_number: str = ""
    rating: str = ""
    symbol: str = ""
    sheets: list = field(default_factory=list)
    refs: list = field(default_factory=list)     # (sheet uid, component id)

    def designator_text(self) -> str:
        return compress_designators(self.designators)

    def as_row(self) -> dict:
        return {"item": self.item, "quantity": self.quantity, "designators": self.designator_text(),
                "description": self.description, "manufacturer": self.manufacturer,
                "part_number": self.part_number, "rating": self.rating, "symbol": self.symbol,
                "sheets": ", ".join(self.sheets)}


BOM_COLUMNS = [("item", "Item"), ("quantity", "Qty"), ("designators", "Designators"),
               ("description", "Description"), ("manufacturer", "Manufacturer"), ("part_number", "Part number"),
               ("rating", "Rating"), ("symbol", "Symbol"), ("sheets", "Sheets")]


def compress_designators(ds: list) -> str:
    """K1, K2, K3, K5 -> 'K1-K3, K5' (ranges of three or more)."""
    items = sorted(set(ds), key=natural_key)
    out, run = [], []

    def flush():
        if len(run) >= 3:
            out.append(f"{run[0][2]}–{run[-1][2]}")
        else:
            out.extend(r[2] for r in run)
        run.clear()
    for d in items:
        m = re.fullmatch(r"(.*?)(\d+)", d)
        if m and run and run[-1][0] == m.group(1) and run[-1][1] + 1 == int(m.group(2)) and ":" not in d:
            run.append((m.group(1), int(m.group(2)), d))
            continue
        flush()
        if m and ":" not in d:
            run.append((m.group(1), int(m.group(2)), d))
        else:
            out.append(d)
    flush()
    return ", ".join(out)


def generate(project, sheet_uids=None, include_excluded: bool = False) -> list[BomLine]:
    groups: dict = {}
    for i, doc in enumerate(project.sheets, 1):
        if sheet_uids is not None and doc.uid not in sheet_uids:
            continue
        for c in doc.components.values():
            if not include_excluded and not purchasable(c):
                continue
            sd = symbols.get(c.symbol)
            name = sd.name if sd else c.symbol
            pn = c.props.get("part_number", "").strip()
            mf = c.props.get("manufacturer", "").strip()
            desc = c.props.get("description", "").strip() or name
            rating = c.props.get("rating", "").strip()
            if pn:
                key = ("pn", mf.lower(), pn.lower())
            else:
                key = ("sym", c.symbol, desc.lower(), rating.lower(), json.dumps(c.params, sort_keys=True))
            line = groups.get(key)
            if line is None:
                line = groups[key] = BomLine(description=desc, manufacturer=mf, part_number=pn, rating=rating,
                                             symbol=name)
            line.quantity += 1
            line.designators.append(c.tag())
            line.refs.append((doc.uid, c.id))
            if doc.name not in line.sheets:
                line.sheets.append(doc.name)
    lines = sorted(groups.values(), key=lambda l: natural_key(min(l.designators, key=natural_key)))
    for n, l in enumerate(lines, 1):
        l.item = n
    return lines


def filter_lines(lines, text: str = "") -> list:
    words = text.lower().split()
    if not words:
        return list(lines)
    out = []
    for l in lines:
        blob = " ".join(str(v) for v in l.as_row().values()).lower()
        if all(w in blob for w in words):
            out.append(l)
    return out


def sort_lines(lines, column: str, descending: bool = False) -> list:
    def key(l):
        v = l.as_row().get(column, "")
        return (0, v) if isinstance(v, int) else (1, natural_key(str(v)))
    return sorted(lines, key=key, reverse=descending)


def bom_csv(lines) -> str:
    return to_csv([l.as_row() for l in lines], BOM_COLUMNS)
