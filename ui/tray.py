"""The menu bar item.

## Why Imprint has one at all

The window opens fullscreen (see `main.py`), and a fullscreen window covers the
macOS menu bar — so this item is never on screen while Imprint is frontmost.
That is not a flaw in it, it is the whole point: the item is visible exactly
when something *else* is in front, which is the only moment you need a way back
to a window you cannot see and may not remember leaving open.

## What macOS decides for us

A status item that owns a menu never receives a plain click — macOS opens the
menu instead. So there is no click-to-open behaviour to write; "Open Imprint"
is simply the first item in the menu.

The menu is deliberately two entries long. Everything Imprint does lives in a
workspace inside the window, and a menu that listed the agents would be a
second, worse navigation surface for them.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from services.runtime_paths import APP_NAME, resource_base

ICON_FILE = "tray.png"


def icon_path():
    """The menu bar glyph on disk — project `assets/` in dev, the bundle's when
    frozen. Exposed so the self-test can check it actually shipped."""
    return resource_base() / "assets" / ICON_FILE


def available() -> bool:
    return QSystemTrayIcon.isSystemTrayAvailable()


def _icon() -> QIcon:
    """The glyph, as a template image.

    setIsMask makes macOS recolour it for a light or dark menu bar and for the
    highlighted state. Without it the icon stays black and vanishes into a dark
    menu bar. Qt picks up the @2x file next to it on its own.
    """
    icon = QIcon(str(icon_path()))
    icon.setIsMask(True)
    return icon


class Tray(QObject):
    open_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self.icon = QSystemTrayIcon(_icon(), self)
        self.icon.setToolTip(APP_NAME)

        menu = QMenu()

        open_action = QAction(f"Open {APP_NAME}", menu)
        open_action.triggered.connect(self.open_requested)
        menu.addAction(open_action)

        menu.addSeparator()
        quit_action = QAction(f"Quit {APP_NAME}", menu)
        quit_action.triggered.connect(self.quit_requested)
        menu.addAction(quit_action)

        # Held on the instance: a QMenu that only the tray icon references is
        # garbage collected out from under it, and the menu comes up empty.
        self._menu = menu
        self.icon.setContextMenu(menu)

    def show(self) -> None:
        self.icon.show()

    def hide(self) -> None:
        self.icon.hide()
