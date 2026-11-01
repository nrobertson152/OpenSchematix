"""Security regressions for bounded, deterministic DXF parsing (Issue #55)."""
import math

import pytest

from openschematix import dxf


def _entity(kind, fields):
    return ("0\nSECTION\n2\nENTITIES\n0\n" + kind + "\n"
            + "".join(f"{code}\n{value}\n" for code, value in fields)
            + "0\nENDSEC\n0\nEOF\n").encode()


def test_dxf_rejects_oversized_bytes_before_decoding():
    with pytest.raises(dxf.DxfError, match="maximum supported size"):
        dxf.import_dxf(b"x" * (dxf.MAX_DXF_BYTES + 1))


def test_dxf_rejects_excess_group_pairs_before_entity_expansion(monkeypatch):
    monkeypatch.setattr(dxf, "MAX_DXF_PAIRS", 6)
    with pytest.raises(dxf.DxfError, match="too many group-code pairs"):
        dxf.import_dxf(_entity("LINE", [(10, 1), (20, 2), (11, 3), (21, 4)]))


@pytest.mark.parametrize("raw_value", ["not-a-number", "NaN", "Infinity", "1e999"])
def test_dxf_rejects_malformed_line_coordinate(raw_value):
    with pytest.raises(dxf.DxfError, match="numeric group"):
        dxf.import_dxf(_entity("LINE", [(10, raw_value), (20, 2), (11, 3), (21, 4)]))


@pytest.mark.parametrize("raw_value", ["abc", "NaN", "Infinity", "1e999"])
def test_dxf_rejects_malformed_polyline_coordinate(raw_value):
    with pytest.raises(dxf.DxfError, match="numeric group"):
        dxf.import_dxf(_entity("LWPOLYLINE", [(10, 0), (20, 0), (10, raw_value), (20, 10)]))


def test_dxf_rejects_invalid_block_base_point():
    data = ("0\nSECTION\n2\nBLOCKS\n0\nBLOCK\n2\nX\n10\nnot-a-number\n"
            "0\nENDBLK\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n0\n"
            "INSERT\n2\nX\n0\nENDSEC\n0\nEOF\n").encode()
    with pytest.raises(dxf.DxfError, match="numeric group 10"):
        dxf.import_dxf(data)


def test_dxf_preserves_valid_line_geometry():
    report = dxf.import_dxf(_entity("LINE", [(10, 0), (20, 0), (11, 10), (21, 0)]))
    assert len(report.shapes) == 1
    assert report.counts == {"LINE": 1}
    assert report.shapes[0].kind == "line"


@pytest.mark.parametrize("scale", [float("nan"), float("inf"), 0])
def test_dxf_rejects_invalid_scale(scale):
    with pytest.raises(dxf.DxfError, match="scale"):
        dxf.import_dxf(_entity("LINE", [(10, 0), (20, 0), (11, 10), (21, 0)]), scale=scale)
