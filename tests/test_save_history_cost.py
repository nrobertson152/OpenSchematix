"""Saving must not get slower as the revision history grows (#75).

Before every save the new bytes are read back (projectio._verify). That
check used to parse every stored revision object again, so each save cost
more than the last: with 25 automatic snapshots of a 2 MB drawing a save
took about seven times as long as the first. Objects already verified in
this session, and byte-identical in the new file, are now accepted without
parsing; everything else is still verified in full, and a file that would
not reopen intact is never written.
"""
import os

import pytest

from openschematix import editing, model, projectio
from openschematix.model import Shape
from openschematix.project import new_project


@pytest.fixture
def parse_count(monkeypatch):
    """Number of Document.from_dict calls (sheet and revision-sheet parses)."""
    calls = [0]
    original = model.Document.from_dict.__func__

    def counting(cls, *a, **k):
        calls[0] += 1
        return original(cls, *a, **k)
    monkeypatch.setattr(model.Document, "from_dict", classmethod(counting))
    return calls


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _edit(p, i):
    d = p.sheets[0]
    d.add_shape(Shape(d.new_id(), "line", pts=[(10.0 * i, 0.0), (10.0 * i + 5, 5.0)]))


def _project():
    p = new_project("History cost")
    editing.place(p.sheets[0], "el.resistor.iec", 100, 100)
    return p


def _save_counts(p, path, parse_count, saves):
    out = []
    for i in range(saves):
        _edit(p, i)
        before = parse_count[0]
        projectio.save_project(p, path)
        out.append(parse_count[0] - before)
    return out


def test_save_parses_the_same_amount_however_long_the_history(tmp_path, parse_count):
    p = _project()
    path = str(tmp_path / "p.schematix")
    counts = _save_counts(p, path, parse_count, 12)
    assert len(p.revisions.entries) == 12
    # every save records one new snapshot of the one sheet; only that and the
    # current sheet need parsing, not the eleven older snapshots
    assert counts[-1] == counts[1], counts
    assert counts[-1] <= 4, counts


def test_history_read_from_a_file_is_not_parsed_again_on_save(tmp_path, parse_count):
    p = _project()
    path = str(tmp_path / "p.schematix")
    _save_counts(p, path, parse_count, 10)
    res = projectio.open_any(path)
    assert not res.recovered and len(res.project.revisions.entries) == 10
    reopened = res.project
    [first_save] = _save_counts(reopened, path, parse_count, 1)
    assert first_save <= 4
    assert len(projectio.open_any(path).project.revisions.entries) == 11


def test_an_object_changed_in_memory_is_verified_in_full_and_the_save_refused(tmp_path):
    p = _project()
    path = str(tmp_path / "p.schematix")
    for i in range(3):
        _edit(p, i)
        projectio.save_project(p, path)
    original = _read(path)
    store = p.revisions
    old_sheet_hash = store.entries[0]["sheets"][0][2]
    assert (old_sheet_hash, "sheet") in store._verified
    # stands for any in-memory corruption of history (a defect elsewhere)
    store.objects[old_sheet_hash] = b"not a zlib stream"     # same name, different bytes
    _edit(p, 99)
    with pytest.raises(OSError, match="could not be verified"):
        projectio.save_project(p, path)
    assert _read(path) == original              # the good file is untouched
    assert len(store.entries) == 3                           # no snapshot recorded by the failed save


def test_a_file_that_would_reopen_with_parts_left_out_is_not_written(tmp_path):
    """Before, the check accepted bytes whose revision history would be
    dropped as damaged on reopening, and the save went ahead."""
    p = _project()
    path = str(tmp_path / "p.schematix")
    projectio.save_project(p, path)
    original = _read(path)
    h = p.revisions.entries[0]["head"]
    p.revisions._verified.clear()
    p.revisions.objects[h] = b"damaged"
    _edit(p, 1)
    with pytest.raises(OSError, match="would not reopen"):
        projectio.save_project(p, path)
    assert _read(path) == original


def test_verification_state_is_not_written_to_the_file(tmp_path):
    p = _project()
    a, b = str(tmp_path / "a.schematix"), str(tmp_path / "b.schematix")
    projectio.save_project(p, a)
    projectio.atomic_write_bytes(b, projectio.project_bytes(p))
    p.revisions._verified.clear()
    assert projectio.project_bytes(p) == _read(b)
    assert os.path.getsize(a) == os.path.getsize(b)
