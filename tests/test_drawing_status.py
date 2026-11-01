"""Sheet drawing status and non-interactive watermark regression tests."""
import io
import zipfile
import re
import zlib

from openschematix.model import Document, Sheet
from openschematix.project import new_project
from openschematix.projectio import project_bytes, save_project, open_any
from openschematix.render import scene
from openschematix.export import to_svg, to_pdf, project_pdf, paper_items


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


def _pdf_page_streams(pdf):
    """Decode Flate page streams so the assertions inspect drawing commands."""
    return [zlib.decompress(data) for data in re.findall(
        rb"stream\n(.*?)\nendstream", pdf, flags=re.DOTALL
    )]


def test_frameless_exports_keep_preliminary_designation():
    doc = Document()
    doc.sheet.drawing_status = "Preliminary"
    for use_sheet in (True, False):
        svg = to_svg(doc, use_sheet=use_sheet)
        assert "PRELIMINARY" in svg and "NOT FOR PRODUCTION" in svg
        assert 'fill="#b8b8b8"' in svg
        content = b"\n".join(_pdf_page_streams(to_pdf(doc, use_sheet=use_sheet)))
        assert b"(PRELIMINARY) Tj" in content
        assert b"(NOT FOR PRODUCTION) Tj" in content
        assert b"0.72 0.72 0.72 rg" in content
    doc.sheet.drawing_status = "Released"
    for use_sheet in (True, False):
        assert "PRELIMINARY" not in to_svg(doc, use_sheet=use_sheet)
        assert b"(PRELIMINARY) Tj" not in b"\n".join(
            _pdf_page_streams(to_pdf(doc, use_sheet=use_sheet))
        )


def test_multisheet_pdf_designation_is_per_sheet():
    project = new_project()
    project.sheets[0].sheet.drawing_status = "Preliminary"
    project.add_sheet("Released")
    streams = _pdf_page_streams(project_pdf(project))
    assert len(streams) == 2
    assert b"(PRELIMINARY) Tj" in streams[0]
    assert b"(PRELIMINARY) Tj" not in streams[1]


def test_native_file_save_reopen_preserves_independent_statuses(tmp_path):
    project = new_project()
    project.sheets[0].sheet.drawing_status = "Preliminary"
    project.add_sheet("Released sheet")
    path = tmp_path / "drawing_status.schematix"
    save_project(project, str(path), snapshot=False)
    reopened = open_any(str(path)).project
    assert [d.sheet.drawing_status for d in reopened.sheets] == ["Preliminary", "Released"]
    assert "PRELIMINARY" in to_svg(reopened.sheets[0], project=reopened)
    assert "PRELIMINARY" not in to_svg(reopened.sheets[1], project=reopened)


def test_drawing_status_uses_real_gui_undo_redo_commands_without_display():
    """Exercise App's actual snapshot, commit, undo, and restore paths headlessly."""
    from types import SimpleNamespace
    from openschematix.gui.app import App

    app = App.__new__(App)
    app.project = new_project()
    app.doc = app.project.sheets[0]
    app.undo_stack = []
    app.redo_stack = []
    app.selection = set()
    app.canvas = SimpleNamespace(drag=False)
    app.runner = SimpleNamespace(active=False)
    app.mark_dirty = lambda: None
    app.refresh = lambda **kwargs: None
    app.set_status = lambda message: None

    app.set_drawing_status("Preliminary")
    assert app.doc.sheet.drawing_status == "Preliminary"
    assert len(app.undo_stack) == 1
    app.undo()
    assert app.doc.sheet.drawing_status == "Released"
    assert len(app.redo_stack) == 1
    app.redo()
    assert app.doc.sheet.drawing_status == "Preliminary"
    assert len(app.undo_stack) == 1
    app.set_drawing_status("Preliminary")
    assert len(app.undo_stack) == 1


def test_scaled_and_frameless_watermark_placement():
    doc = Document()
    doc.sheet.drawing_status = "Preliminary"
    for scale in ("1:1", "1:2", "2:1"):
        doc.sheet.scale = scale
        items, extent = paper_items(doc, use_sheet=True)
        marks = [item for item in items if item.get("role") == "watermark"]
        assert len(marks) == 2
        width, height = doc.sheet.paper_units()
        assert extent == (0.0, 0.0, width, height)
        assert abs(marks[0]["p"][0] - width / 2) < 1e-7
        assert abs(marks[0]["p"][1] - height * 0.46) < 1e-7
        assert marks[0]["size"] > 0
        cropped, bounds = paper_items(doc, use_sheet=False)
        cropped_marks = [item for item in cropped if item.get("role") == "watermark"]
        assert len(cropped_marks) == 2
        assert all(bounds[0] <= m["p"][0] <= bounds[2] and
                   bounds[1] <= m["p"][1] <= bounds[3] for m in cropped_marks)
