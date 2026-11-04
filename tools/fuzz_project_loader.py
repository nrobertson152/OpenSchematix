"""Robustness fuzz for the project-file loader.

Mutates every JSON node of real project files (wrong types, missing keys,
non-finite numbers, oversized values), plus container-level damage
(truncated or non-UTF-8 members, deep nesting, damaged revision objects),
and classifies what happens:

  rejected  open_any raised ProjectFormatError / OSError (expected for bad input)
  opened    the file opened and every follow-up operation worked
  LEAK      open_any raised any other exception (the bug class this guards)
  LATENT    the file opened but a normal operation then crashed: Check,
            netlist, BOM, SVG/PDF export, restoring a revision, saving

    python tools/fuzz_project_loader.py [repo] [--limit N] [--seed S] [-v]

Exit status 1 if any LEAK or LATENT outcome was found.
"""
import argparse
import collections
import io
import json
import os
import random
import sys
import tempfile
import traceback
import zipfile
import zlib

ap = argparse.ArgumentParser()
ap.add_argument("repo", nargs="?", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ap.add_argument("--limit", type=int, default=4000, help="maximum number of node mutations")
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("-v", "--verbose", action="store_true")
ap.add_argument("--dump", help="write every mutation's outcome to this JSON file (to compare versions)")
args = ap.parse_args()
sys.path.insert(0, os.path.abspath(args.repo))

from openschematix import bom, check, editing, export, netlist, projectio, revisions, symbols  # noqa: E402
from openschematix.model import Shape, Wire  # noqa: E402
from openschematix.project import new_project  # noqa: E402
from openschematix.symbols.custom import blank_symbol, normalise, to_symdef  # noqa: E402

FORMAT_ERRORS = (projectio.ProjectFormatError, OSError)


# ---------------------------------------------------------------- seed projects
def rich_project() -> bytes:
    """A project using every serialised feature: components with params,
    props and terminal labels, wires with refs and numbers, every shape kind,
    an embedded custom symbol, layers, and approved + automatic revisions."""
    p = new_project("Fuzz seed")
    d = blank_symbol("Fuzz sensor")
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "A", "name": "A", "x": -20, "y": 0, "dir": "l"},
                 {"id": "B", "name": "B", "x": 20, "y": 0, "dir": "r"}]
    sdoc = normalise(d)
    symbols.add_project_symbol(to_symdef(sdoc))
    doc = p.sheets[0]
    k = editing.place(doc, "el.coil.iec", 200, 200)
    k.props.update(part_number="K-1", rating="24 V")
    k.terminal_labels["A1"] = "13"
    v = editing.place(doc, "fl.hyd.dcv", 400, 200)
    s = editing.place(doc, sdoc["id"], 600, 200)
    w = Wire(doc.new_id(), [k.terminals()["A2"], s.terminals()["A"]], [k.id, "A2"], [s.id, "A"])
    doc.add_wire(w)
    editing.reroute(doc, w)
    w.number, w.number_manual = "101", True
    editing.add_wire(doc, [(100, 400), (300, 400), (300, 500)], style="dashed")
    for sh in (Shape(0, "line", pts=[(0, 0), (50, 0)], arrow_end=True),
               Shape(0, "polygon", pts=[(0, 0), (50, 0), (50, 50)], fill=True),
               Shape(0, "circle", c=(100, 100), r=20), Shape(0, "arc", c=(100, 100), r=30, start=10, extent=80),
               Shape(0, "text", pts=[(10, 10)], s="Note", size=12, angle=90),
               Shape(0, "hatch", rings=[[(0, 0, 0), (40, 0, 0), (40, 40, 0), (0, 40, 0)]])):
        sh.id = doc.new_id()
        doc.add_shape(sh)
    v.layer = "Notes"
    p.add_sheet("Second").sheet.drawing_status = "Preliminary"
    p.embed_symbols()
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "approved", label="A", description="First issue")
    editing.place(p.sheets[1], "el.resistor.iec", 100, 100)
    p.revisions.create(p, "auto", description="Saved")
    data = projectio.project_bytes(p)
    symbols.set_project_symbols([])
    return data


def seeds() -> dict:
    out = {"rich": rich_project()}
    demo = os.path.join(args.repo, "examples", "demo_project.schematix")
    with open(demo, "rb") as f:
        out["demo"] = f.read()
    return out


# ---------------------------------------------------------------- container helpers
def members(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def pack(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in files.items():
            z.writestr(n, b)
    return buf.getvalue()


# ---------------------------------------------------------------- JSON node mutations
INF = float("inf")
BAD_VALUES = [None, True, -1, 0, 1.5, "x", [], {}, [None], {"k": 1}, [[1, 2]], INF, -INF, float("nan"),
              10 ** 400, "1e999"]


def nodes(obj, path=()):
    yield path, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from nodes(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from nodes(v, path + (i,))


def replaced(obj, path, new):
    if not path:
        return new
    obj = json.loads(json.dumps(obj))
    cur = obj
    for p in path[:-1]:
        cur = cur[p]
    if new is DELETE:
        del cur[path[-1]]
    else:
        cur[path[-1]] = new
    return obj


DELETE = object()


def json_mutations(files: dict):
    for name, raw in files.items():
        if not name.endswith((".json", ".osym")):
            continue
        doc = json.loads(raw)
        for path, val in nodes(doc):
            options = list(BAD_VALUES)
            if path and isinstance(path[-1], str):
                options.append(DELETE)
            for new in options:
                if new is not DELETE and type(new) is type(val) and new == val:
                    continue
                label = f"{name}:{'/'.join(map(str, path)) or '<root>'}={'<del>' if new is DELETE else repr(new)[:12]}"
                text = json.dumps(replaced(doc, path, new))
                yield label, dict(files, **{name: text.encode()})


def container_mutations(files: dict):
    for name, raw in files.items():
        if name == "mimetype":
            continue
        if name.endswith(".json") or name.endswith(".osym"):
            for frac in (0, 0.25, 0.5, 0.9):
                yield f"{name}:truncated-{frac}", dict(files, **{name: raw[:int(len(raw) * frac)]})
            yield f"{name}:not-utf8", dict(files, **{name: b"\xff\xfe" + raw})
            yield f"{name}:deep-nesting", dict(files, **{name: b"[" * 100000 + b"]" * 100000})
            yield f"{name}:nested-500", dict(files, **{name: json.dumps(
                json.loads(raw) if not isinstance(json.loads(raw), dict) else dict(json.loads(raw), deep=nest(500))).encode()})
        elif name.startswith("revisions/objects/"):
            yield f"{name}:bitflip", dict(files, **{name: raw[:-3] + bytes([raw[-3] ^ 0x55]) + raw[-2:]})
            yield f"{name}:truncated", dict(files, **{name: raw[: len(raw) // 2]})
            yield f"{name}:not-zlib", dict(files, **{name: b"garbage"})
            yield f"{name}:wrong-content", dict(files, **{name: zlib.compress(b'{"sheets": 5}')})
            yield f"{name}:non-finite", dict(files, **{name: zlib.compress(
                zlib.decompress(raw).replace(b'"x":', b'"x":Infinity,"_x":', 1))})
            yield f"{name}:bomb", dict(files, **{name: zlib.compress(b" " * (300 * 1024 * 1024), 9)})
        if name.startswith("revisions/") or name.startswith("symbols/") or name.startswith("sheets/"):
            yield f"{name}:missing", {k: v for k, v in files.items() if k != name}


def nest(n):
    v = []
    for _ in range(n):
        v = [v]
    return v


# ---------------------------------------------------------------- outcome
def exercise(res) -> None:
    """Normal operations a user can run on an opened project."""
    p = res.project
    check.check(p)
    netlist.compute_nets(p)
    bom.generate(p)
    netlist.assign_wire_numbers(p, True)
    for doc in p.sheets:
        export.to_svg(doc, project=p)
    export.project_pdf(p)
    for e in list(p.revisions.entries):
        p.revisions.load(e["n"])
    projectio.read_zip(io.BytesIO(projectio.project_bytes(p)))


OUTCOMES = {}


def run(label: str, data: bytes, tmp: str, stats, examples):
    before = dict(stats)
    _run(label, data, tmp, stats, examples)
    OUTCOMES[label] = next(k for k in stats if stats[k] != before.get(k, 0))


def _run(label: str, data: bytes, tmp: str, stats, examples):
    path = os.path.join(tmp, "m.schematix")
    with open(path, "wb") as f:
        f.write(data)
    symbols.set_project_symbols([])
    try:
        res = projectio.open_any(path)
    except FORMAT_ERRORS:
        stats["rejected"] += 1
        return
    except BaseException as e:  # noqa: BLE001 - classifying is the point
        key = f"LEAK {type(e).__name__}"
        stats[key] += 1
        examples.setdefault(key, (label, traceback.format_exc(limit=-3)))
        return
    try:
        exercise(res)
    except BaseException as e:  # noqa: BLE001
        key = f"LATENT {type(e).__name__}"
        stats[key] += 1
        examples.setdefault(key, (label, traceback.format_exc(limit=-3)))
        return
    stats["opened"] += 1


def main():
    rnd = random.Random(args.seed)
    stats, examples = collections.Counter(), {}
    with tempfile.TemporaryDirectory() as tmp:
        for seed_name, data in seeds().items():
            files = members(data)
            muts = list(json_mutations(files))
            rnd.shuffle(muts)
            share = args.limit // 2
            for label, f in muts[:share]:
                run(f"{seed_name}/{label}", pack(f), tmp, stats, examples)
            for label, f in container_mutations(files):
                run(f"{seed_name}/{label}", pack(f), tmp, stats, examples)
    if args.dump:
        with open(args.dump, "w") as f:
            json.dump(OUTCOMES, f, indent=0, sort_keys=True)
    total = sum(stats.values())
    print(f"{total} mutated files")
    for k, v in sorted(stats.items()):
        print(f"  {k:28s} {v}")
    for k, (label, tb) in sorted(examples.items()):
        print(f"\n{k}: e.g. {label}")
        if args.verbose:
            print(tb)
        else:
            print("   " + tb.strip().splitlines()[-1][:200])
    return 1 if any(k.startswith(("LEAK", "LATENT")) for k in stats) else 0


if __name__ == "__main__":
    sys.exit(main())
