"""Release metadata and shipped example compatibility regression checks.

The standalone drawing app_version is the *writer's application version*,
not its sheet schema. Old samples remain readable, but current distributed
samples and generated demo projects must advertise the current writer.
"""
import json
import pathlib
import zipfile

import pytest

from openschematix import APP_NAME, VERSION, fileio, projectio
from openschematix.gui import dialogs

pytestmark = pytest.mark.requires_tk

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def test_ui_version_labels_share_application_constant():
    import inspect
    from openschematix.gui import app
    from openschematix import __version__
    assert VERSION == __version__ == "1.1.0"
    assert dialogs.VERSION == app.VERSION == VERSION
    assert f"Version {VERSION}" in inspect.getsource(dialogs.AboutDialog)
    assert 'text=f"Version {VERSION}"' in inspect.getsource(app)
    assert '{APP_NAME} {VERSION}' in inspect.getsource(app)
    assert APP_NAME == "OpenSchematix"


@pytest.mark.parametrize("filename", ["start_stop_latch.osch", "hydraulic_cylinder_circuit.osch"])
def test_distributed_standalone_examples_have_current_writer_version(filename):
    path = EXAMPLES / filename
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["format"] == "OpenSchematix"
    assert raw["app_version"] == VERSION
    assert raw["schema"] == 1  # Legacy schema is intentional, not an app version.
    loaded = fileio.load(str(path))
    assert loaded.document.components
    assert loaded.document.to_dict()["app_version"] == VERSION


def test_demo_generator_writes_current_version_and_reopens(tmp_path):
    from tools.make_demo_project import build
    project = build()
    target = tmp_path / "generated.schematix"
    projectio.save_project(project, str(target), snapshot=False)
    with zipfile.ZipFile(target) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["app"] == f"{APP_NAME} {VERSION}"
    reopened = projectio.open_any(str(target)).project
    assert len(reopened.sheets) == 3


def test_checked_in_demo_is_readable_even_if_created_by_older_writer():
    # The checked-in binary is a compatibility sample. Release builds
    # regenerate it before packaging so distributed copies have current metadata.
    path = EXAMPLES / "demo_project.schematix"
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format"] == projectio.PROJECT_FORMAT
        assert manifest["version"] == projectio.PROJECT_VERSION
    project = projectio.open_any(str(path)).project
    assert len(project.sheets) == 3


def test_release_workflow_regenerates_demo_before_copying_examples():
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert workflow.count("tools/make_demo_project.py") >= 2
    assert "cp examples/*.schematix examples/*.osch dist/OpenSchematix/examples/" in workflow
    assert "Copy-Item examples\\* dist\\OpenSchematix\\examples\\" in workflow


def test_current_serializer_never_copies_old_writer_version():
    from openschematix.model import Document
    doc = Document()
    current = doc.to_dict()
    assert current["app_version"] == VERSION
    current["app_version"] = "1.0.0"
    reopened = Document.from_dict(current)
    assert reopened.to_dict()["app_version"] == VERSION
