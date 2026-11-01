#!/bin/sh
# Build dist/Offleak-Setup-<version>.exe on macOS/Linux (needs mingw-w64 and makensis: brew install mingw-w64 makensis).
set -eu
. "$(dirname "$0")/common.sh"
fetch_obs_sources
sh "$APP/native/build_windows_plugin.sh"
make_icon
STAGE="$APP/.build/stage-windows"
stage_app "$STAGE"
cp "$APP/.build/windows/offleak-direct.dll" "$STAGE/native/"
cp "$APP/requirements-windows.txt" "$STAGE/"
mkdir -p "$STAGE/installers/windows"
cp "$APP/installers/windows/setup.ps1" "$STAGE/installers/windows/"
cp "$APP/installers/windows/Start Offleak.bat" "$STAGE/"
cp "$APP/.build/icon/offleak.ico" "$STAGE/"
makensis -V2 -DVERSION="$VERSION" -DPAYLOAD="$STAGE" -DOUTFILE="$DIST/Offleak-Setup-$VERSION.exe" "$APP/installers/windows/offleak.nsi"
printf 'Built %s\n' "$DIST/Offleak-Setup-$VERSION.exe"
