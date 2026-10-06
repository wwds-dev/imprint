"""The menu bar item, and the three ways it can be present but useless.

A status item fails quietly. The icon can load as a non-template image and
disappear into a dark menu bar; the glyph can be left out of the bundle, so it
is there in the checkout and gone in the .app. Neither shows up in a run from
source, which is why both are asserted here rather than left to be noticed.

The third is not quiet at all: unguarded on macOS 27, the click that opens the
menu aborts the process. `tests/test_appkit_guard.py` covers the guard itself;
what is checked here is that Imprint installs it, and installs it first.
"""

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def menu_bar_item(app):
    # A real Tray, not a fake: constructing QSystemTrayIcon is fine offscreen.
    # Only *showing* it needs a menu bar, and nothing here shows it.
    from ui.tray import Tray
    return Tray()


def test_the_menu_offers_open_and_quit(menu_bar_item):
    labels = [a.text() for a in menu_bar_item._menu.actions() if a.text()]

    assert labels == ["Open Imprint", "Quit Imprint"]


def test_the_menu_is_held_on_the_instance(menu_bar_item):
    """A QMenu referenced only by the tray icon is garbage collected out from
    under it, and the menu opens empty."""
    assert menu_bar_item.icon.contextMenu() is menu_bar_item._menu


def test_the_glyph_is_a_template_image(menu_bar_item):
    """Without the mask flag macOS leaves it black, and a black glyph on a dark
    menu bar is an invisible one."""
    assert menu_bar_item.icon.icon().isMask()


def test_the_glyph_loaded(menu_bar_item):
    """A missing file still yields a QIcon — an empty one, which shows as a
    gap in the menu bar rather than as an error."""
    assert not menu_bar_item.icon.icon().isNull()


def test_both_glyph_sizes_exist():
    """Qt resolves the Retina file by name from the base one, so the @2x file
    is loaded without ever being referenced in code."""
    from ui.tray import icon_path

    retina = icon_path().with_name("tray@2x.png")
    assert icon_path().exists()
    assert retina.exists()


def test_the_glyph_ships_in_the_bundle():
    """datas in the spec is the only thing that puts an asset in the .app."""
    spec = (PROJECT_ROOT / "Imprint.spec").read_text(encoding="utf-8")

    for name in ("tray.png", "tray@2x.png"):
        assert re.search(rf'\("assets/{re.escape(name)}",\s*"assets"\)', spec), name


def test_quit_does_not_bypass_the_window(app):
    """Quit has to go through the window's close(), because closeEvent is
    where the manuscript is saved and the worker QThreads are cancelled — Qt
    aborts the process if one is destroyed while still running."""
    source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    wiring = source[source.index("menu_bar_item = tray.Tray"):]

    assert "menu_bar_item.quit_requested.connect(window.close)" in wiring
    assert "quit_requested.connect(app.quit" not in source
    assert "quit_requested.connect(QApplication.quit" not in source


def test_the_appkit_guard_is_installed_before_the_item_exists():
    """AGENTS.md states the rule as: grep for `QSystemTrayIcon`, then for
    `appkit_guard` — an app with the first and not the second is the next
    crash. The order matters as much as the presence, because the abort
    happens inside AppKit with nothing of this app's on the stack."""
    source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    entry = source.index('if __name__ == "__main__"')

    installed_at = source.index("appkit_guard.install()", entry)
    built_at = source.index("tray.Tray(window)", entry)

    assert installed_at < built_at
