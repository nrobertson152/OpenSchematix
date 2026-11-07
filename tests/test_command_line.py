"""The command line for other programs (openschematix/cli.py, docs/COMMAND_LINE.md), and revision codes on printed sheets
(openschematix/revcode.py): FieldWorx's FWX:R:<number>@<revision> as a QR code in the drawing area's lower right corner. Codes are read
back from the rendered pages by zxing-cpp, the decoder FieldWorx's app uses, after PDFium has rendered them: programs that share no
code with OpenSchematix. The tests that need them skip without them."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from openschematix import cli, editing, export, fwx_label, projectio, revcode
from openschematix.geometry import UNIT_MM
from openschematix.project import new_project


def run(capsys, *args):
    code = cli.main([str(a) for a in args])
    out = capsys.readouterr().out
    assert out.count("\n") == 1, out
    return code, json.loads(out)


def panel(style="standard", scale="1:1", zones=True):
    """Two relays K1 and K2 with part numbers, a fuse F1, a resistor without one, and a ground mark, on two sheets."""
    p = new_project()
    p.meta.update(title="Press panel", number="J-3001")
    d = p.sheets[0]
    d.name = "Power"
    d.sheet.title_block, d.sheet.scale, d.sheet.zones = style, scale, zones
    for i, des in enumerate(("K1", "K2")):
        c = editing.place(d, "el.coil.iec", 100 + 120 * i, 100)
        c.designator = des
        c.props.update(manufacturer="Finder", part_number="40.52.9.024", description="Relay 24 V DC")
    f = editing.place(d, "el.fuse.iec", 400, 100)
    f.designator = "F1"
    f.props.update(manufacturer="Littelfuse", part_number="0213002.MXP", description="Fuse 2 A")
    editing.place(d, "el.earth", 600, 100)
    second = p.add_sheet("Control")
    r = editing.place(second, "el.resistor.iec", 200, 200)
    r.designator = "R1"
    return p


def saved(tmp_path, project=None, name="panel.schematix") -> Path:
    f = tmp_path / name
    projectio.save_project(project or panel(), str(f))
    return f


def codes_in(pdf: Path) -> list:
    pdfium = pytest.importorskip("pypdfium2")
    zxingcpp = pytest.importorskip("zxingcpp")
    doc = pdfium.PdfDocument(str(pdf))
    out = []
    for i in range(len(doc)):
        image = doc[i].render(scale=150 / 72, grayscale=True).to_pil()
        out.append([(r.text, r.position) for r in zxingcpp.read_barcodes(image)])
    return out


# ------------------------------------------------------------------------------------------------- the command line

def test_version(capsys):
    from openschematix import VERSION
    code, out = run(capsys, "version")
    assert code == 0 and out == {"ok": True, "api": 1, "version": VERSION}


def test_the_command_line_never_starts_tkinter():
    probe = ("import sys, io, contextlib\nfrom openschematix import cli\nwith contextlib.redirect_stdout(io.StringIO()):\n"
             "    cli.main(['version'])\nassert 'tkinter' not in sys.modules, 'tkinter was imported'\n")
    r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([sys.executable, "-m", "openschematix", "version"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and json.loads(r.stdout)["ok"] is True


def test_components_with_their_sheets_zones_and_the_bom(capsys, tmp_path):
    f = saved(tmp_path)
    code, out = run(capsys, "components", f)
    assert code == 0 and (out["title"], out["number"]) == ("Press panel", "J-3001")
    assert out["sheets"] == [{"number": 1, "name": "Power"}, {"number": 2, "name": "Control"}]
    by = {c["designator"]: c for c in out["components"] if c["designator"]}
    assert set(by) >= {"K1", "K2", "F1", "R1"}
    k1 = by["K1"]
    assert (k1["sheet"], k1["sheet_name"], k1["symbol"], k1["part_number"], k1["manufacturer"], k1["part"]) == \
        (1, "Power", "el.coil.iec", "40.52.9.024", "Finder", True)
    assert k1["zone"] and k1["zone"][0].isalpha() and k1["zone"][1:].isdigit(), "a grid reference like A2"
    earth = next(c for c in out["components"] if c["symbol"] == "el.earth")
    assert earth["part"] is False, "a ground mark is drawn, not bought"
    relays = next(ln for ln in out["bom"] if ln["part_number"] == "40.52.9.024")
    assert relays["quantity"] == 2 and relays["designators"] == ["K1", "K2"] and relays["sheets"] == ["Power"]
    code, out = run(capsys, "components", f, "--sheet", "Control")
    assert code == 0 and [c["designator"] for c in out["components"]] == ["R1"] and out["sheets"] == [{"number": 2, "name": "Control"}]
    no_zones = panel(zones=False)
    code, out = run(capsys, "components", saved(tmp_path, no_zones, "plain.schematix"), "--sheet", "1")
    assert {c["zone"] for c in out["components"]} == {""}, "no zones on the frame, no grid reference"


def test_a_pdf_as_export_makes_it(capsys, tmp_path):
    f = saved(tmp_path)
    code, out = run(capsys, "pdf", f, tmp_path / "panel.pdf")
    assert code == 0 and out["revision_code"] == "" and out["missing"] == []
    assert out["sheets"] == [{"number": 1, "name": "Power"}, {"number": 2, "name": "Control"}]
    assert (tmp_path / "panel.pdf").read_bytes() == export.project_pdf(projectio.open_any(str(f)).project)
    code, out = run(capsys, "pdf", f, tmp_path / "one.pdf", "--sheet", "2")
    assert code == 0 and out["sheets"] == [{"number": 2, "name": "Control"}]


def test_refusals_change_nothing(capsys, tmp_path):
    f = saved(tmp_path)
    (tmp_path / "there.pdf").write_bytes(b"mine")
    damaged = tmp_path / "damaged.schematix"
    damaged.write_bytes(b"PK\x03\x04 not really a project")
    for args, kind in (((f, tmp_path / "there.pdf"), "exists"), ((f, tmp_path / "a.txt"), "bad-input"),
                       ((f, tmp_path / "a.pdf", "--sheet", "9"), "bad-input"),
                       ((f, tmp_path / "a.pdf", "--revision-code", "E-100"), "bad-input"),
                       ((tmp_path / "nope.schematix", tmp_path / "a.pdf"), "not-readable"),
                       ((damaged, tmp_path / "a.pdf"), "not-readable"), ((f, tmp_path / "a.pdf", "--paper", "A0"), "bad-input")):
        code, out = run(capsys, "pdf", *args)
        assert code == 2 and out["ok"] is False and out["kind"] == kind and out["error"], args
    assert (tmp_path / "there.pdf").read_bytes() == b"mine" and not (tmp_path / "a.pdf").exists()
    code, out = run(capsys, "components", damaged)
    assert code == 2 and out["kind"] == "not-readable"


# ------------------------------------------------------------------------------------------------- revision codes

def test_the_encoder_is_fieldworxs_copied_unchanged():
    # FieldWorx tests fwx_label.py bit for bit against python-qrcode; this copy must be that file, so it draws the same codes.
    assert fwx_label.FWX_LABEL_VERSION == 1
    assert hashlib.sha256(Path(fwx_label.__file__).read_bytes()).hexdigest() == \
        "56cffdf78cb5f0297cf17f06f8ada7a738f30a2f7e7eb6f65d671109a291c067"


@pytest.mark.parametrize("style,scale", [("standard", "1:1"), ("compact", "1:1"), ("iso", "1:1"), ("none", "1:1"),
                                         ("standard", "1:2")])
def test_every_sheet_carries_the_code_above_its_title_block(capsys, tmp_path, style, scale):
    f = saved(tmp_path, panel(style, scale))
    code, out = run(capsys, "pdf", f, tmp_path / "panel.pdf", "--revision-code", "E-100@B")
    assert code == 0 and out["revision_code"] == "FWX:R:E-100@B"
    pages = codes_in(tmp_path / "panel.pdf")
    assert [[t for t, _ in page] for page in pages] == [["FWX:R:E-100@B"], ["FWX:R:E-100@B"]], "on every sheet"
    project = projectio.open_any(str(f)).project
    doc = project.sheets[0]
    x0, y0, x1, y1 = revcode.area(doc)
    pw, ph = doc.sheet.paper_units()
    p = pages[0][0][1]
    k = 150 / 25.4 * UNIT_MM                                  # pixels per paper unit
    cx = (p.top_left.x + p.top_right.x + p.bottom_left.x + p.bottom_right.x) / 4 / k
    cy = (p.top_left.y + p.top_right.y + p.bottom_left.y + p.bottom_right.y) / 4 / k
    assert x0 < cx < x1 and y0 < cy < y0 + revcode.SIZE, "where area() says, the caption below it"
    assert x1 < pw - 40 and y1 < ph - 40, "inside the frame"
    from openschematix import titleblock
    tb = titleblock.frame_layout(doc)["title_block"]
    if tb is not None:
        assert y1 <= tb[1] * doc.sheet.scale_factor(), "above the title block (and its revision table)"


def test_it_never_covers_the_drawing(capsys, tmp_path):
    p = panel()
    doc = p.sheets[0]
    f = doc.sheet.scale_factor()
    x0, y0, x1, y1 = revcode.area(doc)
    editing.add_wire(doc, [((x0 + 10) / f, (y0 + 10) / f), ((x1 + 80) / f, (y0 + 10) / f)])    # a wire through the corner
    path = saved(tmp_path, p)
    code, out = run(capsys, "pdf", path, tmp_path / "a.pdf", "--revision-code", "E-100@B")
    assert code == 2 and out["kind"] == "bad-input" and "Sheet 1. Power: no room for the revision code" in out["error"]
    assert not (tmp_path / "a.pdf").exists()
    skipped: list = []
    data = export.project_pdf(projectio.open_any(str(path)).project, None, None, revcode.RevisionCode("E-100", "B"), skipped)
    assert skipped == ["1. Power"], "the window prints the sheet without it, and says which"
    (tmp_path / "b.pdf").write_bytes(data)
    assert [[t for t, _ in page] for page in codes_in(tmp_path / "b.pdf")] == [[], ["FWX:R:E-100@B"]]


def test_what_is_and_isnt_in_the_way():
    p = panel()
    doc = p.sheets[0]
    items, _ = export.paper_items(doc, True, p)
    box = revcode.area(doc)
    assert revcode.why_not(items, box) == "", "the frame, title block and revision table aren't in the way"
    near = [{"k": "line", "pts": [(box[0] - 30, box[1] - 30), (box[0] - 1, box[3] + 50)], "role": "wire"}]
    assert revcode.why_not(near, box) == "", "close, but clear of it"
    across = [{"k": "line", "pts": [(box[0] - 30, box[1] + 5), (box[2] + 30, box[1] + 5)], "role": "wire"}]
    text = [{"k": "text", "p": ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), "s": "NOTE", "size": 10, "anchor": "c", "role": "ink"}]
    watermark = [{"k": "text", "p": ((box[0] + box[2]) / 2, box[1]), "s": "PRELIMINARY", "size": 80, "anchor": "c",
                  "role": "watermark"}]
    assert revcode.why_not(across, box) and revcode.why_not(text, box) and not revcode.why_not(watermark, box)


def test_revision_codes_are_checked_and_long_ones_get_smaller_words():
    assert revcode.RevisionCode.parse(" E-100@B ") == revcode.RevisionCode("E-100", "B")
    assert revcode.RevisionCode.parse("A@B@C").text == "FWX:R:A@B@C", "the revision is what follows the last @"
    for bad in ("E-100", "@B", "E-100@", "E-100@ ", "E\n100@B", ""):
        with pytest.raises(revcode.CodeError):
            revcode.RevisionCode.parse(bad)
    box = (0.0, 0.0, revcode.CLEAR[0], revcode.CLEAR[1])
    short = [i for i in revcode.code_items(revcode.RevisionCode("E-100", "B"), box) if i["k"] == "text"]
    longer = [i for i in revcode.code_items(revcode.RevisionCode("E-100-PRESS-PANEL", "AB"), box) if i["k"] == "text"]
    longest = [i for i in revcode.code_items(revcode.RevisionCode("E-100-PRESS-PANEL-LINE-3-SHEETS-1-TO-12", "AB"), box)
               if i["k"] == "text"]
    assert short[0]["size"] == revcode.CAPTION and longer[0]["size"] < revcode.CAPTION and longest == [], \
        "words shrink to the code's width, and are left out when too small to read: the code still holds them"
    assert export.text_width(longer[0]["s"], longer[0]["size"]) <= revcode.SIZE + 1e-9


def test_answers_are_ascii_json_whatever_the_names_are(capsys, tmp_path):
    p = panel()
    p.sheets[0].name = "Leistung Ω — 電源"
    code, out = run(capsys, "components", saved(tmp_path, p), "--sheet", "1")
    assert code == 0 and out["sheets"][0]["name"] == "Leistung Ω — 電源"
    assert run(capsys, "version")[0] == 0
    cli.main(["components", str(tmp_path / "panel.schematix")])
    assert capsys.readouterr().out.isascii(), "escaped, so a Windows code page can't break it"
