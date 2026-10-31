# CLAUDE_PROGRESS — development checkpoint (Phase 3: boundary fill)

_Checkpoint written 2026-10-31 ~17:25 EDT by Claude (Opus 5.5). Read this first, then verify the Git state
(section 3) before doing anything. Longer history: `DEVELOPMENT_PROGRESS.md` (sessions 6–7 sections)._

## 1. Where things stand (one paragraph)

Phase 3 (boundary fill: `FILL` / `HATCH` / `H`) is **implemented, stabilised and verified** on branch
`feature/boundary-fill`, draft PR #4. Both assignments given so far are finished: (a) the initial
implementation and (b) the stabilisation pass (revision-history schema compatibility, Tk 8.6 verification,
performance and robustness). **No implementation work is in progress or half-done.** Nothing has been merged;
`main` has not been touched. The work is waiting for the owner's review of PR #4.

## 2. Exact next step when resuming

1. Run the Git checks in section 3. If HEAD or the PR changed since this checkpoint, read the new commits and
   PR comments/reviews first (`gh api repos/nrobertson152/OpenSchematix/issues/4/comments`,
   `.../pulls/4/reviews`, `.../pulls/4/comments`; GraphQL / `gh pr view` is blocked in this environment).
2. If the owner left review feedback: address it on `feature/boundary-fill` (regression test per defect),
   rerun the test commands in section 6, update PR #4. Do not merge.
3. If there is no feedback and no new instruction: **do not start new work.** Report status and wait. Candidate
   follow-ups that need the owner's decision first are listed in section 8.

## 3. Git / PR state at checkpoint

| Item | Value |
|---|---|
| Repository | https://github.com/nrobertson152/OpenSchematix (local clone `/home/claude/openschematix`, shallow) |
| Working branch | `feature/boundary-fill` (tracks `origin/feature/boundary-fill`) |
| HEAD before this checkpoint commit | `b6dd1e4` QA: handle malformed fill vertex numeric values consistently (#11) — by the owner (merged QA PR #11 into this branch); it hardens `regions.clean_rings` and adds `tests/test_fill_input_validation.py` |
| This checkpoint | the commit that adds this file (see `git log -1`) |
| PR | #4 `feature/boundary-fill` → `main`, **draft**, open, mergeable_state `clean`, 1 comment (my stabilisation report), 0 reviews |
| `main` | `a0e52d0` (Fix potential data loss when replacing custom symbols, #18). The branch has **not** been rebased/merged with newer `main`; do not do so unless asked |
| Other work not to touch | Jules' QA branch / PR #6, `main` |

Commits on this branch for Phase 3 (oldest first; base was the owner's WIP draft `98185d2`):

```
205168f Replace boundary detection with a planar arrangement of lines and arcs
78f2674 Add the hatch shape: exact multi-ring fills that persist and transform
1c8d85f Render and export fills as vector regions
ae20895 FILL/HATCH command: repeated picks, gap tolerance, toolbar and inspector
8d7c215 Test boundary fill engine, fill objects, persistence, exports and GUI
8d80e41 Document boundary fill, the hatch format and DXF output
c7de0c2 Write sheet schema 3 when fills exist anywhere, including revision history
0abd645 GUI smoke test: pass under Tk 8.6 and check fill pixels on screen
5ccdbfd Boundary fill: index gap bridging and island nesting, lazy face rings
a5ad37d Document revision-aware schema, Tk 8.6 verification and fill performance
b6dd1e4 QA: handle malformed fill vertex numeric values consistently (#11)   [owner]
```

Commit trailers required for my commits: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01LF46GpLHbqkQLuRasKp6wT`. PR text ends with the
"🤖 Generated with Claude Code" line + session URL. Before pushing from the shallow clone:
`git fetch origin main` (thin pack).

## 4. Completed functionality

- **Command:** `FILL` (aliases `HATCH`, `H`), Draw menu entry, toolbar button (`fill` icon). Repeated picks
  until Enter; one undo step per command; picks ignore grid/object snap (`GetPoint(osnap=False,
  snap_grid=False)`); keyword `G` sets gap tolerance 0–10 mm (setting `fill_gap_mm`). Not offered in the
  symbol editor.
- **Boundary detection** (`openschematix/boundary_fill.py`): planar arrangement of segments + arcs ≤ 90°;
  crossings, tangencies, T-junctions, collinear/co-circular overlaps, 0.01-unit (0.0025 mm) snap merge,
  dedupe, dangling-edge pruning, face tracing by tangent+curvature; smallest enclosing face; bridges split so
  joined islands become holes; other components inside → holes (islands-in-islands not filled). Rejects open
  boundary / outside / on-boundary / degenerate picks with messages. Gap bridging via sort-and-sweep.
  Boundaries = drafting shapes on visible layers (not wires, symbols, text, fills) — `App.fill_boundary_shapes`.
- **Region maths** (`openschematix/regions.py`): bulge rings `(x, y, bulge)`, exact area, exact even-odd
  containment with arcs, bbox, distance, flattening, arc splitting, transforms, validation (`clean_rings`,
  hardened by owner's #11), slab trapezoids.
- **Fill object:** `Shape(kind="hatch", rings=…)`; move/rotate/scale/mirror/copy/paste/delete/group/lock/
  layers; drawn underneath other shapes; hit-tested after everything else (smallest fill wins; holes not
  selectable); inspector shows area / holes / extent.
- **Persistence:** sheet schema 3 (`SHEET_SCHEMA = FILE_SCHEMA = 3`) written **only** when a fill exists in the
  current sheets **or any revision snapshot** (`projectio.required_schema`, `RevisionStore.required_schema`);
  otherwise schema 2 (1.0.x compatible). `.osch` per sheet. Templates with fills = `.ostpl` version 2.
- **Rendering/exports:** canvas keyhole polygon (works under even-odd and non-zero); SVG even-odd `<path>`
  with exact `A` arcs; PDF Bézier arcs + `f*`; DXF R12 block `OSX_FILL_n` of SOLID trapezoids + INSERT on the
  fill's layer.
- **Docs:** `docs/BOUNDARY_FILL.md` (user doc), `docs/FILE_FORMAT.md`, `docs/DXF.md`, `docs/COMMANDS.md`
  (generated by `tools/gen_command_docs.py`), README, CHANGELOG, `DEVELOPMENT_PROGRESS.md`.
- **Tools:** `tools/bench_boundary_fill.py` (benchmarks), `tools/fuzz_boundary_fill.py` (robustness fuzz).

## 5. Defects found and fixed (all with regression tests)

| # | Defect | Fix commit | Test |
|---|---|---|---|
| 1 | Original WIP draft rejected intersections/holes, stored fills as plain polygons, its test failed | 205168f… | `tests/test_boundary_fill.py` |
| 2 | Inside/outside test wrong for arcs ending exactly at a vertical extreme (wrong side) | in 205168f series | `test_random_soup…`, `test_point_in_rings_matches_flattened_polygon` |
| 3 | Fill only in revision history → saved as schema 2; real v1.0.0 opened it and failed on revision restore | c7de0c2 | `tests/test_fill_compat.py` (incl. real v1.0.0 reader via `git archive v1.0.0`) |
| 4 | Gap tolerance O(open ends × edges): 33.2 s on a 3 300-object sheet → 0.21 s | 5ccdbfd | `test_gap_tolerance_on_a_large_sparse_drawing_is_fast`, `test_indexed_gap_bridging_matches_the_reference` |
| 5 | GUI smoke test indexed menubar cascades by position (fails under Tk 8.6, test-only) | 0abd645 | `tests/gui_smoke.py` |
| 6 | Malformed numeric fill vertices raised non-ValueError (owner's QA) | b6dd1e4 (owner) | `tests/test_fill_input_validation.py` |

## 6. Test commands and latest results (at `b6dd1e4`, re-run for this checkpoint)

| Environment | Command | Result |
|---|---|---|
| Python 3.13.14 + Tk 9.0.3 | `/home/claude/venv/bin/python -m pytest -q` | **479 passed**, 1 warning (pre-existing) |
| same | `xvfb-run -a -s "-screen 0 1600x1000x24" /home/claude/venv/bin/python tests/gui_smoke.py /tmp/out` | **169/169 ok**, exit 0 |
| Python 3.13.18 + Tk 8.6.13 (built from source) | `/home/claude/tk86/py86 -m pytest -q` | **478 passed, 1 skipped** (ezdxf subprocess probe in `test_engine.py`) |
| same | `xvfb-run -a -s "-screen 0 1600x1000x24" /home/claude/tk86/py86 tests/gui_smoke.py /tmp/out` | **169/169 ok**, exit 0 |
| Python 3.10.14 (minimum) | `PYTHONPATH=/home/claude/pure310 $(uv python find 3.10.14) -m pytest -q` | 445 passed, 3 skipped at `a5ad37d` (not re-run at `b6dd1e4`); GUI not runnable (pbs Tk 8.6 `tk.Menu` abort, also on `main`) |
| Benchmarks | `python tools/bench_boundary_fill.py` | grid 81×81 0.13 s; 400 crossing lines+arcs 0.61 s; 600 circles 0.59 s; sparse 3 300 objects 0.08 s; same with gap 0.21 s |
| Fuzz | `python tools/fuzz_boundary_fill.py` | 1 398 regions checked, 0 bad |

The 24-bit Xvfb screen matters: the on-screen pixel checks in `gui_smoke.py` are skipped on an 8-bit display
or without ImageMagick `import`. `main` reference: 354 pytest / 134 GUI checks.

### Recreating the test environments (the container is ephemeral; these paths may be gone)

PyPI and apt are blocked; GitHub is reachable.
- **Tk 9 env:** `uv python install 3.13` → `uv venv --python 3.13 /home/claude/venv`; add a `.pth` file in its
  site-packages listing `/usr/local/lib/python3.13/site-packages` (system pytest, pypdf, pypdfium2, numpy,
  PIL, matplotlib) and `/home/claude/ezdxf/src` (`git clone --depth 1 https://github.com/mozman/ezdxf`).
- **Tk 8.6 env:** prebuilt python-build-standalone Tk 8.6 builds abort on `tk.Menu` under Xvfb, so build from
  source: clone `tcltk/tcl` and `tcltk/tk` at tag `core-8-6-13`; `./configure --prefix=/home/claude/tk86/inst
  --enable-shared --enable-threads` (tk: add `--with-tcl=…/inst/lib --disable-xft --disable-xss`), make install;
  sparse-clone `python/cpython` tag `v3.13.18` (`Modules/`, `Lib/tkinter`); compile
  `gcc -shared -fPIC -O2 -I/usr/local/include/python3.13 -I/usr/local/include/python3.13/internal -I.
  -I…/inst/include -DPy_BUILD_CORE_MODULE _tkinter.c -o …/mod313/_tkinter.cpython-313-x86_64-linux-gnu.so
  -L…/inst/lib -ltk8.6 -ltcl8.6 -Wl,-rpath,…/inst/lib`; copy `Lib/tkinter` into `mod313`; wrapper script sets
  `PYTHONPATH=…/mod313:/home/claude/ezdxf/src`, `TCL_LIBRARY=…/inst/lib/tcl8.6`, `TK_LIBRARY=…/inst/lib/tk8.6`
  and execs `/usr/local/bin/python3`.
- **Python 3.10 env:** `uv python install 3.10.14`; pure-python deps symlinked into `/home/claude/pure310`
  (pytest, _pytest, pluggy, iniconfig, packaging, pypdf, pygments from 3.13 site-packages; `exceptiongroup`
  and `tomli` from their GitHub repos' `src/`, with a stub `exceptiongroup/_version.py`).

## 7. Known defects / limitations (none blocking)

- Not run on **Windows or macOS**. Windows hole rendering is checked only in the Tk source
  (`win/tkWinDraw.c`: default fill rule EvenOddRule → GDI ALTERNATE).
- Tk 8.6 verified only with a self-built 8.6.13 (no Xft); packaged distro/Windows Tk 8.6 not run.
- Solid fills only (no patterns/gradients); fills are not associative (changing the boundary does not
  update the fill); island rule fixed ("outer").
- DXF fills are SOLID blocks (R12 has no HATCH); anti-aliased viewers may show hairline seams; DXF HATCH import
  still skipped; our exported fill blocks re-import as many filled polygons.
- Boundary search is global per pick (~0.6 s for 400 densely crossing lines+arcs; fine for typical sheets).
- `test_many_islands_are_nested_quickly` is a timing guard only (old code also met its limit).
- Pre-existing, not Phase 3: unused imports `bbox_union` (export.py) and `GRID` (canvas_view.py); 1 pytest
  warning; `test_engine.py` ezdxf probe skips when ezdxf is only on `PYTHONPATH`.

## 8. Unresolved design decisions (need the owner)

1. **Wires/symbols as boundaries:** currently excluded on purpose (a fill under a circuit is not cut up by
   wiring). AutoCAD uses all visible objects. Keep or add an option?
2. **Native DXF HATCH:** requires moving DXF export from R12 to R2000+ (handles, OBJECTS section) — a larger
   change than Phase 3; deferred.
3. **Associative fills / island detection styles / patterns:** not implemented; product decision.
4. **Phase numbering:** the owner calls boundary fill "Phase 3"; the older plan in `DEVELOPMENT_PROGRESS.md`
   lists localisation (i18n) as Phase 3. To be reconciled by the owner.
5. **Rebasing on newer `main`** (`a0e52d0`): PR currently reports `clean`; rebase/merge only when asked.
6. **Windows verification:** needs a Windows machine or CI runner (the repo's release workflow builds Windows
   installers but runs no GUI tests).
