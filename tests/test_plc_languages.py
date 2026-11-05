"""The same control logic in all six languages must behave identically, scan for scan. Then each language on its own."""
import math

import pytest

from openschematix.plc import build, check, compile_params


def params(lang, source, **extra):
    p = {"di": 4, "do": 4, "ai": 2, "ao": 1, "do_type": "source",
         "tags": {"I0": "Start", "I1": "Stop", "I2": "AtEnd", "Q0": "Run", "Q1": "Done", "AI0": "Pressure", "AO0": "Cmd"},
         "program": {"scan_ms": 10, "vars": extra.pop("vars", []),
                     "pous": [{"name": "Main", "lang": lang, "source": source}], **extra}}
    return p


def runtime(lang, source, **extra):
    rt = compile_params(params(lang, source, **extra))
    assert rt.ok, [str(d) for d in rt.program.diags]
    assert not rt.fault, rt.fault
    return rt


# A latch with a 50 ms on-delay output: Start latches Run, Stop releases it, Done follows Run after 50 ms.
LATCH = {
    "st": """
        VAR dwell : TON; END_VAR
        Run := (Start OR Run) AND NOT Stop;
        dwell(IN := Run, PT := T#50ms);
        Done := dwell.Q;
    """,
    "c": """
        static TON dwell;
        void loop(void) {
            Run = (Start || Run) && !Stop;
            Done = ton(&dwell, Run, 50);
        }
    """,
    "python": """
dwell = TON()
def loop():
    Run = (Start or Run) and not Stop
    dwell(IN=Run, PT=50)
    Done = dwell.Q
""",
    "ld": {"rungs": [
        {"items": [{"t": "par", "branches": [[{"t": "no", "a": "Start"}], [{"t": "no", "a": "Run"}]]},
                   {"t": "nc", "a": "Stop"}, {"t": "coil", "a": "Run"}]},
        {"items": [{"t": "no", "a": "Run"}, {"t": "ton", "a": "dwell", "pt": "T#50ms"}, {"t": "coil", "a": "Done"}]},
    ]},
    "fbd": {"blocks": [
        {"id": 1, "type": "input", "expr": "Start", "x": 0, "y": 0},
        {"id": 2, "type": "input", "expr": "Run", "x": 0, "y": 40},
        {"id": 3, "type": "OR", "x": 100, "y": 0},
        {"id": 4, "type": "input", "expr": "Stop", "x": 0, "y": 80},
        {"id": 5, "type": "NOT", "x": 100, "y": 80},
        {"id": 6, "type": "AND", "x": 200, "y": 0},
        {"id": 7, "type": "output", "target": "Run", "x": 300, "y": 0},
        {"id": 8, "type": "TON", "name": "dwell", "pins": {"PT": "T#50ms"}, "x": 300, "y": 80},
        {"id": 9, "type": "output", "target": "Done", "x": 400, "y": 80}],
        "wires": [{"from": [1, "OUT"], "to": [3, "IN1"]}, {"from": [2, "OUT"], "to": [3, "IN2"]},
                  {"from": [4, "OUT"], "to": [5, "IN"]}, {"from": [3, "OUT"], "to": [6, "IN1"]},
                  {"from": [5, "OUT"], "to": [6, "IN2"]}, {"from": [6, "OUT"], "to": [7, "IN"]},
                  {"from": [6, "OUT"], "to": [8, "IN"]}, {"from": [8, "Q"], "to": [9, "IN"]}]},
    "sfc": {"steps": [
        {"id": 1, "name": "Idle", "initial": True, "actions": []},
        {"id": 2, "name": "Running", "actions": [{"q": "N", "target": "Run"}, {"q": "D", "time": "T#50ms", "target": "Done"}]}],
        "transitions": [{"id": 1, "from": [1], "to": [2], "cond": "Start AND NOT Stop"},
                        {"id": 2, "from": [2], "to": [1], "cond": "Stop"}]},
}


def trace_latch(lang):
    rt = runtime(lang, LATCH[lang])
    out = []

    def scan(start=False, stop=False, n=1):
        for _ in range(n):
            rt.set_input("I0", start)
            rt.set_input("I1", stop)
            assert rt.scan(), rt.fault
            out.append((bool(rt.read("Run")), bool(rt.read("Done"))))
    scan(n=3)
    scan(start=True)
    scan(n=10)
    scan(stop=True, n=2)
    scan(n=10)
    return out


@pytest.mark.parametrize("lang", ["st", "c", "python", "ld", "fbd"])
def test_scan_based_languages_agree_scan_for_scan(lang):
    assert trace_latch(lang) == trace_latch("st")


def test_the_latch_does_what_it_says():
    t = trace_latch("st")
    assert t[:3] == [(False, False)] * 3            # nothing until Start
    assert t[3] == (True, False)                    # Start latches Run at once
    assert t[7] == (True, True) and t[6] == (True, False)    # Done 50 ms (five 10 ms scans) later
    assert t[14] == (False, False)                  # Stop drops both
    assert t[-1] == (False, False)                  # and it stays dropped once Stop is released


def test_sfc_runs_the_same_machine():
    """A chart steps at the end of a scan, so it is one scan behind the combinational forms, and otherwise the same."""
    t = trace_latch("sfc")
    assert not any(r for r, _d in t[:4])
    assert t[4][0] and not t[4][1]
    first_done = next(i for i, (_r, d) in enumerate(t) if d)
    assert first_done - 4 == 5                      # the D action came on after 50 ms of the step
    assert t[-1] == (False, False)


# ---------------------------------------------------------------- ST
@pytest.mark.parametrize("expr,expected", [
    ("7 / 2", 3), ("-7 / 2", -3), ("7 MOD 3", 1), ("-7 MOD 3", -1), ("7.0 / 2", 3.5), ("2 ** 10", 1024), ("16#FF", 255),
    ("2#1010", 10), ("1_000", 1000), ("T#1m30s", 90000), ("T#250ms", 250), ("TRUE AND FALSE", False),
    ("TRUE XOR FALSE", True), ("NOT FALSE", True), ("NOT 0", -1), ("3 > 2 AND 2 > 1", True), ("1 <> 1", False),
    ("ABS(-3)", 3), ("SQRT(16.0)", 4.0), ("MIN(3, 1, 2)", 1), ("MAX(3, 1, 2)", 3), ("LIMIT(0, 5, 3)", 3),
    ("SEL(TRUE, 1, 2)", 2), ("MUX(1, 10, 20, 30)", 20), ("SCALE(12.0, 4.0, 20.0, 0.0, 250.0)", 125.0),
    ("REAL_TO_INT(2.6)", 3), ("TO_INT(2.4)", 2), ("INT_TO_REAL(2)", 2.0), ("SHL(1, 4)", 16), ("SHR(16, 2)", 4),
    ("INT#5 + 1", 6), ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("-2 ** 2", 4),
])
def test_st_expressions(expr, expected):
    rt = runtime("st", f"VAR r : LREAL; b : BOOL; END_VAR\nresult := {expr};",
                 vars=[{"name": "result", "type": "LREAL" if not isinstance(expected, bool) else "BOOL"}])
    assert rt.scan(), rt.fault
    got = rt.read("result")
    assert got == pytest.approx(expected) if not isinstance(expected, bool) else got is expected


def test_st_integer_types_wrap_like_the_hardware():
    rt = runtime("st", """VAR a : INT := 32767; b : USINT := 255; c : SINT := 127; END_VAR
        a := a + 1; b := b + 1; c := c + 1;
        ra := a; rb := b; rc := c;""",
                 vars=[{"name": n, "type": "DINT"} for n in ("ra", "rb", "rc")])
    rt.scan()
    assert (rt.read("ra"), rt.read("rb"), rt.read("rc")) == (-32768, 0, -128)


def test_st_control_structures_and_arrays():
    rt = runtime("st", """
        VAR i, total : DINT; a : ARRAY[1..5] OF INT := [1, 2, 3]; m : ARRAY[0..1, 0..1] OF INT; END_VAR
        total := 0;
        FOR i := 1 TO 5 DO
            IF i = 4 THEN CONTINUE; END_IF;
            total := total + a[i];
        END_FOR;
        WHILE total < 10 DO total := total + 1; END_WHILE;
        REPEAT total := total + 2; UNTIL total > 12 END_REPEAT;
        FOR i := 10 TO 1 BY -3 DO m[0, 1] := i; IF i = 4 THEN EXIT; END_IF; END_FOR;
        CASE total OF
            1, 2: Q1 := FALSE;
            3..20: Q1 := TRUE;
        ELSE
            Q1 := FALSE;
        END_CASE;
        out := total; last := m[0, 1];
    """, vars=[{"name": "out", "type": "DINT"}, {"name": "last", "type": "INT"}])
    assert rt.scan(), rt.fault
    assert rt.read("out") == 14 and rt.read("last") == 4 and rt.read("Done") is True


def test_st_functions_and_function_blocks():
    src = """
FUNCTION Twice : INT
VAR_INPUT x : INT; END_VAR
Twice := x * 2;
END_FUNCTION

FUNCTION_BLOCK Blinker
VAR_INPUT en : BOOL; period : TIME; END_VAR
VAR_OUTPUT q : BOOL; END_VAR
VAR t : TON; END_VAR
t(IN := en AND NOT t.Q, PT := period);
IF t.Q THEN q := NOT q; END_IF;
END_FUNCTION_BLOCK

VAR b : Blinker; END_VAR
b(en := TRUE, period := T#30ms);
Run := b.q;
out := Twice(21);
"""
    rt = runtime("st", src, vars=[{"name": "out", "type": "INT"}])
    seen = []
    for _ in range(12):
        assert rt.scan(), rt.fault
        seen.append(rt.read("Run"))
    assert rt.read("out") == 42
    assert True in seen and False in seen       # it does blink


def test_st_direct_addresses():
    rt = runtime("st", "VAR x AT %IX0.2 : BOOL; END_VAR\n%QX0.3 := %I0 AND x; %MW2 := 5; out := %MW2;",
                 vars=[{"name": "out", "type": "INT"}])
    rt.set_input("I0", True)
    rt.set_input("I2", True)
    rt.scan()
    assert rt.read("Q3") is True and rt.read("out") == 5


def test_st_comments_nest_and_case_does_not_matter():
    rt = runtime("st", "(* outer (* inner *) still *) // line\n/* block */ RUN := start;\nrun := START OR run;")
    rt.set_input("I0", True)
    rt.scan()
    assert rt.read("Run") is True


@pytest.mark.parametrize("src,message", [
    ("Nope := TRUE;", "Nope"),
    ("Start := TRUE;", "input"),
    ("IF Run THEN", "END_IF"),
    ("Run := ;", "value"),
    ("x := FOO(1);", "x"),
    ("VAR t : TON; END_VAR t(IN := TRUE, ZZ := 1);", "ZZ"),
    ("VAR t : TON; END_VAR Run := t;", "function block"),
    ("Run := FOO(1);", "FOO"),
    ("Run := ABS(1, 2);", "ABS"),
    ("VAR a : ARRAY[0..3000000] OF INT; END_VAR", "too large"),
    ("VAR a : NOPE; END_VAR", "NOPE"),
    ("(* never closed", "comment"),
    ("Run := @;", "character"),
])
def test_st_errors_are_messages_with_a_place(src, message):
    diags = [d for d in check(params("st", src)) if d.level == "error"]
    assert diags and message in diags[0].message, [str(d) for d in diags]


def test_st_errors_give_the_line():
    d = check(params("st", "Run := TRUE;\n\nNope := FALSE;\n"))[0]
    assert d.line == 3 and d.pou == "Main"


# ---------------------------------------------------------------- function blocks themselves
def test_timer_and_counter_blocks_scan_by_scan():
    rt = runtime("st", """
        t(IN := Start, PT := T#30ms);
        f(IN := Start, PT := T#30ms);
        c(CU := Start, R := Stop, PV := 2);
        d(CD := Start, LD := Stop, PV := 2);
        ud(CU := Start, CD := Stop, PV := 1);
        r(CLK := Start); g(CLK := Start);
        s(S1 := Start, R := Stop); x(S := Start, R1 := Stop);
    """, vars=[{"name": n, "type": t} for n, t in (("t", "TP"), ("f", "TOF"), ("c", "CTU"), ("d", "CTD"), ("ud", "CTUD"),
                                                   ("r", "R_TRIG"), ("g", "F_TRIG"), ("s", "SR"), ("x", "RS"))])
    fb = {n: rt.read(n) for n in ("t", "f", "c", "d", "ud", "r", "g", "s", "x")}
    rt.set_input("I1", True)
    rt.scan()
    rt.set_input("I1", False)
    assert fb["d"].CV == 2
    rt.set_input("I0", True)
    rt.scan()
    assert fb["r"].Q and not fb["g"].Q and fb["t"].Q and fb["f"].Q and fb["c"].CV == 1 and fb["d"].CV == 1
    assert fb["s"].Q1 and fb["x"].Q1
    rt.scan()
    assert not fb["r"].Q and fb["c"].CV == 1
    rt.scan()
    rt.scan()
    assert not fb["t"].Q                        # the pulse ended after 30 ms though IN stays on
    rt.set_input("I0", False)
    rt.set_input("I1", True)
    rt.scan()
    assert fb["g"].Q and fb["f"].Q and not fb["c"].Q and fb["c"].CV == 0
    assert fb["s"].Q1 is False and fb["x"].Q1 is False
    rt.set_input("I1", False)
    for _ in range(4):
        rt.scan()
    assert not fb["f"].Q                        # off-delay ran out


def test_pid_settles_a_simple_plant():
    rt = runtime("st", """VAR p : PID; END_VAR
        p(SP := 50.0, PV := pv, KP := 2.0, KI := 2.0, KD := 0.0, LO := 0.0, HI := 100.0);
        pv := pv + (p.OUT - pv) * 0.05;""", vars=[{"name": "pv", "type": "REAL"}])
    for _ in range(1500):
        assert rt.scan(), rt.fault
    assert rt.read("pv") == pytest.approx(50.0, abs=0.5)


# ---------------------------------------------------------------- ladder
def test_ladder_edges_set_reset_and_compare():
    src = {"rungs": [
        {"items": [{"t": "rise", "a": "Start"}, {"t": "set", "a": "Run"}]},
        {"items": [{"t": "fall", "a": "Stop"}, {"t": "reset", "a": "Run"}]},
        {"items": [{"t": "cmp", "a": "Pressure", "op": ">", "b": "100"}, {"t": "coil", "a": "Done"}]},
        {"items": [{"t": "no", "a": "Run"}, {"t": "move", "a": "Cmd", "b": "Pressure / 2"}, {"t": "ncoil", "a": "Q3"}]},
    ]}
    rt = runtime("ld", src)
    rt.set_input("I0", True)
    rt.set_input("AI0", 120.0)
    rt.scan()
    assert rt.read("Run") is True and rt.read("Done") is True and rt.read("Cmd") == 60.0 and rt.read("Q3") is False
    rt.set_input("I0", False)
    rt.set_input("I1", True)
    rt.set_input("AI0", 50.0)
    rt.scan()
    assert rt.read("Run") is True and rt.read("Done") is False     # Stop has only risen
    rt.set_input("I1", False)
    rt.scan()
    assert rt.read("Run") is False and rt.read("Q3") is True


def test_ladder_nested_branches_and_undeclared_markers():
    src = {"rungs": [{"items": [
        {"t": "par", "branches": [
            [{"t": "no", "a": "Start"},
             {"t": "par", "branches": [[{"t": "no", "a": "Stop"}], [{"t": "no", "a": "AtEnd"}]]}],
            [{"t": "no", "a": "Marker1"}]]},
        {"t": "coil", "a": "Run"}]},
        {"items": [{"t": "no", "a": "I3"}, {"t": "coil", "a": "Marker1"}]}]}
    rt = runtime("ld", src)

    def run(**inputs):
        for addr in ("I0", "I1", "I2", "I3"):
            rt.set_input(addr, inputs.get(addr, False))
        rt.scan()
        return rt.read("Run")
    assert not run(I0=True)
    assert run(I0=True, I1=True)
    assert run(I0=True, I2=True)
    assert not run(I1=True, I2=True)
    run(I3=True)                                # marker on at the end of this scan: rung 1 already ran
    assert run(I3=True)


def test_ladder_counter_and_empty_rung():
    src = {"rungs": [{"items": []},
                     {"items": [{"t": "rise", "a": "Start"}, {"t": "ctu", "a": "C1", "pv": "2", "r": "Stop"},
                                {"t": "coil", "a": "Run"}]}]}
    rt = runtime("ld", src)
    for on in (True, False, True):
        rt.set_input("I0", on)
        rt.scan()
    assert rt.read("C1").CV == 2


@pytest.mark.parametrize("rung,message", [
    ({"items": [{"t": "no"}]}, "no operand"),
    ({"items": [{"t": "nope", "a": "x"}]}, "unknown element"),
    ({"items": [{"t": "coil", "a": "Start"}]}, "input"),
    ({"items": [{"t": "ton", "a": ""}]}, "instance name"),
    ({"items": [{"t": "ton", "a": "T1"}, {"t": "ctu", "a": "T1"}]}, "T1"),
    ({"items": [{"t": "par", "branches": "x"}]}, "damaged"),
    ({"items": "x"}, "must be a list"),
    ("x", "damaged"),
])
def test_ladder_problems_are_reported_with_the_rung(rung, message):
    diags = [d for d in check(params("ld", {"rungs": [rung]})) if d.level == "error"]
    assert diags and message in diags[0].message, [str(d) for d in diags]


# ---------------------------------------------------------------- function block diagram
def test_fbd_math_compare_and_negated_pin():
    src = {"blocks": [
        {"id": 1, "type": "input", "expr": "Pressure", "x": 0, "y": 0},
        {"id": 2, "type": "SCALE", "pins": {"IN_LO": "0", "IN_HI": "10", "OUT_LO": "0", "OUT_HI": "100"}, "x": 100, "y": 0},
        {"id": 3, "type": "GT", "pins": {"IN2": "50"}, "x": 200, "y": 0},
        {"id": 4, "type": "AND", "n": 3, "neg": ["IN2"], "pins": {"IN3": "TRUE"}, "x": 300, "y": 0},
        {"id": 5, "type": "input", "expr": "Stop", "x": 200, "y": 60},
        {"id": 6, "type": "output", "target": "Run", "x": 400, "y": 0}],
        "wires": [{"from": [1, "OUT"], "to": [2, "IN"]}, {"from": [2, "OUT"], "to": [3, "IN1"]},
                  {"from": [3, "OUT"], "to": [4, "IN1"]}, {"from": [5, "OUT"], "to": [4, "IN2"]},
                  {"from": [4, "OUT"], "to": [6, "IN"]}]}
    rt = runtime("fbd", src)
    rt.set_input("AI0", 6.0)
    rt.scan()
    assert rt.read("Run") is True
    rt.set_input("I1", True)
    rt.scan()
    assert rt.read("Run") is False


def test_fbd_runs_in_signal_order_whatever_the_list_order():
    src = {"blocks": [{"id": 3, "type": "output", "target": "Run", "x": 200, "y": 0},
                      {"id": 2, "type": "NOT", "x": 100, "y": 0},
                      {"id": 1, "type": "input", "expr": "Start", "x": 0, "y": 0}],
           "wires": [{"from": [2, "OUT"], "to": [3, "IN"]}, {"from": [1, "OUT"], "to": [2, "IN"]}]}
    rt = runtime("fbd", src)
    rt.set_input("I0", True)
    rt.scan()
    assert rt.read("Run") is False              # correct on the very first scan: no stale value


def test_fbd_feedback_loop_uses_the_last_scan():
    src = {"blocks": [{"id": 1, "type": "input", "expr": "Start", "x": 0, "y": 0},
                      {"id": 2, "type": "OR", "x": 100, "y": 0},
                      {"id": 3, "type": "output", "target": "Run", "x": 200, "y": 0}],
           "wires": [{"from": [1, "OUT"], "to": [2, "IN1"]}, {"from": [2, "OUT"], "to": [2, "IN2"]},
                     {"from": [2, "OUT"], "to": [3, "IN"]}]}
    rt = runtime("fbd", src)
    rt.set_input("I0", True)
    rt.scan()
    rt.set_input("I0", False)
    rt.scan()
    assert rt.read("Run") is True               # it latches round the loop


@pytest.mark.parametrize("source,message", [
    ({"blocks": [{"id": 1, "type": "ZZZ"}], "wires": []}, "ZZZ"),
    ({"blocks": [{"id": 1, "type": "input"}], "wires": []}, "nothing to read"),
    ({"blocks": [{"id": 1, "type": "output"}], "wires": []}, "nowhere to write"),
    ({"blocks": [{"id": 1, "type": "AND"}, {"id": 1, "type": "OR"}], "wires": []}, "two blocks"),
    ({"blocks": [{"id": 1, "type": "AND"}], "wires": [{"from": [9, "OUT"], "to": [1, "IN1"]}]}, "damaged"),
    ({"blocks": "x", "wires": []}, "damaged"),
    ({"blocks": [{"id": 1, "type": "input", "expr": "A"}, {"id": 2, "type": "input", "expr": "B"},
                 {"id": 3, "type": "NOT"}], "wires": [{"from": [1, "OUT"], "to": [3, "IN"]},
                                                      {"from": [2, "OUT"], "to": [3, "IN"]}]}, "two wires"),
])
def test_fbd_problems_are_reported(source, message):
    diags = [d for d in check(params("fbd", source)) if d.level == "error"]
    assert diags and message in diags[0].message, [str(d) for d in diags]


# ---------------------------------------------------------------- sequential function chart
def chart():
    return {"steps": [
        {"id": 1, "name": "Idle", "initial": True, "actions": [{"q": "N", "target": "Q3"}]},
        {"id": 2, "name": "A", "actions": [{"q": "N", "target": "Run"}, {"q": "P", "code": "Count := Count + 1;"},
                                           {"q": "S", "target": "Q2"}]},
        {"id": 3, "name": "B1", "actions": [{"q": "L", "time": "T#30ms", "target": "Done"}]},
        {"id": 4, "name": "B2", "actions": [{"q": "R", "target": "Q2"}]},
        {"id": 5, "name": "End", "actions": [{"q": "P0", "code": "Leaves := Leaves + 1;"}]}],
        "transitions": [{"id": 1, "from": [1], "to": [2], "cond": "Start"},
                        {"id": 2, "from": [2], "to": [3, 4], "cond": "A.T >= T#20ms"},
                        {"id": 3, "from": [3, 4], "to": [5], "cond": "AtEnd"},
                        {"id": 4, "from": [5], "to": [1], "cond": "TRUE"}]}


def test_sfc_parallel_branch_convergence_timers_and_qualifiers():
    rt = runtime("sfc", chart(), vars=[{"name": "Count", "type": "INT"}, {"name": "Leaves", "type": "INT"}])
    rt.scan()
    assert rt.read("Q3") is True and rt.read("Idle") is True
    rt.set_input("I0", True)
    rt.scan()                                   # Idle's transition fires at the end of this scan
    rt.set_input("I0", False)
    rt.scan()
    assert rt.read("Run") is True and rt.read("Q3") is False and rt.read("Count") == 1 and rt.read("Q2") is True
    rt.scan()
    assert rt.read("Count") == 1                # P ran once
    rt.scan()                                   # A has now been active 30 ms: both branches start
    assert rt.read("B1") is True and rt.read("B2") is True and rt.read("A") is False
    rt.scan()
    assert rt.read("Done") is True and rt.read("Q2") is False   # L on; R reset the stored S
    rt.scan()
    rt.scan()
    rt.scan()
    assert rt.read("Done") is False             # L ran out after 30 ms
    assert rt.read("End") is False              # waits for AtEnd with both branches done
    rt.set_input("I2", True)
    rt.scan()
    rt.set_input("I2", False)
    assert rt.read("End") is True
    rt.scan()
    assert rt.read("Idle") is True and rt.read("End") is False
    rt.scan()
    assert rt.read("Leaves") == 1               # P0 ran on the way out


def test_sfc_step_readable_from_another_program():
    p = params("sfc", {"steps": [{"id": 1, "name": "S1", "initial": True, "actions": []}], "transitions": []})
    p["program"]["pous"].append({"name": "Watch", "lang": "st", "source": "Run := S1.X; x := S1.T;"})
    p["program"]["vars"] = [{"name": "x", "type": "TIME"}]
    rt = compile_params(p)
    assert rt.ok, [str(d) for d in rt.program.diags]
    rt.scan()
    rt.scan()
    assert rt.read("Run") is True and rt.read("x") == 20


@pytest.mark.parametrize("source,message", [
    ({"steps": [{"id": 1, "name": "A"}], "transitions": []}, "initial"),
    ({"steps": [{"id": 1, "name": "A", "initial": True}, {"id": 1, "name": "B"}], "transitions": []}, "two steps"),
    ({"steps": [{"id": 1, "name": "A", "initial": True}, {"id": 2, "name": "a"}], "transitions": []}, "two steps"),
    ({"steps": [{"id": 1, "name": "1a", "initial": True}], "transitions": []}, "name"),
    ({"steps": [{"id": 1, "name": "Start", "initial": True}], "transitions": []}, "same name"),
    ({"steps": [{"id": 1, "name": "A", "initial": True}], "transitions": [{"id": 1, "from": [1], "to": [9], "cond": "x"}]}, "no step"),
    ({"steps": [{"id": 1, "name": "A", "initial": True}], "transitions": [{"id": 1, "from": [1], "to": [1]}]}, "condition"),
    ({"steps": [{"id": 1, "name": "A", "initial": True}], "transitions": [{"id": 1, "from": [1], "to": [1], "cond": "Nope"}]}, "Nope"),
    ({"steps": [{"id": 1, "name": "A", "initial": True, "actions": [{"q": "Z", "target": "Run"}]}], "transitions": []}, "qualifier"),
    ({"steps": [{"id": 1, "name": "A", "initial": True, "actions": [{"q": "L", "time": "x", "target": "Run"}]}], "transitions": []}, "time"),
    ({"steps": [{"id": 1, "name": "A", "initial": True, "actions": [{"q": "N"}]}], "transitions": []}, "one or the other"),
    ({"steps": "x", "transitions": []}, "damaged"),
])
def test_sfc_problems_are_reported(source, message):
    diags = [d for d in check(params("sfc", source)) if d.level == "error"]
    assert diags and message in diags[0].message, [str(d) for d in diags]


# ---------------------------------------------------------------- C
def c_result(body, globals_="", typ="double"):
    src = f"{globals_}\n{typ} result;\nvoid loop(void) {{\n{body}\n}}\nvoid setup(void) {{}}\n"
    p = params("c", src)
    rt = compile_params(p)
    assert rt.ok, [str(d) for d in rt.program.diags]
    assert rt.scan(), rt.fault
    return next(pou for pou in rt.program.pous).frame["result"]


@pytest.mark.parametrize("expr,expected", [
    ("7 / 2", 3), ("-7 / 2", -3), ("7 % 3", 1), ("-7 % 3", -1), ("7.0 / 2", 3.5), ("1 << 4", 16), ("0xFF & 0x0F", 15),
    ("0b101 | 2", 7), ("5 ^ 1", 4), ("~0", -1), ("!3", 0), ("3 > 2 && 1 < 2", 1), ("3 < 2 || 0", 0), ("1 ? 10 : 20", 10),
    ("(int)2.9", 2), ("(uint8_t)300", 44), ("(float)1 / 2", 0.5), ("sizeof(int)", 4), ("sizeof(uint16_t)", 2),
    ("'A'", 65), ("010", 8), ("sqrt(16.0)", 4.0), ("fabs(-2.5)", 2.5), ("pow(2.0, 3.0)", 8.0), ("floor(2.7)", 2),
    ("min(3, 1)", 1), ("max(3, 1)", 3), ("limit(0, 5, 3)", 3), ("scale(12.0, 4.0, 20.0, 0.0, 250.0)", 125.0),
    ("true + true", 2), ("(1, 2)", 2),
])
def test_c_expressions(expr, expected):
    assert c_result(f"result = {expr};") == pytest.approx(expected)


def test_c_integer_widths_wrap_and_floats_truncate():
    assert c_result("int8_t a = 127; a++; result = a;") == -128
    assert c_result("uint8_t a = 200; a += 100; result = a;") == 44
    assert c_result("int a = 3.9; result = a;") == 3
    assert c_result("unsigned int a = -1; result = a;") == 4294967295
    assert c_result("int a = 2147483647; a = a + 1; result = a;") == -2147483648


def test_c_statements_and_functions():
    src = """
int fact(int n) { return n <= 1 ? 1 : n * fact(n - 1); }
float avg(const float *v, int n) { float s = 0; for (int i = 0; i < n; i++) s += v[i]; return s / n; }
void bump(int *p) { *p = *p + 1; }
struct point { int x; float y; };
typedef struct point point_t;
#define SIZE 4
#define DOUBLE_SIZE (SIZE * 2)
int table[SIZE] = {1, 2, 3};
int grid[2][3];
double a, b, c, d, e, f, g, h;
void loop(void) {
    int i = 0, total = 0;
    while (i < 3) { total += table[i]; i++; }
    do { total += 10; } while (0);
    for (;;) { total++; if (total > 20) break; else continue; }
    switch (total) { case 21: total = 100; case 22: total++; break; case 23: total = 0; break; default: total = -1; }
    a = total;
    b = fact(5);
    float vals[] = {1.0, 2.0, 6.0};
    c = avg(vals, 3);
    int v = 1; bump(&v); bump(&v); d = v;
    point_t p = {3, 1.5}; point_t q; q = p; q.x = 9; e = p.x + q.x;
    point_t *pp = &p; pp->y = 2.5; f = p.y;
    grid[1][2] = 7; g = grid[1][2] + DOUBLE_SIZE;
    int *w = table; w = w + 1; h = *w + w[1];
}
"""
    rt = compile_params(params("c", src))
    assert rt.ok, [str(d) for d in rt.program.diags]
    assert rt.scan(), rt.fault
    fr = rt.program.pous[0].frame
    assert fr["a"] == 101 and fr["b"] == 120 and fr["c"] == 3.0 and fr["d"] == 3 and fr["e"] == 12
    assert fr["f"] == 2.5 and fr["g"] == 15 and fr["h"] == 5


def test_c_static_locals_and_setup_persist_across_scans():
    src = """
int seen;
void setup(void) { seen = 100; }
void loop(void) { static int n = 5; n++; seen = seen + 1; Cmd = n; }
"""
    rt = runtime("c", src)
    rt.scan()
    rt.scan()
    assert rt.read("Cmd") == 7.0 and rt.program.pous[0].frame["seen"] == 102


def test_c_time_and_blocks():
    src = """
TON t; CTU c; R_TRIG r; F_TRIG f; SR s; RS x; PID p; TOF o; TP q; CTD d;
void loop(void) {
    Run = ton(&t, Start, 20);
    Done = millis() >= 30;
    ctu(&c, Start, Stop, 1);
    Q2 = c.Q;
    r_trig(&r, Start); f_trig(&f, Start); sr(&s, Start, Stop); rs(&x, Start, Stop);
    pid(&p, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 100.0);
    tof(&o, Start, 10); tp(&q, Start, 10); ctd(&d, Start, Stop, 3);
    plc_log("hello");
}
"""
    rt = runtime("c", src)
    rt.set_input("I0", True)
    rt.scan()
    assert not rt.read("Run") and rt.read("Q2") is True
    rt.scan()
    assert rt.read("Run") and not rt.read("Done")
    rt.scan()
    rt.scan()
    assert rt.read("Done") and "hello" in rt.ctx.messages


@pytest.mark.parametrize("src,message", [
    ("void setup(void) {}", "loop"),
    ("void loop(int a) {}", "no arguments"),
    ("void loop(void) { Start = 1; }", "input"),
    ("void loop(void) { nope = 1; }", "nope"),
    ("void loop(void) { goto x; }", "goto"),
    ("void loop(void) { int a[3] = {1,2,3,4}; }", "too many"),
    ("void loop(void) { foo(); }", "foo"),
    ("#ifdef X\nvoid loop(void) {}\n#endif", "#ifdef"),
    ("#define F(x) x\nvoid loop(void) {}", "macros"),
    ("/* open", "comment"),
    ("void loop(void) { int x = ; }", "value"),
    ("void loop(void) { return 1; }", "void"),
    ("int a[99999999]; void loop(void) {}", "1 to"),
    ("int Run; void loop(void) {}", "already"),
    ("void loop(void) {", "}"),
    ("void f(void); void loop(void) { }", "no body"),
    ("void loop(void) { case 1: ; }", "switch"),
    ("void loop(void) { int x; int x; }", "twice"),
])
def test_c_errors_are_messages(src, message):
    diags = [d for d in check(params("c", src)) if d.level == "error"]
    assert diags and message in diags[0].message, [str(d) for d in diags]


def test_c_errors_give_the_line():
    d = check(params("c", "void loop(void) {\n  Run = 1;\n  Nope = 2;\n}\n"))[0]
    assert d.line == 3


@pytest.mark.parametrize("body,message", [
    ("int a[3]; a[5] = 1;", "index"), ("int a[3]; Cmd = a[3];", "index"), ("int z = 0; Cmd = 1 / z;", "zero"),
    ("int *p = NULL; *p = 1;", "null"), ("while (1) { }", "watchdog"), ("for (;;) { }", "watchdog"),
    ("int a[2]; int *p = a; p = p + 5; *p = 1;", "outside"), ("Cmd = sqrt(-1.0);", "sqrt"), ("rec(0);", "deeply"),
])
def test_c_runtime_faults_stop_the_plc_with_a_reason(body, message):
    rt = runtime("c", "void rec(int n) { rec(n + 1); }\nvoid loop(void) {" + body + "}")
    assert rt.scan() is False
    assert message in rt.fault and rt.running is False


# ---------------------------------------------------------------- Python
def test_python_runs_top_to_bottom_when_there_is_no_loop():
    rt = runtime("python", "Run = Start and not Stop\nDone = Pressure > 100\nCmd = Pressure * 0.5\n")
    rt.set_input("I0", True)
    rt.set_input("AI0", 120.0)
    rt.scan()
    assert rt.read("Run") is True and rt.read("Done") is True and rt.read("Cmd") == 60.0


def test_python_language_features():
    src = """
import math
from math import sqrt, pi

history = []
counts = {"a": 0}

def area(r, factor=1):
    return pi * r ** 2 * factor

def setup():
    global started
    started = 42

def loop():
    global total, name
    history.append(Pressure)
    if len(history) > 3:
        history.pop(0)
    total = sum(history) / len(history)
    counts["a"] += 1
    values = [x * 2 for x in range(5) if x % 2 == 0]
    a, b = values[0], values[-1]
    name = "tick " + str(counts["a"])
    i = 0
    while True:
        i += 1
        if i > 3:
            break
    for k, v in enumerate([10, 20]):
        if v == 20:
            found = k
    Run = 1 < 2 < 3 and "x" in "xyz"
    Done = isclose(area(1.0), 3.14159, 0.01)
    Cmd = max(a, b, found) + round(sqrt(16)) + int(math.floor(1.9)) + len(values) + abs(-1) + min([3, 2])
    Q2 = started == 42 and not None and [1, 2] == [1, 2] and (1, 2)[1] == 2 and {"k": 1}.get("k") == 1

def isclose(x, y, tol):
    return abs(x - y) < tol
"""
    rt = runtime("python", src)
    rt.set_input("AI0", 3.0)
    assert rt.scan(), rt.fault
    assert rt.read("Run") is True and rt.read("Done") is True and rt.read("Q2") is True
    assert rt.read("Cmd") == 8 + 4 + 1 + 3 + 1 + 2
    frame = rt.program.pous[0].frame
    assert frame["total"] == 3.0 and frame["name"] == "tick 1"
    rt.scan()
    assert frame["name"] == "tick 2"            # variables persist between scans


def test_python_function_blocks_and_print():
    src = """
t = TON()
c = CTU()
def loop():
    t(IN=Start, PT=20)
    c(CU=Start, R=Stop, PV=1)
    Run = t.Q
    Q2 = c.CV == 1
    print("et", t.ET)
"""
    rt = runtime("python", src)
    rt.set_input("I0", True)
    rt.scan()
    assert not rt.read("Run") and rt.read("Q2") is True and rt.ctx.messages[-1] == "et 10"
    rt.scan()
    assert rt.read("Run")


def test_python_tags_are_global_in_a_function_without_saying_so():
    rt = runtime("python", "def loop():\n    Run = True\n")
    rt.scan()
    assert rt.read("Run") is True


@pytest.mark.parametrize("src,message", [
    ("import os", "import math"),
    ("from os import path", "from math"),
    ("class A: pass", "classes"),
    ("x = lambda: 1", "lambda"),
    ("try:\n  pass\nexcept Exception:\n  pass", "try"),
    ("with x as y:\n  pass", "with"),
    ("def f():\n  yield 1", "generators"),
    ("eval('1')", "eval"),
    ("exec('1')", "exec"),
    ("open('/etc/passwd')", "open"),
    ("getattr(1, 'real')", "getattr"),
    ("__import__('os')", "__import__"),
    ("x = (1).__class__", "__class__"),
    ("x = [].__class__.__bases__", "__"),
    ("x = __builtins__", "__builtins__"),
    ("x = math.factorial(9)", "math.factorial"),
    ("def f():\n  def g():\n    pass", "inside"),
    ("x = {1, 2}", "sets"),
    ("Start = True", "input"),
    ("x = nope", "nope"),
    ("return 1", "return"),
    ("x = (", "never closed"),
    ("@d\ndef f():\n  pass", "decorators"),
    ("x = f'{1:>9999999}'", "format"),
    ("del x", "del"),
    ("global x\nx += 1\nimport sys", "import math"),
])
def test_python_things_a_drawing_must_not_be_able_to_do_are_refused_at_build_time(src, message):
    diags = [d for d in check(params("python", src)) if d.level == "error"]
    assert diags and message in diags[0].message, [str(d) for d in diags]


def test_python_errors_give_the_line():
    assert check(params("python", "Run = True\n\nimport os\n"))[0].line == 3
