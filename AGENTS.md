# OpenSchematix — three-role engineering workflow

This is the current operating instruction for AI-assisted development. The Director is the decision authority; **Coder**, **Reviewer**, and **Engineering Coordinator** are the only three agent roles. Assignments are per issue or pull request, not permanent ownership by a particular model. See [the coordination playbook](docs/agents/README.md).

## Roles and authority

- **Director (`nrobertson152`)** retains exclusive authority over releases, version/release tags and licensing. The Director delegates routine engineering priorities, decisions and verified PR merges to the Engineering Coordinator and may override those decisions.
- **Coder (Claude or ChatGPT, one assigned owner per task)** investigates, designs, implements, adds regression tests, runs available checks, documents material changes and opens a focused PR. The Coder fixes review findings but does not approve their own work. Do not start a second coding agent on the same task.
- **Reviewer (ChatGPT, independent of the Coder)** reviews the actual PR diff and latest head SHA, runs or evaluates proportionate tests, checks compatibility and engineering invariants, and reports blocking defects with reproducible evidence. Codex GitHub reviews may provide this review; a comment or green CI is not automatically approval. If ChatGPT is the Coder, a separate ChatGPT review session must be used.
- **Engineering Coordinator** manages assignments, routine engineering and integration decisions, exact-SHA CI/review evidence, and merges PRs when mandatory quality gates pass. The Coordinator must not implement or review its own code, bypass safeguards, create releases or tags, or change licensing.

GitHub issues, PRs, commits, review threads and CI are the authoritative record. Historical multi-agent names, assignments and checkout protocols are not current instructions.

## Work cycle

1. **Authorize:** The Director or delegated Coordinator authorizes a bounded in-scope issue or request. The Coordinator checks existing issues/PRs, records the scope, acceptance criteria, priority, dependencies and assigned Coder. Backlog entries alone are not authorization.
2. **Implement:** One Coder works on one dedicated branch and opens one focused PR per issue, with `Closes #<n>` where applicable. Do not edit another agent's branch or create overlapping implementations without Director approval.
3. **Verify:** The Coder posts the exact head SHA, commands actually run, OS/Python/Tk versions as applicable, pass/fail/skip counts, compatibility considerations and unverified cases. A failing or skipped test must not be described as passed.
4. **Review:** The independent ChatGPT Reviewer checks the latest commit and records actionable findings on the PR. A review of an earlier SHA does not approve later changes. The Coder resolves findings and adds regression tests; the Reviewer rechecks the changes.
5. **Coordinate:** The Coordinator confirms CI on the current head, independent review, unresolved threads, dependencies, draft state, conflicts and release scope. Merge only when all mandatory gates are satisfied; otherwise report and resolve specific blockers.
6. **Decide:** The Coordinator may merge independently verified PRs under the delegated merge gates. Only the Director authorizes releases, release tags and licensing changes. No Coder may self-merge; no agent may bypass required checks or branch protections.

Keep one active Coder assignment per issue and avoid unnecessary parallel changes to shared subsystems. Do not require GitHub assignment locks, extra agent roles, hourly check-ins or recurring model runs. Existing scheduled agents stay paused unless the Director explicitly authorizes resumption.

Report results and blockers on the relevant issue or PR, not only in chat. For long tasks, leave a durable branch/commit checkpoint with completed work, tests, next steps and blockers. Never weaken, skip or delete tests to make CI green.

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

Requested future work is in `docs/FUTURE_RELEASE_BACKLOG.md`. It is planning input only; work starts when the Director authorizes an issue.

## Commands

```sh
python -m pip install -e ".[dev]"            # Linux also: sudo apt-get install -y xvfb python3-tk
python -m compileall -q openschematix tests
xvfb-run -a python -m pytest -q -ra          # Windows: python -m pytest -q -ra
xvfb-run -a python tests/gui_smoke.py <tmpdir>
```

CI runs the full suite and GUI smoke tests on Ubuntu and Windows, Python 3.10 and 3.13, for PRs. Record the actual run and commit rather than assuming CI passed.

## Code Review Rules

The independent Reviewer should treat these as blocking:

- Any path that can lose wire-to-terminal attachments or change a net: reopen, undo/redo, revision restore, symbol update, move, rotate.
- One project's custom symbols affecting another project's saved file, analysis, BOM or exports.
- Saves that aren't atomic or verified, and malformed files that crash instead of showing a message.
- Breaking compatibility with existing project or symbol files.
- Behaviour changes without a regression test, or tests that would pass on the old buggy code.
- New network access, telemetry, runtime dependencies or Tkinter imports in the core.
- Windows/Linux differences that the change didn't consider.

## Delegated engineering authority (Director authorization: 2026-11-03)

The Director explicitly delegates routine engineering decisions to the Engineering Coordinator for this repository. The Coordinator may prioritize and authorize bounded work consistent with the product specification, resolve ordinary implementation, design and integration decisions, assign or reassign work without duplicate ownership, and merge reviewed pull requests into permitted development or main branches. No additional Director approval is required for routine merges.

**Mandatory merge gates:** exact current-head required CI successful; independent review covering the latest substantive changes; no unresolved blocking findings; applicable regression and compatibility evidence; correct branch dependencies and no unreviewed integration conflicts. Do not merge draft PRs or bypass GitHub protections. For data integrity, shared-file concurrency, connectivity or other high-risk changes, require evidence adequate to the risk, and fail closed if uncertain. Record the decision, supporting SHA, checks and review in the PR. A Codex comment without blocking findings is not by itself proof of all required verification.

**Director-exclusive authority:** creating, publishing, drafting or editing GitHub Releases; creating or pushing release/version tags; changing licenses or licensing terms. Neither the Coordinator nor Coders/Reviewers may perform these actions. The Director may override or revoke this delegation. The Coordinator may merge release-preparation code and documentation when standard quality gates pass, but must not create or publish a release or any release/version tag. The Coordinator must not alter branch protection or waive safety checks to obtain a merge.
