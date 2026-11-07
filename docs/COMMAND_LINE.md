# The `openschematix-cli` command, for other programs

RevisionWorx, FieldWorx and anything else can use a project without the window, and without importing OpenSchematix:
`openschematix-cli <command> ...` prints **exactly one JSON object** on standard output, with `"ok": true` or `"ok": false`, and exits 0
or 2. It has the same shape as `revisionworx link` and `draftworx`. Nothing here needs tkinter, the network or an account.
`python -m openschematix <command> ...` does the same. The `openschematix` command itself opens the window.

A refusal changes nothing. It says why in `"error"`, written for a person, and what sort of refusal it is in `"kind"`: `bad-input`,
`not-readable`, `exists` or `error`. New fields may be added to answers at any time, so ignore fields you don't know. `api` (from
`version`) only goes up for a change that would break a program using this.

| Command | Does | Answer, besides `ok` |
|---|---|---|
| `version` | this interface's version and the program's | `api`, `version` |
| `pdf PROJECT OUTPUT.pdf [--sheet N ...] [--revision-code NUMBER@REVISION] [--overwrite]` | the project's sheets (all, or those named by number or name) as one PDF, exactly as *Export PDF* makes it | `path`, `sheets` (`number`, `name`), `missing` (characters the PDF can't show, printed as `?`), `revision_code` (what its QR codes hold, or `""`), `warnings` |
| `components PROJECT [--sheet N ...] [--include-excluded]` | the components drawn, and the bill of materials | `title`, `number`, `sheets`, `components` (`designator`, `label`, `sheet`, `sheet_name`, `zone`, `symbol`, `symbol_name`, `description`, `manufacturer`, `part_number`, `rating`, `part`), `bom` (`item`, `quantity`, `designators`, `description`, `manufacturer`, `part_number`, `rating`, `symbol`, `sheets`), `warnings` |

**Components.** Every component drawn on the sheets asked for, ordered by designator. `zone` is its grid reference on the frame (`C4`), or
`""` on a sheet without zones. `part` says whether it's something bought: a ground mark or a sheet connector is drawn, not bought. The
`bom` is the bill of materials, built the same way as the *Bill of materials* report and the BOM a check-in takes along. A device drawn
in several places, such as a coil and its contacts, is one line there.

**Revision codes.** `--revision-code E-100@B` puts FieldWorx's revision label, `FWX:R:E-100@B`, on every sheet as a QR code. Someone
scanning a paper copy with FieldWorx is told whether it's still the released revision. The number and revision are RevisionWorx's:
the document the project file is, and its revision. They aren't the title block's drawing number or revision fields, which can say
anything.

- The code goes in the drawing area's lower right corner, just above the revision table and title block. It is 20 mm square, with
  the number and revision under it, and needs 20 x 23 mm clear.
- If anything is drawn there on a sheet, the command refuses and writes nothing.
- The command prints the revision it's given and doesn't check that the file is that revision. The window does check: it asks
  RevisionWorx.

To keep the PDF with its revision in RevisionWorx (RevisionWorx's `doc pdf`):

```sh
$ openschematix-cli pdf panel.schematix E-100-B.pdf --revision-code E-100@B
{"missing": [], "ok": true, "path": "E-100-B.pdf", "revision_code": "FWX:R:E-100@B", "sheets": [{"name": "Power", "number": 1}], "warnings": []}
$ revisionworx doc pdf E-100@B E-100-B.pdf --tool "openschematix-cli pdf"
```

The standalone builds (Windows installer, Linux AppImage) open the window only. The command line comes with an installation through pip.
