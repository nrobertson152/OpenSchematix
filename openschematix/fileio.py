"""Loading and saving OpenSchematix single-sheet documents."""
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
    raise FileFormatError("Not an OpenSchematix file.")


