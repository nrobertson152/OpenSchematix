"""Temporary PDF files written for Print (#82).

*Print* writes the sheet to a PDF and opens it in the user's PDF viewer, so
the file cannot be deleted right away: the viewer is still reading it, and
on Windows a file that is open in another program cannot be deleted at all.
The files go into one folder of their own in the system temporary folder:

* when the program closes, this session's files are deleted (any still open
  in a viewer are skipped and left for later);
* when the program starts, files older than MAX_AGE_HOURS are deleted. A
  younger file may belong to another running OpenSchematix and still be on
  screen, so it is left alone.

Files that releases before 1.2.0 left directly in the temporary folder
(openschematix-XXXXXXXX.pdf) are tidied up by the same age rule.
Standard library only; never raises for a file that cannot be removed.
"""
from __future__ import annotations

import os
import re
import tempfile
import time

MAX_AGE_HOURS = 24
FOLDER_NAME = "openschematix-print"
# mkstemp(prefix="openschematix-", suffix=".pdf") as used up to 1.1.x: 8 random characters
_LEGACY = re.compile(r"^openschematix-[A-Za-z0-9_]{8}\.pdf$")
_OURS = re.compile(r"^print-.*\.pdf$")


def folder(base: str | None = None) -> str:
    return os.path.join(base or tempfile.gettempdir(), FOLDER_NAME)


class PrintFiles:
    """The print PDFs of one program session."""

    def __init__(self, base: str | None = None):
        self.base = base                 # temporary folder; None = the system's (tests pass their own)
        self.paths: list[str] = []

    def new_path(self) -> str:
        """Create an empty, uniquely named PDF file for printing and return its path."""
        d = folder(self.base)
        os.makedirs(d, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix=f"print-{os.getpid()}-", suffix=".pdf", dir=d)
        os.close(fd)
        self.paths.append(path)
        return path

    def discard(self, path: str) -> None:
        """Delete a file that was never shown (e.g. writing it failed)."""
        _remove(path)
        if path in self.paths:
            self.paths.remove(path)

    def cleanup(self) -> list[str]:
        """Delete this session's files; returns those that could not be deleted (still open)."""
        left = [p for p in self.paths if not _remove(p)]
        self.paths = left
        if not left:
            try:
                os.rmdir(folder(self.base))        # only if empty: other sessions may use it
            except OSError:
                pass
        return left


def cleanup_stale(base: str | None = None, max_age_hours: float = MAX_AGE_HOURS, now: float | None = None) -> int:
    """Delete print PDFs older than `max_age_hours` (ours and the legacy ones). Returns how many."""
    now = time.time() if now is None else now
    limit = now - max_age_hours * 3600
    tmp = base or tempfile.gettempdir()
    removed = 0
    for d, pattern in ((folder(base), _OURS), (tmp, _LEGACY)):
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if not pattern.match(name):
                continue
            path = os.path.join(d, name)
            try:
                if not os.path.isfile(path) or os.path.islink(path) or os.path.getmtime(path) > limit:
                    continue
            except OSError:
                continue
            removed += _remove(path)
    return removed


def _remove(path: str) -> bool:
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False
