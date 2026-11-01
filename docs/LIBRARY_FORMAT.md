# Custom symbols and symbol library packages

## A symbol: `.osym` (version 1)

```json
{
  "format": "OpenSchematix Symbol", "version": 1,
  "id": "user:3f2a9c1e5b7d4e10",
  "revision": 3,
  "name": "Proximity sensor, PNP", "description": "3-wire inductive sensor",
  "category": "Electrical", "group": "Sensors", "tags": ["sensor", "pnp"],
  "prefix": "B", "convention": "Custom",
  "properties": {"manufacturer": "…", "part_number": "…"},
  "prims": [
    {"k": "line",   "pts": [[-10, 0], [10, 0]], "w": "normal", "dash": false},
    {"k": "poly",   "pts": [[…]], "fill": false},
    {"k": "circle", "c": [0, 0], "r": 8, "fill": false},
    {"k": "arc",    "c": [0, 0], "r": 8, "start": 0, "extent": 180},
    {"k": "text",   "p": [0, 0], "s": "B", "size": 8, "anchor": "c"}
  ],
  "pins": [
    {"id": "p1", "name": "BN", "x": -20, "y": 0, "dir": "l", "type": "elec.power", "show": true}
  ]
}
```

* Coordinates are drawing units (0.25 mm) relative to the insertion point; **Y points down**.
  Angles are degrees counter-clockwise as seen on screen. Line widths: `thin` 0.25 mm, `normal` 0.35 mm,
  `thick` 0.55 mm.
* `id` must start with `user:` and is the symbol's permanent identity. Built-in ids can never be used.
* `revision` increases on every save. Projects embed the revision they were drawn with.
* Pins must lie on the 10-unit (2.5 mm) grid. `id` is permanent (drawings connect to it); `name` is the
  displayed designation and can change freely. `dir` is the lead direction (`l`, `r`, `u`, `d`).
* Pin `show` (default `true`) controls whether the designation is drawn when the project setting
  *Show terminal designations on all symbols* is on; with `false` the pin is never numbered automatically.
  Designations are not part of the symbol artwork: they are drawn once by the renderer, so they follow the
  project setting exactly like built-in symbols, and a designation typed for a placed component always shows.
* Pin `type` (port type) is one of `elec.passive`, `elec.input`, `elec.output`, `elec.bidir`, `elec.power`,
  `elec.ground`, `hyd.pressure`, `hyd.tank`, `hyd.work`, `hyd.pilot`, `hyd.drain`, `pneu.supply`,
  `pneu.work`, `pneu.exhaust`, `pneu.pilot`, `any`, or empty (derived from the category). The part before
  the dot is the domain used by Check Drawing.
* Add the tag `terminal` to make a terminal-block symbol (numbered per strip, X1:1, X1:2 …).
* Optional `derived_from` (`{"id": …, "name": …, "revision": …}`, strings) records the symbol a copy was made
  from in the symbol editor (*Edit a copy…* / *Open existing symbol*, *Save as new symbol…*). It is informational
  only; older versions ignore it. A copy keeps the source's connection-point ids (for built-in symbols, the
  terminal names such as `1`, `A1`, `P`), so it connects the same way and can replace the original on a drawing
  without losing wires. Copies can also be made of a `.osym` file (*Edit a copy of a symbol file…*); its
  `derived_from` names the file's symbol.
* Making a copy never alters geometry silently: every primitive and connection point of the copy is compared
  with the source (`symbols/explode.py`, `conversion_losses`), and anything the format above cannot hold
  exactly is reported as an error instead.

## A library package: `.osymlib` (version 1)

A ZIP archive:

```
mimetype         "application/x-openschematix-library" (stored, first member)
manifest.json
symbols/0001.osym …
```

```json
{"format": "OpenSchematix Symbol Library", "version": 1, "name": "Sensors", "description": "…",
 "author": "…", "created": "2026-10-31T10:00:00", "app": "OpenSchematix 1.0.1",
 "folders": ["Inductive", "Inductive/M12"],
 "symbols": [{"id": "user:…", "name": "…", "revision": 3, "folder": "Inductive/M12",
              "file": "symbols/0001.osym"}]}
```

Folder paths are relative to the exported folder and use `/`. Members with absolute paths, drive letters
or `..` are rejected. Packages with a higher `version` are refused with a message.

### Importing

The import dialog shows every symbol, its folder, its revision and whether a symbol with the same `id`
already exists. You choose:

* **Separate library**: a new top-level library named after the package (a number is added if the name
  is taken), or **Merge** into an existing library or folder (folders with the same name are merged).
* For existing symbols: **keep both** (the incoming symbol gets a new id), **replace mine**, or **skip**.

## Where user libraries are stored

`<config folder>/libraries/<Library>/<folder>/…/<symbol>.osym`, where the config folder is
`%APPDATA%\OpenSchematix` on Windows and `~/.config/openschematix` on Linux. The folders can be backed up
or synchronised like any other files.
