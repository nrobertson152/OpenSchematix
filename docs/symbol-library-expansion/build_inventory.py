"""Source of the symbol-library expansion inventory (writes inventory.csv next to this file).

Sources
  HO   "Graphical Symbols for Hydraulic Circuits", HydraulicsOnline.com wall chart (1 page, ISO 1219 style).
       Commercial artwork: used only as a functional reference; symbols are redrawn natively, product
       order codes (e.g. "1VCR...") are not reproduced.
  Y32  "Fluid Power Symbols - ANSI Y32.10 Graphic Symbols" (PDF, 24 pages). Clause numbers are the document's own.
  ECL  "Electric Components Library" (ElCompLib2017.svg), Filip Dominec and contributors, CC0 1.0 public domain.
       Location = section / row / position in row (1-based, left to right).

Status
  existing     already in the built-in library (target = existing id); nothing added
  pending      to implement as a new built-in symbol (target = proposed id)
  configurator to implement inside the directional-valve configurator (fl.*.dcv), optionally also standalone
  annotation   non-connectable drafting element (no terminals, not in the BOM)
  duplicate    same function and meaning as another row (target = that row's key)
  convention   a line/drawing convention handled by the editor (wire styles, crossings), not a symbol
  decision     needs the project director's decision before implementation
  blocked      cannot be implemented faithfully (reason in notes)
  excluded     left out by director decision (reason in notes)
  equivalent   ANSI drawing found identical to the ISO symbol named in target (set while implementing)
  implemented  added; target = the new id(s)      validated = implemented and covered by the batch tests
Run:  python docs/symbol-library-expansion/build_inventory.py
"""
import csv
import os

R = []


def row(key, src, loc, name, cat, group, target, status, batch, notes=""):
    R.append(dict(key=key, source=src, location=loc, source_name=name, category=cat, group=group,
                  target=target, status=status, batch=batch, notes=notes))


H, PN, E, EL, G = "Hydraulic", "Pneumatic", "Electrical", "Electronic", "General"
HP = "Hydraulic+Pneumatic"   # implemented once per medium (fl.hyd.* and fl.pneu.*): port domains differ

# =============================================================== HO chart
# --- Basic Symbols column
row("HO-B01", "HO", "Basic Symbols r1", "Pressure or return line", HP, "Lines", "wire style solid", "convention", "-")
row("HO-B02", "HO", "Basic Symbols r2", "Pilot line", HP, "Lines", "wire style dashed", "convention", "-")
row("HO-B03", "HO", "Basic Symbols r3", "Two or more functions in one unit (enclosure line)", G, "Drafting",
    "gen.enclosure", "annotation", "F2", "Dash-dot component enclosure; also Y32 11.1")
row("HO-B04", "HO", "Basic Symbols r4", "Flexible hose", HP, "Lines & connections", "fl.*.hose", "pending", "F2")
row("HO-B05", "HO", "Basic Symbols r5", "Union", HP, "Lines & connections", "fl.*.union", "pending", "F2",
    "Source shows two variants side by side; drawn as the left (with ports) form")
row("HO-B06", "HO", "Basic Symbols r6", "Cross (lines crossing, bridged and plain)", HP, "Lines", "editor crossings",
    "convention", "-", "Wire crossing/junction rules are editor behaviour")
row("HO-B07", "HO", "Basic Symbols r7", "Closed connection", HP, "Lines & connections", "fl.*.port.closed", "pending", "F2")
row("HO-B08", "HO", "Basic Symbols r8", "Direction of movement (linear arrows)", G, "Drafting", "gen.arrow.move", "annotation", "F2")
row("HO-B09", "HO", "Basic Symbols r9", "Direction of rotation", G, "Drafting", "gen.arrow.rotation", "annotation", "F2")
row("HO-B10", "HO", "Basic Symbols r10", "Regulation possible (adjustability arrow)", G, "Drafting", "gen.arrow.adjust",
    "annotation", "F2", "Same meaning as Y32 2.9")
row("HO-B11", "HO", "Basic Symbols r11", "Electric (energy type)", G, "Drafting", "gen.mark.electric", "annotation", "F2")
row("HO-B12", "HO", "Basic Symbols r12", "Solenoids working in opposite directions", G, "Drafting",
    "gen.mark.solenoids.opposed", "annotation", "F2")
row("HO-B13", "HO", "Basic Symbols r13", "Direction of rotation looking at shaft", G, "Drafting",
    "gen.arrow.rotation.shaft", "annotation", "F2", "Two forms shown (CW, CCW)")
row("HO-B14", "HO", "Basic Symbols r14", "Pneumatic (energy direction, hollow)", PN, "Drafting", "fl.pneu.mark.energy",
    "annotation", "F2", "Same as Y32 2.5.2 / 4.4")
row("HO-B15", "HO", "Basic Symbols r15", "Hydraulic (energy direction, filled)", H, "Drafting", "fl.hyd.mark.energy",
    "annotation", "F2")
row("HO-B16", "HO", "Basic Symbols r16", "Test point", HP, "Lines & connections", "fl.*.testpoint", "pending", "F2")
row("HO-B17", "HO", "Basic Symbols r17", "Spring", HP, "Valve operators", "dcv operator 'spring'", "existing", "F1",
    "Already a configurator operator; standalone element added with F1")
row("HO-B18", "HO", "Basic Symbols r18", "Throttle", HP, "Non-return & flow", "fl.*.throttle", "existing", "-")
row("HO-B19", "HO", "Basic Symbols r19", "Plugged port", HP, "Lines & connections", "fl.*.port.plugged", "pending", "F2")
row("HO-B20", "HO", "Basic Symbols r20", "Rotary union", HP, "Lines & connections", "fl.*.rotaryunion", "pending", "F2")
row("HO-B21", "HO", "Basic Symbols r21", "Detent", HP, "Valve operators", "dcv operator 'detent'", "configurator", "F1",
    "Director: detents and spool controls go in the configurator, optionally also standalone")
row("HO-B22", "HO", "Basic Symbols r22", "Return above / below fluid level", H, "Reservoirs",
    "fl.hyd.tank.above / existing fl.hyd.tank", "pending", "F3", "Below-level form = existing fl.hyd.tank")
row("HO-B23", "HO", "Basic Symbols r23", "Check valve", HP, "Non-return & flow", "fl.*.check", "existing", "-")
row("HO-B24", "HO", "Basic Symbols r24", "Shut-off valve", HP, "Non-return & flow", "fl.*.shutoff", "pending", "F8")

# --- Spool Controls column (directional-valve operators)
ops = [
    ("S01", "General symbol (manual, general)", "manual", "existing"),
    ("S02", "Push knob", "pushbutton", "existing"),
    ("S03", "Push-pull knob", "pushpull", "configurator"),
    ("S04", "Lever", "lever", "existing"),
    ("S05", "Single acting pedal", "pedal", "configurator"),
    ("S06", "Double acting pedal", "pedal2", "configurator"),
    ("S07", "Plunger", "plunger", "configurator"),
    ("S08", "Plunger with stroke limitation", "plunger.limited", "configurator"),
    ("S09", "Spring", "spring", "existing"),
    ("S10", "Roller", "roller", "configurator"),
    ("S11", "Lever with roller", "roller.lever", "configurator"),
    ("S12", "Single solenoid", "solenoid", "existing"),
    ("S13", "Push/pull solenoid", "solenoid.pushpull", "configurator"),
    ("S14", "Direct pilot operated", "pilot.direct", "configurator"),
    ("S15", "Pneumatic / hydraulic operated", "pilot.applied", "configurator"),
    ("S16", "Electric motor", "motor", "configurator"),
    ("S17", "Other control unit (not electric motor)", "motor.other", "configurator"),
    ("S20", "Coupling", "coupling", "configurator"),
    ("S21", "Internal pilot", "pilot.internal", "configurator"),
    ("S22", "External pilot", "pilot.external", "configurator"),
]
for k, name, op, st in ops:
    row(f"HO-{k}", "HO", f"Spool Controls {k}", name, HP, "Valve operators", f"dcv operator '{op}'", st, "F1",
        "Existing configurator operator" if st == "existing" else "New operator + standalone operator element")
row("HO-S18", "HO", "Spool Controls r18", "Intermediate position", HP, "Directional valves",
    "dcv option 'transition position'", "decision", "F1",
    "Needs a valve-dialog option (GUI) - outside the allowed scope; see decision Q2")
row("HO-S19", "HO", "Spool Controls r19", "Proportional spool (infinite positioning bars)", HP, "Directional valves",
    "dcv option 'proportional'", "decision", "F1", "Needs a valve-dialog option (GUI); see decision Q2")

# --- Energy Transformations column
row("HO-T01", "HO", "Energy Transformations r1", "Fixed displacement pump", H, "Pumps & motors", "fl.hyd.pump", "existing", "-")
row("HO-T02", "HO", "Energy Transformations r2", "Single-acting hand pump", H, "Pumps & motors", "fl.hyd.pump.hand", "pending", "F5")
row("HO-T03", "HO", "Energy Transformations r3", "Double-acting hand pump", H, "Pumps & motors", "fl.hyd.pump.hand2",
    "pending", "F5", "Composite (pump, checks, lever); external ports only")
row("HO-T04", "HO", "Energy Transformations r4", "Fixed displacement reversible motor without drain", H,
    "Pumps & motors", "fl.hyd.motor.bidir", "pending", "F5")
row("HO-T05", "HO", "Energy Transformations r5", "Fixed displacement reversible pump with drain", H,
    "Pumps & motors", "fl.hyd.pump.bidir.drain", "pending", "F5")
row("HO-T06", "HO", "Energy Transformations r6", "Fixed displacement reversible motor with drain", H,
    "Pumps & motors", "fl.hyd.motor.bidir.drain", "pending", "F5")
row("HO-T07", "HO", "Energy Transformations r7", "Rotary actuator", H, "Pumps & motors", "fl.hyd.rotary", "pending", "F5",
    "Also Y32 8.7.1 oscillator (same function)")
row("HO-T08", "HO", "Energy Transformations r8", "Single acting cylinder", HP, "Cylinders", "fl.*.cyl.single.ret",
    "pending", "F6", "No spring drawn (return by external force); distinct from existing spring-return fl.*.cyl.single")
row("HO-T09", "HO", "Energy Transformations r9", "Double acting cylinder", HP, "Cylinders", "fl.*.cyl.double", "existing", "-")
row("HO-T10", "HO", "Energy Transformations r10", "Double acting cylinder with variable damping at one end", HP,
    "Cylinders", "fl.*.cyl.double.damp1", "pending", "F6")
row("HO-T11", "HO", "Energy Transformations r11", "Double acting cylinder with variable damping at both ends", HP,
    "Cylinders", "fl.*.cyl.double.damp2", "pending", "F6")
row("HO-T12", "HO", "Energy Transformations r12", "Double acting telescopic cylinder", HP, "Cylinders",
    "fl.*.cyl.tele.double", "pending", "F6")
row("HO-T13", "HO", "Energy Transformations r13", "Single acting telescopic cylinder", HP, "Cylinders",
    "fl.*.cyl.tele.single", "pending", "F6")
row("HO-T14", "HO", "Energy Transformations r14", "Double acting double rod cylinder", HP, "Cylinders",
    "fl.*.cyl.doublerod", "existing", "-")
row("HO-T15", "HO", "Energy Transformations r15", "Accumulator with gas pre-charge", H, "Reservoirs & accumulators",
    "fl.hyd.accumulator.gas", "pending", "F3", "Existing fl.hyd.accumulator is the general form without gas mark")

# --- Energy Control (valves)
ec = [
    ("C01", "Adjustable 3-way flow control with reverse flow check", "Flow control", "fl.hyd.flow.3way.check", "pending", ""),
    ("C02", "Adjustable 3-way flow control with reverse flow check (with T port)", "Flow control",
     "fl.hyd.flow.3way.check.t", "pending", "Second form shows an additional tank connection"),
    ("C03", "Adjustable 3-way flow control", "Flow control", "fl.hyd.flow.3way", "pending", ""),
    ("C04", "Flow divider", "Flow control", "fl.hyd.divider", "pending", ""),
    ("C05", "Spool type flow divider", "Flow control", "fl.hyd.divider.spool", "pending", ""),
    ("C06", "Rotary flow divider", "Flow control", "fl.hyd.divider.rotary", "pending", ""),
    ("C07", "Lowering valve with reverse flow check", "Flow control", "fl.hyd.lowering.check", "pending", ""),
    ("C08", "Throttle with reverse flow check", "Non-return & flow", "fl.hyd.flow.oneway", "existing",
     "Matches existing one-way flow control valve"),
    ("C09", "Pilot operated check valve without drain", "Non-return & flow", "fl.hyd.check.pilot", "pending",
     "Same as Y32 10.9.3"),
    ("C10", "Pilot operated check valve with drain", "Non-return & flow", "fl.hyd.check.pilot.drain", "pending", ""),
    ("C11", "Check valve with spring", "Non-return & flow", "fl.hyd.check.spring", "existing", ""),
    ("C12", "Shuttle valve", "Non-return & flow", "fl.hyd.shuttle", "existing", ""),
    ("C13", "Logic element (cartridge)", "Cartridge valves", "fl.hyd.logic", "pending", ""),
    ("C14", "Priority valve", "Flow control", "fl.hyd.priority", "pending", ""),
    ("C15", "Steering unit, open centre", "Steering", "fl.hyd.steer.oc", "decision", "Composite; see Q3"),
    ("C16", "Steering unit, closed centre", "Steering", "fl.hyd.steer.cc", "decision", "Composite; see Q3"),
    ("C17", "Steering unit, closed centre with LS (with priority valve)", "Steering", "fl.hyd.steer.ls",
     "decision", "Composite; see Q3"),
    ("C18", "Direct acting relief valve", "Pressure control", "fl.hyd.relief", "existing", ""),
    ("C19", "Pilot operated relief valve", "Pressure control", "fl.hyd.relief.pilot", "pending", ""),
    ("C20", "Sequence valve", "Pressure control", "fl.hyd.sequence", "pending", "Also Y32 10.13.2"),
    ("C21", "Leak-free sequence valve with external drain", "Pressure control", "fl.hyd.sequence.leakfree", "pending", ""),
    ("C22", "Relief / unloading valve with external hydraulic pilot and internal drain", "Pressure control",
     "fl.hyd.unloading", "pending", ""),
    ("C23", "Reducing valve", "Pressure control", "fl.hyd.reducing", "existing",
     "Verify drawing matches during F7; existing = direct operated, pilot from outlet"),
    ("C24", "Electrical unloading valve", "Pressure control", "fl.hyd.unloading.sol", "pending", ""),
    ("C25", "Electrical proportional relief valve", "Pressure control", "fl.hyd.relief.prop", "pending", ""),
    ("C26", "Open centre valve", "Directional valves", "fl.hyd.opencentre", "decision", "Composite; see Q3"),
    ("C27", "Relief valve / electrical lowering valve", "Pressure control", "fl.hyd.relief.lowering",
     "decision", "Composite; see Q3"),
    ("C28", "Normally open solenoid check valve", "Directional valves", "fl.hyd.sol.check.no", "pending", "Seated 2/2"),
    ("C29", "Normally closed solenoid check valve", "Directional valves", "fl.hyd.sol.check.nc", "pending", "Seated 2/2"),
    ("C30", "Solenoid operated 6-port diverter / changeover valve", "Directional valves", "fl.hyd.diverter6",
     "pending", "6-port valve: not expressible by the configurator (port layouts 2-5)"),
    ("C31", "Solenoid diverter valve with external drain", "Directional valves", "fl.hyd.diverter6.drain", "pending", ""),
    ("C32", "Direct acting solenoid directional valve (spool form 1)", "Directional valves", "fl.hyd.dcv (config)",
     "configurator", "Reachable with existing configurator; verify spool form against PATTERNS"),
    ("C33", "Direct acting solenoid directional valve (spool form 2)", "Directional valves", "fl.hyd.dcv (config)",
     "configurator", "May need a new centre PATTERN"),
    ("C34", "Pilot operated solenoid directional valve", "Directional valves", "fl.hyd.dcv (config)",
     "configurator", "Needs 3 operators per side (solenoid+pilot+spring); see Q2"),
    ("C35", "Direct acting seated solenoid directional valve", "Directional valves", "fl.hyd.dcv.seated",
     "pending", "Seated 3-way with poppet marks; distinct from spool valve"),
    ("C36", "Direct acting proportional solenoid directional valve", "Directional valves", "fl.hyd.dcv (config)",
     "decision", "Proportional bars; see Q2"),
    ("C37", "Pilot operated proportional solenoid directional valve", "Directional valves", "fl.hyd.dcv (config)",
     "decision", "Proportional bars + 3 operators; see Q2"),
    ("C38", "Series directional control valve", "Mobile valves", "fl.hyd.mobile.series", "decision", "Composite; see Q3"),
    ("C39", "Series directional control valve with negative overlap and valves in spool", "Mobile valves",
     "fl.hyd.mobile.series.neg", "decision", "Composite; see Q3"),
    ("C40", "Parallel directional control valve", "Mobile valves", "fl.hyd.mobile.parallel", "decision", "Composite; Q3"),
    ("C41", "Parallel directional control valve (second form)", "Mobile valves", "fl.hyd.mobile.parallel2",
     "decision", "Composite; Q3"),
    ("C42", "Parallel directional control valve for use with LS pumps", "Mobile valves", "fl.hyd.mobile.ls",
     "decision", "Composite; Q3"),
    ("C43", "Parallel directional control valve for LS pumps with flow control function", "Mobile valves",
     "fl.hyd.mobile.ls.flow", "decision", "Composite; Q3"),
]
for k, name, group, target, st, notes in ec:
    row(f"HO-{k}", "HO", f"Energy Control {k}", name, H, group, target, st,
        {"Flow control": "F8", "Non-return & flow": "F8", "Cartridge valves": "F8", "Pressure control": "F7",
         "Directional valves": "F1" if st in ("configurator", "decision") else "F8", "Steering": "F10",
         "Mobile valves": "F10"}[group], notes)

# --- Fluid Treatment
for k, name, target, st in [
    ("F01", "Breather with filter", "fl.hyd.breather", "pending"),
    ("F02", "Filter", "fl.hyd.filter", "existing"),
    ("F03", "Filter with indicator", "fl.hyd.filter.indicator", "pending"),
    ("F04", "Water / oil cooler", "fl.hyd.cooler.liquid", "pending"),
    ("F05", "Air / oil cooler", "fl.hyd.cooler.air", "pending"),
    ("F06", "Heater", "fl.hyd.heater", "pending"),
    ("F07", "Temperature controller", "fl.hyd.tempcontrol", "pending"),
]:
    row(f"HO-{k}", "HO", f"Fluid Treatment {k}", name, H, "Fluid conditioning", target, st, "F4")

# --- Measuring Instruments & indicators
for k, name, target in [
    ("M01", "Pressure indicator", "fl.*.pressure.indicator"),
    ("M02", "Pressure transducer", "fl.*.pressure.transducer"),
    ("M03", "Pressure gauge", "fl.*.gauge"),
    ("M04", "Differential pressure gauge", "fl.*.gauge.diff"),
    ("M05", "Fluid level gauge", "fl.hyd.level.gauge"),
    ("M06", "Fluid level transducer", "fl.hyd.level.transducer"),
    ("M07", "Thermometer", "fl.*.thermometer"),
    ("M08", "Flow indicator", "fl.*.flow.indicator"),
    ("M09", "Flow meter", "fl.*.flowmeter"),
    ("M10", "Tachometer", "fl.*.tachometer"),
    ("M11", "Torque meter", "fl.*.torquemeter"),
    ("M12", "Pressure switch", "fl.*.pressure.switch"),
    ("M13", "Micro switch (mechanically operated electric switch)", "fl.*.microswitch"),
]:
    row(f"HO-{k}", "HO", f"Measuring {k}", name, HP if "level" not in target else H, "Measurement", target,
        "existing" if k == "M03" else "pending", "F9")

# =============================================================== Y32.10 PDF
Y = lambda clause, page: f"p{page} cl.{clause}"
conv = [("2.4.1", 3, "Solid line - main"), ("2.4.2", 3, "Dash line - pilot"), ("2.4.3", 3, "Dotted line - exhaust or drain"),
        ("2.4.4", 3, "Center line - enclosure outline"), ("2.4.5", 3, "Sensing line"), ("2.4.6", 3, "Lines crossing"),
        ("2.4.7", 3, "Lines joining"), ("2.5", 3, "Basic shapes (circle, triangle, arrow, square, rectangle)"),
        ("3.1", 4, "Line, working (main)"), ("3.2", 4, "Line, pilot"), ("3.3", 4, "Line, exhaust and liquid drain"),
        ("3.4", 4, "Line, sensing"), ("10.4", 15, "Envelopes"), ("10.5", 15, "Ports"),
        ("10.6", 15, "Ports, internally blocked (examples)"), ("10.7", 15, "Flow paths, internally open (examples)"),
        ("10.8", 15, "Flow paths, infinite positioning (examples)")]
for c, p, name in conv:
    row(f"Y32-{c}", "Y32", Y(c, p), name, HP, "Lines" if c.startswith(("2.4", "3")) else "Valve elements",
        "editor / element", "convention", "-",
        "Dotted exhaust line: the editor has solid and dashed wire styles only" if c in ("2.4.3", "3.3") else "")
row("Y32-2.9", "Y32", Y("2.9", 3), "Adjustable (45-degree arrow)", G, "Drafting", "HO-B10", "duplicate", "F2")
row("Y32-2.10", "Y32", Y("2.10", 4), "Pressure compensated (arrow parallel to short side)", G, "Drafting",
    "gen.mark.compensated", "annotation", "F2")
row("Y32-2.11", "Y32", Y("2.11", 4), "Temperature cause or effect (line ending in a dot)", G, "Drafting",
    "gen.mark.temperature", "annotation", "F2")
row("Y32-2.13", "Y32", Y("2.13", 4), "Rotating shaft with direction arrow", G, "Drafting", "HO-B09", "duplicate", "F2")
row("Y32-3.5.1", "Y32", Y("3.5.1", 4), "Flow direction, pneumatic", PN, "Lines & connections", "fl.pneu.flowdir",
    "pending", "F2", "Inline 2-port marker")
row("Y32-3.5.2", "Y32", Y("3.5.2", 4), "Flow direction, hydraulic", H, "Lines & connections", "fl.hyd.flowdir", "pending", "F2")
row("Y32-3.6.1", "Y32", Y("3.6.1", 4), "Outlet to atmosphere, plain orifice, unconnectable", PN, "Lines & connections",
    "fl.pneu.exhaust", "pending", "F2")
row("Y32-3.6.2", "Y32", Y("3.6.2", 4), "Outlet to atmosphere, connectable orifice (thread)", PN, "Lines & connections",
    "fl.pneu.exhaust.port", "pending", "F2")
row("Y32-3.7", "Y32", Y("3.7", 4), "Line with fixed restriction", HP, "Non-return & flow", "fl.*.throttle", "blocked",
    "-", "The PDF figure is empty (only two plain line segments render); existing throttle covers the function")
row("Y32-3.8", "Y32", Y("3.8", 4), "Line, flexible", HP, "Lines & connections", "HO-B04", "duplicate", "F2")
row("Y32-3.9", "Y32", Y("3.9", 4), "Station: testing, measurement or power take-off", HP, "Lines & connections",
    "HO-B16", "duplicate", "F2")
row("Y32-3.9.1", "Y32", Y("3.9.1", 4), "Plugged port (two forms)", HP, "Lines & connections", "HO-B19", "duplicate", "F2")
for c, name, t in [("3.9.3a", "Quick disconnect without checks, connected", "qd.open"),
                   ("3.9.3b", "Quick disconnect without checks, disconnected", "qd.open.apart"),
                   ("3.9.4a", "Quick disconnect with two checks, connected", "qd.2check"),
                   ("3.9.4b", "Quick disconnect with two checks, disconnected", "qd.2check.apart"),
                   ("3.9.5a", "Quick disconnect with one check, connected", "qd.1check"),
                   ("3.9.5b", "Quick disconnect with one check, disconnected", "qd.1check.apart")]:
    row(f"Y32-{c}", "Y32", Y(c[:-1], 4 if c.startswith("3.9.3") else 5), name, HP, "Lines & connections",
        f"fl.*.{t}", "pending", "F2", "Disconnected form: two halves, each with its own port")
row("Y32-3.11", "Y32", Y("3.11", "4-5"), "Rotating coupling", HP, "Lines & connections", "HO-B20", "duplicate", "F2",
    "Ambiguous layout: the circle-with-lines figure sits under 3.9.4 on p4; treated as the 3.11 figure")
for c, p, name, t, st, notes in [
    ("4.1a", 5, "Reservoir, vented", "fl.hyd.tank", "existing", ""),
    ("4.1b", 5, "Reservoir, pressurized", "fl.hyd.tank.pressurized", "pending", ""),
    ("4.1.1a", 5, "Reservoir with connecting lines above fluid level", "fl.hyd.tank.above", "pending", "3 example forms"),
    ("4.1.1b", 5, "Reservoir with connecting lines below fluid level", "fl.hyd.tank", "existing", ""),
    ("4.1.1c", 5, "Reservoir with bottom connection", "fl.hyd.tank.bottom", "pending", ""),
    ("4.1.2", 5, "Reservoir, simplified symbol", "fl.hyd.tank", "existing", ""),
    ("4.1.2.1", 5, "Simplified reservoir, return below fluid level", "fl.hyd.tank", "existing", ""),
    ("4.1.2.2", 5, "Simplified reservoir, return above fluid level", "fl.hyd.tank.above", "duplicate", "HO-B22"),
    ("4.1.2.3", 5, "Vented manifold", "fl.hyd.manifold.vented", "pending", ""),
    ("4.2", 5, "Accumulator", "fl.hyd.accumulator", "existing", ""),
    ("4.2.1", 5, "Accumulator, spring loaded", "fl.hyd.accumulator.spring", "pending", ""),
    ("4.2.2", 5, "Accumulator, gas charged", "fl.hyd.accumulator.gas", "duplicate", "HO-T15"),
    ("4.2.3", 5, "Accumulator, weighted", "fl.hyd.accumulator.weight", "pending", ""),
    ("4.3", 5, "Receiver", "fl.pneu.receiver", "existing", ""),
    ("4.4", 5, "Energy source (hydraulic, pneumatic)", "fl.*.source", "pending", "F2: 1-port source marker"),
]:
    row(f"Y32-{c}", "Y32", Y(c, p), name, H if t.startswith("fl.hyd") else (PN if "pneu" in t else HP),
        "Reservoirs & accumulators" if c != "4.4" else "Lines & connections", t, st, "F3" if c != "4.4" else "F2", notes)
for c, p, name, t, st in [
    ("5", 6, "Fluid conditioner, general", "fl.*.conditioner", "pending"),
    ("5.1.1a", 7, "Heater (inside triangles: introduction of heat)", "fl.*.heater", "pending"),
    ("5.1.1b", 7, "Heater, heating medium liquid (outside triangles filled)", "fl.*.heater.liquid", "pending"),
    ("5.1.1c", 7, "Heater, heating medium gaseous (outside triangles hollow)", "fl.*.heater.gas", "pending"),
    ("5.1.2a", 7, "Cooler (two drawing forms)", "fl.*.cooler", "pending"),
    ("5.1.2b", 7, "Cooler with coolant lines (liquid / gaseous)", "fl.*.cooler.liquid", "pending"),
    ("5.1.3a", 7, "Temperature controller (two drawing forms)", "fl.*.tempcontrol", "pending"),
    ("5.1.3b", 7, "Temperature controller with medium lines (liquid / gaseous)", "fl.*.tempcontrol.lines", "pending"),
    ("5.2", 7, "Filter - strainer", "fl.*.filter", "existing"),
    ("5.3.1", 7, "Separator with manual drain", "fl.*.separator", "pending"),
    ("5.3.2", 7, "Separator with automatic drain", "fl.*.separator.auto", "pending"),
    ("5.4.1", 7, "Filter - separator with manual drain", "fl.*.filtersep", "pending"),
    ("5.4.2", 7, "Filter - separator with automatic drain", "fl.*.filtersep.auto", "pending"),
    ("5.5", 7, "Desiccator (chemical dryer)", "fl.pneu.dryer", "pending"),
    ("5.6.1", 7, "Lubricator, less drain", "fl.pneu.lubricator", "pending"),
    ("5.6.2", 7, "Lubricator with manual drain", "fl.pneu.lubricator.drain", "pending"),
]:
    row(f"Y32-{c}", "Y32", Y(c.rstrip("abc"), p), name, PN if "pneu" in t else HP, "Fluid conditioning", t, st, "F4",
        "Medium of heating/cooling lines: filled = liquid, hollow = gaseous (both forms shown)" if "lines" in t or
        c in ("5.1.1b", "5.1.1c", "5.1.2b") else "")
for c, p, name, t, st in [
    ("6.1.1", 7, "Cylinder, single acting", "fl.*.cyl.single.ret", "duplicate"),
    ("6.1.2", 7, "Cylinder, double acting", "fl.*.cyl.double", "existing"),
    ("6.1.2.1", 7, "Cylinder, double acting, single end rod", "fl.*.cyl.double", "existing"),
    ("6.1.2.2", 7, "Cylinder, double acting, double end rod", "fl.*.cyl.doublerod", "existing"),
    ("6.1.2.3", 8, "Cylinder, fixed cushion advance and retract", "fl.*.cyl.cushion2", "pending"),
    ("6.1.2.4", 8, "Cylinder, adjustable cushion advance only", "fl.*.cyl.cushion.adj1", "pending"),
    ("6.1.2.5a", 8, "Cylinder, rod diameter significant, non cushion", "fl.*.cyl.bigrod", "pending"),
    ("6.1.2.5b", 8, "Cylinder, rod diameter significant, cushion advance and retract", "fl.*.cyl.bigrod.cushion2", "pending"),
    ("6.2", 8, "Pressure intensifier", "fl.*.intensifier", "pending"),
    ("6.3a", 8, "Servo positioner, hydraulic (simplified)", "fl.hyd.servopositioner", "pending"),
    ("6.3b", 8, "Servo positioner, pneumatic (simplified)", "fl.pneu.servopositioner", "pending"),
    ("6.4", 8, "Discrete positioner (combined cylinders)", "fl.*.cyl.multiposition", "pending"),
]:
    row(f"Y32-{c}", "Y32", Y(c.rstrip("ab"), p), name, PN if "pneu" in t else (H if "hyd" in t else HP), "Cylinders",
        t, st, "F6", "Same as HO-T08" if st == "duplicate" else "")
yops = [("7.1", 8, "Spring", "spring", "existing"), ("7.2", 8, "Manual, general", "manual", "existing"),
        ("7.2.1", 8, "Push button", "pushbutton", "existing"), ("7.2.2", 8, "Lever", "lever", "existing"),
        ("7.2.3", 8, "Pedal or treadle", "pedal", "duplicate"),
        ("7.3", 8, "Mechanical (cam / roller; two forms)", "roller / cam", "configurator"),
        ("7.4", 8, "Detent", "detent", "duplicate"),
        ("7.5", 8, "Pressure compensated", "compensated", "configurator"),
        ("7.6.1", 8, "Solenoid (single winding)", "solenoid", "existing"),
        ("7.6.2", 8, "Reversing motor", "motor.reversing", "configurator"),
        ("7.7.1", 8, "Pilot pressure, remote supply", "pilot", "existing"),
        ("7.7.2", 10, "Pilot pressure, internal supply", "pilot.internal", "duplicate"),
        ("7.7.3a", 10, "Actuation by released pressure, by remote exhaust", "pilot.release.remote", "configurator"),
        ("7.7.3b", 10, "Actuation by released pressure, by internal return", "pilot.release.internal", "configurator"),
        ("7.7.4", 10, "Pilot controlled, spring centered (simplified and complete)", "pilot + spring", "existing"),
        ("7.7.5", 10, "Pilot differential (simplified, complete)", "pilot.differential", "configurator"),
        ("7.8.1a", 10, "Solenoid or pilot, external pilot supply", "solenoid.pilot.ext", "configurator"),
        ("7.8.1b", 10, "Solenoid or pilot, internal pilot supply and exhaust", "solenoid.pilot.int", "configurator"),
        ("7.8.2", 10, "Solenoid and pilot (two forms)", "solenoid.and.pilot", "configurator"),
        ("7.9.1", 10, "Thermal, local sensing", "thermal", "configurator"),
        ("7.9.2", 10, "Thermal, with bulb for remote sensing", "thermal.bulb", "configurator"),
        ("7.10", 10, "Servo", "servo", "configurator"),
        ("7.11a", 10, "Composite actuator: basic", "pilot.applied", "duplicate"),
        ("7.11b", 10, "Composite actuator: and", "and", "decision"),
        ("7.11c", 10, "Composite actuator: or", "or", "decision"),
        ("7.11d", 10, "Composite actuator: and/or", "and/or", "decision"),
        ("7.11e", 11, "Composite: solenoid and pilot or manual override and pilot", "and/or 2", "decision"),
        ("7.11f", 11, "Composite: solenoid and pilot or manual override and pilot or manual override alone",
         "and/or 3", "decision")]
for c, p, name, op, st in yops:
    row(f"Y32-{c}", "Y32", Y(c.rstrip("abcdef"), p), name, HP, "Valve operators", f"dcv operator '{op}'", st, "F1",
        {"duplicate": "Same function as an HO spool control row", "decision":
         "Stacked/parallel operator boxes need a configurator layout option; see Q2"}.get(st, ""))
rot = [("8.1", 12, "Rotary device, basic symbol", "element", "convention"),
       ("8.1.1", 12, "Rotary device with ports", "element", "convention"),
       ("8.1.2", 12, "Rotary device with shaft, control and drain (example)", "element", "convention"),
       ("8.2.1.1", 12, "Hydraulic pump, fixed, unidirectional", "fl.hyd.pump", "existing"),
       ("8.2.1.2", 12, "Hydraulic pump, fixed, bidirectional", "fl.hyd.pump.bidir", "pending"),
       ("8.2.2.1s", 12, "Hydraulic pump, variable, non-compensated, unidirectional (simplified)", "fl.hyd.pump.var", "existing"),
       ("8.2.2.1c", 12, "Hydraulic pump, variable, non-compensated, unidirectional (complete)", "fl.hyd.pump.var.full", "pending"),
       ("8.2.2.2s", 12, "Hydraulic pump, variable, non-compensated, bidirectional (simplified)", "fl.hyd.pump.var.bidir", "pending"),
       ("8.2.2.2c", 12, "Hydraulic pump, variable, non-compensated, bidirectional (complete)", "fl.hyd.pump.var.bidir.full", "pending"),
       ("8.2.3.1s", 12, "Hydraulic pump, variable, pressure compensated, unidirectional (simplified)", "fl.hyd.pump.pc", "pending"),
       ("8.2.3.1c", 12, "Hydraulic pump, variable, pressure compensated, unidirectional (complete)", "fl.hyd.pump.pc.full", "pending"),
       ("8.2.3.2s", 12, "Hydraulic pump, variable, pressure compensated, bidirectional (simplified)", "fl.hyd.pump.pc.bidir", "pending"),
       ("8.2.3.2c", 12, "Hydraulic pump, variable, pressure compensated, bidirectional (complete)", "fl.hyd.pump.pc.bidir.full", "pending"),
       ("8.3.1", 12, "Hydraulic motor, fixed, unidirectional (two orientations)", "fl.hyd.motor", "existing"),
       ("8.3.1.2", 12, "Hydraulic motor, fixed, bidirectional", "fl.hyd.motor.bidir", "duplicate"),
       ("8.3.2.1", 12, "Hydraulic motor, variable, unidirectional", "fl.hyd.motor.var", "pending"),
       ("8.3.2.2", 12, "Hydraulic motor, variable, bidirectional", "fl.hyd.motor.var.bidir", "pending"),
       ("8.4.1c", 13, "Pump-motor: pump in one direction, motor in the other (complete)", "fl.hyd.pumpmotor.rev.full", "pending"),
       ("8.4.1s", 13, "Pump-motor: pump in one direction, motor in the other (simplified)", "fl.hyd.pumpmotor.rev", "pending"),
       ("8.4.2c", 13, "Pump-motor: one flow direction, pump or motor (complete)", "fl.hyd.pumpmotor.full", "pending"),
       ("8.4.2s", 13, "Pump-motor: one flow direction, pump or motor (simplified)", "fl.hyd.pumpmotor", "pending"),
       ("8.4.3c", 13, "Pump-motor: both flow directions, variable, pressure compensated (complete)", "fl.hyd.pumpmotor.bidir.pc.full", "pending"),
       ("8.4.3s", 13, "Pump-motor: both flow directions, variable, pressure compensated (simplified)", "fl.hyd.pumpmotor.bidir.pc", "pending"),
       ("8.5.1", 13, "Compressor, fixed displacement", "fl.pneu.compressor", "existing"),
       ("8.5.2", 13, "Vacuum pump, fixed displacement", "fl.pneu.vacuumpump", "pending"),
       ("8.6.1", 13, "Pneumatic motor, unidirectional", "fl.pneu.motor", "existing"),
       ("8.6.2", 13, "Pneumatic motor, bidirectional", "fl.pneu.motor.bidir", "pending"),
       ("8.7.1", 13, "Oscillator, hydraulic", "fl.hyd.rotary", "duplicate"),
       ("8.7.2", 13, "Oscillator, pneumatic", "fl.pneu.rotary", "pending"),
       ("8.8.1", 13, "Electric motor (prime mover)", "fl.*.primemover.electric", "pending"),
       ("8.8.2", 13, "Heat engine (e.g. internal combustion engine)", "fl.*.primemover.engine", "pending")]
for c, p, name, t, st in rot:
    row(f"Y32-{c}", "Y32", Y(c.rstrip("sc"), p), name, PN if "pneu" in t else (H if "hyd" in t else HP),
        "Pumps & motors", t, st, "F5" if st not in ("convention",) else "-",
        {"8.3.1.2": "Same as HO-T04", "8.7.1": "Same as HO-T07 rotary actuator",
         "8.8.1": "Mechanical prime mover (shaft only), not an electrical device; el.motor remains the electrical symbol"}
        .get(c, ""))
for c, p, name, t, st in [
    ("9.1.1", 13, "Pressure indicator / recorder (three forms)", "fl.*.pressure.indicator", "duplicate"),
    ("9.1.2", 13, "Temperature indicator (four forms)", "fl.*.thermometer", "duplicate"),
    ("9.1.3.1", 13, "Flow meter, flow rate", "fl.*.flowmeter", "duplicate"),
    ("9.1.3.2", 14, "Flow meter, totalizing", "fl.*.flowmeter.total", "pending"),
    ("9.2.1", 15, "Venturi", "fl.*.venturi", "pending"),
    ("9.2.2", 15, "Orifice plate (two forms)", "fl.*.orificeplate", "pending"),
    ("9.2.3", 15, "Pitot tube", "fl.*.pitot", "pending"),
    ("9.2.4a", 15, "Nozzle, hydraulic", "fl.hyd.nozzle", "pending"),
    ("9.2.4b", 15, "Nozzle, pneumatic", "fl.pneu.nozzle", "pending"),
    ("9.3.1", 15, "Pressure switch", "fl.*.pressure.switch", "duplicate"),
    ("9.3.2", 15, "Muffler (silencer)", "fl.pneu.silencer", "pending"),
]:
    row(f"Y32-{c}", "Y32", Y(c.rstrip("ab"), p), name, PN if "pneu" in t else (H if "hyd" in t else HP),
        "Measurement" if not t.endswith(("silencer", "nozzle")) else "Lines & connections", t, st,
        "F9" if "silencer" not in t else "F2")
valves = [
    ("10.9.1s", 15, "On-off (manual shut-off), simplified", "fl.*.shutoff", "duplicate", "F8", "Same as HO-B24"),
    ("10.9.1o", 16, "On-off, composite, off", "fl.*.valve.2way.manual", "pending", "F8", "Detented manual 2/2; may map to configurator"),
    ("10.9.1n", 17, "On-off, composite, on", "fl.*.valve.2way.manual", "duplicate", "F8", "Same valve shown actuated"),
    ("10.9.2s", 17, "Check, simplified", "fl.*.check", "existing", "-", ""),
    ("10.9.2c", 17, "Check, composite symbol", "fl.*.check", "duplicate", "-", "Composite drawing of the same function"),
    ("10.9.3", 17, "Check, pilot-operated to open", "fl.*.check.pilot", "pending", "F8", "Hyd form = HO-C09"),
    ("10.9.4", 17, "Check, pilot-operated to close", "fl.*.check.pilotclose", "pending", "F8", ""),
    ("10.9.5.1nc", 17, "Two-way valve, two position, normally closed", "fl.*.dcv (2/2)", "existing", "F1",
     "Configurator 2/2 with spring; verify geometry"),
    ("10.9.5.1no", 17, "Two-way valve, two position, normally open", "fl.*.dcv (2/2)", "existing", "F1", ""),
    ("10.9.5.2nc", 17, "Two-way valve, infinite position, normally closed", "fl.*.valve.2way.prop.nc", "pending", "F8", ""),
    ("10.9.5.2no", 17, "Two-way valve, infinite position, normally open", "fl.*.valve.2way.prop.no", "pending", "F8", ""),
    ("10.10.1.1", 17, "Three-way, two position, normally open", "fl.*.dcv (3/2)", "existing", "F1", "Verify"),
    ("10.10.1.2", 17, "Three-way, two position, normally closed", "fl.*.dcv (3/2)", "existing", "F1", "Verify"),
    ("10.10.1.3", 17, "Three-way distributor (pressure first to one port, then the other)", "fl.*.valve.3way.distributor",
     "pending", "F8", "Port arrangement not expressible by the 3-port configurator layout"),
    ("10.10.1.4", 17, "Three-way two-pressure valve", "fl.*.valve.3way.twopressure", "pending", "F8", ""),
    ("10.10.2.1", 17, "Double check valve without cross bleed", "fl.*.doublecheck", "pending", "F8", ""),
    ("10.10.2.2", 17, "Double check valve with cross bleed", "fl.*.doublecheck.bleed", "pending", "F8", ""),
    ("10.11.1", 18, "Four-way, two position (normal and actuated; two forms)", "fl.*.dcv (4/2)", "existing", "F1",
     "Second form is a 5-connection drawing; check against pneumatic 5/2"),
    ("10.11.2", 18, "Four-way, three position (normal, actuated left, actuated right)", "fl.*.dcv (4/3)", "existing", "F1",
     "Actuated states are the same valve shifted; drawn only in the normal state"),
    ("10.11.3", 18, "Typical centre conditions of three-position valves (8 shown)", "dcv PATTERNS", "configurator", "F1",
     "Add each missing centre condition as a configurator flow pattern"),
    ("10.11.4", 18, "Two-position, snap action with transition", "dcv option 'transition position'", "decision", "F1", "Q2"),
    ("10.12.1", 18, "Infinite positioning between open and closed, normally closed", "fl.*.valve.prop.nc", "pending", "F8", ""),
    ("10.12.2", 18, "Infinite positioning between open and closed, normally open", "fl.*.valve.prop.no", "pending", "F8", ""),
    ("10.13.1s", 18, "Pressure relief, simplified", "fl.*.relief", "existing", "-", "Pneumatic relief added (pending)"),
    ("10.13.1n", 18, "Pressure relief, normal", "fl.*.relief", "duplicate", "-", "Same valve, explanatory form"),
    ("10.13.1a", 18, "Pressure relief, actuated (relieving)", "fl.*.relief", "duplicate", "-", "Same valve shown actuated"),
    ("10.13.2a", 18, "Sequence valve, internal drain", "fl.*.sequence", "pending", "F7", "Hyd form = HO-C20"),
    ("10.13.2b", 18, "Sequence valve, external drain", "fl.*.sequence.drain", "pending", "F7", ""),
    ("10.13.3a", 19, "Pressure reducing", "fl.*.reducing", "existing", "-", "Hyd existing; pneumatic regulator exists"),
    ("10.13.3b", 19, "Pressure reducing with external drain", "fl.hyd.reducing.drain", "pending", "F7", ""),
    ("10.13.4", 19, "Pressure reducing and relieving", "fl.hyd.reducing.relieving", "pending", "F7", ""),
    ("10.13.5", 19, "Airline pressure regulator (adjustable, relieving)", "fl.pneu.regulator.relieving", "pending", "F7", ""),
    ("10.14", 19, "Infinite positioning three-way valves (four examples)", "fl.*.valve.3way.prop", "decision", "F1",
     "Proportional bars; Q2"),
    ("10.15", 19, "Infinite positioning four-way valves (four examples)", "fl.*.valve.4way.prop", "decision", "F1", "Q2"),
    ("10.16.1", 19, "Flow control, adjustable, non-compensated", "fl.*.throttle.adj", "existing", "-", ""),
    ("10.16.2", 19, "Flow control, adjustable with bypass", "fl.*.flow.oneway", "existing", "-", ""),
    ("10.16.3", 19, "Flow control, adjustable and pressure compensated with bypass", "fl.*.flow.pc.bypass", "pending", "F8", ""),
    ("10.16.4", 19, "Flow control, adjustable, temperature and pressure compensated", "fl.*.flow.tpc.bypass", "pending", "F8", ""),
]
for c, p, name, t, st, b, notes in valves:
    row(f"Y32-{c}", "Y32", Y(c.rstrip("sconab").rstrip("."), p), name, PN if "pneu" in t else (H if "hyd" in t else HP),
        "Valves", t, st, b, notes)
comp = [("11.1", 19, "Component enclosure", "gen.enclosure", "duplicate", "Same as HO-B03"),
        ("11.2c", 20, "Airline accessories (FRL), composite", "fl.pneu.frl.full", "decision", "Q3"),
        ("11.2s", 20, "Airline accessories (FRL), simplified", "fl.pneu.frl", "pending", "Single defined symbol with ports"),
        ("11.3.1.1", 21, "Double pump, fixed, one inlet two outlets", "fl.hyd.pump.double", "decision", "Q3"),
        ("11.3.1.2", 21, "Double pump with integral check unloading", "-", "decision", "Q3"),
        ("11.3.1.3", 21, "Integral variable flow rate control with overload relief", "-", "decision", "Q3"),
        ("11.3.1.4", 21, "Variable displacement pump with integral replenishing pump and control valves", "-", "decision", "Q3"),
        ("11.4.1", 23, "Relief valve, balanced type", "fl.hyd.relief.balanced", "decision", "Q3"),
        ("11.4.2", 23, "Remote operated sequence with integral check", "-", "decision", "Q3"),
        ("11.4.3", 23, "Remote and direct operated sequence with differential areas and integral check", "-", "decision", "Q3"),
        ("11.4.4", 23, "Pressure reducing with integral check", "-", "decision", "Q3"),
        ("11.4.5.1", 23, "Pilot operated check, differential pilot opened", "-", "decision", "Q3"),
        ("11.4.5.2", 23, "Pilot operated check (second form; untitled in source)", "-", "decision",
         "Q3; source gives no title for 11.4.5.2"),
        ("11.4.6s", 22, "2-position 4-connection solenoid and pilot actuated, manual pilot override (simplified)",
         "fl.*.dcv (config)", "decision", "Q2 (3 operators per side)"),
        ("11.4.6c", 22, "Same, complete symbol", "-", "decision", "Q3"),
        ("11.4.7s", 24, "2-position 5-connection solenoid controlled pilot actuated, detents, throttled exhaust (simplified)",
         "fl.pneu.dcv (config)", "decision", "Q2 (3 operators + throttled exhausts)"),
        ("11.4.7c", 24, "Same, complete symbol", "-", "decision", "Q3"),
        ("11.4.8", 24, "Variable pressure compensated flow control and overload relief", "-", "decision", "Q3")]
for c, p, name, t, st, notes in comp:
    row(f"Y32-{c}", "Y32", Y(c.rstrip("sc"), p), name, PN if "pneu" in t else (H if "hyd" in t else HP),
        "Composite", t, st, "F10", notes)

# =============================================================== ECL (electrical, CC0)
SEC = {"Other things": "OTH", "Basic logic blocks": "BAS", "Sources, connectors": "SRC",
       "Diodes (semiconductor)": "DIO", "Linear components": "LIN", "Transformers": "XFM", "Transistors": "TRS",
       "Semiconductor devices": "SEM", "Vacuum tubes": "VAC"}


def e(sec, r, i, name, cat, group, t, st, batch, notes=""):
    row(f"ECL-{SEC[sec]}{r}.{i}", "ECL", f"{sec} r{r} #{i}", name, cat, group, t, st, batch, notes)


S = "Other things"
e(S, 1, 1, "Buzzer, AC", E, "Signalling", "el.buzzer.ac", "pending", "E8", "Dome with ~")
e(S, 1, 2, "Buzzer, DC", E, "Signalling", "el.buzzer.dc", "pending", "E8", "Dome with =")
e(S, 1, 3, "Voltmeter", E, "Measurement", "el.meter.v", "pending", "E8")
e(S, 1, 4, "Ammeter", E, "Measurement", "el.meter.a", "pending", "E8")
e(S, 1, 5, "Galvanometer", E, "Measurement", "el.meter.g", "pending", "E8")
e(S, 1, 6, "DC motor with brushes (vertical)", E, "Machines", "el.motor.dc", "pending", "E8",
  "Brush rectangles distinguish it from existing el.motor")
e(S, 1, 7, "Voltmeter, pictorial (illustration)", E, "Measurement", "-", "blocked", "-",
  "Pictorial illustration (shaded meter body), not a schematic symbol")
e(S, 2, 1, "Microphone", EL, "Transducers", "el.microphone", "pending", "E8")
e(S, 2, 2, "Crystal (quartz resonator)", EL, "Passive", "el.crystal", "pending", "E1")
e(S, 2, 3, "Loudspeaker", EL, "Transducers", "el.speaker", "pending", "E8")
e(S, 2, 4, "DC motor with brushes (horizontal)", E, "Machines", "ECL-OTH1.6", "duplicate", "E8", "Rotated drawing of r1 #6")
e(S, 2, 5, "Ammeter, pictorial (illustration)", E, "Measurement", "-", "blocked", "-", "Pictorial illustration")

S = "Basic logic blocks"
gates = ["AND", "NAND", "OR", "NOR", "XOR", "XNOR"]
for r, n in ((1, 2), (2, 3), (3, 4)):
    for i, gname in enumerate(gates, 1):
        e(S, r, i, f"{gname} gate, {n} inputs", EL, "Logic", f"el.logic.{gname.lower()}{n}", "pending", "E7",
          "Distinctive-shape (ANSI/IEEE 91) style")
for i, gname in enumerate(gates, 1):
    e(S, 4, i, f"{gname} gate, wide input bar (5 inputs)", EL, "Logic", f"el.logic.{gname.lower()}5", "pending", "E7",
      "Extended input bar drawing; 5 input leads shown")
e(S, 1, 7, "NOT gate (inverter)", EL, "Logic", "el.logic.not", "pending", "E7")
e(S, 2, 7, "D latch (D, E, Q, /Q)", EL, "Logic", "el.logic.dlatch", "pending", "E7")
e(S, 3, 7, "D flip-flop, edge triggered (D, clock, Q, /Q)", EL, "Logic", "el.logic.dff", "pending", "E7")
e(S, 4, 7, "JK flip-flop (J, clock, K, Q, /Q)", EL, "Logic", "el.logic.jkff", "pending", "E7")
e(S, 1, 8, "Full adder (vertical pin layout)", EL, "Logic", "el.logic.fulladder", "pending", "E7")
e(S, 1, 9, "Full adder (horizontal pin layout)", EL, "Logic", "ECL-BAS1.8", "duplicate", "E7", "Same function, other pin placement")
e(S, 3, 8, "Multiplexer, 2 to 1", EL, "Logic", "el.logic.mux2", "pending", "E7",
  "Select input drawn on the notch; flag: source shows no select-pin label")
e(S, 2, 9, "Bus with branches (bus ripper)", EL, "Logic", "-", "convention", "-", "Wire/bus drawing, not a component")
e(S, 3, 9, "Bus width marker, 4 lines (two forms)", G, "Drafting", "gen.mark.buswidth", "annotation", "E7")

S = "Sources, connectors"
for i, (name, t, notes) in enumerate([
        ("DC voltage source (+/- marked)", "el.source.dc", "Existing el.source.v drawn differently; compare in E2"),
        ("AC voltage source", "el.source.ac", ""), ("Current source", "el.source.i", ""),
        ("Dependent (controlled) current source", "el.source.i.dep", ""),
        ("Coaxial connector", "el.connector.coax", ""), ("Antenna", "el.antenna", "")], 1):
    e(S, 1, i, name, E if i < 5 else EL, "Sources" if i < 5 else "Connections", t,
      "existing" if t == "el.source.ac" else "pending", "E2", notes)
for i, (name, t, st) in enumerate([
        ("Chassis / frame ground", "el.chassis", "existing"), ("Ground, bar (T form)", "el.ground.bar", "pending"),
        ("Ground, hollow triangle (up)", "el.ground.signal.up", "pending"),
        ("Ground, filled triangle (up)", "el.ground.signal.fill", "pending"),
        ("Supply terminal +", "el.rail.pos", "pending"), ("Supply terminal +5V", "el.rail.pos", "duplicate"),
        ("Supply terminal VCC", "el.rail.pos", "duplicate"), ("Single cell, 5V", "el.cell", "existing"),
        ("Battery, multi-cell, 60V", "el.battery", "pending")], 1):
    e(S, 2, i, name, E, "Sources" if "ell" in name or "attery" in name else "Connections", t, st, "E2",
      "Label text is a component label, not part of the symbol" if st == "duplicate" else "")
for i, (name, t, st) in enumerate([
        ("Terminal (open circle with lead)", "el.terminal", "existing"), ("Ground, bar (inverted T)", "el.ground.bar", "duplicate"),
        ("Earth ground", "el.earth", "existing"), ("Signal ground, hollow triangle", "el.ground.signal", "existing"),
        ("Supply terminal -", "el.rail.neg", "pending"), ("Supply terminal -5V", "el.rail.neg", "duplicate"),
        ("Supply terminal VEE", "el.rail.neg", "duplicate"), ("Single cell (horizontal)", "el.cell", "duplicate"),
        ("Battery, multi-cell (horizontal)", "el.battery", "duplicate"), ("Battery, multi-cell with break (120V)",
                                                                          "el.battery.long", "pending")], 1):
    e(S, 3, i, name, E, "Connections" if i < 8 else "Sources", t, st, "E2")
for i, name in enumerate(["Wire", "Junction dot", "Wire crossing, hop (up)", "Wire crossing, hop (left)",
                          "Wire crossing, double hop", "Wire crossing, hop (vertical)"], 1):
    e(S, 4, i, name, E, "Connections", "editor", "convention", "-", "Wire drawing / junction handled by the editor")

S = "Diodes (semiconductor)"
drow = [("Diode", "el.diode", "existing"), ("Zener diode", "el.diode.zener", "existing"),
        ("Schottky diode", "el.diode.schottky", "pending"), ("Varicap (varactor) diode", "el.diode.varicap", "pending"),
        ("Tunnel diode", "el.diode.tunnel", "decision"), ("Diode with bracket cathode (second form)", "el.diode.bracket2", "decision"),
        ("LED", "el.led", "existing"), ("Photodiode", "el.photodiode", "pending"),
        ("Diode with integral cathode mark (S form)", "el.diode.s", "decision"),
        ("Diode, outline with cathode bars (10th form)", "el.diode.form10", "decision")]
for i, (name, t, st) in enumerate(drow, 1):
    e(S, 1, i, name, EL, "Semiconductors", t, st, "E3",
      "Source gives no labels for this cathode variant; identification needed before implementation (Q4)"
      if st == "decision" else "Filled style")
for i, (name, _t, _st) in enumerate(drow[:9], 1):
    e(S, 2, i, name + " (outline style)", EL, "Semiconductors", f"ECL-DIO1.{i}", "duplicate", "E3",
      "Outline vs filled is a drawing style, same meaning")
for i, (name, t, st) in enumerate([
        ("LED (vertical)", "el.led", "duplicate"), ("Photodiode (vertical)", "el.photodiode", "duplicate"),
        ("Zener diode with voltage label (vertical)", "el.diode.zener", "duplicate"),
        ("DIAC (antiparallel diodes)", "el.diac", "pending"), ("TRIAC", "el.triac", "pending"),
        ("Thyristor (SCR), cathode gate", "el.scr", "pending"),
        ("Bidirectional transient suppressor (two zeners)", "el.tvs.bidir", "pending"),
        ("Bidirectional zener with bent bars", "el.diode.zener.bidir", "decision"),
        ("Bridge rectifier block", "el.rectifier.block", "pending"), ("Bridge rectifier (diamond)", "el.rectifier.bridge", "pending")], 1):
    e(S, 3, i, name, EL, "Semiconductors" if "rectifier" not in name else "Power electronics", t, st, "E3",
      "Two adjacent forms differ only in bar style; identify before implementing (Q4)" if st == "decision" else "")
for i, (name, t) in enumerate([("DIAC (outline)", "el.diac"), ("TRIAC (outline)", "el.triac"),
                               ("Thyristor (outline)", "el.scr"), ("TVS (outline)", "el.tvs.bidir"),
                               ("Bidirectional zener (outline)", "el.diode.zener.bidir")], 1):
    e(S, 4, i, name, EL, "Semiconductors", t, "duplicate", "E3", "Outline style of row 3")
e(S, 4, 6, "AC/DC converter (rectifier) block", E, "Power electronics", "el.converter.acdc", "pending", "E3")
e(S, 5, 1, "Circle with cathode bar (unlabelled)", EL, "Semiconductors", "-", "decision", "E3",
  "No label in source; possibly a vacuum/gas diode or photocell. Not implemented without identification (Q4)")

S = "Linear components"
lin = [(1, 1, "Thermistor (IEC rectangle)", "el.thermistor.iec"), (1, 2, "Thermistor (zigzag)", "el.thermistor.ansi"),
       (1, 3, "Resistor, rectangular-wave form", "el.resistor.wave"), (1, 4, "Inductor with magnetic core", "el.inductor.core"),
       (1, 5, "Inductor, adjustable, with core", "el.inductor.core.var"), (2, 1, "Resistor (IEC)", "el.resistor.iec"),
       (2, 2, "Resistor (ANSI)", "el.resistor.ansi"), (2, 3, "Heating element / filled resistor", "el.resistor.filled"),
       (2, 4, "Inductor", "el.inductor"), (2, 5, "Inductor, adjustable", "el.inductor.var"),
       (3, 1, "Potentiometer, rheostat connection (IEC)", "el.rheostat.iec"), (3, 2, "Rheostat (ANSI)", "el.rheostat.ansi"),
       (3, 3, "Rheostat (filled body)", "el.rheostat.filled"), (3, 4, "Photoresistor (LDR, IEC)", "el.ldr.iec"),
       (3, 5, "Photoresistor (LDR, ANSI)", "el.ldr.ansi"), (3, 6, "Capacitor, adjustable (trimmer)", "el.capacitor.trim"),
       (4, 1, "Trimmer resistor, rheostat connection (IEC)", "el.trim.rheostat.iec"),
       (4, 2, "Trimmer resistor, rheostat connection (ANSI)", "el.trim.rheostat.ansi"),
       (4, 3, "Trimmer resistor, rheostat connection (filled)", "el.trim.rheostat.filled"),
       (4, 4, "Photoresistor in envelope (IEC)", "el.ldr.iec.env"), (4, 5, "Photoresistor in envelope (ANSI)", "el.ldr.ansi.env"),
       (5, 1, "Resistor, adjustable (IEC)", "el.resistor.var.iec"), (5, 2, "Resistor, adjustable, preset (ANSI)", "el.resistor.preset.ansi"),
       (5, 3, "Resistor, adjustable, preset (filled)", "el.resistor.preset.filled"),
       (6, 1, "Potentiometer (IEC)", "el.potentiometer.iec"), (6, 2, "Potentiometer (ANSI)", "el.potentiometer.ansi"),
       (6, 3, "Inductor with tap / sliding contact", "el.inductor.tap"), (6, 4, "Capacitor", "el.capacitor"),
       (6, 5, "Capacitor, polarised (curved plate)", "el.capacitor.pol.curved"),
       (6, 6, "Capacitor, polarised (rectangle plate)", "el.capacitor.pol")]
existing_el = {"el.resistor.iec", "el.resistor.ansi", "el.inductor", "el.potentiometer.iec", "el.capacitor",
               "el.capacitor.pol", "el.resistor.var.iec"}
for r, i, name, t in lin:
    st = "existing" if t in existing_el else "pending"
    notes = ""
    if t == "el.resistor.filled":
        st, notes = "decision", "Filled rectangle meaning varies by convention (heater element vs. fixed resistor); Q4"
    if t in ("el.rheostat.filled", "el.trim.rheostat.filled", "el.resistor.preset.filled"):
        st, notes = "decision", "Depends on the meaning of the filled-body resistor (Q4)"
    if t == "el.resistor.var.iec":
        notes = "Verify the existing drawing matches (variable vs preset arrow)"
    if t == "el.capacitor.pol":
        notes = "Existing el.capacitor.pol (IEEE 315) - verify which plate form it uses"
    e(S, r, i, name, EL, "Passive", t, st, "E1", notes)

S = "Transformers"
for r, i, name, t in [(1, 1, "Transformer, iron core, dots same end (in phase)", "el.transformer.dot"),
                      (1, 2, "Transformer, iron core, step-down, dots same end", "el.transformer.dot.step"),
                      (1, 3, "Transformer, centre-tapped secondary", "el.transformer.ct"),
                      (1, 4, "Transformer, two secondary windings", "el.transformer.2sec"),
                      (2, 1, "Transformer, iron core, dots opposite ends (inverting)", "el.transformer.inv"),
                      (2, 2, "Transformer, step-down, dots opposite ends", "el.transformer.inv.step"),
                      (2, 3, "Transformer, centre-tapped secondary, dots opposite ends", "el.transformer.ct.inv"),
                      (2, 4, "Autotransformer (tapped single winding)", "el.autotransformer"),
                      (2, 5, "Autotransformer with core", "el.autotransformer.core")]:
    e(S, r, i, name, E, "Transformers", t, "pending", "E5",
      "Existing el.transformer has no polarity dots; dotted variants are distinct" if i == 1 and r == 1 else "")

S = "Transistors"
tr = [("NPN bipolar transistor", "el.npn", "existing"), ("NPN phototransistor", "el.npn.photo", "pending"),
      ("N-channel JFET", "el.jfet.n", "pending"), ("N-channel MOSFET, enhancement, in envelope", "el.nmos.env", "pending"),
      ("N-channel MOSFET, enhancement (no envelope)", "el.nmos", "pending"),
      ("MOSFET, no body arrow (4th form)", "el.mos.plain", "decision"),
      ("N-channel MOSFET, depletion, in envelope", "el.nmos.depl.env", "decision")]
trp = [("PNP bipolar transistor", "el.pnp", "existing"), ("PNP phototransistor", "el.pnp.photo", "pending"),
       ("P-channel JFET", "el.jfet.p", "pending"), ("P-channel MOSFET, enhancement, in envelope", "el.pmos.env", "pending"),
       ("P-channel MOSFET, enhancement (no envelope)", "el.pmos", "pending"),
       ("P-channel MOSFET, gate bubble form", "el.pmos.bubble", "pending"),
       ("P-channel MOSFET, depletion, in envelope", "el.pmos.depl.env", "decision")]
for r, lst in ((1, tr), (2, trp)):
    for i, (name, t, st) in enumerate(lst, 1):
        e(S, r, i, name, EL, "Semiconductors", t, st, "E4",
          "Gate/channel line style needs confirming against the source before implementation (Q4)" if st == "decision" else "")

S = "Mechanical switches"
for r, i, name, t, st, notes in [
        (1, 1, "Switch, single pole, open (make)", "el.contact.no.iec", "existing",
         "Same function as existing make contact; ECL draws terminal circles"),
        (2, 1, "Switch, single pole, drawn closed", "el.switch.closed", "decision",
         "Blade resting on contact: break (NC) contact or a make contact drawn actuated? Q4"),
        (3, 1, "Switch, single pole double throw (changeover)", "el.switch.spdt", "pending", ""),
        (4, 1, "Changeover switch, centre/blade to common (second position drawing)", "el.switch.spdt", "duplicate",
         "Same switch drawn in another position"),
        (1, 2, "Relay: coil with one make contact (linked)", "el.relay.no", "pending", "Coil and contact linked by a dashed line"),
        (2, 2, "Relay: coil with contact drawn closed", "el.relay.nc", "decision", "As r2 #1 (Q4)"),
        (3, 2, "Switch, two pole, linked (DPST)", "el.switch.dpst", "pending", ""),
        (1, 3, "Relay: coil with two linked make contacts", "el.relay.2no", "pending", ""),
        (2, 3, "Rotary selector switch, four positions", "el.switch.rotary4", "pending", "")]:
    row(f"ECL-MEC{r}.{i}", "ECL", f"{S} r{r} #{i}", name, E, "Switching (IEC)", t, st, "E6", notes)

S = "Semiconductor devices"
for r, i, name, t in [(1, 1, "Schmitt trigger inverter", "el.logic.schmitt.not"),
                      (2, 1, "Schmitt trigger buffer", "el.logic.schmitt"),
                      (1, 2, "Operational amplifier", "el.opamp"),
                      (1, 3, "Operational amplifier with supply pins (+ input on top)", "el.opamp.supply"),
                      (1, 4, "Operational amplifier with supply pins (- input on top)", "el.opamp.supply.inv"),
                      (1, 5, "Voltage regulator, 3 terminal (e.g. 7805)", "el.regulator")]:
    e(S, r, i, name, EL, "Integrated" if "Schmitt" not in name else "Logic", t,
      "existing" if t == "el.opamp" else "pending", "E8" if "Schmitt" not in name else "E7",
      "Part number '7805' is a label, not drawn into the symbol" if t == "el.regulator" else "")

S = "Vacuum tubes"
for i, (name, t) in enumerate([("Vacuum diode, directly heated", "el.tube.diode.direct"),
                               ("Vacuum diode, indirectly heated (cathode)", "el.tube.diode"),
                               ("Triode", "el.tube.triode"), ("Tetrode", "el.tube.tetrode")], 1):
    e(S, 1, i, name, EL, "Vacuum tubes", t, "pending", "E8",
      "4th form has two grids: tetrode (no suppressor grid shown)" if i == 4 else "")

# =============================================================== director decisions (2026-11-01)
# Q1 both styles: a Y32 row whose function already has an ISO symbol (existing, or a duplicate of an HO row) gets
#    its own ANSI Y32.10-style symbol, id suffix ".ansi" - unless, when drawn, the ANSI figure turns out identical
#    to the ISO symbol (then the row becomes "equivalent", naming that symbol).
# Q2 minimal valve-dialog change allowed: third operator slot per side, proportional (infinite positioning) bars,
#    transition position.
# Q3 composite assemblies left out: "excluded" (build from parts inside an enclosure).
# Q4 unlabelled / ambiguous ECL drawings left out: "blocked".
Q2_CONFIG = {"HO-S18", "HO-S19", "HO-C34", "HO-C36", "HO-C37", "Y32-10.11.4", "Y32-10.14", "Y32-10.15",
             "Y32-11.4.6s", "Y32-11.4.7s"}
Q1_SKIP = {"Y32-3.9", "Y32-3.9.1", "Y32-11.1", "Y32-7.11a", "Y32-10.9.1n", "Y32-10.9.2c", "Y32-10.13.1n",
           "Y32-10.13.1a", "Y32-4.1.2.1", "Y32-4.1.1b", "Y32-6.1.2.1", "Y32-8.3.1.2", "Y32-8.7.1"}
for r in R:
    k, st = r["key"], r["status"]
    if st == "decision":
        if k in Q2_CONFIG:
            r["status"], r["batch"] = "configurator", "F1"
            r["notes"] = (r["notes"] + "; " if r["notes"] else "") + "Director Q2: dialog change allowed"
            if k == "Y32-11.4.7s":
                r["notes"] += "; throttled exhausts are not a configurator feature (drawn without them, noted)"
        elif r["source"] == "ECL":
            r["status"] = "blocked"
            r["notes"] = "Director Q4: unlabelled/ambiguous drawing left out until identified. " + r["notes"]
        elif k.startswith("Y32-7.11"):
            r["status"] = "blocked"
            r["notes"] = ("Stacked (parallel) operator boxes are a further configurator layout feature not covered "
                          "by the Q2 change; left out")
        else:
            r["status"], r["batch"] = "excluded", "-"
            r["notes"] = "Director Q3: composite assembly left out; build it from parts inside an enclosure. " + r["notes"]
    elif r["source"] == "Y32" and st in ("existing", "duplicate") and k not in Q1_SKIP \
            and not r["target"].startswith(("dcv", "fl.*.dcv", "editor", "HO-B09", "HO-B10")) \
            and "dcv operator" not in r["target"]:
        base = r["target"].split(" ")[0]
        if base.startswith("HO-"):
            base = next(x["target"] for x in R if x["key"] == base)
        r["notes"] = (f"Director Q1: ANSI-style variant of {base}; becomes 'equivalent' if the ANSI drawing is "
                      f"identical. " + r["notes"]).strip()
        r["target"] = base.split(" ")[0] + ".ansi"
        r["status"] = "pending"
        if r["batch"] == "-":
            r["batch"] = {"Valves": "F8", "Pumps & motors": "F5", "Non-return & flow": "F8"}.get(r["group"], "F8")
    elif r["source"] == "Y32" and st == "duplicate" and "dcv operator" in r["target"]:
        r["status"] = "existing" if r["target"] in ("dcv operator 'pilot + spring'",) else "configurator"
        r["notes"] = ("Director Q1: ANSI drawing of this operator is offered as an operator style where it differs. "
                      + r["notes"]).strip()

# =============================================================== progress (per batch)
def op_ids(*ops):
    out = []
    for o in ops:
        out += [f"dcv operator '{o}'", f"fl.hyd.op.{o}", f"fl.pneu.op.{o}"]
    return "; ".join(out)


# key: (status, target, note to append). "validated" = implemented and covered by the batch's automated tests.
PROGRESS = {
    # ---- batch F1: directional-valve configurator + standalone operator elements
    "HO-B17": ("validated", op_ids("spring"), "Operator existed; standalone element added"),
    "HO-B21": ("validated", op_ids("detent"), "One notch per switching position; marker on the rest position"),
    "HO-S01": ("validated", op_ids("manual"), "Operator existed; standalone element added"),
    "HO-S02": ("validated", op_ids("pushbutton"), "Operator existed; standalone element added"),
    "HO-S03": ("validated", op_ids("pushpull"), ""),
    "HO-S04": ("validated", op_ids("lever"), "Operator existed; standalone element added"),
    "HO-S05": ("validated", op_ids("pedal"), ""),
    "HO-S06": ("validated", op_ids("pedal2"), ""),
    "HO-S07": ("validated", op_ids("plunger"), ""),
    "HO-S08": ("validated", op_ids("plunger.limited"), ""),
    "HO-S09": ("validated", op_ids("spring"), "Operator existed; standalone element added"),
    "HO-S10": ("validated", op_ids("roller"), ""),
    "HO-S11": ("validated", op_ids("roller.lever"), "Arrow drawn as in the source (operating direction)"),
    "HO-S12": ("validated", op_ids("solenoid"), "Operator existed; standalone element added"),
    "HO-S13": ("validated", op_ids("solenoid.pushpull"), ""),
    "HO-S14": ("validated", op_ids("pilot.direct"), "Pilot terminal X / 12 at the line end"),
    "HO-S15": ("validated", op_ids("pilot.applied"), "Pilot terminal on the box's outer edge (the source draws no line)"),
    "HO-S16": ("validated", op_ids("motor"), ""),
    "HO-S17": ("validated", op_ids("motor.other"), ""),
    "HO-S18": ("validated", "dcv option 'transition'", "Two-position valves; dashed transition position"),
    "HO-S19": ("validated", "dcv option 'proportional'", "Bars along the envelopes"),
    "HO-S21": ("validated", op_ids("pilot.internal"),
               "Configurator form: box with triangle, no pilot port (Y32 7.7.2). The source's dashed line from P is "
               "drawn by the user when the valve is drawn by hand"),
    "HO-S22": ("validated", op_ids("pilot"), "External pilot = existing pilot operator with port X / 12"),
    "HO-C32": ("existing", "fl.hyd.dcv",
               "Spool form 1 centre is not legible at the source's resolution (float or tandem); both centres are "
               "available in the configurator"),
    "HO-C33": ("existing", "fl.hyd.dcv", "Spool form 2 = closed centre, available in the configurator"),
    "HO-C34": ("validated", "dcv operator 'solenoid.and.pilot.int'", "With spring as a second operator"),
    "HO-C36": ("validated", op_ids("solenoid.prop") + "; dcv option 'proportional'", ""),
    "HO-C37": ("validated", "dcv operator 'solenoid.and.pilot.int'; dcv operator 'solenoid.prop'; "
                            "dcv option 'proportional'",
               "Three operators per side (spring, pilot stage, proportional solenoid)"),
    "Y32-7.2.3": ("validated", "dcv operator 'pedal'", "Same operator as HO-S05"),
    "Y32-7.3": ("validated", op_ids("cam") + "; dcv operator 'roller'", "First form = roller, second = roller on cam"),
    "Y32-7.4": ("validated", "dcv operator 'detent'", "Same operator as HO-B21"),
    "Y32-7.5": ("validated", op_ids("compensated"),
                "Box with arrow parallel to the short side (2.10); the arc beside it in the figure is not "
                "reproduced (meaning unclear)"),
    "Y32-7.6.2": ("validated", op_ids("motor.reversing"), ""),
    "Y32-7.7.1": ("validated", op_ids("pilot.remote"), "Pilot line into an empty box"),
    "Y32-7.7.2": ("validated", "dcv operator 'pilot.internal'", "Same operator as HO-S21"),
    "Y32-7.7.3a": ("validated", op_ids("release.remote"), ""),
    "Y32-7.7.3b": ("validated", op_ids("release.internal"), ""),
    "Y32-7.7.5": ("blocked", "-", "Pilot differential figures are not legible enough to reproduce without guessing"),
    "Y32-7.8.1a": ("validated", op_ids("solenoid.or.pilot.ext"), "Triangle fill follows the medium"),
    "Y32-7.8.1b": ("validated", op_ids("solenoid.or.pilot.int"), "Triangle fill follows the medium"),
    "Y32-7.8.2": ("validated", op_ids("solenoid.and.pilot.ext", "solenoid.and.pilot.int"),
                  "Pilot supply enters from above (terminal at the top)"),
    "Y32-7.9.1": ("validated", op_ids("thermal"), ""),
    "Y32-7.9.2": ("validated", op_ids("thermal.bulb"), "Bulb drawn outward; the source draws it below the valve"),
    "Y32-7.10": ("validated", op_ids("servo"), ""),
    "Y32-7.11a": ("validated", "dcv operator 'pilot.applied'", "Basic form = pilot-applied box"),
    "Y32-10.11.3": ("validated", "dcv pattern 'b-t'; dcv pattern 'apt'; dcv pattern 'ab'; dcv pattern 'a-t'; "
                                 "dcv pattern 'ab-pt'",
                    "Five new centre conditions; the other three (closed, open, 5-port closed) already existed"),
    "Y32-10.11.4": ("validated", "dcv option 'transition'", ""),
    "Y32-10.14": ("validated", "dcv option 'proportional'",
                  "Three-way infinite-positioning valves: 3/2 valve types with the proportional option"),
    "Y32-10.15": ("validated", "dcv option 'proportional'", "Four-way: 4/2 and 4/3 with the proportional option"),
    "Y32-11.4.6s": ("validated", "dcv operator 'solenoid.and.pilot.ext'; dcv operator 'manual'",
                    "Simplified symbol reproducible with 2 operators per side (pilot stage + manual override)"),
    "Y32-11.4.7s": ("validated", "dcv operator 'detent'; dcv operator 'solenoid.and.pilot.ext'",
                    "Throttled exhausts are drawn separately (not a configurator feature)"),
}
for r in R:
    if r["key"] in PROGRESS:
        st, tgt, note = PROGRESS[r["key"]]
        r["status"], r["target"] = st, tgt
        if note:
            r["notes"] = (r["notes"] + "; " if r["notes"] else "") + note
        if st == "validated":
            r["batch"] = "F1"
for r in R:
    if r["key"] == "HO-S20":
        r.update(status="annotation", target="gen.coupling", batch="F2",
                 notes="Shaft coupling: mechanical drafting element, not a valve operator")
assert not set(PROGRESS) - {r["key"] for r in R}, set(PROGRESS) - {r["key"] for r in R}

# =============================================================== write
here = os.path.dirname(os.path.abspath(__file__))
keys = [r["key"] for r in R]
dup = {k for k in keys if keys.count(k) > 1}
assert not dup, f"duplicate inventory keys: {sorted(dup)}"
with open(os.path.join(here, "inventory.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(R[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(R)
if __name__ == "__main__":
    from collections import Counter
    print(len(R), "rows")
    print(Counter(r["status"] for r in R))
    print(Counter(r["source"] for r in R))
