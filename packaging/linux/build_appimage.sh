#!/usr/bin/env bash
# Package the PyInstaller bundle (dist/OpenSchematix, made by build_linux.sh or the release workflow)
# as an AppImage: dist/OpenSchematix-<version>-x86_64.AppImage
# Needs: appimagetool on PATH or in $APPIMAGETOOL (downloaded automatically if missing).
set -euo pipefail
cd "$(dirname "$0")/../.."
VERSION=$(python3 -c "import openschematix; print(openschematix.VERSION)")
BUNDLE=dist/OpenSchematix
[ -x "$BUNDLE/OpenSchematix" ] || { echo "Build the bundle first (packaging/build_linux.sh)." >&2; exit 1; }

APPDIR=dist/OpenSchematix.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/mime/packages"
cp -a "$BUNDLE" "$APPDIR/usr/lib/openschematix"
rm -f "$APPDIR/usr/lib/openschematix/install.sh"

sed "s|@EXEC@|OpenSchematix|" packaging/linux/openschematix.desktop > "$APPDIR/openschematix.desktop"
cp "$APPDIR/openschematix.desktop" "$APPDIR/usr/share/applications/openschematix.desktop"
cp openschematix/resources/openschematix-256.png "$APPDIR/openschematix.png"
cp openschematix/resources/openschematix-256.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/openschematix.png"
cp openschematix/resources/openschematix-256.png "$APPDIR/.DirIcon"
cp packaging/linux/openschematix-mime.xml "$APPDIR/usr/share/mime/packages/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/openschematix/OpenSchematix" "$@"
EOF
chmod +x "$APPDIR/AppRun"
chmod -R a+rX "$APPDIR"

TOOL="${APPIMAGETOOL:-$(command -v appimagetool || true)}"
if [ -z "$TOOL" ]; then
    TOOL=dist/appimagetool-x86_64.AppImage
    curl -fsSL -o "$TOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi
# Extract-and-run works without FUSE (CI runners, containers).
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$TOOL" --no-appstream "$APPDIR" "dist/OpenSchematix-${VERSION}-x86_64.AppImage"
echo "AppImage written to dist/OpenSchematix-${VERSION}-x86_64.AppImage"
