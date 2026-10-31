"""Customisable keyboard shortcuts.

Shortcuts are stored as readable strings ("Ctrl+Shift+S", "F8") in the
settings and converted to Tk event sequences. Plain letters are reserved for
the command line (AutoCAD style: type L, Enter for LINE), so a shortcut must
use Ctrl or Alt, or be a function / navigation key. Shortcuts are ignored
while a text field has the keyboard focus when the key is a normal text
editing key (Ctrl+C, Ctrl+V, Ctrl+A, Ctrl+X, Ctrl+Z, Delete, …), so editing
text never triggers a drawing command.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

SPECIAL = {"Delete", "Insert", "Home", "End", "Prior", "Next", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9",
           "F10", "F11", "F12"}
TEXT_EDIT_KEYS = {"Ctrl+A", "Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+Z", "Ctrl+Y", "Delete", "Home", "End",
                  "Ctrl+Shift+Z"}
DISPLAY = {"Prior": "PageUp", "Next": "PageDown", "plus": "+", "minus": "-", "equal": "=", "KP_Add": "+",
           "KP_Subtract": "-"}

# action id -> (label, default)
DEFAULT_ACTIONS = {
    "new": ("New project", "Ctrl+N"), "open": ("Open…", "Ctrl+O"), "save": ("Save", "Ctrl+S"),
    "save_as": ("Save as…", "Ctrl+Shift+S"), "export_pdf": ("Export PDF…", "Ctrl+E"), "print": ("Print…", "Ctrl+P"),
    "undo": ("Undo", "Ctrl+Z"), "redo": ("Redo", "Ctrl+Y"), "redo2": ("Redo (alternative)", "Ctrl+Shift+Z"),
    "cut": ("Cut", "Ctrl+X"), "copy": ("Copy", "Ctrl+C"), "paste": ("Paste", "Ctrl+V"),
    "duplicate": ("Duplicate", "Ctrl+D"), "select_all": ("Select all", "Ctrl+A"), "delete": ("Delete", "Delete"),
    "find": ("Search project", "Ctrl+F"), "check": ("Check drawing", "F5"), "help": ("Command help", "F1"),
    "history": ("Show command history", "F2"), "osnap": ("Object snap on/off", "F3"),
    "grid": ("Grid on/off", "F7"), "ortho": ("Ortho on/off", "F8"), "snap": ("Grid snap on/off", "F9"),
    "rotate": ("Rotate 90° clockwise", "Ctrl+R"), "rotate_ccw": ("Rotate 90° counter-clockwise", "Ctrl+Shift+R"),
    "mirror": ("Mirror", "Ctrl+M"), "zoom_extents": ("Zoom to drawing", "Home"),
    "zoom_sheet": ("Zoom to sheet", "Ctrl+Home"), "next_sheet": ("Next sheet", "Ctrl+Next"),
    "prev_sheet": ("Previous sheet", "Ctrl+Prior"), "properties": ("Properties panel", "Ctrl+1"),
    "group": ("Group", "Ctrl+G"), "ungroup": ("Ungroup", "Ctrl+Shift+G"), "bom": ("Bill of materials", "Ctrl+B"),
    "symbol_editor": ("Symbol editor", "Ctrl+Shift+E"), "preferences": ("Preferences", "Ctrl+comma"),
}
FIXED = [("Esc", "Cancel the current command / tool, clear the selection"),
         ("Enter / Space", "Run the typed command, repeat the last command, finish a wire"),
         ("Letters", "Type a command or alias into the command line"),
         ("R / M while placing", "Rotate / mirror the symbol being placed"),
         ("Space while drawing a wire", "Flip the wire bend"),
         ("Arrow keys", "Nudge the selection by one grid step"),
         ("+ / -", "Zoom in / out"), ("Mouse wheel", "Zoom at the cursor (Shift: pan sideways, Ctrl: pan up/down)"),
         ("Middle button drag", "Pan"), ("Right click", "Context menu; Enter while a command runs"),
         ("Up / Down in the command line", "Command history")]


def validate_key(k: str) -> str:
    """Return an error message, or '' if the shortcut is acceptable."""
    if not k:
        return ""
    parts = k.split("+")
    key = parts[-1]
    mods = set(parts[:-1])
    if not mods & {"Ctrl", "Alt"} and key not in SPECIAL and key not in ("PageUp", "PageDown"):
        return ("Plain keys are used to type commands. Use Ctrl, Alt or a function key "
                "(F1–F12, Delete, Home, End, PageUp/PageDown).")
    return ""


def describe_event(e) -> str:
    ks = e.keysym
    if ks in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R", "Super_L",
              "Super_R", "ISO_Level3_Shift", "Caps_Lock"):
        return ""
    mods = []
    if e.state & 0x0004:
        mods.append("Ctrl")
    if e.state & 0x0008 or e.state & 0x20000:
        mods.append("Alt")
    if e.state & 0x0001:
        mods.append("Shift")
    key = DISPLAY.get(ks, ks)
    if len(key) == 1:
        key = key.upper()
    return "+".join(mods + [key])


def to_sequences(k: str) -> list[str]:
    if not k:
        return []
    parts = k.split("+")
    key = parts[-1]
    mods = parts[:-1]
    tkmods = []
    for m in mods:
        tkmods.append({"Ctrl": "Control", "Alt": "Alt", "Shift": "Shift"}[m])
    inv = {"PageUp": "Prior", "PageDown": "Next", "+": "plus", "-": "minus", "=": "equal", ",": "comma"}
    key = inv.get(key, key)
    if len(key) == 1 and key.isalpha():
        if "Shift" in tkmods:
            others = [m for m in tkmods if m != "Shift"]
            return ["<" + "-".join(tkmods + [key.upper()]) + ">", "<" + "-".join(others + [key.upper()]) + ">"]
        return ["<" + "-".join(tkmods + [key.lower()]) + ">"]
    return ["<" + "-".join(tkmods + [key]) + ">"]


def pretty(k: str) -> str:
    return k.replace("comma", ",").replace("Next", "PageDown").replace("Prior", "PageUp")


class KeyMap:
    def __init__(self, app):
        self.app = app
        self.actions = dict(DEFAULT_ACTIONS)
        self.fixed = FIXED
        self.handlers = {}
        self.bound = []

    def current(self) -> dict:
        over = self.app.settings["shortcuts"]
        return {a: over.get(a, d) for a, (_l, d) in self.actions.items()}

    def accel(self, action: str) -> str:
        return pretty(self.current().get(action, ""))

    def save(self, keys: dict):
        over = {a: k for a, k in keys.items() if k != self.actions[a][1]}
        self.app.settings["shortcuts"] = over
        self.app.settings.save()
        self.bind_all()
        self.app.rebuild_menus()

    def register(self, action, fn):
        self.handlers[action] = fn

    def bind_all(self):
        root = self.app.root
        for seq in self.bound:
            try:
                root.unbind(seq)
            except tk.TclError:
                pass
        self.bound = []
        for action, key in self.current().items():
            fn = self.handlers.get(action)
            if not fn or not key:
                continue
            for seq in to_sequences(key):
                try:
                    root.bind(seq, self._guard(fn, key))
                    self.bound.append(seq)
                except tk.TclError:
                    pass

    def _guard(self, fn, key):
        root = self.app.root

        def handler(e):
            w = e.widget
            if isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text, tk.Spinbox, ttk.Spinbox)) and \
                    (key in TEXT_EDIT_KEYS or not key.startswith(("Ctrl", "Alt", "F"))):
                return None
            try:
                if w.winfo_toplevel() is not root:
                    return None
            except (AttributeError, tk.TclError):
                return None
            fn()
            return "break"
        return handler
