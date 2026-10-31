"""Revision history window, issuing revisions and graphical comparison."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .. import compare as cmp
from .. import revisions
from ..render import scene
from . import theme as th
from .canvas_view import PreviewView
from .dialogs import Dialog, form

CURRENT = "Current drawing (unsaved state)"


class IssueRevisionDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Issue revision")
        st = app.project.revisions
        last = st.approved()[-1]["label"] if st and st.approved() else None
        style = "number" if last and last.isdigit() else "letter"
        f, self.vars = form(self.frame, [("label", "Revision", revisions.next_label(last, style)),
                                         ("description", "Description", ""),
                                         ("author", "Drawn by", app.project.meta.get("author", "")),
                                         ("approved_by", "Approved by", app.project.meta.get("approved_by", ""))])
        f.pack(fill="x")
        self.update_tb = tk.IntVar(value=1)
        ttk.Checkbutton(self.frame, text="Show this revision in the title blocks (project revision field)",
                        variable=self.update_tb).pack(anchor="w", pady=(8, 0))
        ttk.Label(self.frame, text="A formal revision stores a permanent snapshot of the whole project inside the "
                                   "project file and appears in the revision table of every sheet.",
                  style="Muted.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(8, 0))
        self.buttons("Issue")
        self.show_modal()

    def ok(self):
        v = {k: x.get().strip() for k, x in self.vars.items()}
        if not v["label"]:
            messagebox.showinfo("Issue revision", "Enter a revision identifier.", parent=self)
            return
        self.app.issue_revision(v["label"], v["description"], v["author"], v["approved_by"], bool(self.update_tb.get()))
        self.destroy()


class RevisionsWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Revision history")
        self.geometry("900x520")
        self.configure(bg=app.theme.ui["surface"])
        self.transient(app.root)
        self.bind("<Escape>", lambda e: self.destroy())
        app.windows.append(self)
        body = ttk.Frame(self, style="Surface.TFrame", padding=12)
        body.pack(fill="both", expand=True)
        top = ttk.Frame(body, style="Surface.TFrame")
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="Issue revision…", style="Accent.TButton", command=lambda: IssueRevisionDialog(app)).pack(
            side="left")
        ttk.Button(top, text="Snapshot now", command=self.snapshot).pack(side="left", padx=6)
        ttk.Button(top, text="View", command=self.view).pack(side="left")
        ttk.Button(top, text="Compare…", command=self.compare).pack(side="left", padx=6)
        ttk.Button(top, text="Restore…", command=self.restore).pack(side="left")
        ttk.Button(top, text="Delete snapshot", command=self.delete).pack(side="left", padx=6)
        self.tree = ttk.Treeview(body, columns=("n", "kind", "label", "when", "desc", "by"), show="headings",
                                 selectmode="extended")
        for c, h, w in (("n", "#", 40), ("kind", "Type", 110), ("label", "Rev.", 50), ("when", "Date", 140),
                        ("desc", "Description", 330), ("by", "By / approved", 160)):
            self.tree.heading(c, text=h, anchor="w")
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.view())
        self.info = ttk.Label(body, text="", style="Muted.TLabel", wraplength=860, justify="left")
        self.info.pack(anchor="w", pady=(6, 0))
        self.refresh()
        app.subscribe_changes(self._changed)
        self.bind("<Destroy>", lambda e: app.unsubscribe_changes(self._changed) if e.widget is self else None)

    def _changed(self):
        if self.winfo_exists():
            self.refresh()

    def refresh(self):
        st = self.app.project.revisions
        self.tree.delete(*self.tree.get_children())
        if st is None:
            return
        for e in reversed(st.entries):
            kind = "Approved revision" if e["kind"] == "approved" else "Automatic"
            by = " / ".join(x for x in (e.get("author", ""), e.get("approved_by", "")) if x)
            self.tree.insert("", "end", str(e["n"]), values=(e["n"], kind, e.get("label", ""),
                                                              e["timestamp"].replace("T", " "), e.get("description", ""),
                                                              by))
        self.info.configure(text=f"{len(st.approved())} approved revisions and "
                                 f"{len(st.entries) - len(st.approved())} automatic snapshots "
                                 f"(automatic snapshots are made when you save; the newest {revisions.AUTO_KEEP} are "
                                 f"kept). Unchanged sheets are stored only once: history uses "
                                 f"{st.stored_bytes() / 1024:.0f} KB inside the project file.")

    def selected(self):
        return [int(i) for i in self.tree.selection()]

    def snapshot(self):
        e = self.app.project.revisions.create(self.app.project, "auto", description="Manual snapshot", force=True)
        self.app.mark_dirty()
        self.refresh()
        self.app.toast(f"Snapshot #{e['n']} created.", "success")

    def view(self):
        sel = self.selected()
        if sel:
            p = self.app.project.revisions.load(sel[0])
            CompareWindow(self.app, ("#%d" % sel[0], p), None)

    def compare(self):
        sel = self.selected()
        st = self.app.project.revisions
        if len(sel) >= 2:
            a, b = sorted(sel)[:2]
            CompareWindow(self.app, (f"#{a}", st.load(a)), (f"#{b}", st.load(b)))
        elif len(sel) == 1:
            CompareWindow(self.app, (f"#{sel[0]}", st.load(sel[0])), (CURRENT, self.app.project))
        else:
            messagebox.showinfo("Compare", "Select one revision (to compare with the current drawing) or two "
                                           "revisions.", parent=self)

    def restore(self):
        sel = self.selected()
        if len(sel) != 1:
            return
        if messagebox.askyesno("Restore revision", f"Replace the current project content with snapshot #{sel[0]}?\n\n"
                               "The current state is saved as an automatic snapshot first, and the restore can be "
                               "undone with Undo.", parent=self):
            self.app.restore_revision(sel[0])
            self.refresh()

    def delete(self):
        st = self.app.project.revisions
        for n in self.selected():
            try:
                st.delete(n)
            except ValueError as e:
                messagebox.showinfo("Delete", str(e), parent=self)
                return
        self.app.mark_dirty()
        self.refresh()


class CompareWindow(tk.Toplevel):
    """Graphical comparison of two project versions (or view of one)."""

    def __init__(self, app, a, b):
        super().__init__(app.root)
        self.app = app
        self.a_label, self.a = a
        self.b_label, self.b = (b if b is not None else (None, None))
        single = b is None
        self.title(f"Revision {self.a_label}" if single else f"Compare {self.a_label} → {self.b_label}")
        self.geometry("1280x760")
        self.configure(bg=app.theme.ui["surface"])
        self.transient(app.root)
        self.bind("<Escape>", lambda e: self.destroy())
        app.windows.append(self)
        self.diff = None if single else cmp.compare(self.a, self.b)
        top = ttk.Frame(self, style="Surface.TFrame", padding=(10, 8))
        top.pack(fill="x")
        ref = self.a if single else self.b
        sheets = list(ref.sheets)
        if not single:
            sheets += [s for s in self.a.sheets if self.b.find_sheet(s.uid) is None]
        self.sheet_ids = [s.uid for s in sheets]
        names = [f"{i + 1}. {s.name}" + ("  (removed)" if not single and self.b.find_sheet(s.uid) is None else "")
                 for i, s in enumerate(sheets)]
        ttk.Label(top, text="Sheet", style="Surface.TLabel").pack(side="left")
        self.sheet = tk.StringVar(value=names[0] if names else "")
        cb = ttk.Combobox(top, textvariable=self.sheet, values=names, state="readonly", width=34)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.show())
        self.names = names
        self.mode = tk.StringVar(value="Overlay")
        if not single:
            for m in ("Overlay", "Side by side"):
                ttk.Radiobutton(top, text=m, value=m, variable=self.mode, command=self.build_views).pack(side="left",
                                                                                                         padx=4)
            leg = ttk.Frame(top, style="Surface.TFrame")
            leg.pack(side="right")
            for key, text in (("diff_added", "added"), ("diff_modified", "modified"), ("diff_removed", "removed"),
                              ("diff_same", "unchanged")):
                tk.Frame(leg, bg=app.theme[key], width=12, height=12).pack(side="left", padx=(0, 4))
                ttk.Label(leg, text=text, style="Muted.TLabel").pack(side="left", padx=(0, 10))
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True)
        self.view_frame = ttk.Frame(pane, style="Surface.TFrame")
        pane.add(self.view_frame, weight=3)
        if not single:
            side = ttk.Frame(pane, style="Surface.TFrame", padding=8)
            pane.add(side, weight=1)
            counts = self.diff.counts()
            summary = ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) or "No differences."
            ttk.Label(side, text="Changes", style="Bold.TLabel").pack(anchor="w")
            ttk.Label(side, text=summary, style="Muted.TLabel", wraplength=320, justify="left").pack(anchor="w")
            self.tree = ttk.Treeview(side, show="tree", selectmode="browse")
            self.tree.pack(fill="both", expand=True, pady=(6, 0))
            self.tree.bind("<<TreeviewSelect>>", self._select_change)
            self.change_map = {}
            groups = {}
            for i, c in enumerate(self.diff.changes):
                gkey = c.sheet_uid or "_project"
                if gkey not in groups:
                    s = self.b.find_sheet(c.sheet_uid) or self.a.find_sheet(c.sheet_uid)
                    groups[gkey] = self.tree.insert("", "end", text=s.name if s else "Project", open=True)
                node = self.tree.insert(groups[gkey], "end", text=f"[{c.status}] {c.title}", open=False)
                self.change_map[node] = c
                for d in c.details:
                    self.tree.insert(node, "end", text=d)
        self.views = []
        self.build_views()

    def build_views(self):
        for w in self.view_frame.winfo_children():
            w.destroy()
        self.views = []
        side = self.diff is not None and self.mode.get() == "Side by side"
        n = 2 if side else 1
        for i in range(n):
            col = ttk.Frame(self.view_frame, style="Surface.TFrame")
            col.pack(side="left", fill="both", expand=True)
            if side:
                ttk.Label(col, text=self.a_label if i == 0 else self.b_label, style="Heading.TLabel",
                          padding=(8, 4)).pack(anchor="w")
            v = PreviewView(col, self.app.theme)
            v.font_family = self.app.canvas.font_family
            v.pack(fill="both", expand=True)
            self.views.append(v)
        self.after(50, self.show)

    def _uid(self):
        try:
            return self.sheet_ids[self.names.index(self.sheet.get())]
        except ValueError:
            return self.sheet_ids[0] if self.sheet_ids else None

    def show(self):
        uid = self._uid()
        if uid is None:
            return
        t = self.app.theme
        if self.diff is None:
            d = self.a.find_sheet(uid)
            self.views[0].show(d, self.a)
            return
        da, db = self.a.find_sheet(uid), self.b.find_sheet(uid)
        added = self.diff.ids(uid, cmp.ADDED)
        removed = self.diff.ids(uid, cmp.REMOVED)
        modified = self.diff.ids(uid, cmp.MODIFIED)

        def color_new(it):
            i = it.get("item")
            if it.get("role") == "frame":
                return t["frame"]
            if i in added:
                return t["diff_added"]
            if i in modified:
                return t["diff_modified"]
            return t["diff_same"]

        def color_old(it):
            i = it.get("item")
            if it.get("role") == "frame":
                return None
            return t["diff_removed"] if i in removed else None
        if len(self.views) == 2:
            def color_a(it):
                i = it.get("item")
                if it.get("role") == "frame":
                    return t["frame"]
                if i in removed:
                    return t["diff_removed"]
                if i in modified:
                    return t["diff_modified"]
                return t["diff_same"]
            if da is not None:
                ia = scene(da, screen=False, project=self.a)
                self.views[0].show(da, self.a, lambda: [(ia, color_a)])
            if db is not None:
                ib = scene(db, screen=False, project=self.b)
                self.views[1].show(db, self.b, lambda: [(ib, color_new)])
            return
        base = db or da
        layers = []
        if da is not None:
            ia = scene(da, screen=False, frame=False, project=self.a)
            layers.append((ia, color_old))
        if db is not None:
            ib = scene(db, screen=False, project=self.b)
            layers.append((ib, color_new))
        self.views[0].show(base, self.b, lambda: layers)

    def _select_change(self, _e):
        sel = self.tree.selection()
        c = self.change_map.get(sel[0]) if sel else None
        if c is None or not c.sheet_uid:
            return
        if c.sheet_uid in self.sheet_ids:
            self.sheet.set(self.names[self.sheet_ids.index(c.sheet_uid)])
            self.show()
        d = self.b.find_sheet(c.sheet_uid) if c.status != cmp.REMOVED else self.a.find_sheet(c.sheet_uid)
        o = d.item(c.obj_id) if d is not None and c.obj_id is not None else None
        if o is not None:
            b = o.bbox()
            for v in self.views:
                v.after(80, lambda v=v, b=b: v.fit_box((b[0] - 120, b[1] - 120, b[2] + 120, b[3] + 120)))


def _unused():  # pragma: no cover
    return th
