"""Simulate in FluidWorx: finds the program, never launches on an unsaved file without saying so, and OpenSchematix
behaves as before when FluidWorx isn't there. The GUI part runs under Tk; skipped when no display is available."""
import os
import tempfile

import pytest

from openschematix import commands, fluidworx_link
from openschematix.model import Component
from openschematix.settings import DEFAULTS, Settings


def test_command_is_registered():
    assert commands.resolve("SIM") == "SIMULATE" and commands.resolve("simulate") == "SIMULATE"


def test_setting_defaults_to_automatic(tmp_path):
    assert DEFAULTS["fluidworx_path"] == ""
    assert Settings(str(tmp_path / "s.json"))["fluidworx_path"] == ""


def test_find_order(tmp_path, monkeypatch):
    monkeypatch.delenv(fluidworx_link.ENV_VAR, raising=False)
    monkeypatch.setattr(fluidworx_link.shutil, "which", lambda n: None)
    monkeypatch.setattr(fluidworx_link.importlib.util, "find_spec", lambda n: None)
    assert fluidworx_link.find_fluidworx("") is None
    assert fluidworx_link.find_fluidworx(str(tmp_path / "missing")) is None, "a stale path must not count as found"
    prog = tmp_path / "fw"
    prog.write_text("")
    env_prog = tmp_path / "fw2"
    env_prog.write_text("")
    monkeypatch.setenv(fluidworx_link.ENV_VAR, str(env_prog))
    assert fluidworx_link.find_fluidworx("") == [str(env_prog)]
    assert fluidworx_link.find_fluidworx(str(prog)) == [str(prog)], "the configured path wins"
    monkeypatch.delenv(fluidworx_link.ENV_VAR)
    monkeypatch.setattr(fluidworx_link.shutil, "which", lambda n: "/usr/bin/fluidworx" if n == "fluidworx" else None)
    assert fluidworx_link.find_fluidworx("") == ["/usr/bin/fluidworx"]


def test_python_package_is_only_used_from_source(monkeypatch):
    monkeypatch.delenv(fluidworx_link.ENV_VAR, raising=False)
    monkeypatch.setattr(fluidworx_link.shutil, "which", lambda n: None)
    monkeypatch.setattr(fluidworx_link.importlib.util, "find_spec", lambda n: object())
    assert fluidworx_link.find_fluidworx("")[1:] == ["-m", "fluidworx"]
    monkeypatch.setattr(fluidworx_link.sys, "frozen", True, raising=False)
    assert fluidworx_link.find_fluidworx("") is None


def test_packaged_build_does_not_leak_its_libraries():
    env = {"TCL_LIBRARY": "/x", "TK_LIBRARY": "/y", "LD_LIBRARY_PATH": "/bundle", "LD_LIBRARY_PATH_ORIG": "/orig", "A": "1"}
    out = fluidworx_link.child_environment(env, frozen=True)
    assert out["LD_LIBRARY_PATH"] == "/orig" and "TCL_LIBRARY" not in out and "TK_LIBRARY" not in out
    assert out["PYINSTALLER_RESET_ENVIRONMENT"] == "1" and out["A"] == "1"
    assert "LD_LIBRARY_PATH" not in fluidworx_link.child_environment({"LD_LIBRARY_PATH": "/bundle"}, frozen=True)
    assert fluidworx_link.child_environment(env, frozen=False) == env


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
    a.dirty = False
    a.recovery.end()


@pytest.fixture
def launched(monkeypatch):
    calls = []
    monkeypatch.setattr(fluidworx_link, "find_fluidworx", lambda configured="": ["fw"])
    monkeypatch.setattr(fluidworx_link, "launch", lambda cmd, path: calls.append((cmd, path)))
    return calls


@pytest.fixture
def dialogs(monkeypatch):
    from openschematix.gui import app as m
    seen = {"info": [], "error": [], "answer": None, "ok": True, "yes": False}
    monkeypatch.setattr(m.messagebox, "showinfo", lambda t, msg, **k: seen["info"].append(msg))
    monkeypatch.setattr(m.messagebox, "showerror", lambda t, msg, **k: seen["error"].append(msg))
    monkeypatch.setattr(m.messagebox, "askyesnocancel", lambda *a, **k: seen["answer"])
    monkeypatch.setattr(m.messagebox, "askokcancel", lambda *a, **k: seen["ok"])
    monkeypatch.setattr(m.messagebox, "askyesno", lambda *a, **k: seen["yes"])
    return seen


def _with_pump(app):
    app.doc.components[1] = Component(id=1, symbol="fl.hyd.pump", x=100, y=100, designator="P1")


def _saved(app, tmp_path):
    _with_pump(app)
    p = str(tmp_path / "c.schematix")
    app.filename = p
    assert app.save()
    return p


def test_no_fluid_parts_says_so(app, launched, dialogs):
    app.doc.components[1] = Component(id=1, symbol="el.coil.iec", x=100, y=100)
    assert not app.simulate()
    assert not launched and "no hydraulic or pneumatic" in dialogs["info"][0]


def test_saved_project_opens(app, launched, dialogs, tmp_path):
    p = _saved(app, tmp_path)
    assert app.simulate()
    assert launched == [(["fw"], p)]


def test_typed_command_runs_it(app, launched, dialogs, tmp_path):
    p = _saved(app, tmp_path)
    app.execute_input("SIM")
    assert launched == [(["fw"], p)]


def test_unsaved_changes_cancel_does_nothing(app, launched, dialogs, tmp_path):
    p = _saved(app, tmp_path)
    before = open(p, "rb").read()
    app.dirty = True
    dialogs["answer"] = None
    assert not app.simulate()
    assert not launched and app.dirty and open(p, "rb").read() == before


def test_unsaved_changes_yes_saves_first(app, launched, dialogs, tmp_path):
    p = _saved(app, tmp_path)
    before = open(p, "rb").read()
    app.doc.components[2] = Component(id=2, symbol="fl.hyd.tank", x=100, y=200, designator="Z1")
    app.dirty = True
    dialogs["answer"] = True
    assert app.simulate()
    assert launched and not app.dirty and open(p, "rb").read() != before


def test_unsaved_changes_no_keeps_them_unsaved(app, launched, dialogs, tmp_path):
    p = _saved(app, tmp_path)
    before = open(p, "rb").read()
    app.dirty = True
    dialogs["answer"] = False
    assert app.simulate()
    assert launched and app.dirty and open(p, "rb").read() == before


def test_never_saved_project_must_be_saved_first(app, launched, dialogs, monkeypatch):
    _with_pump(app)
    app.filename = None
    monkeypatch.setattr(app, "save_as", lambda: False)
    assert not app.simulate()
    assert not launched


def test_not_installed_is_only_a_question(app, dialogs, tmp_path, monkeypatch):
    _saved(app, tmp_path)
    monkeypatch.setattr(fluidworx_link, "find_fluidworx", lambda configured="": None)
    started = []
    monkeypatch.setattr(fluidworx_link, "launch", lambda *a: started.append(a))
    assert not app.simulate()
    assert not started and not dialogs["error"]


def test_located_program_is_remembered(app, dialogs, tmp_path, monkeypatch):
    from openschematix.gui import app as m
    p = _saved(app, tmp_path)
    monkeypatch.setattr(fluidworx_link, "find_fluidworx", lambda configured="": None)
    started = []
    monkeypatch.setattr(fluidworx_link, "launch", lambda *a: started.append(a))
    monkeypatch.setattr(m.filedialog, "askopenfilename", lambda **k: "/opt/fw")
    dialogs["yes"] = True
    assert app.simulate()
    assert started == [(["/opt/fw"], p)] and app.settings["fluidworx_path"] == "/opt/fw"


def test_failure_to_start_shows_a_message(app, dialogs, tmp_path, monkeypatch):
    _saved(app, tmp_path)
    monkeypatch.setattr(fluidworx_link, "find_fluidworx", lambda configured="": ["fw"])

    def boom(*a):
        raise OSError("no such program")
    monkeypatch.setattr(fluidworx_link, "launch", boom)
    assert not app.simulate()
    assert "no such program" in dialogs["error"][0]
