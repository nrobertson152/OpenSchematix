"""Contact sheet of built-in symbols, rendered by the application's own SVG export, for visual comparison
with the reference documents of the symbol-library expansion.

    python tools/symbol_contact_sheet.py OUT.svg [ID_PREFIX ...] [--new] [--cols N] [--valves]

ID_PREFIX limits the sheet to ids starting with one of the prefixes; --new shows only symbols not in the
pre-expansion baseline (tests/data/builtin_symbol_geometry_baseline.json); --valves adds one directional
valve per configurator operator and flow pattern. Each symbol is labelled with its id; terminal names are
shown. Convert to PNG with e.g. `rsvg-convert -w 2400 -b white OUT.svg -o OUT.png`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openschematix import editing, export, symbols  # noqa: E402
from openschematix.project import new_project  # noqa: E402
from openschematix.symbols import fluid  # noqa: E402


def entries(prefixes=(), only_new=False, valves=False):
    base = json.loads((ROOT / "tests/data/builtin_symbol_geometry_baseline.json").read_text(encoding="utf-8"))
    out = []
    for sd in symbols.builtin_symbols():
        if sd.group == "Internal":
            continue
        if prefixes and not sd.id.startswith(tuple(prefixes)):
            continue
        if only_new and sd.id in base["symbols"]:
            continue
        out.append((sd.id, sd.id, None))
    if valves:
        for medium in ("hyd", "pneu"):
            sid = f"fl.{medium}.dcv"
            for vtype, (nports, _n) in fluid.VALVE_TYPES[medium].items():
                d = fluid.default_valve_params(medium, vtype)
                if vtype not in ("4/3", "5/2"):
                    continue
                for op in fluid.OPERATORS:
                    out.append((sid, f"{medium} {vtype} {op}", {**d, "left": [op], "right": ["spring"]}))
                for pat in fluid.PATTERNS[nports]:
                    pos = list(d["positions"])
                    pos[len(pos) // 2] = pat
                    out.append((sid, f"{medium} {vtype} {pat}", {**d, "positions": pos}))
    return out


def build(items, cols=6, cell=(260, 220)):
    p = new_project("Symbol contact sheet")
    p.settings["show_terminal_names"] = True
    doc = p.sheets[0]
    for i, (sid, label, params) in enumerate(items):
        x = 160 + (i % cols) * cell[0]
        y = 140 + (i // cols) * cell[1]
        c = editing.place(doc, sid, x, y, params=params)
        c.designator = ""
        c.label = label
    return p, doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("prefix", nargs="*")
    ap.add_argument("--new", action="store_true")
    ap.add_argument("--valves", action="store_true")
    ap.add_argument("--cols", type=int, default=6)
    a = ap.parse_args(argv)
    items = entries(a.prefix, a.new, a.valves)
    if not items:
        print("no symbols match")
        return 1
    p, doc = build(items, a.cols)
    Path(a.out).write_text(export.to_svg(doc, use_sheet=False, project=p), encoding="utf-8")
    print(f"{len(items)} symbols -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
