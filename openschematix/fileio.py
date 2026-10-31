"""Loading and saving documents, including migration of HPS Schematix
(.hpss, versions 1.0-1.2) files."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field

from . import FILE_FORMAT, FILE_SCHEMA, symbols
from .editing import route
from .geometry import norm_rotation, snap
from .model import Component, Document, Wire
from .symbols.fluid import default_valve_params
from .symbols.general import UNKNOWN_ID


class FileFormatError(ValueError):
    pass


@dataclass
class LoadResult:
    document: Document
    migrated: bool = False
    warnings: list = field(default_factory=list)


def save(doc: Document, path: str):
    """Write atomically: a crash or full disk never leaves a half-written file."""
    data = json.dumps(doc.to_dict(), indent=1, ensure_ascii=False)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".osch-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load(path: str) -> LoadResult:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except UnicodeDecodeError as e:
        raise FileFormatError("The file is not a text (JSON) schematic file.") from e
    except json.JSONDecodeError as e:
        raise FileFormatError(f"The file is not valid JSON: {e}") from e
    return load_data(data)


def load_data(data) -> LoadResult:
    if not isinstance(data, dict):
        raise FileFormatError("Unrecognised file contents.")
    fmt = data.get("format")
    if fmt == FILE_FORMAT:
        schema = data.get("schema", 1)
        if not isinstance(schema, int) or schema > FILE_SCHEMA:
            raise FileFormatError(f"This file was written by a newer version of OpenSchematix (schema {schema}).")
        try:
            doc = Document.from_dict(data)
        except (KeyError, TypeError, ValueError) as e:
            raise FileFormatError(f"The file is damaged or incomplete: {e}") from e
        res = LoadResult(doc)
        unknown = sorted({c.symbol for c in doc.components.values() if symbols.get(c.symbol) is None})
        if unknown:
            res.warnings.append("Unknown symbols shown as placeholders: " + ", ".join(unknown))
        return res
    if fmt == "HPS Schematix":
        return migrate_hps(data)
    raise FileFormatError("Not an OpenSchematix or HPS Schematix file.")


# ================================================================ migration
LEGACY_MAP = {
    # hydraulic
    "pump": "fl.hyd.pump", "motor": "fl.hyd.motor", "cylinder": "fl.hyd.cyl.single",
    "double acting cylinder": "fl.hyd.cyl.double", "reservoir": "fl.hyd.tank", "filter": "fl.hyd.filter",
    "check valve": "fl.hyd.check", "relief valve": "fl.hyd.relief", "directional valve 4/3": "fl.hyd.dcv",
    "flow control": "fl.hyd.throttle.adj", "pressure gauge": "fl.hyd.gauge", "accumulator": "fl.hyd.accumulator",
    # pneumatic
    "compressor": "fl.pneu.compressor", "air receiver": "fl.pneu.receiver", "frl": "fl.pneu.filter",
    "regulator": "fl.pneu.regulator", "pneumatic cylinder": "fl.pneu.cyl.double",
    "directional valve 3/2": "fl.pneu.dcv", "shuttle valve": "fl.pneu.shuttle",
    # electrical
    "resistor": "el.resistor.iec", "capacitor": "el.capacitor", "inductor": "el.inductor", "diode": "el.diode",
    "led": "el.led", "switch no": "el.contact.no.iec", "switch nc": "el.contact.nc.iec", "fuse": "el.fuse.iec",
    "ground": "el.earth", "battery": "el.cell", "motor (electrical)": "el.motor", "solenoid": "el.coil.iec",
    "relay coil": "el.coil.iec", "lamp": "el.lamp.iec", "terminal": "el.terminal",
}

LEGACY_PATTERN = {"straight": "parallel", "cross": "crossed", "closed": "closed", "float": "float"}
LEGACY_OPERATOR = {"spring": "spring", "solenoid": "solenoid", "proportional solenoid": "solenoid", "lever": "lever",
                   "pushbutton": "pushbutton", "hydraulic pilot": "pilot", "pneumatic pilot": "pilot"}


def _legacy_valve_params(spec):
    pos = [LEGACY_PATTERN.get(p, "closed") for p in spec.get("positions", ["straight", "cross"])]
    if len(pos) >= 3:
        pos = [pos[0], pos[len(pos) // 2], pos[-1]]
        vtype = "4/3"
    else:
        pos = (pos + ["crossed"])[:2]
        vtype = "4/2"
    params = default_valve_params("hyd", vtype)
    params["positions"] = pos
    for side in ("left", "right"):
        op = LEGACY_OPERATOR.get(spec.get(side, "none"))
        params[side] = [op] if op else []
        if vtype == "4/3" and op and op != "spring":
            params[side] = ["spring", op]
    return params


def migrate_hps(data) -> LoadResult:
    comps = data.get("components")
    conns = data.get("connections")
    if not isinstance(comps, list) or not isinstance(conns, list):
        raise FileFormatError("HPS Schematix file is missing components or connections.")
    doc = Document()
    res = LoadResult(doc, migrated=True)
    unknown = set()
    approximated = set()
    idmap = {}
    for c in comps:
        try:
            old_id = c["id"]
            t = str(c.get("type", ""))
            key = t.lower()
            params = {}
            if key == "custom directional valve":
                sym = "fl.hyd.dcv"
                params = _legacy_valve_params(c.get("valve", {}))
                approximated.add("custom directional valves")
            elif key in LEGACY_MAP:
                sym = LEGACY_MAP[key]
                if sym.endswith(".dcv"):
                    params = default_valve_params("hyd" if sym.startswith("fl.hyd") else "pneu",
                                                  "4/3" if "4/3" in key else "3/2")
            else:
                sym = UNKNOWN_ID
                unknown.add(t or "?")
            label = str(c.get("label", ""))
            if sym == UNKNOWN_ID:
                label = (label + " " if label else "") + f"[{t}]"
            comp = Component(id=doc.new_id(), symbol=sym, x=snap(float(c["x"])), y=snap(float(c["y"])),
                             rotation=norm_rotation(c.get("rotation", 0)), designator=str(c.get("tag", "")),
                             label=label, params=params)
            doc.add_component(comp)
            idmap[old_id] = comp
        except (KeyError, TypeError, ValueError) as e:
            res.warnings.append(f"Skipped an unreadable component: {e}")
    for w in conns:
        a, b = idmap.get(w.get("a")), idmap.get(w.get("b"))
        if not a or not b:
            res.warnings.append("Skipped a connection to a missing component.")
            continue
        ta, tb = a.terminals(), b.terminals()
        if not ta or not tb:
            continue
        na = w.get("ap") if w.get("ap") in ta else None
        nb = w.get("bp") if w.get("bp") in tb else None
        if na is None or nb is None:
            # choose the closest pair of terminals, as the old renderer did
            pairs = [(i, j) for i in ta for j in tb]
            na2, nb2 = min(pairs, key=lambda ij: (ta[ij[0]][0] - tb[ij[1]][0]) ** 2 + (ta[ij[0]][1] - tb[ij[1]][1]) ** 2)
            na, nb = na or na2, nb or nb2
        pts = route(ta[na], a.terminal_dirs().get(na), tb[nb], b.terminal_dirs().get(nb), [a.bbox(), b.bbox()])
        doc.add_wire(Wire(id=doc.new_id(), points=pts, start=[a.id, na], end=[b.id, nb], auto=True))
    res.warnings.insert(0, "Converted from an HPS Schematix file. Symbols were replaced with the corrected "
                           "OpenSchematix library and connections were redrawn as simple orthogonal wires; "
                           "please review the layout before saving.")
    if unknown:
        res.warnings.append("No equivalent symbol for: " + ", ".join(sorted(unknown)) + " (placeholders inserted).")
    if approximated:
        res.warnings.append("Approximated: " + ", ".join(sorted(approximated)) + ".")
    if any(c.get("type") == "Custom Drawn Symbol" for c in comps):
        res.warnings.append("Custom drawn symbols are not supported in this version and were replaced by placeholders.")
    return res
