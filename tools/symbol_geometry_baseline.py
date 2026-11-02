"""Fingerprint the geometry of every built-in symbol (and of every directional-valve configuration the
configurator could produce) so that additions to the bundled libraries can be checked not to change any
existing drawing.

    python tools/symbol_geometry_baseline.py tests/data/builtin_symbol_geometry_baseline.json

The fingerprint covers primitives (kind, points, radius, fill, dash, width, text) and terminals (name, position,
direction, label, port type) with coordinates rounded to 1e-6. Used by tests/test_bundled_symbol_library.py.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _r(v):
    return round(float(v), 6) + 0.0


def geometry_fingerprint(g) -> str:
    prims = []
    for p in g.prims:
        k = p["k"]
        d = {"k": k, "w": p.get("w", "normal"), "dash": bool(p.get("dash", False)), "fill": bool(p.get("fill", False))}
        if k in ("line", "poly"):
            d["pts"] = [[_r(x), _r(y)] for x, y in p["pts"]]
        elif k == "circle":
            d["c"], d["r"] = [_r(p["c"][0]), _r(p["c"][1])], _r(p["r"])
        elif k == "text":
            d["p"], d["s"], d["size"], d["anchor"] = [_r(p["p"][0]), _r(p["p"][1])], p["s"], p.get("size"), p.get("anchor")
        else:
            d["raw"] = repr(sorted(p.items()))
        prims.append(d)
    terms = [[t.name, _r(t.x), _r(t.y), t.dir, t.label, t.ptype, bool(t.show)] for t in g.terminals]
    blob = json.dumps({"prims": prims, "terms": terms}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def valve_configurations(fluid, operators=None, patterns=None, valve_types=None, max_ops=2):
    """Valve parameter sets covering the given tables: (a) every assignment of flow patterns to positions for
    every valve type, with that type's default operators; (b) every pair of side operator lists (empty, each
    single operator, and common two-operator stacks) with the type's default positions."""
    operators = list(operators if operators is not None else fluid.OPERATORS)
    patterns = patterns if patterns is not None else fluid.PATTERNS
    valve_types = valve_types if valve_types is not None else fluid.VALVE_TYPES
    side_lists = [[]] + [[o] for o in operators]
    pairs = [["solenoid", "spring"], ["spring", "solenoid"], ["lever", "spring"], ["pilot", "spring"],
             ["spring", "pilot"], ["solenoid", "pilot"]]
    side_lists += [p for p in pairs if all(o in operators for o in p)]
    out, seen = [], set()

    def add(p):
        k = valve_key(p)
        if k not in seen:
            seen.add(k)
            out.append(p)

    for medium, types in valve_types.items():
        for vtype, (nports, npos) in types.items():
            d = fluid.default_valve_params(medium, vtype)
            for positions in itertools.product(list(patterns[nports]), repeat=npos):
                add({**d, "positions": list(positions)})
            for left in side_lists:
                for right in side_lists:
                    add({**d, "left": list(left), "right": list(right)})
    return out


def valve_key(params) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def baseline():
    from openschematix import symbols
    from openschematix.symbols import fluid
    out = {"symbols": {}, "valves": {}}
    for sd in symbols.builtin_symbols():
        out["symbols"][sd.id] = geometry_fingerprint(sd.build(None))
    for params in valve_configurations(fluid):
        out["valves"][valve_key(params)] = geometry_fingerprint(fluid.build_valve(params))
    return out


if __name__ == "__main__":
    data = baseline()
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    text = json.dumps(data, indent=0, sort_keys=True) + "\n"
    if target:
        target.write_text(text, encoding="utf-8")
        print(f"{len(data['symbols'])} symbols, {len(data['valves'])} valve configurations -> {target}")
    else:
        sys.stdout.write(text)
