import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _isolated_symbol_registry():
    """Each test starts from, and leaves behind, the same project and user symbol registries.

    The registry is process-wide state (openschematix.symbols); without this, symbols registered by one
    test stay visible to the next one and can hide load-order bugs (see tests/test_custom_symbol_refs.py)."""
    from openschematix import symbols
    saved_project, saved_user = dict(symbols._PROJECT), dict(symbols._USER)
    yield
    symbols._PROJECT.clear()
    symbols._PROJECT.update(saved_project)
    symbols._USER.clear()
    symbols._USER.update(saved_user)
    symbols._geometry_cached.cache_clear()
