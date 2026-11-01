"""Targeted checks for corrupted or truncated source modules.

Motivation: development agents occasionally pushed single-line placeholders
(e.g. the whole file content ``PLACEHOLDER``) or only the first portion of a
large module. These tests catch those patterns without treating ordinary
``TODO`` comments, ``NotImplementedError``, or short legitimate modules as
failures.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "openschematix"

# Exact whole-file bodies (after strip) that mean the file is not real source.
_PLACEHOLDER_BODIES = frozenset({
    "placeholder",
    "todo",
    "tbd",
    "not_implemented",
    "not implemented",
    "pass",
})

# Line that is the *only* non-comment statement and is clearly a stub marker.
_STUB_LINE = re.compile(
    r"(?i)^(PLACEHOLDER|TODO_IMPLEMENT|NOT_IMPLEMENTED|see_local_artifacts\b.*)$"
)

# If the api package exists on this branch, these names must be defined in _core.
# Unfinished feature branches that do not ship openschematix/api/ are not checked.
_API_REQUIRED_NAMES = ("Project", "Sheet", "Component", "Wire", "new_project", "open_project")


def _iter_python_files():
    for base in (PKG, ROOT / "tests"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def _code_lines(text: str) -> list[str]:
    """Non-empty, non-comment lines (best-effort; not a full lexer)."""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines


def test_no_whole_file_placeholder_modules():
    """Fail if a .py file's entire non-comment body is a known corruption stub."""
    offenders = []
    for path in _iter_python_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        code = _code_lines(text)
        if not code:
            if path.name == "__init__.py":
                continue
            offenders.append(f"{path.relative_to(ROOT)}: empty module")
            continue
        if len(code) == 1:
            only = code[0].strip().strip("\"'")
            if only.lower() in _PLACEHOLDER_BODIES or _STUB_LINE.match(only):
                offenders.append(f"{path.relative_to(ROOT)}: stub body {only!r}")
    assert not offenders, "corrupted stub modules:\n  " + "\n  ".join(offenders)


def test_package_and_test_modules_parse():
    """Every package/test module must parse (catches truncated mid-statement uploads)."""
    errors = []
    for path in _iter_python_files():
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            ast.parse(src, filename=str(path))
        except SyntaxError as e:
            errors.append(f"{path.relative_to(ROOT)}: {e}")
    assert not errors, "syntax errors:\n  " + "\n  ".join(errors)


def _top_level_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_api_package_surface_when_present():
    """If ``openschematix/api`` exists, ``_core.py`` must expose the public handles.

    Branches that do not include the scripting API package are unaffected.
    """
    api_dir = PKG / "api"
    if not api_dir.is_dir():
        return
    core = api_dir / "_core.py"
    init = api_dir / "__init__.py"
    problems = []
    if not init.is_file():
        problems.append("openschematix/api/__init__.py missing")
    if not core.is_file():
        problems.append("openschematix/api/_core.py missing while api/ exists")
        assert not problems, "\n".join(problems)
        return
    tree = ast.parse(core.read_text(encoding="utf-8"), filename=str(core))
    defined = _top_level_names(tree)
    missing = [n for n in _API_REQUIRED_NAMES if n not in defined]
    if missing:
        problems.append(
            f"openschematix/api/_core.py is incomplete; missing {missing}. "
            "This usually means a truncated upload replaced the real module."
        )
    # A complete implementation defines many helpers; a 72-line stub only has a few.
    if len(defined) < len(_API_REQUIRED_NAMES):
        problems.append(
            f"openschematix/api/_core.py defines only {sorted(defined)}; "
            "expected a full scripting API implementation."
        )
    assert not problems, "\n".join(problems)


def test_integrity_allows_todo_comments_and_short_modules():
    """Regression: legitimate short files and TODO comments are not false positives."""
    samples = [PKG / "__main__.py", PKG / "__init__.py"]
    for path in samples:
        if path.is_file():
            ast.parse(path.read_text(encoding="utf-8"))
    # A synthetic one-liner that is *not* a placeholder must not match stub rules.
    assert not _STUB_LINE.match("x = 1")
    assert "todo" in _PLACEHOLDER_BODIES  # whole-body only; comments are ignored by _code_lines
