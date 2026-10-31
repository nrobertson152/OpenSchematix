# Boundary fill (`FILL` / `HATCH`)

Fills an enclosed area solid, like AutoCAD's HATCH command with a solid pattern and pick points.

## Using it

1. Type `FILL` (aliases `HATCH`, `H`), use *Draw ▸ Fill (hatch)* or the Fill button on the toolbar.
2. Click inside each area you want filled. Every click makes one independent fill object; the command
   keeps running so you can fill several areas. Press Enter (or right-click) to finish.
3. The new fills are selected when the command ends. Everything one `FILL` command made is a single
   undo step.

Grid snap and object snap are not applied to the pick (a snapped pick would land on a boundary line).

**Gap tolerance.** Type `G` (Gap) at the prompt and enter a distance in millimetres (0–10 mm). Openings up
to that size are closed with a straight bridge before the area is found: an open end is joined to the
nearest other open end or, failing that, to the nearest edge. The default 0 accepts only closed boundaries.
The value is remembered in the preferences (`fill_gap_mm`). End points closer than 0.0025 mm always count as
touching, so drawings imported from CAD with rounding noise close properly at gap 0.

## What forms a boundary

* Lines, polylines, polygons, rectangles, circles and arcs on **visible** layers of the current sheet.
* Boundaries may be made of separate objects, of objects that cross or overshoot each other, of partial
  segments (only the part between intersections is used), of objects that share edges or are drawn twice,
  and of tangent curves.
* Not boundaries: wires, symbols, text and existing fills. A fill drawn under a circuit is therefore not cut
  up by its wiring.

## What gets filled

The smallest closed area around the picked point. Separate geometry lying completely inside that area
(islands) is left open as holes; an island's own inside is not filled (pick inside it to fill it separately).
An island joined to the boundary by a line is still a hole. Lines that dangle into the area (stubs,
overshoots, stray lines) do not split it and are covered by the fill.

The pick is refused, with a message in the command log, when the point is outside every closed boundary,
when the boundary is open (larger than the gap tolerance), when the point lies on a boundary, or when the
area would be degenerate. Nothing is ever filled on a guess.

## The fill object

* An exact vector region: straight edges stay straight, arcs and circles stay true arcs (stored as DXF-style
  bulges), filled with the even-odd rule. No rasterisation anywhere.
* Independent of its boundary: moving, trimming or deleting the boundary lines does not change the fill.
* Can be selected (click inside it; anything drawn over it — a line, a symbol — wins the click, and a click in
  a hole does not select it), moved, copied, rotated, scaled, mirrored, deleted, grouped, locked, put on a
  layer, copied and pasted, and undone/redone like any other drafting object.
* Drawn underneath all other objects, so its boundary lines stay visible.
* The Properties panel shows its area, number of holes and extent.
* Not available in the symbol editor (fills are sheet objects; the symbol format has no filled regions with
  holes).

## Saving and exporting

* Saved in the project as a `hatch` shape (see [FILE_FORMAT.md](FILE_FORMAT.md)). Projects that contain
  fills are written with sheet schema 3; projects without fills keep schema 2 and still open in 1.0.x.
* **SVG:** one `<path>` per fill with `fill-rule="evenodd"`; arcs are SVG elliptical-arc commands (exact).
* **PDF:** one path per fill filled with the even-odd operator `f*`; arcs are cubic Béziers (≤ 90° pieces,
  radial error below 0.03 %).
* **DXF (R12):** one block of SOLID trapezoids per fill, inserted on the fill's layer; arc edges are
  approximated with at most 0.005 mm chord error (see [DXF.md](DXF.md)).

## Limits

* Solid fills only (no hatch patterns, gradients or transparency).
* Fills are not associative: changing the boundary does not update the fill (delete and refill).
* The island rule is fixed ("outer": islands are holes, islands within islands are not filled by the same
  pick).
* Boundary detection considers every boundary object on the sheet. Typical picks take well under a second;
  `tools/bench_boundary_fill.py` measures representative cases (for example 0.08 s for a sheet with 3 300
  sparse objects and ~290 islands, 0.2 s for the same sheet with a 1 mm gap tolerance, 0.6 s for 400 densely
  crossing lines and arcs). `tools/fuzz_boundary_fill.py` checks degenerate drawings (huge and tiny radii,
  near-parallel and concurrent lines, sub-tolerance noise, far-from-origin coordinates, tangent chains).

## Display compatibility

Tk canvas polygons cannot have holes, so a fill is drawn as one polygon whose holes are joined to the outer
boundary by zero-width cuts; holes are oriented opposite to the outer ring, so the result is the same under
the even-odd and the non-zero fill rule. The GUI test suite, including on-screen pixel checks of fills, holes,
islands, selection, zoom, pan and move, passes under Tk 8.6.13 and Tk 9.0.3 on Linux (X11). On Windows, Tk
8.6 and 9.0 fill polygons with GDI's ALTERNATE (even-odd) mode by default (`tkWinDraw.c`); this has been
checked in the Tk source but not run on Windows.
