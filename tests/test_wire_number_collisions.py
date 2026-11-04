"""Manual wire numbers never end up shared with an automatic one (audit F6, #80).

Before: Number wires kept an automatic number on a connection even when a
connection later in drawing order had that number set manually, and setting
a manual number never looked at the other connections. Two different
connections then carried the same number, and Check drawing reported it as
an error that only Renumber could clear.
"""
from openschematix import check, editing, netlist
from openschematix.project import new_project


def _rows(n, sheets=1):
    """`n` separate electrical connections: a resistor with a wire on its terminal 2, per row."""
    p = new_project("Numbering")
    for _ in range(sheets - 1):
        p.add_sheet()
    out = []
    for k in range(n):
        d = p.sheets[k % sheets]
        r = editing.place(d, "el.resistor.iec", 100, 100 + 100 * k)
        x, y = r.terminals()["2"]
        out.append((d, editing.add_wire(d, [(x, y), (x + 60, y)])))
    return p, out


def _duplicate_errors(p):
    return [i for i in check.check(p, rules={"wire-number"}) if i.severity == "error"]


def test_number_wires_moves_an_automatic_number_off_a_later_manual_one():
    p, rows = _rows(3)
    netlist.assign_wire_numbers(p)
    (d1, w1), (d2, w2), (d3, w3) = rows
    assert (w1.number, w2.number, w3.number) == ("1", "2", "3")
    # the third connection is given "1" by hand without the new API (as in an
    # older file, or a project edited before this fix)
    w3.number, w3.number_manual = "1", True
    netlist.assign_wire_numbers(p)
    assert w3.number == "1" and w3.number_manual          # manual numbers are never changed
    assert w1.number not in ("1", w2.number) and w1.number_manual is False
    assert w2.number == "2"                               # unaffected automatic numbers stay put
    assert not _duplicate_errors(p)


def test_new_numbers_skip_manual_numbers_anywhere_in_the_drawing():
    p, rows = _rows(3)
    (_, w1), (_, w2), (_, w3) = rows
    w3.number, w3.number_manual = "1", True                # set before anything was numbered
    assert netlist.assign_wire_numbers(p) == 2
    assert {w1.number, w2.number} == {"2", "3"} and w3.number == "1"
    assert not _duplicate_errors(p)


def test_sheet_scheme_also_respects_manual_numbers():
    p, rows = _rows(4, sheets=2)
    p.settings.setdefault("wire_numbering", {})["scheme"] = "sheet"
    netlist.assign_wire_numbers(p)
    nums = [w.number for _d, w in rows]
    assert len(set(nums)) == 4
    taken = nums[0]
    rows[3][1].number, rows[3][1].number_manual = taken, True
    netlist.assign_wire_numbers(p)
    assert rows[0][1].number != taken and not _duplicate_errors(p)


def test_setting_a_manual_number_renumbers_the_connection_that_had_it_automatically():
    p, rows = _rows(3)
    netlist.assign_wire_numbers(p)
    (d1, w1), (d2, w2), (d3, w3) = rows
    res = netlist.set_net_number(p, d3.uid, w3.id, "1")
    assert w3.number == "1" and w3.number_manual
    # "3" became free when the third connection took "1", so it may be reused
    assert w1.number not in ("1", "2") and w1.number and not w1.number_manual
    assert res.renumbered == [("1", w1.number)] and res.manual_clash == 0
    assert res.net is not None and (d3.uid, w3.id) in res.net.wires
    assert w2.number == "2"
    assert not _duplicate_errors(p)


def test_a_manual_number_already_set_manually_elsewhere_is_reported_not_changed():
    p, rows = _rows(2)
    (d1, w1), (d2, w2) = rows
    netlist.set_net_number(p, d1.uid, w1.id, "L+")
    res = netlist.set_net_number(p, d2.uid, w2.id, "L+")
    assert (w1.number, w1.number_manual) == ("L+", True)      # the user's own number is not touched
    assert res.manual_clash == 1 and res.renumbered == []
    assert _duplicate_errors(p)                              # still reported by Check


def test_clearing_a_manual_number_changes_nothing_else():
    p, rows = _rows(2)
    netlist.assign_wire_numbers(p)
    (d1, w1), (d2, w2) = rows
    netlist.set_net_number(p, d1.uid, w1.id, "X9")
    before = w2.number
    res = netlist.set_net_number(p, d1.uid, w1.id, "")
    assert w1.number == "" and not w1.number_manual
    assert w2.number == before and res.renumbered == [] and res.manual_clash == 0


def test_fluid_lines_are_not_renumbered_by_a_manual_electrical_number():
    """Only electrical connections take part (hydraulic and pneumatic lines are
    never numbered, see test_hydraulic_lines_not_numbered)."""
    p, rows = _rows(1)
    d = p.sheets[0]
    v = editing.place(d, "fl.hyd.cyl.double", 600, 600)
    t = v.terminals()["A"]
    hw = editing.add_wire(d, [t, (t[0] + 40, t[1] + 40)])
    hw.number, hw.number_manual = "1", True                    # odd, but the user's
    netlist.assign_wire_numbers(p)
    res = netlist.set_net_number(p, d.uid, rows[0][1].id, "1")
    assert hw.number == "1" and res.renumbered == [] and res.manual_clash == 0


def test_gui_reports_the_renumbered_connection_and_undo_restores_both(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setenv("OPENSCHEMATIX_CONFIG_DIR", str(tmp_path / "config"))
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Tk GUI display not available: {e}")
    try:
        from openschematix.gui.app import App
        app = App(root, check_recovery=False)
        d = app.doc
        ws = []
        for k in range(2):
            r = editing.place(d, "el.resistor.iec", 100, 100 + 100 * k)
            x, y = r.terminals()["2"]
            ws.append(editing.add_wire(d, [(x, y), (x + 60, y)]))
        netlist.assign_wire_numbers(app.project)
        status = []
        monkeypatch.setattr(app, "set_status", lambda m, *a, **k: status.append(m))
        app.set_wire_number(ws[1], "1")
        assert ws[1].number == "1" and ws[0].number not in ("", "1")
        assert status and "other connection(s) that had 1 automatically" in status[-1]
        app.undo()
        w0, w1 = (app.doc.wires[w.id] for w in ws)
        assert (w0.number, w1.number, w1.number_manual) == ("1", "2", False)
        app.recovery.end()
    finally:
        root.destroy()


def test_override_uses_the_projects_own_symbols_when_another_project_is_active():
    """Codex review of #83: set_net_number must resolve terminal domains as its
    own project. Here a custom symbol id is electrical in A but hydraulic in the
    active project B; resolving through B made A's connection look hydraulic, so
    its automatic number was not moved and two connections shared it."""
    from openschematix import symbols
    from openschematix.model import Wire
    from openschematix.symbols.custom import blank_symbol, normalise

    sid = "user:numbering-scope"

    def definition(ptype, name):
        d = blank_symbol(name)
        d["id"] = sid
        d["prims"] = [{"k": "circle", "c": [0, 0], "r": 10}]
        d["pins"] = [{"id": "1", "name": "1", "x": 20, "y": 0, "dir": "r", "type": ptype}]
        return normalise(d)

    def project(ptype, name, n):
        p = new_project(name)
        p.symbols[sid] = definition(ptype, name)
        p.activate_symbols()
        d = p.sheets[0]
        ws = []
        for k in range(n):
            c = editing.place(d, sid, 100, 100 + 100 * k)
            x, y = c.terminals()["1"]
            w = Wire(d.new_id(), [(x, y), (x + 60, y)], [c.id, "1"], None)
            d.add_wire(w)
            ws.append(w)
        return p, d, ws

    try:
        a, da, (w1, w2) = project("elec.passive", "A", 2)
        netlist.assign_wire_numbers(a)
        assert (w1.number, w2.number) == ("1", "2")
        project("hyd.work", "B", 1)                          # B is now the active project
        res = netlist.set_net_number(a, da.uid, w2.id, "1")
        assert w2.number == "1" and w1.number not in ("", "1"), (w1.number, w2.number)
        assert res.renumbered == [("1", w1.number)]
    finally:
        symbols.set_project_symbols([])
