# Agent coordination

This directory holds concise, reviewable coordination snapshots. The root [AGENTS.md](../AGENTS.md) is the operating protocol.

**Authoritative live sources:** GitHub Issues (assignments and handoffs), pull requests (code and reviews), GitHub Actions (CI), and the project director (approval). These files are not an automatically synchronized task database.

Workflow: director creates an Issue → assigns a single implementation owner → agent acknowledges via Issue comment → agent works in isolated branch → draft PR references Issue → independent reviewer posts verdict → director authorizes merge → agent updates issue status.

Agent sessions and providers do not automatically communicate. Each must have repository access, permission to comment, and instructions to poll GitHub. Agents without write permission must supply a handoff for a connected agent to post.

Files:
- [TASKS.md](TASKS.md): work allocation snapshot.
- [INTEGRATION.md](INTEGRATION.md): dependency and integration policy.
- [RELEASE_STATUS.md](RELEASE_STATUS.md): release gates and known risks.

Avoid committing frequent status churn to these files; use Issues and PR comments for day-to-day updates. Refresh snapshots deliberately after material milestones.

- [AGENT_PROTOCOL.md](AGENT_PROTOCOL.md): standing active-session task cycle, ownership, independent review, and startup instruction.
