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

FIXTURE_OSYM = os.path.join(os.path.dirname(__file__), "fixtures", "integrity_resistor.osym")


def _valid_custom_doc():
    doc = blank_symbol("Test resistor")
    doc["prims"] = [{"k": "line", "pts": [[-20, 0], [20, 0]], "w": "normal"}]
    doc["pins"] = [
        {"id": "p1", "name": "1", "x": -20, "y": 0, "dir": "l", "type": "elec.passive"},
        {"id": "p2", "name": "2", "x": 20, "y": 0, "dir": "r", "type": "elec.passive"},
    ]
    return doc


def test_invalid_text_anchor_loads_but_strict_warns():
    """Unknown anchor is repaired by normalise; strict audit reports a warning."""
    doc = _valid_custom_doc()
    doc["prims"] = [{"k": "text", "p": [0, 0], "s": "X", "size": 8, "anchor": "diagonal"}]
    findings = validate_document(doc)
    assert any("anchor" in f.problem for f in findings)
    assert not any(f.severity == SEVERITY_ERROR and "anchor" in f.problem for f in findings)
    norm = normalise(doc)
    assert norm["prims"][0]["anchor"] == "c"


def test_repairable_legacy_loads_but_fails_strict_audit():
    """Missing pin id + invalid dir: normalise repairs; strict audit reports errors."""
    doc = _valid_custom_doc()
    del doc["pins"][0]["id"]
    doc["pins"][0]["dir"] = "north"
    findings = validate_document(doc)
    assert any("missing id" in f.problem for f in findings)
    assert any("invalid direction" in f.problem for f in findings)
    norm = normalise(doc)
    assert norm["pins"][0]["id"].startswith("p")
    assert norm["pins"][0]["dir"] == "r"


def test_unsupported_geometry_actionable_diagnostic():
    doc = _valid_custom_doc()
    doc["prims"] = [{"k": "bezier", "pts": [[0, 0], [10, 10]]}]
    findings = validate_document(doc)
    assert any("unsupported kind" in f.problem and "bezier" in f.problem for f in findings)
    with pytest.raises(SymbolFormatError, match="unknown kind"):
        normalise(doc)


def test_alias_collision_with_builtin_diagnosed():
    doc = _valid_custom_doc()
    doc["aliases"] = ["el.coil.iec", "MY-ALIAS"]
    findings = validate_document(doc)
    assert any("collides" in f.problem and "el.coil.iec" in f.problem for f in findings)
    norm = normalise(doc)
    assert "MY-ALIAS" in norm.get("aliases", [])


def test_arrow_size_invalid_repairs_on_load():
    doc = _valid_custom_doc()
    doc["prims"] = [{"k": "line", "pts": [[0, 0], [20, 0]], "arrow_end": True, "arrow_size": float("nan")}]
    findings = validate_document(doc)
    assert any("arrow_size" in f.problem for f in findings)
    norm = normalise(doc)
    assert norm["prims"][0].get("arrow_end") is True
    assert norm["prims"][0].get("arrow_size") == 10.0


def test_cli_exit_codes_documented_policy(tmp_path):
    """Exit 0 only when no error-severity findings; warnings alone still 0."""
    from openschematix.symbols.integrity import main
    assert main(["--builtins"]) == 0
    bad = tmp_path / "bad.osym"
    bad.write_text("{")
    assert main([str(bad)]) == 1
    assert main([FIXTURE_OSYM]) == 0
