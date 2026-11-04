"""Wire attachments to custom-symbol pins survive every way a project is rebuilt (audit finding F1).

A wire end attached to a component terminal stores [component id, pin id]. Sheets used to be validated
against the process-wide symbol registry *before* the project's embedded symbols were registered, so every
attachment to a custom-symbol pin was silently dropped when the project was opened on a computer without
that symbol in its library, on redo, on undo of a symbol update, or while another project was active.
The drawing looked unchanged (connectivity is geometric), but the next move left the wires behind.

These tests check real connectivity (nets, open terminals) and what happens when the component is moved
afterwards, not just the stored references. The GUI paths (undo/redo of Import sheets and Update symbol
from library) are in tests/test_custom_symbol_refs_gui.py.
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap
import zipfile

import pytest

from openschematix import connectivity, editing, netlist, projectio, symbols
from openschematix.geometry import same
from openschematix.model import Document
from openschematix.project import Project, new_project
from openschematix.revisions import restore
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef

ROOT = os.path.join(os.path.dirname(__file__), "..")
PINS = {"pA": (-20, 0, "l"), "pB": (20, 0, "r")}


# ---------------------------------------------------------------- helpers
def sensor(pins=("pA", "pB"), revision=0, sid=None, name="Sensor"):
    d = blank_symbol(name)
    if sid:
        d["id"] = sid
    d["revision"] = revision
    d["prims"] = [{"k": "line", "pts": [[-20, 0], [20, 0]]}]
    d["pins"] = [{"id": p, "name": p[-1], "x": PINS[p][0], "y": PINS[p][1], "dir": PINS[p][2]} for p in pins]
    return normalise(d)


def fresh_process():
    """What a newly started program has: no project symbols, an empty user library."""
    symbols.set_project_symbols([])
    symbols.set_user_symbols([])


def wired_project(sdoc, pin="pB"):
    """Custom sensor B1 wired from `pin` to terminal 1 of a built-in block U1, made the way the editor does."""
    p = new_project("refs")
    p.symbols[sdoc["id"]] = sdoc
    p.activate_symbols()
    s = p.sheets[0]
    c = editing.place(s, sdoc["id"], 100, 100)
    u = editing.place(s, "gen.block2", 300, 100)
    w = editing.add_wire(s, [c.terminals()[pin], u.terminals()["1"]])
    assert (w.start, w.end) == ([c.id, pin], [u.id, "1"])
    return p, c.id, u.id, w.id


def refs(project):
    return sorted((d.uid, w.id, tuple(w.start or ()), tuple(w.end or ())) for d in project.sheets
                  for w in d.wires.values())


def net_terminals(project, uid, cid, pin):
    """Terminals on the same net as (cid, pin), as (component designator, terminal)."""
    for n in netlist.compute_nets(project):
        if (uid, cid, pin) in n.terminals:
            doc = project.find_sheet(uid)
            return sorted((doc.components[c].designator, t) for _u, c, t in n.terminals)
    return []


def assert_connected_and_follows(project, cid, uid_comp, wid, pin="pB"):
    """The sensor is on the net with U1, and moving it drags the wire end along (stays on the net)."""
    s = project.sheets[0]
    sensor_des, u_des = s.components[cid].designator, s.components[uid_comp].designator
    assert net_terminals(project, s.uid, cid, pin) == sorted([(sensor_des, pin), (u_des, "1")])
    for dx, dy in ((0, 20), (40, 0), (0, -60)):
        editing.move_items(s, [cid], [], dx, dy)
        w = s.wires[wid]
        assert w.start == [cid, pin], "the wire must stay attached after the move"
        assert same(w.points[0], s.components[cid].terminals()[pin]), "the wire end must follow the pin"
        assert net_terminals(project, s.uid, cid, pin) == sorted([(sensor_des, pin), (u_des, "1")])
        assert (cid, pin) not in {(c, n) for c, n, _p in connectivity.analyse(s).open_terminals}


def save(project, path):
    projectio.save_project(project, str(path))
    return str(path)


def strip_embedded_symbols(src, dst):
    """Copy a .schematix file without its embedded symbol definitions (as if they were lost)."""
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in zi.namelist():
            if n.startswith("symbols/"):
                continue
            data = zi.read(n)
            if n == "manifest.json":
                m = json.loads(data)
                m["symbols"] = []
                data = json.dumps(m).encode()
            zo.writestr(zi.getinfo(n) if n == "mimetype" else n, data)
    return str(dst)


# ---------------------------------------------------------------- opening a file
def test_reopen_without_installed_symbol_keeps_connections_and_movement(tmp_path):
    sdoc = sensor()
    p, cid, uid_comp, wid = wired_project(sdoc)
    path = save(p, tmp_path / "p.schematix")
    before = refs(p)
    fresh_process()                                     # e.g. the file opened on another computer
    q = projectio.open_any(path).project
    assert refs(q) == before
    assert_connected_and_follows(q, cid, uid_comp, wid)
    # ... and the attachments are still there after saving and opening again
    path2 = save(q, tmp_path / "p2.schematix")
    fresh_process()
    r = projectio.open_any(path2).project
    assert r.sheets[0].wires[wid].start == [cid, "pB"]


def test_project_from_dict_does_not_need_registered_symbols():
    sdoc = sensor()
    p, cid, uid_comp, wid = wired_project(sdoc)
    d = p.to_dict()
    fresh_process()
    q = Project.from_dict(d)                            # the registry knows nothing about the sensor
    assert refs(q) == refs(p)
    assert symbols.project_symbols() == {}, "reading a project must not register its symbols"


def test_another_projects_symbol_version_does_not_leak_into_a_load(tmp_path):
    sid = "user:0123456789abcdef"
    p_b, cid, uid_comp, wid = wired_project(sensor(sid=sid, revision=1))      # B: sensor with pins pA, pB
    path_b = save(p_b, tmp_path / "b.schematix")
    p_a = new_project("A")                                                    # A: same id, pB removed
    p_a.symbols[sid] = sensor(("pA",), sid=sid, revision=2)
    p_a.activate_symbols()
    q = projectio.open_any(path_b, activate=False).project                    # read B while A is open
    assert q.sheets[0].wires[wid].start == [cid, "pB"]
    assert symbols.project_symbols()[sid].custom["revision"] == 2, "A must stay the active project"
    q = projectio.open_any(path_b).project                                    # open B for editing
    assert symbols.project_symbols()[sid].custom["revision"] == 1
    assert_connected_and_follows(q, cid, uid_comp, wid)


def test_snapshot_restore_round_trip_keeps_project_only_symbols():
    """The undo/redo snapshot (App.snapshot / App._restore) of a state whose symbol is not registered."""
    p0 = new_project()
    p0.activate_symbols()
    before = json.dumps(p0.to_dict(), sort_keys=True)
    p, cid, uid_comp, wid = wired_project(sensor())
    after = json.dumps(p.to_dict(), sort_keys=True)
    q = Project.from_dict(json.loads(before))           # undo: the sensor is unregistered again
    q.activate_symbols()
    assert symbols.get(p.sheets[0].components[cid].symbol) is None
    r = Project.from_dict(json.loads(after))            # redo
    r.activate_symbols()
    assert refs(r) == refs(p)
    assert_connected_and_follows(r, cid, uid_comp, wid)


def test_snapshot_restore_of_older_symbol_version():
    """Undo of a symbol update: the registered (newer) version lacks the pin the older drawing uses."""
    sid = "user:00000000000000aa"
    p, cid, uid_comp, wid = wired_project(sensor(sid=sid, revision=0))
    before = json.dumps(p.to_dict(), sort_keys=True)
    symbols.add_project_symbol(to_symdef(sensor(("pA",), sid=sid, revision=1)))
    q = Project.from_dict(json.loads(before))
    q.activate_symbols()
    assert q.sheets[0].wires[wid].start == [cid, "pB"]
    assert_connected_and_follows(q, cid, uid_comp, wid)


def test_revision_restore_keeps_attachments_of_an_older_symbol_version():
    sid = "user:00000000000000bb"
    p, cid, uid_comp, wid = wired_project(sensor(sid=sid, revision=0))
    from openschematix.revisions import RevisionStore
    p.revisions = RevisionStore()
    n = p.revisions.create(p, "approved", label="A")["n"]
    # the project moves on to a symbol version without pB (the wire is detached, as the GUI reports)
    p.symbols[sid] = sensor(("pA",), sid=sid, revision=1)
    p.activate_symbols()
    editing.sync_wire_ends(p.sheets[0])
    assert p.sheets[0].wires[wid].start is None
    q = restore(p, p.revisions, n)
    q.activate_symbols()
    assert q.sheets[0].wires[wid].start == [cid, "pB"]
    assert_connected_and_follows(q, cid, uid_comp, wid)


def test_duplicate_sheet_keeps_custom_attachments():
    p, cid, uid_comp, wid = wired_project(sensor())
    dup = p.duplicate_sheet(p.sheets[0].uid)
    fresh_process()                                     # Document.copy uses the project's own symbols
    dup2 = p.duplicate_sheet(p.sheets[0].uid)
    for d in (dup, dup2):
        assert d.wires[wid].start == [cid, "pB"]


# ---------------------------------------------------------------- symbols that are not available at all
def test_missing_symbol_keeps_attachments_until_it_is_installed(tmp_path):
    sdoc = sensor()
    p, cid, uid_comp, wid = wired_project(sdoc)
    path = strip_embedded_symbols(save(p, tmp_path / "p.schematix"), tmp_path / "lost.schematix")
    fresh_process()
    res = projectio.open_any(path)
    q, s = res.project, res.project.sheets[0]
    assert any(sdoc["id"] in w for w in res.warnings), res.warnings      # shown as a placeholder
    assert s.wires[wid].start == [cid, "pB"]
    # editing elsewhere on the sheet (moving U1 re-syncs every wire) must not drop the reference
    editing.move_items(s, [uid_comp], [], 0, 20)
    editing.sync_wire_ends(s)
    assert s.wires[wid].start == [cid, "pB"]
    path2 = save(q, tmp_path / "edited.schematix")
    # once the symbol is installed the connection is intact and works again
    fresh_process()
    symbols.set_user_symbols([to_symdef(sdoc)])
    r = projectio.open_any(path2).project
    w = r.sheets[0].wires[wid]
    assert w.start == [cid, "pB"]
    editing.move_items(r.sheets[0], [cid], [], 0, 20)
    assert same(r.sheets[0].wires[wid].points[0], r.sheets[0].components[cid].terminals()["pB"])


def test_certainly_dangling_references_are_still_dropped():
    p, cid, uid_comp, wid = wired_project(sensor())
    d = p.sheets[0].to_dict()
    for wd in d["wires"]:
        wd["start"], wd["end"] = [cid, "pZ"], [uid_comp, "9"]           # pins that do not exist
    doc = Document.from_dict(d, resolve=p.symbol_resolver())
    assert (doc.wires[wid].start, doc.wires[wid].end) == (None, None)
    for wd in d["wires"]:
        wd["start"], wd["end"] = [999, "pA"], None                       # no such component
    assert Document.from_dict(d).wires[wid].start is None


def test_unbuildable_embedded_symbol_does_not_block_opening(tmp_path):
    p, cid, uid_comp, wid = wired_project(sensor())
    d = p.to_dict()
    d["symbols"][p.sheets[0].components[cid].symbol]["pins"][0]["x"] = 7     # off the pin grid: invalid
    fresh_process()
    q = Project.from_dict(d)
    assert q.sheets[0].wires[wid].start == [cid, "pB"]                     # unverifiable: kept
    assert q.activate_symbols(), "a warning names the damaged symbol"


# ---------------------------------------------------------------- compatibility
@pytest.mark.parametrize("name", sorted(os.listdir(os.path.join(ROOT, "examples"))))
def test_example_files_round_trip_unchanged(name, tmp_path):
    path = os.path.join(ROOT, "examples", name)
    res = projectio.open_any(path)
    stored = []
    for d in res.project.sheets:
        stored += [(w.start, w.end) for w in d.wires.values()]
    assert any(a or b for a, b in stored), "example should contain attached wires"
    if name.endswith(projectio.PROJECT_EXTENSION):
        with zipfile.ZipFile(path) as z:
            on_disk = {n: json.loads(z.read(n)) for n in z.namelist() if n.startswith("sheets/")}
        out = save(res.project, tmp_path / name)
        with zipfile.ZipFile(out) as z:
            again = {n: json.loads(z.read(n)) for n in z.namelist() if n.startswith("sheets/")}
            manifest = json.loads(z.read("manifest.json"))
        keys = ("uid", "next_id", "components", "wires", "shapes")     # (the sheet setup gains new
        assert ({n: {k: s.get(k) for k in keys} for n, s in again.items()} ==  # defaults such as
                {n: {k: s.get(k) for k in keys} for n, s in on_disk.items()})  # drawing_status, #29)
        assert (manifest["version"], manifest["sheet_schema"]) == (1, 2)


def _legacy_tree(tmp_path_factory):
    if shutil.which("git") is None or not os.path.isdir(os.path.join(ROOT, ".git")):
        pytest.skip("git checkout not available")
    if subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "-q", "v1.0.0^{commit}"],
                      capture_output=True).returncode != 0:
        pytest.skip("tag v1.0.0 not available in this clone")
    dest = tmp_path_factory.mktemp("legacy_refs")
    arch = subprocess.run(["git", "-C", ROOT, "archive", "v1.0.0", "openschematix"], capture_output=True, check=True)
    (dest / "pkg.tar").write_bytes(arch.stdout)
    subprocess.run(["tar", "-xf", str(dest / "pkg.tar"), "-C", str(dest)], check=True)
    return dest


LEGACY_WRITE = textwrap.dedent("""
    import json, sys
    sys.path.insert(0, sys.argv[1])
    from openschematix import editing, projectio
    from openschematix.project import new_project
    d = json.loads(sys.argv[3])
    p = new_project()
    p.symbols[d["id"]] = d
    p.activate_symbols()
    s = p.sheets[0]
    c = editing.place(s, d["id"], 100, 100)
    u = editing.place(s, "gen.block2", 300, 100)
    w = editing.add_wire(s, [c.terminals()["pB"], u.terminals()["1"]])
    projectio.save_project(p, sys.argv[2])
    print(json.dumps([c.id, u.id, w.id, w.start, w.end]))
""")

LEGACY_READ = textwrap.dedent("""
    import json, sys
    sys.path.insert(0, sys.argv[1])
    from openschematix import projectio
    p = projectio.open_any(sys.argv[2]).project
    print(json.dumps([len(p.sheets), sorted(p.symbols)]))
""")


def test_files_written_by_1_0_0_keep_custom_attachments(tmp_path_factory, tmp_path):
    legacy = _legacy_tree(tmp_path_factory)
    sdoc = sensor()
    path = tmp_path / "old.schematix"
    r = subprocess.run([sys.executable, "-I", "-c", LEGACY_WRITE, str(legacy), str(path), json.dumps(sdoc)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    cid, uid_comp, wid, start, end = json.loads(r.stdout)
    assert start == [cid, "pB"]
    fresh_process()
    q = projectio.open_any(str(path)).project
    assert q.sheets[0].wires[wid].start == [cid, "pB"]
    assert_connected_and_follows(q, cid, uid_comp, wid)


def test_files_written_here_open_in_1_0_0(tmp_path_factory, tmp_path):
    legacy = _legacy_tree(tmp_path_factory)
    sdoc = sensor()
    p, *_ = wired_project(sdoc)
    path = save(p, tmp_path / "new.schematix")
    r = subprocess.run([sys.executable, "-I", "-c", LEGACY_READ, str(legacy), path],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [1, [sdoc["id"]]]
