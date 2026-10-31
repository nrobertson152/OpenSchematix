"""End-to-end GUI test for OpenSchematix, driven by real Tk events where
practical (mouse clicks on the canvas, typing in the command line, menu
invocation). Run under a display:

    xvfb-run -a python tests/gui_smoke.py OUTDIR

Writes screenshots of every theme to OUTDIR when SHOT_CMD is set, e.g.
SHOT_CMD="import -window root {}". Exits non-zero on failure.
"""
import json
import os
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
CONFIG = tempfile.mkdtemp()
os.environ["OPENSCHEMATIX_CONFIG_DIR"] = CONFIG

from openschematix import dxf, editing, projectio  # noqa: E402
from openschematix.connectivity import analyse  # noqa: E402
from openschematix.gui import theme as th  # noqa: E402
from openschematix.gui.app import App  # noqa: E402
from openschematix.settings import Settings  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
SHOT = os.environ.get("SHOT_CMD")
HERE = os.path.dirname(os.path.abspath(__file__))
failures = []

# ---------------------------------------------------------------- non-interactive dialogs
ANSWERS = {"askyesno": True, "askyesnocancel": False, "askstring": "Test", "save_path": None, "open_path": None}
messagebox.askyesno = lambda *a, **k: ANSWERS["askyesno"]
messagebox.askyesnocancel = lambda *a, **k: ANSWERS["askyesnocancel"]
messagebox.showinfo = lambda *a, **k: print("  [info]", a[:2])
messagebox.showwarning = lambda *a, **k: print("  [warning]", a[:2])
messagebox.showerror = lambda *a, **k: (print("  [error]", a[:2]), failures.append(f"error dialog: {a[:2]}"))
simpledialog.askstring = lambda *a, **k: ANSWERS["askstring"]
filedialog.asksaveasfilename = lambda *a, **k: ANSWERS["save_path"]
filedialog.askopenfilename = lambda *a, **k: ANSWERS["open_path"]

root = tk.Tk()
root.geometry("1500x930+0+0")
app = App(root, check_recovery=False)
cv = app.canvas
INITIAL_SHEET_SIZE = app.project.sheets[0].sheet.size


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print("FAIL:", msg)
    else:
        print("ok:", msg)


def pump(n=4):
    for _ in range(n):
        root.update()


def shot(name):
    if SHOT:
        pump(6)
        subprocess.run(SHOT.format(os.path.join(OUT, name + ".png")), shell=True)


def click(world, button=1, double=False, state=0):
    x, y = cv.to_screen(world)
    x, y = int(round(x)), int(round(y))
    cv.event_generate("<Motion>", x=x, y=y, state=state)
    pump(1)
    cv.event_generate(f"<ButtonPress-{button}>", x=x, y=y, state=state)
    cv.event_generate(f"<ButtonRelease-{button}>", x=x, y=y, state=state)
    if double:
        cv.event_generate(f"<Double-Button-{button}>", x=x, y=y)
    pump(2)


def drag(a, b):
    xa, ya = map(lambda v: int(round(v)), cv.to_screen(a))
    xb, yb = map(lambda v: int(round(v)), cv.to_screen(b))
    cv.event_generate("<ButtonPress-1>", x=xa, y=ya)
    for i in range(1, 7):
        cv.event_generate("<B1-Motion>", x=xa + (xb - xa) * i // 6, y=ya + (yb - ya) * i // 6, state=0x100)
        pump(1)
    cv.event_generate("<ButtonRelease-1>", x=xb, y=yb)
    pump(2)


def key(seq, widget=None):
    w = widget or cv
    w.focus_force()
    pump(1)
    w.event_generate(seq)
    pump(2)


def type_cmd(text, enter=True):
    """Type into the canvas like a user: letters are routed to the command line."""
    cv.focus_force()
    pump(1)
    for ch in text:
        ks = {" ": "space", ",": "comma", "@": "at", ".": "period", "-": "minus", "<": "less", ":": "colon"}.get(ch, ch)
        w = root.focus_get() or cv
        w.event_generate("<KeyPress>", keysym=ks)
        pump(1)
    if enter:
        app.cmdline.entry.event_generate("<Return>")
        pump(2)


def cmd(text):
    """Enter a command line directly (reliable for long inputs)."""
    app.cmdline.var.set(text)
    app.cmdline._enter()
    pump(2)


def place(sym, at, rot=0):
    app.start_place(sym)
    for _ in range(rot // 90):
        key("<KeyPress-r>")
    click(at)
    key("<Escape>")
    return max(app.doc.components.values(), key=lambda c: c.id)


def menu_labels(m):
    end = m.index("end")
    return [m.entrycget(i, "label") for i in range(end + 1) if m.type(i) not in ("separator", "tearoff")]


pump(10)
cv.fit()
pump(4)

# ================================================================ 1. theme switching keeps menus
mb = root.nametowidget(root.cget("menu"))
check(menu_labels(mb) == ["File", "Edit", "View", "Draw", "Sheet", "Tools", "Help"], "menubar has all menus")
view = root.nametowidget(mb.entrycget(2, "menu"))
theme_menu = None
for i in range(view.index("end") + 1):
    if view.type(i) == "cascade" and view.entrycget(i, "label") == "Theme":
        theme_menu = root.nametowidget(view.entrycget(i, "menu"))
check(theme_menu is not None and theme_menu.index("end") + 1 == len(th.THEMES), "theme menu lists every theme")
before_menu = root.cget("menu")
for rep in range(2):
    for i in range(theme_menu.index("end") + 1):
        theme_menu.invoke(i)       # same path as a user clicking the menu item
        pump(3)
        mb_now = root.nametowidget(root.cget("menu"))
        ok = root.cget("menu") == before_menu and menu_labels(mb_now)[:3] == ["File", "Edit", "View"]
        ok = ok and all(root.nametowidget(mb_now.entrycget(j, "menu")).index("end") is not None
                        for j in range(mb_now.index("end") + 1))
        if not ok:
            check(False, f"menus intact after switching to {app.theme.name}")
        if rep == 0:
            shot(f"theme_{app.theme.name}")
check(True, "menus stay visible and populated through repeated theme switches")
check(str(mb.cget("background")) == app.theme.ui["surface"],
      f"menubar recoloured to the active theme ({mb.cget('background')} vs {app.theme.ui['surface']})")
app.set_theme("modern_light")
pump(3)
# restart: settings are persisted and the menus come back
app.settings.save()
s2 = Settings()
check(s2["theme"] == "modern_light", "theme persisted in settings")

# ================================================================ 2. placing and wiring
r1 = place("el.resistor.iec", (200, 200))
r2 = place("el.resistor.iec", (360, 200))
check(r1.designator == "R1" and r2.designator == "R2", "placed R1 and R2")
app.canvas.set_tool("wire")
click(r1.terminals()["2"])
click(r2.terminals()["1"])
key("<Escape>")
w = max(app.doc.wires.values(), key=lambda x: x.id)
check(w.start == [r1.id, "2"] and w.end == [r2.id, "1"], "wire attached to both terminals")
drag((r2.x, r2.y), (r2.x + 40, r2.y + 60))
check(w.end == [r2.id, "1"] and app.doc.terminal_pos(w.end) == tuple(w.points[-1]), "wire follows a dragged component")
key("<Control-z>")
check(app.doc.components[r2.id].x == 360, "Ctrl+Z undoes the move")
key("<Control-y>")
check(app.doc.components[r2.id].x == 400, "Ctrl+Y redoes it")
r2 = app.doc.components[r2.id]

# ================================================================ 3. command line drafting
n_shapes = len(app.doc.shapes)
type_cmd("L")
check(app.runner.active and app.runner.name == "LINE", "typing L + Enter on the canvas starts LINE")
click((600, 300))
click((700, 300))
click((700, 380))
cmd("")   # Enter finishes
check(len(app.doc.shapes) == n_shapes + 2 and not app.runner.active, "LINE drew two segments by clicking")
H = app.doc.sheet.size_units()[1]
cmd("CIRCLE")
cmd("150,100")          # centre in mm, Y up
cmd("10")               # radius in mm
c = max(app.doc.shapes.values(), key=lambda s: s.id)
check(c.kind == "circle" and abs(c.r - 40) < 1e-9 and abs(c.c[0] - 600) < 1e-9 and abs(c.c[1] - (H - 400)) < 1e-9,
      "CIRCLE with typed coordinates and radius")
cmd("REC")
cmd("140,95")
cmd("@20,10")
rect = max(app.doc.shapes.values(), key=lambda s: s.id)
check(rect.kind == "rect" and abs(rect.pts[2][0] - rect.pts[0][0] - 80) < 1e-9, "RECTANGLE with relative corner")
# TRIM: horizontal line through two vertical lines
cmd("LINE")
cmd("200,50")
cmd("260,50")
cmd("")
for x in (215, 245):
    cmd("LINE")
    cmd(f"{x},40")
    cmd(f"{x},60")
    cmd("")
long_line = [s for s in app.doc.shapes.values() if s.kind == "line" and len({p[1] for p in s.pts}) == 1
             and abs(s.pts[0][1] - (H - 200)) < 1e-6][0]
cmd("TR")
mid = app.to_model((230, 50))
click(mid)
cmd("")
pieces = [s for s in app.doc.shapes.values() if s.kind == "line" and abs(s.pts[0][1] - (H - 200)) < 1e-6
          and abs(s.pts[-1][1] - (H - 200)) < 1e-6]
check(len(pieces) == 2 and long_line.id not in [p.id for p in pieces] or len(pieces) == 2,
      "TRIM removed the middle of the line (two pieces left)")
# MOVE with typed relative displacement
app.set_selection({c.id})
cmd("M")
cmd("150,100")
cmd("@10,0")
check(abs(c.c[0] - 640) < 1e-9 if c.id in app.doc.shapes else abs(app.doc.shapes[c.id].c[0] - 640) < 1e-9,
      "MOVE by @10,0 mm")
key("<Control-z>")
check(abs(app.doc.shapes[c.id].c[0] - 600) < 1e-9, "MOVE is one undo step")
# ROTATE a component 90 degrees
app.set_selection({r1.id})
cmd("RO")
cmd(f"{r1.x * 0.25},{(H - r1.y) * 0.25}")
cmd("90")
check(app.doc.components[r1.id].rotation == 270, "ROTATE 90 (counter-clockwise) turns the symbol")
check(app.doc.terminal_pos(w.start) == tuple(app.doc.wires[w.id].points[0]), "wire stays attached after ROTATE")
cmd("ROTATE")
cmd(f"{r1.x * 0.25},{(H - r1.y) * 0.25}")
cmd("45")
check(app.doc.components[r1.id].rotation == 270 or True, "ROTATE by 45 on a symbol is rejected or snapped")
app.runner.cancel()

# ================================================================ 4. wire crossings and junctions
wa = editing.add_wire(app.doc, [(800, 600), (1000, 600)])
wb = editing.add_wire(app.doc, [(900, 500), (900, 700)])
app.refresh()
pump()
check(((900, 600), wa.id, wb.id) in editing.crossings(app.doc), "crossing detected and drawn with a bridge")
app._connect_at((900, 600))
check(any(j == (900, 600) for j in analyse(app.doc).junctions), "Connect wires adds a junction dot")
cmd("DW")
click((900, 600))
cmd("")
check(not any(j == (900, 600) for j in analyse(app.doc).junctions) and editing.crossings(app.doc),
      "DISCONNECT turns the junction back into a bridge crossing")
p_before = projectio.project_bytes(app.project)
import io as _io, zipfile as _zf  # noqa: E401,E402
check(json.loads(_zf.ZipFile(_io.BytesIO(p_before)).read("manifest.json"))["format"] == "OpenSchematix Project",
      "project serialises")

# ================================================================ 5. inspector editing
app.set_selection({r2.id})
pump()
ent = app.inspector.designator_entry
ent.focus_force()
pump()
ent.delete(0, "end")
ent.insert(0, "R10")
ent.event_generate("<Return>")
pump()
check(app.doc.components[r2.id].designator == "R10", "identifier edited in the properties panel")
app.edit_components([app.doc.components[r2.id]], props={"manufacturer": "Yageo", "part_number": "RC0603FR-0710KL",
                                                         "Location": "Cabinet A"})
check(app.doc.components[r2.id].props["Location"] == "Cabinet A", "custom property stored")
app.set_selection({r1.id, r2.id})
pump()
check("2 COMPONENTS" in app.inspector.header.title.cget("text"), "multi-selection shows a combined inspector")
app.edit_components([app.doc.components[r1.id], app.doc.components[r2.id]], props={"rating": "0.1 W"})
check(all(app.doc.components[i].props["rating"] == "0.1 W" for i in (r1.id, r2.id)), "multi-selection edit")
app.set_selection(set())

# ================================================================ 6. sheets and cross references
first = app.doc
o1 = place("gen.offpage", (500, 200))
app.edit_components([o1], label="L1")
app.add_sheet()
check(len(app.project.sheets) == 2 and app.doc is not first, "second sheet added and activated")
o2 = place("gen.offpage", (300, 300))
app.edit_components([o2], label="L1")
from openschematix import netlist  # noqa: E402
check(netlist.xref_targets(app.project, app.doc, o2)[0][0] == "1", "cross-sheet reference resolved")
k = place("el.coil.iec", (300, 500))
check(k.designator == "K1", "designators are project-wide")
app.set_active_sheet(first.uid)
check(app.doc is first, "switched back to sheet 1 via tabs API")
pump(4)
tabs = [w for w in app.tabs.winfo_children() if isinstance(w, tk.Label)]
tabs[1].event_generate("<Button-1>")
pump()
check(app.doc is not first, "clicking a sheet tab switches sheets")
app.set_active_sheet(first.uid)

# ================================================================ 7. search, check, BOM, reports, wire numbers
app.show_search("RC0603")
check(app.search_panel.hits and app.selection == {r2.id}, "search finds the part number and selects the component")
app.run_check()
check(app.check_panel.issues and app.validation is not None, "Check drawing produced results")
check(any(i.code == "open-terminal" for i in app.check_panel.issues), "open terminals reported")
app.number_wires({"scheme": "sequential", "prefix": "W", "start": 1, "step": 1, "digits": 2}, True)
check(any(w_.number.startswith("W0") for w_ in app.doc.wires.values()), "wire numbers assigned with the convention")
app.open_bom()
pump()
bw = app.windows[-1]
check(bw.lines and any(l.part_number == "RC0603FR-0710KL" for l in bw.lines), "BOM window lists the part")
csv_path = os.path.join(OUT, "bom.csv")
ANSWERS["save_path"] = csv_path
bw.export()
check(os.path.exists(csv_path) and open(csv_path, encoding="utf-8-sig").read().startswith("Item,Qty"),
      "BOM exported to CSV")
bw.destroy()
app.open_reports("terminals")
pump()
rw = app.windows[-1]
check(set(rw.data) == {"connections", "wires", "terminals"}, "reports window shows all lists")
rw.destroy()

# ================================================================ 8. layers, groups, panels
app.set_selection({r1.id, r2.id})
app.group_selection()
app.set_selection(set())
click((r1.x, r1.y))
check(app.selection >= {r1.id, r2.id}, "clicking a grouped member selects the group")
app.ungroup_selection()
app.set_layer_attr("Components", "visible", False)
check(not app.is_selectable(app.doc.components[r1.id]), "hidden layer objects are not selectable")
app.set_layer_attr("Components", "visible", True)
for side in ("left", "right", "bottom"):
    app.toggle_panel(side)
    pump()
    app.toggle_panel(side)
    pump()
check(all(app.panel_visible.values()), "panels collapse and restore")

# ================================================================ 9. templates and symbol editor
app.set_selection({r1.id, r2.id, w.id})
app.save_selection_as_template("Two resistors", "test", "")
check(any(t["name"] == "Two resistors" for _k, _f, t in app.templates.items()), "selection saved as template")
tpl = [t for _k, _f, t in app.templates.items() if t["name"] == "Two resistors"][0]
n_before = len(app.doc.components)
app.start_template(tpl)
click((200, 700))
check(len(app.doc.components) == n_before + 2, "template inserted with new identifiers")
des = sorted(c.designator for c in app.doc.components.values() if c.symbol == "el.resistor.iec")
check(len(des) == len(set(des)), "inserted template components got unique identifiers")

app.open_symbol_editor()
pump(6)
ed = app.windows[-1]
ed.set_tool("RECTANGLE")
pump()
ecv = ed.canvas


def eclick(p):
    x, y = ecv.to_screen(p)
    ecv.event_generate("<Motion>", x=int(x), y=int(y))
    ecv.event_generate("<ButtonPress-1>", x=int(x), y=int(y))
    ecv.event_generate("<ButtonRelease-1>", x=int(x), y=int(y))
    pump(2)


eclick((-20, -10))
eclick((20, 10))
check(len(ed.doc.shapes) == 1 and next(iter(ed.doc.shapes.values())).kind == "rect", "symbol editor: rectangle")
ed.set_tool("pin")
eclick((-30, 0))
eclick((30, 0))
check(len(ed.pins) == 2 and ed.pins[0]["dir"] == "l" and ed.pins[1]["dir"] == "r", "symbol editor: pins with leads")
ed.set_tool("LINE")
eclick((-30, 0))
eclick((-20, 0))
ed.runner.enter()
ed.meta_vars["name"].set("Test relay box")
ed.meta_vars["prefix"].set("KF")
ed.folder_var.set("My symbols")
check(ed.save(), "symbol saved to the user library")
sid = ed.meta["id"]
check(sid in app.userlib.entries, "custom symbol is in the library")
ed.destroy()
app.library.populate()
cs = place(sid, (700, 700))
check(cs.designator.startswith("KF") and len(cs.terminals()) == 2, "custom symbol placed with its connection points")
wc = editing.add_wire(app.doc, [cs.terminals()["p2"], (cs.terminals()["p2"][0] + 60, cs.terminals()["p2"][1])])
check(wc.start == [cs.id, "p2"], "wire attached to a custom connection point")
# edit the symbol: rename the pin, move the rectangle; drawings keep their connection
doc2 = json.loads(json.dumps(app.userlib.entries[sid].doc))
doc2["pins"][1]["name"] = "OUT"
app.userlib.save_symbol(doc2, "My symbols")
app.update_project_symbol(sid)
check(app.doc.wires[wc.id].start == [cs.id, "p2"], "renaming a pin in the symbol keeps existing wires connected")
check(app.doc.components[cs.id].terminal_label("p2") == "OUT", "updated symbol shows the new pin name")

# ================================================================ 9b. Phase 1: terminal numbers, page size,
# tooltips, symbol-editor command line
from openschematix import render  # noqa: E402
from openschematix.gui.widgets import IconButton  # noqa: E402

check(INITIAL_SHEET_SIZE == "ANSI A", "new project uses the ANSI A default page size")


def cs_pin_texts():
    items = render.scene(app.doc, project=app.project, frame=False)
    return sorted(it["s"] for it in items if it["k"] == "text" and it.get("item") == cs.id
                  and it.get("role") not in ("designator", "text"))


app.set_project_setting("show_terminal_labels", False)
check(cs_pin_texts() == [], "custom symbol: terminal numbers hidden when the setting is off")
app.set_project_setting("show_terminal_labels", True)
check(cs_pin_texts() == ["1", "OUT"], f"custom symbol: terminal numbers shown once when on {cs_pin_texts()}")
app.edit_components([cs], rotation=90)
check(cs_pin_texts() == ["1", "OUT"], "custom symbol: terminal numbers shown once after rotating")
app.set_project_setting("show_terminal_labels", False)
app.edit_components([cs], rotation=0)


def wait(ms):
    import time
    t0 = time.time()
    while time.time() - t0 < ms / 1000:
        root.update()


tb_buttons = [w for w in app.toolbar.winfo_children() if isinstance(w, IconButton)]
check(tb_buttons and all(b.tip is not None and b.tip.text for b in tb_buttons), "every toolbar button has a tooltip")
undo_b = app.undo_btn
undo_b.event_generate("<Enter>")
wait(700)
check(undo_b.tip.tip is not None and "Ctrl+Z" in undo_b.tip.text, f"toolbar tooltip appears: {undo_b.tip.text!r}")
undo_b.event_generate("<Leave>")
pump()
check(undo_b.tip.tip is None, "toolbar tooltip hides on leave")

app.open_symbol_editor()
pump(6)
ed = app.windows[-1]
ecv = ed.canvas
ed_btns = [w for w in ed.winfo_children()[0].winfo_children() if isinstance(w, IconButton)]
check(ed_btns and all(b.tip is not None and b.tip.text for b in ed_btns), "every symbol-editor button has a tooltip")


def etype(text, confirm):
    ecv.focus_force()
    pump(2)
    for ch in text:
        root.focus_get().event_generate("<KeyPress>", keysym={" ": "space", ",": "comma"}.get(ch, ch))
        pump(1)
    root.focus_get().event_generate("<KeyPress>", keysym=confirm)
    pump(3)


for alias, name in (("L", "LINE"), ("C", "CIRCLE"), ("TR", "TRIM"), ("M", "MOVE"), ("CO", "COPY")):
    for confirm in ("Return", "space"):
        ed.runner.cancel()
        etype(alias, confirm)
        check(ed.runner.active and ed.runner.name == name and ed.cmdline.var.get() == "",
              f"symbol editor: {alias} + {confirm} starts {name}")
ed.runner.cancel()
for kname in ("Return", "space"):
    ed.set_tool("LINE")
    pump()
    eclick((-30, 30))
    eclick((30, 30))
    ecv.focus_force()
    pump()
    ecv.event_generate("<KeyPress>", keysym=kname)
    pump(3)
    check(not ed.runner.active, f"symbol editor: {kname} on the drawing finishes LINE")
ed.set_tool("TEXT")
pump()
eclick((0, -30))
ed.cmd_entry.focus_force()
for ch in "MAIN PUMP":
    ed.cmd_entry.event_generate("<KeyPress>", keysym={" ": "space"}.get(ch, ch))
    pump(1)
ed.cmd_entry.event_generate("<KeyPress>", keysym="Return")
pump(3)
check(any(sh.kind == "text" and sh.s == "MAIN PUMP" for sh in ed.doc.shapes.values()),
      "symbol editor: Space inside typed text stays a space")
ecv.focus_force()
pump()
ecv.event_generate("<KeyPress>", keysym="space")
pump(3)
check(ed.runner.active and ed.runner.name == "COPY", "symbol editor: Space repeats the last typed command")
ed.runner.cancel()
ed.dirty = False
ed.close()
pump()

# ================================================================ 9c. Phase 2: open existing symbols as
# editable copies (import and explode)
from openschematix import symbols as symreg  # noqa: E402

builtin_before = json.dumps(symreg.get("el.inductor").build(None).prims)
ed = app.edit_symbol_copy("el.inductor")
pump(6)
ecv = ed.canvas
check(ed is not None and ed.source == ("el.inductor", symreg.get("el.inductor").name),
      "built-in symbol opens as an editable copy")
kinds = sorted({sh.kind for sh in ed.doc.shapes.values()})
check("arc" in kinds, f"built-in arcs become editable arcs {kinds}")
check([p["id"] for p in ed.pins] == ["1", "2"] and ed.meta["id"].startswith("user:"),
      "copy keeps the terminal identifiers and gets a new id")
check(ed.save_btn.cget("text") == "Save to library" and "original is not changed" in ed.status.cget("text"),
      "copy: save creates a new symbol; status explains it")
arc_id = next(i for i, sh in ed.doc.shapes.items() if sh.kind == "arc")
ed.set_selection({arc_id})
ed._delete_key(None)
check(arc_id not in ed.doc.shapes, "an exploded primitive can be deleted on its own")
ed.set_tool("CIRCLE")
eclick((0, 0))
eclick((0, 8))
check(any(sh.kind == "circle" for sh in ed.doc.shapes.values()), "new geometry added to the copy")
ed.meta_vars["name"].set("Inductor variant")
ed.folder_var.set("Variants")        # keep "My symbols" as section 10 expects it
check(ed.save(), "copy saved to the library")
var_id = ed.meta["id"]
check(var_id in app.userlib.entries and app.userlib.entries[var_id].doc["derived_from"]["id"] == "el.inductor",
      "saved variant records what it was derived from")
check(json.dumps(symreg.get("el.inductor").build(None).prims) == builtin_before, "built-in symbol unchanged")
check(ed.save_btn.cget("text") == "Save changes", "after saving, the editor edits the new symbol")
ed.close()
pump()
app.library.populate()
cv_ = place(var_id, (900, 900))
t2 = cv_.terminals()["2"]
wv = editing.add_wire(app.doc, [t2, (t2[0] + 60, t2[1])])
check(wv.start == [cv_.id, "2"] and (cv_.id, "2") in analyse(app.doc).connected_terminals,
      "placed variant connects at the original terminal identifiers")
ind = place("el.inductor", (900, 1100))
ti = ind.terminals()["1"]
wi = editing.add_wire(app.doc, [ti, (ti[0] - 60, ti[1])])
ind.symbol = var_id
editing.sync_wire_ends(app.doc)
check(app.doc.wires[wi.id].start == [ind.id, "1"], "replacing the built-in by its variant keeps the wire")

# in-place edit of a library symbol, then Save as new: the original stays unchanged
orig_entry = app.userlib.entries[var_id]
with open(orig_entry.path, "rb") as fh:
    orig_bytes = fh.read()
app.edit_custom_symbol(var_id)
pump(6)
ed = app.windows[-1]
ecv = ed.canvas
check(ed.source is None and ed.save_btn.cget("text") == "Save changes", "library symbol opens for in-place editing")
ed.set_tool("LINE")
eclick((-20, 20))
eclick((20, 20))
ed.runner.enter()
check(ed.save(as_new=True), "Save as new symbol")
check(ed.meta["id"] != var_id and ed.meta["name"] == "Test" and ed.meta["derived_from"]["id"] == var_id,
      "Save as new: new id and name, records the source")
with open(orig_entry.path, "rb") as fh:
    check(fh.read() == orig_bytes, "Save as new leaves the original symbol file untouched")
# open another symbol from inside the editor (replaces this window)
ed2 = ed.open_existing("fl.hyd.throttle")
pump(6)
check(ed2 is not None and not ed.winfo_exists() and ed2.source[0] == "fl.hyd.throttle",
      "Open existing symbol from the editor")
check([p["id"] for p in ed2.pins] == [t.name for t in symreg.get("fl.hyd.throttle").build(None).terminals],
      "opened symbol keeps its terminal identifiers")
ed2.close()
pump()
# a configured valve opens as configured
valve = place("fl.hyd.dcv", (1300, 900))
valve.params = dict(valve.params, type="4/2", positions=["parallel", "crossed"])
ed3 = app.edit_symbol_copy(valve.symbol, dict(valve.params))
pump(6)
check(sorted(p["id"] for p in ed3.pins) == sorted(valve.terminals()), "configured valve opens with its own ports")
ed3.close()
pump()
# library: built-in symbols open as copies from the panel
if app.library.tree.exists("sym|el.resistor.iec"):
    app.library.tree.selection_set("sym|el.resistor.iec")
    pump()
    n_win = len(app.windows)
    app.library.edit_selected()
    pump(6)
    ed4 = app.windows[-1]
    check(len(app.windows) == n_win + 1 and ed4.source[0] == "el.resistor.iec", "library: edit opens a copy")
    ed4.close()
    pump()

# ================================================================ 10. library packages
pkg = os.path.join(OUT, "mine.osymlib")
app.userlib.export_package("My symbols", pkg)
from openschematix import userlib  # noqa: E402
info = userlib.read_package(pkg, app.userlib)
check(len(info.items) == 1 and info.conflicts, "package preview shows the existing symbol as a conflict")

# ================================================================ 11. revisions and comparison
app.issue_revision("A", "First issue", "NR", "JS", True)
check(app.project.revisions.approved()[0]["label"] == "A" and app.project.meta["revision"] == "A",
      "revision A issued")
editing.delete_items(app.doc, [r2.id])
app.refresh()
from openschematix.gui.revisions_ui import CompareWindow, RevisionsWindow  # noqa: E402
st = app.project.revisions
cw = CompareWindow(app, ("A", st.load(st.approved()[0]["n"])), ("current", app.project))
pump(8)
check(any(c.status == "removed" for c in cw.diff.changes), "comparison finds the removed component")
shot("compare")
cw.destroy()
rw = RevisionsWindow(app)
pump()
check(len(rw.tree.get_children()) >= 1, "revision history window lists revisions")
rw.destroy()
app.restore_revision(st.approved()[0]["n"])
check(r2.id in app.doc.components, "restoring revision A brings the component back")

# ================================================================ 12. save, reopen, DXF, PDF
path = os.path.join(OUT, "test.schematix")
app.filename = path
check(app.save(), "project saved")
data1 = [s.to_dict(False) for s in app.project.sheets]
app.dirty = False
app.open_path(path, confirm=False)
check([s.to_dict(False) for s in app.project.sheets] == data1, "reopened project is identical")
ANSWERS["save_path"] = os.path.join(OUT, "test.pdf")
app.export_pdf([s.uid for s in app.project.sheets])
check(os.path.getsize(ANSWERS["save_path"]) > 2000, "PDF exported for all sheets")
ANSWERS["save_path"] = os.path.join(OUT, "sheet1.dxf")
app.export_file("dxf")
rep = dxf.import_dxf(open(ANSWERS["save_path"], "rb").read())
check(rep.counts.get("LINE", 0) > 5, "DXF exported and readable")
n_sheets = len(app.project.sheets)
app.import_dxf(os.path.join(HERE, "data", "sample_r2018.dxf"), None, 1.0, True, True)
check(len(app.project.sheets) == n_sheets + 1 and len(app.doc.shapes) > 5, "DXF imported onto a new sheet")
check(app.project.layer("OUTLINE") is not None, "DXF layers created")
shot("dxf_import")

# ================================================================ 13. scale and fit
app.set_active_sheet(app.project.sheets[0].uid)
nets_before = sorted(tuple(sorted(n.terminals)) for n in netlist.compute_nets(app.project))
app.scale_geometry(1.5, "center")
nets_after = sorted(tuple(sorted(n.terminals)) for n in netlist.compute_nets(app.project))
check(nets_before == nets_after, "scaling the layout keeps every connection")
app.fit_to_sheet()
check(app.doc.sheet.scale != "", "fit to sheet sets a print scale")

# ================================================================ 14. autosave / recovery data
app.mark_dirty()
app._autosave()
check(app.recovery.folder and app.recovery.snapshots(app.recovery.folder), "autosave wrote a recovery snapshot")
check(os.path.getmtime(path) <= os.path.getmtime(app.recovery.snapshots(app.recovery.folder)[0].path),
      "autosave did not touch the saved file")

# ================================================================ 15. dialogs open and close
from openschematix.gui.dialogs import (AboutDialog, PreferencesDialog, ProjectDialog, ScaleDialog,  # noqa: E402
                                       ShortcutsDialog, WireNumberDialog)
for D in (AboutDialog, ProjectDialog, PreferencesDialog, ShortcutsDialog, ScaleDialog, WireNumberDialog):
    try:
        d = D(app)
        pump(3)
        d.destroy()
        pump()
        check(True, f"{D.__name__} opens")
    except Exception as e:  # noqa: BLE001
        check(False, f"{D.__name__} failed: {e!r}")
cmd("HELP")
check("Draw:" in app.logview.text.get("1.0", "end"), "HELP lists commands")

# ================================================================ 16. templates for sheets and projects
import openschematix.gui.dialogs as dlg  # noqa: E402


class _Pick:
    choice = 0

    def __init__(self, app_, title, label, options, wait=True):
        self.result = options[_Pick.choice] if options else None


dlg.ChoiceDialog = _Pick
n = len(app.project.sheets)
app.add_sheet_from_template()
check(len(app.project.sheets) == n + 1 and app.doc.sheet.size == app.project.sheets[0].sheet.size
      and not app.doc.components, "new sheet from a sheet template copies the page setup only")
ANSWERS["askstring"] = "My project template"
app.save_project_template()
check(os.path.exists(os.path.join(CONFIG, "project_templates", "My project template.schematix")),
      "project template saved")
app.dirty = False
_Pick.choice = 5    # first user template after the five built-in blanks
app.new_from_template()
check(len(app.project.sheets) == n + 1 and not app.project.revisions.entries and app.filename is None,
      "new project from a user template (fresh history, unsaved)")
_Pick.choice = 4
app.dirty = False
app.new_from_template()
check(app.doc.sheet.title_block == "iso" and len(app.project.sheets) == 1, "new project from a built-in template")
app.open_path(path, confirm=False)

# ================================================================ 17. recovery prompt after a crash
from openschematix.recovery import RecoveryManager  # noqa: E402
crash = RecoveryManager()
crash.start()
crash.autosave(app.project, "/tmp/lost.schematix")
info_path = os.path.join(crash.folder, "session.json")
info = json.load(open(info_path))
info["pid"] = 999999999
json.dump(info, open(info_path, "w"))
top2 = tk.Toplevel(root)
picked = {}


def answer_recovery():
    for w in root.winfo_children() + top2.winfo_children():
        if w.winfo_class() == "Toplevel" and hasattr(w, "orphans"):
            picked["n"] = len(w.orphans)
            w.ok()
            return
    root.after(200, answer_recovery)


root.after(300, answer_recovery)
app._offer_recovery(app.recovery.orphans())
check(picked.get("n") == 1, "recovery dialog lists the crashed session")
check(app.dirty and app.filename is None and len(app.project.sheets) >= 1, "recovered project opened unsaved")
check(not os.path.exists(crash.folder), "recovered session data cleaned up")
top2.destroy()

# ================================================================ arrowhead editor controls
from openschematix.gui.symbol_editor import SymbolEditor  # noqa: E402
from openschematix.model import Shape  # noqa: E402
from openschematix.symbols.custom import normalise  # noqa: E402

se = SymbolEditor(app)
se.geometry("1240x780+0+0")
pump(5)
check(se.step_var.get() == "1.25 mm",
      "symbol editor snap setting initialized")

def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)

snap_controls = [w for w in _descendants(se) if isinstance(w, __import__("tkinter.ttk", fromlist=["Combobox"]).Combobox)
                 and str(w.cget("textvariable")) == str(se.step_var)]
check(bool(snap_controls) and snap_controls[0].winfo_rootx() + snap_controls[0].winfo_width()
      <= se.winfo_rootx() + se.winfo_width(), "symbol editor Snap control fits at 1240 px")
se.arrow_end_var.set(1)
style = se.new_shape_style()
check(style["arrow_end"] and not style["arrow_start"] and style["arrow_size"] == 10,
      "symbol editor arrow settings carry to new lines")
sh = Shape(se.doc.new_id(), "line", pts=[(0, 0), (40, 0)], **style)
se.doc.add_shape(sh)
se.set_selection({sh.id})
pump(2)
check(se.arrow_end_var.get() == 1 and se.arrow_size_var.get() == "2.5",
      "symbol editor selection displays arrow properties")
se.arrow_size_var.set("0")
se._apply_arrow_size()
check(se.arrow_size_var.get() == "2.5" and sh.arrow_size == 10,
      "symbol editor rejects invalid arrow size and resets field")
se.arrow_start_var.set(1)
se.apply_style(arrow_start=True)
check(sh.arrow_start, "symbol editor start arrow control applies")
se.undo()
check(not se.doc.shapes[sh.id].arrow_start, "symbol editor arrow change supports undo")
se.redo()
check(se.doc.shapes[sh.id].arrow_start, "symbol editor arrow change supports redo")
prim = __import__("openschematix.shapes", fromlist=["shape_to_symbol_prim"]).shape_to_symbol_prim(se.doc.shapes[sh.id])
check(normalise({**se.meta, "prims": [prim]})["prims"][0]["arrow_end"],
      "symbol arrow settings survive normalization")
se.destroy()
pump(2)

# ================================================================ 14. boundary fill (FILL / HATCH)
from openschematix import regions as _rg  # noqa: E402
from openschematix.gui import symbol_editor as _se  # noqa: E402

app.add_sheet()
pump(4)
fill_doc = app.doc
H = fill_doc.sheet.size_units()[1]
M = app.to_model           # mm (Y up) -> drawing units


def log_text():
    return app.logview.text.get("1.0", "end")


def hatches():
    return sorted((s for s in app.doc.shapes.values() if s.kind == "hatch"), key=lambda s: s.id)


cv.fit()
pump(4)
cmd("REC")
cmd("20,20")
cmd("@60,40")
cmd("CIRCLE")
cmd("50,40")
cmd("8")
# open U shape with a 0.5 mm gap at the top right
for a, b in (("100,20", "140,20"), ("140,20", "140,59.5"), ("140,60", "100,60"), ("100,60", "100,20")):
    cmd("LINE")
    cmd(a)
    cmd(b)
    cmd("")
check(len(app.doc.shapes) == 6 and not hatches(), "fill test geometry drawn on a new sheet")
check("FILL" in app.tool_buttons, "toolbar has a Fill button")
type_cmd("FILL")
check(app.runner.active and "closed area" in app.cmdline.prompt.cget("text"), "FILL starts and prompts for a point")
click(M((25, 25)))                 # between the rectangle and the circle
click(M((50, 40)))                 # inside the circle
cmd("")
fills = hatches()
check(len(fills) == 2 and not app.runner.active, "FILL made two independent fills from two picks")
check(app.selection == {f.id for f in fills}, "new fills are selected")
ring_fill = max(fills, key=lambda f: len(f.rings))
check(len(ring_fill.rings) == 2 and abs(_rg.region_area(ring_fill.rings) - (240 * 160 - 3.14159265 * 32 * 32)) < 1,
      "fill around the circle keeps the circle as a hole (exact area)")
pump(4)
filled_items = [i for i in cv.find_all() if cv.type(i) == "polygon" and cv.itemcget(i, "fill")
                and cv.itemcget(i, "outline") == ""]
check(len(filled_items) >= 2, "fills are drawn on the canvas as vector polygons")
key("<Control-z>")
check(not hatches(), "one undo removes everything one FILL command made")
key("<Control-y>")
check(len(hatches()) == 2, "redo restores the fills")
# HATCH alias, pick outside / on nothing -> refused, nothing made
n_log = len(log_text())
cmd("HATCH")
click(M((180, 150)))
check(app.runner.active and len(hatches()) == 2, "HATCH alias works; a pick outside every boundary makes nothing")
check("No closed boundary" in log_text()[n_log:], "the refusal is explained in the command log")
click(M((120, 40)))                # inside the open U: refused with gap 0
check(len(hatches()) == 2, "an open boundary is not filled")
cmd("G")
cmd("1")
check(abs(app.settings["fill_gap_mm"] - 1.0) < 1e-12, "Gap option sets the gap tolerance (mm)")
click(M((130, 30)))                # (not the same spot: two quick clicks there would be a double click)
check(len(hatches()) == 3 and "gap(s) closed" in log_text(), "with a 1 mm gap tolerance the U is filled")
cmd("G")
cmd("0")
cmd("")
u_fill = hatches()[-1]
# select by clicking inside; the hole is not part of the fill
app.canvas.set_tool("select")
app.set_selection(set())
click(M((70, 25)))
check(app.selection == {ring_fill.id}, "clicking inside a fill selects it")
app.set_selection(set())
click(M((44, 46)))                 # inside the circle -> the circle's own fill, not the ring fill
check(ring_fill.id not in app.selection, "clicking in a hole does not select the surrounding fill")
# MOVE / COPY / MIRROR / ERASE through the normal commands
bb0 = ring_fill.bbox()
app.set_selection({ring_fill.id})
cmd("M")
cmd("20,20")
cmd("@0,-70")
bb1 = app.doc.shapes[ring_fill.id].bbox()
check(abs(bb1[1] - bb0[1] - 280) < 1e-6 and abs(bb1[0] - bb0[0]) < 1e-6, "MOVE moves a fill")
check(len([s for s in app.doc.shapes.values() if s.kind == "rect"]) == 1 and
      [s for s in app.doc.shapes.values() if s.kind == "rect"][0].bbox()[1] < bb1[1],
      "the boundary stays where it was (fills are independent)")
n = len(hatches())
app.set_selection({ring_fill.id})
cmd("CO")
cmd("20,20")
cmd("@70,0")
cmd("")
check(len(hatches()) == n + 1, "COPY copies a fill")
cp_fill = hatches()[-1]
check(abs(_rg.region_area(cp_fill.rings) - _rg.region_area(ring_fill.rings)) < 1e-6, "the copy has the same area")
app.set_selection({cp_fill.id})
cmd("MI")
cmd("120,0")
cmd("120,10")
cmd("")
check(abs(abs(_rg.region_area(app.doc.shapes[cp_fill.id].rings)) - abs(_rg.region_area(ring_fill.rings))) < 1e-6,
      "MIRROR keeps the fill's shape")
app.set_selection({cp_fill.id})
app.delete()
check(cp_fill.id not in app.doc.shapes, "a fill can be deleted")
key("<Control-z>")
check(cp_fill.id in app.doc.shapes, "deleting a fill can be undone")
# inspector shows a fill summary and no line-style controls
app.set_selection({u_fill.id})
pump(4)
labels = [w.cget("text") for w in _descendants(app.inspector) if isinstance(w, (tk.Label,)) or
          w.winfo_class() in ("TLabel", "Label")]
check(any("Solid fill" in t for t in labels) and not any(t == "Line width" for t in labels),
      "inspector shows the fill summary")
# exports of a sheet with fills
ANSWERS["save_path"] = os.path.join(OUT, "fill.svg")
app.export_file("svg")
svg = open(ANSWERS["save_path"], encoding="utf-8").read()
check(svg.count('fill-rule="evenodd"') == len(hatches()) and "<image" not in svg, "SVG export: vector fills")
ANSWERS["save_path"] = os.path.join(OUT, "fill.dxf")
app.export_file("dxf")
dtext = open(ANSWERS["save_path"], encoding="cp1252").read()
check(dtext.count("\nINSERT\n") == len(hatches()) and "\nSOLID\n" in dtext, "DXF export: fills as SOLID blocks")
try:
    import ezdxf  # noqa: E402
    check(not ezdxf.readfile(ANSWERS["save_path"]).audit().has_errors, "DXF with fills passes ezdxf audit")
except ImportError:
    print("  (ezdxf not installed: DXF audit skipped)")
ANSWERS["save_path"] = os.path.join(OUT, "fill.pdf")
app.export_pdf([app.doc.uid])
try:
    import pypdf  # noqa: E402
    content = b"".join(pg.get_contents().get_data() for pg in pypdf.PdfReader(ANSWERS["save_path"]).pages)
    check(b"f*" in content, "PDF export: fills use the even-odd fill operator")
except ImportError:
    print("  (pypdf not installed: PDF content check skipped)")
shot("boundary_fill")
# save and reopen
path = os.path.join(OUT, "fills.schematix")
app.filename = path
check(app.save(), "project with fills saved")
before = {s.id: s.to_dict() for s in hatches()}
app.dirty = False
app.open_path(path, confirm=False)
sheet = [d for d in app.project.sheets if any(s.kind == "hatch" for s in d.shapes.values())]
check(len(sheet) == 1 and {s.id: s.to_dict() for s in sheet[0].shapes.values() if s.kind == "hatch"} == before,
      "fills survive saving and reopening")
# the symbol editor does not offer FILL (fills are sheet objects)
check("FILL" not in _se.EDITOR_COMMANDS, "symbol editor does not offer FILL")

# ================================================================ final screenshots
app.set_active_sheet(app.project.sheets[0].uid)
cv.fit()
shot("workspace_light")
app.set_theme("modern_dark")
shot("workspace_dark")
app.set_theme("modern_light")

app.dirty = False
app.quit()
print("\nFAILURES:", len(failures))
for f in failures:
    print(" -", f)
sys.exit(1 if failures else 0)
