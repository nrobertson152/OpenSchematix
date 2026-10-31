"""Boundary detection for the FILL / HATCH command.

Given the drafting shapes on a sheet and a picked point, find the smallest
region enclosing the point that is bounded by the shapes' edges, together
with any islands (holes) inside it, and return it as exact vector rings
(see :mod:`openschematix.regions`).

Method (a planar arrangement, as used by CAD boundary/hatch commands):

1. Every line, polyline, polygon, rectangle, circle and arc is broken into
   elementary edges: straight segments and circular arcs of at most 90°.
2. All edges are intersected with each other (proper crossings, tangencies,
   T-junctions, collinear / co-circular overlaps and end points that lie on
   another edge within the snap tolerance). Points closer than the snap
   tolerance are merged into one vertex, so near-coincident end points and
   duplicated geometry connect cleanly.
3. Edges are split at every vertex; identical pieces (shared edges, objects
   drawn twice) are kept once. Dangling pieces (open ends, overshoots,
   stray lines) are removed repeatedly because they cannot bound a region.
4. Around every vertex the outgoing edges are ordered by tangent angle (with
   curvature as the tie-break for tangent curves); walking "next edge
   clockwise" traces every face of the arrangement exactly once. Bounded
   faces have positive signed area, the outside of each connected piece of
   geometry has negative area.
5. The picked region is the bounded face of smallest area containing the
   point. Edges walked on both sides of that face (a line joining an island
   to the boundary) are dropped, which separates the island loops. Separate
   pieces of geometry lying inside the face become holes; islands nested in
   those holes are left alone (pick inside them to fill them separately).

An optional gap tolerance closes small openings: each open end is joined by a
straight bridge to the nearest open end (or edge) within the tolerance
before the arrangement is built. Larger gaps make the boundary open and the
pick is rejected - nothing is ever filled on a guess.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import regions as rg

SNAP_TOL = 0.01            # drawing units (0.0025 mm): end points closer than this coincide
MAX_GAP = 40.0             # largest accepted gap tolerance (10 mm)
HALF_PI = math.pi / 2


@dataclass
class FillResult:
    rings: list | None = None        # bulge rings; first ring is the outer boundary
    message: str = ""
    area: float = 0.0
    holes: int = 0
    bridged: int = 0                 # gaps closed by the gap tolerance
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.rings is not None


# ================================================================ elementary edges
# ("L", p0, p1)  or  ("A", (cx, cy), r, a0, sweep)   (math angles in world coordinates, y down)

def _finite(*vals) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals)


def shape_edges(s) -> list:
    """Elementary edges of one drafting shape (empty for text, fills and
    malformed geometry)."""
    out = []
    kind = getattr(s, "kind", None)
    if kind in ("line", "polyline", "polygon", "rect"):
        pts = [tuple(p) for p in (s.pts or []) if len(p) >= 2 and _finite(p[0], p[1])]
        if len(pts) != len(s.pts or []):
            return []
        pairs = list(zip(pts, pts[1:]))
        if kind in ("polygon", "rect") and len(pts) >= 3:
            pairs.append((pts[-1], pts[0]))
        for a, b in pairs:
            if math.dist(a, b) > 0:
                out.append(("L", (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
    elif kind in ("circle", "arc"):
        c, r = s.c, s.r
        if not (_finite(c[0], c[1], r) and r > 0):
            return []
        if kind == "circle":
            a0, sweep = 0.0, 2 * math.pi
        else:
            if not _finite(s.start, s.extent) or s.extent == 0:
                return []
            start, extent = s.start, s.extent
            if extent < 0:
                start, extent = start + extent, -extent
            extent = min(extent, 360.0)
            # screen angles are counter-clockwise with y down: world angle = -screen angle
            a0, sweep = -math.radians(start), -math.radians(extent)
        n = max(1, int(math.ceil(abs(sweep) / HALF_PI - 1e-9)))
        for i in range(n):
            out.append(("A", (float(c[0]), float(c[1])), float(r), a0 + sweep * i / n, sweep / n))
    return out


def _ends(e):
    if e[0] == "L":
        return e[1], e[2]
    (cx, cy), r, a0, sw = e[1], e[2], e[3], e[4]
    return (cx + r * math.cos(a0), cy + r * math.sin(a0)), (cx + r * math.cos(a0 + sw), cy + r * math.sin(a0 + sw))


def _bbox(e, pad=0.0):
    if e[0] == "L":
        (x0, y0), (x1, y1) = e[1], e[2]
        return (min(x0, x1) - pad, min(y0, y1) - pad, max(x0, x1) + pad, max(y0, y1) + pad)
    p0, p1 = _ends(e)
    xs, ys = [p0[0], p1[0]], [p0[1], p1[1]]
    (cx, cy), r, a0, sw = e[1], e[2], e[3], e[4]
    for q in range(4):
        a = q * HALF_PI
        if rg.angle_in_sweep(a, a0, sw):
            xs.append(cx + r * math.cos(a))
            ys.append(cy + r * math.sin(a))
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def _overlapping_pairs(boxes):
    """Index pairs (i < j) of overlapping boxes (sort and sweep on x)."""
    order = sorted(range(len(boxes)), key=lambda i: boxes[i][0])
    active = []
    for i in order:
        bi = boxes[i]
        active = [j for j in active if boxes[j][2] >= bi[0]]
        for j in active:
            bj = boxes[j]
            if bj[1] <= bi[3] and bi[1] <= bj[3]:
                yield (j, i) if j < i else (i, j)
        active.append(i)


# ---------------------------------------------------------------- parameters and projections
def _param(e, p) -> float:
    """Position of point p along edge e (0..1)."""
    if e[0] == "L":
        (x0, y0), (x1, y1) = e[1], e[2]
        dx, dy = x1 - x0, y1 - y0
        return ((p[0] - x0) * dx + (p[1] - y0) * dy) / (dx * dx + dy * dy)
    (cx, cy), _r, a0, sw = e[1], e[2], e[3], e[4]
    a = math.atan2(p[1] - cy, p[0] - cx)
    d = (a - a0) % rg.TAU if sw > 0 else (a0 - a) % rg.TAU
    if d > (rg.TAU + abs(sw)) / 2:
        d -= rg.TAU        # just before the start (within tolerance)
    return d / abs(sw)


def _project(e, p, tol, box=None):
    """Closest point of edge e to p if within tol, else None."""
    if box is not None and not (box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]):
        return None
    if e[0] == "L":
        (x0, y0), (x1, y1) = e[1], e[2]
        dx, dy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((p[0] - x0) * dx + (p[1] - y0) * dy) / (dx * dx + dy * dy)))
        q = (x0 + t * dx, y0 + t * dy)
    else:
        (cx, cy), r, a0, sw = e[1], e[2], e[3], e[4]
        a = math.atan2(p[1] - cy, p[0] - cx)
        if rg.angle_in_sweep(a, a0, sw):
            q = (cx + r * math.cos(a), cy + r * math.sin(a))
        else:
            q = min(_ends(e), key=lambda z: math.dist(z, p))
    return q if math.dist(q, p) <= tol else None


def _on_edge(e, p, tol) -> bool:
    return _project(e, p, tol) is not None


def _line_circle(a, b, c, r, tol):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    # foot of the perpendicular from the centre
    t0 = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy
    fx, fy = a[0] + t0 * ux, a[1] + t0 * uy
    d = math.hypot(c[0] - fx, c[1] - fy)
    if d > r + tol:
        return []
    if d >= r - tol:                       # tangent (within tolerance)
        return [(fx, fy)]
    h = math.sqrt(r * r - d * d)
    return [(fx - h * ux, fy - h * uy), (fx + h * ux, fy + h * uy)]


def _circle_circle(c1, r1, c2, r2, tol):
    d = math.dist(c1, c2)
    if d <= tol:
        return []                          # concentric (or same circle: handled as overlap)
    if d > r1 + r2 + tol or d < abs(r1 - r2) - tol:
        return []
    ux, uy = (c2[0] - c1[0]) / d, (c2[1] - c1[1]) / d
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h2 = r1 * r1 - a * a
    mx, my = c1[0] + a * ux, c1[1] + a * uy
    if h2 <= (tol * 0.5) ** 2 or abs(d - (r1 + r2)) <= tol or abs(d - abs(r1 - r2)) <= tol:
        return [(mx, my)]
    h = math.sqrt(h2)
    return [(mx - h * uy, my + h * ux), (mx + h * uy, my - h * ux)]


def _intersections(e1, e2, tol) -> list:
    """Candidate intersection points of two edges (verified to lie on both)."""
    cands = []
    if e1[0] == "L" and e2[0] == "L":
        a, b, c, d = e1[1], e1[2], e2[1], e2[2]
        rx, ry = b[0] - a[0], b[1] - a[1]
        sx, sy = d[0] - c[0], d[1] - c[1]
        den = rx * sy - ry * sx
        if abs(den) > 1e-12 * math.hypot(rx, ry) * math.hypot(sx, sy):
            t = ((c[0] - a[0]) * sy - (c[1] - a[1]) * sx) / den
            cands.append((a[0] + t * rx, a[1] + t * ry))
    elif e1[0] == "L" or e2[0] == "L":
        ln, ar = (e1, e2) if e1[0] == "L" else (e2, e1)
        cands = _line_circle(ln[1], ln[2], ar[1], ar[2], tol)
    else:
        cands = _circle_circle(e1[1], e1[2], e2[1], e2[2], tol)
    return [p for p in cands if _on_edge(e1, p, tol) and _on_edge(e2, p, tol)]


# ================================================================ vertex store
class _Points:
    """Merges points closer than tol (grid hashing)."""

    def __init__(self, tol):
        self.tol = tol
        self.cell = max(tol, 1e-12)
        self.pts = []
        self.grid = {}

    def add(self, p) -> int:
        gx, gy = int(math.floor(p[0] / self.cell)), int(math.floor(p[1] / self.cell))
        best = None
        for i in range(gx - 1, gx + 2):
            for j in range(gy - 1, gy + 2):
                for k in self.grid.get((i, j), ()):
                    d = math.dist(self.pts[k], p)
                    if d <= self.tol and (best is None or d < best[0]):
                        best = (d, k)
        if best is not None:
            return best[1]
        k = len(self.pts)
        self.pts.append((float(p[0]), float(p[1])))
        self.grid.setdefault((gx, gy), []).append(k)
        return k


# ================================================================ arrangement
class Arrangement:
    """Planar arrangement of straight and circular edges."""

    def __init__(self, raw_edges, tol=SNAP_TOL):
        self.tol = tol
        self.vs = _Points(tol)
        self.edges = []            # (u, v, kind, data): data = None for lines, (c, r, sweep_u_to_v) for arcs
        self._build([e for e in raw_edges if self._valid(e)])
        self._prune()
        self._faces()

    def _valid(self, e):
        p0, p1 = _ends(e)
        if e[0] == "L":
            return math.dist(p0, p1) > self.tol
        return e[2] * abs(e[4]) > self.tol

    # ------------------------------------------------------------ splitting
    def _build(self, raw):
        tol = self.tol
        splits = [[] for _ in raw]          # per edge: list of points
        for i, e in enumerate(raw):
            splits[i].extend(_ends(e))
        boxes = [_bbox(e, tol) for e in raw]
        for i, j in _overlapping_pairs(boxes):
            a, b = raw[i], raw[j]
            pts = _intersections(a, b, tol)
            # end points lying on the other edge (T-junctions, overlaps, near misses)
            for p in _ends(a):
                if _project(b, p, tol, boxes[j]) is not None:
                    pts.append(p)
            for p in _ends(b):
                if _project(a, p, tol, boxes[i]) is not None:
                    pts.append(p)
            for p in pts:
                splits[i].append(p)
                splits[j].append(p)
        seen_lines = set()
        seen_arcs = {}
        mids = _Points(tol)
        for e, pts in zip(raw, splits):
            ids = sorted(((_param(e, p), self.vs.add(p)) for p in pts), key=lambda t: t[0])
            chain = []
            for _t, vid in ids:
                if not chain or chain[-1][1] != vid:
                    chain.append((_t, vid))
            for (t0, u), (t1, v) in zip(chain, chain[1:]):
                if u == v:
                    continue
                if e[0] == "L":
                    key = (min(u, v), max(u, v))
                    if key in seen_lines:
                        continue
                    seen_lines.add(key)
                    self.edges.append((u, v, "L", None))
                else:
                    (cx, cy), r, a0, sw = e[1], e[2], e[3], e[4]
                    pu, pv = self.vs.pts[u], self.vs.pts[v]
                    au = math.atan2(pu[1] - cy, pu[0] - cx)
                    av = math.atan2(pv[1] - cy, pv[0] - cx)
                    want = sw * (t1 - t0)
                    d = (av - au) % rg.TAU if want > 0 else -((au - av) % rg.TAU)
                    if abs(d - want) > math.pi:          # numerical wrap
                        d = want
                    if abs(d) * r <= tol / 2:
                        continue
                    am = au + d / 2
                    mid = mids.add((cx + r * math.cos(am), cy + r * math.sin(am)))
                    key = (min(u, v), max(u, v), mid)
                    if key in seen_arcs:
                        continue
                    seen_arcs[key] = True
                    self.edges.append((u, v, "A", ((cx, cy), r, d)))
        self.raw_count = len(raw)

    # ------------------------------------------------------------ dangling edges
    def _prune(self):
        n = len(self.vs.pts)
        inc = [[] for _ in range(n)]
        for k, (u, v, _kind, _d) in enumerate(self.edges):
            inc[u].append(k)
            inc[v].append(k)
        alive = [True] * len(self.edges)
        deg = [len(x) for x in inc]
        stack = [i for i in range(n) if deg[i] == 1]
        while stack:
            i = stack.pop()
            if deg[i] != 1:
                continue
            for k in inc[i]:
                if alive[k]:
                    alive[k] = False
                    u, v = self.edges[k][0], self.edges[k][1]
                    deg[u] -= 1
                    deg[v] -= 1
                    o = v if u == i else u
                    if deg[o] == 1:
                        stack.append(o)
                    break
        self.dangling_removed = alive.count(False)
        self.edges = [e for e, a in zip(self.edges, alive) if a]

    # ------------------------------------------------------------ faces
    def _tangent(self, h):
        """(angle, curvature) of half-edge h leaving its origin."""
        k, rev = h >> 1, h & 1
        u, v, kind, data = self.edges[k]
        a, b = (v, u) if rev else (u, v)
        pa, pb = self.vs.pts[a], self.vs.pts[b]
        if kind == "L":
            ang, curv = math.atan2(pb[1] - pa[1], pb[0] - pa[0]), 0.0
        else:
            (cx, cy), r, sw = data
            s = -1.0 if rev else 1.0
            s = s if sw > 0 else -s
            rx, ry = pa[0] - cx, pa[1] - cy
            ang = math.atan2(s * rx, -s * ry)
            curv = s / r
        ang %= rg.TAU
        if ang > rg.TAU - 1e-9:
            ang -= rg.TAU
        return ang, curv

    def origin(self, h):
        u, v = self.edges[h >> 1][0], self.edges[h >> 1][1]
        return v if h & 1 else u

    def dest(self, h):
        u, v = self.edges[h >> 1][0], self.edges[h >> 1][1]
        return u if h & 1 else v

    def bulge(self, h):
        u, v, kind, data = self.edges[h >> 1]
        if kind == "L":
            return 0.0
        sw = -data[2] if h & 1 else data[2]
        return math.tan(sw / 4)

    def _faces(self):
        out = {}
        for k in range(len(self.edges)):
            for h in (2 * k, 2 * k + 1):
                out.setdefault(self.origin(h), []).append(h)
        angtol = 1e-9

        def key(h):
            a, c = self._tangent(h)
            return (round(a / angtol), c)
        pos = {}
        for vtx, hs in out.items():
            hs.sort(key=key)
            for i, h in enumerate(hs):
                pos[h] = i
        self.out = out
        nxt = {}
        for h in pos:
            t = h ^ 1
            hs = out[self.origin(t)]
            nxt[h] = hs[(pos[t] - 1) % len(hs)]
        self.next = nxt
        seen = set()
        self.cycles = []
        for h in sorted(pos):
            if h in seen:
                continue
            cyc = []
            x = h
            while x not in seen:
                seen.add(x)
                cyc.append(x)
                x = nxt[x]
            self.cycles.append(cyc)
        # connected components (union-find over vertices)
        parent = list(range(len(self.vs.pts)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for u, v, _k, _d in self.edges:
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
        self.comp_of_vertex = find
        self.cycle_info = []
        for cyc in self.cycles:
            ring = self.ring(cyc)
            self.cycle_info.append({"cycle": cyc, "ring": ring, "area": rg.ring_area(ring),
                                    "bbox": rg.rings_bbox([ring]), "comp": find(self.origin(cyc[0]))})

    def distance(self, p) -> float:
        """Distance from p to the nearest remaining edge."""
        best = math.inf
        for k in range(len(self.edges)):
            best = min(best, rg.edge_distance(p, *self._edge_geom(2 * k)))
        return best

    def _edge_geom(self, h):
        a, b = self.vs.pts[self.origin(h)], self.vs.pts[self.dest(h)]
        return a, b, self.bulge(h)

    def ring(self, hs):
        return [(*self.vs.pts[self.origin(h)], self.bulge(h)) for h in hs]

    # ------------------------------------------------------------ bridges
    def split_bridges(self, cyc):
        """Rings of a face boundary after removing edges walked on both sides."""
        edges = [h >> 1 for h in cyc]
        count = {}
        for e in edges:
            count[e] = count.get(e, 0) + 1
        keep = [i for i, h in enumerate(cyc) if count[h >> 1] == 1]
        if len(keep) == len(cyc):
            return [self.ring(cyc)]
        n = len(cyc)
        by_origin = {}
        for i in keep:
            by_origin.setdefault(self.origin(cyc[i]), []).append(i)
        used = set()
        rings = []
        for start in keep:
            if start in used:
                continue
            seq = []
            i = start
            while True:
                used.add(i)
                seq.append(cyc[i])
                end = self.dest(cyc[i])
                cands = by_origin.get(end, [])
                if not cands:
                    break
                nxt = min(cands, key=lambda j: (j - i) % n or n)
                if nxt == start or nxt in used:
                    break
                i = nxt
            if seq and self.origin(seq[0]) == self.dest(seq[-1]):
                rings.append(self.ring(seq))
        return rings


# ================================================================ cleanup
def _simplify(ring, tol):
    """Merge collinear straight edges and co-circular arcs (sweep <= 180°)."""
    ring = list(ring)
    changed = True
    while changed and len(ring) > 2:
        changed = False
        n = len(ring)
        for i in range(n):
            a, b, c = ring[i - 1], ring[i], ring[(i + 1) % n]
            if a[2] == 0 and b[2] == 0:
                ux, uy = b[0] - a[0], b[1] - a[1]
                vx, vy = c[0] - b[0], c[1] - b[1]
                lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
                if lu > 0 and lv > 0 and ux * vx + uy * vy > 0:
                    # perpendicular offset of b from line a-c
                    acx, acy = c[0] - a[0], c[1] - a[1]
                    lac = math.hypot(acx, acy)
                    if lac > 0 and abs((b[0] - a[0]) * acy - (b[1] - a[1]) * acx) / lac <= tol * 1e-2:
                        del ring[i]
                        changed = True
                        break
            elif a[2] and b[2] and (a[2] > 0) == (b[2] > 0):
                c1, r1, _a0, s1 = rg.bulge_arc(a[:2], b[:2], a[2])
                c2, r2, _a1, s2 = rg.bulge_arc(b[:2], c[:2], b[2])
                if math.dist(c1, c2) <= tol * 1e-2 and abs(r1 - r2) <= tol * 1e-2 and abs(s1 + s2) <= math.pi + 1e-9:
                    ring[i - 1] = (a[0], a[1], math.tan((s1 + s2) / 4))
                    del ring[i]
                    changed = True
                    break
    return ring


# ================================================================ public API
def _gap_bridges(raw, gap, tol):
    """Straight bridges closing open ends that are within `gap` of other geometry."""
    vs = _Points(tol)
    deg = {}
    for e in raw:
        for p in _ends(e):
            k = vs.add(p)
            deg[k] = deg.get(k, 0) + 1
    # an end point lying on another edge is not open
    open_ends = []
    for k, d in deg.items():
        if d != 1:
            continue
        p = vs.pts[k]
        if any(_on_edge(e, p, tol) and all(math.dist(p, q) > tol for q in _ends(e)) for e in raw):
            continue
        open_ends.append(p)
    bridges = []
    done = set()
    for i, p in enumerate(open_ends):
        best = None
        for j, q in enumerate(open_ends):
            if j != i:
                d = math.dist(p, q)
                if tol < d <= gap and (best is None or d < best[0]):
                    best = (d, q, ("end", min(i, j), max(i, j)))
        if best is None:
            for e in raw:
                if any(math.dist(p, q) <= tol for q in _ends(e)):
                    continue                     # the edge this end belongs to
                q = _project(e, p, gap)
                if q is not None:
                    d = math.dist(p, q)
                    if d > tol and (best is None or d < best[0]):
                        best = (d, q, ("edge", i, q))
        if best is not None and best[2] not in done:
            done.add(best[2])
            bridges.append(("L", p, best[1]))
    return bridges


def collect_edges(shapes) -> list:
    raw = []
    for s in shapes:
        raw.extend(shape_edges(s))
    return raw


def find_region(shapes, point, gap: float = 0.0, tol: float = SNAP_TOL) -> FillResult:
    """Region enclosing `point` bounded by `shapes` (drafting Shape objects).
    `gap`: largest opening (drawing units) closed automatically."""
    if not (_finite(point[0], point[1])):
        return FillResult(message="Invalid point.")
    raw = collect_edges(shapes)
    if not raw:
        return FillResult(message="There are no lines, arcs or closed shapes to form a boundary.")
    bridged = 0
    gap = max(0.0, min(float(gap or 0.0), MAX_GAP))
    if gap > tol:
        extra = _gap_bridges(raw, gap, tol)
        bridged = len(extra)
        raw = raw + extra
    arr = Arrangement(raw, tol)
    if arr.distance(point) <= tol:
        return FillResult(message="The picked point lies on a boundary; pick inside the region.", bridged=bridged)
    best = None
    for info in arr.cycle_info:
        if info["area"] <= tol * tol:
            continue
        b = info["bbox"]
        if not (b[0] <= point[0] <= b[2] and b[1] <= point[1] <= b[3]):
            continue
        if rg.point_in_rings([info["ring"]], point) and (best is None or info["area"] < best["area"]):
            best = info
    if best is None:
        return FillResult(message="No closed boundary around the picked point (the region is open or the point "
                                  "is outside all boundaries).", bridged=bridged)
    face = [r for r in arr.split_bridges(best["cycle"]) if abs(rg.ring_area(r)) > tol * tol]
    if not face or not rg.point_in_rings(face, point):
        return FillResult(message="The picked point is not inside a fillable region.", bridged=bridged)
    if rg.boundary_distance(face, point) <= tol:
        return FillResult(message="The picked point lies on a boundary; pick inside the region.", bridged=bridged)
    # islands: other pieces of geometry inside the face
    comp = best["comp"]
    outers = {}
    for info in arr.cycle_info:
        if info["comp"] != comp and info["area"] < 0:
            outers.setdefault(info["comp"], []).append(info)
    cands = {}
    for c, infos in outers.items():
        rep = infos[0]["ring"][0][:2]
        if rg.point_in_rings(face, rep):
            rings = [r for info in infos for r in arr.split_bridges(info["cycle"])
                     if abs(rg.ring_area(r)) > tol * tol]
            if rings:
                cands[c] = (rep, rings)
    holes = []
    for c, (rep, rings) in cands.items():
        if any(d != c and rg.point_in_rings(other, rep) for d, (_r, other) in cands.items()):
            continue                          # nested inside another island
        holes.extend(rings)
    outer = [r for r in face if rg.ring_area(r) > 0]
    inner = [r for r in face if rg.ring_area(r) < 0]
    rings = [_simplify(r, tol) for r in outer + inner + holes]
    rings = [r if (i < len(outer)) == (rg.ring_area(r) > 0) else rg.reverse_ring(r) for i, r in enumerate(rings)]
    area = rg.region_area(rings)
    if area <= tol * tol:
        return FillResult(message="The region is too small to fill.", bridged=bridged)
    res = FillResult(rings=rings, area=area, holes=len(rings) - len(outer), bridged=bridged,
                     message=f"Filled region ({len(rings) - len(outer)} hole(s)).")
    if arr.dangling_removed:
        res.warnings.append(f"{arr.dangling_removed} open edge piece(s) ignored")
    return res


__all__ = ["find_region", "FillResult", "Arrangement", "shape_edges", "collect_edges", "SNAP_TOL", "MAX_GAP"]
