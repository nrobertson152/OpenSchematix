# OpenSchematix — Future Release Bug and Feature Backlog

**Source:** Project Director's 2026-11-02 report. **Scope:** future OpenSchematix releases; no release version assigned.
**Status:** Intake only. These are user-reported observations and requested capabilities, **not independently reproduced defects, implemented features, accepted designs, or assigned work**.

**Agent instruction:** This backlog is planning input, not an assignment. Work on an item starts only when the Director opens an issue that cites its ID; the ARF coordinator then writes the contract (see `AGENTS.md`). Do **not** silently include these items in other work, or claim that the bugs have been verified. Keep the stable IDs below when referring to items in issues and PRs.

## Triage and priority guidance

- **Investigate first:** Windows save freeze (**OS-FUT-001**, [issue #75](https://github.com/nrobertson152/OpenSchematix/issues/75)); possible Windows autosnapshot/recovery discrepancy (**OS-FUT-023**). Determine whether either causes data loss before setting a release gate.
- **Platform/functional defects:** OS-FUT-003, 009, 010, 011, 017, 019, 020, 022. Prioritize based on reproducibility, severity and workflow impact.
- **Feature and engineering-data design:** OS-FUT-002, 004–008, 012–016, 018, 021 and the configurable aspects of 023. Evaluate file-format, BOM, connectivity, export, UI and backward-compatibility effects.
- **Related work to coordinate:** 003 + 021 + 022 (scaling); 004 + 005 + 006 (annotations); 002 + 013 (connector models); 014 + 015 + 016 (fluid/electrical physical connection metadata); 001 + 023 (save/recovery).
- **Priorities are provisional**, not Director-approved milestone assignments.

## Complete Director-requested inventory

| ID | Type | Reported bug or requested feature | Acceptance / investigation notes |
| --- | --- | --- | --- |
| **OS-FUT-001** | Windows bug report | **Saving freezes the application on Windows.** | [Issue #75](https://github.com/nrobertson152/OpenSchematix/issues/75). Reproduce with Windows version/build and project; inspect responsiveness, atomic save, last-good file, Save As, recovery and data integrity. Treat data loss as a potential blocker **only if confirmed**. |
| **OS-FUT-002** | Feature | **Configurable electrical connectors** (e.g., Deutsch, M12, D-sub). | Define connector family, cavity/terminal count and layout, pin/socket gender, numbering, mating compatibility, component/symbol metadata, drawing/BOM/export representation. Coordinate with item 013. |
| **OS-FUT-003** | Bug / redesign | **Rework the Scale feature:** currently laggy and reportedly does not scale individual components. | Reproduce performance with representative drawings; define selected-object vs entire-drawing behavior, geometry and terminals, wires/connectivity, labels, undo/redo, save/reopen and exports. Coordinate with items 021 and 022. |
| **OS-FUT-004** | UI feature | **Replace component-properties text-position dropdown with a graphical position selector.** Default **Automatic**; manual placement in **45° increments** rather than 90° only; include **Center**. | Specify 8 compass positions + center + automatic, preview and keyboard accessibility; verify rotations/mirrors, save/reopen and exports. |
| **OS-FUT-005** | Annotation bug / enhancement | **Automatic component-text placement should avoid overlapping existing wires or text.** | Test crowded schematics and multiple orientations; prioritize legibility, deterministic placement, minimal overlap and stable export; define fallback when no clear position exists. |
| **OS-FUT-006** | Annotation bug / enhancement | **Smart terminal-designation placement**: designations frequently overlap wires, but should remain visually uniform. | Define consistent offsets/alignment, collision avoidance with wires and text, component rotations/mirrors, zoom, export and dense multi-terminal symbols. |
| **OS-FUT-007** | Design exploration | **Consider mating shafts** between mechanical power components such as hydraulic pumps and electric motors. | Clarify whether this is a schematic mechanical-coupling graphic, explicit semantic connection, or both; define port/shaft compatibility, transforms, BOM and save-format implications before implementation. |
| **OS-FUT-008** | Feature | **Adjustable reservoir sizing.** | Determine supported reservoir symbol variants and resize handles/properties; keep ports, annotations, stroke weights, snap and exported drawings consistent. |
| **OS-FUT-009** | Rendering bug report | **Dashed-line appearance changes inconsistently with zoom.** | Reproduce at multiple zoom/DPI levels; verify dash phase/length/weight consistency on canvas and SVG/PDF/DXF where supported. |
| **OS-FUT-010** | Windows bug report | **Command line doesn't accept typing until clicked on Windows**, unlike Linux; **Space** does not toggle the active tool as expected. | Compare Windows/Linux keyboard focus and shortcut dispatch with and without selected drawing tools; avoid stealing text from property editors/dialogs. Verify expected Space behavior against documented command modes. |
| **OS-FUT-011** | Editor feature gap | **Fill command unavailable in component/symbol editor.** | Determine supported symbol geometry and persistence/export implications; enable boundary fill or document explicit restrictions; test editor undo/redo, symbol libraries and embedded symbols. |
| **OS-FUT-012** | Feature | **Customizable title blocks.** | Provide editable title-block layout/fields/template persistence; preserve sheet zones, margins, revision data, page sizes and PDF/DXF exports. |
| **OS-FUT-013** | Connector feature | **Per-terminal part number** for configurable connectors (individual pins/sockets). | Define terminal-level manufacturer/part number, cavity assignment and optional quantity/BOM handling; ensure compatibility with item 002 and no accidental conflation with connector-housing part number. |
| **OS-FUT-014** | Hydraulic metadata | **Hydraulic port sizes** assignable per component/port. | Define size units/designations and per-port storage, property editor, symbols, BOM/reporting and compatibility with existing project files. |
| **OS-FUT-015** | Fluid connection feature | **Account for hydraulic/pneumatic fittings and couplings**, and other applicable connection hardware. | Specify explicit fitting/coupling components vs connection metadata, quantities, mating compatibility, BOM/reporting and physical-vs-schematic semantics. |
| **OS-FUT-016** | Engineering metadata | **Wire gauge and hose type/size** (and analogous connection properties) must be user-designatable. | Define per-wire/per-hose attributes, units, inheritance, editing, connection lists/BOM and exports; preserve legacy data. |
| **OS-FUT-017** | Layer rendering bug report | **Wire connection dots remain visible when the wire layer is hidden.** | Verify junction/dot ownership and visibility when the corresponding wire layer is disabled; test mixed-layer crossings, export, undo/redo and actual netlist semantics independently of visibility. |
| **OS-FUT-018** | UI feature | **Detach a sheet into its own window.** | Design multi-window shared-project state, active sheet, focus, tools, undo/redo, save/reopen, close behavior and cross-window edits; avoid duplicate unsynchronized project models. |
| **OS-FUT-019** | UI scaling bug report | **Interface scale changes only appear after restarting.** | Reproduce live settings changes on Windows/Linux; update fonts, icons, layouts, dialogs and canvas interactions immediately without reopening, preserving usability and settings. |
| **OS-FUT-020** | UX bug / enhancement | **Automatically fit the sheet to the view when a project opens.** | Apply to initial project/sheet opening without overriding explicit user zoom/pan during subsequent work; account for dock/sidebar sizes, window resize and different sheet sizes. |
| **OS-FUT-021** | Feature | **Allow users to scale individual components.** | Define per-instance scale vs symbol definition edits; preserve terminal connectivity, grid/snap, labels, bounds, exports, undo/redo and save/reopen. Coordinate with 003. |
| **OS-FUT-022** | Layout bug / enhancement | **Improve Fit Drawing to Sheet:** output is currently too small, but must not overlap title block, sheet zones or edges. | Calculate available printable/drawable area and margins, honor title-block exclusion, aspect ratio, line/text legibility and all supported paper sizes. Coordinate with 003/021. |
| **OS-FUT-023** | Recovery bug report + feature | **Configurable autosnapshots**, default **one snapshot every 5 minutes**; restore **any retained snapshot**. Reportedly works on Linux but **may not work on Windows** (unconfirmed). | Verify both OSes before claiming platform defect. Define interval setting, retention/cleanup, per-project history and restore selection; test real timed snapshots, crash/relaunch, unsaved edits, multiple snapshots, missing/corrupt snapshots and non-destructive restore. |

## Cross-cutting implementation acceptance

1. **Reproduce before fixing:** For bug reports, collect app version, OS, exact steps, observed/expected behavior, reproducibility, minimal project and logs/screenshots. Record *unconfirmed* if not reproduced.
2. **Preserve engineering correctness:** Visual changes must not silently alter terminal geometry, wire/netlist connectivity, hydraulic/pneumatic semantics, BOM data, or source/project meaning.
3. **Persist and export faithfully:** For new settings, per-instance attributes, annotations, connectors, mechanical couplings and title-block customizations, test undo/redo, save/reopen, legacy projects, embedded symbols, and supported SVG/PDF/DXF exports. Evaluate project/schema migration before changes.
4. **Verify both platforms:** GUI and focus bugs require actual Windows and Linux verification, not only headless tests. Record version, Python/Tk, display scaling, exact SHA and executed results.
5. **Keep releases controlled:** Items remain unassigned backlog entries until the Director approves scope/priority and GitHub ownership. Only the Director may authorize merges/releases. Do not weaken tests or claim fixes without independent evidence.

## Updating this backlog

- Preserve each **OS-FUT-###** identifier in future issues/PRs and release notes.
- Add links to dedicated tracking issues or PRs once created; record whether reported, reproduced, implemented, independently verified, or deferred.
- When a feature changes project formats or engineering semantics, document the approved design and compatibility plan in its issue.
- Do not mark any entry complete based on this intake document alone.
