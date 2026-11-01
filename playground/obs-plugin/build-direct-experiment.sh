#!/bin/sh
set -eu
: "${OBS_SDK:?Set OBS_SDK to an OBS 33.0.1 source checkout}"
: "${SIMDE_INCLUDE:?Set SIMDE_INCLUDE to the directory containing simde/}"
OUT=playground/.cache/direct-filter
mkdir -p "$OUT"
printf '#pragma once\n#define OBS_RELEASE_CANDIDATE 0\n#define OBS_BETA 0\n' > "$OUT/obsconfig.h"
for MODE in normal test; do
  FLAG=
  [ "$MODE" = normal ] || FLAG=-DOFFLEAK_DIRECT_TEST
  # shellcheck disable=SC2086
  clang -dynamiclib -std=gnu11 $FLAG -I"$OUT" -I"$SIMDE_INCLUDE" -I"$OBS_SDK/libobs" \
    playground/obs-plugin/direct-filter-experiment.c -o "$OUT/offleak-direct-$MODE.so" \
    -F/Applications/OBS.app/Contents/Frameworks -framework libobs
 done
clang -std=gnu11 -I"$OUT" -I"$SIMDE_INCLUDE" -I"$OBS_SDK/libobs" \
  playground/obs-plugin/test-direct-filter.c -o "$OUT/test-direct-filter" \
  -F/Applications/OBS.app/Contents/Frameworks -framework libobs \
  -Wl,-rpath,/Applications/OBS.app/Contents/Frameworks
printf 'Built isolated experimental filter and test harness in %s; nothing installed.\n' "$OUT"
