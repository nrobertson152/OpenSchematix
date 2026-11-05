"""Starting FluidWorx, the simulator for circuits drawn here. FluidWorx is optional and a separate program.

Only finds a program and starts it on a saved file. Nothing is sent anywhere, and no file format changes.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys

ENV_VAR = "OPENSCHEMATIX_FLUIDWORX"
NAMES = ("fluidworx", "FluidWorx")


def find_fluidworx(configured: str = "") -> list[str] | None:
    """Command that runs FluidWorx: the path in Preferences, an environment variable, PATH, then an
    installed Python package. None if it isn't there."""
    for candidate in (configured, os.environ.get(ENV_VAR, "")):
        if candidate and (os.path.isfile(candidate) or shutil.which(candidate)):
            return [candidate]
    for name in NAMES:
        found = shutil.which(name)
        if found:
            return [found]
    if not getattr(sys, "frozen", False):
        try:
            if importlib.util.find_spec("fluidworx") is not None:
                return [sys.executable, "-m", "fluidworx"]
        except (ImportError, ValueError):
            pass
    return None


def child_environment(environ=None, frozen=None) -> dict:
    """Environment for a program started from here. A packaged OpenSchematix points these variables at its own
    libraries, which would break a different program that inherited them."""
    env = dict(os.environ if environ is None else environ)
    if getattr(sys, "frozen", False) if frozen is None else frozen:
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        for key in ("TCL_LIBRARY", "TK_LIBRARY", "TKPATH"):
            env.pop(key, None)
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is not None:
            env["LD_LIBRARY_PATH"] = original
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


def launch(command: list[str], path: str) -> None:
    """Start FluidWorx on a file and leave it running. Raises OSError if it can't be started."""
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
          "env": child_environment()}
    if sys.platform.startswith("win"):
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen([*command, path], **kw)  # noqa: S603 - the user's own program, no shell
