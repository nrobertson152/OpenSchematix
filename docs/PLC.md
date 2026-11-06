# The PLC block

Place **PLC (programmable controller)** from the Electrical library, wire it like any other part, and double-click it
to program it. Its pins are ordinary terminals, so it takes part in the drawing's connections, bill of materials,
reports and exports like everything else. FluidWorx runs the same program when it simulates the drawing.

## The block

| Pin | What it is |
|---|---|
| `L+`, `M` | Supply. FluidWorx powers the PLC from these, so it doesn't run without its 24 V |
| `I0`, `I1`, ... | Digital inputs, on when the pin is at least 15 V above `M` on a 24 V supply |
| `Q0`, `Q1`, ... | Digital outputs: sourcing (`L+` to the pin), sinking (the pin to `M`) or relay (`C` to the pin) |
| `AI0`, ... | Analog inputs: 0-10 V, 0-5 V, +-10 V, 4-20 mA or 0-20 mA |
| `AO0`, ... | Analog outputs, with the same signal choices |

The I/O table sets how many of each (up to 64), a **tag** for each pin (shown on the block, usable in every language)
and a note. Give an analog channel a range, say 0 to 250 for a 4-20 mA pressure transmitter, and programs read bar.
Pins keep their names however the block is configured, so wires stay attached when it grows. Removing a pin that has
a wire on it asks first.

## Programs

A block holds one or more programs, in any mix of languages. Every scan (10 ms unless you change it):
the inputs are read, each program runs in the order listed, and the outputs are written. They share the I/O, the
variables table and any markers.

| Language | How it's edited | Notes |
|---|---|---|
| **Ladder logic** (LD) | Graphically | Contacts NO, NC and edge; compare; coils, set, reset; TON, TOF, TP, CTU, CTD; assign; ST boxes; nested parallel branches. Operands can be any expression, such as `T1.Q` or `Pressure > 120.0`. A name nobody declared becomes a BOOL marker |
| **Function block diagram** (FBD) | Graphically | Logic, compare, math, SCALE, LIMIT, SEL, timers, counters, latches, edges, PID. Drag from pin to pin. Inputs can be inverted or given a fixed value. Runs in signal-flow order; a feedback loop reads last scan's value |
| **Sequential function chart** (SFC) | Graphically | Steps, transitions, parallel branches and convergence. Actions N, S, R, P, P0, L, D. `Step.X` and `Step.T` read anywhere |
| **Structured text** (ST) | Code | IEC 61131-3: IF, CASE, FOR, WHILE, REPEAT, EXIT, VAR, ARRAY, FUNCTION, FUNCTION_BLOCK, typed and based literals, time literals, direct addresses such as `%IX0.3`, integer wrap-around by type |
| **C** | Code | `setup()` runs once and `loop()` every scan. Integer and floating types, arrays, structs, pointers, functions, recursion, all the statements and operators; `#define` for constants. No heap, no goto, no function-like macros |
| **Python** | Code | A safe subset. The program runs top to bottom every scan, or define `loop()`. Lists, dicts, functions, comprehensions, `math`. No imports beyond `math`, no classes, no try |

Function blocks, by language:

```
ST      Dwell(IN := Run, PT := T#2s);      IF Dwell.Q THEN ...
C       TON dwell;  ...                    if (ton(&dwell, Run, 2000)) ...
Python  dwell = TON()  ...                 dwell(IN=Run, PT=2000); if dwell.Q: ...
```

Standard blocks: `TON TOF TP` (timers), `CTU CTD CTUD` (counters), `R_TRIG F_TRIG` (edges), `SR RS` (latches), `PID`
(SP, PV, KP, KI, KD, LO, HI; OUT). Functions: `ABS SQRT MIN MAX LIMIT SEL MUX SCALE SIN COS TAN ASIN ACOS ATAN EXP LN
LOG EXPT TRUNC ROUND FLOOR CEIL SHL SHR` and conversions such as `REAL_TO_INT`, `TO_DINT`. Read-only everywhere:
`first_scan`, `now_ms`, `scan_ms`. TIME values are whole milliseconds.

C and Python are case-sensitive; ST, ladder, FBD and SFC aren't. Inputs can't be written by any language: that is
an error when the program is checked.

## Checking and testing

*Check program* (and *Check drawing*, rule **PLC programs**) lists every problem with its place; double-click to go
to it. The **Test** tab runs the program right there, with check boxes for inputs, sliders for analog inputs and a live
list of values. As it runs, ladder rungs light up by power flow, as far as the power really went in the last scan; function block wires
light up by their signals; and charts by their active steps. FluidWorx shows the same thing with the program running in the simulated machine.

## Importing a program from another tool

**Import…** under the program list reads **PLCopen XML** (IEC 61131-10), the one exchange format PLC programming tools have in common. CODESYS and the
tools built on it can export it, and so can Beremiz. Vendors' own formats aren't read. Nothing reaches the drawing until you press *Apply*, so an import can
be checked and tested first.

| In the file | Here |
|---|---|
| Structured text program | Structured text |
| Ladder program | Ladder, if it has only contacts, coils, TON, TOF, TP, CTU, CTD, compares and MOVE. Structured text if not |
| Function block program | A function block diagram, if it has only the blocks here. Structured text if not, as when it uses a function block of your own |
| Chart program | A chart: steps, transitions, branches, jumps, and actions N, S, R, P, P0, P1, L, D |
| Function, function block | Structured text, the one language here that can define them, whichever language it was drawn in |
| A variable on an address, such as `%IX0.3` | That pin's tag: I3. An address the block can't have takes the next free pin, and says so. Pins are added as needed |
| Other variables and global variables | The variable table, or the text of a structured text program |
| Tasks | The shortest interval is the scan time, and everything runs every scan. A program no task runs is there but switched off |

**Not read:** instruction list, a chart inside a function block, your own data types (structs and enumerations), macro steps, jumps and labels in ladder and function block networks,
and anything vendor-specific. The import lists what it left out, and whatever needed it shows up as a problem to fix, as a library function this PLC doesn't have does.

This has been tried on hand-written files and the examples that come with Beremiz. It hasn't been tried on an export from CODESYS or anything built on it.

## Safety of programs in files

A PLC program is part of a drawing, and drawings come from other people. So none of these languages is run by Python
itself. Each is parsed and turned into code that can only reach the PLC's own memory:

- There is no way to name a file, a module, a process or Python's own objects: not from ST, C or the graphic languages,
  which have no such concepts, and not from the Python subset, which has no `import` beyond a fixed list of `math`
  functions, no access to attributes other than listed methods and block pins, and no `eval`, `exec`, `open` or
  `getattr`. `tests/test_plc_safety.py` tries the classic ways out.
- A scan has a budget. A loop that runs too long trips the **watchdog**: the PLC stops, its outputs drop, and the
  message says why, as on a real PLC. Numbers, lists and strings are size-limited, so a program can't exhaust memory.
- Division by zero, a bad index or a null pointer stop the PLC with a message. They never crash the program.
- A damaged program in a file is reported as a problem. It never stops the file from opening, and a program with
  errors doesn't run.
- An imported file is treated the same way. It can't declare XML entities, it's limited in size, and whatever is in it comes out as ordinary program
  source with the limits above.

OpenSchematix only runs a program when you press *Run* on the Test tab. FluidWorx runs it when you simulate.

## Tying it to the rest of the machine

Same tag, same device. That is how drawings are read, and it is how FluidWorx reads them:

| On the electrical sheet | On the fluid sheet | Then |
|---|---|---|
| Coil `Y1` | Valve `Y1` with one solenoid | The coil shifts the valve |
| Coils `Y1a`, `Y1b` | Valve `Y1` with two solenoids | a is the left-hand solenoid, b the right-hand one |
| Coils `Y1`, `Y2` | Valve `V1` with *Solenoid a* = `Y1`, *Solenoid b* = `Y2` | The same, for a valve tagged differently |
| Pressure switch contact `S3` | Pressure switch `S3` | The contact follows the pressure |
| Analog sensor `PT1` | Pressure transducer `PT1` | The sensor's output follows the pressure |
| Motor `M1` | Pump with *Driven by* = `M1`, or tagged `M1` | The pump runs while the motor does |
| Relay coil `K1` | (none: contacts `K1`) | The contacts follow the coil |

A position switch has no symbol on the fluid sheet, so it says what operates it. Its **Senses** field, in the
*Simulation* section of the properties panel, takes a cylinder's tag and a place:

| Senses | Means |
|---|---|
| `A1 100%`, `A1 extended` | At the end of A1's stroke |
| `A1 0%`, `A1 retracted` | At the start of its stroke |
| `A1 150 mm` | At that position (a cam passing the switch) |
| `A1 > 50%`, `A1 > 150 mm` | Anywhere beyond that (a long cam) |
| `A1` | On a potentiometer or analog sensor: a position transducer across the whole stroke |
| `PT1 > 120 bar` | On a contact: closed while that gauge or transducer reads above 120 bar |

A valve operated by the machine itself says the same. Give a directional valve a roller, plunger or cam as an operator and it has a
**Senses** field too, with the same places: `A1 100%` shifts it while A1 is at the end of its stroke. With one on each side, there's
**Senses a** for the left-hand one and **Senses b** for the right-hand one. Pneumatic drawings are often already written this way: a roller
valve tagged `a1` is at the end of cylinder `A`'s stroke and `a0` at the start, and FluidWorx reads them so.

These are ordinary component properties, and FluidWorx can also set them in a study without changing the drawing.
See FluidWorx's `docs/ELECTRICAL.md` for how the simulation works.

## In the file

The whole configuration is in the component's `params`. No format version changes, and a release that doesn't know the
symbol shows a placeholder and keeps the data, so a program survives opening and saving there.

```json
{"id": 1, "symbol": "el.plc", "x": 400, "y": 400, "designator": "PLC1",
 "params": {"di": 8, "do": 6, "ai": 2, "ao": 1, "do_type": "source",
            "tags": {"I0": "Start", "Q0": "Y1a", "AI0": "Pressure"},
            "program": {"version": 1, "scan_ms": 10,
                        "io": {"AI0": {"signal": "4-20mA", "lo": 0, "hi": 250, "note": "System pressure"}},
                        "vars": [{"name": "Count", "type": "INT", "init": "0", "note": ""}],
                        "pous": [{"name": "Main", "lang": "ld", "source": {"rungs": []}},
                                 {"name": "Calc", "lang": "st", "source": "Count := Count + 1;"}]}}}
```

`source` is text for ST, C and Python. For the graphic languages it is structured data, documented at the top of
`openschematix/plc/ladder.py`, `fbd.py` and `sfc.py`. Nothing else is trusted either: I/O counts are limited to 64
whatever a file says.

From a script: `sheet.place("el.plc", x, y, params={...})`; check it with `openschematix.plc.check(component.params)`.
