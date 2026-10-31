"""Context-sensitive properties inspector (right sidebar).

Shows the sheet and project settings when nothing is selected; component,
wire or drafting-shape properties otherwise. Multiple selected objects can
be edited together: fields whose values differ are shown empty (“mixed”)
and are only written when changed. Every edit is one undo step.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import symbols
from ..geometry import UNIT_MM
from ..model import (CUSTOM_SIZE, PROP_LABELS, SHEET_SIZE_GROUPS, STANDARD_SCALES, TITLE_BLOCK_NAMES, TITLE_BLOCKS,
                     Component, Shape, Wire)
from ..symbols.base import PORT_TYPES
from .widgets import IconButton, PanelHeader, ScrollFrame, Section, current_theme

MIXED = ""
SIDES = ("auto", "above", "below", "left", "right")


def _common(objs, getter):
    vals = {getter(o) for o in objs}
    return vals.pop() if len(vals) == 1 else None


class Inspector(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Surface.TFrame")
        self.app = app
        self.header = PanelHeader(self, "Properties")
        self.header.pack(fill="x")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.first_entry = None
        self.collapsed = set(app.settings["layout"].get("collapsed_sections", []))
        self._sig = None

    # ---------------------------------------------------------------- building blocks
    def section(self, title):
        s = Section(self.scroll.inner, title, expanded=title not in self.collapsed,
                    on_toggle=lambda exp, t=title: self._toggled(t, exp))
        s.pack(fill="x")
        ttk.Separator(self.scroll.inner).pack(fill="x")
        return s

    def _toggled(self, title, expanded):
        (self.collapsed.discard if expanded else self.collapsed.add)(title)
        lay = self.app.settings["layout"]
        lay["collapsed_sections"] = sorted(self.collapsed)
        self.app.settings["layout"] = lay

    def entry(self, sec, label, value, commit, width=None, hint="", readonly=False):
        var = tk.StringVar(value="" if value is None else str(value))
        e = ttk.Entry(sec.body, textvariable=var, width=width or 14)
        if readonly:
            e.state(["readonly"])
        orig = var.get()

        def do_commit(_e=None):
            nonlocal orig
            v = var.get()
            if v != orig:
                orig = v
                commit(v)
        e.bind("<Return>", do_commit)
        e.bind("<KP_Enter>", do_commit)
        e.bind("<FocusOut>", do_commit)
        sec.add_row(label, e, hint)
        if self.first_entry is None and not readonly:
            self.first_entry = e
        return e

    def combo(self, sec, label, value, values, commit, labels=None, hint=""):
        labels = labels or list(values)
        var = tk.StringVar(value=labels[list(values).index(value)] if value in values else "")
        cb = ttk.Combobox(sec.body, textvariable=var, values=labels, state="readonly", width=14)

        def changed(_e=None):
            if var.get() in labels:
                commit(list(values)[labels.index(var.get())])
        cb.bind("<<ComboboxSelected>>", changed)
        sec.add_row(label, cb, hint)
        return cb

    def check(self, sec, label, value, commit, hint=""):
        var = tk.IntVar(value=1 if value else 0)
        cb = ttk.Checkbutton(sec.body, text=label, variable=var,
                             command=lambda: commit(bool(var.get())))
        if value is None:
            cb.state(["alternate"])
        sec.add_full(cb)
        return cb

    def button(self, sec, text, cmd, style="TButton"):
        b = ttk.Button(sec.body, text=text, command=cmd, style=style)
        sec.add_full(b, pady=(4, 2))
        return b

    def note(self, sec, text, style="Muted.TLabel"):
        lab = ttk.Label(sec.body, text=text, style=style, wraplength=240, justify="left")
        sec.add_full(lab)
        return lab

    # ---------------------------------------------------------------- refresh
    def refresh(self, force=False):
        app = self.app
        doc = app.doc
        sel = [doc.item(i) for i in app.selection if doc.item(i) is not None]
        sig = (doc.uid, tuple(sorted(app.selection)), app.change_counter)
        if sig == self._sig and not force:
            return
        self._sig = sig
        self.scroll.clear()
        self.first_entry = None
        comps = [o for o in sel if isinstance(o, Component)]
        wires = [o for o in sel if isinstance(o, Wire)]
        shapes = [o for o in sel if isinstance(o, Shape)]
        if not sel:
            self.header.title.configure(text="SHEET")
            self._sheet()
        elif comps and not wires and not shapes:
            self.header.title.configure(text="COMPONENT" if len(comps) == 1 else f"{len(comps)} COMPONENTS")
            self._components(comps)
        elif wires and not comps and not shapes:
            self.header.title.configure(text="WIRE" if len(wires) == 1 else f"{len(wires)} WIRES")
            self._wires(wires)
        elif shapes and not comps and not wires:
            self.header.title.configure(text="DRAWING OBJECT" if len(shapes) == 1 else f"{len(shapes)} OBJECTS")
            self._shapes(shapes)
        else:
            self.header.title.configure(text=f"{len(sel)} OBJECTS")
            self._mixed(sel)

    # ---------------------------------------------------------------- nothing selected: sheet
    def _sheet(self):
        app, doc = self.app, self.app.doc
        s = doc.sheet
        sec = self.section("General")
        self.entry(sec, "Name", doc.name, lambda v: app.rename_sheet(doc.uid, v))
        self.entry(sec, "Title", s.title, lambda v: app.set_sheet(title=v), hint="Sheet title (empty: project title)")
        self.entry(sec, "Drawing no.", s.drawing_number, lambda v: app.set_sheet(drawing_number=v),
                   hint="Empty: project number + sheet number")
        self.entry(sec, "Description", s.description, lambda v: app.set_sheet(description=v))
        num = app.project.sheet_number_text(doc)
        self.entry(sec, "Sheet no.", s.sheet, lambda v: app.set_sheet(sheet=v),
                   hint=f"Empty = automatic ({num})")
        sec = self.section("Page")
        sizes, labels = [], []
        for group, names in SHEET_SIZE_GROUPS:
            for n in names:
                sizes.append(n)
                labels.append(n if group != "ANSI" else n)
        sizes.append(CUSTOM_SIZE)
        labels.append("Custom…")
        self.combo(sec, "Size", s.size, sizes, lambda v: app.set_sheet(size=v), labels)
        if s.size == CUSTOM_SIZE:
            self.entry(sec, "Width mm", f"{s.custom_w:g}", lambda v: self._num(v, lambda f: app.set_sheet(custom_w=f)))
            self.entry(sec, "Height mm", f"{s.custom_h:g}", lambda v: self._num(v, lambda f: app.set_sheet(custom_h=f)))
        else:
            self.combo(sec, "Orientation", s.orientation, ("landscape", "portrait"),
                       lambda v: app.set_sheet(orientation=v), ["Landscape", "Portrait"])
        self.combo(sec, "Title block", s.title_block if s.show_title_block else "none", TITLE_BLOCKS,
                   lambda v: app.set_sheet(title_block=v, show_title_block=v != "none"),
                   [TITLE_BLOCK_NAMES[t] for t in TITLE_BLOCKS])
        self.check(sec, "Reference zones on the frame", s.zones, lambda v: app.set_sheet(zones=v))
        sc = ttk.Combobox(sec.body, values=STANDARD_SCALES, width=14)
        sc.set(s.scale)
        sc.bind("<<ComboboxSelected>>", lambda e: app.set_plot_scale(sc.get()))
        sc.bind("<Return>", lambda e: app.set_plot_scale(sc.get()))
        sec.add_row("Print scale", sc, "Presentation scale: how large the drawing prints on the sheet. "
                                       "Geometry and symbols are not changed.")
        self.button(sec, "Fit drawing to sheet", app.fit_to_sheet)
        sec = self.section("Title block overrides")
        for key, label in (("author", "Drawn by"), ("checked_by", "Checked by"), ("approved_by", "Approved by"),
                           ("date", "Date"), ("revision", "Revision"), ("organisation", "Organisation")):
            self.entry(sec, label, getattr(s, key), lambda v, k=key: app.set_sheet(**{k: v}),
                       hint="Empty: use the project value")
        sec = self.section("Project")
        p = app.project
        self.note(sec, f"{p.meta.get('title') or 'Untitled project'}\n{len(p.sheets)} sheet(s) · "
                       f"{sum(len(d.components) for d in p.sheets)} components")
        self.button(sec, "Project properties…", app.project_properties)

    def _num(self, text, fn):
        try:
            v = float(text.replace(",", "."))
        except ValueError:
            self.app.set_status(f"“{text}” is not a number.")
            return
        fn(v)

    # ---------------------------------------------------------------- components
    def _components(self, comps):
        app = self.app
        one = comps[0] if len(comps) == 1 else None
        sd = symbols.get(one.symbol) if one else None
        sec = self.section("Identification")
        e = self.entry(sec, "Identifier", _common(comps, lambda c: c.designator),
                       lambda v: app.edit_components(comps, designator=v.strip()),
                       hint="Reference designator, e.g. K1. Parts of one device (coil and contacts) may share it.")
        self.designator_entry = e
        self.entry(sec, "Label", _common(comps, lambda c: c.label), lambda v: app.edit_components(comps, label=v))
        if one:
            row = ttk.Frame(sec.body, style="Surface.TFrame")
            ttk.Label(row, text=sd.name if sd else one.symbol, style="Surface.TLabel", wraplength=170,
                      justify="left").pack(side="left", fill="x", expand=True)
            IconButton(row, "refresh", lambda: app.replace_symbol(comps), "Replace symbol…", size=14,
                       bg_key="surface").pack(side="right")
            sec.add_row("Symbol", row)
            if sd is not None:
                self.note(sec, f"{sd.category} · {sd.convention}" + (" · custom" if sd.is_custom else ""))
                if sd.parametric:
                    self.button(sec, "Configure valve…", lambda: app.configure_valve(one.id))
                if sd.is_custom:
                    self.button(sec, "Edit symbol…", lambda: app.edit_custom_symbol(one.symbol))
                self.button(sec, "Edit a copy of the symbol…",
                            lambda: app.edit_symbol_copy(one.symbol, dict(one.params) or None))
            from ..project import is_terminal_symbol
            if is_terminal_symbol(one.symbol):
                self.entry(sec, "Terminal no.", one.props.get("terminal", ""),
                           lambda v: app.edit_components(comps, props={"terminal": v.strip()}),
                           hint="Number of this terminal on strip " + (one.designator or "X1"))
        sec = self.section("Part")
        for key in ("description", "manufacturer", "part_number", "rating"):
            self.entry(sec, PROP_LABELS[key], _common(comps, lambda c, k=key: c.props.get(k, "")),
                       lambda v, k=key: app.edit_components(comps, props={k: v}))
        self.check(sec, "Include in bill of materials", _common(comps, lambda c: c.in_bom),
                   lambda v: app.edit_components(comps, in_bom=v))
        if one is not None and one.terminals():
            sec = self.section("Terminals")
            g = one.geometry()
            for t in g.terminals:
                default = t.label or t.name
                ptype = (sd.port_type(t) if sd else "") or "any"
                self.entry(sec, f"{default}", one.terminal_labels.get(t.name, ""),
                           lambda v, n=t.name: app.edit_components(comps, terminal_label=(n, v.strip())),
                           hint=f"Displayed designation of terminal {default} (empty = {default}). "
                                f"Port type: {PORT_TYPES.get(ptype, ptype)}")
            self.check(sec, "Show terminal designations on the drawing",
                       app.project.settings.get("show_terminal_labels", False),
                       lambda v: app.set_project_setting("show_terminal_labels", v))
        sec = self.section("Placement")
        if one:
            ux, uy = app.to_user((one.x, one.y))
            self.entry(sec, "X mm", f"{ux:g}", lambda v: self._num(v, lambda f: app.move_component_to(one, x=f)))
            self.entry(sec, "Y mm", f"{uy:g}", lambda v: self._num(v, lambda f: app.move_component_to(one, y=f)))
        self.combo(sec, "Rotation", _common(comps, lambda c: c.rotation), (0, 90, 180, 270),
                   lambda v: app.edit_components(comps, rotation=v), ["0°", "90°", "180°", "270°"])
        self.check(sec, "Mirrored", _common(comps, lambda c: c.mirror), lambda v: app.edit_components(comps, mirror=v))
        self.combo(sec, "Text position", _common(comps, lambda c: c.text_side), SIDES,
                   lambda v: app.edit_components(comps, text_side=v), ["Automatic", "Above", "Below", "Left", "Right"])
        self._layer_lock(sec, comps)
        sec = self.section("Custom properties")
        if one:
            customs = [(k, v) for k, v in one.props.items() if k not in PROP_LABELS]
            for k, v in customs:
                row = ttk.Frame(sec.body, style="Surface.TFrame")
                var = tk.StringVar(value=v)
                ent = ttk.Entry(row, textvariable=var, width=12)
                ent.pack(side="left", fill="x", expand=True)
                ent.bind("<Return>", lambda e, k=k, var=var: app.edit_components(comps, props={k: var.get()}))
                ent.bind("<FocusOut>", lambda e, k=k, var=var, v=v: var.get() != v and
                         app.edit_components(comps, props={k: var.get()}))
                IconButton(row, "close", lambda k=k: app.edit_components(comps, remove_prop=k), "Remove property",
                           size=12, bg_key="surface", pad=3).pack(side="left")
                sec.add_row(k, row)
            if not customs:
                self.note(sec, "No custom properties.")
        self.button(sec, "Add property…", lambda: app.add_custom_property(comps))

    def _layer_lock(self, sec, objs):
        app = self.app
        names = app.project.layer_names()
        self.combo(sec, "Layer", _common(objs, lambda o: o.layer), names, lambda v: app.edit_objects(objs, layer=v))
        self.check(sec, "Locked (cannot be moved or deleted)", _common(objs, lambda o: o.locked),
                   lambda v: app.edit_objects(objs, locked=v))

    # ---------------------------------------------------------------- wires
    def _wires(self, wires):
        app = self.app
        one = wires[0] if len(wires) == 1 else None
        sec = self.section("Wire")
        if one:
            self.entry(sec, "Wire no.", one.number, lambda v: app.set_wire_number(one, v.strip()),
                       hint="Typing a number sets it for the whole connection (manual number). "
                            "Empty = automatic.")
            self.note(sec, "Manual number" if one.number_manual else ("Automatic number" if one.number else
                                                                      "Not numbered yet (Tools ▸ Wire numbers)"))
        self.combo(sec, "Line type", _common(wires, lambda w: w.style), ("solid", "dashed"),
                   lambda v: app.edit_objects(wires, style=v), ["Solid (main / power line)",
                                                                "Dashed (pilot / drain line)"])
        self.entry(sec, "Colour", _common(wires, lambda w: w.props.get("colour", "")),
                   lambda v: app.edit_objects(wires, props={"colour": v}), hint="Wire insulation colour, e.g. BK, BU")
        self.entry(sec, "Cross-section", _common(wires, lambda w: w.props.get("size", "")),
                   lambda v: app.edit_objects(wires, props={"size": v}), hint="e.g. 1.5 mm² / 16 AWG")
        self._layer_lock(sec, wires)
        if one:
            sec = self.section("Connections")
            doc = app.doc

            def end(ref, p):
                if ref and ref[0] in doc.components:
                    c = doc.components[ref[0]]
                    return f"{c.tag()}:{c.terminal_label(ref[1])}"
                ux, uy = app.to_user(p)
                return f"free end at {ux:g}, {uy:g} mm"
            self.note(sec, f"From: {end(one.start, one.points[0])}\nTo: {end(one.end, one.points[-1])}", "Surface.TLabel")

    # ---------------------------------------------------------------- shapes
    def _shapes(self, shapes):
        app = self.app
        one = shapes[0] if len(shapes) == 1 else None
        sec = self.section("Style")
        self.combo(sec, "Line width", _common(shapes, lambda s: s.width), ("thin", "normal", "thick"),
                   lambda v: app.edit_objects(shapes, width=v), ["Thin 0.25 mm", "Normal 0.35 mm", "Thick 0.55 mm"])
        self.check(sec, "Dashed", _common(shapes, lambda s: s.dash), lambda v: app.edit_objects(shapes, dash=v))
        if all(s.kind in ("polygon", "rect", "circle") for s in shapes):
            self.check(sec, "Filled", _common(shapes, lambda s: s.fill), lambda v: app.edit_objects(shapes, fill=v))
        self._layer_lock(sec, shapes)
        texts = [s for s in shapes if s.kind == "text"]
        if texts:
            sec = self.section("Text")
            self.entry(sec, "Text", _common(texts, lambda s: s.s), lambda v: app.edit_objects(texts, s=v))
            self.entry(sec, "Height mm", _common(texts, lambda s: f"{s.size * UNIT_MM:g}"),
                       lambda v: self._num(v, lambda f: app.edit_objects(texts, size=f / UNIT_MM)))
            self.entry(sec, "Angle °", _common(texts, lambda s: f"{s.angle:g}"),
                       lambda v: self._num(v, lambda f: app.edit_objects(texts, angle=f % 360)))
            self.combo(sec, "Anchor", _common(texts, lambda s: s.anchor),
                       ("w", "c", "e", "nw", "n", "ne", "sw", "s", "se"),
                       lambda v: app.edit_objects(texts, anchor=v),
                       ["Left", "Centre", "Right", "Top left", "Top", "Top right", "Bottom left", "Bottom",
                        "Bottom right"])
        if one is not None and one.kind != "text":
            sec = self.section("Geometry")
            if one.kind in ("circle", "arc"):
                ux, uy = app.to_user(one.c)
                self.note(sec, f"Centre {ux:g}, {uy:g} mm · radius {one.r * UNIT_MM:g} mm", "Surface.TLabel")
                self.entry(sec, "Radius mm", f"{one.r * UNIT_MM:g}",
                           lambda v: self._num(v, lambda f: app.edit_objects([one], r=f / UNIT_MM)))
                if one.kind == "arc":
                    self.entry(sec, "Start °", f"{one.start:g}",
                               lambda v: self._num(v, lambda f: app.edit_objects([one], start=f % 360)))
                    self.entry(sec, "Sweep °", f"{one.extent:g}",
                               lambda v: self._num(v, lambda f: app.edit_objects([one], extent=f)))
            else:
                import math
                length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(one.pts, one.pts[1:]))
                pts = ", ".join("(%g, %g)" % app.to_user(p) for p in one.pts[:6])
                self.note(sec, f"{one.kind.title()} · {len(one.pts)} points · length {length * UNIT_MM:.2f} mm\n{pts}"
                          + (" …" if len(one.pts) > 6 else ""), "Surface.TLabel")

    def _mixed(self, objs):
        sec = self.section("Selection")
        kinds = {}
        for o in objs:
            k = type(o).__name__
            kinds[k] = kinds.get(k, 0) + 1
        self.note(sec, ", ".join(f"{n} {k.lower()}{'s' if n > 1 else ''}" for k, n in kinds.items()), "Surface.TLabel")
        self._layer_lock(sec, objs)
        self.button(sec, "Group", self.app.group_selection)

    def focus_first(self):
        e = getattr(self, "designator_entry", None) or self.first_entry
        if e is not None and e.winfo_exists():
            e.focus_set()
            try:
                e.select_range(0, "end")
            except tk.TclError:
                pass


def _unused():  # pragma: no cover
    return current_theme
