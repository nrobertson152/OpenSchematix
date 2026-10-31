"""Regression tests for settings persistence and recovery."""
import json
import os
from unittest.mock import patch

from openschematix.settings import Settings


def test_settings_missing_file_is_normal(tmp_path):
    s = Settings(str(tmp_path / "settings.json"))
    assert s.last_load_error is None
    assert s["theme"] == "modern_light"
    assert s.save() is True
    assert Settings(s.path)["theme"] == "modern_light"


def test_corrupt_settings_preserved_before_save(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{invalid json", encoding="utf-8")
    s = Settings(str(path))
    assert s.last_load_error
    assert s["theme"] == "modern_light"
    assert s.save() is True
    assert json.loads(path.read_text())["theme"] == "modern_light"
    backups = list(tmp_path.glob("settings-corrupt-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text() == "{invalid json"


def test_invalid_types_reported_without_discarding_valid_keys(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "dark", "show_grid": "yes"}))
    s = Settings(str(path))
    assert s["theme"] == "modern_dark"
    assert s["show_grid"] is True
    assert "show_grid" in s.last_load_error


def test_failed_replace_preserves_existing_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "modern_light"}')
    s = Settings(str(path))
    s["theme"] = "modern_dark"
    with patch("openschematix.settings.os.replace", side_effect=OSError("simulated disk error")):
        assert s.save() is False
    assert path.read_text() == '{"theme": "modern_light"}'
    assert not list(tmp_path.glob(".settings-*.tmp"))
    assert "simulated disk error" in s.last_save_error


def test_unwritable_config_path_returns_false(tmp_path):
    # A regular file cannot be used as a parent directory, even as root.
    parent = tmp_path / "not-a-directory"
    parent.write_text("occupied")
    s = Settings(str(parent / "settings.json"))
    assert s.save() is False
    assert parent.read_text() == "occupied"


def test_warning_callback_once_per_failure_type(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("bad json")
    s = Settings(str(path))
    seen = []
    s.set_warning_handler(lambda kind, detail: seen.append(kind))
    assert seen == ["load"]
    with patch("openschematix.settings.os.replace", side_effect=OSError("fail")):
        assert s.save() is False
        assert s.save() is False
    assert seen == ["load", "save"]


def test_corrupt_file_not_replaced_if_backup_fails(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("bad json")
    s = Settings(str(path))
    with patch("openschematix.settings.shutil.copy2", side_effect=OSError("backup denied")):
        assert s.save() is False
    assert path.read_text() == "bad json"
