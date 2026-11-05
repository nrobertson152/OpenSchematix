"""A PLC program comes from a file. It must not be able to harm the computer, hang the program or crash it."""
import json
import math
import sys
import time

import pytest

from openschematix.plc import build, check, compile_params, core
from openschematix.plc.program import Runtime, program_of


def params(lang, source):
    return {"di": 2, "do": 2, "ai": 1, "ao": 1, "tags": {"Q0": "Out"},
            "program": {"pous": [{"name": "Main", "lang": lang, "source": source}]}}


def run(lang, source, scans=1):
    rt = compile_params(params(lang, source))
    for _ in range(scans):
        if not rt.scan():
            break
    return rt


@pytest.mark.parametrize("lang,source", [
    ("st", "WHILE TRUE DO Q1 := NOT Q1; END_WHILE;"),
    ("st", "REPEAT Q1 := NOT Q1; UNTIL FALSE END_REPEAT;"),
    ("st", "VAR i : DINT; END_VAR FOR i := 0 TO 2000000000 DO Q1 := TRUE; END_FOR;"),
    ("c", "void loop(void) { while (1) { Q1 = !Q1; } }"),
    ("c", "void loop(void) { for (;;) ; }"),
    ("c", "void loop(void) { do { } while (1); }"),
    ("c", "int f(void) { return f(); } void loop(void) { f(); }"),
    ("python", "while True:\n    pass\n"),
    ("python", "for i in range(10**12):\n    pass\n"),
    ("python", "def f():\n    f()\nf()\n"),
    ("python", "def f():\n    return g()\ndef g():\n    return f()\nf()\n"),
])
def test_endless_programs_are_stopped_quickly_and_nothing_else_happens(lang, source):
    t0 = time.monotonic()
    rt = run(lang, source)
    assert time.monotonic() - t0 < 5.0
    assert rt.fault and rt.running is False
    assert rt.read("Out") is False              # outputs drop


@pytest.mark.parametrize("source", [
    "x = 10 ** 10 ** 10",
    "x = 2 ** 100000",
    "x = 1 << 100000",
    "x = [0] * 10 ** 9",
    "x = 'a' * 10 ** 9",
    "x = 10 ** 19\nwhile True:\n    x = x * x\n",
    "x = [0] * 100000\nwhile True:\n    x = x + x\n",
    "x = 'a' * 100000\nwhile True:\n    x = x + x\n",
    "x = list(range(10 ** 10))",
    "x = sum(range(10 ** 12))",
    "x = sorted(range(10 ** 10))",
    "x = list(zip(range(10 ** 10), range(10 ** 10)))",
    "x = list(enumerate(range(10 ** 10)))",
    "x = reversed(range(10 ** 10))",
    "x = [0] * 100000\ny = [x] * 100000\nz = str(y)",
    "x = [0] * 100000\ny = [x] * 100000\nz = y == [x] * 100000",
    "x = [0] * 100000\ny = [x] * 100000\nz = sorted(y)",
    "x = '%1000000000d' % 1",
    "x = []\nwhile True:\n    x.append(0)\n",
    "x = {}\ni = 0\nwhile True:\n    x[i] = i\n    i += 1\n",
    "x = int('9' * 100000)",
])
def test_python_cannot_exhaust_cpu_or_memory(source):
    t0 = time.monotonic()
    rt = run("python", source)
    assert time.monotonic() - t0 < 5.0, source
    assert rt.fault or rt.program.errors, source


ESCAPES = [
    "().__class__.__bases__[0].__subclasses__()",
    "[].append.__self__",
    "(lambda: 1).__globals__",
    "math.__dict__",
    "math.sys",
    "TON.__init__.__globals__",
    "TON().__class__",
    "TON().run.__func__",
    "len.__self__",
    "abs.__self__",
    "print.__self__",
    "str.format",
    "'{0.__class__}'.format(1)",
    "f'{().__class__}'",
    "type(1)",
    "vars()",
    "dir()",
    "globals()",
    "locals()",
    "breakpoint()",
    "compile('1', '', 'eval')",
    "input()",
    "memoryview(b'')",
    "bytes(10)",
    "b'abc'",
    "object()",
    "super()",
]


@pytest.mark.parametrize("expr", ESCAPES)
def test_python_has_no_way_out(expr):
    """Each of these is a classic route out of a sandbox. It must be refused at build time or fault at run time."""
    rt = run("python", f"x = {expr}\n")
    assert rt.program.errors or rt.fault, expr
    assert "x" not in rt.program.pous[0].frame if rt.program.pous else True


def test_python_nothing_real_reachable_from_values():
    rt = compile_params(params("python", "x = 1\ny = str(x)\nz = TON()\n"))
    assert rt.ok and rt.scan()
    # the program's namespace holds only its own values, never modules or real builtins
    frame = rt.program.pous[0].frame
    assert set(frame) == {"x", "y", "z"}


def test_python_source_file_side_effects_are_impossible(tmp_path):
    target = tmp_path / "written.txt"
    src = f"open({str(target)!r}, 'w').write('x')\n"
    rt = compile_params(params("python", src))
    rt.scan()
    assert not target.exists() and not rt.ok


@pytest.mark.parametrize("lang,source", [
    ("st", "x := " + "(" * 5000 + "1" + ")" * 5000 + ";"),
    ("st", "x := " + "NOT " * 5000 + "TRUE;"),
    ("st", "x := " + "- " * 5000 + "1;"),
    ("st", "IF TRUE THEN " * 2000 + "END_IF; " * 2000),
    ("st", "x := 1" + " + 1" * 50000 + ";"),
    ("c", "void loop(void) { int x = " + "(" * 5000 + "1" + ")" * 5000 + "; }"),
    ("c", "void loop(void) { int x = " + "!" * 5000 + "1; }"),
    ("c", "void loop(void) " + "{" * 5000 + "}" * 5000),
    ("c", "void loop(void) { " + "if (1) " * 5000 + ";}"),
    ("python", "x = " + "(" * 5000 + "1" + ")" * 5000),
    ("python", "x = " + "not " * 5000 + "1"),
    ("python", "x = 1" + " + 1" * 50000),
    ("python", "\n".join(" " * i + "if 1:" for i in range(200)) + "\n" + " " * 200 + "pass"),
])
def test_deeply_nested_source_is_an_error_not_a_crash(lang, source):
    """Whatever the depth: the build reports it or it works. It never raises."""
    prog = build(params(lang, source))
    assert prog.errors or prog.pous


@pytest.mark.parametrize("source", [
    "x = 1" + " + 1" * 50000,
    "x = a" + ".b" * 50000,
    "x = f" + "()" * 50000,
    "x = a" + "[0]" * 50000,
    'x = f"{' + "1+" * 50000 + '1}"',
    "x = " + "(" * 5000 + "1" + ")" * 5000,
    "x = (" * 80 + "1" + ")" * 80,
    "if 1:\n  pass\n" + "elif 1:\n  pass\n" * 20000,
    "x = (1" + " + 1" * 900 + ")" + (" + (1" + " + 1" * 900 + ")") * 2,
    "x = ((((((1" + " + 1" * 400 + ")" + " + 1" * 400 + ")" + " + 1" * 400 + ")" + " + 1" * 400 + ")))",
])
def test_python_that_would_overflow_the_parser_never_reaches_it(source, monkeypatch):
    """A deep enough tree overflows the C stack inside ast.parse on some versions and platforms: Python 3.10 on Windows
    took the whole process down this way. No except clause can catch that, so it must not get that far."""
    from openschematix.plc import pylang
    monkeypatch.setattr(pylang.ast, "parse", lambda *a, **k: pytest.fail("reached the parser"))
    prog = build(params("python", source))
    assert prog.errors
    assert any(word in prog.errors[0].message for word in ("too", "elif"))


@pytest.mark.parametrize("source", [
    "TABLE = [" + ", ".join(str(i) for i in range(20000)) + "]\n",
    "TABLE = [" + ", ".join(f"-{i}.5" for i in range(20000)) + "]\n",
    "TABLE = [" + ", ".join(f"({i}, {i} + 1)" for i in range(5000)) + "]\n",
    "NAMES = {" + ", ".join(f"'k{i}': 'a + b - c * d'" for i in range(5000)) + "}\n",
    "\n".join(f"x{i} = {i} + 1 + 2 + 3" for i in range(5000)) + "\n",
    "; ".join(f"x{i} = {i} + 1 + 2 + 3" for i in range(1000)) + "\n",
    "text = '" + "+-*/ " * 5000 + "'\n",
    "# " + "+-*/ " * 5000 + "\nx = 1\n",
    "if a:\n  pass\n" + "elif a:\n  pass\n" * 200,
    "x = 1 + \\\n  2 + \\\n  3\ny = (1 +\n 2 +\n 3)\n",
])
def test_real_programs_are_not_mistaken_for_deep_ones(source):
    from openschematix.plc import pylang
    pylang.check_depth(source)


def test_too_long_a_source_is_refused():
    prog = build(params("st", "x := 1;\n" * 200000))
    assert prog.errors and "too long" in prog.errors[0].message


@pytest.mark.parametrize("value", [
    None, 1, "x", [], {"pous": 1}, {"pous": []}, {"pous": [1]}, {"pous": [{}]}, {"pous": [{"lang": "cobol"}]},
    {"pous": [{"name": "A", "lang": "st", "source": 5}]}, {"pous": [{"name": "A", "lang": "ld", "source": "x"}]},
    {"pous": [{"name": "A", "lang": "ld", "source": {"rungs": [1]}}]},
    {"pous": [{"name": "A", "lang": "ld", "source": {"rungs": [{"items": [1]}]}}]},
    {"pous": [{"name": "A", "lang": "ld", "source": {"rungs": [{"items": [{"t": "par", "branches": [1]}]}]}}]},
    {"pous": [{"name": "A", "lang": "fbd", "source": {"blocks": [1], "wires": []}}]},
    {"pous": [{"name": "A", "lang": "fbd", "source": {"blocks": [{"id": True, "type": "AND"}], "wires": []}}]},
    {"pous": [{"name": "A", "lang": "fbd", "source": {"blocks": [{"id": 1, "type": "AND", "n": 10**9}], "wires": [1]}}]},
    {"pous": [{"name": "A", "lang": "sfc", "source": {"steps": [1], "transitions": []}}]},
    {"pous": [{"name": "A", "lang": "sfc", "source": {"steps": [{"id": 1, "name": "S", "initial": True,
                                                                  "actions": [1]}], "transitions": [1]}}]},
    {"vars": 1, "io": 2, "scan_ms": "x", "pous": None},
    {"vars": [1, {"name": 5}, {"name": "a b"}, {"name": "x", "type": "NOPE"}, {"name": "y", "init": "("}]},
    {"scan_ms": 1e308}, {"scan_ms": -5}, {"scan_ms": True},
    {"io": {"AI0": {"signal": "nope", "lo": "x", "hi": []}, "AO0": 5}},
    {"io": {"AI0": {"lo": 5, "hi": 5}}},
])
def test_damaged_programs_never_raise(value):
    p = {"di": 2, "do": 2, "ai": 1, "ao": 1, "program": value}
    prog = build(p)
    rt = Runtime(prog)
    rt.scan()
    rt.set_analog_raw("AI0", 5.0)
    rt.analog_output_raw("AO0")


@pytest.mark.parametrize("bad", [
    {"di": 10 ** 12}, {"di": -5}, {"di": "x"}, {"di": True}, {"di": None}, {"do": 1e9}, {"tags": 1},
    {"tags": {"I0": 5}}, {"tags": {"I0": "a b"}}, {"tags": {"I0": "IF"}}, {"tags": {"I0": "TON"}}, {"tags": {"I99": "x"}},
    {"tags": {"I0": "x", "I1": "x"}}, {"tags": {5: "x"}}, {"do_type": 5}, {"do_type": "x"},
])
def test_damaged_block_settings_never_raise(bad):
    prog = build(bad)
    Runtime(prog).scan()


def test_io_counts_are_limited_whatever_the_file_says():
    assert len(build({"di": 10 ** 12, "do": 10 ** 12}).addr["di"]) == 64


def test_division_by_zero_and_bad_index_stop_the_plc_in_st():
    for src, word in (("Q1 := 1 / 0 > 0;", "zero"), ("VAR a : ARRAY[0..1] OF INT; END_VAR Q1 := a[5] > 0;", "index"),
                      ("VAR a : ARRAY[0..1] OF INT; i : INT := 9; END_VAR a[i] := 1;", "index"),
                      ("Q1 := 1 MOD 0 > 0;", "zero"), ("Q1 := SQRT(-1.0) > 0;", "sqrt"),
                      ("Q1 := MUX(9, 1, 2) > 0;", "MUX"), ("Q1 := SCALE(1.0, 2.0, 2.0, 0.0, 1.0) > 0;", "SCALE")):
        rt = run("st", src)
        assert rt.fault and word in rt.fault, (src, rt.fault)


def test_a_fault_drops_outputs_and_reset_recovers():
    rt = compile_params(params("st", "Out := TRUE; IF I0 THEN Q1 := 1 / 0 > 0; END_IF;"))
    assert rt.scan()
    assert rt.read("Out") is True
    rt.set_input("I0", True)
    assert rt.scan() is False
    assert rt.read("Out") is False and rt.fault
    rt.reset()
    assert rt.running and not rt.fault
    rt.set_input("I0", False)
    assert rt.scan() and rt.read("Out") is True


def test_a_program_with_errors_never_runs():
    rt = compile_params(params("st", "Nope := TRUE;"))
    assert not rt.ok and rt.running is False and rt.scan() is False


def test_reset_restores_every_language_to_its_starting_state():
    sources = {"st": "VAR n : INT := 3; t : TON; END_VAR n := n + 1; v := n; t(IN := TRUE, PT := T#20ms); Q1 := t.Q;",
               "c": "static TON t; int n = 3; void loop(void) { n++; v = n; Q1 = ton(&t, 1, 20); }",
               "python": "t = TON()\nn = 3\ndef loop():\n    global n\n    n += 1\n    v = n\n    t(IN=True, PT=20)\n    Q1 = t.Q\n"}
    for lang, src in sources.items():
        p = params(lang, src)
        p["program"]["vars"] = [{"name": "v", "type": "INT"}]
        rt = compile_params(p)
        assert rt.ok, (lang, [str(d) for d in rt.program.diags])
        for _ in range(3):
            assert rt.scan(), (lang, rt.fault)
        assert rt.read("v") == 6 and rt.read("Q1") is True, lang
        rt.reset()
        assert rt.scan(), (lang, rt.fault)
        assert rt.read("v") == 4 and rt.read("Q1") is False, lang


def test_reset_restores_graphic_languages():
    sfc = {"steps": [{"id": 1, "name": "A", "initial": True}, {"id": 2, "name": "B"}],
           "transitions": [{"id": 1, "from": [1], "to": [2], "cond": "TRUE"}]}
    rt = compile_params(params("sfc", sfc))
    assert rt.scan() and rt.read("B") is True
    rt.reset()
    assert rt.read("B") is False and rt.scan()
    ld = {"rungs": [{"items": [{"t": "rise", "a": "I0"}, {"t": "ton", "a": "T1", "pt": "T#10ms"}, {"t": "coil", "a": "Out"}]}]}
    rt = compile_params(params("ld", ld))
    rt.set_input("I0", True)
    rt.scan()
    rt.scan()
    rt.reset()
    rt.set_input("I0", True)
    rt.scan()
    assert rt.read("T1").ET == 10                # the edge was seen again after the reset


def test_analog_scaling_both_ways():
    p = {"ai": 2, "ao": 2, "di": 0, "do": 0, "tags": {"AI0": "P", "AO1": "V"},
         "program": {"io": {"AI0": {"signal": "4-20mA", "lo": 0, "hi": 250}, "AO1": {"signal": "0-10V", "lo": 0, "hi": 100}},
                     "pous": [{"name": "M", "lang": "st", "source": "V := P / 2.5; AO0 := AI1;"}]}}
    rt = compile_params(p)
    assert rt.ok, [str(d) for d in rt.program.diags]
    rt.set_analog_raw("AI0", 12.0)
    rt.set_analog_raw("AI1", 3.0)
    rt.scan()
    assert rt.read("P") == pytest.approx(125.0)
    assert rt.read("V") == pytest.approx(50.0)
    assert rt.analog_output_raw("AO1") == pytest.approx(5.0)
    assert rt.analog_output_raw("AO0") == pytest.approx(3.0)        # no scaling: the signal's own units
    rt.ctx.G["AO1"] = 500.0
    assert rt.analog_output_raw("AO1") == 10.0                      # an output can't leave its signal range


def test_program_of_gives_defaults():
    p = program_of({})
    assert p["scan_ms"] == 10 and p["pous"][0]["lang"] == "ld" and p["vars"] == []
    assert program_of({"program": {"scan_ms": 1e308}})["scan_ms"] == 1000
    assert program_of({"program": {"scan_ms": 0}})["scan_ms"] == 1


def test_a_program_is_plain_json():
    ld = {"rungs": [{"items": [{"t": "no", "a": "I0"}, {"t": "coil", "a": "Out"}]}]}
    p = params("ld", ld)
    assert json.loads(json.dumps(p)) == p


def test_no_language_uses_exec_or_eval():
    import ast
    import pathlib
    root = pathlib.Path(core.__file__).parent
    for f in root.glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                assert n.func.id not in ("exec", "eval", "compile", "__import__", "open", "getattr_static"), (f, n.lineno)
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
                for name in names:
                    assert name.split(".")[0] not in ("os", "sys", "subprocess", "socket", "shutil", "tkinter",
                                                      "importlib", "pickle", "ctypes"), (f, name)
