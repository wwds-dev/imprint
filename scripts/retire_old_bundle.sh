# Sourced by install_app.sh and build_app.sh; defines retire_old_bundle.
#
# The app was installed as /Applications/Imprint.app until 2026-11-22, when it
# became "Imprint Studio.app" (spec docs/specs/rename-imprint-studio.md, D1-B).
# Left in place, the old bundle would be a second app in Launchpad, Spotlight
# and the Dock. This removes it, and nothing else:
#   * one fixed path, written out in full: no glob, no variable that could be
#     empty or point elsewhere;
#   * only a real directory (not a symlink) whose Info.plist carries this
#     app's bundle id, so an unrelated "Imprint.app" is left alone;
#   * a running copy is asked to quit the way its own Quit does; if it is
#     still running after 20 s, the script stops and deletes nothing.
# User data lives in ~/Library/Application Support/Imprint/ (or the project
# folder for the live launcher) and is never touched here.

retire_old_bundle() {
    local old="/Applications/Imprint.app"
    local running="/Applications/Imprint\\.app/Contents/MacOS/"
    local lsreg="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

    if [ -L "$old" ] || [ ! -d "$old" ]; then
        return 0
    fi
    local bundle_id
    bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' \
        "$old/Contents/Info.plist" 2>/dev/null || true)"
    if [ "$bundle_id" != "com.netrunner3000.imprint" ]; then
        echo "Note: /Applications/Imprint.app is not this app (bundle id '${bundle_id}'); left in place."
        return 0
    fi

    local pid
    for pid in $(pgrep -f "$running" || true); do
        osascript -l JavaScript -e "ObjC.import('AppKit');
            const app = \$.NSRunningApplication.runningApplicationWithProcessIdentifier(${pid});
            app.isNil() ? false : app.terminate" >/dev/null 2>&1 || true
    done
    local _
    for _ in $(seq 1 40); do
        pgrep -f "$running" >/dev/null || break
        sleep 0.5
    done
    if pgrep -f "$running" >/dev/null; then
        echo "Error: the old Imprint.app is still running. Quit it, then re-run." >&2
        return 1
    fi

    "$lsreg" -u "$old" 2>/dev/null || true
    rm -rf -- "/Applications/Imprint.app"
    echo "✓ Removed the old /Applications/Imprint.app (renamed to Imprint Studio)."
}
