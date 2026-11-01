"""User symbol libraries and library packages.

Libraries live in the user's configuration folder:

    <config>/libraries/<Library name>/<folder>/<subfolder>/<symbol>.osym

A library is a top-level folder; folders may be nested freely. Each
``.osym`` file holds one custom symbol (see symbols/custom.py). The symbol's
``id`` inside the file is its identity: moving or renaming files never
changes it, so drawings keep working.

Library packages (``.osymlib``) are ZIP files used to share libraries
between users; the format is documented in docs/LIBRARY_FORMAT.md:

    mimetype        application/x-openschematix-library (stored, first)
    manifest.json   {"format": "OpenSchematix Symbol Library", "version": 1,
                     "name", "description", "author", "created", "app",
                     "folders": ["Sensors", "Sensors/Inductive", ...],
                     "symbols": [{"id", "name", "revision", "folder", "file"}]}
    symbols/0001.osym ...
All paths inside a package are relative, use "/" and contain no "..".
"""
from __future__ import annotations

import copy
import datetime as _dt
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field

from . import VERSION, symbols
from .settings import config_dir
from .symbols.custom import SYMBOL_FORMAT, SymbolFormatError, alias_problems, new_symbol_id, normalise, to_symdef

LIB_FORMAT = "OpenSchematix Symbol Library"
LIB_VERSION = 1
LIB_MIMETYPE = "application/x-openschematix-library"
SYMBOL_EXT = ".osym"
PACKAGE_EXT = ".osymlib"
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str, fallback: str = "Untitled") -> str:
    n = _BAD.sub("_", (name or "").strip()).strip(". ")
    if n.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
        n = "_" + n
    return n[:80] or fallback


def _rel_ok(p: str) -> bool:
    parts = p.replace("\\", "/").split("/")
    return bool(p) and not p.startswith("/") and ".." not in parts and ":" not in p


def _atomic_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@dataclass
class Entry:
    id: str
    path: str          # absolute file path
    folder: str        # "Library/Folder/Sub" (relative to the libraries root, "/" separated)
    doc: dict

    @property
    def name(self):
        return self.doc.get("name", "")


class UserLibrary:
    """All user libraries under one root folder."""

    def __init__(self, root: str | None = None):
        self.root = root or os.path.join(config_dir(), "libraries")
        self.entries: dict[str, Entry] = {}
        self.problems: list[str] = []

    # ---------------------------------------------------------------- scanning
    def scan(self):
        self.entries.clear()
        self.problems.clear()
        if not os.path.isdir(self.root):
            return
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames.sort()
            for fn in sorted(filenames):
                if not fn.lower().endswith(SYMBOL_EXT):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, encoding="utf-8") as f:
                        doc = normalise(json.load(f))
                except (OSError, ValueError) as e:
                    self.problems.append(f"{path}: {e}")
                    continue
                if doc["id"] in self.entries:
                    self.problems.append(f"{path}: duplicate symbol id {doc['id']} (ignored; first copy is "
                                         f"{self.entries[doc['id']].path})")
                    continue
                self.entries[doc["id"]] = Entry(doc["id"], path, self.rel(dirpath), doc)
        self.publish()

    def publish(self):
        """Register the user symbols with the symbol registry."""
        defs = []
        for e in self.entries.values():
            try:
                defs.append(to_symdef(e.doc))
            except SymbolFormatError as ex:
                self.problems.append(f"{e.path}: {ex}")
        symbols.set_user_symbols(defs)

    def rel(self, abs_dir: str) -> str:
        r = os.path.relpath(abs_dir, self.root)
        return "" if r == "." else r.replace(os.sep, "/")

    def abs(self, folder: str) -> str:
        if folder and not _rel_ok(folder):
            raise ValueError(f"invalid folder {folder!r}")
        return os.path.join(self.root, *folder.split("/")) if folder else self.root

    # ---------------------------------------------------------------- folders
    def libraries(self) -> list[str]:
        if not os.path.isdir(self.root):
            return []
        return sorted(d for d in os.listdir(self.root) if os.path.isdir(os.path.join(self.root, d)))

    def folders(self) -> list[str]:
        out = []
        if not os.path.isdir(self.root):
            return out
        for dirpath, dirnames, _f in os.walk(self.root):
            dirnames.sort()
            r = self.rel(dirpath)
            if r:
                out.append(r)
        return out

    def create_folder(self, parent: str, name: str) -> str:
        folder = f"{parent}/{safe_name(name)}" if parent else safe_name(name)
        p = self.abs(folder)
        if os.path.exists(p):
            raise FileExistsError(f"a folder named {name!r} already exists")
        os.makedirs(p)
        return folder

    def rename_folder(self, folder: str, new_name: str) -> str:
        parent = folder.rsplit("/", 1)[0] if "/" in folder else ""
        dest = f"{parent}/{safe_name(new_name)}" if parent else safe_name(new_name)
        if os.path.exists(self.abs(dest)):
            raise FileExistsError(f"{new_name!r} already exists")
        os.rename(self.abs(folder), self.abs(dest))
        self.scan()
        return dest

    def move_folder(self, folder: str, new_parent: str) -> str:
        name = folder.rsplit("/", 1)[-1]
        dest = f"{new_parent}/{name}" if new_parent else name
        if dest == folder or dest.startswith(folder + "/"):
            raise ValueError("cannot move a folder into itself")
        if os.path.exists(self.abs(dest)):
            raise FileExistsError(f"{dest!r} already exists")
        shutil.move(self.abs(folder), self.abs(dest))
        self.scan()
        return dest

    def copy_folder(self, folder: str, new_parent: str) -> str:
        """Copy a folder; the copies get new symbol ids (they are new symbols)."""
        name = folder.rsplit("/", 1)[-1]
        dest = f"{new_parent}/{name}" if new_parent else name
        n = 2
        while os.path.exists(self.abs(dest)):
            dest = f"{new_parent}/{name} ({n})" if new_parent else f"{name} ({n})"
            n += 1
        shutil.copytree(self.abs(folder), self.abs(dest))
        for dirpath, _d, files in os.walk(self.abs(dest)):
            for fn in files:
                if fn.lower().endswith(SYMBOL_EXT):
                    p = os.path.join(dirpath, fn)
                    try:
                        with open(p, encoding="utf-8") as f:
                            doc = json.load(f)
                        doc["id"] = new_symbol_id()
                        doc["revision"] = 0
                        doc.pop("aliases", None)      # aliases stay with the original
                        _atomic_json(p, doc)
                    except (OSError, ValueError):
                        pass
        self.scan()
        return dest

    def delete_folder(self, folder: str):
        if not folder:
            raise ValueError("cannot delete the library root")
        shutil.rmtree(self.abs(folder))
        self.scan()

    # ---------------------------------------------------------------- symbols
    def save_symbol(self, doc: dict, folder: str) -> Entry:
        """Create or update a symbol. Updating increments its revision; the
        id never changes, so drawings using it stay connected."""
        doc = normalise(copy.deepcopy(doc))
        problems = alias_problems(doc.get("aliases", []), doc["id"], self.alias_pairs())
        if problems:
            raise ValueError("Symbol aliases: " + "; ".join(problems) + ".")
        old = self.entries.get(doc["id"])
        doc["revision"] = (old.doc.get("revision", 0) + 1) if old else max(1, doc.get("revision", 0))
        doc["modified"] = _dt.datetime.now().isoformat(timespec="seconds")
        target_dir = self.abs(folder)
        os.makedirs(target_dir, exist_ok=True)
        if old and os.path.dirname(old.path) == target_dir:
            path = old.path
            want = os.path.join(target_dir, safe_name(doc["name"]) + SYMBOL_EXT)
            if os.path.basename(want) != os.path.basename(path) and not os.path.exists(want):
                path = want
        else:
            path = self._free_path(target_dir, doc["name"])
        _atomic_json(path, doc)
        if old and os.path.abspath(old.path) != os.path.abspath(path):
            try:
                os.unlink(old.path)
            except OSError:
                pass
        self.scan()
        return self.entries[doc["id"]]

    def alias_pairs(self) -> list[tuple[str, tuple, str]]:
        """(id, aliases, name) of the built-in symbols and of every library symbol (see alias_problems)."""
        return symbols.alias_pairs(symbols.builtin_symbols()) + \
            [(sid, tuple(e.doc.get("aliases", ())), e.doc.get("name", "")) for sid, e in self.entries.items()]

    def _free_path(self, d: str, name: str) -> str:
        base = safe_name(name)
        p = os.path.join(d, base + SYMBOL_EXT)
        n = 2
        while os.path.exists(p):
            p = os.path.join(d, f"{base} ({n}){SYMBOL_EXT}")
            n += 1
        return p

    def move_symbol(self, sid: str, folder: str):
        e = self.entries[sid]
        d = self.abs(folder)
        os.makedirs(d, exist_ok=True)
        dest = self._free_path(d, e.name)
        shutil.move(e.path, dest)
        self.scan()

    def copy_symbol(self, sid: str, folder: str) -> Entry:
        e = self.entries[sid]
        doc = copy.deepcopy(e.doc)
        doc["id"] = new_symbol_id()
        doc["revision"] = 0
        doc.pop("aliases", None)              # aliases stay with the original
        if os.path.abspath(self.abs(folder)) == os.path.dirname(os.path.abspath(e.path)):
            doc["name"] = doc["name"] + " (copy)"
        return self.save_symbol(doc, folder)

    def rename_symbol(self, sid: str, name: str) -> Entry:
        e = self.entries[sid]
        doc = copy.deepcopy(e.doc)
        doc["name"] = name.strip() or doc["name"]
        return self.save_symbol(doc, e.folder)

    def delete_symbol(self, sid: str):
        e = self.entries.pop(sid)
        os.unlink(e.path)
        self.scan()

    def set_tags(self, sid: str, tags: list, category: str | None = None):
        e = self.entries[sid]
        doc = copy.deepcopy(e.doc)
        doc["tags"] = [t.strip() for t in tags if t.strip()]
        if category:
            doc["category"] = category
        return self.save_symbol(doc, e.folder)

    def in_folder(self, folder: str, recursive: bool = False) -> list[Entry]:
        out = []
        for e in self.entries.values():
            if e.folder == folder or (recursive and (folder == "" or e.folder.startswith(folder + "/"))):
                out.append(e)
        return sorted(out, key=lambda e: e.name.lower())

    def search(self, query: str, folder: str | None = None, category: str | None = None, tag: str | None = None):
        words = query.lower().split()
        out = []
        for e in self.entries.values():
            d = e.doc
            if folder is not None and not (e.folder == folder or e.folder.startswith(folder + "/")):
                continue
            if category and d.get("category") != category:
                continue
            if tag and tag.lower() not in (t.lower() for t in d.get("tags", [])):
                continue
            blob = " ".join([d.get("name", ""), d.get("description", ""), d.get("category", ""), d.get("group", ""),
                             d.get("prefix", ""), e.folder, *d.get("tags", []), *d.get("aliases", [])]).lower()
            if all(w in blob for w in words):
                out.append(e)
        return sorted(out, key=lambda e: e.name.lower())

    def all_tags(self) -> list[str]:
        return sorted({t for e in self.entries.values() for t in e.doc.get("tags", [])}, key=str.lower)

    # ---------------------------------------------------------------- single symbols
    def export_symbol(self, sid: str, path: str):
        doc = copy.deepcopy(self.entries[sid].doc)
        _atomic_json(path, doc)

    def import_symbol_file(self, path: str, folder: str, on_conflict: str = "duplicate") -> Entry | None:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return self.import_symbol_doc(data, folder, on_conflict)

    def import_symbol_doc(self, data: dict, folder: str, on_conflict: str = "duplicate") -> Entry | None:
        """on_conflict (same id already present): skip | replace | duplicate."""
        doc = normalise(data)
        if doc["id"] in self.entries:
            if on_conflict == "skip":
                return None
            if on_conflict == "duplicate":
                doc["id"] = new_symbol_id()
                doc["revision"] = 0
                doc.pop("aliases", None)      # aliases stay with the original
            elif on_conflict == "replace":
                old = self.entries[doc["id"]]
                doc["revision"] = max(doc.get("revision", 0), old.doc.get("revision", 0))
                # save_symbol writes the replacement atomically and only then
                # removes the previous file, preserving it on write failure.
        # an imported symbol must not take identifiers already in use: keep only its unambiguous aliases
        if doc.get("aliases"):
            pairs = self.alias_pairs()
            keep = [a for a in doc["aliases"] if not alias_problems([a], doc["id"], pairs)]
            if keep:
                doc["aliases"] = keep
            else:
                doc.pop("aliases")
        return self.save_symbol(doc, folder)

    # ---------------------------------------------------------------- packages
    def export_package(self, folder: str, path: str, description: str = "", author: str = ""):
        """Export a library (or any folder) with its subfolders as .osymlib."""
        name = folder.rsplit("/", 1)[-1] if folder else "Library"
        prefix = folder + "/" if folder else ""
        folders = [f[len(prefix):] for f in self.folders() if f.startswith(prefix)]
        syms = self.in_folder(folder, recursive=True)
        manifest = {"format": LIB_FORMAT, "version": LIB_VERSION, "name": name, "description": description,
                    "author": author, "created": _dt.datetime.now().isoformat(timespec="seconds"),
                    "app": f"OpenSchematix {VERSION}", "folders": folders, "symbols": []}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(zipfile.ZipInfo("mimetype"), LIB_MIMETYPE, compress_type=zipfile.ZIP_STORED)
            for i, e in enumerate(syms, 1):
                f = f"symbols/{i:04d}{SYMBOL_EXT}"
                rel = e.folder[len(prefix):] if e.folder.startswith(prefix) else ""
                if e.folder == folder:
                    rel = ""
                manifest["symbols"].append({"id": e.id, "name": e.name, "revision": e.doc.get("revision", 0),
                                            "folder": rel, "file": f})
                z.writestr(f, json.dumps(e.doc, indent=1, ensure_ascii=False))
            z.writestr("manifest.json", json.dumps(manifest, indent=1, ensure_ascii=False))
        from .projectio import atomic_write_bytes
        atomic_write_bytes(path, buf.getvalue())
        return manifest


@dataclass
class PackageItem:
    id: str
    name: str
    folder: str
    doc: dict
    revision: int = 0
    conflict: str = ""        # "" | "same id" | "same id (older here)" | "same id (newer here)"


@dataclass
class PackageInfo:
    path: str
    name: str
    description: str
    author: str
    created: str
    folders: list = field(default_factory=list)
    items: list = field(default_factory=list)
    problems: list = field(default_factory=list)

    @property
    def conflicts(self):
        return [i for i in self.items if i.conflict]


def read_package(path: str, lib: UserLibrary | None = None) -> PackageInfo:
    """Read and validate a package without importing it (for the preview)."""
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise ValueError("not a valid symbol library package") from e
    with z:
        try:
            man = json.loads(z.read("manifest.json").decode("utf-8"))
        except (KeyError, ValueError) as e:
            raise ValueError("the package has no readable manifest") from e
        if man.get("format") != LIB_FORMAT:
            raise ValueError("not an OpenSchematix symbol library")
        if not isinstance(man.get("version"), int) or man["version"] > LIB_VERSION:
            raise ValueError(f"library format version {man.get('version')} is newer than supported")
        info = PackageInfo(path, str(man.get("name") or "Imported library"), str(man.get("description", "")),
                           str(man.get("author", "")), str(man.get("created", "")))
        info.folders = [f for f in man.get("folders", []) if isinstance(f, str) and _rel_ok(f)]
        for s in man.get("symbols", []):
            f = s.get("file", "")
            folder = s.get("folder", "") or ""
            if not _rel_ok(f) or (folder and not _rel_ok(folder)):
                info.problems.append(f"unsafe path skipped: {f!r}")
                continue
            try:
                doc = normalise(json.loads(z.read(f).decode("utf-8")))
            except (KeyError, ValueError) as e:
                info.problems.append(f"{s.get('name', f)}: {e}")
                continue
            it = PackageItem(doc["id"], doc["name"], folder, doc, doc.get("revision", 0))
            if lib is not None and doc["id"] in lib.entries:
                mine = lib.entries[doc["id"]].doc.get("revision", 0)
                it.conflict = "same id" + (" (newer in package)" if it.revision > mine else
                                           " (older in package)" if it.revision < mine else "")
            if symbols.is_builtin(doc["id"]):
                info.problems.append(f"{doc['name']}: uses a built-in id (skipped)")
                continue
            info.items.append(it)
    return info


def import_package(info: PackageInfo, lib: UserLibrary, mode: str = "separate", target: str = "",
                   on_conflict: str = "duplicate", selected_ids=None) -> dict:
    """Import a previewed package.

    mode "separate": create a new top-level library named after the package
                     (made unique), keeping the package's folder structure.
    mode "merge":    import into folder `target` (an existing library or
                     folder), merging folders with the same names.
    on_conflict for symbols whose id already exists: skip | replace | duplicate
    (duplicate = import as a new symbol with a new id).
    Returns counts {"imported", "skipped", "replaced", "duplicated"}."""
    if mode == "separate":
        base = safe_name(info.name, "Imported library")
        name, n = base, 2
        while os.path.exists(lib.abs(name)):
            name = f"{base} ({n})"
            n += 1
        os.makedirs(lib.abs(name))
        root = name
    else:
        root = target
        os.makedirs(lib.abs(root), exist_ok=True)
    for f in info.folders:
        os.makedirs(lib.abs(f"{root}/{f}" if root else f), exist_ok=True)
    counts = {"imported": 0, "skipped": 0, "replaced": 0, "duplicated": 0}
    for it in info.items:
        if selected_ids is not None and it.id not in selected_ids:
            continue
        folder = "/".join(x for x in (root, it.folder) if x)
        exists = it.id in lib.entries
        res = lib.import_symbol_doc(it.doc, folder, on_conflict if exists else "replace")
        if res is None:
            counts["skipped"] += 1
        elif exists and on_conflict == "replace":
            counts["replaced"] += 1
        elif exists:
            counts["duplicated"] += 1
        else:
            counts["imported"] += 1
    lib.scan()
    return counts


# ================================================================ favourites / recent (in settings)
MAX_RECENT_SYMBOLS = 16


def add_recent_symbol(settings, sid: str):
    rec = [s for s in settings["recent_symbols"] if s != sid]
    settings["recent_symbols"] = [sid] + rec[: MAX_RECENT_SYMBOLS - 1]


def toggle_favorite(settings, sid: str) -> bool:
    fav = list(settings["favorite_symbols"])
    if sid in fav:
        fav.remove(sid)
        settings["favorite_symbols"] = fav
        return False
    settings["favorite_symbols"] = fav + [sid]
    return True


__all__ = ["UserLibrary", "read_package", "import_package", "SYMBOL_FORMAT", "PACKAGE_EXT", "SYMBOL_EXT"]
