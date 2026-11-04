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


@pytest.mark.parametrize("raw_value", ["abc", "NaN", "Infinity", "1e999"])
def test_dxf_rejects_invalid_spline_control_coordinates(raw_value):
    data = _entity("SPLINE", [(10, raw_value), (20, 0), (10, 1), (20, 1)])
    with pytest.raises(dxf.DxfError, match="numeric group 10"):
        dxf.import_dxf(data)


@pytest.mark.parametrize("origin", [("abc", 0), (float("nan"), 0), (float("inf"), 0), (0,), None])
def test_dxf_rejects_invalid_origin_with_dxf_error(origin):
    data = _entity("LINE", [(10, 0), (20, 0), (11, 10), (21, 0)])
    with pytest.raises(dxf.DxfError, match="origin|numeric"):
        dxf.import_dxf(data, origin=origin)


def test_dxf_coerces_numeric_string_origin_and_scale():
    data = _entity("LINE", [(10, 0), (20, 0), (11, 10), (21, 0)])
    report = dxf.import_dxf(data, scale="1", origin=("5", "7"))
    assert len(report.shapes) == 1
    assert all(math.isfinite(v) for pt in report.shapes[0].pts for v in pt)


def test_dxf_rejects_extreme_ellipse_sweep_before_allocating_points():
    data = _entity("ELLIPSE", [(10, 0), (20, 0), (11, 10), (21, 0),
                                   (40, 0.5), (41, 0), (42, "1e300")])
    with pytest.raises(dxf.DxfError, match="ELLIPSE parameter sweep"):
        dxf.import_dxf(data)


def test_dxf_rejects_transformed_coordinate_overflow():
    data = _entity("LINE", [(10, "1e300"), (20, 0), (11, 0), (21, 0)])
    with pytest.raises(dxf.DxfError, match="finite coordinate range"):
        dxf.import_dxf(data, scale="1e300")


@pytest.mark.parametrize("kind,fields", [
    ("CIRCLE", [(10, 0), (20, 0), (40, "1e308")]),
    ("ARC", [(10, 0), (20, 0), (40, "1e308"), (50, 0), (51, 90)]),
    ("TEXT", [(10, 0), (20, 0), (40, "1e308"), (1, "X")]),
    ("MTEXT", [(10, 0), (20, 0), (40, "1e308"), (1, "X")]),
])
def test_dxf_rejects_nonfinite_derived_size(kind, fields):
    with pytest.raises(dxf.DxfError, match="finite range"):
        dxf.import_dxf(_entity(kind, fields))


def test_dxf_rejects_mtext_output_shape_amplification():
    data = _entity("MTEXT", [(10, 0), (20, 0), (40, 2.5),
                              (1, r"X\PX\PX\PX\PX\PX")])
    with pytest.raises(dxf.DxfError, match="emits more than 3 shapes"):
        dxf.import_dxf(data, max_entities=3)


def test_dxf_accepts_mtext_below_output_budget():
    data = _entity("MTEXT", [(10, 0), (20, 0), (40, 2.5), (1, r"X\PY")])
    assert len(dxf.import_dxf(data, max_entities=2).shapes) == 2


@pytest.mark.parametrize("attachment", [1, 7])
def test_dxf_rejects_mtext_nonfinite_line_spacing(attachment):
    data = _entity("MTEXT", [(10, 0), (20, 0), (40, "3e307"),
                              (71, attachment), (1, r"First\PSecond")])
    with pytest.raises(dxf.DxfError, match="finite range"):
        dxf.import_dxf(data)


def test_dxf_rejects_mtext_nonfinite_derived_line_position():
    data = _entity("MTEXT", [(10, "1e308"), (20, 0), (40, "1e307"),
                              (71, 1), (1, r"First\PSecond")])
    with pytest.raises(dxf.DxfError, match="finite range|finite coordinate range"):
        dxf.import_dxf(data)


@pytest.mark.parametrize("units", ["invalid", 42, [], {}])
def test_dxf_rejects_invalid_units_override_with_dxf_error(units):
    data = _entity("LINE", [(10, 0), (20, 0), (11, 1), (21, 1)])
    with pytest.raises(dxf.DxfError, match="units override"):
        dxf.import_dxf(data, units=units)


@pytest.mark.parametrize("bulge", ["1", "1e308"])
def test_dxf_rejects_extreme_polyline_bulge_geometry(bulge):
    data = _entity("LWPOLYLINE", [(10, "-1e308"), (20, 0), (42, bulge),
                                    (10, "1e308"), (20, 0)])
    with pytest.raises(dxf.DxfError, match="finite range"):
        dxf.import_dxf(data)
