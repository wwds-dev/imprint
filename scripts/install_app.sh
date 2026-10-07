#!/usr/bin/env bash
# Install "Imprint.app" into /Applications — a thin launcher that runs the
# project's own main.py through the project's .venv.
#
#   ./scripts/install_app.sh
#
# RUN THIS ONCE. The bundle contains no application code, only a launcher, so
# edits to main.py (or anything else in the project) are live on the next launch
# — no rebuild step. Re-run this only if the icon, the bundle identity, or the
# launcher itself changes, or if the project moves to a different path.
#
# Trade-off vs. the old PyInstaller build: the app now depends on this project
# folder and its .venv staying where they are. Moving or deleting either breaks
# the launcher (it reports the missing path instead of failing silently).
#
# Data lives in the project (data/, config/, .env) exactly as it does when you
# run `python main.py` by hand, so the app and the terminal share one state.
#
# The bundle's executable is scripts/app_launcher.c, compiled here against the
# venv's own libpython: Python runs *inside* Contents/MacOS/Imprint rather than
# being handed off to .venv/bin/python. macOS names a process after the
# executable it runs, so that is the only way Imprint is called Imprint in
# Activity Monitor, the Dock, Cmd-Tab and Force Quit — a launcher that execs the
# venv's python shows "python" in all four, whatever the app does afterwards.
# What came before, and why each went: an AppleScript applet, which blocked in
# `do shell script` for the GUI's lifetime and so was "Not Responding" the whole
# time; then Sentinel's fork-and-exec shim for one day, which was "python".
#
# Because the interpreter is linked, not exec'd, re-run this after the venv is
# rebuilt on a different Python minor version (3.11 -> 3.12). Patch upgrades
# need nothing: the link goes through uv's minor-version directory.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Bake the build number in. This launcher runs the checkout live, so the app
# normally reads git directly — but stamping anyway means the bundle still
# reports a version if the checkout is later moved or its .git is absent.
"${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/scripts/stamp_version.py" 2>/dev/null \
  || python3 "${PROJECT_ROOT}/scripts/stamp_version.py" 2>/dev/null \
  || true
APP_NAME="Imprint"
INSTALLED="/Applications/${APP_NAME}.app"
PY="${PROJECT_ROOT}/.venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "Error: no interpreter at ${PY}" >&2
    echo "Create it first:  uv venv && uv pip install -r requirements.txt" >&2
    exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
APP_DIR="$STAGE/${APP_NAME}.app"

mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

# Link against the base interpreter the venv was made from: `home` in
# pyvenv.cfg is uv's minor-version directory (cpython-3.11-…), which uv moves
# forward on a patch upgrade, so the rpath goes through it rather than through
# the exact patch release libpython names itself after.
PY_HOME="$(sed -n 's/^home = //p' "$PROJECT_ROOT/.venv/pyvenv.cfg")"
PY_LIBDIR="$(dirname "$PY_HOME")/lib"
PY_INCLUDE="$("$PY" -c "import sysconfig; print(sysconfig.get_config_var('INCLUDEPY'))")"
PY_LDVERSION="$("$PY" -c "import sysconfig; print(sysconfig.get_config_var('LDVERSION'))")"
EXE="$APP_DIR/Contents/MacOS/${APP_NAME}"
xcrun clang -std=c11 -Wall -Wextra -Werror \
    -DAPP_NAME="\"${APP_NAME}\"" -DLOG_PATH="\"/tmp/imprint_launch.log\"" \
    -I"$PY_INCLUDE" "$PROJECT_ROOT/scripts/app_launcher.c" \
    -L"$PY_LIBDIR" -lpython"$PY_LDVERSION" -Wl,-rpath,"$PY_LIBDIR" \
    -o "$EXE"
LINKED="$(otool -L "$EXE" | awk '/libpython/ {print $1; exit}')"
install_name_tool -change "$LINKED" "@rpath/libpython${PY_LDVERSION}.dylib" "$EXE"

cp "$PROJECT_ROOT/assets/icon.icns" "$APP_DIR/Contents/Resources/icon.icns"
# The launcher reads the checkout's path from here rather than having it
# compiled in, so app_launcher.c stays identical across the apps that use it.
printf '%s\n' "$PROJECT_ROOT" > "$APP_DIR/Contents/Resources/project_root.txt"

defaults write "$APP_DIR/Contents/Info" CFBundleName -string "${APP_NAME}"
defaults write "$APP_DIR/Contents/Info" CFBundleDisplayName -string "${APP_NAME}"
defaults write "$APP_DIR/Contents/Info" CFBundleIdentifier -string "com.netrunner3000.imprint"
defaults write "$APP_DIR/Contents/Info" CFBundleExecutable -string "${APP_NAME}"
defaults write "$APP_DIR/Contents/Info" CFBundleIconFile -string "icon.icns"
defaults write "$APP_DIR/Contents/Info" CFBundlePackageType -string "APPL"
defaults write "$APP_DIR/Contents/Info" NSHighResolutionCapable -bool true
defaults write "$APP_DIR/Contents/Info" LSUIElement -bool false
plutil -convert xml1 "$APP_DIR/Contents/Info.plist"
printf 'APPL????' > "$APP_DIR/Contents/PkgInfo"

# Quit a running copy so Launch Services picks up the new bundle — asked to
# quit, the way its own Quit does, never killed: closeEvent is where the
# manuscript is saved and the worker threads are stopped, and a SIGTERM skips
# it. Matches this bundle's process, a terminal run of main.py, and an install
# still on an older launcher (whose window belongs to a process named python).
RUNNING="${PROJECT_ROOT}/main.py|${INSTALLED}/Contents/MacOS/"
for pid in $(pgrep -f "$RUNNING" || true); do
    osascript -l JavaScript -e "ObjC.import('AppKit');
        const app = \$.NSRunningApplication.runningApplicationWithProcessIdentifier(${pid});
        app.isNil() ? false : app.terminate" >/dev/null 2>&1 || true
done
for _ in $(seq 1 40); do
    pgrep -f "$RUNNING" >/dev/null || break
    sleep 0.5
done
if pgrep -f "$RUNNING" >/dev/null; then
    echo "Error: ${APP_NAME} did not quit within 20 seconds. Quit it, then re-run." >&2
    exit 1
fi

rm -rf "$INSTALLED"
cp -R "$APP_DIR" "$INSTALLED"
xattr -cr "$INSTALLED" 2>/dev/null || true
codesign --force --deep --sign - "$INSTALLED"

LSREG="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
"$LSREG" -f "$INSTALLED"

echo ""
echo "✓ Installed: ${INSTALLED}"
echo "  Runs live from: ${PROJECT_ROOT}"
echo "  Edit the code, relaunch the app — no rebuild."
echo "  API keys: ${PROJECT_ROOT}/.env"
