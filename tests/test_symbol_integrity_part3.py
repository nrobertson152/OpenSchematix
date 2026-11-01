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
