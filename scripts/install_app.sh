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
# Built around a small compiled launcher (scripts/thin_launcher.c), the same one
# Sentinel uses. Not a shell-script bundle — an unsigned shell-script
# CFBundleExecutable gets killed silently by Gatekeeper on launch — and no longer
# an AppleScript applet: the applet had to block in `do shell script` for as long
# as the GUI ran, so its main thread never answered the window server and
# Activity Monitor listed Imprint as "Not Responding" for its whole lifetime. The
# launcher forks a detached child that execs python, then exits at once.
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
xcrun clang -std=c11 -Wall -Wextra -Werror \
    "$PROJECT_ROOT/scripts/thin_launcher.c" \
    -o "$APP_DIR/Contents/MacOS/ImprintLauncher"
cp "$PROJECT_ROOT/assets/icon.icns" "$APP_DIR/Contents/Resources/icon.icns"
# The launcher reads the checkout's path from here rather than having it
# compiled in, so the C source stays identical for every install location.
printf '%s\n' "$PROJECT_ROOT" > "$APP_DIR/Contents/Resources/project_root.txt"

defaults write "$APP_DIR/Contents/Info" CFBundleName -string "${APP_NAME}"
defaults write "$APP_DIR/Contents/Info" CFBundleDisplayName -string "${APP_NAME}"
defaults write "$APP_DIR/Contents/Info" CFBundleIdentifier -string "com.netrunner3000.imprint"
defaults write "$APP_DIR/Contents/Info" CFBundleExecutable -string "ImprintLauncher"
defaults write "$APP_DIR/Contents/Info" CFBundleIconFile -string "icon.icns"
defaults write "$APP_DIR/Contents/Info" CFBundlePackageType -string "APPL"
defaults write "$APP_DIR/Contents/Info" NSHighResolutionCapable -bool true
defaults write "$APP_DIR/Contents/Info" LSUIElement -bool false
plutil -convert xml1 "$APP_DIR/Contents/Info.plist"
printf 'APPL????' > "$APP_DIR/Contents/PkgInfo"

# Stop a running copy so Launch Services picks up the new bundle. The new
# launcher has already exited by the time the window is up, so Python is the only
# process to stop — the `applet` line is for an install still on the old
# AppleScript launcher, which blocked for the GUI's lifetime and, left alive,
# made `open Imprint.app` focus the stale process instead of the new bundle.
pkill -f "${PROJECT_ROOT}/main.py" 2>/dev/null || true
pkill -f "${INSTALLED}/Contents/MacOS/applet" 2>/dev/null || true
sleep 1

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
