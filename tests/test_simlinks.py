"""What the properties panel offers for simulation links, and who gets it."""
from openschematix import simlinks
from openschematix.model import Component
from openschematix.project import new_project
from openschematix.symbols.fluid import default_valve_params


def comp(symbol, **kw):
    return Component(id=1, symbol=symbol, x=0, y=0, **kw)


def test_valve_sides_follow_its_operators():
    assert simlinks.solenoid_sides(comp("fl.hyd.dcv", params=default_valve_params("hyd", "4/3"))) == ["a", "b"]
    single = default_valve_params("hyd", "4/2")
    assert simlinks.solenoid_sides(comp("fl.hyd.dcv", params=single)) == ["a"]
    assert simlinks.solenoid_sides(comp("fl.hyd.dcv", params={**single, "left": ["lever"], "right": ["spring"]})) == []
    assert simlinks.solenoid_sides(comp("fl.hyd.dcv", params={**single, "left": ["spring"], "right": ["solenoid.prop"]})) == ["b"]


def test_built_in_solenoids():
    assert simlinks.solenoid_sides(comp("fl.hyd.unloading.sol")) == ["a"]
    assert simlinks.solenoid_sides(comp("fl.hyd.check")) == []
    assert simlinks.solenoid_sides(comp("el.coil.iec")) == []


def test_who_gets_which_field():
    assert [f[0] for f in simlinks.fields_for(comp("el.switch.limit.no"))] == [simlinks.SENSES]
    assert [f[0] for f in simlinks.fields_for(comp("el.potentiometer.iec"))] == [simlinks.SENSES]
    assert [f[0] for f in simlinks.fields_for(comp("el.sensor.analog"))] == [simlinks.SENSES]
    assert [f[0] for f in simlinks.fields_for(comp("fl.hyd.pump"))] == [simlinks.DRIVEN_BY]
    assert [f[0] for f in simlinks.fields_for(comp("fl.hyd.dcv", params=default_valve_params("hyd", "4/3")))] == \
        [simlinks.SOLENOID_A, simlinks.SOLENOID_B]
    assert simlinks.fields_for(comp("el.plc")) == []
    assert simlinks.fields_for(comp("el.resistor.iec")) == []
    assert simlinks.fields_for(comp("fl.hyd.tank")) == []


def test_a_pressure_switch_contact_can_say_which_gauge_it_reads():
    """Its tag ties it to a pressure switch. Without one, `PT1 > 120 bar` ties it to a gauge or transducer instead."""
    assert [f[0] for f in simlinks.fields_for(comp("el.switch.pressure.no"))] == [simlinks.SENSES]
    assert [f[0] for f in simlinks.fields_for(comp("el.switch.pressure.nc"))] == [simlinks.SENSES]


def test_suggestions_come_from_the_project():
    p = new_project()
    d = p.sheets[0]
    for i, (symbol, tag) in enumerate((("fl.hyd.cyl.double", "A1"), ("fl.hyd.pressure.transducer", "PT1"), ("el.coil.valve", "Y1"),
                                       ("el.motor", "M1"), ("el.coil.iec", "K1"), ("fl.hyd.tank", "Z1"), ("el.coil.iec", "")), 1):
        d.add_component(Component(id=i, symbol=symbol, x=0, y=0, designator=tag))
    assert simlinks.suggestions(p, simlinks.SENSES) == ["A1", "PT1"]
    assert simlinks.suggestions(p, simlinks.SOLENOID_A) == ["K1", "Y1"]
    assert simlinks.suggestions(p, simlinks.DRIVEN_BY) == ["M1"]


def _valve(left, right, medium="pneu", vtype="3/2"):
    return comp(f"fl.{medium}.dcv", params={**default_valve_params(medium, vtype), "left": left, "right": right})


def test_a_roller_or_a_cam_is_operated_by_the_machine():
    assert simlinks.mechanical_sides(_valve(["roller"], ["spring"])) == ["a"]
    assert simlinks.mechanical_sides(_valve(["spring"], ["cam"])) == ["b"]
    assert simlinks.mechanical_sides(_valve(["roller.lever"], ["plunger"])) == ["a", "b"]
    assert simlinks.mechanical_sides(_valve(["plunger.limited"], ["spring"])) == ["a"]
    assert simlinks.mechanical_sides(_valve(["lever"], ["spring"])) == []
    assert simlinks.mechanical_sides(_valve(["solenoid"], ["spring"])) == []
    assert simlinks.mechanical_sides(comp("fl.hyd.check")) == []
    assert simlinks.mechanical_sides(comp("el.switch.limit.no")) == []


def test_a_damaged_valve_has_no_mechanical_side():
    assert simlinks.mechanical_sides(comp("fl.pneu.dcv", params={"left": "roller", "right": [3, None]})) == []


def test_a_valve_offers_senses_for_its_rollers():
    assert [f[0] for f in simlinks.fields_for(_valve(["roller"], ["spring"]))] == [simlinks.SENSES]
    assert [f[0] for f in simlinks.fields_for(_valve(["roller"], ["cam"]))] == [simlinks.SENSES_A, simlinks.SENSES_B]
    assert [f[0] for f in simlinks.fields_for(_valve(["solenoid"], ["roller"]))] == [simlinks.SOLENOID_A, simlinks.SENSES]
    assert [f[0] for f in simlinks.fields_for(_valve(["lever"], ["spring"]))] == []
    tip = simlinks.fields_for(_valve(["spring"], ["roller"]))[0][2]
    assert "right-hand" in tip and "A1 100%" in tip


def test_senses_on_a_valve_are_links_not_custom_properties():
    assert {simlinks.SENSES_A, simlinks.SENSES_B} <= set(simlinks.ALL_KEYS)
