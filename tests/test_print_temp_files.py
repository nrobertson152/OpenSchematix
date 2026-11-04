"""Print no longer leaves a PDF behind for every print (audit F12, #82).

Print writes the sheet to a temporary PDF and opens it in the PDF viewer.
Before, that file was never deleted. Now print files live in their own
temporary folder: a session deletes its own on exit (any still open in a
viewer are skipped), and a later start deletes ones older than a day, never
younger ones that another running instance may still show.
"""
import os
import sys
import time

import pytest

from openschematix import printtemp


def _age(path, hours):
    t = time.time() - hours * 3600
    os.utime(path, (t, t))


def test_session_files_go_to_their_own_folder_and_are_deleted_on_cleanup(tmp_path):
    pf = printtemp.PrintFiles(str(tmp_path))
    a, b = pf.new_path(), pf.new_path()
    assert a != b and os.path.dirname(a) == printtemp.folder(str(tmp_path))
    assert os.path.basename(a).startswith(f"print-{os.getpid()}-") and a.endswith(".pdf")
    assert pf.cleanup() == []
    assert not os.path.exists(a) and not os.path.exists(b)
    assert not os.path.exists(printtemp.folder(str(tmp_path)))      # empty folder removed too


def test_a_file_that_cannot_be_deleted_is_kept_for_later(tmp_path, monkeypatch):
    """Windows refuses to delete a file a viewer still has open."""
    pf = printtemp.PrintFiles(str(tmp_path))
    busy, done = pf.new_path(), pf.new_path()
    real = os.unlink

    def unlink(p, *a, **k):
        if p == busy:
            raise PermissionError(13, "in use by another process", p)
        return real(p, *a, **k)
    monkeypatch.setattr(os, "unlink", unlink)
    assert pf.cleanup() == [busy]
    assert os.path.exists(busy) and not os.path.exists(done)
    assert os.path.isdir(printtemp.folder(str(tmp_path)))           # not removed while in use
    monkeypatch.setattr(os, "unlink", real)
    assert pf.cleanup() == [] and not os.path.exists(busy)


def test_another_sessions_folder_contents_survive_cleanup(tmp_path):
    mine, other = printtemp.PrintFiles(str(tmp_path)), printtemp.PrintFiles(str(tmp_path))
    o = other.new_path()
    mine.new_path()
    mine.cleanup()
    assert os.path.exists(o)


def test_startup_removes_only_stale_print_files(tmp_path):
    base = str(tmp_path)
    pf = printtemp.PrintFiles(base)
    old, fresh = pf.new_path(), pf.new_path()
    _age(old, 25)
    _age(fresh, 2)                                                  # maybe on screen in another instance
    legacy_old = tmp_path / "openschematix-ab12cd34.pdf"            # left by 1.1.x in the temp folder itself
    legacy_new = tmp_path / "openschematix-zz99yy88.pdf"
    unrelated = tmp_path / "openschematix-notes.pdf"                # not our naming pattern
    other_ext = printtemp.folder(base) + os.sep + "readme.txt"
    for f in (legacy_old, legacy_new, unrelated):
        f.write_bytes(b"%PDF")
    with open(other_ext, "w") as f:
        f.write("x")
    for f in (legacy_old, unrelated, other_ext):
        _age(str(f), 100)
    _age(str(legacy_new), 1)
    assert printtemp.cleanup_stale(base) == 2
    assert not os.path.exists(old) and not legacy_old.exists()
    assert os.path.exists(fresh) and legacy_new.exists() and unrelated.exists() and os.path.exists(other_ext)


def test_startup_cleanup_tolerates_a_missing_folder_and_locked_files(tmp_path, monkeypatch):
    assert printtemp.cleanup_stale(str(tmp_path / "does-not-exist")) == 0
    pf = printtemp.PrintFiles(str(tmp_path))
    p = pf.new_path()
    _age(p, 48)
    monkeypatch.setattr(os, "unlink", lambda *a, **k: (_ for _ in ()).throw(PermissionError(13, "busy")))
    assert printtemp.cleanup_stale(str(tmp_path)) == 0 and os.path.exists(p)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="symlinks need privileges on Windows")
def test_startup_cleanup_does_not_follow_links(tmp_path):
    target = tmp_path / "keep.pdf"
    target.write_bytes(b"%PDF")
    os.makedirs(printtemp.folder(str(tmp_path)))
    link = os.path.join(printtemp.folder(str(tmp_path)), "print-1-x.pdf")
    os.symlink(target, link)
    _age(str(target), 100)
    printtemp.cleanup_stale(str(tmp_path))
    assert target.exists()


# ---------------------------------------------------------------- the application
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSCHEMATIX_CONFIG_DIR", str(tmp_path / "config"))
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Tk GUI display not available: {e}")
    from openschematix.gui import app as app_mod
    a = app_mod.App(root, check_recovery=False)
    a.print_files = printtemp.PrintFiles(str(tmp_path / "tmp"))
    opened = []
    if sys.platform.startswith("win"):
        monkeypatch.setattr(os, "startfile", lambda p: opened.append(p), raising=False)
    else:
        monkeypatch.setattr(app_mod.subprocess, "Popen", lambda args, **k: opened.append(args[-1]))
    a._opened = opened
    yield a
    try:
        root.destroy()
    except Exception:  # noqa: BLE001 - quit() may already have destroyed it
        pass


def test_print_writes_into_the_print_folder_and_quit_deletes_it(app, tmp_path):
    app.print_()
    [path] = app._opened
    assert os.path.dirname(path) == printtemp.folder(str(tmp_path / "tmp"))
    with open(path, "rb") as f:
        assert f.read(5) == b"%PDF-"
    app.dirty = False
    app.quit()
    assert not os.path.exists(path)


def test_a_failed_print_leaves_no_file(app, tmp_path, monkeypatch):
    import tempfile
    from openschematix.gui import app as app_mod
    systmp = tmp_path / "systmp"
    systmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(systmp))      # where the old code put its file
    shown = []
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *a, **k: shown.append(a))

    def fail(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(app_mod.export, "export_project_pdf", fail)
    app.print_()
    assert shown and not app._opened and app.print_files.paths == []
    assert [str(f) for f in tmp_path.rglob("*.pdf")] == []
    app.recovery.end()
