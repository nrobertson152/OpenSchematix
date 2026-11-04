"""The recent-files menu must not touch the file system (#75).

It is rebuilt on the UI thread after every save and open. On Windows a
stat() of a recent file on a disconnected network drive or share can block
for many seconds, which freezes the window just after saving. The menu now
lists the recent files as recorded; a file that has gone is reported when
it is chosen, and dropped from the list if its folder is still there. Runs under Tk; skipped when no
display is available.
"""
import os
import tempfile

import pytest


@pytest.fixture(scope="module")
def tk_root():
    os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", tempfile.mkdtemp())
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Tk GUI display not available: {e}")
    yield root
    root.destroy()


@pytest.fixture
def app(tk_root, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSCHEMATIX_CONFIG_DIR", str(tmp_path / "config"))
    from openschematix.gui.app import App
    a = App(tk_root, check_recovery=False)
    yield a
    a.recovery.end()


@pytest.fixture
def errors(monkeypatch):
    from openschematix.gui import app as app_mod
    shown = []
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda title, message, **k: shown.append((title, message)))
    return shown


def _labels(menu):
    end = menu.index("end")
    return [] if end is None else [menu.entrycget(i, "label") for i in range(end + 1)]


def _no_stat(monkeypatch):
    calls = []

    def recorder(fn):
        def wrapped(p, *a, **k):
            calls.append(str(p))
            return fn(p, *a, **k)
        return wrapped
    for name in ("exists", "isfile", "getsize", "getmtime"):
        monkeypatch.setattr(os.path, name, recorder(getattr(os.path, name)))
    monkeypatch.setattr(os, "stat", recorder(os.stat))
    return calls


def test_rebuilding_the_menu_does_not_stat_the_recent_files(app, tmp_path, monkeypatch):
    unreachable = os.path.abspath(str(tmp_path / "offline-share" / "plant.schematix"))
    app.settings["recent_files"] = [unreachable]
    calls = _no_stat(monkeypatch)
    app._rebuild_recent()
    assert unreachable not in calls
    assert _labels(app.recent_menu) == [unreachable]


def test_saving_does_not_stat_other_recent_files(app, tmp_path, monkeypatch):
    other = os.path.abspath(str(tmp_path / "offline-share" / "plant.schematix"))
    app.settings["recent_files"] = [other]
    app.filename = str(tmp_path / "current.schematix")
    calls = _no_stat(monkeypatch)
    assert app.save()
    assert other not in calls
    assert _labels(app.recent_menu) == [os.path.abspath(app.filename), other]


def test_choosing_a_recent_file_that_has_gone_reports_it_and_drops_it(app, tmp_path, errors):
    gone = os.path.abspath(str(tmp_path / "gone.schematix"))
    kept = os.path.abspath(str(tmp_path / "kept.schematix"))
    app.settings["recent_files"] = [gone, kept]
    app._rebuild_recent()
    app.open_path(gone, confirm=False)
    assert errors and errors[0][0] == "Could not open" and gone in errors[0][1]
    assert app.settings["recent_files"] == [kept]
    assert _labels(app.recent_menu) == [kept]


def test_a_recent_file_on_an_unavailable_drive_stays_in_the_list(app, tmp_path, errors):
    """Its folder cannot be reached either (an offline share or a removed
    drive, which Windows reports as "not found"): keep it for later."""
    offline = os.path.abspath(str(tmp_path / "offline-share" / "plant.schematix"))
    app.settings["recent_files"] = [offline]
    app.open_path(offline, confirm=False)
    assert errors and errors[0][0] == "Could not open"
    assert app.settings["recent_files"] == [offline]


def test_a_recent_file_that_cannot_be_read_stays_in_the_list(app, tmp_path, errors):
    """Only a file that no longer exists is dropped: a damaged one, or one on
    a drive that is back later, is not silently forgotten for other errors."""
    bad = tmp_path / "damaged.schematix"
    bad.write_bytes(b"not a project")
    app.settings["recent_files"] = [os.path.abspath(str(bad))]
    app.open_path(str(bad), confirm=False)
    assert errors and errors[0][0] == "Could not open"
    assert app.settings["recent_files"] == [os.path.abspath(str(bad))]


def test_the_empty_list_still_shows_none(app):
    app.settings["recent_files"] = []
    app._rebuild_recent()
    assert _labels(app.recent_menu) == ["(none)"]
