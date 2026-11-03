# OpenSchematix — working with AI agents

## Roles

- **Director (`nrobertson152`)** decides what to build, merges pull requests and approves releases. Only the Director merges, releases, tags, deletes branches or changes the licence.
- **Claude** is the primary developer and architect. It implements issues and opens pull requests.
- **ChatGPT / Codex** does independent review and testing. Codex reviews every pull request automatically. Comment `@codex <request>` on a PR to ask it for a fix.
- **GitHub** holds the record: issues, pull requests and CI (`.github/workflows/tests.yml`).

## How work flows

1. The Director opens an issue.
2. One branch and one focused PR per issue. The PR description says `Closes #<n>`.
3. CI and Codex review run on the PR. Address the findings, or explain on the PR why a finding is wrong.
4. The Director merges.

Report results, blockers and questions on the issue or PR, not only in chat. For every test claim, give the exact command, the OS and Python version, the commit, and the pass/fail/skip counts. "Not run" is not "passed". Never weaken, skip or delete a test to get green. Don't push to someone else's open PR branch unless asked.

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

Requested future work is in `docs/FUTURE_RELEASE_BACKLOG.md`. It's only planning input; work starts when the Director opens an issue.

## Commands

```sh
python -m pip install -e ".[dev]"            # Linux also: sudo apt-get install -y xvfb python3-tk
python -m compileall -q openschematix tests
xvfb-run -a python -m pytest -q -ra          # Windows: python -m pytest -q -ra
xvfb-run -a python tests/gui_smoke.py <tmpdir>
```

CI runs the full suite and GUI smoke tests on Ubuntu and Windows, Python 3.10 and 3.13, for every PR.

## Code Review Rules

Reviewers (Codex reads this section) should treat these as blocking:

- Any path that can lose wire-to-terminal attachments or change a net: reopen, undo/redo, revision restore, symbol update, move, rotate.
- One project's custom symbols affecting another project's saved file, analysis, BOM or exports.
- Saves that aren't atomic or verified, and malformed files that crash instead of showing a message.
- Breaking compatibility with existing project or symbol files.
- Behaviour changes without a regression test, or tests that would pass on the old buggy code.
- New network access, telemetry, runtime dependencies or Tkinter imports in the core.
- Windows/Linux differences that the change didn't consider.
