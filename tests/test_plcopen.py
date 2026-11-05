"""Reading PLCopen XML. Each program is run after it's imported: what matters is that it does what the file says."""
import pytest

from openschematix import plc
from openschematix.plc import plcopen

NS = 'xmlns="http://www.plcopen.org/xml/tc6_0201" xmlns:xhtml="http://www.w3.org/1999/xhtml"'


def project(pous="", instances="", types=""):
    return (f'<?xml version="1.0" encoding="utf-8"?><project {NS}><fileHeader companyName="x" productName="y" productVersion="1" creationDateTime="2026-01-01T00:00:00"/>'
            f'<contentHeader name="t"><coordinateInfo/></contentHeader><types><dataTypes>{types}</dataTypes><pous>{pous}</pous></types>'
            f'<instances><configurations>{instances}</configurations></instances></project>').encode("utf-8")


def var(name, typ="BOOL", address="", init=""):
    at = f' address="{address}"' if address else ""
    start = f'<initialValue><simpleValue value="{init}"/></initialValue>' if init else ""
    t = f'<derived name="{typ}"/>' if typ not in ("BOOL", "INT", "REAL", "TIME", "DINT") else f"<{typ}/>"
    return f'<variable name="{name}"{at}><type>{t}</type>{start}</variable>'


def pou(name, body, variables="", kind="program", extra=""):
    iface = f"<interface>{extra}<localVars>{variables}</localVars></interface>"
    return f'<pou name="{name}" pouType="{kind}">{iface}<body>{body}</body></pou>'


def st(text):
    return f'<ST><xhtml:p><![CDATA[{text}]]></xhtml:p></ST>'


def load(data, **counts):
    imported = plcopen.parse(data)
    params = plc.default_params()
    params.update(counts)
    plcopen.merge(params, imported, replace=True)
    return imported, params


def run(params, **inputs):
    rt = plc.compile_params(params)
    assert rt.ok, [str(d) for d in rt.program.errors]
    for k, v in inputs.items():
        rt.set_input(k, v)
    rt.scan()
    return rt


# ---------------------------------------------------------------- structured text
def test_a_structured_text_program():
    data = project(pou("Main", st("Out1 := Start AND NOT Stop;\nCount := Count + 1;"),
                       var("Start", address="%IX0.0") + var("Stop", address="%IX0.1") + var("Out1", address="%QX0.0") + var("Count", "INT")))
    imported, params = load(data)
    assert [p["lang"] for p in imported.pous] == ["st"]
    assert imported.tags == {"I0": "Start", "I1": "Stop", "Q0": "Out1"}
    rt = run(params, I0=True)
    assert rt.read("Q0") is True
    rt.set_input("I1", True)
    rt.scan()
    assert rt.read("Q0") is False


def test_addresses_are_pins_and_the_block_grows_to_fit():
    data = project(pou("Main", st("Q := A;"), var("A", address="%IX1.2") + var("Q", address="%QX2.0") + var("P", "REAL", address="%IW3")))
    imported, params = load(data, di=1, do=1, ai=0, ao=0)
    assert imported.tags == {"I10": "A", "Q16": "Q", "AI3": "P"}
    assert params["di"] == 11 and params["do"] == 17 and params["ai"] == 4
    assert any("11 digital inputs" in n for n in imported.notes)
    assert run(params, I10=True).read("Q16") is True


def test_an_address_too_high_takes_the_next_free_pin_and_says_so():
    data = project(pou("Main", st("Q := A;"), var("A", address="%IX100.0") + var("Q", address="%QX0.1.2.3")))
    imported, params = load(data)
    assert imported.tags == {"I0": "A", "Q0": "Q"}
    assert any("%IX100.0 is on I0" in n for n in imported.notes)
    assert run(params, I0=True).read("Q0") is True


def test_an_address_written_in_the_text_is_the_pin():
    data = project(pou("Main", st("%QX0.1 := %IX100.0 AND TRUE;")))
    _imported, params = load(data, do=4, di=4)
    assert run(params, I0=True).read("Q1") is True


def test_a_function_and_a_function_block_written_in_text():
    f = pou("Twice", st("Twice := A * 2;"), "", "function", '<returnType><INT/></returnType><inputVars>' + var("A", "INT") + "</inputVars>")
    b = pou("Latch", st("Q := (Q OR Set1) AND NOT Rst;"), "", "functionBlock",
            "<inputVars>" + var("Set1") + var("Rst") + "</inputVars><outputVars>" + var("Q") + "</outputVars>")
    m = pou("Main", st("L1(Set1 := %IX0.0, Rst := %IX0.1);\nOut1 := L1.Q;\nN := Twice(21);"), var("L1", "Latch") + var("Out1", address="%QX0.0") + var("N", "INT"))
    imported, params = load(project(f + b + m))
    assert [p["name"] for p in imported.pous][-1] == "Main", "what the program needs comes first"
    rt = run(params, I0=True)
    assert rt.read("Q0") is True
    rt.set_input("I0", False)
    rt.scan()
    assert rt.read("Q0") is True, "it latched"


# ---------------------------------------------------------------- ladder
def rail(i=1):
    return f'<leftPowerRail localId="{i}" height="20" width="10"><position x="0" y="{i * 10}"/><connectionPointOut formalParameter=""/></leftPowerRail>'


def into(*refs):
    return "<connectionPointIn>" + "".join(f'<connection refLocalId="{r}"/>' for r in refs) + "</connectionPointIn>"


def contact(i, name, *refs, negated=False, edge=""):
    extra = (' negated="true"' if negated else "") + (f' edge="{edge}"' if edge else "")
    return f'<contact localId="{i}"{extra}><position x="{i * 10}" y="50"/>{into(*refs)}<connectionPointOut/><variable>{name}</variable></contact>'


def coil(i, name, *refs, storage="", y=50):
    extra = f' storage="{storage}"' if storage else ""
    return f'<coil localId="{i}"{extra}><position x="500" y="{y}"/>{into(*refs)}<connectionPointOut/><variable>{name}</variable></coil>'


def ladder(*elements):
    return "<LD>" + "".join(elements) + "</LD>"


PINS = var("A", address="%IX0.0") + var("B", address="%IX0.1") + var("C", address="%IX0.2") + var("X", address="%QX0.0") + var("Y", address="%QX0.1")


def test_a_rung():
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1), contact(3, "B", 2, negated=True), coil(4, "X", 3)), PINS))
    imported, params = load(data)
    assert imported.pous[0]["lang"] == "ld"
    items = imported.pous[0]["source"]["rungs"][0]["items"]
    assert [i["t"] for i in items] == ["no", "nc", "coil"] and items[0]["a"] == "A"
    assert run(params, I0=True).read("Q0") is True
    assert run(params, I0=True, I1=True).read("Q0") is False


def test_parallel_contacts_share_what_comes_before_them():
    """A then (B or C) then X. The A isn't there twice."""
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1), contact(3, "B", 2), contact(4, "C", 2), coil(5, "X", 3, 4)), PINS))
    imported, params = load(data)
    items = imported.pous[0]["source"]["rungs"][0]["items"]
    assert [i["t"] for i in items] == ["no", "par", "coil"]
    assert run(params, I0=True, I1=True).read("Q0") is True
    assert run(params, I0=True, I2=True).read("Q0") is True
    assert run(params, I1=True, I2=True).read("Q0") is False


def test_a_seal_in():
    """(A or X) and not B: the classic latch, with a contact on its own coil."""
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1), contact(3, "X", 1), contact(4, "B", 2, 3, negated=True), coil(5, "X", 4)), PINS))
    _imported, params = load(data)
    rt = run(params, I0=True)
    assert rt.read("Q0") is True
    rt.set_input("I0", False)
    rt.scan()
    assert rt.read("Q0") is True
    rt.set_input("I1", True)
    rt.scan()
    assert rt.read("Q0") is False


def test_coils_on_one_power_are_one_rung():
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1), coil(3, "X", 2), coil(4, "Y", 2, y=90)), PINS))
    imported, params = load(data)
    rungs = imported.pous[0]["source"]["rungs"]
    assert len(rungs) == 1 and [i["t"] for i in rungs[0]["items"]] == ["no", "coil", "coil"]
    rt = run(params, I0=True)
    assert rt.read("Q0") is True and rt.read("Q1") is True


def test_set_and_reset_coils():
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1), coil(3, "X", 2, storage="set"), contact(4, "B", 1), coil(5, "X", 4, storage="reset", y=90)), PINS))
    _imported, params = load(data)
    rt = run(params, I0=True)
    rt.set_input("I0", False)
    rt.scan()
    assert rt.read("Q0") is True
    rt.set_input("I1", True)
    rt.scan()
    assert rt.read("Q0") is False


def timer_block(i, power, name="T1", pt="T#50ms"):
    return (f'<inVariable localId="{i + 1}"><position x="0" y="90"/><connectionPointOut/><expression>{pt}</expression></inVariable>'
            f'<block localId="{i}" typeName="TON" instanceName="{name}"><position x="100" y="50"/><inputVariables>'
            f'<variable formalParameter="IN">{into(power)}</variable><variable formalParameter="PT">{into(i + 1)}</variable></inputVariables><inOutVariables/>'
            '<outputVariables><variable formalParameter="Q"><connectionPointOut/></variable><variable formalParameter="ET"><connectionPointOut/></variable></outputVariables></block>')


def test_a_timer_on_a_rung():
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1), timer_block(3, 2), coil(5, "X", 3)), PINS + var("T1", "TON")))
    imported, params = load(data)
    assert [i["t"] for i in imported.pous[0]["source"]["rungs"][0]["items"]] == ["no", "ton", "coil"]
    rt = run(params, I0=True)
    assert rt.read("Q0") is False
    for _ in range(10):
        rt.scan(10)
    assert rt.read("Q0") is True


def test_a_timer_feeding_two_paths_runs_once_a_scan():
    """It gets a rung of its own, or it would count double."""
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1), timer_block(3, 2), contact(5, "B", 3), contact(6, "C", 3),
                                      coil(7, "X", 5), coil(8, "Y", 6, y=90)), PINS + var("T1", "TON")))
    imported, params = load(data)
    rungs = imported.pous[0]["source"]["rungs"]
    timers = [i for r in rungs for i in r["items"] if i["t"] == "ton"]
    assert len(timers) == 1
    rt = run(params, I0=True, I1=True)
    for _ in range(3):
        rt.scan(10)
    assert rt.read("Q0") is False, "50 ms hasn't gone yet: it would have, if it ran twice a scan"
    for _ in range(2):
        rt.scan(10)
    assert rt.read("Q0") is True


def test_a_rising_edge_contact():
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1, edge="rising"), coil(3, "X", 2)), PINS))
    _imported, params = load(data)
    rt = run(params, I0=True)
    assert rt.read("Q0") is True
    rt.scan()
    assert rt.read("Q0") is False


def test_a_rung_that_runs_in_a_circle_is_left_out_and_said():
    data = project(pou("Main", ladder(rail(), contact(2, "A", 3), contact(3, "B", 2), coil(4, "X", 3)), PINS))
    imported, params = load(data)
    assert any("circle" in n for n in imported.notes)
    run(params)


def test_ladder_with_a_block_a_rung_cant_hold_is_written_out():
    add = ('<inVariable localId="5"><position x="0" y="90"/><connectionPointOut/><expression>N</expression></inVariable>'
           '<block localId="6" typeName="ADD"><position x="100" y="50"/><inputVariables><variable formalParameter="EN">' + into(2) + '</variable>'
           '<variable formalParameter="IN1">' + into(5) + '</variable><variable formalParameter="IN2">' + into(5) + '</variable></inputVariables><inOutVariables/>'
           '<outputVariables><variable formalParameter="OUT"><connectionPointOut/></variable></outputVariables></block>'
           '<outVariable localId="7"><position x="300" y="50"/>' + into(6) + '<expression>M</expression></outVariable>')
    data = project(pou("Main", ladder(rail(), contact(2, "A", 1), add), PINS + var("N", "INT", init="21") + var("M", "REAL", address="%QW0")))
    imported, params = load(data, ao=1)
    assert imported.pous[0]["lang"] == "st"
    assert any("can't hold" in n for n in imported.notes)
    assert run(params).read("AO0") == 42


# ---------------------------------------------------------------- function block diagrams
def invar(i, text, x=0, y=50):
    return f'<inVariable localId="{i}"><position x="{x}" y="{y}"/><connectionPointOut/><expression>{text}</expression></inVariable>'


def outvar(i, text, ref, pin=""):
    p = f' formalParameter="{pin}"' if pin else ""
    return f'<outVariable localId="{i}"><position x="400" y="50"/><connectionPointIn><connection refLocalId="{ref}"{p}/></connectionPointIn><expression>{text}</expression></outVariable>'


def block(i, typ, pins, outs=("OUT",), name="", negate=()):
    ins = "".join(f'<variable formalParameter="{p}"{" negated=" + chr(34) + "true" + chr(34) if p in negate else ""}>{into(r)}</variable>' for p, r in pins)
    out = "".join(f'<variable formalParameter="{o}"><connectionPointOut/></variable>' for o in outs)
    n = f' instanceName="{name}"' if name else ""
    return f'<block localId="{i}" typeName="{typ}"{n}><position x="200" y="50"/><inputVariables>{ins}</inputVariables><inOutVariables/><outputVariables>{out}</outputVariables></block>'


def test_a_function_block_diagram_stays_a_diagram():
    body = "<FBD>" + invar(1, "A") + invar(2, "B", y=90) + block(3, "AND", (("IN1", 1), ("IN2", 2))) + outvar(4, "X", 3) + "</FBD>"
    imported, params = load(project(pou("Main", body, PINS)))
    assert imported.pous[0]["lang"] == "fbd"
    src = imported.pous[0]["source"]
    assert {b["type"] for b in src["blocks"]} == {"input", "AND", "output"}
    assert run(params, I0=True, I1=True).read("Q0") is True
    assert run(params, I0=True).read("Q0") is False


def test_a_negated_input_and_a_timer_block_in_a_diagram():
    body = "<FBD>" + invar(1, "A") + invar(2, "T#30ms", y=90) + block(3, "TON", (("IN", 1), ("PT", 2)), ("Q", "ET"), "T1") + invar(5, "B", y=130) + \
        block(4, "AND", (("IN1", 3), ("IN2", 5)), negate=("IN2",)) + outvar(6, "X", 4) + "</FBD>"
    imported, params = load(project(pou("Main", body, PINS + var("T1", "TON"))))
    assert imported.pous[0]["lang"] == "fbd"
    rt = run(params, I0=True)
    for _ in range(5):
        rt.scan(10)
    assert rt.read("Q0") is True
    rt.set_input("I1", True)
    rt.scan(10)
    rt.scan(10)
    assert rt.read("Q0") is False


def test_connectors_join_a_diagram():
    body = ("<FBD>" + invar(1, "A") + f'<connector name="c1" localId="2"><position x="100" y="50"/>{into(1)}</connector>'
            '<continuation name="c1" localId="3"><position x="200" y="50"/><connectionPointOut/></continuation>' + outvar(4, "X", 3) + "</FBD>")
    _imported, params = load(project(pou("Main", body, PINS)))
    assert run(params, I0=True).read("Q0") is True


def test_a_function_block_of_your_own_comes_across_as_text_and_runs():
    fb = pou("Inv", st("OUT1 := NOT IN1;"), "", "functionBlock", "<inputVars>" + var("IN1") + "</inputVars><outputVars>" + var("OUT1") + "</outputVars>")
    body = "<FBD>" + invar(1, "A") + block(2, "Inv", (("IN1", 1),), ("OUT1",), "I1x") + outvar(3, "X", 2, "OUT1") + "</FBD>"
    imported, params = load(project(fb + pou("Main", body, PINS + var("I1x", "Inv"))))
    main = next(p for p in imported.pous if p["name"] == "Main")
    assert main["lang"] == "st" and any("structured text" in n for n in imported.notes)
    assert run(params).read("Q0") is True
    assert run(params, I0=True).read("Q0") is False


def test_a_function_block_drawn_as_a_diagram_comes_across_as_text():
    body = "<FBD>" + invar(1, "IN1") + block(2, "NOT", (("IN", 1),)) + outvar(3, "OUT1", 2) + "</FBD>"
    fb = pou("Inv", body, "", "functionBlock", "<inputVars>" + var("IN1") + "</inputVars><outputVars>" + var("OUT1") + "</outputVars>")
    m = pou("Main", st("I1x(IN1 := A);\nX := I1x.OUT1;"), PINS + var("I1x", "Inv"))
    _imported, params = load(project(fb + m))
    assert run(params).read("Q0") is True


def test_a_function_block_drawn_as_a_ladder_comes_across_as_text():
    body = ladder(rail(), contact(2, "IN1", 1, negated=True), coil(3, "OUT1", 2))
    fb = pou("Inv", body, "", "functionBlock", "<inputVars>" + var("IN1") + "</inputVars><outputVars>" + var("OUT1") + "</outputVars>")
    m = pou("Main", st("I1x(IN1 := A);\nX := I1x.OUT1;"), PINS + var("I1x", "Inv"))
    _imported, params = load(project(fb + m))
    assert run(params).read("Q0") is True
    assert run(params, I0=True).read("Q0") is False


# ---------------------------------------------------------------- charts
def step(i, name, ref=None, initial=False):
    extra = ' initialStep="true"' if initial else ""
    conn = into(ref) if ref else ""
    return f'<step localId="{i}" name="{name}"{extra}><position x="100" y="{i * 40}"/>{conn}<connectionPointOut/></step>'


def transition(i, ref, cond):
    return (f'<transition localId="{i}"><position x="100" y="{i * 40}"/>{into(ref)}<connectionPointOut/><condition><inline name=""><ST><xhtml:p>{cond}</xhtml:p></ST></inline></condition></transition>')


def action(i, ref, target):
    return (f'<actionBlock localId="{i}"><position x="200" y="50"/>{into(ref)}<action qualifier="N"><reference name="{target}"/></action></actionBlock>')


def jump(i, ref, target):
    return f'<jumpStep localId="{i}" targetName="{target}"><position x="100" y="400"/>{into(ref)}</jumpStep>'


def test_a_chart():
    body = ("<SFC>" + step(1, "Idle", initial=True) + transition(2, 1, "A") + step(3, "Run", 2) + action(4, 3, "X") + transition(5, 3, "B") + jump(6, 5, "Idle") + "</SFC>")
    imported, params = load(project(pou("Main", body, PINS)))
    assert imported.pous[0]["lang"] == "sfc"
    rt = run(params)
    assert rt.read("Idle") is True and rt.read("Q0") is False
    rt.set_input("I0", True)
    rt.scan()
    rt.scan()
    assert rt.read("Run") is True and rt.read("Q0") is True
    rt.set_input("I0", False)
    rt.set_input("I1", True)
    rt.scan()
    rt.scan()
    assert rt.read("Idle") is True


def test_a_chart_with_a_choice_and_parallel_branches():
    body = ("<SFC>" + step(1, "S1", initial=True) + f'<selectionDivergence localId="2"><position x="0" y="0"/>{into(1)}<connectionPointOut formalParameter=""/><connectionPointOut formalParameter=""/></selectionDivergence>'
            + transition(3, 2, "A") + transition(4, 2, "B") + step(5, "Left1", 3)
            + f'<simultaneousDivergence localId="6"><position x="0" y="0"/>{into(4)}<connectionPointOut formalParameter=""/><connectionPointOut formalParameter=""/></simultaneousDivergence>'
            + step(7, "Par1", 6) + step(8, "Par2", 6)
            + f'<simultaneousConvergence localId="9"><position x="0" y="0"/>{into(7)}{into(8)}<connectionPointOut/></simultaneousConvergence>'
            + transition(10, 9, "C") + step(11, "End1", 10) + "</SFC>")
    imported, params = load(project(pou("Main", body, PINS)))
    chart = imported.pous[0]["source"]
    joined = next(t for t in chart["transitions"] if t["cond"] == "C")
    names = {s["id"]: s["name"] for s in chart["steps"]}
    assert {names[i] for i in joined["from"]} == {"Par1", "Par2"} and [names[i] for i in joined["to"]] == ["End1"]
    fork = next(t for t in chart["transitions"] if t["cond"] == "B")
    assert {names[i] for i in fork["to"]} == {"Par1", "Par2"}
    rt = run(params)
    rt.set_input("I1", True)
    rt.scan()
    rt.scan()
    assert rt.read("Par1") is True and rt.read("Par2") is True
    rt.set_input("I1", False)
    rt.set_input("I2", True)
    rt.scan()
    rt.scan()
    assert rt.read("End1") is True and rt.read("Par1") is False


def test_a_selection_convergence_is_one_transition_for_each_way_in():
    body = ("<SFC>" + step(1, "A1", initial=True) + step(2, "B1", initial=True)
            + f'<selectionConvergence localId="3"><position x="0" y="0"/>{into(1)}{into(2)}<connectionPointOut/></selectionConvergence>'
            + transition(4, 3, "A") + step(5, "C1", 4) + "</SFC>")
    imported, _params = load(project(pou("Main", body, PINS)))
    chart = imported.pous[0]["source"]
    assert sorted(t["from"] for t in chart["transitions"]) == [[1], [2]]


def test_named_actions_and_transitions():
    actions = '<actions><action name="Count1"><body><ST><xhtml:p>N := N + 1;</xhtml:p></ST></body></action></actions>'
    trans = '<transitions><transition name="Go"><body><ST><xhtml:p>Go := A;</xhtml:p></ST></body></transition></transitions>'
    body = ("<SFC>" + step(1, "S1", initial=True)
            + f'<transition localId="2"><position x="0" y="0"/>{into(1)}<connectionPointOut/><condition><reference name="Go"/></condition></transition>'
            + step(3, "S2", 2) + f'<actionBlock localId="4"><position x="0" y="0"/>{into(3)}<action qualifier="P1"><reference name="Count1"/></action></actionBlock>'
            + "</SFC>")
    text = f'<pou name="Main" pouType="program"><interface><localVars>{PINS}{var("N", "INT")}</localVars></interface>{actions}{trans}<body>{body}</body></pou>'
    imported, params = load(project(text))
    chart = imported.pous[0]["source"]
    assert chart["transitions"][0]["cond"] == "A"
    assert chart["steps"][1]["actions"] == [{"q": "P", "code": "N := N + 1;"}]
    run(params)


# ---------------------------------------------------------------- what isn't read, and what's in a project
def test_what_isnt_read_is_said():
    il = pou("Old", '<IL><xhtml:p>LD A</xhtml:p></IL>')
    chart_fb = pou("Seq", "<SFC>" + step(1, "S1", initial=True) + "</SFC>", "", "functionBlock")
    types = '<dataType name="Motor"><baseType><struct/></baseType></dataType>'
    imported = plcopen.parse(project(il + chart_fb, types=types))
    text = " ".join(imported.notes)
    assert "Old" in text and "instruction list" in text
    assert "Seq" in text and "function block" in text
    assert "Motor" in text
    assert "no programs" in text


def test_tasks_set_the_scan_and_which_programs_run():
    main = pou("Main", st("X := TRUE;"), PINS)
    other = pou("Other", st("Y := TRUE;"), PINS)
    config = ('<configuration name="c"><resource name="r"><task name="t" interval="T#20ms" priority="0"><pouInstance name="i" typeName="Main"/></task>'
              '<globalVars>' + var("Shared", "INT", init="5") + var("Pin", address="%IX0.3") + '</globalVars></resource></configuration>')
    imported, params = load(project(main + other, config))
    assert imported.scan_ms == 20 and params["program"]["scan_ms"] == 20
    assert next(p for p in imported.pous if p["name"] == "Other")["disabled"] is True
    assert "disabled" not in next(p for p in imported.pous if p["name"] == "Main")
    assert any("Other" in n and "switched off" in n for n in imported.notes)
    assert {"name": "Shared", "type": "INT", "init": "5", "note": ""} in imported.vars
    assert imported.tags["I3"] == "Pin"
    rt = run(params)
    assert rt.read("Q0") is True and rt.read("Q1") is False


def test_tasks_at_different_rates_are_said():
    config = ('<configuration name="c"><resource name="r"><task name="t" interval="T#20ms" priority="0"><pouInstance name="i" typeName="Main"/></task>'
              '<task name="u" interval="T#100ms" priority="0"/></resource></configuration>')
    imported = plcopen.parse(project(pou("Main", st("")), config))
    assert imported.scan_ms == 20 and any("different rates" in n for n in imported.notes)


def test_two_names_on_one_pin_are_said():
    imported = plcopen.parse(project(pou("Main", st(""), var("A", address="%IX0.0") + var("B", address="%IX0.0"))))
    assert imported.tags == {"I0": "A"} and any("both" in n for n in imported.notes)


def test_namespaces_dont_matter():
    plain = project(pou("Main", st("X := TRUE;"), var("X", address="%QX0.0"))).replace(f" {NS}".encode(), b"").replace(b"xhtml:p", b"p")
    assert plcopen.parse(plain).tags == {"Q0": "X"}
    old = project(pou("Main", st("X := TRUE;"), var("X", address="%QX0.0"))).replace(b"tc6_0201", b"tc6_0200")
    assert plcopen.parse(old).tags == {"Q0": "X"}


# ---------------------------------------------------------------- nothing in a file is trusted
@pytest.mark.parametrize("data", [b"", b"not xml", b"<a><b></a>", b"\xff\xfe\x00garbage", b"<html><body/></html>", b"<project/>"])
def test_what_isnt_a_project_is_refused_with_a_message(data):
    with pytest.raises(plcopen.PlcOpenError):
        plcopen.parse(data)


def test_entities_are_refused():
    bomb = b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;">]><project><types/></project>'
    with pytest.raises(plcopen.PlcOpenError, match="entities"):
        plcopen.parse(bomb)
    with pytest.raises(plcopen.PlcOpenError, match="entities"):
        plcopen.parse(bomb.decode().encode("utf-16"))


def test_a_file_too_large_is_refused_without_reading_it():
    with pytest.raises(plcopen.PlcOpenError, match="too large"):
        plcopen.parse(b" " * (plcopen.MAX_FILE + 1))


@pytest.mark.parametrize("body", [
    "<LD><contact/></LD>", "<LD><coil localId='x'/></LD>", '<LD><coil localId="1"><connectionPointIn><connection refLocalId="1"/></connectionPointIn></coil></LD>',
    '<FBD><block localId="1"/></FBD>', '<FBD><block localId="1" typeName="AND"><inputVariables><variable/></inputVariables></block></FBD>',
    '<FBD><outVariable localId="1"><connectionPointIn><connection refLocalId="9"/></connectionPointIn></outVariable></FBD>',
    '<FBD><continuation name="z" localId="1"/><outVariable localId="2"><connectionPointIn><connection refLocalId="1"/></connectionPointIn><expression>q</expression></outVariable></FBD>',
    '<SFC><step localId="1"/></SFC>', '<SFC><step localId="1" name="9 bad"/></SFC>', '<SFC><transition localId="1"/></SFC>',
    '<SFC><actionBlock localId="1"><action/></actionBlock></SFC>', '<SFC><jumpStep localId="1" targetName="nope"/></SFC>',
    "<ST/>", "<NOPE/>", "",
])
def test_a_damaged_body_never_crashes_and_what_comes_of_it_can_be_checked(body):
    imported = plcopen.parse(project(pou("Main", body)))
    params = plc.default_params()
    plcopen.merge(params, imported, replace=True)
    plc.check(params)
    plc.compile_params(params)


def test_a_rung_nested_very_deeply_is_only_not_imported():
    chain = "".join(contact(i, "A", i - 1) for i in range(2, 4000))
    imported = plcopen.parse(project(pou("Main", ladder(rail(), chain, coil(4000, "X", 3999)), PINS)))
    params = plc.default_params()
    plcopen.merge(params, imported, replace=True)
    plc.check(params)


# ---------------------------------------------------------------- into a block
def test_adding_keeps_what_was_there():
    params = {"di": 2, "do": 2, "tags": {"I0": "Keep"}, "program": {"pous": [{"name": "Main", "lang": "st", "source": "Q0 := TRUE;"}], "vars": [{"name": "V", "type": "INT"}]}}
    imported = plcopen.parse(project(pou("Main", st("Q1 := TRUE;"), var("W", "INT") + var("Other", address="%IX0.0"))))
    added = plcopen.merge(params, imported)
    assert added == ["Main2"]
    assert [p["name"] for p in params["program"]["pous"]] == ["Main", "Main2"]
    assert params["tags"]["I0"] == "Keep", "a pin's tag isn't overwritten"
    assert any("already tagged" in n for n in imported.notes) and any("Main2" in n for n in imported.notes)


def test_replacing_takes_out_what_was_there():
    params = {"program": {"pous": [{"name": "Old", "lang": "st", "source": ""}], "vars": [{"name": "V", "type": "INT"}]}}
    imported = plcopen.parse(project(pou("New", st("Q0 := TRUE;"))))
    assert plcopen.merge(params, imported, replace=True) == ["New"]
    assert [p["name"] for p in params["program"]["pous"]] == ["New"] and params["program"]["vars"] == []


def test_a_bad_block_count_in_a_drawing_doesnt_stop_an_import():
    params = {"di": "many", "program": "nonsense"}
    imported = plcopen.parse(project(pou("Main", st(""), var("A", address="%IX0.0"))))
    plcopen.merge(params, imported)
    assert params["tags"]["I0"] == "A"


def test_more_programs_than_a_block_can_have_are_said():
    pous = "".join(pou(f"P{i}", st("")) for i in range(40))
    imported = plcopen.parse(project(pous))
    assert len(imported.pous) == plcopen.MAX_POUS and any("first 32" in n for n in imported.notes)
