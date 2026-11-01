# OpenSchematix 1.1.0 — assignment snapshot

Snapshot: 2026-11-01. **Director decision: five active agents only.** GitHub Issues, PRs and current CI remain authoritative for live task status.

| Agent | Responsibility | Tracking |
| --- | --- | --- |
| ChatGPT A | Release coordination; independent review of PR #47; review of PR #39; DXF security review after release-critical integration | Issues #50, #56, #55 |
| ChatGPT B | Engineering invariants and independent regression tests | PR #48; Issues #52, #53 |
| ChatGPT C | Symbol-library import security and malformed-file validation | Issue #54 |
| Claude A | Symbol import/edit fidelity, corrections requested by independent review | PR #39; Issue #56 |
| Claude B | Project-file reliability and project-scoped symbol implementation/integration | PRs #47, #46; Issues #50, #51 |

**Copilot A and Copilot B are no longer active agents or eligible for new assignments.** Their prior reviews and comments remain historical evidence, not authorization to merge. Jules is not an active agent.

Rules: confirm implementation ownership through the relevant Issue before modifying code; one owner per branch; independent reviewers remain read-only. ChatGPT A reviews PR #47 independently of Claude B's implementation, and PR #39 independently of Claude A's implementation. After PR #47 review, ChatGPT A owns the separate DXF security review task in Issue #55, subject to priority and non-overlap. Never merge or release without the director's explicit authorization.
