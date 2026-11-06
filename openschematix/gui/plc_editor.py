"""The PLC program editor: one window per PLC block.

Left: the block's I/O, its variables and its programs. Centre: an editor for what is selected, graphical for ladder,
function block diagrams and sequential function charts, text for structured text, C and Python. Bottom: problems,
a test panel that runs the program on the spot, and a short reference.

Nothing here changes the drawing until Apply, which is one undo step. The program runs in the same safe runtime
FluidWorx uses (openschematix.plc), so a program can't do anything to the computer.
"""
from __future__ import annotations

import copy
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import plc
from ..plc import plcopen
from ..plc.core import FB_TYPES
from ..plc.fbd import GATES, block_title, pins_of
from ..plc.ladder import COMPARE_OPS, ELEMENT_TITLES
from ..plc.sfc import QUALIFIERS
from . import plc_view
from .plc_view import coord as _coord, snap_grid as _snap_grid
from .widgets import ScrollFrame, Tooltip

LANG_SHORT = {"ld": "LD", "fbd": "FBD", "sfc": "SFC", "st": "ST", "c": "C", "python": "PY"}
VAR_TYPES = ("BOOL", "INT", "DINT", "REAL", "LREAL", "TIME", "STRING", "TON", "TOF", "TP", "CTU", "CTD", "CTUD", "R_TRIG",
             "F_TRIG", "SR", "RS", "PID", "ARRAY[0..9] OF INT", "ARRAY[0..9] OF REAL")
TEST_MS = 40

KEYWORDS = {
    "st": ("IF THEN ELSIF ELSE END_IF CASE OF END_CASE FOR TO BY DO END_FOR WHILE END_WHILE REPEAT UNTIL END_REPEAT EXIT "
           "CONTINUE RETURN VAR VAR_INPUT VAR_OUTPUT VAR_GLOBAL VAR_TEMP END_VAR CONSTANT RETAIN AT ARRAY PROGRAM "
           "END_PROGRAM FUNCTION END_FUNCTION FUNCTION_BLOCK END_FUNCTION_BLOCK AND OR XOR NOT MOD TRUE FALSE BOOL INT DINT "
           "SINT LINT UINT USINT UDINT ULINT REAL LREAL TIME STRING BYTE WORD DWORD LWORD TON TOF TP CTU CTD CTUD R_TRIG "
           "F_TRIG SR RS PID").split(),
    "c": ("if else while for do switch case default break continue return sizeof struct typedef static const void char "
          "short int long float double bool signed unsigned true false NULL uint8_t int8_t uint16_t int16_t uint32_t "
          "int32_t uint64_t int64_t size_t TON TOF TP CTU CTD CTUD R_TRIG F_TRIG SR RS PID").split(),
    "python": ("if elif else while for in not and or def return global pass break continue True False None import from "
               "assert is TON TOF TP CTU CTD CTUD R_TRIG F_TRIG SR RS PID").split(),
}
COMMENTS = {"st": r"\(\*.*?\*\)|//[^\n]*|/\*.*?\*/", "c": r"//[^\n]*|/\*.*?\*/", "python": r"#[^\n]*"}
STRINGS = {"st": r"'(?:[^'$\n]|\$.)*'", "c": r'"(?:[^"\\\n]|\\.)*"', "python": r"\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'"}
NUMBERS = r"\b(?:T#[\w.]+|TIME#[\w.]+|\d+#[\w]+|0x[0-9a-fA-F]+|\d[\d_]*(?:\.\d+)?(?:[eE][-+]?\d+)?)\b"

EXAMPLES = {
    "st": """VAR
    Dwell : TON;
END_VAR

// Latch on Start, drop on Stop, and hold Y1 for 2 s once it is running.
Run := (Start OR Run) AND NOT Stop;
Dwell(IN := Run, PT := T#2s);
IF Dwell.Q THEN
    Y1 := TRUE;
ELSE
    Y1 := FALSE;
END_IF;
""",
    "c": """// Latch on Start, drop on Stop, and hold Y1 for 2 s once it is running.
TON dwell;

void setup(void) {
}

void loop(void) {
    Run = (Start || Run) && !Stop;
    Y1 = ton(&dwell, Run, 2000);
}
""",
    "python": """# Latch on Start, drop on Stop, and hold Y1 for 2 s once it is running.
dwell = TON()

def loop():
    Run = (Start or Run) and not Stop
    dwell(IN=Run, PT=2000)
    Y1 = dwell.Q
""",
}

HELP = """Inputs and outputs are I0, I1, ... (BOOL), Q0, Q1, ... (BOOL), AI0, ... and AO0, ... (REAL). A tag in the I/O table is \
another name for the same place. These names work in all six languages. An analog channel reads in its signal's \
units (V or mA) unless you give it a range, say 0 to 250: then the program reads bar.

Every scan: the inputs are read, each program runs in the order listed here, and the outputs are written.

Ladder  A rung runs left to right. Select an element and add after it; Branch adds a parallel path. A name nobody \
declared becomes an internal marker. Operands can be any expression: T1.Q or Pressure > 120.0.

Function blocks  Click a block in the list to add it, drag from an output pin to an input pin to wire them. A pin \
with no wire uses the value typed in the block's properties.

Sequential function chart  One step or several are active; a transition fires when its steps are active and its \
condition is true. Actions: N while active, S set, R reset, P once on entry, P0 once on exit, L limited time, D delayed. \
Step.X is true while a step is active, Step.T is how long it has been.

Structured text  IEC 61131-3: IF, CASE, FOR, WHILE, REPEAT, VAR ... END_VAR, ARRAY, FUNCTION, FUNCTION_BLOCK, time \
literals such as T#2s. Blocks: TON TOF TP CTU CTD CTUD R_TRIG F_TRIG SR RS PID. Functions: ABS SQRT MIN MAX LIMIT SEL \
MUX SCALE SIN COS TAN EXP LN LOG TRUNC ROUND SHL SHR and conversions such as REAL_TO_INT.

C  setup() runs once, loop() every scan. Types, arrays, structs, pointers, functions; #define for constants. Blocks: \
TON t; then ton(&t, in, ms), and likewise tof tp ctu ctd r_trig f_trig sr rs pid. Also millis() and plc_log("text").

Python  A safe subset: the program can only compute, and no file can make it do anything else. The whole program runs \
every scan, or define loop() and just that does. Blocks: t = TON(), then t(IN=x, PT=2000) and t.Q. math is available; \
other imports, classes and try aren't.

A program can never hang or harm anything: a loop that runs too long trips the watchdog and the PLC stops with a message."""


def known_names(editor) -> list:
    """Everything a program can name, for the operand lists."""
    a = plc.addresses(editor.params)
    tags = plc.tags_of(editor.params)
    names = []
    for kind in ("di", "do", "ai", "ao"):
        for addr in a[kind]:
            names.append(tags.get(addr, addr))
    for row in editor.program["vars"]:
        if isinstance(row, dict) and row.get("name"):
            names.append(str(row["name"]))
    return names


class PlcEditor(tk.Toplevel):
    def __init__(self, app, doc_uid, comp_id):
        super().__init__(app.root)
        self.app, self.doc_uid, self.comp_id = app, doc_uid, comp_id
        app.windows.append(self)
        comp = self._component()
        self.params = copy.deepcopy(comp.params) if comp.params else plc.default_params()
        for k, v in plc.default_params().items():
            self.params.setdefault(k, copy.deepcopy(v))
        self.program = copy.deepcopy(plc.program_of(self.params))
        self.params["program"] = self.program
        self.dirty = False
        self.page = None
        self.selected = "io"
        self.runtime = None
        self._test_after = None
        self._check_after = None
        self.title(f"PLC program: {comp.designator or 'PLC'}")
        self.geometry("1280x820")
        self.minsize(960, 600)
        self.configure(bg=app.theme.ui["bg"])
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Destroy>", self._on_destroy)
        self._build()
        self.select_item(self._first_pou_item())
        self.run_check()

    # ---------------------------------------------------------------- the drawing
    def _doc(self):
        return self.app.project.find_sheet(self.doc_uid)

    def _component(self):
        doc = self._doc()
        return doc.components.get(self.comp_id) if doc is not None else None

    def apply(self) -> bool:
        """Write the block into the drawing, as one undo step. A pin going away takes its wire end with it, so ask."""
        self._commit_page()
        comp = self._component()
        if comp is None:
            messagebox.showerror("PLC program", "This PLC block is no longer on the drawing. Your changes can't be "
                                                "saved.", parent=self)
            return False
        doc = self._doc()
        new = copy.deepcopy(self.params)
        new["program"] = copy.deepcopy(self.program)
        keep = set(plc.addresses(new)["di"] + plc.addresses(new)["do"] + plc.addresses(new)["ai"] + plc.addresses(new)["ao"])
        keep |= {"L+", "M"} | ({"C"} if plc.do_type(new) == "relay" else set())
        lost = sorted({ref[1] for w in doc.wires.values() for ref in (w.start, w.end)
                       if ref and ref[0] == comp.id and str(ref[1]) not in keep})
        if lost and not messagebox.askokcancel(
                "PLC program", f"{', '.join(lost)} will no longer exist, and the wires on {'them' if len(lost) > 1 else 'it'} "
                               "will be disconnected from this block.", parent=self):
            return False
        if self.app.doc.uid != self.doc_uid:
            self.app.switch_to_sheet(self.doc_uid)
            comp = self._component()
        self.app.edit_components([comp], params=new)
        self.dirty = False
        self._title_state()
        self.app.set_status(f"PLC {comp.designator or ''} updated.".replace("  ", " "))
        return True

    def ok(self):
        if self.apply():
            self.destroy()

    def close(self):
        self._commit_page()
        if self.dirty:
            ans = messagebox.askyesnocancel("PLC program", "Apply your changes to the drawing before closing?", parent=self)
            if ans is None or (ans and not self.apply()):
                return
        self.destroy()

    def _on_destroy(self, e):
        if e.widget is self:
            self.test_stop()
            if self in self.app.windows:
                self.app.windows.remove(self)

    def mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self._title_state()
        self._schedule_check()

    def _title_state(self):
        comp = self._component()
        name = comp.designator if comp is not None and comp.designator else "PLC"
        self.title(f"{'*' if self.dirty else ''}PLC program: {name}")

    # ---------------------------------------------------------------- layout
    def _build(self):
        bar = ttk.Frame(self, style="Toolbar.TFrame", padding=(8, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text="OK", style="Accent.TButton", command=self.ok).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Apply", command=self.apply).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Close", command=self.close).pack(side="right")
        ttk.Button(bar, text="Check program", command=self.run_check).pack(side="left")
        self.check_label = ttk.Label(bar, text="", style="Toolbar.TLabel")
        self.check_label.pack(side="left", padx=(10, 0))
        ttk.Separator(self).pack(fill="x")
        outer = ttk.PanedWindow(self, orient="vertical")
        outer.pack(fill="both", expand=True)
        top = ttk.PanedWindow(outer, orient="horizontal")
        outer.add(top, weight=4)
        left = ttk.Frame(top, style="Surface.TFrame", padding=6)
        top.add(left, weight=0)
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse", height=12)
        self.tree.column("#0", width=210)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._tree_select)
        row = ttk.Frame(left, style="Surface.TFrame")
        row.pack(fill="x", pady=(6, 0))
        mb = ttk.Menubutton(row, text="New program")
        menu = tk.Menu(mb, tearoff=0)
        for key, label in plc.LANGUAGES.items():
            menu.add_command(label=label, command=lambda k=key: self.add_pou(k))
        mb["menu"] = menu
        mb.pack(side="left", fill="x", expand=True)
        imp = ttk.Button(row, text="Import…", command=self.import_plcopen)
        imp.pack(side="left", padx=(4, 0))
        Tooltip(imp, "Bring in a program from another PLC tool, exported as PLCopen XML")
        row2 = ttk.Frame(left, style="Surface.TFrame")
        row2.pack(fill="x", pady=(4, 0))
        for text, cmd, tip in (("Rename", self.rename_pou, "Rename the selected program"),
                               ("▲", lambda: self.move_pou(-1), "Run this program earlier in the scan"),
                               ("▼", lambda: self.move_pou(1), "Run this program later in the scan"),
                               ("Delete", self.delete_pou, "Delete the selected program")):
            b = ttk.Button(row2, text=text, command=cmd, width=len(text) + 1)
            b.pack(side="left", padx=(0, 3))
            Tooltip(b, tip)
        self.holder = ttk.Frame(top, style="Surface.TFrame")
        top.add(self.holder, weight=1)
        self.dock = ttk.Notebook(outer)
        outer.add(self.dock, weight=1)
        self.problems = ttk.Treeview(self.dock, columns=("where", "line", "text"), show="headings", selectmode="browse", height=6)
        for col, label, w, st in (("where", "Where", 140, False), ("line", "Line", 50, False), ("text", "Problem", 760, True)):
            self.problems.heading(col, text=label, anchor="w")
            self.problems.column(col, width=w, stretch=st)
        self.problems.tag_configure("warning", foreground=self.app.theme.ui["warning"])
        self.problems.tag_configure("error", foreground=self.app.theme.ui["danger"])
        self.problems.bind("<Double-Button-1>", self._go_to_problem)
        self.dock.add(self.problems, text="Problems")
        self.test = TestPanel(self.dock, self)
        self.dock.add(self.test, text="Test")
        helpf = ttk.Frame(self.dock, style="Surface.TFrame")
        txt = tk.Text(helpf, wrap="word", height=8, bd=0, padx=10, pady=8, bg=self.app.theme.ui["surface"],
                      fg=self.app.theme.ui["text"], font=self.app.theme.fonts["ui"])
        sb = ttk.Scrollbar(helpf, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.insert("1.0", HELP)
        txt.configure(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.dock.add(helpf, text="Reference")
        self._fill_tree()
        self.after(60, lambda: self._place_sash(outer))

    def _place_sash(self, outer):
        h = outer.winfo_height()
        if h > 300:
            outer.sashpos(0, h - 190)

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.insert("", "end", iid="io", text="Inputs and outputs")
        self.tree.insert("", "end", iid="vars", text="Variables")
        self.pou_group = self.tree.insert("", "end", iid="pous", text="Programs (in scan order)", open=True)
        for i, pou in enumerate(self.program["pous"]):
            label = f"{pou.get('name', '?')}  ({LANG_SHORT.get(pou.get('lang'), '?')})"
            self.tree.insert(self.pou_group, "end", iid=f"pou{i}", text=label)

    def _first_pou_item(self):
        return "pou0" if self.program["pous"] else "io"

    def select_item(self, iid):
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
            self._show(iid)

    def _tree_select(self, _e):
        sel = self.tree.selection()
        if sel and sel[0] != "pous" and sel[0] != self.selected:
            self._show(sel[0])

    def _commit_page(self):
        if self.page is not None and hasattr(self.page, "commit"):
            self.page.commit()

    def _show(self, iid):
        self._commit_page()
        for w in self.holder.winfo_children():
            w.destroy()
        self.selected = iid
        if iid == "io":
            self.page = IoPage(self.holder, self)
        elif iid == "vars":
            self.page = VarsPage(self.holder, self)
        elif iid.startswith("pou"):
            pou = self.program["pous"][int(iid[3:])]
            cls = {"ld": LadderPage, "fbd": FbdPage, "sfc": SfcPage}.get(pou.get("lang"), TextPage)
            self.page = cls(self.holder, self, pou)
        else:
            self.page = None
            return
        self.page.pack(fill="both", expand=True)

    def current_pou_index(self):
        return int(self.selected[3:]) if self.selected.startswith("pou") else None

    def add_pou(self, lang):
        self._commit_page()
        n = 1
        names = {str(p.get("name")).casefold() for p in self.program["pous"]}
        base = {"ld": "Rungs", "fbd": "Blocks", "sfc": "Sequence", "st": "Logic", "c": "Code", "python": "Script"}[lang]
        while f"{base}{n}".casefold() in names:
            n += 1
        self.program["pous"].append(plc.new_pou(f"{base}{n}", lang))
        self._fill_tree()
        self.mark_dirty()
        self.select_item(f"pou{len(self.program['pous']) - 1}")

    def rename_pou(self):
        i = self.current_pou_index()
        if i is None:
            return
        from tkinter import simpledialog
        name = simpledialog.askstring("Rename program", "Name:", initialvalue=self.program["pous"][i].get("name", ""), parent=self)
        if name and name.strip():
            self.program["pous"][i]["name"] = name.strip()
            self._fill_tree()
            self.select_item(f"pou{i}")
            self.mark_dirty()

    def move_pou(self, d):
        i = self.current_pou_index()
        pous = self.program["pous"]
        if i is None or not 0 <= i + d < len(pous):
            return
        self._commit_page()
        pous[i], pous[i + d] = pous[i + d], pous[i]
        self._fill_tree()
        self.selected = ""
        self.page = None
        self.select_item(f"pou{i + d}")
        self.mark_dirty()

    def delete_pou(self):
        i = self.current_pou_index()
        if i is None:
            return
        pous = self.program["pous"]
        if len(pous) == 1:
            messagebox.showinfo("PLC program", "A PLC needs at least one program.", parent=self)
            return
        if not messagebox.askokcancel("PLC program", f"Delete the program {pous[i].get('name')}?", parent=self):
            return
        self.page = None
        del pous[i]
        self._fill_tree()
        self.selected = ""
        self.select_item(f"pou{max(0, i - 1)}")
        self.mark_dirty()

    # ---------------------------------------------------------------- bringing in a program
    def import_plcopen(self):
        path = filedialog.askopenfilename(parent=self, title="Import a program as PLCopen XML",
                                          filetypes=[("PLCopen XML", "*.xml"), ("All files", "*.*")])
        if path:
            self.read_plcopen(path)

    def read_plcopen(self, path):
        try:
            with open(path, "rb") as f:
                imported = plcopen.parse(f.read(plcopen.MAX_FILE + 1))
        except (plcopen.PlcOpenError, OSError) as e:
            messagebox.showerror("PLC program", f"This file couldn't be imported.\n\n{e}", parent=self)
            return None
        return ImportDialog(self, imported, os.path.basename(path))

    def blank(self) -> bool:
        """Whether this block has only the empty program it started with."""
        pous = self.program["pous"]
        return len(pous) == 1 and pous[0].get("lang") == "ld" and not any(
            r.get("items") for r in (pous[0].get("source") or {}).get("rungs", []) if isinstance(r, dict))

    def take_import(self, imported, replace):
        """Nothing reaches the drawing until Apply, as with any other change here."""
        self._commit_page()
        added = plcopen.merge(self.params, imported, replace)
        self.program = self.params["program"]
        self._fill_tree()
        self.page = None
        self.selected = ""
        self.mark_dirty()
        names = [p.get("name") for p in self.program["pous"]]
        self.select_item(f"pou{names.index(added[0])}" if added else self._first_pou_item())
        self.run_check()
        return added

    # ---------------------------------------------------------------- checking
    def _schedule_check(self):
        if self._check_after is not None:
            self.after_cancel(self._check_after)
        self._check_after = self.after(700, self.run_check)

    def run_check(self):
        self._check_after = None
        self._commit_page()
        diags = plc.check(self.params)
        self.problems.delete(*self.problems.get_children())
        self._problem_map = {}
        for d in diags:
            iid = self.problems.insert("", "end", values=(d.pou, d.line or "", d.message), tags=(d.level,))
            self._problem_map[iid] = d
        errors = sum(d.level == "error" for d in diags)
        warns = len(diags) - errors
        if errors:
            self.check_label.configure(text=f"{errors} problem{'s' * (errors != 1)} to fix before this can run")
        elif warns:
            self.check_label.configure(text=f"Ready to run, with {warns} warning{'s' * (warns != 1)}")
        else:
            self.check_label.configure(text="No problems found")
        return not errors

    def _go_to_problem(self, _e):
        sel = self.problems.selection()
        d = self._problem_map.get(sel[0]) if sel else None
        if d is None:
            return
        if d.pou in ("I/O",):
            self.select_item("io")
            return
        if d.pou == "Variables":
            self.select_item("vars")
            return
        for i, pou in enumerate(self.program["pous"]):
            if pou.get("name") == d.pou:
                self.select_item(f"pou{i}")
                if d.line and isinstance(self.page, TextPage):
                    self.page.goto(d.line)
                return

    # ---------------------------------------------------------------- testing
    def test_stop(self):
        if self._test_after is not None:
            try:
                self.after_cancel(self._test_after)
            except tk.TclError:
                pass
            self._test_after = None
        self.runtime = None

    def theme(self):
        return self.app.theme


# ================================================================ test panel
class ImportDialog(tk.Toplevel):
    """What's in a file, what became of it, and what to do with it."""

    def __init__(self, editor, imported, name):
        super().__init__(editor)
        self.editor, self.imported = editor, imported
        self.title(f"Import {name}")
        self.transient(editor)
        self.geometry("680x440")
        u = editor.app.theme.ui
        self.configure(bg=u["bg"])
        box = ttk.Frame(self, style="Surface.TFrame", padding=12)
        box.pack(fill="both", expand=True)
        found = ", ".join(f"{p['name']} ({LANG_SHORT.get(p['lang'], p['lang'])})" for p in imported.pous)
        ttk.Label(box, text=f"Programs found: {found}" if found else "No programs found that this PLC block can run.", style="Bold.TLabel",
                  wraplength=640, justify="left").pack(anchor="w")
        pins = ", ".join(f"{k} {v}" for k, v in sorted(imported.tags.items()))
        if pins:
            ttk.Label(box, text=f"Tags: {pins}", style="Muted.TLabel", wraplength=640, justify="left").pack(anchor="w", pady=(4, 0))
        if imported.notes:
            ttk.Label(box, text="Worth knowing", style="Heading.TLabel").pack(anchor="w", pady=(10, 2))
            holder = ttk.Frame(box, style="Surface.TFrame")
            holder.pack(fill="both", expand=True)
            self.notes = tk.Text(holder, wrap="word", height=8, bd=0, padx=8, pady=6, bg=u["surface2"], fg=u["text"], font=editor.app.theme.fonts["ui"])
            bar = ttk.Scrollbar(holder, command=self.notes.yview)
            self.notes.configure(yscrollcommand=bar.set)
            self.notes.insert("1.0", "\n".join(f"• {n}" for n in imported.notes))
            self.notes.configure(state="disabled")
            self.notes.pack(side="left", fill="both", expand=True)
            bar.pack(side="right", fill="y")
        ttk.Label(box, text="It can be checked and tested here before it goes on the drawing: nothing changes until you press Apply.", style="Faint.TLabel",
                  wraplength=640, justify="left").pack(anchor="w", pady=(8, 0))
        row = ttk.Frame(box, style="Surface.TFrame")
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text="Cancel", command=self.destroy).pack(side="right")
        if imported.pous:
            if editor.blank():
                ttk.Button(row, text="Import", style="Accent.TButton", command=lambda: self.go(True)).pack(side="right", padx=(0, 6))
            else:
                ttk.Button(row, text="Replace this block's programs", command=lambda: self.go(True)).pack(side="right", padx=(0, 6))
                ttk.Button(row, text="Add to this block's programs", style="Accent.TButton", command=lambda: self.go(False)).pack(side="right", padx=(0, 6))
        self.bind("<Escape>", lambda e: self.destroy())

    def go(self, replace):
        self.editor.take_import(self.imported, replace)
        self.destroy()


class TestPanel(ttk.Frame):
    """Run the program here, with inputs from check boxes: the quickest way to see that it does what you meant."""

    def __init__(self, master, editor):
        super().__init__(master, style="Surface.TFrame", padding=6)
        self.editor = editor
        bar = ttk.Frame(self, style="Surface.TFrame")
        bar.pack(fill="x")
        self.run_btn = ttk.Button(bar, text="Run", style="Accent.TButton", command=self.toggle)
        self.run_btn.pack(side="left")
        ttk.Button(bar, text="Restart", command=self.restart).pack(side="left", padx=(6, 0))
        self.state = ttk.Label(bar, text="Stopped.", style="Surface.TLabel")
        self.state.pack(side="left", padx=(12, 0))
        body = ttk.Frame(self, style="Surface.TFrame")
        body.pack(fill="both", expand=True, pady=(6, 0))
        self.left = ScrollFrame(body)
        self.left.pack(side="left", fill="both", expand=True)
        self.watch = ttk.Treeview(body, columns=("name", "tag", "value"), show="headings", height=6)
        for col, label, w in (("name", "Name", 110), ("tag", "Tag", 110), ("value", "Value", 110)):
            self.watch.heading(col, text=label, anchor="w")
            self.watch.column(col, width=w, stretch=True)
        self.watch.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.in_vars = {}
        self.running = False
        self._rows = {}

    def _build_inputs(self):
        self.left.clear()
        self.in_vars = {}
        rt = self.editor.runtime
        inner = self.left.inner
        tags = rt.program.tags
        for addr in rt.program.addr["di"]:
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(inner, text=f"{addr}  {tags.get(addr, '')}".rstrip(), variable=v).pack(anchor="w")
            self.in_vars[addr] = ("di", v)
        for addr in rt.program.addr["ai"]:
            name, s_lo, s_hi, _lo, _hi = rt._ai[addr]
            row = ttk.Frame(inner, style="Surface.TFrame")
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"{addr} {tags.get(addr, '')} ({name})", style="Surface.TLabel").pack(side="left")
            v = tk.DoubleVar(value=s_lo)
            ttk.Scale(row, from_=s_lo, to=s_hi, variable=v, orient="horizontal").pack(side="left", fill="x", expand=True, padx=6)
            self.in_vars[addr] = ("ai", v)

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        ed = self.editor
        ed._commit_page()
        if not ed.run_check():
            self.state.configure(text="Fix the problems first.")
            ed.dock.select(ed.problems)
            return
        ed.runtime = plc.compile_params(ed.params)
        self.running = True
        self.run_btn.configure(text="Stop")
        self._build_inputs()
        self._rows = {}
        self.watch.delete(*self.watch.get_children())
        self.state.configure(text="Running.")
        self._tick()

    def stop(self):
        self.running = False
        self.run_btn.configure(text="Run")
        self.editor.test_stop()
        self.state.configure(text="Stopped.")
        page = self.editor.page
        if hasattr(page, "live"):
            page.live(None)

    def restart(self):
        self.stop()
        self.start()

    def _tick(self):
        ed = self.editor
        rt = ed.runtime
        if not self.running or rt is None:
            return
        for addr, (kind, v) in self.in_vars.items():
            try:
                if kind == "di":
                    rt.set_input(addr, bool(v.get()))
                else:
                    rt.set_analog_raw(addr, float(v.get()))
            except tk.TclError:
                pass
        n = max(1, min(20, round(TEST_MS / rt.program.scan_ms)))
        for _ in range(n):
            if not rt.scan():
                break
        self._show()
        if rt.fault:
            self.running = False
            self.run_btn.configure(text="Run")
            self.state.configure(text=f"Stopped: {rt.fault}")
            return
        page = ed.page
        if hasattr(page, "live"):
            page.live(rt)
        ed._test_after = ed.after(TEST_MS, self._tick)

    def _show(self):
        rt = self.editor.runtime
        for name, tag, value in rt.watch():
            text = ("ON" if value else "off") if isinstance(value, bool) else (f"{value:.3f}" if isinstance(value, float)
                                                                                else str(value))
            iid = self._rows.get(name)
            if iid is None:
                iid = self.watch.insert("", "end", values=(name, tag, text))
                self._rows[name] = iid
            else:
                self.watch.set(iid, "value", text)


# ================================================================ inputs and outputs
class IoPage(ScrollFrame):
    def __init__(self, master, editor):
        super().__init__(master)
        self.editor = editor
        self.build()

    def build(self):
        self.clear()
        ed = self.editor
        inner = self.inner
        head = ttk.Frame(inner, style="Surface.TFrame", padding=10)
        head.pack(fill="x")
        self.counts = {}
        di, do, ai, ao = plc.io_counts(ed.params)
        for col, (key, label, value) in enumerate((("di", "Digital inputs", di), ("do", "Digital outputs", do),
                                                   ("ai", "Analog inputs", ai), ("ao", "Analog outputs", ao))):
            ttk.Label(head, text=label, style="Surface.TLabel").grid(row=0, column=col * 2, sticky="w", padx=(0, 4))
            v = tk.IntVar(value=value)
            sp = ttk.Spinbox(head, from_=0, to=plc.MAX_IO, textvariable=v, width=4, command=lambda k=key, x=v: self._count(k, x))
            sp.grid(row=0, column=col * 2 + 1, padx=(0, 14))
            sp.bind("<Return>", lambda e, k=key, x=v: self._count(k, x))
            sp.bind("<FocusOut>", lambda e, k=key, x=v: self._count(k, x))
            self.counts[key] = v
        ttk.Label(head, text="Outputs", style="Surface.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        names = list(plc.DO_TYPES.values())
        keys = list(plc.DO_TYPES)
        self.out_var = tk.StringVar(value=plc.DO_TYPES[plc.do_type(ed.params)])
        cb = ttk.Combobox(head, textvariable=self.out_var, values=names, state="readonly", width=38)
        cb.grid(row=1, column=1, columnspan=4, sticky="w", pady=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._out(keys[names.index(self.out_var.get())]))
        ttk.Label(head, text="Scan time (ms)", style="Surface.TLabel").grid(row=1, column=5, sticky="w", pady=(8, 0), padx=(10, 4))
        self.scan_var = tk.StringVar(value=str(ed.program["scan_ms"]))
        e = ttk.Entry(head, textvariable=self.scan_var, width=6)
        e.grid(row=1, column=6, sticky="w", pady=(8, 0))
        e.bind("<FocusOut>", lambda ev: self._scan())
        e.bind("<Return>", lambda ev: self._scan())
        table = ttk.Frame(inner, style="Surface.TFrame", padding=(10, 0, 10, 10))
        table.pack(fill="x")
        for col, (text, w) in enumerate((("Pin", 6), ("Tag", 16), ("Note", 30), ("Signal", 8), ("Reads as, low", 8), ("high", 8))):
            ttk.Label(table, text=text, style="Heading.TLabel").grid(row=0, column=col, sticky="w", padx=(0, 6), pady=(0, 4))
        a = plc.addresses(ed.params)
        tags = ed.params["tags"] if isinstance(ed.params.get("tags"), dict) else {}
        io = ed.program["io"]
        r = 1
        for kind in ("di", "do", "ai", "ao"):
            for addr in a[kind]:
                ttk.Label(table, text=addr, style="Surface.TLabel").grid(row=r, column=0, sticky="w")
                self._entry(table, r, 1, 16, str(tags.get(addr, "")), lambda v, x=addr: self._tag(x, v))
                cfg = io.get(addr) if isinstance(io.get(addr), dict) else {}
                self._entry(table, r, 2, 30, str(cfg.get("note", "")), lambda v, x=addr: self._cfg(x, "note", v))
                if kind in ("ai", "ao"):
                    sig = tk.StringVar(value=cfg.get("signal") if cfg.get("signal") in plc.SIGNALS else "0-10V")
                    c = ttk.Combobox(table, textvariable=sig, values=list(plc.SIGNALS), state="readonly", width=8)
                    c.grid(row=r, column=3, padx=(0, 6), pady=1)
                    c.bind("<<ComboboxSelected>>", lambda e, x=addr, s=sig: self._cfg(x, "signal", s.get()))
                    self._entry(table, r, 4, 8, _num_text(cfg.get("lo")), lambda v, x=addr: self._range(x, "lo", v))
                    self._entry(table, r, 5, 8, _num_text(cfg.get("hi")), lambda v, x=addr: self._range(x, "hi", v))
                r += 1
        ttk.Label(inner, text="L+ and M are the block's supply. An analog channel with no range reads in its signal's "
                              "units; give it a range and the program reads, say, 0 to 250 for 4-20 mA.",
                  style="Muted.TLabel", wraplength=720, justify="left", padding=(10, 0)).pack(anchor="w")

    @staticmethod
    def _entry(parent, r, c, width, value, commit):
        var = tk.StringVar(value=value)
        e = ttk.Entry(parent, textvariable=var, width=width)
        e.grid(row=r, column=c, sticky="w", padx=(0, 6), pady=1)
        last = [value]

        def done(_e=None):
            if var.get() != last[0]:
                last[0] = var.get()
                commit(var.get())
        e.bind("<FocusOut>", done)
        e.bind("<Return>", done)
        return e

    def _count(self, key, var):
        try:
            n = max(0, min(int(var.get()), plc.MAX_IO))
        except (tk.TclError, ValueError):
            return
        if self.editor.params.get(key) != n:
            self.editor.params[key] = n
            self.editor.mark_dirty()
            self.after_idle(self.build)

    def _out(self, value):
        self.editor.params["do_type"] = value
        self.editor.mark_dirty()

    def _scan(self):
        try:
            v = int(float(self.scan_var.get()))
        except ValueError:
            self.scan_var.set(str(self.editor.program["scan_ms"]))
            return
        v = max(1, min(v, 1000))
        self.scan_var.set(str(v))
        if v != self.editor.program["scan_ms"]:
            self.editor.program["scan_ms"] = v
            self.editor.mark_dirty()

    def _tag(self, addr, value):
        tags = self.editor.params.setdefault("tags", {})
        value = value.strip()
        if value:
            tags[addr] = value
        else:
            tags.pop(addr, None)
        self.editor.mark_dirty()

    def _cfg(self, addr, key, value):
        cfg = self.editor.program["io"].setdefault(addr, {})
        if value == "":
            cfg.pop(key, None)
        else:
            cfg[key] = value
        self.editor.mark_dirty()

    def _range(self, addr, key, text):
        text = text.strip()
        if not text:
            self._cfg(addr, key, "")
            return
        try:
            self._cfg(addr, key, float(text))
        except ValueError:
            pass


def _num_text(v) -> str:
    return f"{v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else ""


# ================================================================ variables
class VarsPage(ScrollFrame):
    def __init__(self, master, editor):
        super().__init__(master)
        self.editor = editor
        self.build()

    def build(self):
        self.clear()
        table = ttk.Frame(self.inner, style="Surface.TFrame", padding=10)
        table.pack(fill="x")
        for col, text in enumerate(("Name", "Type", "Starting value", "Note")):
            ttk.Label(table, text=text, style="Heading.TLabel").grid(row=0, column=col, sticky="w", padx=(0, 6), pady=(0, 4))
        rows = self.editor.program["vars"]
        for r, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                continue
            IoPage._entry(table, r, 0, 18, str(row.get("name", "")), lambda v, x=row: self._set(x, "name", v.strip()))
            var = tk.StringVar(value=str(row.get("type", "BOOL")))
            c = ttk.Combobox(table, textvariable=var, values=VAR_TYPES, width=20)
            c.grid(row=r, column=1, padx=(0, 6), pady=1)
            c.bind("<<ComboboxSelected>>", lambda e, x=row, s=var: self._set(x, "type", s.get()))
            c.bind("<FocusOut>", lambda e, x=row, s=var: self._set(x, "type", s.get().strip() or "BOOL"))
            IoPage._entry(table, r, 2, 14, str(row.get("init", "")), lambda v, x=row: self._set(x, "init", v.strip()))
            IoPage._entry(table, r, 3, 34, str(row.get("note", "")), lambda v, x=row: self._set(x, "note", v))
            ttk.Button(table, text="✕", width=3, command=lambda x=row: self._del(x)).grid(row=r, column=4, padx=(4, 0))
        ttk.Button(table, text="Add variable", command=self._add).grid(row=len(rows) + 1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(self.inner, text="These are global: every program can read and write them. A program can also declare "
                                   "its own. In ladder and function blocks, a name nobody declared becomes a BOOL marker.",
                  style="Muted.TLabel", wraplength=720, justify="left", padding=(10, 0)).pack(anchor="w")

    def _set(self, row, key, value):
        if row.get(key) != value:
            row[key] = value
            self.editor.mark_dirty()

    def _add(self):
        rows = self.editor.program["vars"]
        names = {str(r.get("name")) for r in rows if isinstance(r, dict)}
        n = 1
        while f"Var{n}" in names:
            n += 1
        rows.append({"name": f"Var{n}", "type": "BOOL", "init": "", "note": ""})
        self.editor.mark_dirty()
        self.build()

    def _del(self, row):
        self.editor.program["vars"].remove(row)
        self.editor.mark_dirty()
        self.build()


# ================================================================ text languages
class TextPage(ttk.Frame):
    def __init__(self, master, editor, pou):
        super().__init__(master, style="Surface.TFrame")
        self.editor, self.pou = editor, pou
        self.lang = pou.get("lang")
        u = editor.app.theme.ui
        bar = ttk.Frame(self, style="Surface.TFrame", padding=(8, 6))
        bar.pack(fill="x")
        ttk.Label(bar, text=plc.LANGUAGES.get(self.lang, ""), style="Bold.TLabel").pack(side="left")
        ttk.Button(bar, text="Insert an example", command=self._example).pack(side="right")
        holder = ttk.Frame(self, style="Surface.TFrame")
        holder.pack(fill="both", expand=True)
        mono = editor.app.theme.fonts["mono"]
        self.numbers = tk.Text(holder, width=5, padx=4, bd=0, bg=u["surface2"], fg=u["faint"], font=mono, state="disabled",
                               takefocus=0, wrap="none")
        self.numbers.pack(side="left", fill="y")
        self.text = tk.Text(holder, wrap="none", undo=True, bd=0, padx=6, bg=u["input"], fg=u["text"],
                            insertbackground=u["text"], font=mono)
        ys = ttk.Scrollbar(holder, command=self._yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=lambda a, b: (ys.set(a, b), self.numbers.yview_moveto(a)), xscrollcommand=xs.set)
        self.text.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        xs.pack(fill="x")
        self.text.tag_configure("keyword", foreground=u["accent"])
        self.text.tag_configure("comment", foreground=u["faint"])
        self.text.tag_configure("string", foreground=u["warning"])
        self.text.tag_configure("number", foreground=u["success"] if "success" in u else u["accent"])
        self.text.tag_configure("line", background=u["accent_soft"])
        source = pou.get("source")
        self.text.insert("1.0", source if isinstance(source, str) else "")
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.bind("<<Modified>>", self._modified)
        self.text.bind("<Tab>", self._tab)
        self._after = None
        self._highlight()

    def _yview(self, *a):
        self.text.yview(*a)
        self.numbers.yview(*a)

    def _tab(self, _e):
        self.text.insert("insert", "    ")
        return "break"

    def _modified(self, _e=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self.commit()
        self.editor.mark_dirty()
        if self._after is not None:
            self.after_cancel(self._after)
        self._after = self.after(200, self._highlight)

    def commit(self):
        try:
            self.pou["source"] = self.text.get("1.0", "end-1c")
        except tk.TclError:
            pass

    def goto(self, line):
        self.text.tag_remove("line", "1.0", "end")
        self.text.tag_add("line", f"{line}.0", f"{line}.end+1c")
        self.text.see(f"{line}.0")
        self.text.mark_set("insert", f"{line}.0")
        self.text.focus_set()

    def _example(self):
        from ..plc.program import TEMPLATES
        now = self.text.get("1.0", "end-1c").strip()
        if now and now != TEMPLATES.get(self.lang, "").strip() and not messagebox.askokcancel(
                "PLC program", "Replace what you have written with the example?", parent=self):
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", EXAMPLES.get(self.lang, ""))

    def _highlight(self):
        self._after = None
        src = self.text.get("1.0", "end-1c")
        n = src.count("\n") + 1
        self.numbers.configure(state="normal")
        self.numbers.delete("1.0", "end")
        self.numbers.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        self.numbers.configure(state="disabled")
        for tag in ("keyword", "comment", "string", "number"):
            self.text.tag_remove(tag, "1.0", "end")
        if len(src) > 200_000:
            return
        flags = re.IGNORECASE if self.lang == "st" else 0
        words = KEYWORDS.get(self.lang, [])
        spans = {"number": NUMBERS, "keyword": r"\b(?:" + "|".join(words) + r")\b",
                 "string": STRINGS.get(self.lang, r"$^"), "comment": COMMENTS.get(self.lang, r"$^")}
        for tag, pattern in spans.items():
            for m in re.finditer(pattern, src, flags | re.DOTALL):
                self.text.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        self.text.tag_raise("string")
        self.text.tag_raise("comment")


# ================================================================ ladder
class LadderPage(ttk.Frame):
    def __init__(self, master, editor, pou):
        super().__init__(master, style="Surface.TFrame")
        self.editor, self.pou = editor, pou
        if not isinstance(pou.get("source"), dict) or not isinstance(pou["source"].get("rungs"), list):
            pou["source"] = {"rungs": [{"comment": "", "items": []}]}
        self.rungs = pou["source"]["rungs"]
        self.sel = None         # (series path, index): index None = the empty series itself
        self.rt = None
        self.hits = []
        bar = ttk.Frame(self, style="Surface.TFrame", padding=(8, 6))
        bar.pack(fill="x")
        rows = [ttk.Frame(bar, style="Surface.TFrame"), ttk.Frame(bar, style="Surface.TFrame")]
        rows[0].pack(fill="x")
        rows[1].pack(fill="x", pady=(3, 0))

        def add(row, text, cmd, tip=""):
            b = ttk.Button(rows[row], text=text, command=cmd, width=max(4, len(text) + 1))
            b.pack(side="left", padx=(0, 3))
            if tip:
                Tooltip(b, tip)
        add(0, "+ Rung", self.add_rung, "Add a rung after this one")
        add(0, "− Rung", self.del_rung, "Delete this rung")
        add(0, "▲", lambda: self.move_rung(-1), "Move the rung up")
        add(0, "▼", lambda: self.move_rung(1), "Move the rung down")
        ttk.Label(rows[0], text="  ", style="Surface.TLabel").pack(side="left")
        add(0, "Branch", self.branch, "Add a parallel path around the selected element")
        add(0, "Delete", self.delete, "Delete the selected element (Delete)")
        add(0, "◀", lambda: self.shift(-1), "Move the element left")
        add(0, "▶", lambda: self.shift(1), "Move the element right")
        for t, text in (("no", "NO"), ("nc", "NC"), ("rise", "↑ P"), ("fall", "↓ N"), ("cmp", "Compare")):
            add(1, text, lambda x=t: self.insert(x), ELEMENT_TITLES[t])
        ttk.Label(rows[1], text="  ", style="Surface.TLabel").pack(side="left")
        for t, text in (("coil", "( )"), ("ncoil", "(/)"), ("set", "(S)"), ("reset", "(R)")):
            add(1, text, lambda x=t: self.insert(x), ELEMENT_TITLES[t])
        ttk.Label(rows[1], text="  ", style="Surface.TLabel").pack(side="left")
        for t, text in (("ton", "TON"), ("tof", "TOF"), ("tp", "TP"), ("ctu", "CTU"), ("ctd", "CTD"), ("move", "Assign"),
                        ("st", "ST")):
            add(1, text, lambda x=t: self.insert(x), ELEMENT_TITLES[t])
        holder = ttk.Frame(self, style="Surface.TFrame")
        holder.pack(fill="both", expand=True)
        u = editor.app.theme.ui
        self.cv = tk.Canvas(holder, bg=u["surface"], highlightthickness=0, takefocus=1)
        ys = ttk.Scrollbar(holder, command=self.cv.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.cv.xview)
        self.cv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.cv.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        xs.pack(fill="x")
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Delete>", lambda e: self.delete())
        self.cv.bind("<Configure>", lambda e: self.draw())
        self.props = ttk.Frame(self, style="Surface.TFrame", padding=(8, 6))
        self.props.pack(fill="x")
        if not self.rungs:
            self.rungs.append({"comment": "", "items": []})
        self.sel = ((0,), None) if not self.rungs[0].get("items") else ((0,), 0)
        self.draw()
        self.show_props()

    # ---- navigation in the model
    def series_at(self, path) -> list:
        series = self.rungs[path[0]].setdefault("items", [])
        for el_i, br_i in path[1:]:
            series = series[el_i]["branches"][br_i]
        return series

    def _selected_element(self):
        if self.sel is None or self.sel[1] is None:
            return None
        s = self.series_at(self.sel[0])
        return s[self.sel[1]] if self.sel[1] < len(s) else None

    def rung_index(self) -> int:
        return self.sel[0][0] if self.sel else 0

    # ---- editing
    def _changed(self):
        self.editor.mark_dirty()
        self.draw()

    def add_rung(self):
        i = self.rung_index() + 1
        self.rungs.insert(i, {"comment": "", "items": []})
        self.sel = ((i,), None)
        self._changed()
        self.show_props()

    def del_rung(self):
        if len(self.rungs) <= 1:
            self.rungs[0]["items"] = []
            self.rungs[0]["comment"] = ""
            self.sel = ((0,), None)
        else:
            i = self.rung_index()
            del self.rungs[i]
            self.sel = ((min(i, len(self.rungs) - 1),), None)
        self._changed()
        self.show_props()

    def move_rung(self, d):
        i = self.rung_index()
        if 0 <= i + d < len(self.rungs):
            self.rungs[i], self.rungs[i + d] = self.rungs[i + d], self.rungs[i]
            self.sel = ((i + d,) + self.sel[0][1:], self.sel[1])
            self._changed()

    def _next_name(self, prefix) -> str:
        used = set()

        def walk(series):
            for el in series:
                if el.get("t") == "par":
                    for b in el.get("branches", []):
                        walk(b)
                elif el.get("a"):
                    used.add(str(el["a"]))
        for r in self.rungs:
            walk(r.get("items", []))
        n = 1
        while f"{prefix}{n}" in used:
            n += 1
        return f"{prefix}{n}"

    def insert(self, t):
        el = {"t": t, "a": ""}
        if t in ("ton", "tof", "tp"):
            el.update(a=self._next_name("T"), pt="T#1s")
        elif t in ("ctu", "ctd"):
            el.update(a=self._next_name("C"), pv="1", r="")
        elif t == "cmp":
            el.update(op=">", b="0")
        elif t == "move":
            el.update(b="0")
        elif t == "st":
            el = {"t": "st", "code": ""}
        if self.sel is None:
            self.sel = ((0,), None)
        path, i = self.sel
        series = self.series_at(path)
        if i is None:
            at = len(series)
        else:
            at = i + 1
        if t not in ("coil", "ncoil", "set", "reset", "move", "st"):
            while at > 0 and series[at - 1].get("t") in ("coil", "ncoil", "set", "reset"):
                at -= 1                 # contacts go before the coils at the end of a rung
        series.insert(at, el)
        self.sel = (path, at)
        self._changed()
        self.show_props(focus=True)

    def branch(self):
        el = self._selected_element()
        if self.sel is None or self.sel[1] is None:
            return
        path, i = self.sel
        series = self.series_at(path)
        if el.get("t") == "par":
            el["branches"].append([])
            self.sel = (path + ((i, len(el["branches"]) - 1),), None)
        else:
            series[i] = {"t": "par", "branches": [[el], []]}
            self.sel = (path + ((i, 1),), None)
        self._changed()
        self.show_props()

    def delete(self):
        if self.sel is None or self.sel[1] is None:
            return self._delete_empty_branch()
        path, i = self.sel
        series = self.series_at(path)
        del series[i]
        if series:
            self.sel = (path, min(i, len(series) - 1))
        else:
            self.sel = (path, None)
        self._tidy(path)
        self._changed()
        self.show_props()

    def _delete_empty_branch(self):
        if self.sel is None or len(self.sel[0]) < 2:
            return
        path = self.sel[0]
        if not self.series_at(path):
            self._tidy(path, remove_empty=True)
            self._changed()
            self.show_props()

    def _tidy(self, path, remove_empty=False):
        """A branch with nothing left in it goes, and a parallel with one path left is just that path."""
        if len(path) < 2:
            return
        parent_path, (el_i, br_i) = path[:-1], path[-1]
        parent = self.series_at(parent_path)
        par = parent[el_i]
        if remove_empty and not par["branches"][br_i]:
            del par["branches"][br_i]
        if len(par["branches"]) == 1:
            parent[el_i:el_i + 1] = par["branches"][0]
            if self.sel[0][:len(path)] == path:
                self.sel = (parent_path, el_i if parent else None)
        elif remove_empty:
            self.sel = (parent_path, el_i)

    def shift(self, d):
        if self.sel is None or self.sel[1] is None:
            return
        path, i = self.sel
        series = self.series_at(path)
        if 0 <= i + d < len(series):
            series[i], series[i + d] = series[i + d], series[i]
            self.sel = (path, i + d)
            self._changed()

    # ---- drawing
    def draw(self):
        drawing = plc_view.Ladder(self.cv, self.editor.app.theme, self.rungs, sel=self.sel, rt=self.rt, pou=self.pou.get("name"))
        drawing.draw()
        self.hits = drawing.hits

    def _click(self, e):
        self.cv.focus_set()
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        for x0, y0, x1, y1, ref in self.hits:
            if x0 <= x <= x1 and y0 <= y <= y1:
                if ref[1] == "rung":
                    path = ref[0]
                    items = self.series_at(path)
                    self.sel = (path, None) if not items else (path, len(items) - 1)
                else:
                    self.sel = ref
                self.draw()
                self.show_props()
                return

    def live(self, rt):
        self.rt = rt
        self.draw()

    # ---- the selected element's fields
    def show_props(self, focus=False):
        for w in self.props.winfo_children():
            w.destroy()
        el = self._selected_element()
        names = known_names(self.editor)
        first = None

        def field(label, key, values=(), width=22, target=None):
            nonlocal first
            target = target if target is not None else el
            ttk.Label(self.props, text=label, style="Muted.TLabel").pack(side="left", padx=(0, 4))
            var = tk.StringVar(value=str(target.get(key) or ""))
            w = ttk.Combobox(self.props, textvariable=var, values=list(values), width=width)
            w.pack(side="left", padx=(0, 12))

            def changed(_e=None):
                if target.get(key) != var.get():
                    target[key] = var.get()
                    self._changed()
            w.bind("<KeyRelease>", changed)
            w.bind("<<ComboboxSelected>>", changed)
            first = first or w
            return w
        if el is None or el.get("t") == "par":
            rung = self.rungs[self.rung_index()]
            field("Rung note", "comment", (), 50, rung)
            if el is not None:
                ttk.Label(self.props, text="Parallel branches. Press Branch to add another path.", style="Muted.TLabel").pack(side="left")
        else:
            k = el.get("t")
            title = ELEMENT_TITLES.get(k, k)
            ttk.Label(self.props, text=title, style="Bold.TLabel").pack(side="left", padx=(0, 12))
            if k in ("no", "nc", "rise", "fall", "coil", "ncoil", "set", "reset"):
                field("Tag", "a", names)
            elif k == "cmp":
                field("Value", "a", names, 16)
                op = tk.StringVar(value=el.get("op", ">"))
                c = ttk.Combobox(self.props, textvariable=op, values=COMPARE_OPS, state="readonly", width=4)
                c.pack(side="left", padx=(0, 8))

                def set_op(_e=None):
                    el["op"] = op.get()
                    self._changed()
                c.bind("<<ComboboxSelected>>", set_op)
                field("than", "b", names, 16)
            elif k in ("ton", "tof", "tp"):
                field("Name", "a", (), 10)
                field("Time", "pt", ("T#100ms", "T#500ms", "T#1s", "T#2s", "T#5s", "T#10s"), 12)
            elif k in ("ctu", "ctd"):
                field("Name", "a", (), 10)
                field("Count to", "pv", (), 8)
                field("Reset by" if k == "ctu" else "Load by", "r", names, 14)
            elif k == "move":
                field("Set", "a", names, 16)
                field("to", "b", names, 26)
            elif k == "st":
                field("Statements", "code", (), 60)
        if focus and first is not None:
            first.focus_set()


# ================================================================ function block diagram
PALETTE = (("Connect", ("input", "output")), ("Logic", ("AND", "OR", "XOR", "NAND", "NOR", "NOT")),
           ("Compare", ("GT", "GE", "LT", "LE", "EQ", "NE")),
           ("Math", ("ADD", "SUB", "MUL", "DIV", "MOD", "ABS", "NEG", "SQRT", "MIN", "MAX", "LIMIT", "SCALE", "SEL", "MOVE")),
           ("Timers and counters", ("TON", "TOF", "TP", "CTU", "CTD", "CTUD")),
           ("Latches and edges", ("SR", "RS", "R_TRIG", "F_TRIG")), ("Control", ("PID",)))


class FbdPage(ttk.Frame):
    def __init__(self, master, editor, pou):
        super().__init__(master, style="Surface.TFrame")
        self.editor, self.pou = editor, pou
        src = pou.get("source")
        if not isinstance(src, dict) or not isinstance(src.get("blocks"), list) or not isinstance(src.get("wires"), list):
            pou["source"] = src = {"blocks": [], "wires": []}
        self.src = src
        self.sel = None         # ("block", id) | ("wire", wire dict)
        self.drag = None
        self.rt = None
        u = editor.app.theme.ui
        left = ttk.Frame(self, style="Surface.TFrame", padding=6)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Click to add", style="Heading.TLabel").pack(anchor="w")
        self.palette = ttk.Treeview(left, show="tree", selectmode="browse", height=16)
        self.palette.column("#0", width=170)
        self.palette.pack(fill="y", expand=True, pady=(3, 0))
        for group, items in PALETTE:
            g = self.palette.insert("", "end", text=group, open=group in ("Connect", "Logic", "Timers and counters"))
            for t in items:
                self.palette.insert(g, "end", iid=f"p:{t}", text=f"{t}  {block_title(t)}" if t not in ("input", "output")
                                    else block_title(t))
        self.palette.bind("<<TreeviewSelect>>", self._palette_pick)
        self.props = ttk.Frame(self, style="Surface.TFrame", padding=8, width=260)
        self.props.pack(side="right", fill="y")
        holder = ttk.Frame(self, style="Surface.TFrame")
        holder.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(holder, bg=u["surface"], highlightthickness=0, takefocus=1)
        ys = ttk.Scrollbar(holder, command=self.cv.yview)
        xs = ttk.Scrollbar(holder, orient="horizontal", command=self.cv.xview)
        self.cv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set, scrollregion=(0, 0, 2000, 1500))
        xs.pack(side="bottom", fill="x")
        ys.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._motion)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.cv.bind("<Delete>", lambda e: self.delete_selected())
        self.draw()
        self.show_props()

    # ---- geometry
    @staticmethod
    def _rect(b):
        return plc_view.block_rect(b)

    @staticmethod
    def _pin_xy(b, pin, side):
        return plc_view.pin_xy(b, pin, side)

    def _block(self, bid):
        return next((b for b in self.src["blocks"] if b.get("id") == bid), None)

    def _pin_at(self, x, y):
        for b in self.src["blocks"]:
            try:
                ins, outs = pins_of(b)
            except plc.CompileError:
                continue
            for side, names in (("in", ins), ("out", outs)):
                for name in names:
                    px, py = self._pin_xy(b, name, side)
                    if abs(px - x) <= 9 and abs(py - y) <= 8:
                        return b["id"], name, side
        return None

    def _block_at(self, x, y):
        for b in reversed(self.src["blocks"]):
            try:
                x0, y0, x1, y1 = self._rect(b)
            except plc.CompileError:
                continue
            if x0 <= x <= x1 and y0 <= y <= y1:
                return b
        return None

    def _wire_path(self, w):
        return plc_view.wire_path(self.src["blocks"], w)

    # ---- drawing
    def draw(self):
        t = self.editor.app.theme
        plc_view.draw_fbd(self.cv, t, self.src, sel=self.sel, frame=self._live_frame())
        u = t.ui
        cv = self.cv
        if not self.src["blocks"]:
            cv.create_text(200, 60, text="Add blocks from the list on the left, then drag from an output pin to an input pin.",
                           anchor="w", fill=u["faint"], font=t.fonts["ui"])
        if self.drag and self.drag[0] == "wire":
            _k, _bid, _pin, _side, x0, y0, x1, y1 = self.drag
            cv.create_line(x0, y0, x1, y1, fill=u["accent"], dash=(4, 3), width=1.5)

    def _undriven(self, b, pin):
        return not any(isinstance(w, dict) and w.get("to") == [b["id"], pin] for w in self.src["wires"])

    def _live_frame(self):
        return plc_view.running_frame(self.rt, self.pou.get("name")) if self.rt is not None else None

    def live(self, rt):
        self.rt = rt
        self.draw()

    # ---- interaction
    def _palette_pick(self, _e):
        sel = self.palette.selection()
        if not sel or not sel[0].startswith("p:"):
            return
        t = sel[0][2:]
        self.palette.selection_remove(sel[0])
        ids = [b.get("id") for b in self.src["blocks"] if isinstance(b.get("id"), int)]
        bid = max(ids, default=0) + 1
        x, y = 80, 40
        used = {(_coord(b.get("x")), _coord(b.get("y"))) for b in self.src["blocks"]}
        while (x, y) in used:
            y += 70
        b = {"id": bid, "type": t, "x": x, "y": y}
        if t in FB_TYPES:
            names = {str(o.get("name")) for o in self.src["blocks"]}
            prefix = {"T": "T", "C": "C"}.get(t[0], "F")
            n = 1
            while f"{prefix}{n}" in names:
                n += 1
            b["name"] = f"{prefix}{n}"
        self.src["blocks"].append(b)
        self.sel = ("block", bid)
        self.editor.mark_dirty()
        self.draw()
        self.show_props()

    def _press(self, e):
        self.cv.focus_set()
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        pin = self._pin_at(x, y)
        if pin is not None:
            bid, name, side = pin
            px, py = self._pin_xy(self._block(bid), name, side)
            self.drag = ("wire", bid, name, side, px, py, x, y)
            return
        b = self._block_at(x, y)
        if b is not None:
            self.sel = ("block", b["id"])
            self.drag = ("move", b, x - _coord(b.get("x")), y - _coord(b.get("y")), False)
            self.draw()
            self.show_props()
            return
        w = self._wire_at(x, y)
        self.sel = ("wire", w) if w is not None else None
        self.drag = None
        self.draw()
        self.show_props()

    def _wire_at(self, x, y):
        for w in self.src["wires"]:
            path = self._wire_path(w) if isinstance(w, dict) else None
            if not path:
                continue
            for i in range(0, len(path) - 2, 2):
                x0, y0, x1, y1 = path[i:i + 4]
                if min(x0, x1) - 4 <= x <= max(x0, x1) + 4 and min(y0, y1) - 4 <= y <= max(y0, y1) + 4:
                    return w
        return None

    def _motion(self, e):
        if not self.drag:
            return
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        if self.drag[0] == "move":
            _k, b, dx, dy, _m = self.drag
            nx, ny = max(20, _snap_grid(x - dx)), max(10, _snap_grid(y - dy))
            if (nx, ny) != (b.get("x"), b.get("y")):
                b["x"], b["y"] = nx, ny
                self.drag = ("move", b, dx, dy, True)
                self.draw()
        else:
            self.drag = self.drag[:6] + (x, y)
            self.draw()

    def _release(self, e):
        drag, self.drag = self.drag, None
        if not drag:
            return
        if drag[0] == "move":
            if drag[4]:
                self.editor.mark_dirty()
            return
        _k, bid, name, side, *_r = drag
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        other = self._pin_at(x, y)
        if other is not None and other[2] != side:
            src = (bid, name) if side == "out" else (other[0], other[1])
            dst = (other[0], other[1]) if side == "out" else (bid, name)
            self.src["wires"][:] = [w for w in self.src["wires"] if not isinstance(w, dict) or w.get("to") != list(dst)]
            self.src["wires"].append({"from": list(src), "to": list(dst)})
            self.editor.mark_dirty()
        self.draw()

    def delete_selected(self):
        if not self.sel:
            return
        kind, what = self.sel
        if kind == "block":
            self.src["blocks"][:] = [b for b in self.src["blocks"] if b.get("id") != what]
            self.src["wires"][:] = [w for w in self.src["wires"] if isinstance(w, dict) and
                                    w.get("from", [None])[0] != what and w.get("to", [None])[0] != what]
        else:
            self.src["wires"].remove(what)
        self.sel = None
        self.editor.mark_dirty()
        self.draw()
        self.show_props()

    # ---- properties
    def show_props(self):
        for w in self.props.winfo_children():
            w.destroy()
        names = known_names(self.editor)
        if not self.sel:
            ttk.Label(self.props, text="Nothing selected", style="Bold.TLabel").pack(anchor="w")
            ttk.Label(self.props, text="Click a block or a wire. Delete removes it.", style="Muted.TLabel", wraplength=230).pack(anchor="w")
            return
        kind, what = self.sel
        if kind == "wire":
            ttk.Label(self.props, text="Wire", style="Bold.TLabel").pack(anchor="w")
            ttk.Button(self.props, text="Delete", command=self.delete_selected).pack(anchor="w", pady=(6, 0))
            return
        b = self._block(what)
        if b is None:
            return
        t = b.get("type")
        ttk.Label(self.props, text=block_title(t), style="Bold.TLabel").pack(anchor="w")

        def field(label, get, put, values=(), width=26):
            ttk.Label(self.props, text=label, style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
            var = tk.StringVar(value=str(get() or ""))
            c = ttk.Combobox(self.props, textvariable=var, values=list(values), width=width)
            c.pack(anchor="w")

            def changed(_e=None):
                if str(get() or "") != var.get():
                    put(var.get())
                    self.editor.mark_dirty()
                    self.draw()
            c.bind("<KeyRelease>", changed)
            c.bind("<<ComboboxSelected>>", changed)
        if t == "input":
            field("Reads (a tag or any expression)", lambda: b.get("expr"), lambda v: b.__setitem__("expr", v), names)
        elif t == "output":
            field("Writes to", lambda: b.get("target"), lambda v: b.__setitem__("target", v), names)
        else:
            if t in FB_TYPES:
                field("Instance name (readable elsewhere as name.Q)", lambda: b.get("name"), lambda v: b.__setitem__("name", v))
            if t in GATES and GATES[t][0] is None:
                ttk.Label(self.props, text="Inputs", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
                var = tk.IntVar(value=len(pins_of(b)[0]))
                sp = ttk.Spinbox(self.props, from_=2, to=32, textvariable=var, width=5,
                                 command=lambda: self._set_inputs(b, var))
                sp.pack(anchor="w")
                sp.bind("<Return>", lambda e: self._set_inputs(b, var))
            ins, _outs = pins_of(b)
            for pin in ins:
                if not self._undriven(b, pin):
                    continue
                pins = b.setdefault("pins", {})
                field(f"{pin}, when no wire is on it", lambda p=pin: pins.get(p), lambda v, p=pin: pins.__setitem__(p, v), width=20)
            neg = tk.StringVar(value=" ".join(b.get("neg") or []))
            ttk.Label(self.props, text="Inverted inputs (names, space between)", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
            e = ttk.Entry(self.props, textvariable=neg, width=20)
            e.pack(anchor="w")

            def set_neg(_e=None):
                b["neg"] = [x for x in neg.get().split() if x in ins]
                self.editor.mark_dirty()
                self.draw()
            e.bind("<FocusOut>", set_neg)
            e.bind("<Return>", set_neg)
        ttk.Button(self.props, text="Delete block", command=self.delete_selected).pack(anchor="w", pady=(12, 0))

    def _set_inputs(self, b, var):
        try:
            b["n"] = max(2, min(int(var.get()), 32))
        except (tk.TclError, ValueError):
            return
        valid = set(pins_of(b)[0])
        self.src["wires"][:] = [w for w in self.src["wires"] if not isinstance(w, dict) or w.get("to", [None])[0] != b["id"]
                                or w["to"][1] in valid]
        self.editor.mark_dirty()
        self.draw()


class SfcPage(ttk.Frame):
    def __init__(self, master, editor, pou):
        super().__init__(master, style="Surface.TFrame")
        self.editor, self.pou = editor, pou
        src = pou.get("source")
        if not isinstance(src, dict) or not isinstance(src.get("steps"), list) or not isinstance(src.get("transitions"), list):
            pou["source"] = src = {"steps": [], "transitions": []}
        self.src = src
        self.sel = None         # ("step", id) | ("trans", id)
        self.rt = None
        self.pos = {}
        self.hits = []
        bar = ttk.Frame(self, style="Surface.TFrame", padding=(8, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text="Add step after this one", command=self.add_step_after).pack(side="left")
        ttk.Button(bar, text="Add a parallel step", command=self.add_parallel).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Add a transition", command=self.add_transition).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Delete", command=self.delete_selected).pack(side="left", padx=(6, 0))
        u = editor.app.theme.ui
        self.props = ScrollFrame(self)
        self.props.configure(width=330)
        self.props.pack(side="right", fill="y")
        self.props.pack_propagate(False)
        holder = ttk.Frame(self, style="Surface.TFrame")
        holder.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(holder, bg=u["surface"], highlightthickness=0, takefocus=1)
        ys = ttk.Scrollbar(holder, command=self.cv.yview)
        xs = ttk.Scrollbar(holder, orient="horizontal", command=self.cv.xview)
        self.cv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        xs.pack(side="bottom", fill="x")
        ys.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Delete>", lambda e: self.delete_selected())
        steps = self._steps()
        if steps:
            self.sel = ("step", steps[0]["id"])
        self.draw()
        self.show_props()

    def _steps(self):
        return [s for s in self.src["steps"] if isinstance(s, dict) and isinstance(s.get("id"), int)]

    def _trans(self):
        return [t for t in self.src["transitions"] if isinstance(t, dict)]

    def _step(self, sid):
        return next((s for s in self._steps() if s["id"] == sid), None)

    def _next_id(self, items):
        return max((x.get("id", 0) for x in items if isinstance(x.get("id"), int)), default=0) + 1

    def _new_step(self, name_hint="Step"):
        steps = self._steps()
        names = {str(s.get("name")).casefold() for s in steps}
        n = len(steps) + 1
        while f"{name_hint}{n}".casefold() in names:
            n += 1
        s = {"id": self._next_id(steps), "name": f"{name_hint}{n}", "actions": []}
        if not steps:
            s["initial"] = True
        self.src["steps"].append(s)
        return s

    def add_step_after(self):
        prev = self.sel[1] if self.sel and self.sel[0] == "step" else None
        s = self._new_step()
        if prev is not None:
            self.src["transitions"].append({"id": self._next_id(self._trans()), "from": [prev], "to": [s["id"]], "cond": "TRUE"})
        self.sel = ("step", s["id"])
        self._changed()

    def add_parallel(self):
        """Another step started by the transition into the selected step: a parallel branch."""
        if not self.sel or self.sel[0] != "step":
            return
        into = [t for t in self._trans() if self.sel[1] in (t.get("to") or [])]
        s = self._new_step()
        if into:
            into[0]["to"].append(s["id"])
        self.sel = ("step", s["id"])
        self._changed()

    def add_transition(self):
        steps = self._steps()
        if not steps:
            return
        start = self.sel[1] if self.sel and self.sel[0] == "step" else steps[0]["id"]
        t = {"id": self._next_id(self._trans()), "from": [start], "to": [steps[0]["id"]], "cond": "TRUE"}
        self.src["transitions"].append(t)
        self.sel = ("trans", t["id"])
        self._changed()

    def delete_selected(self):
        if not self.sel:
            return
        kind, i = self.sel
        if kind == "step":
            self.src["steps"][:] = [s for s in self.src["steps"] if not isinstance(s, dict) or s.get("id") != i]
            keep = []
            for t in self.src["transitions"]:
                if not isinstance(t, dict):
                    continue
                t["from"] = [x for x in t.get("from", []) if x != i]
                t["to"] = [x for x in t.get("to", []) if x != i]
                if t["from"] and t["to"]:
                    keep.append(t)
            self.src["transitions"][:] = keep
        else:
            self.src["transitions"][:] = [t for t in self._trans() if t.get("id") != i]
        self.sel = None
        self._changed()

    def _changed(self):
        self.editor.mark_dirty()
        self.draw()
        self.show_props()

    # ---- layout: steps by depth from the start, top to bottom; parallel steps side by side
    def draw(self):
        t = self.editor.app.theme
        self.hits = plc_view.draw_chart(self.cv, t, self.src, sel=self.sel, active=plc_view.step_is_active(self.rt) if self.rt is not None else None)
        if not self.src["steps"]:
            self.cv.create_text(40, 40, text="Press “Add step after this one” to begin.", anchor="w", fill=t.ui["faint"], font=t.fonts["ui"])

    def _click(self, e):
        self.cv.focus_set()
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        for x0, y0, x1, y1, ref in self.hits:
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.sel = ref
                self.draw()
                self.show_props()
                return
        self.sel = None
        self.draw()
        self.show_props()

    def live(self, rt):
        self.rt = rt
        self.draw()

    # ---- properties
    def show_props(self):
        self.props.clear()
        box = ttk.Frame(self.props.inner, style="Surface.TFrame", padding=8)
        box.pack(fill="both", expand=True)
        if not self.sel:
            ttk.Label(box, text="Nothing selected", style="Bold.TLabel").pack(anchor="w")
            ttk.Label(box, text="Click a step or the bar of a transition.", style="Muted.TLabel", wraplength=280).pack(anchor="w")
            return
        kind, i = self.sel
        if kind == "step":
            self._step_props(box, self._step(i))
        else:
            self._trans_props(box, next((t for t in self._trans() if t.get("id") == i), None))

    def _step_props(self, box, s):
        if s is None:
            return
        ttk.Label(box, text="Step", style="Bold.TLabel").pack(anchor="w")
        var = tk.StringVar(value=str(s.get("name", "")))
        ttk.Label(box, text="Name", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        e = ttk.Entry(box, textvariable=var, width=24)
        e.pack(anchor="w")

        def rename(_e=None):
            value = var.get().strip()
            if value and value != s.get("name"):
                s["name"] = value
                self.editor.mark_dirty()
                self.draw()
        e.bind("<KeyRelease>", rename)
        init = tk.BooleanVar(value=bool(s.get("initial")))

        def set_init():
            if init.get():
                s["initial"] = True
            else:
                s.pop("initial", None)
            self.editor.mark_dirty()
            self.draw()
        ttk.Checkbutton(box, text="Active at the start", variable=init, command=set_init).pack(anchor="w", pady=(6, 0))
        ttk.Label(box, text="Actions", style="Heading.TLabel").pack(anchor="w", pady=(12, 2))
        acts = s.setdefault("actions", [])
        names = known_names(self.editor)
        for a in list(acts):
            if not isinstance(a, dict):
                continue
            row = ttk.Frame(box, style="Surface.TFrame", padding=(0, 2))
            row.pack(fill="x")
            q = tk.StringVar(value=a.get("q", "N"))
            c = ttk.Combobox(row, textvariable=q, values=list(QUALIFIERS), state="readonly", width=3)
            c.pack(side="left")
            Tooltip(c, "  ".join(f"{k}: {v}." for k, v in QUALIFIERS.items()))

            def set_q(_e=None, a=a, q=q):
                a["q"] = q.get()
                self._changed()
            c.bind("<<ComboboxSelected>>", set_q)
            text = tk.StringVar(value=str(a.get("target") or a.get("code") or ""))
            w = ttk.Combobox(row, textvariable=text, values=names, width=20)
            w.pack(side="left", padx=4)
            Tooltip(w, "A tag to set, or ST statements ending in ; to run")

            def set_text(_e=None, a=a, text=text):
                value = text.get().strip()
                a.pop("target", None)
                a.pop("code", None)
                if ";" in value or ":=" in value:
                    a["code"] = value
                elif value:
                    a["target"] = value
                self.editor.mark_dirty()
                self.draw()
            w.bind("<KeyRelease>", set_text)
            w.bind("<<ComboboxSelected>>", set_text)
            if a.get("q") in ("L", "D"):
                tv = tk.StringVar(value=str(a.get("time") or "T#1s"))
                te = ttk.Entry(row, textvariable=tv, width=7)
                te.pack(side="left")

                def set_time(_e=None, a=a, tv=tv):
                    a["time"] = tv.get().strip()
                    self.editor.mark_dirty()
                te.bind("<KeyRelease>", set_time)
            ttk.Button(row, text="✕", width=2, command=lambda a=a: (acts.remove(a), self._changed())).pack(side="left", padx=(4, 0))
        ttk.Button(box, text="Add action", command=lambda: (acts.append({"q": "N", "target": ""}), self._changed())).pack(anchor="w", pady=(6, 0))
        ttk.Label(box, text="Elsewhere, this step reads as Name.X (active) and Name.T (time active).", style="Muted.TLabel",
                  wraplength=280, justify="left").pack(anchor="w", pady=(12, 0))

    def _trans_props(self, box, t):
        if t is None:
            return
        ttk.Label(box, text="Transition", style="Bold.TLabel").pack(anchor="w")
        ttk.Label(box, text="Fires when", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        var = tk.StringVar(value=str(t.get("cond") or ""))
        c = ttk.Combobox(box, textvariable=var, values=known_names(self.editor) + ["TRUE"], width=34)
        c.pack(anchor="w")

        def set_cond(_e=None):
            t["cond"] = var.get()
            self.editor.mark_dirty()
            self.draw()
        c.bind("<KeyRelease>", set_cond)
        c.bind("<<ComboboxSelected>>", set_cond)
        ttk.Label(box, text="e.g. Start AND NOT Stop, or Clamp.T > T#2s", style="Faint.TLabel").pack(anchor="w")
        steps = self._steps()
        for key, title in (("from", "From these steps (all must be active)"), ("to", "To these steps (all start)")):
            ttk.Label(box, text=title, style="Muted.TLabel").pack(anchor="w", pady=(10, 0))
            current = t.setdefault(key, [])
            for s in steps:
                on = tk.BooleanVar(value=s["id"] in current)

                def toggle(s=s, on=on, current=current):
                    if on.get() and s["id"] not in current:
                        current.append(s["id"])
                    elif not on.get() and s["id"] in current:
                        current.remove(s["id"])
                    self.editor.mark_dirty()
                    self.draw()
                ttk.Checkbutton(box, text=str(s.get("name")), variable=on, command=toggle).pack(anchor="w")
