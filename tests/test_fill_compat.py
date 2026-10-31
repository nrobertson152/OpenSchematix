"""Compatibility of files containing boundary fills with older readers.

Fill data ("hatch" shapes) must never reach an OpenSchematix 1.0.x reader
in a file that claims a schema it understands - neither in the current
sheets nor in the revision history stored in the project file. Files
without fills anywhere must stay readable by 1.0.x."""
import io
import json
import os
import shutil
import subprocess
import sys
import textwrap
import zipfile

import pytest

from openschematix import fileio, projectio, revisions, templates
from openschematix.boundary_fill import find_region
from openschematix.model import Document, Shape
from openschematix.project import new_project

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def manifest_schema(data: bytes) -> int:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return json.loads(z.read("manifest.json"))["sheet_schema"]


def add_fill(doc):
    rect = Shape(doc.new_id(), "rect", pts=[(100, 100), (300, 100), (300, 200), (100, 200)])
    doc.add_shape(rect)
    h = Shape(doc.new_id(), "hatch", rings=find_region([rect], (150, 150)).rings)
    doc.add_shape(h)
    return h


def project_fill_only_in_history():
    """Fill saved once (auto snapshot), then deleted from the drawing."""
    p = new_project()
    h = add_fill(p.sheets[0])
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "auto", description="with fill")
    del p.sheets[0].shapes[h.id]
    assert not any(s.kind == "hatch" for d in p.sheets for s in d.shapes.values())
    return p, h


# ================================================================ the defect
def test_fill_only_in_revision_history_forces_schema_3(tmp_path):
    p, h = project_fill_only_in_history()
    assert projectio.required_schema(p) == 3
    assert manifest_schema(projectio.project_bytes(p)) == 3
    path = tmp_path / "hist.schematix"
    projectio.save_project(p, str(path))          # also adds a fill-free auto snapshot
    data = path.read_bytes()
    assert manifest_schema(data) == 3
    back = projectio.open_any(str(path)).project
    n = [e["n"] for e in back.revisions.entries if e["description"] == "with fill"][0]
    restored = revisions.restore(back, back.revisions, n)
    assert h.id in restored.sheets[0].shapes and restored.sheets[0].shapes[h.id].kind == "hatch"


def test_fill_in_approved_revision_forces_schema_3():
    p = new_project()
    h = add_fill(p.sheets[0])
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "approved", label="A")
    del p.sheets[0].shapes[h.id]
    assert manifest_schema(projectio.project_bytes(p)) == 3


def test_schema_returns_to_2_when_no_fill_is_left_anywhere():
    p, _h = project_fill_only_in_history()
    st = p.revisions
    for e in list(st.entries):
        st.delete(e["n"])
    st.create(p, "auto")
    assert st.required_schema() == 2
    assert manifest_schema(projectio.project_bytes(p)) == 2


def test_fill_free_projects_and_histories_stay_schema_2():
    p = new_project()
    p.sheets[0].add_shape(Shape(p.sheets[0].new_id(), "rect", pts=[(0, 0), (10, 0), (10, 10), (0, 10)]))
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "auto")
    p.revisions.create(p, "approved", label="A")
    assert manifest_schema(projectio.project_bytes(p)) == 2


def test_schema_cache_follows_new_snapshots():
    p = new_project()
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "auto")
    assert p.revisions.required_schema() == 2
    add_fill(p.sheets[0])
    p.revisions.create(p, "auto")
    assert p.revisions.required_schema() == 3


def test_recovery_snapshot_uses_the_same_rule(tmp_path):
    from openschematix.recovery import RecoveryManager
    p, _h = project_fill_only_in_history()
    rm = RecoveryManager(str(tmp_path))
    rm.start()
    path = rm.autosave(p, source="x")
    assert path and manifest_schema(open(path, "rb").read()) == 3
    rm.end()


# ================================================================ the old readers' gates
def _old_project_reader(monkeypatch):
    """The current reader with 1.0.x's limit (sheet schema 2)."""
    monkeypatch.setattr(projectio, "SHEET_SCHEMA", 2)


@pytest.mark.parametrize("case", ["current", "history"])
def test_gate_refuses_fill_projects_for_a_schema_2_reader(monkeypatch, case):
    if case == "current":
        p = new_project()
        add_fill(p.sheets[0])
    else:
        p, _h = project_fill_only_in_history()
    data = projectio.project_bytes(p)
    _old_project_reader(monkeypatch)
    with pytest.raises(projectio.ProjectFormatError, match="newer than supported"):
        projectio.read_zip(io.BytesIO(data))


def test_gate_accepts_fill_free_projects_for_a_schema_2_reader(monkeypatch):
    p = new_project()
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "auto")
    data = projectio.project_bytes(p)
    _old_project_reader(monkeypatch)
    assert projectio.read_zip(io.BytesIO(data)).project.sheets


def test_osch_sheet_with_fill_is_refused_by_a_schema_2_reader(monkeypatch, tmp_path):
    doc = Document()
    add_fill(doc)
    path = tmp_path / "s.osch"
    fileio.save(doc, str(path))
    assert json.loads(path.read_text())["schema"] == 3
    monkeypatch.setattr(fileio, "FILE_SCHEMA", 2)
    with pytest.raises(fileio.FileFormatError, match="newer version"):
        fileio.load(str(path))


def test_templates_with_fills_are_version_2(monkeypatch):
    from openschematix.editing import copy_items
    doc = Document()
    h = add_fill(doc)
    tpl = templates.make_template("with fill", copy_items(doc, [h.id]))
    assert tpl["version"] == 2
    plain = templates.make_template("plain", copy_items(doc, [i for i in doc.shapes if i != h.id]))
    assert plain["version"] == 1
    templates.validate(tpl)
    # a 1.0.x reader (TPL_VERSION 1) refuses it as newer instead of failing on the unknown shape
    monkeypatch.setattr(templates, "TPL_VERSION", 1)
    with pytest.raises(templates.TemplateError, match="newer version"):
        templates.validate(tpl)
    templates.validate(plain)


# ================================================================ the real 1.0.x reader
def _legacy_tree(tmp_path_factory):
    """Extract the released 1.0.x package (git tag v1.0.0) next to the tests."""
    if shutil.which("git") is None or not os.path.isdir(os.path.join(ROOT, ".git")):
        pytest.skip("git checkout not available")
    ok = subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "-q", "v1.0.0^{commit}"],
                        capture_output=True).returncode == 0
    if not ok:
        pytest.skip("tag v1.0.0 not available in this clone")
    dest = tmp_path_factory.mktemp("legacy")
    arch = subprocess.run(["git", "-C", ROOT, "archive", "v1.0.0", "openschematix"], capture_output=True, check=True)
    with open(dest / "pkg.tar", "wb") as f:
        f.write(arch.stdout)
    subprocess.run(["tar", "-xf", str(dest / "pkg.tar"), "-C", str(dest)], check=True)
    return dest


LEGACY_PROBE = textwrap.dedent("""
    import sys
    sys.path.insert(0, sys.argv[1])
    import openschematix
    assert openschematix.FILE_SCHEMA == 2, openschematix.FILE_SCHEMA
    from openschematix import projectio
    try:
        res = projectio.open_any(sys.argv[2])
    except projectio.ProjectFormatError as e:
        print("REFUSED", e)
    else:
        print("OPENED", sum(len(d.shapes) for d in res.project.sheets))
""")


@pytest.fixture(scope="module")
def legacy(tmp_path_factory):
    return _legacy_tree(tmp_path_factory)


def _probe(legacy, path):
    r = subprocess.run([sys.executable, "-I", "-c", LEGACY_PROBE, str(legacy), str(path)], capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_released_1_0_reader_refuses_fill_projects(legacy, tmp_path):
    cur = new_project()
    add_fill(cur.sheets[0])
    hist, _h = project_fill_only_in_history()
    for name, p in (("current", cur), ("history", hist)):
        path = tmp_path / f"{name}.schematix"
        projectio.save_project(p, str(path))
        out = _probe(legacy, path)
        assert out.startswith("REFUSED") and "newer" in out, (name, out)


def test_released_1_0_reader_opens_fill_free_projects(legacy, tmp_path):
    p = new_project()
    p.sheets[0].add_shape(Shape(p.sheets[0].new_id(), "rect", pts=[(0, 0), (10, 0), (10, 10), (0, 10)]))
    path = tmp_path / "plain.schematix"
    projectio.save_project(p, str(path))
    assert _probe(legacy, path) == "OPENED 1"
