"""Process-global symbol registry must not leak between tests."""
from openschematix import symbols
from openschematix.symbols.base import Geometry, SymbolDef, Terminal


def _probe(suffix: str) -> SymbolDef:
    terminals = [Terminal("1", 0.0, 0.0), Terminal("2", 20.0, 0.0)]
    return SymbolDef(
        id=f"user:registry-isolation-{suffix}",
        name=f"Isolation {suffix}",
        category="General",
        group="Test",
        convention="",
        description="ci isolation probe",
        prefix="X",
        geometry=Geometry(prims=[], terminals=terminals),
        custom={"revision": 1},
    )


def test_project_symbols_do_not_leak_to_next_test_part_a():
    sym = _probe("a")
    symbols.set_project_symbols([sym])
    assert sym.id in symbols.project_symbols()
    assert symbols.get(sym.id) is not None


def test_project_symbols_do_not_leak_to_next_test_part_b():
    # Runs after part_a; autouse fixture must have cleared the probe.
    assert "user:registry-isolation-a" not in symbols.project_symbols()
    assert "user:registry-isolation-a" not in symbols.user_symbols()
    assert symbols.get("user:registry-isolation-a") is None


def test_user_symbols_do_not_leak_to_next_test_part_a():
    sym = _probe("user-a")
    symbols.set_user_symbols([sym])
    assert sym.id in symbols.user_symbols()


def test_user_symbols_do_not_leak_to_next_test_part_b():
    assert "user:registry-isolation-user-a" not in symbols.user_symbols()
    assert symbols.get("user:registry-isolation-user-a") is None
