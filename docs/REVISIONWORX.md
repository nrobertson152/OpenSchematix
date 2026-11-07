# RevisionWorx

[RevisionWorx](https://github.com/nrobertson152/RevisionWorx) is the family's revision control program: offline, free, and separate.
When it's installed, OpenSchematix works with it. Without it, nothing here shows and nothing changes.

## What you see

For a project file RevisionWorx controls, the status bar shows RevisionWorx's own line for it, such as
*E-100 rev B · Released · checked out by you*, and one button for the next step:

- **Check out** when it's available, so it's yours to change.
- **Check in…** when it's checked out to you, has been changed, or has unsaved changes. It asks what changed (RevisionWorx keeps
  that with the revision), saves the project first, checks it out if nobody has it, and checks it in.

Someone else's check-out shows who has it, and no button. Hovering over the line says what's true and what to do, as RevisionWorx's
own window does.

**File ▸ RevisionWorx** has the same two, and:

- **Undo check-out…**: Yes puts the latest revision back in the file and reopens it, losing what was changed since; No keeps the file
  as it is.
- **Add to RevisionWorx…**: puts a project that isn't controlled yet into a RevisionWorx project, with a number and title (suggested
  from the project's properties). A file outside that project's folder is copied into it, and OpenSchematix carries on with the copy.
- **Show in RevisionWorx** opens it there.

## The bill of materials

Checking in can take the project's bill of materials along, as a BOM document next to it: numbered like the schematic with `-BOM`
(`E-100-BOM`), in the RevisionWorx project's BOM folder if it has one, and naming the schematic's revision. It's written as RevisionWorx
reads a BOM (its `docs/bom`): an item for the schematic and for each part, and a line for each part with its quantity and designators.

- A part is a BOM line with a part number. Lines without one can't be ordered by number, so they're left out, and checking in says
  how many.
- Lines with the same part number, such as one written with two manufacturers' names, are one line.
- Checking in again makes a new revision of the BOM only if it changed.

[OpenMeridian](https://github.com/nrobertson152/OpenMeridian) imports a BOM from a released revision, so once the BOM is released in
RevisionWorx, the schematic's parts reach purchasing and stock there.

## Revision codes on prints

*Print* and *Export PDF* put the revision's code on every sheet when RevisionWorx says the saved project is exactly its latest revision,
with nothing changed since. The code is FieldWorx's revision label, a QR code holding `FWX:R:E-100@B`. Anyone with
[FieldWorx](https://github.com/nrobertson152/FieldWorx) on a phone can scan a paper copy and see whether it's still the released
revision, and which revision is if it isn't.

- It goes in the drawing area's lower right corner, just above the revision table and title block. It is 20 mm square, with the
  number and revision under it.
- It never covers anything. On a sheet with something drawn there, that sheet is printed without it, and the Output panel says which
  sheets.
- A project with unsaved changes, or one that differs from its latest revision, is printed without a code. The window says why:
  the print wouldn't be that revision.
- The number and revision are RevisionWorx's, not the title block's own fields.

`openschematix-cli pdf --revision-code` does the same for other programs ([COMMAND_LINE.md](COMMAND_LINE.md)).

## Someone else's working file

A project someone else has checked out is the file they're working on, so it isn't saved over: Save says who has it and offers to save
a copy. If RevisionWorx doesn't answer at that moment, what it said last counts; if it never said anything, the save goes ahead.

## How it works

Only RevisionWorx's command line is used: `revisionworx link` (its interface for other programs) for a file's status, checking in and
the projects, and `revisionworx --json doc checkout|cancel` for checking out and undoing that. RevisionWorx's rules, locks and records
apply exactly as they would by hand, and OpenSchematix never reads or writes a workspace itself.

It finds RevisionWorx as RevisionWorx's own reference client does: the `REVISIONWORX_CLI` environment variable, `revisionworx` on the
PATH, the standalone build where it installs, then the installed Python package. What RevisionWorx says is asked again when a project is
opened or saved, after checking in or out, and when you come back to the window, in the background, so a slow shared folder doesn't hold
up drawing.

## Not verified

Tested with the real RevisionWorx and OpenMeridian on one computer, on Linux and Windows in CI. Not with a workspace in a shared folder
between real computers, which RevisionWorx itself hasn't verified yet.
