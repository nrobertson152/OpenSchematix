"""Symbol library registry.

Three layers are searched in order:
  1. project symbols - custom symbols embedded in the open project (the
     exact versions its drawings were made with);
  2. user library    - custom symbols in the user's own libraries;
  3. built-in        - the read-only symbols shipped with the program.
Built-in ids can never be overridden by custom symbols.
"""
from __future__ import annotations

import json
from functools import lru_cache

from .base import Geometry, SymbolDef, Terminal, validate_geometry, LINE_WIDTHS, PORT_TYPES, port_domain  # noqa: F401
from . import electrical, fluid, general

CATEGORY_ORDER = ["Electrical", "Electronic", "Hydraulic", "Pneumatic", "General"]

_REGISTRY: dict[str, SymbolDef] = {}     # built-in
_USER: dict[str, SymbolDef] = {}         # user libraries
_PROJECT: dict[str, SymbolDef] = {}      # embedded in the open project


def _register_all():
    for mod in (electrical, fluid, general):
        for sym in mod.symbols():
            if sym.id in _REGISTRY:
                raise ValueError(f"duplicate symbol id {sym.id}")
            _REGISTRY[sym.id] = sym


_register_all()


def is_builtin(symbol_id: str) -> bool:
    return symbol_id in _REGISTRY


def get(symbol_id: str) -> SymbolDef | None:
    return _REGISTRY.get(symbol_id) or _PROJECT.get(symbol_id) or _USER.get(symbol_id)


def builtin_symbols() -> list[SymbolDef]:
    return list(_REGISTRY.values())


def all_symbols(include_custom: bool = True) -> list[SymbolDef]:
    out = list(_REGISTRY.values())
    if include_custom:
        ids = set(_REGISTRY)
        for d in (_PROJECT, _USER):
            for k, v in d.items():
                if k not in ids:
                    out.append(v)
                    ids.add(k)
    return out


def _clean(defs) -> dict:
    return {s.id: s for s in defs if s.id not in _REGISTRY}


def set_user_symbols(defs):
    _USER.clear()
    _USER.update(_clean(defs))
    _geometry_cached.cache_clear()


def set_project_symbols(defs):
    _PROJECT.clear()
    _PROJECT.update(_clean(defs))
    _geometry_cached.cache_clear()


def add_project_symbol(sd: SymbolDef):
    if sd.id not in _REGISTRY:
        _PROJECT[sd.id] = sd
        _geometry_cached.cache_clear()


def project_symbols() -> dict:
    return dict(_PROJECT)


def user_symbols() -> dict:
    return dict(_USER)


def categories() -> list[str]:
    present = {s.category for s in all_symbols()}
    return [c for c in CATEGORY_ORDER if c in present] + sorted(present - set(CATEGORY_ORDER))


def search(query: str, category: str | None = None, include_custom: bool = True) -> list[SymbolDef]:
    words = query.lower().split()
    out = []
    for s in all_symbols(include_custom):
        if category and s.category != category:
            continue
        text = s.search_text()
        if all(w in text for w in words):
            out.append(s)
    return out


@lru_cache(maxsize=1024)
def _geometry_cached(symbol_id: str, params_json: str) -> Geometry:
    sym = get(symbol_id) or get(general.UNKNOWN_ID)
    return sym.build(json.loads(params_json) if params_json else None)


def geometry(symbol_id: str, params: dict | None = None) -> Geometry:
    """Return (cached) geometry for a symbol and its parameters. Unknown ids
    resolve to the 'missing symbol' placeholder."""
    key = json.dumps(params, sort_keys=True) if params else ""
    return _geometry_cached(symbol_id, key)
