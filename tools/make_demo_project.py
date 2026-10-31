"""Build examples/demo_project.schematix, a three-sheet project that shows the
features: terminal strips, sheet connectors with automatic cross
references, wire numbers, a bridged crossing and a junction, title blocks,
a revision table and a hydraulic sheet.

    python tools/make_demo_project.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from openschematix import editing, netlist, projectio, revisions  # noqa: E402
from openschematix.model import Wire  # noqa: E402
from openschematix.project import new_project  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "examples", "demo_project.schematix")


def link(doc, a, ta, b, tb):
    w = Wire(doc.new_id(), [a.terminals()[ta], b.terminals()[tb]], [a.id, ta], [b.id, tb])
    doc.add_wire(w)
    editing.reroute(doc, w)
    return w


def build():
    p = new_project("Conveyor station 3", size="A3")
    p.meta.update(number="CS3-E", client="Example Manufacturing Ltd", organisation="Example Engineering",
                  author="N. Robertson", checked_by="J. Smith", approved_by="A. Engineer",
                  description="Demonstration project for OpenSchematix")
    # ---------------------------------------------------------------- sheet 1: supply
    s1 = p.sheets[0]
    s1.name = "24 V supply"
    s1.sheet.title = "24 V DC control supply"
    x1a = editing.place(s1, "el.terminal", 300, 300)
    x1b = editing.place(s1, "el.terminal", 300, 500)
    for t, d in ((x1a, "+24 V in"), (x1b, "0 V in")):
        t.props["description"] = d
    f1 = editing.place(s1, "el.fuse.iec", 480, 300)
    f1.props.update(description="Fuse 2 A", manufacturer="Example", part_number="FU-2A", rating="2 A")
    q1 = editing.place(s1, "el.breaker.iec", 660, 300)
    q1.props.update(description="Miniature circuit breaker", manufacturer="Example", part_number="MCB-C6",
                    rating="C6")
    o24 = editing.place(s1, "gen.offpage", 900, 300)
    o24.label = "24V"
    o0 = editing.place(s1, "gen.offpage", 900, 500)
    o0.label = "0V"
    h0 = editing.place(s1, "el.lamp.iec", 780, 400, rotation=90)
    h0.label = "Supply on"
    h0.props.update(description="Indicator lamp, green", manufacturer="Example", part_number="IL-24G")
    link(s1, x1a, "2", f1, "1")
    link(s1, f1, "2", q1, "1")
    link(s1, q1, "2", o24, "1")
    link(s1, x1b, "2", o0, "1")
    editing.add_wire(s1, [h0.terminals()["1"], (h0.terminals()["1"][0], 300)])
    editing.add_wire(s1, [h0.terminals()["2"], (h0.terminals()["2"][0], 500)])
    # ---------------------------------------------------------------- sheet 2: control
    s2 = p.add_sheet("Motor control")
    s2.sheet.title = "Conveyor motor control"
    i24 = editing.place(s2, "gen.offpage", 300, 200, rotation=180)
    i24.label = "24V"
    i0 = editing.place(s2, "gen.offpage", 300, 800, rotation=180)
    i0.label = "0V"
    stop = editing.place(s2, "el.pushbutton.nc.iec", 400, 300, rotation=90)
    stop.label = "Stop"
    start = editing.place(s2, "el.pushbutton.no.iec", 400, 420, rotation=90)
    start.label = "Start"
    k1 = editing.place(s2, "el.coil.iec", 400, 600)
    k1.label = "Conveyor"
    k1.props.update(description="Contactor 24 V DC coil", manufacturer="Example", part_number="CT-09-24DC")
    hold = editing.place(s2, "el.contact.no.iec", 520, 420, rotation=90)
    hold.designator, hold.label = k1.designator, "13-14"
    hold.in_bom = False
    lamp = editing.place(s2, "el.lamp.iec", 700, 600, rotation=90)
    lamp.label = "Running"
    lamp.props.update(description="Indicator lamp, white", manufacturer="Example", part_number="IL-24W")
    aux = editing.place(s2, "el.contact.no.iec", 700, 420, rotation=90)
    aux.designator, aux.label = k1.designator, "23-24"
    aux.in_bom = False
    rail_top, rail_bot = 200, 800
    editing.add_wire(s2, [i24.terminals()["1"], (700, rail_top)])
    editing.add_wire(s2, [i0.terminals()["1"], (700, rail_bot)])
    editing.add_wire(s2, [stop.terminals()["1"], (400, rail_top)])
    link(s2, stop, "2", start, "1")
    link(s2, start, "2", k1, "A1")
    editing.add_wire(s2, [k1.terminals()["A2"], (400, rail_bot)])
    a, b = hold.terminals()["1"], hold.terminals()["2"]
    editing.add_wire(s2, [a, (a[0], 370), (400, 370)])
    editing.add_wire(s2, [b, (b[0], 480), (400, 480)])
    editing.add_wire(s2, [aux.terminals()["1"], (700, rail_top)])
    link(s2, aux, "2", lamp, "1")
    editing.add_wire(s2, [lamp.terminals()["2"], (700, rail_bot)])
    # a test line that crosses the control circuit without connecting (drawn with a bridge)
    tp = editing.place(s2, "el.connector.point", 260, 700, mirror=True)
    tp.label, tp.text_side = "TP1", "above"
    t2 = editing.place(s2, "el.connector.point", 600, 700)
    t2.label, t2.text_side = "TP2", "above"
    editing.add_wire(s2, [tp.terminals()["1"], t2.terminals()["1"]])
    # ---------------------------------------------------------------- sheet 3: hydraulics
    s3 = p.add_sheet("Hydraulics")
    s3.sheet.title = "Lift unit hydraulics"
    src = projectio.open_any(os.path.join(HERE, "..", "examples", "hydraulic_cylinder_circuit.osch")).project
    editing.paste(s3, editing.copy_items(src.sheets[0], src.sheets[0].all_ids()), 200, 60)
    netlist.assign_wire_numbers(p)
    p.revisions = revisions.RevisionStore()
    p.revisions.create(p, "approved", label="A", description="First issue", author="N. Robertson",
                       approved_by="A. Engineer")
    p.meta["revision"] = "A"
    return p


if __name__ == "__main__":
    proj = build()
    projectio.save_project(proj, OUT, snapshot=False)
    print("wrote", os.path.relpath(OUT))
