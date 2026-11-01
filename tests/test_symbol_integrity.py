"""Regression tests for symbol library integrity validation and load errors."""
from __future__ import annotations

import copy
import json

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


def test_builtin_symbols_pass_integrity():
    findings = validate_builtin_library()
    errors = [f for f in findings if f.severity == SEVERITY_ERROR]
    assert errors == [], f"built-in library errors: {errors[:5]}"


def test_valid_builtin_symbol_def():
    sd = get("el.resistor.iec")
    assert sd is not None
    findings = validate_symbol_def(sd)
    assert not any(f.severity == SEVERITY_ERROR for f in findings)


def test_valid_custom_symbol_document():
    doc = _valid_custom_doc()
    findings = validate_document(doc)
    assert not any(f.severity == SEVERITY_ERROR for f in findings)
    sd = to_symdef(doc)
    findings2 = validate_symbol_def(sd)
    assert not any(f.severity == SEVERITY_ERROR for f in findings2)


def test_serialization_compatibility_roundtrip():
    doc = _valid_custom_doc()
    text = json.dumps(doc)
    loaded = load_symbol_json(text)
    assert loaded["id"] == doc["id"]
    assert loaded["name"] == doc["name"]
    sd = to_symdef(loaded)
    assert sd.id == doc["id"]
    assert len(sd.geometry.terminals) == 2


def test_malformed_json_error_message():
    with pytest.raises(SymbolFormatError, match=r"invalid JSON"):
        load_symbol_json("{not json", source="bad.osym")


def test_empty_or_truncated_file_message():
    with pytest.raises(SymbolFormatError, match=r"empty or truncated"):
        load_symbol_json("   ", source="empty.osym")
    with pytest.raises(SymbolFormatError, match=r"empty or truncated"):
        load_symbol_json("", source="empty.osym")


def test_wrong_format_message():
    with pytest.raises(SymbolFormatError, match=r"expected format"):
        load_symbol_json(json.dumps({"format": "Other", "version": 1, "id": "user:abc"}))


def test_unsupported_schema_version():
    doc = _valid_custom_doc()
    doc["version"] = 99
    with pytest.raises(SymbolFormatError, match=r"newer than this program supports"):
        normalise(doc)
    findings = validate_document(doc)
    assert any("newer" in f.problem for f in findings if f.severity == SEVERITY_ERROR)


def test_non_integer_version():
    doc = _valid_custom_doc()
    doc["version"] = "1"
    with pytest.raises(SymbolFormatError, match=r"must be an integer"):
        normalise(doc)


def test_missing_required_id_prefix():
    doc = _valid_custom_doc()
    doc["id"] = "builtin.like"
    with pytest.raises(SymbolFormatError, match=r"must start with 'user:'"):
        normalise(doc)


def test_duplicate_pin_ids_in_document():
    doc = _valid_custom_doc()
    doc["pins"].append({"id": "p1", "name": "X", "x": 0, "y": 10, "dir": "u"})
    findings = validate_document(doc)
    assert any("duplicate pin id" in f.problem for f in findings)
    with pytest.raises(SymbolFormatError, match=r"duplicate id"):
        normalise(doc)


def test_duplicate_symbol_ids_in_library():
    doc = _valid_custom_doc()
    sd1 = to_symdef(doc)
    sd2 = to_symdef(copy.deepcopy(doc))
    findings = validate_library([sd1, sd2], check_duplicates=True)
    assert any("duplicate symbol identifier" in f.problem for f in findings)


def test_missing_or_malformed_pin():
    doc = _valid_custom_doc()
    doc["pins"] = ["not-a-dict"]
    findings = validate_document(doc)
    assert any("not an object" in f.problem for f in findings)


def test_invalid_pin_direction():
    doc = _valid_custom_doc()
    doc["pins"][0]["dir"] = "north"
    findings = validate_document(doc)
    assert any("invalid direction" in f.problem for f in findings)


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
    """Documents with optional fields and without optional sections remain valid."""
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


def test_missing_optional_pins_and_prims_lists():
    doc = blank_symbol("Empty artwork")
    doc.pop("pins", None)
    doc.pop("prims", None)
    findings = validate_document({**doc, "pins": [], "prims": []})
    assert not any(f.severity == SEVERITY_ERROR for f in findings)
    norm = normalise(doc)
    assert norm["pins"] == []
    assert norm["prims"] == []


def test_invalid_field_types_for_core_metadata():
    doc = _valid_custom_doc()
    doc["pins"] = {"not": "a list"}
    findings = validate_document(doc)
    assert any("pins must be a list" in f.problem for f in findings)

    doc2 = _valid_custom_doc()
    doc2["prims"] = "line"
    findings2 = validate_document(doc2)
    assert any("prims must be a list" in f.problem for f in findings2)

    with pytest.raises(SymbolFormatError, match=r"JSON object|not an OpenSchematix"):
        load_symbol_json("[1, 2, 3]", source="array.osym")
