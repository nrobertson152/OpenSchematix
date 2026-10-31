"""Report windows: bill of materials and connection / wire / terminal lists."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import bom, netlist
from .widgets import SearchEntry


class _ReportWindow(tk.Toplevel):
    def __init__(self, app, title, geometry="1100x560"):
        super().__init__(app.root)
        self.app = app
        self.title(title)
        self.geometry(geometry)
        self.configure(bg=app.theme.ui["surface"])
        self.transient(app.root)
        self.bind("<Escape>", lambda e: self.destroy())
        self.body = ttk.Frame(self, style="Surface.TFrame", padding=12)
        self.body.pack(fill="both", expand=True)
        app.windows.append(self)

    def make_table(self, parent, columns, sortable=True):
        frame = ttk.Frame(parent, style="Surface.TFrame")
        tv = ttk.Treeview(frame, columns=[c for c, _h, _w in columns], show="headings", selectmode="browse")
        for c, h, w in columns:
            tv.heading(c, text=h, anchor="w", command=(lambda c=c: self.sort_by(tv, c)) if sortable else "")
            tv.column(c, width=w, anchor="w", stretch=w >= 150)
        vs = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        tv.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tv._sort = (None, False)
        return frame, tv

    def sort_by(self, tv, col):
        last, desc = tv._sort
        desc = not desc if last == col else False
        tv._sort = (col, desc)
        rows = [(tv.set(k, col), k) for k in tv.get_children("")]
        rows.sort(key=lambda r: bom.natural_key(r[0]), reverse=desc)
        for i, (_v, k) in enumerate(rows):
            tv.move(k, "", i)

    def save_csv(self, text, default_name):
        p = filedialog.asksaveasfilename(parent=self, title="Export CSV", defaultextension=".csv",
                                         initialfile=default_name, filetypes=[("CSV (spreadsheet)", "*.csv")],
                                         initialdir=self.app.settings["last_dir"] or None)
        if not p:
            return
        try:
            from ..projectio import atomic_write_bytes
            atomic_write_bytes(p, text.encode("utf-8"))
        except OSError as e:
            messagebox.showerror("Export failed", str(e), parent=self)
            return
        self.app.toast(f"Exported {os.path.basename(p)}", "success")


class BomWindow(_ReportWindow):
    COLS = [("item", "Item", 50), ("quantity", "Qty", 50), ("designators", "Designators", 200),
            ("description", "Description", 220), ("manufacturer", "Manufacturer", 130),
            ("part_number", "Part number", 140), ("rating", "Rating", 100), ("symbol", "Symbol", 170),
            ("sheets", "Sheets", 120)]

    def __init__(self, app):
        super().__init__(app, "Bill of materials")
        top = ttk.Frame(self.body, style="Surface.TFrame")
        top.pack(fill="x", pady=(0, 8))
        self.scope = tk.StringVar(value="Whole project")
        cb = ttk.Combobox(top, textvariable=self.scope, values=("Whole project", "Current sheet"), state="readonly",
                          width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.search = SearchEntry(top, "Filter", on_change=lambda q: self.refresh())
        self.search.pack(side="left", fill="x", expand=True, padx=8)
        self.excluded = tk.IntVar(value=0)
        ttk.Checkbutton(top, text="Include non-purchasable items", variable=self.excluded,
                        command=self.refresh).pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Export CSV…", style="Accent.TButton", command=self.export).pack(side="left", padx=(8, 0))
        frame, self.tree = self.make_table(self.body, self.COLS)
        frame.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._go)
        self.status = ttk.Label(self.body, text="", style="Muted.TLabel")
        self.status.pack(anchor="w", pady=(6, 0))
        self.lines = []
        self.refresh()
        app.subscribe_changes(self._changed)
        self.bind("<Destroy>", lambda e: app.unsubscribe_changes(self._changed) if e.widget is self else None)

    def _changed(self):
        if self.winfo_exists():
            self.refresh()

    def refresh(self):
        uids = None if self.scope.get() == "Whole project" else {self.app.doc.uid}
        lines = bom.generate(self.app.project, uids, include_excluded=bool(self.excluded.get()))
        self.lines = bom.filter_lines(lines, self.search.get())
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for l in self.lines:
            r = l.as_row()
            iid = self.tree.insert("", "end", values=[r[c] for c, _h, _w in self.COLS])
            self.rows[iid] = l
        total = sum(l.quantity for l in self.lines)
        self.status.configure(text=f"{len(self.lines)} lines · {total} parts. Components are grouped by manufacturer "
                                   "and part number (or by symbol, description and rating). Double-click a line to "
                                   "find its first component. Untick “Include in BOM” in a component's properties to "
                                   "leave it out.")

    def export(self):
        title = self.app.project.meta.get("title") or "project"
        from ..userlib import safe_name
        self.save_csv(bom.bom_csv(self.lines), safe_name(title) + " BOM.csv")

    def _go(self, _e):
        sel = self.tree.selection()
        if sel and sel[0] in self.rows and self.rows[sel[0]].refs:
            uid, cid = self.rows[sel[0]].refs[0]
            self.app.navigate(uid, cid)


class ReportsWindow(_ReportWindow):
    def __init__(self, app, tab="connections"):
        super().__init__(app, "Connection reports")
        top = ttk.Frame(self.body, style="Surface.TFrame")
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="Number wires…", command=app.wire_number_dialog).pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=8)
        ttk.Button(top, text="Export this list as CSV…", style="Accent.TButton", command=self.export).pack(side="right")
        self.nb = ttk.Notebook(self.body)
        self.nb.pack(fill="both", expand=True)
        self.tabs = {}
        for key, title, cols in (("connections", "Connections (from–to)", netlist.CONNECTION_COLUMNS),
                                 ("wires", "Wire list", netlist.WIRE_COLUMNS),
                                 ("terminals", "Terminal strips", netlist.TERMINAL_COLUMNS)):
            frame, tv = self.make_table(self.nb, [(k, h, 150 if k in ("from", "to", "side1", "side2") else 100)
                                                  for k, h in cols])
            self.nb.add(frame, text=title)
            self.tabs[key] = (tv, cols)
        self.nb.select(list(self.tabs).index(tab) if tab in self.tabs else 0)
        self.note = ttk.Label(self.body, text="", style="Muted.TLabel", wraplength=1000, justify="left")
        self.note.pack(anchor="w", pady=(6, 0))
        self.data = {}
        self.refresh()
        app.subscribe_changes(self._changed)
        self.bind("<Destroy>", lambda e: app.unsubscribe_changes(self._changed) if e.widget is self else None)

    def _changed(self):
        if self.winfo_exists():
            self.refresh()

    def refresh(self):
        p = self.app.project
        nets = netlist.compute_nets(p)
        self.data = {"connections": netlist.connection_rows(p, nets), "wires": netlist.wire_rows(p),
                     "terminals": netlist.terminal_rows(p, nets)}
        for key, (tv, cols) in self.tabs.items():
            tv.delete(*tv.get_children())
            for r in self.data[key]:
                tv.insert("", "end", values=[r.get(k, "") for k, _h in cols])
        unnumbered = sum(1 for r in self.data["connections"] if not r["wire"])
        self.note.configure(text=f"{len(nets)} connections (nets), {len(self.data['wires'])} drawn wires, "
                                 f"{len(self.data['terminals'])} terminals."
                                 + (f" {unnumbered} rows have no wire number yet — use Number wires." if unnumbered
                                    else ""))

    def current_key(self):
        return list(self.tabs)[self.nb.index(self.nb.select())]

    def export(self):
        key = self.current_key()
        tv, cols = self.tabs[key]
        from ..userlib import safe_name
        title = self.app.project.meta.get("title") or "project"
        self.save_csv(netlist.to_csv(self.data[key], cols), f"{safe_name(title)} {key}.csv")
