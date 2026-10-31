"""Autosave and crash recovery.

While the program runs it owns a *session folder*:

    <config>/recovery/<session id>/session.json     who/what/when (heartbeat)
    <config>/recovery/<session id>/snap-0003.schematix

Autosave writes snapshots of the open project into the session folder only;
it never touches the user's own file, so a manually saved file is never
replaced by recovery data. Snapshots are written atomically (temporary file,
fsync, rename) and the newest KEEP snapshots are kept.

On a clean exit the session folder is deleted. A session folder that still
exists when the program starts, and whose process is no longer running,
belongs to a session that ended unexpectedly: the user is offered its
snapshots. Abandoned sessions older than MAX_AGE_DAYS are removed
automatically.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass

from .settings import config_dir

KEEP = 3
MAX_AGE_DAYS = 14


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform.startswith("win"):
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        except Exception:  # noqa: BLE001
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@dataclass
class Snapshot:
    path: str
    time: float

    @property
    def when(self) -> str:
        return _dt.datetime.fromtimestamp(self.time).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class OrphanSession:
    folder: str
    source: str            # file the user was editing ("" = never saved)
    title: str
    started: str
    snapshots: list        # newest first

    @property
    def newest(self) -> Snapshot | None:
        return self.snapshots[0] if self.snapshots else None


class RecoveryManager:
    def __init__(self, root: str | None = None):
        self.root = root or os.path.join(config_dir(), "recovery")
        self.folder: str | None = None
        self.counter = 0
        self.last_key = None
        self.source = ""

    # ---------------------------------------------------------------- session
    def start(self):
        os.makedirs(self.root, exist_ok=True)
        sid = _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
        self.folder = os.path.join(self.root, sid)
        os.makedirs(self.folder, exist_ok=True)
        self._write_info(source="", title="")

    def _write_info(self, source: str, title: str):
        if not self.folder:
            return
        info = {"pid": os.getpid(), "started": os.path.basename(self.folder), "source": source, "title": title,
                "heartbeat": time.time()}
        tmp = os.path.join(self.folder, "session.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(info, f)
        os.replace(tmp, os.path.join(self.folder, "session.json"))

    def end(self):
        """Clean exit: discard this session's recovery data."""
        if self.folder and os.path.isdir(self.folder):
            shutil.rmtree(self.folder, ignore_errors=True)
        self.folder = None

    def discard_snapshots(self):
        """After a successful manual save the recovery data is obsolete."""
        if not self.folder:
            return
        for s in self.snapshots(self.folder):
            try:
                os.unlink(s.path)
            except OSError:
                pass
        self.last_key = None

    # ---------------------------------------------------------------- autosave
    def autosave(self, project, source: str | None = None) -> str | None:
        """Write a snapshot if the project changed since the last one.
        `source` is the user's file path (remembered between calls)."""
        if source is not None:
            self.source = source
        source = self.source
        from .projectio import atomic_write_bytes, project_bytes
        from .revisions import RevisionStore
        if not self.folder:
            self.start()
        key = RevisionStore().content_key(project)
        if key == self.last_key:
            self._write_info(source, project.meta.get("title", ""))
            return None
        data = project_bytes(project)
        self.counter += 1
        path = os.path.join(self.folder, f"snap-{self.counter:04d}.schematix")
        atomic_write_bytes(path, data)
        self.last_key = key
        self._write_info(source, project.meta.get("title", ""))
        for old in self.snapshots(self.folder)[KEEP:]:
            try:
                os.unlink(old.path)
            except OSError:
                pass
        return path

    @staticmethod
    def snapshots(folder: str) -> list[Snapshot]:
        out = []
        try:
            names = os.listdir(folder)
        except OSError:
            return out
        for n in names:
            if n.startswith("snap-") and n.endswith(".schematix"):
                p = os.path.join(folder, n)
                try:
                    out.append(Snapshot(p, os.path.getmtime(p)))
                except OSError:
                    pass
        out.sort(key=lambda s: (s.time, s.path), reverse=True)
        return out

    # ---------------------------------------------------------------- recovery
    def orphans(self) -> list[OrphanSession]:
        out = []
        if not os.path.isdir(self.root):
            return out
        for n in sorted(os.listdir(self.root)):
            folder = os.path.join(self.root, n)
            if not os.path.isdir(folder) or folder == self.folder:
                continue
            try:
                with open(os.path.join(folder, "session.json"), encoding="utf-8") as f:
                    info = json.load(f)
            except (OSError, ValueError):
                info = {}
            if _pid_alive(int(info.get("pid", 0) or 0)) and time.time() - float(info.get("heartbeat", 0)) < 3600:
                continue  # another running instance owns it
            snaps = self.snapshots(folder)
            if not snaps:
                shutil.rmtree(folder, ignore_errors=True)
                continue
            out.append(OrphanSession(folder, str(info.get("source", "")), str(info.get("title", "")),
                                     str(info.get("started", n)), snaps))
        return out

    def cleanup(self, max_age_days: float = MAX_AGE_DAYS) -> int:
        """Delete abandoned sessions older than max_age_days."""
        n = 0
        limit = time.time() - max_age_days * 86400
        for o in self.orphans():
            newest = o.newest.time if o.newest else 0
            if newest < limit:
                shutil.rmtree(o.folder, ignore_errors=True)
                n += 1
        return n

    @staticmethod
    def discard(orphan: OrphanSession):
        shutil.rmtree(orphan.folder, ignore_errors=True)
