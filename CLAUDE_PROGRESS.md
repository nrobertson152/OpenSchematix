# CLAUDE_PROGRESS — development checkpoint (Phase 4: performance)

_Checkpoint updated 2026-10-31 by Claude (Opus 5.5). Longer history: `DEVELOPMENT_PROGRESS.md`._

## 1. Where things stand

- Optimization 1 (connectivity spatial index) is merged as PR #20.
- Optimization 2 (crossing-detection index) is merged as PR #21 (`0e2823b`).
- Optimization 3 (hover highlighting without full redraws) is **implemented, tested and benchmarked** on
  branch `perf/hover-highlighting`, and a draft PR is open.
- **Nothing is in progress.** It is waiting for review. Do not merge, and do not start viewport culling or any
  other optimization until authorised.

## 2. Exact next step when resuming

1. `git fetch origin`, then check `main` and the PR for comments and reviews. Use the REST API
   (`gh api repos/nrobertson152/OpenSchematix/issues/<n>/comments`, `.../pulls/<n>/reviews`,
   `.../pulls/<n>/comments`); GraphQL and `gh pr view` are blocked in this environment.
2. Address feedback with a regression test per defect, then rerun section 5.
3. Without new instructions: report status and wait.

## 3. Git / PR state

| Item | Value |
|---|---|
| Base | `main` @ `0e2823b` (PR #21) |
| Branch | `perf/hover-highlighting`: implementation + tests + docs commit, then this checkpoint |
| Do not touch | `test/cache-invalidation-regressions`, any Jules branch or PR |

## 4. Architectural decisions

- **Connectivity** (`connectivity._WireIndex`, merged):
  - grid of 50-unit cells; segment boxes padded by tol + 1;
  - built per call; no caching.
- **Crossings** (`editing.crossings`, merged):
  - horizontals are registered along their row (y = a.y), others along their column (x = a.x);
  - per segment, candidates are tested in increasing index order;
  - non-finite, over-256-cell and over-budget segments fall back to all pairs.
- **Hover** (`gui/canvas_view.py`, this branch):
  - `draw_items(hover_index=HoverIndex())` records (document item, canvas id) for hoverable canvas items: not
    overridden, not selected, actually created. Recording is two list appends per canvas item. It also records
    the normal colour of items drawn already hovered.
  - `SchematicCanvas._set_hover(h)`:
    - if h is unchanged, it does nothing;
    - if a redraw is pending, it only stores h (the redraw draws it);
    - otherwise it restores the previously shown object and paints h with `recolor()`.
  - `recolor()` replaces whichever of fill/outline is non-empty, which is exactly how `draw_items` colours each
    kind, and returns the previous colour so it can be restored.
  - The index lives only until the next full redraw. `_hover_shown` is the object currently drawn
    highlighted.
  - No connectivity, scene or Tk item creation happens on hover changes. The hit test still runs on every
    motion (unchanged).

## 5. Test / benchmark commands and results (2026-10-31)

**Environment:**
- Standalone CPython 3.13.14 + Tk 9.0 (installed with uv), Xvfb, 2 vCPU.
- The system Pythons have no tkinter.
- PyPI is blocked, so ezdxf is unavailable.
- Run `git fetch --depth=1 origin tag v1.0.0` so the fill-compat tests run.

```
PYTHONPATH=.:/usr/local/lib/python3.13/site-packages xvfb-run -a <py3.13> -m pytest -q -rs
xvfb-run -a <py3.13> tests/gui_smoke.py OUT
xvfb-run -a -s "-screen 0 1920x1200x24" <py3.13> tools/bench_phase4.py --sizes small,medium,large --repeat 9 --gui --json OUT.json
```

**Tests:**
- pytest: **600 passed, 3 skipped** (ezdxf ×3), 0 failed.
- GUI smoke: **168/168**, 0 failures.
- `tests/test_hover_highlighting.py`: 28 tests. They skip without a display.
- Mutation check: all six seeded defects fail the suite.

**Benchmark changes:**
- `hover_change_redraw_s` now alternates between two wires. The old version re-entered the same object, which
  is a no-op with this change.
- New metrics: `hover_leave_s`, `hover_hit_test_s`, `redraw_peak_kib`, `hover_index_items`.

**Results**, main @ 0e2823b → branch (median of 9):

| | small | medium | large |
|---|---|---|---|
| hover change (switch) | 0.048 → 0.0022 s | 0.103 → 0.0028 s | 0.266 → 0.0057 s |
| hover leave (includes the hit test of an empty point) | 0.041 → 0.0019 s | 0.140 → 0.0080 s | 0.306 → 0.020 s |
| full redraw, 5 interleaved rounds (median) | — | 0.074 → 0.075 s | 0.222 → 0.229 s |
| redraw peak memory | 553 → 572 KiB | 1.8 → 1.9 MiB | 5.0 → 5.4 MiB |

## 6. Known issues / follow-ups (need owner decision)

- **Hit test on every motion:** it is now the main per-motion cost on large sheets (5–9 ms on an object,
  ~20 ms over empty space). Not addressed: out of scope.
- **Code that changes the document without requesting a redraw:** previously this was hidden by the next hover
  change, which redrew everything. It no longer is. All editing paths found go through `commit_change`/
  `refresh`/`redraw`, and drags call `redraw`.
- **`point_on_segment` overshoot** on very short diagonals: pre-existing; preserved.
- **`crossings()` and diagonals:** a diagonal is treated as vertical at its first x. Pre-existing; preserved.
- **Dead state:** `SchematicCanvas._scene_cache` is never read.
