#!/bin/sh
# Cross-compile the direct filter for Windows x64 OBS 33 on macOS/Linux with MinGW-w64 (brew install mingw-w64).
# The obs.dll import library is generated from exactly the libobs symbols the plugin uses, so no Windows SDK is needed.
# Output: app/.build/windows/offleak-direct.dll (installed by the Windows installer into OBS's plugin folder).
set -eu
: "${OBS_SDK:?Set OBS_SDK to an OBS Studio 33.0.1 source checkout}"
: "${SIMDE_INCLUDE:?Set SIMDE_INCLUDE to the directory containing simde/}"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT="$HERE/../.build/windows"
CC=x86_64-w64-mingw32-gcc
mkdir -p "$OUT"
printf '#pragma once\n#define OBS_RELEASE_CANDIDATE 0\n#define OBS_BETA 0\n' > "$OUT/obsconfig.h"
$CC -c -std=gnu11 -O2 -Wall -Wextra -I"$OUT" -I"$SIMDE_INCLUDE" -I"$OBS_SDK/libobs" -I"$OBS_SDK/deps/w32-pthreads" \
  "$HERE/direct-filter.c" -o "$OUT/direct-filter.o"
{ echo 'LIBRARY obs.dll'; echo 'EXPORTS'
  x86_64-w64-mingw32-nm -u "$OUT/direct-filter.o" | awk '{print $2}' | grep -E '^(obs_|gs_|blog$|os_|bfree$|bmalloc$|bzalloc$)' | sort -u
} > "$OUT/obs.def"
x86_64-w64-mingw32-dlltool -d "$OUT/obs.def" -l "$OUT/libobs.dll.a" -D obs.dll
$CC -shared -o "$OUT/offleak-direct.dll" "$OUT/direct-filter.o" -L"$OUT" -lobs.dll -lws2_32 -static-libgcc
printf 'Built %s\n' "$OUT/offleak-direct.dll"
