"""Reporting unexpected errors in the GUI.

Tk calls ``report_callback_exception`` for any exception escaping an event
handler, ``after`` callback or menu command. Its default prints the
traceback to ``sys.stderr``. The packaged Windows application is built
without a console (``console=False``), where ``sys.stderr`` is None, so the
traceback went nowhere: the action silently did nothing and nobody could
find out why.

``install(root)`` replaces that default. Each unexpected error is written,
with its traceback, to a log file in the configuration folder, printed to the
console if there is one, and shown in an error dialog that names the error
type and the log file. The dialog never shows the exception message or the
traceback, since those can contain text from the user's files; the log stays
on the user's computer. Dialogs are rate-limited so an error that repeats on
every redraw cannot flood the screen.
"""
from __future__ import annotations

import datetime as _dt
import os
import platform
import sys
import time
import traceback

LOG_NAME = "openschematix-errors.log"
MAX_LOG_BYTES = 1024 * 1024      # rotated to <name>.1 beyond this
REPEAT_SECONDS = 30.0            # the same error is shown at most once per this period


def log_path() -> str:
    from ..settings import config_dir
    return os.path.join(config_dir(), "logs", LOG_NAME)


def write_log(exc_type, exc, tb, context: str = "") -> str | None:
    """Append the error with its traceback to the error log. Returns the log
    path, or None if it could not be written. Never raises."""
    try:
        from .. import VERSION
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            if os.path.getsize(path) > MAX_LOG_BYTES:
                os.replace(path, path + ".1")
        except OSError:
            pass
        stamp = _dt.datetime.now().isoformat(timespec="seconds")
        head = (f"==== {stamp}  OpenSchematix {VERSION}  Python {platform.python_version()}  "
                f"{platform.system()} {platform.release()}" + (f"  [{context}]" if context else "") + "\n")
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(head + "".join(traceback.format_exception(exc_type, exc, tb)) + "\n")
        return path
    except Exception:  # noqa: BLE001 - logging must never cause a second error
        return None


def _print_console(exc_type, exc, tb) -> None:
    stream = sys.stderr
    if stream is None:             # windowed build: no console
        return
    try:
        traceback.print_exception(exc_type, exc, tb, file=stream)
    except Exception:  # noqa: BLE001
        pass


class ErrorReporter:
    """Shows unexpected errors to the user; see the module docstring."""

    def __init__(self, root=None, showerror=None):
        self.root = root
        self._showerror = showerror
        self._showing = False
        self._last_shown: dict[tuple, float] = {}
        self.reported = 0              # errors handled (for tests and diagnostics)

    def showerror(self, title, message):
        if self._showerror is not None:
            return self._showerror(title, message)
        from tkinter import messagebox
        return messagebox.showerror(title, message, parent=self.root)

    @staticmethod
    def message(exc_type, log: str | None) -> str:
        where = (f"Details were saved to:\n{log}" if log else
                 "The details could not be saved to the error log.")
        return ("OpenSchematix ran into an unexpected problem and could not complete the last action "
                f"({exc_type.__name__}).\n\nYour drawing is still open. Save it under a new name to be safe, "
                f"and please report the problem with the error log attached.\n\n{where}")

    def report(self, exc_type, exc, tb, context: str = "") -> None:
        self.reported += 1
        log = write_log(exc_type, exc, tb, context)
        _print_console(exc_type, exc, tb)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            return
        frames = traceback.extract_tb(tb) if tb is not None else []
        key = (exc_type.__name__, (frames[-1].filename, frames[-1].lineno) if frames else None)
        now = time.monotonic()
        if self._showing or now - self._last_shown.get(key, -REPEAT_SECONDS) < REPEAT_SECONDS:
            return                     # logged; a dialog for it is open or was shown just now
        self._last_shown[key] = now
        self._showing = True
        try:
            self.showerror("Unexpected error", self.message(exc_type, log))
        except Exception:  # noqa: BLE001 - e.g. Tk already destroyed; the log has it
            pass
        finally:
            self._showing = False

    # Tk's signature: report_callback_exception(exc_type, exc, tb)
    def __call__(self, exc_type, exc, tb):
        self.report(exc_type, exc, tb, "event handler")


def install(root) -> ErrorReporter:
    """Report unexpected errors of `root`'s event handlers (all of its
    windows) and of the main thread outside Tk."""
    reporter = ErrorReporter(root)
    root.report_callback_exception = reporter
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return previous(exc_type, exc, tb)
        reporter.report(exc_type, exc, tb, "uncaught")
    sys.excepthook = hook
    return reporter


def report_startup_failure(exc_type, exc, tb) -> str | None:
    """An error while the main window was being created: log it and show a
    dialog with its own temporary Tk root, as the application cannot."""
    log = write_log(exc_type, exc, tb, "start-up")
    _print_console(exc_type, exc, tb)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror("OpenSchematix could not start", ErrorReporter.message(exc_type, log), parent=root)
        finally:
            root.destroy()
    except Exception:  # noqa: BLE001 - no display at all: the log and exit status remain
        pass
    return log
