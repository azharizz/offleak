#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine . 2>/dev/null || true  # files copied from the downloaded disk image
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
printf '\nOffleak installer for macOS Apple Silicon and OBS 33.0.1\n\n'
fail() { printf '\n%s\n' "$1"; exit 1; }
trap 'status=$?; if [ "$status" -ne 0 ]; then printf "\nInstallation stopped (error %s). Review the message above and run the installer again.\n" "$status"; read -r -p "Press Return to close. " _; fi' EXIT
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || fail 'This installer currently supports Apple Silicon Macs only.'
[ -d /Applications/OBS.app ] || fail 'Install OBS Studio 33.0.1 in /Applications first, then run this installer again.'
OBS_VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' /Applications/OBS.app/Contents/Info.plist)
[ "$OBS_VERSION" = 33.0.1 ] || fail "This build is tested with OBS 33.0.1; installed version is $OBS_VERSION."
if ! command -v python3.11 >/dev/null || ! command -v ffmpeg >/dev/null; then
  command -v brew >/dev/null || fail 'Install Homebrew from https://brew.sh, then run this installer again.'
  command -v python3.11 >/dev/null || brew install python@3.11
  command -v ffmpeg >/dev/null || brew install ffmpeg
fi
if [ ! -x .venv/bin/python ]; then
  printf '\nCreating Python environment...\n'
  python3.11 -m venv .venv
fi
if ! .venv/bin/python -c 'import cv2, Foundation, AppKit, Vision, Quartz, flask, torch, ultralytics, qrdet, lap, scipy, websocket; assert hasattr(cv2, "FaceRecognizerSF")' >/dev/null 2>&1; then
  printf '\nInstalling Python dependencies (this may take several minutes)...\n'
  .venv/bin/python -m pip install -r requirements-macos.txt
  .venv/bin/python -m pip install --force-reinstall --no-deps opencv-contrib-python-headless==4.12.0.88
fi
printf '\nChecking detector models...\n'
sh scripts/download_models.sh
PLUGINS="$HOME/Library/Application Support/obs-studio/plugins"
# install_plugin <prebuilt binary> <bundle and executable name>: user-only OBS plugin bundle, ad-hoc signed
install_plugin() {
  bundle="$PLUGINS/$2.plugin"
  mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources"
  cp "$1" "$bundle/Contents/MacOS/$2"
  sed -e "s|<string>offleak</string>|<string>$2</string>|" -e "s|com.offleak.obs<|com.offleak.obs.$2<|" native/Info.plist > "$bundle/Contents/Info.plist"
  xattr -dr com.apple.quarantine "$bundle" 2>/dev/null || true
  codesign --force --sign - "$bundle"
  printf 'Installed OBS plugin: %s\n' "$2"
}
if [ -f native/prebuilt/offleak.so ]; then
  printf '\nInstalling the OBS plugins...\n'
  install_plugin native/prebuilt/offleak.so offleak
  install_plugin native/prebuilt/offleak-direct.so offleak-direct
elif [ ! -f "$PLUGINS/offleak.plugin/Contents/MacOS/offleak" ] || [ native/offleak-source.c -nt "$PLUGINS/offleak.plugin/Contents/MacOS/offleak" ]; then
  { command -v git && command -v clang; } >/dev/null || fail 'Install Apple Command Line Tools, then run this installer again (xcode-select --install).'
  printf '\nBuilding the OBS source...\n'
  BUILD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/offleak-build.XXXXXX")
  git clone --depth 1 --branch 33.0.1 --filter=blob:none --sparse https://github.com/obsproject/obs-studio.git "$BUILD_DIR/obs-studio"
  git -C "$BUILD_DIR/obs-studio" sparse-checkout set libobs
  git clone --depth 1 https://github.com/simd-everywhere/simde.git "$BUILD_DIR/simde"
  OBS_SDK="$BUILD_DIR/obs-studio" SIMDE_INCLUDE="$BUILD_DIR/simde" sh native/build_source.sh
  rm -r "$BUILD_DIR"
else
  printf '\nOBS plugin is already installed.\n'
fi
.venv/bin/python scripts/install_obs_collection.py
printf '\nInstallation complete. Restart OBS if it was open, then double-click Start Offleak.command.\n'
read -r -p 'Press Return to close. ' _
