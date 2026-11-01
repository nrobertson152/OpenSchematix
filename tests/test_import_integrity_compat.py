"""Compatibility audit: symbol integrity (PR #34) vs import/explode (PR #30/#35).

These tests document confirmed interactions after merging main (integrity) with
the import-edit branch. They are intentionally independent of Jules's production
changes and only assert observable behavior at the public API boundary.

Requires: PR #35 explode APIs + main integrity modules (merge main into this branch).
"""
from __future__ import annotations

import copy
import json

import pytest

from openschematix.symbols import get, all_symbols
from openschematix.symbols.base import Geometry, SymbolDef, Terminal
from openschematix.symbols.custom import (
    SymbolFormatError,
    blank_symbol,
    load_symbol_json,
    normalise,
    to_symdef,
)

integrity = pytest.importorskip("openschematix.symbols.integrity")
SEVERITY_ERROR = integrity.SEVERITY_ERROR
validate_document = integrity.validate_document
validate_symbol_def = integrity.validate_symbol_def

explode = pytest.importorskip("openschematix.symbols.explode")
symbol_to_doc = explode.symbol_to_doc
doc_from_data = explode.doc_from_data
SymbolImportError = explode.SymbolImportError


def _doc(**kw):
    d = blank_symbol("Compat probe")
    d["prims"] = [{"k": "line", "pts": [[-20, 0], [20, 0]], "w": "normal"}]
    d["pins"] = [
        {"id": "p1", "name": "1", "x": -20, "y": 0, "dir": "l", "type": "elec.passive", "show": True},
        {"id": "p2", "name": "2", "x": 20, "y": 0, "dir": "r", "type": "elec.passive", "show": True},
    ]
    d.update(kw)
    return d


def test_integrity_flags_missing_pin_id_as_error():
    doc = _doc()
    del doc["pins"][0]["id"]
    errs = [f for f in validate_document(doc) if f.severity == SEVERITY_ERROR]
    assert any("missing id" in f.problem for f in errs)


def test_normalise_repairs_missing_pin_id():
    doc = _doc()
    del doc["pins"][0]["id"]
    norm = normalise(doc)
    assert norm["pins"][0]["id"].startswith("p")


def test_doc_from_data_accepts_missing_pin_id_via_setdefault():
    """CONFIRMED GAP: doc_from_data setdefaults pin ids before fidelity check."""
    doc = _doc()
    del doc["pins"][0]["id"]
    out = doc_from_data(copy.deepcopy(doc), as_copy=True)
    assert out["pins"][0]["id"]
    errs = [f for f in validate_document(doc) if f.severity == SEVERITY_ERROR]
    assert any("missing id" in f.problem for f in errs)


def test_duplicate_pin_id_rejected_by_all_paths():
    doc = _doc()
    doc["pins"].append({"id": "p1", "name": "X", "x": 0, "y": 10, "dir": "u", "type": "elec.passive"})
    assert any("duplicate" in f.problem for f in validate_document(doc) if f.severity == SEVERITY_ERROR)
    with pytest.raises(SymbolFormatError, match="duplicate"):
        normalise(copy.deepcopy(doc))
    with pytest.raises((SymbolImportError, SymbolFormatError)):
        doc_from_data(copy.deepcopy(doc))


def test_off_grid_pin_rejected_by_all_paths():
    doc = _doc()
    doc["pins"][0]["x"] = 15
    assert any("grid" in f.problem for f in validate_document(doc) if f.severity == SEVERITY_ERROR)
    with pytest.raises(SymbolFormatError, match="grid"):
        normalise(copy.deepcopy(doc))
    with pytest.raises((SymbolImportError, SymbolFormatError)):
        doc_from_data(copy.deepcopy(doc))


def test_unknown_port_type_integrity_warns_import_rejects():
    doc = _doc()
    doc["pins"][0]["type"] = "elec.future"
    findings = validate_document(doc)
    assert any("port type" in f.problem for f in findings)
    norm = normalise(copy.deepcopy(doc))
    assert norm["pins"][0]["type"] == ""
    with pytest.raises(SymbolImportError, match="type"):
        doc_from_data(copy.deepcopy(doc))


def test_long_text_integrity_silent_import_rejects():
    doc = _doc()
    doc["prims"] = [{"k": "text", "p": [0, 0], "s": "Z" * 250, "size": 8, "anchor": "c"}]
    assert not any(f.severity == SEVERITY_ERROR for f in validate_document(doc))
    norm = normalise(copy.deepcopy(doc))
    assert len(norm["prims"][0]["s"]) == 200
    with pytest.raises(SymbolImportError):
        doc_from_data(copy.deepcopy(doc))


def test_unsupported_region_rejected_by_integrity_and_import():
    doc = _doc()
    doc["prims"] = [{"k": "region", "rings": [[[0, 0], [10, 0], [10, 10]]]}]
    assert any("unsupported" in f.problem or "region" in f.problem
               for f in validate_document(doc) if f.severity == SEVERITY_ERROR)
    with pytest.raises((SymbolImportError, SymbolFormatError)):
        doc_from_data(copy.deepcopy(doc))


def test_terminal_show_false_preserved_on_builtin_convert():
    g = Geometry(
        prims=[{"k": "line", "pts": [(-20.0, 0.0), (20.0, 0.0)], "w": "normal", "dash": False}],
        terminals=[
            Terminal("1", -20, 0, "l", label="1", ptype="elec.passive", show=False),
            Terminal("2", 20, 0, "r", label="2", ptype="elec.passive", show=True),
        ],
    )
    sd = SymbolDef("probe.show", "Show probe", "Electrical", "T", "T", "", "U", g)
    out = symbol_to_doc(sd, as_copy=True)
    by_id = {p["id"]: p for p in out["pins"]}
    assert by_id["1"]["show"] is False
    assert by_id["2"]["show"] is True


def test_terminal_show_false_preserved_on_custom_inplace_and_copy():
    doc = _doc()
    doc["pins"][0]["show"] = False
    sd = to_symdef(doc)
    inplace = symbol_to_doc(sd, as_copy=False)
    assert inplace["pins"][0]["show"] is False
    copied = symbol_to_doc(sd, as_copy=True)
    assert copied["pins"][0]["show"] is False


def test_aliases_stripped_on_copy_kept_inplace():
    doc = _doc()
    doc["aliases"] = ["ALT-A", "ALT-B"]
    sd = to_symdef(doc)
    copied = symbol_to_doc(sd, as_copy=True)
    assert not copied.get("aliases")
    inplace = symbol_to_doc(sd, as_copy=False)
    assert inplace.get("aliases") == ["ALT-A", "ALT-B"]


def test_non_bool_show_coerced_by_normalise_rejected_by_import():
    doc = _doc()
    doc["pins"][0]["show"] = "yes"
    norm = normalise(copy.deepcopy(doc))
    assert norm["pins"][0]["show"] is True
    with pytest.raises(SymbolImportError, match="show"):
        doc_from_data(copy.deepcopy(doc))


def test_all_builtins_convert_with_zero_integrity_errors():
    failures = []
    for sd in all_symbols():
        try:
            d = symbol_to_doc(sd)
            errs = [f for f in validate_document(d) if f.severity == SEVERITY_ERROR]
            if errs:
                failures.append((sd.id, errs[0].problem))
        except Exception as e:
            failures.append((sd.id, f"{type(e).__name__}: {e}"))
    assert failures == [], failures[:5]


def test_derived_pin_ids_match_source_terminal_names():
    sd = get("el.resistor.iec")
    assert sd is not None
    doc = symbol_to_doc(sd)
    src_names = [t.name for t in sd.build().terminals]
    assert [p["id"] for p in doc["pins"]] == src_names
    assert [p["name"] for p in doc["pins"]] == [t.label or t.name for t in sd.build().terminals]


def test_symbol_to_doc_does_not_mutate_source():
    sd = get("el.resistor.iec")
    g_before = [(t.name, t.x, t.y, t.show) for t in sd.build().terminals]
    prim_before = copy.deepcopy(sd.build().prims)
    _ = symbol_to_doc(sd)
    assert [(t.name, t.x, t.y, t.show) for t in sd.build().terminals] == g_before
    assert sd.build().prims == prim_before


def test_integrity_validate_symbol_def_read_only_after_import():
    sd = get("el.coil.iec")
    doc = symbol_to_doc(sd)
    derived = to_symdef(doc)
    findings = validate_symbol_def(derived)
    assert not any(f.severity == SEVERITY_ERROR for f in findings)


def test_roundtrip_osym_json_through_load_and_import(tmp_path):
    sd = get("el.resistor.iec")
    doc = symbol_to_doc(sd)
    path = tmp_path / "r.osym"
    path.write_text(json.dumps(doc), encoding="utf-8")
    loaded = load_symbol_json(path.read_text(encoding="utf-8"), source=str(path))
    again = doc_from_data(loaded, as_copy=True)
    assert len(again["pins"]) == len(doc["pins"])
    assert [p["id"] for p in again["pins"]] == [p["id"] for p in doc["pins"]]


def test_malformed_json_rejected_consistently(tmp_path):
    path = tmp_path / "bad.osym"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(SymbolFormatError, match=r"invalid JSON|not a valid"):
        explode.doc_from_file(str(path))
    with pytest.raises(SymbolFormatError, match=r"invalid JSON"):
        load_symbol_json(path.read_text(encoding="utf-8"), source=str(path))
