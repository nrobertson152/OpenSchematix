# OpenSchematix v1.2.0 — Release notes

**Release date:** _set when the Director publishes the release_

OpenSchematix is a free, open-source, offline schematic editor for electrical, electronic, hydraulic and pneumatic drawings. Version 1.2.0 greatly expands the bundled symbol libraries, and fixes save performance, wire numbering, PDF text and temporary print files.

> **Draft:** this page lists the changes intended for v1.2.0 (issue #87). The final notes must match the PRs actually merged; see "Verification and release control" below.

## Highlights

- **Much larger symbol libraries (#66):** 425 new built-in, connectable symbols. Existing symbols are unchanged.
  - **Hydraulic and pneumatic** (ISO 1219 and ANSI Y32.10 styles): lines and couplings, reservoirs and accumulators, fluid conditioning, pumps and motors, cylinders, pressure, flow and non-return valves, instruments.
  - **Electrical and electronic:** passive parts, sources, semiconductors, transistors, transformers, switches and relays, logic, meters and op-amps.
  - **Directional-valve configurator:** 28 more operators, five more centre conditions, a third operator per side, and proportional and transition options.
  - **Drafting marks** (arrows, energy and marking symbols): these have no terminals and never appear in the BOM.
- **Faster saving (#79, related to #75):** saving no longer slows down as the revision history grows. On a 2 MB drawing with 25 snapshots, a save took 1.56 s and now takes 0.24 s.
  - The *Recent files* menu no longer checks each file's location after every save. On Windows that check could hang for seconds on an offline network drive.
  - A save is now refused, and the previous file kept, if any part of the new file would not reopen intact.
- **Wire numbering (#83):** *Number wires* never reuses a number set by hand on another connection. Setting a number by hand moves any connection that already had it automatically, and the status bar reports the change.
- **PDF text (#84):** Greek letters, maths and arrow characters (Ω, Δ, μ, ≤, ≥, ∞, →, …) now appear in PDF exports and printouts, using the standard Symbol font. Characters that still can't be shown are reported, not silently replaced with "?".
- **Print (#85):** temporary print PDFs go into a private folder for each user and are cleaned up when the program closes, and later by age. Files left in the temporary folder by 1.1.x are tidied up too.

For the full list of changes, see [CHANGELOG.md](../CHANGELOG.md).

## Downloads

After the GitHub release is published, download the platform package from [GitHub Releases](https://github.com/nrobertson152/OpenSchematix/releases):

| Platform | File |
| --- | --- |
| Windows installer (x64) | `OpenSchematix-1.2.0-Setup-x64.exe` |
| Windows portable (x64) | `OpenSchematix-1.2.0-windows-x64-portable.zip` |
| Linux AppImage (x86-64) | `OpenSchematix-1.2.0-x86_64.AppImage` |
| Linux bundle (x86-64) | `OpenSchematix-1.2.0-linux-x86_64.tar.gz` |

The release workflow builds the Windows installer and the Linux packages automatically. After publication, check the files actually attached and `SHA256SUMS.txt`. The packaged application needs no Python installation, account or internet connection.

## Compatibility and limitations

- **No file format changes.** Projects, `.osch` drawings, `.osym` symbols and `.osymlib` libraries from 1.0.x and 1.1.x open unchanged.
- **New symbols and older versions.** A project that uses one of the new built-in symbols opens in 1.1.x with that symbol shown as a placeholder, with a warning. Its wires keep their attachments, including after a re-save. This was checked against current `main` (1.1.0 plus #83).
- **PDF fonts.** PDF text uses the standard Helvetica and Symbol fonts; no fonts are embedded. Characters outside both fonts (for example Cyrillic or CJK) are drawn as "?", and Export PDF and Print say which ones. SVG and DXF exports keep them.
- **Viewer font substitution.** Viewers that substitute a font without the standard Symbol glyphs may draw some symbols blank. Acrobat, PDFium (Edge and Chrome), MuPDF and pdf.js include the standard fonts.
- **Windows save freeze (#75).** The user report has not been reproduced. 1.2.0 fixes the two causes found, but it isn't known whether they explain that report.
- **Manual acceptance.** Automated Linux and Windows CI checks don't replace hands-on acceptance of the installer and uninstaller, file associations, upgrades from 1.1.0, or PDF appearance in the viewers people actually use.

## Verification and release control

The v1.2.0 code and packaging must be validated against the **final tagged commit**, including any documentation changes. A successful workflow run against an earlier commit does not validate the final release. Publishing the `v1.2.0` GitHub release triggers Linux and Windows builds and attaches the generated packages and checksums after both platform jobs pass.

**License:** GNU GPL v3.0 or later. Copyright © 2026 Nate Robertson.
