"""DIAGNOSTIC ONLY (temporary branch): when does App._restore_layout run, and what does it do to the canvas?"""
import time
T0 = [None]; CUR = ["?"]


def pytest_runtest_setup(item):
    CUR[0] = item.nodeid.split("::")[-1][:70]


def pytest_configure(config):
    from openschematix.gui import app as A
    real_init, real_restore = A.App.__init__, A.App._restore_layout

    def init(self, *a, **k):
        T0[0] = time.perf_counter()
        real_init(self, *a, **k)
        print(f"\n[diag] App created during {CUR[0]} geometry={self.root.geometry()}")

    def restore(self, attempts=0):
        self.root.update_idletasks()
        before = (self.hpane.winfo_width(), self.vpane.winfo_height(), self.canvas.winfo_height(),
                  self.canvas.winfo_ismapped())
        r = real_restore(self, attempts)
        self.root.update_idletasks()
        print(f"[diag] _restore_layout attempt={attempts} t={time.perf_counter() - T0[0]:.2f}s test={CUR[0]} "
              f"hpane,vpane,canvas_h,mapped before={before} canvas_h after={self.canvas.winfo_height()} "
              f"redraw_pending={self.canvas._redraw_pending}")
        return r
    A.App.__init__, A.App._restore_layout = init, restore
