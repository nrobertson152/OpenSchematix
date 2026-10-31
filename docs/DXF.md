# DXF import and export

OpenSchematix reads and writes DXF with its own code (no external libraries). Exported files were validated
with [ezdxf](https://ezdxf.mozman.at/) (no audit errors) during development; the automated test suite repeats
this check when ezdxf is available.

## Export (*File ▸ Export ▸ DXF*)

* Format: AutoCAD **R12 ASCII DXF** (`AC1009`), the most widely supported dialect (AutoCAD, BricsCAD,
  DraftSight, LibreCAD, QCAD, FreeCAD, …).
* Units: **millimetres**, true model size (the sheet's print scale is not applied, so dimensions measured in
  CAD are real drawing dimensions). R12 has no units header; set the drawing units to millimetres in your CAD
  program if it asks.
* Coordinates: origin at the lower-left corner of the sheet, Y up.
* Content: frame and title block (layer `FRAME`), wires (`Wires`), symbols exploded into lines, polylines,
  circles and solids on their OpenSchematix layer, text as TEXT entities with alignment, filled dots as
  donuts, dashed lines with the `DASHED` linetype. Layer names are made DXF-safe (spaces become `_`).
* Boundary fills (`FILL` / `HATCH`): R12 has no HATCH entity, so each fill is written as one block
  (`OSX_FILL_<n>`, inserted once at the origin on the fill's layer) made of SOLID trapezoids that tile the
  region exactly, holes left open. Straight edges are exact; arc edges are approximated with a chord error of
  at most 0.005 mm. In CAD the fill selects as one object and can be exploded into its SOLIDs. Some
  anti-aliased viewers show hairline seams between the SOLIDs on screen; printed output is unaffected.
* Not exported: symbol identities as blocks/attributes (everything is exploded geometry), screen-only markers.

## Import (*File ▸ Import ▸ DXF drawing*)

Reads ASCII DXF of any version (R12 to 2018 and later).

| Entity | Import |
|---|---|
| LINE, CIRCLE, ARC | editable line / circle / arc |
| LWPOLYLINE, POLYLINE (2D) | editable polyline or closed polygon; arc segments (bulges) are approximated by short lines |
| TEXT, ATTRIB, MTEXT | editable text (position, height, rotation, alignment); MTEXT formatting codes are removed and each line becomes a text object |
| SOLID, TRACE | filled polygon |
| INSERT (blocks) | exploded with insertion point, scale, rotation and mirroring; nested blocks up to 8 levels |
| DIMENSION | exploded from the dimension's block, so it appears as lines, arrows and text (no longer associative) |
| ELLIPSE, SPLINE | approximated by polylines (spline: through its fit points, else its control points) |
| HATCH, IMAGE, 3D entities, 3D meshes, others | skipped and listed in the import summary |

* **Units:** taken from `$INSUNITS` (inches, feet, mm, cm, m, …). If the file does not specify units,
  millimetres are assumed (or inches when `$MEASUREMENT` says imperial). You can override the units and add
  an extra scale factor in the import dialog.
* **Placement:** centred in the drawing area of the target sheet, or with the DXF origin at the sheet's
  lower-left corner. You can import onto the current sheet or a new sheet.
* **Layers:** each DXF layer becomes a project layer of the same name, with its colour when the DXF layer has
  one of the standard colours (1–9).
* Imported geometry is ordinary drafting geometry: it can be moved, trimmed, extended, restyled and deleted.
  It does not become symbols or wires, so it is not part of the connectivity model.

## Known limitations

* Binary DXF and DWG files are not supported (save as ASCII DXF in your CAD program).
* Line weights and linetype scales are not carried over; dashed linetypes become dashed lines.
* Paper-space layouts and viewports are ignored; only model space is imported.
* Text fonts are not carried over (OpenSchematix uses Helvetica/Arial-style fonts).
* Very large drawings (more than 200 000 entities) are refused to keep the editor responsive.
* Exported fills are SOLID blocks, not associative HATCH entities (R12 limitation); imported HATCH entities
  are skipped.
