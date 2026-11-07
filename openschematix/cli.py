"""``openschematix-cli``: OpenSchematix for other programs, without the window (docs/COMMAND_LINE.md).

    openschematix-cli version
    openschematix-cli pdf PROJECT OUTPUT.pdf [--sheet N ...] [--overwrite]
    openschematix-cli components PROJECT [--sheet N ...] [--include-excluded]

Each prints exactly one JSON object on standard output, with ``"ok": true`` or ``"ok": false``, and exits 0 or 2, the same shape as
``revisionworx link`` and ``draftworx``. A refusal changes nothing and says why in ``"error"``, written for a person, and what sort of
refusal it is in ``"kind"``: ``bad-input``, ``not-readable``, ``exists`` or ``error``. New fields may be added to answers; ``api`` only
goes up for a change that would break a program using this. Nothing here uses tkinter, the network or an account.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

API_VERSION = 1

COMMANDS = {
    "version": "this interface's version and the program's",
    "pdf": "the project's sheets as a PDF, as Export PDF makes it",
    "components": "the components drawn, with their sheet and zone, and the bill of materials",
}


class Refused(Exception):
    def __init__(self, message: str, kind: str = "bad-input"):
        super().__init__(message)
        self.kind = kind


def _answer(obj: dict) -> int:
    # ASCII with \u escapes: the same JSON to any reader, whatever code page a Windows pipe or console has
    sys.stdout.write(json.dumps(obj, ensure_ascii=True, sort_keys=True) + "\n")
    sys.stdout.flush()
    return 0 if obj.get("ok") else 2


def _open(path: str):
    """The project in a .schematix file (or a legacy .osch drawing), never changing it."""
    from . import api
    if not os.path.isfile(path):
        raise Refused(f"{os.path.basename(path) or path} isn't there.", "not-readable")
    try:
        return api.open_project(path)
    except api.ApiError as exc:
        raise Refused(str(exc), "not-readable") from exc


def _sheets(project, wanted: list) -> list:
    """The sheets asked for by number or name, in project order; all when none are."""
    sheets = project._use().sheets
    if not wanted:
        return list(sheets)
    chosen = set()
    for w in wanted:
        hits = [d for i, d in enumerate(sheets, 1) if w == str(i) or w.casefold() == d.name.casefold()]
        if not hits:
            raise Refused(f"There's no sheet {w!r}. The sheets are: "
                          + ", ".join(f"{i} {d.name}" for i, d in enumerate(sheets, 1)) + ".")
        chosen.update(d.uid for d in hits)
    return [d for d in sheets if d.uid in chosen]


def _pdf(args) -> dict:
    from . import export
    if not args.output.casefold().endswith(".pdf"):
        raise Refused("The PDF's name has to end in .pdf.")
    project = _open(args.project)
    docs = _sheets(project, args.sheet)
    if os.path.exists(args.output) and not args.overwrite:
        raise Refused(f"{os.path.basename(args.output)} is already there. Add --overwrite to replace it.", "exists")
    internal = project._use()
    try:
        missing = export.export_project_pdf(internal, args.output, {d.uid for d in docs})
    except OSError as exc:
        raise Refused(f"{args.output} couldn't be written: {exc}", "error") from exc
    return {"ok": True, "path": args.output,
            "sheets": [{"number": internal.sheet_number(d), "name": d.name} for d in docs],
            "missing": missing, "warnings": list(project.warnings)}


def _components(args) -> dict:
    from . import bom, symbols, titleblock
    project = _open(args.project)
    internal = project._use()
    docs = _sheets(project, args.sheet)
    out = []
    with symbols.project_scope(internal):
        for d in docs:
            for c in sorted(d.components.values(), key=lambda c: (bom.natural_key(c.designator), c.id)):
                sd = symbols.get(c.symbol)
                props = c.props
                out.append({"designator": c.designator, "label": c.label, "sheet": internal.sheet_number(d), "sheet_name": d.name,
                            "zone": titleblock.zone_of(d, (c.x, c.y)), "symbol": c.symbol, "symbol_name": sd.name if sd else "",
                            "description": props.get("description", ""), "manufacturer": props.get("manufacturer", ""),
                            "part_number": props.get("part_number", ""), "rating": props.get("rating", ""),
                            "part": bom.purchasable(c)})
        lines = bom.generate(internal, {d.uid for d in docs}, include_excluded=args.include_excluded)
    meta = internal.meta
    return {"ok": True, "path": args.project, "title": meta.get("title", ""), "number": meta.get("number", ""),
            "sheets": [{"number": internal.sheet_number(d), "name": d.name} for d in docs], "components": out,
            "bom": [{"item": ln.item, "quantity": ln.quantity, "designators": list(ln.designators),
                     "description": ln.description, "manufacturer": ln.manufacturer, "part_number": ln.part_number,
                     "rating": ln.rating, "symbol": ln.symbol, "sheets": list(ln.sheets)} for ln in lines],
            "warnings": list(project.warnings)}


def _parser(name: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"openschematix-cli {name}", description=COMMANDS[name])
    if name in ("pdf", "components"):
        p.add_argument("project", help="a .schematix project (or a legacy .osch drawing)")
    if name == "pdf":
        p.add_argument("output", help="the PDF to write")
        p.add_argument("--overwrite", action="store_true", help="replace OUTPUT if it's there")
    if name in ("pdf", "components"):
        p.add_argument("--sheet", action="append", default=[], metavar="N", help="just this sheet, by number or name (repeatable)")
    if name == "components":
        p.add_argument("--include-excluded", action="store_true", help="the bill of materials with parts left out of it too")
    return p


def main(argv: list | None = None) -> int:
    given = sys.argv[1:] if argv is None else list(argv)
    if not given or given[0] not in COMMANDS:
        print("openschematix-cli <command> ...: " + "; ".join(f"{k}: {v}" for k, v in COMMANDS.items())
              + ". Each prints one JSON object.", file=sys.stderr)
        return 2
    name = given[0]
    if name == "version":
        from . import VERSION
        return _answer({"ok": True, "api": API_VERSION, "version": VERSION})
    try:
        args = _parser(name).parse_args(given[1:])
    except SystemExit as exc:
        if exc.code == 0:
            return 0                    # --help
        return _answer({"ok": False, "error": f"Those aren't arguments openschematix-cli {name} takes. Try --help.",
                        "kind": "bad-input"})
    try:
        return _answer((_pdf if name == "pdf" else _components)(args))
    except Refused as exc:
        return _answer({"ok": False, "error": str(exc), "kind": exc.kind})
    except Exception as exc:  # noqa: BLE001 - another program reads this: never a traceback instead of an answer
        return _answer({"ok": False, "error": f"Something went wrong: {type(exc).__name__}: {exc}", "kind": "error"})


if __name__ == "__main__":
    sys.exit(main())
