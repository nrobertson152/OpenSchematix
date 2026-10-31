"""Symbol editor: draw custom electrical, electronic, hydraulic and
pneumatic symbols with lines, polylines, rectangles, circles, arcs and text,
add named and typed connection points, set the insertion point and save the
symbol into a user library.

The drawing tools are the same CAD commands as in the schematic editor
(cadcmds.py), so LINE, TRIM, ROTATE … behave identically, with grid snap,
object snap, ortho and typed coordinates (millimetres, relative to the
symbol's insertion point, Y up).
"""
from __future__ import annotations

import copy
import json
import math
import tkinter as tk
from tkinter import messagebox, ttk

from .. import symbols
from ..geometry import GRID, UNIT_MM, snap
from ..model import Document, Shape
from ..shapes import (move_shape, rotate_point, shape_distance, shape_prims, shape_to_symbol_prim, shapes_bbox,
                      snap_points, symbol_prim_to_shape)
from ..symbols.base import PORT_TYPES
from ..symbols.custom import CATEGORIES, SymbolFormatError, blank_symbol, new_symbol_id, normalise
from . import cadcmds
from . import interact as ia
from . import theme as th
from .canvas_view import DrawingView, draw_items
from .cmdline import CommandLine
from .widgets import IconButton, ToolbarSeparator, Tooltip, current_theme

SNAP_STEPS = {"0.25 mm": 1, "0.625 mm": 2.5, "1.25 mm": 5, "2.5 mm (pin grid)": 10}
DIR_LABEL = {"l": "Left", "r": "Right", "u": "Up", "d": "Down"}
EXTENT = 200     # half-size of the editing area in units (50 mm)
# Commands that can be typed in the symbol editor (names from commands.py;
# every alias of these, built-in or user defined, works as well).
EDITOR_COMMANDS = frozenset(cadcmds.DRAW_COMMANDS) | {"UNDO", "REDO", "ZOOM", "SAVE", "HELP"}


class EditorCanvas(DrawingView):
    def __init__(self, master, ed):
        super().__init__(master, takefocus=1)
        self.ed = ed
        self.request = None
        self.cursor = (0.0, 0.0)
        self.snap_kind = None
        self.drag = None
        self.tool = "select"
        self._fitted = False
        self.bind("<Configure>", lambda e: self.redraw() if self._fitted else self.after_idle(self.fit))
        self.bind("<Motion>", self._motion)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<ButtonPress-3>", lambda e: self.ed.runner.enter() if self.request else self.ed.context_menu(e))
        self.bind("<Double-Button-1>", self._double)

    def fit(self):
        self._fitted = True
        b = self.ed.bbox() or (-60, -40, 60, 40)
        b = (min(b[0], -40), min(b[1], -40), max(b[2], 40), max(b[3], 40))
        self.fit_box((b[0] - 30, b[1] - 30, b[2] + 30, b[3] + 30))

    def default_cursor(self):
        return "crosshair" if self.request is not None or self.tool != "select" else ""

    def on_request(self, req):
        self.request = req
        self.configure(cursor=self.default_cursor())
        self.redraw()

    def escape(self):
        if self.ed.runner.active:
            self.ed.runner.cancel()
        elif self.tool != "select":
            self.ed.set_tool("select")
        else:
            self.ed.set_selection(set())

    # ---------------------------------------------------------------- snapping
    def resolve_point(self, raw, base=None, step=None):
        st = self.ed.app.settings
        self.snap_kind = None
        tol = 10 / self.zoom
        if st["osnap"]:
            best = None
            for s in self.ed.doc.shapes.values():
                for kind, q in snap_points(s):
                    d = math.hypot(q[0] - raw[0], q[1] - raw[1])
                    if d <= tol and (best is None or d < best[0]):
                        best = (d, kind, q)
            for p in self.ed.pins:
                q = (p["x"], p["y"])
                d = math.hypot(q[0] - raw[0], q[1] - raw[1])
                if d <= tol and (best is None or d < best[0]):
                    best = (d, "end", q)
            if best:
                self.snap_kind = best[1]
                return best[2]
        p = raw
        if base is not None and st["ortho"]:
            p = (p[0], base[1]) if abs(p[0] - base[0]) >= abs(p[1] - base[1]) else (base[0], p[1])
        step = step or self.ed.snap_step()
        if st["snap_grid"] or step == GRID:
            p = (snap(p[0], step), snap(p[1], step))
        return p

    # ---------------------------------------------------------------- drawing
    def _redraw_now(self):
        self._redraw_pending = False
        t = self.ed.app.theme
        self.delete("all")
        self.configure(bg=t["paper"])
        step = self.ed.snap_step()
        g = step
        while g * self.zoom < 7:
            g *= 2
        wx0, wy0 = self.to_world(0, 0)
        wx1, wy1 = self.to_world(self.winfo_width(), self.winfo_height())
        x = snap(wx0, g) - g
        while x <= wx1:
            sx = self.to_screen((x, 0))[0]
            col = t["grid_major"] if abs(x % GRID) < 1e-6 else t["grid"]
            self.create_line(sx, 0, sx, self.winfo_height(), fill=col)
            x += g
        y = snap(wy0, g) - g
        while y <= wy1:
            sy = self.to_screen((0, y))[1]
            col = t["grid_major"] if abs(y % GRID) < 1e-6 else t["grid"]
            self.create_line(0, sy, self.winfo_width(), sy, fill=col)
            y += g
        ox, oy = self.to_screen((0, 0))
        self.create_line(ox - 14, oy, ox + 14, oy, fill=t["xref"], width=1)
        self.create_line(ox, oy - 14, ox, oy + 14, fill=t["xref"], width=1)
        self.create_oval(ox - 4, oy - 4, ox + 4, oy + 4, outline=t["xref"])
        sel = self.ed.selection
        items = []
        for s in self.ed.doc.shapes.values():
            items += shape_prims(s, item=s.id, role="ink")
        draw_items(self, items, self.to_screen, self.zoom, t, self.font_family, selected=sel)
        for p in self.ed.pins:
            key = "pin:" + p["id"]
            col = t["select"] if key in sel else t["wire"]
            x, y = self.to_screen((p["x"], p["y"]))
            r = max(3, 2.5 * self.zoom)
            self.create_oval(x - r, y - r, x + r, y + r, outline=col, width=2)
            dx, dy = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}[p["dir"]]
            self.create_line(x, y, x + dx * 14, y + dy * 14, fill=col, width=2, arrow="last", arrowshape=(6, 7, 3))
            if dx:
                self.create_text(x, y - r - 4, text=p["name"], fill=col, anchor="s",
                                 font=(self.font_family, -11, "bold"))
            else:
                self.create_text(x + r + 5, y, text=p["name"], fill=col, anchor="w",
                                 font=(self.font_family, -11, "bold"))
        for i in sel:
            s = self.ed.doc.shapes.get(i) if isinstance(i, int) else None
            if s is None:
                continue
            for kind, q in snap_points(s):
                if kind in ("end", "center", "node"):
                    x, y = self.to_screen(q)
                    self.create_rectangle(x - 3, y - 3, x + 3, y + 3, fill=t["paper"], outline=t["select"])
        self._overlay()

    def _overlay(self):
        t = self.ed.app.theme
        self.delete("overlay")
        r = self.request
        if r is not None:
            base = getattr(r, "base", None)
            if base is not None and isinstance(r, (ia.GetPoint, ia.GetDistance, ia.GetAngle)):
                self.create_line(*self.to_screen(base), *self.to_screen(self.cursor), fill=t["ghost"], dash=(4, 3),
                                 tags="overlay")
            prev = getattr(r, "preview", None)
            if prev:
                try:
                    draw_items(self, prev(self.cursor) or [], self.to_screen, self.zoom, t, self.font_family,
                               override=t["ghost"], tag="overlay")
                except Exception:  # noqa: BLE001
                    pass
        if self.tool in ("pin", "origin") or r is not None:
            x, y = self.to_screen(self.cursor)
            self.create_line(x - 12, y, x + 12, y, fill=t["crosshair"], tags="overlay")
            self.create_line(x, y - 12, x, y + 12, fill=t["crosshair"], tags="overlay")
        if self.snap_kind:
            x, y = self.to_screen(self.cursor)
            self.create_rectangle(x - 6, y - 6, x + 6, y + 6, outline=t["snap"], width=2, tags="overlay")
        if self.drag and self.drag.get("kind") == "band":
            a = self.to_screen(self.drag["start"])
            b = self.to_screen(self.drag["cur"])
            self.create_rectangle(*a, *b, outline=t["band"], dash=(4, 2), tags="overlay")

    # ---------------------------------------------------------------- events
    def _motion(self, e):
        raw = self.to_world(e.x, e.y)
        r = self.request
        if r is not None and isinstance(r, (ia.GetPoint, ia.GetDistance, ia.GetAngle)):
            self.cursor = self.resolve_point(raw, getattr(r, "base", None))
        elif self.tool == "pin" or self.tool == "origin":
            self.cursor = self.resolve_point(raw, step=GRID)
            self.snap_kind = None
        else:
            self.cursor = raw
            self.snap_kind = None
        self.ed.show_coords(self.cursor)
        self._overlay()

    def hit(self, p):
        tol = 6 / self.zoom
        for pin in self.ed.pins:
            if math.hypot(pin["x"] - p[0], pin["y"] - p[1]) <= tol * 1.5:
                return "pin:" + pin["id"]
        best = None
        for s in self.ed.doc.shapes.values():
            d = shape_distance(s, p)
            if d <= tol and (best is None or d < best[0]):
                best = (d, s.id)
        return best[1] if best else None

    def _press(self, e):
        self.focus_set()
        raw = self.to_world(e.x, e.y)
        r = self.request
        runner = self.ed.runner
        if r is not None:
            if isinstance(r, (ia.GetPoint, ia.GetDistance, ia.GetAngle)):
                runner.answer(self.resolve_point(raw, getattr(r, "base", None)))
            elif isinstance(r, ia.GetSelection):
                h = self.hit(raw)
                if h is None:
                    self.drag = {"kind": "band", "start": raw, "cur": raw}
                else:
                    self.ed.set_selection(self.ed.selection ^ {h})
            elif isinstance(r, ia.GetObject):
                h = self.hit(raw)
                runner.answer((h if isinstance(h, int) else None, raw))
            return
        if self.tool == "pin":
            self.ed.add_pin(self.resolve_point(raw, step=GRID))
            return
        if self.tool == "origin":
            self.ed.set_origin(self.resolve_point(raw, step=GRID))
            self.ed.set_tool("select")
            return
        h = self.hit(raw)
        if h is None:
            if not e.state & 0x0005:
                self.ed.set_selection(set())
            self.drag = {"kind": "band", "start": raw, "cur": raw}
            return
        if e.state & 0x0005:
            self.ed.set_selection(self.ed.selection ^ {h})
            return
        if h not in self.ed.selection:
            self.ed.set_selection({h})
        step = self.ed.snap_step()
        self.drag = {"kind": "move", "start": (snap(raw[0], GRID if any(isinstance(i, str) for i in self.ed.selection)
                                                    else step),
                                               snap(raw[1], GRID if any(isinstance(i, str) for i in self.ed.selection)
                                                    else step)),
                     "applied": (0, 0), "snap": self.ed.begin_change(), "moved": False}

    def _drag(self, e):
        d = self.drag
        if not d:
            return
        raw = self.to_world(e.x, e.y)
        if d["kind"] == "band":
            d["cur"] = raw
            self._overlay()
            return
        step = GRID if any(isinstance(i, str) for i in self.ed.selection) else self.ed.snap_step()
        tx, ty = snap(raw[0], step) - d["start"][0], snap(raw[1], step) - d["start"][1]
        ax, ay = d["applied"]
        if (tx, ty) != (ax, ay):
            self.ed.sel_move(self.ed.selection, tx - ax, ty - ay)
            d["applied"] = (tx, ty)
            d["moved"] = True
            self.redraw()

    def _release(self, e):
        d, self.drag = self.drag, None
        if not d:
            return
        if d["kind"] == "band":
            a, b = d["start"], self.to_world(e.x, e.y)
            r = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
            if r[2] - r[0] > 1 or r[3] - r[1] > 1:
                found = {s.id for s in self.ed.doc.shapes.values()
                         if (bb := s.bbox()) and r[0] <= bb[0] and r[1] <= bb[1] and bb[2] <= r[2] and bb[3] <= r[3]}
                found |= {"pin:" + p["id"] for p in self.ed.pins if r[0] <= p["x"] <= r[2] and r[1] <= p["y"] <= r[3]}
                self.ed.set_selection(self.ed.selection | found)
            self.redraw()
            return
        if d.get("moved"):
            self.ed.commit_change(d["snap"], "Moved.")

    def _double(self, e):
        h = self.hit(self.to_world(e.x, e.y))
        if isinstance(h, str):
            self.ed.select_pin_row(h[4:])
        elif isinstance(h, int) and self.ed.doc.shapes[h].kind == "text":
            self.ed.edit_text(h)


class SymbolEditor(tk.Toplevel):
    def __init__(self, app, doc=None, folder=None, from_builtin=None):
        super().__init__(app.root)
        self.app = app
        app.windows.append(self)
        self.geometry("1240x780")
        self.minsize(900, 560)
        self.configure(bg=app.theme.ui["bg"])
        self.protocol("WM_DELETE_WINDOW", self.close)
        if doc is not None:
            self.meta = normalise(copy.deepcopy(doc))
            self.is_new = doc.get("id") not in app.userlib.entries
        elif from_builtin is not None:
            self.meta = self._from_builtin(from_builtin)
            self.is_new = True
        else:
            self.meta = blank_symbol()
            self.meta["revision"] = 0
            self.is_new = True
        self.folder = folder if folder is not None else (app.userlib.entries[self.meta["id"]].folder
                                                         if self.meta["id"] in app.userlib.entries else None)
        self.doc = Document()
        for p in self.meta["prims"]:
            self.doc.add_shape(symbol_prim_to_shape(p, self.doc.new_id()))
        self.pins = [dict(p) for p in self.meta["pins"]]
        self.selection = set()
        self.undo_stack, self.redo_stack = [], []
        self.dirty = False
        self.change_counter = 0
        self.runner = ia.CommandRunner(self)
        self.available_commands = EDITOR_COMMANDS      # filters command-line autocomplete
        self.last_command = ""
        self._build()
        self._update_title()
        self.bind("<Escape>", lambda e: self.canvas.escape())
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Delete>", lambda e: self._delete_key(e))
        self.bind("<KeyPress>", self._key)
        self.bind("<Return>", self._confirm_key)
        self.bind("<KP_Enter>", self._confirm_key)

    # ---------------------------------------------------------------- construction
    def _from_builtin(self, sid):
        sd = symbols.get(sid)
        m = blank_symbol(f"{sd.name} (custom)", sd.category if sd.category in CATEGORIES else "General")
        g = sd.build(None)
        m.update(description=sd.description, group=sd.group, prefix=sd.prefix, convention="Custom (based on " +
                 sd.convention + ")", tags=list(sd.keywords))
        m["prims"] = [p for p in g.prims]
        m["pins"] = [{"id": t.name, "name": t.label or t.name, "x": t.x, "y": t.y, "dir": t.dir,
                      "type": sd.port_type(t), "show": False} for t in g.terminals]
        return normalise(json.loads(json.dumps(m)))

    def _build(self):
        t = self.app.theme
        tb = ttk.Frame(self, style="Toolbar.TFrame", padding=(8, 4))
        tb.pack(fill="x")
        self.tool_buttons = {}

        def tool(icon, name, tip):
            b = IconButton(tb, icon, lambda: self.set_tool(name), tip, checkable=True)
            b.pack(side="left", padx=1)
            self.tool_buttons[name] = b

        def cmd(icon, fn, tip):
            IconButton(tb, icon, fn, tip).pack(side="left", padx=1)

        def sep():
            ToolbarSeparator(tb).pack(side="left", padx=6, pady=4)
        from .. import commands as cp
        aliases = self.app.settings["aliases"]
        tool("select", "select", "Select and move objects (Esc)")
        sep()
        for icon, name in (("line", "LINE"), ("polyline", "PLINE"), ("rect", "RECTANGLE"), ("circle", "CIRCLE"),
                           ("arc", "ARC"), ("text", "TEXT")):
            tool(icon, name, cp.tooltip(name, extra_aliases=aliases, summary=cadcmds.TOOL_TIPS[name]))
        tool("pin", "pin", "Add a connection point: click on the 2.5 mm grid")
        tool("origin", "origin", "Set the insertion point (origin) of the symbol")
        sep()
        for icon, name in (("move", "MOVE"), ("copy", "COPY"), ("rotate", "ROTATE"), ("mirror", "MIRROR"),
                           ("scale", "SCALE"), ("trim", "TRIM"), ("extend", "EXTEND")):
            tool(icon, name, cp.tooltip(name, extra_aliases=aliases, summary=cadcmds.TOOL_TIPS[name]))
        cmd("delete", lambda: self._delete_key(None),
            cp.tooltip("ERASE", "Delete", aliases, summary="Delete the selection"))
        sep()
        cmd("undo", self.undo, cp.tooltip("UNDO", "Ctrl+Z", aliases, summary="Undo the last change"))
        cmd("redo", self.redo, cp.tooltip("REDO", "Ctrl+Y", aliases, summary="Redo the last undone change"))
        cmd("zoom_fit", lambda: self.canvas.fit(), cp.tooltip("ZOOM", extra_aliases=aliases,
                                                              summary="Zoom to the whole symbol"))
        # Keep drawing commands on the first row; style and snap controls need
        # their own row so they remain accessible at the default window width.
        tb = ttk.Frame(self, style="Toolbar.TFrame", padding=(8, 4))
        tb.pack(fill="x")
        ttk.Label(tb, text="Line", style="Toolbar.TLabel").pack(side="left", padx=(4, 4))
        self.width_var = tk.StringVar(value="normal")
        wcb = ttk.Combobox(tb, textvariable=self.width_var, values=("thin", "normal", "thick"), state="readonly",
                           width=7)
        wcb.pack(side="left")
        wcb.bind("<<ComboboxSelected>>", lambda e: self.apply_style(width=self.width_var.get()))
        Tooltip(wcb, "Line width of the selected objects and of new objects (0.25 / 0.35 / 0.55 mm)")
        self.dash_var = tk.IntVar(value=0)
        self.fill_var = tk.IntVar(value=0)
        ttk.Checkbutton(tb, text="Dashed", variable=self.dash_var,
                        command=lambda: self.apply_style(dash=bool(self.dash_var.get()))).pack(side="left", padx=4)
        ttk.Checkbutton(tb, text="Filled", variable=self.fill_var,
                        command=lambda: self.apply_style(fill=bool(self.fill_var.get()))).pack(side="left")
        sep()
        ttk.Label(tb, text="Arrows", style="Toolbar.TLabel").pack(side="left", padx=(4, 4))
        self.arrow_start_var = tk.IntVar(value=0)
        self.arrow_end_var = tk.IntVar(value=0)
        ttk.Checkbutton(tb, text="Start", variable=self.arrow_start_var,
                        command=lambda: self.apply_style(arrow_start=bool(self.arrow_start_var.get()))).pack(side="left")
        ttk.Checkbutton(tb, text="End", variable=self.arrow_end_var,
                        command=lambda: self.apply_style(arrow_end=bool(self.arrow_end_var.get()))).pack(side="left")
        self.arrow_size_var = tk.StringVar(value="2.5")
        ttk.Label(tb, text="Size mm", style="Toolbar.TLabel").pack(side="left", padx=(4, 2))
        size_entry = ttk.Entry(tb, textvariable=self.arrow_size_var, width=5)
        size_entry.pack(side="left")
        size_entry.bind("<FocusOut>", self._apply_arrow_size)
        size_entry.bind("<Return>", self._apply_arrow_size)
        sep()
        ttk.Label(tb, text="Snap", style="Toolbar.TLabel").pack(side="left", padx=(4, 4))
        self.step_var = tk.StringVar(value="1.25 mm")
        cb = ttk.Combobox(tb, textvariable=self.step_var, values=list(SNAP_STEPS), state="readonly", width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.canvas.redraw())
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True)
        left = ttk.Frame(pane, style="Surface.TFrame")
        self.canvas = EditorCanvas(left, self)
        self.canvas.font_family = self.app.canvas.font_family
        self.canvas.pack(fill="both", expand=True)
        bottom = ttk.Frame(left, style="Surface.TFrame", padding=(8, 4))
        bottom.pack(fill="x")
        self.cmdline = CommandLine(bottom, self.app, host=self, padding=0,
                                   tooltip="Command line — type a command or alias (L, C, TR, M …) and press Enter "
                                           "or Space. Enter or Space on its own repeats the last command.")
        self.cmdline.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.cmd_entry = self.cmdline.entry
        self.coords = ttk.Label(bottom, text="", style="Muted.TLabel", width=26)
        self.coords.pack(side="right")
        pane.add(left, weight=1)
        right = ttk.Frame(pane, style="Surface.TFrame", padding=10)
        pane.add(right, weight=0)
        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)
        self._build_meta(nb)
        self._build_pins(nb)
        self.status = ttk.Label(right, text="", style="Muted.TLabel", wraplength=300, justify="left")
        self.status.pack(fill="x", pady=(6, 0))
        btns = ttk.Frame(right, style="Surface.TFrame")
        btns.pack(fill="x", pady=(8, 0))
        save_btn = ttk.Button(btns, text="Save to library", style="Accent.TButton", command=self.save)
        save_btn.pack(side="left", fill="x", expand=True)
        Tooltip(save_btn, "Save this symbol to the selected library folder (Ctrl+S · type SAVE)")
        ttk.Button(btns, text="Save as new symbol", command=lambda: self.save(as_new=True)).pack(side="left",
                                                                                              padx=(6, 0))
        self.set_tool("select")
        _ = t

    def _build_meta(self, nb):
        f = ttk.Frame(nb, style="Surface.TFrame", padding=10)
        nb.add(f, text="Symbol")
        f.columnconfigure(1, weight=1)
        self.meta_vars = {}
        rows = (("name", "Name"), ("description", "Description"), ("group", "Group"), ("prefix", "Identifier prefix"),
                ("convention", "Convention"))
        r = 0
        for key, label in rows:
            ttk.Label(f, text=label, style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            v = tk.StringVar(value=self.meta.get(key, ""))
            ttk.Entry(f, textvariable=v, width=26).grid(row=r, column=1, sticky="ew", pady=3)
            v.trace_add("write", lambda *a: self._mark())
            self.meta_vars[key] = v
            r += 1
        ttk.Label(f, text="Category", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
        self.cat = tk.StringVar(value=self.meta.get("category", "General"))
        ttk.Combobox(f, textvariable=self.cat, values=CATEGORIES, state="readonly", width=24).grid(row=r, column=1,
                                                                                                  sticky="ew")
        r += 1
        ttk.Label(f, text="Tags", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
        self.tags = tk.StringVar(value=", ".join(self.meta.get("tags", [])))
        e = ttk.Entry(f, textvariable=self.tags, width=26)
        e.grid(row=r, column=1, sticky="ew", pady=3)
        Tooltip(e, "Comma separated; used by the library search. Add the tag “terminal” to make a terminal-block "
                   "symbol (numbered per strip).")
        r += 1
        ttk.Label(f, text="Library folder", style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
        folders = self.app.userlib.folders()
        self.folder_var = tk.StringVar(value=self.folder or (folders[0] if folders else "My symbols"))
        ttk.Combobox(f, textvariable=self.folder_var, values=folders or ["My symbols"], width=24).grid(
            row=r, column=1, sticky="ew")
        r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=2, sticky="ew", pady=10)
        r += 1
        ttk.Label(f, text="Default component properties", style="Bold.TLabel").grid(row=r, column=0, columnspan=2,
                                                                                     sticky="w")
        r += 1
        self.prop_vars = {}
        for key, label in (("description", "Description"), ("manufacturer", "Manufacturer"),
                           ("part_number", "Part number"), ("rating", "Rating")):
            ttk.Label(f, text=label, style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=self.meta.get("properties", {}).get(key, ""))
            ttk.Entry(f, textvariable=v, width=26).grid(row=r, column=1, sticky="ew", pady=3)
            self.prop_vars[key] = v
            r += 1
        ttk.Label(f, text=f"Revision {self.meta.get('revision', 0)} · id {self.meta['id']}", style="Faint.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _build_pins(self, nb):
        f = ttk.Frame(nb, style="Surface.TFrame", padding=10)
        nb.add(f, text="Connection points")
        self.pin_tree = ttk.Treeview(f, columns=("name", "type", "dir", "pos"), show="headings", height=8)
        for c, h, w in (("name", "Name", 60), ("type", "Type", 120), ("dir", "Lead", 50), ("pos", "Position mm", 90)):
            self.pin_tree.heading(c, text=h, anchor="w")
            self.pin_tree.column(c, width=w)
        self.pin_tree.pack(fill="both", expand=True)
        self.pin_tree.bind("<<TreeviewSelect>>", self._pin_selected)
        form_ = ttk.Frame(f, style="Surface.TFrame")
        form_.pack(fill="x", pady=(8, 0))
        form_.columnconfigure(1, weight=1)
        self.pin_name = tk.StringVar()
        self.pin_type = tk.StringVar()
        self.pin_dir = tk.StringVar()
        self.pin_show = tk.IntVar(value=1)
        ttk.Label(form_, text="Name / number", style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(form_, textvariable=self.pin_name, width=14).grid(row=0, column=1, sticky="ew")
        ttk.Label(form_, text="Port type", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(form_, textvariable=self.pin_type, values=list(PORT_TYPES.values()), state="readonly",
                     width=28).grid(row=1, column=1, sticky="ew")
        ttk.Label(form_, text="Lead direction", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(form_, textvariable=self.pin_dir, values=list(DIR_LABEL.values()), state="readonly",
                     width=10).grid(row=2, column=1, sticky="w")
        show_cb = ttk.Checkbutton(form_, text="Number this point on drawings", variable=self.pin_show)
        show_cb.grid(row=3, column=0, columnspan=2, sticky="w")
        Tooltip(show_cb, "When the project shows terminal designations (Project settings), draw this point's "
                         "name next to it. Clear it for points that should never be numbered.")
        row = ttk.Frame(form_, style="Surface.TFrame")
        row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(row, text="Apply", style="Accent.TButton", command=self._pin_apply).pack(side="left")
        ttk.Button(row, text="Renumber 1…n", command=self._pin_renumber).pack(side="left", padx=6)
        ttk.Button(row, text="Delete", command=self._pin_delete).pack(side="left")
        ttk.Label(f, text="Connection points sit on the 2.5 mm grid so wires meet them exactly. The lead direction "
                          "tells the wire router which way the wire leaves. Renaming a point never disconnects "
                          "existing drawings: points are identified internally by a permanent id.",
                  style="Muted.TLabel", wraplength=300, justify="left").pack(fill="x", pady=(8, 0))
        self._fill_pins()

    # ---------------------------------------------------------------- state
    def snap_step(self):
        return SNAP_STEPS.get(self.step_var.get(), 5)

    def _mark(self):
        self.dirty = True
        self._update_title()

    def _update_title(self):
        name = self.meta_vars["name"].get() if hasattr(self, "meta_vars") else self.meta["name"]
        self.title(f"{'*' if self.dirty else ''}{name} — Symbol editor")

    def snapshot(self):
        return json.dumps({"shapes": [s.to_dict() for s in self.doc.shapes.values()], "pins": self.pins,
                           "next": self.doc.next_id}, sort_keys=True)

    def _restore(self, snap_):
        d = json.loads(snap_)
        self.doc.shapes = {}
        for sd in d["shapes"]:
            s = Shape.from_dict(sd)
            self.doc.shapes[s.id] = s
        self.doc.next_id = d["next"]
        self.pins = d["pins"]
        self.selection = {i for i in self.selection if (isinstance(i, int) and i in self.doc.shapes) or
                          (isinstance(i, str) and any("pin:" + p["id"] == i for p in self.pins))}
        self._fill_pins()
        self.canvas.redraw()

    def begin_change(self):
        return self.snapshot()

    def cancel_change(self, _s):
        pass

    def commit_change(self, before, message=None):
        if before is not None and before != self.snapshot():
            self.undo_stack.append(before)
            self.redo_stack.clear()
            self._mark()
        self._fill_pins()
        self.canvas.redraw()
        if message:
            self.set_status(message)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self._restore(self.undo_stack.pop())
            self._mark()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self._restore(self.redo_stack.pop())
            self._mark()

    def set_status(self, msg):
        self.status.configure(text=msg)

    def log(self, msg, kind="info"):
        self.set_status(msg)

    def show_prompt(self, text):
        self.cmdline.set_prompt(text)
        if text:
            self.cmd_entry.focus_set()

    def show_coords(self, p):
        x, y = self.to_user(p)
        self.coords.configure(text=f"X {x:7.2f}   Y {y:7.2f} mm")

    def to_user(self, p):
        return (p[0] * UNIT_MM, -p[1] * UNIT_MM)

    def to_model(self, p):
        return (p[0] / UNIT_MM, -p[1] / UNIT_MM)

    def mm_per_unit(self):
        return UNIT_MM

    def runner_last_was_typed(self):
        return self.runner.typed

    def bbox(self):
        b = shapes_bbox(self.doc.shapes.values())
        for p in self.pins:
            q = (p["x"], p["y"], p["x"], p["y"])
            b = q if b is None else (min(b[0], q[0]), min(b[1], q[1]), max(b[2], q[2]), max(b[3], q[3]))
        return b

    def set_selection(self, ids):
        self.selection = set(ids)
        sel = [self.doc.shapes[i] for i in self.selection if isinstance(i, int) and i in self.doc.shapes]
        if sel and hasattr(self, "width_var"):
            self.width_var.set(sel[0].width)
            self.dash_var.set(1 if sel[0].dash else 0)
            self.fill_var.set(1 if sel[0].fill else 0)
            arrows = next((sh for sh in sel if sh.kind in ("line", "polyline")), None)
            if arrows is not None:
                self.arrow_start_var.set(int(arrows.arrow_start))
                self.arrow_end_var.set(int(arrows.arrow_end))
                self.arrow_size_var.set(f"{arrows.arrow_size * UNIT_MM:g}")
        self.canvas.redraw()

    def _current_arrow_size(self):
        try:
            value = float(self.arrow_size_var.get().replace(",", ".")) / UNIT_MM
            if math.isfinite(value) and 0 < value <= 10000:
                return value
        except (ValueError, OverflowError):
            pass
        return 10.0

    def _apply_arrow_size(self, event=None):
        try:
            size_mm = float(self.arrow_size_var.get().replace(",", "."))
            size = size_mm / UNIT_MM
            if not 0 < size <= 10000:
                raise ValueError("out of range")
        except (ValueError, OverflowError):
            self.set_status("Arrow size must be a positive number.")
            self.set_selection(self.selection)
            return "break"
        self.apply_style(arrow_size=size)
        return "break"

    def apply_style(self, **kw):
        """Apply line properties to the selected objects (and remember them for new objects)."""
        sel = [self.doc.shapes[i] for i in self.selection if isinstance(i, int) and i in self.doc.shapes]
        if not sel:
            return
        s = self.begin_change()
        for sh in sel:
            for k, v in kw.items():
                if k == "fill" and sh.kind not in ("rect", "polygon", "circle"):
                    continue
                if k.startswith("arrow_") and sh.kind not in ("line", "polyline"):
                    continue
                setattr(sh, k, v)
        self.commit_change(s, "Line properties changed.")

    def refresh_view(self):
        self.canvas.redraw()

    def new_shape_layer(self):
        return "Drafting"

    def new_shape_style(self):
        return {"width": self.width_var.get(), "dash": bool(self.dash_var.get()),
                "arrow_start": bool(self.arrow_start_var.get()),
                "arrow_end": bool(self.arrow_end_var.get()),
                "arrow_size": self._current_arrow_size()}

    def rotation_step(self, ids):
        return 90 if any(isinstance(i, str) for i in ids) else 0

    def cut_edges(self):
        return list(self.doc.shapes.values())

    # ---------------------------------------------------------------- selection transforms (cadcmds hooks)
    def _pins_in(self, ids):
        keys = {i[4:] for i in ids if isinstance(i, str)}
        return [p for p in self.pins if p["id"] in keys]

    def sel_bbox(self, ids):
        return shapes_bbox([self.doc.shapes[i] for i in ids if isinstance(i, int) and i in self.doc.shapes])

    def sel_ghost(self, ids, op):
        items = []
        for i in ids:
            if isinstance(i, int) and i in self.doc.shapes:
                items += shape_prims(cadcmds.transform_shape_copy(self.doc.shapes[i], op))
        for p in self._pins_in(ids):
            x, y = cadcmds.transform_point((p["x"], p["y"]), op)
            items.append({"k": "circle", "c": (x, y), "r": 2.5, "fill": False, "role": "ghost", "item": None})
        return items

    def _apply(self, ids, op):
        for i in ids:
            if isinstance(i, int) and i in self.doc.shapes:
                s = cadcmds.transform_shape_copy(self.doc.shapes[i], op)
                self.doc.shapes[i] = s
        bad = 0
        for p in self._pins_in(ids):
            x, y = cadcmds.transform_point((p["x"], p["y"]), op)
            sx, sy = snap(x), snap(y)
            if abs(sx - x) > 0.01 or abs(sy - y) > 0.01:
                bad += 1
            p["x"], p["y"] = sx, sy
            if op[0] in ("rotate", "mirror"):
                v = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}[p["dir"]]
                o = cadcmds.transform_point((0, 0), op)
                w = cadcmds.transform_point(v, op)
                vx, vy = w[0] - o[0], w[1] - o[1]
                p["dir"] = ("r" if vx > 0 else "l") if abs(vx) >= abs(vy) else ("d" if vy > 0 else "u")
        if bad:
            self.log(f"{bad} connection point(s) were moved to the nearest 2.5 mm grid point.", "warning")

    def sel_move(self, ids, dx, dy):
        if any(isinstance(i, str) for i in ids):
            dx, dy = snap(dx), snap(dy)
        for i in ids:
            if isinstance(i, int) and i in self.doc.shapes:
                move_shape(self.doc.shapes[i], dx, dy)
        for p in self._pins_in(ids):
            p["x"], p["y"] = snap(p["x"] + dx), snap(p["y"] + dy)

    def sel_copy(self, ids, dx, dy):
        new = set()
        for i in ids:
            if isinstance(i, int) and i in self.doc.shapes:
                s = copy.deepcopy(self.doc.shapes[i])
                s.id = self.doc.new_id()
                move_shape(s, dx, dy)
                self.doc.add_shape(s)
                new.add(s.id)
        for p in self._pins_in(ids):
            q = dict(p, id=self._new_pin_id(), name=self._next_pin_name(), x=snap(p["x"] + dx), y=snap(p["y"] + dy))
            self.pins.append(q)
            new.add("pin:" + q["id"])
        return new

    def sel_rotate(self, ids, center, deg_ccw):
        self._apply(ids, ("rotate", center, deg_ccw))

    def sel_scale(self, ids, center, k):
        self._apply(ids, ("scale", center, k))

    def sel_mirror(self, ids, p, q):
        self._apply(ids, ("mirror", p, q))

    def sel_delete(self, ids):
        for i in ids:
            if isinstance(i, int):
                self.doc.shapes.pop(i, None)
        keys = {i[4:] for i in ids if isinstance(i, str)}
        self.pins = [p for p in self.pins if p["id"] not in keys]
        self.selection = set()

    # ---------------------------------------------------------------- tools
    def set_tool(self, name):
        if self.runner.active:
            self.runner.cancel()
        for k, b in self.tool_buttons.items():
            b.set_checked(k == name)
        if name in cadcmds.DRAW_COMMANDS:
            self.canvas.tool = "select"
            self.runner.start(name, cadcmds.DRAW_COMMANDS[name](self))
            self.after(10, lambda: [b.set_checked(k == name) for k, b in self.tool_buttons.items()])
            return
        self.canvas.tool = name
        self.canvas.configure(cursor=self.canvas.default_cursor())
        hints = {"select": "Click to select, drag to move, drag on empty space for a selection window.",
                 "pin": "Click a 2.5 mm grid point to add a connection point. Its lead direction is set from its "
                        "position (edit it in Connection points).",
                 "origin": "Click the point that should become the symbol's insertion point."}
        self.set_status(hints.get(name, ""))
        self.canvas.redraw()

    # ---------------------------------------------------------------- keyboard / command line
    # Same behaviour as the schematic editor (app.py _on_key/_enter_key and
    # cmdline.CommandLine): letters go to the command line; Enter or Space on
    # the drawing confirms the running command or repeats the last one. Space
    # inside a text prompt or a typed coordinate stays a normal space
    # (CommandLine._space). Keys typed into other fields are left alone.
    TEXT_WIDGETS = (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text, tk.Spinbox, ttk.Spinbox, tk.Listbox, ttk.Treeview)

    def _on_drawing(self, w):
        return w is self.canvas or w is self

    def _key(self, e):
        w = e.widget
        if isinstance(w, self.TEXT_WIDGETS) or e.state & 0x000C:
            return None
        ch = e.char
        if not ch or not ch.isprintable():
            return None
        if ch == " ":
            # buttons and check boxes keep Space for themselves
            return self._confirm_key(e) if self._on_drawing(w) else None
        self.cmdline.focus_entry(ch)
        return "break"

    def _confirm_key(self, e):
        if e is not None and not self._on_drawing(e.widget):
            return None
        if self.runner.active:
            self.runner.enter()
        elif self.last_command:
            self.execute_input(self.last_command)
        return "break"

    def execute_input(self, text: str):
        """Run a line typed in the command line (CommandLine host API)."""
        from .. import commands as cp
        if self.runner.active:
            if not self.runner.text(text):
                self.set_status(f"Not understood: {text}")
            return
        text = text.strip()
        if not text:
            if not self.last_command:
                return
            text = self.last_command
        aliases = self.app.settings["aliases"]
        word, _args = cp.split(text)
        name = cp.resolve(word, aliases)
        if name is None:
            self.set_status(f"Unknown command “{word}”. Type HELP for the symbol editor's commands.")
            return
        if name not in EDITOR_COMMANDS:
            self.set_status(f"{name} is not available in the symbol editor. Type HELP for its commands.")
            return
        if name in cadcmds.DRAW_COMMANDS:      # Enter/Space repeats drawing commands only
            self.last_command = word
        if name in cadcmds.DRAW_COMMANDS:
            self.set_tool(name)
        elif name == "UNDO":
            self.undo()
        elif name == "REDO":
            self.redo()
        elif name == "ZOOM":
            self.canvas.fit()
        elif name == "SAVE":
            self.save()
        elif name == "HELP":
            self.set_status("Commands: " + ", ".join(
                f"{n} ({'/'.join(cp.typed_forms(n, aliases))})" for n in sorted(EDITOR_COMMANDS)))
        if not self.runner.active:
            self.canvas.focus_set()

    def _delete_key(self, e):
        if e is not None and isinstance(e.widget, (tk.Entry, ttk.Entry)):
            return
        if self.selection:
            s = self.begin_change()
            self.sel_delete(self.selection)
            self.commit_change(s, "Deleted.")

    def context_menu(self, e):
        from .widgets import make_menu
        m = make_menu(self)
        st = "normal" if self.selection else "disabled"
        for label, name in (("Move", "MOVE"), ("Copy", "COPY"), ("Rotate", "ROTATE"), ("Mirror", "MIRROR"),
                            ("Scale", "SCALE")):
            m.add_command(label=label, command=lambda n=name: self.set_tool(n), state=st)
        m.add_command(label="Delete", command=lambda: self._delete_key(None), state=st)
        m.add_separator()
        m.add_command(label="Add connection point", command=lambda: self.set_tool("pin"))
        m.add_command(label="Set insertion point", command=lambda: self.set_tool("origin"))
        m.tk_popup(e.x_root, e.y_root)

    # ---------------------------------------------------------------- pins
    def _new_pin_id(self):
        n = 1
        ids = {p["id"] for p in self.pins}
        while f"p{n}" in ids:
            n += 1
        return f"p{n}"

    def _next_pin_name(self):
        names = {p["name"] for p in self.pins}
        n = 1
        while str(n) in names:
            n += 1
        return str(n)

    def add_pin(self, p):
        if any(abs(q["x"] - p[0]) < 0.01 and abs(q["y"] - p[1]) < 0.01 for q in self.pins):
            self.set_status("There is already a connection point there.")
            return
        s = self.begin_change()
        b = shapes_bbox(self.doc.shapes.values()) or (0, 0, 0, 0)
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        dx, dy = p[0] - cx, p[1] - cy
        d = ("r" if dx > 0 else "l") if abs(dx) >= abs(dy) else ("d" if dy > 0 else "u")
        cat = self.cat.get()
        ptype = {"Hydraulic": "hyd.work", "Pneumatic": "pneu.work"}.get(cat, "elec.passive")
        pin = {"id": self._new_pin_id(), "name": self._next_pin_name(), "x": p[0], "y": p[1], "dir": d,
               "type": ptype, "show": True}
        self.pins.append(pin)
        self.selection = {"pin:" + pin["id"]}
        self.commit_change(s, f"Connection point {pin['name']} added.")
        self.select_pin_row(pin["id"])

    def _fill_pins(self):
        if not hasattr(self, "pin_tree"):
            return
        sel = self.pin_tree.selection()
        self.pin_tree.delete(*self.pin_tree.get_children())
        for p in self.pins:
            x, y = self.to_user((p["x"], p["y"]))
            self.pin_tree.insert("", "end", p["id"], values=(p["name"], PORT_TYPES.get(p.get("type", ""), "—"),
                                                             DIR_LABEL[p["dir"]], f"{x:g}, {y:g}"))
        if sel and self.pin_tree.exists(sel[0]):
            self.pin_tree.selection_set(sel[0])

    def select_pin_row(self, pid):
        if self.pin_tree.exists(pid):
            self.pin_tree.selection_set(pid)
            self.pin_tree.see(pid)

    def _pin(self):
        sel = self.pin_tree.selection()
        return next((p for p in self.pins if sel and p["id"] == sel[0]), None)

    def _pin_selected(self, _e):
        p = self._pin()
        if p is None:
            return
        self.pin_name.set(p["name"])
        self.pin_type.set(PORT_TYPES.get(p.get("type", ""), ""))
        self.pin_dir.set(DIR_LABEL[p["dir"]])
        self.pin_show.set(1 if p.get("show", True) else 0)
        self.selection = {"pin:" + p["id"]}
        self.canvas.redraw()

    def _pin_apply(self):
        p = self._pin()
        if p is None:
            return
        name = self.pin_name.get().strip()
        if not name:
            messagebox.showinfo("Connection point", "Enter a name or number.", parent=self)
            return
        if any(q["name"] == name and q is not p for q in self.pins):
            if not messagebox.askyesno("Connection point", f"Another connection point is already named {name}. "
                                       "Use the name anyway?", parent=self):
                return
        s = self.begin_change()
        inv = {v: k for k, v in PORT_TYPES.items()}
        p["name"] = name
        p["type"] = inv.get(self.pin_type.get(), p.get("type", ""))
        p["dir"] = {v: k for k, v in DIR_LABEL.items()}.get(self.pin_dir.get(), p["dir"])
        p["show"] = bool(self.pin_show.get())
        self.commit_change(s, f"Connection point {name} updated.")

    def _pin_renumber(self):
        s = self.begin_change()
        for i, p in enumerate(sorted(self.pins, key=lambda q: (q["x"], q["y"])), 1):
            p["name"] = str(i)
        self.commit_change(s, "Connection points renumbered left to right.")

    def _pin_delete(self):
        p = self._pin()
        if p is not None:
            s = self.begin_change()
            self.pins.remove(p)
            self.commit_change(s, "Connection point deleted.")

    def set_origin(self, p):
        s = self.begin_change()
        for sh in self.doc.shapes.values():
            move_shape(sh, -p[0], -p[1])
        for q in self.pins:
            q["x"], q["y"] = snap(q["x"] - p[0]), snap(q["y"] - p[1])
        self.commit_change(s, "Insertion point set.")
        self.canvas.fit()

    def edit_text(self, sid):
        from .dialogs import TextDialog
        sh = self.doc.shapes[sid]
        d = TextDialog(self.app, "Edit text", "Text:", sh.s)
        if d.result is not None:
            s = self.begin_change()
            sh.s = d.result
            self.commit_change(s, "Text changed.")

    # ---------------------------------------------------------------- save
    def build_doc(self, new_id=False) -> dict:
        m = copy.deepcopy(self.meta)
        for k, v in self.meta_vars.items():
            m[k] = v.get().strip()
        m["category"] = self.cat.get()
        m["tags"] = [t.strip() for t in self.tags.get().split(",") if t.strip()]
        m["properties"] = {k: v.get().strip() for k, v in self.prop_vars.items() if v.get().strip()}
        m["prims"] = [shape_to_symbol_prim(s) for s in self.doc.shapes.values()]
        m["pins"] = [dict(p) for p in self.pins]
        if new_id:
            m["id"] = new_symbol_id()
            m["revision"] = 0
        return normalise(m)

    def save(self, as_new=False):
        try:
            doc = self.build_doc(new_id=as_new or False)
        except SymbolFormatError as e:
            messagebox.showerror("Cannot save symbol", str(e), parent=self)
            return False
        if not doc["prims"]:
            messagebox.showerror("Cannot save symbol", "Draw the symbol first.", parent=self)
            return False
        if not doc["pins"] and not messagebox.askyesno("No connection points", "The symbol has no connection points, "
                                                       "so nothing can be wired to it. Save anyway?", parent=self):
            return False
        folder = self.folder_var.get().strip() or "My symbols"
        lib = self.app.userlib
        try:
            if folder not in lib.folders():
                import os
                os.makedirs(lib.abs(folder), exist_ok=True)
            entry = lib.save_symbol(doc, folder)
        except (OSError, ValueError) as e:
            messagebox.showerror("Cannot save symbol", str(e), parent=self)
            return False
        self.meta = copy.deepcopy(entry.doc)
        self.folder = folder
        self.dirty = False
        self._update_title()
        self.app.library.populate()
        self.set_status(f"Saved “{entry.name}” (revision {entry.doc['revision']}) in {folder}.")
        if entry.id in self.app.project.used_custom_symbols():
            if messagebox.askyesno("Update drawings?", f"The open project uses “{entry.name}”. Update its drawings "
                                   "to this new version?\n\nIf you choose No, the project keeps the version it was "
                                   "drawn with until you update it from the library.", parent=self):
                self.app.update_project_symbol(entry.id)
        return True

    def close(self):
        if self.runner.active:
            self.runner.cancel()
        if self.dirty:
            ans = messagebox.askyesnocancel("Unsaved symbol", "Save the symbol before closing?", parent=self)
            if ans is None:
                return
            if ans and not self.save():
                return
        self.destroy()

    @property
    def canvas_settings(self):
        return self.app.settings


def _unused():  # pragma: no cover
    return th, current_theme, rotate_point
