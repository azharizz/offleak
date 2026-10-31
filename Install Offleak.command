#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
printf '\nOffleak installer for macOS Apple Silicon and OBS 33.0.1\n\n'
fail() { printf '\n%s\n' "$1"; exit 1; }
trap 'status=$?; if [ "$status" -ne 0 ]; then printf "\nInstallation stopped (error %s). Review the message above and run the installer again.\n" "$status"; read -r -p "Press Return to close. " _; fi' EXIT
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || fail 'This installer currently supports Apple Silicon Macs only.'
[ -d /Applications/OBS.app ] || fail 'Install OBS Studio 33.0.1 in /Applications first, then run this installer again.'
OBS_VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' /Applications/OBS.app/Contents/Info.plist)
[ "$OBS_VERSION" = 33.0.1 ] || fail "This prototype is tested with OBS 33.0.1; installed version is $OBS_VERSION."
command -v git >/dev/null || fail 'Install Apple Command Line Tools, then run this installer again (xcode-select --install).'
command -v clang >/dev/null || fail 'Install Apple Command Line Tools, then run this installer again (xcode-select --install).'
if ! command -v python3.11 >/dev/null || ! command -v ffmpeg >/dev/null; then
  command -v brew >/dev/null || fail 'Install Homebrew from https://brew.sh, then run this installer again.'
  command -v python3.11 >/dev/null || brew install python@3.11
  command -v ffmpeg >/dev/null || brew install ffmpeg
fi
if [ ! -x playground/.venv/bin/python ]; then
  printf '\nCreating Python environment...\n'
  python3.11 -m venv playground/.venv
fi
if ! playground/.venv/bin/python -c 'import cv2, Foundation, AppKit, Vision, Quartz, flask, torch, ultralytics, qrdet, lap, scipy; assert hasattr(cv2, "FaceRecognizerSF")' >/dev/null 2>&1; then
  printf '\nInstalling Python dependencies (this may take several minutes)...\n'
  playground/.venv/bin/python -m pip install -r playground/requirements.txt
  playground/.venv/bin/python -m pip install --force-reinstall --no-deps opencv-contrib-python-headless==4.12.0.88
fi
printf '\nChecking detector models...\n'
sh playground/scripts/setup/download_models.sh
if [ ! -f "$HOME/Library/Application Support/obs-studio/plugins/offleak.plugin/Contents/MacOS/offleak" ] || [ playground/obs-plugin/offleak.c -nt "$HOME/Library/Application Support/obs-studio/plugins/offleak.plugin/Contents/MacOS/offleak" ]; then
  printf '\nBuilding the OBS source...\n'
  BUILD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/offleak-build.XXXXXX")
  git clone --depth 1 --branch 33.0.1 --filter=blob:none --sparse https://github.com/obsproject/obs-studio.git "$BUILD_DIR/obs-studio"
  git -C "$BUILD_DIR/obs-studio" sparse-checkout set libobs
  git clone --depth 1 https://github.com/simd-everywhere/simde.git "$BUILD_DIR/simde"
  OBS_SDK="$BUILD_DIR/obs-studio" SIMDE_INCLUDE="$BUILD_DIR/simde" sh playground/obs-plugin/build.sh
  rm -r "$BUILD_DIR"
else
  printf '\nOBS plugin is already installed.\n'
fi
playground/.venv/bin/python playground/scripts/setup/install_obs_collection.py
printf '\nInstallation complete. Restart OBS if it was open, then double-click Start Offleak.command.\n'
read -r -p 'Press Return to close. ' _
