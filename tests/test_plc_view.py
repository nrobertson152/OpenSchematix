"""Showing a program as it runs. Ladder is lit by what the scan really did with its power."""
import pytest

from openschematix import plc


def ladder_params(rungs, tags=None):
    return {"di": 4, "do": 4, "ai": 0, "ao": 0, "tags": tags or {}, "program": {"pous": [{"name": "Main", "lang": "ld", "source": {"rungs": rungs}}]}}


def no(a):
    return {"t": "no", "a": a}


def nc(a):
    return {"t": "nc", "a": a}


def coil(a):
    return {"t": "coil", "a": a}


def run(params, inputs=None, scans=1):
    rt = plc.compile_params(params)
    assert rt.ok, rt.program.errors
    for k, v in (inputs or {}).items():
        rt.set_input(k, v)
    for _ in range(scans):
        rt.scan()
    return rt, rt.program.power["Main"]


def test_power_stops_at_the_first_open_contact():
    rt, power = run(ladder_params([{"items": [no("I0"), no("I1"), no("I2"), coil("Q0")]}]), {"I0": True, "I1": False, "I2": True})
    path = (0,)
    assert power[(path, 0)] == (True, True)
    assert power[(path, 1)] == (True, False)
    assert power[(path, 2)] == (False, False), "no power reached it"
    assert power[(path, 3)] == (False, False)
    assert rt.read("Q0") is False


def test_a_normally_closed_contact_passes_power_while_its_input_is_off():
    _rt, power = run(ladder_params([{"items": [nc("I0"), coil("Q0")]}]))
    assert power[((0,), 0)] == (True, True) and power[((0,), 1)] == (True, True)
    _rt, power = run(ladder_params([{"items": [nc("I0"), coil("Q0")]}]), {"I0": True})
    assert power[((0,), 0)] == (True, False)


def test_power_through_parallel_branches():
    rungs = [{"items": [{"t": "par", "branches": [[no("I0")], [no("I1"), no("I2")]]}, coil("Q0")]}]
    rt, power = run(ladder_params(rungs), {"I1": True})
    top = (0,)
    assert power[((top + ((0, 0),)), 0)] == (True, False)
    assert power[((top + ((0, 1),)), 0)] == (True, True)
    assert power[((top + ((0, 1),)), 1)] == (True, False), "the lower branch stops at I2"
    assert power[(top, 0)] == (True, False), "and nothing came out of the branches"
    assert rt.read("Q0") is False
    rt.set_input("I2", True)
    rt.scan()
    assert power[(top, 0)] == (True, True) and rt.read("Q0") is True


def test_a_later_rung_sees_what_an_earlier_one_did():
    rungs = [{"items": [no("I0"), coil("M1")]}, {"items": [no("M1"), coil("Q0")]}]
    _rt, power = run(ladder_params(rungs), {"I0": True})
    assert power[((1,), 0)] == (True, True)


def test_a_timer_passes_power_only_when_it_has_timed_out():
    rungs = [{"items": [no("I0"), {"t": "ton", "a": "T1", "pt": "T#100ms"}, coil("Q0")]}]
    rt, power = run(ladder_params(rungs), {"I0": True}, scans=2)
    assert power[((0,), 1)] == (True, False)
    for _ in range(20):
        rt.scan(10)
    assert power[((0,), 1)] == (True, True) and rt.read("Q0") is True


def test_a_reset_clears_what_was_lit():
    rt, power = run(ladder_params([{"items": [no("I0"), coil("Q0")]}]), {"I0": True})
    assert power
    rt.reset()
    assert rt.program.power["Main"] == {}


def test_watching_it_changes_nothing_a_contact_guards():
    """A display must not make an expression run that the rung protects: this one faults if it ever does."""
    rungs = [{"items": [no("I0"), {"t": "no", "a": "(1 / Zero) > 0"}, coil("Q0")]}]
    params = ladder_params(rungs)
    params["program"]["vars"] = [{"name": "Zero", "type": "INT", "init": "0"}]
    rt, power = run(params)
    assert rt.fault == "" and rt.running
    assert power[((0,), 1)] == (False, False)


# ---------------------------------------------------------------- the drawing
tk = pytest.importorskip("tkinter")


@pytest.fixture
def view():
    from openschematix.gui import plc_view, theme as th
    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"no display: {e}")
    root.geometry("900x500")
    theme = th.Theme("light", "paper") if "light" in th.THEMES else th.Theme(next(iter(th.THEMES)), "paper")
    th.apply(root, theme)
    v = plc_view.ProgramView(root, lambda: theme)
    v.pack(fill="both", expand=True)
    root.update()
    yield v, theme
    root.destroy()


def hot_items(cv, theme):
    from openschematix.gui.plc_view import _hot
    hot = _hot(theme.ui)
    return [i for i in cv.find_all() if cv.type(i) in ("line", "arc") and hot in (cv.itemcget(i, "fill") if cv.type(i) == "line" else cv.itemcget(i, "outline"))]


def test_a_rung_lights_up_as_far_as_the_power_goes(view):
    v, theme = view
    params = ladder_params([{"items": [no("I0"), no("I1"), coil("Q0")]}])
    rt = plc.compile_params(params)
    pou = plc.program_of(params)["pous"][0]
    v.show(rt, pou)
    rt.scan()
    v.refresh()
    only_to_first = len(hot_items(v.cv, theme))
    rt.set_input("I0", True)
    rt.scan()
    v.refresh()
    further = len(hot_items(v.cv, theme))
    rt.set_input("I1", True)
    rt.scan()
    v.refresh()
    to_the_coil = len(hot_items(v.cv, theme))
    assert 0 < only_to_first < further < to_the_coil


def test_a_stopped_plc_shows_nothing_lit(view):
    v, theme = view
    params = ladder_params([{"items": [no("I0"), coil("Q0")]}])
    rt = plc.compile_params(params)
    rt.set_input("I0", True)
    rt.scan()
    v.show(rt, plc.program_of(params)["pous"][0])
    assert hot_items(v.cv, theme)
    rt.running = False
    v.refresh()
    assert not hot_items(v.cv, theme)


def test_whoever_hosts_it_can_say_it_isnt_running(view):
    """A PLC on a machine can be stopped, or lose its supply, with its program still standing ready."""
    v, theme = view
    params = ladder_params([{"items": [no("I0"), coil("Q0")]}])
    rt = plc.compile_params(params)
    rt.set_input("I0", True)
    rt.scan()
    running = [True]
    v.is_running = lambda: running[0]
    v.show(rt, plc.program_of(params)["pous"][0])
    assert hot_items(v.cv, theme)
    running[0] = False
    v.refresh()
    assert rt.running and not hot_items(v.cv, theme)


def test_every_language_can_be_shown_and_a_text_one_says_it_wont_light(view):
    v, theme = view
    pous = [plc.new_pou(f"P{lang}", lang) for lang in plc.LANGUAGES]
    params = {"di": 2, "do": 2, "program": {"pous": pous}}
    rt = plc.compile_params(params)
    assert rt.ok, rt.program.errors
    rt.scan()
    for pou in plc.program_of(params)["pous"]:
        v.show(rt, pou)
        v.update()
        v.refresh(force=True)
        text = pou["lang"] in ("st", "c", "python")
        assert bool(v.text.winfo_ismapped()) == text
        assert bool(v.note.winfo_ismapped()) == text
        if text:
            assert v.text.get("1.0", "end").strip() == pou["source"].strip()


def test_a_function_block_diagram_lights_its_true_wires(view):
    v, theme = view
    src = {"blocks": [{"id": 1, "type": "input", "expr": "I0", "x": 40, "y": 40}, {"id": 2, "type": "output", "target": "Q0", "x": 300, "y": 40}],
           "wires": [{"from": [1, "OUT"], "to": [2, "IN"]}]}
    params = {"di": 2, "do": 2, "program": {"pous": [{"name": "F", "lang": "fbd", "source": src}]}}
    rt = plc.compile_params(params)
    rt.scan()
    v.show(rt, plc.program_of(params)["pous"][0])
    assert not hot_items(v.cv, theme)
    rt.set_input("I0", True)
    rt.scan()
    v.refresh()
    assert hot_items(v.cv, theme)


def test_a_chart_fills_its_active_step(view):
    from openschematix.gui.plc_view import _hot
    v, theme = view
    src = {"steps": [{"id": 1, "name": "A", "initial": True, "actions": []}, {"id": 2, "name": "B", "actions": []}],
           "transitions": [{"id": 1, "from": [1], "to": [2], "cond": "I0"}]}
    params = {"di": 2, "do": 2, "program": {"pous": [{"name": "S", "lang": "sfc", "source": src}]}}
    rt = plc.compile_params(params)
    rt.scan()
    v.show(rt, plc.program_of(params)["pous"][0])

    def filled():
        return [i for i in v.cv.find_all() if v.cv.type(i) == "rectangle" and v.cv.itemcget(i, "fill") == _hot(theme.ui)]
    assert len(filled()) == 1
    rt.set_input("I0", True)
    rt.scan()
    rt.scan()
    v.refresh()
    assert len(filled()) == 1


def test_a_damaged_program_is_only_not_shown(view):
    v, _theme = view
    params = {"di": 1, "do": 1, "program": {"pous": [{"name": "D", "lang": "ld", "source": {"rungs": "nonsense"}}]}}
    rt = plc.compile_params(params)
    assert not rt.ok
    v.show(rt, {"name": "D", "lang": "ld", "source": {"rungs": []}})
    v.show(rt, {"name": "D", "lang": "fbd", "source": {"blocks": "x"}})
    v.show(rt, {"name": "D", "lang": "sfc", "source": 3})
    v.show(rt, {"name": "D", "lang": "st", "source": None})
    v.show(None, None)
    v.refresh()
