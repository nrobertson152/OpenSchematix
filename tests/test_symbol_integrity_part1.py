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


def test_invalid_coordinates_nan_inf():
    doc = _valid_custom_doc()
    doc["pins"][0]["x"] = float("nan")
    findings = validate_document(doc)
    assert any("invalid numeric coordinates" in f.problem for f in findings)

    doc2 = _valid_custom_doc()
    doc2["pins"][0]["y"] = float("inf")
    findings2 = validate_document(doc2)
    assert any("invalid numeric coordinates" in f.problem for f in findings2)


def test_off_grid_pin_coordinates():
    doc = _valid_custom_doc()
    doc["pins"][0]["x"] = 15
    findings = validate_document(doc)
    assert any("not on the" in f.problem and "grid" in f.problem for f in findings)
    with pytest.raises(SymbolFormatError, match=r"not on the .* grid"):
        normalise(doc)


def test_invalid_primitive_coordinates():
    doc = _valid_custom_doc()
    doc["prims"] = [{"k": "line", "pts": [[0, 0], [float("nan"), 10]]}]
    findings = validate_document(doc)
    assert any("invalid numeric coordinates" in f.problem for f in findings)


def test_unsupported_geometry_primitive():
    doc = _valid_custom_doc()
    doc["prims"] = [{"k": "bezier", "pts": [[0, 0], [10, 10]]}]
    findings = validate_document(doc)
    assert any("unsupported kind" in f.problem for f in findings)
    with pytest.raises(SymbolFormatError, match=r"unknown kind"):
        normalise(doc)


def test_invalid_metadata_types():
    doc = _valid_custom_doc()
    doc["properties"] = ["not", "a", "dict"]
    findings = validate_document(doc)
    assert any("properties must be" in f.problem for f in findings)
    doc2 = _valid_custom_doc()
    doc2["tags"] = "sensor"
    findings2 = validate_document(doc2)
    assert any("tags must be a list" in f.problem for f in findings2)


def test_validator_does_not_mutate_document():
    doc = _valid_custom_doc()
    original = copy.deepcopy(doc)
    validate_document(doc)
    assert doc == original


def test_validator_does_not_mutate_symbol_def():
    sd = get("el.resistor.iec")
    assert sd is not None
    before_id = sd.id
    before_name = sd.name
    before_terms = [(t.name, t.x, t.y) for t in sd.build().terminals]
    validate_symbol_def(sd)
    assert sd.id == before_id
    assert sd.name == before_name
    after_terms = [(t.name, t.x, t.y) for t in sd.build().terminals]
    assert before_terms == after_terms


def test_finding_structure():
    doc = _valid_custom_doc()
    doc["id"] = "bad"
    findings = validate_document(doc)
    assert findings
    f = findings[0]
    assert isinstance(f, Finding)
    assert f.symbol_id
    assert f.problem
    assert f.severity in (SEVERITY_ERROR, "warning", "info")
    d = f.as_dict()
    assert "symbol_id" in d and "problem" in d and "severity" in d


def test_load_symbol_json_preserves_normalise_contract():
    doc = _valid_custom_doc()
    loaded = load_symbol_json(json.dumps(doc))
    assert loaded["format"] == "OpenSchematix Symbol"
    assert loaded["pins"][0]["id"] == "p1"
    problems = validate_geometry(to_symdef(loaded).geometry)
    assert problems == []


def test_optional_and_legacy_fields_accepted():
    doc = blank_symbol("Legacy-ish")
    del doc["tags"]
    doc["derived_from"] = {"id": "el.resistor.iec", "name": "Resistor", "revision": "1"}
    doc["future_optional"] = {"note": "ignored by current schema"}
    findings = validate_document(doc)
    assert not any(f.severity == SEVERITY_ERROR for f in findings)
    norm = normalise(doc)
    assert norm["id"].startswith("user:")
    assert norm["derived_from"]["id"] == "el.resistor.iec"
    assert "future_optional" not in norm
    sd = to_symdef(doc)
    assert sd.id == norm["id"]
    findings2 = validate_symbol_def(sd)
    assert not any(f.severity == SEVERITY_ERROR for f in findings2)
