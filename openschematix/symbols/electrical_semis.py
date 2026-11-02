"""Diodes, thyristors and rectifiers (symbol-library expansion, batch E3).

Source: ECL = "Electric Components Library" (ElCompLib2017.svg, CC0 1.0), section "Diodes (semiconductor)".
Redrawn natively in the style of the existing el.diode (outline triangle; the source's filled and outline rows are
the same symbols). Two-terminal parts horizontal, anode / main terminal 2 on the left, terminals at x = -20 / +20.
"""
from __future__ import annotations

import math

from .base import IEC, IEEE, Geometry, SymbolDef, Terminal as T, arrow, line, poly, polyline, rect, text

EL = "Electronic"
G = "Semiconductors"
IEC_IEEE = IEC + " / " + IEEE.split(" /")[0]


def diode_body(bar=True):
    p = [line(-20, 0, -6, 0), poly(-6, -6, 6, 0, -6, 6)]
    if bar:
        p.append(line(6, -6, 6, 6))
    return p


def ak(prims, extra=()):
    return Geometry(prims, [T("A", -20, 0, "l"), T("K", 20, 0, "r"), *extra])


def small_diode(x1, y1, x2, y2, s=3.2):
    """Small diode on the segment (x1,y1)-(x2,y2), conducting towards the second point."""
    d = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / d, (y2 - y1) / d
    nx, ny = -uy, ux
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    bx, by = mx - ux * s, my - uy * s
    tx, ty = mx + ux * s, my + uy * s
    return [line(x1, y1, x2, y2), poly(bx + nx * s, by + ny * s, tx, ty, bx - nx * s, by - ny * s),
            line(tx + nx * s, ty + ny * s, tx - nx * s, ty - ny * s)]


def symbols():
    s = []
    add = s.append
    add(SymbolDef("el.diode.schottky", "Schottky diode", EL, G, IEC_IEEE,
                  "Schottky (metal-semiconductor) diode. A anode, K cathode.", "D",
                  ak(diode_body(False) + [polyline([(10, -3), (10, -6), (6, -6), (6, 6), (2, 6), (2, 3)]),
                                          line(6, 0, 20, 0)]), keywords=("schottky", "barrier")))
    add(SymbolDef("el.diode.varicap", "Varicap (varactor) diode", EL, G, IEC_IEEE,
                  "Variable-capacitance diode. A anode, K cathode.", "D",
                  ak(diode_body() + [line(9, -6, 9, 6), line(9, 0, 20, 0)]), keywords=("varactor", "tuning")))
    add(SymbolDef("el.photodiode", "Photodiode", EL, G, IEC_IEEE,
                  "Photodiode; arrows indicate incident light. A anode, K cathode.", "D",
                  ak(diode_body() + [line(6, 0, 20, 0)] + arrow(-6, -16, 0, -10, head=3.5)
                     + arrow(0, -18, 6, -12, head=3.5)), keywords=("light", "sensor")))
    diac = [line(-20, 0, -6, 0), line(6, 0, 20, 0), line(-6, -12, -6, 12), line(6, -12, 6, 12),
            poly(-6, -11, 6, -6, -6, -1), poly(6, 1, -6, 6, 6, 11)]
    add(SymbolDef("el.diac", "DIAC", EL, G, IEC_IEEE,
                  "Bidirectional trigger diode (DIAC).", "D",
                  Geometry(diac, [T("1", -20, 0, "l"), T("2", 20, 0, "r")]), keywords=("trigger",)))
    add(SymbolDef("el.triac", "TRIAC", EL, G, IEC_IEEE,
                  "Bidirectional triode thyristor (TRIAC): main terminals MT2 and MT1, gate G at the MT1 side.", "Q",
                  Geometry(diac + [polyline([(6, 10), (10, 14), (10, 20)])],
                           [T("MT2", -20, 0, "l"), T("MT1", 20, 0, "r"), T("G", 10, 20, "d")]),
                  keywords=("thyristor", "ac switch")))
    add(SymbolDef("el.scr", "Thyristor (SCR), cathode gate", EL, G, IEC_IEEE,
                  "Reverse-blocking triode thyristor, gate on the cathode side. A anode, K cathode, G gate.", "Q",
                  ak(diode_body() + [line(6, 0, 20, 0), polyline([(6, 4), (10, 9), (10, 20)])],
                     [T("G", 10, 20, "d")]), keywords=("thyristor", "scr")))
    tvs = [line(-20, 0, -12, 0), poly(-12, -6, 0, 0, -12, 6), poly(12, -6, 0, 0, 12, 6), line(12, 0, 20, 0),
           polyline([(-3, -9), (0, -6), (0, 6), (3, 9)])]
    add(SymbolDef("el.tvs.bidir", "Transient voltage suppressor, bidirectional", EL, G, IEC_IEEE,
                  "Bidirectional breakdown (TVS / back-to-back Zener) diode.", "D",
                  Geometry(tvs, [T("1", -20, 0, "l"), T("2", 20, 0, "r")]),
                  keywords=("tvs", "zener", "surge", "suppressor")))
    br = []
    for (x1, y1, x2, y2) in ((-20, 0, 0, -20), (-20, 0, 0, 20), (0, -20, 20, 0), (0, 20, 20, 0)):
        br += small_diode(x1, y1, x2, y2)
    br += [text(-14, 10, "-", size=8), text(14, -10, "+", size=8)]
    add(SymbolDef("el.rectifier.bridge", "Bridge rectifier", EL, G, IEC_IEEE,
                  "Full-wave bridge of four diodes: AC inputs AC1 (top) and AC2 (bottom), DC outputs + and -.", "D",
                  Geometry(br, [T("AC1", 0, -20, "u"), T("AC2", 0, 20, "d"), T("-", -20, 0, "l"), T("+", 20, 0, "r")]),
                  keywords=("graetz", "bridge")))
    blk = [rect(-20, -20, 20, 20), line(-30, -10, -20, -10), line(-30, 10, -20, 10), line(20, -10, 30, -10),
           line(20, 10, 30, 10), line(-12, 0, -6, 0), poly(-6, -5, 4, 0, -6, 5), line(4, -5, 4, 5), line(4, 0, 10, 0),
           text(-14, -12, "~", size=8), text(-14, 12, "~", size=8), text(14, -12, "+", size=8),
           text(14, 12, "-", size=8)]
    add(SymbolDef("el.rectifier.block", "Rectifier (bridge) block", EL, G, IEC,
                  "Rectifier as a block: AC inputs AC1 and AC2 (left), DC outputs + and - (right).", "D",
                  Geometry(blk, [T("AC1", -30, -10, "l"), T("AC2", -30, 10, "l"), T("+", 30, -10, "r"),
                                 T("-", 30, 10, "r")]), keywords=("bridge", "rectifier")))
    conv = [rect(-20, -20, 20, 20), line(-20, 20, 20, -20), line(-30, -10, -20, -10), line(-30, 10, -20, 10),
            line(20, -10, 30, -10), line(20, 10, 30, 10), text(-12, -12, "~", size=8), text(12, 12, "-", size=8)]
    add(SymbolDef("el.converter.acdc", "AC/DC converter", EL, G, IEC,
                  "Converter from alternating to direct current (rectifier), general block: AC side AC1/AC2 (left), "
                  "DC side DC1/DC2 (right).", "U",
                  Geometry(conv, [T("AC1", -30, -10, "l"), T("AC2", -30, 10, "l"), T("DC1", 30, -10, "r"),
                                  T("DC2", 30, 10, "r")]), keywords=("rectifier", "power supply"),
                  notes="The source marks the AC side with ~ and the DC side with a bar; it does not mark the DC "
                        "polarity, so the DC terminals are not named + and -."))
    return s
