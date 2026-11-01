"""Hover highlighting without full canvas redraws (Phase 4, optimization 3).

Moving the hover highlight must only recolor the canvas items of the
previously and newly hovered objects, and the result must be exactly what a
full redraw with the same hover state draws: same items, same stacking order,
same coordinates and options. Runs against the real App under a Tk display
(skipped when no display is available).
"""
import os
import tempfile

import pytest

from openschematix import editing
from openschematix.model import Shape
from openschematix.project import Layer

OPTS = ("fill", "outline", "width", "dash", "text", "font", "anchor", "angle", "capstyle", "joinstyle", "tags")


@pytest.fixture(scope="module")
def env():
    os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", tempfile.mkdtemp())
    try:
        import tkinter as tk
        root = tk.Tk()
        root.geometry("1200x800")
        root.withdraw()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Tk GUI display not available: {e}")
    from openschematix.gui.app import App
    app = App(root, check_recovery=False)
    yield root, app
    root.destroy()


@pytest.fixture
def scene(env):
    """A fresh sheet with overlapping objects of every primitive kind."""
    root, app = env
    from openschematix.project import new_project
    p = new_project("hover")
    app._reset(p, None)
    d = app.doc
    r = editing.place(d, "el.resistor.iec", 200, 200)          # lines + designator text
    r.designator = "R1"
    w = editing.add_wire(d, [(100, 200), (180, 200)])           # ends on R1 terminal 1
    w.number = "7"                                              # wire-number text
    w2 = editing.add_wire(d, [(200, 150), (200, 260)])          # crosses over R1's body (overlap)
    if not any(l.name == "Red" for l in p.layers):
        p.layers.append(Layer("Red", color="#c92a2a"))
    s_red = Shape(d.new_id(), "rect", pts=[(300, 100), (380, 100), (380, 160), (300, 160)], layer="Red")
    d.add_shape(s_red)
    s_txt = Shape(d.new_id(), "text", pts=[(300, 250)], s="NOTE", size=12)
    d.add_shape(s_txt)
    s_circ = Shape(d.new_id(), "circle", c=(450, 300), r=20, fill=True)
    d.add_shape(s_circ)
    s_fill = Shape(d.new_id(), "hatch", rings=[[(500, 100, 0.0), (560, 100, 0.0), (560, 160, 0.0),
                                               (500, 160, 0.0)]])
    d.add_shape(s_fill)
    app.selection = set()
    app.canvas.set_tool("select")
    settle(root)
    app.canvas.center_on((330, 200), zoom=2.0)
    full_redraw(root, app)
    ids = dict(r=r.id, w=w.id, w2=w2.id, red=s_red.id, txt=s_txt.id, circ=s_circ.id, fill=s_fill.id)
    return root, app, ids


def settle(root):
    """Process all pending events, including geometry (<Configure>) changes. On Windows a withdrawn
    window's geometry can be computed late, which changes the canvas size and therefore the grid."""
    root.update_idletasks()
    root.update()


def full_redraw(root, app):
    settle(root)
    app.canvas._redraw_pending = True
    app.canvas._redraw_now()


def reference_redraw(app):
    """Full redraw with the current state and WITHOUT processing events first, so the reference is drawn
    at the same canvas size as the snapshot it is compared with (processing events could apply a pending
    geometry change, which legitimately triggers its own full redraw in the application)."""
    app.canvas._redraw_pending = True
    app.canvas._redraw_now()


def snapshot(cv):
    """Canvas size and every canvas item in stacking order: type, coordinates and drawing options
    (ids excluded)."""
    out = [("canvas size", cv.winfo_width(), cv.winfo_height())]
    for cid in cv.find_all():
        opts = cv.itemconfigure(cid)
        out.append((cv.type(cid), tuple(round(v, 3) for v in cv.coords(cid)),
                    tuple((k, str(opts[k][4])) for k in OPTS if k in opts)))
    return out


def move_to(app, world):
    cv = app.canvas
    x, y = cv.to_screen(world)
    pending = cv._redraw_pending
    cv._on_motion(type("E", (), {"x": x, "y": y, "state": 0})())
    assert cv._redraw_pending == pending          # a hover change never requests a redraw


def target_point(app, key, ids):
    d = app.doc
    return {"r": (214, 198), "w": (140, 200), "w2": (200, 155), "red": (340, 100), "txt": (305, 250),
            "circ": (470, 300), "fill": (530, 130)}[key]


@pytest.fixture
def counting(monkeypatch):
    """Counts connectivity analyses and scene builds done by the canvas."""
    from openschematix.gui import canvas_view
    calls = {"analyse": 0, "scene": 0}
    real_a, real_s = canvas_view.analyse, canvas_view.scene

    def a(*args, **kw):
        calls["analyse"] += 1
        return real_a(*args, **kw)

    def s(*args, **kw):
        calls["scene"] += 1
        return real_s(*args, **kw)
    monkeypatch.setattr(canvas_view, "analyse", a)
    monkeypatch.setattr(canvas_view, "scene", s)
    return calls


def hover_items(cv, item_id):
    return list(cv._hover_index.canvas_ids(item_id))


# ---------------------------------------------------------------- transitions without redraws
def test_enter_switch_leave_recolor_without_rebuilding(scene, counting):
    root, app, ids = scene
    cv = app.canvas
    hov = app.theme["hover"]
    before = snapshot(cv)
    canvas_ids = cv.find_all()

    move_to(app, target_point(app, "w", ids))
    assert cv.hover == ids["w"] and not cv._redraw_pending
    assert hover_items(cv, ids["w"])
    assert all(cv.itemcget(c, "fill") == hov for c in hover_items(cv, ids["w"]))

    move_to(app, target_point(app, "red", ids))                # switch
    assert cv.hover == ids["red"]
    assert all(cv.itemcget(c, "outline") == hov for c in hover_items(cv, ids["red"]))
    assert all(cv.itemcget(c, "fill") != hov for c in hover_items(cv, ids["w"]))

    move_to(app, (700, 700))                                   # leave to empty space
    assert cv.hover is None
    assert snapshot(cv) == before                              # every item restored exactly

    move_to(app, target_point(app, "r", ids))
    cv._on_leave(None)                                         # pointer leaves the canvas
    assert cv.hover is None and snapshot(cv) == before

    settle(root)
    assert cv.find_all() == canvas_ids                         # nothing was recreated
    assert counting == {"analyse": 0, "scene": 0}


@pytest.mark.parametrize("key", ["w", "w2", "r", "red", "txt", "circ", "fill"])
@pytest.mark.parametrize("zoom", [0.6, 2.0, 5.0])
def test_incremental_hover_equals_full_redraw(scene, key, zoom):
    root, app, ids = scene
    cv = app.canvas
    cv.center_on((300, 220), zoom=zoom)
    full_redraw(root, app)
    move_to(app, (700, 700))
    move_to(app, target_point(app, key, ids))
    assert cv.hover == ids[key] and not cv._redraw_pending
    incremental = snapshot(cv)
    reference_redraw(app)                                      # same hover state, drawn from scratch
    assert incremental == snapshot(cv)
    move_to(app, (700, 700))
    unhovered = snapshot(cv)
    reference_redraw(app)
    assert unhovered == snapshot(cv)


def test_overlapping_objects_pick_and_restore(scene):
    root, app, ids = scene
    cv = app.canvas
    before = snapshot(cv)
    move_to(app, (200, 200))                     # wire w2 runs over the resistor body: wire wins
    assert cv.hover == ids["w2"]
    move_to(app, (200 + 9 / cv.zoom, 197))       # still on the resistor, off the wire
    assert cv.hover == ids["r"]
    incremental = snapshot(cv)
    reference_redraw(app)
    assert incremental == snapshot(cv)
    move_to(app, (700, 700))
    assert snapshot(cv) == before


def test_selected_object_keeps_selection_color(scene):
    root, app, ids = scene
    cv = app.canvas
    app.set_selection({ids["w"]})
    full_redraw(root, app)
    before = snapshot(cv)
    move_to(app, target_point(app, "w", ids))
    assert cv.hover == ids["w"]
    assert snapshot(cv) == before                # selection color has priority; nothing changes
    reference_redraw(app)
    assert snapshot(cv) == before


# ---------------------------------------------------------------- no stale highlights
def test_hover_while_redraw_pending_is_drawn_by_the_redraw(scene):
    root, app, ids = scene
    cv = app.canvas
    cv.redraw()
    assert cv._redraw_pending
    move_to(app, target_point(app, "w", ids))
    assert cv.hover == ids["w"]
    settle(root)                      # the pending redraw runs
    assert not cv._redraw_pending
    drawn = snapshot(cv)
    reference_redraw(app)
    assert drawn == snapshot(cv)
    assert cv._hover_shown == ids["w"]


def test_deleting_hovered_object_leaves_no_highlight(scene):
    root, app, ids = scene
    cv = app.canvas
    hov = app.theme["hover"]
    move_to(app, target_point(app, "w", ids))
    app.selection = {ids["w"]}
    app.delete()
    settle(root)
    assert not cv._redraw_pending
    assert ids["w"] not in app.doc.wires
    colors = {cv.itemcget(c, o) for c in cv.find_withtag("scene") for o in ("fill", "outline")
              if o in cv.itemconfigure(c)}
    assert hov not in colors
    # hovering still works afterwards. Baseline: a settled full redraw (on Windows the redraw after the
    # deletion can run during a transient re-layout of the withdrawn test window, which then reports a
    # different size without a <Configure> redraw; unrelated to hover)
    full_redraw(root, app)
    move_to(app, target_point(app, "red", ids))
    inc = snapshot(cv)
    reference_redraw(app)
    assert inc == snapshot(cv)


def test_edit_undo_tool_and_theme_changes_rebuild_hover_state(scene):
    root, app, ids = scene
    cv = app.canvas
    move_to(app, target_point(app, "r", ids))
    # editing: move the hovered component; the redraw rebuilds the item map
    s = app.begin_change()
    editing.move_items(app.doc, [ids["r"]], [], 0, 40)
    app.commit_change(s, "moved")
    settle(root)
    move_to(app, (214, 238))
    assert cv.hover == ids["r"]
    inc = snapshot(cv)
    reference_redraw(app)
    assert inc == snapshot(cv)
    # undo
    app.undo()
    settle(root)
    move_to(app, target_point(app, "red", ids))
    inc = snapshot(cv)
    reference_redraw(app)
    assert inc == snapshot(cv)
    # another tool: no hover highlight drawn; back to select
    cv.set_tool("wire")
    settle(root)
    assert cv._hover_shown is None
    cv._on_leave(None)
    cv.set_tool("select")
    settle(root)
    move_to(app, target_point(app, "circ", ids))
    inc = snapshot(cv)
    reference_redraw(app)
    assert inc == snapshot(cv)
    # theme change: hover color comes from the new theme
    old = app.settings["theme"]
    other = "dark" if old != "dark" else "light"
    try:
        app.set_theme(other)
        settle(root)
        move_to(app, (700, 700))
        move_to(app, target_point(app, "fill", ids))
        assert all(cv.itemcget(c, "fill") == app.theme["hover"] for c in hover_items(cv, ids["fill"]))
        inc = snapshot(cv)
        reference_redraw(app)
        assert inc == snapshot(cv)
    finally:
        app.set_theme(old)
        settle(root)


def test_sheet_switch_and_new_project_reset_hover(scene):
    root, app, ids = scene
    cv = app.canvas
    move_to(app, target_point(app, "w", ids))
    d2 = app.project.add_sheet("Two")
    app.doc = d2
    app.refresh(full=True)
    settle(root)
    assert not cv._hover_index.canvas_ids(ids["w"])
    hov = app.theme["hover"]
    assert all(cv.itemcget(c, "fill") != hov for c in cv.find_withtag("scene"))
