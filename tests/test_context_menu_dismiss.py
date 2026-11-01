"""Regression tests for native Tk context-menu dismissal (PR #68).

Tk owns the popup's grab: Escape/outside-click must unpost the popup
without ever invoking the application's drawing-command Escape handler.
Tests that actually map native menus require a display (Xvfb on Linux).
"""
import os
import sys
import tempfile
import tkinter as tk
from types import SimpleNamespace

import pytest

from openschematix import editing

pytestmark = pytest.mark.gui


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", tempfile.mkdtemp())
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No Tk display: {exc}")
    from openschematix.gui.app import App
    instance = App(root, check_recovery=False)
    root.deiconify()
    root.update()
    root.focus_force()
    root.update()
    yield instance
    root.destroy()


@pytest.fixture
def capture_menus(app, monkeypatch):
    from openschematix.gui import app as app_module
    original = app_module.make_menu
    menus = []

    def tracked(parent, *args, **kwargs):
        menu = original(parent, *args, **kwargs)
        menus.append(menu)
        return menu

    monkeypatch.setattr(app_module, "make_menu", tracked)
    # Native Tk menus are global: do not leave a posted menu between tests.
    yield menus
    try:
        if menus:
            app.root.tk.call("tk::MenuEscape", str(menus[0]))
        app.root.update()
    except tk.TclError:
        pass
    # Direct Menu.invoke() in tests bypasses Tk's mouse-release class
    # binding, so clean up an artificial leftover grab after unposting.
    try:
        grabbed = app.root.grab_current()
        if grabbed is not None:
            grabbed.grab_release()
    except tk.TclError:
        pass
    for menu in reversed(menus):
        try:
            menu.destroy()
        except tk.TclError:
            pass


def popup(app):
    app.show_context_menu(app.root.winfo_rootx() + 120,
                          app.root.winfo_rooty() + 120)
    app.root.update()


@pytest.mark.skipif(sys.platform == "win32", reason="Native Win32 popup mapping is managed by the OS")
def test_escape_unposts_without_cancelling_the_active_cad_command(app, capture_menus, monkeypatch):
    cancelled = []
    monkeypatch.setattr(app.canvas, "escape", lambda: cancelled.append(True))
    before_escape = app.root.bind("<Escape>")
    app.root.focus_force()
    app.root.update()
    popup(app)
    menu = capture_menus[-1]
    assert menu.winfo_ismapped()
    assert app.root.grab_current() == menu

    # Deliver a Tk key event to the focused native menu, exercising the
    # Menu class Escape binding rather than a private application callback.
    assert str(app.root.tk.call("focus")) == str(menu)
    menu.event_generate("<Escape>")
    app.root.update()
    assert not menu.winfo_ismapped()
    assert app.root.grab_current() is None
    assert cancelled == []
    assert app.root.bind("<Escape>") == before_escape


@pytest.mark.skipif(sys.platform == "win32", reason="X11 native menu grab introspection")
def test_repeated_menu_post_and_dismiss_does_not_leak_grabs_or_root_bindings(app, capture_menus):
    original_escape = app.root.bind("<Escape>")
    original_click = app.root.bind("<ButtonPress>")
    app.root.focus_force()
    app.root.update()
    for _ in range(5):
        popup(app)
        menu = capture_menus[-1]
        assert menu.winfo_ismapped()
        assert app.root.grab_current() == menu
        # The native Menu class Escape handler performs both unposting
        # and proper grab release (unpost alone need not release grabs).
        menu.event_generate("<Escape>")
        app.root.update()
        assert not menu.winfo_ismapped()
        assert app.root.grab_current() is None
        assert app.root.bind("<Escape>") == original_escape
        assert app.root.bind("<ButtonPress>") == original_click


def test_regular_menu_commands_remain_callable(app, capture_menus, monkeypatch):
    invoked = []
    monkeypatch.setattr(app, "select_all", lambda: invoked.append("select"))
    before_escape = app.root.bind("<Escape>")
    before_click = app.root.bind("<ButtonPress>")
    popup(app)
    menu = capture_menus[-1]
    labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
              if menu.type(i) == "command"]
    index = next(i for i in range(menu.index("end") + 1)
                 if menu.type(i) == "command" and menu.entrycget(i, "label") == "Select all")
    assert "Select all" in labels
    menu.invoke(index)
    assert invoked == ["select"]
    app.root.tk.call("tk::MenuEscape", str(menu))
    app.root.update()
    assert app.root.bind("<Escape>") == before_escape
    assert app.root.bind("<ButtonPress>") == before_click


def test_align_submenu_commands_and_disabled_items_survive(app, capture_menus, monkeypatch):
    doc = app.doc
    placed = [editing.place(doc, "el.resistor.iec", 100 + i * 100, 100) for i in range(2)]
    old_selection = set(app.selection)
    called = []
    monkeypatch.setattr(app, "align", lambda mode: called.append(mode))
    try:
        app.selection = {c.id for c in placed}
        popup(app)
        main_menu = capture_menus[0]
        cascades = [i for i in range(main_menu.index("end") + 1)
                    if main_menu.type(i) == "cascade" and main_menu.entrycget(i, "label") == "Align"]
        assert len(cascades) == 1
        submenu = main_menu.nametowidget(main_menu.entrycget(cascades[0], "menu"))
        submenu.invoke(0)
        assert called == [editing.ALIGN_MODES[0]]
    finally:
        app.root.tk.call("tk::MenuEscape", str(main_menu))
        app.root.update()
        app.selection = old_selection
        for c in placed:
            doc.components.pop(c.id, None)


def test_failed_popup_does_not_install_global_bindings(app, capture_menus, monkeypatch):
    from openschematix.gui import app as app_module
    before = {key: app.root.bind(key) for key in ("<Escape>", "<ButtonPress>")}
    orig = app_module.make_menu

    def failing(parent, *args, **kwargs):
        menu = orig(parent, *args, **kwargs)
        def fail(*_a):
            raise tk.TclError("simulated popup failure")
        monkeypatch.setattr(menu, "tk_popup", fail)
        return menu

    monkeypatch.setattr(app_module, "make_menu", failing)
    with pytest.raises(tk.TclError, match="simulated popup failure"):
        popup(app)
    assert {key: app.root.bind(key) for key in before} == before
    assert app.root.grab_current() is None


def test_sheet_tab_context_menu_uses_same_native_popup_semantics(app, capture_menus):
    app.root.focus_force()
    app.root.update()
    before_escape = app.root.bind("<Escape>")
    uid = app.doc.uid
    event = SimpleNamespace(x_root=app.root.winfo_rootx() + 80,
                            y_root=app.root.winfo_rooty() + 80)
    app._tab_menu(event, uid)
    app.root.update()
    menu = capture_menus[-1]
    assert menu.entrycget(0, "label") == "Rename…"
    app.root.tk.call("tk::MenuEscape", str(menu))
    app.root.update()
    assert app.root.bind("<Escape>") == before_escape
