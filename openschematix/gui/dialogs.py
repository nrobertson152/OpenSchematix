"""Dialogs: About, project properties, preferences, keyboard shortcuts, valve
configuration, library import preview, DXF import, PDF export, drawing scale,
wire numbering, recovery, symbol picker and small helpers."""
from __future__ import annotations

import copy
import os
import platform
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from .. import (APP_NAME, COPYRIGHT, DONATE_URL, LICENSE_NAME, LICENSE_URL, VERSION, symbols)
from ..model import STANDARD_SCALES, Component
from ..project import META_FIELDS, NUMBERING_SCHEMES
from ..render import CROSSING_STYLES, component_prims
from ..symbols.fluid import OPERATORS, PATTERNS, VALVE_OPTIONS, VALVE_TYPES, default_valve_params
from . import theme as th
from .canvas_view import draw_items
from .widgets import SearchEntry, Tooltip, current_theme  # noqa: F401  (Tooltip re-exported)


class Dialog(tk.Toplevel):
    def __init__(self, app, title, resizable=False, parent=None):
        # parent: window the dialog belongs to (default: the main window), e.g.
        # the symbol editor, so the dialog stays above it and is centred on it.
        self.parent = parent if parent is not None else app.root
        super().__init__(self.parent)
        self.app = app
        self.title(title)
        self.configure(bg=app.theme.ui["surface"])
        self.transient(self.parent)
        self.resizable(resizable, resizable)
        self.bind("<Escape>", lambda e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.frame = ttk.Frame(self, style="Surface.TFrame", padding=18)
        self.frame.pack(fill="both", expand=True)
        self.result = None

    def buttons(self, ok_text="OK", ok=None, cancel_text="Cancel", extra=()):
        bar = ttk.Frame(self.frame, style="Surface.TFrame")
        bar.pack(fill="x", pady=(16, 0), side="bottom")
        if cancel_text:
            ttk.Button(bar, text=cancel_text, command=self.cancel).pack(side="right")
        if ok_text:
            b = ttk.Button(bar, text=ok_text, style="Accent.TButton", command=ok or self.ok)
            b.pack(side="right", padx=(0, 8))
            self.bind("<Return>", lambda e: (ok or self.ok)() if not isinstance(e.widget, tk.Text) else None)
        for text, cmd in extra:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 8))
        return bar

    def ok(self):
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

    def show_modal(self, wait=False):
        self.update_idletasks()
        r = self.parent
        x = r.winfo_rootx() + (r.winfo_width() - self.winfo_reqwidth()) // 2
        y = r.winfo_rooty() + (r.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()
        if wait:
            self.wait_window()
        return self.result


def form(parent, rows, width=34):
    """Grid of labelled entries: rows = [(key, label, value)] -> {key: StringVar}."""
    f = ttk.Frame(parent, style="Surface.TFrame")
    f.columnconfigure(1, weight=1)
    vars_ = {}
    for i, (key, label, value) in enumerate(rows):
        ttk.Label(f, text=label, style="Surface.TLabel").grid(row=i, column=0, sticky="w", padx=(0, 12), pady=3)
        v = tk.StringVar(value=value)
        ttk.Entry(f, textvariable=v, width=width).grid(row=i, column=1, sticky="ew", pady=3)
        vars_[key] = v
    return f, vars_


# ================================================================ about
class AboutDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, f"About {APP_NAME}")
        f = self.frame
        t = app.theme
        top = ttk.Frame(f, style="Surface.TFrame")
        top.pack(fill="x")
        if app.icon_image is not None:
            try:
                self._img = app.icon_image.subsample(1)
                tk.Label(top, image=self._img, bg=t.ui["surface"]).pack(side="left", padx=(0, 16))
            except tk.TclError:
                pass
        col = ttk.Frame(top, style="Surface.TFrame")
        col.pack(side="left", fill="x")
        ttk.Label(col, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(col, text=f"Version {VERSION}", style="Surface.TLabel").pack(anchor="w")
        ttk.Label(col, text="Electrical, hydraulic and pneumatic schematic editor", style="Muted.TLabel").pack(anchor="w")
        body = (f"{COPYRIGHT}\n\n"
                f"Free and open-source software, licensed under the {LICENSE_NAME}. You may use, study, share and "
                f"modify it under the terms of that licence. It comes with ABSOLUTELY NO WARRANTY.\n\n"
                "Symbols follow the drawing conventions of IEC 60617, IEEE 315 / ANSI Y32.2, NEMA/JIC ladder "
                "diagrams and ISO 1219-1 as widely documented; they have not been checked against the official "
                "standard documents. Check Drawing finds common drafting mistakes; it does not certify that a "
                "circuit is safe or compliant. Always have safety-related designs reviewed by a qualified person.\n\n"
                "OpenSchematix has no ads, no telemetry, no accounts and no feature limits. If it is useful to you, "
                "you can support its development voluntarily.")
        ttk.Label(f, text=body, style="Surface.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(16, 8))
        links = ttk.Frame(f, style="Surface.TFrame")
        links.pack(anchor="w")
        ttk.Button(links, text="Support development (Ko-fi)", style="Link.TButton",
                   command=lambda: webbrowser.open(DONATE_URL)).pack(side="left")
        ttk.Button(links, text="Licence text", style="Link.TButton",
                   command=lambda: webbrowser.open(LICENSE_URL)).pack(side="left", padx=8)
        ttk.Label(f, text=f"Python {platform.python_version()} · Tk {app.root.tk.call('info', 'patchlevel')} · "
                          f"{platform.system()} {platform.release()}", style="Faint.TLabel").pack(anchor="w", pady=(10, 0))
        self.buttons("Close", cancel_text="")
        self.show_modal()


# ================================================================ project properties
class ProjectDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Project properties")
        p = app.project
        ttk.Label(self.frame, text="Project information", style="Bold.TLabel").pack(anchor="w")
        ttk.Label(self.frame, text="Used in every sheet's title block unless a sheet overrides a field.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        f, self.vars = form(self.frame, [(k, label, p.meta.get(k, "")) for k, label in META_FIELDS])
        f.pack(fill="x")
        ttk.Separator(self.frame).pack(fill="x", pady=12)
        ttk.Label(self.frame, text="Drawing options", style="Bold.TLabel").pack(anchor="w")
        g = ttk.Frame(self.frame, style="Surface.TFrame")
        g.pack(fill="x", pady=(6, 0))
        st = p.settings
        self.cross = tk.StringVar(value=CROSSING_STYLES.get(st.get("crossing_style", "bridge")))
        ttk.Label(g, text="Unconnected crossings", style="Surface.TLabel").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Combobox(g, textvariable=self.cross, values=list(CROSSING_STYLES.values()), state="readonly",
                     width=28).grid(row=0, column=1, sticky="w", padx=12)
        self.jsize = tk.StringVar(value=st.get("junction_size", "medium"))
        ttk.Label(g, text="Junction dot size", style="Surface.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(g, textvariable=self.jsize, values=("small", "medium", "large"), state="readonly",
                     width=28).grid(row=1, column=1, sticky="w", padx=12)
        self.xref = tk.StringVar(value=st.get("xref_format", "/{sheet}.{zone}"))
        ttk.Label(g, text="Cross-reference format", style="Surface.TLabel").grid(row=2, column=0, sticky="w", pady=3)
        e = ttk.Entry(g, textvariable=self.xref, width=30)
        e.grid(row=2, column=1, sticky="w", padx=12)
        Tooltip(e, "Text shown next to sheet connectors: {sheet} = sheet number, {zone} = grid zone, e.g. /2.C4")
        self.wn = tk.IntVar(value=1 if st.get("show_wire_numbers", True) else 0)
        ttk.Checkbutton(g, text="Show wire numbers", variable=self.wn).grid(row=3, column=0, columnspan=2, sticky="w",
                                                                           pady=3)
        self.tl = tk.IntVar(value=1 if st.get("show_terminal_labels", False) else 0)
        ttk.Checkbutton(g, text="Show terminal designations on all symbols", variable=self.tl).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=3)
        self.buttons("Save")
        self.show_modal()

    def ok(self):
        meta = {k: v.get().strip() for k, v in self.vars.items()}
        inv = {v: k for k, v in CROSSING_STYLES.items()}
        settings = {"crossing_style": inv.get(self.cross.get(), "bridge"), "junction_size": self.jsize.get(),
                    "xref_format": self.xref.get() or "/{sheet}.{zone}", "show_wire_numbers": bool(self.wn.get()),
                    "show_terminal_labels": bool(self.tl.get())}
        try:
            settings["xref_format"].format(sheet=1, zone="A1")
        except (KeyError, IndexError, ValueError):
            messagebox.showerror("Cross-reference format", "Use only {sheet} and {zone} as placeholders.", parent=self)
            return
        self.app.update_project(meta, settings)
        self.destroy()


# ================================================================ preferences
class PreferencesDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Preferences")
        st = app.settings
        nb = ttk.Notebook(self.frame)
        nb.pack(fill="both", expand=True)
        # appearance
        a = ttk.Frame(nb, style="Surface.TFrame", padding=14)
        nb.add(a, text="Appearance")
        self.theme = tk.StringVar(value=th.THEMES[app.theme.name]["label"])
        self.canvas = tk.StringVar(value="Same as interface theme" if st["canvas_theme"] == "auto" else
                                   th.CANVAS_THEMES.get(st["canvas_theme"], ("White paper",))[0])
        rows = [("Interface theme", ttk.Combobox(a, textvariable=self.theme, state="readonly", width=26,
                                                 values=[t["label"] for t in th.THEMES.values()])),
                ("Drawing canvas", ttk.Combobox(a, textvariable=self.canvas, state="readonly", width=26,
                                                values=["Same as interface theme"] +
                                                [v[0] for v in th.CANVAS_THEMES.values()]))]
        self.scale = tk.StringVar(value="Automatic" if not st["ui_scale"] else f"{st['ui_scale']:g}")
        rows.append(("Interface scale", ttk.Combobox(a, textvariable=self.scale, width=26,
                                                     values=["Automatic", "1", "1.25", "1.5", "1.75", "2"])))
        for i, (lab, w) in enumerate(rows):
            ttk.Label(a, text=lab, style="Surface.TLabel").grid(row=i, column=0, sticky="w", pady=4, padx=(0, 12))
            w.grid(row=i, column=1, sticky="w", pady=4)
        ttk.Label(a, text="Printed and exported drawings are always black on white.\nThe interface scale takes "
                          "effect after a restart.", style="Muted.TLabel", justify="left").grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(8, 0))
        # editing
        e = ttk.Frame(nb, style="Surface.TFrame", padding=14)
        nb.add(e, text="Editing")
        self.grid_step = tk.StringVar(value=f"{st['grid_step'] * 0.25:g}")
        self.autosave = tk.StringVar(value=str(st["autosave_minutes"]))
        self.default_sheet = tk.StringVar(value=st["default_sheet"])
        from ..model import SHEET_SIZES_MM
        erows = [("Grid / snap step (mm)", ttk.Combobox(e, textvariable=self.grid_step, width=10,
                                                         values=["0.25", "0.5", "1.25", "2.5", "5"])),
                 ("Autosave every (minutes, 0 = off)", ttk.Spinbox(e, from_=0, to=60, textvariable=self.autosave,
                                                                    width=8)),
                 ("Default sheet size", ttk.Combobox(e, textvariable=self.default_sheet, state="readonly", width=10,
                                                     values=list(SHEET_SIZES_MM)))]
        for i, (lab, w) in enumerate(erows):
            ttk.Label(e, text=lab, style="Surface.TLabel").grid(row=i, column=0, sticky="w", pady=4, padx=(0, 12))
            w.grid(row=i, column=1, sticky="w", pady=4)
        self.flags = {}
        for j, (k, lab) in enumerate((("snap_grid", "Snap to grid (F9)"), ("osnap", "Object snap (F3)"),
                                      ("ortho", "Ortho mode (F8)"), ("show_grid", "Show grid (F7)"),
                                      ("show_markers", "Show unconnected-terminal markers"),
                                      ("show_command_line", "Show the command line"))):
            v = tk.IntVar(value=1 if st[k] else 0)
            ttk.Checkbutton(e, text=lab, variable=v).grid(row=len(erows) + j, column=0, columnspan=2, sticky="w",
                                                          pady=2)
            self.flags[k] = v
        ttk.Label(e, text="Wires always snap to the 2.5 mm grid so they meet symbol terminals exactly.",
                  style="Muted.TLabel").grid(row=20, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.buttons("Apply", extra=[("Keyboard shortcuts…", lambda: ShortcutsDialog(self.app))])
        self.show_modal()

    def ok(self):
        st = self.app.settings
        inv = {t["label"]: k for k, t in th.THEMES.items()}
        cinv = {v[0]: k for k, v in th.CANVAS_THEMES.items()}
        try:
            step_mm = float(self.grid_step.get().replace(",", "."))
            auto = int(float(self.autosave.get()))
            sc = 0.0 if self.scale.get() == "Automatic" else float(self.scale.get())
        except ValueError:
            messagebox.showerror("Preferences", "Please enter numbers.", parent=self)
            return
        st["grid_step"] = max(1, int(round(step_mm / 0.25)))
        st["autosave_minutes"] = max(0, min(120, auto))
        st["ui_scale"] = sc if 0.5 <= sc <= 4 else 0.0
        st["default_sheet"] = self.default_sheet.get()
        for k, v in self.flags.items():
            st[k] = bool(v.get())
        self.app.set_theme(inv.get(self.theme.get(), th.DEFAULT_THEME), cinv.get(self.canvas.get(), "auto"))
        self.app.apply_settings()
        self.destroy()


# ================================================================ shortcuts
class ShortcutsDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Keyboard shortcuts", resizable=True)
        f = self.frame
        ttk.Label(f, text="Keyboard shortcuts", style="Bold.TLabel").pack(anchor="w")
        ttk.Label(f, text="Double-click a shortcut to change it. Letters typed on the drawing go to the command "
                          "line (type L Enter for LINE, CO for COPY…), so shortcuts must use Ctrl, Alt or a "
                          "function key.", style="Muted.TLabel", wraplength=640, justify="left").pack(anchor="w",
                                                                                                      pady=(0, 8))
        body = ttk.Frame(f, style="Surface.TFrame")
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=("key", "action"), show="headings", height=16)
        self.tree.heading("key", text="Shortcut", anchor="w")
        self.tree.heading("action", text="Action", anchor="w")
        self.tree.column("key", width=170)
        self.tree.column("action", width=380)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._edit)
        self.keys = dict(app.keymap.current())
        self._fill()
        ttk.Label(f, text="Command aliases (type in the command line):", style="Bold.TLabel").pack(anchor="w",
                                                                                                    pady=(10, 2))
        from .. import commands
        alias = ", ".join(f"{a} {c.name}" for c in commands.COMMANDS for a in c.aliases)
        ttk.Label(f, text=alias, style="Muted.TLabel", wraplength=640, justify="left").pack(anchor="w")
        self.buttons("Save", extra=[("Reset to defaults", self._reset)])
        self.show_modal()

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        for aid, (label, _default) in self.app.keymap.actions.items():
            self.tree.insert("", "end", aid, values=(self.keys.get(aid, ""), label))
        for key, label in self.app.keymap.fixed:
            self.tree.insert("", "end", values=(key, label + "  (fixed)"))

    def _edit(self, e):
        aid = self.tree.identify_row(e.y)
        if aid not in self.app.keymap.actions:
            return
        cap = KeyCaptureDialog(self.app, self.app.keymap.actions[aid][0], self.keys.get(aid, ""))
        key = cap.show_modal(wait=True)
        if key is None:
            return
        from .keymap import validate_key
        err = validate_key(key)
        if err:
            messagebox.showerror("Shortcut", err, parent=self)
            return
        other = [a for a, k in self.keys.items() if k == key and a != aid and key]
        if other:
            if not messagebox.askyesno("Shortcut in use", f"{key} is used by “{self.app.keymap.actions[other[0]][0]}”."
                                       " Move it to this action?", parent=self):
                return
            self.keys[other[0]] = ""
        self.keys[aid] = key
        self._fill()

    def _reset(self):
        self.keys = {a: d for a, (_l, d) in self.app.keymap.actions.items()}
        self._fill()

    def ok(self):
        self.app.keymap.save(self.keys)
        self.destroy()


class KeyCaptureDialog(Dialog):
    def __init__(self, app, action, current):
        super().__init__(app, "Change shortcut")
        ttk.Label(self.frame, text=action, style="Bold.TLabel").pack(anchor="w")
        ttk.Label(self.frame, text="Press the new key combination (Backspace clears it).",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 10))
        self.var = tk.StringVar(value=current or "—")
        ttk.Label(self.frame, textvariable=self.var, style="Title.TLabel").pack(pady=10)
        self.key = current
        self.bind("<KeyPress>", self._key)
        self.buttons("OK")

    def _key(self, e):
        from .keymap import describe_event
        if e.keysym in ("Escape",):
            return
        if e.keysym in ("BackSpace",):
            self.key = ""
            self.var.set("—")
            return "break"
        k = describe_event(e)
        if k:
            self.key = k
            self.var.set(k)
        return "break"

    def ok(self):
        self.result = self.key
        self.destroy()


# ================================================================ choice / symbol picker
class ChoiceDialog(Dialog):
    def __init__(self, app, title, label, options, wait=True):
        super().__init__(app, title)
        ttk.Label(self.frame, text=label, style="Surface.TLabel").pack(anchor="w")
        self.lb = tk.Listbox(self.frame, height=min(14, max(4, len(options))), width=48, exportselection=False)
        for o in options:
            self.lb.insert("end", o)
        self.lb.pack(fill="both", expand=True, pady=6)
        self.lb.bind("<Double-1>", lambda e: self.ok())
        if options:
            self.lb.selection_set(0)
        self.options = options
        self.buttons("OK")
        th.recolor_tree(self, app.theme)
        self.show_modal(wait=wait)

    def ok(self):
        sel = self.lb.curselection()
        self.result = self.options[sel[0]] if sel else None
        self.destroy()


class SymbolPickerDialog(Dialog):
    def __init__(self, app, title="Choose a symbol", parent=None, ok_text="Choose"):
        super().__init__(app, title, resizable=True, parent=parent)
        self.search = SearchEntry(self.frame, "Search symbols", on_change=lambda q: self._fill())
        self.search.pack(fill="x")
        self.tree = ttk.Treeview(self.frame, columns=("cat",), show="tree headings", height=14)
        self.tree.heading("#0", text="Symbol", anchor="w")
        self.tree.heading("cat", text="Category", anchor="w")
        self.tree.column("#0", width=300)
        self.tree.pack(fill="both", expand=True, pady=6)
        self.tree.bind("<Double-1>", lambda e: self.ok())
        self._fill()
        self.buttons(ok_text)
        self.show_modal(wait=True)

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        for s in symbols.search(self.search.get()):
            if s.group != "Internal":
                kind = " · custom" if s.is_custom else ""
                self.tree.insert("", "end", s.id, text=s.name, values=(f"{s.category} · {s.convention}{kind}",))

    def ok(self):
        sel = self.tree.selection()
        self.result = sel[0] if sel else None
        self.destroy()


# ================================================================ valve
class ValveDialog(Dialog):
    OP_SLOTS = 3          # operators per side (e.g. spring + solenoid-operated pilot + manual override)

    def __init__(self, app, comp_id):
        super().__init__(app, "Configure directional control valve")
        self.comp = app.doc.components[comp_id]
        self.params = copy.deepcopy(self.comp.params) or default_valve_params()
        self.medium = self.params.get("medium", "hyd")
        f = self.frame
        top = ttk.Frame(f, style="Surface.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=f"Medium: {'Hydraulic' if self.medium == 'hyd' else 'Pneumatic'}",
                  style="Surface.TLabel").pack(side="left")
        ttk.Label(top, text="   Ways / positions:", style="Surface.TLabel").pack(side="left")
        self.vtype = tk.StringVar(value=self.params.get("type"))
        cb = ttk.Combobox(top, textvariable=self.vtype, values=list(VALVE_TYPES[self.medium]), state="readonly", width=6)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._type_changed())
        self.pos_frame = ttk.Frame(f, style="Surface.TFrame")
        self.pos_frame.pack(fill="x", pady=(10, 0))
        ops = ttk.Frame(f, style="Surface.TFrame")
        ops.pack(fill="x", pady=(10, 0))
        names = ["(none)"] + [OPERATORS[k] for k in OPERATORS]
        self.op_vars = {}
        for col, side in enumerate(("left", "right")):
            box = ttk.Frame(ops, style="Surface.TFrame")
            box.grid(row=0, column=col, sticky="nw", padx=(0, 24))
            ttk.Label(box, text=f"{side.title()} operators (next to valve → outer)", style="Surface.TLabel").pack(anchor="w")
            cur = self.params.get(side, [])
            for i in range(self.OP_SLOTS):
                v = tk.StringVar(value=OPERATORS[cur[i]] if i < len(cur) and cur[i] in OPERATORS else "(none)")
                c = ttk.Combobox(box, textvariable=v, values=names, state="readonly", width=18)
                c.pack(anchor="w", pady=2)
                c.bind("<<ComboboxSelected>>", lambda e: self._update())
                self.op_vars[(side, i)] = v
        opts = ttk.Frame(f, style="Surface.TFrame")
        opts.pack(fill="x", pady=(8, 0))
        self.opt_vars = {}
        for key, label in VALVE_OPTIONS.items():
            v = tk.BooleanVar(value=bool(self.params.get(key)))
            ttk.Checkbutton(opts, text=label, variable=v, command=self._update).pack(anchor="w")
            self.opt_vars[key] = v
        t = app.theme
        self.preview = tk.Canvas(f, width=560, height=170, bg=t["paper"], highlightthickness=1,
                                 highlightbackground=t.ui["border"])
        self.preview.pack(pady=(12, 0))
        ttk.Label(f, text="Ports are drawn on the rest (spring-offset or centre) position. "
                          "Operators on a side shift the valve into the position next to that side.",
                  style="Muted.TLabel", wraplength=560, justify="left").pack(anchor="w", pady=(6, 0))
        self.buttons("Apply")
        self._build_positions()
        self.show_modal()

    def _type_changed(self):
        p = default_valve_params(self.medium, self.vtype.get())
        self.params["type"] = p["type"]
        self.params["positions"] = p["positions"]
        self._build_positions()

    def _build_positions(self):
        for w in self.pos_frame.winfo_children():
            w.destroy()
        nports, npos = VALVE_TYPES[self.medium][self.params["type"]]
        pats = PATTERNS[nports]
        keys = list(pats)
        labels = [pats[k]["label"] for k in keys]
        self.pos_vars = []
        names = ["Left position (a)", "Centre position (0)", "Right position (b)"] if npos == 3 else \
            ["Left position (a)", "Right position (b)"]
        for i in range(npos):
            ttk.Label(self.pos_frame, text=names[i], style="Surface.TLabel").grid(row=i, column=0, sticky="w", pady=2)
            cur = self.params["positions"][i] if i < len(self.params["positions"]) else keys[0]
            v = tk.StringVar(value=pats.get(cur, pats[keys[0]])["label"])
            c = ttk.Combobox(self.pos_frame, textvariable=v, values=labels, state="readonly", width=42)
            c.grid(row=i, column=1, sticky="w", padx=8, pady=2)
            c.bind("<<ComboboxSelected>>", lambda e: self._update())
            self.pos_vars.append((v, keys, labels))
        self._update()

    def _collect(self):
        p = dict(self.params)
        p["positions"] = [keys[labels.index(v.get())] for v, keys, labels in self.pos_vars]
        rev = {v: k for k, v in OPERATORS.items()}
        for side in ("left", "right"):
            p[side] = [rev[self.op_vars[(side, i)].get()] for i in range(self.OP_SLOTS)
                       if self.op_vars[(side, i)].get() in rev]
        for key, v in self.opt_vars.items():
            if v.get():
                p[key] = True
            else:
                p.pop(key, None)       # an unset option is not stored (existing valves keep their params)
        return p

    def _update(self):
        p = self._collect()
        cv = self.preview
        cv.delete("all")
        comp = Component(0, self.comp.symbol, 0, 0, params=p)
        b = comp.bbox()
        w, h = 560, 170
        z = min((w - 40) / max(b[2] - b[0], 1), (h - 30) / max(b[3] - b[1], 1), 3.0)
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        items = [i for i in component_prims(comp, item=False)]
        t = self.app.theme
        draw_items(cv, items, lambda q: (w / 2 + (q[0] - cx) * z, h / 2 + (q[1] - cy) * z), z, t,
                   self.app.canvas.font_family)
        for name, q in comp.terminals().items():
            x, y = w / 2 + (q[0] - cx) * z, h / 2 + (q[1] - cy) * z
            cv.create_text(x + 8, y, text=name, fill=t["open_term"], anchor="w")

    def ok(self):
        self.app.edit_components([self.comp], params=self._collect())
        self.destroy()


# ================================================================ library import preview
class LibraryImportDialog(Dialog):
    def __init__(self, app, path, target=""):
        from ..userlib import read_package
        super().__init__(app, "Import symbol library", resizable=True)
        try:
            self.info = read_package(path, app.userlib)
        except (OSError, ValueError) as e:
            self.destroy()
            messagebox.showerror("Import library", str(e), parent=app.root)
            return
        info = self.info
        f = self.frame
        ttk.Label(f, text=info.name, style="Title.TLabel").pack(anchor="w")
        meta = " · ".join(x for x in (info.author and f"by {info.author}", info.created[:10],
                                      f"{len(info.items)} symbols", f"{len(info.folders)} folders") if x)
        ttk.Label(f, text=meta, style="Muted.TLabel").pack(anchor="w")
        if info.description:
            ttk.Label(f, text=info.description, style="Surface.TLabel", wraplength=600).pack(anchor="w", pady=(6, 0))
        body = ttk.Frame(f, style="Surface.TFrame")
        body.pack(fill="both", expand=True, pady=8)
        self.tree = ttk.Treeview(body, columns=("folder", "rev", "conflict"), show="tree headings", height=12,
                                 selectmode="extended")
        for c, h, w in (("#0", "Symbol", 220), ("folder", "Folder", 160), ("rev", "Rev.", 50),
                        ("conflict", "Already in your library", 200)):
            self.tree.heading(c, text=h, anchor="w")
            self.tree.column(c, width=w)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for it in info.items:
            self.tree.insert("", "end", it.id, text=it.name, values=(it.folder or "(top)", it.revision, it.conflict))
        self.tree.selection_set([it.id for it in info.items])
        if info.problems:
            ttk.Label(f, text="Skipped: " + "; ".join(info.problems[:5]), style="Warning.TLabel", wraplength=600).pack(
                anchor="w")
        opts = ttk.Frame(f, style="Surface.TFrame")
        opts.pack(fill="x")
        self.mode = tk.StringVar(value="separate")
        ttk.Radiobutton(opts, text=f"Import as a separate library “{info.name}”", value="separate",
                        variable=self.mode).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(opts, text="Merge into:", value="merge", variable=self.mode).grid(row=1, column=0, sticky="w")
        folders = app.userlib.folders() or [""]
        self.target = tk.StringVar(value=target or folders[0])
        ttk.Combobox(opts, textvariable=self.target, values=folders, width=30).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(opts, text="When a symbol already exists:", style="Surface.TLabel").grid(row=2, column=0, sticky="w",
                                                                                        pady=(8, 0))
        self.conf = tk.StringVar(value="Keep both (import as a new symbol)")
        ttk.Combobox(opts, textvariable=self.conf, state="readonly", width=34,
                     values=("Keep both (import as a new symbol)", "Replace mine", "Skip")).grid(
            row=2, column=1, sticky="w", padx=6, pady=(8, 0))
        n = len(info.conflicts)
        if n:
            ttk.Label(opts, text=f"{n} symbol(s) already exist in your libraries.", style="Warning.TLabel").grid(
                row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.buttons("Import")
        self.show_modal()

    def ok(self):
        from ..userlib import import_package
        policy = {"Keep both (import as a new symbol)": "duplicate", "Replace mine": "replace", "Skip": "skip"}[
            self.conf.get()]
        sel = set(self.tree.selection())
        if not sel:
            messagebox.showinfo("Import", "Select the symbols to import.", parent=self)
            return
        try:
            res = import_package(self.info, self.app.userlib, mode=self.mode.get(), target=self.target.get().strip(),
                                 on_conflict=policy, selected_ids=sel)
        except (OSError, ValueError) as e:
            messagebox.showerror("Import failed", str(e), parent=self)
            return
        self.app.library.populate()
        self.app.toast(f"Imported {res['imported'] + res['duplicated']} symbol(s)"
                       + (f", replaced {res['replaced']}" if res["replaced"] else "")
                       + (f", skipped {res['skipped']}" if res["skipped"] else "") + ".", "success")
        self.destroy()


# ================================================================ template save
class TemplateSaveDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Save as circuit template")
        folders = ["My templates"] + app.templates.folders()
        f, self.vars = form(self.frame, [("name", "Name", ""), ("description", "Description", "")])
        f.pack(fill="x")
        g = ttk.Frame(self.frame, style="Surface.TFrame")
        g.pack(fill="x", pady=(4, 0))
        ttk.Label(g, text="Folder", style="Surface.TLabel").pack(side="left", padx=(0, 12))
        self.folder = tk.StringVar(value=folders[0])
        ttk.Combobox(g, textvariable=self.folder, values=folders, width=30).pack(side="left")
        ttk.Label(self.frame, text="Components, wires and drawing objects in the selection are saved with their "
                                   "properties. Identifiers are reassigned when the template is inserted.",
                  style="Muted.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(10, 0))
        self.buttons("Save")
        self.show_modal()

    def ok(self):
        name = self.vars["name"].get().strip()
        if not name:
            messagebox.showinfo("Template", "Enter a name.", parent=self)
            return
        folder = self.folder.get().strip()
        folder = "" if folder == "My templates" else folder
        self.app.save_selection_as_template(name, self.vars["description"].get().strip(), folder)
        self.destroy()


# ================================================================ DXF import
class DxfImportDialog(Dialog):
    def __init__(self, app, path):
        super().__init__(app, "Import DXF")
        self.path = path
        f = self.frame
        ttk.Label(f, text=os.path.basename(path), style="Bold.TLabel").pack(anchor="w")
        g = ttk.Frame(f, style="Surface.TFrame")
        g.pack(fill="x", pady=8)
        self.units = tk.StringVar(value="From the file")
        self.scale = tk.StringVar(value="1")
        self.place = tk.StringVar(value="Centre in the drawing area")
        self.target = tk.StringVar(value="Current sheet")
        rows = (("Drawing units", ttk.Combobox(g, textvariable=self.units, state="readonly", width=24,
                                               values=("From the file", "mm", "cm", "m", "in", "ft"))),
                ("Extra scale factor", ttk.Entry(g, textvariable=self.scale, width=10)),
                ("Placement", ttk.Combobox(g, textvariable=self.place, state="readonly", width=24,
                                           values=("Centre in the drawing area",
                                                   "DXF origin at the sheet's lower-left corner"))),
                ("Import into", ttk.Combobox(g, textvariable=self.target, state="readonly", width=24,
                                             values=("Current sheet", "New sheet"))))
        for i, (lab, w) in enumerate(rows):
            ttk.Label(g, text=lab, style="Surface.TLabel").grid(row=i, column=0, sticky="w", pady=3, padx=(0, 12))
            w.grid(row=i, column=1, sticky="w", pady=3)
        ttk.Label(f, text="Lines, polylines, circles, arcs, text and dimensions become editable drawing objects on "
                          "layers named after the DXF layers. Blocks are exploded. Hatches, images and 3D objects "
                          "are skipped (a summary is shown).", style="Muted.TLabel", wraplength=440,
                  justify="left").pack(anchor="w")
        self.buttons("Import")
        self.show_modal()

    def ok(self):
        try:
            sc = float(self.scale.get().replace(",", "."))
            assert sc > 0
        except (ValueError, AssertionError):
            messagebox.showerror("Import DXF", "The scale factor must be a positive number.", parent=self)
            return
        units = None if self.units.get() == "From the file" else self.units.get()
        self.destroy()
        self.app.import_dxf(self.path, units, sc, self.place.get().startswith("Centre"),
                            self.target.get() == "New sheet")


# ================================================================ PDF export
class ExportPdfDialog(Dialog):
    def __init__(self, app, preselect=None):
        super().__init__(app, "Export PDF")
        f = self.frame
        ttk.Label(f, text="Sheets to export", style="Bold.TLabel").pack(anchor="w")
        self.vars = {}
        box = ttk.Frame(f, style="Surface.TFrame")
        box.pack(fill="x", pady=6)
        for i, d in enumerate(app.project.sheets, 1):
            v = tk.IntVar(value=1 if preselect is None or d.uid in preselect else 0)
            ttk.Checkbutton(box, text=f"{i}. {d.name}   ({d.sheet.size} {d.sheet.orientation}, {d.sheet.scale})",
                            variable=v).pack(anchor="w")
            self.vars[d.uid] = v
        row = ttk.Frame(f, style="Surface.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="All", style="Link.TButton", command=lambda: [v.set(1) for v in self.vars.values()]).pack(
            side="left")
        ttk.Button(row, text="None", style="Link.TButton", command=lambda: [v.set(0) for v in self.vars.values()]).pack(
            side="left")
        ttk.Label(f, text="Sheets are combined into one PDF, each page at its own size and orientation, with "
                          "bookmarks per sheet. Output is fully vector, so no resolution setting is needed.",
                  style="Muted.TLabel", wraplength=440, justify="left").pack(anchor="w", pady=(8, 0))
        self.buttons("Export…")
        self.show_modal()

    def ok(self):
        uids = [u for u, v in self.vars.items() if v.get()]
        if not uids:
            messagebox.showinfo("Export PDF", "Select at least one sheet.", parent=self)
            return
        self.destroy()
        self.app.export_pdf(uids)


# ================================================================ scale drawing
class ScaleDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Drawing scale")
        f = self.frame
        s = app.doc.sheet
        ttk.Label(f, text="Print (presentation) scale", style="Bold.TLabel").pack(anchor="w")
        ttk.Label(f, text="Changes only how large the drawing is printed on the sheet: the frame and title block "
                          "stay the paper size. Geometry, symbol sizes and connections are not changed.",
                  style="Muted.TLabel", wraplength=460, justify="left").pack(anchor="w")
        row = ttk.Frame(f, style="Surface.TFrame")
        row.pack(fill="x", pady=6)
        self.plot = tk.StringVar(value=s.scale)
        ttk.Combobox(row, textvariable=self.plot, values=STANDARD_SCALES, width=10).pack(side="left")
        ttk.Button(row, text="Apply print scale", command=self.apply_plot).pack(side="left", padx=8)
        ttk.Button(row, text="Fit drawing to sheet", command=self.fit).pack(side="left")
        ttk.Separator(f).pack(fill="x", pady=12)
        ttk.Label(f, text="Scale the drawing layout (geometry)", style="Bold.TLabel").pack(anchor="w")
        ttk.Label(f, text="Moves components further apart or closer together and scales wires and drawing objects. "
                          "Symbols keep their size and every connection is kept; wires are re-routed where needed.",
                  style="Muted.TLabel", wraplength=460, justify="left").pack(anchor="w")
        g = ttk.Frame(f, style="Surface.TFrame")
        g.pack(fill="x", pady=6)
        self.factor = tk.StringVar(value="1.5")
        ttk.Label(g, text="Factor", style="Surface.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Combobox(g, textvariable=self.factor, values=("0.5", "0.75", "1.25", "1.5", "2", "1:2", "2:1"),
                     width=10).grid(row=0, column=1, sticky="w", padx=8)
        self.ref = tk.StringVar(value="Centre of the drawing")
        ttk.Label(g, text="Reference point", style="Surface.TLabel").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(g, textvariable=self.ref, state="readonly", width=28,
                     values=("Centre of the drawing", "Sheet origin (top-left)", "Pick a point on the drawing")).grid(
            row=1, column=1, sticky="w", padx=8)
        self.only_sel = tk.IntVar(value=1 if app.selection else 0)
        ttk.Checkbutton(g, text="Selected objects only", variable=self.only_sel).grid(row=2, column=0, columnspan=2,
                                                                                       sticky="w")
        self.buttons("Scale geometry", cancel_text="Close")
        self.show_modal()

    def apply_plot(self):
        self.app.set_plot_scale(self.plot.get())

    def fit(self):
        self.app.fit_to_sheet()
        self.plot.set(self.app.doc.sheet.scale)

    def ok(self):
        from ..commands import ParseError, parse_scale_factor
        try:
            f = parse_scale_factor(self.factor.get())
        except ParseError as e:
            messagebox.showerror("Scale", str(e), parent=self)
            return
        ref = self.ref.get()
        ids = set(self.app.selection) if self.only_sel.get() and self.app.selection else None
        self.destroy()
        if ref.startswith("Pick"):
            self.app.run_command("SCALEDRAWING", factor=f, ids=ids)
        else:
            self.app.scale_geometry(f, "origin" if ref.startswith("Sheet") else "center", ids)


# ================================================================ wire numbering
class WireNumberDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Wire numbers")
        conv = app.project.settings["wire_numbering"]
        f = self.frame
        ttk.Label(f, text="Numbering convention", style="Bold.TLabel").pack(anchor="w")
        g = ttk.Frame(f, style="Surface.TFrame")
        g.pack(fill="x", pady=6)
        self.scheme = tk.StringVar(value=NUMBERING_SCHEMES[conv.get("scheme", "sequential")])
        self.prefix = tk.StringVar(value=conv.get("prefix", ""))
        self.start = tk.StringVar(value=str(conv.get("start", 1)))
        self.step = tk.StringVar(value=str(conv.get("step", 1)))
        self.digits = tk.StringVar(value=str(conv.get("digits", 0)))
        rows = (("Scheme", ttk.Combobox(g, textvariable=self.scheme, values=list(NUMBERING_SCHEMES.values()),
                                        state="readonly", width=40)),
                ("Prefix", ttk.Entry(g, textvariable=self.prefix, width=10)),
                ("Start at", ttk.Entry(g, textvariable=self.start, width=10)),
                ("Increment", ttk.Entry(g, textvariable=self.step, width=10)),
                ("Minimum digits (0 = no padding)", ttk.Entry(g, textvariable=self.digits, width=10)))
        for i, (lab, w) in enumerate(rows):
            ttk.Label(g, text=lab, style="Surface.TLabel").grid(row=i, column=0, sticky="w", pady=3, padx=(0, 12))
            w.grid(row=i, column=1, sticky="w", pady=3)
        ttk.Label(f, text="Every electrical connection (net) gets one number, shared by all its wires and carried "
                          "across sheet connectors. Existing numbers are kept when wires or components move; "
                          "numbers you type yourself are never changed. Hydraulic and pneumatic lines are not "
                          "numbered.", style="Muted.TLabel", wraplength=460, justify="left").pack(anchor="w")
        self.buttons("Number new connections", extra=[("Renumber all", lambda: self.ok(True))])
        self.show_modal()

    def ok(self, renumber=False):
        inv = {v: k for k, v in NUMBERING_SCHEMES.items()}
        try:
            conv = {"scheme": inv[self.scheme.get()], "prefix": self.prefix.get().strip(),
                    "start": int(self.start.get()), "step": max(1, int(self.step.get())),
                    "digits": max(0, min(6, int(self.digits.get())))}
        except ValueError:
            messagebox.showerror("Wire numbers", "Start, increment and digits must be whole numbers.", parent=self)
            return
        if renumber and not messagebox.askyesno("Renumber all", "Reassign all automatic wire numbers in drawing "
                                                "order? Manual numbers are kept.", parent=self):
            return
        self.destroy()
        self.app.number_wires(conv, renumber)


# ================================================================ recovery
class RecoveryDialog(Dialog):
    def __init__(self, app, orphans):
        super().__init__(app, "Recover unsaved work")
        self.orphans = orphans
        f = self.frame
        ttk.Label(f, text="OpenSchematix did not close normally last time.", style="Bold.TLabel").pack(anchor="w")
        ttk.Label(f, text="Automatic recovery copies were found. They are separate from your own files, which have "
                          "not been changed. Open a copy to review it, then save it under a name of your choice.",
                  style="Muted.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(4, 8))
        self.tree = ttk.Treeview(f, columns=("when", "file"), show="tree headings", height=min(8, 2 + len(orphans) * 2))
        self.tree.heading("#0", text="Project", anchor="w")
        self.tree.heading("when", text="Saved", anchor="w")
        self.tree.heading("file", text="Original file", anchor="w")
        self.tree.column("#0", width=200)
        self.tree.column("when", width=140)
        self.tree.column("file", width=240)
        for i, o in enumerate(orphans):
            node = self.tree.insert("", "end", f"o{i}", text=o.title or "Untitled project",
                                    values=(o.newest.when, o.source or "(never saved)"), open=False)
            for j, s in enumerate(o.snapshots):
                self.tree.insert(node, "end", f"o{i}s{j}", text=f"Snapshot {j + 1}", values=(s.when, ""))
        self.tree.pack(fill="both", expand=True)
        self.tree.selection_set("o0")
        self.buttons("Open copy", extra=[("Discard all", self.discard)], cancel_text="Later")
        self.show_modal(wait=True)

    def ok(self):
        sel = self.tree.selection()
        if not sel:
            return
        node = sel[0]
        i = int(node[1:].split("s")[0])
        j = int(node.split("s")[1]) if "s" in node else 0
        o = self.orphans[i]
        self.result = (o, o.snapshots[j])
        self.destroy()

    def discard(self):
        if messagebox.askyesno("Discard recovery data", "Delete all recovery copies? This cannot be undone.",
                               parent=self):
            from ..recovery import RecoveryManager
            for o in self.orphans:
                RecoveryManager.discard(o)
            self.result = None
            self.destroy()


# ================================================================ text entry (multi-line aware)
class TextDialog(Dialog):
    def __init__(self, app, title, prompt, initial=""):
        super().__init__(app, title)
        ttk.Label(self.frame, text=prompt, style="Surface.TLabel").pack(anchor="w")
        self.var = tk.StringVar(value=initial)
        e = ttk.Entry(self.frame, textvariable=self.var, width=48)
        e.pack(fill="x", pady=6)
        e.focus_set()
        e.select_range(0, "end")
        self.buttons("OK")
        self.show_modal(wait=False)
        e.focus_set()
        self.wait_window()

    def ok(self):
        self.result = self.var.get()
        self.destroy()
