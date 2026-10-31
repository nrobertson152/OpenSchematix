# OpenSchematix - Development Progress

_Last updated: 2026-10-31 (session 5: Phase 1 merged into main; Phase 2 item 6 (import/explode symbols) complete on
branch `phase2-symbol-import-explode`, not merged). Read this first when resuming development._

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
