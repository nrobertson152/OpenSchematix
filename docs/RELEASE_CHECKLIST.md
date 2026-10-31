# Release readiness checklist

This is a release gate, not a claim that a test or build has passed. Record evidence (commit SHA, CI run, test log, or artifact) for each checked item. Do not merge feature work or publish a release solely because its author reports passing tests.

## 1. Integration and scope

- [ ] Confirm release scope and intended version; update version metadata, README, changelog, and packaging names consistently.
- [ ] Review and merge baseline QA changes independently of feature development (PR #6, if accepted).
- [ ] Rebase or merge the latest `main` into the boundary-fill branch, resolve conflicts, and rerun all tests.
- [ ] Complete independent review of boundary fill (PR #4); close release-blocking findings before merge.
- [ ] Resolve the Phase 3 naming conflict in `DEVELOPMENT_PROGRESS.md` (localisation versus boundary fill).
- [ ] Confirm no unrelated files or unreviewed changes are included in the release diff.
- [ ] Record the exact release commit and tag.

## 2. Automated and manual verification

- [ ] Run the complete `pytest` suite on the final integrated commit; record passed, failed, and skipped counts.
- [ ] Install optional test dependencies (including `pypdf` and `ezdxf`) in a validation environment; confirm export tests **run** rather than skip.
- [ ] Run `tests/gui_smoke.py` with a display or Xvfb; record the exact checks passed and Tk version.
- [ ] Verify GUI behavior on Tk 8.6 as well as any newer Tk version used in development.
- [ ] Open an existing pre-feature project, edit, save, and reopen it without data loss.
- [ ] Test malformed/truncated projects and verify errors are intelligible and do not overwrite original files.
- [ ] Verify undo/redo, wire connectivity, custom symbols, multi-sheet projects, and revision history with production code paths.
- [ ] Validate actual SVG, PDF, and DXF files with independent readers/renderers, not only successful export return values.

## 3. Boundary-fill release gates (if included)

- [ ] Verify open and closed boundaries, line/arc intersections, tangencies, overlaps, gap tolerance, nested holes, and degenerate inputs.
- [ ] Verify fill and hole rendering on Tk 8.6, including zoom, pan, selection, and redraw.
- [ ] Verify fill object transforms, copy/paste, grouping, locking, deletion, undo/redo, save/reopen, and all supported exports.
- [ ] Verify schema selection considers **revision history**, not only currently visible fill objects; document older-version compatibility.
- [ ] Document limitations: solid fills only; non-associative boundaries; DXF R12 SOLID output; DXF HATCH import unsupported; performance on dense geometry.
- [ ] Confirm whether wires and symbols are intentionally excluded as fill boundaries.

## 4. Windows and Linux packages

- [ ] Build Windows executable and installer from the release commit.
- [ ] Test Windows startup, icon/splash, installer/uninstaller, file associations, DPI scaling, and mouse/keyboard behavior on a real Windows environment.
- [ ] Build Linux archive from the release commit; test launch on supported distributions and desktop environments.
- [ ] Test a fresh install and an upgrade from the prior public release on each platform.
- [ ] Confirm bundled files, licenses, example projects, icons, and documentation are present.
- [ ] Test packages without a development Python environment; confirm the application works offline with no account or telemetry requirement.
- [ ] Record package hashes and verify downloaded artifacts launch.

## 5. Publication

- [ ] Update release notes with features, fixes, known limitations, and any file-format compatibility changes.
- [ ] Check README download links, filenames, version strings, and installation instructions against the actual artifacts.
- [ ] Publish a version tag and GitHub release only after review and platform verification.
- [ ] Download the published artifacts and smoke-test them again.
- [ ] Retain a rollback path: prior release artifacts and a known-good tag.

## Release sign-off

| Item | Evidence / link | Approved by |
| --- | --- | --- |
| Integrated commit and diff review | | |
| Unit and GUI test results | | |
| Independent QA | | |
| Windows validation | | |
| Linux validation | | |
| File-format and export compatibility | | |
| Release artifacts and hashes | | |

Release decision: **Pending** until required gates are complete.
