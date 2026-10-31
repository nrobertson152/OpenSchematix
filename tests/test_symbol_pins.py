import pytest

from openschematix.geometry import GRID
from openschematix.symbols.base import Geometry, Terminal, validate_geometry
from openschematix.symbols.custom import (
    SymbolFormatError,
    blank_symbol,
    normalise,
    to_symdef,
)


def _symbol_with_pin(x, y, name="1", pid="p1"):
    doc = blank_symbol()
    doc["prims"] = [{"k": "line", "pts": [[0, 0], [10, 0]]}]
    doc["pins"] = [{"id": pid, "name": name, "x": x, "y": y, "dir": "r"}]
    return doc


def test_valid_grid_coordinates():
    # Zero coordinates
    for x, y in [(0, 0), (0.0, 0.0), (-0.0, 0.0), (0.0, -0.0)]:
        doc = _symbol_with_pin(x, y)
        norm = normalise(doc)
        assert norm["pins"][0]["x"] == 0.0
        assert norm["pins"][0]["y"] == 0.0
        sd = to_symdef(doc)
        assert sd.geometry.terminals[0].x == 0.0
        assert sd.geometry.terminals[0].y == 0.0

    # Positive integer and float multiples of GRID (10)
    for coord in [10, 20, 50, 100, 10.0, 20.0, 100.0]:
        doc = _symbol_with_pin(coord, coord)
        norm = normalise(doc)
        assert norm["pins"][0]["x"] == float(coord)
        assert norm["pins"][0]["y"] == float(coord)
        sd = to_symdef(doc)
        assert sd.geometry.terminals[0].x == float(coord)
        assert sd.geometry.terminals[0].y == float(coord)


def test_invalid_grid_coordinates():
    # Off-grid values in X or Y
    invalid_coords = [
        (15, 0),
        (0, 15),
        (2.5, 0),
        (0, 2.5),
        (5, 0),
        (0, 5),
        (1, 0),
        (0, 1),
        (0.1, 0),
        (0, 0.1),
        (10.5, 20),
        (20, 10.5),
    ]
    for x, y in invalid_coords:
        doc = _symbol_with_pin(x, y)
        with pytest.raises(SymbolFormatError, match=f"not on the {GRID}-unit grid"):
            normalise(doc)


def test_negative_coordinates():
    # Valid negative coordinates (multiples of GRID)
    valid_negatives = [
        (-10, 0),
        (0, -10),
        (-10.0, 0.0),
        (-20, -30),
        (-100, 100),
    ]
    for x, y in valid_negatives:
        doc = _symbol_with_pin(x, y)
        norm = normalise(doc)
        assert norm["pins"][0]["x"] == float(x)
        assert norm["pins"][0]["y"] == float(y)
        sd = to_symdef(doc)
        assert sd.geometry.terminals[0].x == float(x)
        assert sd.geometry.terminals[0].y == float(y)

    # Invalid negative coordinates (off-grid)
    invalid_negatives = [
        (-15, 0),
        (0, -15),
        (-2.5, 0),
        (0, -5),
        (-10.5, 0),
        (0, -10.5),
        (-0.1, 0),
        (-10, -5),
    ]
    for x, y in invalid_negatives:
        doc = _symbol_with_pin(x, y)
        with pytest.raises(SymbolFormatError, match=f"not on the {GRID}-unit grid"):
            normalise(doc)


def test_floating_point_precision_edge_cases():
    # Within floating-point tolerance (1e-6 normalized to GRID, i.e., 1e-5 in coordinate space)
    # 1e-8 delta is well within tolerance (1e-8 / 10 = 1e-9 <= 1e-6)
    tolerable_deltas = [1e-8, -1e-8, 1e-7, -1e-7]
    for base in [0.0, 10.0, -10.0, 100.0, -100.0]:
        for delta in tolerable_deltas:
            x = base + delta
            doc = _symbol_with_pin(x, base)
            norm = normalise(doc)
            assert norm["pins"][0]["x"] == x
            sd = to_symdef(doc)
            assert sd.geometry.terminals[0].x == x

    # Outside tolerance (e.g. 1e-4 delta gives 1e-5 > 1e-6)
    intolerable_deltas = [1e-4, -1e-4, 1e-3, -1e-3, 0.01, -0.01]
    for base in [0.0, 10.0, -10.0, 50.0, -50.0]:
        for delta in intolerable_deltas:
            x = base + delta
            doc = _symbol_with_pin(x, base)
            with pytest.raises(SymbolFormatError, match=f"not on the {GRID}-unit grid"):
                normalise(doc)


def test_validate_geometry_grid_validation():
    # Test Geometry directly with validate_geometry
    # Valid terminals on grid
    geom_valid = Geometry(
        prims=[{"k": "line", "pts": [(0, 0), (10, 0)]}],
        terminals=[
            Terminal(name="t1", x=0.0, y=0.0),
            Terminal(name="t2", x=10.0, y=-20.0),
            Terminal(name="t3", x=-30.0, y=40.0),
            Terminal(name="t4", x=10.0 + 1e-8, y=20.0 - 1e-8),
        ],
    )
    assert validate_geometry(geom_valid) == []

    # Invalid terminals off grid
    geom_invalid = Geometry(
        prims=[{"k": "line", "pts": [(0, 0), (10, 0)]}],
        terminals=[
            Terminal(name="off_x", x=15.0, y=0.0),
            Terminal(name="off_y", x=0.0, y=-2.5),
            Terminal(name="off_tol", x=10.0 + 1e-4, y=0.0),
        ],
    )
    problems = validate_geometry(geom_invalid)
    assert len(problems) == 3
    assert "terminal off_x off grid at (15.0, 0.0)" in problems[0]
    assert "terminal off_y off grid at (0.0, -2.5)" in problems[1]
    assert "terminal off_tol off grid" in problems[2]
