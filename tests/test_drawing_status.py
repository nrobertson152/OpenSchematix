"""Sheet drawing status and non-interactive watermark regression tests."""
import io
import zipfile

from openschematix.model import Document, Sheet
from openschematix.project import new_project
from openschematix.projectio import project_bytes
from openschematix.render import scene
from openschematix.export import to_svg, to_pdf, project_pdf


def test_legacy_sheet_defaults_to_released():
    sheet = Sheet.from_dict({"size": "A4"})
    assert sheet.drawing_status == "Released"
    assert Sheet.from_dict({"drawing_status": "invalid"}).drawing_status == "Released"
    assert not any(x.get("role") == "watermark" for x in scene(Document()))


def test_status_round_trip_and_independent_sheets():
    project = new_project()
    first = project.sheets[0]
    second = project.add_sheet("Second")
    first.sheet.drawing_status = "Preliminary"
    assert second.sheet.drawing_status == "Released"
    copy = type(project).from_dict(project.to_dict())
    assert copy.sheets[0].sheet.drawing_status == "Preliminary"
    assert copy.sheets[1].sheet.drawing_status == "Released"
    with zipfile.ZipFile(io.BytesIO(project_bytes(project))) as archive:
        assert archive.testzip() is None


def test_watermark_not_selectable_or_in_document_geometry():
    doc = Document()
    doc.sheet.drawing_status = "Preliminary"
    assert not doc.components and not doc.wires and not doc.shapes
    assert doc.bbox() is None
    marks = [x for x in scene(doc) if x.get("role") == "watermark"]
    assert [x["s"] for x in marks] == ["PRELIMINARY", "NOT FOR PRODUCTION"]
    assert all(x["item"] is None for x in marks)
    w, h = doc.sheet.size_units()
    assert marks[0]["p"] == (w / 2, h * 0.46)
    doc.sheet.drawing_status = "Released"
    assert not any(x.get("role") == "watermark" for x in scene(doc))


def test_svg_pdf_watermark_and_released_absence():
    doc = Document()
    doc.sheet.drawing_status = "Preliminary"
    svg = to_svg(doc)
    pdf = to_pdf(doc)
    assert "PRELIMINARY" in svg
    assert "NOT FOR PRODUCTION" in svg
    assert "#b8b8b8" in svg
    assert pdf.startswith(b"%PDF")
    doc.sheet.drawing_status = "Released"
    assert "PRELIMINARY" not in to_svg(doc)
    assert "NOT FOR PRODUCTION" not in to_svg(doc)
    assert to_pdf(doc).startswith(b"%PDF")


def test_multisheet_project_pdf_export():
    project = new_project()
    project.sheets[0].sheet.drawing_status = "Preliminary"
    project.add_sheet("Released")
    pdf = project_pdf(project)
    assert pdf.startswith(b"%PDF")
