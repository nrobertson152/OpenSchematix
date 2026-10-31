"""Hydraulic and pneumatic (fluid power) symbols, drawn in ISO 1219-1 style.

Conventions used:
  * Energy-direction triangles are filled for hydraulic and hollow for
    pneumatic media.
  * Working lines are solid; pilot and drain lines are dashed (set per wire).
  * Hydraulic ports use letter codes P, T, A, B, X, Y.
  * Pneumatic valve ports use the numeric codes 1 (supply), 2/4 (outputs),
    3/5 (exhausts) and 10/12/14 (pilot), following ISO 11727 / ISO 5599 usage.

Directional control valves are parametric: the number of switching positions,
the flow path in each position and the operators on each side are stored in
the component's `params`, so a valve can be reconfigured after placement.
"""
from __future__ import annotations

import math

from .base import (
    ISO, Geometry, SymbolDef, Terminal as T, arc, arrow, arrowhead, circle, line, poly,
    polyline, rect, text, zigzag,
)

H = "Hydraulic"
P = "Pneumatic"


def _tri(fill):
    return fill  # hydraulic: filled, pneumatic: hollow


# ---------------------------------------------------------------- energy conversion
def pump(fill, variable=False):
    p = [circle(0, 0, 12), line(0, -20, 0, -12), line(0, 12, 0, 20),
         poly(0, -12, -4.5, -4.5, 4.5, -4.5, fill=fill),
         # drive shaft (two parallel lines) on the right
         line(12, -1.5, 19, -1.5, w="thin"), line(12, 1.5, 19, 1.5, w="thin")]
    if variable:
        p += arrow(-11, 11, 13, -13, head=4.5)
    return p


def motor(fill, variable=False):
    y = -math.sqrt(144 - 36)
    p = [circle(0, 0, 12), line(0, -20, 0, -12), line(0, 12, 0, 20),
         poly(-6, y, 6, y, 0, -4.5, fill=fill),
         line(12, -1.5, 19, -1.5, w="thin"), line(12, 1.5, 19, 1.5, w="thin")]
    if variable:
        p += arrow(-11, 11, 13, -13, head=4.5)
    return p


def cylinder_double(double_rod=False):
    p = [rect(-30, -10, 20, 10), line(-10, -10, -10, 10, w="thick"), line(-10, 0, 35, 0),
         line(-20, -20, -20, -10), line(10, -20, 10, -10)]
    if double_rod:
        p.append(line(-35, 0, -10, 0))
    return p


def cylinder_single_spring():
    return [rect(-30, -10, 20, 10), line(-10, -10, -10, 10, w="thick"), line(-10, 0, 35, 0),
            line(-20, -20, -20, -10), zigzag(-9, -6, 19, -6, n=6, amp=3)]


# ---------------------------------------------------------------- valves
def relief_valve(fill):
    """Pressure-relief valve, direct operated, adjustable (normally closed)."""
    p = [rect(-15, -15, 15, 15), line(0, 20, 0, 15), line(0, -15, 0, -20),
         # flow arrow offset from the port axis -> normally closed
         *arrow(6, 10, 6, -10, head=4),
         # adjustable spring on the right
         line(15, 0, 17, 0), zigzag(17, 0, 29, 0, n=6, amp=4), *arrow(17, 7, 30, -7, head=3.5),
         # pilot line from the inlet to the opposite (left) side
         polyline([(0, 17), (-22, 17), (-22, 0), (-15, 0)], dash=True, w="thin")]
    return Geometry(p, [T("P", 0, 20, "d"), T("T", 0, -20, "u")])


def reducing_valve(fill, ports=("P", "A")):
    """Pressure-reducing valve, direct operated (normally open), pilot from outlet."""
    p = [rect(-15, -15, 15, 15), line(0, 20, 0, 15), line(0, -15, 0, -20),
         *arrow(0, 10, 0, -10, head=4),
         line(15, 0, 17, 0), zigzag(17, 0, 29, 0, n=6, amp=4), *arrow(17, 7, 30, -7, head=3.5),
         polyline([(0, -17), (-22, -17), (-22, 0), (-15, 0)], dash=True, w="thin")]
    return Geometry(p, [T(ports[0], 0, 20, "d"), T(ports[1], 0, -20, "u")])


def check_valve_prims(x0=0.0, y0=0.0, spring=False):
    # Seat drawn as a V whose mouth holds the ball. Free flow from the seat
    # (vertex) side towards the ball side: left -> right.
    p = [polyline([(x0 + 4, y0 - 8), (x0 - 6, y0), (x0 + 4, y0 + 8)]), circle(x0 + 4, y0, 6)]
    if spring:
        p.append(zigzag(x0 + 10, y0, x0 + 18, y0, n=4, amp=3))
    return p


def check_valve(spring=False):
    p = [line(-20, 0, -6, 0)] + check_valve_prims(spring=spring)
    p.append(line(18 if spring else 10, 0, 20, 0))
    return Geometry(p, [T("1", -20, 0, "l"), T("2", 20, 0, "r")])


def throttle_prims(adjustable):
    p = [arc(0, -10, 8, 210, 120), arc(0, 10, 8, 30, 120)]
    if adjustable:
        p += arrow(-8, 9, 9, -10, head=3.5)
    return p


def throttle(adjustable):
    return Geometry([line(-20, 0, 20, 0)] + throttle_prims(adjustable), [T("1", -20, 0, "l"), T("2", 20, 0, "r")])


def one_way_flow_control():
    p = [line(-30, 0, 30, 0)] + throttle_prims(True)
    # bypass with check valve: free flow 1 -> 2 through the check
    p += [polyline([(-20, 0), (-20, -20), (-6, -20)]), polyline([(10, -20), (20, -20), (20, 0)])]
    p += check_valve_prims(0, -20)
    p += [circle(-20, 0, 1.6, fill=True, w="thin"), circle(20, 0, 1.6, fill=True, w="thin")]
    return Geometry(p, [T("1", -30, 0, "l"), T("2", 30, 0, "r")])


def shuttle_valve(names):
    p = [rect(-12, -7, 12, 7), line(-20, 0, -12, 0), line(12, 0, 20, 0), line(0, -7, 0, -20),
         circle(-5, 0, 4), line(-10, -5, -10, 5, w="thin"), line(10, -5, 10, 5, w="thin")]
    return Geometry(p, [T(names[0], -20, 0, "l"), T(names[1], 20, 0, "r"), T(names[2], 0, -20, "u")])


# ---------------------------------------------------------------- energy storage / conditioning
def reservoir():
    p = [polyline([(-15, -6), (-15, 8), (15, 8), (15, -6)]), line(0, -20, 0, 4)]
    return Geometry(p, [T("T", 0, -20, "u")])


def accumulator():
    p = [arc(0, -7, 8, 0, 180), arc(0, 7, 8, 180, 180), line(-8, -7, -8, 7), line(8, -7, 8, 7),
         line(-8, 0, 8, 0), line(0, 15, 0, 20)]
    return Geometry(p, [T("P", 0, 20, "d")])


def air_receiver():
    p = [arc(-12, 0, 8, 90, 180), arc(12, 0, 8, -90, 180), line(-12, -8, 12, -8), line(-12, 8, 12, 8),
         line(0, -8, 0, -20)]
    return Geometry(p, [T("1", 0, -20, "u")])


def filter_geo(names=("1", "2")):
    p = [line(-20, 0, -10, 0), line(10, 0, 20, 0), poly(-10, 0, 0, -10, 10, 0, 0, 10),
         line(0, -10, 0, 10, dash=True, w="thin")]
    return Geometry(p, [T(names[0], -20, 0, "l"), T(names[1], 20, 0, "r")])


def gauge(name):
    p = [circle(0, 0, 10), line(0, 10, 0, 20), *arrow(-6, 6, 6, -6, head=3.5)]
    return Geometry(p, [T(name, 0, 20, "d")])


# ================================================================ directional valves
ENV = 40          # envelope (switching position square) size, units
HALF = ENV / 2
LEAD = 10         # port lead length outside the envelope

# Port layouts relative to the centre of an envelope: (name, dx, side)
LAYOUTS = {
    ("hyd", 2): [("A", 0, "top"), ("P", 0, "bot")],
    ("hyd", 3): [("A", -10, "top"), ("P", -10, "bot"), ("T", 10, "bot")],
    ("hyd", 4): [("A", -10, "top"), ("B", 10, "top"), ("P", -10, "bot"), ("T", 10, "bot")],
    ("pneu", 2): [("2", 0, "top"), ("1", 0, "bot")],
    ("pneu", 3): [("2", -10, "top"), ("1", -10, "bot"), ("3", 10, "bot")],
    ("pneu", 5): [("4", -10, "top"), ("2", 10, "top"), ("5", -10, "bot"), ("1", 0, "bot"), ("3", 10, "bot")],
}

# Flow-path patterns: arrows (from, to), plain links (undirected), blocked ports.
PATTERNS = {
    2: {
        "open": {"label": "Open (P→A)", "arrows": [(1, 0)], "blocked": []},
        "closed": {"label": "Closed", "arrows": [], "blocked": [0, 1]},
    },
    3: {
        "P-A": {"label": "P→A, T blocked", "arrows": [(1, 0)], "blocked": [2]},
        "A-T": {"label": "A→T, P blocked", "arrows": [(0, 2)], "blocked": [1]},
        "closed": {"label": "All ports blocked", "arrows": [], "blocked": [0, 1, 2]},
    },
    4: {
        "parallel": {"label": "P→A, B→T (parallel)", "arrows": [(2, 0), (1, 3)], "blocked": []},
        "crossed": {"label": "P→B, A→T (crossed)", "arrows": [(2, 1), (0, 3)], "blocked": []},
        "closed": {"label": "Closed centre (all blocked)", "arrows": [], "blocked": [0, 1, 2, 3]},
        "tandem": {"label": "Tandem centre (P→T, A B blocked)", "special": "tandem", "blocked": [0, 1]},
        "float": {"label": "Float centre (A B T linked, P blocked)", "special": "float", "blocked": [2]},
        "open": {"label": "Open centre (all linked)", "special": "open", "blocked": []},
    },
    5: {
        "1-2": {"label": "1→2, 4→5", "arrows": [(3, 1), (0, 2)], "blocked": []},
        "1-4": {"label": "1→4, 2→3", "arrows": [(3, 0), (1, 4)], "blocked": []},
        "closed": {"label": "Closed centre (all blocked)", "arrows": [], "blocked": [0, 1, 2, 3, 4]},
        "exhaust": {"label": "Exhausted centre (4→5, 2→3, 1 blocked)", "arrows": [(0, 2), (1, 4)], "blocked": [3]},
    },
}

OPERATORS = {
    "spring": "Spring",
    "solenoid": "Solenoid",
    "pilot": "Pilot pressure",
    "lever": "Lever",
    "pushbutton": "Push-button",
    "manual": "Manual, general",
}

VALVE_TYPES = {
    "hyd": {"2/2": (2, 2), "3/2": (3, 2), "4/2": (4, 2), "4/3": (4, 3)},
    "pneu": {"2/2": (2, 2), "3/2": (3, 2), "5/2": (5, 2), "5/3": (5, 3)},
}


def default_valve_params(medium="hyd", vtype=None):
    if medium == "hyd":
        vtype = vtype or "4/3"
    else:
        vtype = vtype or "5/2"
    ports, npos = VALVE_TYPES[medium][vtype]
    defaults = {
        (2, 2): ["open", "closed"],
        (3, 2): ["P-A", "A-T"],
        (4, 2): ["parallel", "crossed"],
        (4, 3): ["parallel", "closed", "crossed"],
        (5, 2): ["1-4", "1-2"],
        (5, 3): ["1-4", "closed", "1-2"],
    }[(ports, npos)]
    if npos == 3:
        left, right = ["spring", "solenoid"], ["spring", "solenoid"]
    else:
        left, right = ["solenoid"], ["spring"]
    return {"medium": medium, "type": vtype, "positions": list(defaults), "left": left, "right": right}


def normal_position(npos, left, right):
    """Index of the position in which the ports are drawn (the rest position)."""
    if npos == 3:
        return 1
    if "spring" in right and "spring" not in left:
        return npos - 1
    if "spring" in left and "spring" not in right:
        return 0
    return npos - 1


def _pilot_name(medium, side, positions, nports):
    if medium == "hyd":
        return "X" if side < 0 else "Y"
    pos = positions[0] if side < 0 else positions[-1]
    if nports == 5:
        return "14" if pos == "1-4" else "12"
    if nports in (2, 3):
        return "12" if pos in ("open", "P-A") else "10"
    return "X" if side < 0 else "Y"


def _operator(kind, x, s, fill):
    """Draw one operator starting at x (envelope side), extending in direction s.
    Returns (prims, width)."""
    p = []
    if kind == "spring":
        p.append(zigzag(x, 0, x + s * 10, 0, n=6, amp=5))
        return p, 10
    if kind == "solenoid":
        a, b = sorted((x, x + s * 10))
        p += [rect(a, -6, b, 6), line(a, 6, b, -6)]
        return p, 10
    if kind == "pilot":
        # triangle pointing at the valve, then the (dashed) pilot line to port
        p += [poly(x, 0, x + s * 8, -4.5, x + s * 8, 4.5, fill=fill),
              line(x + s * 8, 0, x + s * 20, 0, dash=True, w="thin")]
        return p, 20
    if kind == "lever":
        p += [line(x, 0, x + s * 5, 0), line(x + s * 5, 0, x + s * 10, -9)]
        return p, 10
    if kind == "pushbutton":
        p += [line(x, 0, x + s * 5, 0), arc(x + s * 5, 0, 4, 90, -180 if s > 0 else 180)]
        return p, 10
    if kind == "manual":
        p += [line(x, 0, x + s * 8, 0), line(x + s * 8, -5, x + s * 8, 5)]
        return p, 10
    return p, 0


def build_valve(params):
    medium = params.get("medium", "hyd")
    vtype = params.get("type", "4/3")
    if medium not in VALVE_TYPES or vtype not in VALVE_TYPES[medium]:
        medium, vtype = "hyd", "4/3"
    nports, npos = VALVE_TYPES[medium][vtype]
    positions = list(params.get("positions") or [])
    patterns = PATTERNS[nports]
    fallback = default_valve_params(medium, vtype)["positions"]
    positions = [positions[i] if i < len(positions) and positions[i] in patterns else fallback[i] for i in range(npos)]
    left = [o for o in params.get("left", []) if o in OPERATORS]
    right = [o for o in params.get("right", []) if o in OPERATORS]
    fill = medium == "hyd"
    layout = LAYOUTS[(medium, nports)]

    W = ENV * npos
    x0 = -W / 2
    p = []
    for i in range(npos):
        cx = x0 + HALF + ENV * i
        p.append(rect(cx - HALF, -HALF, cx + HALF, HALF))
        pat = patterns[positions[i]]

        def edge(idx, inset=3.0):
            name, dx, side = layout[idx]
            y = -HALF + inset if side == "top" else HALF - inset
            return (cx + dx, y)

        for a, b in pat.get("arrows", []):
            (ax, ay), (bx, by) = edge(a), edge(b)
            p += arrow(ax, ay, bx, by, head=4.5)
        for idx in pat.get("blocked", []):
            name, dx, side = layout[idx]
            sg = -1 if side == "top" else 1
            yb = sg * HALF
            p += [line(cx + dx, yb, cx + dx, yb - sg * 7), line(cx + dx - 4, yb - sg * 7, cx + dx + 4, yb - sg * 7)]
        sp = pat.get("special")
        if sp == "tandem":
            # P and T joined inside the envelope
            p.append(polyline([(cx - 10, HALF), (cx - 10, 6), (cx + 10, 6), (cx + 10, HALF)]))
        elif sp == "float":
            p.append(line(cx + 10, -HALF, cx + 10, HALF))                              # B - T
            p.append(polyline([(cx - 10, -HALF), (cx - 10, 4), (cx + 10, 4)]))        # A - T
            p.append(circle(cx + 10, 4, 1.6, fill=True, w="thin"))
        elif sp == "open":
            p += [line(cx - 10, -HALF, cx - 10, HALF), line(cx + 10, -HALF, cx + 10, HALF), line(cx - 10, 0, cx + 10, 0),
                  circle(cx - 10, 0, 1.6, fill=True, w="thin"), circle(cx + 10, 0, 1.6, fill=True, w="thin")]

    k = normal_position(npos, left, right)
    cxn = x0 + HALF + ENV * k
    terms = []
    for name, dx, side in layout:
        x = cxn + dx
        if side == "top":
            p.append(line(x, -HALF, x, -HALF - LEAD))
            terms.append(T(name, x, -HALF - LEAD, "u"))
        else:
            p.append(line(x, HALF, x, HALF + LEAD))
            terms.append(T(name, x, HALF + LEAD, "d"))

    for s, ops in ((-1, left), (1, right)):
        x = s * W / 2
        for kind in ops:
            prims, width = _operator(kind, x, s, fill)
            p += prims
            x += s * width
            if kind == "pilot":
                terms.append(T(_pilot_name(medium, s, positions, nports), x, 0, "l" if s < 0 else "r"))
    # make pilot terminal names unique if both sides use the same code
    seen = {}
    uniq = []
    for t in terms:
        n = t.name
        if n in seen:
            seen[n] += 1
            n = f"{n}.{seen[n]}"
        else:
            seen[n] = 1
        uniq.append(T(n, t.x, t.y, t.dir))
    return Geometry(p, uniq)


def valve_summary(params) -> str:
    medium = params.get("medium", "hyd")
    vtype = params.get("type", "4/3")
    try:
        nports = VALVE_TYPES[medium][vtype][0]
    except KeyError:
        return "directional valve"
    pos = params.get("positions", [])
    centre = ""
    if len(pos) == 3:
        centre = ", " + PATTERNS[nports].get(pos[1], {}).get("label", pos[1]).split(" (")[0].lower()
    ops = lambda side: "+".join(params.get(side, [])) or "none"
    return f"{vtype} way {'hydraulic' if medium == 'hyd' else 'pneumatic'}{centre}; left: {ops('left')}, right: {ops('right')}"


# ================================================================ registry entries
def symbols():
    s = []
    add = s.append
    for medium, cat, fill in (("hyd", H, True), ("pneu", P, False)):
        pre = "fl." + medium
        if medium == "hyd":
            add(SymbolDef(f"{pre}.pump", "Pump, fixed displacement", cat, "Pumps & motors", ISO,
                          "Hydraulic pump, fixed displacement, one direction of flow. S = suction, P = pressure outlet.", "P",
                          Geometry(pump(True), [T("P", 0, -20, "u"), T("S", 0, 20, "d")]), keywords=("hpu",)))
            add(SymbolDef(f"{pre}.pump.var", "Pump, variable displacement", cat, "Pumps & motors", ISO,
                          "Hydraulic pump, variable displacement, one direction of flow.", "P",
                          Geometry(pump(True, True), [T("P", 0, -20, "u"), T("S", 0, 20, "d")])))
            add(SymbolDef(f"{pre}.motor", "Motor, fixed displacement", cat, "Pumps & motors", ISO,
                          "Hydraulic motor, fixed displacement, one direction of rotation. A = inlet, B = outlet.", "M",
                          Geometry(motor(True), [T("A", 0, -20, "u"), T("B", 0, 20, "d")])))
        else:
            add(SymbolDef(f"{pre}.compressor", "Compressor", cat, "Supply", ISO,
                          "Air compressor, fixed displacement.", "P",
                          Geometry(pump(False), [T("2", 0, -20, "u"), T("1", 0, 20, "d")])))
            add(SymbolDef(f"{pre}.motor", "Air motor, fixed displacement", cat, "Actuators", ISO,
                          "Pneumatic motor, fixed displacement, one direction of rotation.", "M",
                          Geometry(motor(False), [T("1", 0, -20, "u"), T("2", 0, 20, "d")])))
        act = "Cylinders" if medium == "hyd" else "Actuators"
        add(SymbolDef(f"{pre}.cyl.double", "Cylinder, double-acting", cat, act, ISO,
                      "Double-acting cylinder, single rod. A = cap-end port, B = rod-end port.", "A",
                      Geometry(cylinder_double(), [T("A", -20, -20, "u"), T("B", 10, -20, "u")]), keywords=("ram", "actuator")))
        add(SymbolDef(f"{pre}.cyl.doublerod", "Cylinder, double-acting, double rod", cat, act, ISO,
                      "Double-acting cylinder with through rod.", "A",
                      Geometry(cylinder_double(True), [T("A", -20, -20, "u"), T("B", 10, -20, "u")]), keywords=("actuator",)))
        add(SymbolDef(f"{pre}.cyl.single", "Cylinder, single-acting, spring return", cat, act, ISO,
                      "Single-acting cylinder, return by spring. A = cap-end port.", "A",
                      Geometry(cylinder_single_spring(), [T("A", -20, -20, "u")]), keywords=("ram", "actuator")))
        if medium == "hyd":
            add(SymbolDef(f"{pre}.relief", "Pressure-relief valve", cat, "Pressure control", ISO,
                          "Pressure-relief valve, direct operated, adjustable spring, internal pilot from P.", "V",
                          relief_valve(True), keywords=("safety", "rv")))
            add(SymbolDef(f"{pre}.reducing", "Pressure-reducing valve", cat, "Pressure control", ISO,
                          "Pressure-reducing valve, direct operated (normally open), pilot from outlet A.", "V",
                          reducing_valve(True), keywords=("prv",)))
        else:
            add(SymbolDef(f"{pre}.regulator", "Pressure regulator (non-relieving)", cat, "Pressure control", ISO,
                          "Pressure-reducing valve / regulator, direct operated, pilot from outlet. Relieving types are not shown.", "V",
                          reducing_valve(False, ("1", "2")), keywords=("prv",)))
        add(SymbolDef(f"{pre}.check", "Check valve", cat, "Non-return & flow", ISO,
                      "Non-return (check) valve, unloaded. Free flow from 1 to 2.", "V", check_valve(), keywords=("non-return", "nrv")))
        add(SymbolDef(f"{pre}.check.spring", "Check valve, spring loaded", cat, "Non-return & flow", ISO,
                      "Non-return valve with spring. Free flow from 1 to 2 when the cracking pressure is exceeded.", "V",
                      check_valve(True), keywords=("non-return",)))
        add(SymbolDef(f"{pre}.throttle", "Throttle (restrictor)", cat, "Non-return & flow", ISO,
                      "Fixed restriction (throttle / orifice), viscosity dependent.", "V", throttle(False), keywords=("orifice",)))
        add(SymbolDef(f"{pre}.throttle.adj", "Throttle, adjustable", cat, "Non-return & flow", ISO,
                      "Adjustable throttle (needle valve).", "V", throttle(True), keywords=("needle", "flow control")))
        add(SymbolDef(f"{pre}.flow.oneway", "One-way flow control valve", cat, "Non-return & flow", ISO,
                      "Adjustable throttle with bypass check valve: free flow 1→2, restricted flow 2→1.", "V",
                      one_way_flow_control(), keywords=("speed control", "meter")))
        names = ("X", "Y", "A") if medium == "hyd" else ("1", "1.1", "2")
        add(SymbolDef(f"{pre}.shuttle", "Shuttle valve", cat, "Non-return & flow", ISO,
                      "Shuttle valve (OR function): the higher-pressure inlet is connected to the outlet.", "V",
                      shuttle_valve(names), keywords=("or",), notes="Simplified seat representation."))
        add(SymbolDef(f"{pre}.dcv", "Directional control valve (configurable)", cat, "Directional valves", ISO,
                      "Directional control valve. Configure the way/position count, flow paths and operators in the properties panel.", "V",
                      builder=build_valve, default_params=default_valve_params(medium),
                      keywords=("spool", "solenoid valve", "4/3", "4/2", "5/2", "3/2", "2/2", "dcv")))
        if medium == "hyd":
            add(SymbolDef(f"{pre}.tank", "Reservoir (vented)", cat, "Fluid conditioning", ISO,
                          "Reservoir open to atmosphere; line ends below the fluid level.", "Z", reservoir(), keywords=("tank",)))
            add(SymbolDef(f"{pre}.accumulator", "Accumulator", cat, "Fluid conditioning", ISO,
                          "Accumulator, general symbol with separating element.", "Z", accumulator(),
                          notes="Gas-charge marking not shown."))
            add(SymbolDef(f"{pre}.filter", "Filter", cat, "Fluid conditioning", ISO,
                          "Filter or strainer, general symbol. Flow 1→2.", "Z", filter_geo(), keywords=("strainer",)))
        else:
            add(SymbolDef(f"{pre}.receiver", "Air receiver", cat, "Supply", ISO,
                          "Air receiver (pressure vessel).", "Z", air_receiver(), keywords=("tank", "vessel")))
            add(SymbolDef(f"{pre}.filter", "Filter", cat, "Supply", ISO,
                          "Air filter, general symbol (without water separator). Flow 1→2.", "Z", filter_geo(), keywords=("frl",)))
        add(SymbolDef(f"{pre}.gauge", "Pressure gauge", cat, "Measurement", ISO,
                      "Pressure indicator / gauge.", "S", gauge("P" if medium == "hyd" else "1"), keywords=("manometer",)))
    return s
