"""Prevent data loss when importing a replacement custom symbol."""
from pathlib import Path

import pytest

from openschematix import userlib
from openschematix.symbols.custom import blank_symbol


def test_replacement_write_failure_keeps_original(tmp_path, monkeypatch):
    lib = userlib.UserLibrary(str(tmp_path))
    original = blank_symbol()
    original["name"] = "Original"
    entry = lib.save_symbol(original, "Library")
    old_path = Path(entry.path)
    old_contents = old_path.read_bytes()

    replacement = dict(original)
    replacement["name"] = "Replacement"

    def fail_write(*args, **kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(userlib, "_atomic_json", fail_write)
    with pytest.raises(OSError, match="simulated disk failure"):
        lib.import_symbol_doc(replacement, "Library", on_conflict="replace")

    assert old_path.read_bytes() == old_contents
    assert lib.entries[entry.id].path == str(old_path)


def test_successful_replacement_preserves_id(tmp_path):
    lib = userlib.UserLibrary(str(tmp_path))
    original = blank_symbol()
    original["name"] = "Original"
    entry = lib.save_symbol(original, "Library")
    original_id = entry.id
    original_revision = entry.doc["revision"]

    replacement = dict(original)
    replacement["name"] = "Replacement"
    result = lib.import_symbol_doc(replacement, "Library", on_conflict="replace")

    assert result.id == original_id
    assert result.name == "Replacement"
    assert result.doc["revision"] > original_revision
    assert Path(result.path).is_file()
