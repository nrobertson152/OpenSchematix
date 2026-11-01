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
