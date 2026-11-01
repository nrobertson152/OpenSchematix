"""Phase 4 performance baseline for OpenSchematix.

Usage:
    python tools/bench_phase4.py [--sizes small,medium,large] [--repeat N] [--gui] [--json OUT]

`--gui` additionally measures a real SchematicCanvas redraw (needs a display;
run under `xvfb-run -a` on headless Linux) and splits the time into the CPU
part (connectivity + scene construction) and the Tk part (canvas item creation).

All workloads are generated deterministically (ladder diagrams built from
built-in symbols, with T-junctions, crossings, wire numbers, drafting shapes
and boundary fills), so runs on the same machine are comparable.
Only the standard library is used. Prints median wall-clock times.
"""
from __future__ import annotations

import argparse
import gc
import io
import json
import os
import platform
import random
import statistics
import sys
import time
import tracemalloc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from openschematix import editing, projectio  # noqa: E402
from openschematix.connectivity import analyse  # noqa: E402
from openschematix.model import Shape, Wire  # noqa: E402
from openschematix.project import new_project  # noqa: E402
from openschematix.render import scene  # noqa: E402

# (block columns, block rows); each block is one ladder of RUNGS rungs
SIZES = {"small": (2, 2), "medium": (4, 4), "large": (8, 6), "xlarge": (12, 8)}
RUNGS = 8
BLOCK_W, RUNG_DY, BLOCK_GAP = 340, 50, 60


def build_project(cols: int, rows: int, with_fills: bool = True):
    """Deterministic ladder-diagram workload on one sheet."""
    p = new_project("Phase 4 benchmark", size="A0")
    d = p.sheets[0]
    block_h = RUNGS * RUNG_DY + 40
    for bc in range(cols):
        for br in range(rows):
            x0 = 80 + bc * (BLOCK_W + BLOCK_GAP)
            y0 = 80 + br * (block_h + BLOCK_GAP)
            ytop, ybot = y0, y0 + block_h
            # rails: rung ends land on their interior -> T-junctions
            editing.add_wire(d, [(x0, ytop), (x0, ybot)])
            editing.add_wire(d, [(x0 + 300, ytop), (x0 + 300, ybot)])
            for r in range(RUNGS):
                y = y0 + 20 + r * RUNG_DY
                k1 = editing.place(d, "el.contact.no.iec", x0 + 60, y)
                k2 = editing.place(d, "el.contact.nc.iec", x0 + 140, y)
                k3 = editing.place(d, "el.resistor.iec", x0 + 220, y)
                for a, b in ((None, k1), (k1, k2), (k2, k3), (k3, None)):
                    pa = (x0, y) if a is None else a.terminals()["2"]
                    pb = (x0 + 300, y) if b is None else b.terminals()["1"]
                    w = editing.add_wire(d, [pa, pb])
                    if w is not None and r % 2 == 0:
                        w.number = f"{bc}{br}{r}"
            # a signal bus crossing every rung (crossings, two open ends)
            editing.add_wire(d, [(x0 + 100, ytop - 10), (x0 + 100, ybot + 10)])
            # an L-shaped wire with a corner (corner candidates)
            editing.add_wire(d, [(x0 + 30, ybot + 20), (x0 + 270, ybot + 20), (x0 + 270, ybot + 40)])
            # drafting: frame, label, and a boundary fill inside the frame
            d.add_shape(Shape(d.new_id(), "rect", pts=[(x0 - 20, ytop - 30), (x0 + 320, ytop - 30),
                                                        (x0 + 320, ybot + 50), (x0 - 20, ybot + 50)]))
            d.add_shape(Shape(d.new_id(), "text", pts=[(x0, ytop - 40)], s=f"Block {bc}.{br}", size=10))
            if with_fills:
                d.add_shape(Shape(d.new_id(), "hatch", rings=[[(x0 + 310, ytop, 0.0), (x0 + 318, ytop, 0.0),
                                                               (x0 + 318, ytop + 8, 0.0),
                                                               (x0 + 310, ytop + 8, 0.0)]]))
    return p, d


def timed(fn, repeat):
    out = []
    for _ in range(repeat):
        gc.collect()
        t = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t)
    return statistics.median(out), min(out)


def peak_kib(fn):
    gc.collect()
    tracemalloc.start()
    fn()
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1024


class _SnapHost:
    """Minimal stand-in for SchematicCanvas.object_snap/_terminal_near (they only use .doc and .zoom)."""

    def __init__(self, doc, zoom=1.0):
        self.doc, self.zoom = doc, zoom


def sample_points(d, n, seed=7):
    rnd = random.Random(seed)
    b = d.bbox()
    return [(rnd.uniform(b[0], b[2]), rnd.uniform(b[1], b[3])) for _ in range(n)]


def bench_core(name, repeat):
    from openschematix.boundary_fill import find_region
    from openschematix.editing import crossings
    from openschematix.gui import canvas_view as cv_mod  # importing tkinter only; no display needed

    cols, rows = SIZES[name]
    p, d = build_project(cols, rows)
    conn = analyse(d)
    res = {
        "size": name, "components": len(d.components), "wires": len(d.wires), "shapes": len(d.shapes),
        "wire_segments": sum(len(w.points) - 1 for w in d.wires.values()),
        "junctions": len(conn.junctions), "open_wire_ends": len(conn.open_wire_ends),
        "crossings": len(crossings(d)),
    }
    res["analyse_s"] = timed(lambda: analyse(d), repeat)[0]
    res["crossings_s"] = timed(lambda: crossings(d), repeat)[0]
    res["scene_given_conn_s"] = timed(lambda: scene(d, screen=True, conn=conn, project=p), repeat)[0]
    res["scene_full_s"] = timed(lambda: scene(d, screen=True, conn=analyse(d), project=p), repeat)[0]
    res["scene_items"] = len(scene(d, screen=True, conn=conn, project=p))

    pts = sample_points(d, 50)
    host = _SnapHost(d, zoom=1.0)
    res["hit_test_ms"] = 1000 * timed(lambda: [editing.hit_test(d, q, 6.0) for q in pts], repeat)[0] / len(pts)
    res["object_snap_ms"] = 1000 * timed(
        lambda: [cv_mod.SchematicCanvas.object_snap(host, q) for q in pts], repeat)[0] / len(pts)
    res["terminal_near_ms"] = 1000 * timed(
        lambda: [cv_mod.SchematicCanvas._terminal_near(host, q) for q in pts], repeat)[0] / len(pts)
    b = d.bbox()
    rect = (b[0], b[1], (b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    res["items_in_rect_ms"] = 1000 * timed(lambda: editing.items_in_rect(d, rect), repeat)[0]

    # undo snapshot taken on every press in the select tool (App.begin_change)
    res["snapshot_ms"] = 1000 * timed(
        lambda: json.dumps({"p": p.to_dict(), "active": d.uid}, sort_keys=True), repeat)[0]

    # boundary fill: pick inside the first block frame (all sheet shapes are candidates, as in cmd_fill)
    shapes = list(d.shapes.values())
    first = next(s for s in shapes if s.kind == "rect")
    pick = (first.pts[0][0] + 5, first.pts[0][1] + 5)
    fr = find_region(shapes, pick)
    res["fill_ok"] = fr.ok
    res["fill_s"] = timed(lambda: find_region(shapes, pick), max(1, repeat // 2))[0]

    # persistence: bytes (serialise), verify (re-read), full save (incl. revision snapshot + fsync), load
    import tempfile
    res["project_bytes_s"] = timed(lambda: projectio.project_bytes(p), repeat)[0]
    data = projectio.project_bytes(p)
    res["file_kib"] = len(data) / 1024
    res["verify_s"] = timed(lambda: projectio._verify(data), repeat)[0]
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "bench.schematix")
    res["save_s"] = timed(lambda: projectio.save_project(p, path, snapshot=True), max(1, repeat // 2))[0]
    res["load_s"] = timed(lambda: projectio.open_any(path), repeat)[0]

    res["peak_kib_analyse"] = peak_kib(lambda: analyse(d))
    res["peak_kib_scene"] = peak_kib(lambda: scene(d, screen=True, conn=conn, project=p))
    res["peak_kib_save"] = peak_kib(lambda: projectio.save_project(p, path, snapshot=False))
    res["peak_kib_load"] = peak_kib(lambda: projectio.open_any(path))
    return res


def bench_gui(name, repeat):
    """Real SchematicCanvas redraw inside a real App window."""
    import tkinter as tk

    os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", __import__("tempfile").mkdtemp())
    from openschematix.gui import canvas_view as cv_mod
    from openschematix.gui.app import App

    cols, rows = SIZES[name]
    p, d = build_project(cols, rows)
    root = tk.Tk()
    root.geometry("1600x1000")
    app = App(root, check_recovery=False)
    app._reset(p, None)
    root.update()
    cv = app.canvas
    cv.fit_drawing()
    root.update()

    def full():
        cv._redraw_pending = True
        cv._redraw_now()
        root.update_idletasks()

    res = {"size": name, "canvas_px": (cv.winfo_width(), cv.winfo_height())}
    res["redraw_fit_s"] = timed(full, repeat)[0]
    res["canvas_items_fit"] = len(cv.find_all())

    # split CPU vs Tk by timing the pieces of _redraw_now with the same inputs
    conn = analyse(d)
    items = scene(d, screen=app.settings["show_markers"], conn=conn, project=p)
    res["cpu_analyse_s"] = timed(lambda: analyse(d), repeat)[0]
    res["cpu_scene_s"] = timed(lambda: scene(d, screen=True, conn=conn, project=p), repeat)[0]

    def tk_only():
        cv.delete("all")
        cv_mod.draw_items(cv, items, cv.to_screen, cv.zoom, app.theme, cv.font_family, selected=app.selection)
        root.update_idletasks()
    res["tk_draw_items_s"] = timed(tk_only, repeat)[0]

    # zoomed in to ~1/16 of the drawing: everything off-screen is still created
    b = d.bbox()
    cv.center_on(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), zoom=cv.zoom * 4)
    root.update()
    res["redraw_zoom4_s"] = timed(full, repeat)[0]
    res["canvas_items_zoom4"] = len(cv.find_all())

    # hover transitions in the select tool: alternate between two wires (enter A / switch to B / back),
    # then leave to empty space; each motion is a real hover change, and pending idle work is run
    ws = list(d.wires.values())
    mids = []
    for w in (ws[0], ws[len(ws) // 2]):
        a, bpt = cv.to_screen(w.points[0]), cv.to_screen(w.points[1])
        mids.append(((a[0] + bpt[0]) / 2, (a[1] + bpt[1]) / 2))
    empty = cv.to_screen((b[2] + 500, b[3] + 500))

    def ev(p):
        return type("E", (), {"x": p[0], "y": p[1], "state": 0})()
    cv._on_motion(ev(empty))
    root.update_idletasks()
    state = {"i": 0}

    def hover_switch():
        state["i"] ^= 1
        cv._on_motion(ev(mids[state["i"]]))
        root.update_idletasks()
    res["hover_change_redraw_s"] = timed(hover_switch, repeat)[0]

    def hover_leave():
        cv._on_motion(ev(mids[0]))
        root.update_idletasks()
        t = time.perf_counter()
        cv._on_motion(ev(empty))
        root.update_idletasks()
        return time.perf_counter() - t
    res["hover_leave_s"] = statistics.median(hover_leave() for _ in range(repeat))
    # the motion handler's own hit test (paid on every motion, hover change or not)
    w0 = cv.to_world(*mids[0])
    res["hover_hit_test_s"] = timed(lambda: editing.hit_test(d, w0, cv_mod.PICK_PX / cv.zoom, cv.selectable),
                                    repeat)[0]
    # peak Python memory of a full redraw (scene, connectivity and, on newer code, the hover item map)
    gc.collect()
    tracemalloc.start()
    full()
    res["redraw_peak_kib"] = tracemalloc.get_traced_memory()[1] / 1024
    tracemalloc.stop()
    res["hover_index_items"] = len(getattr(getattr(cv, "_hover_index", None), "cids", ()))
    root.destroy()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="small,medium,large")
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--gui", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    env = {"python": platform.python_version(), "platform": platform.platform(), "cpu_count": os.cpu_count()}
    try:
        import tkinter
        env["tk"] = tkinter.TkVersion
    except ImportError:
        env["tk"] = None
    out = {"env": env, "core": [], "gui": []}
    for s in a.sizes.split(","):
        r = bench_core(s, a.repeat)
        out["core"].append(r)
        print(json.dumps(r), flush=True)
        if a.gui:
            g = bench_gui(s, a.repeat)
            out["gui"].append(g)
            print(json.dumps(g), flush=True)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
