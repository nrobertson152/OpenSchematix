"""Sidebar and dock panels: project sheets, circuit templates, layers, Check
Drawing results and project-wide search."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from .. import check as checker
from .. import search as searcher
from .. import templates
from ..titleblock import zone_of
from . import theme as th
from .canvas_view import PreviewView
from .widgets import IconButton, PanelHeader, SearchEntry, Tooltip, current_theme, make_menu


def _tree(parent, columns, headings, widths, show="headings", height=8):
    frame = ttk.Frame(parent, style="Surface.TFrame")
    tv = ttk.Treeview(frame, columns=columns, show=show, height=height, selectmode="browse")
    for c, h, w in zip(columns, headings, widths):
        tv.heading(c, text=h, anchor="w")
        tv.column(c, width=w, minwidth=30, stretch=w > 120, anchor="w")
    sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, tv


# ================================================================ project / sheets
class ProjectPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Surface.TFrame")
        self.app = app
        PanelHeader(self, "Sheets", [("sheet_add", app.add_sheet, "New sheet (SHEET NEW)"),
                                     ("properties", app.project_properties, "Project properties…")]).pack(fill="x")
        frame, self.tree = _tree(self, ("n", "name", "size"), ("#", "Sheet", "Size"), (34, 150, 60), height=10)
        frame.pack(fill="both", expand=True, padx=(6, 0))
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.tree.bind("<Double-1>", lambda e: self.rename())
        self.tree.bind("<ButtonPress-3>", self._context)
        bar = ttk.Frame(self, style="Surface.TFrame", padding=(6, 4))
        bar.pack(fill="x")
        for icon, cmd, tip in (("sheet_add", app.add_sheet, "New sheet"), ("copy", self.duplicate, "Duplicate sheet"),
                               ("text", self.rename, "Rename sheet"),
                               ("chevron_left", lambda: self.move(-1), "Move up (earlier)"),
                               ("chevron_right", lambda: self.move(1), "Move down (later)"),
                               ("delete", self.delete, "Delete sheet")):
            IconButton(bar, icon, cmd, tip, size=15, bg_key="surface", pad=4).pack(side="left")
        self.info = ttk.Label(self, text="", style="Muted.TLabel", padding=(10, 2, 10, 10), justify="left")
        self.info.pack(fill="x")
        self._updating = False

    def refresh(self):
        self._updating = True
        self.tree.delete(*self.tree.get_children())
        p = self.app.project
        for i, d in enumerate(p.sheets, 1):
            s = d.sheet
            size = s.size if s.size != "Custom" else "Custom"
            self.tree.insert("", "end", d.uid, values=(i, d.name, size))
        if self.tree.exists(self.app.doc.uid):
            self.tree.selection_set(self.app.doc.uid)
            self.tree.see(self.app.doc.uid)
        title = p.meta.get("title") or "Untitled project"
        n = sum(len(d.components) for d in p.sheets)
        self.info.configure(text=f"{title}\n{len(p.sheets)} sheets · {n} components"
                                 + (f" · no. {p.meta['number']}" if p.meta.get("number") else ""))
        self._updating = False

    def _select(self, _e):
        if self._updating:
            return
        sel = self.tree.selection()
        if sel and sel[0] != self.app.doc.uid:
            self.app.set_active_sheet(sel[0])

    def current(self):
        sel = self.tree.selection()
        return sel[0] if sel else self.app.doc.uid

    def duplicate(self):
        self.app.duplicate_sheet(self.current())

    def rename(self):
        uid = self.current()
        d = self.app.project.find_sheet(uid)
        name = simpledialog.askstring("Rename sheet", "Sheet name:", initialvalue=d.name, parent=self.app.root)
        if name and name.strip():
            self.app.rename_sheet(uid, name)

    def move(self, delta):
        self.app.move_sheet(self.current(), delta)

    def delete(self):
        self.app.delete_sheet(self.current())

    def _context(self, e):
        node = self.tree.identify_row(e.y)
        if node:
            self.tree.selection_set(node)
        m = make_menu(self)
        m.add_command(label="New sheet", command=self.app.add_sheet)
        if node:
            m.add_command(label="Duplicate", command=self.duplicate)
            m.add_command(label="Rename…", command=self.rename)
            m.add_command(label="Move up", command=lambda: self.move(-1))
            m.add_command(label="Move down", command=lambda: self.move(1))
            m.add_separator()
            m.add_command(label="Export sheet as PDF…", command=lambda: self.app.export_pdf_dialog([node]))
            m.add_separator()
            m.add_command(label="Delete…", command=self.delete)
        m.tk_popup(e.x_root, e.y_root)


# ================================================================ templates
class TemplatesPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Surface.TFrame")
        self.app = app
        PanelHeader(self, "Circuit templates", [("plus", app.save_template_dialog, "Save selection as template…"),
                                                ("import", self.import_file, "Import template…")]).pack(fill="x")
        self.search = SearchEntry(self, "Search templates", on_change=lambda q: self.refresh())
        self.search.pack(fill="x", padx=8, pady=(0, 6))
        frame, self.tree = _tree(self, ("name",), ("Template",), (200,), show="tree", height=8)
        frame.pack(fill="both", expand=True, padx=(6, 0))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.preview_selected())
        self.tree.bind("<Double-1>", lambda e: self.insert())
        self.tree.bind("<ButtonPress-3>", self._context)
        card = ttk.Frame(self, style="Surface.TFrame", padding=(8, 6, 8, 8))
        card.pack(fill="x")
        self.preview = PreviewView(card, app.theme, height=int(130 * th.dpi_factor(self)))
        self.preview.pack(fill="x")
        self.desc = ttk.Label(card, text="", style="Muted.TLabel", wraplength=230, justify="left")
        self.desc.pack(fill="x", pady=(6, 0))
        self.insert_btn = ttk.Button(card, text="Insert", style="Accent.TButton", command=self.insert)
        self.insert_btn.pack(fill="x", pady=(8, 0))
        self.bind("<Configure>", lambda e: self.desc.configure(wraplength=max(120, e.width - 24)))
        self.items = {}
        th.subscribe(self._retheme)

    def _retheme(self, t):
        self.preview.theme = t
        self.preview.redraw()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.items = {}
        q = self.search.get().lower().split()
        folders = {}
        for key, folder, tpl in self.app.templates.items():
            blob = f"{tpl['name']} {tpl.get('description', '')} {tpl.get('category', '')} {folder}".lower()
            if q and not all(w in blob for w in q):
                continue
            parent = ""
            path = ""
            for part in folder.split("/"):
                path = f"{path}/{part}" if path else part
                if path not in folders:
                    folders[path] = self.tree.insert(parent, "end", text=part, open=True)
                parent = folders[path]
            iid = self.tree.insert(parent, "end", text=tpl["name"])
            self.items[iid] = (key, tpl)
        self.preview_selected()

    def selected(self):
        sel = self.tree.selection()
        return self.items.get(sel[0]) if sel else None

    def preview_selected(self):
        it = self.selected()
        self.insert_btn.state(["!disabled"] if it else ["disabled"])
        if not it:
            self.preview.show(None)
            self.preview.delete("all")
            self.desc.configure(text="Select a template to preview it. Insert places it on the sheet with new "
                                     "identifiers.")
            return
        key, tpl = it
        d = templates.preview_document(tpl)
        b = d.bbox() or (0, 0, 100, 100)
        from ..render import scene
        items = scene(d, screen=False, frame=False)
        self.preview.doc = d
        self.preview.items_fn = lambda: [(items, None)]
        self.preview.update_idletasks()
        self.preview.fit_box((b[0] - 20, b[1] - 20, b[2] + 20, b[3] + 20), margin=8)
        n = len(d.components)
        self.desc.configure(text=f"{tpl.get('description') or tpl['name']}\n{n} components · "
                                 f"{tpl.get('category', '')}")

    def insert(self):
        it = self.selected()
        if it:
            self.app.start_template(it[1])

    def import_file(self):
        p = filedialog.askopenfilename(parent=self.app.root, title="Import circuit template",
                                       filetypes=[("OpenSchematix template", "*.ostpl"), ("All files", "*")])
        if p:
            try:
                self.app.templates.import_file(p, "Imported")
            except (OSError, ValueError) as e:
                messagebox.showerror("Import failed", str(e), parent=self.app.root)
                return
            self.refresh()
            self.app.toast("Template imported.", "success")

    def _context(self, e):
        node = self.tree.identify_row(e.y)
        if node:
            self.tree.selection_set(node)
        it = self.items.get(node) if node else None
        m = make_menu(self)
        m.add_command(label="Save selection as template…", command=self.app.save_template_dialog)
        m.add_command(label="Import template…", command=self.import_file)
        if it:
            key, tpl = it
            m.add_separator()
            m.add_command(label="Insert", command=self.insert)
            m.add_command(label="Export…", command=lambda: self._export(tpl))
            if not key.startswith(templates.BUILTIN_PREFIX):
                m.add_command(label="Delete…", command=lambda: self._delete(key, tpl))
        m.tk_popup(e.x_root, e.y_root)

    def _export(self, tpl):
        from ..userlib import safe_name
        p = filedialog.asksaveasfilename(parent=self.app.root, title="Export template", defaultextension=".ostpl",
                                         initialfile=safe_name(tpl["name"]) + ".ostpl",
                                         filetypes=[("OpenSchematix template", "*.ostpl")])
        if p:
            templates.TemplateStore.export_file(tpl, p)
            self.app.toast(f"Exported {os.path.basename(p)}", "success")

    def _delete(self, key, tpl):
        if messagebox.askyesno("Delete template", f"Delete the template “{tpl['name']}”?", parent=self.app.root):
            self.app.templates.delete(key)
            self.refresh()


# ================================================================ layers
class LayersPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Surface.TFrame")
        self.app = app
        PanelHeader(self, "Layers", [("plus", self.new, "New layer")]).pack(fill="x")
        frame, self.tree = _tree(self, ("cur", "vis", "lock", "prn", "name"), ("", "Show", "Lock", "Print", "Layer"),
                                 (22, 46, 42, 42, 120), height=8)
        frame.pack(fill="both", expand=True, padx=(6, 0))
        self.tree.bind("<ButtonRelease-1>", self._click)
        self.tree.bind("<Double-1>", lambda e: self.rename())
        self.tree.bind("<ButtonPress-3>", self._context)
        bar = ttk.Frame(self, style="Surface.TFrame", padding=(6, 4))
        bar.pack(fill="x")
        for icon, cmd, tip in (("plus", self.new, "New layer"), ("text", self.rename, "Rename layer"),
                               ("check", self.set_current, "Make current (new objects go on it)"),
                               ("theme", self.colour, "Layer colour"), ("delete", self.delete, "Delete layer")):
            IconButton(bar, icon, cmd, tip, size=15, bg_key="surface", pad=4).pack(side="left")
        self.note = ttk.Label(self, text="", style="Muted.TLabel", padding=(10, 2, 10, 10), wraplength=240,
                              justify="left")
        self.note.pack(fill="x")
        self.bind("<Configure>", lambda e: self.note.configure(wraplength=max(120, e.width - 24)))

    def refresh(self):
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        cur = self.app.current_layer
        t = current_theme()
        counts = {}
        for d in self.app.project.sheets:
            for coll in (d.components, d.wires, d.shapes):
                for o in coll.values():
                    counts[o.layer] = counts.get(o.layer, 0) + 1
        for l in self.app.project.layers:
            tag = "c_" + (l.color or "none").lstrip("#")
            self.tree.insert("", "end", l.name, values=("▸" if l.name == cur else "", "✓" if l.visible else "—",
                                                        "✓" if l.locked else "", "✓" if l.printable else "—",
                                                        f"{l.name}  ({counts.get(l.name, 0)})"), tags=(tag,))
            if l.color:
                self.tree.tag_configure(tag, foreground=l.color)
            elif t:
                self.tree.tag_configure(tag, foreground=t.ui["text"])
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])
        self.note.configure(text=f"Current layer: {cur or 'automatic (by object type)'}. Click Show/Lock/Print to "
                                 "toggle. Hidden layers are not drawn; locked layers cannot be selected.")

    def _click(self, e):
        node = self.tree.identify_row(e.y)
        col = self.tree.identify_column(e.x)
        if not node:
            return
        l = self.app.project.layer(node)
        if l is None:
            return
        attr = {"#2": "visible", "#3": "locked", "#4": "printable"}.get(col)
        if col == "#1":
            self.app.current_layer = None if self.app.current_layer == node else node
            self.refresh()
            return
        if attr:
            self.app.set_layer_attr(node, attr, not getattr(l, attr))

    def selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def new(self):
        name = simpledialog.askstring("New layer", "Layer name:", parent=self.app.root)
        if name and name.strip():
            self.app.add_layer(name.strip())

    def rename(self):
        n = self.selected()
        if not n:
            return
        name = simpledialog.askstring("Rename layer", "New name:", initialvalue=n, parent=self.app.root)
        if name and name.strip() and name.strip() != n:
            self.app.rename_layer(n, name.strip())

    def set_current(self):
        n = self.selected()
        if n:
            self.app.current_layer = n
            self.refresh()

    def colour(self):
        n = self.selected()
        if not n:
            return
        l = self.app.project.layer(n)
        res = colorchooser.askcolor(color=l.color or None, parent=self.app.root, title=f"Colour of layer {n}")
        if res and res[1]:
            self.app.set_layer_attr(n, "color", res[1])

    def delete(self):
        n = self.selected()
        if n:
            self.app.delete_layer(n)

    def _context(self, e):
        node = self.tree.identify_row(e.y)
        if node:
            self.tree.selection_set(node)
        m = make_menu(self)
        m.add_command(label="New layer…", command=self.new)
        if node:
            m.add_command(label="Make current", command=self.set_current)
            m.add_command(label="Rename…", command=self.rename)
            m.add_command(label="Colour…", command=self.colour)
            m.add_command(label="Reset colour", command=lambda: self.app.set_layer_attr(node, "color", ""))
            m.add_command(label="Select objects on this layer", command=lambda: self.app.select_layer(node))
            m.add_separator()
            m.add_command(label="Delete…", command=self.delete)
        m.tk_popup(e.x_root, e.y_root)


# ================================================================ check drawing results
SEV_LABEL = {"error": "Error", "warning": "Warning", "info": "Info"}


class CheckPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Surface.TFrame")
        self.app = app
        bar = ttk.Frame(self, style="Surface.TFrame", padding=(8, 6, 8, 4))
        bar.pack(fill="x")
        ttk.Button(bar, text="Check drawing", style="Accent.TButton", command=self.run).pack(side="left")
        self.filter = tk.StringVar(value="All")
        cb = ttk.Combobox(bar, textvariable=self.filter, values=("All", "Errors", "Warnings", "Info"),
                          state="readonly", width=10)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.show())
        self.scope = tk.StringVar(value="Project")
        cb2 = ttk.Combobox(bar, textvariable=self.scope, values=("Project", "Current sheet"), state="readonly",
                           width=13)
        cb2.pack(side="left")
        cb2.bind("<<ComboboxSelected>>", lambda e: self.show())
        self.summary = ttk.Label(bar, text="Not checked yet.", style="Muted.TLabel")
        self.summary.pack(side="left", padx=12)
        ttk.Label(bar, text="Passing these checks does not certify a drawing as safe or standards-compliant.",
                  style="Faint.TLabel").pack(side="right")
        frame, self.tree = _tree(self, ("sev", "msg", "obj", "sheet", "zone", "fix"),
                                 ("Severity", "Issue", "Object", "Sheet", "Zone", "Suggested action"),
                                 (80, 380, 90, 110, 50, 360), height=6)
        frame.pack(fill="both", expand=True, padx=(6, 0))
        self.tree.bind("<Double-1>", self._go)
        self.tree.bind("<Return>", self._go)
        self.issues = []
        self.map = {}

    def run(self):
        self.issues = checker.check(self.app.project)
        self.show()
        s = checker.summary(self.issues)
        self.app.set_validation(s)
        return s

    def show(self):
        t = current_theme()
        self.tree.delete(*self.tree.get_children())
        self.map = {}
        f = self.filter.get()
        want = {"All": None, "Errors": "error", "Warnings": "warning", "Info": "info"}[f]
        p = self.app.project
        for n, i in enumerate(self.issues):
            if want and i.severity != want:
                continue
            if self.scope.get() == "Current sheet" and i.sheet_uid != self.app.doc.uid:
                continue
            d = p.find_sheet(i.sheet_uid)
            o = d.item(i.obj_id) if d is not None and i.obj_id is not None else None
            obj = ""
            if o is not None and hasattr(o, "tag") and getattr(o, "symbol", None):
                obj = o.tag()
            elif o is not None and hasattr(o, "number"):
                obj = f"wire {o.number}" if o.number else "wire"
            zone = zone_of(d, i.point) if d is not None and i.point else ""
            iid = self.tree.insert("", "end", values=(SEV_LABEL[i.severity], i.message, obj, d.name if d else "",
                                                       zone, i.suggestion), tags=(i.severity,))
            self.map[iid] = i
        if t:
            self.tree.tag_configure("error", foreground=t.ui["danger"])
            self.tree.tag_configure("warning", foreground=t.ui["warning"])
            self.tree.tag_configure("info", foreground=t.ui["muted"])
        s = checker.summary(self.issues)
        self.summary.configure(text=f"{s['error']} errors · {s['warning']} warnings · {s['info']} notes"
                               if self.issues else "No problems found by the checks.")

    def _go(self, _e=None):
        sel = self.tree.selection()
        if sel and sel[0] in self.map:
            i = self.map[sel[0]]
            self.app.navigate(i.sheet_uid, i.obj_id, i.point)


# ================================================================ search
class SearchPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Surface.TFrame")
        self.app = app
        bar = ttk.Frame(self, style="Surface.TFrame", padding=(8, 6, 8, 4))
        bar.pack(fill="x")
        self.entry = SearchEntry(bar, "Search all sheets: identifier, part number, wire number, text…",
                                 on_enter=lambda q: self.run())
        self.entry.pack(side="left", fill="x", expand=True)
        fields = ["All fields"] + list(searcher.FIELDS.values())
        self.field = tk.StringVar(value=fields[0])
        cb = ttk.Combobox(bar, textvariable=self.field, values=fields, state="readonly", width=16)
        cb.pack(side="left", padx=6)
        self.exact = tk.IntVar(value=0)
        ttk.Checkbutton(bar, text="Whole value", variable=self.exact).pack(side="left")
        ttk.Button(bar, text="Search", command=self.run).pack(side="left", padx=(6, 0))
        self.count = ttk.Label(bar, text="", style="Muted.TLabel")
        self.count.pack(side="left", padx=10)
        frame, self.tree = _tree(self, ("obj", "field", "value", "sheet"), ("Object", "Matched field", "Value", "Sheet"),
                                 (220, 120, 260, 140), height=6)
        frame.pack(fill="both", expand=True, padx=(6, 0))
        self.tree.bind("<Double-1>", self._go)
        self.tree.bind("<Return>", self._go)
        self.hits = {}

    def run(self, query=None):
        if query is not None:
            self.entry.focus()
            self.entry.var.set(query)
            self.entry._ph = False
        q = self.entry.get()
        label = self.field.get()
        fields = None
        if label != "All fields":
            fields = {k for k, v in searcher.FIELDS.items() if v == label}
        hits = searcher.search(self.app.project, q, fields=fields, exact=bool(self.exact.get()))
        self.tree.delete(*self.tree.get_children())
        self.hits = {}
        for h in hits:
            iid = self.tree.insert("", "end", values=(h.title, h.field_label, h.value, f"{h.sheet_no}. {h.sheet_name}"))
            self.hits[iid] = h
        self.count.configure(text=f"{len(hits)} result{'s' if len(hits) != 1 else ''}")
        if len(hits) >= 1:
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
        return hits

    def _go(self, _e=None):
        sel = self.tree.selection()
        if sel and sel[0] in self.hits:
            h = self.hits[sel[0]]
            self.app.navigate(h.sheet_uid, h.obj_id, searcher.object_point(self.app.project, h))


def _unused():  # pragma: no cover
    return Tooltip
