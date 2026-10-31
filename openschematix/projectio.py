"""Reading and writing ``.schematix`` project files, and opening older
documents (including legacy single-sheet drawings).

The ``.schematix`` container is a ZIP archive (see docs/FILE_FORMAT.md):

    mimetype                         application/x-openschematix-project (stored, first)
    manifest.json                    container format/version, app version, sheet list
    project.json                     metadata, settings, layers, sheet order
    sheets/<sheet uid>.json          one JSON document per sheet
    symbols/<n>.osym                 embedded custom symbol definitions
    revisions/index.json             revision history entries
    revisions/objects/<sha256>       content-addressed, zlib-compressed snapshots

All member paths are relative and machine-independent. Files are written to
a temporary file in the destination folder, flushed to disk and then
atomically renamed over the destination, so an interrupted save never
damages the previous file.
"""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import dataclass, field

from . import FILE_FORMAT, VERSION, fileio
from .model import SHEET_SCHEMA, Document
from .project import Project, project_from_document
from .revisions import RevisionStore

PROJECT_FORMAT = "OpenSchematix Project"
PROJECT_VERSION = 1            # container layout version
PROJECT_EXTENSION = ".schematix"
MIMETYPE = "application/x-openschematix-project"
MAX_MEMBER_BYTES = 200 * 1024 * 1024


class ProjectFormatError(ValueError):
    pass


@dataclass
class OpenResult:
    project: Project
    migrated: bool = False          # converted from an older format: must be saved under a new name
    source_format: str = "schematix"
    warnings: list = field(default_factory=list)


# ================================================================ writing
def project_bytes(project: Project) -> bytes:
    """Serialise a project to .schematix bytes."""
    import io
    buf = io.BytesIO()
    write_zip(project, buf)
    return buf.getvalue()


def write_zip(project: Project, fileobj):
    d = project.to_dict()
    sheets = d.pop("sheets")
    symbols = d.pop("symbols")
    manifest = {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "sheet_schema": SHEET_SCHEMA,
        "app": f"OpenSchematix {VERSION}",
        "project_uid": project.uid,
        "sheets": [{"uid": s["uid"], "name": s["name"], "path": f"sheets/{s['uid']}.json"} for s in sheets],
        "symbols": [],
        "revisions": "revisions/index.json" if project.revisions is not None else None,
    }
    with zipfile.ZipFile(fileobj, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, compress_type=zipfile.ZIP_STORED)
        for i, (sid, sdoc) in enumerate(sorted(symbols.items())):
            path = f"symbols/{i + 1:04d}.osym"
            manifest["symbols"].append({"id": sid, "path": path})
            z.writestr(path, json.dumps(sdoc, indent=1, ensure_ascii=False))
        z.writestr("manifest.json", json.dumps(manifest, indent=1, ensure_ascii=False))
        d["sheet_order"] = [s["uid"] for s in sheets]
        z.writestr("project.json", json.dumps(d, indent=1, ensure_ascii=False))
        for s in sheets:
            z.writestr(f"sheets/{s['uid']}.json", json.dumps(s, indent=1, ensure_ascii=False))
        if project.revisions is not None:
            st = project.revisions
            z.writestr("revisions/index.json", json.dumps(st.index(), indent=1, ensure_ascii=False))
            for h, blob in st.objects.items():
                z.writestr(zipfile.ZipInfo(f"revisions/objects/{h}"), blob, compress_type=zipfile.ZIP_STORED)


def atomic_write_bytes(path: str, data: bytes):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".schematix-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_project(project: Project, path: str, snapshot: bool = True):
    """Save atomically. With `snapshot`, an automatic revision snapshot is
    recorded first if the content changed since the last snapshot."""
    if project.revisions is None:
        project.revisions = RevisionStore()
    if snapshot:
        project.revisions.create(project, "auto", description="Saved")
    data = project_bytes(project)
    # verify before replacing the user's file: the bytes must load back
    _verify(data)
    atomic_write_bytes(path, data)


def _verify(data: bytes):
    import io
    try:
        read_zip(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001 - never replace a good file with a bad one
        raise OSError(f"internal error: the project could not be verified before saving ({e})") from e


# ================================================================ reading
def _read_json(z: zipfile.ZipFile, name: str):
    try:
        info = z.getinfo(name)
    except KeyError as e:
        raise ProjectFormatError(f"the project file is missing '{name}'") from e
    if info.file_size > MAX_MEMBER_BYTES:
        raise ProjectFormatError(f"'{name}' is unreasonably large")
    try:
        return json.loads(z.read(name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProjectFormatError(f"'{name}' is damaged: {e}") from e


def read_zip(fileobj) -> OpenResult:
    try:
        z = zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile as e:
        raise ProjectFormatError("the file is not a valid OpenSchematix project (damaged ZIP container)") from e
    with z:
        manifest = _read_json(z, "manifest.json")
        if not isinstance(manifest, dict) or manifest.get("format") != PROJECT_FORMAT:
            raise ProjectFormatError("the file is not an OpenSchematix project")
        ver = manifest.get("version")
        if not isinstance(ver, int) or ver > PROJECT_VERSION:
            raise ProjectFormatError(f"this project was written by a newer version of OpenSchematix "
                                     f"(container version {ver}); please update the program")
        schema = manifest.get("sheet_schema", SHEET_SCHEMA)
        if not isinstance(schema, int) or schema > SHEET_SCHEMA:
            raise ProjectFormatError(f"this project uses sheet schema {schema}, newer than supported ({SHEET_SCHEMA})")
        head = _read_json(z, "project.json")
        warnings = []
        sheets = []
        for entry in manifest.get("sheets", []):
            path = entry.get("path", "")
            if not path.startswith("sheets/") or ".." in path:
                raise ProjectFormatError(f"invalid sheet path {path!r}")
            sheets.append(_read_json(z, path))
        order = head.pop("sheet_order", None)
        if order:
            pos = {u: i for i, u in enumerate(order)}
            sheets.sort(key=lambda s: pos.get(s.get("uid"), len(pos)))
        head["sheets"] = sheets
        symbols = {}
        for entry in manifest.get("symbols", []):
            path = entry.get("path", "")
            if not path.startswith("symbols/") or ".." in path:
                continue
            try:
                doc = _read_json(z, path)
                symbols[str(doc.get("id", entry.get("id")))] = doc
            except ProjectFormatError as e:
                warnings.append(str(e))
        head["symbols"] = symbols
        try:
            project = Project.from_dict(head)
        except (KeyError, TypeError, ValueError) as e:
            raise ProjectFormatError(f"the project is damaged or incomplete: {e}") from e
        store = RevisionStore()
        if manifest.get("revisions"):
            try:
                index = _read_json(z, "revisions/index.json")
                objects = {n.rsplit("/", 1)[1]: z.read(n) for n in z.namelist()
                           if n.startswith("revisions/objects/") and not n.endswith("/")}
                store = RevisionStore.from_parts(index, objects)
            except (ProjectFormatError, KeyError, zipfile.BadZipFile) as e:
                warnings.append(f"The revision history could not be read and was reset ({e}).")
        project.revisions = store
    return OpenResult(project, warnings=warnings)


def open_any(path: str) -> OpenResult:
    """Open a .schematix project, or convert a legacy drawing into a
    new (unsaved) one-sheet project. The original file is never modified."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head.startswith(b"PK"):
        with open(path, "rb") as f:
            res = read_zip(f)
        warnings = res.project.activate_symbols()
        res.warnings += warnings
        _check_unknown(res)
        return res
    try:
        legacy = fileio.load(path)
    except fileio.FileFormatError as e:
        raise ProjectFormatError(str(e)) from e
    name = os.path.splitext(os.path.basename(path))[0]
    project = project_from_document(legacy.document, title=legacy.document.sheet.title or name)
    project.revisions = RevisionStore()
    project.activate_symbols()
    fmt = "legacy" if legacy.migrated else "osch"
    warnings = list(legacy.warnings)
    warnings.insert(0, f"Converted from an older drawing format. "
                       f"The original file is unchanged; save the project as a new {PROJECT_EXTENSION} file.")
    return OpenResult(project, migrated=True, source_format=fmt, warnings=warnings)


def _check_unknown(res: OpenResult):
    from . import symbols
    unknown = sorted({c.symbol for _s, c in res.project.all_components() if symbols.get(c.symbol) is None})
    if unknown:
        res.warnings.append("Unknown symbols shown as placeholders: " + ", ".join(unknown))


def suggested_project_path(source_path: str) -> str:
    base = os.path.splitext(source_path)[0]
    cand = base + PROJECT_EXTENSION
    n = 2
    while os.path.exists(cand):
        cand = f"{base} ({n}){PROJECT_EXTENSION}"
        n += 1
    return cand


def export_sheet_osch(doc: Document, path: str):
    """Export one sheet as a standalone .osch drawing (schema 2)."""
    fileio.save(doc, path)


__all__ = ["PROJECT_EXTENSION", "ProjectFormatError", "OpenResult", "save_project", "open_any", "read_zip",
           "project_bytes", "FILE_FORMAT"]
