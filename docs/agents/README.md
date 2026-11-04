# OpenSchematix — engineering coordination playbook

**Canonical roles and engineering rules:** [AGENTS.md](../../AGENTS.md). This document describes the Coordinator's operating procedure; it does not create another coding or review role.

## Assignment and handoff

1. Inspect the live issue/PR queue and the current `main` branch. Never rely on a fixed list of PR numbers or a previous chat's status.
2. Confirm existing authorization or use delegated authority to approve bounded in-scope work, with acceptance criteria, one named Coder, target branch, priority and dependencies. Resolve ownership ambiguity without starting duplicate implementations.
3. Keep the issue or PR as the handoff record. The Coder supplies a branch, latest commit SHA, test evidence and known limitations. The independent ChatGPT Reviewer supplies findings against that exact SHA.
4. On fixes, require a new review of the changed code. Review comments that are merely `COMMENTED` or unresolved are not proof of approval. Track any explicitly accepted risk.
5. After confirming current-head CI, independent review and safety gates, the Coordinator may make and execute the merge decision. Record its evidence in the PR, and summarize merged work and remaining blockers to the Director. Never bypass required checks, create releases/tags or change licensing.

## Coordinator status report

For every open PR, give: link, title, draft state, head SHA, mergeability, latest CI conclusion, latest independent review, unresolved blocking findings, dependencies and **READY / BLOCKED / IN REVIEW / DRAFT** disposition. Distinguish observed GitHub evidence from author claims and from manual tests not performed. Identify the next concrete action and its owner. Do not claim Windows, Linux, packaged-app or file-format acceptance without matching evidence on the relevant commit.

Report the current Coder assignment, Reviewer queue and Coordinator decisions. Do not report legacy five-agent roles as active positions. Preserve historical PRs and comments for traceability; their old role labels are not instructions to reactivate those agents.

## Automation and resource discipline

The Director authorized staggered hourly coordination and coding schedules on 2026-11-03. Scheduling or changing additional runs still requires explicit authorization; a status request alone is not authorization. Prefer one focused implementation PR at a time per shared subsystem, asynchronous independent review, and existing GitHub Actions for deterministic checks. Avoid extra coordination bots, artificial check-in intervals and GitHub ref-based assignment locks.

## Delegated merge checklist

Before merging, verify current-head required CI, a current independent review, no unresolved blocking findings, correct base/dependencies, regression and platform evidence proportionate to risk, and no draft/release-only scope. For filesystem integrity/concurrent authority changes, require actual appropriate failure-mode evidence; do not use hosted CI alone to claim production multi-user safety. Document SHA, evidence and merge rationale. The Director exclusively controls releases, release tags and licensing.
