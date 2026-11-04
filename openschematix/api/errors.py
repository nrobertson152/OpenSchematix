"""Exceptions raised by the OpenSchematix scripting API.

Every error raised deliberately by :mod:`openschematix.api` derives from
:class:`ApiError`, so a script can catch them all with one ``except``. Each
class also derives from the matching built-in exception (``KeyError`` or
``ValueError``) so ordinary Python error handling keeps working.
"""
from __future__ import annotations


class ApiError(Exception):
    """Base class of all scripting-API errors."""

    def __str__(self) -> str:      # KeyError would otherwise repr() the message
        return str(self.args[0]) if self.args else ""


class SymbolNotFoundError(ApiError, KeyError):
    """No symbol with the given identifier exists (built-in, loaded user
    library, or embedded in the project)."""


class ObjectNotFoundError(ApiError, KeyError):
    """A sheet, component, wire or terminal does not exist, or the object a
    handle refers to has been removed."""


class InvalidOperationError(ApiError, ValueError):
    """The operation would produce invalid engineering data (off-grid
    position, unsupported rotation, diagonal wire, invalid symbol parameter,
    locked object, ...). Nothing is changed when this is raised."""


class ProjectFileError(ApiError, ValueError):
    """A project file cannot be read or written."""
