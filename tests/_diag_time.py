"""DIAGNOSTIC ONLY: is the late pane layout time-driven or action-driven? argv[1] = idle | reset"""
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("OPENSCHEMATIX_CONFIG_DIR", tempfile.mkdtemp())
import tkinter as tk
from openschematix.gui.app import App
from openschematix.project import new_project
root = tk.Tk(); root.geometry("1200x800"); root.withdraw()
app = App(root, check_recovery=False); cv = app.canvas; T0 = time.perf_counter(); last = None
if sys.argv[1] == "reset":
    app._reset(new_project("x"), None)
while time.perf_counter() - T0 < 5:
    root.update()
    cur = (root.winfo_width(), root.winfo_height(), app.hpane.winfo_width(), app.vpane.winfo_height(),
           cv.winfo_width(), cv.winfo_height(), app.layout_restored)
    if cur != last:
        print(f"{sys.argv[1]:5s} {time.perf_counter() - T0:5.2f}s root={cur[0]}x{cur[1]} hpane={cur[2]} vpane={cur[3]} "
              f"canvas={cur[4]}x{cur[5]} restored={cur[6]}", flush=True)
        last = cur
    time.sleep(0.02)
