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


def test_cli_exit_codes_and_source_location(tmp_path):
    from openschematix.symbols.integrity import main
    assert main(["--builtins"]) == 0
    bad = tmp_path / "bad.osym"
    bad.write_text("{not json")
    assert main([str(bad)]) == 1
    doc = _valid_custom_doc()
    doc["pins"][0]["x"] = 15
    good_path = tmp_path / "offgrid.osym"
    good_path.write_text(json.dumps(doc))
    findings = validate_document(json.loads(good_path.read_text()), source=str(good_path))
    assert findings
    assert all(f.source == str(good_path) for f in findings)
    assert any(f.location for f in findings)
    d = findings[0].as_dict()
    assert "source" in d and "problem" in d and "severity" in d


def test_cli_json_output_includes_source(tmp_path, capsys):
    from openschematix.symbols.integrity import main
    doc = _valid_custom_doc()
    doc["pins"].append({"id": "p1", "name": "X", "x": 0, "y": 10, "dir": "u"})
    path = tmp_path / "dup.osym"
    path.write_text(json.dumps(doc))
    code = main([str(path), "--json"])
    assert code == 1
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, list) and data
    assert any(item.get("source") == str(path) for item in data)
    assert any("duplicate pin id" in item.get("problem", "") for item in data)


def test_nested_mutable_params_not_mutated():
    """Deep copy of params: nested lists/dicts survive validation unchanged."""
    sd = get("fl.hyd.dcv")
    assert sd is not None and sd.parametric
    nested = {"positions": ["parallel", "closed"], "extra": {"k": [1, 2, 3]}}
    params = {"type": "4/3", "medium": "hyd", "nested": nested}
    params_before = copy.deepcopy(params)
    default_before = copy.deepcopy(sd.default_params)
    geo_before = sd.geometry
    findings = validate_symbol_def(sd, params=params)
    assert params == params_before
    assert params["nested"] is nested
    assert params["nested"]["extra"]["k"] == [1, 2, 3]
    assert sd.default_params == default_before
    assert sd.geometry is geo_before
    assert not any(f.severity == SEVERITY_ERROR for f in findings)


def test_cli_module_subprocess_builtins():
    """Invoke the real CLI entry point: python -m openschematix.symbols.integrity."""
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, "-m", "openschematix.symbols.integrity", "--builtins"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr or r.stdout
    assert "finding" not in r.stdout.lower() or "No integrity problems" in r.stdout


def test_cli_module_subprocess_bad_file_and_json(tmp_path):
    import subprocess
    import sys
    bad = tmp_path / "broken.osym"
    bad.write_text("{not-json")
    r = subprocess.run(
        [sys.executable, "-m", "openschematix.symbols.integrity", str(bad)],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 1
    assert "invalid JSON" in r.stdout or "invalid JSON" in r.stderr

    doc = _valid_custom_doc()
    doc["pins"].append({"id": "p1", "name": "X", "x": 0, "y": 10, "dir": "u"})
    path = tmp_path / "dup.osym"
    path.write_text(json.dumps(doc))
    r2 = subprocess.run(
        [sys.executable, "-m", "openschematix.symbols.integrity", str(path), "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert r2.returncode == 1
    data = json.loads(r2.stdout)
    assert isinstance(data, list) and data
    assert any(item.get("source") == str(path) for item in data)
    assert any("duplicate pin id" in item.get("problem", "") for item in data)


def test_aliases_optional_field_accepted_after_main_merge():
    """Documents with aliases (main PR #31) remain valid under strict validation."""
    doc = _valid_custom_doc()
    doc["aliases"] = ["ALT-ID", "sensor.prox"]
    findings = validate_document(doc)
    assert not any(f.severity == SEVERITY_ERROR for f in findings)
    norm = normalise(doc)
    assert norm.get("aliases") == ["ALT-ID", "sensor.prox"]
