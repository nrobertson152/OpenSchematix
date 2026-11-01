"""Unexpected errors in the GUI are logged and shown (audit F2), and a
project that fails to open leaves the open project untouched.

The packaged Windows application has no console: sys.stdout and sys.stderr
are None there, which these tests reproduce. Runs under Tk; skipped when no
display is available.
"""
import io
import json
import os
import sys
import tempfile
import zipfile

import pytest

from openschematix import editing, projectio, symbols

SECRET = "TOP-SECRET-CLIENT-NAME"


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
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSCHEMATIX_CONFIG_DIR", str(tmp_path / "config"))
    return tmp_path / "config"


@pytest.fixture
def dialogs(monkeypatch):
    from tkinter import messagebox
    shown = []
    monkeypatch.setattr(messagebox, "showerror", lambda title, message, **k: shown.append((title, message)))
    return shown


@pytest.fixture
def windowed(monkeypatch):
    """No console, as in the windowed Windows build."""
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "stdout", None)


@pytest.fixture
def reporter(tk_root, monkeypatch):
    from openschematix.gui import errors
    saved = sys.excepthook
    r = errors.install(tk_root)
    yield r
    sys.excepthook = saved
    try:
        del tk_root.report_callback_exception          # back to Tk's default
    except AttributeError:
        pass


def fail_in_callback(root, exc):
    def boom():
        raise exc
    root.after(0, boom)
    root.update()


def read_log(config):
    from openschematix.gui import errors
    with open(os.path.join(str(config), "logs", errors.LOG_NAME), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- error reporting
def test_callback_errors_are_shown_and_logged_without_a_console(tk_root, config, dialogs, windowed, reporter):
    fail_in_callback(tk_root, ValueError(f"cannot parse {SECRET}"))
    assert reporter.reported == 1 and len(dialogs) == 1
    title, message = dialogs[0]
    log = read_log(config)
    assert title == "Unexpected error" and "ValueError" in message
    assert os.path.join("logs", "openschematix-errors.log") in message
    assert SECRET not in message                        # file content stays out of the dialog
    assert "Traceback" in log and "ValueError: cannot parse" in log and "boom" in log


def test_repeated_errors_show_one_dialog_but_are_all_logged(tk_root, config, dialogs, windowed, reporter):
    for _ in range(5):
        fail_in_callback(tk_root, RuntimeError("redraw failed"))
    fail_in_callback(tk_root, KeyError("other"))
    assert reporter.reported == 6
    assert [m.split("(")[1].split(")")[0] for _t, m in dialogs] == ["RuntimeError", "KeyError"]
    assert read_log(config).count("Traceback") == 6


def test_console_still_gets_the_traceback(tk_root, config, dialogs, reporter, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    fail_in_callback(tk_root, ZeroDivisionError("x"))
    assert "ZeroDivisionError" in buf.getvalue() and len(dialogs) == 1


def test_unwritable_log_still_shows_the_dialog(tk_root, tmp_path, dialogs, windowed, reporter, monkeypatch):
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    monkeypatch.setenv("OPENSCHEMATIX_CONFIG_DIR", str(blocker))
    fail_in_callback(tk_root, OSError("disk"))
    assert len(dialogs) == 1 and "could not be saved to the error log" in dialogs[0][1]


def test_error_while_showing_the_dialog_does_not_recurse(tk_root, config, windowed, reporter, monkeypatch):
    from tkinter import messagebox

    def broken(*a, **k):
        raise RuntimeError("Tk is gone")
    monkeypatch.setattr(messagebox, "showerror", broken)
    fail_in_callback(tk_root, ValueError("first"))
    assert reporter.reported == 1 and "ValueError: first" in read_log(config)


def test_uncaught_main_thread_errors_use_the_same_reporter(tk_root, config, dialogs, windowed, reporter):
    try:
        raise LookupError("outside Tk")
    except LookupError:
        sys.excepthook(*sys.exc_info())
    assert len(dialogs) == 1 and "LookupError" in dialogs[0][1] and "[uncaught]" in read_log(config)


def test_start_up_failure_is_reported_and_exits_nonzero(config, dialogs, windowed, monkeypatch, tk_root):
    from openschematix.gui import app as app_mod

    class Broken:
        def __init__(self, *a, **k):
            raise RuntimeError(f"settings unreadable: {SECRET}")
    monkeypatch.setattr(app_mod, "App", Broken)
    saved = sys.excepthook
    try:
        assert app_mod.main([]) == 1
    finally:
        sys.excepthook = saved
    assert dialogs and dialogs[-1][0] == "OpenSchematix could not start" and SECRET not in dialogs[-1][1]
    assert "[start-up]" in read_log(config) and SECRET in read_log(config)


# ---------------------------------------------------------------- opening files in the application
@pytest.fixture(scope="module")
def app(tk_root):
    from openschematix.gui.app import App
    return App(tk_root, check_recovery=False)


@pytest.fixture
def app_dialogs(monkeypatch):
    from openschematix.gui import app as app_mod
    shown = []
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda title, message, **k: shown.append((title, message)))
    return shown


def open_project_with_symbol(app, tmp_path):
    from openschematix.project import new_project
    from openschematix.symbols.custom import blank_symbol, normalise, to_symdef
    d = blank_symbol("Sensor")
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "A", "name": "A", "x": -20, "y": 0, "dir": "l"}]
    sdoc = normalise(d)
    symbols.add_project_symbol(to_symdef(sdoc))
    p = new_project("Open one")
    editing.place(p.sheets[0], sdoc["id"], 100, 100)
    path = str(tmp_path / "open.schematix")
    projectio.save_project(p, path)
    app.open_path(path, confirm=False)
    return path, sdoc["id"]


def state(app):
    return (app.project, app.filename, app.dirty, json.dumps([d.to_dict() for d in app.project.sheets]),
            sorted(symbols.project_symbols()))


def damaged_copy(path, out):
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    sheet = next(n for n in files if n.startswith("sheets/"))
    files[sheet] = files[sheet].replace(b'"x":', b'"x": NaN, "_x":', 1)
    with zipfile.ZipFile(out, "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
    return str(out)


def test_failed_open_leaves_the_open_project_untouched(app, app_dialogs, tmp_path, config):
    path, sid = open_project_with_symbol(app, tmp_path)
    before = state(app)
    assert sid in before[4]
    app.open_path(damaged_copy(path, tmp_path / "bad.schematix"), confirm=False)
    assert state(app) == before
    assert len(app_dialogs) == 1 and app_dialogs[0][0] == "Could not open" and "NaN" in app_dialogs[0][1]


def test_unexpected_error_while_opening_is_reported_and_changes_nothing(app, tk_root, tmp_path, config, dialogs,
                                                                      windowed, reporter, monkeypatch):
    open_project_with_symbol(app, tmp_path)
    before = state(app)

    def bug(path):
        raise TypeError("a bug in the loader")
    monkeypatch.setattr(projectio, "open_any", bug)
    tk_root.after(0, lambda: app.open_path(str(tmp_path / "any.schematix"), confirm=False))
    tk_root.update()
    assert state(app) == before
    assert len(dialogs) == 1 and "TypeError" in dialogs[0][1]
    assert "a bug in the loader" in read_log(config)


def test_project_with_damaged_history_must_be_saved_under_a_new_name(app, app_dialogs, tmp_path, config,
                                                                    monkeypatch):
    from openschematix.gui import app as app_mod
    path, _sid = open_project_with_symbol(app, tmp_path)
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    obj = next(n for n in files if n.startswith("revisions/objects/"))
    files[obj] = b"garbage"
    damaged = tmp_path / "damaged.schematix"
    with zipfile.ZipFile(damaged, "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
    original = damaged.read_bytes()
    app.open_path(str(damaged), confirm=False)
    assert app.filename is None and app.dirty and not app_dialogs
    target = tmp_path / "rescued.schematix"
    monkeypatch.setattr(app_mod.filedialog, "asksaveasfilename", lambda **k: str(target))
    assert app.save()
    assert damaged.read_bytes() == original and app.filename == str(target)
    assert projectio.open_any(str(target)).project.sheets[0].components


def test_save_failure_from_a_non_finite_value_is_shown(app, app_dialogs, tmp_path, config):
    open_project_with_symbol(app, tmp_path)
    original = open(app.filename, "rb").read()
    next(iter(app.project.sheets[0].components.values())).x = float("inf")
    assert app.save() is False
    assert app_dialogs and app_dialogs[-1][0] == "Save failed" and "not a finite number" in app_dialogs[-1][1]
    assert open(app.filename, "rb").read() == original
