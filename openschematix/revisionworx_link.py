"""RevisionWorx, the revision control program of OpenSchematix's family: whether the open project is a controlled document, checking it out
and in, and its bill of materials as a BOM document beside it, which is how a schematic's parts reach OpenMeridian.

Only RevisionWorx's command line is used, and nothing here reads or writes a workspace: `revisionworx link` (its interface for other
programs, docs/INTEGRATION.md there) for a file's status, checking in and the projects, and `revisionworx --json doc checkout|cancel` for
checking out and undoing it, which `link` doesn't have (FluidWorx and DraftWorx do the same). RevisionWorx's own rules and locks apply as
they would by hand. Without RevisionWorx none of this shows, and OpenSchematix behaves as before.

No Tk here: the window's part is in gui/app.py.
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

API_VERSION = 1
TIMEOUT = 120.0         # RevisionWorx waits up to 90 s for another program's change to finish before it says it's busy
ENV_VAR = "REVISIONWORX_CLI"
_NO_WINDOW = {"creationflags": 0x08000000} if sys.platform.startswith("win") else {}     # no console flashing up


class RevisionWorxError(Exception):
    """RevisionWorx refused, or couldn't be asked. The message is written for the person; `kind` is RevisionWorx's (`not-found`,
    `checked-out`, `busy`, `no-workspace`, `bad-input`, `error`), or `unavailable` when it isn't installed."""

    def __init__(self, message: str, kind: str = "error"):
        super().__init__(message)
        self.kind = kind


def _standalone() -> list:
    names = ("revisionworx.exe",) if sys.platform.startswith("win") else ("revisionworx",)
    roots = []
    if sys.platform.startswith("win"):
        roots += [Path(os.environ[v]) for v in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)") if os.environ.get(v)]
        roots.append(Path.home() / "Downloads")
    else:
        roots += [Path.home() / "Applications", Path.home() / ".local" / "opt", Path("/opt"), Path.home()]
    out = []
    for root in roots:
        try:
            for folder in sorted(root.glob("RevisionWorx*"), reverse=True):
                out += [folder / n for n in names if (folder / n).is_file()]
        except OSError:
            continue
    return out


def find_revisionworx() -> list | None:
    """The command that runs RevisionWorx, as its reference client finds it: REVISIONWORX_CLI, `revisionworx` on the PATH, the standalone
    build where it installs, then the installed Python package (not from a packaged OpenSchematix). None if it isn't there."""
    given = os.environ.get(ENV_VAR, "")
    if given:
        return [given]
    found = shutil.which("revisionworx")
    if found:
        return [found]
    for exe in _standalone():
        return [str(exe)]
    if not getattr(sys, "frozen", False):
        try:
            if importlib.util.find_spec("revisionworx") is not None:
                return [sys.executable, "-m", "revisionworx"]
        except (ImportError, ValueError):
            pass
    return None


def child_environment(environ=None, frozen=None) -> dict:
    """Environment for RevisionWorx: ours, without what a packaged OpenSchematix sets for its own libraries."""
    env = dict(os.environ if environ is None else environ)
    if getattr(sys, "frozen", False) if frozen is None else frozen:
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        for key in ("TCL_LIBRARY", "TK_LIBRARY", "TKPATH"):
            env.pop(key, None)
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is not None:
            env["LD_LIBRARY_PATH"] = original
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


@dataclass(frozen=True)
class Status:
    """What RevisionWorx says about one file."""
    controlled: bool
    path: str = ""
    workspace: str = ""             # the workspace's folder
    doc_id: str = ""
    number: str = ""
    title: str = ""
    project_id: str = ""
    project: str = ""               # its number, or its name
    revision: str = ""              # the latest revision's label
    state: str = ""                 # and its lifecycle state, as RevisionWorx names it
    released: str = ""
    file_state: str = "unmanaged"   # unchanged, modified, modified-externally, missing, unrevisioned or unmanaged
    checked_out_by: str = ""        # "alex on SHOP-PC", or ""
    mine: bool = False              # checked out to this computer's session

    @classmethod
    def of(cls, answer: dict) -> "Status":
        file = answer.get("file") or {}
        if not answer.get("controlled"):
            return cls(False, str(file.get("path", "")))
        doc = answer.get("document") or {}
        latest = doc.get("latest") or {}
        released = doc.get("released") or {}
        project = doc.get("project") or {}
        co = doc.get("checkout")
        who = f"{co.get('user') or '?'} on {co.get('host') or '?'}" if co else ""
        return cls(True, str(file.get("path", "")), str((answer.get("workspace") or {}).get("location", "")), str(doc.get("id", "")),
                   str(doc.get("number") or ""), str(doc.get("title") or ""), str(project.get("id") or ""),
                   str(project.get("number") or project.get("name") or ""), str(latest.get("label") or ""), str(latest.get("state_name") or ""),
                   str(released.get("label") or ""), str(file.get("state") or ""), who, bool(co and co.get("mine")))

    @property
    def name(self) -> str:
        return self.number or self.title or "This project"

    @property
    def theirs(self) -> bool:
        """Checked out by someone else: their working file, which nobody else should write."""
        return bool(self.checked_out_by) and not self.mine

    @property
    def changed(self) -> bool:
        return self.file_state in ("modified", "modified-externally", "unrevisioned")

    def headline(self) -> tuple:
        """(title, what to do, tone), as RevisionWorx's own document panel says it. Tone: ok, info, warn, danger or neutral."""
        if not self.controlled:
            return ("", "", "neutral")
        if self.file_state == "missing":
            return ("File missing", "The file isn't where RevisionWorx expects it.", "danger")
        if self.theirs:
            return (f"Checked out by {self.checked_out_by}", "Read-only for you until they check it in. Save a copy to keep your changes.",
                    "warn")
        if self.file_state == "modified-externally":
            return ("Changed without a check-out", "Check it in to keep the changes as a new revision.", "warn")
        if self.mine:
            if self.file_state == "modified":
                return ("Checked out by you · changed", "Check it in to keep your changes as a new revision.", "info")
            return ("Checked out by you", "Change it, save it, then check it in.", "info")
        if self.file_state == "unrevisioned":
            return ("No revision yet", "Check it in to make its first revision.", "neutral")
        return ("Available", "Check it out before you change it.", "ok")

    def primary(self, unsaved: bool = False) -> str:
        """The one next step: "check-in", "check-out", or "" when there's none."""
        if not self.controlled or self.theirs or self.file_state == "missing":
            return ""
        if self.mine or self.changed or unsaved:
            return "check-in"
        return "check-out"

    def sentence(self) -> str:
        """RevisionWorx's status line for it (contrib/rwx_client.py `describe`): "E-100 rev B · Released · checked out by you"."""
        if not self.controlled:
            return ""
        parts = [f"{self.name} rev {self.revision or '?'}", self.state]
        if self.checked_out_by:
            parts.append("checked out by you" if self.mine else f"checked out by {self.checked_out_by}")
        if self.file_state in ("modified", "modified-externally"):
            parts.append("this file differs from the latest revision")
        elif self.file_state == "missing":
            parts.append("file missing")
        return " · ".join(p for p in parts if p)


class RevisionWorx:
    """One RevisionWorx installation."""

    def __init__(self, command: list | None = None, timeout: float = TIMEOUT):
        self.command = command if command is not None else find_revisionworx()
        self.timeout = timeout
        self._api = None

    def available(self) -> bool:
        """Installed, and speaking the interface this was written for."""
        if self.command is None:
            return False
        if self._api is None:
            try:
                self._api = int(self._link("version").get("api", 0))
            except (RevisionWorxError, ValueError, TypeError):
                self._api = 0
        return self._api == API_VERSION

    def _call(self, args: list) -> subprocess.CompletedProcess:
        if self.command is None:
            raise RevisionWorxError("RevisionWorx isn't installed, or OpenSchematix can't find it. Put it on the PATH, or set "
                                    f"{ENV_VAR} to its revisionworx program.", "unavailable")
        try:
            return subprocess.run([*self.command, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=self.timeout, stdin=subprocess.DEVNULL, env=child_environment(), **_NO_WINDOW)
        except FileNotFoundError:
            raise RevisionWorxError(f"{self.command[0]} couldn't be run.", "unavailable") from None
        except subprocess.TimeoutExpired:
            raise RevisionWorxError("RevisionWorx didn't answer in time. Is the workspace busy, or its folder offline?", "busy") from None
        except OSError as e:
            raise RevisionWorxError(f"RevisionWorx couldn't be run: {e}", "unavailable") from None

    def _link(self, *args: str, workspace: str = "") -> dict:
        r = self._call([*(["-w", workspace] if workspace else []), "link", *args])
        lines = [x for x in r.stdout.splitlines() if x.strip()]
        try:
            data = json.loads(lines[-1]) if lines else None
        except ValueError:
            data = None
        if not isinstance(data, dict):
            said = (r.stderr or r.stdout or "").strip().splitlines()
            raise RevisionWorxError("RevisionWorx gave an answer OpenSchematix can't read" + (f": {said[-1]}" if said else "."), "error")
        if not data.get("ok"):
            raise RevisionWorxError(str(data.get("error") or "RevisionWorx refused."), str(data.get("kind") or "error"))
        return data

    def _doc(self, workspace: str, *args: str) -> dict:
        r = self._call(["--json", "-w", workspace, "doc", *args])
        if r.returncode != 0:
            said = (r.stderr or r.stdout).strip()
            said = said[len("error: "):] if said.startswith("error: ") else said
            kind = "checked-out" if "checked out" in said else "busy" if "busy" in said else "error"
            raise RevisionWorxError(said or f"RevisionWorx stopped with code {r.returncode}.", kind)
        try:
            data = json.loads(r.stdout) if r.stdout.strip() else {}
        except ValueError:
            raise RevisionWorxError("RevisionWorx gave an answer OpenSchematix can't read.", "error") from None
        return data if isinstance(data, dict) else {}

    def status(self, file) -> Status:
        return Status.of(self._link("status", os.path.abspath(file)))

    def check_out(self, s: Status) -> None:
        self._doc(s.workspace, "checkout", s.doc_id, "--note", "OpenSchematix")

    def undo_check_out(self, s: Status, put_back: bool) -> None:
        """Give the check-out up. `put_back` also puts the latest revision back in the file, losing what was changed since."""
        self._doc(s.workspace, "cancel", s.doc_id, *(["--revert"] if put_back else []))

    def check_in(self, file, message: str) -> dict:
        """A new revision of the document this file is, checked out first if nobody has it. `result` is "revised", or "unchanged"."""
        return self._link("publish", os.path.abspath(file), "--message", message)

    def publish(self, file, project: str, number: str = "", title: str = "", message: str = "", folder: str = "",
                workspace: str = "") -> dict:
        """A new document in `project`, or a new revision of the one numbered `number` there. A file outside the project's folder is copied
        into it (into `folder`), and never over another; the answer's `document.path` is the file it controls."""
        args = ["publish", os.path.abspath(file), "--project", project]
        for flag, value in (("--number", number), ("--title", title), ("--folder", folder), ("--message", message)):
            if value:
                args += [flag, value]
        return self._link(*args, workspace=workspace)

    def projects(self, workspace: str = "") -> list:
        return list(self._link("projects", workspace=workspace).get("projects") or [])

    def workspaces(self) -> list:
        return list(self._link("workspaces").get("workspaces") or [])

    def show(self, file) -> None:
        """Show the document in RevisionWorx's window."""
        self._link("open", "--file", os.path.abspath(file))


def workspaces_for(rwx: RevisionWorx, file) -> list:
    """The workspaces a project file could go in: the one round its folder, if there is one, then those RevisionWorx knows. Each is
    {"location", "name"}."""
    out, seen = [], set()
    if file:
        d = Path(file).resolve().parent
        for folder in (d, *d.parents):
            if (folder / ".revisionworx").is_dir():
                out.append({"location": str(folder), "name": folder.name})
                seen.add(os.path.normcase(str(folder)))
                break
    for w in rwx.workspaces():
        loc = str(w.get("location") or "")
        if loc and not w.get("error") and os.path.normcase(str(Path(loc).resolve())) not in seen:
            out.append({"location": loc, "name": str(w.get("name") or Path(loc).name)})
            seen.add(os.path.normcase(str(Path(loc).resolve())))
    return out


def project_for(projects: list, file) -> dict | None:
    """The project whose folder holds this file, if one does."""
    try:
        here = Path(file).resolve()
    except OSError:
        return None
    best = None
    for p in projects:
        folder = p.get("folder")
        if not folder or p.get("archived"):
            continue
        try:
            root = Path(folder).resolve()
        except OSError:
            continue
        if root == here or root in here.parents:
            if best is None or len(root.parts) > best[0]:
                best = (len(root.parts), p)
    return best[1] if best else None


# ------------------------------------------------------------------------------------------------- the BOM, as RevisionWorx reads one

#: What a BOM file of RevisionWorx's has (docs/bom there), in its order
COLUMNS = ("parent_number", "find_number", "child_number", "child_revision", "quantity", "unit", "reference_designators", "description",
           "part_unit", "note")


def _cell(text: str) -> str:
    """Text a spreadsheet would run as a formula gets a quote in front. The same rule as RevisionWorx's, which takes it off again."""
    return "'" + text if text.lstrip("'")[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def bom_csv(lines, number: str, title: str = "", revision: str = "") -> tuple:
    """The bill of materials (`bom.generate`) as a RevisionWorx BOM under the project's own number: an item row for the project and for
    each part, then a line for each part, numbered 10, 20, 30, with its quantity and designators. A part is what has a part number; lines
    without one can't be bought by number, so they're left out and counted. Lines with the same part number, as from two manufacturers'
    names for it, are one. Returns (bytes, how many lines were left out)."""
    merged: dict = {}
    order: list = []
    left_out = 0
    for line in lines:
        pn = (line.part_number or "").strip()
        if not pn:
            left_out += 1
            continue
        key = pn.casefold()
        if key not in merged:
            words = [w for w in ((line.description or "").strip(), (line.rating or "").strip()) if w]
            merged[key] = {"number": pn, "description": ", ".join(words), "quantity": 0, "designators": []}
            order.append(key)
        merged[key]["quantity"] += int(line.quantity)
        merged[key]["designators"] += [d for d in line.designators if d not in merged[key]["designators"]]
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(COLUMNS)
    w.writerow(["", "", _cell(number), _cell(revision), "", "", "", _cell(title), "EA", ""])
    for key in order:
        p = merged[key]
        w.writerow(["", "", _cell(p["number"]), "", "", "", "", _cell(p["description"]), "EA", ""])
    for i, key in enumerate(order, 1):
        p = merged[key]
        w.writerow([_cell(number), str(i * 10), _cell(p["number"]), "", str(p["quantity"]), "EA", _cell(" ".join(p["designators"])),
                    "", "", ""])
    return out.getvalue().encode("utf-8"), left_out


def _file_name(text: str) -> str:
    out = "".join("-" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in text).strip(" .")
    return out or "bom"


def publish_bom(rwx: RevisionWorx, s: Status, lines, message: str) -> tuple:
    """The project's bill of materials as a BOM document next to it in its RevisionWorx project: numbered as the schematic is, with
    -BOM, in a folder of the project's that's for BOMs if it has one, naming the schematic's revision. A new revision if it's there
    already, and none if nothing changed. `s` is the schematic's status after it was checked in. Returns (RevisionWorx's answer or None
    when there are no parts with a part number, how many lines were left out for having none)."""
    if not s.controlled:
        return None, 0
    number = f"{s.number}-BOM" if s.number else f"{Path(s.path).stem}-BOM"
    data, left_out = bom_csv(lines, s.number or Path(s.path).stem, s.title, s.revision)
    if data.count(b"\r\n") <= 2:
        return None, left_out
    folder = ""
    for p in rwx.projects(s.workspace):
        if p.get("id") == s.project_id and p.get("folder"):
            try:
                found = sorted(x.name for x in Path(p["folder"]).iterdir() if x.is_dir() and "bom" in x.name.casefold())
            except OSError:
                found = []
            folder = found[0] if found else ""
    with tempfile.TemporaryDirectory(prefix="openschematix-bom-") as tmp:
        f = Path(tmp) / f"{_file_name(number)}.csv"
        f.write_bytes(data)
        return rwx.publish(f, s.project_id, number, f"{s.title or s.name} bill of materials", message, folder, s.workspace), left_out
