"""CAD-style command line with autocomplete, history and a log."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import commands as cmdparse
from . import theme as th
from .widgets import IconButton, current_theme


class CommandLine(ttk.Frame):
    MAX_HISTORY = 100

    def __init__(self, master, app):
        super().__init__(master, style="Surface.TFrame", padding=(8, 5, 8, 5))
        self.app = app
        self.history: list[str] = list(app.settings.data.get("command_history", []))[-self.MAX_HISTORY:]
        self.hpos = None
        self.last_command = ""
        self.icon = IconButton(self, "command", self.focus_entry, "Command line — type a command and press "
                                                                   "Enter (F2: command history)", size=15,
                               bg_key="surface", pad=3)
        self.icon.pack(side="left")
        self.prompt = ttk.Label(self, text="Command:", style="Prompt.TLabel")
        self.prompt.pack(side="left", padx=(4, 6))
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, style="Command.TEntry")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._enter)
        self.entry.bind("<KP_Enter>", self._enter)
        self.entry.bind("<space>", self._space)
        self.entry.bind("<Escape>", self._escape)
        self.entry.bind("<Up>", lambda e: self._hist(-1) or "break")
        self.entry.bind("<Down>", lambda e: self._hist(1) or "break")
        self.entry.bind("<Tab>", self._tab)
        self.entry.bind("<KeyRelease>", self._changed)
        self.entry.bind("<FocusOut>", lambda e: self.after(150, self._hide_popup))
        self.popup = None
        self.listbox = None
        self.suggestions = []

    # ---------------------------------------------------------------- prompt
    def set_prompt(self, text: str):
        self.prompt.configure(text=(text + " ") if text else "Command:")

    def focus_entry(self, initial: str = ""):
        self.entry.focus_set()
        if initial:
            self.entry.insert("end", initial)
            self._changed()
        self.entry.icursor("end")

    # ---------------------------------------------------------------- input
    def _enter(self, _e=None):
        if self.popup is not None and self.listbox is not None and self.listbox.curselection():
            self._accept_suggestion()
        text = self.var.get()
        self.var.set("")
        self._hide_popup()
        self.hpos = None
        self.app.execute_input(text)
        if text.strip():
            if not self.history or self.history[-1] != text.strip():
                self.history.append(text.strip())
                del self.history[:-self.MAX_HISTORY]
        return "break"

    def _space(self, _e):
        """Space acts as Enter for command names (AutoCAD); inside text and
        coordinates it is a normal space."""
        text = self.var.get()
        runner = self.app.runner
        if runner.active:
            from .interact import GetText
            if isinstance(runner.req, GetText):
                return None
            if text.strip() and any(ch.isdigit() for ch in text):
                return None
            return self._enter()
        if " " in text.strip() or self._expects_args(text):
            return None
        return self._enter()

    def _expects_args(self, text):
        name = cmdparse.resolve(text.split(" ")[0] if text else "", self.app.settings["aliases"])
        return name in ("INSERT", "SEARCH", "ZOOM", "ALIGN", "DISTRIBUTE", "EXPORT", "IMPORT", "SHEET", "THEME",
                        "LAYER", "PLOTSCALE", "TEMPLATE", "HELP", "WIRENUMBER", "PAN", "GRID", "SNAP", "ORTHO",
                        "OSNAP") and text.endswith(text.strip())

    def _escape(self, _e):
        if self.popup is not None:
            self._hide_popup()
        elif self.var.get():
            self.var.set("")
        else:
            self.app.canvas.escape()
            self.app.canvas.focus_set()
        return "break"

    def _hist(self, d):
        if self.popup is not None and self.listbox is not None:
            n = self.listbox.size()
            cur = self.listbox.curselection()
            i = (cur[0] + d) if cur else (0 if d > 0 else n - 1)
            i = max(0, min(n - 1, i))
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(i)
            self.listbox.see(i)
            return
        if not self.history:
            return
        if self.hpos is None:
            self.hpos = len(self.history)
        self.hpos = max(0, min(len(self.history), self.hpos + d))
        self.var.set(self.history[self.hpos] if self.hpos < len(self.history) else "")
        self.entry.icursor("end")

    def _tab(self, _e):
        if self.suggestions:
            if self.listbox is not None and not self.listbox.curselection():
                self.listbox.selection_set(0)
            self._accept_suggestion()
        return "break"

    def _accept_suggestion(self):
        if self.listbox is None:
            return
        sel = self.listbox.curselection()
        if not sel:
            return
        word = self.suggestions[sel[0]][0]
        rest = self.var.get().split(" ", 1)
        self.var.set(word + (" " + rest[1] if len(rest) > 1 else ""))
        self.entry.icursor("end")
        self._hide_popup()

    # ---------------------------------------------------------------- autocomplete
    def _changed(self, e=None):
        if e is not None and e.keysym in ("Up", "Down", "Return", "Escape", "Tab", "KP_Enter"):
            return
        text = self.var.get()
        if self.app.runner.active or not text or " " in text:
            self._hide_popup()
            return
        self.suggestions = cmdparse.complete(text, self.app.settings["aliases"], limit=10)
        if not self.suggestions:
            self._hide_popup()
            return
        self._show_popup()

    def _show_popup(self):
        t = current_theme()
        u = t.ui
        if self.popup is None:
            self.popup = tk.Toplevel(self)
            self.popup.wm_overrideredirect(True)
            try:
                self.popup.wm_attributes("-topmost", True)
            except tk.TclError:
                pass
            frame = tk.Frame(self.popup, bg=u["border_strong"])
            frame.pack(fill="both", expand=True)
            self.listbox = tk.Listbox(frame, activestyle="none", bd=0, highlightthickness=0, exportselection=False,
                                      font=t.fonts["mono"])
            self.listbox.pack(fill="both", expand=True, padx=1, pady=1)
            self.listbox.bind("<ButtonRelease-1>", lambda e: (self._accept_suggestion(), self.entry.focus_set()))
        self.listbox.configure(bg=u["surface"], fg=u["text"], selectbackground=u["select_bg"],
                               selectforeground=u["select_fg"])
        self.listbox.delete(0, "end")
        width = 0
        for name, summary in self.suggestions:
            line = f"{name:<12} {summary}"
            width = max(width, len(line))
            self.listbox.insert("end", line)
        self.listbox.configure(height=len(self.suggestions), width=min(70, width + 2))
        self.listbox.selection_set(0)
        self.update_idletasks()
        x = self.entry.winfo_rootx()
        h = self.listbox.winfo_reqheight() + 2
        y = self.entry.winfo_rooty() - h - 2
        self.popup.wm_geometry(f"+{x}+{y}")
        self.popup.deiconify()

    def _hide_popup(self):
        if self.popup is not None:
            try:
                self.popup.destroy()
            except tk.TclError:
                pass
        self.popup = None
        self.listbox = None
        self.suggestions = []

    def save_history(self):
        self.app.settings.data["command_history"] = self.history[-self.MAX_HISTORY:]


class LogView(ttk.Frame):
    """Command/output history (bottom dock)."""

    def __init__(self, master):
        super().__init__(master, style="Surface.TFrame")
        self.text = tk.Text(self, height=6, wrap="word", bd=0, highlightthickness=0, padx=10, pady=6,
                            state="disabled", cursor="arrow")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        th.subscribe(self._retheme)
        self._retheme(current_theme())

    def _retheme(self, t):
        if t is None:
            return
        u = t.ui
        self.text.configure(bg=u["surface"], fg=u["text"], font=t.fonts["mono"])
        self.text.tag_configure("cmd", foreground=u["accent"])
        self.text.tag_configure("error", foreground=u["danger"])
        self.text.tag_configure("warning", foreground=u["warning"])
        self.text.tag_configure("success", foreground=u["success"])
        self.text.tag_configure("info", foreground=u["muted"])

    def add(self, line: str, kind: str = "info"):
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n", kind)
        n = int(self.text.index("end-1c").split(".")[0])
        if n > 600:
            self.text.delete("1.0", f"{n - 500}.0")
        self.text.configure(state="disabled")
        self.text.see("end")
