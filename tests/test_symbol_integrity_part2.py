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


def test_unhashable_port_type_does_not_crash():
    doc = _valid_custom_doc()
    doc["pins"][0]["type"] = ["elec", "passive"]
    findings = validate_document(doc)
    assert any("port type" in f.problem for f in findings)
    assert isinstance(findings, list)


def test_overflow_and_huge_coordinates():
    doc = _valid_custom_doc()
    doc["pins"][0]["x"] = 10 ** 400
    findings = validate_document(doc)
    assert any("invalid numeric" in f.problem or "out of range" in f.problem for f in findings)

    doc2 = _valid_custom_doc()
    doc2["pins"][0]["x"] = 1e20
    findings2 = validate_document(doc2)
    assert any("out of range" in f.problem for f in findings2)


def test_nested_unexpected_structures():
    doc = _valid_custom_doc()
    doc["prims"] = [{"k": "line", "pts": {"a": 1}}]
    findings = validate_document(doc)
    assert any("needs at least two points" in f.problem or "malformed" in f.problem for f in findings)

    doc3 = _valid_custom_doc()
    doc3["pins"] = [None, 42]
    findings3 = validate_document(doc3)
    assert sum(1 for f in findings3 if "not an object" in f.problem) >= 2


def test_strict_vs_normalise_missing_pin_id():
    doc = _valid_custom_doc()
    del doc["pins"][0]["id"]
    findings = validate_document(doc)
    assert any("missing id" in f.problem for f in findings)
    norm = normalise(doc)
    assert norm["pins"][0]["id"].startswith("p")


def test_strict_vs_normalise_invalid_direction():
    doc = _valid_custom_doc()
    doc["pins"][0]["dir"] = "north"
    findings = validate_document(doc)
    assert any("invalid direction" in f.problem for f in findings)
    norm = normalise(doc)
    assert norm["pins"][0]["dir"] == "r"


def test_parametric_symbol_build_does_not_mutate_params():
    sd = get("fl.hyd.dcv")
    assert sd is not None and sd.parametric
    params = {"type": "4/3", "medium": "hyd"}
    params_before = dict(params)
    default_before = dict(sd.default_params)
    findings = validate_symbol_def(sd, params=params)
    assert params == params_before
    assert sd.default_params == default_before
    assert not any(f.severity == SEVERITY_ERROR for f in findings)


def test_parametric_symbol_default_build_read_only():
    sd = get("fl.pneu.dcv")
    assert sd is not None and sd.parametric
    default_before = dict(sd.default_params)
    geo_before = sd.geometry
    findings = validate_symbol_def(sd)
    assert sd.default_params == default_before
    assert sd.geometry is geo_before
    assert not any(f.severity == SEVERITY_ERROR for f in findings)
