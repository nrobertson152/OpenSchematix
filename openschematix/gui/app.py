"""Main application window.

Layout (all panels resizable and collapsible; sizes are remembered):

    menu bar
    toolbar  (file · edit · draw · modify · wires · view · project)
    ┌ left sidebar ┐ ┌ sheet tabs ───────────────┐ ┌ right sidebar ┐
    │ Symbols      │ │ drawing canvas            │ │ Properties    │
    │ Sheets       │ │                           │ │ Layers        │
    │ Templates    │ ├ Output · Check · Search ──┤ │               │
    └──────────────┘ └───────────────────────────┘ └───────────────┘
    command line
    status bar  (message · GRID SNAP ORTHO OSNAP · layer · scale · X/Y · zoom · checks)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tempfile
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import (APP_NAME, DONATE_URL, PROJECT_EXTENSION, VERSION, commands as cmdparse, editing, export, netlist,
                projectio, symbols, templates)
from ..geometry import GRID, UNIT_MM, norm_rotation, snap
from ..model import Component, Shape, Wire, format_scale, parse_scale
from ..project import Project, new_project
from ..recovery import RecoveryManager
from ..settings import Settings
from ..userlib import UserLibrary, add_recent_symbol
from . import cadcmds, theme as th
from . import interact as ia
from .canvas_view import SchematicCanvas
from .cmdline import CommandLine, LogView
from .dialogs import (AboutDialog, DxfImportDialog, ExportPdfDialog, PreferencesDialog, ProjectDialog, RecoveryDialog,
                      ScaleDialog, ShortcutsDialog, SymbolPickerDialog, TemplateSaveDialog, TextDialog, ValveDialog,
                      WireNumberDialog)
from .inspector import Inspector
from .keymap import KeyMap
from .library import LibraryPanel
from .panels import CheckPanel, LayersPanel, ProjectPanel, SearchPanel, TemplatesPanel
from .widgets import IconButton, ToastHost, ToolbarSeparator, Tooltip, make_menu, set_current_theme

UNDO_LIMIT = 150
FILETYPES_OPEN = [("OpenSchematix files", "*.schematix *.osch"),
                  ("OpenSchematix project", "*" + PROJECT_EXTENSION), ("OpenSchematix legacy drawing", "*.osch"),
                  ("All files", "*.*")]


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, "openschematix", "resources", name)
        if os.path.exists(p):
            return p
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", name)


class App:
    def __init__(self, root: tk.Tk, path: str | None = None, settings: Settings | None = None,
                 check_recovery: bool = True):
        self.root = root
        self.settings = settings or Settings()
        th.set_ui_scale(root, self.settings["ui_scale"])
        self.theme = th.Theme(self.settings["theme"], self.settings["canvas_theme"])
        set_current_theme(self.theme)
        th.apply(root, self.theme)
        self.userlib = UserLibrary()
        self.userlib.scan()
        self.templates = templates.TemplateStore()
        self.project: Project = new_project(size=self._default_size())
        self.project.revisions = None
        from ..revisions import RevisionStore
        self.project.revisions = RevisionStore()
        self.doc = self.project.sheets[0]
        self.filename: str | None = None
        self.dirty = False
        self.selection: set = set()
        self.undo_stack: list = []
        self.redo_stack: list = []
        self.change_counter = 0
        self._change_subs = []
        self.clipboard = None
        self.paste_count = 0
        self.wire_style = "solid"
        self.current_layer = None
        self.icon_image = None
        self.windows = []
        self.validation = None
        self.last_command = ""
        self.runner = ia.CommandRunner(self)
        self.keymap = KeyMap(self)
        self.recovery = RecoveryManager()
        self._autosave_job = None
        self._load_icon()
        root.title(APP_NAME)
        root.minsize(1000, 620)
        geo = self.settings["geometry"]
        root.geometry(geo if geo else "1500x900")
        self._build()
        self._register_actions()
        self.keymap.bind_all()
        self._bind_keys()
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.refresh(full=True)
        try:
            self.recovery.cleanup()
            orphans = self.recovery.orphans() if check_recovery else []
        except OSError:
            orphans = []
        try:
            self.recovery.start()
        except OSError:
            pass
        self._schedule_autosave()
        if orphans:
            root.after(300, lambda: self._offer_recovery(orphans))
        elif path:
            root.after(80, lambda: self.open_path(path))
        self.log(f"{APP_NAME} {VERSION}. Type a command (HELP lists them) or use the toolbar.", "info")

    def _default_size(self):
        from ..model import SHEET_SIZES_MM
        from ..project import DEFAULT_SHEET_SIZE
        s = self.settings["default_sheet"]
        return s if s in SHEET_SIZES_MM else DEFAULT_SHEET_SIZE

    # ================================================================ construction
    def _load_icon(self):
        try:
            self.icon_image = tk.PhotoImage(file=resource_path("openschematix-64.png"))
            self.root.iconphoto(True, self.icon_image)
        except tk.TclError:
            self.icon_image = None
        if sys.platform.startswith("win"):
            try:
                self.root.iconbitmap(default=resource_path("openschematix.ico"))
            except tk.TclError:
                pass

    def _build(self):
        self.menu_accels = []
        self._build_menu()
        self.toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(8, 4))
        self.toolbar.pack(fill="x")
        self._build_toolbar()
        ttk.Separator(self.root).pack(fill="x")
        # status bar and command line (bottom, packed first so they keep their height)
        self.status_bar = ttk.Frame(self.root, style="Status.TFrame", padding=(10, 3))
        self.status_bar.pack(fill="x", side="bottom")
        self._build_status()
        self.cmd_sep = ttk.Separator(self.root)
        self.cmdline = CommandLine(self.root, self)
        if self.settings["show_command_line"]:
            self.cmdline.pack(fill="x", side="bottom")
            self.cmd_sep.pack(fill="x", side="bottom")
        # main panes
        self.hpane = ttk.PanedWindow(self.root, orient="horizontal")
        self.hpane.pack(fill="both", expand=True)
        self.left = ttk.Notebook(self.hpane, padding=0)
        self.library = LibraryPanel(self.left, self)
        self.project_panel = ProjectPanel(self.left, self)
        self.templates_panel = TemplatesPanel(self.left, self)
        self.left.add(self.library, text="Symbols")
        self.left.add(self.project_panel, text="Sheets")
        self.left.add(self.templates_panel, text="Templates")
        self.center = ttk.Frame(self.hpane, style="Surface.TFrame")
        self.vpane = ttk.PanedWindow(self.center, orient="vertical")
        self.vpane.pack(fill="both", expand=True)
        self.doc_area = ttk.Frame(self.vpane, style="Surface.TFrame")
        self.tabs = ttk.Frame(self.doc_area, style="Raised.TFrame")
        self.tabs.pack(fill="x")
        canvas_holder = ttk.Frame(self.doc_area, style="Surface.TFrame")
        canvas_holder.pack(fill="both", expand=True)
        self.canvas = SchematicCanvas(canvas_holder, self)
        self.canvas.font_family = th.canvas_font_family(self.root)
        self.canvas.pack(fill="both", expand=True)
        self.toasts = ToastHost(canvas_holder)
        self.vpane.add(self.doc_area, weight=5)
        self.dock = ttk.Notebook(self.vpane)
        self.logview = LogView(self.dock)
        self.check_panel = CheckPanel(self.dock, self)
        self.search_panel = SearchPanel(self.dock, self)
        self.dock.add(self.logview, text="Output")
        self.dock.add(self.check_panel, text="Check drawing")
        self.dock.add(self.search_panel, text="Search")
        self.vpane.add(self.dock, weight=1)
        self.right = ttk.Notebook(self.hpane)
        self.inspector = Inspector(self.right, self)
        self.layers_panel = LayersPanel(self.right, self)
        self.right.add(self.inspector, text="Properties")
        self.right.add(self.layers_panel, text="Layers")
        self.hpane.add(self.left, weight=0)
        self.hpane.add(self.center, weight=1)
        self.hpane.add(self.right, weight=0)
        lay = self.settings["layout"]
        self.panel_visible = {"left": lay.get("left", True), "right": lay.get("right", True),
                              "bottom": lay.get("bottom", True)}
        self.root.after(60, self._restore_layout)

    def _restore_layout(self, attempts=0):
        """Apply the saved three-column layout only after Tk has sized the panes.

        On first launch ttk.PanedWindow may still be 1px wide when the
        original 60ms timer fires. Setting sash positions at that point
        can leave the Properties pane occupying nearly the entire window.
        """
        self.root.update_idletasks()
        total = self.hpane.winfo_width()
        height = self.vpane.winfo_height()
        if (total < 900 or height < 300) and attempts < 20:
            self.root.after(100, lambda: self._restore_layout(attempts + 1))
            return
        lay = self.settings["layout"]
        f = th.dpi_factor(self.root)
        if total >= 900:
            left_w = max(180, min(int(lay.get("left_w", 290 * f)), int(total * .30)))
            right_w = max(200, min(int(lay.get("right_w", 310 * f)), int(total * .30)))
            # Keep the drawing canvas wider than either sidebar.
            if left_w + right_w > total - 450:
                right_w = max(200, total - 450 - left_w)
            try:
                self.hpane.sashpos(0, left_w)
                self.hpane.sashpos(1, total - right_w)
            except tk.TclError:
                pass
        if height >= 300:
            bottom_h = max(100, min(int(lay.get("bottom_h", 170 * f)), int(height * .40)))
            try:
                self.vpane.sashpos(0, height - bottom_h)
            except tk.TclError:
                pass
        for side in ("left", "right", "bottom"):
            if not self.panel_visible[side]:
                self.panel_visible[side] = True
                self.toggle_panel(side)

    def _save_layout(self):
        lay = self.settings["layout"]
        try:
            if self.panel_visible["left"]:
                lay["left_w"] = self.hpane.sashpos(0)
            if self.panel_visible["right"]:
                idx = 1 if self.panel_visible["left"] else 0
                lay["right_w"] = self.hpane.winfo_width() - self.hpane.sashpos(idx)
            if self.panel_visible["bottom"]:
                lay["bottom_h"] = self.vpane.winfo_height() - self.vpane.sashpos(0)
        except tk.TclError:
            pass
        lay.update(self.panel_visible)
        self.settings["layout"] = lay

    def toggle_panel(self, side):
        vis = not self.panel_visible[side]
        self.panel_visible[side] = vis
        try:
            if side == "left":
                if vis:
                    self.hpane.insert(0, self.left, weight=0)
                else:
                    self._save_layout_one("left_w", self.hpane.sashpos(0))
                    self.hpane.forget(self.left)
            elif side == "right":
                if vis:
                    self.hpane.add(self.right, weight=0)
                else:
                    self.hpane.forget(self.right)
            else:
                if vis:
                    self.vpane.add(self.dock, weight=1)
                else:
                    self.vpane.forget(self.dock)
        except tk.TclError:
            pass
        self.panel_vars[side].set(vis)
        self.panel_buttons[side].set_checked(vis)
        if vis:
            self.root.after(30, self._apply_sashes)

    def _apply_sashes(self):
        lay = self.settings["layout"]
        f = th.dpi_factor(self.root)
        try:
            self.root.update_idletasks()
            total = self.hpane.winfo_width()
            idx = 0
            lw = int(lay.get("left_w", 290 * f))
            rw = int(lay.get("right_w", 310 * f))
            if self.panel_visible["left"]:
                self.hpane.sashpos(0, lw)
                idx = 1
            if self.panel_visible["right"]:
                self.hpane.sashpos(idx, max((lw if idx else 0) + 400, total - rw))
            if self.panel_visible["bottom"]:
                h = self.vpane.winfo_height()
                self.vpane.sashpos(0, max(200, h - int(lay.get("bottom_h", 170 * f))))
        except tk.TclError:
            pass

    def _save_layout_one(self, key, value):
        lay = self.settings["layout"]
        lay[key] = value
        self.settings["layout"] = lay

    # ---------------------------------------------------------------- menus
    def _add(self, menu, label, command, action=None, **kw):
        acc = self.keymap.accel(action) if action else kw.pop("accelerator", "")
        menu.add_command(label=label, command=command, accelerator=acc, **kw)
        if action:
            self.menu_accels.append((menu, menu.index("end"), action))

    def _build_menu(self):
        m = tk.Menu(self.root)
        self.menubar = m
        f = tk.Menu(m, tearoff=0)
        self._add(f, "New project", self.new, "new")
        f.add_command(label="New from project template…", command=self.new_from_template)
        self._add(f, "Open…", self.open, "open")
        self.recent_menu = tk.Menu(f, tearoff=0)
        f.add_cascade(label="Open recent", menu=self.recent_menu)
        f.add_separator()
        self._add(f, "Save", self.save, "save")
        self._add(f, "Save as…", self.save_as, "save_as")
        f.add_command(label="Save as project template…", command=self.save_project_template)
        f.add_command(label="Close project", command=self.new)
        f.add_separator()
        imp = tk.Menu(f, tearoff=0)
        imp.add_command(label="DXF drawing…", command=self.import_dxf_dialog)
        imp.add_command(label="Sheets from another project…", command=self.import_project_sheets)
        imp.add_command(label="Symbol library package…", command=lambda: self.library.import_package())
        f.add_cascade(label="Import", menu=imp)
        exp = tk.Menu(f, tearoff=0)
        self._add(exp, "PDF (all or selected sheets)…", lambda: self.export_pdf_dialog(), "export_pdf")
        exp.add_command(label="SVG (current sheet)…", command=lambda: self.export_file("svg"))
        exp.add_command(label="DXF (current sheet)…", command=lambda: self.export_file("dxf"))
        exp.add_command(label="Bill of materials (CSV)…", command=self.export_bom_csv)
        exp.add_command(label="Connection list (CSV)…", command=lambda: self.open_reports("connections"))
        exp.add_command(label="Current sheet as legacy single drawing (.osch)…", command=self.export_osch)
        exp.add_command(label="Project as a copy (.schematix)…", command=self.export_project_copy)
        f.add_cascade(label="Export", menu=exp)
        self._add(f, "Print (via PDF viewer)…", self.print_, "print")
        f.add_separator()
        f.add_command(label="Project properties…", command=self.project_properties)
        self._add(f, "Preferences…", self.preferences, "preferences")
        f.add_separator()
        f.add_command(label="Exit", command=self.quit)
        m.add_cascade(label="File", menu=f)
        e = tk.Menu(m, tearoff=0)
        self._add(e, "Undo", self.undo, "undo")
        self._add(e, "Redo", self.redo, "redo")
        e.add_separator()
        self._add(e, "Cut", self.cut, "cut")
        self._add(e, "Copy", self.copy, "copy")
        self._add(e, "Paste", self.paste, "paste")
        self._add(e, "Duplicate", self.duplicate, "duplicate")
        self._add(e, "Delete", self.delete, "delete")
        self._add(e, "Select all", self.select_all, "select_all")
        sf = tk.Menu(e, tearoff=0)
        self.filter_vars = {}
        for k, label in (("component", "Components"), ("wire", "Wires"), ("shape", "Drawing objects")):
            v = tk.BooleanVar(value=k in self.settings["selection_filter"])
            sf.add_checkbutton(label=label, variable=v, command=self._filter_changed)
            self.filter_vars[k] = v
        e.add_cascade(label="Selection filter", menu=sf)
        e.add_separator()
        self._add(e, "Rotate 90° clockwise", lambda: self.rotate(True), "rotate")
        self._add(e, "Rotate 90° counter-clockwise", lambda: self.rotate(False), "rotate_ccw")
        self._add(e, "Mirror", self.mirror, "mirror")
        al = tk.Menu(e, tearoff=0)
        for mode, label in (("left", "Left"), ("center", "Centre"), ("right", "Right"), ("top", "Top"),
                            ("middle", "Middle"), ("bottom", "Bottom")):
            al.add_command(label=label, command=lambda mo=mode: self.align(mo))
        al.add_separator()
        al.add_command(label="Distribute horizontally", command=lambda: self.distribute("h"))
        al.add_command(label="Distribute vertically", command=lambda: self.distribute("v"))
        e.add_cascade(label="Align and distribute", menu=al)
        self._add(e, "Group", self.group_selection, "group")
        self._add(e, "Ungroup", self.ungroup_selection, "ungroup")
        e.add_command(label="Lock selection", command=lambda: self.set_locked(True))
        e.add_command(label="Unlock all on this sheet", command=lambda: self.set_locked(False, everything=True))
        m.add_cascade(label="Edit", menu=e)
        v = tk.Menu(m, tearoff=0)
        v.add_command(label="Zoom in", accelerator="+", command=lambda: self.canvas.zoom_by(1.25))
        v.add_command(label="Zoom out", accelerator="-", command=lambda: self.canvas.zoom_by(0.8))
        self._add(v, "Zoom to drawing", self.canvas_fit_drawing, "zoom_extents")
        self._add(v, "Zoom to sheet", lambda: self.canvas.fit(), "zoom_sheet")
        v.add_separator()
        self.toggle_vars = {}
        for key, label, action in (("show_grid", "Grid", "grid"), ("snap_grid", "Snap to grid", "snap"),
                                   ("ortho", "Ortho", "ortho"), ("osnap", "Object snap", "osnap"),
                                   ("show_markers", "Unconnected-terminal markers", None)):
            var = tk.BooleanVar(value=self.settings[key])
            v.add_checkbutton(label=label, variable=var, command=lambda k=key: self.set_toggle(k, None),
                              accelerator=self.keymap.accel(action) if action else "")
            if action:
                self.menu_accels.append((v, v.index("end"), action))
            self.toggle_vars[key] = var
        v.add_separator()
        self.panel_vars = {}
        for side, label in (("left", "Left sidebar"), ("right", "Properties sidebar"), ("bottom", "Bottom panel")):
            var = tk.BooleanVar(value=True)
            v.add_checkbutton(label=label, variable=var, command=lambda s=side: self.toggle_panel(s))
            self.panel_vars[side] = var
        self.cmd_var = tk.BooleanVar(value=self.settings["show_command_line"])
        v.add_checkbutton(label="Command line", variable=self.cmd_var, command=self.toggle_command_line)
        v.add_command(label="Reset workspace layout", command=self.reset_layout)
        v.add_separator()
        tm = tk.Menu(v, tearoff=0)
        self.theme_var = tk.StringVar(value=self.theme.name)
        for key, t in th.THEMES.items():
            tm.add_radiobutton(label=t["label"], value=key, variable=self.theme_var,
                               command=lambda k=key: self.set_theme(k))
        v.add_cascade(label="Theme", menu=tm)
        m.add_cascade(label="View", menu=v)
        d = tk.Menu(m, tearoff=0)
        d.add_command(label="Select", accelerator="Esc", command=lambda: self.canvas.set_tool("select"))
        d.add_command(label="Wire", accelerator="W", command=lambda: self.canvas.set_tool("wire"))
        d.add_separator()
        for name, label, al_ in (("LINE", "Line", "L"), ("PLINE", "Polyline", "PL"), ("RECTANGLE", "Rectangle", "REC"),
                                 ("CIRCLE", "Circle", "C"), ("ARC", "Arc", "A"), ("TEXT", "Text", "T"),
                                 ("FILL", "Fill (hatch)", "FILL")):
            d.add_command(label=label, accelerator=al_, command=lambda n=name: self.run_command(n))
        d.add_separator()
        for name, label, al_ in (("MOVE", "Move", "M"), ("COPY", "Copy", "CO"), ("ROTATE", "Rotate", "RO"),
                                 ("MIRROR", "Mirror", "MI"), ("SCALE", "Scale", "SC"), ("TRIM", "Trim", "TR"),
                                 ("EXTEND", "Extend", "EX")):
            d.add_command(label=label, accelerator=al_, command=lambda n=name: self.run_command(n))
        d.add_separator()
        d.add_command(label="Connect crossing wires", accelerator="CW", command=lambda: self.run_command("CONNECT"))
        d.add_command(label="Remove junction", accelerator="DW", command=lambda: self.run_command("DISCONNECT"))
        d.add_command(label="Insert symbol by name…", accelerator="I", command=self.insert_symbol_dialog)
        d.add_command(label="Insert template…", command=lambda: self.left.select(self.templates_panel))
        m.add_cascade(label="Draw", menu=d)
        s = tk.Menu(m, tearoff=0)
        s.add_command(label="New sheet", command=self.add_sheet)
        s.add_command(label="New sheet from template…", command=self.add_sheet_from_template)
        s.add_command(label="Duplicate sheet", command=lambda: self.duplicate_sheet(self.doc.uid))
        s.add_command(label="Rename sheet…", command=lambda: self.project_panel.rename())
        s.add_command(label="Delete sheet…", command=lambda: self.delete_sheet(self.doc.uid))
        self._add(s, "Next sheet", lambda: self.step_sheet(1), "next_sheet")
        self._add(s, "Previous sheet", lambda: self.step_sheet(-1), "prev_sheet")
        s.add_separator()
        s.add_command(label="Drawing scale and fit…", command=lambda: ScaleDialog(self))
        s.add_command(label="Fit drawing to sheet", command=self.fit_to_sheet)
        s.add_separator()
        s.add_command(label="Project properties…", command=self.project_properties)
        m.add_cascade(label="Sheet", menu=s)
        t = tk.Menu(m, tearoff=0)
        self._add(t, "Check drawing", self.run_check, "check")
        self._add(t, "Search project…", lambda: self.show_search(), "find")
        t.add_separator()
        self._add(t, "Bill of materials…", self.open_bom, "bom")
        t.add_command(label="Wire numbers…", command=self.wire_number_dialog)
        t.add_command(label="Connection and wire lists…", command=lambda: self.open_reports("connections"))
        t.add_command(label="Terminal strips…", command=lambda: self.open_reports("terminals"))
        t.add_separator()
        t.add_command(label="Revision history…", command=self.open_revisions)
        t.add_command(label="Issue revision…", command=self.issue_revision_dialog)
        t.add_command(label="Compare with a revision…", command=self.open_revisions)
        t.add_separator()
        self._add(t, "Symbol editor…", lambda: self.open_symbol_editor(), "symbol_editor")
        t.add_command(label="Save selection as template…", command=self.save_template_dialog)
        m.add_cascade(label="Tools", menu=t)
        h = tk.Menu(m, tearoff=0)
        self._add(h, "Command reference", lambda: self.execute_input("HELP"), "help")
        h.add_command(label="Keyboard shortcuts…", command=lambda: ShortcutsDialog(self))
        h.add_separator()
        h.add_command(label="Support development…", command=lambda: webbrowser.open(DONATE_URL))
        h.add_command(label=f"About {APP_NAME}", command=lambda: AboutDialog(self))
        m.add_cascade(label="Help", menu=h)
        self.root.config(menu=m)
        th.recolor_menu(m, self.theme)
        self._rebuild_recent()

    def rebuild_menus(self):
        """Update accelerator labels after shortcut changes (menus are never
        replaced, see theme.py)."""
        for menu, idx, action in self.menu_accels:
            try:
                menu.entryconfigure(idx, accelerator=self.keymap.accel(action))
            except tk.TclError:
                pass
        self._rebuild_toolbar_tips()

    # ---------------------------------------------------------------- toolbar
    def _build_toolbar(self):
        tb = self.toolbar
        self.tool_buttons = {}
        # (button, description, keymap action or None, command-line command or None)
        self.tips = []

        def btn(icon, cmd, tip, action=None, checkable=False, key=None, command=None, side="left"):
            b = IconButton(tb, icon, cmd, tip, checkable=checkable)
            b.pack(side=side, padx=1)
            self.tips.append((b, tip, action, command))
            if key:
                self.tool_buttons[key] = b
            return b

        def sep():
            ToolbarSeparator(tb).pack(side="left", padx=7, pady=3)
        btn("new", self.new, "New project", "new", command="NEW")
        btn("open", self.open, "Open a project or drawing", "open", command="OPEN")
        btn("save", self.save, "Save the project", "save", command="SAVE")
        sep()
        self.undo_btn = btn("undo", self.undo, "Undo the last change", "undo", command="UNDO")
        self.redo_btn = btn("redo", self.redo, "Redo the last undone change", "redo", command="REDO")
        sep()
        btn("select", lambda: self.canvas.set_tool("select"), "Select and move objects (Esc)", checkable=True,
            key="select")
        btn("wire", lambda: self.canvas.set_tool("wire"), "Draw wires: click terminals and bend points",
            checkable=True, key="wire", command="WIRE")
        for icon, name in (("line", "LINE"), ("polyline", "PLINE"), ("rect", "RECTANGLE"), ("circle", "CIRCLE"),
                           ("arc", "ARC"), ("text", "TEXT"), ("fill", "FILL")):
            btn(icon, lambda n=name: self.run_command(n), cadcmds.TOOL_TIPS[name], checkable=True, key=name,
                command=name)
        sep()
        for icon, name in (("move", "MOVE"), ("copy", "COPY"), ("rotate", "ROTATE"), ("mirror", "MIRROR"),
                           ("scale", "SCALE"), ("trim", "TRIM"), ("extend", "EXTEND")):
            btn(icon, lambda n=name: self.run_command(n), cadcmds.TOOL_TIPS[name], checkable=True, key=name,
                command=name)
        btn("delete", self.delete, "Delete the selection", "delete", command="ERASE")
        sep()
        btn("connect", lambda: self.run_command("CONNECT"), "Connect crossing wires with a junction",
            checkable=True, key="CONNECT", command="CONNECT")
        btn("bridge", lambda: self.run_command("DISCONNECT"), "Remove a junction", checkable=True,
            key="DISCONNECT", command="DISCONNECT")
        btn("wire_number", self.wire_number_dialog, "Wire numbers…", command="WIRENUMBER")
        sep()
        btn("zoom_in", lambda: self.canvas.zoom_by(1.25), "Zoom in (+)")
        btn("zoom_out", lambda: self.canvas.zoom_by(0.8), "Zoom out (-)")
        btn("zoom_fit", self.canvas_fit_drawing, "Zoom to the whole drawing", "zoom_extents")
        sep()
        btn("search", lambda: self.show_search(), "Search the project", "find", command="SEARCH")
        btn("check", self.run_check, "Check the drawing for errors", "check", command="CHECK")
        btn("bom", self.open_bom, "Bill of materials", "bom", command="BOM")
        btn("revision", self.open_revisions, "Revision history", command="REVISION")
        btn("pdf", lambda: self.export_pdf_dialog(), "Export PDF…", "export_pdf")
        # right side: panel toggles and settings
        self.panel_buttons = {}
        for side, icon, tip, action in (("right", "properties", "Show / hide the properties sidebar", "properties"),
                                        ("bottom", "command", "Show / hide the bottom panel", None),
                                        ("left", "library", "Show / hide the left sidebar", None)):
            b = btn(icon, lambda s=side: self.toggle_panel(s), tip, action, checkable=True, side="right")
            b.set_checked(True)
            self.panel_buttons[side] = b
        ToolbarSeparator(tb).pack(side="right", padx=7, pady=3)
        btn("settings", self.preferences, "Preferences", "preferences", command="PREFERENCES", side="right")
        btn("theme", self.cycle_theme, "Switch to the next colour theme", side="right")
        self._rebuild_toolbar_tips()

    def _rebuild_toolbar_tips(self):
        """(Re)write toolbar tooltips with the current shortcuts and aliases."""
        aliases = self.settings["aliases"]
        for b, tip, action, command in self.tips:
            acc = self.keymap.accel(action) if action else ""
            if command:
                b.set_tooltip(cmdparse.tooltip(command, acc, aliases, summary=tip))
            else:
                b.set_tooltip(f"{tip} ({acc})" if acc else tip)

    # ---------------------------------------------------------------- status bar
    def _build_status(self):
        sb = self.status_bar
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(sb, textvariable=self.status, style="Status.TLabel").pack(side="left", fill="x", expand=True)
        self.check_label = ttk.Label(sb, text="", style="Status.TLabel", cursor="hand2")
        self.check_label.pack(side="right", padx=(8, 0))
        self.check_label.bind("<Button-1>", lambda e: self.run_check())
        Tooltip(self.check_label, "Drawing check results — click to run Check drawing")
        self.zoom_label = ttk.Label(sb, text="100%", style="Status.TLabel", width=6, anchor="e")
        self.zoom_label.pack(side="right")
        self.coord_label = ttk.Label(sb, text="", style="StatusStrong.TLabel", width=24, anchor="e")
        self.coord_label.pack(side="right", padx=6)
        self.scale_label = ttk.Label(sb, text="", style="Status.TLabel", cursor="hand2")
        self.scale_label.pack(side="right", padx=6)
        self.scale_label.bind("<Button-1>", lambda e: ScaleDialog(self))
        Tooltip(self.scale_label, "Print scale of this sheet — click to change or fit")
        self.layer_label = ttk.Label(sb, text="", style="Status.TLabel", cursor="hand2")
        self.layer_label.pack(side="right", padx=6)
        self.layer_label.bind("<Button-1>", lambda e: self.right.select(self.layers_panel))
        self.toggle_labels = {}
        for key, text, tip in (("osnap", "OSNAP", "Object snap (F3)"), ("ortho", "ORTHO", "Ortho (F8)"),
                               ("snap_grid", "SNAP", "Grid snap (F9)"), ("show_grid", "GRID", "Grid (F7)")):
            lab = tk.Label(sb, text=text, padx=6, pady=1, cursor="hand2")
            lab._theme_bg = "status"
            lab.pack(side="right", padx=1)
            lab.bind("<Button-1>", lambda e, k=key: self.set_toggle(k, not self.settings[k]))
            Tooltip(lab, tip)
            self.toggle_labels[key] = lab
        self.conn_label = ttk.Label(sb, text="", style="Status.TLabel")
        self.conn_label.pack(side="right", padx=8)
        th.subscribe(lambda t: self._update_toggles())
        self._update_toggles()

    def _update_toggles(self):
        u = self.theme.ui
        for key, lab in self.toggle_labels.items():
            on = self.settings[key]
            lab.configure(bg=u["accent_soft"] if on else u["status"], fg=u["accent"] if on else u["faint"],
                          font=self.theme.fonts["heading"])
        for key, var in getattr(self, "toggle_vars", {}).items():
            var.set(self.settings[key])

    # ================================================================ actions & keys
    def _register_actions(self):
        km = self.keymap
        for action, fn in {
            "new": self.new, "open": self.open, "save": self.save, "save_as": self.save_as,
            "export_pdf": lambda: self.export_pdf_dialog(), "print": self.print_, "undo": self.undo,
            "redo": self.redo, "redo2": self.redo, "cut": self.cut, "copy": self.copy, "paste": self.paste,
            "duplicate": self.duplicate, "select_all": self.select_all, "delete": self.delete,
            "find": lambda: self.show_search(), "check": self.run_check, "help": lambda: self.execute_input("HELP"),
            "history": lambda: self.show_dock(self.logview), "osnap": lambda: self.set_toggle("osnap", None),
            "grid": lambda: self.set_toggle("show_grid", None), "ortho": lambda: self.set_toggle("ortho", None),
            "snap": lambda: self.set_toggle("snap_grid", None), "rotate": lambda: self.rotate(True),
            "rotate_ccw": lambda: self.rotate(False), "mirror": self.mirror, "zoom_extents": self.canvas_fit_drawing,
            "zoom_sheet": lambda: self.canvas.fit(), "next_sheet": lambda: self.step_sheet(1),
            "prev_sheet": lambda: self.step_sheet(-1), "properties": self.focus_properties,
            "group": self.group_selection, "ungroup": self.ungroup_selection, "bom": self.open_bom,
            "symbol_editor": lambda: self.open_symbol_editor(), "preferences": self.preferences,
        }.items():
            km.register(action, fn)

    def _bind_keys(self):
        r = self.root
        r.bind("<KeyPress>", self._on_key, add="+")
        for seq, fn in (("<Escape>", self._esc), ("<Return>", self._enter_key), ("<KP_Enter>", self._enter_key),
                        ("<Left>", lambda: self.nudge(-GRID, 0)), ("<Right>", lambda: self.nudge(GRID, 0)),
                        ("<Up>", lambda: self.nudge(0, -GRID)), ("<Down>", lambda: self.nudge(0, GRID))):
            r.bind(seq, self._plain_guard(fn))

    def _is_text_widget(self, w):
        return isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text, tk.Spinbox, ttk.Spinbox, tk.Listbox,
                              ttk.Treeview))

    def _plain_guard(self, fn):
        def handler(e):
            if self._is_text_widget(e.widget):
                return None
            try:
                if e.widget.winfo_toplevel() is not self.root:
                    return None
            except (AttributeError, tk.TclError):
                return None
            fn()
            return "break"
        return handler

    def _esc(self):
        self.canvas.escape()

    def _enter_key(self):
        if self.runner.active:
            self.runner.enter()
        elif self.canvas.tool == "wire" and self.canvas.wire_pts:
            self.canvas.finish_wire()
        elif self.last_command:
            self.execute_input(self.last_command)

    def _on_key(self, e):
        w = e.widget
        if self._is_text_widget(w):
            return None
        try:
            if w.winfo_toplevel() is not self.root:
                return None
        except (AttributeError, tk.TclError):
            return None
        if e.state & 0x000C:          # Ctrl / Alt: shortcuts handle these
            return None
        ch = e.char
        if not ch or not ch.isprintable():
            return None
        if self.canvas.tool == "place" and ch in "rRmM":
            if ch in "rR":
                self.canvas.rotate_ghost(ch == "r")
            else:
                self.canvas.mirror_ghost()
            return "break"
        if ch == " ":
            if self.canvas.tool == "wire":
                self.canvas.toggle_bend()
            elif self.runner.active:
                self.runner.enter()
            elif self.last_command:
                self.execute_input(self.last_command)
            return "break"
        if ch in "+=":
            self.canvas.zoom_by(1.25)
            return "break"
        if ch == "-" and not self.runner.active:
            self.canvas.zoom_by(0.8)
            return "break"
        self.cmdline.focus_entry(ch)
        return "break"

    # ================================================================ state helpers
    def snapshot(self) -> str:
        return json.dumps({"p": self.project.to_dict(), "active": self.doc.uid}, sort_keys=True)

    def begin_change(self) -> str:
        return self.snapshot()

    def cancel_change(self, _before):
        pass

    def commit_change(self, before, message: str | None = None):
        if before is None or before == self.snapshot():
            self.refresh()
            return
        self.undo_stack.append(before)
        del self.undo_stack[:-UNDO_LIMIT]
        self.redo_stack.clear()
        self.mark_dirty()
        self.refresh()
        if message:
            self.set_status(message)

    def mark_dirty(self):
        self.dirty = True
        self.change_counter += 1
        self.update_title()

    def _restore(self, state: str):
        d = json.loads(state)
        store = self.project.revisions
        p = Project.from_dict(d["p"])
        p.revisions = store
        self.project = p
        p.activate_symbols()
        self.doc = p.find_sheet(d.get("active")) or p.sheets[0]
        self.selection = {i for i in self.selection if self.doc.item(i) is not None}
        self.mark_dirty()
        self.refresh(full=True)

    def undo(self):
        if self.canvas.drag:
            return
        if self.runner.active:
            self.runner.cancel()
        if not self.undo_stack:
            self.set_status("Nothing to undo.")
            return
        self.redo_stack.append(self.snapshot())
        self._restore(self.undo_stack.pop())
        self.set_status("Undone.")

    def redo(self):
        if not self.redo_stack:
            self.set_status("Nothing to redo.")
            return
        self.undo_stack.append(self.snapshot())
        self._restore(self.redo_stack.pop())
        self.set_status("Redone.")

    def subscribe_changes(self, fn):
        self._change_subs.append(fn)

    def unsubscribe_changes(self, fn):
        if fn in self._change_subs:
            self._change_subs.remove(fn)

    def refresh(self, full=False):
        self.change_counter += 1
        self.update_title()
        self.inspector.refresh()
        self.canvas.redraw()
        self._refresh_tabs()
        self.project_panel.refresh()
        if full:
            self.layers_panel.refresh()
            self.templates_panel.refresh()
        self.layer_label.configure(text=f"Layer: {self.current_layer or 'auto'}")
        self.scale_label.configure(text=f"Scale {self.doc.sheet.scale}")
        self.undo_btn.set_enabled(bool(self.undo_stack))
        self.redo_btn.set_enabled(bool(self.redo_stack))
        for fn in list(self._change_subs):
            try:
                fn()
            except tk.TclError:
                self.unsubscribe_changes(fn)

    def set_status(self, msg: str):
        self.status.set(msg)

    def log(self, msg: str, kind: str = "info"):
        self.logview.add(msg, kind)
        if kind in ("error", "warning"):
            self.set_status(msg)

    def toast(self, msg, kind="info"):
        self.toasts.show(msg, kind)
        self.log(msg, "success" if kind == "success" else kind)

    def show_prompt(self, text):
        self.cmdline.set_prompt(text)

    def update_title(self):
        name = os.path.basename(self.filename) if self.filename else (self.project.meta.get("title") or "Untitled")
        self.root.title(f"{'● ' if self.dirty else ''}{name} — {self.doc.name} — {APP_NAME} {VERSION}")

    def update_zoom_label(self):
        self.zoom_label.configure(text=f"{self.canvas.zoom * 100 / (96 / 25.4 * UNIT_MM):.0f}%")

    def mm_per_unit(self):
        return UNIT_MM

    def to_user(self, p):
        """Model point -> CAD coordinates in mm (origin lower-left of the sheet, Y up)."""
        H = self.doc.sheet.size_units()[1]
        return (round(p[0] * UNIT_MM, 4), round((H - p[1]) * UNIT_MM, 4))

    def to_model(self, p):
        H = self.doc.sheet.size_units()[1]
        return (p[0] / UNIT_MM, H - p[1] / UNIT_MM)

    def show_cursor(self, p):
        if p is None:
            self.coord_label.configure(text="")
        else:
            x, y = self.to_user(p)
            self.coord_label.configure(text=f"X {x:8.2f}   Y {y:8.2f} mm")

    def update_connection_status(self, conn):
        n = len(conn.open_wire_ends)
        self.conn_label.configure(text=f"⚠ {n} open wire end{'s' if n != 1 else ''}" if n else "")

    def set_validation(self, s):
        self.validation = s
        if s is None:
            self.check_label.configure(text="")
            return
        if s["error"]:
            txt, style = f"✖ {s['error']} errors · {s['warning']} warnings", "Danger.TLabel"
        elif s["warning"]:
            txt, style = f"▲ {s['warning']} warnings", "Warning.TLabel"
        else:
            txt, style = "✔ Checks passed", "Success.TLabel"
        self.check_label.configure(text=txt, style=style.replace(".TLabel", ".TLabel"))

    def on_tool_changed(self, tool):
        for k, b in self.tool_buttons.items():
            active = (k == tool) or (tool == "command" and self.runner.name == k)
            b.set_checked(active)
        if tool == "wire":
            self.set_status("Wire: click a terminal or grid point to start; Space flips the bend; Enter or "
                            "double-click finishes.")
        elif tool == "select":
            self.set_status("Select: click, or drag a window (drag right: fully inside; drag left: crossing). "
                            "Type a command at any time.")

    def set_selection(self, sel):
        self.selection = set(sel)
        self.inspector.refresh()
        self.canvas.redraw()

    def focus_properties(self):
        if not self.panel_visible["right"]:
            self.toggle_panel("right")
        self.right.select(self.inspector)
        self.inspector.focus_first()

    def show_dock(self, panel):
        if not self.panel_visible["bottom"]:
            self.toggle_panel("bottom")
        self.dock.select(panel)

    def is_selectable(self, o) -> bool:
        lay = self.project.layer(o.layer)
        if lay is not None and (not lay.visible or lay.locked):
            return False
        kind = "component" if isinstance(o, Component) else "wire" if isinstance(o, Wire) else "shape"
        return kind in self.settings["selection_filter"]

    def _filter_changed(self):
        self.settings["selection_filter"] = [k for k, v in self.filter_vars.items() if v.get()]
        self.selection = {i for i in self.selection if self.doc.item(i) and self.is_selectable(self.doc.item(i))}
        self.refresh()

    def layer_for(self, kind):
        if self.current_layer and self.project.layer(self.current_layer):
            return self.current_layer
        from ..model import DEFAULT_LAYER_COMPONENTS, DEFAULT_LAYER_SHAPES, DEFAULT_LAYER_WIRES
        return {"component": DEFAULT_LAYER_COMPONENTS, "wire": DEFAULT_LAYER_WIRES}.get(kind, DEFAULT_LAYER_SHAPES)

    def new_shape_layer(self):
        return self.layer_for("shape")

    def note_symbol_used(self, sid):
        add_recent_symbol(self.settings, sid)

    # ================================================================ commands
    def execute_input(self, text: str):
        if self.runner.active:
            if not self.runner.text(text):
                self.log(f"Not understood: {text}", "warning")
            return
        text = text.strip()
        if not text:
            if self.last_command:
                text = self.last_command
            else:
                return
        word, args = cmdparse.split(text)
        name = cmdparse.resolve(word, self.settings["aliases"])
        self.logview.add(f"› {text}", "cmd")
        if name is None:
            self.log(f"Unknown command “{word}”. Type HELP for a list.", "error")
            return
        self.last_command = text if name not in ("UNDO", "REDO", "HELP") else self.last_command
        self.run_command(name, args)

    def run_command(self, name, args="", **kw):
        name = name.upper()
        try:
            handler = getattr(self, "cmd_" + name.lower(), None)
            if name in cadcmds.DRAW_COMMANDS:
                if self.canvas.tool not in ("select", "command"):
                    self.canvas.set_tool("select")
                self.runner.start(name, cadcmds.DRAW_COMMANDS[name](self))
                self.canvas.focus_set()
            elif handler is not None:
                handler(args, **kw)
            else:
                self.log(f"{name} is not available here.", "warning")
        except (ValueError, KeyError, cmdparse.ParseError) as e:
            self.log(f"{name}: {e}", "error")

    # simple command handlers --------------------------------------------------
    def cmd_wire(self, args):
        self.canvas.set_tool("wire")

    def cmd_undo(self, args):
        self.undo()

    def cmd_redo(self, args):
        self.redo()

    def cmd_selectall(self, args):
        self.select_all()

    def cmd_group(self, args):
        self.group_selection()

    def cmd_ungroup(self, args):
        self.ungroup_selection()

    def cmd_lock(self, args):
        self.set_locked(True)

    def cmd_unlock(self, args):
        self.set_locked(False, everything=True)

    def cmd_align(self, args):
        mode = args.strip().lower() or "left"
        if mode not in editing.ALIGN_MODES:
            raise ValueError("use left, center, right, top, middle or bottom")
        self.align(mode)

    def cmd_distribute(self, args):
        self.distribute("v" if args.strip().lower().startswith("v") else "h")

    def cmd_connect(self, args):
        self.runner.start("CONNECT", self._gen_connect())

    def cmd_disconnect(self, args):
        self.runner.start("DISCONNECT", self._gen_disconnect())

    def _gen_connect(self):
        n = 0
        while True:
            p = yield ia.GetPoint("Click a wire crossing to connect it (Enter to finish)", allow_enter=True,
                                  snap_grid=True)
            if p is None or isinstance(p, ia.Answer):
                break
            if editing.connect_crossing(self.doc, p, tol=6 / self.canvas.zoom):
                n += 1
                self.canvas.redraw()
            else:
                self.log("No unconnected crossing there.", "warning")
        return f"{n} crossing(s) connected."

    def _gen_disconnect(self):
        n = 0
        while True:
            p = yield ia.GetPoint("Click a junction dot to remove it (Enter to finish)", allow_enter=True,
                                  snap_grid=True)
            if p is None or isinstance(p, ia.Answer):
                break
            msg = editing.disconnect_junction(self.doc, (snap(p[0]), snap(p[1])))
            if msg:
                n += 1
                self.log(msg)
                self.canvas.redraw()
            else:
                self.log("No junction there.", "warning")
        return f"{n} junction(s) removed."

    def cmd_insert(self, args):
        q = args.strip()
        if not q:
            self.insert_symbol_dialog()
            return
        import re
        hits = [s for s in symbols.search(q) if s.group != "Internal"]
        exact = [s for s in hits if s.name.lower() == q.lower() or s.id == q]
        if exact or hits:
            sd = (exact or hits)[0]
            self.start_place(sd.id)
            if len(hits) > 1 and not exact:
                self.log(f"INSERT: {len(hits)} symbols match “{q}”; placing “{sd.name}”. Refine the name to choose "
                         "another.")
            return
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", q)
        if m:
            prefix = m.group(1).upper()
            cands = [s for s in symbols.all_symbols() if s.prefix.upper() == prefix and s.group != "Internal"]
            pref = {"K": "el.coil.iec", "S": "el.pushbutton.no.iec", "F": "el.fuse.iec", "H": "el.lamp.iec",
                    "M": "el.motor", "Q": "el.breaker.iec", "X": "el.terminal", "R": "el.resistor.iec",
                    "V": "fl.hyd.dcv", "A": "fl.hyd.cyl.double", "P": "fl.hyd.pump"}
            sid = pref.get(prefix) if pref.get(prefix) in {c.id for c in cands} else (cands[0].id if cands else None)
            if sid:
                self.start_place(sid, designator=q.upper())
                return
        raise ValueError(f"no symbol matches “{q}”")

    def cmd_template(self, args):
        q = args.strip().lower()
        if q:
            for _k, _f, tpl in self.templates.items():
                if q in tpl["name"].lower():
                    self.start_template(tpl)
                    return
        if not self.panel_visible["left"]:
            self.toggle_panel("left")
        self.left.select(self.templates_panel)

    def cmd_properties(self, args):
        self.focus_properties()

    def cmd_zoom(self, args):
        a = args.strip().upper()
        if a in ("", "E", "EXTENTS"):
            self.canvas_fit_drawing()
        elif a in ("S", "SHEET", "A", "ALL"):
            self.canvas.fit()
        elif a == "IN":
            self.canvas.zoom_by(1.5)
        elif a == "OUT":
            self.canvas.zoom_by(1 / 1.5)
        else:
            self.canvas.zoom_by(cmdparse.parse_scale_factor(a.rstrip("X")))

    def cmd_pan(self, args):
        x, y = cmdparse.parse_point(args)
        self.canvas.pan(x / UNIT_MM * self.canvas.zoom, -y / UNIT_MM * self.canvas.zoom)

    def _onoff(self, key, args):
        a = args.strip().lower()
        self.set_toggle(key, True if a == "on" else False if a == "off" else None)

    def cmd_grid(self, args):
        self._onoff("show_grid", args)

    def cmd_snap(self, args):
        self._onoff("snap_grid", args)

    def cmd_ortho(self, args):
        self._onoff("ortho", args)

    def cmd_osnap(self, args):
        self._onoff("osnap", args)

    def cmd_layer(self, args):
        name = args.strip()
        if name:
            if self.project.layer(name) is None:
                raise ValueError(f"no layer named “{name}”")
            self.current_layer = name
            self.layers_panel.refresh()
            self.refresh()
            self.log(f"Current layer: {name}")
        else:
            if not self.panel_visible["right"]:
                self.toggle_panel("right")
            self.right.select(self.layers_panel)

    def cmd_theme(self, args):
        a = args.strip().lower().replace(" ", "_")
        for k, t in th.THEMES.items():
            if a in (k, t["label"].lower().replace(" ", "_")) or (a and k.startswith(a)):
                self.set_theme(k)
                return
        raise ValueError("themes: " + ", ".join(t["label"] for t in th.THEMES.values()))

    def cmd_new(self, args):
        self.new()

    def cmd_open(self, args):
        self.open()

    def cmd_save(self, args):
        self.save()

    def cmd_saveas(self, args):
        self.save_as()

    def cmd_sheet(self, args):
        a = args.strip()
        al = a.lower()
        if al in ("", "new", "add"):
            self.add_sheet()
        elif al == "next":
            self.step_sheet(1)
        elif al in ("prev", "previous"):
            self.step_sheet(-1)
        elif al == "delete":
            self.delete_sheet(self.doc.uid)
        elif al.startswith("rename"):
            self.rename_sheet(self.doc.uid, a[6:].strip() or simpledialog.askstring("Rename", "Sheet name:",
                                                                                  parent=self.root) or self.doc.name)
        elif al.isdigit():
            i = int(al) - 1
            if not 0 <= i < len(self.project.sheets):
                raise ValueError(f"there are {len(self.project.sheets)} sheets")
            self.set_active_sheet(self.project.sheets[i].uid)
        else:
            raise ValueError("use SHEET new | next | prev | <number> | delete | rename <name>")

    def cmd_search(self, args):
        self.show_search(args.strip() or None)

    def cmd_bom(self, args):
        self.open_bom()

    def cmd_wirelist(self, args):
        self.open_reports("connections")

    def cmd_terminals(self, args):
        self.open_reports("terminals")

    def cmd_wirenumber(self, args):
        if args.strip().lower().startswith("renum"):
            self.number_wires(None, True)
        elif args.strip():
            self.number_wires(None, False)
        else:
            self.wire_number_dialog()

    def cmd_check(self, args):
        self.run_check()

    def cmd_export(self, args):
        a = args.strip().upper()
        if a in ("", "PDF"):
            self.export_pdf_dialog()
        elif a == "SVG":
            self.export_file("svg")
        elif a == "DXF":
            self.export_file("dxf")
        elif a == "BOM":
            self.export_bom_csv()
        elif a in ("WIRELIST", "CONNECTIONS", "CSV"):
            self.open_reports("connections")
        else:
            raise ValueError("use EXPORT PDF | SVG | DXF | BOM | WIRELIST")

    def cmd_import(self, args):
        self.import_dxf_dialog()

    def cmd_fit(self, args):
        self.fit_to_sheet()

    def cmd_plotscale(self, args):
        if not args.strip():
            ScaleDialog(self)
        else:
            self.set_plot_scale(args.strip())

    def cmd_revision(self, args):
        self.open_revisions()

    def cmd_compare(self, args):
        self.open_revisions()

    def cmd_symbol(self, args):
        self.open_symbol_editor()

    def cmd_preferences(self, args):
        self.preferences()

    def cmd_help(self, args):
        self.show_dock(self.logview)
        if args.strip():
            self.log(cmdparse.help_text(args.strip()))
            return
        cats = {}
        for c in cmdparse.COMMANDS:
            cats.setdefault(c.category, []).append(c)
        for cat, lst in cats.items():
            self.log(f"{cat}: " + "   ".join(f"{c.name}" + (f" ({'/'.join(c.aliases)})" if c.aliases else "")
                                              for c in lst))
        self.log("Points: x,y  |  @dx,dy  |  @distance<angle  (mm, origin at the sheet's lower-left corner). "
                 "HELP <command> for details.")

    def cmd_scaledrawing(self, args, factor=1.0, ids=None):
        def gen():
            p = yield ia.GetPoint(f"Pick the reference point for scaling by {factor:g}")
            if p is None:
                return "Cancelled."
            editing.scale_geometry(self.doc, factor, p, ids)
            return f"Drawing layout scaled by {factor:g}."
        self.runner.start("SCALE", gen())

    # ================================================================ cadcmds host hooks
    def sel_bbox(self, ids):
        return editing.selection_bbox(self.doc, ids)

    def runner_last_was_typed(self):
        return self.runner.typed

    def rotation_step(self, ids):
        return 90 if any(i in self.doc.components or i in self.doc.wires for i in ids) else 0

    def cut_edges(self):
        return list(self.doc.shapes.values()) + [editing.wire_as_shape(w) for w in self.doc.wires.values()]

    def fill_boundary_shapes(self):
        """Drafting shapes that can bound a FILL: those on visible layers.
        Wires and symbols are not boundaries (a fill under a circuit is not
        cut up by its wiring); existing fills and text are ignored."""
        def visible(name):
            lay = self.project.layer(name)
            return lay is None or lay.visible
        return [s for s in self.doc.shapes.values() if s.kind not in ("hatch", "text") and visible(s.layer)]

    def refresh_view(self):
        self.canvas.redraw()

    def _temp_copy(self, ids):
        from ..model import Document
        d = Document()
        d.sheet = self.doc.sheet
        editing.paste(d, editing.copy_items(self.doc, ids), 0, 0)
        return d

    def sel_ghost(self, ids, op):
        from ..render import scene
        if len(ids) > 250:
            b = self.sel_bbox(ids)
            if not b:
                return []
            pts = [cadcmds.transform_point(p, op) for p in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
            return [{"k": "poly", "pts": pts, "fill": False, "role": "ghost", "item": None}]
        d = self._temp_copy(ids)
        try:
            self._apply_op(d, set(d.all_ids()), op)
        except ValueError:
            pass
        return scene(d, screen=False, frame=False)

    def _apply_op(self, d, ids, op):
        c, w, s = editing.split_ids(d, ids)
        if op[0] == "move":
            dx, dy = op[1], op[2]
            if c or w:
                dx, dy = snap(dx), snap(dy)
            editing.move_items(d, c, w, dx, dy, s)
        elif op[0] == "rotate":
            center, ang = op[1], op[2]
            if c or w:
                n = int(round(ang / 90.0)) % 4
                if abs(ang - round(ang / 90.0) * 90) > 1e-6:
                    raise ValueError("symbols and wires can only be rotated in steps of 90°")
                ctr = (snap(center[0]), snap(center[1]))
                for _ in range(n):
                    editing.rotate_items(d, c, w, clockwise=False, shape_ids=s, center=ctr)
            else:
                editing.rotate_shapes_by(d, s, center, -ang)
        elif op[0] == "scale":
            center, k = op[1], op[2]
            from ..shapes import scale_shape
            for i in s:
                scale_shape(d.shapes[i], center, k)
            if c or w:
                editing.scale_geometry(d, k, center, set(c) | set(w))
        elif op[0] == "mirror":
            p, q = op[1], op[2]
            if c or w:
                if abs(p[0] - q[0]) < 1e-6:
                    editing.mirror_items(d, c, w, s, center=(snap(p[0]), snap(p[1])))
                elif abs(p[1] - q[1]) < 1e-6:
                    ctr = (snap(p[0]), snap(p[1]))
                    editing.mirror_items(d, c, w, s, center=ctr)
                    editing.rotate_items(d, c, w, True, s, center=ctr)
                    editing.rotate_items(d, c, w, True, s, center=ctr)
                else:
                    raise ValueError("symbols and wires can only be mirrored about a horizontal or vertical line")
            else:
                from ..shapes import mirror_shape
                for i in s:
                    mirror_shape(d.shapes[i], p, q)

    def sel_move(self, ids, dx, dy):
        self._apply_op(self.doc, set(ids), ("move", dx, dy))

    def sel_copy(self, ids, dx, dy):
        c, w, _s = editing.split_ids(self.doc, ids)
        if c or w:
            dx, dy = snap(dx), snap(dy)
        new = editing.paste(self.doc, editing.copy_items(self.doc, ids), dx, dy)
        self.canvas.redraw()
        return set(new)

    def sel_rotate(self, ids, center, deg_ccw):
        try:
            self._apply_op(self.doc, set(ids), ("rotate", center, deg_ccw))
        except ValueError as e:
            return str(e)

    def sel_scale(self, ids, center, k):
        self._apply_op(self.doc, set(ids), ("scale", center, k))
        if any(i in self.doc.components for i in ids):
            self.log("Symbols keep their size; their positions were scaled and connections kept.")

    def sel_mirror(self, ids, p, q):
        try:
            self._apply_op(self.doc, set(ids), ("mirror", p, q))
        except ValueError as e:
            return str(e)

    def sel_delete(self, ids):
        editing.delete_items(self.doc, ids)
        self.selection = set()

    # ================================================================ editing
    def start_place(self, symbol_id, designator=None):
        self.set_selection(set())
        sd = symbols.get(symbol_id)
        if sd is None:
            return
        self.canvas.set_tool("place", symbol_id)
        self._pending_designator = designator
        self.set_status(f"Placing {sd.name}: click to place, R rotate, M mirror, Esc to finish.")
        self.canvas.focus_set()

    def place_at(self, symbol_id, p):
        s = self.begin_change()
        comp = editing.place(self.doc, symbol_id, *p, layer=self.layer_for("component"))
        self.note_symbol_used(symbol_id)
        self.selection = {comp.id}
        self.commit_change(s, f"Placed {comp.tag() if comp.designator else symbols.get(symbol_id).name}.")

    def start_template(self, tpl):
        self.set_selection(set())
        self.canvas.set_tool("template", template=tpl)
        self.set_status(f"Inserting template “{tpl['name']}”: click to place it (Esc cancels). New identifiers are "
                        "assigned automatically.")
        self.canvas.focus_set()

    def _sel_split(self, movable=True):
        ids = [i for i in self.selection if not (movable and getattr(self.doc.item(i), "locked", False))]
        return editing.split_ids(self.doc, ids)

    def rotate(self, cw=True):
        if self.canvas.tool == "place":
            self.canvas.rotate_ghost(cw)
            return
        c, w, s = self._sel_split()
        if not (c or w or s):
            return
        snap_ = self.begin_change()
        editing.rotate_items(self.doc, c, w, cw, s)
        self.commit_change(snap_, "Rotated.")

    def mirror(self):
        if self.canvas.tool == "place":
            self.canvas.mirror_ghost()
            return
        c, w, s = self._sel_split()
        if not (c or w or s):
            return
        snap_ = self.begin_change()
        editing.mirror_items(self.doc, c, w, s)
        self.commit_change(snap_, "Mirrored.")

    def nudge(self, dx, dy):
        c, w, s = self._sel_split()
        if not (c or w or s):
            self.canvas.pan(dx * 4 * self.canvas.zoom, dy * 4 * self.canvas.zoom)
            return
        snap_ = self.begin_change()
        editing.move_items(self.doc, c, w, dx, dy, s)
        self.commit_change(snap_, "Moved.")

    def delete(self):
        ids = [i for i in self.selection if not getattr(self.doc.item(i), "locked", False)]
        if not ids:
            if self.selection:
                self.set_status("The selection is locked.")
            return
        s = self.begin_change()
        editing.delete_items(self.doc, ids)
        self.selection = set()
        self.commit_change(s, f"Deleted {len(ids)} object(s).")

    def copy(self):
        if not self.selection:
            return
        self.clipboard = editing.copy_items(self.doc, self.selection)
        self.paste_count = 0
        self.set_status(f"Copied {len(self.clipboard['components'])} component(s), {len(self.clipboard['wires'])} "
                        f"wire(s), {len(self.clipboard['shapes'])} drawing object(s).")

    def cut(self):
        if self.selection:
            self.copy()
            self.delete()

    def paste(self):
        if not self.clipboard:
            return
        self.paste_count += 1
        s = self.begin_change()
        new = editing.paste(self.doc, self.clipboard, 2 * GRID * self.paste_count, 2 * GRID * self.paste_count)
        self.selection = set(new)
        self.commit_change(s, f"Pasted {len(new)} object(s). Drag them into place.")

    def duplicate(self):
        if self.selection:
            self.copy()
            self.paste()

    def select_all(self):
        self.set_selection({i for i in self.doc.all_ids() if self.is_selectable(self.doc.item(i))})

    def group_selection(self):
        if len(self.selection) < 2:
            self.set_status("Select two or more objects to group.")
            return
        s = self.begin_change()
        editing.group_items(self.doc, self.selection)
        self.commit_change(s, "Grouped: clicking any member selects the whole group.")

    def ungroup_selection(self):
        s = self.begin_change()
        editing.ungroup_items(self.doc, self.selection)
        self.commit_change(s, "Ungrouped.")

    def set_locked(self, locked, everything=False):
        ids = self.doc.all_ids() if everything else self.selection
        s = self.begin_change()
        for i in ids:
            o = self.doc.item(i)
            if o is not None:
                o.locked = locked
        self.commit_change(s, "Locked." if locked else "Unlocked.")

    def align(self, mode):
        s = self.begin_change()
        editing.align_items(self.doc, self.selection, mode)
        self.commit_change(s, f"Aligned {mode}.")

    def distribute(self, axis):
        s = self.begin_change()
        editing.distribute_items(self.doc, self.selection, axis)
        self.commit_change(s, "Distributed.")

    def edit_components(self, comps, **kw):
        s = self.begin_change()
        for c in comps:
            if c.id not in self.doc.components:
                continue
            if "designator" in kw:
                c.designator = kw["designator"]
            if "label" in kw:
                c.label = kw["label"]
            if "rotation" in kw:
                c.rotation = norm_rotation(kw["rotation"])
            if "mirror" in kw:
                c.mirror = bool(kw["mirror"])
            if "text_side" in kw:
                c.text_side = kw["text_side"]
            if "params" in kw:
                c.params = kw["params"]
            if "in_bom" in kw:
                c.in_bom = bool(kw["in_bom"])
            for k, v in (kw.get("props") or {}).items():
                if v:
                    c.props[k] = v
                else:
                    c.props.pop(k, None)
            if "remove_prop" in kw:
                c.props.pop(kw["remove_prop"], None)
            if "terminal_label" in kw:
                n, v = kw["terminal_label"]
                if v:
                    c.terminal_labels[n] = v
                else:
                    c.terminal_labels.pop(n, None)
        editing.sync_wire_ends(self.doc)
        editing.attach_touching_wires(self.doc, [c.id for c in comps])
        self.commit_change(s, "Properties updated.")
        if "designator" in kw and kw["designator"]:
            from .. import check
            dups = [i for i in check.check(self.project, rules={"duplicate-id"})]
            if dups:
                self.log(f"Note: identifier {kw['designator']} is now used by identical components "
                         "(see Check drawing).", "warning")

    def edit_objects(self, objs, **kw):
        s = self.begin_change()
        for o in objs:
            for k, v in kw.items():
                if k == "props":
                    for pk, pv in v.items():
                        if pv:
                            o.props[pk] = pv
                        else:
                            o.props.pop(pk, None)
                elif hasattr(o, k):
                    setattr(o, k, v)
        self.commit_change(s, "Properties updated.")
        if "layer" in kw or "locked" in kw:
            self.layers_panel.refresh()

    def move_component_to(self, comp, x=None, y=None):
        ux, uy = self.to_user((comp.x, comp.y))
        nx, ny = self.to_model((ux if x is None else x, uy if y is None else y))
        s = self.begin_change()
        editing.move_items(self.doc, [comp.id], [], snap(nx) - comp.x, snap(ny) - comp.y)
        self.commit_change(s, "Moved.")

    def add_custom_property(self, comps):
        key = simpledialog.askstring("Custom property", "Property name (e.g. Location, IP rating):", parent=self.root)
        if not key or not key.strip():
            return
        val = simpledialog.askstring("Custom property", f"Value of “{key.strip()}”:", parent=self.root)
        if val is None:
            return
        self.edit_components(comps, props={key.strip(): val})

    def replace_symbol(self, comps):
        sid = SymbolPickerDialog(self, "Replace symbol").result
        if not sid:
            return
        s = self.begin_change()
        sd = symbols.get(sid)
        for c in comps:
            c.symbol = sid
            c.params = dict(sd.default_params)
        editing.sync_wire_ends(self.doc)
        self.commit_change(s, f"Symbol replaced by {sd.name}. Wires to terminals that no longer exist were "
                              "detached.")

    def configure_valve(self, cid):
        ValveDialog(self, cid)

    def set_wire_number(self, wire, number):
        s = self.begin_change()
        netlist.set_net_number(self.project, self.doc.uid, wire.id, number)
        self.commit_change(s, f"Wire number set to {number} for the whole connection." if number else
                              "Manual wire number removed.")

    def edit_text_shape(self, sid):
        sh = self.doc.shapes[sid]
        d = TextDialog(self, "Edit text", "Text:", sh.s)
        if d.result is not None and d.result != sh.s:
            self.edit_objects([sh], s=d.result)

    # ---------------------------------------------------------------- sheet / project
    def set_sheet(self, **kw):
        s = self.begin_change()
        for k, v in kw.items():
            setattr(self.doc.sheet, k, v)
        self.commit_change(s, "Sheet updated.")

    def set_plot_scale(self, text):
        try:
            f = parse_scale(text)
        except ValueError:
            self.log(f"“{text}” is not a scale (use e.g. 1:2).", "error")
            return
        self.set_sheet(scale=format_scale(f))
        self.canvas.fit()

    def fit_to_sheet(self):
        if self.doc.bbox() is None:
            self.set_status("The sheet is empty.")
            return
        s = self.begin_change()
        sc = editing.fit_to_sheet(self.doc)
        self.commit_change(s, f"Print scale set to {sc} and the drawing centred on the sheet.")
        self.canvas.fit()

    def scale_geometry(self, factor, ref="center", ids=None):
        s = self.begin_change()
        b = editing.selection_bbox(self.doc, ids) if ids else self.doc.bbox()
        if b is None:
            return
        p = (0.0, 0.0) if ref == "origin" else (snap((b[0] + b[2]) / 2), snap((b[1] + b[3]) / 2))
        editing.scale_geometry(self.doc, factor, p, ids)
        self.commit_change(s, f"Drawing layout scaled by {factor:g}; symbols keep their size.")

    def project_properties(self):
        ProjectDialog(self)

    def update_project(self, meta, settings):
        s = self.begin_change()
        self.project.meta.update(meta)
        self.project.settings.update(settings)
        self.commit_change(s, "Project properties updated.")

    def set_project_setting(self, key, value):
        s = self.begin_change()
        self.project.settings[key] = value
        self.commit_change(s)

    def _refresh_tabs(self):
        for w in self.tabs.winfo_children():
            w.destroy()
        u = self.theme.ui
        f = self.theme.fonts
        for i, d in enumerate(self.project.sheets, 1):
            active = d is self.doc
            lab = tk.Label(self.tabs, text=f"  {i}. {d.name}  ", padx=8, pady=5, cursor="hand2",
                           bg=u["tab_active"] if active else u["surface2"], fg=u["text"] if active else u["muted"],
                           font=f["bold"] if active else f["ui"], bd=0)
            lab.pack(side="left")
            if active:
                bar = tk.Frame(lab, bg=u["accent"], height=2)
                bar.place(relx=0, rely=1.0, relwidth=1, anchor="sw")
            lab.bind("<Button-1>", lambda e, uid=d.uid: self.set_active_sheet(uid))
            lab.bind("<Double-1>", lambda e: self.project_panel.rename())
            lab.bind("<ButtonPress-3>", lambda e, uid=d.uid: self._tab_menu(e, uid))
            tk.Frame(self.tabs, bg=u["border"], width=1).pack(side="left", fill="y")
        add = IconButton(self.tabs, "plus", self.add_sheet, "New sheet", size=14, bg_key="surface2", pad=5)
        add.pack(side="left", padx=4)
        self.tabs.configure(style="Raised.TFrame")

    def _tab_menu(self, e, uid):
        self.set_active_sheet(uid)
        m = make_menu(self.root)
        m.add_command(label="Rename…", command=self.project_panel.rename)
        m.add_command(label="Duplicate", command=lambda: self.duplicate_sheet(uid))
        m.add_command(label="Move left", command=lambda: self.move_sheet(uid, -1))
        m.add_command(label="Move right", command=lambda: self.move_sheet(uid, 1))
        m.add_separator()
        m.add_command(label="Delete…", command=lambda: self.delete_sheet(uid))
        m.tk_popup(e.x_root, e.y_root)

    def set_active_sheet(self, uid):
        d = self.project.find_sheet(uid)
        if d is None or d is self.doc:
            return
        if self.runner.active:
            self.runner.cancel()
        self.canvas.set_tool("select")
        self.doc = d
        self.selection = set()
        self.canvas._fitted = True
        self.refresh()
        self.canvas.fit()
        self.set_status(f"Sheet {self.project.sheet_number(d)}: {d.name}")

    def step_sheet(self, delta):
        i = self.project.sheets.index(self.doc)
        j = max(0, min(len(self.project.sheets) - 1, i + delta))
        self.set_active_sheet(self.project.sheets[j].uid)

    def add_sheet(self):
        s = self.begin_change()
        d = self.project.add_sheet(index=self.project.sheets.index(self.doc) + 1)
        self.commit_change(s, f"Added {d.name}.")
        self.set_active_sheet(d.uid)

    def add_sheet_from_template(self):
        """A sheet template is an existing sheet whose page setup (size, orientation,
        title block, zones, scale and title-block fields) is reused, without its content."""
        from .dialogs import ChoiceDialog
        names = [f"{i}. {d.name}" for i, d in enumerate(self.project.sheets, 1)]
        choice = ChoiceDialog(self, "New sheet from template", "Use the page setup of:", names).result
        if not choice:
            return
        src = self.project.sheets[names.index(choice)]
        s = self.begin_change()
        d = self.project.add_sheet(index=self.project.sheets.index(self.doc) + 1, template=src)
        self.commit_change(s, f"Added {d.name} with the page setup of {src.name}.")
        self.set_active_sheet(d.uid)

    # ---------------------------------------------------------------- project templates
    def _project_template_dir(self):
        from ..settings import config_dir
        return os.path.join(config_dir(), "project_templates")

    def save_project_template(self):
        name = simpledialog.askstring("Save as project template", "Template name:",
                                      initialvalue=self.project.meta.get("title") or "My template", parent=self.root)
        if not name or not name.strip():
            return
        from ..revisions import RevisionStore
        from ..userlib import safe_name
        p = self.project.copy()
        p.revisions = RevisionStore()
        d = self._project_template_dir()
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, safe_name(name.strip()) + PROJECT_EXTENSION)
        projectio.atomic_write_bytes(path, projectio.project_bytes(p))
        self.toast(f"Project template “{name.strip()}” saved.", "success")

    def new_from_template(self):
        from .dialogs import ChoiceDialog
        d = self._project_template_dir()
        builtins = {"Blank — A3 landscape, standard title block": ("A3", "landscape", "standard"),
                    "Blank — A4 landscape, compact title block": ("A4", "landscape", "compact"),
                    "Blank — A4 portrait, standard title block": ("A4", "portrait", "standard"),
                    "Blank — ANSI B (11×17 in), standard title block": ("ANSI B", "landscape", "standard"),
                    "Blank — A3 landscape, ISO 7200 style title block": ("A3", "landscape", "iso")}
        user = sorted(f for f in os.listdir(d) if f.endswith(PROJECT_EXTENSION)) if os.path.isdir(d) else []
        options = list(builtins) + [os.path.splitext(f)[0] for f in user]
        choice = ChoiceDialog(self, "New from template", "Project template:", options).result
        if not choice or not self.confirm_discard():
            return
        if choice in builtins:
            size, orient, tb = builtins[choice]
            p = new_project(size=size)
            p.sheets[0].sheet.orientation = orient
            p.sheets[0].sheet.title_block = tb
        else:
            try:
                p = projectio.open_any(os.path.join(d, choice + PROJECT_EXTENSION)).project
            except (OSError, projectio.ProjectFormatError) as e:
                messagebox.showerror("Template", str(e), parent=self.root)
                return
            from ..model import new_uid
            from ..revisions import RevisionStore
            p.uid = new_uid()
            p.revisions = RevisionStore()
            import datetime as _dt
            p.meta["date"] = _dt.date.today().isoformat()
            p.meta["revision"] = ""
        p.activate_symbols()
        self._reset(p, None)
        self.dirty = True
        self.update_title()
        self.canvas.fit()
        self.set_status(f"New project from template “{choice}”.")

    def duplicate_sheet(self, uid):
        s = self.begin_change()
        d = self.project.duplicate_sheet(uid)
        self.commit_change(s, f"Duplicated as {d.name} (components got new identifiers).")
        self.set_active_sheet(d.uid)

    def rename_sheet(self, uid, name):
        try:
            s = self.begin_change()
            self.project.rename_sheet(uid, name)
            self.commit_change(s, "Sheet renamed.")
        except ValueError as e:
            self.log(str(e), "error")

    def move_sheet(self, uid, delta):
        i = [d.uid for d in self.project.sheets].index(uid)
        s = self.begin_change()
        self.project.move_sheet(uid, i + delta)
        self.commit_change(s, "Sheet order changed.")

    def delete_sheet(self, uid):
        d = self.project.find_sheet(uid)
        if len(self.project.sheets) <= 1:
            messagebox.showinfo("Delete sheet", "A project needs at least one sheet.", parent=self.root)
            return
        n = len(d.components) + len(d.wires) + len(d.shapes)
        if n and not messagebox.askyesno("Delete sheet", f"Delete “{d.name}” and its {n} objects?\n\n"
                                         "You can undo this.", parent=self.root):
            return
        s = self.begin_change()
        i = self.project.sheets.index(d)
        self.project.delete_sheet(uid)
        if d is self.doc:
            self.doc = self.project.sheets[min(i, len(self.project.sheets) - 1)]
            self.selection = set()
        self.commit_change(s, f"Deleted {d.name}.")
        self.canvas.fit()

    # ---------------------------------------------------------------- layers
    def add_layer(self, name):
        if self.project.layer(name):
            self.log(f"Layer {name} already exists.", "warning")
            return
        s = self.begin_change()
        self.project.ensure_layer(name)
        self.current_layer = name
        self.commit_change(s, f"Layer {name} added and made current.")
        self.layers_panel.refresh()

    def rename_layer(self, old, new):
        if self.project.layer(new):
            self.log(f"Layer {new} already exists.", "error")
            return
        s = self.begin_change()
        self.project.layer(old).name = new
        for d in self.project.sheets:
            for coll in (d.components, d.wires, d.shapes):
                for o in coll.values():
                    if o.layer == old:
                        o.layer = new
        if self.current_layer == old:
            self.current_layer = new
        self.commit_change(s, "Layer renamed.")
        self.layers_panel.refresh()

    def delete_layer(self, name):
        from ..model import DEFAULT_LAYER_COMPONENTS, DEFAULT_LAYER_SHAPES, DEFAULT_LAYER_WIRES
        if name in (DEFAULT_LAYER_COMPONENTS, DEFAULT_LAYER_WIRES, DEFAULT_LAYER_SHAPES):
            messagebox.showinfo("Delete layer", "The standard layers cannot be deleted.", parent=self.root)
            return
        used = sum(1 for d in self.project.sheets for coll in (d.components, d.wires, d.shapes)
                   for o in coll.values() if o.layer == name)
        if used and not messagebox.askyesno("Delete layer", f"{used} objects are on “{name}”. Move them to their "
                                            "standard layers and delete the layer?", parent=self.root):
            return
        s = self.begin_change()
        for d in self.project.sheets:
            for coll, default in ((d.components, DEFAULT_LAYER_COMPONENTS), (d.wires, DEFAULT_LAYER_WIRES),
                                  (d.shapes, DEFAULT_LAYER_SHAPES)):
                for o in coll.values():
                    if o.layer == name:
                        o.layer = default
        self.project.layers = [l for l in self.project.layers if l.name != name]
        if self.current_layer == name:
            self.current_layer = None
        self.commit_change(s, f"Layer {name} deleted.")
        self.layers_panel.refresh()

    def set_layer_attr(self, name, attr, value):
        s = self.begin_change()
        setattr(self.project.layer(name), attr, value)
        if attr in ("visible", "locked"):
            self.selection = {i for i in self.selection if self.is_selectable(self.doc.item(i))}
        self.commit_change(s)
        self.layers_panel.refresh()

    def select_layer(self, name):
        self.set_selection({i for i in self.doc.all_ids() if self.doc.item(i).layer == name})

    # ---------------------------------------------------------------- symbols / templates
    def open_symbol_editor(self, doc=None, folder=None, from_builtin=None, copy_of=None, params=None):
        """Open the symbol editor: empty, on a custom symbol `doc` (edited in
        place), or on an editable copy of any symbol `copy_of` (built-in,
        library or project; `params` = variant of a parametric symbol)."""
        from .symbol_editor import SymbolEditor
        if not self.userlib.folders():
            try:
                self.userlib.create_folder("", "My symbols")
            except OSError:
                pass
        return SymbolEditor(self, doc=doc, folder=folder, copy_of=copy_of or from_builtin, params=params)

    def edit_symbol_copy(self, sid, params=None):
        """Open any symbol as an editable copy; the original is never changed."""
        if symbols.get(sid) is None:
            return None
        return self.open_symbol_editor(copy_of=sid, params=params)

    def edit_custom_symbol(self, sid):
        sd = symbols.get(sid)
        if sd is None or not sd.is_custom:
            return
        e = self.userlib.entries.get(sid)
        self.open_symbol_editor(doc=sd.custom, folder=e.folder if e else None)

    def update_project_symbol(self, sid):
        """Switch the project's embedded copy of a custom symbol to the library version."""
        e = self.userlib.entries.get(sid)
        if e is None:
            return
        from ..symbols.custom import to_symdef
        s = self.begin_change()
        before = {(d.uid, w.id): (w.start, w.end) for d in self.project.sheets for w in d.wires.values()}
        self.project.symbols[sid] = json.loads(json.dumps(e.doc))
        symbols.add_project_symbol(to_symdef(e.doc))
        for d in self.project.sheets:
            editing.sync_wire_ends(d)
        lost = sum(1 for d in self.project.sheets for w in d.wires.values()
                   if before.get((d.uid, w.id)) and (bool(before[(d.uid, w.id)][0]) and not w.start or
                                                     bool(before[(d.uid, w.id)][1]) and not w.end))
        self.commit_change(s, f"Drawings updated to “{e.name}” revision {e.doc.get('revision', 0)}." +
                           (f" {lost} wire end(s) were detached from connection points that no longer exist."
                            if lost else ""))
        if lost:
            self.log(f"{lost} wire end(s) lost their connection point after the symbol update.", "warning")

    def insert_symbol_dialog(self):
        sid = SymbolPickerDialog(self, "Insert symbol").result
        if sid:
            self.start_place(sid)

    def save_template_dialog(self):
        if not self.selection:
            messagebox.showinfo("Save as template", "Select the components and wires to save first.",
                                parent=self.root)
            return
        TemplateSaveDialog(self)

    def save_selection_as_template(self, name, description, folder):
        clip = editing.copy_items(self.doc, self.selection)
        try:
            tpl = templates.make_template(name, clip, description, folder.split("/")[-1] if folder else "My templates")
            self.templates.save(tpl, folder)
        except (OSError, templates.TemplateError) as e:
            messagebox.showerror("Save template", str(e), parent=self.root)
            return
        self.templates_panel.refresh()
        self.toast(f"Template “{name}” saved.", "success")

    # ---------------------------------------------------------------- reports / tools
    def open_bom(self):
        from .reports import BomWindow
        BomWindow(self)

    def open_reports(self, tab="connections"):
        from .reports import ReportsWindow
        ReportsWindow(self, tab)

    def export_bom_csv(self):
        from .. import bom
        from ..userlib import safe_name
        lines = bom.generate(self.project)
        p = filedialog.asksaveasfilename(parent=self.root, title="Export bill of materials", defaultextension=".csv",
                                         initialfile=safe_name(self.project.meta.get("title") or "project") + " BOM.csv",
                                         filetypes=[("CSV (spreadsheet)", "*.csv")])
        if p:
            projectio.atomic_write_bytes(p, bom.bom_csv(lines).encode("utf-8"))
            self.toast(f"Exported {os.path.basename(p)} ({len(lines)} lines).", "success")

    def wire_number_dialog(self):
        WireNumberDialog(self)

    def number_wires(self, conv, renumber):
        s = self.begin_change()
        if conv:
            self.project.settings["wire_numbering"].update(conv)
        n = netlist.assign_wire_numbers(self.project, renumber)
        self.commit_change(s, f"{n} connection(s) numbered." if n or renumber else "All connections already have "
                                                                                    "numbers.")

    def run_check(self):
        self.show_dock(self.check_panel)
        s = self.check_panel.run()
        self.set_status(f"Check drawing: {s['error']} errors, {s['warning']} warnings, {s['info']} notes.")

    def show_search(self, query=None):
        self.show_dock(self.search_panel)
        if query:
            hits = self.search_panel.run(query)
            if len(hits) == 1:
                h = hits[0]
                from .. import search
                self.navigate(h.sheet_uid, h.obj_id, search.object_point(self.project, h))
        else:
            self.search_panel.entry.focus()

    def navigate(self, sheet_uid, obj_id=None, point=None):
        if sheet_uid and sheet_uid != self.doc.uid:
            self.set_active_sheet(sheet_uid)
        o = self.doc.item(obj_id) if obj_id is not None else None
        if o is not None:
            self.set_selection({obj_id})
            b = o.bbox()
            pad = 160
            self.canvas.after(30, lambda: self.canvas.fit((b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)))
        elif point is not None:
            self.canvas.after(30, lambda: self.canvas.center_on(point, max(self.canvas.zoom, 1.5)))

    def open_revisions(self):
        from .revisions_ui import RevisionsWindow
        RevisionsWindow(self)

    def issue_revision_dialog(self):
        from .revisions_ui import IssueRevisionDialog
        IssueRevisionDialog(self)

    def issue_revision(self, label, description, author, approved_by, update_title_block):
        s = self.begin_change()
        if update_title_block:
            self.project.meta["revision"] = label
        self.project.revisions.create(self.project, "approved", label=label, description=description, author=author,
                                      approved_by=approved_by)
        self.commit_change(s, f"Revision {label} issued.")
        self.mark_dirty()
        self.toast(f"Revision {label} issued and added to the revision tables.", "success")

    def restore_revision(self, n):
        from .. import revisions
        s = self.begin_change()
        p = revisions.restore(self.project, self.project.revisions, n)
        uid = self.doc.uid
        self.project = p
        p.activate_symbols()
        self.doc = p.find_sheet(uid) or p.sheets[0]
        self.selection = set()
        self.commit_change(s, f"Restored snapshot #{n}.")
        self.refresh(full=True)
        self.canvas.fit()

    # ---------------------------------------------------------------- view / theme / settings
    def canvas_fit_drawing(self):
        self.canvas.fit_drawing()

    def set_toggle(self, key, value=None):
        self.settings[key] = (not self.settings[key]) if value is None else bool(value)
        self.settings.save()
        self._update_toggles()
        self.canvas.redraw()
        self.set_status(f"{ {'show_grid': 'Grid', 'snap_grid': 'Grid snap', 'ortho': 'Ortho', 'osnap': 'Object snap', 'show_markers': 'Markers'}[key]} "
                        f"{'on' if self.settings[key] else 'off'}.")

    def set_theme(self, name, canvas=None):
        if canvas is not None:
            self.settings["canvas_theme"] = canvas
        self.settings["theme"] = name
        self.settings.save()
        self.theme = th.Theme(name, self.settings["canvas_theme"])
        set_current_theme(self.theme)
        th.apply(self.root, self.theme)
        for w in list(self.windows):
            try:
                if w.winfo_exists():
                    th.recolor_tree(w, self.theme)
                    w.configure(bg=self.theme.ui["surface"])
            except tk.TclError:
                pass
        self.theme_var.set(name)
        self.toasts.clear()
        self.templates_panel.preview.theme = self.theme
        self._update_toggles()
        self.refresh(full=True)
        self.inspector.refresh(force=True)
        self.set_status(f"Theme: {self.theme.label}.")

    def cycle_theme(self):
        keys = list(th.THEMES)
        self.set_theme(keys[(keys.index(self.theme.name) + 1) % len(keys)])

    def preferences(self):
        PreferencesDialog(self)

    def apply_settings(self):
        self.settings.save()
        self._update_toggles()
        self._schedule_autosave()
        if bool(self.settings["show_command_line"]) != bool(self.cmdline.winfo_ismapped()):
            self.cmd_var.set(self.settings["show_command_line"])
            self.toggle_command_line(save=False)
        self.canvas.redraw()

    def toggle_command_line(self, save=True):
        show = self.cmd_var.get()
        if show:
            self.cmd_sep.pack(fill="x", side="bottom", before=self.hpane)
            self.cmdline.pack(fill="x", side="bottom", before=self.cmd_sep)
        else:
            self.cmdline.pack_forget()
            self.cmd_sep.pack_forget()
        if save:
            self.settings["show_command_line"] = bool(show)
            self.settings.save()

    def reset_layout(self):
        self.settings["layout"] = {}
        for side in ("left", "right", "bottom"):
            if not self.panel_visible[side]:
                self.toggle_panel(side)
        self._restore_layout()

    # ================================================================ context menu
    def show_context_menu(self, x, y, p=None, hit=None):
        m = make_menu(self.root)
        doc = self.doc
        tol = 8 / self.canvas.zoom
        if p is not None:
            cross = [c for c in editing.crossings(doc) if abs(c[0][0] - p[0]) + abs(c[0][1] - p[1]) <= tol]
            if cross:
                q = cross[0][0]
                m.add_command(label="Connect wires here (add junction)", command=lambda: self._connect_at(q))
            from ..connectivity import analyse
            junc = [j for j in analyse(doc).junctions if abs(j[0] - p[0]) + abs(j[1] - p[1]) <= tol]
            if junc:
                q = junc[0]
                m.add_command(label="Disconnect junction", command=lambda: self._disconnect_at(q))
            if cross or junc:
                m.add_separator()
        has = bool(self.selection)
        st = "normal" if has else "disabled"
        sel = list(self.selection)
        one = doc.item(sel[0]) if len(sel) == 1 else None
        if has:
            m.add_command(label="Properties", command=self.focus_properties, accelerator=self.keymap.accel("properties"))
            m.add_separator()
        m.add_command(label="Rotate 90° clockwise", command=lambda: self.rotate(True), state=st,
                      accelerator=self.keymap.accel("rotate"))
        m.add_command(label="Rotate 90° counter-clockwise", command=lambda: self.rotate(False), state=st)
        m.add_command(label="Mirror", command=self.mirror, state=st, accelerator=self.keymap.accel("mirror"))
        m.add_command(label="Move…", command=lambda: self.run_command("MOVE"), state=st)
        m.add_separator()
        m.add_command(label="Cut", command=self.cut, state=st, accelerator=self.keymap.accel("cut"))
        m.add_command(label="Copy", command=self.copy, state=st, accelerator=self.keymap.accel("copy"))
        m.add_command(label="Paste", command=self.paste, state="normal" if self.clipboard else "disabled",
                      accelerator=self.keymap.accel("paste"))
        m.add_command(label="Duplicate", command=self.duplicate, state=st, accelerator=self.keymap.accel("duplicate"))
        m.add_command(label="Delete", command=self.delete, state=st, accelerator=self.keymap.accel("delete"))
        if has:
            m.add_separator()
            if len(sel) > 1:
                m.add_command(label="Group", command=self.group_selection)
                al = make_menu(m)
                for mode in editing.ALIGN_MODES:
                    al.add_command(label=mode.title(), command=lambda mo=mode: self.align(mo))
                al.add_command(label="Distribute horizontally", command=lambda: self.distribute("h"))
                al.add_command(label="Distribute vertically", command=lambda: self.distribute("v"))
                m.add_cascade(label="Align", menu=al)
            if any(getattr(doc.item(i), "group", "") for i in sel):
                m.add_command(label="Ungroup", command=self.ungroup_selection)
            m.add_command(label="Lock", command=lambda: self.set_locked(True))
            m.add_command(label="Save as template…", command=self.save_template_dialog)
        if isinstance(one, Component):
            sd = symbols.get(one.symbol)
            m.add_separator()
            if sd is not None and sd.parametric:
                m.add_command(label="Configure valve…", command=lambda: self.configure_valve(one.id))
            if sd is not None and sd.is_custom:
                m.add_command(label="Edit symbol…", command=lambda: self.edit_custom_symbol(one.symbol))
            if sd is not None:
                # a configured valve opens as configured (its params)
                m.add_command(label="Edit a copy of the symbol…",
                              command=lambda: self.edit_symbol_copy(one.symbol, dict(one.params) or None))
            m.add_command(label="Replace symbol…", command=lambda: self.replace_symbol([one]))
            m.add_command(label="Find in project", command=lambda: self.show_search(one.designator)
                          if one.designator else None)
        if isinstance(one, Wire):
            m.add_separator()
            m.add_command(label="Set wire number…", command=lambda: self._ask_wire_number(one))
            m.add_command(label="Solid line" if one.style == "dashed" else "Dashed line (pilot / drain)",
                          command=lambda: self.edit_objects([one], style="solid" if one.style == "dashed" else "dashed"))
        if isinstance(one, Shape) and one.kind == "text":
            m.add_command(label="Edit text…", command=lambda: self.edit_text_shape(one.id))
        if not has:
            m.add_command(label="Select all", command=self.select_all)
            m.add_command(label="Zoom to drawing", command=self.canvas_fit_drawing)
            m.add_command(label="Zoom to sheet", command=lambda: self.canvas.fit())
            m.add_command(label="Sheet properties", command=self.focus_properties)
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _connect_at(self, p):
        s = self.begin_change()
        if editing.connect_crossing(self.doc, p):
            self.commit_change(s, "Wires connected: a junction was added.")

    def _disconnect_at(self, p):
        s = self.begin_change()
        msg = editing.disconnect_junction(self.doc, p)
        self.commit_change(s, msg or "This junction cannot be removed automatically.")

    def _ask_wire_number(self, w):
        v = simpledialog.askstring("Wire number", "Wire number for this connection (empty = automatic):",
                                   initialvalue=w.number, parent=self.root)
        if v is not None:
            self.set_wire_number(w, v.strip())

    # ================================================================ files
    def confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        ans = messagebox.askyesnocancel("Unsaved changes", "Save changes to the current project?", parent=self.root)
        if ans is None:
            return False
        if ans:
            return self.save()
        return True

    def _reset(self, project, filename):
        if self.runner.active:
            self.runner.cancel()
        self.project = project
        if project.revisions is None:
            from ..revisions import RevisionStore
            project.revisions = RevisionStore()
        self.doc = project.sheets[0]
        self.filename = filename
        self.selection = set()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self.current_layer = None
        self.set_validation(None)
        self.check_panel.issues = []
        self.check_panel.show()
        self.canvas.set_tool("select")
        self.refresh(full=True)

    def new(self):
        if not self.confirm_discard():
            return
        p = new_project(size=self._default_size())
        p.activate_symbols()
        self._reset(p, None)
        self.canvas.fit()
        self.recovery.discard_snapshots()
        self.set_status("New project.")

    def open(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self.root, title="Open", filetypes=FILETYPES_OPEN,
                                          initialdir=self.settings["last_dir"] or None)
        if path:
            self.open_path(path, confirm=False)

    def open_path(self, path, confirm=True):
        if confirm and not self.confirm_discard():
            return
        try:
            res = projectio.open_any(path)
        except (OSError, projectio.ProjectFormatError) as e:
            messagebox.showerror("Could not open", f"{path}\n\n{e}", parent=self.root)
            return
        self.settings["last_dir"] = os.path.dirname(os.path.abspath(path))
        if res.migrated:
            self._reset(res.project, None)
            self._suggested_path = projectio.suggested_project_path(path)
            self.dirty = True
            self.update_title()
            for w in res.warnings:
                self.log(w, "warning")
            self.toast(f"Converted {os.path.basename(path)} to a project. The original file is unchanged; "
                       f"Save asks for a new name (suggested: {os.path.basename(self._suggested_path)}).", "info")
        else:
            self._reset(res.project, path)
            self.settings.add_recent(path)
            for w in res.warnings:
                self.log(w, "warning")
            if res.warnings:
                self.toast("Opened with warnings — see the Output panel.", "warning")
        self.settings.save()
        self._rebuild_recent()
        self.root.after(40, self.canvas.fit)
        self.log(f"Opened {os.path.basename(path)} ({len(self.project.sheets)} sheet(s)).", "success")

    def save(self) -> bool:
        if not self.filename:
            return self.save_as()
        try:
            projectio.save_project(self.project, self.filename)
        except OSError as e:
            messagebox.showerror("Save failed", f"{self.filename}\n\n{e}\n\nYour previous file is unchanged.",
                                 parent=self.root)
            return False
        self.dirty = False
        self.settings.add_recent(self.filename)
        self.settings.save()
        self._rebuild_recent()
        self.update_title()
        self.recovery.discard_snapshots()
        self.set_status(f"Saved {self.filename}")
        self.log(f"Saved {self.filename}", "success")
        return True

    def save_as(self) -> bool:
        sugg = getattr(self, "_suggested_path", None)
        initial = os.path.basename(self.filename) if self.filename else (
            os.path.basename(sugg) if sugg else (self.project.meta.get("title") or "project") + PROJECT_EXTENSION)
        path = filedialog.asksaveasfilename(parent=self.root, title="Save project as",
                                            defaultextension=PROJECT_EXTENSION,
                                            filetypes=[("OpenSchematix project", "*" + PROJECT_EXTENSION)],
                                            initialdir=(os.path.dirname(sugg) if sugg else None) or
                                            self.settings["last_dir"] or None, initialfile=initial)
        if not path:
            return False
        if not path.lower().endswith(PROJECT_EXTENSION):
            path += PROJECT_EXTENSION
        self.filename = path
        self._suggested_path = None
        self.settings["last_dir"] = os.path.dirname(path)
        return self.save()

    def export_project_copy(self):
        p = filedialog.asksaveasfilename(parent=self.root, title="Export project copy",
                                         defaultextension=PROJECT_EXTENSION,
                                         filetypes=[("OpenSchematix project", "*" + PROJECT_EXTENSION)])
        if p:
            projectio.atomic_write_bytes(p, projectio.project_bytes(self.project))
            self.toast(f"Exported {os.path.basename(p)}", "success")

    def import_project_sheets(self):
        path = filedialog.askopenfilename(parent=self.root, title="Import sheets from", filetypes=FILETYPES_OPEN)
        if not path:
            return
        try:
            other = projectio.open_any(path).project
        except (OSError, projectio.ProjectFormatError) as e:
            messagebox.showerror("Import", str(e), parent=self.root)
            return
        s = self.begin_change()
        for d in other.sheets:
            new = self.project.add_sheet(d.name)
            editing.paste(new, editing.copy_items(d, d.all_ids()), 0, 0)
            new.sheet = Sheet_copy(d.sheet)
        for sid, sdoc in other.symbols.items():
            self.project.symbols.setdefault(sid, sdoc)
        self.project.activate_symbols()
        self.commit_change(s, f"Imported {len(other.sheets)} sheet(s) from {os.path.basename(path)}.")

    def _rebuild_recent(self):
        m = self.recent_menu
        m.delete(0, "end")
        rec = [p for p in self.settings["recent_files"] if os.path.exists(p)]
        if not rec:
            m.add_command(label="(none)", state="disabled")
        for p in rec:
            m.add_command(label=p, command=lambda p=p: self.open_path(p))

    def export_pdf_dialog(self, preselect=None):
        ExportPdfDialog(self, preselect)

    def export_pdf(self, uids):
        base = os.path.splitext(os.path.basename(self.filename))[0] if self.filename else (
            self.project.meta.get("title") or "drawing")
        path = filedialog.asksaveasfilename(parent=self.root, title="Export PDF", defaultextension=".pdf",
                                            filetypes=[("PDF", "*.pdf")], initialfile=base + ".pdf",
                                            initialdir=self.settings["last_dir"] or None)
        if not path:
            return
        try:
            export.export_project_pdf(self.project, path, set(uids))
        except OSError as e:
            messagebox.showerror("Export failed", f"{path}\n\n{e}", parent=self.root)
            return
        self.toast(f"Exported {len(uids)} sheet(s) to {os.path.basename(path)}", "success")

    def export_file(self, kind):
        ext = "." + kind
        from ..userlib import safe_name
        base = safe_name(self.doc.name)
        path = filedialog.asksaveasfilename(parent=self.root, title=f"Export {kind.upper()}", defaultextension=ext,
                                            filetypes=[(kind.upper(), "*" + ext)], initialfile=base + ext,
                                            initialdir=self.settings["last_dir"] or None)
        if not path:
            return
        try:
            if kind == "svg":
                export.export_svg(self.doc, path, project=self.project)
            else:
                from .. import dxf
                dxf.export_dxf(self.doc, path, self.project)
        except OSError as e:
            messagebox.showerror("Export failed", f"{path}\n\n{e}", parent=self.root)
            return
        self.toast(f"Exported {os.path.basename(path)}", "success")

    def export_osch(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Export sheet as .osch", defaultextension=".osch",
                                            filetypes=[("OpenSchematix drawing", "*.osch")])
        if path:
            projectio.export_sheet_osch(self.doc, path)
            self.toast("Exported. Note: older builds cannot open files with newer content "
                       "(drawing objects, layers).", "warning")

    def import_dxf_dialog(self):
        path = filedialog.askopenfilename(parent=self.root, title="Import DXF",
                                          filetypes=[("DXF drawing", "*.dxf"), ("All files", "*")],
                                          initialdir=self.settings["last_dir"] or None)
        if path:
            DxfImportDialog(self, path)

    def import_dxf(self, path, units, scale, center, new_sheet):
        from .. import dxf
        try:
            with open(path, "rb") as f:
                raw = f.read()
            target_h = self.doc.sheet.size_units()[1]
            rep = dxf.import_dxf(raw, units=units, scale=scale, origin=(0.0, target_h))
        except (OSError, dxf.DxfError) as e:
            messagebox.showerror("Import DXF", str(e), parent=self.root)
            return
        if not rep.shapes:
            messagebox.showinfo("Import DXF", "Nothing could be imported.\n\n" + rep.summary(), parent=self.root)
            return
        s = self.begin_change()
        if new_sheet:
            d = self.project.add_sheet(os.path.splitext(os.path.basename(path))[0],
                                       index=self.project.sheets.index(self.doc) + 1)
            self.doc = d
        ids = dxf.place_on_sheet(rep, self.doc, self.project, fit=center)
        self.selection = set(ids)
        self.commit_change(s, f"Imported {os.path.basename(path)}.")
        self.refresh(full=True)
        self.canvas_fit_drawing()
        self.log("DXF import: " + rep.summary(), "success")
        if rep.skipped or rep.approximated:
            self.toast("DXF imported. " + rep.summary(), "warning")

    def print_(self):
        try:
            fd, path = tempfile.mkstemp(prefix="openschematix-", suffix=".pdf")
            os.close(fd)
            export.export_project_pdf(self.project, path, {self.doc.uid})
        except OSError as e:
            messagebox.showerror("Print failed", str(e), parent=self.root)
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa: S606 - opens the user's PDF viewer
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            self.set_status("The sheet was opened as a PDF in your viewer; print it from there at 100% scale.")
        except (OSError, AttributeError) as e:
            messagebox.showinfo("Print", f"The PDF was written to:\n{path}\n\nOpen it to print. ({e})", parent=self.root)

    # ---------------------------------------------------------------- autosave / recovery
    def _schedule_autosave(self):
        if self._autosave_job is not None:
            try:
                self.root.after_cancel(self._autosave_job)
            except tk.TclError:
                pass
            self._autosave_job = None
        mins = self.settings["autosave_minutes"]
        if mins and mins > 0:
            self._autosave_job = self.root.after(int(mins * 60000), self._autosave)

    def _autosave(self):
        self._autosave_job = None
        if self.dirty:
            try:
                path = self.recovery.autosave(self.project, self.filename or "")
                if path:
                    self.log("Recovery copy saved (your own file is only written when you save).", "info")
            except OSError as e:
                self.log(f"Autosave failed: {e}", "warning")
        self._schedule_autosave()

    def _offer_recovery(self, orphans):
        res = RecoveryDialog(self, orphans).result
        if not res:
            return
        orphan, snap_ = res
        try:
            r = projectio.open_any(snap_.path)
        except (OSError, projectio.ProjectFormatError) as e:
            messagebox.showerror("Recovery", f"The recovery copy could not be opened:\n{e}", parent=self.root)
            return
        self._reset(r.project, None)
        self._suggested_path = orphan.source or None
        self.dirty = True
        self.update_title()
        RecoveryManager.discard(orphan)
        messagebox.showinfo("Recovered", f"Recovered the copy saved at {snap_.when}.\n\nIt has not been saved yet: "
                            "use Save as to store it" + (f" (original file: {orphan.source})." if orphan.source else "."),
                            parent=self.root)
        self.canvas.fit()

    def quit(self):
        if self.runner.active:
            self.runner.cancel()
        if not self.confirm_discard():
            return
        try:
            if self.root.state() == "normal":
                self.settings["geometry"] = self.root.geometry()
        except tk.TclError:
            pass
        self._save_layout()
        self.cmdline.save_history()
        self.settings.save()
        try:
            self.recovery.end()
        except OSError:
            pass
        self.root.destroy()


def Sheet_copy(sheet):
    from ..model import Sheet
    return Sheet.from_dict(sheet.to_dict())



def _startup_splash(root):
    """Show a borderless startup window while the main workspace initializes."""
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg="#0d2343")
    width, height = 480, 260
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 2)
    splash.geometry(f"{width}x{height}+{x}+{y}")
    frame = tk.Frame(splash, bg="#0d2343", highlightthickness=1,
                     highlightbackground="#2765a3")
    frame.pack(fill="both", expand=True)
    # Keep a reference: Tk discards images when the PhotoImage is collected.
    try:
        splash.logo = tk.PhotoImage(file=resource_path("openschematix-256.png"))
        splash.logo = splash.logo.subsample(3, 3)
        tk.Label(frame, image=splash.logo, bg="#0d2343").pack(pady=(25, 10))
    except tk.TclError:
        tk.Label(frame, text="S", fg="#ffbd30", bg="#0d2343",
                 font=("Arial", 48, "bold")).pack(pady=(22, 10))
    tk.Label(frame, text=APP_NAME, fg="#ffffff", bg="#0d2343",
             font=("Arial", 23, "bold")).pack()
    tk.Label(frame, text=f"Version {VERSION}", fg="#b6cce5", bg="#0d2343",
             font=("Arial", 11)).pack(pady=(5, 0))
    tk.Label(frame, text="Loading engineering workspace…", fg="#b6cce5",
             bg="#0d2343", font=("Arial", 10)).pack(side="bottom", pady=17)
    splash.lift()
    splash.update()
    return splash


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("--version", "-V"):
        print(f"{APP_NAME} {VERSION}")
        return 0
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # system DPI aware (Tk scales at start-up)
        except Exception:  # noqa: BLE001 - older Windows versions
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:  # noqa: BLE001
                pass
    root = tk.Tk(className="OpenSchematix")
    root.withdraw()
    splash = _startup_splash(root)
    started_at = time.monotonic()
    try:
        app = App(root, argv[0] if argv else None)
    except BaseException:
        splash.destroy()
        root.destroy()
        raise
    # Never delay initialization itself: only keep the splash visible for
    # the remainder of the two-second minimum, then reveal the workspace.
    remaining_ms = max(0, int(2000 - (time.monotonic() - started_at) * 1000))
    def reveal_workspace():
        root.deiconify()
        root.update_idletasks()
        # Restoring sash positions while the root is withdrawn sees a 1px
        # pane and can make Properties cover the entire workspace.
        root.after(100, lambda: app._restore_layout())
        splash.destroy()
    root.after(remaining_ms, reveal_workspace)
    root.mainloop()
    return 0
