"""Built-in revision history.

Snapshots are stored inside the project file in a content-addressed object
store: the project header and every sheet are serialised separately, hashed
(SHA-256) and stored once. A snapshot is a list of object hashes, so a sheet
that did not change between revisions is stored only once.

Two kinds of entries:
  * ``auto``     - created automatically when the project is saved and its
                   content differs from the latest snapshot. Only the newest
                   AUTO_KEEP automatic snapshots are kept.
  * ``approved`` - formal revisions issued by the user ("Issue revision"),
                   with a revision identifier (A, B, C … or 0, 1, 2 …),
                   description, author and approver. They are never pruned
                   automatically and appear in title-block revision tables.
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import json
import zlib

AUTO_KEEP = 25
KINDS = ("auto", "approved")


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def next_label(prev: str | None, style: str = "letter") -> str:
    """Next formal revision identifier: A, B, … Z, AA, AB … or 0, 1, 2 …"""
    if style == "number":
        try:
            return str(int(prev) + 1) if prev not in (None, "") else "0"
        except ValueError:
            return "0"
    if not prev or not prev.isalpha():
        return "A"
    s = list(prev.upper())
    i = len(s) - 1
    while i >= 0:
        if s[i] != "Z":
            s[i] = chr(ord(s[i]) + 1)
            return "".join(s)
        s[i] = "A"
        i -= 1
    return "A" + "".join(s)


class RevisionStore:
    def __init__(self):
        self.entries: list[dict] = []
        self.objects: dict[str, bytes] = {}   # sha -> zlib-compressed canonical JSON
        self._schema_cache: dict[str, int] = {}   # sha -> sheet schema needed (objects never change)

    # ---------------------------------------------------------------- objects
    def _put(self, obj) -> str:
        raw = _canon(obj)
        h = _sha(raw)
        if h not in self.objects:
            self.objects[h] = zlib.compress(raw, 6)
        return h

    def _get(self, h: str):
        return json.loads(zlib.decompress(self.objects[h]).decode("utf-8"))

    # ---------------------------------------------------------------- snapshots
    @staticmethod
    def _split(project) -> tuple[dict, list]:
        d = project.to_dict()
        sheets = d.pop("sheets")
        return d, sheets

    def content_key(self, project) -> str:
        head, sheets = self._split(project)
        return _sha(_canon([head, sheets]))

    def latest(self, kind: str | None = None):
        for e in reversed(self.entries):
            if kind is None or e["kind"] == kind:
                return e
        return None

    def create(self, project, kind: str = "auto", label: str = "", description: str = "", author: str = "",
               approved_by: str = "", force: bool = False):
        """Create a snapshot. For automatic snapshots nothing is stored if the
        content equals the most recent snapshot. Returns the entry or None."""
        if kind not in KINDS:
            raise ValueError(kind)
        head, sheets = self._split(project)
        key = _sha(_canon([head, sheets]))
        last = self.latest()
        if kind == "auto" and not force and last is not None and last.get("content") == key:
            return None
        entry = {
            "n": (max((e["n"] for e in self.entries), default=0) + 1),
            "kind": kind,
            "label": label or "",
            "description": description,
            "author": author,
            "approved_by": approved_by,
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "content": key,
            "head": self._put(head),
            "sheets": [[s["uid"], s.get("name", ""), self._put(s)] for s in sheets],
        }
        self.entries.append(entry)
        self.prune()
        return entry

    def get(self, n: int) -> dict:
        for e in self.entries:
            if e["n"] == n:
                return e
        raise KeyError(n)

    def load(self, n: int):
        """Reconstruct the Project stored in snapshot n."""
        from .project import Project
        e = self.get(n)
        head = self._get(e["head"])
        head["sheets"] = [self._get(h) for _uid, _name, h in e["sheets"]]
        p = Project.from_dict(head)
        p.revisions = self
        return p

    def delete(self, n: int):
        e = self.get(n)
        if e["kind"] == "approved":
            raise ValueError("approved revisions cannot be deleted")
        self.entries.remove(e)
        self.gc()

    def prune(self):
        autos = [e for e in self.entries if e["kind"] == "auto"]
        if len(autos) > AUTO_KEEP:
            drop = {id(e) for e in autos[:len(autos) - AUTO_KEEP]}
            self.entries = [e for e in self.entries if id(e) not in drop]
            self.gc()

    def gc(self):
        live = set()
        for e in self.entries:
            live.add(e["head"])
            live.update(h for _u, _n, h in e["sheets"])
        for h in list(self.objects):
            if h not in live:
                del self.objects[h]

    def approved(self) -> list[dict]:
        return [e for e in self.entries if e["kind"] == "approved"]

    def required_schema(self) -> int:
        """Lowest sheet schema able to represent every stored snapshot.

        The revision history is part of the project file, so a project whose
        current sheets have no boundary fills but whose history does must
        still be written as schema 3: an older reader would otherwise open it
        and fail (or misbehave) only when that revision is restored."""
        from .model import sheet_dict_schema
        need = 2
        for e in self.entries:
            for _uid, _name, h in e.get("sheets", []):
                v = self._schema_cache.get(h)
                if v is None:
                    try:
                        v = sheet_dict_schema(self._get(h))
                    except (KeyError, ValueError, zlib.error):
                        v = 2               # unreadable objects are dropped on load anyway
                    self._schema_cache[h] = v
                need = max(need, v)
        return need

    def stored_bytes(self) -> int:
        return sum(len(b) for b in self.objects.values())

    # ---------------------------------------------------------------- persistence
    def index(self) -> dict:
        return {"version": 1, "entries": copy.deepcopy(self.entries)}

    @classmethod
    def from_parts(cls, index: dict, objects: dict[str, bytes]) -> "RevisionStore":
        st = cls()
        for e in (index or {}).get("entries", []):
            if not isinstance(e, dict) or e.get("kind") not in KINDS:
                continue
            hashes = [e.get("head")] + [h for _u, _n, h in e.get("sheets", [])]
            if all(h in objects for h in hashes):
                st.entries.append(e)
        st.objects = dict(objects)
        st.gc()
        return st


def restore(project, store: RevisionStore, n: int):
    """Return a new Project with the content of revision n. The current state
    is first saved as an automatic snapshot, so a restore can be undone."""
    store.create(project, "auto", description=f"Before restoring revision #{n}", force=False)
    p = store.load(n)
    p.uid = project.uid
    p.revisions = store
    return p
