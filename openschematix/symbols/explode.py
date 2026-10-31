"""Open an existing symbol for editing ("import and explode").

Converts any symbol - built-in, user library or project-embedded - into a
custom symbol document (see custom.py) whose primitives the symbol editor can
edit individually, keeping every connection point's identifier, position,
lead direction, port type and display name.

Built-in symbols are defined with arcs already sampled into polylines (see
base.arc), so a polyline whose points lie evenly on a circle is turned back
into a native arc (or circle) here; everything else is kept exactly as drawn.

Terminal identifiers are kept as pin ids, so a derived symbol connects the
same way as the original: wires reference terminals by id, and replacing a
placed symbol by its derivative keeps the wires on terminals that still exist.
"""
from __future__ import annotations

import copy
import math

from .base import SymbolDef
from .custom import CATEGORIES, blank_symbol, new_symbol_id, normalise

MAX_STEP_DEG = 15.0      # sampled arcs use <= 12.5 deg steps; regular polygons use far larger ones
MIN_POINTS = 5


def _fit_circle(pts):
    """Least-squares (Kasa) circle fit; None if the points are (nearly) collinear."""
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    suu = svv = suv = suuu = svvv = suvv = svuu = 0.0
    for x, y in pts:
        u, v = x - mx, y - my
        suu += u * u
        svv += v * v
        suv += u * v
        suuu += u * u * u
        svvv += v * v * v
        suvv += u * v * v
        svuu += v * u * u
    det = suu * svv - suv * suv
    if abs(det) < 1e-12:
        return None
    a = 0.5 * (suuu + suvv)
    b = 0.5 * (svvv + svuu)
    uc = (a * svv - b * suv) / det
    vc = (b * suu - a * suv) / det
    cx, cy = uc + mx, vc + my
    r = sum(math.hypot(x - cx, y - cy) for x, y in pts) / n
    return cx, cy, r


def _angle(cx, cy, p):
    """Angle in degrees, counter-clockwise as seen on screen (Y down), like geometry.arc_points."""
    return math.degrees(math.atan2(-(p[1] - cy), p[0] - cx))


def recognise_arc(prim: dict) -> dict | None:
    """Return an arc (or circle) primitive equivalent to a sampled-arc
    polyline, or None if `prim` is not one."""
    if prim.get("k") != "line":
        return None
    pts = [tuple(p) for p in prim["pts"]]
    if len(pts) < MIN_POINTS:
        return None
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    chord = math.hypot(x1 - x0, y1 - y0)
    if chord > 1e-9:       # reject straight runs: points must bulge away from the chord
        bulge = max(abs((x1 - x0) * (y0 - y) - (x0 - x) * (y1 - y0)) / chord for x, y in pts)
        if bulge < 0.2:
            return None
    fit = _fit_circle(pts)
    if fit is None:
        return None
    cx, cy, r = fit
    if not (0.5 <= r <= 10000):
        return None
    if max(abs(math.hypot(x - cx, y - cy) - r) for x, y in pts) > max(0.02, r * 1e-3):
        return None
    steps = []
    for a, b in zip(pts, pts[1:]):
        d = (_angle(cx, cy, b) - _angle(cx, cy, a) + 180.0) % 360.0 - 180.0
        steps.append(d)
    mean = sum(steps) / len(steps)
    if abs(mean) < 1e-6 or abs(mean) > MAX_STEP_DEG:
        return None
    if any((d > 0) != (mean > 0) or abs(d - mean) > max(0.05, abs(mean) * 0.01) for d in steps):
        return None
    extent = sum(steps)
    if abs(extent) > 360.0 + 1e-6:
        return None
    style = {"w": prim.get("w", "normal"), "dash": bool(prim.get("dash", False))}
    c = (round(cx, 4), round(cy, 4))
    r = round(r, 4)
    if abs(abs(extent) - 360.0) < 0.5:
        return {"k": "circle", "c": c, "r": r, "fill": False, **style}
    start = _angle(cx, cy, pts[0])
    if extent < 0:                       # same arc, counter-clockwise from its other end
        start, extent = start + extent, -extent
    return {"k": "arc", "c": c, "r": r, "start": round(start % 360.0, 4), "extent": round(extent, 4), **style}


def recognise_arcs(prims) -> list:
    out = []
    for p in prims:
        out.append(recognise_arc(p) or p)
    return out


def _plain(prim: dict) -> dict:
    """JSON-friendly copy (tuples -> lists) of a primitive."""
    q = copy.deepcopy(prim)
    if "pts" in q:
        q["pts"] = [[float(x), float(y)] for x, y in q["pts"]]
    for key in ("c", "p"):
        if key in q:
            q[key] = [float(q[key][0]), float(q[key][1])]
    return q


def symbol_to_doc(sd: SymbolDef, params: dict | None = None, as_copy: bool = True) -> dict:
    """Editable custom-symbol document for `sd`.

    `params` selects the variant of a parametric built-in (e.g. a configured
    valve). With `as_copy` (always the case for built-ins) the document gets a
    new id, revision 0, a "(copy)" name and a `derived_from` reference, so
    saving it can never overwrite the original. Without it a custom symbol is
    returned unchanged for in-place editing."""
    if sd.is_custom:
        doc = normalise(copy.deepcopy(sd.custom))
        if as_copy:
            src = {"id": doc["id"], "name": doc["name"], "revision": str(doc["revision"])}
            doc.update(id=new_symbol_id(), revision=0, name=f"{doc['name']} (copy)"[:120], derived_from=src)
        return normalise(doc)
    g = sd.build(params)
    m = blank_symbol(f"{sd.name} (custom)", sd.category if sd.category in CATEGORIES else "General")
    m.update(description=sd.description, group=sd.group, prefix=sd.prefix,
             convention=f"Custom (based on {sd.convention})", tags=list(sd.keywords),
             derived_from={"id": sd.id, "name": sd.name})
    m["prims"] = [_plain(p) for p in recognise_arcs(g.prims)]
    # Built-in designations are shown when the project setting is on, so the
    # copy numbers its points the same way (show=True).
    m["pins"] = [{"id": t.name, "name": t.label or t.name, "x": float(t.x), "y": float(t.y), "dir": t.dir,
                  "type": sd.port_type(t), "show": True} for t in g.terminals]
    return normalise(m)
