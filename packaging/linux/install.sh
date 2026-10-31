#!/usr/bin/env bash
# Install (or remove with --uninstall) OpenSchematix for the current user.
# Run from the extracted OpenSchematix folder. No root access needed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
DEST="$DATA/openschematix"
BIN="$HOME/.local/bin"

if [ "${1:-}" = "--uninstall" ]; then
    rm -rf "$DEST" "$BIN/openschematix" "$DATA/applications/openschematix.desktop" \
           "$DATA/icons/hicolor/256x256/apps/openschematix.png" "$DATA/mime/packages/openschematix-mime.xml"
    update-desktop-database "$DATA/applications" 2>/dev/null || true
    update-mime-database "$DATA/mime" 2>/dev/null || true
    echo "OpenSchematix removed."
    exit 0
fi

mkdir -p "$DEST" "$BIN" "$DATA/applications" "$DATA/icons/hicolor/256x256/apps" "$DATA/mime/packages"
cp -a "$HERE/." "$DEST/"
ln -sf "$DEST/OpenSchematix" "$BIN/openschematix"
sed "s|@EXEC@|$DEST/OpenSchematix|" "$HERE/openschematix.desktop" > "$DATA/applications/openschematix.desktop"
cp "$HERE/openschematix.png" "$DATA/icons/hicolor/256x256/apps/openschematix.png"
cp "$HERE/openschematix-mime.xml" "$DATA/mime/packages/openschematix-mime.xml"
update-desktop-database "$DATA/applications" 2>/dev/null || true
update-mime-database "$DATA/mime" 2>/dev/null || true
echo "OpenSchematix installed to $DEST (launcher: $BIN/openschematix)."
