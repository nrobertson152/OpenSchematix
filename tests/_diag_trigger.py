"""DIAGNOSTIC ONLY: which action makes Windows lay out the withdrawn test window?"""
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", tempfile.mkdtemp())
import tkinter as tk
from openschematix import editing
from openschematix.gui.app import App
from openschematix.project import new_project

root = tk.Tk(); root.geometry("1200x800"); root.withdraw()
app = App(root, check_recovery=False)
cv = app.canvas
T0 = time.perf_counter()


def log(tag):
    root.update_idletasks(); root.update()
    print(f"{time.perf_counter() - T0:5.2f}s {tag:38s} canvas={cv.winfo_width()}x{cv.winfo_height()} "
          f"root={root.winfo_width()}x{root.winfo_height()} geom={root.geometry()} state={root.wm_state()} "
          f"mapped={cv.winfo_ismapped()} restored={getattr(app, 'layout_restored', '?')}", flush=True)


log("after App()")
while not app.layout_restored:
    root.update(); time.sleep(0.01)
log("layout_restored")
p = new_project("x"); app._reset(p, None); log("_reset")
editing.place(app.doc, "el.resistor.iec", 200, 200); app.canvas.redraw(); log("place + redraw")
cv.center_on((330, 200), zoom=2.0); log("center_on")
cv._on_motion(type("E", (), {"x": 100, "y": 100, "state": 0})()); log("motion (status coords)")
app.set_status("hello"); log("set_status")
app.update_title(); log("update_title")
app.dirty = True; app.update_title(); log("dirty title")
app.undo_stack.append("x"); app.refresh(); log("refresh with undo enabled")
app.undo_stack.clear()
s = app.begin_change(); editing.place(app.doc, "el.resistor.iec", 300, 200); app.commit_change(s, "placed"); log("commit_change")
for i in range(5):
    time.sleep(0.2); log(f"idle {i}")
