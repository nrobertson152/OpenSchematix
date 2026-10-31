"""Generate a catalogue of every library symbol (PDF or SVG) for visual review.

Usage: python tools/symbol_catalog.py out.pdf [--category Hydraulic] [--valves]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openschematix import editing, export, symbols  # noqa: E402
from openschematix.model import Document  # noqa: E402
from openschematix.symbols.fluid import PATTERNS, VALVE_TYPES, default_valve_params  # noqa: E402


def build(category=None, valves=False):
    doc = Document()
    doc.sheet.size = "A2"
    doc.sheet.title = "OpenSchematix symbol catalogue" + (f" - {category}" if category else "")
    doc.sheet.show_title_block = False
    x, y = 120, 140
    W, _ = doc.sheet.size_units()
    entries = []
    if valves:
        for medium, types in VALVE_TYPES.items():
            for vt, (nports, npos) in types.items():
                p = default_valve_params(medium, vt)
                entries.append(("fl.hyd.dcv" if medium == "hyd" else "fl.pneu.dcv", p, f"{medium} {vt}"))
            for pat in PATTERNS[4 if medium == "hyd" else 5]:
                p = default_valve_params(medium, "4/3" if medium == "hyd" else "5/3")
                p["positions"][1] = pat
                p["left"], p["right"] = ["spring", "pilot"], ["spring", "lever"]
                entries.append(("fl.hyd.dcv" if medium == "hyd" else "fl.pneu.dcv", p, f"centre {pat}"))
    else:
        for s in symbols.all_symbols():
            if category and s.category != category:
                continue
            entries.append((s.id, None, f"{s.name} ({s.convention.split(' style')[0]})"))
    step_x = 330 if valves else 230
    for sid, params, name in entries:
        c = editing.place(doc, sid, x, y, params=params)
        c.designator = ""
        c.label = name[:34]
        c.text_side = "below"
        x += step_x
        if x > W - 150:
            x = 120
            y += 150
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--category")
    ap.add_argument("--valves", action="store_true")
    a = ap.parse_args()
    d = build(a.category, a.valves)
    (export.export_svg if a.out.endswith(".svg") else export.export_pdf)(d, a.out, use_sheet=False)
    print("wrote", a.out, len(d.components), "symbols")
