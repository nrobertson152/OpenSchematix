# Manual engineering acceptance tests

These are **human-executed acceptance scenarios**, not evidence that any test has passed. Run against a packaged release candidate, record platform, OS, Python/Tk (if running from source), app version, commit, tester, and date. Capture a screenshot or saved test project for each failure. Do not modify original customer drawings.

For each scenario record **Pass / Fail / Blocked / Not applicable**, the observed result, and a reproduction reference. Start with a new project unless otherwise stated.

## A. Drawing and editing workflow

| ID | Procedure | Expected result |
| --- | --- | --- |
| A01 | Create a project, rename a sheet, add a second sheet, save, close, reopen. | Sheet order, names, metadata, and drawing contents persist. |
| A02 | Draw lines, polylines, rectangles, circles, arcs, and text; apply object snap, grid snap, and ortho. | Coordinates and displayed geometry agree; snap/ortho behave predictably. |
| A03 | Select multiple objects; move, copy, rotate, mirror, and scale them; undo and redo each operation. | Geometry and object properties are restored without duplicates or loss. |
| A04 | Trim and extend intersecting drawing geometry, including arcs. | Correct intersection selected; unrelated geometry unchanged. |
| A05 | Create layers; change visibility/lock state; group and ungroup objects. | Editing respects lock state and visibility; state persists after reopen. |
| A06 | Execute commands by toolbar/menu and command line; use typed absolute, relative, and polar coordinates. | Equivalent operations produce equivalent geometry. |

## B. Electrical schematic workflow

| ID | Procedure | Expected result |
| --- | --- | --- |
| B01 | Place two built-in components and connect terminals with wires. | Wires attach to intended terminals; netlist shows expected connectivity. |
| B02 | Cross two wires without a junction, then explicitly connect and disconnect the crossing. | Netlist changes only when a junction is intentionally added/removed; bridge rendering agrees. |
| B03 | Move and rotate a wired component, undo, redo, save and reopen. | Connectivity and wire geometry remain consistent with supported editing behavior. |
| B04 | Add matching sheet connectors across two sheets; run drawing checks. | Cross-references and project-wide connections are correct. |
| B05 | Add manufacturer, part number, and custom fields; generate BOM and connection/wire lists. | Reports reflect actual component data, identifiers, and quantities. |
| B06 | Delete or duplicate components and wires; run drawing checks again. | No stale report entries or phantom connectivity remain. |

## C. Symbol libraries and documentation

| ID | Procedure | Expected result |
| --- | --- | --- |
| C01 | Copy a built-in symbol into an editable custom symbol; change pins and save it. | Original built-in symbol remains unchanged; custom symbol is usable. |
| C02 | Export and import a custom symbol library in a fresh user profile. | Symbol geometry, pins, labels, and metadata survive. |
| C03 | Insert custom symbols into a project, save, reopen on a clean profile without that library. | Embedded symbol appearance and pin behavior remain correct. |
| C04 | Create title block, drawing zones, revision entry, and issue a revision. | Metadata and revision history survive save/reopen and appear in intended outputs. |
| C05 | Export a multi-sheet PDF and inspect all pages in an external viewer. | Page count, scale, symbols, text, title blocks, and line weights are legible and correct. |
| C06 | Export SVG and DXF; open each in independent compatible viewers. | Geometry and supported semantics remain faithful; unsupported elements are documented. |

## D. Boundary fill (only when Phase 3 is included)

| ID | Procedure | Expected result |
| --- | --- | --- |
| D01 | Fill a closed rectangle and a closed mixed line/arc outline. | Interior region fills; boundaries remain independently editable. |
| D02 | Fill a ring between concentric circles; click inside the hole. | Ring is filled and central hole remains empty visually and during selection. |
| D03 | Create two and three nested contours and multiple disjoint holes. | Fill follows intended even/odd containment with no accidental bridging. |
| D04 | Pan and zoom repeatedly on Tk 8.6; switch sheets; reopen project. | Holes and curved boundaries render consistently with no stale canvas artifacts. |
| D05 | Try open boundaries with gap tolerance off, then adjust tolerance deliberately. | Open regions are rejected unless the permitted gap-closing behavior yields a valid region. |
| D06 | Test tangencies, overlaps, and near-coincident line/arc intersections. | No crash, hang, invalid geometry, or unintended fill. |
| D07 | Move/rotate/mirror/scale a fill, undo/redo, then save and reopen. | Fill shape, hole geometry, and editing state remain consistent. |
| D08 | Export fill to SVG, PDF, and DXF; inspect in independent viewers. | Solid regions and holes match intended geometry within each documented format limitation. |
| D09 | Save a project whose current drawing has no fills but an older revision does; reopen. | Historical fill data is preserved and project schema compatibility is enforced. |
| D10 | Create a dense drawing with many intersections; attempt fill and cancel where supported. | Application remains responsive or fails gracefully; record timing and object count. |

## E. Packaging, recovery, and offline operation

| ID | Procedure | Expected result |
| --- | --- | --- |
| E01 | Install on a clean Windows machine; launch, create/save project, uninstall. | Installer, shortcuts, file associations, application and uninstaller work. |
| E02 | Extract and launch Linux package; test optional integration script and uninstall. | Program starts without developer environment; desktop integration is reversible. |
| E03 | Test a normal project at 100%, 150%, and 200% display scaling where available. | Text, icons, dialogs, and canvas interaction remain usable. |
| E04 | Force-close application after an unsaved edit; relaunch and inspect recovery behavior. | Recovery works according to documented guarantees without corrupting last saved project. |
| E05 | Attempt to open a damaged or unsupported newer-version project. | Clear error; original file remains intact; application stays responsive. |
| E06 | Operate disconnected from network, including startup, editing, save, and export. | Core functions work without login, cloud service, or network access. |

## Defect report template

- Scenario ID:
- Severity: Blocker / High / Medium / Low
- Platform and application commit:
- Steps and input drawing:
- Expected versus observed:
- Evidence (screenshot, exported file, log, or minimal project):
- Reproducibility (e.g., 5/5 attempts):
- Owner / fix PR / retest outcome:

**Release rule:** Any confirmed data-loss, incorrect electrical connectivity, corrupt project serialization, or materially incorrect exported engineering drawing is a release blocker until resolved or explicitly excluded from release scope.
