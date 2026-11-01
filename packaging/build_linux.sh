#!/usr/bin/env bash
# Build a self-contained Linux x86_64 bundle of OpenSchematix.
# Requirements: Python 3.10+ with Tkinter (Debian/Ubuntu: sudo apt install python3-tk python3-venv).
# Use the distribution's Python: its Tk is built with Xft (anti-aliased fonts). Self-contained Python
# builds (e.g. python-build-standalone / uv) ship a Tk without Xft, which bundles bitmap fonts.
# Output: dist/OpenSchematix-<version>-linux-x86_64.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python3 -c "import openschematix; print(openschematix.VERSION)")

if [ ! -d .build-venv ]; then
    python3 -m venv .build-venv
fi
# shellcheck disable=SC1091
source .build-venv/bin/activate
python -m pip install -r packaging/requirements-release.txt
python packaging/check_release_version.py

echo "Running tests..."
python -m pytest -q tests

echo "Building application..."
python -m PyInstaller --noconfirm --clean packaging/openschematix.spec
if python -c "import sys, tkinter, tkinter.font; r = tkinter.Tk(); sys.exit(0 if len(tkinter.font.families(r)) > 20 else 1)" 2>/dev/null; then
    echo "Tk font check: Xft fonts available."
else
    echo "WARNING: could not confirm Xft font support in this Tk (no display, or Tk built without Xft)." >&2
fi
mkdir -p dist/OpenSchematix/examples
cp examples/*.schematix examples/*.osch dist/OpenSchematix/examples/

cp packaging/linux/install.sh packaging/linux/openschematix.desktop packaging/linux/openschematix-mime.xml dist/OpenSchematix/
cp openschematix/resources/openschematix-256.png dist/OpenSchematix/openschematix.png
chmod +x dist/OpenSchematix/install.sh
tar -C dist -czf "dist/OpenSchematix-${VERSION}-linux-x86_64.tar.gz" OpenSchematix
echo "Bundle written to dist/OpenSchematix-${VERSION}-linux-x86_64.tar.gz"
