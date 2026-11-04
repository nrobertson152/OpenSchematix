# OpenSchematix — development workflow

## Roles (Director decision, 2026-11-04)

- **Director (`nrobertson152`)** has sole authority over releases, release/version tags and licensing. The Director may override any decision.
- **Developer (Claude)** is the only developer. It plans, implements, tests, reviews and merges its own work. No independent reviewer, coordinator or second coding agent is required, and merges need no Director approval.

GitHub issues, PRs, commits and CI are the record. Older role names (Coder, Reviewer, Coordinator, numbered agents) in historical issues and PRs are not current instructions.

## Work cycle

1. Work on a dedicated branch and open a focused PR, with `Closes #<n>` where applicable.
2. Add regression tests that fail on the old code. Run the commands below locally.
3. Post the exact head SHA, commands run, versions and pass/fail/skip counts on the PR. Never describe a failing or skipped test as passed.
4. Merge when the required CI passes on the exact head and the self-review checklist below is clear. Record the merge rationale on the PR. State anything unverified, such as native Windows behaviour, rather than claiming it.
5. Release-preparation PRs may be merged, but creating, drafting or publishing GitHub Releases and pushing release/version tags is for the Director only.

Never weaken, skip or delete tests to make CI green, and never bypass CI.

## Product rules

- GPL-3.0-or-later, free and open source.
- Fully offline: no network access, accounts, telemetry, ads or feature limits.
- Standard library only at runtime. `[dev]` extras are for tests and builds only.
- The engineering core never imports Tkinter.
- Windows and Linux; Python 3.10–3.13; Tk 8.6 and 9.0.
- Existing `.schematix`, legacy `.osch`, `.osym` and `.osymlib` files must keep opening. Document any format change, version it, and test it.

## Priorities

1. Data loss, corruption, unsafe writes and recovery.
2. Wrong engineering output: connectivity, netlist, symbols.
3. Security, crashes and runaway resource use.
4. Regressions and platform compatibility.
5. Performance, features, cosmetics.

Requested future work is in `docs/FUTURE_RELEASE_BACKLOG.md`. It is planning input: the Developer picks work from it and from open issues, and the Director decides what goes into each release.

## Commands

```sh
python -m pip install -e ".[dev]"            # Linux also: sudo apt-get install -y xvfb python3-tk
python -m compileall -q openschematix tests
xvfb-run -a python -m pytest -q -ra          # Windows: python -m pytest -q -ra
xvfb-run -a python tests/gui_smoke.py <tmpdir>
```

CI runs the full suite and GUI smoke tests on Ubuntu and Windows, Python 3.10 and 3.13, for PRs. Record the actual run and commit rather than assuming CI passed.

## Self-review checklist

Treat any of these as a blocking defect in your own change:

- Any path that can lose wire-to-terminal attachments or change a net: reopen, undo/redo, revision restore, symbol update, move, rotate.
- One project's custom symbols affecting another project's saved file, analysis, BOM or exports.
- Saves that aren't atomic or verified, and malformed files that crash instead of showing a message.
- Breaking compatibility with existing project or symbol files.
- Behaviour changes without a regression test, or tests that would pass on the old buggy code.
- New network access, telemetry, runtime dependencies or Tkinter imports in the core.
- Windows/Linux differences that the change didn't consider.
