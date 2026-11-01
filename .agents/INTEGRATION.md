# OpenSchematix 1.1.0 — integration coordination

Snapshot: 2026-11-01. This is a plan, not a statement that PRs are approved. Check live GitHub before using it.

## Workstreams
- PR #37: reported merged into main; custom-symbol load-time attachment fix and Windows hover initialization.
- PR #47: draft reliability integration of #40, #42, #44; independent integration review assigned to ChatGPT A (Issue #50); no merge authorized. Do not merge component PRs separately if #47 is accepted.
- PR #45: hover workaround reported redundant with #37; evaluate for closure after integration approval.
- PR #46: draft project-scoped symbol ownership; Copilot B's completed review is retained as historical evidence; ChatGPT A coordinates final post-integration verification; high priority because of reported cross-project save corruption.
- PR #39: symbol import/edit fidelity; CI passed at 1b9f686; ChatGPT A review requested library-versus-embedded symbol edit clarification and regression on PR #39.
- PR #43: phantom-terminal fix; review against #46.
- PR #41: netlist performance; merge after correctness and equivalence validation.
- PR #33: scripting API; refresh against integrated main and rerun CI.

## Active agents
Only Claude A, Claude B, ChatGPT A, ChatGPT B and ChatGPT C are active. Copilot A/B receive no further tasks. ChatGPT A owns the independent PR #47 review (Issue #50), PR #39 review (Issue #56), and DXF security review (Issue #55) after release-critical work.

## Proposed dependency order
1. Independently review #47, then request director merge authorization.
2. Independently review #46, rebase/test against latest main after #47, then request director authorization.
3. Finish #39 and #43, verify project-scoped symbol interactions and CI.
4. Integrate #33 and #41 after correctness prerequisites, with independent verification.

Never merge based on this plan alone. A PR must pass current CI at the reviewed head SHA, have no unresolved blocking review findings, and be explicitly authorized by the director.

When PRs conflict, implementation owner documents conflict resolution and runs tests on the combined tree; reviewers inspect semantic correctness, not just textual mergeability.
