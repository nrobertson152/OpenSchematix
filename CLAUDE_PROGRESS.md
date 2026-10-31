# CLAUDE_PROGRESS — development checkpoint (Phase 4: performance)

_Checkpoint written 2026-10-31 by Claude (Opus 5.5). Replaces the Phase 3 checkpoint (Phase 3 was merged as
PR #4). Longer history: `DEVELOPMENT_PROGRESS.md`._

## 1. Where things stand

Phase 4 optimization 1 (connectivity spatial index) is **implemented, tested and benchmarked** on branch
`perf/connectivity-index`, draft PR open (see section 3). **Nothing is in progress.** Waiting for the owner's
(and ChatGPT's) review. Do not merge. Do not start the crossings optimization until authorised.

## 2. Exact next step when resuming

1. `git fetch origin`; check `main` and the PR for new commits, comments and reviews
   (`gh api repos/nrobertson152/OpenSchematix/issues/<n>/comments`, `.../pulls/<n>/reviews`,
   `.../pulls/<n>/comments`; GraphQL / `gh pr view` is blocked in this environment).
2. Address review feedback on `perf/connectivity-index` (a regression test per defect), rerun section 5.
3. Without new instructions: report status and wait.

## 3. Git / PR state

| Item | Value |
|---|---|
| Base | `main` @ `dc163ea` (PR #19 on top of PR #4) |
| Branch | `perf/connectivity-index` (benchmark tool commit, then the optimization commit, then this checkpoint) |
| Do not touch | `test/cache-invalidation-regressions` (separate cache-invalidation effort; identical to main at checkpoint), any Jules branch/PR |

## 4. Architectural decisions

- `connectivity._WireIndex`: uniform grid, `_CELL` = 50 units, wires registered by segment bbox padded by
  `_PAD` = tol + 1 (covers `point_on_segment`'s along-segment overshoot of up to tol/length < 1/√2 on short
  diagonals). Index only filters; exact per-wire tests and output order unchanged. Built per call — **no
  caching, no invalidation**.
- Memory bound: segment > `_MAX_CELLS_PER_SEGMENT` (256) cells, non-finite coordinates, < 2 points, or total
  registrations > 32·S + 4096 → wire goes to the always-examined list (falls back to the old full test).
- Oracle: `tests/test_connectivity_index.py::reference_analyse` is a verbatim copy of the old algorithm.

## 5. Test / benchmark commands and results (2026-10-31)

Environment: standalone CPython 3.13.14 + Tk 9.0 (uv), Xvfb, 2 vCPU; system Pythons have no tkinter; PyPI
blocked (ezdxf unavailable).

```
PYTHONPATH=.:/usr/local/lib/python3.13/site-packages xvfb-run -a <py3.13> -m pytest -q -rs
xvfb-run -a <py3.13> tests/gui_smoke.py OUT
xvfb-run -a -s "-screen 0 1920x1200x24" <py3.13> tools/bench_phase4.py --sizes small,medium,large --repeat 5 --gui --json OUT.json
```

- pytest: **527 passed, 3 skipped** (ezdxf ×3), with `git fetch --depth=1 origin tag v1.0.0` so the two
  compat tests run. New file: 31 tests. GUI smoke: **168/168 ok, 0 failures**.
- Mutation check: the new tests fail for `_PAD = tol`, `_PAD = 0` and for dropping the always-list.

| median of 5 | small (96 c / 144 w) | medium (384 / 576) | large (1152 / 1728) |
|---|---|---|---|
| analyse() main → branch | 0.060 → 0.0032 s | 0.99 → 0.014 s | 8.84 → 0.046 s |
| full redraw (fit) | 0.14 → 0.033 s | 1.06 → 0.11 s | 10.06 → 0.57 s |
| hover-change redraw | 0.10 → 0.033 s | 1.09 → 0.14 s | 9.77 → 0.59 s |
| analyse peak memory | 189 → 238 KiB | 749 → 944 KiB | 2.3 → 2.9 MiB |

## 6. Known issues / follow-ups (need owner decision)

- `geometry.point_on_segment` compares the projection `dot` against `tol` in squared-length units, so a point
  up to tol/length beyond a very short diagonal segment counts as on it (e.g. 0.49 units off a 0.017-unit
  stub). Pre-existing; preserved deliberately; not fixed.
- Next candidate: `editing.crossings()` — O(S²), ~0.35 s of the remaining 0.57 s large redraw.
- Later: hover hit-test (12 ms/motion on large), object snap, per-press JSON undo snapshot (13 ms on large).
- `SchematicCanvas._scene_cache` is dead state (never read).
