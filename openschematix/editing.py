"""Editing operations on a Document. Pure functions, no GUI code, so they can
be unit-tested. The GUI wraps each user action in an undo checkpoint."""
from __future__ import annotations

import copy
from typing import Iterable, Optional

from . import symbols
from .geometry import (
    GRID, Point, bbox_union, clean, elbow, norm_rotation, same, simplify_orthogonal, snap, xform,
)
from .model import Component, Document, Wire


# ---------------------------------------------------------------- placement
def place(doc: Document, symbol_id: str, x: float, y: float, rotation=0, mirror=False, params=None,
          layer: str | None = None) -> Component:
    sym = symbols.get(symbol_id)
    if sym is None:
        raise KeyError(f"unknown symbol {symbol_id}")
    p = copy.deepcopy(params if params is not None else sym.default_params)
    comp = Component(id=doc.new_id(), symbol=symbol_id, x=snap(x), y=snap(y), rotation=norm_rotation(rotation),
                     mirror=bool(mirror), params=p)
    if sym.custom:
        comp.props.update({k: v for k, v in (sym.custom.get("properties") or {}).items() if v})
    if layer:
        comp.layer = layer
    from .project import is_terminal_symbol
    if is_terminal_symbol(symbol_id):
        strip, num = next_terminal(doc, sym.prefix or "X")
        comp.designator, comp.props["terminal"] = strip, num
    else:
        comp.designator = doc.next_designator(sym.prefix)
    doc.add_component(comp)
    attach_touching_wires(doc, [comp.id])
    return comp


def _terminal_numbers(doc: Document, strip: str) -> set:
    from .project import is_terminal_symbol
    sheets = doc.project.sheets if doc.project is not None else [doc]
    out = set()
    for s in sheets:
        for c in s.components.values():
            if is_terminal_symbol(c.symbol) and c.designator == strip:
                out.add(c.props.get("terminal", ""))
    return out


def next_terminal(doc: Document, prefix: str = "X", strip: str | None = None) -> tuple[str, str]:
    """Terminal strip and next free terminal number. Without an explicit strip
    the most recently placed strip on this sheet is continued."""
    from .project import is_terminal_symbol
    if strip is None:
        strips = [c.designator for c in doc.components.values() if is_terminal_symbol(c.symbol) and c.designator]
        strip = strips[-1] if strips else f"{prefix}1"
    used = _terminal_numbers(doc, strip)
    n = 1
    while str(n) in used:
        n += 1
    return strip, str(n)


def find_terminal_at(doc: Document, p: Point, exclude: Iterable[int] = ()) -> Optional[list]:
    ex = set(exclude)
    for c in doc.components.values():
        if c.id in ex:
            continue
        for name, tp in c.terminals().items():
            if same(tp, p):
                return [c.id, name]
    return None


def attach_touching_wires(doc: Document, comp_ids: Iterable[int]):
    """Attach free wire ends that coincide with terminals of the given components."""
    ids = set(comp_ids)
    for w in doc.wires.values():
        for attr, idx in (("start", 0), ("end", -1)):
            if getattr(w, attr) is None:
                for cid in ids:
                    c = doc.components.get(cid)
                    if not c:
                        continue
                    for name, tp in c.terminals().items():
                        if same(tp, w.points[idx]):
                            setattr(w, attr, [cid, name])


# ---------------------------------------------------------------- wires
def add_wire(doc: Document, points: list, style: str = "solid") -> Optional[Wire]:
    pts = simplify_orthogonal([(snap(p[0], 1), snap(p[1], 1)) for p in points])
    if len(pts) < 2 or same(pts[0], pts[-1]) and len(pts) == 2:
        return None
    w = Wire(id=doc.new_id(), points=pts, style=style)
    w.start = find_terminal_at(doc, pts[0])
    w.end = find_terminal_at(doc, pts[-1])
    doc.add_wire(w)
    return w


def set_endpoint(points: list, which: str, p: Point) -> list:
    """Move one end point of an orthogonal polyline to p, keeping it orthogonal
    by adjusting the neighbouring vertex (or inserting a bend)."""
    pts = simplify_orthogonal(points)
    if which == "end":
        pts.reverse()
    old = pts[0]
    if not same(old, p):
        if len(pts) == 2:
            q = pts[1]
            horiz = abs(old[1] - q[1]) < 0.01 and abs(old[0] - q[0]) >= 0.01
            pts = elbow(p, q, horizontal_first=horiz)
        else:
            n = pts[1]
            horiz = abs(old[1] - n[1]) < 0.01 and abs(old[0] - n[0]) >= 0.01
            pts[1] = (n[0], p[1]) if horiz else (p[0], n[1])
            pts[0] = p
    if which == "end":
        pts.reverse()
    return simplify_orthogonal(pts)


DIRV = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}
STUB = 2 * GRID


def route(p: Point, dp: Optional[str], q: Point, dq: Optional[str], avoid=(), avoid_segs=(), avoid_points=()) -> list:
    """Orthogonal route from p to q. dp/dq are the outward directions of the
    terminals at each end (or None for a free end). The route leaves and
    enters terminals along their lead direction, does not double back, and
    where possible avoids component bodies (`avoid` bounding boxes), running
    on top of other wires (`avoid_segs`) and passing over foreign terminals
    (`avoid_points`)."""
    from .geometry import point_on_segment

    def stub(pt, d, n):
        return (pt[0] + DIRV[d][0] * n, pt[1] + DIRV[d][1] * n) if d else pt
    cores = []
    for sp in (STUB, GRID, 3 * GRID, 4 * GRID):
        for sq in (STUB, GRID, 3 * GRID, 4 * GRID):
            ps, qs = stub(p, dp, sp), stub(q, dq, sq)
            mx, my = snap((ps[0] + qs[0]) / 2), snap((ps[1] + qs[1]) / 2)
            cores += [[ps, (qs[0], ps[1]), qs], [ps, (ps[0], qs[1]), qs],
                      [ps, (mx, ps[1]), (mx, qs[1]), qs], [ps, (ps[0], my), (qs[0], my), qs]]
            for b in avoid:  # detours around obstacles
                for x in (snap(b[0] - GRID), snap(b[2] + GRID)):
                    cores.append([ps, (x, ps[1]), (x, qs[1]), qs])
                for y in (snap(b[1] - GRID), snap(b[3] + GRID)):
                    cores.append([ps, (ps[0], y), (qs[0], y), qs])
            if not dp and not dq:
                break
        if not dp and not dq:
            break

    def cost(path):
        raw = []
        for pt in path:  # keep reversals visible: only drop repeated points
            if not raw or not same(raw[-1], pt):
                raw.append(pt)
        pts = simplify_orthogonal(path)
        c = 0.0
        prev = None
        for a, b in zip(raw, raw[1:]):
            d = (b[0] - a[0], b[1] - a[1])
            c += abs(d[0]) + abs(d[1])
            u = (0 if abs(d[0]) < 0.01 else (1 if d[0] > 0 else -1), 0 if abs(d[1]) < 0.01 else (1 if d[1] > 0 else -1))
            if prev and u[0] == -prev[0] and u[1] == -prev[1]:
                c += 1000  # doubles back on itself
            prev = u
            for box in avoid:
                if _seg_hits_box(a, b, (box[0] + 0.5, box[1] + 0.5, box[2] - 0.5, box[3] - 0.5)):
                    c += 400
            for sa, sb in avoid_segs:
                if _overlap(a, b, sa, sb):
                    c += 600
            for t in avoid_points:
                if point_on_segment(t, a, b):
                    c += 600
        c += 8 * len(pts)
        return c, pts
    best = min((cost([p] + core + [q]) for core in cores), key=lambda t: t[0])
    return best[1]


def _overlap(a, b, c, d) -> bool:
    """True if two orthogonal segments are collinear and share a length."""
    if abs(a[1] - b[1]) < 0.01 and abs(c[1] - d[1]) < 0.01 and abs(a[1] - c[1]) < 0.01:
        return max(min(a[0], b[0]), min(c[0], d[0])) < min(max(a[0], b[0]), max(c[0], d[0])) - 0.01
    if abs(a[0] - b[0]) < 0.01 and abs(c[0] - d[0]) < 0.01 and abs(a[0] - c[0]) < 0.01:
        return max(min(a[1], b[1]), min(c[1], d[1])) < min(max(a[1], b[1]), max(c[1], d[1])) - 0.01
    return False


def _seg_hits_box(a, b, box):
    l, t, r, btm = box
    if abs(a[1] - b[1]) < 0.01:
        y = a[1]
        return t < y < btm and max(min(a[0], b[0]), l) < min(max(a[0], b[0]), r)
    x = a[0]
    return l < x < r and max(min(a[1], b[1]), t) < min(max(a[1], b[1]), btm)


def _end_dir(doc: Document, ref):
    if not ref:
        return None
    c = doc.components.get(ref[0])
    return c.terminal_dirs().get(ref[1]) if c else None


def reroute(doc: Document, w: Wire):
    """Recompute a wire's path from its end points and terminal directions."""
    p, q = w.points[0], w.points[-1]
    if w.start:
        p = doc.terminal_pos(w.start) or p
    if w.end:
        q = doc.terminal_pos(w.end) or q
    own = {tuple(r) for r in (w.start, w.end) if r}
    avoid = [doc.components[r[0]].bbox() for r in (w.start, w.end) if r and r[0] in doc.components]
    segs = [(a, b) for o in doc.wires.values() if o.id != w.id for a, b in zip(o.points, o.points[1:])]
    pts = [tp for c in doc.components.values() for n, tp in c.terminals().items() if (c.id, n) not in own]
    w.points = route(p, _end_dir(doc, w.start), q, _end_dir(doc, w.end), avoid, segs, pts)
    w.auto = True


def sync_wire_ends(doc: Document, wire_ids: Optional[Iterable[int]] = None):
    """Move attached wire end points onto their terminals' current positions.
    Automatically routed wires and simple wires (at most one bend) are
    re-routed; hand-shaped wires are adjusted minimally so their shape is
    preserved."""
    targets = doc.wires.values() if wire_ids is None else [doc.wires[i] for i in wire_ids if i in doc.wires]
    for w in targets:
        moved = False
        for attr, idx in (("start", 0), ("end", -1)):
            ref = getattr(w, attr)
            if not ref:
                continue
            tp = doc.terminal_pos(ref)
            if tp is None:
                setattr(w, attr, None)
            elif not same(tp, w.points[idx]):
                moved = True
        if not moved:
            continue
        if w.auto or len(w.points) <= 3:
            reroute(doc, w)
        else:
            for attr, which, idx in (("start", "start", 0), ("end", "end", -1)):
                ref = getattr(w, attr)
                if ref:
                    tp = doc.terminal_pos(ref)
                    if tp and not same(tp, w.points[idx]):
                        w.points = set_endpoint(w.points, which, tp)


def drag_segment(points: list, index: int, delta: float) -> tuple[list, int]:
    """Move segment `index` perpendicular to itself by delta. End points stay
    where they are (a short stub is inserted). Returns (points, new_index)."""
    pts = [tuple(p) for p in points]
    if index < 0 or index >= len(pts) - 1:
        return pts, index
    a, b = pts[index], pts[index + 1]
    horiz = abs(a[1] - b[1]) < 0.01
    if index == 0:
        pts.insert(0, pts[0])
        index += 1
    if index + 1 == len(pts) - 1:
        pts.append(pts[-1])
    a, b = pts[index], pts[index + 1]
    if horiz:
        pts[index], pts[index + 1] = (a[0], a[1] + delta), (b[0], b[1] + delta)
    else:
        pts[index], pts[index + 1] = (a[0] + delta, a[1]), (b[0] + delta, b[1])
    return pts, index


def segment_at(w: Wire, p: Point, tol: float) -> Optional[int]:
    from .geometry import seg_distance
    best, bi = tol, None
    for i, (a, b) in enumerate(zip(w.points, w.points[1:])):
        d = seg_distance(p, a, b)
        if d <= best:
            best, bi = d, i
    return bi


# ---------------------------------------------------------------- transforms
def _rigid_wires(doc: Document, comp_ids: set, wire_ids: set) -> set:
    rigid = set(wire_ids)
    for w in doc.wires.values():
        if w.start and w.end and w.start[0] in comp_ids and w.end[0] in comp_ids:
            rigid.add(w.id)
    return rigid


def split_ids(doc: Document, ids: Iterable[int]):
    ids = set(ids)
    return ([i for i in ids if i in doc.components], [i for i in ids if i in doc.wires],
            [i for i in ids if i in doc.shapes])


def move_items(doc: Document, comp_ids: Iterable[int], wire_ids: Iterable[int], dx: float, dy: float,
               shape_ids: Iterable[int] = ()):
    from .shapes import move_shape
    comp_ids, wire_ids = set(comp_ids), set(wire_ids)
    for cid in comp_ids:
        c = doc.components.get(cid)
        if c:
            c.x, c.y = clean(c.x + dx), clean(c.y + dy)
    for wid in _rigid_wires(doc, comp_ids, wire_ids):
        w = doc.wires.get(wid)
        if w:
            w.points = [(clean(x + dx), clean(y + dy)) for x, y in w.points]
            # a moved wire whose end is no longer on its terminal is detached
            for attr, idx in (("start", 0), ("end", -1)):
                ref = getattr(w, attr)
                if ref and ref[0] not in comp_ids:
                    tp = doc.terminal_pos(ref)
                    if tp is None or not same(tp, w.points[idx]):
                        setattr(w, attr, None)
    for sid in shape_ids:
        s = doc.shapes.get(sid)
        if s:
            move_shape(s, dx, dy)
    sync_wire_ends(doc)
    attach_touching_wires(doc, comp_ids)


def selection_bbox(doc: Document, ids):
    b = None
    for i in ids:
        o = doc.item(i)
        if o is not None:
            b = bbox_union(b, o.bbox())
    return b


def selection_center(doc: Document, comp_ids, wire_ids, shape_ids=()) -> Point:
    b = selection_bbox(doc, list(comp_ids) + list(wire_ids) + list(shape_ids))
    if b is None:
        return (0.0, 0.0)
    return (snap((b[0] + b[2]) / 2), snap((b[1] + b[3]) / 2))


def _transform_items(doc, comp_ids, wire_ids, fn_point, fn_comp, shape_ids=(), fn_shape=None, center=None):
    comp_ids, wire_ids = set(comp_ids), set(wire_ids)
    shape_ids = set(shape_ids)
    single = len(comp_ids) == 1 and not wire_ids and not shape_ids and center is None
    cx, cy = center if center is not None else selection_center(doc, comp_ids, wire_ids, shape_ids)
    rigid = _rigid_wires(doc, comp_ids, wire_ids)
    for cid in comp_ids:
        c = doc.components.get(cid)
        if not c:
            continue
        fn_comp(c)
        if not single:
            nx, ny = fn_point(c.x - cx, c.y - cy)
            c.x, c.y = snap(cx + nx), snap(cy + ny)
    for wid in rigid:
        w = doc.wires.get(wid)
        if not w:
            continue
        w.points = simplify_orthogonal([(clean(cx + fn_point(x - cx, y - cy)[0]), clean(cy + fn_point(x - cx, y - cy)[1]))
                                        for x, y in w.points])
    if fn_shape:
        for sid in shape_ids:
            s = doc.shapes.get(sid)
            if s:
                fn_shape(s, (cx, cy))
    sync_wire_ends(doc)


def rotate_items(doc: Document, comp_ids, wire_ids, clockwise: bool = True, shape_ids=(), center=None):
    from .shapes import rotate_shape
    deg = 90 if clockwise else 270

    def fc(c):
        # Rotation is applied after mirroring in the component transform,
        # so a plain rotation increment is correct for mirrored parts too.
        c.rotation = (c.rotation + deg) % 360
    _transform_items(doc, comp_ids, wire_ids, lambda x, y: xform(x, y, deg, False), fc, shape_ids,
                     lambda s, ctr: rotate_shape(s, ctr, deg), center)


def mirror_items(doc: Document, comp_ids, wire_ids, shape_ids=(), center=None):
    from .shapes import mirror_shape

    def fc(c):
        # Mirror in world X: toggling the mirror flag and negating the
        # rotation gives the world-space mirror image.
        c.mirror = not c.mirror
        c.rotation = (-c.rotation) % 360
    _transform_items(doc, comp_ids, wire_ids, lambda x, y: (-x, y), fc, shape_ids,
                     lambda s, ctr: mirror_shape(s, ctr, (ctr[0], ctr[1] + 10)), center)


def rotate_shapes_by(doc: Document, shape_ids, center: Point, deg_cw: float):
    from .shapes import rotate_shape
    for sid in shape_ids:
        s = doc.shapes.get(sid)
        if s:
            rotate_shape(s, center, deg_cw)


# ---------------------------------------------------------------- delete / clipboard
def delete_items(doc: Document, ids: Iterable[int]):
    ids = set(ids)
    for i in ids:
        doc.components.pop(i, None)
        doc.wires.pop(i, None)
        doc.shapes.pop(i, None)
    for w in doc.wires.values():
        if w.start and w.start[0] in ids:
            w.start = None
        if w.end and w.end[0] in ids:
            w.end = None


def copy_items(doc: Document, ids: Iterable[int]) -> dict:
    ids = set(ids)
    comps = [doc.components[i].to_dict() for i in ids if i in doc.components]
    cids = {c["id"] for c in comps}
    wires = []
    for w in doc.wires.values():
        if w.id in ids or (w.start and w.end and w.start[0] in cids and w.end[0] in cids):
            wd = w.to_dict()
            if wd["start"] and wd["start"][0] not in cids:
                wd["start"] = None
            if wd["end"] and wd["end"][0] not in cids:
                wd["end"] = None
            if not w.number_manual:
                wd.pop("number", None)
            wires.append(wd)
    shapes = [doc.shapes[i].to_dict() for i in ids if i in doc.shapes]
    from . import symbols as _s
    used = {c["symbol"] for c in comps if c["symbol"].startswith("user:")}
    custom = {}
    for sid in used:
        sd = _s.get(sid)
        if sd is not None and sd.custom is not None:
            custom[sid] = copy.deepcopy(sd.custom)
    return {"components": comps, "wires": wires, "shapes": shapes, "symbols": custom}


def paste(doc: Document, clip: dict, dx: float, dy: float, renumber: bool = False) -> list[int]:
    """Insert clipboard/template content. Designators that already exist in
    the project (or all designators, with `renumber`) are reassigned."""
    from .model import Shape
    from .project import is_terminal_symbol
    from .shapes import move_shape
    from . import symbols as _s
    for sid, sdoc in (clip.get("symbols") or {}).items():
        if _s.get(sid) is None:
            try:
                from .symbols.custom import to_symdef
                _s.add_project_symbol(to_symdef(sdoc))
            except ValueError:
                pass
    idmap = {}
    new_ids = []
    taken = doc.used_designators()
    existing = set(taken)
    clip_des = {cd.get("designator") for cd in clip.get("components", []) if cd.get("designator")}
    remap: dict = {}     # old designator -> new; parts of one device keep sharing it
    for cd in clip.get("components", []):
        c = Component.from_dict(cd)
        old = c.id
        c.id = doc.new_id()
        c.x, c.y = clean(c.x + dx), clean(c.y + dy)
        sym = _s.get(c.symbol)
        if is_terminal_symbol(c.symbol):
            if renumber or c.props.get("terminal", "") in _terminal_numbers(doc, c.designator):
                _strip, c.props["terminal"] = next_terminal(doc, strip=c.designator or "X1")
        elif c.designator and (renumber or c.designator in existing or c.designator in remap):
            if c.designator not in remap:
                import re as _re
                prefix = _re.sub(r"\d+$", "", c.designator) or (sym.prefix if sym else "")
                if prefix:
                    nd = _next_free(prefix, taken if renumber else taken | clip_des)
                    remap[c.designator] = nd
                    taken.add(nd)
                else:
                    remap[c.designator] = c.designator
            c.designator = remap[c.designator]
        if c.designator and not is_terminal_symbol(c.symbol):
            taken.add(c.designator)
        doc.add_component(c)
        idmap[old] = c.id
        new_ids.append(c.id)
    for wd in clip.get("wires", []):
        w = Wire.from_dict(wd)
        w.id = doc.new_id()
        w.points = [(clean(x + dx), clean(y + dy)) for x, y in w.points]
        w.start = [idmap[w.start[0]], w.start[1]] if w.start and w.start[0] in idmap else None
        w.end = [idmap[w.end[0]], w.end[1]] if w.end and w.end[0] in idmap else None
        if renumber and not w.number_manual:
            w.number = ""
        doc.add_wire(w)
        new_ids.append(w.id)
    for sd in clip.get("shapes", []):
        s = Shape.from_dict(sd)
        s.id = doc.new_id()
        move_shape(s, dx, dy)
        doc.add_shape(s)
        new_ids.append(s.id)
    sync_wire_ends(doc)
    return new_ids


def _next_free(prefix, taken):
    n = 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


# ---------------------------------------------------------------- hit testing
def items_in_rect(doc: Document, r, selectable=None, crossing: bool = False) -> list[int]:
    """Objects inside rectangle r. With `crossing`, objects that merely touch
    the rectangle are included too (AutoCAD crossing selection)."""
    from .geometry import bbox_contains

    def inside(b):
        if b is None:
            return False
        if crossing:
            return not (b[2] < r[0] or b[0] > r[2] or b[3] < r[1] or b[1] > r[3])
        return bbox_contains(r, b)
    out = []
    for coll in (doc.components, doc.wires, doc.shapes):
        for o in coll.values():
            if (selectable is None or selectable(o)) and inside(o.bbox()):
                out.append(o.id)
    return out


def hit_test(doc: Document, p: Point, tol: float, selectable=None) -> Optional[int]:
    """Topmost item under p. Wires and shapes are tested first (they are thin
    and drawn over symbol bodies), then components in reverse placement order,
    then boundary fills (drawn underneath everything, so anything else at the
    point wins; among overlapping fills the smallest is picked)."""
    from .geometry import bbox_hit, seg_distance
    from .regions import region_area
    from .shapes import shape_distance
    best = None
    fills = []
    for w in doc.wires.values():
        if selectable is not None and not selectable(w):
            continue
        d = min(seg_distance(p, a, b) for a, b in zip(w.points, w.points[1:]))
        if d <= tol and (best is None or d < best[0]):
            best = (d, w.id)
    for s in doc.shapes.values():
        if selectable is not None and not selectable(s):
            continue
        if s.kind == "hatch":
            fills.append(s)
            continue
        d = shape_distance(s, p)
        if d <= tol and (best is None or d < best[0]):
            best = (d, s.id)
    if best:
        return best[1]
    for c in reversed(list(doc.components.values())):
        if selectable is not None and not selectable(c):
            continue
        if bbox_hit(c.bbox(), p, tol * 0.5):
            return c.id
    hits = []
    for s in fills:
        d = shape_distance(s, p)
        if d <= tol:
            hits.append((d, abs(region_area(s.rings)), s.id))
    if hits:
        return min(hits)[2]
    return None


def expand_groups(doc: Document, ids: Iterable[int]) -> set:
    ids = set(ids)
    groups = {doc.item(i).group for i in ids if doc.item(i) is not None and doc.item(i).group}
    if not groups:
        return ids
    for coll in (doc.components, doc.wires, doc.shapes):
        for o in coll.values():
            if o.group in groups:
                ids.add(o.id)
    return ids


def group_items(doc: Document, ids: Iterable[int]) -> str:
    import uuid
    g = uuid.uuid4().hex[:8]
    for i in ids:
        o = doc.item(i)
        if o is not None:
            o.group = g
    return g


def ungroup_items(doc: Document, ids: Iterable[int]):
    for i in expand_groups(doc, ids):
        o = doc.item(i)
        if o is not None:
            o.group = ""


# ---------------------------------------------------------------- wire crossings and junctions
def _interior(p, pts) -> bool:
    return not same(p, pts[0]) and not same(p, pts[-1])


_XCELL = 50.0                    # crossing index cell size (drawing units)
_XMAX_CELLS_PER_SEGMENT = 256    # longer segments are paired with every opposite segment
_XBUDGET_PER_SEGMENT = 32        # total index registrations allowed per segment ...
_XBUDGET_MIN = 4096              # ... plus this many


def _crossing_pair(w1, a1, b1, w2, a2, b2):
    """The pair test of crossings() (unchanged): crossing tuple or None."""
    if w1.id == w2.id:
        return None
    h1, h2 = abs(a1[1] - b1[1]) < 0.01, abs(a2[1] - b2[1]) < 0.01
    if h1 == h2:
        return None  # parallel: overlaps are not crossings
    hs, vs = ((a1, b1), (a2, b2)) if h1 else ((a2, b2), (a1, b1))
    x, y = vs[0][0], hs[0][1]
    if not (min(hs[0][0], hs[1][0]) + 0.01 < x < max(hs[0][0], hs[1][0]) - 0.01):
        return None
    if not (min(vs[0][1], vs[1][1]) + 0.01 < y < max(vs[0][1], vs[1][1]) - 0.01):
        return None
    p = (x, y)
    if not (_interior(p, w1.points) and _interior(p, w2.points)):
        return None
    # a corner of either wire exactly at the crossing is a touch, not a crossing
    if any(same(p, q) for q in w1.points + w2.points):
        return None
    wv = w1 if not h1 else w2
    wh = w2 if wv is w1 else w1
    return (p, wh.id, wv.id)


def _xcell(v: float) -> int:
    import math
    return math.floor(v / _XCELL)


def crossings(doc: Document) -> list:
    """Points where two wires cross without being connected: a segment of
    one wire passes through a segment of another, and neither wire ends
    there. Returns [(point, wire_a_id, wire_b_id)] with wire_b the one that
    is drawn with a bridge (the vertical segment by convention, otherwise
    the later wire).

    Semantics are defined by `_crossing_pair`, applied to every pair of
    segments (i, j), i < j, in segment order: only a "horizontal" segment
    (|dy| < 0.01) and a non-horizontal one can cross; the non-horizontal one
    is treated as vertical at the x of its FIRST point (its x extent is not
    used), and the crossing (x, y_h) must lie strictly inside both ranges.

    Speed-up (results and order identical to testing every pair): such a
    pair can only pass when x lies in the horizontal's x range and y_h in
    the other's y range, i.e. when the horizontal's grid row and the
    other's grid column share the cell containing (x, y_h). Horizontals are
    registered in the cells of their row, the others in the cells of their
    column; a row and a column share at most one cell, so every candidate
    pair is found exactly once. For each segment i the candidates j > i are
    tested in increasing j, so output order is unchanged. Segments with
    non-finite coordinates, spanning more than _XMAX_CELLS_PER_SEGMENT
    cells, or beyond the registration budget (_XBUDGET_PER_SEGMENT * S +
    _XBUDGET_MIN, so memory is O(S)) are not registered and are paired with
    every segment of the opposite kind instead (the original behaviour).
    Time O(S * c + K log K) for K candidate pairs; worst case the original
    O(S^2). The index is local to the call: nothing is cached."""
    import math
    from bisect import bisect_right

    ws = list(doc.wires.values())
    segs = [(w, a, b) for w in ws for a, b in zip(w.points, w.points[1:])]
    n = len(segs)
    horiz = [abs(a[1] - b[1]) < 0.01 for _w, a, b in segs]
    budget = _XBUDGET_PER_SEGMENT * n + _XBUDGET_MIN
    used = 0
    cells_h, cells_v = {}, {}
    seg_cells = [None] * n          # (first cell, last cell, fixed cell) of an indexed segment
    for i, (_w, a, b) in enumerate(segs):
        if horiz[i]:
            lo, hi, fixed = min(a[0], b[0]), max(a[0], b[0]), a[1]   # row at y = a.y
        else:
            lo, hi, fixed = min(a[1], b[1]), max(a[1], b[1]), a[0]   # column at x = a.x
        if not (math.isfinite(lo) and math.isfinite(hi) and math.isfinite(fixed)):
            continue
        k0, k1, f = _xcell(lo), _xcell(hi), _xcell(fixed)
        count = k1 - k0 + 1
        if count > _XMAX_CELLS_PER_SEGMENT or used + count > budget:
            continue
        used += count
        seg_cells[i] = (k0, k1, f)
        table = cells_h if horiz[i] else cells_v
        for k in range(k0, k1 + 1):
            table.setdefault((k, f) if horiz[i] else (f, k), []).append(i)
    all_h = [i for i in range(n) if horiz[i]]
    all_v = [i for i in range(n) if not horiz[i]]
    loose_h = [i for i in all_h if seg_cells[i] is None]
    loose_v = [i for i in all_v if seg_cells[i] is None]

    out = []
    for i in range(n):
        if horiz[i]:
            others, every, loose = cells_v, all_v, loose_v
        else:
            others, every, loose = cells_h, all_h, loose_h
        if seg_cells[i] is None:
            cand = every[bisect_right(every, i):]
        else:
            k0, k1, f = seg_cells[i]
            cand = []
            for k in range(k0, k1 + 1):
                for j in others.get((k, f) if horiz[i] else (f, k), ()):
                    if j > i:
                        cand.append(j)
            cand += loose[bisect_right(loose, i):]
            cand.sort()
        w1, a1, b1 = segs[i]
        for j in cand:
            w2, a2, b2 = segs[j]
            r = _crossing_pair(w1, a1, b1, w2, a2, b2)
            if r is not None:
                out.append(r)
    return out


def split_wire(doc: Document, w: Wire, p: Point) -> Optional[Wire]:
    """Split wire w at point p (which must lie on it). Returns the new second
    part, or None if p is not an interior point of w."""
    from .geometry import point_on_segment
    pts = w.points
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        if point_on_segment(p, a, b) and _interior(p, pts):
            first = simplify_orthogonal(pts[:i + 1] + [p])
            second = simplify_orthogonal([p] + pts[i + 1:])
            if len(first) < 2 or len(second) < 2 or same(first[0], first[-1]) or same(second[0], second[-1]):
                return None
            nw = Wire(id=doc.new_id(), points=second, start=None, end=w.end, style=w.style, auto=False,
                      number=w.number, number_manual=w.number_manual, props=dict(w.props), layer=w.layer,
                      group=w.group)
            w.points, w.end, w.auto = first, None, False
            doc.add_wire(nw)
            return nw
    return None


def connect_crossing(doc: Document, p: Point, tol: float = 0.5) -> bool:
    """Turn the crossing nearest p into a connection (junction): both wires
    are split there, so four wire ends meet at the point."""
    best = None
    for q, wa, wb in crossings(doc):
        d = abs(q[0] - p[0]) + abs(q[1] - p[1])
        if d <= tol and (best is None or d < best[0]):
            best = (d, q, wa, wb)
    if best is None:
        return False
    _d, q, wa, wb = best
    a, b = doc.wires[wa], doc.wires[wb]
    split_wire(doc, a, q)
    split_wire(doc, b, q)
    return True


def wire_ends_at(doc: Document, p: Point) -> list:
    out = []
    for w in doc.wires.values():
        if same(w.points[0], p):
            out.append((w, "start"))
        if same(w.points[-1], p):
            out.append((w, "end"))
    return out


def _end_heading(w: Wire, which: str):
    """Direction pointing from the junction along the wire: 'l','r','u','d'."""
    pts = w.points if which == "start" else list(reversed(w.points))
    a, b = pts[0], pts[1]
    if abs(a[1] - b[1]) < 0.01:
        return "r" if b[0] > a[0] else "l"
    return "d" if b[1] > a[1] else "u"


def junction_at(doc: Document, p: Point) -> bool:
    """True if a junction (three or more connected branches) is at p."""
    from .connectivity import analyse
    return any(same(p, q) for q in analyse(doc).junctions)


def disconnect_junction(doc: Document, p: Point) -> str:
    """Undo a junction at p.
      * four wire ends meeting from four directions -> the opposite pairs are
        merged back into two wires that cross (shown with a bridge);
      * a T-junction -> the branch wire is pulled back one grid step so it no
        longer touches the through wire (its end is then flagged as open).
    Returns a description of what happened ("" if nothing was done)."""
    ends = wire_ends_at(doc, p)
    if len(ends) == 4:
        by_dir = {}
        for w, which in ends:
            by_dir.setdefault(_end_heading(w, which), []).append((w, which))
        if all(len(by_dir.get(d, [])) == 1 for d in "lrud"):
            for d1, d2 in (("l", "r"), ("u", "d")):
                (w1, e1), = by_dir[d1]
                (w2, e2), = by_dir[d2]
                merge_wires(doc, w1, e1, w2, e2)
            return "Junction removed: the wires now cross without connecting."
    # T: one wire passes through p (or two collinear ends) and one branch ends at p
    from .geometry import point_on_segment
    through = [w for w in doc.wires.values()
               if any(point_on_segment(p, a, b) for a, b in zip(w.points, w.points[1:])) and _interior(p, w.points)]
    branch = None
    if through and len(ends) == 1:
        branch = ends[0]
    elif len(ends) == 3:
        by_dir = {}
        for w, which in ends:
            by_dir.setdefault(_end_heading(w, which), []).append((w, which))
        lone = [v[0] for d, v in by_dir.items() if len(v) == 1 and
                {"l": "r", "r": "l", "u": "d", "d": "u"}[d] not in by_dir]
        if len(lone) == 1:
            branch = lone[0]
    if branch is None:
        return ""
    w, which = branch
    h = _end_heading(w, which)
    step = {"l": (-GRID, 0), "r": (GRID, 0), "u": (0, -GRID), "d": (0, GRID)}[h]
    idx = 0 if which == "start" else -1
    seg_len = abs(w.points[idx][0] - w.points[idx + (1 if idx == 0 else -1)][0]) + \
        abs(w.points[idx][1] - w.points[idx + (1 if idx == 0 else -1)][1])
    if seg_len <= GRID + 0.01:
        return ""
    q = (clean(p[0] + step[0]), clean(p[1] + step[1]))
    w.points = set_endpoint(w.points, which, q)
    w.auto = False
    return "Branch disconnected from the junction (its end is now open)."


def merge_wires(doc: Document, w1: Wire, e1: str, w2: Wire, e2: str):
    """Join two wires that end at the same point into one wire."""
    a = list(w1.points) if e1 == "end" else list(reversed(w1.points))
    b = list(w2.points) if e2 == "start" else list(reversed(w2.points))
    far1 = w1.start if e1 == "end" else w1.end
    far2 = w2.end if e2 == "start" else w2.start
    w1.points = simplify_orthogonal(a + b[1:])
    w1.start, w1.end = far1, far2
    w1.auto = False
    if not w1.number and w2.number:
        w1.number, w1.number_manual = w2.number, w2.number_manual
    doc.wires.pop(w2.id, None)


# ---------------------------------------------------------------- scaling
def scale_geometry(doc: Document, factor: float, ref: Point = (0.0, 0.0), ids: Optional[Iterable[int]] = None):
    """Scale the *positions* of the drawing about `ref` (the model geometry).

    Component symbols keep their size (a contactor stays the same contactor),
    so only their insertion points move; wires follow their terminals and
    free wire geometry is scaled and kept on the grid; drafting shapes are
    scaled exactly, including text height. Connections are preserved because
    wire ends attached to terminals are re-synchronised afterwards and all
    snapped coordinates are mapped by the same monotonic function."""
    from .shapes import scale_shape
    if factor <= 0:
        raise ValueError("scale factor must be positive")
    sel = doc.all_ids() if ids is None else set(ids)
    rx, ry = ref

    def sp(p):
        return (snap(rx + (p[0] - rx) * factor), snap(ry + (p[1] - ry) * factor))
    for i in sel:
        c = doc.components.get(i)
        if c:
            c.x, c.y = sp((c.x, c.y))
    for i in sel:
        w = doc.wires.get(i)
        if w:
            pts = [sp(p) for p in w.points]
            w.points = simplify_orthogonal(pts) if len(simplify_orthogonal(pts)) >= 2 else pts
    for i in sel:
        s = doc.shapes.get(i)
        if s:
            scale_shape(s, ref, factor)
    # drop wires that collapsed to a point unless attached
    for w in list(doc.wires.values()):
        if len(w.points) == 2 and same(w.points[0], w.points[1]) and not (w.start or w.end):
            doc.wires.pop(w.id)
    sync_wire_ends(doc)


def drawable_area(doc: Document):
    """Region of the sheet (model units) inside the frame and above the
    title block, where drawing content belongs."""
    from .titleblock import frame_layout
    lay = frame_layout(doc)
    return lay["drawable"]


def fit_to_sheet(doc: Document, standard: bool = True, margin_mm: float = 5.0) -> str:
    """Choose the presentation scale so the drawing fits inside the frame and
    centre it there. Only the printed scale and the drawing's position change;
    geometry, symbol sizes and connections are untouched. Returns the scale."""
    from .model import STANDARD_SCALES, format_scale, parse_scale
    from .geometry import UNIT_MM
    b = doc.bbox()
    if b is None:
        return doc.sheet.scale
    old = doc.sheet.scale
    doc.sheet.scale = "1:1"
    x0, y0, x1, y1 = drawable_area(doc)          # paper units at 1:1
    m = margin_mm / UNIT_MM
    aw, ah = (x1 - x0) - 2 * m, (y1 - y0) - 2 * m
    bw, bh = max(b[2] - b[0], 1.0), max(b[3] - b[1], 1.0)
    need = min(aw / bw, ah / bh)                 # paper per model
    if standard:
        cands = sorted((parse_scale(s) for s in STANDARD_SCALES), reverse=True)
        f = next((c for c in cands if c <= need + 1e-9), cands[-1])
    else:
        f = need
    doc.sheet.scale = format_scale(f)
    try:
        ax0, ay0, ax1, ay1 = drawable_area(doc)
    except Exception:  # noqa: BLE001
        doc.sheet.scale = old
        raise
    cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
    dx, dy = snap(cx - (b[0] + b[2]) / 2), snap(cy - (b[1] + b[3]) / 2)
    if dx or dy:
        c, w, s = split_ids(doc, doc.all_ids())
        move_items(doc, c, w, dx, dy, s)
    return doc.sheet.scale


# ---------------------------------------------------------------- align / distribute
ALIGN_MODES = ("left", "center", "right", "top", "middle", "bottom")


def align_items(doc: Document, ids, mode: str):
    """Align components and shapes (by bounding box) to the selection extent."""
    from .shapes import move_shape
    objs = [doc.item(i) for i in ids if i in doc.components or i in doc.shapes]
    if len(objs) < 2:
        return
    boxes = [o.bbox() for o in objs]
    if mode == "left":
        target = min(b[0] for b in boxes)
    elif mode == "right":
        target = max(b[2] for b in boxes)
    elif mode == "top":
        target = min(b[1] for b in boxes)
    elif mode == "bottom":
        target = max(b[3] for b in boxes)
    elif mode == "center":
        target = sum((b[0] + b[2]) / 2 for b in boxes) / len(boxes)
    elif mode == "middle":
        target = sum((b[1] + b[3]) / 2 for b in boxes) / len(boxes)
    else:
        raise ValueError(mode)
    for o, b in zip(objs, boxes):
        cur = {"left": b[0], "right": b[2], "top": b[1], "bottom": b[3],
               "center": (b[0] + b[2]) / 2, "middle": (b[1] + b[3]) / 2}[mode]
        d = target - cur
        dx, dy = (d, 0.0) if mode in ("left", "right", "center") else (0.0, d)
        if isinstance(o, Component):
            o.x, o.y = snap(o.x + dx), snap(o.y + dy)
        else:
            move_shape(o, snap(dx), snap(dy))
    sync_wire_ends(doc)


def distribute_items(doc: Document, ids, axis: str = "h"):
    """Space components/shapes evenly between the outermost two."""
    from .shapes import move_shape
    objs = [doc.item(i) for i in ids if i in doc.components or i in doc.shapes]
    if len(objs) < 3:
        return
    k = 0 if axis == "h" else 1

    def ctr(o):
        b = o.bbox()
        return (b[k] + b[k + 2]) / 2
    objs.sort(key=ctr)
    first, last = ctr(objs[0]), ctr(objs[-1])
    step = (last - first) / (len(objs) - 1)
    for n, o in enumerate(objs[1:-1], 1):
        d = snap(first + n * step - ctr(o))
        dx, dy = (d, 0.0) if axis == "h" else (0.0, d)
        if isinstance(o, Component):
            o.x, o.y = clean(o.x + dx), clean(o.y + dy)
        else:
            move_shape(o, dx, dy)
    sync_wire_ends(doc)


# ---------------------------------------------------------------- drafting shapes on a sheet
def wire_as_shape(w: Wire):
    from .model import Shape
    return Shape(id=-w.id, kind="polyline", pts=list(w.points))


def trim_on_sheet(doc: Document, shape_id: int, pick: Point, edge_ids: Optional[Iterable[int]] = None) -> bool:
    """TRIM a drafting shape against cutting edges (all other shapes and
    wires by default). Returns True if something was trimmed."""
    from .shapes import trim
    s = doc.shapes.get(shape_id)
    if s is None:
        return False
    edges = []
    pool = doc.all_ids() if edge_ids is None else set(edge_ids)
    for i in pool:
        if i == shape_id:
            continue
        if i in doc.shapes:
            edges.append(doc.shapes[i])
        elif i in doc.wires:
            edges.append(wire_as_shape(doc.wires[i]))
    res = trim(s, pick, edges, doc.new_id)
    if res is None:
        return False
    doc.shapes.pop(shape_id)
    for r in res:
        doc.add_shape(r)
    return True


def extend_on_sheet(doc: Document, shape_id: int, pick: Point, edge_ids: Optional[Iterable[int]] = None) -> bool:
    from .shapes import extend
    s = doc.shapes.get(shape_id)
    if s is None:
        return False
    pool = doc.all_ids() if edge_ids is None else set(edge_ids)
    edges = [doc.shapes[i] if i in doc.shapes else wire_as_shape(doc.wires[i])
             for i in pool if i != shape_id and (i in doc.shapes or i in doc.wires)]
    return extend(s, pick, edges)
