"""Regression tests for symbol library integrity validation and load errors."""
from __future__ import annotations

import copy
import json
import os

import pytest

from openschematix.symbols import get
from openschematix.symbols.base import validate_geometry
from openschematix.symbols.custom import (
    SymbolFormatError,
    blank_symbol,
    load_symbol_json,
    normalise,
    to_symdef,
)
from openschematix.symbols.integrity import (
    SEVERITY_ERROR,
    Finding,
    validate_builtin_library,
    validate_document,
    validate_library,
    validate_symbol_def,
)


def _valid_custom_doc():
    doc = blank_symbol("Test resistor")
    doc["prims"] = [{"k": "line", "pts": [[-20, 0], [20, 0]], "w": "normal"}]
    doc["pins"] = [
        {"id": "p1", "name": "1", "x": -20, "y": 0, "dir": "l", "type": "elec.passive"},
        {"id": "p2", "name": "2", "x": 20, "y": 0, "dir": "r", "type": "elec.passive"},
    ]
    return doc


def test_aliases_optional_field_accepted_after_main_merge():
    """Documents with aliases (main PR #31) remain valid under strict validation."""
    doc = _valid_custom_doc()
    doc["aliases"] = ["ALT-ID", "sensor.prox"]
    findings = validate_document(doc)
    assert not any(f.severity == SEVERITY_ERROR for f in findings)
    norm = normalise(doc)
    assert norm.get("aliases") == ["ALT-ID", "sensor.prox"]


FIXTURE_OSYM = os.path.join(os.path.dirname(__file__), "fixtures", "integrity_resistor.osym")


def test_fixture_osym_validate_then_load():
    """Valid .osym → strict audit clean → load succeeds."""
    raw = open(FIXTURE_OSYM, encoding="utf-8").read()
    doc = json.loads(raw)
    findings = validate_document(doc)
    assert not any(f.severity == SEVERITY_ERROR for f in findings), findings
    loaded = load_symbol_json(raw, source=FIXTURE_OSYM)
    assert loaded["id"] == "user:fixture-resistor-001"
    assert loaded["aliases"] == ["FIX-R", "R.fixture"]
    assert any(p.get("arrow_end") for p in loaded["prims"])
    sd = to_symdef(loaded)
    assert [t.name for t in sd.geometry.terminals] == ["p1", "p2"]
    assert not any(f.severity == SEVERITY_ERROR for f in validate_symbol_def(sd))


def test_embed_save_reopen_preserves_pins_aliases_arrows(tmp_path):
    """Symbol → place in project → save → reopen preserves pins, aliases, arrows."""
    from openschematix import projectio
    from openschematix.project import new_project
    from openschematix import symbols as symreg
    from openschematix import editing

    raw = open(FIXTURE_OSYM, encoding="utf-8").read()
    doc = load_symbol_json(raw)
    sd = to_symdef(doc)
    symreg.add_project_symbol(sd)
    p = new_project("Integrity e2e")
    sheet = p.sheets[0]
    c = editing.place(sheet, sd.id, 100, 100)
    assert sorted(c.terminals()) == ["p1", "p2"]
    path = str(tmp_path / "e2e.schematix")
    projectio.save_project(p, path, snapshot=False)
    res = projectio.open_any(path)
    p2 = res.project
    p2.activate_symbols()
    c2 = next(iter(p2.sheets[0].components.values()))
    assert sorted(c2.terminals()) == ["p1", "p2"]
    emb = p2.symbols.get(sd.id) or {}
    assert emb.get("aliases") == ["FIX-R", "R.fixture"]
    assert any(pr.get("arrow_end") for pr in emb.get("prims", []))
    term_meta = {(t.name, t.label, t.ptype) for t in to_symdef(emb).geometry.terminals}
    assert ("p1", "1", "elec.passive") in term_meta
    assert ("p2", "2", "elec.passive") in term_meta


def test_invalid_revision_fails_load_and_strict_audit():
    doc = _valid_custom_doc()
    doc["revision"] = "not-an-int"
    findings = validate_document(doc)
    assert any("revision" in f.problem for f in findings if f.severity == SEVERITY_ERROR)
    with pytest.raises(SymbolFormatError, match="revision"):
        normalise(doc)
    doc2 = _valid_custom_doc()
    doc2["revision"] = -3
    assert any("revision" in f.problem for f in validate_document(doc2) if f.severity == SEVERITY_ERROR)
    with pytest.raises(SymbolFormatError, match="revision"):
        normalise(doc2)


def test_invalid_text_size_fails_load_and_strict_audit():
    doc = _valid_custom_doc()
    doc["prims"] = [{"k": "text", "p": [0, 0], "s": "X", "size": "huge"}]
    findings = validate_document(doc)
    assert any("text size" in f.problem for f in findings if f.severity == SEVERITY_ERROR)
    with pytest.raises(SymbolFormatError, match="not a number"):
        normalise(doc)
