# Release attempt: audit P1 billing branch (2026-10-22)

Branch foundry/imprint-audit-p1-2026-10-14 at 12604e9. Playbook sre-release last-reviewed 2026-10-14, status current.
Version: VERSION=2, commits=276 -> expected badge v2.276 (not seen: app never started).

Result: BLOCKED. The frozen build crashes at startup.

| Step | Result |
|---|---|
| log release start | pass |
| CI green | not verified (no GitHub access checked) |
| build_app.sh | first run failed: no .venv in this worktree. Re-ran with a temporary symlink to /Users/as/Documents/lab/active/imprint/.venv (PyInstaller 6.22.2); build rc=0, ad-hoc signed, codesign --verify ok, id com.netrunner3000.imprint |
| install | script replaced /Applications/Imprint.app (previous one was the 35 KB live launcher, backed up first) |
| smoke: launch | FAIL. Process exits within seconds. |
| smoke: name/quit/relaunch | not reachable |

Evidence (running /Applications/Imprint.app/Contents/MacOS/Imprint):

    File "main.py", line 1952, in build_ui
    File "main.py", line 782, in get_recommended_setup
    File "agents/recommendation_profiles.py", line 21, in profile_for
    ModuleNotFoundError: No module named 'agents.chat.recommendations'

Cause: `profile_for` loads `agents.<key>.recommendations` with `import_module`, which PyInstaller cannot see.
`Imprint.spec` hiddenimports lacks the agent recommendation modules (e.g. `collect_submodules("agents")`).
The source file agents/chat/recommendations.py exists. Likely every agent's module is missing.

Other findings:
- Bundle Info.plist shows CFBundleShortVersionString 1.0.1, not the derived v2.276.
- No test covers the frozen bundle; the 1826 tests run from source and cannot catch this.
- Signing: ad-hoc only, no notarization.

Rollback: the previous launcher was restored to /Applications/Imprint.app (codesign verify ok). The temporary .venv symlink was removed. dist/Builds.noindex remains (generated). No commit, push or PR.

## Addendum: retry (2026-10-22), result PASS (with gaps listed)

Fixes under test (uncommitted): `collect_submodules` for agents/services in Imprint.spec, plist version derived from VERSION + build stamp, tests/test_spec_hiddenimports.py.

| Step | Result | Evidence |
|---|---|---|
| log release start | pass | log_activity.py |
| backup of current launcher | pass | copied to the session scratchpad `bak/Imprint.app` |
| build (temp symlink .venv, `build_app.sh --no-install` first) | pass | rc=0, PyInstaller 6.22.2 |
| bundle plist | pass | CFBundleShortVersionString=2.276, CFBundleVersion=2.276, CFBundleName=Imprint |
| frozen `--selftest` (build copy) | pass | 16 checks PASS, "all checks passed" |
| hidden imports in archive | pass | PYZ-00.pyz holds agents.{audiobook,author,chat,creator,fiverr,manuscript,music,social,video,webdesign}.recommendations (10 of 10 source files) and agents.recommendation_profiles. warn file has no chat.recommendations entry |
| install (`build_app.sh`) | pass | /Applications/Imprint.app, ad-hoc signed, `codesign --verify --deep --strict` ok, plist 2.276 |
| launch, stays up >15 s | pass | alive at 20 s, 0 Tracebacks in stdout/stderr; the previous ModuleNotFoundError is gone |
| app name | partial | System Events lists the process as "Imprint"; window title not read (osascript has no assistive access) |
| clean quit | pass | AppleScript quit; process gone within 5 s |

Notes:
- profile_for('chat') was proven by archive contents plus a crash-free build_ui (the path that crashed before), not by calling it in the frozen interpreter.
- At launch the app made model-list requests with invalid Anthropic and Gemini keys (401/400, logged as warnings). Free list calls, no generation; the configured keys in Application Support are invalid and need the owner's attention.
- Not run: CI status, UAT manual cases, relaunch with DB intact, one agent action (needs GUI input). Signing: ad-hoc only, no notarization.
- Temporary .venv symlink removed. Nothing committed or pushed. dist/Builds.noindex build copy was removed by the install script.
