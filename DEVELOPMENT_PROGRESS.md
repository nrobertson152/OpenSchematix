# OpenSchematix - Development Progress

_Last updated: 2026-10-31 (session 7: boundary-fill stabilisation — schema/revision compatibility, Tk 8.6
verification, performance — on `feature/boundary-fill`, draft PR #4, not merged. Session 6: boundary fill (FILL/HATCH)
implemented. Session 5: Phase 2 item 6 (import/explode symbols)). Read this
first when resuming development._

## Release / branding

Current public release is **v1.0.1** (earlier internal versions 2.0/3.0 are not used publicly). No publisher name appears in the program; copyright holder is Nate Robertson. Source is on GitHub: https://github.com/nrobertson152/OpenSchematix

## Multi-phase development specification (current objective)

The master specification (symbol editor, drafting, usability, i18n) is implemented one phase at a time; stop after
each phase for authorisation. Order: **Phase 1 ✅ (merged)** → Phase 2 (item 5 line-end arrows: **being done
separately by another developer — do not touch arrowhead code here**; item 6 import/explode symbols **✅ on branch
`phase2-symbol-import-explode`**) → Phase 3
(i18n: EN/DE/FR/ES) → Phase 4 (sketch-import feasibility report only) → Phase 5 (scripting architecture proposal
only) → revision-history verification (verify, do not rewrite).

### Phase 1 — symbol editor defects and basic usability (done, session 4)

1. **Duplicate terminal numbers.** Root cause: `symbols/custom.build_geometry` appended a text prim for every pin
   with `show: true` (the default) to the symbol *artwork*, independent of the project setting
   `show_terminal_labels`; with the setting on, `render.terminal_label_prims` drew a second set. Fix: artwork no
   longer contains pin labels; `Terminal` has a `show` flag (default True) from the pin's `show`;
   `render.terminal_label_prims` is the only place designations are drawn: setting on → every terminal with
   `show`, setting off → only component overrides (`terminal_labels`). The editor checkbox is now "Number this
   point on drawings". File formats unchanged (`show` already existed). Visible change: existing custom symbols
   lose their always-on numbers unless the project setting is on.
2. **ANSI A default.** `project.DEFAULT_SHEET_SIZE = "ANSI A"` used by `new_project()`, the settings default
   `default_sheet` and `App._default_size()` fallback. The `Sheet` dataclass default stays "A3" on purpose: it
   is the value used when a file has no `size`, so old files keep their size. Saved Preferences are respected
   (settings.json stores all keys, so existing installs keep whatever is stored). Built-in project templates
   (A3/A4/ANSI B) unchanged.
3. **Tooltips.** Defect: `IconButton` bound `<Enter>/<Leave>` without `add="+"`, replacing the tooltip's handlers
   — no IconButton tooltip ever showed. Fixed (and the tooltip now hides on click). New
   `commands.tooltip()/typed_forms()` format "Description (Ctrl+Z · type U)" from the command registry, keymap
   and user aliases; `cadcmds.TOOL_TIPS` holds the drafting-tool descriptions shared by both toolbars. Main
   toolbar tips are rebuilt on shortcut changes (`App._rebuild_toolbar_tips`, now also for panel toggles,
   preferences and theme). Symbol-editor Save button and section chevrons got tooltips.
4. **Symbol-editor command line.** Defects: no Space confirmation (Space was inserted), Enter/Space on the
   drawing did nothing while a command ran, user aliases ignored, no repeat-last-command. Fix: the editor now
   hosts the shared `cmdline.CommandLine` (new `host` parameter: object with `runner`, `canvas`,
   `execute_input`; optional `available_commands` filters autocomplete). `SymbolEditor.execute_input` resolves
   through `commands.resolve` with user aliases; `EDITOR_COMMANDS` = drafting commands + UNDO/REDO/ZOOM/SAVE/HELP.
   Space on buttons/check boxes and inside text/coordinate prompts keeps its normal meaning. Also fixed in the
   shared command line: Enter/Space before the last key's release accepted a stale autocomplete entry
   (`_refresh_popup`).

Affected files: `symbols/base.py`, `symbols/custom.py`, `render.py`, `project.py`, `settings.py`, `commands.py`,
`gui/app.py`, `gui/cadcmds.py`, `gui/cmdline.py`, `gui/symbol_editor.py`, `gui/widgets.py`, `tests/test_phase1.py`
(new), `tests/test_engine.py` (two size assertions now use the sheet's size), `tests/gui_smoke.py` (+22 checks),
`tools/gen_command_docs.py` + `docs/COMMANDS.md`, `docs/LIBRARY_FORMAT.md`, `CHANGELOG.md`.

Phase 1 test results (session 4): `pytest` **246 passed, 0 skipped** (with ezdxf); `tests/gui_smoke.py` under
Xvfb **105/105 ok** (83 previous + 22 new). New tests were confirmed to fail on the pre-fix code (9 unit tests;
GUI: page size, hidden/duplicate numbers, tooltip, command line). ANSI A PDF with title block inspected.
Next action: Phase 2, item 5 (line-end arrows) — only after authorisation.

### Phase 2, item 6 — open existing symbols as editable copies (done, session 5)

- **Already present before:** built-ins opened as a copy (`SymbolEditor._from_builtin`), custom symbols in place,
  "Save as new symbol". Gaps fixed: built-in arcs arrived as sampled polylines (not editable arcs); configured
  valves opened as the default variant; copied built-in pins had `show=False` (inconsistent with Phase 1);
  project-only custom symbols were edited under their original id; no way to open a symbol from inside the
  editor; no record of where a copy came from; Save-as kept the old name.
- **Core (GUI independent):** new `symbols/explode.py`. `symbol_to_doc(sd, params=None, as_copy=True)` returns a
  normalised custom-symbol document: copies get a new id, revision 0 and `derived_from`; pins keep ids (built-in
  terminal names), positions, directions, port types (`sd.port_type`), names; built-ins get `show=True`.
  `recognise_arc()` turns a polyline of ≥5 points lying evenly on a circle (least-squares fit, radial tolerance
  max(0.02, r·1e-3), uniform steps ≤ 15°, must bulge from its chord) back into a native arc, or a circle at 360°.
  Over the 78 built-ins: 29 arcs recovered in 11 symbols; zigzags, springs and the AC sine wave stay polylines;
  primitive count and order unchanged.
- **Format:** `custom.normalise` keeps an optional `derived_from` {id, name, revision} (strings); documents without
  it normalise exactly as before; symbol format version stays 1; project files unchanged.
- **GUI:** `App.open_symbol_editor(copy_of=, params=)` (+ `from_builtin` kept), `App.edit_symbol_copy(sid, params)`;
  "Edit a copy…" in the library context menu (all symbols), drawing context menu and inspector (passes the
  component's params); library edit button opens built-in and project-only symbols as copies; editor toolbar
  button / `OPEN` command (`SymbolEditor.open_existing`, picker centred on the editor via new `Dialog(parent=)`);
  save button reads "Save to library" for new/copies and "Save changes" when editing a library symbol in place;
  "Save as new symbol…" prompts for a name and records `derived_from`; Symbol tab shows "Based on …".
- **Not changed:** arrowhead code (item 5), file formats other than the optional key, built-in symbol definitions.
- **Files:** `symbols/explode.py` (new), `symbols/custom.py`, `gui/symbol_editor.py`, `gui/app.py`,
  `gui/library.py`, `gui/inspector.py`, `gui/dialogs.py`, `tests/test_symbol_import.py` (new, 98 tests incl. one
  per built-in symbol), `tests/gui_smoke.py` (+20 checks; also renamed a Phase 1 loop variable that shadowed the
  `key()` helper), `docs/LIBRARY_FORMAT.md`, `README.md`, `CHANGELOG.md`, this file.
- **Tests (session 5):** `pytest` **344 passed, 0 skipped**; `tests/gui_smoke.py` under Xvfb **125/125 ok**.
- **Limitations:** an arc drawn as part of a longer polyline (arc + straight segments in one primitive) stays a
  polyline; only the two parametric valves take `params`; copying does not replace placed components
  automatically (use *Replace symbol*; wires on matching terminal ids stay connected).
- **Next action:** wait for authorisation (Phase 3 localisation, or merging item 5 from the other branch).

### Boundary fill — FILL / HATCH (done, session 6, branch `feature/boundary-fill`, PR #4)

The owner's brief calls this "Phase 3: Boundary Fill"; the earlier specification above listed localisation as
Phase 3 — the numbering is for the owner to reconcile. The draft on the branch (closed-contour chaining that
rejected intersections and holes, fills stored as plain polygons, a failing test) was replaced.

- **Engine (`boundary_fill.py`, GUI independent):** planar arrangement. Shapes → elementary edges (segments,
  arcs ≤ 90°, world angles = −screen angles); pairwise intersections via sort-and-sweep on bounding boxes
  (segment/segment, segment/circle and circle/circle with tangency tolerance, plus "end point on edge" for
  T-junctions, overlaps and near misses); points within `SNAP_TOL` = 0.01 units (0.0025 mm) merged by grid
  hashing; edges split at vertices, identical pieces deduplicated (shared edges, duplicates, co-circular
  overlaps); dangling pieces pruned; half-edges sorted by tangent angle with curvature tie-break; faces traced
  "next clockwise" (bounded faces positive area). Pick = smallest bounded face containing the point; edges walked
  on both sides of the face (bridges) dropped so joined islands become separate rings; other connected
  components inside the face become holes unless nested in another such component. Rings simplified (collinear
  segments / co-circular arcs ≤ 180° merged). Rejects: no geometry, point outside all faces (open boundary),
  point within `SNAP_TOL` of an edge, degenerate area. Optional gap tolerance (≤ 40 units / 10 mm) adds straight
  bridges from open ends to the nearest open end or edge, then re-runs the arrangement.
- **Regions (`regions.py`):** rings of `(x, y, bulge)` (DXF bulge convention in world coordinates, |b| ≤ 1);
  exact signed area (shoelace + circular segments), exact even-odd containment (arcs split into y-monotone
  pieces), bbox, boundary distance, flattening by chord tolerance, arc splitting, transforms (mirror negates
  bulges), validation (`clean_rings`), slab trapezoid decomposition for DXF SOLIDs.
- **Model / format:** `Shape(kind="hatch", rings=…)`; `to_dict` writes `rings` (bulge omitted when 0), no
  width/dash/fill. `SHEET_SCHEMA = FILE_SCHEMA = 3`; `Document.required_schema()` returns 3 only when the sheet
  has fills, `projectio.write_zip` writes the max over sheets → files without fills stay schema 2 (1.0.x
  compatible). Revision snapshots are not considered (a 1.0.x reader could open a fill-free project whose old
  revisions contain fills and fail only when restoring that revision).
- **Shapes:** bbox, prims (`{"k": "region", "rings", "fill": True}`), move/rotate/scale/mirror, hit distance
  (0 inside, distance to boundary outside / in holes), snap/grip points at vertices, not a TRIM/EXTEND edge,
  `trim()` returns None. `render.scene` draws fills before other shapes; `editing.hit_test` tests fills last
  (after components) and prefers the smallest fill.
- **Output:** canvas = one Tk polygon per fill with keyhole cuts (holes oriented opposite → same result under
  even-odd and non-zero), chord error ⅓ px; SVG = `<path fill-rule="evenodd">` with `A` arcs; PDF = path with
  Bézier arcs + `f*`; DXF R12 = per fill a block `OSX_FILL_n` of SOLID trapezoids + INSERT on the fill's layer
  (arc chord error 0.005 mm). `paper_items` scales `rings`; `prim_bbox` handles `region`.
- **GUI:** `cadcmds.cmd_fill` loop (Enter finishes, keyword Gap → `GetNumber` mm stored in setting
  `fill_gap_mm`), `GetPoint(osnap=False, snap_grid=False)` (new `osnap` field honoured by
  `SchematicCanvas.resolve_point`); host hook `App.fill_boundary_shapes()` = drafting shapes on visible layers
  except text/fills (wires and symbols are deliberately not boundaries); toolbar button (new `fill` icon), Draw
  menu entry, aliases HATCH/H; inspector shows area/holes/extent and hides line style for fills; FILL excluded
  from the symbol editor (`EDITOR_COMMANDS`), `shape_to_symbol_prim` degrades a fill to a filled outer polygon
  defensively.
- **Files:** `boundary_fill.py` (rewritten), `regions.py` (new), `model.py`, `__init__.py`, `projectio.py`,
  `shapes.py`, `render.py`, `editing.py`, `export.py`, `dxf.py`, `symbols/base.py`, `settings.py`, `commands.py`,
  `gui/cadcmds.py`, `gui/canvas_view.py`, `gui/interact.py`, `gui/app.py`, `gui/inspector.py`, `gui/icons.py`,
  `gui/symbol_editor.py`, `tests/test_boundary_fill.py` (rewritten, 67 tests), `tests/gui_smoke.py` (+31
  checks), docs (`BOUNDARY_FILL.md` new, `FILE_FORMAT.md`, `DXF.md`, `COMMANDS.md` regenerated), README,
  CHANGELOG.
- **Tests (session 6, Python 3.13 / Tk 9.0, ezdxf 1.4.6b0 from source, pypdf, pypdfium2):** `pytest` **421
  passed, 0 skipped**; `tests/gui_smoke.py` under Xvfb **165/165 ok** (main: 354 / 134). Exports checked on real
  files: SVG rendered in Chromium, PDF rasterised with pdfium (fill black, hole white), DXF audited and rendered
  with ezdxf (SOLID area = region area within 3·10⁻⁴); randomised consistency test (any interior pick of a found
  region finds the same region; exact area = finely flattened area).
- **Limitations:** solid fills only; not associative; fixed "outer" island rule; DXF fills are SOLID blocks (R12
  has no HATCH; some anti-aliased viewers show hairline seams); imported DXF HATCH still skipped and our
  exported fill blocks re-import as many filled polygons; boundary search is global per pick (≈0.2 s for 3 300
  sparse objects, seconds for thousands of densely crossing ones).
- **Next action:** owner review of PR #4; do not merge without authorisation.

#### Session 7 — stabilisation and compatibility (same branch)

- **Defect 1 (fixed): fills only in revision history were saved as schema 2.** Reproduced with the released
  v1.0.0 code (extracted from the tag): it opened such a project and failed with "unknown shape kind 'hatch'"
  only when restoring that revision. Now `projectio.required_schema(project)` = max(current sheets,
  `RevisionStore.required_schema()`), the latter scanning every snapshot sheet object (`model.sheet_dict_schema`,
  cached per content hash; objects are immutable). Schema drops back to 2 once no snapshot holds a fill.
  Templates with fills are written as `.ostpl` version 2 (1.0.x refuses them as newer instead of "damaged").
  Tests: `tests/test_fill_compat.py` (13) — including running the real v1.0.0 reader (`git archive v1.0.0`,
  skipped without git/tag) against files written now: fill files refused, fill-free files open.
- **Tk 8.6:** python-build-standalone Tk 8.6.12/8.6.14 builds abort on `tk.Menu` under Xvfb (xcb assertion,
  also on `main`: a toolchain defect, not ours), so Tcl/Tk 8.6.13 was built from source (no Xft) with a
  `_tkinter` built for the system Python 3.13 (wrapper `/home/claude/tk86/py86` in the dev container, not in
  the repo). Results: pytest 447 passed / 1 skipped (ezdxf subprocess probe), GUI smoke 169/169. The only
  failures before were two **test** defects (menubar cascades indexed by position; Tk 8.6 menubars have a
  tear-off entry at index 0) — fixed in the test. New pixel checks in `gui_smoke.py` (ImageMagick `import`, 24-bit
  display; skipped otherwise): fill, empty hole, separately filled island, selection colour, zoom, pan, MOVE —
  identical results under Tk 8.6.13 and 9.0.3. Windows: Tk's GC default fill rule is EvenOddRule → GDI
  ALTERNATE (`win/tkWinDraw.c`); source-checked only, not run.
- **Defect 2 (fixed): gap tolerance was O(open ends × edges)** — 33.2 s for a 3 300-object sheet. Now
  sort-and-sweep candidate pairs (`_point_edge_pairs`, `_point_point_pairs`): 0.21 s; output proven identical to
  the old all-pairs algorithm (reference copy in the tests, 12 randomised drawings × 3 gaps, incl. exact ties).
- **Measured speed-ups (no behaviour change):** island nesting with bounding-box prefilters (sparse sheet 0.28 →
  0.08 s); cycle area / bbox computed from edge data, bulge rings built lazily (dense 400 lines+arcs 0.73 → 0.61 s,
  600 circles 0.69 → 0.59 s). Areas and hole counts identical before/after on every benchmark case.
- **Robustness:** `tools/fuzz_boundary_fill.py` (7 degenerate scenario families × 30 seeds, 1 398 accepted
  regions): 0 failures before and after — no numerical defect found, so the arrangement maths was not changed.
- **Python 3.10.14** (minimum supported; pbs build, Tk 8.6.12): pytest 445 passed / 3 skipped (pypdfium2, ezdxf);
  GUI not runnable there (same pbs Menu abort).

### Phase 4 (performance) — optimization 1: connectivity spatial index (session 8, branch `perf/connectivity-index`)

- Baseline (`tools/bench_phase4.py`, new): `connectivity.analyse` was 90–95 % of every canvas redraw and
  O(points × wires); a hover change on a 1,152-component sheet froze the editor ~10 s.
- Change: `connectivity._WireIndex`, a uniform grid (50-unit cells) of wires by padded segment bounding box,
  built per call and used only to narrow which wires `counts_at` tests. Per-wire tests, tolerances and output
  order unchanged; no caching. Padding is tol + 1 because `point_on_segment` accepts points up to tol/length
  beyond very short diagonal segments (pre-existing behaviour, preserved). Memory is linear: segments over 256
  cells, non-finite wires and anything beyond a 32-per-segment registration budget are always examined.
- Tests: `tests/test_connectivity_index.py` (oracle = verbatim old algorithm; seeded differential fuzz,
  tolerance/cell-boundary/overshoot/degenerate/non-finite/huge-segment cases, memory bound, superset property,
  example projects).
- Result: analyse 19×/72×/193× faster (small/medium/large); full redraw 0.14→0.03 s, 1.06→0.11 s,
  10.1→0.57 s. analyse peak memory +26 % (index). Next candidate: `editing.crossings()` (now the largest
  redraw cost on large sheets) — not started.

### Phase 4 (performance) — optimization 2: crossing-detection index (session 9, branch `perf/crossing-detection`)

- Contract: `crossings()` pairs only a "horizontal" segment (|dy| < 0.01) with a non-horizontal one, treats the
  latter as vertical at the x of its FIRST point (x extent ignored — diagonals included), requires strict
  0.01 margins on both ranges, then the interior/corner filters; output in (i, j) segment-pair order with
  duplicates. The pair test is now `editing._crossing_pair` (body unchanged).
- Change: horizontals registered in the grid cells of their row, others in the cells of their column (50-unit
  cells, per call). A row and a column share at most one cell, so each candidate pair is found once; per
  segment i the candidates j > i are tested in increasing j, so order is unchanged. Non-finite, > 256-cell
  and over-budget (32·S + 4096 registrations) segments are paired with every opposite segment (original
  behaviour). No caching.
- Tests: `tests/test_crossings_index.py` (40; oracle = verbatim old algorithm).
- Result (median of 7, main @ 81a8da2 → branch): crossings 0.0025→0.0006 s / 0.036→0.0028 s / 0.337→0.0093 s;
  full redraw large 0.56→0.22 s, medium 0.104→0.074 s, small unchanged within noise. Peak memory of the call
  on large 188 KiB → 1.27 MiB (linear in segments).

### Phase 4 (performance) — optimization 3: hover highlighting without redraws (session 10, branch `perf/hover-highlighting`)

- Root cause: `SchematicCanvas._on_motion` (select tool) and `_on_leave` called `redraw()` on every hover
  change; `_redraw_now` deletes all canvas items and reruns connectivity, crossings, scene and Tk item creation,
  although hover only changes the color of the hovered object's own items (not width, dash or order;
  selected items never show hover).
- Change (`gui/canvas_view.py` only): `draw_items(hover_index=)` records (document item, canvas id) for every
  hoverable canvas item (not overridden, not selected) with two list appends, plus the normal color of items
  drawn hovered. `SchematicCanvas._set_hover` recolors only the old and new hovered objects' items via
  `recolor()` (replaces whichever of fill/outline is non-empty, exactly as draw_items colors them) and
  remembers the previous color to restore. The item map is built lazily on first hover and discarded by every
  full redraw; if a redraw is already pending the redraw draws the new hover itself.
- Tests: `tests/test_hover_highlighting.py` (28, real App under Tk; compare complete canvas snapshots —
  type, coords, options, stacking order — of incremental hover vs a full redraw with the same state).
- Result (median of 9, main @ 0e2823b → branch): hover change 0.048→0.0022 s / 0.103→0.0028 s /
  0.266→0.0057 s; full redraw unchanged within noise (interleaved 5 rounds: medium 0.074→0.075 s, large
  0.222→0.229 s medians); redraw peak memory large 5.0→5.4 MiB.

### v1.1.0 engineering correctness — multi-unit BOM quantities (branch `fix/bom-multi-unit-quantities`)

- Defect (reproduced on main @ 5b0f46b): `bom.generate` counted every schematic symbol as a physical part, so
  relay K1 drawn as coil + 2 contacts was ordered 3× (also in `examples/start_stop_latch.osch`).
- Device identity uses the existing, documented model (check.py duplicate-id rule, docs/VALIDATION.md):
  purchasable non-terminal components with the same identifier are one device; terminal-block terminals and
  components without identifier are individual parts. No schema or file-format change.
- Line choice per device: part-number units decide (pn-less units absorbed; several distinct part numbers →
  counted once on each line + new check rule `device-parts`, warning); else units with description/rating;
  else one line naming the distinct symbols. Sheet-filtered BOM: device included if any unit is on the
  selected sheets, identity from all its units.
- Review follow-up (shared identifiers hiding unrelated devices): a group is merged only if no two of its
  symbols share symbol, label and terminal designations (the duplicate-id criterion); otherwise every symbol
  counts (pre-fix behaviour) and duplicate-id / device-parts report it. Groups that differ by label, terminal
  numbers or symbol stay merged: they are the documented multi-unit pattern and cannot be told apart from
  two devices without explicit device data (owner decision; would need a schema field).
- Tests: `tests/test_bom_devices.py` (20; 11 fail on main, the 4 clash tests fail on the first PR head).
  Full pytest 620 passed / 3 skipped (ezdxf), GUI smoke 168/168.

### v1.1.0 cycle 2 — symbol editor and symbol aliases (branch `feature/symbol-editor-aliases`)

- Pin numbers: the renderer and the PDF/SVG/DXF exports already honoured `pins[].show` (Phase 1). The defects
  were in the editor: the "Number this point" checkbox (and type/direction) only took effect on Apply and was
  lost when saving first; the editor canvas drew every pin name. Now: form changes apply immediately (Enter in
  the name field), save applies pending form edits (only when the form holds the selected point), hidden
  numbers are not drawn on the editor canvas (muted "(n)" while selected) and are listed as "(n)".
- Keyboard (editor, matching the main window's keymap defaults): Ctrl+A, arrow-key nudge (2.5 mm grid when
  connection points are selected so they stay on the grid; else the snap step), Ctrl+Shift+Z, Caps-Lock-safe
  Ctrl shortcuts. Space behaviour (Phase 1) unchanged.
- Aliases: optional `aliases` list in `.osym` docs (`symbols/custom.py`: `clean_aliases`, `alias_problems`;
  `SymbolDef.aliases`; `symbols.resolve()`; search text; `userlib` search, save check, import drops colliding
  ones; every copy path drops them; library details panel; `INSERT <alias>`). Drawings store canonical ids.
  Built-in symbols have no aliases (not editable).
- Review (integration prep): `symbols.resolve()` also compares ids case-insensitively and returns nothing unless
  exactly one symbol matches; aliases may not equal another symbol's name; INSERT order is exact id, exact name,
  alias, search (keeps pre-alias behaviour for names). Real 1.0.0 reader verified (tag v1.0.0) for `.osym` and
  projects with aliases. PR #30 overlap: on merge, `doc.pop("aliases", None)` belongs in its `_as_copy()`.
- Tests: `tests/test_symbol_aliases.py` (16), `tests/test_symbol_editor_pins.py` (11, Tk). Full pytest 661 passed /
  3 skipped (ezdxf), GUI smoke 168/168.

## Status summary

**Version 1.0.1 (originally developed internally as "3.0") is implemented and tested on Linux** (engine + GUI). All 25 sections of the brief are
implemented; a few sub-items are deliberately limited and documented (see *Known limitations*).
**Still to do before public release:** build and test on Windows; build the Linux bundle with a distribution
Python whose Tk has Xft fonts (see *Packaging*); manual usability pass on real hardware.

## Architecture (1.0)

- **Python 3.10+ standard library only; GUI in Tkinter/ttk.** Qt was not an option (PyPI blocked in the
  development sandbox, licence/size). DXF and PDF are written with our own code; ezdxf is used only in tests
  to validate DXF output.
- **Units:** 1 drawing unit = 0.25 mm; grid 10 units (2.5 mm); terminals on grid; Y down internally.
  User-facing coordinates (status bar, command line) are mm with origin at the sheet's lower-left, Y up.
- **Model:** `Project` (project.py) → ordered `Document` sheets (model.py) with `components`, `wires`,
  `shapes` (drafting). Persistent identity = (sheet uid, object id); ids never reused (`next_id` saved).
  Component `props` (standard + custom), `terminal_labels`, `layer`, `locked`, `group`, `in_bom`.
  Wire `number`/`number_manual`/`props`. Project `meta`, `settings`, `layers`, embedded custom `symbols`.
  `Document.project` back-reference gives project-wide designators to existing editing code.
- **Connectivity rule (unchanged):** wire ends connect to wires/terminals; crossings don't connect.
  Junction = wires *split* at the point (`editing.connect_crossing`), so no separate junction table is needed
  and junctions persist through moves/saves. Crossings are computed (`editing.crossings`) and drawn with a
  bridge by `render.wire_prims`; `check` uses the same functions → picture and model agree.
- **Nets** (netlist.py) union-find over all sheets; sheet connectors (`gen.offpage`) join by label.
  Wire numbers are per net, stable, manual overrides; electrical nets only.
- **One renderer** (render.scene) for screen, PDF, SVG, DXF; title blocks/zones in titleblock.py in paper
  units scaled by the sheet's presentation scale (`Sheet.scale`; frame grows in model space).
- **File format:** `.schematix` ZIP (projectio.py, docs/FILE_FORMAT.md); container version 1, sheet schema 2;
  atomic + verified saves. `.osch` (schema 1) and `.hpss` migrate to a new unsaved project.
- **Revisions:** content-addressed snapshots inside the project (revisions.py); auto on save (25 kept) and
  approved revisions (kept forever, shown in title-block revision tables). compare.py diffs by ids.
- **Symbols:** built-in registry + user library overlay + project overlay (embedded versions win for the
  open project). Custom symbols (symbols/custom.py) keep pin ids permanent; arcs flattened at build time.
- **GUI:** gui/theme.py design system (6 UI themes × canvas palettes, recolouring in place — the 2.0 menu
  bug fix), icons.py vector icons, widgets.py, canvas_view.py (DrawingView/PreviewView/SchematicCanvas),
  interact.py (generator-based commands + CommandRunner), cadcmds.py (LINE…EXTEND, shared with the symbol
  editor via host hooks), cmdline.py, keymap.py (customisable shortcuts), panels.py, inspector.py,
  library.py, dialogs.py, reports.py, revisions_ui.py, symbol_editor.py, app.py (window + actions).
- **Undo:** whole-project JSON snapshots (150 levels). Simple and reliable; cost grows with project size.

## Completed work (session 2)

All phases 1–8 of the brief:
1. Theme-switch bug fixed (menus recoloured in place; GUI test switches through all themes twice).
2. Model/project/file format/migration (+ tests). 3. CAD primitives, TRIM/EXTEND, object snap, ortho,
   command line, shortcuts. 4. Symbol editor, user libraries, `.osymlib` sharing, circuit templates,
   properties inspector. 5. Multi-sheet projects, search, autosave/recovery. 6. BOM, wire numbering,
   terminals, connection reports, Check Drawing. 7. DXF, ANSI/ISO/custom sheets, title-block styles,
   revision tables, multi-page PDF. 8. Revisions + comparison, themes, QoL (layers, groups, locks, align,
   selection filters, favourites/recent, context menus, status bar), docs, packaging.
- Examples: `examples/demo_project.schematix` (built by tools/make_demo_project.py) + the 2.0 `.osch` files.
- Docs: README, CHANGELOG, docs/FILE_FORMAT.md, LIBRARY_FORMAT.md, DXF.md, VALIDATION.md, COMMANDS.md
  (generated), SYMBOLS.md (generated).

## Testing results (session 2)

- `pytest`: **231 passed** (180 from 2.0, updated for new theme names; 51 new engine tests in
  `tests/test_engine.py`: model/ids, project ops, .schematix round trip, atomic save, newer-version
  refusal, .osch/.hpss migration without touching originals, revisions dedupe/prune/restore, compare by ids,
  shape transforms, intersections, TRIM/EXTEND, crossings/connect/disconnect, scale preserving nets,
  fit-to-sheet, cross-sheet nets/xrefs, wire numbering stability/manual/renumber, reports/CSV safety,
  terminal strips, BOM, search, check rules, custom symbols, libraries + packages (conflicts, unsafe paths),
  templates, autosave/recovery/cleanup, DXF round trip + R2018 sample + **ezdxf validation (0 audit
  errors)**, multi-page PDF sizes/outline/page numbers, scaled sheets, title-block styles, command parsing).
- `tests/gui_smoke.py` under Xvfb: **83/83 checks passed** using real Tk events and menu invocation:
  repeated theme switching via the menu, placing/wiring/dragging, Ctrl+Z/Y, typing commands on the canvas,
  LINE/CIRCLE/RECTANGLE/TRIM/MOVE/ROTATE with clicks and typed coordinates, connect/disconnect junctions,
  inspector editing (single and multi), sheets/tabs/xrefs, search navigation, check, BOM + CSV, reports,
  wire numbers, groups, layers, panel toggles, templates, symbol editor (rectangle, pins, line, save, place,
  edit pin name → wires stay connected), library package preview, revisions/compare/restore, save/reopen,
  PDF/DXF export, DXF import, layout scaling, autosave, all dialogs, sheet/project templates, crash-recovery
  prompt. Screenshots of every theme were inspected.
- Linux PyInstaller build (PyInstaller 6.22.3 from GitHub sources, uv CPython 3.12, Tk 9.0): built
  (44 MB), `--version` works, GUI launched with the demo project under Xvfb and was inspected.
- Run: `EZDXF_PYTHON=<python with ezdxf> EZDXF_PATH=<ezdxf src> python -m pytest` (ezdxf test skips otherwise);
  `xvfb-run -a python tests/gui_smoke.py OUT` (SHOT_CMD="import -window root {}" for screenshots).

## Known defects / limitations

- **Linux bundle fonts:** the sandbox's standalone Python has a Tk without Xft, so the bundle built here uses
  core X fonts (no anti-aliasing; some Unicode glyphs missing). Build releases with distro Python + python3-tk
  (build_linux.sh warns). Windows Tk is unaffected.
- Windows: build, installer (now also .schematix association), DPI awareness untested.
- Panels: resizable, collapsible, remembered — not floating/undockable; toolbars not customisable.
- Symbols rotate in 90° steps; drafting objects rotate freely.
- PDF text is WinAnsi (cp1252) Helvetica; other characters print as `?`.
- Undo snapshots and full redraws scale with project size; fine for typical projects (tested up to a few
  hundred parts), not tuned for very large ones.
- Check Drawing's electrical port rules only bite for custom symbols with typed pins (built-in electrical
  pins are `elec.passive`).
- Project-wide BOM/reports windows refresh on every change (fine for normal sizes).
- DXF export explodes symbols (no blocks/attributes); R12 has no units header.

## Next steps (in order)

1. **Windows verification:** `packaging\build_windows.bat` on Windows 10/11 with python.org Python 3.12.
   Check launch, icons, HiDPI (125–200 %), .schematix/.osch association, installer/uninstaller, mouse wheel,
   Ctrl shortcuts, file dialogs, Print.
2. **Linux release build** on Ubuntu 22.04/24.04 with system Python + python3-tk (Xft fonts), then
   `install.sh` and the MIME types.
3. Manual usability pass with a real mouse (double-click timing, drag-and-drop from the library, context
   menus, command-line feel).
4. 3.1 candidates: floating panels, customisable toolbar, DXF export with blocks/attributes, PDF with embedded
   TrueType fonts (Unicode), PLC I/O symbols, more ISO 1219 symbols, cable/harness reports, incremental
   undo/redraw for very large projects.

## Resuming in a new session

Sandbox recipe that works (session 4): system Python has no Tk and PyPI/apt are blocked, but
`uv python install 3.12` (from GitHub) has Tk 9.0 and `git clone --depth 1 https://github.com/mozman/ezdxf`
gives ezdxf. Then:
`EZDXF_PYTHON=python3 EZDXF_PATH=/tmp/ezdxf-src/src python3 -m pytest -q tests` and
`xvfb-run -a -s "-screen 0 1600x1000x24" $(uv python find 3.12) tests/gui_smoke.py OUT`.

Older notes:

Source: GitHub repository nrobertson152/OpenSchematix. Unzip, then `python -m pytest`. In a sandbox without
system Tk: `uv python install 3.12` (includes Tkinter); PyPI may be blocked — clone pytest-free deps from
GitHub or copy pure-Python packages; PyInstaller/altgraph/pyinstaller-hooks-contrib can be cloned from GitHub
and used via PYTHONPATH (bootloaders are in the repo). Standalone-Python builds need
`LD_LIBRARY_PATH=<python>/lib` for Tk.

## Python scripting API, phase 1 (`feature/python-scripting-api`)

- New package `openschematix/api/`:
  - `__init__.py`: public surface (`__all__`);
  - `_core.py`: handles (`Project`, `Sheet`, `Component`, `Wire`) and entry points;
  - `types.py`: frozen value types;
  - `errors.py`: the `ApiError` hierarchy.

  It is a thin layer over `editing`, `projectio`, `connectivity`, `netlist`, `bom` and `check`. No
  existing module was changed.
- **Decisions:**
  - Handles hold (project, sheet uid, object id) and resolve the object on each access. A removed
    object raises `ObjectNotFoundError`.
  - Strict validation, so input that the engine would silently correct raises instead:
    - off-grid insertion points;
    - rotations other than 0/90/180/270;
    - non-orthogonal or fractional wires;
    - invalid valve parameters (the builder would fall back to defaults);
    - a parameter change that would orphan a wired terminal;
    - locked objects or layers.
  - Symbol registry: it is process-wide, so every entry point re-activates its project's embedded
    symbols (`_activate`). `load_user_library` always re-publishes, because `UserLibrary.scan()` leaves
    the registry untouched for a missing folder.
- The example script lives in `docs/examples/`: tests in `test_connectivity_index.py` and
  `test_crossings_index.py` open every entry of `examples/` as a drawing.
- Tests: `tests/test_scripting_api.py` (68), including a subprocess test with tkinter blocked and no
  display.
- Not covered yet (documented): drafting shapes, layers, page setup beyond paper size, manual wire
  numbers, terminal overrides, revisions, exports, undo.
