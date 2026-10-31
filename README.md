# OpenSchematix

**Free and open-source schematic editor for electrical, electronic, hydraulic and pneumatic circuits.**
Windows and Linux. Version 1.0.0.

Copyright © 2026 Nate Robertson.
Licensed under the GNU General Public License v3.0 or later (see `LICENSE`).

OpenSchematix is for technicians, engineers, students and hobbyists who need clear, conventional circuit
drawings without a CAD licence. It works fully offline and has no accounts, telemetry, advertisements or
feature limits. If you find it useful you can optionally [support development on Ko-fi](https://ko-fi.com/nr270343).

## Features

- **Projects with multiple sheets** in one `.schematix` file, with project-wide identifiers, sheet tabs,
  sheet connectors with automatic cross-references (`/2.C4`), sheet and project templates.
- **A modern CAD workspace**: vector icons, six themes (Modern Light/Dark, Graphite, Neutral Gray, Blueprint,
  High Contrast) with separate canvas colours, collapsible sidebars, a context-sensitive properties inspector,
  and an **AutoCAD-style command line** with autocomplete, history and typed coordinates.
- **Drafting tools**: line, polyline, rectangle, circle, arc and text; move, copy, rotate, mirror, scale,
  TRIM and EXTEND; grid snap, object snap (end, mid, centre, quadrant, intersection, terminal) and ortho.
- **Custom symbols**: a symbol editor with named, numbered and typed connection points, saved in your own
  **symbol libraries** (folders, tags, search, drag and drop) and shared as `.osymlib` packages.
- **Wire crossings shown with bridges**; right-click *Connect wires* adds a junction and *Disconnect junction*
  removes it. Drawing and connectivity always agree.
- **Engineering data**: component properties (manufacturer, part number, rating, custom fields), automatic
  **bill of materials**, **wire numbering**, terminal strips, connection and wire lists (CSV), project-wide
  **search** and **Check Drawing**.
- **Documentation**: ISO A0–A4, ANSI A–E, Letter/Legal/Tabloid and custom sheets, three title-block styles,
  reference zones, revision tables, print scales and *Fit drawing to sheet*, multi-page PDF.
- **DXF import and export**, **revision history** with graphical comparison, **autosave and crash recovery**,
  reusable **circuit templates**, layers, grouping, locking, alignment.

The release notes are in [`CHANGELOG.md`](CHANGELOG.md).

## Installing

**Windows:** run `OpenSchematix-1.0.0-Setup-x64.exe` (no administrator rights needed), or use the portable
`OpenSchematix` folder and run `OpenSchematix.exe`. You do not need to install Python.

**Linux (x86-64):** extract `OpenSchematix-1.0.0-linux-x86_64.tar.gz`, then run `OpenSchematix/OpenSchematix`
directly or run `OpenSchematix/install.sh` to add a menu entry, icon, `openschematix` command and the
`.schematix` / `.osch` file types for your user. `install.sh --uninstall` removes it.

**From source (any OS):** Python 3.10 or newer with Tkinter (Debian/Ubuntu: `sudo apt install python3-tk`).
There are no other dependencies.

```
python -m openschematix [project.schematix | drawing.osch]
```

Examples are in `examples/`: `demo_project.schematix` (three sheets: supply, motor control, hydraulics),
and the single-sheet drawings `start_stop_latch.osch` and `hydraulic_cylinder_circuit.osch`.

## Quick start

1. **Place symbols.** Find a symbol in the *Symbols* sidebar (type to search) and double-click it or drag it
   onto the sheet. While placing, `R` rotates and `M` mirrors; `Esc` finishes.
2. **Draw wires.** Type `W` and press Enter (or click the wire tool). Click a terminal, click bend points,
   and click another terminal or wire to finish. `Space` flips the bend.
3. **Edit properties.** Select a part: the *Properties* inspector shows identifier, label, part data,
   terminal designations, position, rotation, layer and custom properties. Several parts can be edited at once.
4. **Use the command line.** Just start typing: `L` Enter draws lines, `C` circles, `TR` trims, `M` moves,
   `INSERT K1` places a relay coil named K1, `SEARCH motor` searches the project, `BOM`, `CHECK`, `EXPORT PDF`.
   Points can be clicked or typed: `100,50` (absolute, mm, origin at the sheet's lower-left corner),
   `@20,0` (relative) or `@30<45` (polar). `HELP` lists every command; see [`docs/COMMANDS.md`](docs/COMMANDS.md).
5. **Add sheets** with the `+` tab. Use *Sheet connectors* (General ▸ Connections) with the same label on two
   sheets to continue a line; the cross-reference appears automatically.
6. **Before issuing:** *Tools ▸ Wire numbers*, *Tools ▸ Check drawing*, *Tools ▸ Issue revision*, then
   *File ▸ Export ▸ PDF*.

Shortcuts are listed and can be changed under *Help ▸ Keyboard shortcuts*. Letters typed on the drawing go
to the command line, so shortcuts use Ctrl, Alt or function keys (F3 object snap, F7 grid, F8 ortho,
F9 snap, F5 check).

## Files

| Extension | Contents |
|---|---|
| `.schematix` | Project: all sheets, metadata, layers, embedded custom symbols and revision history (ZIP + JSON, see [`docs/FILE_FORMAT.md`](docs/FILE_FORMAT.md)) |
| `.osch` | Legacy single-sheet drawing from development builds. Opened and converted to a project; the original is never changed |
| `.hpss` | HPS Schematix 1.x drawing (converted on open) |
| `.osym` / `.osymlib` | One custom symbol / a shared symbol library ([`docs/LIBRARY_FORMAT.md`](docs/LIBRARY_FORMAT.md)) |
| `.ostpl` | Circuit template |
| `.dxf` | AutoCAD-compatible drawing exchange (import and export, [`docs/DXF.md`](docs/DXF.md)) |

Your settings, symbol libraries, templates and recovery data live in `%APPDATA%\OpenSchematix` (Windows) or
`~/.config/openschematix` (Linux).

**Saving is safe:** projects are written to a temporary file, checked by reading them back, and then
renamed over the old file, so a crash or full disk cannot damage your last saved project. **Autosave**
writes recovery copies to a separate folder every few minutes (Preferences); it never overwrites your own
file. After an unexpected shutdown you are offered the recovery copies on the next start.

## Opening older drawings (.osch, HPS Schematix)

Open the `.osch` or `.hpss` file. It becomes a one-sheet project; title-block fields move to the project
properties. Nothing is lost, and the original file is not modified: when you save you choose a new
`.schematix` name. `File ▸ Export ▸ Current sheet as .osch` writes a single sheet in the legacy layout
(older builds will refuse files that use newer content such as drawing objects or layers).

## Limitations (please read)

- **Standards.** Symbols follow the published conventions of IEC 60617, IEEE 315/ANSI Y32.2, NEMA/JIC and
  ISO 1219-1 as generally documented. They have **not been certified against the official standard
  documents**. Some symbols are simplified and say so in the library; missing fluid-power symbols are listed
  in [`docs/SYMBOLS.md`](docs/SYMBOLS.md) and can be drawn with the symbol editor.
- **Check Drawing** finds common drafting mistakes with documented rules ([`docs/VALIDATION.md`](docs/VALIDATION.md)).
  **Passing the checks does not mean a drawing is safe, correct or compliant with any standard.** Nothing is
  simulated.
- **Rotation of symbols** is limited to 90° steps (drafting objects can rotate by any angle).
- **Panels** can be resized, collapsed and are remembered, but cannot be undocked into separate windows,
  and toolbars cannot be customised. One project is open at a time; its sheets are the document tabs.
- **DXF**: binary DXF and DWG are not supported; hatches, images and 3D entities are skipped on import;
  splines and ellipses are approximated. Export is DXF R12 in millimetres with symbols exploded into lines.
- **Text** in PDF exports uses the built-in Helvetica font with the Windows-1252 character set; characters
  outside it (for example Ω and most other Greek letters, or CJK text) print as `?`. SVG and the screen are not affected.
- **Large drawings.** The canvas redraws the visible sheet on every change; it is comfortable up to a few
  hundred parts per sheet.
- **Platforms.** Development and automated testing happen on Linux. The Windows build scripts, installer and
  Windows-specific code (high-DPI awareness, file association) still need verification on real Windows
  hardware. macOS is not a supported target.
- **Linux fonts.** If the program looks like it uses old bitmap fonts, your Tk was built without Xft;
  run it with your distribution's Python (`python3-tk`) instead of a self-contained Python build.

**Disclaimer:** OpenSchematix comes with no warranty (GPL sections 15–16). You are responsible for checking
that drawings meet the requirements of your project, employer and jurisdiction. Drawings are not a substitute
for professional engineering review.

## Building release packages

```
packaging\build_windows.bat      # Windows: dist\OpenSchematix\ and, with Inno Setup 6, installer_output\
packaging/build_linux.sh         # Linux: dist/OpenSchematix-<version>-linux-x86_64.tar.gz
```

Both scripts create a private virtual environment, install PyInstaller and pytest, run the tests and build
with `packaging/openschematix.spec`. Build each platform on that platform.

## Development

```
python -m pytest                      # unit and engine tests
xvfb-run -a python tests/gui_smoke.py # event-driven GUI test (needs a display on Linux)
python tools/make_demo_project.py     # rebuild examples/demo_project.schematix
python tools/gen_command_docs.py      # regenerate docs/COMMANDS.md
python tools/gen_symbol_docs.py       # regenerate docs/SYMBOLS.md
```

### Project structure

```
openschematix/
  model.py          sheets (Document): components, wires, drafting shapes, page setup
  project.py        projects: ordered sheets, metadata, layers, embedded custom symbols
  projectio.py      .schematix container, migration of .osch/.hpss, atomic saving
  editing.py        editing operations, router, crossings/junctions, scaling, align (pure functions)
  shapes.py         CAD geometry: transforms, object snap, intersections, TRIM, EXTEND
  connectivity.py   junction dots and unconnected ends on one sheet
  netlist.py        project-wide nets, wire numbering, connection/wire/terminal reports, CSV
  render.py         one scene builder for screen, PDF, SVG and DXF
  titleblock.py     frames, zones, title-block styles, revision tables
  export.py         SVG and multi-page vector PDF (no dependencies)
  dxf.py            DXF import/export (no dependencies)
  bom.py search.py check.py compare.py revisions.py recovery.py templates.py userlib.py commands.py
  symbols/          symbol framework, built-in libraries, custom symbols
  gui/              Tkinter interface: theme (design system), icons, widgets, canvas, command line,
                    panels, inspector, dialogs, reports, revisions, symbol editor
tests/              pytest suites and the GUI smoke test
tools/              documentation generators and example builders
packaging/          PyInstaller spec, Windows and Linux build scripts, installer
docs/               reference documentation
```

Contributions should keep the core dependency-free and include tests. Please keep the drawing conventions
honest: if a symbol's geometry cannot be confirmed, leave it out and list it in `docs/SYMBOLS.md`.
