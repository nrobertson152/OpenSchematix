# Symbol library reference

Generated from the source by `tools/gen_symbol_docs.py`; do not edit by hand.

**Conventions.** Symbols are drawn following the conventions of the standards named in the *Convention* column as they are generally published and taught. They were reviewed visually during development but have **not** been certified against the official (paid) standard documents. Where IEC and IEEE/ANSI practice differ, both forms are provided and labelled.

Drawing units: 1 unit = 0.25 mm, snap grid = 10 units (2.5 mm). All terminals lie on the grid.

## Electrical

| Symbol | Group | Convention | Terminals | Ref. prefix | Notes |
|---|---|---|---|---|---|
| Transformer, two windings, iron core | Power | IEC 60617 style | P1, P2, S1, S2 | T | Two-winding transformer in winding (coil) form with magnetic core. |
| Cell / battery | Sources | IEC 60617 style / IEEE 315 | +, - | G | Primary or secondary cell. Long line is the positive pole. |
| AC voltage source | Sources | IEC 60617 style | 1, 2 | G | Alternating-current source / generator, general. |
| Voltage source, ideal | Sources | IEC 60617 style | +, - | G | Ideal voltage source (circle with line along the conductor). |
| Earth (ground) | Connections | IEC 60617 style | 1 | - | Earth, general symbol. |
| Protective earth | Connections | IEC 60617 style | 1 | - | Protective earth (PE): earth symbol enclosed in a circle. |
| Frame / chassis | Connections | IEC 60617 style | 1 | - | Frame or chassis connection. |
| Terminal | Connections | IEC 60617 style | 1, 2 | X | Terminal (connection point), feed-through form. |
| Signal end / off-page | Connections | Generic | 1 | - | Single connection point for labelling a signal or off-page reference. |
| Fuse | Protection | IEC 60617 style | 1, 2 | F | Fuse, general symbol. |
| Circuit breaker | Protection | IEC 60617 style | 1, 2 | Q | Circuit breaker: make contact with breaker function mark (x) at the fixed contact. |
| Contact, make (NO) | Switching (IEC) | IEC 60617 style | 1, 2 | S | Make contact, normally open. Also used as general switch symbol. |
| Contact, break (NC) | Switching (IEC) | IEC 60617 style | 1, 2 | S | Break contact, normally closed. |
| Push-button, make (NO) | Switching (IEC) | IEC 60617 style | 1, 2 | S | Push-button switch, normally open (push operator linked to the contact). |
| Push-button, break (NC) | Switching (IEC) | IEC 60617 style | 1, 2 | S | Push-button switch, normally closed. |
| Coil (relay / contactor / solenoid) | Switching (IEC) | IEC 60617 style | A1, A2 | K | Operating device (coil) of a relay, contactor or solenoid. Terminals A1/A2. |
| Lamp / indicator | Signalling | IEC 60617 style | 1, 2 | H | Lamp, general symbol (signal or lighting lamp). |
| Relay contact, NO | Ladder (NEMA) | NEMA / JIC ladder style (IEEE 315) | 1, 2 | CR | Normally open relay contact as used on ladder diagrams. Note: resembles the capacitor symbol; use the IEC set if ambiguity matters. |
| Relay contact, NC | Ladder (NEMA) | NEMA / JIC ladder style (IEEE 315) | 1, 2 | CR | Normally closed relay contact as used on ladder diagrams. |
| Relay coil | Ladder (NEMA) | NEMA / JIC ladder style (IEEE 315) | 1, 2 | CR | Relay / contactor coil as used on ladder diagrams. |
| Push-button, NO | Ladder (NEMA) | NEMA / JIC ladder style (IEEE 315) | 1, 2 | PB | Normally open momentary push-button (bar above the contacts). |
| Push-button, NC | Ladder (NEMA) | NEMA / JIC ladder style (IEEE 315) | 1, 2 | PB | Normally closed momentary push-button (bar below the contacts). |
| Motor | Machines | IEC 60617 style | 1, 2 | M | Motor, general symbol (add DC / AC marking with the label if needed). |
| Motor, three-phase | Machines | IEC 60617 style | U1, V1, W1 | M | Three-phase AC motor. Terminals U1, V1, W1. |
| Generator | Machines | IEC 60617 style | 1, 2 | G | Generator, general symbol. |

## Electronic

| Symbol | Group | Convention | Terminals | Ref. prefix | Notes |
|---|---|---|---|---|---|
| Resistor | Passive | IEC 60617 style | 1, 2 | R | Resistor, general symbol (rectangle). |
| Resistor | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2 | R | Resistor, zig-zag form. |
| Resistor, adjustable | Passive | IEC 60617 style | 1, 2 | R | Resistor with adjustability arrow drawn through it. |
| Potentiometer | Passive | IEC 60617 style | 1, 2, 3 | R | Resistor with movable contact (wiper, terminal 3). |
| Capacitor | Passive | IEC 60617 style / IEEE 315 | 1, 2 | C | Capacitor, general symbol (non-polarised). |
| Capacitor, polarised | Passive | IEEE 315 / ANSI Y32.2 style | +, - | C | Polarised (e.g. electrolytic) capacitor; straight plate and terminal + are positive. |
| Inductor / winding | Passive | IEC 60617 style | 1, 2 | L | Inductor, coil or winding (semicircle form, used by IEC 60617 and IEEE 315). |
| Diode | Semiconductors | IEC 60617 style / IEEE 315 | A, K | D | Semiconductor diode. Terminal A = anode, K = cathode. |
| Zener diode | Semiconductors | IEC 60617 style / IEEE 315 | A, K | D | Voltage-reference (Zener / breakdown) diode. |
| Light-emitting diode (LED) | Semiconductors | IEC 60617 style / IEEE 315 | A, K | D | LED; arrows indicate emitted light. |
| Transistor, NPN | Semiconductors | IEEE 315 / ANSI Y32.2 style | B, C, E | Q | Bipolar junction transistor, NPN (envelope shown). B base, C collector, E emitter. |
| Transistor, PNP | Semiconductors | IEEE 315 / ANSI Y32.2 style | B, C, E | Q | Bipolar junction transistor, PNP (envelope shown). B base, C collector, E emitter. |
| Operational amplifier | Integrated | IEEE 315 / ANSI Y32.2 style | -, +, OUT | U | Op-amp, triangle form. Supply pins are not shown. *Supply terminals omitted; IEC 60617 uses a rectangular amplifier symbol instead.* |
| Signal ground | Connections | IEEE 315 / ANSI Y32.2 style | 1 | - | Signal / common ground (triangle). |

## Hydraulic

| Symbol | Group | Convention | Terminals | Ref. prefix | Notes |
|---|---|---|---|---|---|
| Pump, fixed displacement | Pumps & motors | ISO 1219-1 style | P, S | P | Hydraulic pump, fixed displacement, one direction of flow. S = suction, P = pressure outlet. |
| Pump, variable displacement | Pumps & motors | ISO 1219-1 style | P, S | P | Hydraulic pump, variable displacement, one direction of flow. |
| Motor, fixed displacement | Pumps & motors | ISO 1219-1 style | A, B | M | Hydraulic motor, fixed displacement, one direction of rotation. A = inlet, B = outlet. |
| Cylinder, double-acting | Cylinders | ISO 1219-1 style | A, B | A | Double-acting cylinder, single rod. A = cap-end port, B = rod-end port. |
| Cylinder, double-acting, double rod | Cylinders | ISO 1219-1 style | A, B | A | Double-acting cylinder with through rod. |
| Cylinder, single-acting, spring return | Cylinders | ISO 1219-1 style | A | A | Single-acting cylinder, return by spring. A = cap-end port. |
| Pressure-relief valve | Pressure control | ISO 1219-1 style | P, T | V | Pressure-relief valve, direct operated, adjustable spring, internal pilot from P. |
| Pressure-reducing valve | Pressure control | ISO 1219-1 style | P, A | V | Pressure-reducing valve, direct operated (normally open), pilot from outlet A. |
| Check valve | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Non-return (check) valve, unloaded. Free flow from 1 to 2. |
| Check valve, spring loaded | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Non-return valve with spring. Free flow from 1 to 2 when the cracking pressure is exceeded. |
| Throttle (restrictor) | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Fixed restriction (throttle / orifice), viscosity dependent. |
| Throttle, adjustable | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Adjustable throttle (needle valve). |
| One-way flow control valve | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Adjustable throttle with bypass check valve: free flow 1→2, restricted flow 2→1. |
| Shuttle valve | Non-return & flow | ISO 1219-1 style | X, Y, A | V | Shuttle valve (OR function): the higher-pressure inlet is connected to the outlet. *Simplified seat representation.* |
| Directional control valve (configurable) | Directional valves | ISO 1219-1 style | A, B, P, T (varies with configuration) | V | Directional control valve. Configure the way/position count, flow paths and operators in the properties panel. |
| Reservoir (vented) | Fluid conditioning | ISO 1219-1 style | T | Z | Reservoir open to atmosphere; line ends below the fluid level. |
| Accumulator | Fluid conditioning | ISO 1219-1 style | P | Z | Accumulator, general symbol with separating element. *Gas-charge marking not shown.* |
| Filter | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Filter or strainer, general symbol. Flow 1→2. |
| Pressure gauge | Measurement | ISO 1219-1 style | P | S | Pressure indicator / gauge. |

## Pneumatic

| Symbol | Group | Convention | Terminals | Ref. prefix | Notes |
|---|---|---|---|---|---|
| Compressor | Supply | ISO 1219-1 style | 2, 1 | P | Air compressor, fixed displacement. |
| Air motor, fixed displacement | Actuators | ISO 1219-1 style | 1, 2 | M | Pneumatic motor, fixed displacement, one direction of rotation. |
| Cylinder, double-acting | Actuators | ISO 1219-1 style | A, B | A | Double-acting cylinder, single rod. A = cap-end port, B = rod-end port. |
| Cylinder, double-acting, double rod | Actuators | ISO 1219-1 style | A, B | A | Double-acting cylinder with through rod. |
| Cylinder, single-acting, spring return | Actuators | ISO 1219-1 style | A | A | Single-acting cylinder, return by spring. A = cap-end port. |
| Pressure regulator (non-relieving) | Pressure control | ISO 1219-1 style | 1, 2 | V | Pressure-reducing valve / regulator, direct operated, pilot from outlet. Relieving types are not shown. |
| Check valve | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Non-return (check) valve, unloaded. Free flow from 1 to 2. |
| Check valve, spring loaded | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Non-return valve with spring. Free flow from 1 to 2 when the cracking pressure is exceeded. |
| Throttle (restrictor) | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Fixed restriction (throttle / orifice), viscosity dependent. |
| Throttle, adjustable | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Adjustable throttle (needle valve). |
| One-way flow control valve | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Adjustable throttle with bypass check valve: free flow 1→2, restricted flow 2→1. |
| Shuttle valve | Non-return & flow | ISO 1219-1 style | 1, 1.1, 2 | V | Shuttle valve (OR function): the higher-pressure inlet is connected to the outlet. *Simplified seat representation.* |
| Directional control valve (configurable) | Directional valves | ISO 1219-1 style | 4, 2, 5, 1, 3 (varies with configuration) | V | Directional control valve. Configure the way/position count, flow paths and operators in the properties panel. |
| Air receiver | Supply | ISO 1219-1 style | 1 | Z | Air receiver (pressure vessel). |
| Filter | Supply | ISO 1219-1 style | 1, 2 | Z | Air filter, general symbol (without water separator). Flow 1→2. |
| Pressure gauge | Measurement | ISO 1219-1 style | 1 | S | Pressure indicator / gauge. |

## General

| Symbol | Group | Convention | Terminals | Ref. prefix | Notes |
|---|---|---|---|---|---|
| Function block, 2 terminals | Blocks | Generic | 1, 2 | U | Generic rectangular function block (use the label for its function). |
| Function block, 4 terminals | Blocks | Generic | 1, 2, 3, 4 | U | Generic rectangular function block with two terminals on each side. |
| Sheet connector (cross-sheet reference) | Connections | Generic | 1 | - | Connects a signal or line to every sheet connector with the same label anywhere in the project. The sheet and zone of the matching connectors are shown next to it automatically. |

## Directional control valves

Configurable through *Configure valve...*: hydraulic 2/2, 3/2, 4/2, 4/3 and pneumatic 2/2, 3/2, 5/2, 5/3; per-position flow paths (parallel, crossed, closed, tandem, float and open centres; pneumatic exhausted centre); up to two operators per side (spring, solenoid, pilot, lever, push-button, general manual). Ports are drawn on the rest position (the centre position of 3-position valves, otherwise the position next to the spring). Pilot operators add pilot ports (X/Y hydraulic; 12/14 or 10/12 pneumatic).

## Not included in this release

Symbols that could not be drawn with confidence without the standard documents were left out rather than guessed: silencers, lubricators and complete FRL units, proportional/servo valves, pressure switches and transducers, sequence and counterbalance valves, rotary actuators, quick couplings, logic gates, and IEC 60617 binary-logic symbols. Use the generic function blocks and the label field meanwhile.
