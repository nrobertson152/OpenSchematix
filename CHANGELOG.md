# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Symbol aliases: a custom symbol can have extra identifiers (symbol editor, *Symbol* tab, "Aliases"). The library
  search, the symbol pickers and `INSERT <alias>` find it by them; drawings always store the symbol itself.
  Aliases are unique among all symbols (collisions with symbol ids or other aliases are refused) and are not
  copied to derived symbols. Stored as an optional `aliases` list in `.osym` documents (format version unchanged).
- Symbol editor: Ctrl+A selects everything, arrow keys move the selection (by the 2.5 mm grid when it contains
  connection points, otherwise by the snap step), Ctrl+Shift+Z redoes, and the shortcuts also work with Caps Lock;
  Enter in a connection point's name field applies it.

- Boundary fill: `FILL` (aliases `HATCH`, `H`, *Draw ▸ Fill (hatch)*, toolbar button). Click inside areas
  enclosed by lines, polylines, polygons, rectangles, circles and arcs to fill them solid — boundaries may be
  made of separate, crossing, overshooting, overlapping or partial segments and tangent curves. Islands inside
  the area become holes; open boundaries, picks outside all boundaries and picks on a boundary are refused
  with an explanation. Optional gap tolerance (`G`, 0–10 mm) closes small openings. Fills are exact vector
  regions (arcs stay arcs), independent objects that can be selected, moved, copied, rotated, scaled,
  mirrored, deleted and undone, are drawn underneath other objects, and export to SVG (even-odd path with
  arcs), PDF (even-odd fill) and DXF (block of SOLIDs). See `docs/BOUNDARY_FILL.md`.
- `tools/bench_boundary_fill.py` and `tools/fuzz_boundary_fill.py`: boundary-fill benchmarks and robustness fuzz.
- `tools/bench_phase4.py`: reproducible performance baseline (connectivity, crossings, scene, canvas redraw
  split into CPU and Tk time, hit-testing, object snap, undo snapshots, boundary fill, save/load, peak memory).

- Adjustable vector arrowheads at either or both ends of drafting lines and polylines, with
  Properties inspector and custom symbol editor controls, project persistence and exports.
- Optional arrowhead settings for custom symbol line primitives.


- Open any existing symbol — built-in, user library or project — in the symbol editor as an editable copy:
  *Edit a copy…* in the library and on placed components (a configured valve opens as configured), the editor's
  *Open existing symbol* button (or `OPEN`), and the library's edit button for built-in symbols. The symbol is
  converted into individual lines, polylines, arcs, circles and text; arcs that built-in symbols store as sampled
  polylines become real arcs again. Connection points keep their identifiers, positions, lead directions and port
  types. Saving a copy always creates a new symbol (new id) and records what it was derived from; the original is
  never changed.
- *Save as new symbol…* asks for a name. When a library symbol is edited in place the primary button reads
  *Save changes* and its tooltip says that it overwrites the symbol.


### Fixed

- Symbol editor: clearing "Number this point on drawings" (and changing a connection point's port type or lead
  direction) took effect only after pressing Apply, and was lost if the symbol was saved first; it now applies
  immediately, and pending edits are applied when saving. A point that is not numbered no longer shows its number
  on the editor canvas (only while selected, in parentheses) and is listed as "(1)".

- Bill of materials: a device drawn with several symbols that share one identifier (relay coil K1 and its
  contacts) is counted once instead of once per symbol. Symbols without purchasing data are absorbed into
  the device's line; a device without any part data is listed once with its symbols named ("Coil … +
  Contact, make (NO)"). Terminal-block terminals and components without an identifier are still counted
  individually. Symbols are only merged when they can be parts of one device: if two of them have the same
  symbol, label and terminal designations (an identifier clash, reported by *Duplicate identifiers*), every
  symbol of that identifier is counted as before. A new drawing check ("Identifiers shared by several
  symbols") reports devices whose symbols carry different part numbers (listed once per part number) and
  clashes the duplicate-identifier check misses.
- Custom symbols: terminal numbers were drawn on every placed custom symbol even with *Show terminal designations*
  off, and twice with it on. Pin designations are no longer baked into the symbol artwork; they are drawn once by
  the renderer and follow the project setting like built-in symbols. A pin can opt out ("Number this point on
  drawings" in the symbol editor); a designation typed for a placed component always shows. Symbol and project
  files are unchanged; existing custom symbols now follow the setting.
- Toolbar tooltips never appeared (the button's own hover handlers replaced the tooltip's).
- Symbol editor command line: Space now runs a typed command or alias (L, C, TR, M …) like Enter; Enter or Space
  on the drawing finishes the running command or repeats the last one; user aliases and autocomplete work. The
  editor uses the same command-line component as the main window.
- Command line (both editors): pressing Enter or Space quickly after the last letter could run the stale
  autocomplete suggestion (e.g. TR started TEXT, CO started CIRCLE).

### Changed
- Performance: connection analysis (junction dots, open wire ends, open terminals) uses a per-call spatial
  grid index instead of testing every wire for every wire end and corner. Results are identical; canvas
  redraws on a 1,152-component / 1,728-wire sheet drop from about 10 s to about 0.6 s (see
  `tools/bench_phase4.py`). No caching was introduced.
- Performance: wire-crossing detection (bridges/gaps, crossing checks) only tests pairs of wire segments
  that share a cell of a per-call grid index instead of every pair. Results and their order are identical;
  crossing detection on the 1,152-component benchmark sheet drops from 0.34 s to 0.009 s and a full canvas
  redraw from about 0.56 s to about 0.22 s. No caching was introduced.
- Performance: moving the mouse onto, off or between objects no longer redraws the whole drawing; only the
  colors of the previously and newly highlighted objects' canvas items change. Appearance is unchanged; a
  hover change on the 1,152-component benchmark sheet takes about 6 ms instead of about 0.27 s.
- File format: new `hatch` drafting shape and sheet schema 3. Projects and `.osch` sheets are written with the
  lowest schema that can hold their content, so files without fills remain schema 2 and open in 1.0.x;
  1.0.x refuses files with fills with a clear "newer schema" message. A fill stored only in the revision
  history also makes a project schema 3 (otherwise 1.0.x opened it and failed when restoring that revision).
  Circuit templates containing fills are written as template version 2.
- Clicking a point now selects anything drawn over a fill before the fill itself.
- New drawings and projects default to ANSI A (8.5 × 11 in, landscape). Existing files keep their page size and
  a default sheet size already chosen in Preferences is kept.
- Toolbar tooltips in both editors describe the function and give the shortcut and the alias to type, from one
  shared table.

## [1.0.1] - 2026-10-30

- Corrected startup splash-screen and panel layout initialization.
- Removed obsolete historical product branding.
- Updated release packaging and application version metadata.

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
