"""Generate a two-sheet OpenSchematix project with the scripting API.

Sheet 1: start/stop control of a motor contactor (latching circuit) with a
run lamp. Sheet 2: a hydraulic cylinder driven by a 4/3 directional valve.

Run from the repository root (no display needed):

    python docs/examples/motor_starter.py [output.schematix]

then open the result in OpenSchematix.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))   # run from a source checkout

from openschematix import api  # noqa: E402


def build() -> api.Project:
    project = api.new_project("Motor starter and press cylinder", sheet_size="A3")

    # ------------------------------------------------------------ sheet 1: control circuit
    ctl = project.sheets[0]
    ctl.name = "Control"
    # Positions are insertion points in drawing units (0.25 mm) on the
    # 10-unit grid; Y grows downwards. These horizontal symbols have their
    # terminals 20 units left and right of the insertion point.
    supply_l = ctl.place("el.terminal", 100, 200, designator="X1")     # X1:1, line
    fuse = ctl.place("el.fuse.iec", 200, 200, properties={"rating": "2 A gG"})
    stop = ctl.place("el.pushbutton.nc.iec", 300, 200, label="Stop")
    start = ctl.place("el.pushbutton.no.iec", 400, 200, label="Start")
    coil = ctl.place("el.coil.iec", 520, 200, rotation=270, label="Motor contactor")   # A1 left, A2 right
    supply_n = ctl.place("el.terminal", 640, 200, designator="X1")     # X1:2, neutral
    # The hold-in contact belongs to the same device as the coil, so it
    # shares its designator (the BOM counts K1 once).
    hold = ctl.place("el.contact.no.iec", 400, 280, designator=coil.designator)
    lamp = ctl.place("el.lamp.iec", 520, 360, label="Running")

    # Series path, terminal to terminal (automatically routed).
    ctl.connect(supply_l, "2", fuse, "1")
    ctl.connect(fuse, "2", stop, "1")
    ctl.connect(stop, "2", start, "1")
    ctl.connect(start, "2", coil, "A1")
    ctl.connect(coil, "A2", supply_n, "1")
    # Parallel branches: a wire end placed on another wire makes a junction.
    ctl.add_wire([(360, 200), (360, 280), hold.terminal("1").position])
    ctl.add_wire([hold.terminal("2").position, (440, 280), (440, 200)])
    ctl.add_wire([(460, 200), (460, 360), lamp.terminal("1").position])
    ctl.add_wire([lamp.terminal("2").position, (580, 360), (580, 200)])

    coil.set_property("manufacturer", "ACME Controls")
    coil.set_property("part_number", "AC-9-230V")
    coil.set_property("description", "Contactor 9 A, 230 V AC coil")
    fuse.set_property("part_number", "FU-2A")
    lamp.set_property("part_number", "PL-22-G")
    stop.set_property("part_number", "PB-22-R")
    start.set_property("part_number", "PB-22-G")

    # ------------------------------------------------------------ sheet 2: hydraulics
    hyd = project.add_sheet("Hydraulics")
    pump = hyd.place("fl.hyd.pump", 200, 400, properties={"rating": "12 l/min"})
    suction = hyd.place("fl.hyd.tank", 200, 460)
    valve = hyd.place("fl.hyd.dcv", 500, 300, params={"type": "4/3", "left": ["solenoid", "spring"],
                                                      "right": ["solenoid", "spring"]})
    return_tank = hyd.place("fl.hyd.tank", 510, 400)
    # Mirrored and turned 180 degrees so its ports face the valve, A over A.
    cylinder = hyd.place("fl.hyd.cyl.double", 500, 140, rotation=180, mirror=True, label="Press cylinder")
    relief = hyd.place("fl.hyd.relief", 320, 320, properties={"rating": "160 bar"})
    relief_tank = hyd.place("fl.hyd.tank", 380, 460)

    hyd.connect(suction, "T", pump, "S")
    hyd.add_wire([pump.terminal("P").position, (200, 360), (490, 360), valve.terminal("P").position])
    hyd.add_wire([relief.terminal("P").position, (320, 360)])           # branch off the pressure line
    hyd.connect(relief, "T", relief_tank, "T")
    hyd.connect(valve, "T", return_tank, "T")
    hyd.connect(valve, "A", cylinder, "A")
    hyd.connect(valve, "B", cylinder, "B")
    valve.set_property("part_number", "DCV-4/3-NG6")
    cylinder.set_property("part_number", "CYL-40/25-200")
    return project


def main(argv: list[str]) -> int:
    out = argv[1] if len(argv) > 1 else "motor_starter.schematix"
    project = build()
    project.number_wires()

    issues = project.check()
    for issue in issues:
        print(f"{issue.severity}: {issue.message}")
    problems = [i for i in issues if i.severity == "error"]

    print(f"{len(project.nets())} nets")
    for line in project.bom():
        print(f"{line.item:>3}  {line.quantity:>2} x {line.designator_text:<10} {line.part_number:<16} "
              f"{line.description}")
    print("saved", project.save(out))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
