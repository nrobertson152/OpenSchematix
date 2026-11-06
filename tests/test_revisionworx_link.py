"""RevisionWorx, through its real command line: whether a project is controlled, checking it out and in, someone else's check-out, putting
a project under revision control, and the bill of materials reaching OpenMeridian as a released BOM. These run the real programs when they
can be found and skip otherwise; CI installs them. The window's part runs under Tk, and is skipped without a display."""
import csv
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from openschematix import bom, editing, projectio, revisionworx_link as rl
from openschematix.project import new_project

FOUND = rl.find_revisionworx()
needs_rwx = pytest.mark.skipif(FOUND is None, reason="RevisionWorx isn't installed")


@pytest.fixture(autouse=True)
def private_revisionworx(tmp_path, monkeypatch):
    """RevisionWorx keeps its workspaces list and check-outs per user: here, a test's own folders, never the real ones."""
    for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.setenv(var, str(tmp_path / "user" / var.lower()))
    monkeypatch.delenv("REVISIONWORX_WORKSPACE", raising=False)


def run(*args, env=None):
    r = subprocess.run([*FOUND, *[str(a) for a in args]], capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def panel():
    """Two relays K1 and K2 (Finder 40.52), a fuse F1 with a part number, and a resistor without one."""
    p = new_project()
    d = p.sheets[0]
    for i, des in enumerate(("K1", "K2")):
        c = editing.place(d, "el.coil.iec", 100 + 120 * i, 100)
        c.designator = des
        c.props.update(manufacturer="Finder", part_number="40.52.9.024", description="Relay 24 V DC")
    f = editing.place(d, "el.fuse.iec", 400, 100)
    f.designator = "F1"
    f.props.update(manufacturer="Littelfuse", part_number="0213002.MXP", description="Fuse 2 A")
    editing.place(d, "el.resistor.iec", 500, 100)
    return p


def workspace(tmp_path):
    eng = tmp_path / "eng"
    run("init", eng, "--name", "Engineering")
    (eng / "Projects").mkdir()
    run("-w", eng, "root", "add", "Projects", eng / "Projects")
    project = json.loads(run("-w", eng, "--json", "project", "new", "--name", "Press", "--number", "J-3001"))
    rwx = rl.RevisionWorx()
    assert rwx.available()
    folder = Path(next(p["folder"] for p in rwx.projects(str(eng)) if p["id"] == project["id"]))
    return eng, project["id"], folder, rwx


def controlled(ws, project=None):
    eng, project_id, folder, rwx = ws
    f = folder / "04 Schematics" / "panel.schematix"
    projectio.save_project(project or panel(), str(f))
    answer = rwx.publish(f, project_id, "E-100", "Press panel", "First issue")
    assert answer["result"] == "created" and Path(answer["document"]["path"]) == f
    return f


def elsewhere(tmp_path):
    env = dict(os.environ)
    for var in ("XDG_STATE_HOME", "LOCALAPPDATA"):
        env[var] = str(tmp_path / "someone-else")
    return env


# ---------------------------------------------------------------------------------------------------------- finding it

def test_find_order(tmp_path, monkeypatch):
    monkeypatch.delenv(rl.ENV_VAR, raising=False)
    monkeypatch.setattr(rl.shutil, "which", lambda n: None)
    monkeypatch.setattr(rl, "_standalone", lambda: [])
    monkeypatch.setattr(rl.importlib.util, "find_spec", lambda n: None)
    assert rl.find_revisionworx() is None and not rl.RevisionWorx().available()
    monkeypatch.setenv(rl.ENV_VAR, "/opt/rwx/revisionworx")
    assert rl.find_revisionworx() == ["/opt/rwx/revisionworx"]
    monkeypatch.delenv(rl.ENV_VAR)
    monkeypatch.setattr(rl.shutil, "which", lambda n: "/usr/bin/revisionworx" if n == "revisionworx" else None)
    assert rl.find_revisionworx() == ["/usr/bin/revisionworx"]


def test_a_command_that_isnt_there_is_said_and_isnt_available(tmp_path):
    rwx = rl.RevisionWorx([str(tmp_path / "missing")])
    assert not rwx.available()
    with pytest.raises(rl.RevisionWorxError) as e:
        rwx.status(tmp_path / "x.schematix")
    assert e.value.kind == "unavailable"


def test_reading_an_answer_it_doesnt_know_all_of():
    s = rl.Status.of({"ok": True, "controlled": True, "document": {"number": "E-1", "checkout": {"user": "alex", "host": "PC", "mine": False},
                                                                   "latest": {"label": "C", "state_name": "Released"}, "new": 1},
                      "file": {"state": "unchanged"}, "workspace": {"location": "/w"}})
    assert s.theirs and s.sentence() == "E-1 rev C · Released · checked out by alex on PC" and s.primary() == ""


# ------------------------------------------------------------------------------------------------------ the BOM it writes

def test_the_bom_is_one_revisionworx_reads():
    data, left_out = rl.bom_csv(bom.generate(panel()), "E-100", "Press panel", "B")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    assert tuple(rows[0]) == rl.COLUMNS and left_out == 1         # the resistor has no part number
    assert rows[1][2] == "E-100" and rows[1][3] == "B" and sorted(r[2] for r in rows[2:4]) == ["0213002.MXP", "40.52.9.024"]
    assert sorted((r[2], r[4], r[6]) for r in rows[4:]) == [("0213002.MXP", "1", "F1"), ("40.52.9.024", "2", "K1 K2")]
    structure = pytest.importorskip("revisionworx.bom").structure_from_csv(data)
    assert {p.number for p in structure.parts} == {"E-100", "40.52.9.024", "0213002.MXP"}


def test_one_part_number_is_one_line_and_a_formula_stays_text():
    p = panel()
    c = editing.place(p.sheets[0], "el.coil.iec", 700, 100)
    c.designator = "K3"
    c.props.update(manufacturer="Other name for Finder", part_number="40.52.9.024")
    t = editing.place(p.sheets[0], "el.fuse.iec", 800, 100)
    t.designator = "F2"
    t.props.update(part_number="=1+1")
    data, _ = rl.bom_csv(bom.generate(p), "E-100")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    relay = [r for r in rows if r[0] == "E-100" and r[2] == "40.52.9.024"]
    assert len(relay) == 1 and relay[0][4] == "3" and relay[0][6] == "K1 K2 K3"
    assert any(r[2] == "'=1+1" for r in rows)


# ------------------------------------------------------------------------------------------------- with the real program

@needs_rwx
class TestRevisionWorx:
    def test_a_project_it_doesnt_control(self, tmp_path):
        ws = workspace(tmp_path)
        f = tmp_path / "loose.schematix"
        projectio.save_project(panel(), str(f))
        s = ws[3].status(f)
        assert not s.controlled and s.sentence() == "" and s.primary() == ""

    def test_check_out_change_check_in(self, tmp_path):
        ws = workspace(tmp_path)
        f = controlled(ws)
        rwx = ws[3]
        first = rwx.status(f)
        assert first.controlled and first.number == "E-100" and first.primary() == "check-out" and first.headline()[0] == "Available"
        rwx.check_out(first)
        assert rwx.status(f).mine and rwx.status(f).primary() == "check-in"
        p = panel()
        editing.place(p.sheets[0], "el.lamp.iec", 600, 100)
        projectio.save_project(p, str(f))
        answer = rwx.check_in(f, "A lamp")
        s = rwx.status(f)
        assert answer["result"] == "revised" and not s.checked_out_by and s.file_state == "unchanged" and s.revision != first.revision

    def test_someone_elses_check_out(self, tmp_path):
        ws = workspace(tmp_path)
        f = controlled(ws)
        run("-w", ws[0], "doc", "checkout", ws[3].status(f).doc_id, env=elsewhere(tmp_path))
        s = ws[3].status(f)
        assert s.theirs and s.primary() == ""
        with pytest.raises(rl.RevisionWorxError) as e:
            ws[3].check_in(f, "Mine")
        assert e.value.kind == "checked-out"

    def test_undoing_a_check_out_can_put_the_revision_back(self, tmp_path):
        ws = workspace(tmp_path)
        f = controlled(ws)
        before = f.read_bytes()
        rwx = ws[3]
        rwx.check_out(rwx.status(f))
        projectio.save_project(new_project(), str(f))
        rwx.undo_check_out(rwx.status(f), put_back=True)
        assert f.read_bytes() == before and not rwx.status(f).checked_out_by

    def test_the_bom_goes_beside_the_schematic(self, tmp_path):
        ws = workspace(tmp_path)
        f = controlled(ws)
        rwx = ws[3]
        answer, left_out = rl.publish_bom(rwx, rwx.status(f), bom.generate(panel()), "First issue")
        d = answer["document"]
        assert answer["result"] == "created" and d["number"] == "E-100-BOM" and Path(d["path"]).parent.name == "05 BOM" and left_out == 1
        assert rl.publish_bom(rwx, rwx.status(f), bom.generate(panel()), "Again")[0]["result"] == "unchanged"
        nothing = new_project()
        assert rl.publish_bom(rwx, rwx.status(f), bom.generate(nothing), "x") == (None, 0)

    def test_openmeridian_imports_it_once_its_released(self, tmp_path):
        meridian = pytest.importorskip("openmeridian.revisionworx")
        ws = workspace(tmp_path)
        f = controlled(ws)
        rwx = ws[3]
        d = rl.publish_bom(rwx, rwx.status(f), bom.generate(panel()), "First issue")[0]["document"]
        client = meridian.Client(str(ws[0]), cli=FOUND)
        with pytest.raises(meridian.RevisionWorxError):
            client.read_bom(d["id"])         # nothing released: OpenMeridian fails closed
        for state in ("in_review", "approved", "released"):
            run("-w", ws[0], "rev", "transition", d["latest"]["id"], state)
        got = client.read_bom(d["id"])
        assert got["root"] == "E-100" and sorted((x["child"], x["qty"]) for x in got["lines"]) == [("0213002.MXP", 1000), ("40.52.9.024", 2000)]

    def test_which_project_a_file_is_in_and_which_workspaces(self, tmp_path):
        eng, project_id, folder, rwx = workspace(tmp_path)
        projects = rwx.projects(str(eng))
        assert rl.project_for(projects, folder / "04 Schematics" / "x.schematix")["id"] == project_id
        assert rl.project_for(projects, tmp_path / "x.schematix") is None
        assert [w["location"] for w in rl.workspaces_for(rwx, folder / "x.schematix")] == [str(eng)]


# ------------------------------------------------------------------------------------------------------------- the window

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
def asked(monkeypatch):
    from openschematix.gui import revisionworx_ui as ui
    seen = {"info": [], "warning": [], "yes": False, "questions": []}
    monkeypatch.setattr(ui.messagebox, "showinfo", lambda t, msg, **k: seen["info"].append(msg))
    monkeypatch.setattr(ui.messagebox, "showwarning", lambda t, msg, **k: seen["warning"].append(msg))
    monkeypatch.setattr(ui.messagebox, "askyesno", lambda t, msg, **k: seen["questions"].append(msg) or seen["yes"])
    return seen


@needs_rwx
class TestTheWindow:
    def test_the_status_bar_says_what_it_is_and_offers_the_next_step(self, app, asked, tmp_path):
        f = controlled(workspace(tmp_path))
        app.open_path(str(f), confirm=False)
        ui = app.revisionworx
        ui.refresh(wait=True)
        first = ui.status.revision
        assert ui.label.cget("text") == f"E-100 rev {first} · Work in Progress" and ui.button.cget("text") == "Check out"
        assert ui.label.winfo_manager() == "pack" and ui.button.winfo_manager() == "pack"
        assert app.status_bar.pack_slaves()[:2] == [ui.label, ui.button][::-1] or app.status_bar.pack_slaves()[0] in (ui.label, ui.button)
        assert app.file_menu.index("RevisionWorx") is not None
        assert ui.check_out()
        assert ui.button.cget("text") == "Check in…" and ui.label.cget("text").endswith("checked out by you")
        editing.place(app.doc, "el.lamp.iec", 600, 100)
        app.mark_dirty()
        assert ui.check_in(message="A lamp", with_bom=True)
        s = ui.status
        assert s.revision != first and not s.checked_out_by and not app.dirty and ui.button.cget("text") == "Check out"

    def test_someone_elses_working_file_isnt_saved_over(self, app, asked, tmp_path):
        ws = workspace(tmp_path)
        f = controlled(ws)
        app.open_path(str(f), confirm=False)
        run("-w", ws[0], "doc", "checkout", ws[3].status(f).doc_id, env=elsewhere(tmp_path))
        app.revisionworx.refresh(wait=True)
        assert "checked out by" in app.revisionworx.label.cget("text") and app.revisionworx.button.winfo_manager() == ""
        before = f.read_bytes()
        editing.place(app.doc, "el.lamp.iec", 600, 100)
        app.mark_dirty()
        assert not app.save()
        assert f.read_bytes() == before and app.dirty and "Saving here would overwrite the file they're working on" in asked["questions"][0]

    def test_undo_check_out_can_put_the_revision_back(self, app, asked, tmp_path):
        f = controlled(workspace(tmp_path))
        before = f.read_bytes()
        app.open_path(str(f), confirm=False)
        assert app.revisionworx.check_out()
        editing.place(app.doc, "el.lamp.iec", 600, 100)
        app.mark_dirty()
        assert app.save()
        assert app.revisionworx.undo_check_out(put_back=True)
        assert f.read_bytes() == before and not app.dirty and not app.revisionworx.status.checked_out_by

    def test_adding_a_project_from_elsewhere_carries_on_with_its_copy(self, app, asked, tmp_path, monkeypatch):
        eng, project_id, folder, rwx = workspace(tmp_path)
        monkeypatch.setenv("REVISIONWORX_WORKSPACE", str(eng))     # as RevisionWorx would know it, once it had opened it
        f = tmp_path / "loose.schematix"
        projectio.save_project(panel(), str(f))
        app.open_path(str(f), confirm=False)
        app.revisionworx.refresh(wait=True)
        assert app.revisionworx.label.winfo_manager() == ""
        assert app.revisionworx.add(({"id": project_id, "workspace": str(eng)}, "E-200", "Loose", "First issue"))
        assert folder in Path(app.filename).parents and app.revisionworx.status.number == "E-200"
