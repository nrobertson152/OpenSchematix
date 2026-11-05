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
| DC voltage source | Sources | IEEE 315 / ANSI Y32.2 style | +, - | G | Direct-voltage source with polarity marks; terminal + is positive. |
| Current source | Sources | IEC 60617 style | 1, 2 | G | Ideal current source; the arrow gives the current direction (out of terminal 2). |
| Dependent (controlled) current source | Sources | IEEE 315 / ANSI Y32.2 style | 1, 2 | G | Controlled current source (diamond); the arrow gives the current direction. The controlling quantity is written as the value. |
| Battery, multi-cell | Sources | IEC 60617 style / IEEE 315 | +, - | G | Battery of cells; long line is the positive pole of each cell. |
| Battery, multi-cell, with break | Sources | IEC 60617 style / IEEE 315 | +, - | G | Battery of many cells, drawn with a break (dashed) for the cells not shown. |
| Ground (bar) | Connections | IEEE 315 / ANSI Y32.2 style | 1 | - | Ground / reference, bar form. *The source shows it both ways up; rotate as needed.* |
| Ground, filled triangle | Connections | IEEE 315 / ANSI Y32.2 style | 1 | - | Ground / reference, filled-triangle form. *The source draws it point up below the connection; rotate as needed.* |
| Supply terminal, positive | Connections | IEEE 315 / ANSI Y32.2 style | 1 | - | Supply rail / terminal (positive). Write the voltage or net name (+5V, VCC) as the value. |
| Supply terminal, negative | Connections | IEEE 315 / ANSI Y32.2 style | 1 | - | Supply rail / terminal (negative). Write the voltage or net name (-5V, VEE) as the value. |
| Transformer with polarity dots (in phase) | Power | IEC 60617 style / IEEE 315 | P1, P2, S1, S2 | T | Two-winding transformer, iron core; the dotted ends P1 and S1 are in phase. |
| Transformer with polarity dots (inverting) | Power | IEC 60617 style / IEEE 315 | P1, P2, S1, S2 | T | Two-winding transformer, iron core; the dotted ends P1 and S2 are in phase (inverting). |
| Transformer, step-down, polarity dots (in phase) | Power | IEC 60617 style / IEEE 315 | P1, P2, S1, S2 | T | Transformer drawn with fewer secondary turns (step-down); P1 and S1 in phase. |
| Transformer, step-down, polarity dots (inverting) | Power | IEC 60617 style / IEEE 315 | P1, P2, S1, S2 | T | Transformer drawn with fewer secondary turns (step-down); P1 and S2 in phase. |
| Transformer, centre-tapped secondary | Power | IEC 60617 style / IEEE 315 | P1, P2, S1, CT, S2 | T | Transformer with centre-tapped secondary (tap CT); P1 and S1 in phase. |
| Transformer, centre-tapped secondary, inverting dots | Power | IEC 60617 style / IEEE 315 | P1, P2, S1, CT, S2 | T | Transformer with centre-tapped secondary (tap CT); P1 and S2 in phase. |
| Transformer, two secondary windings | Power | IEC 60617 style / IEEE 315 | P1, P2, S1, S2, S3, S4 | T | Transformer with two separate secondary windings S1-S2 and S3-S4; dotted ends in phase. |
| Autotransformer | Power | IEC 60617 style / IEEE 315 | 1, 2, 3 | T | Autotransformer: single winding 1-2 with tap 3. |
| Autotransformer with core | Power | IEC 60617 style / IEEE 315 | 1, 2, 3 | T | Autotransformer with magnetic core: single winding 1-2 with tap 3. |
| Switch, changeover (SPDT) | Switching | IEEE 315 / ANSI Y32.2 style | C, A, B | S | Single-pole double-throw switch: common C, contacts A (shown connected) and B. |
| Switch, two-pole (DPST) | Switching | IEEE 315 / ANSI Y32.2 style | 1, 2, 3, 4 | S | Two-pole make switch, poles operated together (dashed link). |
| Relay, coil with one make contact | Switching | IEC 60617 style / IEEE 315 | 13, 14, A1, A2 | K | Relay drawn as one unit: coil A1-A2 operating make contact 13-14 (dashed link). *To spread coil and contacts over a diagram, use el.coil.iec and the contact symbols.* |
| Relay, coil with two make contacts | Switching | IEC 60617 style / IEEE 315 | 13, 14, 23, 24, A1, A2 | K | Relay drawn as one unit: coil A1-A2 operating make contacts 13-14 and 23-24. |
| Selector switch, rotary, four positions | Switching | IEEE 315 / ANSI Y32.2 style | C, 1, 2, 3, 4 | S | Rotary selector: common C connected to one of the positions 1-4 (shown on 2). |
| Buzzer, AC | Signalling | IEC 60617 style / IEEE 315 | 1, 2 | H | Buzzer for alternating current. |
| Buzzer, DC | Signalling | IEC 60617 style / IEEE 315 | 1, 2 | H | Buzzer for direct current. |
| Voltmeter | Measuring | IEC 60617 style / IEEE 315 | 1, 2 | P | Voltmeter. |
| Ammeter | Measuring | IEC 60617 style / IEEE 315 | 1, 2 | P | Ammeter. |
| Galvanometer | Measuring | IEC 60617 style / IEEE 315 | 1, 2 | P | Galvanometer (sensitive current detector). |
| Motor, DC, with brushes | Machines | IEC 60617 style / IEEE 315 | 1, 2 | M | Direct-current motor; the rectangles are the brushes on the commutator. |
| PLC (programmable controller) | Control | IEC 60617 style | I0, I1, I2, I3, I4, I5, I6, I7, AI0, AI1, Q0, Q1, Q2, Q3, Q4, Q5, AO0, L+, M (varies with configuration) | PLC | Programmable logic controller: set its inputs and outputs, then program it in ladder, function blocks, sequential function chart, structured text, C or Python. L+ and M are its supply; inputs are I0, I1, ..., outputs Q0, Q1, ..., analog AI0, ... and AO0, ... |
| Position switch, make (NO) | Control | IEC 60617 style | 1, 2 | S | Position (limit) switch, normally open: operated by the machine. |
| Position switch, break (NC) | Control | IEC 60617 style | 1, 2 | S | Position (limit) switch, normally closed: operated by the machine. |
| Pressure switch contact, make (NO) | Control | IEC 60617 style | 1, 2 | S | Contact of a pressure switch, normally open. Give it the tag of the pressure switch on the fluid sheet. |
| Pressure switch contact, break (NC) | Control | IEC 60617 style | 1, 2 | S | Contact of a pressure switch, normally closed. Give it the tag of the pressure switch on the fluid sheet. |
| Selector switch, make (NO) | Control | IEC 60617 style | 1, 2 | S | Hand-operated switch that stays where it is put, normally open. |
| Selector switch, break (NC) | Control | IEC 60617 style | 1, 2 | S | Hand-operated switch that stays where it is put, normally closed. |
| Emergency stop | Control | IEC 60617 style | 1, 2 | S | Emergency stop, normally closed: stays open once pushed, until it is released. |
| Solenoid valve coil | Control | IEC 60617 style | A1, A2 | Y | Coil of a solenoid valve. Give it the tag of the valve on the fluid sheet: Y1, or Y1a and Y1b for the two solenoids of a double-solenoid valve. |
| Timer relay coil, on-delay | Control | IEC 60617 style | A1, A2 | KT | Relay coil that operates its contacts after a delay. Write the time in its label, e.g. 5 s. |
| Timer relay coil, off-delay | Control | IEC 60617 style | A1, A2 | KT | Relay coil that holds its contacts for a delay after it drops out. Write the time in its label, e.g. 5 s. |
| Main contacts, three-pole | Power | IEC 60617 style | 1, 3, 5, 2, 4, 6 | K | Three make contacts of a contactor (1-2, 3-4, 5-6). Give it the tag of the contactor's coil. |
| Circuit breaker, three-pole | Protection | IEC 60617 style | 1, 3, 5, 2, 4, 6 | Q | Three-pole circuit breaker (1-2, 3-4, 5-6). |
| Thermal overload relay, three-pole | Protection | IEC 60617 style | 1, 3, 5, 2, 4, 6 | F | Thermal overload heaters (1-2, 3-4, 5-6). Its normally closed trip contact is an el.contact.nc.iec with the same tag. Write the setting in its rating, e.g. 2.5 A. |
| Power supply, AC to DC | Sources | IEC 60617 style | L, N, +, - | G | Power supply unit: mains on L and N, DC out on + and -. Write the output in its label, e.g. 24 V. |

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
| Thermistor | Passive | IEC 60617 style | 1, 2 | R | Thermistor (temperature-dependent resistor), rectangle form. |
| Thermistor | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2 | R | Thermistor (temperature-dependent resistor), zig-zag form. |
| Resistor (rectangular-wave form) | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2 | R | Resistor drawn as a rectangular wave, as in the source library. |
| Inductor with magnetic core | Passive | IEC 60617 style | 1, 2 | L | Inductor with magnetic (iron or ferrite) core. |
| Inductor with magnetic core, preset adjustment | Passive | IEC 60617 style | 1, 2 | L | Inductor with magnetic core, preset (trimming) adjustment. |
| Inductor, preset adjustment | Passive | IEC 60617 style | 1, 2 | L | Inductor with preset (trimming) adjustment. |
| Rheostat (potentiometer, rheostat connection) | Passive | IEC 60617 style | 1, 2 | R | Variable resistor: wiper connected to terminal 1. |
| Rheostat (potentiometer, rheostat connection) | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2 | R | Variable resistor, zig-zag form: wiper connected to terminal 1. |
| Trimmer resistor, rheostat connection | Passive | IEC 60617 style | 1, 2 | R | Preset (trimmer) resistor with the wiper connected to terminal 1. |
| Trimmer resistor, rheostat connection | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2 | R | Preset (trimmer) resistor, zig-zag form, wiper connected to terminal 1. |
| Resistor, preset adjustment | Passive | IEC 60617 style | 1, 2 | R | Resistor with preset (trimming) adjustment, rectangle form. (The existing el.resistor.var.iec, with an arrow, is the continuously adjustable resistor.) |
| Resistor, preset adjustment | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2 | R | Resistor with preset (trimming) adjustment, zig-zag form. |
| Photoresistor (LDR) | Passive | IEC 60617 style | 1, 2 | R | Light-dependent resistor; arrows indicate incident light. |
| Photoresistor (LDR) | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2 | R | Light-dependent resistor, zig-zag form; arrows indicate incident light. |
| Photoresistor (LDR) in envelope | Passive | IEC 60617 style | 1, 2 | R | Light-dependent resistor in an envelope. |
| Photoresistor (LDR) in envelope | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2 | R | Light-dependent resistor, zig-zag form, in an envelope. |
| Capacitor, preset adjustment (trimmer) | Passive | IEC 60617 style / IEEE 315 | 1, 2 | C | Trimmer capacitor (preset adjustment). |
| Potentiometer | Passive | IEEE 315 / ANSI Y32.2 style | 1, 2, 3 | R | Resistor with movable contact (wiper, terminal 3), zig-zag form. |
| Inductor with sliding contact | Passive | IEC 60617 style | 1, 2, 3 | L | Inductor with movable (sliding) contact, terminal 3. |
| Capacitor, polarised (rectangle plate) | Passive | IEC 60617 style | +, - | C | Polarised capacitor; the open-rectangle plate and terminal + are positive. |
| Coaxial connector | Connections | IEEE 315 / ANSI Y32.2 style | C, S | X | Coaxial connector: centre conductor C, shield S. |
| Antenna | Connections | IEC 60617 style / IEEE 315 | 1 | W | Antenna, general symbol. |
| Schottky diode | Semiconductors | IEC 60617 style / IEEE 315 | A, K | D | Schottky (metal-semiconductor) diode. A anode, K cathode. |
| Varicap (varactor) diode | Semiconductors | IEC 60617 style / IEEE 315 | A, K | D | Variable-capacitance diode. A anode, K cathode. |
| Photodiode | Semiconductors | IEC 60617 style / IEEE 315 | A, K | D | Photodiode; arrows indicate incident light. A anode, K cathode. |
| DIAC | Semiconductors | IEC 60617 style / IEEE 315 | 1, 2 | D | Bidirectional trigger diode (DIAC). |
| TRIAC | Semiconductors | IEC 60617 style / IEEE 315 | MT2, MT1, G | Q | Bidirectional triode thyristor (TRIAC): main terminals MT2 and MT1, gate G at the MT1 side. |
| Thyristor (SCR), cathode gate | Semiconductors | IEC 60617 style / IEEE 315 | A, K, G | Q | Reverse-blocking triode thyristor, gate on the cathode side. A anode, K cathode, G gate. |
| Transient voltage suppressor, bidirectional | Semiconductors | IEC 60617 style / IEEE 315 | 1, 2 | D | Bidirectional breakdown (TVS / back-to-back Zener) diode. |
| Bridge rectifier | Semiconductors | IEC 60617 style / IEEE 315 | AC1, AC2, -, + | D | Full-wave bridge of four diodes: AC inputs AC1 (top) and AC2 (bottom), DC outputs + and -. |
| Rectifier (bridge) block | Semiconductors | IEC 60617 style | AC1, AC2, +, - | D | Rectifier as a block: AC inputs AC1 and AC2 (left), DC outputs + and - (right). |
| AC/DC converter | Semiconductors | IEC 60617 style | AC1, AC2, DC1, DC2 | U | Converter from alternating to direct current (rectifier), general block: AC side AC1/AC2 (left), DC side DC1/DC2 (right). *The source marks the AC side with ~ and the DC side with a bar; it does not mark the DC polarity, so the DC terminals are not named + and -.* |
| Phototransistor, NPN | Semiconductors | IEEE 315 / ANSI Y32.2 style | C, E | Q | NPN phototransistor: light acts as the base drive (no base connection). C collector, E emitter. |
| Phototransistor, PNP | Semiconductors | IEEE 315 / ANSI Y32.2 style | C, E | Q | PNP phototransistor: light acts as the base drive (no base connection). C collector, E emitter. |
| JFET, N-channel | Semiconductors | IEEE 315 / ANSI Y32.2 style | G, D, S | Q | Junction field-effect transistor, N-channel. G gate, D drain, S source. |
| JFET, P-channel | Semiconductors | IEEE 315 / ANSI Y32.2 style | G, D, S | Q | Junction field-effect transistor, P-channel. G gate, D drain, S source. |
| MOSFET, N-channel, enhancement | Semiconductors | IEEE 315 / ANSI Y32.2 style | G, D, S | Q | Enhancement-mode N-channel MOSFET in an envelope, body connected to the source. G gate, D drain, S source. |
| MOSFET, N-channel, enhancement (no envelope) | Semiconductors | IEEE 315 / ANSI Y32.2 style | G, D, S | Q | Enhancement-mode N-channel MOSFET, compact form with the arrow on the source. G gate, D drain, S source. |
| MOSFET, P-channel, enhancement | Semiconductors | IEEE 315 / ANSI Y32.2 style | G, D, S | Q | Enhancement-mode P-channel MOSFET in an envelope, body connected to the source. G gate, D drain, S source. |
| MOSFET, P-channel, enhancement (no envelope) | Semiconductors | IEEE 315 / ANSI Y32.2 style | G, D, S | Q | Enhancement-mode P-channel MOSFET, compact form with the arrow on the source. G gate, D drain, S source. |
| MOSFET, P-channel (gate-bubble form) | Semiconductors | IEEE 315 / ANSI Y32.2 style | G, D, S | Q | P-channel MOSFET, logic (gate-bubble) form. G gate, D drain, S source. |
| Microphone | Signalling | IEC 60617 style / IEEE 315 | 1, 2 | B | Microphone, general symbol. |
| Loudspeaker | Signalling | IEC 60617 style / IEEE 315 | 1, 2 | B | Loudspeaker, general symbol. |
| Operational amplifier with supply pins (+ input on top) | Integrated | IEEE 315 / ANSI Y32.2 style | +, -, OUT, V+, V- | U | Op-amp, triangle form, with supply pins V+ (top) and V- (bottom). |
| Operational amplifier with supply pins (- input on top) | Integrated | IEEE 315 / ANSI Y32.2 style | -, +, OUT, V+, V- | U | Op-amp, triangle form, with supply pins V+ (top) and V- (bottom). |
| Voltage regulator, three-terminal | Integrated | IEC 60617 style / IEEE 315 | IN, OUT, GND | U | Linear voltage regulator: input IN, output OUT, common GND. Write the type (e.g. 7805) as the value. |
| Vacuum diode, directly heated | Vacuum tubes | IEC 60617 style / IEEE 315 | A, F1, F2 | V | Vacuum diode with directly heated cathode (filament F1-F2) and anode A. |
| Vacuum diode, indirectly heated | Vacuum tubes | IEC 60617 style / IEEE 315 | A, K, F1, F2 | V | Vacuum diode with indirectly heated cathode K, heater F1-F2, anode A. |
| Triode | Vacuum tubes | IEC 60617 style / IEEE 315 | A, G, K, F1, F2 | V | Triode: anode A, control grid G, indirectly heated cathode K, heater F1-F2. |
| Tetrode | Vacuum tubes | IEC 60617 style / IEEE 315 | A, G2, G1, K, F1, F2 | V | Tetrode: anode A, screen grid G2, control grid G1, indirectly heated cathode K, heater F1-F2. |
| AND gate, 2 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, Y | U | AND gate, 2 inputs (A, B), output Y; distinctive shape. |
| NAND gate, 2 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, Y | U | NAND gate, 2 inputs (A, B), output Y; distinctive shape. |
| OR gate, 2 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, Y | U | OR gate, 2 inputs (A, B), output Y; distinctive shape. |
| NOR gate, 2 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, Y | U | NOR gate, 2 inputs (A, B), output Y; distinctive shape. |
| XOR gate, 2 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, Y | U | XOR gate, 2 inputs (A, B), output Y; distinctive shape. |
| XNOR gate, 2 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, Y | U | XNOR gate, 2 inputs (A, B), output Y; distinctive shape. |
| AND gate, 3 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, Y | U | AND gate, 3 inputs (A, B, C), output Y; distinctive shape. |
| NAND gate, 3 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, Y | U | NAND gate, 3 inputs (A, B, C), output Y; distinctive shape. |
| OR gate, 3 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, Y | U | OR gate, 3 inputs (A, B, C), output Y; distinctive shape. |
| NOR gate, 3 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, Y | U | NOR gate, 3 inputs (A, B, C), output Y; distinctive shape. |
| XOR gate, 3 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, Y | U | XOR gate, 3 inputs (A, B, C), output Y; distinctive shape. |
| XNOR gate, 3 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, Y | U | XNOR gate, 3 inputs (A, B, C), output Y; distinctive shape. |
| AND gate, 4 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, Y | U | AND gate, 4 inputs (A, B, C, D), output Y; distinctive shape. |
| NAND gate, 4 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, Y | U | NAND gate, 4 inputs (A, B, C, D), output Y; distinctive shape. |
| OR gate, 4 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, Y | U | OR gate, 4 inputs (A, B, C, D), output Y; distinctive shape. |
| NOR gate, 4 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, Y | U | NOR gate, 4 inputs (A, B, C, D), output Y; distinctive shape. |
| XOR gate, 4 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, Y | U | XOR gate, 4 inputs (A, B, C, D), output Y; distinctive shape. |
| XNOR gate, 4 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, Y | U | XNOR gate, 4 inputs (A, B, C, D), output Y; distinctive shape. |
| AND gate, 5 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, E, Y | U | AND gate, 5 inputs (A, B, C, D, E), output Y; distinctive shape. Extended input bar. |
| NAND gate, 5 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, E, Y | U | NAND gate, 5 inputs (A, B, C, D, E), output Y; distinctive shape. Extended input bar. |
| OR gate, 5 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, E, Y | U | OR gate, 5 inputs (A, B, C, D, E), output Y; distinctive shape. Extended input bar. |
| NOR gate, 5 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, E, Y | U | NOR gate, 5 inputs (A, B, C, D, E), output Y; distinctive shape. Extended input bar. |
| XOR gate, 5 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, E, Y | U | XOR gate, 5 inputs (A, B, C, D, E), output Y; distinctive shape. Extended input bar. |
| XNOR gate, 5 inputs | Logic | IEEE 315 / ANSI Y32.2 style | A, B, C, D, E, Y | U | XNOR gate, 5 inputs (A, B, C, D, E), output Y; distinctive shape. Extended input bar. |
| NOT gate (inverter) | Logic | IEEE 315 / ANSI Y32.2 style | A, Y | U | Inverter: input A, output Y. |
| Schmitt-trigger inverter | Logic | IEEE 315 / ANSI Y32.2 style | A, Y | U | Inverter with Schmitt-trigger (hysteresis) input: input A, output Y. |
| Schmitt-trigger buffer | Logic | IEEE 315 / ANSI Y32.2 style | A, Y | U | Buffer with Schmitt-trigger (hysteresis) input: input A, output Y. |
| D latch | Logic | IEEE 315 / ANSI Y32.2 style | D, E, Q, /Q | U | Transparent D latch: data D, enable E, outputs Q and /Q. |
| D flip-flop | Logic | IEEE 315 / ANSI Y32.2 style | D, CLK, Q, /Q | U | Edge-triggered D flip-flop: data D, clock CLK, outputs Q and /Q. |
| JK flip-flop | Logic | IEEE 315 / ANSI Y32.2 style | J, CLK, K, Q, /Q | U | Edge-triggered JK flip-flop: inputs J and K, clock CLK, outputs Q and /Q. |
| Full adder | Logic | IEEE 315 / ANSI Y32.2 style | CIN, A, B, Y, COUT | U | One-bit full adder: inputs A, B and carry CIN, sum Y and carry COUT. |
| Proximity sensor, PNP | Sensors | IEC 60617 style | +, -, OUT | B | Three-wire proximity sensor, PNP: OUT goes to + when it senses its target. |
| Proximity sensor, NPN | Sensors | IEC 60617 style | +, -, OUT | B | Three-wire proximity sensor, NPN: OUT goes to - when it senses its target. |
| Analog sensor, three-wire | Sensors | IEC 60617 style | +, -, OUT | B | Sensor or transmitter with an analog output: 0-10 V unless its label says otherwise. Give it the tag of the transducer on the fluid sheet. |
| Analog sensor, two-wire (4-20 mA) | Sensors | IEC 60617 style | +, - | B | Loop-powered transmitter: draws 4-20 mA from + to -, in line with the input that reads it. Give it the tag of the transducer on the fluid sheet. |

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
| Valve operator: Spring | Valve operators | ISO 1219-1 style |  | - | Spring - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid | Valve operators | ISO 1219-1 style |  | - | Solenoid - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot pressure | Valve operators | ISO 1219-1 style | X | - | Pilot pressure - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Lever | Valve operators | ISO 1219-1 style |  | - | Lever - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Push-button | Valve operators | ISO 1219-1 style |  | - | Push-button - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Manual, general | Valve operators | ISO 1219-1 style |  | - | Manual, general - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Detent | Valve operators | ISO 1219-1 style |  | - | Detent - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side. Two notches (two positions), the right-hand notch in use.* |
| Valve operator: Push-pull knob | Valve operators | ISO 1219-1 style |  | - | Push-pull knob - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pedal, single acting | Valve operators | ISO 1219-1 style |  | - | Pedal, single acting - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pedal, double acting | Valve operators | ISO 1219-1 style |  | - | Pedal, double acting - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Plunger | Valve operators | ISO 1219-1 style |  | - | Plunger - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Plunger with stroke limitation | Valve operators | ISO 1219-1 style |  | - | Plunger with stroke limitation - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Roller | Valve operators | ISO 1219-1 style |  | - | Roller - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Lever with roller | Valve operators | ISO 1219-1 style |  | - | Lever with roller - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Roller on cam (mechanical) | Valve operators | ISO 1219-1 style |  | - | Roller on cam (mechanical) - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid, push/pull | Valve operators | ISO 1219-1 style |  | - | Solenoid, push/pull - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid, proportional | Valve operators | ISO 1219-1 style |  | - | Solenoid, proportional - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot, direct (line only) | Valve operators | ISO 1219-1 style | X | - | Pilot, direct (line only) - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot, pressure applied (box) | Valve operators | ISO 1219-1 style | X | - | Pilot, pressure applied (box) - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot, remote supply | Valve operators | ISO 1219-1 style | X | - | Pilot, remote supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot, internal supply | Valve operators | ISO 1219-1 style |  | - | Pilot, internal supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Released pressure, remote exhaust | Valve operators | ISO 1219-1 style | X | - | Released pressure, remote exhaust - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Released pressure, internal return | Valve operators | ISO 1219-1 style |  | - | Released pressure, internal return - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid or pilot, external supply | Valve operators | ISO 1219-1 style | X | - | Solenoid or pilot, external supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid or pilot, internal supply | Valve operators | ISO 1219-1 style |  | - | Solenoid or pilot, internal supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid-operated pilot, external supply | Valve operators | ISO 1219-1 style | X | - | Solenoid-operated pilot, external supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid-operated pilot, internal supply | Valve operators | ISO 1219-1 style |  | - | Solenoid-operated pilot, internal supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Electric motor | Valve operators | ISO 1219-1 style |  | - | Electric motor - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Other control unit (not electric motor) | Valve operators | ISO 1219-1 style |  | - | Other control unit (not electric motor) - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Reversing motor | Valve operators | ISO 1219-1 style |  | - | Reversing motor - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pressure compensated | Valve operators | ISO 1219-1 style |  | - | Pressure compensated - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Thermal, local sensing | Valve operators | ISO 1219-1 style |  | - | Thermal, local sensing - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Thermal, remote bulb | Valve operators | ISO 1219-1 style |  | - | Thermal, remote bulb - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Servo | Valve operators | ISO 1219-1 style |  | - | Servo - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Reservoir (vented) | Fluid conditioning | ISO 1219-1 style | T | Z | Reservoir open to atmosphere; line ends below the fluid level. |
| Accumulator | Fluid conditioning | ISO 1219-1 style | P | Z | Accumulator, general symbol with separating element. *Gas-charge marking not shown.* |
| Filter | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Filter or strainer, general symbol. Flow 1→2. |
| Pressure gauge | Measurement | ISO 1219-1 style | P | S | Pressure indicator / gauge. |
| Flexible hose | Lines & connections | ISO 1219-1 style | 1, 2 | - | Flexible hose line between two connections. |
| Flexible line (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Flexible line; the dots are its connections. |
| Closed connection | Lines & connections | ISO 1219-1 style | 1 | - | Connection closed off (blanked) at this point. |
| Plugged port | Lines & connections | ISO 1219-1 style | 1 | - | Port closed by a plug (ISO 1219 and ANSI Y32.10 3.9.1 draw it the same way). |
| Test point | Lines & connections | ISO 1219-1 style | 1, 2 | - | Test / measuring connection on a line, with check and closed end. |
| Rotary union, one passage | Lines & connections | ISO 1219-1 style | 1, 2 | - | Rotating joint passing one line between a fixed and a rotating part. |
| Rotating coupling, three passages (ANSI) | Lines & connections | ANSI Y32.10 style | 1a, 1b, 2a, 2b, 3a, 3b | - | Rotating coupling with three passages (1a-1b, 2a-2b, 3a-3b). |
| Quick disconnect without checks, connected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling without checks, shown connected. |
| Quick disconnect without checks, disconnected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling without checks, shown disconnected. |
| Quick disconnect with two checks, connected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling with two checks, shown connected. |
| Quick disconnect with two checks, disconnected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling with two checks, shown disconnected. |
| Quick disconnect with one check, connected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling with one check, shown connected (the check is in the right-hand half). |
| Quick disconnect with one check, disconnected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling with one check, shown disconnected (the check is in the right-hand half). |
| Flow direction | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Direction of hydraulic flow in a line (also used to mark an energy source, Y32 4.4). |
| Flow direction, both ways | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Hydraulic flow in either direction. |
| Reservoir, return above fluid level | Reservoirs & accumulators | ISO 1219-1 style | T | Z | Reservoir open to atmosphere; the line ends above the fluid level. |
| Reservoir, vented, line above fluid level (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | T | Z | Reservoir, vented to atmosphere (complete symbol); the connection ends above the fluid level. |
| Reservoir, vented, line below fluid level (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | T | Z | Reservoir, vented to atmosphere (complete symbol); the connection ends below the fluid level. |
| Reservoir, pressurized, line above fluid level (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | T | Z | Reservoir, closed and pressurized (complete symbol); the connection ends above the fluid level. |
| Reservoir, pressurized, line below fluid level (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | T | Z | Reservoir, closed and pressurized (complete symbol); the connection ends below the fluid level. |
| Reservoir, bottom connection (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | T | Z | Vented reservoir with a connection through the bottom (draw only where essential to the circuit function, Y32 4.1.1). |
| Vented manifold (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | T | - | Return manifold vented to atmosphere and draining to the reservoir. |
| Accumulator, gas charged | Reservoirs & accumulators | ISO 1219-1 style | P | Z | Accumulator with gas pre-charge (gas side above the separating element). ANSI Y32.10 4.2.2 draws it the same way. |
| Accumulator (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | P | Z | Accumulator, general symbol without loading indication. |
| Accumulator, spring loaded (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | P | Z | Accumulator loaded by a spring above the separating element. |
| Accumulator, weighted (ANSI) | Reservoirs & accumulators | ANSI Y32.10 style | P | Z | Accumulator loaded by a weight resting on the separating element. |
| Heater | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Heater: heat introduced into the fluid. |
| Cooler | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Cooler: heat dissipated from the fluid (ANSI Y32.10 5.1.2 first form is drawn the same way). |
| Filter with clogging indicator | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Filter with visual contamination indicator. |
| Fluid conditioner, general (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Device controlling the physical characteristics of the fluid, general symbol. |
| Heater (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Heater; inside triangles indicate the introduction of heat. |
| Heater, liquid heating medium (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Heater with liquid heating-medium lines (C1 out, C2 in). |
| Cooler, liquid coolant (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Cooler with liquid coolant lines (C1 out, C2 in). |
| Temperature controller, liquid medium (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Temperature controller (heating and cooling) with liquid medium lines. |
| Heater, gaseous heating medium (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Heater with gaseous heating-medium lines (C1 out, C2 in). |
| Cooler, gaseous coolant (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Cooler with gaseous coolant lines (C1 out, C2 in). |
| Temperature controller, gaseous medium (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Temperature controller (heating and cooling) with gaseous medium lines. |
| Cooler, filled corners (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Cooler drawn with the corners filled in to represent heat dissipation. |
| Temperature controller (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Temperature maintained between two predetermined limits (heating and cooling). |
| Separator with manual drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, L | Z | Separator (e.g. water separator) with manual drain. |
| Separator with automatic drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, L | Z | Separator with automatic drain. |
| Filter-separator with manual drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, L | Z | Filter and separator with manual drain. |
| Filter-separator with automatic drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, L | Z | Filter and separator with automatic drain. |
| Water / oil cooler | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Oil cooler with liquid coolant; the arrows show the coolant flow (not connections). |
| Air / oil cooler | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Oil cooler with air cooling by fan; arrows show the air flow (not connections). |
| Breather with filter | Fluid conditioning | ISO 1219-1 style | 1 | Z | Reservoir air breather with filter element. *A small element drawn between the vent and the filter in the source chart is not legible and is not reproduced.* |
| Motor, fixed displacement, reversible | Pumps & motors | ISO 1219-1 style | A, B | M | Hydraulic motor, fixed displacement, two directions of rotation, without drain. |
| Motor, fixed displacement, reversible, with drain | Pumps & motors | ISO 1219-1 style | A, B | M | Reversible fixed-displacement motor with case drain to the reservoir. |
| Pump, fixed displacement, reversible, with drain | Pumps & motors | ISO 1219-1 style | A, B | P | Reversible fixed-displacement pump (flow in either direction) with case drain to the reservoir. |
| Rotary actuator | Pumps & motors | ISO 1219-1 style | A, B | M | Rotary (limited-angle) actuator. *Port positions follow the chart's other rotary devices; the chart's figure does not show them.* |
| Pump, fixed, unidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | P, S | P | Hydraulic pump, fixed displacement, one direction of flow (simplified, no shaft). |
| Pump, fixed, bidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Hydraulic pump, fixed displacement, flow in either direction. |
| Pump, variable, non-compensated, unidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | P, S | P | Variable-displacement pump, non-compensated, unidirectional (simplified). |
| Pump, variable, non-compensated, unidirectional, complete (ANSI) | Pumps & motors | ANSI Y32.10 style | P, S | P | Variable-displacement pump, non-compensated, unidirectional: control, shaft with rotation and case drain. |
| Pump, variable, non-compensated, bidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Variable-displacement pump, non-compensated, bidirectional (simplified). |
| Pump, variable, non-compensated, bidirectional, complete (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Variable-displacement pump, non-compensated, bidirectional: control, shaft with rotation and case drain. |
| Pump, variable, pressure compensated, unidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | P, S | P | Variable-displacement pump, pressure compensated, unidirectional (simplified). |
| Pump, variable, pressure compensated, unidirectional, complete (ANSI) | Pumps & motors | ANSI Y32.10 style | P, S | P | Variable-displacement pump, pressure compensated, unidirectional: control, shaft with rotation and case drain. |
| Pump, variable, pressure compensated, bidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Variable-displacement pump, pressure compensated, bidirectional (simplified). |
| Pump, variable, pressure compensated, bidirectional, complete (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Variable-displacement pump, pressure compensated, bidirectional: control, shaft with rotation and case drain. |
| Pump-motor: pump one way, motor the other (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Operating in one direction as a pump, in the other as a motor (simplified). |
| Pump-motor: pump one way, motor the other, complete (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Operating in one direction as a pump, in the other as a motor: control, shaft, rotation both ways. |
| Pump-motor, one flow direction (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | One direction of flow, operating as either a pump or a motor (simplified). |
| Pump-motor, one flow direction, complete (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | One direction of flow as a pump or a motor: control, shaft with rotation. |
| Pump-motor, both flow directions, variable, compensated (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Either flow direction as a pump or a motor; variable displacement, pressure compensated (simplified). |
| Pump-motor, both flow directions, variable, compensated, complete (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | P | Either flow direction as a pump or a motor, variable, pressure compensated: control, shaft, rotation. |
| Oscillator (rotary actuator, ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | M | Oscillating (limited-rotation) actuator. |
| Motor, fixed, unidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | M | Hydraulic motor, fixed displacement, one direction of rotation (simplified, no shaft); inlet A. *Interpretation: Y32.10 prints this figure with outward (pump-like) triangles; drawn with inward motor triangles by director decision D1. Y32.10's second orientation is the same symbol rotated.* |
| Motor, fixed, bidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | M | Hydraulic motor, fixed displacement, two directions of rotation (simplified, no shaft). *Interpretation: Y32.10 prints this figure with outward (pump-like) triangles; drawn with inward motor triangles by director decision D1.* |
| Motor, variable, unidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | M | Hydraulic motor, variable displacement, one direction of rotation (simplified, no shaft); inlet A. *Interpretation: Y32.10 prints this figure with outward (pump-like) triangles; drawn with inward motor triangles by director decision D1.* |
| Motor, variable, bidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | A, B | M | Hydraulic motor, variable displacement, two directions of rotation (simplified, no shaft). *Interpretation: Y32.10 prints this figure with outward (pump-like) triangles; drawn with inward motor triangles by director decision D1.* |
| Cylinder, single-acting (return by external force) | Cylinders | ISO 1219-1 style | A | A | Single-acting cylinder without spring: returned by load or external force. A = cap-end port; the rod-end stub is a vent, not a connection. |
| Cylinder, double-acting, adjustable damping one end | Cylinders | ISO 1219-1 style | A, B | A | Double-acting cylinder with adjustable cushioning (damping) at the cap end. |
| Cylinder, double-acting, adjustable damping both ends | Cylinders | ISO 1219-1 style | A, B | A | Double-acting cylinder with adjustable cushioning at both ends. |
| Cylinder, telescopic, double-acting | Cylinders | ISO 1219-1 style | A, B | A | Double-acting telescopic (multi-stage) cylinder. |
| Cylinder, telescopic, single-acting | Cylinders | ISO 1219-1 style | A | A | Single-acting telescopic (multi-stage) cylinder, returned by external force. |
| Cylinder, single-acting (ANSI) | Cylinders | ANSI Y32.10 style | A | A | Single-acting cylinder: body open at the rod end. A = cap-end port. |
| Cylinder, double-acting (ANSI) | Cylinders | ANSI Y32.10 style | A, B | A | Double-acting cylinder, single end rod. |
| Cylinder, double-acting, double end rod (ANSI) | Cylinders | ANSI Y32.10 style | A, B | A | Double-acting cylinder with rod through both ends. |
| Cylinder, fixed cushion, advance and retract (ANSI) | Cylinders | ANSI Y32.10 style | A, B | A | Double-acting cylinder with fixed cushions at both ends of the stroke. |
| Cylinder, adjustable cushion, advance only (ANSI) | Cylinders | ANSI Y32.10 style | A, B | A | Double-acting cylinder with an adjustable cushion on the advance stroke. |
| Cylinder, large rod, non-cushioned (ANSI) | Cylinders | ANSI Y32.10 style | A, B | A | Double-acting cylinder; rod drawn wide where the rod-to-bore ratio matters to the circuit. |
| Cylinder, large rod, cushioned advance and retract (ANSI) | Cylinders | ANSI Y32.10 style | A, B | A | Large-rod double-acting cylinder with cushions at both ends of the stroke. |
| Pressure intensifier (ANSI) | Cylinders | ANSI Y32.10 style | 1, 2 | A | Pressure intensifier (booster): large piston driving a small one; 1 = low-pressure inlet, 2 = high-pressure outlet. |
| Servo positioner, simplified (ANSI) | Cylinders | ANSI Y32.10 style | P | A | Cylinder with integral servo (positioning) valve; supply connection on top, return to reservoir. |
| Pressure-relief valve, pilot operated | Pressure control | ISO 1219-1 style | P, T | V | Pressure-relief valve, pilot operated (normally closed), pilot from the inlet. |
| Sequence valve | Pressure control | ISO 1219-1 style | P, A | V | Sequence valve, adjustable, pilot from the inlet; drain to the reservoir. |
| Relief / unloading valve, external pilot | Pressure control | ISO 1219-1 style | P, T, X | V | Relief / unloading valve with external hydraulic pilot X and internal drain. |
| Pressure-reducing valve with drain | Pressure control | ISO 1219-1 style | P, A | V | Pressure-reducing valve (normally open), pilot from the outlet, drain to the reservoir. |
| Unloading valve, solenoid operated | Pressure control | ISO 1219-1 style | P, T | V | Electrical unloading valve: pilot-operated relief vented by a solenoid. |
| Pressure-relief valve, proportional solenoid | Pressure control | ISO 1219-1 style | P, T | V | Electrical proportional relief valve: relief setting by a proportional solenoid. |
| Pressure-relief valve (ANSI) | Pressure control | ANSI Y32.10 style | P, T | V | Pressure relief, normally closed, pilot from the inlet. The same drawing is used for a sequence valve with internal drain (10.13.2) - the outlet connection tells them apart. |
| Sequence valve, external drain (ANSI) | Pressure control | ANSI Y32.10 style | P, A | V | Sequence valve, pilot from the inlet, drain to the reservoir. |
| Pressure-reducing valve (ANSI) | Pressure control | ANSI Y32.10 style | P, A | V | Pressure reducing, normally open, pilot from the outlet. |
| Pressure-reducing valve with drain (ANSI) | Pressure control | ANSI Y32.10 style | P, A | V | Pressure reducing, normally open, pilot from the outlet, drain to the reservoir. |
| Pressure-reducing and relieving valve (ANSI) | Pressure control | ANSI Y32.10 style | P, A | V | Pressure reducing and relieving: flow either way through the valve; relieving path from the inlet line to the reservoir; pilot from the outlet; drain to the reservoir. |
| Shut-off valve | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Manual shut-off (isolating) valve. |
| On-off valve, simplified (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Two-way on-off (manual shut-off) valve, simplified symbol. |
| Check valve, pilot operated to open | Non-return & flow | ISO 1219-1 style | 1, 2, X | V | Pilot-operated check valve: free flow 1 to 2; pilot pressure at X opens it for reverse flow. ANSI Y32.10 10.9.3 draws it the same way. *The chart's dash-dot cartridge outline is not drawn (centre-line style not available).* |
| Check valve, pilot operated to close (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2, X | V | Check valve held closed by pilot pressure at X. |
| Double check valve, without cross bleed (ANSI) | Non-return & flow | ANSI Y32.10 style | X, Y, A | V | Two inlets, one outlet; one-way flow (no cross bleed during transition). |
| Double check valve, with cross bleed (ANSI) | Non-return & flow | ANSI Y32.10 style | X, Y, A | V | Two inlets, one outlet; single poppet, cross bleed (reverse flow) possible during transition. |
| Check valve, pilot operated, with drain | Non-return & flow | ISO 1219-1 style | 1, 2, X | V | Pilot-operated check valve with external drain to the reservoir. *The chart's dash-dot cartridge outline is not drawn (centre-line style not available).* |
| Logic element (2-way cartridge) | Cartridge valves | ISO 1219-1 style | A, B | V | Two-way slip-in cartridge (logic element): spring-loaded poppet, ports A (side) and B (seat). *No control (X) connection is drawn in the source chart.* |
| Flow control, 3-way, adjustable | Non-return & flow | ISO 1219-1 style | P, A | V | Adjustable pressure-compensated flow control P -> A; excess flow from the inlet to the reservoir. |
| Flow control, 3-way, adjustable, with reverse-flow check | Non-return & flow | ISO 1219-1 style | P, A | V | Adjustable pressure-compensated flow control P -> A with a check for free reverse flow A -> P. *The chart's dash-dot component enclosure is not drawn (centre-line style deferred, director D3). Drawn as the chart draws it (no reservoir connection).* |
| Flow control, 3-way, adjustable, with reverse-flow check and tank line | Non-return & flow | ISO 1219-1 style | P, A | V | Adjustable pressure-compensated flow control P -> A, excess flow to the reservoir, check for free reverse flow A -> P. *The chart's dash-dot component enclosure is not drawn (centre-line style deferred, director D3).* |
| Lowering valve with reverse-flow check | Non-return & flow | ISO 1219-1 style | P, A | V | Pressure-compensated (non-adjustable) lowering valve: controlled flow P -> A, free reverse flow A -> P through the check. |
| Flow divider, spool type | Non-return & flow | ISO 1219-1 style | P, A, B | V | Spool-type flow divider: inlet P split into two equal flows A and B, the spools sensing the outlets. *The chart's dash-dot component enclosure is not drawn (centre-line style deferred, director D3).* |
| Flow divider, rotary (gear) type | Non-return & flow | ISO 1219-1 style | A1, A2, B1, B2 | V | Rotary flow divider: two mechanically coupled reversible motor sections. Each section has its own ports (A1/B1, A2/B2); feeding both A ports divides the flow equally to B1 and B2. |
| Priority valve | Non-return & flow | ISO 1219-1 style | P, CF, EF, LS | V | Priority (load-sensing) valve: inlet P feeds the controlled (priority) flow CF first; the excess flow goes to EF. Load-sensing pilot LS acts with the spring; CF pressure acts against it. *The chart's dash-dot component enclosure is not drawn (centre-line style deferred, director D3).* |
| Solenoid check valve, normally open | Directional valves | ISO 1219-1 style | 1, 2 | V | Seated 2/2 solenoid valve, normally open: open position flow 1 -> 2 (either way); check position blocks 1 -> 2 and allows free flow 2 -> 1. |
| Solenoid check valve, normally closed | Directional valves | ISO 1219-1 style | 1, 2 | V | Seated 2/2 solenoid valve, normally closed: open position flow 1 -> 2 (either way); check position blocks 1 -> 2 and allows free flow 2 -> 1. |
| Diverter (changeover) valve, 6-port, solenoid operated | Directional valves | ISO 1219-1 style | P, T, A1, A2, B1, B2 | V | Six-port diverter: P and T are switched between circuit 1 (A1, B1; spring position) and circuit 2 (A2, B2; solenoid energised); the circuit not selected is blocked. |
| Directional valve 3/2, seated, solenoid operated | Directional valves | ISO 1219-1 style | A, P, T | V | Direct-acting seated (poppet) 3/2 solenoid valve: spring position A -> T with P sealed on a seat; energised P -> A with T sealed. |
| Valve, infinite positioning, normally closed (ANSI) | Directional valves | ANSI Y32.10 style | P, X | V | Two-way valve with infinite positioning between open and closed, normally closed; adjustable spring, pilot X; outlet to the reservoir as drawn in Y32.10 10.12. |
| Valve, infinite positioning, normally open (ANSI) | Directional valves | ANSI Y32.10 style | P, X | V | Two-way valve with infinite positioning between open and closed, normally open; adjustable spring, pilot X; outlet to the reservoir as drawn in Y32.10 10.12. |
| Flow control, adjustable, non-compensated (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Adjustable restriction, flow controlled in each direction. *Y32.10 draws the same symbol on a pilot line (dashed); draw it on a pilot line as required.* |
| Flow control, adjustable, with bypass (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Flow 1 -> 2 is controlled; flow 2 -> 1 bypasses the control through the check. |
| Flow control, adjustable, pressure compensated, with bypass (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Pressure-compensated adjustable flow control 1 -> 2; flow 2 -> 1 bypasses through the check. |
| Flow control, adjustable, temperature and pressure compensated, with bypass (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Temperature- and pressure-compensated adjustable flow control 1 -> 2; flow 2 -> 1 bypasses through the check. *Y32.10 10.16.4 draws the bypass check although its title does not mention it.* |
| Two-way valve, infinite position, normally closed (ANSI) | Directional valves | ANSI Y32.10 style | 1, 2 | V | Two-way valve, infinite positioning, normally closed, spring offset. |
| Two-way valve, infinite position, normally open (ANSI) | Directional valves | ANSI Y32.10 style | 1, 2 | V | Two-way valve, infinite positioning, normally open, spring offset. |
| Three-way valve, distributor (ANSI) | Directional valves | ANSI Y32.10 style | A, B, P | V | Two-position three-way distributor: pressure at P goes first to B (normal), then to A (actuated). The inlet pressure-source marker of the source is not part of the symbol. |
| Three-way valve, two-pressure (ANSI) | Directional valves | ANSI Y32.10 style | P1, P2, A | V | Two-position three-way valve selecting between two pressure supplies: normal P2 -> A, actuated P1 -> A. The pressure-source markers of the source are not part of the symbol. |
| Pressure indicator | Measurement | ISO 1219-1 style | P | S | Pressure indicator (optical, e.g. pop-up or lamp type), connected at the bottom. *The short line on the right is drawn as in the chart; it is not a connection.* |
| Pressure transducer | Measurement | ISO 1219-1 style | P | S | Pressure transducer: pressure in at the bottom, electrical signal out (drawn, no electrical terminal). |
| Differential pressure gauge | Measurement | ISO 1219-1 style | P1, P2 | S | Differential pressure gauge with two connections. |
| Thermometer | Measurement | ISO 1219-1 style | P | S | Thermometer (temperature indicator). ANSI Y32.10 9.1.2 draws it the same way. |
| Flow indicator | Measurement | ISO 1219-1 style | P | S | Flow indicator, connected at the bottom. |
| Flow meter | Measurement | ISO 1219-1 style | 1, 2 | S | Flow meter (flow rate), in line. ANSI Y32.10 9.1.3.1 draws it the same way. |
| Pressure indicator / recorder (ANSI) | Measurement | ANSI Y32.10 style | P | S | Pressure indicating or recording instrument; connection at the top (Y32.10 also shows it from the side - rotate the symbol). |
| Flow meter, totalizing (ANSI) | Measurement | ANSI Y32.10 style | 1, 2 | S | Totalizing flow meter, in line. |
| Venturi (ANSI) | Measurement | ANSI Y32.10 style | 1, 2, X | S | Venturi: flow 1 - 2 through a converging-diverging section, sensing tap X at the throat. |
| Orifice plate (ANSI) | Measurement | ANSI Y32.10 style | 1, 2 | S | Orifice plate between flanges, in line. |
| Orifice plate with pressure taps (ANSI) | Measurement | ANSI Y32.10 style | 1, 2, X1, X2 | S | Orifice plate with upstream and downstream pressure taps X1 and X2. |
| Pitot tube (ANSI) | Measurement | ANSI Y32.10 style | 1, 2, X1, X2 | S | Pitot tube in a line 1 - 2; taps X1 and X2 (static and total pressure) below. Drawn as in Y32.10 9.2.3. |
| Nozzle (ANSI) | Measurement | ANSI Y32.10 style | 1 | S | Nozzle discharging in the direction of the arrow; inlet 1. |
| Pressure switch (ANSI) | Measurement | ANSI Y32.10 style | X | S | Pressure switch: pilot pressure at X operates the contact against the spring (electrical contacts drawn, no electrical terminals). *Y32.10 draws the pilot line as two dashes.* |
| Pressure switch | Measurement | ISO 1219-1 style | X | S | Pressure switch, adjustable: pilot pressure at X (below) operates the contact against the spring; electrical output drawn, no electrical terminals. |
| Fluid level gauge | Measurement | ISO 1219-1 style | 1 | S | Fluid level gauge (sight glass). |
| Fluid level transducer | Measurement | ISO 1219-1 style | 1 | S | Fluid level transducer: electrical signal out (drawn, no electrical terminal). |
| Energy direction, hydraulic | Drafting | ISO 1219-1 style |  | - | Filled triangle: hydraulic energy, pointing in the direction of flow. |

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
| Valve operator: Spring | Valve operators | ISO 1219-1 style |  | - | Spring - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid | Valve operators | ISO 1219-1 style |  | - | Solenoid - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot pressure | Valve operators | ISO 1219-1 style | 12 | - | Pilot pressure - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Lever | Valve operators | ISO 1219-1 style |  | - | Lever - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Push-button | Valve operators | ISO 1219-1 style |  | - | Push-button - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Manual, general | Valve operators | ISO 1219-1 style |  | - | Manual, general - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Detent | Valve operators | ISO 1219-1 style |  | - | Detent - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side. Two notches (two positions), the right-hand notch in use.* |
| Valve operator: Push-pull knob | Valve operators | ISO 1219-1 style |  | - | Push-pull knob - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pedal, single acting | Valve operators | ISO 1219-1 style |  | - | Pedal, single acting - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pedal, double acting | Valve operators | ISO 1219-1 style |  | - | Pedal, double acting - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Plunger | Valve operators | ISO 1219-1 style |  | - | Plunger - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Plunger with stroke limitation | Valve operators | ISO 1219-1 style |  | - | Plunger with stroke limitation - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Roller | Valve operators | ISO 1219-1 style |  | - | Roller - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Lever with roller | Valve operators | ISO 1219-1 style |  | - | Lever with roller - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Roller on cam (mechanical) | Valve operators | ISO 1219-1 style |  | - | Roller on cam (mechanical) - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid, push/pull | Valve operators | ISO 1219-1 style |  | - | Solenoid, push/pull - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid, proportional | Valve operators | ISO 1219-1 style |  | - | Solenoid, proportional - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot, direct (line only) | Valve operators | ISO 1219-1 style | 12 | - | Pilot, direct (line only) - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot, pressure applied (box) | Valve operators | ISO 1219-1 style | 12 | - | Pilot, pressure applied (box) - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot, remote supply | Valve operators | ISO 1219-1 style | 12 | - | Pilot, remote supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pilot, internal supply | Valve operators | ISO 1219-1 style |  | - | Pilot, internal supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Released pressure, remote exhaust | Valve operators | ISO 1219-1 style | 12 | - | Released pressure, remote exhaust - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Released pressure, internal return | Valve operators | ISO 1219-1 style |  | - | Released pressure, internal return - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid or pilot, external supply | Valve operators | ISO 1219-1 style | 12 | - | Solenoid or pilot, external supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid or pilot, internal supply | Valve operators | ISO 1219-1 style |  | - | Solenoid or pilot, internal supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid-operated pilot, external supply | Valve operators | ISO 1219-1 style | 12 | - | Solenoid-operated pilot, external supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Solenoid-operated pilot, internal supply | Valve operators | ISO 1219-1 style |  | - | Solenoid-operated pilot, internal supply - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Electric motor | Valve operators | ISO 1219-1 style |  | - | Electric motor - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Other control unit (not electric motor) | Valve operators | ISO 1219-1 style |  | - | Other control unit (not electric motor) - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Reversing motor | Valve operators | ISO 1219-1 style |  | - | Reversing motor - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Pressure compensated | Valve operators | ISO 1219-1 style |  | - | Pressure compensated - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Thermal, local sensing | Valve operators | ISO 1219-1 style |  | - | Thermal, local sensing - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Thermal, remote bulb | Valve operators | ISO 1219-1 style |  | - | Thermal, remote bulb - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Valve operator: Servo | Valve operators | ISO 1219-1 style |  | - | Servo - valve operator element (also available in the directional-valve configurator). *Drawn for the left side of a valve; mirror the component for the right side.* |
| Air receiver | Supply | ISO 1219-1 style | 1 | Z | Air receiver (pressure vessel). |
| Filter | Supply | ISO 1219-1 style | 1, 2 | Z | Air filter, general symbol (without water separator). Flow 1→2. |
| Pressure gauge | Measurement | ISO 1219-1 style | 1 | S | Pressure indicator / gauge. |
| Flexible hose | Lines & connections | ISO 1219-1 style | 1, 2 | - | Flexible hose line between two connections. |
| Flexible line (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Flexible line; the dots are its connections. |
| Closed connection | Lines & connections | ISO 1219-1 style | 2 | - | Connection closed off (blanked) at this point. |
| Plugged port | Lines & connections | ISO 1219-1 style | 2 | - | Port closed by a plug (ISO 1219 and ANSI Y32.10 3.9.1 draw it the same way). |
| Test point | Lines & connections | ISO 1219-1 style | 1, 2 | - | Test / measuring connection on a line, with check and closed end. |
| Rotary union, one passage | Lines & connections | ISO 1219-1 style | 1, 2 | - | Rotating joint passing one line between a fixed and a rotating part. |
| Rotating coupling, three passages (ANSI) | Lines & connections | ANSI Y32.10 style | 1a, 1b, 2a, 2b, 3a, 3b | - | Rotating coupling with three passages (1a-1b, 2a-2b, 3a-3b). |
| Quick disconnect without checks, connected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling without checks, shown connected. |
| Quick disconnect without checks, disconnected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling without checks, shown disconnected. |
| Quick disconnect with two checks, connected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling with two checks, shown connected. |
| Quick disconnect with two checks, disconnected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling with two checks, shown disconnected. |
| Quick disconnect with one check, connected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling with one check, shown connected (the check is in the right-hand half). |
| Quick disconnect with one check, disconnected (ANSI) | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Quick-disconnect coupling with one check, shown disconnected (the check is in the right-hand half). |
| Flow direction | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Direction of pneumatic flow in a line (also used to mark an energy source, Y32 4.4). |
| Flow direction, both ways | Lines & connections | ANSI Y32.10 style | 1, 2 | - | Pneumatic flow in either direction. |
| Exhaust to atmosphere, plain (not connectable) | Lines & connections | ANSI Y32.10 style | 3 | - | Outlet to atmosphere through a plain orifice that cannot be connected. |
| Exhaust to atmosphere, connectable | Lines & connections | ANSI Y32.10 style | 3 | - | Outlet to atmosphere through a connectable orifice (e.g. threaded). |
| Silencer (muffler) | Lines & connections | ANSI Y32.10 style | 3 | Z | Exhaust silencer / muffler. |
| Air receiver, inline (ANSI) | Supply | ANSI Y32.10 style | 1, 2 | Z | Receiver (pressure vessel) with inlet and outlet. |
| Heater | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Heater: heat introduced into the fluid. |
| Cooler | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Cooler: heat dissipated from the fluid (ANSI Y32.10 5.1.2 first form is drawn the same way). |
| Filter with clogging indicator | Fluid conditioning | ISO 1219-1 style | 1, 2 | Z | Filter with visual contamination indicator. |
| Fluid conditioner, general (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Device controlling the physical characteristics of the fluid, general symbol. |
| Heater (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Heater; inside triangles indicate the introduction of heat. |
| Heater, liquid heating medium (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Heater with liquid heating-medium lines (C1 out, C2 in). |
| Cooler, liquid coolant (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Cooler with liquid coolant lines (C1 out, C2 in). |
| Temperature controller, liquid medium (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Temperature controller (heating and cooling) with liquid medium lines. |
| Heater, gaseous heating medium (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Heater with gaseous heating-medium lines (C1 out, C2 in). |
| Cooler, gaseous coolant (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Cooler with gaseous coolant lines (C1 out, C2 in). |
| Temperature controller, gaseous medium (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, C1, C2 | Z | Temperature controller (heating and cooling) with gaseous medium lines. |
| Cooler, filled corners (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Cooler drawn with the corners filled in to represent heat dissipation. |
| Temperature controller (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Temperature maintained between two predetermined limits (heating and cooling). |
| Separator with manual drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, 3 | Z | Separator (e.g. water separator) with manual drain. |
| Separator with automatic drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, 3 | Z | Separator with automatic drain. |
| Filter-separator with manual drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, 3 | Z | Filter and separator with manual drain. |
| Filter-separator with automatic drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, 3 | Z | Filter and separator with automatic drain. |
| Air dryer, desiccant (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Desiccator (chemical dryer). |
| Lubricator (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Lubricator without drain. |
| Lubricator with manual drain (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2, 3 | Z | Lubricator with manual drain. |
| Airline accessories (FRL), simplified (ANSI) | Fluid conditioning | ANSI Y32.10 style | 1, 2 | Z | Filter, regulator and lubricator unit, simplified symbol: adjustable regulator with gauge in one body; flow 1 -> 2. *The open triangle on the inlet line is drawn as in Y32.10 11.2.* |
| Oscillator (rotary actuator, ANSI) | Pumps & motors | ANSI Y32.10 style | 2, 4 | M | Oscillating (limited-rotation) actuator. |
| Compressor, fixed displacement (ANSI) | Pumps & motors | ANSI Y32.10 style | 2, 1 | P | Compressor, fixed displacement (simplified, no shaft). |
| Vacuum pump, fixed displacement (ANSI) | Pumps & motors | ANSI Y32.10 style | 2, 1 | P | Vacuum pump, fixed displacement. |
| Air motor, unidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | 1, 2 | M | Pneumatic motor, one direction of rotation (simplified, no shaft). |
| Air motor, bidirectional (ANSI) | Pumps & motors | ANSI Y32.10 style | 2, 4 | M | Pneumatic motor, two directions of rotation (simplified, no shaft). *Interpretation: Y32.10 prints this figure with outward (pump-like) triangles; drawn with inward motor triangles by director decision D1.* |
| Cylinder, single-acting (return by external force) | Actuators | ISO 1219-1 style | A | A | Single-acting cylinder without spring: returned by load or external force. A = cap-end port; the rod-end stub is a vent, not a connection. |
| Cylinder, double-acting, adjustable damping one end | Actuators | ISO 1219-1 style | A, B | A | Double-acting cylinder with adjustable cushioning (damping) at the cap end. |
| Cylinder, double-acting, adjustable damping both ends | Actuators | ISO 1219-1 style | A, B | A | Double-acting cylinder with adjustable cushioning at both ends. |
| Cylinder, telescopic, double-acting | Actuators | ISO 1219-1 style | A, B | A | Double-acting telescopic (multi-stage) cylinder. |
| Cylinder, telescopic, single-acting | Actuators | ISO 1219-1 style | A | A | Single-acting telescopic (multi-stage) cylinder, returned by external force. |
| Cylinder, single-acting (ANSI) | Actuators | ANSI Y32.10 style | A | A | Single-acting cylinder: body open at the rod end. A = cap-end port. |
| Cylinder, double-acting (ANSI) | Actuators | ANSI Y32.10 style | A, B | A | Double-acting cylinder, single end rod. |
| Cylinder, double-acting, double end rod (ANSI) | Actuators | ANSI Y32.10 style | A, B | A | Double-acting cylinder with rod through both ends. |
| Cylinder, fixed cushion, advance and retract (ANSI) | Actuators | ANSI Y32.10 style | A, B | A | Double-acting cylinder with fixed cushions at both ends of the stroke. |
| Cylinder, adjustable cushion, advance only (ANSI) | Actuators | ANSI Y32.10 style | A, B | A | Double-acting cylinder with an adjustable cushion on the advance stroke. |
| Cylinder, large rod, non-cushioned (ANSI) | Actuators | ANSI Y32.10 style | A, B | A | Double-acting cylinder; rod drawn wide where the rod-to-bore ratio matters to the circuit. |
| Cylinder, large rod, cushioned advance and retract (ANSI) | Actuators | ANSI Y32.10 style | A, B | A | Large-rod double-acting cylinder with cushions at both ends of the stroke. |
| Pressure intensifier (ANSI) | Actuators | ANSI Y32.10 style | 1, 2 | A | Pressure intensifier (booster): large piston driving a small one; 1 = low-pressure inlet, 2 = high-pressure outlet. |
| Servo positioner, simplified (ANSI) | Actuators | ANSI Y32.10 style | 1 | A | Cylinder with integral servo (positioning) valve; supply connection on top, exhaust to atmosphere. |
| Pressure-relief valve (ANSI) | Pressure control | ANSI Y32.10 style | 1, 3 | V | Pressure relief, normally closed, pilot from the inlet. The same drawing is used for a sequence valve with internal drain (10.13.2) - the outlet connection tells them apart. |
| Sequence valve, external drain (ANSI) | Pressure control | ANSI Y32.10 style | 1, 2 | V | Sequence valve, pilot from the inlet, drain to the reservoir. |
| Pressure-reducing valve (ANSI) | Pressure control | ANSI Y32.10 style | 1, 2 | V | Pressure reducing, normally open, pilot from the outlet. |
| Pressure regulator, relieving (ANSI) | Pressure control | ANSI Y32.10 style | 1, 2 | V | Airline pressure regulator, adjustable, relieving (vents to atmosphere). |
| Shut-off valve | Non-return & flow | ISO 1219-1 style | 1, 2 | V | Manual shut-off (isolating) valve. |
| On-off valve, simplified (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Two-way on-off (manual shut-off) valve, simplified symbol. |
| Check valve, pilot operated to open | Non-return & flow | ISO 1219-1 style | 1, 2, 12 | V | Pilot-operated check valve: free flow 1 to 2; pilot pressure at 12 opens it for reverse flow. ANSI Y32.10 10.9.3 draws it the same way. *The chart's dash-dot cartridge outline is not drawn (centre-line style not available).* |
| Check valve, pilot operated to close (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2, 12 | V | Check valve held closed by pilot pressure at 12. |
| Double check valve, without cross bleed (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 1.1, 2 | V | Two inlets, one outlet; one-way flow (no cross bleed during transition). |
| Double check valve, with cross bleed (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 1.1, 2 | V | Two inlets, one outlet; single poppet, cross bleed (reverse flow) possible during transition. |
| Flow control, adjustable, non-compensated (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Adjustable restriction, flow controlled in each direction. *Y32.10 draws the same symbol on a pilot line (dashed); draw it on a pilot line as required.* |
| Flow control, adjustable, with bypass (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Flow 1 -> 2 is controlled; flow 2 -> 1 bypasses the control through the check. |
| Flow control, adjustable, pressure compensated, with bypass (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Pressure-compensated adjustable flow control 1 -> 2; flow 2 -> 1 bypasses through the check. |
| Flow control, adjustable, temperature and pressure compensated, with bypass (ANSI) | Non-return & flow | ANSI Y32.10 style | 1, 2 | V | Temperature- and pressure-compensated adjustable flow control 1 -> 2; flow 2 -> 1 bypasses through the check. *Y32.10 10.16.4 draws the bypass check although its title does not mention it.* |
| Two-way valve, infinite position, normally closed (ANSI) | Directional valves | ANSI Y32.10 style | 1, 2 | V | Two-way valve, infinite positioning, normally closed, spring offset. |
| Two-way valve, infinite position, normally open (ANSI) | Directional valves | ANSI Y32.10 style | 1, 2 | V | Two-way valve, infinite positioning, normally open, spring offset. |
| Three-way valve, distributor (ANSI) | Directional valves | ANSI Y32.10 style | 2, 4, 1 | V | Two-position three-way distributor: pressure at 1 goes first to 4 (normal), then to 2 (actuated). The inlet pressure-source marker of the source is not part of the symbol. |
| Three-way valve, two-pressure (ANSI) | Directional valves | ANSI Y32.10 style | 1a, 1b, 2 | V | Two-position three-way valve selecting between two pressure supplies: normal 1b -> 2, actuated 1a -> 2. The pressure-source markers of the source are not part of the symbol. |
| Pressure indicator | Measurement | ISO 1219-1 style | 1 | S | Pressure indicator (optical, e.g. pop-up or lamp type), connected at the bottom. *The short line on the right is drawn as in the chart; it is not a connection.* |
| Pressure transducer | Measurement | ISO 1219-1 style | 1 | S | Pressure transducer: pressure in at the bottom, electrical signal out (drawn, no electrical terminal). |
| Differential pressure gauge | Measurement | ISO 1219-1 style | 11, 12 | S | Differential pressure gauge with two connections. |
| Thermometer | Measurement | ISO 1219-1 style | 1 | S | Thermometer (temperature indicator). ANSI Y32.10 9.1.2 draws it the same way. |
| Flow indicator | Measurement | ISO 1219-1 style | 1 | S | Flow indicator, connected at the bottom. |
| Flow meter | Measurement | ISO 1219-1 style | 1, 2 | S | Flow meter (flow rate), in line. ANSI Y32.10 9.1.3.1 draws it the same way. |
| Pressure indicator / recorder (ANSI) | Measurement | ANSI Y32.10 style | 1 | S | Pressure indicating or recording instrument; connection at the top (Y32.10 also shows it from the side - rotate the symbol). |
| Flow meter, totalizing (ANSI) | Measurement | ANSI Y32.10 style | 1, 2 | S | Totalizing flow meter, in line. |
| Venturi (ANSI) | Measurement | ANSI Y32.10 style | 1, 2, X | S | Venturi: flow 1 - 2 through a converging-diverging section, sensing tap X at the throat. |
| Orifice plate (ANSI) | Measurement | ANSI Y32.10 style | 1, 2 | S | Orifice plate between flanges, in line. |
| Orifice plate with pressure taps (ANSI) | Measurement | ANSI Y32.10 style | 1, 2, X1, X2 | S | Orifice plate with upstream and downstream pressure taps X1 and X2. |
| Pitot tube (ANSI) | Measurement | ANSI Y32.10 style | 1, 2, X1, X2 | S | Pitot tube in a line 1 - 2; taps X1 and X2 (static and total pressure) below. Drawn as in Y32.10 9.2.3. |
| Nozzle (ANSI) | Measurement | ANSI Y32.10 style | 1 | S | Nozzle discharging in the direction of the arrow; inlet 1. |
| Pressure switch (ANSI) | Measurement | ANSI Y32.10 style | X | S | Pressure switch: pilot pressure at X operates the contact against the spring (electrical contacts drawn, no electrical terminals). *Y32.10 draws the pilot line as two dashes.* |
| Pressure switch | Measurement | ISO 1219-1 style | X | S | Pressure switch, adjustable: pilot pressure at X (below) operates the contact against the spring; electrical output drawn, no electrical terminals. |
| Energy direction, pneumatic | Drafting | ISO 1219-1 style |  | - | Hollow triangle: pneumatic energy, pointing in the direction of flow. |

## General

| Symbol | Group | Convention | Terminals | Ref. prefix | Notes |
|---|---|---|---|---|---|
| Function block, 2 terminals | Blocks | Generic | 1, 2 | U | Generic rectangular function block (use the label for its function). |
| Function block, 4 terminals | Blocks | Generic | 1, 2, 3, 4 | U | Generic rectangular function block with two terminals on each side. |
| Sheet connector (cross-sheet reference) | Connections | Generic | 1 | - | Connects a signal or line to every sheet connector with the same label anywhere in the project. The sheet and zone of the matching connectors are shown next to it automatically. |
| Direction of movement | Drafting | ISO 1219-1 style |  | - | Straight arrow: direction of linear movement. |
| Direction of movement, both ways | Drafting | ISO 1219-1 style |  | - | Double-headed arrow: linear movement in both directions. |
| Direction of rotation | Drafting | ISO 1219-1 style |  | - | Curved arrow: direction of rotation (mirror the element for the other direction). |
| Direction of rotation looking at shaft | Drafting | ISO 1219-1 style |  | - | Rotation arrow across a shaft (double line), seen looking at the shaft end. |
| Adjustable (regulation possible) | Drafting | ISO 1219-1 style |  | - | Arrow at about 45 degrees: the component can be adjusted or varied (also ANSI Y32.10 2.9). |
| Pressure compensated (mark) | Drafting | ANSI Y32.10 style |  | - | Arrow parallel to the short side of a symbol: the component is pressure compensated. |
| Temperature cause or effect (mark) | Drafting | ANSI Y32.10 style |  | - | Line ending in a dot: temperature cause or effect (thermometer). |
| Electric (energy type) | Drafting | ISO 1219-1 style |  | - | Electric energy / electrical actuation mark. |
| Solenoids working in opposite directions | Drafting | ISO 1219-1 style |  | - | Two windings acting in opposite directions. |
| Bus width marker | Drafting | Generic |  | - | Short slash drawn across a wire to show that it is a bus; write the number of lines beside it (source: ECL basic logic blocks). Place it over the wire; it does not connect. |
| Shaft coupling | Drafting | ISO 1219-1 style |  | - | Mechanical coupling between two shafts. |

## Directional control valves

Configurable through *Configure valve...*: hydraulic 2/2, 3/2, 4/2, 4/3 and pneumatic 2/2, 3/2, 5/2, 5/3; per-position flow paths (parallel, crossed, closed, tandem, float and open centres; pneumatic exhausted centre); up to two operators per side (spring, solenoid, pilot, lever, push-button, general manual). Ports are drawn on the rest position (the centre position of 3-position valves, otherwise the position next to the spring). Pilot operators add pilot ports (X/Y hydraulic; 12/14 or 10/12 pneumatic).

## Not included in this release

Symbols that could not be drawn with confidence without the standard documents were left out rather than guessed: silencers, lubricators and complete FRL units, proportional/servo valves, pressure switches and transducers, sequence and counterbalance valves, rotary actuators, quick couplings, logic gates, and IEC 60617 binary-logic symbols. Use the generic function blocks and the label field meanwhile.
