"""Regression tests for bounded, transactional symbol-library imports (Issue #54)."""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from openschematix import symbols, userlib
from openschematix.symbols.custom import (MAX_SYMBOL_BYTES, MAX_SYMBOL_JSON_DEPTH,
                                          SymbolFormatError, blank_symbol, load_symbol_json,
                                          normalise)


@pytest.fixture(autouse=True)
def restore_symbols():
    before = symbols.user_symbols()
    yield
    symbols.set_user_symbols(before.values())


def symbol_doc(name: str) -> dict:
    d = blank_symbol(name)
    d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
    d["pins"] = [{"id": "1", "name": "1", "x": -20, "y": 0},
                 {"id": "2", "name": "2", "x": 20, "y": 0}]
    return normalise(d)


def package(path: Path, docs: list[dict], *, manifest=None):
    entries = [{"id": d["id"], "name": d["name"], "revision": d.get("revision", 0),
                "folder": "Sensors", "file": f"symbols/{n:04d}.osym"}
               for n, d in enumerate(docs, 1)]
    man = manifest if manifest is not None else {
        "format": userlib.LIB_FORMAT, "version": userlib.LIB_VERSION,
        "name": "Shared", "folders": ["Sensors"], "symbols": entries}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(man))
        for d, e in zip(docs, entries):
            z.writestr(e["file"], json.dumps(d))
    return path


@pytest.mark.parametrize("field,bad", [
    ("properties", []), ("properties", "x"),
    ("tags", "foo"), ("tags", 42),
    ("prims", {}), ("pins", "not an array"),
])
def test_malformed_symbol_container_raises_format_error(field, bad):
    d = symbol_doc("Bad")
    d[field] = bad
    with pytest.raises(SymbolFormatError, match=field):
        normalise(d)


def test_malformed_primitive_points_and_pin_type():
    d = symbol_doc("Bad points")
    d["prims"] = [{"k": "line", "pts": 123}]
    with pytest.raises(SymbolFormatError, match="pts"):
        normalise(d)
    d = symbol_doc("Bad pin type")
    d["pins"][0]["type"] = {"not": "hashable"}
    with pytest.raises(SymbolFormatError, match="port type"):
        normalise(d)


def test_nested_json_rejected_without_recursion_escape():
    d = symbol_doc("Nested")
    nested = {}
    d["properties"] = nested
    for _ in range(MAX_SYMBOL_JSON_DEPTH + 2):
        child = {}
        nested["next"] = child
        nested = child
    with pytest.raises(SymbolFormatError, match="nesting"):
        load_symbol_json(json.dumps(d))


def test_oversized_single_symbol_is_rejected_before_parsing(tmp_path):
    p = tmp_path / "large.osym"
    p.write_bytes(b" " * (MAX_SYMBOL_BYTES + 1))
    lib = userlib.UserLibrary(str(tmp_path / "libs"))
    with pytest.raises(SymbolFormatError, match="exceeds"):
        lib.import_symbol_file(str(p), "Home")
    lib.root = str(tmp_path)
    lib.scan()
    assert any("exceeds" in issue for issue in lib.problems)


def test_valid_package_preview_and_import_roundtrip(tmp_path):
    d1, d2 = symbol_doc("A"), symbol_doc("B")
    p = package(tmp_path / "valid.osymlib", [d1, d2])
    lib = userlib.UserLibrary(str(tmp_path / "user-libs"))
    info = userlib.read_package(str(p), lib)
    assert not info.problems and len(info.items) == 2
    result = userlib.import_package(info, lib)
    assert result == {"imported": 2, "skipped": 0, "replaced": 0, "duplicated": 0}
    assert {d1["id"], d2["id"]} == set(lib.entries)
    assert {e.doc["name"] for e in lib.entries.values()} == {"A", "B"}
    assert all(Path(e.path).is_file() for e in lib.entries.values())


@pytest.mark.parametrize("manifest", [
    [],
    {"format": userlib.LIB_FORMAT, "version": 1, "folders": {}, "symbols": []},
    {"format": userlib.LIB_FORMAT, "version": 1, "folders": [], "symbols": {}},
])
def test_malformed_package_manifest_is_controlled_error(tmp_path, manifest):
    p = package(tmp_path / "bad.osymlib", [], manifest=manifest)
    with pytest.raises(ValueError, match="manifest|arrays"):
        userlib.read_package(str(p))


def test_invalid_manifest_item_is_reported_and_skipped(tmp_path):
    d = symbol_doc("Valid")
    man = {"format": userlib.LIB_FORMAT, "version": 1, "folders": [],
           "symbols": [None, {"file": "symbols/0001.osym", "folder": ""}]}
    p = package(tmp_path / "mixed.osymlib", [d], manifest=man)
    info = userlib.read_package(str(p))
    assert len(info.items) == 1
    assert any("expected an object" in problem for problem in info.problems)


def test_oversized_compressed_zip_member_does_not_expand(tmp_path):
    d = symbol_doc("A")
    man = {"format": userlib.LIB_FORMAT, "version": 1, "folders": [],
           "symbols": [{"id": d["id"], "name": "Oversize", "file": "symbols/0001.osym"}]}
    p = tmp_path / "bomb.osymlib"
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(man))
        z.writestr("symbols/0001.osym", b" " * (MAX_SYMBOL_BYTES + 1))
    info = userlib.read_package(str(p))
    assert not info.items
    assert any("exceeds" in problem for problem in info.problems)


def test_zip_duplicate_members_rejected(tmp_path):
    p = tmp_path / "duplicate.osymlib"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("manifest.json", "{}")
        z.writestr("manifest.json", "{}")
    with pytest.raises(ValueError, match="duplicate ZIP"):
        userlib.read_package(str(p))


def test_zip_entry_count_is_bounded(tmp_path):
    p = tmp_path / "many.osymlib"
    with zipfile.ZipFile(p, "w") as z:
        for n in range(userlib.MAX_PACKAGE_ENTRIES + 1):
            z.writestr(f"unused/{n}", b"")
    with pytest.raises(ValueError, match="ZIP entries"):
        userlib.read_package(str(p))


def test_malformed_symbol_member_does_not_abort_other_previews(tmp_path):
    good = symbol_doc("Valid")
    bad = symbol_doc("Malformed")
    bad["properties"] = []
    p = package(tmp_path / "partial.osymlib", [good, bad])
    info = userlib.read_package(str(p))
    assert len(info.items) == 1 and info.items[0].id == good["id"]
    assert any("properties" in problem for problem in info.problems)


def test_package_import_rolls_back_staged_write_failure(tmp_path, monkeypatch):
    old = symbol_doc("Unchanged")
    lib = userlib.UserLibrary(str(tmp_path / "user-libs"))
    existing = lib.save_symbol(old, "Original")
    before = Path(existing.path).read_bytes()
    first, second = symbol_doc("First"), symbol_doc("Second")
    info = userlib.read_package(str(package(tmp_path / "two.osymlib", [first, second])), lib)
    real_write = userlib._atomic_json
    calls = 0

    def fail_second(path, data):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected staged write failure")
        return real_write(path, data)

    monkeypatch.setattr(userlib, "_atomic_json", fail_second)
    with pytest.raises(OSError, match="injected staged write failure"):
        userlib.import_package(info, lib, mode="merge", target="Original")
    assert Path(existing.path).read_bytes() == before
    assert set(lib.entries) == {old["id"]}
    assert first["id"] not in lib.entries and second["id"] not in lib.entries
    assert sorted(os.listdir(lib.root)) == ["Original"]


def test_package_import_rolls_back_failed_directory_swap(tmp_path, monkeypatch):
    old = symbol_doc("Existing")
    lib = userlib.UserLibrary(str(tmp_path / "user-libs"))
    existing = lib.save_symbol(old, "Original")
    before = Path(existing.path).read_bytes()
    info = userlib.read_package(str(package(tmp_path / "one.osymlib", [symbol_doc("Incoming")])), lib)
    real_replace = userlib.os.replace

    def fail_swap(src, dst):
        if os.path.basename(src) == "staged":
            raise OSError("injected directory swap failure")
        return real_replace(src, dst)

    monkeypatch.setattr(userlib.os, "replace", fail_swap)
    with pytest.raises(OSError, match="injected directory swap failure"):
        userlib.import_package(info, lib, mode="merge", target="Original")
    assert Path(existing.path).read_bytes() == before
    assert set(lib.entries) == {old["id"]}


def test_package_merge_replace_keeps_identity(tmp_path):
    d = symbol_doc("Old")
    lib = userlib.UserLibrary(str(tmp_path / "user-libs"))
    lib.save_symbol(d, "Original")
    revised = dict(d, name="Updated", revision=10)
    info = userlib.read_package(str(package(tmp_path / "replacement.osymlib", [revised])), lib)
    count = userlib.import_package(info, lib, mode="merge", target="Original", on_conflict="replace")
    assert count["replaced"] == 1 and len(lib.entries) == 1
    assert lib.entries[d["id"]].name == "Updated"



def test_scan_recovers_interrupted_package_import_backup(tmp_path):
    root = tmp_path / "user-libs"
    lib = userlib.UserLibrary(str(root))
    doc = symbol_doc("Protected")
    original = lib.save_symbol(doc, "Original")
    original_name = Path(original.path).name
    original_bytes = Path(original.path).read_bytes()

    interrupted = tmp_path / ".osymlib-import-simulated"
    interrupted.mkdir()
    (interrupted / "target.txt").write_text(str(root), encoding="utf-8")
    os.replace(root, interrupted / "previous")
    assert not root.exists()

    lib.scan()
    assert root.exists()
    assert (root / "Original" / original_name).read_bytes() == original_bytes
    assert doc["id"] in lib.entries


def test_scan_does_not_restore_another_librarys_backup(tmp_path):
    root = tmp_path / "unrelated"
    interrupted = tmp_path / ".osymlib-import-other"
    backup = interrupted / "previous"
    backup.mkdir(parents=True)
    (interrupted / "target.txt").write_text(str(tmp_path / "different"), encoding="utf-8")
    lib = userlib.UserLibrary(str(root))
    lib.scan()
    assert not root.exists()
    assert backup.exists()



def test_repeated_member_references_are_not_decoded_multiple_times(tmp_path):
    d = symbol_doc("One")
    entry = {"id": d["id"], "name": d["name"], "folder": "",
             "file": "symbols/0001.osym"}
    manifest = {"format": userlib.LIB_FORMAT, "version": 1,
                "folders": [], "symbols": [entry, dict(entry)]}
    p = package(tmp_path / "repeat.osymlib", [d], manifest=manifest)
    info = userlib.read_package(str(p))
    assert len(info.items) == 1
    assert any("duplicate symbol member" in issue for issue in info.problems)


def test_excessive_zip_directory_size_rejected_before_zipfile_parse(tmp_path):
    p = tmp_path / "large-directory.osymlib"
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_STORED) as z:
        for n in range(1050):
            z.writestr(f"unused/{n:04d}-" + "x" * 520, b"")
    assert p.stat().st_size < userlib.MAX_PACKAGE_ARCHIVE_BYTES
    with pytest.raises(ValueError, match="ZIP directory"):
        userlib.read_package(str(p))



def test_excessive_manifest_folder_count_is_rejected(tmp_path):
    man = {"format": userlib.LIB_FORMAT, "version": 1,
           "folders": [f"folder-{n}" for n in range(userlib.MAX_PACKAGE_FOLDERS + 1)],
           "symbols": []}
    p = package(tmp_path / "many-folders.osymlib", [], manifest=man)
    with pytest.raises(ValueError, match="folders"):
        userlib.read_package(str(p))


@pytest.mark.parametrize("folder", [
    "../escape", "bad\\path", "x" * 81,
    "/absolute", "a/" * (userlib.MAX_PACKAGE_PATH_DEPTH + 1) + "leaf",
])
def test_unsafe_or_excessive_manifest_symbol_folder_is_skipped(tmp_path, folder):
    doc = symbol_doc("Safe")
    man = {"format": userlib.LIB_FORMAT, "version": 1, "folders": [],
           "symbols": [{"id": doc["id"], "name": doc["name"],
                        "folder": folder, "file": "symbols/0001.osym"}]}
    p = package(tmp_path / "unsafe-folder.osymlib", [doc], manifest=man)
    info = userlib.read_package(str(p))
    assert not info.items
    assert any("unsafe" in message for message in info.problems)


def test_invalid_preview_folder_is_rejected_before_import(tmp_path):
    doc = symbol_doc("Safe")
    p = package(tmp_path / "safe.osymlib", [doc])
    info = userlib.read_package(str(p))
    lib = userlib.UserLibrary(str(tmp_path / "user-libs"))
    info.items[0].folder = "../escape"
    with pytest.raises(ValueError, match="invalid symbol folder"):
        userlib.import_package(info, lib)
    assert not Path(lib.root).exists()



def test_exporter_rejects_packages_it_cannot_reimport(tmp_path, monkeypatch):
    lib = userlib.UserLibrary(str(tmp_path / "libs"))
    lib.save_symbol(symbol_doc("First"), "Engineering")
    lib.save_symbol(symbol_doc("Second"), "Engineering")
    target = tmp_path / "export.osymlib"
    monkeypatch.setattr(userlib, "MAX_PACKAGE_SYMBOLS", 1)
    with pytest.raises(ValueError, match="more than 1 symbols"):
        lib.export_package("Engineering", str(target))
    assert not target.exists()
    monkeypatch.setattr(userlib, "MAX_PACKAGE_SYMBOLS", 1000)
    monkeypatch.setattr(userlib, "MAX_PACKAGE_UNCOMPRESSED", 100)
    with pytest.raises(ValueError, match="uncompressed size limit"):
        lib.export_package("Engineering", str(target))
    assert not target.exists()


def test_exported_package_is_readable_and_imports_with_same_pin_geometry(tmp_path):
    lib = userlib.UserLibrary(str(tmp_path / "source"))
    doc = symbol_doc("Reference")
    lib.save_symbol(doc, "Engineering")
    package_path = tmp_path / "created.osymlib"
    lib.export_package("Engineering", str(package_path))
    info = userlib.read_package(str(package_path))
    assert not info.problems and len(info.items) == 1
    dest = userlib.UserLibrary(str(tmp_path / "destination"))
    counts = userlib.import_package(info, dest)
    assert counts["imported"] == 1
    assert doc["id"] in dest.entries
    assert [(p["id"], p["x"], p["y"]) for p in dest.entries[doc["id"]].doc["pins"]] == [
        (p["id"], p["x"], p["y"]) for p in doc["pins"]]



@pytest.mark.parametrize("field,value", [
    ("tags", True), ("properties", 5), ("pins", "invalid"), ("prims", {}),
])
def test_malformed_embedded_symbol_is_recovered_and_not_reembedded(tmp_path, field, value):
    """Untrusted malformed field containers must not survive recovery into a saved project."""
    import io
    from openschematix import projectio
    from openschematix.project import new_project
    from openschematix import editing

    doc = symbol_doc("Malformed embedded")
    from openschematix.symbols.custom import to_symdef
    symbols.set_user_symbols([to_symdef(doc)])
    p = new_project("Recovery")
    editing.place(p.sheets[0], doc["id"], 100, 100)
    raw = projectio.project_bytes(p)
    members = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = {n: z.read(n) for n in z.namelist()}
    embedded = next(n for n in members if n.startswith("symbols/"))
    damaged = json.loads(members[embedded])
    damaged[field] = value
    members[embedded] = json.dumps(damaged).encode("utf-8")
    path = tmp_path / "damaged.schematix"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, payload in members.items():
            z.writestr(name, payload)
    symbols.set_user_symbols([])
    loaded = projectio.open_any(str(path))
    assert loaded.recovered
    assert loaded.project.symbols == {}
    assert any("placeholders" in w for w in loaded.warnings)
    assert not loaded.project.symbols
