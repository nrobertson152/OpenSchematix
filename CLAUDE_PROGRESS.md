# CLAUDE_PROGRESS — development checkpoint (Phase 4: performance)

_Checkpoint updated 2026-10-31 by Claude (Opus 5.5). Longer history: `DEVELOPMENT_PROGRESS.md`._

## 1. Where things stand

- Optimization 1 (connectivity spatial index) is **merged** (PR #20, `81a8da2`).
- Optimization 2 (crossing-detection index) is **implemented, tested and benchmarked** on branch
  `perf/crossing-detection`, with a draft PR open. **Nothing is in progress.**
- Waiting for independent review. Do not merge, and do not start another optimization until authorised.

## 2. Exact next step when resuming

1. `git fetch origin`, then check `main` and the PR for new commits, comments and reviews. Use the REST API
   (`gh api repos/nrobertson152/OpenSchematix/issues/<n>/comments`, `.../pulls/<n>/reviews`,
   `.../pulls/<n>/comments`); GraphQL and `gh pr view` are blocked in this environment.
2. Address review feedback on `perf/crossing-detection` with a regression test per defect, then rerun section 5.
3. Without new instructions: report status and wait.

## 3. Git / PR state

| Item | Value |
|---|---|
| Base | `main` @ `81a8da2` (PR #20) |
| Branch | `perf/crossing-detection`: optimization + tests + docs commit, then this checkpoint |
| Do not touch | `test/cache-invalidation-regressions`, any Jules branch or PR |

## 4. Architectural decisions

- **Connectivity (`connectivity._WireIndex`, merged):**
  - Grid of 50-unit cells; segment bounding boxes padded by tol + 1.
  - Segments over 256 cells, non-finite wires and wires over the 32·S + 4096 registration budget go to an
    always-examined list.
  - Built per call; no caching.
- **Crossings (`editing.crossings`, this branch):**
  - The pair test `_crossing_pair` keeps the original body.
  - Horizontals are registered in the cells of their row (y = a.y); non-horizontals in the cells of their
    column (x = a.x, i.e. the first point, matching the original quirk that ignores a diagonal's x extent).
  - A row and a column share at most one cell, so each candidate pair is found exactly once.
  - Per segment i, candidates j > i are tested in increasing j, so output order and duplicates are unchanged.
  - Non-finite, over-256-cell and over-budget segments are paired with every opposite-kind segment
    (the original behaviour).
  - Built per call; no caching.
- **Oracles:** each test file holds a verbatim copy of the original algorithm (`reference_analyse`,
  `reference_crossings`).

## 5. Test / benchmark commands and results (2026-10-31)

Environment:
- Standalone CPython 3.13.14 + Tk 9.0 (installed with uv), Xvfb, 2 vCPU.
- The system Pythons have no tkinter.
- PyPI is blocked, so ezdxf is unavailable.
- Run `git fetch --depth=1 origin tag v1.0.0` so the fill-compat tests run.

```
PYTHONPATH=.:/usr/local/lib/python3.13/site-packages xvfb-run -a <py3.13> -m pytest -q -rs
xvfb-run -a <py3.13> tests/gui_smoke.py OUT
xvfb-run -a -s "-screen 0 1920x1200x24" <py3.13> tools/bench_phase4.py --sizes small,medium,large --repeat 7 --gui --json OUT.json
```

**Tests:**
- pytest: **572 passed, 3 skipped** (ezdxf ×3), 0 failed.
- GUI smoke: **168/168**, 0 failures.
- `tests/test_crossings_index.py`: 40 tests.
- Mutation check:
  - Caught: using the wrong column anchor (b.x), dropping the fallback list, reversing the candidate order.
  - Never finishes: removing the cap (killed by the timeout).
  - Survives, but equivalent: row from b.y, and a shifted cell origin.

**Benchmarks** (median of 7, main @ 81a8da2 → branch):

| | small | medium | large |
|---|---|---|---|
| crossings() | 0.0025 → 0.0006 s | 0.036 → 0.0028 s | 0.337 → 0.0093 s (36×) |
| full redraw (fit) | 0.027 → 0.029 s (noise) | 0.104 → 0.074 s | 0.556 → 0.217 s |
| crossings() peak memory | 17 → 96 KiB | 63 → 396 KiB | 188 KiB → 1.27 MiB |

## 6. Known issues / follow-ups (need owner decision)

- **`point_on_segment`:** a point up to tol/length beyond a very short diagonal counts as on it.
  Pre-existing; preserved.
- **`crossings()` and non-horizontal segments:** a diagonal is treated as vertical at its first point's x, so
  crossings with diagonal wires are reported at a point not on the diagonal, or missed. Pre-existing;
  preserved.
- **Remaining large-redraw costs:** connectivity ~0.04 s, scene ~0.06 s, Tk ~0.10 s. Further candidates
  (hover hit-test ~12 ms per motion, object snap, the per-press JSON undo snapshot) are not started.
- **Dead state:** `SchematicCanvas._scene_cache` is never read.
