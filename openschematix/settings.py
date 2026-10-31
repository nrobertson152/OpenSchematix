"""User settings stored as JSON in the platform's configuration directory:
  Windows: %APPDATA%\\OpenSchematix\\settings.json
  macOS:   ~/Library/Application Support/OpenSchematix/settings.json
  Linux:   $XDG_CONFIG_HOME/openschematix/settings.json (default ~/.config)
"""
from __future__ import annotations

import json
import os
import sys

DEFAULTS = {
    "theme": "modern_light",        # UI theme (see gui/theme.py)
    "canvas_theme": "auto",         # drawing canvas colours: auto = follow the UI theme
    "show_grid": True,
    "show_markers": True,
    "snap_grid": True,
    "osnap": True,                  # object snap for drafting tools
    "ortho": False,
    "grid_step": 10,                # snap/grid step in drawing units (0.25 mm)
    "recent_files": [],
    "last_dir": "",
    "geometry": "",
    "default_sheet": "A3",
    "autosave_minutes": 5,          # 0 = off
    "recent_symbols": [],
    "favorite_symbols": [],
    "shortcuts": {},                # command -> key sequence overrides
    "aliases": {},                  # extra command aliases
    "layout": {},                   # panel sizes / visibility
    "ui_scale": 0.0,                # 0 = automatic
    "show_command_line": True,
    "selection_filter": ["component", "wire", "shape"],
    "command_history": [],
    "recent_templates": [],
}
THEME_MIGRATION = {"light": "modern_light", "dark": "modern_dark"}
MAX_RECENT = 8


def config_dir() -> str:
    override = os.environ.get("OPENSCHEMATIX_CONFIG_DIR")
    if override:
        return override
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        return os.path.join(base, "OpenSchematix")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/OpenSchematix")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "openschematix")


class Settings:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config_dir(), "settings.json")
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for k, v in loaded.items():
                    if k in DEFAULTS and (isinstance(v, type(DEFAULTS[k])) or
                                          (isinstance(DEFAULTS[k], float) and isinstance(v, int))):
                        self.data[k] = v
                self.data["theme"] = THEME_MIGRATION.get(self.data["theme"], self.data["theme"])
        except (OSError, ValueError):
            pass  # missing or corrupt settings: fall back to defaults

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass  # settings are a convenience; never block the user

    def __getitem__(self, k):
        import copy
        v = self.data.get(k, DEFAULTS.get(k))
        return copy.copy(v) if isinstance(v, (list, dict)) else v

    def __setitem__(self, k, v):
        self.data[k] = v

    def add_recent(self, path: str):
        path = os.path.abspath(path)
        rec = [p for p in self.data.get("recent_files", []) if p != path]
        self.data["recent_files"] = [path] + rec[: MAX_RECENT - 1]
