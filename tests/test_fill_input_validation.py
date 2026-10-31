"""Regression tests for malformed boundary-fill ring input."""

import pytest

from openschematix.regions import clean_rings


@pytest.mark.parametrize("bad", [None, {}, [], "invalid", object(), 10**1000])
@pytest.mark.parametrize("coordinate", [0, 1, 2])
def test_invalid_vertex_numeric_types_raise_value_error(bad, coordinate):
    vertex = [1.0, 2.0, 0.0]
    vertex[coordinate] = bad
    with pytest.raises(ValueError, match="fill vertex values"):
        clean_rings([[vertex, [3.0, 4.0, 0.5]]])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("coordinate", [0, 1, 2])
def test_nonfinite_vertex_values_rejected(bad, coordinate):
    vertex = [1.0, 2.0, 0.0]
    vertex[coordinate] = bad
    with pytest.raises(ValueError, match="fill vertex values out of range"):
        clean_rings([[vertex, [3.0, 4.0, 0.5]]])


@pytest.mark.parametrize("coordinate", [0, 1, 2])
def test_boolean_vertex_values_rejected(coordinate):
    vertex = [1.0, 2.0, 0.0]
    vertex[coordinate] = True
    with pytest.raises(ValueError, match="fill vertex values must be numbers"):
        clean_rings([[vertex, [3.0, 4.0, 0.5]]])


def test_valid_two_arc_ring_still_loads():
    assert clean_rings([[[0, 0, 1], [10, 0, 1]]]) == [[(0.0, 0.0, 1.0), (10.0, 0.0, 1.0)]]
