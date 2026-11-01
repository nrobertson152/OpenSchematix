"""Shared pytest configuration for OpenSchematix.

Environment rules
-----------------
* Engine/model tests never import Tk and always run.
* Tests that import ``openschematix.gui`` need the Tk *bindings* installed
  (``python3-tk`` on Debian/Ubuntu; included with official Windows/macOS
  builds). Mark them ``requires_tk``. They do **not** need a display when
  they use ``App.__new__`` or similar headless patterns.
* Tests that create a real ``tk.Tk()`` root or drive the interactive UI
  must be marked ``gui``. Those also need a display (real or Xvfb).
* ``tests/gui_smoke.py`` is a standalone script (not collected by pytest)
  and is run under Xvfb in CI.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Cached probes so collection and fixtures share one result per process.
_TK_IMPORTABLE: bool | None = None
_TK_INIT_OK: bool | None = None


def tkinter_importable() -> bool:
    """True if ``import tkinter`` succeeds in this interpreter."""
    global _TK_IMPORTABLE
    if _TK_IMPORTABLE is None:
        try:
            import tkinter  # noqa: F401
            _TK_IMPORTABLE = True
        except Exception:
            _TK_IMPORTABLE = False
    return _TK_IMPORTABLE


def tk_root_initializable() -> bool:
    """True if a real Tk root can be created (bindings + display/server).

    On failure this records the reason on ``tk_root_initializable.reason``.
    """
    global _TK_INIT_OK
    if _TK_INIT_OK is not None:
        return _TK_INIT_OK
    if not tkinter_importable():
        tk_root_initializable.reason = "tkinter module is not importable"
        _TK_INIT_OK = False
        return False
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        tk_root_initializable.reason = ""
        _TK_INIT_OK = True
    except Exception as e:  # noqa: BLE001 — probe must never crash collection
        tk_root_initializable.reason = f"{type(e).__name__}: {e}"
        _TK_INIT_OK = False
    return _TK_INIT_OK


tk_root_initializable.reason = ""


@pytest.fixture(scope="session")
def require_tk():
    """Skip only when the Tk bindings are missing from this Python."""
    if not tkinter_importable():
        pytest.skip(
            "Tkinter is not importable in this Python (install python3-tk, or use "
            "an official Windows/macOS build). Headless GUI *logic* tests need the "
            "bindings; pure engine tests do not."
        )


@pytest.fixture(scope="session")
def require_gui_display():
    """Skip when a Tk root cannot be initialized (no display / broken Tk)."""
    if not tk_root_initializable():
        pytest.skip(
            "Cannot initialize a Tk root "
            f"({tk_root_initializable.reason or 'unknown'}). "
            "Interactive GUI tests need a display (e.g. xvfb-run on Linux)."
        )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_tk: needs importable tkinter bindings (display optional)",
    )
    config.addinivalue_line(
        "markers",
        "gui: needs a working Tk root / graphical display (real or Xvfb)",
    )


def pytest_collection_modifyitems(config, items):
    """Apply skips for missing Tk bindings or display without blanket-skipping.

    * ``requires_tk`` — skipped only if ``import tkinter`` fails.
    * ``gui`` — skipped only if a Tk root cannot be created.
    When both bindings and display are present (typical CI with python3-tk +
    xvfb-run), no test is skipped for environment reasons.
    """
    skip_tk = None
    skip_gui = None
    if not tkinter_importable():
        skip_tk = pytest.mark.skip(
            reason="tkinter not importable; install python3-tk (Linux) or use an "
            "official Python build. Non-GUI tests still run."
        )
    elif not tk_root_initializable():
        skip_gui = pytest.mark.skip(
            reason="Tk root cannot be initialized "
            f"({tk_root_initializable.reason}). Use xvfb-run on Linux for @pytest.mark.gui tests."
        )
    for item in items:
        if skip_tk is not None and ("requires_tk" in item.keywords or "gui" in item.keywords):
            item.add_marker(skip_tk)
        elif skip_gui is not None and "gui" in item.keywords:
            item.add_marker(skip_gui)


@pytest.fixture(autouse=True)
def isolate_symbol_registry():
    """Prevent process-global symbol registry state from leaking between tests.

    Built-in symbols (``_REGISTRY``) are never cleared. Only the project and
    user layers are saved and restored, matching the production mutators
    ``set_project_symbols`` / ``set_user_symbols``.
    """
    from openschematix import symbols
    user = symbols.user_symbols()
    project = symbols.project_symbols()
    yield
    symbols.set_user_symbols(user.values())
    symbols.set_project_symbols(project.values())
