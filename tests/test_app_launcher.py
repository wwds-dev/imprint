"""The installed app runs Python inside its own bundle, so it is named Imprint.

macOS names a process after the executable it is running. Both launchers before
this one got that wrong in a way nothing inside the app could repair: the
AppleScript applet blocked for the app's lifetime and was "Not Responding" the
whole time, and the fork-and-exec shim that replaced it made the process
"python" in Activity Monitor, the Dock, Cmd-Tab and Force Quit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "scripts" / "install_app.sh"
LAUNCHER = ROOT / "scripts" / "app_launcher.c"


def test_the_bundle_executable_is_the_interpreter():
    installer = INSTALLER.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert 'CFBundleExecutable -string "${APP_NAME}"' in installer
    assert "-lpython" in installer
    assert "Py_InitializeFromConfig" in launcher
    assert "Py_RunMain" in launcher
    # Handing off to another executable is exactly what renames the process.
    assert re.search(r"\bexec[lv]p?e?\(", launcher) is None
    assert "fork(" not in launcher
    assert "osacompile" not in installer


def test_workers_started_with_sys_executable_come_back_through_the_bundle():
    """The narrator converter runs as `sys.executable -u -m ...`; pointing
    sys.executable at the bundle is what keeps those workers named Imprint."""
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert 'PySys_SetObject("executable"' in launcher


def test_a_running_copy_is_asked_to_quit_never_killed():
    """closeEvent saves the manuscript and stops the worker threads; a signal
    skips all of it."""
    installer = INSTALLER.read_text(encoding="utf-8")
    assert "pkill" not in installer
    assert "terminate" in installer


def test_launcher_source_matches_sentinels_copy():
    """One source, two apps. Skipped when Sentinel is not checked out beside it."""
    other = ROOT.parent / "sentinel" / "scripts" / "app_launcher.c"
    if not other.is_file():
        pytest.skip("sentinel checkout not present")
    assert LAUNCHER.read_bytes() == other.read_bytes()
