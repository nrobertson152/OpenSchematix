# KiCad

*File ▸ Export ▸ KiCad project (all sheets)…* (or `EXPORT KICAD`) writes the whole project as a KiCad project, so
the schematic can be carried on in [KiCad](https://www.kicad.org/), shared with someone who uses it, or taken on to a
circuit board. KiCad 7, 8 and 9 open it: the files are in KiCad 7's format, which the later versions read and
update. Every change to the export is checked by KiCad 7, 8 and 9 themselves (CI installs each and compares its netlist
with OpenSchematix's nets).

Choose a name and a folder. A new, empty folder is best: it becomes the KiCad project.

| File | What it is |
|---|---|
| `NAME.kicad_sch` | the schematic. A project with several sheets is a root sheet holding one sheet per OpenSchematix sheet, as KiCad does it (`NAME-2-Motor_control.kicad_sch` and so on) |
| `OpenSchematix.kicad_sym` | the symbols the drawing uses, as a KiCad library, so they can be placed again in KiCad |
| `sym-lib-table` | tells KiCad where that library is. A table already in the folder is added to, never replaced |
| `NAME.kicad_pro` | so KiCad opens the folder as a project. One that's already there is left alone |

If the folder already has files the export would replace, other than the schematic you named, it asks first.

## What comes across

- **Every connection, exactly.** What OpenSchematix connects, KiCad connects, and nothing else: wires are split wherever
  another wire ends on them (KiCad only joins ends), a wire attached to a terminal ends exactly on it, junction dots are
  where OpenSchematix draws them, wires that only cross stay apart, and a terminal lying on the middle of a wire isn't
  connected to it in either program. The tests have KiCad read the export and compare its netlist with OpenSchematix's
  nets, for the examples and for every built-in symbol.
- **Sheet connectors** become KiCad *global labels*, which join every label of the same name on every sheet, as sheet
  connectors do.
- **Wire numbers** become the names of the nets (a label on one of the net's wires on each sheet). A number that two
  nets share isn't used, because in KiCad it would join them; the export says which.
- **Parts.** Designators, labels (as KiCad's *Value*), description, manufacturer, part number, rating and your own
  properties are fields of each part. A device drawn in several places under one designator, such as a contactor's coil
  and its contacts, is one KiCad part with a unit for each place (K1A, K1B, …). A terminal stays its own part (`X1:3`).
- **Pin numbers** are the terminal designations (A1, A2, 13, 14…). Where two places of one device have the same
  designation, the second gets the unit's number after it (`1.3` is terminal 1 of unit 3); give the terminals their
  real designations in OpenSchematix to get 13, 14, 23, 24. Pin numbers are shown when OpenSchematix shows terminal
  designations.
- **Drafting**: lines, rectangles, polygons, circles, arcs and text, with their line widths and dashes.
- **The title block**: title, date, revision, organisation, drawing number, who drew, checked and approved it, and the client.

## Size and grid

OpenSchematix draws on a 2.5 mm grid; KiCad's schematic grid is 100 mil (2.54 mm). The export writes the drawing 1.6 %
larger, so every terminal and wire lands on KiCad's grid, and parts from KiCad's own libraries connect to it. The
drawing is centred on the same paper size; something drawn right at the edge of the frame can reach KiCad's border.
A sheet at a scale other than 1:1, or on a custom paper size, gets a KiCad paper of its own size.

## What doesn't come across

- **Our frame and title block**: KiCad draws its own, filled in from the sheet.
- **Electrical pin types.** Every pin is *passive*, so KiCad's electrical rules check doesn't complain about drivers
  OpenSchematix doesn't model.
- **Footprints.** OpenSchematix has none; assign them in KiCad before making a board.
- **Wire colours and cross-sections**: KiCad's wires have no such properties. The export says so when the project has them.
- **Hydraulic and pneumatic lines** come across as wires, which is what they are in OpenSchematix's connectivity; KiCad
  knows nothing of fluid power.
- **Text in symbols turns with the symbol** in KiCad, where OpenSchematix keeps it upright.
- **Solid fills** are filled outlines; arcs in them are drawn as short straight pieces.
- **Cross-references** (the `/2.B4` beside a connector or a contact) aren't written; KiCad can show its own
  (*Show inter-sheet references*).
- **A symbol OpenSchematix can't find** is written as its placeholder, and wires attached to it by terminal name may
  not connect in KiCad. The export says which.
- **There's no import from KiCad** yet.
