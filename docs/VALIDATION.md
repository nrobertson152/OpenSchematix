# Check Drawing rules

*Tools ▸ Check drawing* (F5, command `CHECK`) runs the rules below on the whole project and lists the
results in the *Check drawing* panel with their severity, a description, the affected object, the sheet,
the grid zone and a suggested action. Double-click a result to go to it.

> **Passing these checks does not certify a drawing as safe, correct or compliant with any standard.**
> The rules find common drafting mistakes and inconsistencies between the drawing and its connection data.
> They do not simulate circuits, check ratings, protection, interlocks or safety functions.

Severities: **Error** — almost certainly wrong; **Warning** — often wrong, check it; **Info** — a note.

| Rule | Severity | Finds |
|---|---|---|
| Duplicate identifiers | Error | Two or more components with the same identifier that are indistinguishable (same symbol, same label, same terminal designations). Parts of one device — a relay coil K1 and its contacts K1 13-14, K1 23-24 — may share an identifier. |
| Duplicate terminal designations | Error / Warning | Two terminals with the same strip and number (X1:3 twice); a terminal without a number; repeated terminal designations on one component. |
| Disconnected terminals | Warning | Component terminals with nothing connected. Intentionally unused terminals (spare contacts, plugged ports) are reported too; ignore them. Sheet connectors are excluded. |
| Dangling wires | Warning | Wire ends that touch no terminal and no other wire. |
| Incompatible port domains | Error | A connection joining electrical, hydraulic and pneumatic ports. |
| Fluid-power port rules | Warning | Pump delivery (P) connected straight to a tank; a pneumatic exhaust port (3, 5) connected to a supply port (1); a pressure port connected directly to a tank/return port with nothing else on the line. |
| Electrical port rules | Error / Warning | Two or more outputs on one connection (warning); a power-supply port connected directly to earth/ground (error). Applies to custom symbols whose pins have port types. |
| Missing properties | Warning / Info | Components that need an identifier but have none; optionally purchasable parts without a part number. |
| Cross-sheet references | Error / Info | Sheet connectors without a label; labels with no matching connector anywhere (error); all matching connectors on one sheet (info). |
| Junction and overlap consistency | Error / Warning | Wires running on top of each other (error); a wire passing over a terminal without connecting to it (warning); a wire ending exactly on a bridged crossing, which joins all three (warning). These are the cases where the picture could be read differently from the connection data. |
| Unsupported or incomplete symbols | Error / Warning / Info | Missing symbols (placeholders); custom symbols with no geometry (error) or no connection points (warning); fluid-power custom symbols whose connection points have no port type (info). |
| Wire numbers | Error / Warning | One wire number used by different connections (error); several manual numbers on one connection (warning). |

## Port types and domains

Every connection point has a port type. Built-in symbols derive it from their category and port name
(ISO 1219 / ISO 5599 conventions):

| Category | Port names | Port type |
|---|---|---|
| Hydraulic | P / T / X, Y / L / others (A, B, 1, 2 …) | hyd.pressure / hyd.tank / hyd.pilot / hyd.drain / hyd.work |
| Pneumatic | 1 / 3, 5 / 12, 14 / others (2, 4 …) | pneu.supply / pneu.exhaust / pneu.pilot / pneu.work |
| Electrical, Electronic | all | elec.passive |
| General | all | any (never checked) |

Custom symbols set the port type of each connection point in the symbol editor. The domain is the part
before the dot (`elec`, `hyd`, `pneu`); `any` is compatible with everything.

## Connectivity rules (used by checks, reports and the drawing)

* A wire connects to another wire where one of its **end points** lies on the other wire.
* A terminal connects to wires whose **end point** lies on it, and to other terminals at the same point.
* Wires that merely **cross** are not connected; the crossing is drawn with a bridge. *Connect wires*
  splits both wires at the crossing so four wire ends meet there (a junction dot is drawn).
* Sheet connectors with the same label are connected across all sheets of the project.
