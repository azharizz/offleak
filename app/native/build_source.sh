#!/bin/sh
# Build and install the native "Offleak Redacted Video" OBS source (Virtual Camera path).
# Run from anywhere with OBS 33.0.1 sources and SIMDe headers available.
set -eu
: "${OBS_SDK:?Set OBS_SDK to an OBS Studio 33.0.1 source checkout}"
: "${SIMDE_INCLUDE:?Set SIMDE_INCLUDE to the directory containing simde/}"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_DIR="${OFFLEAK_PLUGIN_DIR:-$HOME/Library/Application Support/obs-studio/plugins/offleak.plugin}"
BUILD_DIR=$(mktemp -d)
trap 'rm -r "$BUILD_DIR"' EXIT
printf '#pragma once\n#define OBS_RELEASE_CANDIDATE 0\n#define OBS_BETA 0\n' > "$BUILD_DIR/obsconfig.h"
mkdir -p "$PLUGIN_DIR/Contents/MacOS" "$PLUGIN_DIR/Contents/Resources"
clang -dynamiclib -std=gnu11 -I"$BUILD_DIR" -I"$SIMDE_INCLUDE" -I"$OBS_SDK/libobs" \
  "$HERE/offleak-source.c" -o "$PLUGIN_DIR/Contents/MacOS/offleak" \
  -F/Applications/OBS.app/Contents/Frameworks -framework libobs
cp "$HERE/Info.plist" "$PLUGIN_DIR/Contents/Info.plist"
codesign --force --sign - "$PLUGIN_DIR"
printf 'Installed %s\n' "$PLUGIN_DIR"
