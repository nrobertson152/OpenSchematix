"""Acceptance check for a packaged (PyInstaller / AppImage) OpenSchematix build.

`--version` returns before Tk is created, so it cannot catch a bundle that is
missing Tcl/Tk data, resources or hidden imports. This script starts the real
application on a copy of examples/demo_project.schematix, waits for the main
window to show that project, and then:

  * Linux (X11, e.g. under xvfb-run): presses Ctrl+S through XTest, checks
    that the file was rewritten and still loads with the same content;
  * Windows: no synthetic input (focus on hosted runners is unreliable);
    the open project is verified through the window title.

Finally it closes the main window the way a window manager does and requires
exit code 0. Uses only the standard library (ctypes); run from the repository
root with a Python that can import the source tree.

    python packaging/ci/packaged_smoke.py <command> [args...]
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

WINDOWS = sys.platform.startswith("win")
NAME = "acceptance.schematix"


def fail(msg, proc=None):
    print(f"FAIL: {msg}")
    if proc is not None:
        try:
            print("windows:", titles())
        except Exception as e:  # noqa: BLE001
            print("windows: <unavailable>", e)
        if proc.poll() is None:
            proc.kill()
        out, _ = proc.communicate(timeout=30)
        print("--- application output ---")
        print(out or "<none>")
    sys.exit(1)


# ---------------------------------------------------------------- Windows (user32)
if WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _windows():
        found = []

        def cb(hwnd, _l):
            n = user32.GetWindowTextLengthW(hwnd)
            if n and user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                found.append((hwnd, buf.value))
            return True

        user32.EnumWindows(WNDENUMPROC(cb), 0)
        return found

    def close_window(w):
        user32.PostMessageW(w, 0x0010, 0, 0)      # WM_CLOSE

# ---------------------------------------------------------------- X11 (libX11 + XTest)
else:
    x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
    xtst = ctypes.cdll.LoadLibrary("libXtst.so.6")
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                               ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                               ctypes.POINTER(ctypes.c_uint)]
    x11.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XStringToKeysym.restype = ctypes.c_ulong
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x11.XKeysymToKeycode.restype = ctypes.c_ubyte
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

    class _ClientMessage(ctypes.Structure):
        _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                    ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                    ("format", ctypes.c_int), ("l", ctypes.c_long * 5)]

    class _Event(ctypes.Union):
        _fields_ = [("xclient", _ClientMessage), ("pad", ctypes.c_long * 24)]

    x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long,
                               ctypes.POINTER(_Event)]
    DPY = x11.XOpenDisplay(None)
    if not DPY:
        print("FAIL: no X display (run under xvfb-run)")
        sys.exit(1)

    def _tree(w, depth, out):
        root, parent = ctypes.c_ulong(), ctypes.c_ulong()
        kids, n = ctypes.POINTER(ctypes.c_ulong)(), ctypes.c_uint()
        if not x11.XQueryTree(DPY, w, ctypes.byref(root), ctypes.byref(parent), ctypes.byref(kids),
                              ctypes.byref(n)):
            return out
        for i in range(n.value):
            name = ctypes.c_char_p()
            if x11.XFetchName(DPY, kids[i], ctypes.byref(name)) and name.value:
                out.append((kids[i], name.value.decode("utf-8", "replace")))
            if depth < 2:
                _tree(kids[i], depth + 1, out)
        return out

    def _windows():
        return _tree(x11.XDefaultRootWindow(DPY), 0, [])

    def press_ctrl_s(w):
        x11.XSetInputFocus(DPY, w, 1, 0)          # RevertToPointerRoot, CurrentTime
        x11.XSync(DPY, 0)
        time.sleep(0.5)
        ctrl = x11.XKeysymToKeycode(DPY, x11.XStringToKeysym(b"Control_L"))
        s = x11.XKeysymToKeycode(DPY, x11.XStringToKeysym(b"s"))
        for code, down in ((ctrl, 1), (s, 1), (s, 0), (ctrl, 0)):
            xtst.XTestFakeKeyEvent(DPY, code, down, 0)
        x11.XSync(DPY, 0)

    def close_window(w):
        ev = _Event()
        ev.xclient.type = 33                      # ClientMessage, as sent by a window manager
        ev.xclient.window = w
        ev.xclient.message_type = x11.XInternAtom(DPY, b"WM_PROTOCOLS", 0)
        ev.xclient.format = 32
        ev.xclient.l[0] = x11.XInternAtom(DPY, b"WM_DELETE_WINDOW", 0)
        x11.XSendEvent(DPY, w, 0, 0, ctypes.byref(ev))
        x11.XSync(DPY, 0)


def titles():
    return [t for _w, t in _windows()]


def wait_window(proc, text, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if proc.poll() is not None:
            fail(f"the application exited with code {proc.returncode} before showing {text!r}", proc)
        for w, t in _windows():
            if text in t:
                return w, t
        time.sleep(0.5)
    fail(f"no window titled with {text!r} after {timeout} s", proc)


def summary(path):
    from openschematix import projectio
    p = projectio.open_any(path, activate=False).project
    return [(s.name, sorted(c.symbol for c in s.components.values()), len(s.wires)) for s in p.sheets]


def main(cmd):
    work = tempfile.mkdtemp(prefix="osx-packaged-")
    try:
        path = os.path.join(work, NAME)
        shutil.copyfile(os.path.join(ROOT, "examples", "demo_project.schematix"), path)
        before = summary(path)
        env = dict(os.environ, OPENSCHEMATIX_CONFIG_DIR=os.path.join(work, "config"))
        print("command:", cmd + [path])
        proc = subprocess.Popen(cmd + [path], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace")
        w, title = wait_window(proc, NAME, 90)
        print(f"ok: main window shows the project: {title!r}")

        if not WINDOWS:
            time.sleep(2.5)                       # past the start-up splash
            stamp = os.stat(path).st_mtime_ns
            os.utime(path, ns=(stamp - 10**9, stamp - 10**9))
            stamp = os.stat(path).st_mtime_ns
            press_ctrl_s(w)
            end = time.monotonic() + 30
            while os.stat(path).st_mtime_ns == stamp and time.monotonic() < end:
                time.sleep(0.3)
            if os.stat(path).st_mtime_ns == stamp:
                fail("Ctrl+S did not rewrite the project file", proc)
            time.sleep(1.0)
            after = summary(path)
            if after != before:
                fail(f"saved project differs: {before} -> {after}", proc)
            print(f"ok: Ctrl+S saved the project; it reloads unchanged ({len(after)} sheet(s))")
        else:
            print("note: save is not exercised on Windows (no reliable synthetic input on hosted runners)")

        close_window(w)
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            fail("the application did not exit after its window was closed", proc)
        out, _ = proc.communicate()
        if proc.returncode != 0:
            print(out)
            fail(f"exit code {proc.returncode} after closing")
        print("ok: closed cleanly (exit code 0)")
        if "Traceback" in (out or ""):
            print(out)
            fail("the application printed a traceback")
        print("PACKAGED SMOKE: PASS")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
