# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-31

First public release of **OpenSchematix**: a free, offline schematic editor for electrical, electronic, hydraulic and pneumatic circuits with multi-sheet projects, CAD drafting, custom symbols and libraries, engineering reports, revision management and a modern interface.

### Interface
- Design system with central theme tokens, six themes (Modern Light, Modern Dark, Graphite, Neutral Gray, Blueprint, High Contrast) plus independent canvas colours; themes switch in place without a restart.
- Vector icon set (sharp at any DPI), sidebars with Symbols/Sheets/Templates and Properties/Layers, bottom dock with Output/Check/Search, status bar with GRID/SNAP/ORTHO/OSNAP toggles, layer, print scale, coordinates, zoom and check results, non-intrusive notifications, remembered layout.
- Symbol library of 77 built-in symbols (IEC 60617, IEEE 315 / ANSI, NEMA ladder and ISO 1219-1 conventions), configurable hydraulic and pneumatic directional control valves.

### Added — projects and documentation
- `.schematix` project format: versioned ZIP container with JSON manifest, one JSON file per sheet,
  embedded custom symbols and revision history; atomic, verified saving. Documented in `docs/FILE_FORMAT.md`.
- Multiple sheets per project: add, duplicate, rename, reorder, delete, sheet tabs, next/previous sheet,
  sheet templates (reuse a sheet's page setup) and project templates. Identifiers are unique project-wide.
- Sheet connectors with automatic cross-reference text (`/sheet.zone`), nets across sheets.
- Opening legacy `.osch` drawings and older-format files converts them to projects without modifying the originals.
- Sheet sizes ISO A0–A4, ANSI A–E, Letter, Legal, Tabloid and custom; portrait/landscape; reference zones.
- Title-block styles (standard, compact, ISO 7200 style, none) fed by project metadata with per-sheet
  overrides: drawing and sheet numbers, revision, drawn/checked/approved, dates, scale.
- Revision tables in title blocks, filled from formally issued revisions.
- Print (presentation) scale per sheet, standard engineering scales, *Fit drawing to sheet*; separate
  *Scale drawing layout* that moves parts apart or together without resizing symbols or breaking connections.
- Multi-page vector PDF of all or selected sheets, each page at its own size, with bookmarks and page labels.

### Added — drafting and editing
- Drafting objects: lines, polylines, rectangles, circles, arcs and text, with line width, dash and fill.
- CAD commands: MOVE, COPY, ROTATE (any angle for drafting, 90° steps for symbols), MIRROR (any axis),
  SCALE, TRIM, EXTEND, ERASE, with grid snap, object snap (end, mid, centre, quadrant, intersection,
  terminal), ortho, rubber-band previews and typed coordinates (`x,y`, `@dx,dy`, `@d<angle`).
- Command line with autocomplete, aliases (L, C, M, CO, TR, RO, SC, …), history, keyword options and
  context prompts; every command uses the same operations as menus and toolbars and is undoable.
- Customisable keyboard shortcuts with conflict detection and a reference (*Help ▸ Keyboard shortcuts*).
- Wire crossings drawn with a bridge (or gap / plain, configurable); *Connect wires* adds a junction,
  *Disconnect junction* removes it; junction dot size configurable. Junctions persist through moves and saves.
- Layers (visibility, lock, print, colour, current layer), grouping, object locking, align and distribute,
  selection filters, window and crossing selection, hover highlight, context-sensitive right-click menus.
- Clipboard works across sheets; pasted and inserted components get new identifiers, and parts of one device
  (a coil and its contacts) keep sharing their identifier.

### Added — symbols, libraries and templates
- Symbol editor with the same drafting tools, connection points (name/number, port type, lead direction,
  shown or hidden), insertion point, metadata, tags and default part properties. Built-in symbols can be
  copied and modified. Editing a symbol never disconnects existing drawings (pins have permanent ids);
  projects keep the version they were drawn with until you choose to update.
- User symbol libraries with nested folders: create, rename, move, copy, delete, drag and drop, search,
  categories and tags; import/export single symbols (`.osym`). Built-in library is read-only.
- Library packages (`.osymlib`) with preview, conflict detection, merge or separate import, and
  skip/replace/keep-both handling. Documented in `docs/LIBRARY_FORMAT.md`.
- Favourite and recently used symbols; drag symbols onto the drawing.
- Circuit templates (built-in: relay latch, DOL motor starter, hydraulic cylinder with 4/3 valve, pneumatic
  cylinder with 5/2 valve; plus your own) with folders, previews, import/export and automatic renumbering.
- New *Sheet connector* symbol.

### Added — engineering data and checks
- Component properties: description, manufacturer, part number, rating, terminal designations, custom
  properties, include-in-BOM flag, layer, lock; multi-selection editing.
- Automatic bill of materials grouped by part, with sorting, filtering, exclusion of non-purchasable items and
  spreadsheet-safe CSV export (UTF-8 BOM, CRLF, formula-injection protection).
- Automatic wire numbering with conventions (sequential or per sheet, prefix, start, step, digits), stable
  numbers when parts move, manual overrides per connection, renumbering.
- Terminal strips (X1:1, X1:2 …) with automatic terminal numbering and a strip report; connection (from-to)
  lists and wire lists; all exportable as CSV.
- Project-wide search by identifier, symbol type, description, manufacturer, part number, wire number,
  terminal and custom properties, with navigation to the object.
- Check Drawing with a results panel (severity, issue, object, sheet, zone, suggested action, click to go):
  duplicate identifiers and terminals, unconnected terminals, dangling wires, incompatible port domains,
  fluid-power and electrical port rules, missing identifiers, unresolved cross-references, overlapping wires,
  wires passing over terminals, ambiguous junctions, missing or incomplete symbols, wire-number conflicts.
  Rules documented in `docs/VALIDATION.md`.

### Added — interoperability, history and safety
- DXF import (LINE, LWPOLYLINE with bulges, POLYLINE, CIRCLE, ARC, ELLIPSE, SPLINE, TEXT, MTEXT, SOLID, INSERT,
  DIMENSION; units from `$INSUNITS`; layers and colours) as editable geometry, and DXF R12 export.
  Exported files validate with ezdxf. Documented in `docs/DXF.md`.
- Revision history stored in the project (content-addressed, unchanged sheets stored once): automatic
  snapshots on save, formally issued revisions, view, restore (undoable) and graphical comparison
  (overlay or side by side; added/removed/modified objects and changed connections, matched by persistent ids).
- Autosave to a separate recovery folder (configurable interval, three snapshots kept), recovery prompt
  after an unexpected exit, automatic clean-up of old recovery data.

Older single-sheet drawing formats can be opened and converted into projects.
