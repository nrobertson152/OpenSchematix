"""Symbol library sidebar: search, favourites, recently used, the built-in
library (read-only) and the user's own libraries (folders, drag and drop,
import/export)."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import symbols
from ..model import Component
from ..render import component_prims
from . import theme as th
from .canvas_view import draw_items
from .widgets import IconButton, PanelHeader, SearchEntry, Tooltip, current_theme, make_menu

CONVENTIONS = ("All conventions", "IEC 60617", "IEEE 315 / ANSI", "NEMA ladder", "ISO 1219-1", "Custom")


class LibraryPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Surface.TFrame")
        self.app = app
        PanelHeader(self, "Symbols", [("symbol_edit", lambda: app.open_symbol_editor(), "New custom symbol…"),
                                      ("folder_add", self.new_library, "New library…"),
                                      ("import", self.import_menu, "Import symbols or a library…")]).pack(fill="x")
        top = ttk.Frame(self, style="Surface.TFrame", padding=(8, 0, 8, 6))
        top.pack(fill="x")
        self.search = SearchEntry(top, "Search symbols  (name, tag, prefix…)", on_change=lambda q: self.populate())
        self.search.pack(fill="x")
        self.convention = tk.StringVar(value=CONVENTIONS[0])
        cb = ttk.Combobox(top, textvariable=self.convention, values=CONVENTIONS, state="readonly")
        cb.pack(fill="x", pady=(6, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self.populate())
        body = ttk.Frame(self, style="Surface.TFrame")
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0))
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_preview())
        self.tree.bind("<Double-1>", self._double)
        self.tree.bind("<Return>", lambda e: self.place_selected())
        self.tree.bind("<ButtonPress-3>", self._context)
        self.tree.bind("<ButtonPress-1>", self._drag_start, add="+")
        self.tree.bind("<B1-Motion>", self._drag_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self._drag_end, add="+")
        self.drag = None
        # preview card
        card = ttk.Frame(self, style="Surface.TFrame", padding=(8, 6, 8, 8))
        card.pack(fill="x")
        ttk.Separator(card).pack(fill="x", pady=(0, 6))
        self.preview = tk.Canvas(card, height=int(110 * th.dpi_factor(self)), highlightthickness=1, borderwidth=0)
        self.preview.pack(fill="x")
        self.name_label = ttk.Label(card, text="", style="Bold.TLabel", wraplength=230, justify="left")
        self.name_label.pack(fill="x", pady=(6, 0))
        self.info = ttk.Label(card, text="", style="Muted.TLabel", wraplength=230, justify="left")
        self.info.pack(fill="x")
        row = ttk.Frame(card, style="Surface.TFrame")
        row.pack(fill="x", pady=(8, 0))
        self.place_btn = ttk.Button(row, text="Place", style="Accent.TButton", command=self.place_selected)
        self.place_btn.pack(side="left", fill="x", expand=True)
        self.fav_btn = IconButton(row, "star", self.toggle_favorite, "Add to / remove from favourites", size=16,
                                  bg_key="surface")
        self.fav_btn.pack(side="left", padx=(6, 0))
        self.edit_btn = IconButton(row, "symbol_edit", self.edit_selected, "Edit the symbol (built-in and project "
                                   "symbols open as an editable copy)", size=16, bg_key="surface")
        self.edit_btn.pack(side="left")
        self.bind("<Configure>", self._wrap)
        th.subscribe(lambda t: self.show_preview())
        self.populate()

    def _wrap(self, e):
        w = max(120, e.width - 24)
        self.info.configure(wraplength=w)
        self.name_label.configure(wraplength=w)

    # ---------------------------------------------------------------- content
    def _conv_ok(self, s):
        c = self.convention.get()
        if c.startswith("All"):
            return True
        if c == "Custom":
            return s.is_custom
        key = {"IEC 60617": "IEC 60617", "IEEE 315 / ANSI": "IEEE 315", "NEMA ladder": "NEMA",
               "ISO 1219-1": "ISO 1219"}[c]
        return key in s.convention

    def populate(self):
        open_nodes = {n for n in self._all_nodes() if self.tree.item(n, "open")}
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        q = self.search.get().strip()
        found = {s.id: s for s in symbols.search(q) if s.group != "Internal" and self._conv_ok(s)}
        st = self.app.settings
        favs = [sid for sid in st["favorite_symbols"] if sid in found]
        if favs or not q:
            n = self.tree.insert("", "end", "fav", text="★  Favourites", open=True)
            for sid in favs:
                self.tree.insert(n, "end", "fav|" + sid, text=found[sid].name)
            if not favs:
                self.tree.insert(n, "end", "hint|fav", text="Star a symbol to keep it here", tags=("hint",))
        recent = [sid for sid in st["recent_symbols"] if sid in found][:10]
        if recent:
            n = self.tree.insert("", "end", "rec", text="Recently used", open=bool(q) or "rec" in open_nodes)
            for sid in recent:
                self.tree.insert(n, "end", "rec|" + sid, text=found[sid].name)
        b = self.tree.insert("", "end", "builtin", text="Built-in library", open=True)
        for cat in symbols.CATEGORY_ORDER:
            in_cat = [s for s in found.values() if s.category == cat and not s.is_custom]
            if not in_cat:
                continue
            cn = self.tree.insert(b, "end", "cat|" + cat, text=cat, open=bool(q) or ("cat|" + cat) in open_nodes)
            groups = []
            for s in in_cat:
                if s.group not in groups:
                    groups.append(s.group)
            for g in groups:
                gid = f"grp|{cat}|{g}"
                gn = self.tree.insert(cn, "end", gid, text=g, open=bool(q) or gid in open_nodes)
                for s in in_cat:
                    if s.group == g:
                        label = s.name
                        if self._ambiguous(s):
                            conv = s.convention.replace(" style", "")
                            label = f"{s.name}  [{conv.split(' /')[0].split(' (')[0]}]"
                        self.tree.insert(gn, "end", "sym|" + s.id, text=label)
        lib = self.app.userlib
        u = self.tree.insert("", "end", "user", text="My libraries", open=True)
        folders = lib.folders()
        for f in folders:
            parent = "user" if "/" not in f else "dir|" + f.rsplit("/", 1)[0]
            if not self.tree.exists(parent):
                parent = "user"
            self.tree.insert(parent, "end", "dir|" + f, text=f.rsplit("/", 1)[-1],
                             open=bool(q) or ("dir|" + f) in open_nodes or "/" not in f)
        for e in (lib.search(q) if q else lib.entries.values()):
            if not self._conv_ok_doc(e.doc):
                continue
            parent = "dir|" + e.folder if e.folder else "user"
            if not self.tree.exists(parent):
                parent = "user"
            self.tree.insert(parent, "end", "usym|" + e.id, text=e.name)
        if not lib.entries and not folders:
            self.tree.insert(u, "end", "hint|user", text="Create a library with the folder button", tags=("hint",))
        if q:   # hide empty folders while searching
            for f in reversed(folders):
                node = "dir|" + f
                if self.tree.exists(node) and not self.tree.get_children(node):
                    self.tree.delete(node)
        t = current_theme()
        if t:
            self.tree.tag_configure("hint", foreground=t.ui["faint"])
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])
            self.tree.see(sel[0])
        self.show_preview()

    def _conv_ok_doc(self, doc):
        c = self.convention.get()
        return c.startswith("All") or c == "Custom" or c.split(" ")[0] in doc.get("convention", "")

    def _all_nodes(self, parent=""):
        out = []
        for n in self.tree.get_children(parent):
            out.append(n)
            out += self._all_nodes(n)
        return out

    @staticmethod
    def _ambiguous(s):
        return len([o for o in symbols.builtin_symbols() if o.name == s.name and o.category == s.category]) > 1

    def selected_symbol_id(self, node=None):
        node = node or (self.tree.selection() or [None])[0]
        if not node or "|" not in node:
            return None
        kind, rest = node.split("|", 1)
        if kind in ("sym", "usym", "fav", "rec"):
            return rest
        return None

    def selected_symbol(self):
        sid = self.selected_symbol_id()
        return symbols.get(sid) if sid else None

    def show_preview(self):
        t = current_theme()
        if t is None:
            return
        cv = self.preview
        cv.delete("all")
        cv.configure(bg=t["paper"], highlightbackground=t.ui["border"])
        s = self.selected_symbol()
        self.place_btn.state(["!disabled"] if s else ["disabled"])
        self.fav_btn.set_enabled(bool(s))
        self.edit_btn.set_enabled(bool(s))
        if not s:
            self.name_label.configure(text="")
            self.info.configure(text="Select a symbol to preview it. Double-click or drag it onto the drawing to "
                                     "place it.")
            return
        self.fav_btn.icon = "star_filled" if s.id in self.app.settings["favorite_symbols"] else "star"
        self.fav_btn.draw()
        comp = Component(0, s.id, 0, 0, params=s.default_params)
        items = [p for p in component_prims(comp, item=False)]
        b = comp.bbox()
        cv.update_idletasks()
        w = max(cv.winfo_width(), 200)
        h = int(cv["height"])
        z = min((w - 30) / max(b[2] - b[0], 1), (h - 24) / max(b[3] - b[1], 1), 3.2)
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2

        def ts(p):
            return (w / 2 + (p[0] - cx) * z, h / 2 + (p[1] - cy) * z)
        draw_items(cv, items, ts, z, t, self.app.canvas.font_family)
        for name, p in comp.terminals().items():
            x, y = ts(p)
            cv.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, outline=t["open_term"])
        terms = ", ".join(tt.label or tt.name for tt in comp.geometry().terminals)
        self.name_label.configure(text=s.name)
        txt = f"{s.description}\n" if s.description else ""
        txt += f"{s.convention}  ·  prefix {s.prefix or '—'}\nConnections: {terms or 'none'}"
        if s.is_custom:
            e = self.app.userlib.entries.get(s.id)
            txt += f"\nCustom symbol, revision {s.custom.get('revision', 0)}"
            if e:
                txt += f" · {e.folder or 'My libraries'}"
            if s.keywords:
                txt += f"\nTags: {', '.join(s.keywords)}"
            if s.aliases:
                txt += f"\nAliases: {', '.join(s.aliases)}"
        if s.notes:
            txt += f"\nNote: {s.notes}"
        self.info.configure(text=txt)

    # ---------------------------------------------------------------- actions
    def _double(self, e):
        node = self.tree.identify_row(e.y)
        if node and self.selected_symbol_id(node):
            self.place_selected()
            return "break"

    def place_selected(self):
        sid = self.selected_symbol_id()
        if sid:
            self.app.start_place(sid)

    def toggle_favorite(self):
        from ..userlib import toggle_favorite
        sid = self.selected_symbol_id()
        if sid:
            on = toggle_favorite(self.app.settings, sid)
            self.app.settings.save()
            self.populate()
            self.app.set_status("Added to favourites." if on else "Removed from favourites.")

    def edit_selected(self):
        s = self.selected_symbol()
        if s is None:
            return
        e = self.app.userlib.entries.get(s.id)
        if s.is_custom and e is not None:
            self.app.open_symbol_editor(doc=s.custom, folder=e.folder)
        else:
            # built-in or project-only symbols open as a copy: the original is never changed
            self.app.edit_symbol_copy(s.id)

    def selected_folder(self):
        node = (self.tree.selection() or [None])[0]
        if not node:
            return None
        if node.startswith("dir|"):
            return node[4:]
        if node.startswith("usym|"):
            e = self.app.userlib.entries.get(node[5:])
            return e.folder if e else None
        return None

    # ---------------------------------------------------------------- user library management
    def new_library(self, parent=""):
        name = simpledialog.askstring("New folder" if parent else "New library",
                                      "Name of the new folder:" if parent else "Name of the new library:",
                                      parent=self.app.root)
        if not name:
            return
        try:
            self.app.userlib.create_folder(parent, name)
        except (OSError, ValueError) as ex:
            messagebox.showerror("Could not create folder", str(ex), parent=self.app.root)
            return
        self.app.userlib.scan()
        self.populate()

    def import_menu(self):
        m = make_menu(self)
        m.add_command(label="Import library package (.osymlib)…", command=self.import_package)
        m.add_command(label="Import symbol file (.osym)…", command=self.import_symbol)
        x, y = self.winfo_pointerxy()
        m.tk_popup(x, y)

    def import_package(self):
        path = filedialog.askopenfilename(parent=self.app.root, title="Import symbol library",
                                          filetypes=[("OpenSchematix symbol library", "*.osymlib"), ("All files", "*")])
        if path:
            from .dialogs import LibraryImportDialog
            LibraryImportDialog(self.app, path, target=self.selected_folder() or "")

    def import_symbol(self):
        folder = self.selected_folder()
        if folder is None:
            libs = self.app.userlib.libraries()
            if not libs:
                self.app.userlib.create_folder("", "My symbols")
                libs = ["My symbols"]
            folder = libs[0]
        paths = filedialog.askopenfilenames(parent=self.app.root, title="Import symbols",
                                            filetypes=[("OpenSchematix symbol", "*.osym"), ("All files", "*")])
        n = 0
        for p in paths:
            try:
                if self.app.userlib.import_symbol_file(p, folder, "duplicate"):
                    n += 1
            except (OSError, ValueError) as ex:
                messagebox.showerror("Import failed", f"{os.path.basename(p)}: {ex}", parent=self.app.root)
        self.app.userlib.scan()
        self.populate()
        if n:
            self.app.toast(f"Imported {n} symbol(s) into “{folder}”.", "success")

    def _context(self, e):
        node = self.tree.identify_row(e.y)
        if node:
            self.tree.selection_set(node)
        m = make_menu(self)
        lib = self.app.userlib
        sid = self.selected_symbol_id(node) if node else None
        if sid:
            s = symbols.get(sid)
            m.add_command(label="Place", command=self.place_selected)
            fav = sid in self.app.settings["favorite_symbols"]
            m.add_command(label="Remove from favourites" if fav else "Add to favourites", command=self.toggle_favorite)
            m.add_separator()
            if s is not None and s.is_custom and sid in lib.entries:
                e_ = lib.entries[sid]
                m.add_command(label="Edit symbol…", command=self.edit_selected)
                m.add_command(label="Edit a copy…", command=lambda: self.app.edit_symbol_copy(sid))
                m.add_command(label="Rename…", command=lambda: self._rename_symbol(sid))
                m.add_command(label="Tags and category…", command=lambda: self._tags(sid))
                m.add_command(label="Duplicate", command=lambda: self._do(lambda: lib.copy_symbol(sid, e_.folder)))
                m.add_command(label="Move to folder…", command=lambda: self._move_symbol(sid))
                m.add_command(label="Export symbol…", command=lambda: self._export_symbol(sid))
                if sid in self.app.project.used_custom_symbols():
                    m.add_command(label="Update drawings to this version", command=lambda: self.app.update_project_symbol(sid))
                m.add_separator()
                m.add_command(label="Delete symbol…", command=lambda: self._delete_symbol(sid))
            elif s is not None:
                # built-in or project symbol: editing always starts from a copy
                m.add_command(label="Edit a copy…", command=lambda: self.app.edit_symbol_copy(sid))
        elif node and (node.startswith("dir|") or node == "user"):
            folder = node[4:] if node.startswith("dir|") else ""
            m.add_command(label="New symbol here…", command=lambda: self.app.open_symbol_editor(folder=folder or None))
            m.add_command(label="New folder…" if folder else "New library…", command=lambda: self.new_library(folder))
            if folder:
                m.add_command(label="Rename folder…", command=lambda: self._rename_folder(folder))
                m.add_command(label="Duplicate folder", command=lambda: self._do(
                    lambda: lib.copy_folder(folder, folder.rsplit("/", 1)[0] if "/" in folder else "")))
                m.add_separator()
                m.add_command(label="Export as library package…", command=lambda: self._export_package(folder))
            m.add_command(label="Import library package…", command=self.import_package)
            m.add_command(label="Import symbol file…", command=self.import_symbol)
            if folder:
                m.add_separator()
                m.add_command(label="Delete folder…", command=lambda: self._delete_folder(folder))
        elif node and node.startswith(("cat|", "grp|", "builtin", "sym|")):
            m.add_command(label="Built-in symbols are read-only", state="disabled")
        else:
            return
        m.tk_popup(e.x_root, e.y_root)

    def _do(self, fn):
        try:
            fn()
        except (OSError, ValueError, KeyError) as ex:
            messagebox.showerror("Library", str(ex), parent=self.app.root)
        self.app.userlib.scan()
        self.populate()

    def _rename_symbol(self, sid):
        e = self.app.userlib.entries[sid]
        name = simpledialog.askstring("Rename symbol", "New name:", initialvalue=e.name, parent=self.app.root)
        if name:
            self._do(lambda: self.app.userlib.rename_symbol(sid, name))

    def _tags(self, sid):
        e = self.app.userlib.entries[sid]
        tags = simpledialog.askstring("Tags", "Tags (comma separated):", initialvalue=", ".join(e.doc.get("tags", [])),
                                      parent=self.app.root)
        if tags is None:
            return
        cat = simpledialog.askstring("Category", "Category (Electrical, Electronic, Hydraulic, Pneumatic, General):",
                                     initialvalue=e.doc.get("category", "General"), parent=self.app.root)
        self._do(lambda: self.app.userlib.set_tags(sid, tags.split(","), cat or None))

    def _choose_folder(self, title):
        folders = self.app.userlib.folders()
        if not folders:
            messagebox.showinfo(title, "Create a library first.", parent=self.app.root)
            return None
        from .dialogs import ChoiceDialog
        return ChoiceDialog(self.app, title, "Folder:", folders).result

    def _move_symbol(self, sid):
        f = self._choose_folder("Move symbol")
        if f is not None:
            self._do(lambda: self.app.userlib.move_symbol(sid, f))

    def _export_symbol(self, sid):
        e = self.app.userlib.entries[sid]
        from ..userlib import safe_name
        p = filedialog.asksaveasfilename(parent=self.app.root, title="Export symbol", defaultextension=".osym",
                                         initialfile=safe_name(e.name) + ".osym",
                                         filetypes=[("OpenSchematix symbol", "*.osym")])
        if p:
            self._do(lambda: self.app.userlib.export_symbol(sid, p))
            self.app.toast(f"Exported {os.path.basename(p)}", "success")

    def _delete_symbol(self, sid):
        e = self.app.userlib.entries[sid]
        used = sid in self.app.project.used_custom_symbols()
        msg = f"Delete the symbol “{e.name}” from your library?"
        if used:
            msg += "\n\nThe open project uses it; the project keeps its own copy, so its drawings are not affected."
        if messagebox.askyesno("Delete symbol", msg, parent=self.app.root):
            self._do(lambda: self.app.userlib.delete_symbol(sid))

    def _rename_folder(self, folder):
        name = simpledialog.askstring("Rename folder", "New name:", initialvalue=folder.rsplit("/", 1)[-1],
                                      parent=self.app.root)
        if name:
            self._do(lambda: self.app.userlib.rename_folder(folder, name))

    def _delete_folder(self, folder):
        n = len(self.app.userlib.in_folder(folder, recursive=True))
        if messagebox.askyesno("Delete folder", f"Delete the folder “{folder}” and the {n} symbol(s) in it?\n\n"
                               "This cannot be undone.", icon="warning", parent=self.app.root):
            self._do(lambda: self.app.userlib.delete_folder(folder))

    def _export_package(self, folder):
        from ..userlib import safe_name
        p = filedialog.asksaveasfilename(parent=self.app.root, title="Export library", defaultextension=".osymlib",
                                         initialfile=safe_name(folder.rsplit("/", 1)[-1]) + ".osymlib",
                                         filetypes=[("OpenSchematix symbol library", "*.osymlib")])
        if p:
            try:
                man = self.app.userlib.export_package(folder, p, author=self.app.project.meta.get("author", ""))
            except OSError as ex:
                messagebox.showerror("Export failed", str(ex), parent=self.app.root)
                return
            self.app.toast(f"Exported {len(man['symbols'])} symbols to {os.path.basename(p)}", "success")

    # ---------------------------------------------------------------- drag and drop
    def _drag_start(self, e):
        node = self.tree.identify_row(e.y)
        self.drag = {"node": node, "x": e.x_root, "y": e.y_root, "active": False} if node else None

    def _drag_motion(self, e):
        d = self.drag
        if not d:
            return
        if not d["active"] and abs(e.x_root - d["x"]) + abs(e.y_root - d["y"]) > 8:
            if self.selected_symbol_id(d["node"]) or d["node"].startswith("dir|"):
                d["active"] = True
                self.tree.configure(cursor="hand2")
        if d["active"]:
            w = self.winfo_containing(e.x_root, e.y_root)
            if w is self.app.canvas:
                self.app.set_status("Release to place the symbol here.")

    def _drag_end(self, e):
        d, self.drag = self.drag, None
        self.tree.configure(cursor="")
        if not d or not d["active"]:
            return
        target = self.winfo_containing(e.x_root, e.y_root)
        node = d["node"]
        sid = self.selected_symbol_id(node)
        if target is self.app.canvas and sid:
            cx = e.x_root - self.app.canvas.winfo_rootx()
            cy = e.y_root - self.app.canvas.winfo_rooty()
            self.app.place_at(sid, self.app.canvas.to_world(cx, cy))
            return
        if target is self.tree:
            ty = e.y_root - self.tree.winfo_rooty()
            dest = self.tree.identify_row(ty)
            if not dest:
                return
            if dest.startswith("usym|"):
                ent = self.app.userlib.entries.get(dest[5:])
                dest_folder = ent.folder if ent else None
            elif dest.startswith("dir|"):
                dest_folder = dest[4:]
            elif dest == "user":
                dest_folder = ""
            else:
                return
            if node.startswith("usym|") and dest_folder is not None and dest_folder != "":
                self._do(lambda: self.app.userlib.move_symbol(node[5:], dest_folder))
            elif node.startswith("dir|") and dest_folder is not None and node[4:] != dest_folder:
                self._do(lambda: self.app.userlib.move_folder(node[4:], dest_folder))
            elif node.startswith(("sym|", "fav|", "rec|")) and dest_folder:
                # copy a built-in symbol into a user library as an editable custom symbol
                self.app.open_symbol_editor(from_builtin=sid, folder=dest_folder)


def _unused():  # pragma: no cover
    return Tooltip
