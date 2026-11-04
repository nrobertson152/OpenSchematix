"""Temporary PDF files written for Print (#82).

*Print* writes the sheet to a PDF and opens it in the user's PDF viewer, so
the file cannot be deleted right away: the viewer starts asynchronously and
then reads it, and on Windows a file that is open in another program cannot
be deleted at all. The files go into a folder of their own in the system
temporary folder:

* when the program closes, this session's files are deleted, except ones
  printed in the last KEEP_AT_EXIT_MINUTES (a viewer may still be starting)
  and ones still open in a viewer; those are left for a later start;
* when the program starts, files older than MAX_AGE_HOURS are deleted. A
  younger file may belong to another running OpenSchematix and still be on
  screen, so it is left alone.

The folder is private to the user: on Linux (a shared /tmp) its name carries
the user id and it is created with mode 0700. It is used only if it is a real
directory, not a link or junction, owned by the user and not writable by
others; otherwise this session prints into a new private folder
(tempfile.mkdtemp) and the startup clean-up leaves the untrusted one alone;
it does clean such private folders of earlier sessions by the same age rule
and removes them once empty.
Clean-up never follows links. Files that releases before 1.2.0 left directly
in the temporary folder (openschematix-XXXXXXXX.pdf) are tidied up by the
same age rule, only if they belong to the user.
Standard library only; never raises for a file that cannot be removed.
"""
from __future__ import annotations

import os
import re
import stat
import tempfile
import time

MAX_AGE_HOURS = 24
KEEP_AT_EXIT_MINUTES = 10
FOLDER_NAME = "openschematix-print"
# mkstemp(prefix="openschematix-", suffix=".pdf") as used up to 1.1.x: 8 random characters
_LEGACY = re.compile(r"^openschematix-[A-Za-z0-9_]{8}\.pdf$")
_OURS = re.compile(r"^print-.*\.pdf$")
# private fallback folders: tempfile.mkdtemp(prefix=FOLDER_NAME + "-") adds 8 random characters
_FALLBACK = re.compile(r"^openschematix-print-[a-z0-9_]{8}$")
_REPARSE_POINT = 0x400        # FILE_ATTRIBUTE_REPARSE_POINT (Windows links and junctions)


def _uid():
    return os.getuid() if hasattr(os, "getuid") else None


def folder(base: str | None = None) -> str:
    """The user's print folder (it may not exist yet)."""
    uid = _uid()
    name = FOLDER_NAME if uid is None else f"{FOLDER_NAME}-{uid}"
    return os.path.join(base or tempfile.gettempdir(), name)


def _is_link(st) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT)


def _ours(st) -> bool:
    uid = _uid()
    return uid is None or st.st_uid == uid


def trusted_dir(path: str) -> bool:
    """True if `path` is a real directory (not a link or junction) that only this user can change."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if _is_link(st) or not stat.S_ISDIR(st.st_mode) or not _ours(st):
        return False
    return _uid() is None or not (st.st_mode & 0o022)


class PrintFiles:
    """The print PDFs of one program session."""

    def __init__(self, base: str | None = None):
        self.base = base                 # temporary folder; None = the system's (tests pass their own)
        self.paths: list[tuple[str, float]] = []      # (path, created)
        self._private: str | None = None              # fallback folder of this session

    def _dir(self) -> str:
        if self._private:
            return self._private
        d = folder(self.base)
        try:
            os.mkdir(d, 0o700)
        except FileExistsError:
            pass
        except OSError:
            pass
        if trusted_dir(d):
            return d
        # someone else's folder, a link, or not creatable: never write there
        self._private = tempfile.mkdtemp(prefix=f"{FOLDER_NAME}-", dir=self.base)
        return self._private

    def new_path(self) -> str:
        """Create an empty, uniquely named PDF file for printing and return its path."""
        fd, path = tempfile.mkstemp(prefix=f"print-{os.getpid()}-", suffix=".pdf", dir=self._dir())
        os.close(fd)
        self.paths.append((path, time.time()))
        return path

    def discard(self, path: str) -> None:
        """Delete a file that was never shown (e.g. writing it failed)."""
        _remove(path)
        self.paths = [(p, t) for p, t in self.paths if p != path]

    def cleanup(self, now: float | None = None, keep_minutes: float = KEEP_AT_EXIT_MINUTES) -> list[str]:
        """At exit: delete this session's files except recent ones and ones still open.
        Returns the files left for a later start's clean-up."""
        now = time.time() if now is None else now
        left = []
        for path, created in self.paths:
            if now - created < keep_minutes * 60 or not _remove(path):
                left.append((path, created))
        self.paths = left
        if not left:
            for d in {folder(self.base), self._private} - {None}:
                try:
                    os.rmdir(d)        # only if empty: other sessions may use it
                except OSError:
                    pass
        return [p for p, _t in left]


def cleanup_stale(base: str | None = None, max_age_hours: float = MAX_AGE_HOURS, now: float | None = None) -> int:
    """Delete the user's print PDFs older than `max_age_hours`: in the print folder, in private fallback
    folders of earlier sessions (removed once empty), and the legacy ones. Returns how many files."""
    now = time.time() if now is None else now
    limit = now - max_age_hours * 3600
    tmp = base or tempfile.gettempdir()
    removed = 0
    folders = [folder(base)]
    try:
        folders += [e.path for e in os.scandir(tmp) if _FALLBACK.match(e.name) and e.path != folder(base)]
    except OSError:
        pass
    for d in folders:
        if not trusted_dir(d):          # a link, or someone else's: never look inside
            continue
        removed += _remove_old(d, _OURS, limit)
        if d != folder(base):
            try:
                os.rmdir(d)             # a fallback folder: only once empty
            except OSError:
                pass
    removed += _remove_old(tmp, _LEGACY, limit)
    return removed


def _remove_old(d: str, pattern, limit: float) -> int:
    """Delete regular files in `d` named like `pattern`, owned by the user, last changed before `limit`."""
    removed = 0
    try:
        entries = list(os.scandir(d))
    except OSError:
        return 0
    for e in entries:
        if not pattern.match(e.name):
            continue
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        if _is_link(st) or not stat.S_ISREG(st.st_mode) or not _ours(st) or st.st_mtime > limit:
            continue
        removed += _remove(e.path)
    return removed


def _remove(path: str) -> bool:
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False
