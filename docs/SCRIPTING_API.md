# Python scripting API

`openschematix.api` lets a Python script create, open, edit, inspect, check and save OpenSchematix
projects **without the graphical interface**. Use it to generate drawings from data (I/O lists, valve
manifests, motor schedules), apply bulk changes, or check projects in a build pipeline.

The API is a thin layer over the application's own engine: the same placement, wiring and routing
code, the same connectivity rules, BOM, checker and `.schematix` writer. So a project made by a
script is identical to one drawn by hand and opens normally in the application.

- **Headless.** Importing `openschematix.api` never imports tkinter or opens a window, and it does not
  need a display server.
- **Local only.** There is no networking, telemetry or account. The API reads and writes only the
  files you name.
- **Strict.** Invalid input raises an exception and changes nothing. Nothing is silently snapped,
  clamped or replaced.

API version: `api.API_VERSION == 1` (phase 1).

## Installation and running

Scripting needs OpenSchematix as Python source (the packaged Windows/Linux applications do not include
a Python interpreter):

```
git clone https://github.com/nrobertson152/OpenSchematix.git
cd OpenSchematix
python -m pip install .            # optional: makes `import openschematix` work from anywhere
```

Python 3.10 or newer is required. Tkinter is **not** needed for scripting.

Run a script with any Python 3.10+ interpreter:

```
python my_script.py
python docs/examples/motor_starter.py out.schematix   # the complete example below
```

Without `pip install`, run scripts from the repository folder or set `PYTHONPATH` to it.

## Quick start

```python
from openschematix import api

project = api.new_project("Pump control", sheet_size="A3")
sheet = project.sheets[0]

k1 = sheet.place("el.coil.iec", 300, 200, rotation=270)       # contactor coil, A1 left / A2 right
s1 = sheet.place("el.pushbutton.no.iec", 150, 200)            # S1
sheet.connect(s1, "2", k1, "A1")                              # routed wire, terminal to terminal
k1.set_property("part_number", "AC-9-230V")

for line in project.bom():
    print(line.quantity, line.designator_text, line.part_number)
project.save("pump_control.schematix")
```

## Coordinates and grid

- **Units.** Coordinates are drawing units: 1 unit = 0.25 mm (`api.UNIT_MM`). X grows to the right
  and **Y grows downwards**.
- **Insertion points.** A component's `position` is its symbol's insertion point. It must be a
  multiple of the 10-unit grid (`api.GRID`). Every terminal then also lies on the grid, so wires
  connect exactly. Off-grid positions raise `InvalidOperationError`; they are not snapped.
- **Rotation and mirroring.** `rotation` is clockwise in degrees: 0, 90, 180 or 270 (`api.ROTATIONS`).
  `mirror=True` flips the symbol about its vertical axis and is applied **before** rotation, as in the
  application.
- **Symbol coordinates.** `api.get_symbol(id).terminals` gives each terminal's position relative to the
  insertion point before rotation. `component.terminals` gives world positions after rotation and
  mirroring.
- **Wires.** A wire is a polyline of horizontal and vertical segments. Its coordinates are whole
  units; diagonal segments raise an error.
- **Connection rules**, the same as the application's:
  - A wire end on a terminal connects to it. A wire that only passes over a terminal does not.
  - A wire end on another wire makes a junction (a T-junction).
  - Wires that merely cross are not connected.

## Identifiers

| Object | Identifier | Stable across save/reopen |
|---|---|---|
| Sheet | `sheet.uid` (string) | yes |
| Component | `component.id` (int, unique on its sheet); `(sheet.uid, component.id)` is unique in the project | yes |
| Wire | `wire.id` (int, unique on its sheet) | yes |
| Terminal | `terminal.name`, e.g. `"A1"`, `"P"`; the permanent key wires attach to | yes |
| Symbol | `symbol_id`, e.g. `"el.coil.iec"`; custom symbols are `"user:…"` | yes |

**Designators** (`K1`, `S2`) are what people read. They are not unique keys: several symbols of one
device (a relay coil and its contacts) share one. Use `project.find("K1")` to get all of them.

## API reference

Only the names in `openschematix.api.__all__` are public. Other `openschematix` modules are internal
and may change.

### Module functions

| Function | Returns | Description |
|---|---|---|
| `new_project(title="", sheet_size="A3")` | `Project` | New project with one empty sheet. Sizes: `A0`–`A4`, `ANSI A`–`ANSI E`, `Letter`, `Legal`, `Tabloid`. |
| `open_project(path)` | `Project` | Open a `.schematix` project, or convert a legacy `.osch` drawing. A converted drawing has `path` None, so `save()` needs a new path. The file is never modified by opening it. |
| `list_symbols(query="", category=None)` | `list[SymbolInfo]` | Placeable symbols, optionally filtered by search words and/or category. |
| `get_symbol(symbol_id)` | `SymbolInfo` | One symbol's description and terminals. |
| `load_user_library(path=None)` | `list[str]` | Register a custom-symbol library folder (default: the application's library). Returns load problems. |

### `Project`

| Member | Description |
|---|---|
| `title` | Project title (read/write). |
| `path` | Last opened/saved file, or `None`. |
| `warnings` | Tuple of messages from opening (format conversion, unknown symbols). |
| `sheets` | List of `Sheet` in order. |
| `sheet(key)` | Sheet by uid, name, or 1-based number. |
| `add_sheet(name=None)` | Append a sheet; returns it. |
| `remove_sheet(sheet)` | Delete a sheet. The last sheet cannot be removed. |
| `components()` | Every component on every sheet. |
| `find(designator)` | Components with that designator. |
| `nets()` | `list[Net]`: connected terminals and wires, project-wide. Sheet connectors with equal labels join nets across sheets. |
| `number_wires(renumber=False)` | Assign wire numbers as *Number wires* in the application. Returns the count. |
| `bom(include_excluded=False)` | `list[BomItem]`, exactly as the BOM report. |
| `bom_csv(include_excluded=False)` | The BOM as CSV text, starting with a UTF-8 byte-order mark (write it with `encoding="utf-8"`). |
| `check(rules=None, require_part_numbers=False)` | `list[Issue]` from Check Drawing; `rules` is a subset of `openschematix.check.RULES`. |
| `save(path=None, snapshot=True)` | Save as `.schematix`: atomic, and verified before the old file is replaced. `snapshot` records an automatic revision snapshot, like saving in the application. Returns the path. |

### `Sheet`

| Member | Description |
|---|---|
| `uid`, `name` (read/write), `number`, `size`, `project` | Identity and page information. |
| `components()`, `component(id)` | Components on the sheet. |
| `wires()`, `wire(id)` | Wires on the sheet. |
| `place(symbol_id, x, y, *, rotation=0, mirror=False, params=None, designator=None, label="", properties=None)` | Place a symbol; returns a `Component` (details below). |
| `add_wire(points, style="solid")` | Draw a wire through `points` (see Coordinates). Ends on terminals attach to them. Returns a `Wire`. |
| `connect(a, a_terminal, b, b_terminal, style="solid")` | Wire two terminals with the application's router. Returns a `Wire`. |
| `remove(obj)` | Remove a component or wire. |
| `connectivity()` | `SheetConnectivity`: junction points, open wire ends, open and connected terminals. |

How `place` fills in details:
- **Designator.** Without `designator`, the next free one is assigned project-wide (K1, K2, …).
- **Terminal blocks** (`el.terminal`) get a strip and a terminal number (X1:1, X1:2). Passing
  `designator="X5"` puts the terminal on strip X5 with that strip's next number.
- **Parameters.** `params` sets parameters of a parametric symbol; omitted keys keep their defaults.
- **Existing wires.** Free wire ends that touch the new terminals connect to them.

### `Component`

| Member | Description |
|---|---|
| `id`, `sheet`, `symbol_id`, `locked` | Identity (read-only). |
| `designator`, `label` | Read/write strings. |
| `position` | `(x, y)`, read/write; must be on the grid. Attached wires follow, as when dragging in the application. |
| `move_by(dx, dy)` | Grid-aligned relative move. |
| `rotation`, `mirror` | Read/write. Attached wires follow. |
| `params`, `set_params(**changes)` | Parameters of parametric symbols (see below). |
| `properties`, `set_property(key, value)`, `remove_property(key)` | Properties: `description`, `manufacturer`, `part_number`, `rating`, `terminal`, or any custom key. An empty value removes the property, as in the Properties panel. |
| `in_bom` | Read/write: counted in the bill of materials. |
| `terminals`, `terminal(name)` | `Terminal` values in world coordinates. |
| `remove()` | Delete the component; wires stay with their ends unconnected. |

Returned dicts (`params`, `properties`, `terminals`) are copies. Change the component through the
setters and methods.

**Locking.** Components and wires that are locked, or on a locked layer, cannot be changed: every
change raises `InvalidOperationError`, matching the application, where they cannot be selected.

### `Wire`

`id`, `sheet`, `points`, `start` / `end` (`(component_id, terminal)` or `None`), `style`, `number`,
`remove()`.

### Value types

These are frozen dataclasses: snapshots that do not change when the project changes.

| Type | Fields |
|---|---|
| `SymbolInfo` | `id, name, category, group, convention, description, prefix, parametric, default_params, terminals, custom` |
| `SymbolTerminal` | `name, label, x, y, direction, port_type`. Symbol-local; `direction` is the outward lead direction `l/r/u/d`. |
| `Terminal` | `name, label, position, direction, port_type`. World coordinates. |
| `TerminalRef` | `sheet_uid, sheet_name, component_id, designator, terminal` |
| `Net` | `number, terminals, wires, sheets` |
| `SheetConnectivity` | `junctions, open_wire_ends, open_terminals, connected_terminals` |
| `BomItem` | `item, quantity, designators, designator_text, description, manufacturer, part_number, rating, symbol, sheets` |
| `Issue` | `severity` (`error`/`warning`/`info`), `code`, `message, sheet_uid, object_id, suggestion` |

### Parametric symbols (directional valves)

`fl.hyd.dcv` and `fl.pneu.dcv` take these parameters:

| Key | Values |
|---|---|
| `type` | Hydraulic: `2/2`, `3/2`, `4/2`, `4/3`. Pneumatic: `2/2`, `3/2`, `5/2`, `5/3`. |
| `positions` | One pattern per switching position (see `openschematix.symbols.fluid.PATTERNS`). Changing `type` without giving `positions` uses that type's default positions. |
| `left`, `right` | Lists of actuators: `spring`, `solenoid`, `pilot`, `lever`, `pushbutton`, `manual`. |
| `medium` | Fixed by the symbol; it cannot be changed. |

The drawing engine falls back to defaults for unknown values. The API raises instead.

`set_params` also refuses a change that would remove a terminal with a wire attached (for example
changing a wired 4/2 valve to 2/2), instead of silently disconnecting it. Remove those wires first.

### Errors

Every error derives from `api.ApiError`. Each also derives from the matching built-in exception, so
`except KeyError` or `except ValueError` work too.

| Exception | Base | Raised when |
|---|---|---|
| `SymbolNotFoundError` | `KeyError` | Unknown symbol id. |
| `ObjectNotFoundError` | `KeyError` | Unknown sheet, component, wire or terminal, or a handle to a removed object. |
| `InvalidOperationError` | `ValueError` | The input would give invalid engineering data: off grid, bad rotation, diagonal wire, invalid parameter, locked object, removing the last sheet, … |
| `ProjectFileError` | `ValueError` | A project cannot be opened or saved. |

```python
from openschematix import api

project = api.new_project()
sheet = project.sheets[0]
try:
    sheet.place("el.coil.iec", 105, 200)
except api.InvalidOperationError as e:
    print(e)    # position (105, 200) is not on the 10-unit grid; ...

try:
    sheet.place("el.contactor.magic", 100, 200)
except api.SymbolNotFoundError as e:
    print(e)    # unknown symbol 'el.contactor.magic'; use openschematix.api.list_symbols() ...

k1 = sheet.place("el.coil.iec", 100, 200)
try:
    k1.terminal("1")
except api.ObjectNotFoundError as e:
    print(e)    # K1 (el.coil.iec) has no terminal '1'; terminals: A1, A2

try:
    api.open_project("missing.schematix")
except api.ProjectFileError as e:
    print(e)
```

### Custom symbols

Placing a custom symbol (`user:…`) needs it to be registered first. There are two ways:
- **From a library:** `api.load_user_library(path)` registers a folder of `.osym` files.
- **From a project:** opening a project registers the custom symbols embedded in it.

When a custom symbol is placed, its definition is embedded in the project (as when saving in the
application), so the saved file opens anywhere. A script can work with several open projects at
once: each project's embedded symbols are activated automatically when it is used.

## Complete example

[`docs/examples/motor_starter.py`](examples/motor_starter.py) builds a two-sheet project:
- **Control:** a fused start/stop latching contactor circuit with a run lamp.
- **Hydraulics:** a pump with a relief valve feeding a 4/3 solenoid valve that drives a cylinder.

The script then numbers the wires, runs the checker, prints the BOM and saves the project:

```
$ python docs/examples/motor_starter.py motor_starter.schematix
warning: Terminal X1:1:1 is not connected.
warning: Terminal X1:2:2 is not connected.
11 nets
  1   1 x A1         CYL-40/25-200    Cylinder, double-acting
  2   1 x F1         FU-2A            Fuse
  ...
saved motor_starter.schematix
```

The two warnings are the supply terminals' field-side connections, which are left open on purpose. The
script's key steps:

```python
ctl = project.sheets[0]
supply_l = ctl.place("el.terminal", 100, 200, designator="X1")
fuse = ctl.place("el.fuse.iec", 200, 200, properties={"rating": "2 A gG"})
stop = ctl.place("el.pushbutton.nc.iec", 300, 200, label="Stop")
start = ctl.place("el.pushbutton.no.iec", 400, 200, label="Start")
coil = ctl.place("el.coil.iec", 520, 200, rotation=270, label="Motor contactor")
supply_n = ctl.place("el.terminal", 640, 200, designator="X1")
hold = ctl.place("el.contact.no.iec", 400, 280, designator=coil.designator)   # part of K1

ctl.connect(supply_l, "2", fuse, "1")
ctl.connect(fuse, "2", stop, "1")
ctl.connect(stop, "2", start, "1")
ctl.connect(start, "2", coil, "A1")
ctl.connect(coil, "A2", supply_n, "1")
# parallel branch: wire ends on the rung wire make junctions
ctl.add_wire([(360, 200), (360, 280), hold.terminal("1").position])
ctl.add_wire([hold.terminal("2").position, (440, 280), (440, 200)])
```

Tip: draw parallel branches with `add_wire` ending on an existing wire, as above. Several `connect()`
wires leaving one terminal can run on top of each other, which Check Drawing reports as an error.

## Current limitations (phase 1)

- **No undo.** Keep a copy of the file, or don't save, if you need to go back.
- **Not covered yet:**
  - drafting shapes (lines, text, fills);
  - layers;
  - title-block and page setup beyond the paper size;
  - manual wire numbers;
  - terminal designation overrides;
  - revisions, export (PDF/SVG/DXF), netlist and terminal reports.

  These remain available through the application.
- **Shared symbol registry.** The registry is process-wide. The API keeps open projects correct by
  re-activating each project's embedded symbols when it is used. Code that mixes the API with
  internal `openschematix` modules must do the same.
- **Not thread-safe.** Use one thread.
- **Source checkout required.** The packaged Windows/Linux applications cannot run scripts.
