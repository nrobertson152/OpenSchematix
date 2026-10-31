"""Regenerate docs/SYMBOLS.md from the symbol library: python tools/gen_symbol_docs.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from openschematix import symbols  # noqa: E402

lines = ["# Symbol library reference", "",
         "Generated from the source by `tools/gen_symbol_docs.py`; do not edit by hand.", "",
         "**Conventions.** Symbols are drawn following the conventions of the standards named in the "
         "*Convention* column as they are generally published and taught. They were reviewed visually "
         "during development but have **not** been certified against the official (paid) standard documents. "
         "Where IEC and IEEE/ANSI practice differ, both forms are provided and labelled.", "",
         "Drawing units: 1 unit = 0.25 mm, snap grid = 10 units (2.5 mm). All terminals lie on the grid.", ""]
for cat in symbols.categories():
    syms = [s for s in symbols.all_symbols() if s.category == cat and s.group != "Internal"]
    if not syms:
        continue
    lines += [f"## {cat}", "", "| Symbol | Group | Convention | Terminals | Ref. prefix | Notes |", "|---|---|---|---|---|---|"]
    for s in syms:
        g = s.build(s.default_params)
        terms = ", ".join(t.name for t in g.terminals)
        notes = s.description + (f" *{s.notes}*" if s.notes else "")
        if s.parametric:
            terms += " (varies with configuration)"
        lines.append(f"| {s.name} | {s.group} | {s.convention} | {terms} | {s.prefix or '-'} | {notes} |")
    lines.append("")
lines += ["## Directional control valves", "",
          "Configurable through *Configure valve...*: hydraulic 2/2, 3/2, 4/2, 4/3 and pneumatic 2/2, 3/2, 5/2, 5/3; "
          "per-position flow paths (parallel, crossed, closed, tandem, float and open centres; pneumatic exhausted "
          "centre); up to two operators per side (spring, solenoid, pilot, lever, push-button, general manual). "
          "Ports are drawn on the rest position (the centre position of 3-position valves, otherwise the "
          "position next to the spring). Pilot operators add pilot ports (X/Y hydraulic; 12/14 or 10/12 pneumatic).",
          "", "## Not included in this release", "",
          "Symbols that could not be drawn with confidence without the standard documents were left out rather "
          "than guessed: silencers, lubricators and complete FRL units, proportional/servo valves, "
          "pressure switches and transducers, sequence and counterbalance valves, rotary actuators, quick "
          "couplings, logic gates, and IEC 60617 binary-logic symbols. Use the generic function blocks and the "
          "label field meanwhile.", ""]
out = os.path.join(os.path.dirname(__file__), "..", "docs", "SYMBOLS.md")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("wrote", os.path.abspath(out))
