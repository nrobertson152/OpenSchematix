# OpenSchematix — engineering coordination playbook

**Canonical roles and engineering rules:** [AGENTS.md](../../AGENTS.md). This document describes the Coordinator's operating procedure; it does not create another coding or review role.

## Assignment and handoff

1. Inspect the live issue/PR queue and the current `main` branch. Never rely on a fixed list of PR numbers or a previous chat's status.
2. Confirm Director authorization, acceptance criteria, one named Coder (Claude **or** ChatGPT), target branch, priority and dependencies. If ownership is ambiguous, ask the Director rather than starting parallel implementations.
3. Keep the issue or PR as the handoff record. The Coder supplies a branch, latest commit SHA, test evidence and known limitations. The independent ChatGPT Reviewer supplies findings against that exact SHA.
4. On fixes, require a new review of the changed code. Review comments that are merely `COMMENTED` or unresolved are not proof of approval. Track any explicitly accepted risk.
5. Summarize readiness to the Director. The Coordinator cannot merge, change required checks, tag, release, delete branches or reassign active work without authorization.

## Coordinator status report

For every open PR, give: link, title, draft state, head SHA, mergeability, latest CI conclusion, latest independent review, unresolved blocking findings, dependencies and **READY / BLOCKED / IN REVIEW / DRAFT** disposition. Distinguish observed GitHub evidence from author claims and from manual tests not performed. Identify the next concrete action and its owner. Do not claim Windows, Linux, packaged-app or file-format acceptance without matching evidence on the relevant commit.

Report the current Coder assignment, Reviewer queue and Coordinator decisions. Do not report legacy five-agent roles as active positions. Preserve historical PRs and comments for traceability; their old role labels are not instructions to reactivate those agents.

## Automation and resource discipline

No standing scheduled engineering runs are authorized by this document. The Director must explicitly request any new schedule or resumption; a request for a status update is not permission to resume agents. Prefer one focused implementation PR at a time per shared subsystem, asynchronous independent review, and existing GitHub Actions for deterministic checks. Avoid extra coordination bots, artificial check-in intervals and GitHub ref-based assignment locks.
