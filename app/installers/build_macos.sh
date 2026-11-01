#!/bin/sh
# Build dist/Offleak-<version>.dmg (Apple Silicon): app + prebuilt OBS plugins + an "Install Offleak" app.
set -eu
. "$(dirname "$0")/common.sh"
fetch_obs_sources
make_icon
STAGE="$APP/.build/stage-macos"
PAYLOAD="$STAGE/dmg/Offleak"
rm -rf "$STAGE" && mkdir -p "$STAGE/dmg"
stage_app "$PAYLOAD"
# prebuilt plugins: users need no Xcode tools or OBS source checkout
mkdir -p "$PAYLOAD/native/prebuilt"
OFFLEAK_PLUGIN_DIR="$STAGE/offleak.plugin" sh "$APP/native/build_source.sh" >/dev/null
cp "$STAGE/offleak.plugin/Contents/MacOS/offleak" "$PAYLOAD/native/prebuilt/offleak.so"
sh "$APP/native/build_direct_filter.sh" >/dev/null
cp "$APP/.build/direct-filter/offleak-direct.so" "$PAYLOAD/native/prebuilt/offleak-direct.so"
cp -R "$APP/scripts" "$APP/requirements-macos.txt" "$APP/Install Offleak.command" "$APP/Start Offleak.command" \
  "$APP/Start Offleak Direct.command" "$PAYLOAD/"
# "Install Offleak" app: copies the folder to ~/Applications/Offleak and runs the installer in Terminal
osacompile -o "$STAGE/dmg/Install Offleak.app" "$APP/installers/macos/install.applescript"
iconset="$STAGE/offleak.iconset"
mkdir -p "$iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$APP/.build/icon/logo-512.png" --out "$iconset/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2)); [ $d -le 512 ] && sips -z $d $d "$APP/.build/icon/logo-512.png" --out "$iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$iconset" -o "$STAGE/dmg/Install Offleak.app/Contents/Resources/applet.icns"
codesign --force --deep --sign - "$STAGE/dmg/Install Offleak.app"
rm -f "$DIST/Offleak-$VERSION.dmg"
hdiutil create -quiet -volname "Offleak $VERSION" -srcfolder "$STAGE/dmg" -ov -format UDZO "$DIST/Offleak-$VERSION.dmg"
printf 'Built %s\n' "$DIST/Offleak-$VERSION.dmg"
