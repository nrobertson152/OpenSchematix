"""Build the example drawings in examples/: python tools/make_examples.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from openschematix import editing, fileio  # noqa: E402
from openschematix.model import Document, Wire  # noqa: E402
from openschematix.symbols.fluid import default_valve_params  # noqa: E402


def connect(doc, a, ta, b, tb, style="solid"):
    w = Wire(doc.new_id(), [a.terminals()[ta], b.terminals()[tb]], [a.id, ta], [b.id, tb], style)
    doc.add_wire(w)
    editing.reroute(doc, w)
    return w


def hydraulic():
    d = Document()
    d.sheet.size, d.sheet.title = "A4", "Double-acting cylinder, 4/3 tandem-centre control"
    d.sheet.drawing_number, d.sheet.revision, d.sheet.author = "EX-001", "A", "OpenSchematix example"
    cyl = editing.place(d, "fl.hyd.cyl.double", 510, 180, rotation=180, mirror=True)   # ports face down
    cyl.label = "Lift cylinder"
    p = default_valve_params("hyd", "4/3")
    p["positions"] = ["parallel", "tandem", "crossed"]
    v = editing.place(d, "fl.hyd.dcv", 500, 340, params=p)
    pump = editing.place(d, "fl.hyd.pump", 300, 520)
    pump.label = "10 L/min"
    tank1 = editing.place(d, "fl.hyd.tank", 300, 600)
    rv = editing.place(d, "fl.hyd.relief", 400, 470, rotation=180)                    # P up, T down
    rv.label = "160 bar"
    tank2 = editing.place(d, "fl.hyd.tank", 400, 550)
    gauge = editing.place(d, "fl.hyd.gauge", 360, 380)
    flt = editing.place(d, "fl.hyd.filter", 600, 450, rotation=90)                   # flow downwards
    tank3 = editing.place(d, "fl.hyd.tank", 600, 530)
    t = lambda c, n: c.terminals()[n]  # noqa: E731
    line_y = 420
    editing.add_wire(d, [t(pump, "S"), t(tank1, "T")])
    editing.add_wire(d, [t(pump, "P"), (300, line_y), (t(v, "P")[0], line_y), t(v, "P")])   # pressure line
    editing.add_wire(d, [t(rv, "P"), (t(rv, "P")[0], line_y)])                              # branch to relief
    editing.add_wire(d, [t(rv, "T"), t(tank2, "T")])
    editing.add_wire(d, [t(gauge, "P"), (t(gauge, "P")[0], line_y)])                        # branch to gauge
    vt = t(v, "T")
    editing.add_wire(d, [vt, (vt[0], 400), (600, 400), t(flt, "1")])                       # return line
    editing.add_wire(d, [t(flt, "2"), t(tank3, "T")])
    connect(d, v, "A", cyl, "A")
    connect(d, v, "B", cyl, "B")
    return d


def electrical():
    d = Document()
    d.sheet.size, d.sheet.title = "A4", "Start/stop latching relay (IEC)"
    d.sheet.drawing_number, d.sheet.revision, d.sheet.author = "EX-002", "A", "OpenSchematix example"
    f = editing.place(d, "el.fuse.iec", 300, 200, rotation=90)
    stop = editing.place(d, "el.pushbutton.nc.iec", 300, 280, rotation=90)
    stop.label = "Stop"
    start = editing.place(d, "el.pushbutton.no.iec", 300, 360, rotation=90)
    start.label = "Start"
    latch = editing.place(d, "el.contact.no.iec", 400, 360, rotation=90)
    k = editing.place(d, "el.coil.iec", 300, 450)
    lamp = editing.place(d, "el.lamp.iec", 500, 450, rotation=90)
    k2 = editing.place(d, "el.contact.no.iec", 500, 370, rotation=90)
    latch.designator = k2.designator = k.designator
    latch.label, k2.label = "13-14", "23-24"
    for a, ta, b, tb in ((f, "2", stop, "1"), (stop, "2", start, "1"), (start, "2", k, "A1")):
        connect(d, a, ta, b, tb)
    s1, s2 = start.terminals()["1"], start.terminals()["2"]
    l1, l2 = latch.terminals()["1"], latch.terminals()["2"]
    editing.add_wire(d, [s1, (s1[0], s1[1] - 10), (l1[0], s1[1] - 10), l1])
    editing.add_wire(d, [l2, (l2[0], s2[1] + 10), (s2[0], s2[1] + 10)])
    f1 = f.terminals()["1"]
    a2 = k.terminals()["A2"]
    editing.add_wire(d, [f1, (f1[0], f1[1] - 20), (k2.terminals()["1"][0], f1[1] - 20), k2.terminals()["1"]])
    connect(d, k2, "2", lamp, "1")
    l2 = lamp.terminals()["2"]
    editing.add_wire(d, [a2, (a2[0], a2[1] + 20), (l2[0], a2[1] + 20), l2])
    return d


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "examples")
    os.makedirs(out, exist_ok=True)
    for name, fn in (("hydraulic_cylinder_circuit.osch", hydraulic), ("start_stop_latch.osch", electrical)):
        fileio.save(fn(), os.path.join(out, name))
        print("wrote", name)
