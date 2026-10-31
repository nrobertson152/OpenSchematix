"""Interactive CAD commands (LINE, CIRCLE, MOVE, TRIM, …).

The commands are generators driven by interact.CommandRunner. They only use
a small set of hooks on the host, so the same command code runs in the
schematic editor and in the symbol editor:

    host.doc                    object with .shapes, .new_id(), .add_shape()
    host.selection              set of selected ids
    host.sel_bbox(ids)          bounding box of objects
    host.sel_ghost(ids, fn)     preview prims of objects transformed by fn(shape-like op)
    host.sel_move(ids, dx, dy)  host.sel_copy(ids, dx, dy) -> new ids
    host.sel_rotate(ids, center, deg_ccw) -> str|None (error)
    host.sel_scale(ids, center, k) -> str|None
    host.sel_mirror(ids, p, q) -> str|None
    host.sel_delete(ids)
    host.new_shape_layer()      layer for new drafting shapes
    host.set_selection(ids)

Optional hooks: host.fill_boundary_shapes() (shapes that may bound a FILL;
default: all drafting shapes), host.settings (FILL gap tolerance).
"""
from __future__ import annotations

import math

from ..geometry import UNIT_MM, clean
from ..model import Shape, clean_bulge
from ..shapes import angle_of, extend, shape_prims, trim
from .interact import (Answer, CommandError, GetAngle, GetDistance, GetNumber, GetObject, GetPoint, GetSelection,
                       GetText)


def _shape(host, kind, **kw):
    s = Shape(host.doc.new_id(), kind, **kw)
    s.layer = host.new_shape_layer()
    style = getattr(host, "new_shape_style", None)
    if style is not None and kind != "text":
        for k, v in style().items():
            setattr(s, k, v)
    host.doc.add_shape(s)
    return s


def _ghost(kind, **kw):
    return shape_prims(Shape(-1, kind, **kw), role="ghost")


def _fill_gap_mm(host) -> float:
    st = getattr(host, "settings", None)
    try:
        v = float(st["fill_gap_mm"]) if st is not None else 0.0
    except (KeyError, TypeError, ValueError):
        v = 0.0
    return v if 0 <= v <= MAX_FILL_GAP_MM else 0.0


MAX_FILL_GAP_MM = 10.0


def make_fill(host, rings) -> Shape:
    """Add a boundary-fill shape (independent of the objects that bounded it)."""
    s = Shape(host.doc.new_id(), "hatch",
              rings=[[(clean(x), clean(y), clean_bulge(b)) for x, y, b in ring] for ring in rings])
    s.layer = host.new_shape_layer()
    host.doc.add_shape(s)
    return s


def cmd_fill(host):
    """FILL / HATCH: click inside closed areas to fill them solid. Each pick
    makes one independent fill object (with holes for islands inside it)."""
    from ..boundary_fill import find_region
    made = []
    while True:
        gap = _fill_gap_mm(host)
        hint = f" (gap tolerance {gap:g} mm)" if gap else ""
        p = yield GetPoint(f"Click inside a closed area to fill{hint} (Enter to finish)", allow_enter=True,
                           keywords=("Gap",), snap_grid=False, osnap=False)
        if p is None:
            break
        if isinstance(p, Answer):
            if p.keyword == "Gap":
                v = yield GetNumber(f"Gap tolerance in mm: largest opening to close automatically "
                                    f"(0 to {MAX_FILL_GAP_MM:g}, current {gap:g})", default=gap)
                if v is None or isinstance(v, Answer):
                    continue
                if not 0 <= v <= MAX_FILL_GAP_MM:
                    host.log(f"Gap tolerance must be between 0 and {MAX_FILL_GAP_MM:g} mm.", "warning")
                    continue
                st = getattr(host, "settings", None)
                if st is not None:
                    st["fill_gap_mm"] = float(v)
            continue
        hook = getattr(host, "fill_boundary_shapes", None)
        shapes = hook() if hook is not None else list(host.doc.shapes.values())
        res = find_region(shapes, p, gap=gap / UNIT_MM)
        if not res.ok:
            host.log(res.message, "warning")
            continue
        s = make_fill(host, res.rings)
        made.append(s.id)
        msg = "Area filled" + (f" with {res.holes} hole(s)" if res.holes else "") + \
              (f"; {res.bridged} gap(s) closed" if res.bridged else "") + "."
        host.log(msg, "info")
        host.refresh_view()
    if made:
        host.set_selection(set(made))
    return f"{len(made)} fill(s) created."


def cmd_line(host):
    pts = []
    made = []
    p = yield GetPoint("Specify first point")
    if p is None:
        return "Cancelled."
    pts.append(p)
    while True:
        a = pts[-1]
        kws = ("Undo",) + (("Close",) if len(pts) >= 3 else ())
        q = yield GetPoint("Specify next point (Enter to finish)", base=a, allow_enter=True, keywords=kws,
                           preview=lambda c, a=a: _ghost("line", pts=[a, c]))
        if q is None:
            break
        if isinstance(q, Answer):
            if q.keyword == "Undo" and made:
                host.doc.shapes.pop(made.pop().id, None)
                pts.pop()
                continue
            if q.keyword == "Close":
                made.append(_shape(host, "line", pts=[pts[-1], pts[0]]))
                break
            continue
        if q == a:
            continue
        made.append(_shape(host, "line", pts=[a, q]))
        pts.append(q)
    return f"{len(made)} line(s) drawn."


def cmd_pline(host):
    pts = []
    p = yield GetPoint("Specify start point")
    if p is None:
        return "Cancelled."
    pts.append(p)
    closed = False
    while True:
        q = yield GetPoint("Specify next point (Enter to finish)", base=pts[-1], allow_enter=True,
                           keywords=("Undo", "Close") if len(pts) >= 3 else ("Undo",),
                           preview=lambda c: _ghost("polyline", pts=pts + [c]))
        if q is None:
            break
        if isinstance(q, Answer):
            if q.keyword == "Undo" and len(pts) > 1:
                pts.pop()
            elif q.keyword == "Close":
                closed = True
                break
            continue
        if q != pts[-1]:
            pts.append(q)
    if len(pts) < 2:
        return "Polyline needs at least two points."
    s = _shape(host, "polygon" if closed else ("line" if len(pts) == 2 else "polyline"), pts=pts)
    host.set_selection({s.id})
    return "Polyline drawn."


def cmd_rect(host):
    a = yield GetPoint("Specify first corner")
    if a is None:
        return "Cancelled."

    def corners(c):
        return [a, (c[0], a[1]), c, (a[0], c[1])]
    b = yield GetPoint("Specify opposite corner", base=a, preview=lambda c: _ghost("rect", pts=corners(c)))
    if b is None or b[0] == a[0] or b[1] == a[1]:
        return "Rectangle needs two different corners."
    s = _shape(host, "rect", pts=corners(b))
    host.set_selection({s.id})
    return "Rectangle drawn."


def cmd_circle(host):
    c = yield GetPoint("Specify centre point")
    if c is None:
        return "Cancelled."
    r = yield GetDistance("Specify radius (mm) or pick a point", base=c,
                          preview=lambda p: _ghost("circle", c=c, r=math.hypot(p[0] - c[0], p[1] - c[1])))
    if not r or r <= 0:
        return "Radius must be positive."
    s = _shape(host, "circle", c=c, r=r / UNIT_MM)
    host.set_selection({s.id})
    return f"Circle drawn (radius {r:g} mm)."


def cmd_arc(host):
    c = yield GetPoint("Specify arc centre")
    if c is None:
        return "Cancelled."
    p1 = yield GetPoint("Specify start point (sets the radius)", base=c)
    if p1 is None:
        return "Cancelled."
    r = math.hypot(p1[0] - c[0], p1[1] - c[1])
    if r <= 0:
        return "Radius must be positive."
    a0 = angle_of(p1, c)

    def ext(p):
        e = (angle_of(p, c) - a0) % 360
        return e or 360
    p2 = yield GetPoint("Specify end point (counter-clockwise)", base=c,
                        preview=lambda p: _ghost("arc", c=c, r=r, start=a0, extent=ext(p)))
    if p2 is None:
        return "Cancelled."
    s = _shape(host, "arc", c=c, r=r, start=round(a0, 6), extent=round(ext(p2), 6))
    host.set_selection({s.id})
    return "Arc drawn."


def cmd_text(host):
    p = yield GetPoint("Specify text position")
    if p is None:
        return "Cancelled."
    t = yield GetText("Enter text")
    if not t:
        return "No text entered."
    s = _shape(host, "text", pts=[p], s=t, size=10.0, anchor="w")
    host.set_selection({s.id})
    return "Text placed."


def _need_selection(host, verb):
    ids = yield GetSelection(f"Select objects to {verb}, then press Enter")
    ids = {i for i in (ids or set()) if host.doc.item(i) is not None and not getattr(host.doc.item(i), "locked", False)}
    if not ids:
        raise CommandError("nothing selected (locked objects are skipped)")
    host.set_selection(ids)
    return ids


def cmd_move(host):
    ids = yield from _need_selection(host, "move")
    base = yield GetPoint("Specify base point")
    if base is None:
        return "Cancelled."
    tgt = yield GetPoint("Specify second point", base=base,
                         preview=lambda c: host.sel_ghost(ids, ("move", c[0] - base[0], c[1] - base[1])))
    if tgt is None:
        return "Cancelled."
    host.sel_move(ids, tgt[0] - base[0], tgt[1] - base[1])
    return "Moved."


def cmd_copy(host):
    ids = yield from _need_selection(host, "copy")
    base = yield GetPoint("Specify base point")
    if base is None:
        return "Cancelled."
    n = 0
    while True:
        tgt = yield GetPoint("Specify second point (Enter to finish)", base=base, allow_enter=True,
                             preview=lambda c: host.sel_ghost(ids, ("move", c[0] - base[0], c[1] - base[1])))
        if tgt is None or isinstance(tgt, Answer):
            break
        host.sel_copy(ids, tgt[0] - base[0], tgt[1] - base[1])
        n += 1
    return f"{n} copy(ies) made."


def cmd_rotate(host):
    ids = yield from _need_selection(host, "rotate")
    base = yield GetPoint("Specify base point")
    if base is None:
        return "Cancelled."
    step = host.rotation_step(ids)
    ang = yield GetAngle("Specify rotation angle (degrees, counter-clockwise)" +
                         (" — symbols rotate in 90° steps" if step else ""), base=base, step=step or 0,
                         preview=lambda c: host.sel_ghost(ids, ("rotate", base, _snap_ang(
                             math.degrees(math.atan2(-(c[1] - base[1]), c[0] - base[0])), step))))
    if ang is None:
        return "Cancelled."
    err = host.sel_rotate(ids, base, _snap_ang(float(ang), step))
    if err:
        raise CommandError(err)
    return f"Rotated {_snap_ang(float(ang), step):g}°."


def _snap_ang(a, step):
    return round(a / step) * step if step else a


def cmd_scale(host):
    ids = yield from _need_selection(host, "scale")
    base = yield GetPoint("Specify base point")
    if base is None:
        return "Cancelled."
    ref = 20.0  # mm reference length for dynamic scaling
    k = yield GetDistance("Specify scale factor (type a number, or pick: 20 mm = 1×)", base=base,
                          preview=lambda c: host.sel_ghost(ids, ("scale", base, max(0.01, math.hypot(
                              c[0] - base[0], c[1] - base[1]) * UNIT_MM / ref))))
    if k is None:
        return "Cancelled."
    # a typed number is the factor itself; a picked point gives a distance in mm
    factor = float(k) if host.runner_last_was_typed() else float(k) / ref
    if factor <= 0:
        raise CommandError("the factor must be positive")
    err = host.sel_scale(ids, base, factor)
    if err:
        raise CommandError(err)
    return f"Scaled by {factor:g}."


def cmd_mirror(host):
    ids = yield from _need_selection(host, "mirror")
    p = yield GetPoint("Specify first point of the mirror line")
    if p is None:
        return "Cancelled."
    q = yield GetPoint("Specify second point of the mirror line", base=p,
                       preview=lambda c: host.sel_ghost(ids, ("mirror", p, c)) if c != p else [])
    if q is None or q == p:
        return "Cancelled."
    err = host.sel_mirror(ids, p, q)
    if err:
        raise CommandError(err)
    return "Mirrored."


def cmd_erase(host):
    ids = yield from _need_selection(host, "delete")
    host.sel_delete(ids)
    return f"Deleted {len(ids)} object(s)."


def _edges(host):
    return host.cut_edges()


def cmd_trim(host):
    n = 0
    while True:
        hit = yield GetObject("Click the part of a drawing object to trim (Enter to finish)",
                              accept=lambda o: isinstance(o, Shape) and o.kind != "text")
        if hit is None or isinstance(hit, Answer) or hit[0] is None:
            if hit is None or isinstance(hit, Answer):
                break
            continue
        sid, p = hit
        s = host.doc.shapes.get(sid)
        if s is None:
            continue
        res = trim(s, p, [e for e in _edges(host) if e is not s and getattr(e, "id", None) != sid], host.doc.new_id)
        if res is None:
            host.log("Nothing to trim there: the object does not cross another object.", "warning")
            continue
        host.doc.shapes.pop(sid)
        for r in res:
            host.doc.add_shape(r)
        n += 1
        host.refresh_view()
    return f"{n} trim(s)."


def cmd_extend(host):
    n = 0
    while True:
        hit = yield GetObject("Click near the end of a line or arc to extend (Enter to finish)",
                              accept=lambda o: isinstance(o, Shape) and o.kind in ("line", "polyline", "arc"))
        if hit is None or isinstance(hit, Answer):
            break
        sid, p = hit
        s = host.doc.shapes.get(sid)
        if s is None:
            continue
        if extend(s, p, [e for e in _edges(host) if getattr(e, "id", None) != sid]):
            n += 1
            host.refresh_view()
        else:
            host.log("No boundary found in that direction.", "warning")
    return f"{n} extension(s)."


DRAW_COMMANDS = {"FILL": cmd_fill, "LINE": cmd_line, "PLINE": cmd_pline, "RECTANGLE": cmd_rect, "CIRCLE": cmd_circle, "ARC": cmd_arc,
                 "TEXT": cmd_text, "MOVE": cmd_move, "COPY": cmd_copy, "ROTATE": cmd_rotate, "SCALE": cmd_scale,
                 "MIRROR": cmd_mirror, "ERASE": cmd_erase, "TRIM": cmd_trim, "EXTEND": cmd_extend}

# Toolbar descriptions of the drafting tools, shared by the schematic editor
# and the symbol editor so both toolbars read the same. The typed alias and
# any shortcut are appended by commands.tooltip().
TOOL_TIPS = {
    "FILL": "Fill: click inside closed areas to fill them solid (islands stay open)",
    "LINE": "Line: draw straight segments",
    "PLINE": "Polyline: draw connected segments (C closes)",
    "RECTANGLE": "Rectangle: pick two corners",
    "CIRCLE": "Circle: pick the centre, then the radius",
    "ARC": "Arc: pick the centre, start point and end point",
    "TEXT": "Text: place a note",
    "MOVE": "Move the selection: base point, then target point",
    "COPY": "Copy the selection: base point, then target points",
    "ROTATE": "Rotate the selection about a base point",
    "MIRROR": "Mirror the selection",
    "SCALE": "Scale the selection about a base point",
    "TRIM": "Trim objects at cutting edges",
    "EXTEND": "Extend objects to boundaries",
}


# ---------------------------------------------------------------- shared transform helpers for shapes
def transform_shape_copy(s: Shape, op) -> Shape:
    """Copy of s transformed by op (used for ghost previews)."""
    import copy as _c
    from ..shapes import mirror_shape, move_shape, rotate_shape, scale_shape
    o = _c.deepcopy(s)
    if op[0] == "move":
        move_shape(o, op[1], op[2])
    elif op[0] == "rotate":
        rotate_shape(o, op[1], -op[2])
    elif op[0] == "scale":
        scale_shape(o, op[1], op[2])
    elif op[0] == "mirror":
        mirror_shape(o, op[1], op[2])
    return o


def transform_point(p, op):
    from ..shapes import rotate_point
    if op[0] == "move":
        return (p[0] + op[1], p[1] + op[2])
    if op[0] == "rotate":
        return rotate_point(p, op[1], -op[2])
    if op[0] == "scale":
        c, k = op[1], op[2]
        return (c[0] + (p[0] - c[0]) * k, c[1] + (p[1] - c[1]) * k)
    if op[0] == "mirror":
        a, b = op[1], op[2]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d2 = dx * dx + dy * dy or 1
        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2
        fx, fy = a[0] + t * dx, a[1] + t * dy
        return (2 * fx - p[0], 2 * fy - p[1])
    return p
