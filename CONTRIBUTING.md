# Contributing to OpenSchematix

OpenSchematix is a free and open-source, local-first schematic editor for electrical, electronic, hydraulic, and pneumatic drawings. Contributions are welcome, including bug reports, regression tests, documentation, symbol improvements, and focused feature changes.

## Project principles

- **Offline operation:** Core editing, saving, export, and documentation workflows must work without an internet connection, account, server, telemetry, or subscription.
- **Engineering correctness:** Drawing geometry, electrical connectivity, and exported documents must agree. Avoid silently changing project meaning.
- **Backward compatibility:** Preserve supported existing projects and symbol libraries. Document file-format changes, migration behavior, and any new version requirements.
- **Maintainability:** Prefer small, reviewable changes with clear behavior, tests, and minimal unrelated refactoring.
- **Platform support:** Consider both Windows and Linux, including differences between Tk versions.

## Before starting

Check existing issues and pull requests to avoid duplicating active work. For larger features or file-format changes, propose the intended behavior and compatibility approach before implementation. Work on a feature branch and open a pull request against `main`.

## Development setup

Python 3.10+ and Tkinter are required. From the repository root:

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m openschematix
```

On Debian/Ubuntu, Tkinter may require `sudo apt install python3-tk`. Tests marked `requires_tk` need the Tk bindings (they may still run headlessly). Tests marked `gui` need a working display or Xvfb. Linux CI runs `xvfb-run -a python -m pytest` and a separate `tests/gui_smoke.py` job. See `tests/conftest.py` for detection helpers.

The application has no required third-party runtime dependencies. Development and verification dependencies are different: optional packages such as `pypdf` and `ezdxf` support deeper export validation. When reporting test results, identify tests that were skipped because optional dependencies were absent.

## Changes and tests

1. State the user-visible behavior and acceptance criteria.
2. Add a regression test for each confirmed bug where practical. Tests should exercise production application code, not a parallel test-only implementation of the feature.
3. Test normal, boundary, and invalid inputs. For drawing changes, include save/reopen and undo/redo where relevant.
4. For project format changes, test old-file loading, new-file round trips, and unsupported-version handling. Consider historical revisions and embedded symbols.
5. For rendering and exports, verify representative files in an independent viewer when practical. A successful export call alone does not establish fidelity.
6. For GUI changes, record the operating system, Python version, Tk version, and whether testing used a real display or Xvfb.
7. Run the full available test suite and report exact passed, failed, and skipped counts. Do not report unexecuted tests as passed.

See `docs/MANUAL_ACCEPTANCE_TESTS.md` and `docs/RELEASE_CHECKLIST.md` **if present on the target branch**; these documents may still be under review.

## Pull requests

Keep each PR focused. Describe what changed, why, how it was verified, compatibility implications, and remaining limitations. Include screenshots or sample files when behavior is visual. Use the repository's PR template if available.

Automated coding assistants are welcome as development aids, but contributors remain responsible for inspecting generated code and reporting verification accurately. Do not merge or publish a release without maintainer approval.

## Licensing

Contributions to this repository are intended for distribution under the repository's **GNU GPL v3.0 or later** license. Only submit code and assets you have the right to contribute under that license. Identify any third-party material and its licensing before inclusion.

## Reporting defects

Open a GitHub issue with the application version, OS, reproduction steps, expected and actual results, and a minimal non-sensitive example project if possible. Do not publish passwords, private drawings, proprietary customer data, or security-sensitive details in public reports.
