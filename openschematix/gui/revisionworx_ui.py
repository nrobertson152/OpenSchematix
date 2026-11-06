"""RevisionWorx in the window: its sentence about the open project in the status bar, the one next step as a button (Check out or
Check in), File ▸ RevisionWorx, and the rule that someone else's checked-out file isn't saved over. Everything goes through
revisionworx_link; the window only asks and shows. Hidden when RevisionWorx isn't installed."""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from .. import bom
from ..revisionworx_link import RevisionWorx, RevisionWorxError, project_for, publish_bom, workspaces_for
from . import theme as th
from .dialogs import Dialog, form
from .widgets import Tooltip


def _parts_with_numbers(project) -> int:
    return len({(l.part_number or "").strip().casefold() for l in bom.generate(project) if (l.part_number or "").strip()})


class CheckInDialog(Dialog):
    """What changed, which RevisionWorx keeps with the revision, and whether the bill of materials goes too."""

    def __init__(self, app, name, parts):
        super().__init__(app, f"Check in {name}")
        ttk.Label(self.frame, text="What changed? RevisionWorx keeps this with the revision.", style="Surface.TLabel").pack(anchor="w")
        self.message = tk.StringVar()
        entry = ttk.Entry(self.frame, textvariable=self.message, width=56)
        entry.pack(fill="x", pady=(6, 0))
        self.bom = tk.BooleanVar(value=parts > 0)
        if parts:
            ttk.Checkbutton(self.frame, variable=self.bom,
                            text=f"Its bill of materials too ({parts} part{'s' if parts != 1 else ''} with a part number), "
                                 "as a BOM next to it").pack(anchor="w", pady=(10, 0))
        self.buttons("Check in")
        th.recolor_tree(self, app.theme)
        entry.focus_set()

    def ok(self):
        text = self.message.get().strip()
        if not text:
            messagebox.showinfo("Check in", "Say what changed. RevisionWorx keeps it with the revision.", parent=self)
            return
        self.result = (text, bool(self.bom.get()))
        self.destroy()


class AddDialog(Dialog):
    """Putting the project under revision control: which RevisionWorx project, and its number and title."""

    def __init__(self, app, projects, chosen, number, title):
        super().__init__(app, "Add to RevisionWorx")
        self.projects = projects
        names = [self._name(p) for p in projects]
        g = ttk.Frame(self.frame, style="Surface.TFrame")
        g.pack(fill="x")
        ttk.Label(g, text="Project", style="Surface.TLabel").pack(side="left", padx=(0, 12))
        self.project = tk.StringVar(value=self._name(chosen) if chosen is not None else names[0])
        ttk.Combobox(g, textvariable=self.project, values=names, state="readonly", width=40).pack(side="left", fill="x", expand=True)
        f, self.vars = form(self.frame, [("number", "Number", number), ("title", "Title", title), ("message", "Description", "First issue")])
        f.pack(fill="x", pady=(8, 0))
        ttk.Label(self.frame, text="A project file that isn't in the RevisionWorx project's folder is copied into it, and OpenSchematix "
                                   "carries on with the copy.", style="Muted.TLabel", wraplength=440, justify="left").pack(anchor="w", pady=(10, 0))
        self.buttons("Add")
        th.recolor_tree(self, app.theme)

    @staticmethod
    def _name(p):
        words = " ".join(x for x in (p.get("number", ""), p.get("name", "")) if x)
        return f"{p['workspace_name']} › {words}" if p.get("workspace_name") else words

    def ok(self):
        chosen = next((p for p in self.projects if self._name(p) == self.project.get()), None)
        number = self.vars["number"].get().strip()
        if chosen is None or not number:
            messagebox.showinfo("Add to RevisionWorx", "Choose a project and give it a number.", parent=self)
            return
        self.result = (chosen, number, self.vars["title"].get().strip(), self.vars["message"].get().strip())
        self.destroy()


class RevisionWorxUI:
    """The window's part. `status` is what RevisionWorx last said about the project's file, or None."""

    def __init__(self, app, status_bar, file_menu, after_label):
        self.app = app
        self.rwx: RevisionWorx | None = None
        self._looked = False
        self._lock = threading.Lock()
        self.status = None
        self._question = 0
        self._answers: queue.Queue = queue.Queue()
        self._polling = False
        self._asked_at = 0.0
        self.file_menu = file_menu
        self.after_label = after_label
        self.menu = tk.Menu(file_menu, tearoff=0)
        for label, fn in (("Check out", self.check_out), ("Check in…", self.check_in), ("Undo check-out…", self.undo_check_out),
                          ("Add to RevisionWorx…", self.add), ("Show in RevisionWorx", self.show_in_revisionworx)):
            self.menu.add_command(label=label, command=fn, state="disabled")
        self._in_menu = False
        self.status_bar = status_bar
        self.button = ttk.Button(status_bar, text="", style="Accent.TButton", command=self._act)
        self.label = ttk.Label(status_bar, text="", style="Status.TLabel")
        self.tip = Tooltip(self.label, "")
        self.action = ""

    # ------------------------------------------------------------------------------------------------- asking

    def _found(self) -> RevisionWorx | None:
        """RevisionWorx, if it's installed and speaks the interface this knows. Looked for once, when there's first a file to ask about."""
        with self._lock:
            if not self._looked:
                rwx = RevisionWorx()
                self.rwx = rwx if rwx.available() else None
                self._looked = True
            return self.rwx

    def now(self, path):
        if not path:
            return None
        rwx = self._found()
        if rwx is None:
            return None
        try:
            return rwx.status(path)
        except RevisionWorxError:
            return None

    def refresh(self, wait=False):
        """Ask again about the project's file: in the background, or now. Only the newest question's answer counts."""
        self._asked_at = time.monotonic()
        self._question += 1
        path = self.app.filename or ""
        if wait or not path:
            self._answered(self._question, path, self.now(path))
            return
        q = self._question
        threading.Thread(target=lambda: self._answers.put((q, path, self.now(path))), daemon=True).start()
        if not self._polling:
            self._polling = True
            self.app.root.after(60, self._poll)

    def _poll(self):
        try:
            while True:
                self._answered(*self._answers.get_nowait())
        except queue.Empty:
            pass
        if self._answers.empty() and self._question_answered():
            self._polling = False
            return
        try:
            self.app.root.after(60, self._poll)
        except tk.TclError:
            self._polling = False

    def _question_answered(self) -> bool:
        return getattr(self, "_last_answered", 0) >= self._question

    def _answered(self, question, path, status):
        if question != self._question or path != (self.app.filename or ""):
            return              # out of date: asked about before something newer, or about a project that isn't open now
        self._last_answered = question
        self.status = status
        if self.rwx is not None and not self._in_menu:
            index = self._menu_index()
            self.file_menu.insert_cascade(index, label="RevisionWorx", menu=self.menu)
            self._in_menu = True
        s = status
        controlled = s is not None and s.controlled
        for label, on in (("Check out", controlled and not s.checked_out_by), ("Check in…", controlled and not s.theirs),
                          ("Undo check-out…", controlled and s.mine), ("Add to RevisionWorx…", self.rwx is not None and not controlled),
                          ("Show in RevisionWorx", controlled)):
            self.menu.entryconfigure(label, state="normal" if on else "disabled")
        self.show()

    def _menu_index(self) -> int:
        end = self.file_menu.index("end") or 0
        for i in range(end + 1):
            try:
                if self.file_menu.entrycget(i, "label") == self.after_label:
                    return i + 1
            except tk.TclError:
                continue
        return end + 1

    def focus_returned(self):
        """Coming back to the window, RevisionWorx may have been used meanwhile."""
        if self.app.filename and time.monotonic() - self._asked_at > 3.0:
            self.refresh()

    # ------------------------------------------------------------------------------------------------- showing

    def show(self):
        s = self.status
        if s is None or not s.controlled:
            self.action = ""
            self.label.pack_forget()
            self.button.pack_forget()
            return
        title, text, tone = s.headline()
        self.label.configure(text=s.sentence(), style="StatusStrong.TLabel" if tone in ("warn", "danger") else "Status.TLabel")
        self.tip.set(f"{title}. {text} (RevisionWorx)")
        self.action = s.primary(self.app.dirty)
        self.button.configure(text={"check-in": "Check in…", "check-out": "Check out"}.get(self.action, ""))
        # packed ahead of everything else in the status bar, at its right-hand end, so a long message can't squeeze them out
        first = self.status_bar.pack_slaves()[0] if self.status_bar.pack_slaves() else None
        if self.label.winfo_manager() != "pack":
            self.label.pack(side="right", padx=(10, 0), **({"before": first} if first is not None and first is not self.button else {}))
        if self.action:
            if self.button.winfo_manager() != "pack":
                self.button.pack(side="right", padx=(6, 0), before=self.label)
        else:
            self.button.pack_forget()

    def _act(self):
        if self.action == "check-in":
            self.check_in()
        elif self.action == "check-out":
            self.check_out()

    def _refused(self, e) -> bool:
        messagebox.showwarning("RevisionWorx", str(e), parent=self.app.root)
        self.refresh(wait=True)
        return False

    def _busy(self, on):
        try:
            self.app.root.configure(cursor="watch" if on else "")
            self.app.root.update_idletasks()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------------------------------------- doing

    def may_write(self, path) -> bool:
        """Whether saving over this file is all right: not if it's someone else's checked-out working file, which would lose their work.
        If RevisionWorx doesn't answer, what it said last counts."""
        s = self.now(path) if self.rwx is not None or not self._looked else None
        if s is None and self.status is not None and path == self.app.filename:
            s = self.status
        if s is None or not s.theirs:
            return True
        if messagebox.askyesno("RevisionWorx", f"{s.name} is checked out by {s.checked_out_by}. Saving here would overwrite the file "
                                               f"they're working on.\n\nSave a copy instead?", parent=self.app.root):
            self.app.root.after(10, self.app.save_as)
        return False

    def check_out(self) -> bool:
        self.refresh(wait=True)
        s = self.status
        if self.rwx is None or s is None or not s.controlled:
            return False
        if s.checked_out_by:
            self.app.set_status(f"{s.name} is already checked out by {'you' if s.mine else s.checked_out_by}.")
            return s.mine
        self._busy(True)
        try:
            self.rwx.check_out(s)
        except RevisionWorxError as e:
            return self._refused(e)
        finally:
            self._busy(False)
        self.refresh(wait=True)
        self.app.toast(f"Checked out {s.name}. Change it, save it, then check it in.", "success")
        return True

    def check_in(self, message=None, with_bom=None) -> bool:
        """Keep the project as a new revision: saved first if it has changes, checked out first if nobody has it. Its bill of materials
        goes with it as a BOM if asked. `message` and `with_bom` stand in for the dialog."""
        self.refresh(wait=True)
        s = self.status
        if s is None or not s.controlled:
            return self.add()
        if s.theirs:
            messagebox.showinfo("RevisionWorx", f"{s.name} is checked out by {s.checked_out_by}. It can be checked in once they have.",
                                parent=self.app.root)
            return False
        if message is None:
            d = CheckInDialog(self.app, s.name, _parts_with_numbers(self.app.project))
            got = d.show_modal(wait=True)
            if not got:
                return False
            message, with_bom = got
        if self.app.dirty and not self.app.save():
            return False
        notes = []
        self._busy(True)
        try:
            answer = self.rwx.check_in(self.app.filename, message)
            label = ((answer.get("document") or {}).get("latest") or {}).get("label", "?")
            if answer.get("result") == "unchanged":
                after = self.rwx.status(self.app.filename)
                if after.mine:
                    self.rwx.undo_check_out(after, False)       # nothing to keep, so it isn't left checked out
                notes.append(f"Nothing had changed since revision {label}, so there's no new one, and it's checked back in.")
            else:
                notes.append(f"Checked in {s.name} as revision {label}.")
            if with_bom:
                answer, left_out = publish_bom(self.rwx, self.rwx.status(self.app.filename), bom.generate(self.app.project), message)
                if answer is not None:
                    d = answer.get("document") or {}
                    what = "unchanged" if answer.get("result") == "unchanged" else f"revision {(d.get('latest') or {}).get('label', '?')}"
                    notes.append(f"Its bill of materials is {d.get('number', 'a BOM')}, {what}.")
                if left_out:
                    notes.append(f"{left_out} line{'s' if left_out != 1 else ''} without a part number {'aren' if left_out != 1 else 'isn'}'t "
                                 "in it.")
        except RevisionWorxError as e:
            return self._refused(e)
        finally:
            self._busy(False)
        self.refresh(wait=True)
        self.app.toast(" ".join(notes), "success")
        return True

    def undo_check_out(self, put_back=None) -> bool:
        self.refresh(wait=True)
        s = self.status
        if self.rwx is None or s is None or not s.mine:
            return False
        if put_back is None:
            answer = messagebox.askyesnocancel(
                "RevisionWorx", f"Give up the check-out of {s.name}?\n\nYes puts revision {s.revision} back in the file, losing what's "
                                f"changed since. No keeps the file as it is.", parent=self.app.root)
            if answer is None:
                return False
            put_back = bool(answer)
        self._busy(True)
        try:
            self.rwx.undo_check_out(s, put_back)
        except RevisionWorxError as e:
            return self._refused(e)
        finally:
            self._busy(False)
        if put_back:
            self.app.open_path(self.app.filename, confirm=False)
            self.refresh(wait=True)
            self.app.toast(f"{s.name} is checked back in, and revision {s.revision} is back.", "success")
        else:
            self.refresh(wait=True)
            self.app.toast(f"{s.name} is checked back in. The file stays as it is.", "success")
        return True

    def add(self, choice=None) -> bool:
        """Put the project file under revision control. `choice` (project, number, title, description) stands in for the dialog."""
        rwx = self._found()
        if rwx is None:
            return False
        try:
            found = []
            for ws in workspaces_for(rwx, self.app.filename):
                for p in rwx.projects(ws["location"]):
                    if p.get("mode", "managed") == "managed" and not p.get("archived"):
                        found.append({**p, "workspace": ws["location"], "workspace_name": ws["name"]})
        except RevisionWorxError as e:
            return self._refused(e)
        if not found:
            messagebox.showinfo("RevisionWorx", "RevisionWorx has no project to put it in yet. Make one in RevisionWorx first.",
                                parent=self.app.root)
            return False
        if len({p["workspace"] for p in found}) < 2:
            found = [{**p, "workspace_name": ""} for p in found]
        if choice is None:
            meta = self.app.project.meta
            stem = os.path.splitext(os.path.basename(self.app.filename or ""))[0]
            d = AddDialog(self.app, found, project_for(found, self.app.filename) if self.app.filename else None,
                          str(meta.get("number") or stem), str(meta.get("title") or stem))
            choice = d.show_modal(wait=True)
            if not choice:
                return False
        project, number, title, message = choice
        if (not self.app.filename or self.app.dirty) and not self.app.save():
            return False
        self._busy(True)
        try:
            answer = rwx.publish(self.app.filename, project["id"], number, title, message or "First issue", workspace=project.get("workspace", ""))
        except RevisionWorxError as e:
            return self._refused(e)
        finally:
            self._busy(False)
        d = answer.get("document") or {}
        label = (d.get("latest") or {}).get("label", "?")
        where = d.get("path", "")
        if where and os.path.normcase(os.path.realpath(where)) != os.path.normcase(os.path.realpath(self.app.filename)):
            self.app.open_path(where, confirm=False)
            self.refresh(wait=True)
            self.app.toast(f"Added as {d.get('number') or title} revision {label}. This is its copy in the project's folder.", "success")
        else:
            self.refresh(wait=True)
            self.app.toast(f"Added as {d.get('number') or title} revision {label}.", "success")
        return True

    def show_in_revisionworx(self) -> bool:
        if self.rwx is None or not self.app.filename:
            return False
        try:
            self.rwx.show(self.app.filename)
        except RevisionWorxError as e:
            return self._refused(e)
        return True


__all__ = ["AddDialog", "CheckInDialog", "RevisionWorxUI"]
