"""PDF text keeps the characters common on schematics (audit F8, #81).

PDF text used to be encoded as cp1252 with errors="replace", so Ω, Δ, ≤, μ,
∞ and arrows silently became "?". Characters missing from Helvetica's
WinAnsi encoding are now drawn with the standard Symbol font, which every
PDF reader provides; no font is embedded. Anything neither font has is
drawn as "?" and returned to the caller, which tells the user.
"""
import io
import re
import zlib

import pytest

from openschematix import export
from openschematix.model import Shape
from openschematix.project import new_project

ENGINEERING = ["R1 = 10 kΩ ±5 %", "Δp ≤ 5 bar, Q ≥ 2 l/min", "C = 4,7 μF", "∞ √2 π ≠ ≈ → ← ↔ ∴ θ φ"]


def _project(texts, angle=0.0):
    p = new_project("Text")
    d = p.sheets[0]
    for i, t in enumerate(texts):
        d.add_shape(Shape(d.new_id(), "text", pts=[(60, 60 + 25 * i)], s=t, size=12, angle=angle))
    return p, d


def _streams(pdf: bytes) -> str:
    return "\n".join(zlib.decompress(m.group(1)).decode("latin-1")
                     for m in re.finditer(rb"stream\n(.*?)\nendstream", pdf, re.S))


def test_engineering_characters_are_kept(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    p, d = _project(ENGINEERING)
    path = str(tmp_path / "t.pdf")
    assert export.export_pdf(d, path, project=p) == []
    with open(path, "rb") as f:
        data = f.read()
    text = pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text()
    # pypdf names Symbol's "Delta" glyph U+2206 (INCREMENT), which looks the same
    norm = text.replace("∆", "Δ").replace("Ω", "Ω")
    for line in ENGINEERING:
        assert line in norm, (line, text)
    assert "?" not in text


def test_symbol_font_is_declared_and_used_only_where_needed():
    p, d = _project(["10 kΩ"])
    pdf = export.to_pdf(d, project=p)
    assert b"/BaseFont /Symbol" in pdf and b"/F3 7 0 R" in pdf
    content = _streams(pdf)
    assert "(10 k) Tj /F3 12 Tf (W) Tj" in content


def test_cp1252_text_is_drawn_exactly_as_before():
    """Text Helvetica can show keeps the single-string form (same layout)."""
    texts = ["plain ASCII", "Größe 5 °C ± µ – “quoted” €"]
    p, d = _project(texts)
    content = _streams(export.to_pdf(d, project=p))
    for t in texts:
        assert f"({export._pdf_str(t)}) Tj ET" in content
    assert "/F3" not in content


def test_characters_no_font_has_are_reported_and_drawn_as_question_marks(tmp_path):
    p, d = _project(["Ж Ω 中", "ok"])
    missing = export.export_project_pdf(p, str(tmp_path / "t.pdf"))
    assert missing == sorted({"Ж", "中"})
    missing = set()
    content = _streams(export.project_pdf(p, missing=missing))
    assert missing == {"Ж", "中"}
    assert "(? ) Tj /F3 12 Tf (W) Tj /F1 12 Tf ( ?) Tj" in content


def test_symbol_bytes_that_need_escaping_are_escaped():
    """∴ is byte 0x5C in Symbol: a backslash, which must be escaped."""
    runs = export._pdf_runs("a∴(b)")
    assert runs == [(False, "a"), (True, "\\\\"), (False, "\\(b\\)")]


def test_rotated_text_uses_the_same_runs():
    p, d = _project(["90° Ω"], angle=90.0)
    content = _streams(export.to_pdf(d, project=p))
    assert re.search(r"Tm \(90\\260 \) Tj /F3 12 Tf \(W\) Tj ET", content), content


def test_metadata_and_bookmarks_stay_unicode():
    p, d = _project(["x"])
    p.meta["title"] = "Pumpe Ω"
    d.name = "Blatt Δ"
    pdf = export.project_pdf(p)
    assert "Pumpe Ω".encode("utf-16-be").hex().upper().encode() in pdf
    assert "Blatt Δ".encode("utf-16-be").hex().upper().encode() in pdf


def test_every_symbol_mapping_is_a_distinct_single_byte_outside_cp1252():
    seen = {}
    for ch, code in export._SYMBOL.items():
        assert 0x20 <= code <= 0xFE, ch
        with pytest.raises(UnicodeEncodeError):
            ch.encode("cp1252")
        seen.setdefault(code, []).append(ch)
    # only true synonyms share a glyph: Omega / ohm sign, Delta / increment, epsilon / lunate epsilon
    assert {tuple(sorted(v)) for v in seen.values() if len(v) > 1} == {
        ("\u0394", "\u2206"), ("\u03a9", "\u2126"), ("\u03b5", "\u03f5")}


def test_gui_export_tells_the_user_about_characters_shown_as_question_marks(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSCHEMATIX_CONFIG_DIR", str(tmp_path / "config"))
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Tk GUI display not available: {e}")
    try:
        from openschematix.gui import app as app_mod
        app = app_mod.App(root, check_recovery=False)
        toasts, logs = [], []
        monkeypatch.setattr(app, "toast", lambda m, kind="info": toasts.append((kind, m)))
        monkeypatch.setattr(app, "log", lambda m, kind="info": logs.append((kind, m)))
        out = str(tmp_path / "out.pdf")
        monkeypatch.setattr(app_mod.filedialog, "asksaveasfilename", lambda **k: out)
        d = app.doc
        d.add_shape(Shape(d.new_id(), "text", pts=[(60, 60)], s="10 kΩ", size=12))
        app.export_pdf([d.uid])
        assert toasts and toasts[-1][0] == "success" and not logs
        d.add_shape(Shape(d.new_id(), "text", pts=[(60, 90)], s="Ж", size=12))
        app.export_pdf([d.uid])
        assert toasts[-1][0] == "warning" and "Ж" in toasts[-1][1]
        assert logs and logs[-1][0] == "warning" and "U+0416" in logs[-1][1]
        app.recovery.end()
    finally:
        root.destroy()


def test_gui_print_reports_unshown_characters_and_uses_the_print_folder(tmp_path, monkeypatch):
    """Print combines #85 (private print folder) and #84 (report what PDF cannot show)."""
    import os
    import sys
    from openschematix import printtemp
    monkeypatch.setenv("OPENSCHEMATIX_CONFIG_DIR", str(tmp_path / "config"))
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Tk GUI display not available: {e}")
    try:
        from openschematix.gui import app as app_mod
        app = app_mod.App(root, check_recovery=False)
        (tmp_path / "tmp").mkdir()
        app.print_files = printtemp.PrintFiles(str(tmp_path / "tmp"))
        opened, toasts = [], []
        if sys.platform.startswith("win"):
            monkeypatch.setattr(os, "startfile", lambda p: opened.append(p), raising=False)
        else:
            monkeypatch.setattr(app_mod.subprocess, "Popen", lambda args, **k: opened.append(args[-1]))
        monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *a, **k: pytest.fail(f"error dialog: {a}"))
        monkeypatch.setattr(app, "toast", lambda m, kind="info": toasts.append((kind, m)))
        d = app.doc
        d.add_shape(Shape(d.new_id(), "text", pts=[(60, 60)], s="10 kΩ Ж", size=12))
        app.print_()
        [path] = opened
        assert os.path.dirname(path) == printtemp.folder(str(tmp_path / "tmp"))
        assert toasts and toasts[-1][0] == "warning" and "Ж" in toasts[-1][1] and "Ω" not in toasts[-1][1]
        app.recovery.end()
    finally:
        root.destroy()
