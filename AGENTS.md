# OpenSchematix AI Agent Coordination Protocol

This document governs AI-assisted development. Human project director retains final authority.

## Start-of-task procedure
1. Read this file and `.agents/README.md`, `.agents/TASKS.md`, `.agents/INTEGRATION.md`, and `.agents/RELEASE_STATUS.md` from the latest default branch.
2. Read your assigned GitHub Issue, linked PRs, and their most recent comments. Check actual head SHAs and CI before acting.
3. Confirm the issue has a named owner, scope, acceptance criteria, and no competing implementation owner. If ambiguous, comment and wait.
4. Use an isolated branch for changes. Never modify another agent's branch without explicit authorization.
5. Treat documents as coordination snapshots; GitHub PR state, CI, and issue discussion are authoritative for live facts.

## Communication
- Assignment, decisions, questions, blockers, and handoffs: comment on the task's GitHub Issue.
- Code-specific findings and review verdicts: comment/review on the PR, and link the issue.
- Include: agent name, UTC timestamp, issue/PR number, branch and exact SHA, changed paths, tests run and results, outstanding blockers, next requested action.
- Read new comments at the start of each work session and before pushing or declaring completion.
- No silent assumptions that other agents received messages. No automatic notifications unless a separate integration is configured.

## Ownership and authority
- One implementation owner per branch and per overlapping set of files.
- Independent reviewers must not change the reviewed branch.
- Cross-cutting changes require an Issue comment requesting coordination before editing.
- Never merge PRs, publish releases, close another agent's work, delete branches, change licenses, or weaken tests without project-director authorization.
- Never expose tokens, secrets, private project contents, or sensitive logs in public issues.
- A green CI run is evidence for its exact SHA, not blanket approval.
- When a task is blocked, post a blocker comment and stop rather than overwrite someone else's work.

## Handoff format
```text
AGENT:
TASK / ISSUE:
PR / BRANCH / HEAD SHA:
SUMMARY:
FILES CHANGED:
VALIDATION (commands, environment, counts, skips):
CI (run URL, exact SHA, individual failing jobs):
KNOWN RISKS / CONFLICTS:
NEXT OWNER / REQUESTED DECISION:
```

## Release rules
Release decisions are: AWAITING VERIFICATION, CHANGES REQUIRED, READY FOR REVIEW, READY TO MERGE, DEFERRED.
Only the project director can authorize a merge or release.
OpenSchematix application remains GPLv3, free/open-source, offline-first, without telemetry or account requirements.

## Active-session task continuity
Read [the standing autonomous engineering protocol](.agents/AGENT_PROTOCOL.md) at session start. After a verified task handoff, check GitHub for your next explicitly assigned task and continue during the active session. This is not background execution; no agent can act when disconnected. The project director retains merge and release authority.
