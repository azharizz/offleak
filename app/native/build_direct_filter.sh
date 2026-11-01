#!/bin/sh
# Build the direct OBS filter into app/.build/direct-filter (nothing is installed).
# OFFLEAK_BUILD_TESTS=1 also builds the test-socket variant and the synthetic test harness.
set -eu
: "${OBS_SDK:?Set OBS_SDK to an OBS 33.0.1 source checkout}"
: "${SIMDE_INCLUDE:?Set SIMDE_INCLUDE to the directory containing simde/}"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT="$HERE/../.build/direct-filter"
mkdir -p "$OUT"
printf '#pragma once\n#define OBS_RELEASE_CANDIDATE 0\n#define OBS_BETA 0\n' > "$OUT/obsconfig.h"
build() {  # $1 = output name, $2 = extra flag
  # shellcheck disable=SC2086
  clang -dynamiclib -std=gnu11 $2 -I"$OUT" -I"$SIMDE_INCLUDE" -I"$OBS_SDK/libobs" \
    "$HERE/direct-filter.c" -o "$OUT/$1" -F/Applications/OBS.app/Contents/Frameworks -framework libobs
}
build offleak-direct.so ''
if [ "${OFFLEAK_BUILD_TESTS:-0}" = 1 ]; then
  build offleak-direct-test.so -DOFFLEAK_DIRECT_TEST
  clang -std=gnu11 -I"$OUT" -I"$SIMDE_INCLUDE" -I"$OBS_SDK/libobs" \
    "$HERE/../tests/native/test_direct_filter.c" -o "$OUT/test-direct-filter" \
    -F/Applications/OBS.app/Contents/Frameworks -framework libobs -Wl,-rpath,/Applications/OBS.app/Contents/Frameworks
fi
printf 'Built the direct filter in %s; nothing installed.\n' "$OUT"
