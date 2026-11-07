"""The command line for other programs (openschematix/cli.py, docs/COMMAND_LINE.md)."""
import json
import subprocess
import sys
from pathlib import Path

from openschematix import cli, editing, export, projectio
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
    assert code == 0 and out["missing"] == [] and "revision_code" not in out
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
                       ((tmp_path / "nope.schematix", tmp_path / "a.pdf"), "not-readable"),
                       ((damaged, tmp_path / "a.pdf"), "not-readable"), ((f, tmp_path / "a.pdf", "--paper", "A0"), "bad-input")):
        code, out = run(capsys, "pdf", *args)
        assert code == 2 and out["ok"] is False and out["kind"] == kind and out["error"], args
    assert (tmp_path / "there.pdf").read_bytes() == b"mine" and not (tmp_path / "a.pdf").exists()
    code, out = run(capsys, "components", damaged)
    assert code == 2 and out["kind"] == "not-readable"


def test_a_pdf_carries_no_revision_code(capsys, tmp_path):
    """Prints carry no QR code: which revision of a drawing applies is a unit's to say (RevisionWorx's unit register), so a code on
    paper could only say whether it's the released one, which can be the wrong advice for a machine built to an earlier one."""
    f = saved(tmp_path)
    code, out = run(capsys, "pdf", f, tmp_path / "panel.pdf", "--revision-code", "E-100@B")
    assert code == 2 and out["kind"] == "bad-input" and not (tmp_path / "panel.pdf").exists()


def test_answers_are_ascii_json_whatever_the_names_are(capsys, tmp_path):
    p = panel()
    p.sheets[0].name = "Leistung Ω — 電源"
    code, out = run(capsys, "components", saved(tmp_path, p), "--sheet", "1")
    assert code == 0 and out["sheets"][0]["name"] == "Leistung Ω — 電源"
    assert run(capsys, "version")[0] == 0
    cli.main(["components", str(tmp_path / "panel.schematix")])
    assert capsys.readouterr().out.isascii(), "escaped, so a Windows code page can't break it"
