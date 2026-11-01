#!/bin/sh
set -eu
# Build into an isolated cache, never over the user's installed OBS plugin.
: "${OBS_SDK:?Set OBS_SDK to an OBS 33.0.1 source checkout}"
: "${SIMDE_INCLUDE:?Set SIMDE_INCLUDE to the directory containing simde/}"
OUT="${GPU_PROTOTYPE_OUT:-playground/.cache/gpu-prototype}"
mkdir -p "$OUT"
printf '#pragma once\n#define OBS_RELEASE_CANDIDATE 0\n#define OBS_BETA 0\n' > "$OUT/obsconfig.h"
clang -dynamiclib -std=gnu11 -I"$OUT" -I"$SIMDE_INCLUDE" -I"$OBS_SDK/libobs" \
  playground/obs-plugin/gpu-prototype.c -o "$OUT/offleak-gpu.so" \
  -F/Applications/OBS.app/Contents/Frameworks -framework libobs
cp playground/obs-plugin/gpu-prototype.effect "$OUT/gpu-prototype.effect"
printf 'Built experimental source and filter in %s; not installed in OBS.\n' "$OUT"
