"""Project-file loading: malformed input, damaged revision history and
non-finite numbers (audit findings F4, F5, F9)."""
import io
import json
import os
import zipfile
import zlib

import pytest

from openschematix import editing, fileio, model, projectio, revisions, safejson, symbols
from openschematix.model import Shape, Wire
from openschematix.project import new_project
from openschematix.symbols.custom import blank_symbol, normalise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")
SECRET = "TOP-SECRET-CLIENT-NAME"


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    symbols.set_project_symbols([])


# ---------------------------------------------------------------- helpers
def sensor_doc():
    d = blank_symbol("Sensor")
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "A", "name": "A", "x": -20, "y": 0, "dir": "l"},
                 {"id": "B", "name": "B", "x": 20, "y": 0, "dir": "r"}]
    return normalise(d)


def rich_project():
    """Two sheets, every shape kind, a valve, an embedded custom symbol and
    three revisions (one approved)."""
    from openschematix.symbols.custom import to_symdef
    p = new_project("Reliability")
    sdoc = sensor_doc()
    symbols.add_project_symbol(to_symdef(sdoc))
    doc = p.sheets[0]
    k = editing.place(doc, "el.coil.iec", 200, 200)
    s = editing.place(doc, sdoc["id"], 600, 200)
    editing.place(doc, "fl.hyd.dcv", 400, 400)
    w = Wire(doc.new_id(), [k.terminals()["A2"], s.terminals()["A"]], [k.id, "A2"], [s.id, "A"])
    doc.add_wire(w)
    editing.reroute(doc, w)
    for sh in (Shape(0, "line", pts=[(0, 0), (50, 0)]), Shape(0, "circle", c=(100, 100), r=20),
               Shape(0, "arc", c=(100, 100), r=30, start=10, extent=80), Shape(0, "text", pts=[(10, 10)], s="Note"),
               Shape(0, "hatch", rings=[[(0, 0, 0), (40, 0, 0), (40, 40, 0), (0, 40, 0)]])):
        sh.id = doc.new_id()
        doc.add_shape(sh)
    p.embed_symbols()
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "approved", label="A", description="First issue")
    editing.place(p.add_sheet("Second"), "el.resistor.iec", 100, 100)
    p.revisions.create(p, "auto", description="Saved")
    editing.place(p.sheets[1], "el.resistor.iec", 300, 100)
    p.revisions.create(p, "approved", label="B", description="Second issue")
    return p


@pytest.fixture
def files():
    """Members of a valid project file, by name (bytes)."""
    data = projectio.project_bytes(rich_project())
    symbols.set_project_symbols([])
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def sheet_member(files, index=0):
    order = json.loads(files["project.json"])["sheet_order"]
    return f"sheets/{order[index]}.json"


def write(tmp_path, files, name="p.schematix"):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in files.items():
            z.writestr(n, b if isinstance(b, bytes) else json.dumps(b))
    return str(path)


def edited(files, member, fn):
    """Copy of `files` with JSON member `member` changed by fn(obj) (in place)."""
    obj = json.loads(files[member])
    fn(obj)
    return dict(files, **{member: json.dumps(obj).encode()})


def rejected(path, *fragments):
    with pytest.raises(projectio.ProjectFormatError) as e:
        projectio.open_any(path)
    msg = str(e.value)
    for f in fragments:
        assert f in msg, msg
    assert SECRET not in msg
    return msg


# ---------------------------------------------------------------- valid files keep working
def test_valid_projects_open_and_round_trip(tmp_path, files):
    res = projectio.open_any(write(tmp_path, files))
    assert not res.warnings and not res.recovered and not res.needs_new_name
    p = res.project
    assert [len(d.components) for d in p.sheets] == [3, 2] and len(p.sheets[0].shapes) == 5
    assert [e["label"] for e in p.revisions.approved()] == ["A", "B"] and len(p.revisions.entries) == 3
    path2 = str(tmp_path / "again.schematix")
    projectio.save_project(p, path2)
    q = projectio.open_any(path2).project
    assert [d.to_dict() for d in q.sheets] == [d.to_dict() for d in p.sheets]
    for e in q.revisions.entries:
        q.revisions.load(e["n"])                         # every revision restores


@pytest.mark.parametrize("name", sorted(os.listdir(EXAMPLES)))
def test_shipped_examples_open_without_warnings(name):
    res = projectio.open_any(os.path.join(EXAMPLES, name))
    assert not res.recovered and res.project.sheets
    assert not [w for w in res.warnings if "damaged" in w]


# ---------------------------------------------------------------- malformed members
@pytest.mark.parametrize("member", ["manifest.json", "project.json", "sheet", "revisions/index.json"])
@pytest.mark.parametrize("cut", [0, 0.5, 0.95])
def test_truncated_json(tmp_path, files, member, cut):
    member = sheet_member(files) if member == "sheet" else member
    raw = files[member]
    path = write(tmp_path, dict(files, **{member: raw[: int(len(raw) * cut)]}))
    if member.startswith("revisions/"):
        res = projectio.open_any(path)                  # the drawing itself is intact
        assert res.recovered and res.project.revisions.entries == []
        assert any("revision history is damaged" in w for w in res.warnings)
    else:
        rejected(path, member, "not valid JSON")


def test_member_that_is_not_utf8(tmp_path, files):
    rejected(write(tmp_path, dict(files, **{"project.json": b"\xff\xfe" + files["project.json"]})),
             "project.json", "not UTF-8")


@pytest.mark.parametrize("change, fragment", [
    (lambda s: s["components"][0].update(x="left"), "x must be a number"),
    (lambda s: s["components"][0].update(id=[1]), "component id must be a number"),
    (lambda s: s["components"][0].update(designator={"k": SECRET}), "designator must be text"),
    (lambda s: s["components"][0].update(params=5), "params must be an object"),
    (lambda s: s["components"][2].update(params={"type": ["4/2"]}), "parameter 'type' must be text"),
    (lambda s: s["components"][2].update(params={"left": "solenoid"}), "parameter 'left' must be a list"),
    (lambda s: s["components"][2].update(params={"right": [[SECRET]]}), "parameter 'right'"),
    (lambda s: s["wires"][0].update(points=[[0, 0], [SECRET, 0]]), "point 1 x must be a number"),
    (lambda s: s["wires"][0].update(points=[[0, 0], [5]]), "point 1 must be an [x, y] pair"),
    (lambda s: s["wires"][0].update(start=[1]), "start must be [component id, terminal name]"),
    (lambda s: s["wires"][0].update(start=[1.5, "A"]), "start component must be a whole number"),
    (lambda s: s["shapes"][1].update(r=-5), "radius must not be negative"),
    (lambda s: s["shapes"][3].update(size=0), "size must be positive"),
    (lambda s: s.update(components={}), "components must be a list"),
    (lambda s: s.update(sheet=[1]), "page setup must be an object"),
    (lambda s: s.update(next_id=True), "next_id must be a number"),
], ids=lambda v: v if isinstance(v, str) else "")
def test_incorrect_field_types(tmp_path, files, change, fragment):
    rejected(write(tmp_path, edited(files, sheet_member(files), change)), fragment, "sheet '")


@pytest.mark.parametrize("member, change, fragment", [
    ("project.json", lambda h: h.update(meta=[1]), "metadata must be an object"),
    ("project.json", lambda h: h.update(settings="x"), "settings must be an object"),
    ("project.json", lambda h: h.update(layers="x"), "layer list must be a list"),
    ("project.json", lambda h: h.update(sheet_order=[1, 2]), "sheet order is invalid"),
    ("manifest.json", lambda m: m.update(sheets={"k": 1}), "sheet list is invalid"),
    ("manifest.json", lambda m: m["sheets"][0].update(path=5), "invalid sheet path"),
    ("manifest.json", lambda m: m.update(version=True), "newer version"),
])
def test_incorrect_container_types(tmp_path, files, member, change, fragment):
    rejected(write(tmp_path, edited(files, member, change)), fragment)


@pytest.mark.parametrize("change, fragment", [
    (lambda s: s["components"][0].pop("x"), "has no 'x'"),
    (lambda s: s["components"][0].pop("symbol"), "has no 'symbol'"),
    (lambda s: s["components"][0].pop("id"), "a component has no 'id'"),
    (lambda s: s["wires"][0].pop("points"), "has no 'points'"),
    (lambda s: s["shapes"][1].pop("c"), "has no 'c'"),
])
def test_missing_required_fields(tmp_path, files, change, fragment):
    rejected(write(tmp_path, edited(files, sheet_member(files), change)), fragment)


def test_missing_members(tmp_path, files):
    rejected(write(tmp_path, {k: v for k, v in files.items() if k != "project.json"}), "missing 'project.json'")
    rejected(write(tmp_path, {k: v for k, v in files.items() if k != sheet_member(files)}), "missing")


@pytest.mark.parametrize("value", [None, 5, "x", [1], [[]], [{"id": 1}]])
def test_invalid_nested_objects(tmp_path, files, value):
    def change(s):
        s["components"][1] = value
    rejected(write(tmp_path, edited(files, sheet_member(files), change)), "sheet '")


# ---------------------------------------------------------------- numbers and size limits
@pytest.mark.parametrize("text", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_non_finite_coordinates_are_rejected(tmp_path, files, text):
    member = sheet_member(files)
    raw = files[member].decode()
    obj = json.loads(raw)
    x = obj["components"][0]["x"]
    bad = raw.replace(f'"x": {json.dumps(x)}', f'"x": {text}', 1)
    assert bad != raw
    rejected(write(tmp_path, dict(files, **{member: bad.encode()})), member)


@pytest.mark.parametrize("value", ["nan", "inf", "-1e999"])
def test_non_finite_numbers_in_text_form_are_rejected(tmp_path, files, value):
    def change(s):
        s["wires"][0]["points"][0][1] = value
    rejected(write(tmp_path, edited(files, sheet_member(files), change)), "finite")


def test_non_finite_rotation_and_page_size(tmp_path, files):
    rejected(write(tmp_path, edited(files, sheet_member(files),
                                    lambda s: s["components"][0].update(rotation="inf"))), "rotation")
    res = projectio.open_any(write(tmp_path, edited(files, sheet_member(files),
                                                    lambda s: s["sheet"].update(custom_w="inf"))))
    assert res.project.sheets[0].sheet.custom_w == 420.0      # page setup stays lenient: default kept


def test_huge_integers_are_rejected(tmp_path, files):
    member = sheet_member(files)
    raw = files[member].decode()
    obj = json.loads(raw)
    bad = raw.replace(f'"next_id": {obj["next_id"]}', '"next_id": ' + "9" * 5000, 1)
    rejected(write(tmp_path, dict(files, **{member: bad.encode()})), "integer that is too large")


def test_deep_nesting_is_rejected(tmp_path, files):
    for depth in (safejson.MAX_DEPTH + 5, 100_000):
        def change(s, depth=depth):
            v = []
            for _ in range(min(depth, 900)):
                v = [v]
            s["deep"] = v
        if depth < 1000:
            path = write(tmp_path, edited(files, sheet_member(files), change))
        else:
            path = write(tmp_path, dict(files, **{sheet_member(files): b"[" * depth + b"]" * depth}))
        rejected(path, "nested too deeply")


def test_oversized_members_are_rejected_before_reading(tmp_path, files, monkeypatch):
    monkeypatch.setattr(projectio, "MAX_MEMBER_BYTES", 1000)
    rejected(write(tmp_path, files), "unreasonably large")


def test_total_size_limit(tmp_path, files, monkeypatch):
    monkeypatch.setattr(projectio, "MAX_TOTAL_BYTES", 5000)
    rejected(write(tmp_path, files), "unreasonably large")


def test_damaged_zip_member_is_reported(tmp_path, files):
    path = write(tmp_path, files)
    data = bytearray(open(path, "rb").read())
    with zipfile.ZipFile(path) as z:
        info = z.getinfo("project.json")
    start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    data[start + 5] ^= 0xFF                               # corrupt the compressed bytes
    open(path, "wb").write(bytes(data))
    rejected(path, "project.json", "damaged")


# ---------------------------------------------------------------- revision history
def objects_of(files, n):
    idx = json.loads(files["revisions/index.json"])
    e = next(e for e in idx["entries"] if e["n"] == n)
    return [e["head"]] + [s[2] for s in e["sheets"]]


def exclusive_object(files, n):
    """An object used only by revision n."""
    idx = json.loads(files["revisions/index.json"])
    others = {h for e in idx["entries"] if e["n"] != n for h in [e["head"]] + [s[2] for s in e["sheets"]]}
    return next(h for h in objects_of(files, n) if h not in others)


@pytest.mark.parametrize("damage", ["bitflip", "truncated", "not-zlib", "wrong-hash", "invalid-sheet",
                                    "non-finite", "missing", "bomb"])
def test_one_damaged_revision_object_loses_only_that_revision(tmp_path, files, damage, monkeypatch):
    h = exclusive_object(files, 3)
    name = f"revisions/objects/{h}"
    blob = files[name]
    raw = zlib.decompress(blob)
    bad = {"bitflip": blob[:-3] + bytes([blob[-3] ^ 0x55]) + blob[-2:],
           "truncated": blob[: len(blob) // 2],
           "not-zlib": b"garbage",
           "wrong-hash": zlib.compress(raw + b" "),
           "invalid-sheet": zlib.compress(b'{"components": 5}'),
           "non-finite": zlib.compress(raw.replace(b'"x":', b'"x":NaN,"_x":', 1)),
           "missing": None,
           "bomb": zlib.compress(b" " * (2 * 1024 * 1024), 9)}[damage]
    if damage == "bomb":
        monkeypatch.setattr(revisions, "MAX_OBJECT_BYTES", 1024 * 1024)
    f = {k: v for k, v in files.items() if k != name}
    if bad is not None:
        f[name] = bad
    path = write(tmp_path, f)
    before = open(path, "rb").read()
    res = projectio.open_any(path)
    st = res.project.revisions
    assert [e["n"] for e in st.entries] == [1, 2]                      # intact revisions kept
    assert res.recovered and res.needs_new_name
    msg = next(w for w in res.warnings if "revision history is damaged" in w)
    assert "revision #3 (B)" in msg and "file itself is unchanged" in msg
    for e in st.entries:
        st.load(e["n"])
    assert open(path, "rb").read() == before                          # the source is never modified


@pytest.mark.parametrize("change, fragment", [
    (lambda e: e.update(timestamp=None), "'timestamp' is not text"),
    (lambda e: e.update(n="3"), "revision number"),
    (lambda e: e.update(kind="other"), "kind"),
    (lambda e: e.update(sheets=[[None]]), "sheet reference"),
    (lambda e: e.update(sheets=None), "sheet list"),
    (lambda e: e.update(head="../../etc"), "snapshot reference"),
])
def test_damaged_index_entry_is_left_out_alone(tmp_path, files, change, fragment):
    def edit(idx):
        change(next(e for e in idx["entries"] if e["n"] == 2))
    res = projectio.open_any(write(tmp_path, edited(files, "revisions/index.json", edit)))
    assert [e["n"] for e in res.project.revisions.entries] == [1, 3] and res.recovered
    assert fragment in " ".join(res.warnings)


@pytest.mark.parametrize("index", [[], {"entries": 5}, {"entries": None}, "x"])
def test_unreadable_index_keeps_the_drawing(tmp_path, files, index):
    res = projectio.open_any(write(tmp_path, dict(files, **{"revisions/index.json": json.dumps(index).encode()})))
    assert res.project.revisions.entries == [] and res.recovered
    assert len(res.project.sheets) == 2


def test_duplicate_revision_numbers(tmp_path, files):
    res = projectio.open_any(write(tmp_path, edited(
        files, "revisions/index.json", lambda idx: idx["entries"].append(dict(idx["entries"][0])))))
    assert [e["n"] for e in res.project.revisions.entries] == [1, 2, 3]
    assert "duplicate revision number 1" in " ".join(res.warnings)


def test_unknown_index_keys_survive_a_save(tmp_path, files):
    res = projectio.open_any(write(tmp_path, edited(
        files, "revisions/index.json", lambda idx: idx["entries"][0].update(future_field={"x": 1}))))
    assert not res.recovered
    out = str(tmp_path / "out.schematix")
    projectio.save_project(res.project, out, snapshot=False)
    assert projectio.open_any(out).project.revisions.entries[0]["future_field"] == {"x": 1}


# ---------------------------------------------------------------- embedded symbols
@pytest.mark.parametrize("change", [
    lambda d: d.update(tags=True), lambda d: d.update(properties=5), lambda d: d.update(revision={}),
    lambda d: d.update(revision="1e999"), lambda d: d.update(id=None),
], ids=["tags", "properties", "revision-dict", "revision-text", "id"])
def test_damaged_embedded_symbol_is_left_out_with_a_warning(tmp_path, files, change):
    member = next(n for n in files if n.startswith("symbols/"))
    res = projectio.open_any(write(tmp_path, edited(files, member, change)))
    assert res.recovered and res.project.symbols == {}
    assert any("embedded custom symbol" in w for w in res.warnings)
    assert any("placeholders" in w for w in res.warnings)       # its component is shown as unknown
    projectio.project_bytes(res.project)                        # and the project can still be saved


# ---------------------------------------------------------------- saving non-finite values
def test_non_finite_values_are_not_saved(tmp_path):
    p = new_project("NaN")
    c = editing.place(p.sheets[0], "el.resistor.iec", 100, 100)
    path = str(tmp_path / "ok.schematix")
    projectio.save_project(p, path)
    good = open(path, "rb").read()
    entries = len(p.revisions.entries)
    c.x = float("nan")
    with pytest.raises(projectio.ProjectFormatError, match=r"not a finite number \(components\[0\]\.x\)"):
        projectio.save_project(p, path)
    assert open(path, "rb").read() == good and len(p.revisions.entries) == entries
    with pytest.raises(fileio.FileFormatError, match="not a finite number"):
        fileio.save(p.sheets[0], str(tmp_path / "x.osch"))


# ---------------------------------------------------------------- legacy drawings
@pytest.mark.parametrize("text, fragment", [
    ('{"format": "%s", "schema": 2, "components": [{"id": 1, "symbol": "x", "x": NaN, "y": 0}]}',
     "non-standard number NaN"),
    ('{"format": "%s", "schema": 2, "components": [5]}', "damaged or incomplete"),
    ('{"format": "%s", "schema": 2, "wires": [{"id": 1, "points": [[0, 0], [1e999, 0]]}]}', "too large"),
    ('{"format": "%s", "schema": 2', "not valid JSON"),
])
def test_legacy_drawings_report_damage(tmp_path, text, fragment):
    path = tmp_path / "d.osch"
    path.write_text(text % fileio.FILE_FORMAT if "%s" in text else text)
    with pytest.raises(projectio.ProjectFormatError, match=fragment):
        projectio.open_any(str(path))


# ---------------------------------------------------------------- classification
def test_programming_defects_are_not_reported_as_damaged_files(tmp_path, files, monkeypatch):
    """Only ValueError from the model readers means "damaged file"; anything
    else is a bug and must surface as itself (gui/errors.py reports it)."""
    path = write(tmp_path, files)

    def broken(d):
        raise TypeError("a bug in the reader")
    monkeypatch.setattr(model.Document, "from_dict", staticmethod(broken))
    with pytest.raises(TypeError, match="a bug in the reader"):
        projectio.open_any(path)


def test_failed_open_leaves_the_symbol_registry_unchanged(tmp_path, files):
    from openschematix.symbols.custom import to_symdef
    other = to_symdef(dict(sensor_doc(), id="user:other-project"))
    symbols.set_project_symbols([other])
    before = symbols.project_symbols()
    bad = edited(files, sheet_member(files, 1), lambda s: s["components"][0].update(x=None))
    with pytest.raises(projectio.ProjectFormatError):
        projectio.open_any(write(tmp_path, bad))
    assert symbols.project_symbols() == before


def test_error_messages_do_not_quote_file_content(tmp_path, files):
    for change in (lambda s: s["components"][0].update(x=SECRET),
                   lambda s: s["components"][0].update(label={SECRET: 1}),
                   lambda s: s["wires"][0].update(start=[SECRET, "A"]),
                   lambda s: s.update(components=SECRET)):
        rejected(write(tmp_path, edited(files, sheet_member(files), change)))
    raw = files["project.json"].decode().replace("{", '{"x": "' + SECRET + '" ', 1)
    rejected(write(tmp_path, dict(files, **{"project.json": raw.encode()})), "not valid JSON")
