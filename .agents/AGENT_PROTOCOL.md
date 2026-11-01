# OpenSchematix — Autonomous Multi-Agent Engineering Protocol

This document defines the standing work cycle for ChatGPT A, ChatGPT B, ChatGPT C, Claude A, and Claude B. It supplements [AGENTS.md](../AGENTS.md). The project director retains final authority over merges, releases, licensing, scope, and destructive operations.

## Scope and operating model

GitHub Issues hold task assignments, acceptance criteria, owners, and handoffs. Pull requests hold implementation and independent review; GitHub Actions provides CI evidence for exact commit SHAs. The files in `.agents/` are coordination snapshots, **not** a live task database.

Agents cannot work when their session is inactive, cannot automatically observe another agent's messages, and cannot guarantee continuous polling. This protocol applies **during active sessions with the required repository tools and permissions**. Do not claim background execution or automatic notification without a separately configured service.

## Start every active session

1. Read `AGENTS.md`, `.agents/README.md`, `.agents/TASKS.md`, `.agents/INTEGRATION.md`, and `.agents/RELEASE_STATUS.md`.
2. Read the assigned Issue, linked PR, and latest comments. Verify current main, branch head SHA, mergeability, and CI.
3. Confirm one implementation owner for the branch and overlapping code, and confirm that no director instruction supersedes the task.
4. Select the highest-priority **authorized** actionable task and begin substantive work. Avoid repeated metadata checks when a concrete code or environment blocker is already established.

## Continuous work cycle

**READ → IMPLEMENT / REVIEW → TEST → PUSH / COMMENT → REQUEST INDEPENDENT REVIEW → CHECK NEXT ASSIGNED TASK.**

After completing an assignment, publish a factual handoff on the Issue and PR, then check for the next task explicitly assigned to you. Start that task during the same active session if tools, time, and dependencies permit. If none is assigned, request an assignment on the relevant coordination Issue. Investigating unowned work is allowed; editing another owner's branch or claiming ownership is not.

A status update, coordination-file refresh, or plan is not a substitute for implementation when the assigned task can actually be executed.

## Default roles (explicit GitHub assignments override these)

- **ChatGPT A:** engineering coordination, release gates, independent review of PR #39, implementation owner of PR #60. Do not self-review #60.
- **ChatGPT B:** independent QA, security, regression reviews, including PR #60 and designated PR #43 review.
- **ChatGPT C:** assigned investigations, tests, documentation, and support; no implementation ownership of PR #39 after transfer.
- **Claude A:** implementation and integration owner of PR #39, subject to branch ownership acknowledgment.
- **Claude B:** implementation owner of PR #43 after acknowledgment and confirmation of exclusive ownership.

Verify current ownership in Issues #61, #56, #55, and PR discussions; the above assignments may become stale.

## Priority order during 1.1.0 stabilization

1. Data loss, corruption, unsafe writes, and recovery.
2. Incorrect engineering outputs, connectivity, netlist, and symbol ownership.
3. Security, crashes, uncontrolled resource consumption.
4. Release-blocking integration and CI.
5. Functional regressions and platform compatibility.
6. Performance, new features, cosmetics, and documentation only when specifically authorized.

Do not expand release scope or begin unrelated features without the director's decision.

## Branch ownership and review

One implementation owner per branch and overlapping work area. Before editing, verify ownership and dependencies. Do not force-push, delete branches, close another agent's PR, weaken tests, merge, or release without director authorization. Independent reviewers are read-only on the reviewed branch. Reviews apply to the exact reviewed SHA; any changed head requires appropriate re-review.

A review verdict must be **APPROVED**, **CHANGES REQUIRED**, or **DEFER**, with exact SHA, evidence, residual risks, and next action. A PR may be described as **READY FOR DIRECTOR MERGE APPROVAL** only after required integration, tests, CI, and independent review pass. Explicitly alert the director when that threshold is reached, even if the PR remains a draft.

## Verification and completion

Run focused regression tests, the full pytest suite where feasible, and GUI smoke tests for GUI changes. Verify GitHub Actions on the exact SHA across supported Windows/Linux configurations. Investigate failures; never suppress or skip tests solely to obtain green CI. If local tests cannot run, distinguish verified CI evidence from unexecuted tests. Check project save/reopen, custom-symbol isolation, engineering outputs, and import/export where relevant.

Post meaningful updates in the task Issue and PR using:

```text
AGENT:
TASK / ISSUE:
PR / BRANCH / EXACT HEAD SHA:
STATUS: IN PROGRESS | BLOCKED | READY FOR REVIEW | CHANGES REQUIRED | APPROVED | READY FOR DIRECTOR APPROVAL
WORK COMPLETED:
FILES CHANGED:
TESTS EXECUTED / RESULTS:
CI RUN / RESULTS:
RISKS / DEPENDENCIES:
NEXT OWNER / ACTION:
```

Do not post repetitive no-change updates. Keep secrets and sensitive logs out of public Issues.

## Blockers and session continuity

If a dependency, tool limit, missing checkout, network failure, or conflicting owner prevents progress, document the **specific** blocker and the next actionable operation. Do not fabricate commits, test results, or merge history. Request a coordinated ownership transfer if the environment cannot do the task. Preserve work and the exact branch/SHA before the session ends; the next active session resumes from the GitHub handoff.

## Current 1.1.0 gates (verify live state)

- **PR #39:** Claude A integrates latest main and adds cross-project regression coverage; ChatGPT A independently reviews the final SHA.
- **PR #43:** Claude B owns correction after acknowledgment; ChatGPT B independently reviews.
- **PR #60:** ChatGPT A implements DXF security fixes; ChatGPT B independently reviews.
- **PRs #46, #47, #48, #58:** merged as of 2026-11-01.
- **PRs #33 and #41:** candidates for deferral, not automatically authorized for merge or closure.

The project director alone decides final PR merges, release publication, major scope changes, and deferrals.

## Startup instruction for each agent

> Read `AGENTS.md` and `.agents/AGENT_PROTOCOL.md`, check your current GitHub assignments and latest PR comments, then continue your highest-priority authorized engineering task. After a verified handoff, pick up the next assigned task during this active session. Never merge or release without the project director.
