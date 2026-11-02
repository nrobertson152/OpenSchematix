"""Validation of the bundled (built-in) symbol libraries.

Covers every built-in symbol, existing and new, so each symbol-library batch is checked the same way:
definition loads, ids unique, terminals valid and on the drawing, port domains match the category, geometry
renders (SVG and PDF), placement, wiring to every terminal, save and reopen, and - against a baseline taken
from main before the library expansion - that no existing symbol or directional-valve configuration changes.
Traceability: every symbol added by the expansion is recorded in docs/symbol-library-expansion/inventory.csv.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from openschematix import editing, export, netlist, projectio, symbols
from openschematix.geometry import GRID, point_on_segment
from openschematix.project import new_project
from openschematix.symbols import fluid
from openschematix.symbols.base import (CATEGORY_DOMAIN, LINE_WIDTHS, PORT_TYPES, is_drafting_element, port_domain,
                                        validate_geometry)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from symbol_geometry_baseline import geometry_fingerprint, valve_key  # noqa: E402

BASELINE = json.loads((ROOT / "tests/data/builtin_symbol_geometry_baseline.json").read_text(encoding="utf-8"))
INVENTORY = ROOT / "docs/symbol-library-expansion/inventory.csv"
BUILTINS = symbols.builtin_symbols()
NEW = [s for s in BUILTINS if s.id not in BASELINE["symbols"]]
ids = lambda s: s.id  # noqa: E731


def _geometries(sd):
    """(label, geometry) for a symbol; a configurable valve contributes every operator and pattern."""
    if sd.id.endswith(".dcv"):
        medium = sd.default_params["medium"]
        out = [("default", sd.build(None))]
        for vtype, (nports, _npos) in fluid.VALVE_TYPES[medium].items():
            d = fluid.default_valve_params(medium, vtype)
            for op in fluid.OPERATORS:
                out.append((f"{vtype} {op}", sd.build({**d, "left": [op], "right": ["spring"]})))
            for pat in fluid.PATTERNS[nports]:
                out.append((f"{vtype} {pat}", sd.build({**d, "positions": [pat] * len(d["positions"])})))
        return out
    return [("", sd.build(None))]


def _on_drawing(g, x, y, tol=1e-6):
    for p in g.prims:
        if p["k"] in ("line", "poly"):
            pts = list(p["pts"]) + ([p["pts"][0]] if p["k"] == "poly" else [])
            if any(point_on_segment((x, y), a, b, tol) for a, b in zip(pts, pts[1:])):
                return True
        elif p["k"] == "circle":
            (cx, cy), r = p["c"], p["r"]
            if abs(math.hypot(x - cx, y - cy) - r) <= 1e-3:
                return True
    return False


# ---------------------------------------------------------------- definitions
def test_symbol_ids_are_unique_and_well_formed():
    all_ids = [s.id for s in BUILTINS]
    assert len(all_ids) == len(set(all_ids))
    for i in all_ids:
        assert re.fullmatch(r"[a-z][a-z0-9]*(\.[a-z0-9]+)+", i), i


def test_no_existing_symbol_was_removed():
    missing = set(BASELINE["symbols"]) - {s.id for s in BUILTINS}
    assert not missing


@pytest.mark.parametrize("sd", BUILTINS, ids=ids)
def test_definition_loads_and_geometry_is_valid(sd):
    assert sd.name.strip() and sd.category.strip() and sd.group.strip() and sd.convention.strip()
    assert sd.description.strip()
    for label, g in _geometries(sd):
        assert not validate_geometry(g), (label, validate_geometry(g))
        assert g.prims, label
        for p in g.prims:
            assert p.get("w", "normal") in LINE_WIDTHS, (label, p)
            nums = []
            if p["k"] in ("line", "poly"):
                nums = [v for pt in p["pts"] for v in pt]
            elif p["k"] == "circle":
                nums = [*p["c"], p["r"]]
                assert p["r"] > 0
            elif p["k"] == "text":
                nums = list(p["p"])
                assert str(p["s"]).strip()
            assert all(math.isfinite(v) for v in nums), (label, p)
        b = g.bbox()
        assert (b[2] - b[0]) + (b[3] - b[1]) > 0, label


@pytest.mark.parametrize("sd", BUILTINS, ids=ids)
def test_terminals_have_valid_port_types_and_domain(sd):
    domain = CATEGORY_DOMAIN.get(sd.category)
    for label, g in _geometries(sd):
        seen = set()
        for t in g.terminals:
            assert t.name.strip(), label
            pt = sd.port_type(t)
            assert pt in PORT_TYPES, (label, t.name, pt)
            if domain and pt != "any":
                assert port_domain(pt) == domain, (sd.id, label, t.name, pt)
            assert (t.x, t.y) not in seen, (label, "two terminals at one point", t)
            seen.add((t.x, t.y))


@pytest.mark.parametrize("sd", NEW, ids=ids)
def test_new_symbol_terminals_lie_on_the_drawing(sd):
    """A terminal must be the end of a drawn lead (or lie on the outline): a pin floating in empty space
    connects a wire that visibly touches nothing."""
    for label, g in _geometries(sd):
        for t in g.terminals:
            assert t.x % GRID == 0 and t.y % GRID == 0
            assert _on_drawing(g, t.x, t.y), (sd.id, label, t.name, (t.x, t.y))


@pytest.mark.parametrize("sd", NEW, ids=ids)
def test_new_symbol_is_searchable_and_documented(sd):
    assert sd.id in {s.id for s in symbols.search(sd.name)}
    assert sd.category in symbols.categories()
    if not sd.build(None).terminals:
        assert is_drafting_element(sd), "only drafting elements (no BOM prefix, drafting group) may lack terminals"


# ---------------------------------------------------------------- unchanged existing drawings
@pytest.mark.parametrize("sid", sorted(BASELINE["symbols"]))
def test_existing_symbol_geometry_unchanged(sid):
    assert geometry_fingerprint(symbols.get(sid).build(None)) == BASELINE["symbols"][sid]


def test_existing_valve_configurations_unchanged():
    changed = [k for k, fp in BASELINE["valves"].items()
               if geometry_fingerprint(fluid.build_valve(json.loads(k))) != fp]
    assert not changed, f"{len(changed)} existing valve configurations render differently, e.g. {changed[:3]}"


# ---------------------------------------------------------------- render, place, wire, save, reopen
@pytest.fixture(scope="module")
def placed_project():
    """One sheet per category holding every built-in symbol, each terminal wired outward."""
    p = new_project("Bundled symbol library")
    by_cat = {}
    for sd in BUILTINS:
        if sd.group == "Internal":
            continue
        by_cat.setdefault(sd.category, []).append(sd)
    expect = []        # (sheet uid, component id, terminal name, wire id)
    first = True
    for cat, lst in sorted(by_cat.items()):
        doc = p.sheets[0] if first else p.add_sheet(cat)
        if first:
            doc.name, first = cat, False
        for i, sd in enumerate(lst):
            x, y = 200 + (i % 10) * 200, 200 + (i // 10) * 200
            c = editing.place(doc, sd.id, x, y)
            vec = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}
            for name, (tx, ty) in c.terminals().items():
                dx, dy = vec[c.terminal_dirs()[name]]
                w = editing.add_wire(doc, [(tx, ty), (tx + dx * 30, ty + dy * 30)])
                assert w is not None, (sd.id, name)
                expect.append((doc.uid, c.id, name, w.id, sd.id))
    return p, expect


def test_every_terminal_accepts_a_wire_and_joins_the_netlist(placed_project):
    p, expect = placed_project
    nets = netlist.compute_nets(p)
    where = {}
    for n in nets:
        for t in n.terminals:
            where[t] = n
    for uid, cid, name, wid, sid in expect:
        w = p.find_sheet(uid).wires[wid]
        assert w.start == [cid, name], (sid, name, w.start)
        n = where.get((uid, cid, name))
        assert n is not None and (uid, wid) in n.wires, (sid, name)


def test_all_symbols_render_to_svg_and_pdf(placed_project):
    p, _ = placed_project
    for doc in p.sheets:
        svg = export.to_svg(doc, project=p)
        assert svg.startswith("<?xml") or svg.lstrip().startswith("<svg")
        assert not re.search(r"\b(nan|inf)\b", svg.lower()), "non-finite coordinate in SVG"
        assert export.to_pdf(doc, project=p).startswith(b"%PDF")


def test_save_and_reopen_keeps_symbols_params_and_connections(placed_project, tmp_path):
    p, expect = placed_project
    before = {(d.uid, c.id): (c.symbol, json.dumps(c.params, sort_keys=True)) for d in p.sheets
              for c in d.components.values()}
    rows = netlist.connection_rows(p)
    path = tmp_path / "library.schematix"
    projectio.save_project(p, str(path), snapshot=False)
    q = projectio.open_any(str(path)).project
    after = {(d.uid, c.id): (c.symbol, json.dumps(c.params, sort_keys=True)) for d in q.sheets
             for c in d.components.values()}
    assert after == before
    for uid, cid, name, wid, sid in expect:
        assert q.find_sheet(uid).wires[wid].start == [cid, name], (sid, name)
    assert netlist.connection_rows(q) == rows


# ---------------------------------------------------------------- traceability and scope
def _inventory():
    with open(INVENTORY, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_inventory_traces_every_new_symbol():
    rows = _inventory()
    done = [r for r in rows if r["status"] in ("implemented", "validated")]
    traced = {t.strip() for r in done for t in r["target"].split(";") if t.strip()}
    untraced = sorted(s.id for s in NEW if s.id not in traced)
    assert not untraced, f"new symbols missing from inventory.csv: {untraced}"
    built = {s.id for s in BUILTINS}
    for r in done:
        for t in (x.strip() for x in r["target"].split(";")):
            if t.startswith("dcv operator '"):
                assert t[len("dcv operator '"):-1] in fluid.OPERATORS, (r["key"], t)
            elif t.startswith("dcv pattern '"):
                assert any(t[len("dcv pattern '"):-1] in v for v in fluid.PATTERNS.values()), (r["key"], t)
            elif t.startswith("dcv option '"):
                continue
            elif t:
                assert t in built, (r["key"], t)


ALLOWED = ("openschematix/symbols/", "openschematix/gui/dialogs.py", "tests/", "docs/", "tools/", "CHANGELOG.md")
BRANCH = "feature/expanded-default-symbol-libraries"


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)


def test_expansion_branch_changes_only_library_files():
    """On the expansion branch (or its pull request), production changes are limited to the bundled symbol
    definitions and the valve dialog (director decision Q2). Elsewhere - main, other branches - it is skipped."""
    try:
        branch = os.environ.get("GITHUB_HEAD_REF") or _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if branch != BRANCH:
            pytest.skip("not the symbol-library expansion branch")
        base = _git("merge-base", "HEAD", "origin/main")
        if base.returncode != 0:
            pytest.skip("origin/main not available")
        diff = _git("diff", "--name-only", base.stdout.strip(), "HEAD")
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git not available")
    files = [f for f in diff.stdout.split() if f]
    outside = [f for f in files if not f.startswith(ALLOWED)]
    assert not outside, f"unexpected production changes: {outside}"


# ---------------------------------------------------------------- drafting elements (director decision Q5)
DRAFTING = [s for s in BUILTINS if is_drafting_element(s)]


def test_drafting_element_classification_is_explicit():
    """Exemption needs BOTH a drafting group and an empty designator prefix; neither alone qualifies."""
    from openschematix.symbols.base import Geometry, SymbolDef, line
    g = Geometry([line(0, 0, 10, 0)], [])
    mk = lambda group, prefix: SymbolDef("x.test", "t", "Hydraulic", group, "Generic", "d", prefix, g)  # noqa: E731
    assert is_drafting_element(mk("Valve operators", ""))
    assert is_drafting_element(mk("Drafting", ""))
    assert not is_drafting_element(mk("Valve operators", "V")), "a purchasable part is never a drafting element"
    assert not is_drafting_element(mk("Connections", "")), "an empty prefix alone is not enough"
    assert not is_drafting_element(symbols.get("gen.offpage")), "sheet connector has no prefix but connects"
    terminal_less = [s.id for s in BUILTINS if not s.build(None).terminals]
    assert terminal_less and all(is_drafting_element(symbols.get(i)) for i in terminal_less)


def test_drafting_elements_never_connect_enter_bom_or_raise_checks(tmp_path):
    from openschematix import bom, check
    p = new_project("Drafting elements")
    doc = p.sheets[0]
    placed = []
    for i, sd in enumerate(DRAFTING):
        c = editing.place(doc, sd.id, 200 + (i % 12) * 150, 200 + (i // 12) * 150)
        placed.append(c)
        if not c.terminals():
            # a wire drawn onto the drawing (its envelope-side point) attaches to nothing
            w = editing.add_wire(doc, [(c.x, c.y), (c.x, c.y - 40)])
            assert w.start is None and w.end is None, sd.id
    assert bom.generate(p) == []
    ids = {c.id for c in placed}
    nets = netlist.compute_nets(p)
    pilot_terms = {(doc.uid, c.id, n) for c in placed for n in c.terminals()}
    assert {t for n in nets for t in n.terminals if t[1] in ids} <= pilot_terms
    no_term = {c.id for c in placed if not c.terminals()}
    issues = [i for i in check.check(p) if i.obj_id in ids]
    assert not [i for i in issues if i.obj_id in no_term], "terminal-less elements must not raise Check issues"
    assert {i.code for i in issues} <= {"open-terminal"}, "a pilot element may only report its unconnected port"
    for c in placed[:6]:
        before = {t: v for t, v in c.terminals().items()}
        editing.rotate_items(doc, [c.id], [], clockwise=True)
        editing.mirror_items(doc, [c.id], [])
        editing.move_items(doc, [c.id], [], 20, 10)
        assert set(c.terminals()) == set(before)
    path = tmp_path / "drafting.schematix"
    projectio.save_project(p, str(path), snapshot=False)
    q = projectio.open_any(str(path)).project
    got = {c.id: (c.symbol, c.rotation, c.mirror, c.x, c.y) for c in q.sheets[0].components.values()}
    assert got == {c.id: (c.symbol, c.rotation, c.mirror, c.x, c.y) for c in placed}
    assert bom.generate(q) == []
