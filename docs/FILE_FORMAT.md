# The `.schematix` project format (version 1)

A `.schematix` file is a ZIP archive. All text members are UTF-8 JSON. Member names are relative paths
with `/` separators and never contain `..` or drive letters, so a project is independent of the computer
it was made on. Readers must ignore members they do not know.

```
mimetype                          "application/x-openschematix-project" (stored uncompressed, first member)
manifest.json                     container information
project.json                      project metadata, settings, layers, sheet order
sheets/<sheet uid>.json           one document per sheet
symbols/<nnnn>.osym               custom symbols used by the project (same format as library symbols)
revisions/index.json              revision history entries
revisions/objects/<sha256>        zlib-compressed JSON snapshots, content-addressed
```

## Versioning

`manifest.json`:

```json
{"format": "OpenSchematix Project", "version": 1, "sheet_schema": 2, "app": "OpenSchematix 1.0.1",
 "project_uid": "…", "sheets": [{"uid": "…", "name": "…", "path": "sheets/<uid>.json"}],
 "symbols": [{"id": "user:…", "path": "symbols/0001.osym"}], "revisions": "revisions/index.json"}
```

* `version` is the container layout. A reader refuses files with a higher version and tells the user to
  update; it never guesses.
* `sheet_schema` is the schema of the sheet documents (1 = legacy `.osch`, 2 = 1.0).
  New optional fields can be added within a schema; anything that changes the meaning of existing data
  increments it, with a migration step in `projectio.py`.

## project.json

```json
{"uid": "…", "created": "2026-10-31T10:00:00",
 "meta": {"title": "", "number": "", "client": "", "organisation": "", "author": "", "checked_by": "",
          "approved_by": "", "date": "", "revision": "", "description": ""},
 "settings": {"wire_numbering": {"scheme": "sequential|sheet", "prefix": "", "start": 1, "step": 1, "digits": 0},
              "show_wire_numbers": true, "show_terminal_labels": false, "xref_format": "/{sheet}.{zone}",
              "crossing_style": "bridge|gap|plain", "junction_size": "small|medium|large"},
 "layers": [{"name": "Components", "color": "", "visible": true, "locked": false, "printable": true}],
 "sheet_order": ["<uid>", "…"]}
```

## Sheets (`sheet_schema` 2)

Coordinates are drawing units of 0.25 mm, X to the right and **Y down**, origin at the top-left corner of
the sheet. The snap grid is 10 units (2.5 mm); symbol terminals always lie on it.

```json
{"uid": "3f9a…", "name": "Motor control", "next_id": 57,
 "sheet": {"size": "A3", "orientation": "landscape", "custom_w": 420, "custom_h": 297,
           "title_block": "standard|compact|iso|none", "zones": true, "scale": "1:1",
           "title": "", "drawing_number": "", "revision": "", "author": "", "checked_by": "",
           "approved_by": "", "date": "", "organisation": "", "description": "", "sheet": ""},
 "components": [{"id": 1, "symbol": "el.coil.iec", "x": 400, "y": 600, "rotation": 0, "mirror": false,
                 "designator": "K1", "label": "Conveyor", "params": {}, "text_side": "auto",
                 "props": {"manufacturer": "…", "part_number": "…", "Location": "…"},
                 "terminal_labels": {"A1": "A1"}, "layer": "Components", "locked": false, "group": "",
                 "in_bom": true}],
 "wires": [{"id": 7, "points": [[400, 200], [400, 260]], "start": [1, "A1"], "end": null, "style": "solid",
            "auto": false, "number": "12", "number_manual": false, "props": {"colour": "BU"}}],
 "shapes": [{"id": 9, "kind": "line|polyline|polygon|rect|circle|arc|text", "pts": [[0, 0], [10, 0]],
             "c": [0, 0], "r": 10, "start": 0, "extent": 90, "p": [0, 0], "s": "text", "size": 10,
             "anchor": "w", "angle": 0, "width": "normal", "dash": false, "fill": false}]}
```

Optional fields equal to their defaults are omitted when writing. Object ids are unique within a sheet and
never reused (`next_id`); together with the sheet `uid` they identify an object permanently. Wire ends
reference terminals as `[component id, terminal name]`; for custom symbols the terminal name is the pin's
permanent `id`, not its displayed name.

## Revisions

`revisions/index.json` holds `{"version": 1, "entries": [...]}`. Each entry:

```json
{"n": 3, "kind": "auto|approved", "label": "B", "description": "…", "author": "…", "approved_by": "…",
 "timestamp": "2026-10-31T10:00:00", "content": "<sha256 of the whole snapshot>",
 "head": "<sha256 of the project header>", "sheets": [["<uid>", "<name>", "<sha256>"]]}
```

Each object is the canonical JSON (sorted keys, no whitespace) of the project header or of one sheet,
compressed with zlib and named by the SHA-256 of the uncompressed JSON. Unchanged sheets are therefore
stored only once across all revisions.

## Saving

Files are written to a temporary file in the destination folder, flushed to disk, read back and verified,
and only then renamed over the existing file. An interrupted save leaves the previous file intact.

## Legacy `.osch`

A single JSON document `{"format": "OpenSchematix", "schema": 1, "sheet": {…}, "components": […],
"wires": […]}`; the same component and wire objects as above without the newer fields. OpenSchematix opens it as a
one-sheet project (title-block fields move to the project metadata) and can export a sheet as schema 2.

## Drafting line arrowheads

Drawing `Shape` records with `kind: "line"` or `kind: "polyline"` may include optional
`arrow_start` and `arrow_end` booleans, and `arrow_size` (positive finite drawing units).
The defaults are `false`, `false`, and `10` units (2.5 mm). Malformed sizes fall back to 10;
unknown fields are ignored by older readers. Arrowhead settings are omitted when no arrows
are enabled. Custom symbol `line` primitives use the same optional fields; their arrowheads
are rendered as filled vector triangles.
