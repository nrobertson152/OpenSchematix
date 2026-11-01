# OpenSchematix 1.1.0 — release readiness snapshot

Snapshot: 2026-11-01. Not an automatically updated dashboard.

**Overall: NOT RELEASE READY.** No merge/release authorization implied.

## Required release gates
- Project save/load, rollback, recovery, revisions and legacy-file compatibility verified.
- Cross-project custom symbols cannot contaminate saved files, analysis, BOM, or exports.
- Symbol import/edit fidelity and terminal connectivity regression tests pass.
- Netlist/ERC correctness and engineering invariant tests pass.
- Malformed .osymlib/.osym and DXF import resource/validation risks triaged and addressed according to severity.
- Full configured Windows/Linux CI passes for the final integrated commit; record exact SHA and jobs.
- Windows and Linux packaged applications receive functional open/edit/save/reopen acceptance testing.
- Changelog, version metadata, release artifacts and licensing reviewed.
- Independent reviews complete; project director explicitly authorizes release.

## Latest reported evidence (verify live)
- PR #47: reported 8/8 GitHub Actions jobs successful; final independent integration review pending.
- PR #46: reported successful GitHub Actions workflow; independent review pending.
- PR #39: previously failing CI; repair pending.
- BOM Current sheet F3: reviewed as fixed on main, additional regression test recommended.
- Security audit: project/revision parsing protections pending integration; symbol-library and DXF import hardening still under investigation.

Update this snapshot only after checking GitHub and documenting evidence in the corresponding PR/Issue.
