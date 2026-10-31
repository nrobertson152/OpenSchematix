# PyInstaller spec for OpenSchematix (Windows and Linux).
# Build from the repository root:  pyinstaller --noconfirm --clean packaging/openschematix.spec
# Produces a self-contained folder dist/OpenSchematix/ (no Python install needed).
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
RES = os.path.join(ROOT, "openschematix", "resources")

a = Analysis(
    [os.path.join(ROOT, "packaging", "launcher.py")],
    pathex=[ROOT],
    datas=[
        (RES, os.path.join("openschematix", "resources")),
        (os.path.join(ROOT, "LICENSE"), "."),
        (os.path.join(ROOT, "README.md"), "."),
        (os.path.join(ROOT, "CHANGELOG.md"), "."),
        (os.path.join(ROOT, "docs"), "docs"),
    ],
    hiddenimports=[],
    excludes=["numpy", "PIL", "pytest", "unittest", "pydoc", "test", "lib2to3"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OpenSchematix",
    console=False,
    icon=os.path.join(RES, "openschematix.ico") if sys.platform.startswith("win") else None,
    version=os.path.join(ROOT, "packaging", "windows_version_info.txt") if sys.platform.startswith("win") else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="OpenSchematix")
