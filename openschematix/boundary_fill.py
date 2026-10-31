"""Conservative boundary detection for the FILL command.

Only closed, non-branching contours are accepted. Intersecting segments,
nested holes and open gaps are intentionally rejected rather than filled
incorrectly. Geometry is expressed in drawing units.
"""
from __future__ import annotations

import math

from .shapes import point_in_polygon


def _area(points):
    return sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(points, points[1:] + points[:1])) / 2


def _key(p, tolerance):
    return (round(p[0] / tolerance), round(p[1] / tolerance))


def closed_contours(shapes, tolerance=1e-5):
    """Find isolated closed contours assembled from drafting primitives."""
    edges = []
    contours = []
    for shape in shapes:
        if shape.kind in ("polygon", "rect") and len(shape.pts) >= 3:
            contours.append(list(shape.pts))
        elif shape.kind == "circle" and shape.r > 0:
            contours.append([(shape.c[0] + shape.r * math.cos(2 * math.pi * i / 120),
                              shape.c[1] + shape.r * math.sin(2 * math.pi * i / 120))
                             for i in range(120)])
        elif shape.kind in ("line", "polyline"):
            edges.extend((a, b) for a, b in zip(shape.pts, shape.pts[1:])
                         if math.dist(a, b) > tolerance)
    nodes = {}
    for i, (a, b) in enumerate(edges):
        nodes.setdefault(_key(a, tolerance), []).append((i, 0))
        nodes.setdefault(_key(b, tolerance), []).append((i, 1))
    visited = set()
    for i, (a, b) in enumerate(edges):
        if i in visited:
            continue
        path = []
        component = set()
        pending = [i]
        while pending:
            e = pending.pop()
            if e in component:
                continue
            component.add(e)
            for p in edges[e]:
                pending.extend(j for j, _ in nodes[_key(p, tolerance)]
                               if j not in component)
        visited.update(component)
        if not all(len(nodes[_key(p, tolerance)]) == 2
                   for e in component for p in edges[e]):
            continue
        current = _key(a, tolerance)
        start = current
        previous = None
        for _ in range(len(component)):
            choices = [(j, side) for j, side in nodes[current] if j != previous]
            if len(choices) != 1:
                break
            j, side = choices[0]
            path.append(edges[j][side])
            current = _key(edges[j][1 - side], tolerance)
            previous = j
        if current == start and len(path) >= 3 and len(path) == len(component):
            contours.append(path)
    return [p for p in contours if abs(_area(p)) > tolerance ** 2]


def find_boundary(shapes, point):
    """Return the smallest enclosing simple contour, or None.

    Nested contours are not yet supported: filling between nested rings
    requires a multi-ring vector shape and even-odd export semantics.
    """
    contours = closed_contours(shapes)
    inside = [p for p in contours if point_in_polygon(point, p)]
    if len(inside) != 1:
        return None
    return inside[0]
