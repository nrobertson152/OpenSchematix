# Repository profile — OpenSchematix

Agents read this before changing code. Everything here was checked against the repository on 2026-11-02 (main at `1cbf0da`). If you find it wrong, open an issue labelled `rules-change`; don't work around it.

## Identity

- Repository: `nrobertson152/OpenSchematix` (public)
- Director: `nrobertson152`
- Default branch: `main`. Releases are tagged from `main` by the Director only (`.github/workflows/release.yml`).
- Current version: 1.1.0 (`openschematix/__init__.py`)
- Supported platforms: Windows and Linux; Python 3.10–3.13; Tkinter (Tk 8.6 and 9.0)
- Licence and product constraints:
  - GPL-3.0-or-later; never change the licence.
  - Fully offline: no network access, accounts, telemetry, ads or feature limits.
  - The only links are the two the user clicks.
  - Standard library only at runtime. `pyproject.toml` `[dev]` extras are test/build only.

## System map

- **Purpose.** A schematic editor for electrical, electronic, hydraulic and pneumatic drawings. Users draw on multiple sheets in one `.schematix` project, then check, number wires, produce reports and BOMs, and export SVG, PDF and DXF.
- **Engine and GUI separation.** The engineering core never imports Tkinter. Keep it that way.
- **GUI** (`openschematix/gui/`, about 9,800 lines):
  - `app.py` (`App`, about 2,600 lines) owns the open project, undo/redo (full JSON snapshots) and many editing operations.
  - `canvas_view.py` changes the model directly during drags.
- **Engineering core:**
  - `editing.py`: placement, moves, routing, wire attach/detach.
  - `connectivity.py`: spatially indexed connectivity analysis.
  - `netlist.py`: nets, wire numbering, reports.
  - `check.py`: drawing rules.
  - `bom.py`, `compare.py`, `commands.py`.
- **Data model:** `project.py` (`Project`), `model.py` (`Document`, `Component`, `Wire`, `Shape`, `Sheet`), `shapes.py`, `regions.py`, `boundary_fill.py`, `revisions.py` (content-addressed revision store inside the project file).
- **Files and I/O:**
  - `projectio.py`: atomic, read-back-verified `.schematix` ZIP writes.
  - `fileio.py`: legacy `.osch`.
  - `recovery.py`: per-session autosave.
  - `safejson.py`, `export.py`, `render.py`, `dxf.py`, `settings.py`, `userlib.py`.
- **Symbols:**
  - `openschematix/symbols/__init__.py` holds a process-global registry. `model.Component.geometry()` resolves pins through it, so results can depend on which project was activated last; see audit finding F1 below.
  - Built-in symbols: `symbols/electrical.py`, `fluid.py`, `general.py`.
  - Custom symbols: `symbols/custom.py` (`.osym`).
- **Formats:** `.schematix` (ZIP: manifest, project, sheets, revisions), legacy `.osch`, `.osym`, `.osymlib`. See `docs/FILE_FORMAT.md` and `docs/LIBRARY_FORMAT.md`. Files saved by v1.0.0 must keep opening; the tests check this against tag `v1.0.0`.

## Invariants that must never break

- **Saved connectivity survives everything.** Reopen on another computer, undo/redo, revision restore, symbol updates, moves and rotations must keep every wire-to-terminal attachment and every net.
- **Drawing, netlist and exports agree.** Geometry, connectivity and exported documents must agree. Never silently change what a project means.
- **Projects can't contaminate each other.** One project's custom symbols must never affect another project's saved file, analysis, BOM or exports.
- **Saves are atomic and verified.** Recovery never touches the user's file. Malformed files fail with a message, never an uncaught exception.
- **Old files keep opening.** Projects and symbol libraries from earlier releases keep opening. Any format change is versioned, documented and covered by tests.

## Commands (repository root)

- Install: `python -m pip install -e ".[dev]"`. Linux also needs `sudo apt-get install -y xvfb python3-tk`.
- Byte-compile: `python -m compileall -q openschematix tests`
- Integrity check: `python -m pytest -q tests/test_repo_integrity.py`
- Full tests: Linux `xvfb-run -a python -m pytest -q --tb=short -ra`; Windows `python -m pytest -q --tb=short -ra`. Tests marked `gui` need a display. `tests/conftest.py` detects one.
- GUI smoke: `xvfb-run -a python tests/gui_smoke.py <tmpdir>` (Linux); `python tests/gui_smoke.py <tmpdir>` (Windows).
- Packaged build: `packaging/build_linux.sh`, `packaging/build_windows.bat`; acceptance check `packaging/ci/packaged_smoke.py`.
- CI (`.github/workflows/tests.yml`) runs on every PR: pytest on Ubuntu and Windows with Python 3.10 and 3.13, plus GUI smoke on both OSes. These are the project's required checks.
- **Workflow agents** run on Ubuntu only, with the `ARF_BOOTSTRAP_CMD` install. They must report Windows behaviour as *not verified* unless CI on the exact SHA shows it.

## Change controls

- **Risk floors** are enforced by `.agents/risk-floors.json`: project I/O, the data model, revisions, recovery, symbols, connectivity, netlist and checks are `high`; packaging and release are `high`.
- **One issue at a time** may change `openschematix/gui/app.py`. It is the most contended file.
- **Compatibility fixtures** in `tests/data/` and `tests/fixtures/`, and the `v1.0.0` legacy-file tests, must keep passing.
- **The Director decides** releases, version numbers, licence, new runtime dependencies, file-format version changes and anything that adds network access.
- **Planning input:** `docs/FUTURE_RELEASE_BACKLOG.md` (stable IDs `OS-FUT-…`) lists requested work. It is not an assignment; work starts when the Director opens an issue.
- **Known defects** come from the Director's 2026-11 architecture and reliability audit (findings F1–F12). They become issues when the Director files them. F1, custom-symbol wire attachments dropped whenever a project is rebuilt before its symbols are registered, is critical.

## Release gates (from the 1.1.0 release checklist; see `docs/RELEASE_CHECKLIST.md`)

- Save, load, rollback, recovery, revisions and legacy-file compatibility verified.
- Full Windows/Linux CI green on the exact release commit.
- Packaged Windows and Linux builds pass open/edit/save/reopen acceptance.
- The Director authorises the release.

## Current work

Not here. It lives on issues, PRs and the "ARF: Director briefing" issue.
