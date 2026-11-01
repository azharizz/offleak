# Shared by the installer builds: paths, version, OBS/SIMDe sources, the app payload and the icon.
APP=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=$(cat "$APP/VERSION")
DIST="$APP/dist"
DEPS="$APP/.build/deps"
mkdir -p "$DIST" "$DEPS"

fetch_obs_sources() {
  [ -d "$DEPS/obs-studio" ] || {
    git clone -q --depth 1 --branch 33.0.1 --filter=blob:none --sparse https://github.com/obsproject/obs-studio.git "$DEPS/obs-studio"
    git -C "$DEPS/obs-studio" sparse-checkout set libobs deps/w32-pthreads
  }
  [ -d "$DEPS/simde" ] || git clone -q --depth 1 https://github.com/simd-everywhere/simde.git "$DEPS/simde"
  export OBS_SDK="$DEPS/obs-studio" SIMDE_INCLUDE="$DEPS/simde"
}

# stage_app <dir>: the app's runtime code and the native sources (AGPL corresponding source ships with every build)
stage_app() {
  rm -rf "$1" && mkdir -p "$1/models"
  rsync -a --exclude __pycache__ --exclude '*.pyc' "$APP/offleak" "$1/"
  rsync -a --exclude prebuilt "$APP/native" "$1/"
  cp "$APP/LICENSE" "$APP/README.md" "$APP/VERSION" "$1/"
  cp "$APP/models/README.md" "$1/models/"
}

make_icon() {  # .build/icon/{logo-512.png,offleak.ico} from the dock logo (headless Chrome + Pillow)
  icon="$APP/.build/icon"
  [ -f "$icon/offleak.ico" ] && return
  mkdir -p "$icon"
  printf '<html><body style="margin:0;background:transparent">%s</body></html>' \
    "$(sed 's/<svg /<svg width="512" height="512" /' "$APP/offleak/dock/static/logo.svg")" > "$icon/logo.html"
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
    --default-background-color=00000000 --window-size=512,512 --screenshot="$icon/logo-512.png" "file://$icon/logo.html" >/dev/null 2>&1
  "$APP/.venv/bin/python" -c "from PIL import Image; Image.open('$icon/logo-512.png').save('$icon/offleak.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])"
}
