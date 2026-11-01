# OpenSchematix v1.1.0 — Release notes

**Release date:** 2026-11-01

OpenSchematix is a free, open-source, offline schematic editor for electrical, electronic, hydraulic and pneumatic drawings. Version 1.1.0 adds drafting and symbol-editing capabilities, improves performance, and fixes project integrity and UI defects.

## Highlights

- **Boundary fill / hatch:** `FILL` and `HATCH` fill closed areas bounded by lines, polylines, polygons, rectangles, circles and arcs, with support for islands (holes) and an optional small-gap tolerance. Fills remain editable vector objects and export to SVG, PDF and DXF.
- **Symbol editing:** Open existing built-in, library or project symbols as editable copies, including symbols placed on drawings. Custom symbols support aliases, with collision checks; the symbol editor gains selection, navigation and redo shortcuts.
- **Drafting:** Adjustable arrowheads on lines and polylines, including custom-symbol line primitives.
- **Performance:** Spatial indexing speeds up connection analysis and wire-crossing detection; hover highlighting no longer redraws the entire drawing.
- **Context menus:** Right-click canvas menus now retain Tk's native menu grab, allowing Escape and outside-click dismissal without installing temporary root handlers that could interfere with active CAD commands.
- **Reliability and data integrity:** Improved validation of malformed project files, revision history and symbol definitions; project-specific symbol resolution prevents cross-project pin mismatches; safer custom-symbol updates and wire attachments; improved BOM grouping of multi-symbol devices.
- **Usability:** Toolbar tooltip fixes, command-line completion fixes, custom-symbol terminal designation corrections and ANSI A as the default sheet size for new projects.

For the full list of changes, see [CHANGELOG.md](../CHANGELOG.md).

## Downloads

After the GitHub release is published, download the platform package from [GitHub Releases](https://github.com/nrobertson152/OpenSchematix/releases):

| Platform | File |
| --- | --- |
| Windows installer (x64) | `OpenSchematix-1.1.0-Setup-x64.exe` |
| Windows portable (x64) | `OpenSchematix-1.1.0-windows-x64-portable.zip` |
| Linux AppImage (x86-64) | `OpenSchematix-1.1.0-x86_64.AppImage` |
| Linux bundle (x86-64) | `OpenSchematix-1.1.0-linux-x86_64.tar.gz` |

Windows installer and Linux packages are built automatically by the release workflow; verify the actual attached files and `SHA256SUMS.txt` after publication. No Python installation, account or internet connection is required to run the packaged application.

## Compatibility and limitations

- Projects without hatch fills retain the older sheet schema where possible. Sheets containing fills use **schema 3** and cannot be opened by OpenSchematix 1.0.x. A fill present only in revision history also requires schema 3.
- Circuit templates containing fills use **template version 2**.
- Older `.osch` drawings can still be opened and converted without overwriting the originals.
- Fills are solid and non-associative: changing the surrounding boundary does not automatically recalculate an existing fill. Wires and symbols are not fill boundaries.
- DXF export uses R12-compatible SOLID entities for fills; DXF HATCH import is not supported.
- The built-in PDF text font does not support all Unicode characters.
- Automated Linux and Windows CI checks do not replace interactive acceptance of native Windows context-menu dismissal, installer/uninstaller, file associations or upgrade behavior. These require manual testing or explicit release-risk acceptance.

## Verification and release control

The v1.1.0 code and packaging must be validated against the **final tagged commit**, including any documentation changes. A successful workflow run against an earlier commit does not validate the final release. Publishing the `v1.1.0` GitHub release triggers Linux and Windows builds and attaches the generated packages and checksums after both platform jobs pass.

**License:** GNU GPL v3.0 or later. Copyright © 2026 Nate Robertson.
