"""Bill of materials: one physical device drawn as several symbols is counted once.

Components that share an identifier are units of one device (a relay coil
K1 and its contacts K1 13-14, K1 23-24), as the drawing checks already
define. Terminal-block terminals and components without an identifier are
each one physical part.
"""
import json
import os

from openschematix import bom, check, editing, projectio
from openschematix.project import new_project

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")
PN = dict(manufacturer="Finder", part_number="40.52.9.024")


def relay(doc, des, x=0, y=0, contacts=2, coil_props=None, contact_props=None, contact_symbol="el.contact.no.iec"):
    """Coil plus contacts sharing `des`; contacts get distinct terminal numbers (13-14, 23-24, ...)."""
    coil = editing.place(doc, "el.coil.iec", x, y)
    coil.designator = des
    coil.props.update(coil_props or {})
    units = [coil]
    for i in range(contacts):
        c = editing.place(doc, contact_symbol, x + 100 + 80 * i, y)
        c.designator = des
        c.terminal_labels = {"1": f"{i + 1}3", "2": f"{i + 1}4"}
        c.props.update(contact_props or {})
        units.append(c)
    return units


def rows(lines):
    return [(l.quantity, l.designator_text(), l.part_number, l.description) for l in lines]


def total(lines):
    return sum(l.quantity for l in lines)


# ---------------------------------------------------------------- ordinary components (unchanged)
def test_ordinary_components_unchanged():
    p = new_project()
    d = p.sheets[0]
    for i in range(3):
        editing.place(d, "el.resistor.iec", i * 80, 0).props.update(manufacturer="Yageo", part_number="RC-10K")
    editing.place(d, "el.resistor.iec", 400, 0)
    editing.place(d, "el.capacitor", 500, 0)
    lines = bom.generate(p)
    assert [(l.quantity, l.designator_text(), l.part_number) for l in lines] == \
        [(1, "C1", ""), (3, "R1–R3", "RC-10K"), (1, "R4", "")]


def test_components_without_identifier_are_counted_individually():
    p = new_project()
    d = p.sheets[0]
    for i in range(2):
        editing.place(d, "el.resistor.iec", i * 80, 0).designator = ""
    lines = bom.generate(p)
    assert rows(lines) == [(2, "?", "", "Resistor")]


def test_terminal_block_terminals_are_separate_parts():
    p = new_project()
    d = p.sheets[0]
    for n in ("1", "2", "3"):
        t = editing.place(d, "el.terminal", int(n) * 40, 0)
        t.designator = "X1"
        t.props.update(terminal=n, manufacturer="Phoenix", part_number="UT 2,5")
    lines = bom.generate(p)
    assert [(l.quantity, l.designators) for l in lines] == [(3, ["X1:1", "X1:2", "X1:3"])]


# ---------------------------------------------------------------- multi-unit devices
def test_relay_without_metadata_is_one_device():
    p = new_project()
    units = relay(p.sheets[0], "K1")
    lines = bom.generate(p)
    assert rows(lines) == [(1, "K1", "", "Coil (relay / contactor / solenoid) + Contact, make (NO)")]
    assert lines[0].symbol == "Coil (relay / contactor / solenoid) + Contact, make (NO)"
    assert sorted(lines[0].refs) == sorted((p.sheets[0].uid, u.id) for u in units)    # every unit is reachable


def test_relay_with_part_number_on_every_unit():
    p = new_project()
    relay(p.sheets[0], "K1", coil_props=PN, contact_props=PN)
    assert rows(bom.generate(p)) == [(1, "K1", "40.52.9.024", "Coil (relay / contactor / solenoid)")]


def test_part_number_on_coil_only_absorbs_the_contacts():
    p = new_project()
    units = relay(p.sheets[0], "K1", coil_props=dict(PN, description="Relay 24 V DC, 2 CO"))
    lines = bom.generate(p)
    assert rows(lines) == [(1, "K1", "40.52.9.024", "Relay 24 V DC, 2 CO")]          # no phantom contact line
    assert len(lines[0].refs) == len(units)


def test_description_only_unit_defines_the_line():
    p = new_project()
    relay(p.sheets[0], "K1", coil_props=dict(description="Relay 24 V", rating="24 V DC"))
    assert [(l.quantity, l.description, l.rating) for l in bom.generate(p)] == [(1, "Relay 24 V", "24 V DC")]


def test_identically_drawn_devices_group_regardless_of_insertion_order():
    p = new_project()
    d = p.sheets[0]
    relay(d, "K1", y=0)
    # K2: contacts placed before the coil
    for i in range(2):
        c = editing.place(d, "el.contact.no.iec", 100 + 80 * i, 200)
        c.designator, c.terminal_labels = "K2", {"1": f"{i + 1}3", "2": f"{i + 1}4"}
    coil = editing.place(d, "el.coil.iec", 0, 200)
    coil.designator = "K2"
    lines = bom.generate(p)
    assert rows(lines) == [(2, "K1, K2", "", "Coil (relay / contactor / solenoid) + Contact, make (NO)")]


def test_equal_part_numbers_on_distinct_devices_stay_separate_instances():
    p = new_project()
    d = p.sheets[0]
    relay(d, "K1", coil_props=PN)
    relay(d, "K2", y=200, coil_props=PN, contact_props=PN)
    relay(d, "K3", y=400, coil_props=PN, contacts=1)
    lines = bom.generate(p)
    assert rows(lines) == [(3, "K1–K3", "40.52.9.024", "Coil (relay / contactor / solenoid)")]


def test_conflicting_part_numbers_are_listed_and_reported():
    p = new_project()
    d = p.sheets[0]
    coil, c1, c2 = relay(d, "K1", coil_props=dict(manufacturer="ABB", part_number="AF09-30-10"))
    c2.props.update(manufacturer="ABB", part_number="CA4-01")             # auxiliary contact block
    lines = bom.generate(p)
    assert sorted((l.quantity, l.part_number) for l in lines) == [(1, "AF09-30-10"), (1, "CA4-01")]
    issues = [i for i in check.check(p) if i.code == "device-parts"]
    assert sorted(i.obj_id for i in issues) == sorted([coil.id, c2.id])
    assert all(i.severity == check.WARNING and "K1" in i.message for i in issues)
    # same part number on every unit: no warning
    c2.props.update(part_number="AF09-30-10")
    assert not [i for i in check.check(p) if i.code == "device-parts"]
    assert rows(bom.generate(p)) == [(1, "K1", "AF09-30-10", "Coil (relay / contactor / solenoid)")]


def test_part_number_matching_is_case_and_space_insensitive():
    p = new_project()
    relay(p.sheets[0], "K1", coil_props=PN, contact_props=dict(manufacturer=" finder ", part_number="40.52.9.024 "))
    assert total(bom.generate(p)) == 1
    assert not [i for i in check.check(p) if i.code == "device-parts"]


def test_excluded_units():
    p = new_project()
    coil, c1, c2 = relay(p.sheets[0], "K1", coil_props=PN)
    coil.in_bom = False                                    # coil excluded: the contacts still form K1
    assert rows(bom.generate(p)) == [(1, "K1", "", "Contact, make (NO)")]
    assert total(bom.generate(p, include_excluded=True)) == 1
    for u in (c1, c2):
        u.in_bom = False
    assert bom.generate(p) == []


# ---------------------------------------------------------------- multi-sheet
def test_device_spread_over_sheets():
    p = new_project()
    s1 = p.sheets[0]
    s2 = p.add_sheet("Contacts")
    coil = editing.place(s1, "el.coil.iec", 0, 0)
    coil.designator = "K1"
    coil.props.update(PN)
    contacts = []
    for i in range(2):
        c = editing.place(s2, "el.contact.no.iec", 80 * i, 0)
        c.designator, c.terminal_labels = "K1", {"1": f"{i + 1}3", "2": f"{i + 1}4"}
        contacts.append(c)
    lines = bom.generate(p)
    assert rows(lines) == [(1, "K1", "40.52.9.024", "Coil (relay / contactor / solenoid)")]
    assert lines[0].sheets == [s1.name, s2.name]
    # sheet-filtered BOM: the device appears with its part identity (from sheet 1) and only sheet-2 units
    only2 = bom.generate(p, sheet_uids={s2.uid})
    assert rows(only2) == [(1, "K1", "40.52.9.024", "Coil (relay / contactor / solenoid)")]
    assert sorted(only2[0].refs) == sorted((s2.uid, c.id) for c in contacts) and only2[0].sheets == [s2.name]
    both = bom.generate(p, sheet_uids={s1.uid, s2.uid})
    assert rows(both) == rows(lines)
    assert not [i for i in check.check(p) if i.code in ("duplicate-id", "device-parts")]


# ---------------------------------------------------------------- compatibility
def test_example_latch_counts_relay_once():
    p = projectio.open_any(os.path.join(EXAMPLES, "start_stop_latch.osch")).project
    lines = bom.generate(p)
    k1 = [l for l in lines if "K1" in l.designators]
    assert len(k1) == 1 and k1[0].quantity == 1
    assert total(lines) == 5                           # F1, H1, K1, S1, S2


def test_generation_does_not_change_the_project_and_survives_save_load(tmp_path):
    p = new_project()
    d = p.sheets[0]
    relay(d, "K1", coil_props=PN)
    editing.place(d, "el.resistor.iec", 0, 300)
    before = json.dumps(p.to_dict(), sort_keys=True)
    lines = bom.generate(p)
    assert json.dumps(p.to_dict(), sort_keys=True) == before
    path = tmp_path / "bom.schematix"
    projectio.save_project(p, str(path))
    p2 = projectio.open_any(str(path)).project
    assert rows(bom.generate(p2)) == rows(lines)
    csv = bom.bom_csv(lines)
    assert csv.lstrip("\ufeff").splitlines()[0] == ",".join(h for _k, h in bom.BOM_COLUMNS)   # columns unchanged
