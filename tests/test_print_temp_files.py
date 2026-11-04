"""Print no longer leaves a PDF behind for every print (audit F12, #82).

Print writes the sheet to a temporary PDF and opens it in the PDF viewer.
Before, that file was never deleted. Now print files live in a private
temporary folder of the user's: a session deletes its own on exit (except
recent ones a viewer may still be opening, and any still open), and a later
start deletes ones older than a day, never younger ones that another running
instance may still show. Untrusted folders (links, other users') are never
written to or cleaned.
"""
import os
import stat
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
    assert pf.cleanup(keep_minutes=0) == []
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
    assert pf.cleanup(keep_minutes=0) == [busy]
    assert os.path.exists(busy) and not os.path.exists(done)
    assert os.path.isdir(printtemp.folder(str(tmp_path)))           # not removed while in use
    monkeypatch.setattr(os, "unlink", real)
    assert pf.cleanup(keep_minutes=0) == [] and not os.path.exists(busy)


def test_another_sessions_folder_contents_survive_cleanup(tmp_path):
    mine, other = printtemp.PrintFiles(str(tmp_path)), printtemp.PrintFiles(str(tmp_path))
    o = other.new_path()
    mine.new_path()
    mine.cleanup(keep_minutes=0)
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


def test_recent_prints_are_kept_at_exit_for_a_viewer_still_starting(tmp_path):
    """Codex review of #85: the viewer opens the file asynchronously."""
    pf = printtemp.PrintFiles(str(tmp_path))
    p = pf.new_path()
    created = pf.paths[0][1]
    assert pf.cleanup(now=created + 60) == [p] and os.path.exists(p)
    assert pf.cleanup(now=created + 11 * 60) == [] and not os.path.exists(p)


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="per-user folder name and modes are POSIX")
def test_the_folder_is_per_user_and_private(tmp_path):
    pf = printtemp.PrintFiles(str(tmp_path))
    p = pf.new_path()
    d = os.path.dirname(p)
    assert d == os.path.join(str(tmp_path), f"openschematix-print-{os.getuid()}")
    assert stat.S_IMODE(os.lstat(d).st_mode) == 0o700


@pytest.mark.skipif(sys.platform.startswith("win"), reason="symlinks need privileges on Windows")
def test_a_linked_print_folder_is_never_written_to_or_cleaned(tmp_path):
    """Codex review of #85: another user pre-creates the folder name as a link
    to the victim's documents; startup clean-up must not delete there."""
    docs = tmp_path / "documents"
    docs.mkdir()
    report = docs / "print-report.pdf"
    report.write_bytes(b"%PDF")
    _age(str(report), 100)
    base = tmp_path / "tmp"
    base.mkdir()
    os.symlink(docs, printtemp.folder(str(base)))
    assert printtemp.cleanup_stale(str(base)) == 0 and report.exists()
    pf = printtemp.PrintFiles(str(base))
    p = pf.new_path()                                        # prints still work, privately
    assert os.path.dirname(p) != printtemp.folder(str(base)) and not os.path.realpath(p).startswith(str(docs))
    assert printtemp.trusted_dir(os.path.dirname(p))
    assert pf.cleanup(keep_minutes=0) == [] and not os.path.exists(os.path.dirname(p))
    assert report.exists()


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX permissions")
def test_a_folder_others_can_write_to_is_not_used(tmp_path):
    """Codex review of #85: the folder may already exist with someone else's
    permissions; Print must keep working and nothing there is cleaned."""
    d = printtemp.folder(str(tmp_path))
    os.mkdir(d)
    os.chmod(d, 0o777)
    old = os.path.join(d, "print-x.pdf")
    with open(old, "wb") as f:
        f.write(b"%PDF")
    _age(old, 100)
    assert not printtemp.trusted_dir(d)
    assert printtemp.cleanup_stale(str(tmp_path)) == 0 and os.path.exists(old)
    p = printtemp.PrintFiles(str(tmp_path)).new_path()
    assert os.path.dirname(p) != d


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX ownership")
def test_a_folder_owned_by_another_user_is_not_trusted(tmp_path, monkeypatch):
    d = tmp_path / "x"
    d.mkdir(mode=0o700)
    assert printtemp.trusted_dir(str(d))
    monkeypatch.setattr(printtemp, "_uid", lambda: os.getuid() + 1)
    assert not printtemp.trusted_dir(str(d))


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() != 0, reason="needs chown (root)")
def test_legacy_files_of_other_users_are_left_alone(tmp_path):
    theirs = tmp_path / "openschematix-ab12cd34.pdf"
    theirs.write_bytes(b"%PDF")
    os.chown(theirs, 12345, 12345)
    _age(str(theirs), 100)
    assert printtemp.cleanup_stale(str(tmp_path)) == 0 and theirs.exists()


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
    (tmp_path / "tmp").mkdir()
    a.print_files = printtemp.PrintFiles(str(tmp_path / "tmp"))
    errors = []
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *x, **k: errors.append(x))
    a._errors = errors
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
    assert not app._errors
    [path] = app._opened
    assert os.path.dirname(path) == printtemp.folder(str(tmp_path / "tmp"))
    with open(path, "rb") as f:
        assert f.read(5) == b"%PDF-"
    app.print_()
    recent = app._opened[1]
    app.print_files.paths[0] = (path, time.time() - 11 * 60)   # printed a while ago
    app.dirty = False
    app.quit()
    assert not os.path.exists(path)
    assert os.path.exists(recent)                              # the viewer may still be opening it


def test_a_failed_print_leaves_no_file(app, tmp_path, monkeypatch):
    import tempfile
    from openschematix.gui import app as app_mod
    systmp = tmp_path / "systmp"
    systmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(systmp))      # where the old code put its file
    shown = app._errors

    def fail(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(app_mod.export, "export_project_pdf", fail)
    app.print_()
    assert shown and not app._opened and app.print_files.paths == []
    assert [str(f) for f in tmp_path.rglob("*.pdf")] == []
    app.recovery.end()
