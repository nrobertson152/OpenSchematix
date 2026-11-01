# OpenSchematix 1.1.0 — integration coordination

Snapshot: 2026-11-01. This is a plan, not a statement that PRs are approved. Check live GitHub before using it.

## Workstreams
- PR #37: reported merged into main; custom-symbol load-time attachment fix and Windows hover initialization.
- PR #47: draft reliability integration of #40, #42, #44; independent integration review pending. Do not merge component PRs separately if #47 is accepted.
- PR #45: hover workaround reported redundant with #37; evaluate for closure after integration approval.
- PR #46: draft project-scoped symbol ownership; independent review pending; high priority because of reported cross-project save corruption.
- PR #39: symbol import/edit fidelity; reported Windows CI failure and editor scope concerns; repair pending.
- PR #43: phantom-terminal fix; review against #46.
- PR #41: netlist performance; merge after correctness and equivalence validation.
- PR #33: scripting API; refresh against integrated main and rerun CI.

## Proposed dependency order
1. Independently review #47, then request director merge authorization.
2. Independently review #46, rebase/test against latest main after #47, then request director authorization.
3. Finish #39 and #43, verify project-scoped symbol interactions and CI.
4. Integrate #33 and #41 after correctness prerequisites, with independent verification.

Never merge based on this plan alone. A PR must pass current CI at the reviewed head SHA, have no unresolved blocking review findings, and be explicitly authorized by the director.

When PRs conflict, implementation owner documents conflict resolution and runs tests on the combined tree; reviewers inspect semantic correctness, not just textual mergeability.
