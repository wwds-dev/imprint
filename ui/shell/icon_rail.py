"""The 72 px icon rail (Design S2; ADR 0006, decision 3).

``WorkspaceRail`` is the window's ``workspace_tabs``: it implements the part
of ``QTabBar``'s API the app, the tests and the help lessons use — ``count``,
``tabText``, ``currentIndex``, ``setCurrentIndex``, ``currentChanged`` (only
on a change), ``elideMode``, ``isTabVisible``, ``setTabToolTip`` and
``tabToolTip`` — over one checkable button per workspace. A hidden QTabBar
was rejected: lessons ring ``workspace_tabs`` and a hidden widget has no
geometry to ring.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QFrame, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)

from ui import theme
from ui.style import ASSETS_DIR

RAIL_WIDTH = 72
BUTTON = 44
ICON = 20
MARK = 36
PAD = 16

_svg_cache: dict[str, str] = {}


def _pixmaps(name: str, colour: str, size: int) -> list[QPixmap]:
    from PySide6.QtSvg import QSvgRenderer
    if name not in _svg_cache:
        _svg_cache[name] = (ASSETS_DIR / "shell" / f"{name}.svg").read_text(
            encoding="utf-8")
    svg = _svg_cache[name].replace("currentColor", colour)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    out = []
    for scale in (1, 2):
        pixmap = QPixmap(size * scale, size * scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        out.append(pixmap)
    return out


def shell_icon(name: str, colour: str, size: int = ICON) -> QIcon:
    """One of assets/shell/*.svg drawn in `colour` (the files use
    ``currentColor``), sharp on a Retina screen."""
    icon = QIcon()
    for pixmap in _pixmaps(name, colour, size):
        icon.addPixmap(pixmap)
    return icon


def _two_state_icon(name: str) -> QIcon:
    """TEXT_DIM at rest, TEXT when checked (S2)."""
    icon = QIcon()
    for colour, state in ((theme.token("TEXT_DIM"), QIcon.State.Off),
                          (theme.token("TEXT"), QIcon.State.On)):
        for pixmap in _pixmaps(name, colour, ICON):
            icon.addPixmap(pixmap, QIcon.Mode.Normal, state)
    return icon


class AppMark(QWidget):
    """The "i" mark: the version on its tooltip, an amber dot when stale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AppMark")
        self.setFixedSize(MARK, MARK)
        # Not a button, but VoiceOver reaches it and reads the version.
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.stale = False

    def set_version(self, tooltip: str, stale: bool) -> None:
        self.stale = bool(stale)
        if self.stale:
            tooltip = (f"{tooltip}\nThis build is older than the code: "
                       "rebuild to update")
        self.setToolTip(tooltip)
        self.setAccessibleName("Imprint" + (" (stale build)" if stale else ""))
        self.setAccessibleDescription(tooltip)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.token("TEXT")))
        painter.drawRoundedRect(QRectF(0, 0, MARK, MARK), 10, 10)
        font = painter.font()
        font.setPixelSize(19)
        font.setWeight(font.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(theme.token("SURFACE")))
        painter.drawText(QRectF(0, 0, MARK, MARK - 1),
                         Qt.AlignmentFlag.AlignCenter, "i")
        if self.stale:
            centre = QPointF(MARK - 4, 4)
            painter.setPen(QPen(QColor(theme.token("SURFACE")), 2))
            painter.setBrush(QColor(theme.token("WARNING_DOT")))
            painter.drawEllipse(centre, 5, 5)
        if self.hasFocus():
            painter.setPen(QPen(QColor(theme.token("ACCENT")), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(1, 1, MARK - 2, MARK - 2), 10, 10)


class RailButton(QToolButton):
    """A 44 px square with one 20 px icon."""

    def __init__(self, icon_name: str, name: str, parent=None, *,
                 checkable: bool = False):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setObjectName("RailButton")
        self.setFixedSize(BUTTON, BUTTON)
        self.setIconSize(QSize(ICON, ICON))
        self.setCheckable(checkable)
        self.setAccessibleName(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.restyle()

    def restyle(self) -> None:
        self.setIcon(_two_state_icon(self.icon_name))


class WorkspaceRail(QFrame):
    """The icon rail, and the window's ``workspace_tabs``."""

    currentChanged = Signal(int)

    def __init__(self, workspaces: list[tuple[str, str]], parent=None):
        """`workspaces`: (name, icon) pairs in rail order."""
        super().__init__(parent)
        self.setObjectName("IconRail")
        self.setFixedWidth(RAIL_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Expanding)
        self._names = [name for name, _icon in workspaces]
        self._descriptions = [""] * len(self._names)
        self._tooltips = [""] * len(self._names)
        self._current = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins((RAIL_WIDTH - BUTTON) // 2, PAD,
                                  (RAIL_WIDTH - BUTTON) // 2, PAD)
        layout.setSpacing(4)
        self.app_mark = AppMark(self)
        layout.addWidget(self.app_mark, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10 - 4)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[RailButton] = []
        for index, (name, icon) in enumerate(workspaces):
            button = RailButton(icon, name, self, checkable=True)
            self.group.addButton(button, index)
            self.buttons.append(button)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
            self._refresh_tooltip(index)
        self.group.idClicked.connect(self.setCurrentIndex)

        layout.addStretch(1)
        self.help_btn = RailButton("help", "Help", self)
        self.help_btn.setToolTip("Help and documentation (⌘?)")
        layout.addWidget(self.help_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8 - 4)
        self.settings_btn = RailButton("settings", "Settings", self)
        self.settings_btn.setToolTip("Settings (⌘,)")
        layout.addWidget(self.settings_btn, 0, Qt.AlignmentFlag.AlignHCenter)

    # ── the QTabBar subset ──────────────────────────────────────────
    def count(self) -> int:
        return len(self._names)

    def tabText(self, index: int) -> str:  # noqa: N802 - QTabBar API
        return self._names[index] if 0 <= index < len(self._names) else ""

    def currentIndex(self) -> int:  # noqa: N802 - QTabBar API
        return self._current

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802 - QTabBar API
        if not 0 <= index < len(self._names):
            return
        self.buttons[index].setChecked(True)
        for i, button in enumerate(self.buttons):
            button.setProperty("selected", i == index)
            button.setAccessibleDescription(
                self._descriptions[i] + (" (selected)" if i == index else ""))
        if index == self._current:
            return
        self._current = index
        self.update()
        self.currentChanged.emit(index)

    def elideMode(self):  # noqa: N802 - QTabBar API
        return Qt.TextElideMode.ElideNone

    def isTabVisible(self, index: int) -> bool:  # noqa: N802 - QTabBar API
        return 0 <= index < len(self._names)

    def setTabToolTip(self, index: int, text: str) -> None:  # noqa: N802
        self._tooltips[index] = text
        self.buttons[index].setToolTip(text)

    def tabToolTip(self, index: int) -> str:  # noqa: N802 - QTabBar API
        return self._tooltips[index]

    def tabRect(self, index: int):  # noqa: N802 - QTabBar API
        return self.buttons[index].geometry()

    # ── descriptions (the old strip's text) ─────────────────────────
    def set_description(self, index: int, text: str) -> None:
        self._descriptions[index] = text
        self._refresh_tooltip(index)

    def description(self, index: int) -> str:
        return self._descriptions[index]

    def _refresh_tooltip(self, index: int) -> None:
        name = self._names[index]
        text = self._descriptions[index]
        self.setTabToolTip(index, f"{name}\n{text}" if text else name)
        self.buttons[index].setAccessibleName(name)
        self.buttons[index].setAccessibleDescription(text)

    # ── look ────────────────────────────────────────────────────────
    def restyle(self) -> None:
        """Redraw the icons in the current theme's colours."""
        for button in (*self.buttons, self.help_btn, self.settings_btn):
            button.restyle()
        self.app_mark.update()
        self.update()

    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        """Up and Down move between the rail's buttons (S9)."""
        order = [self.app_mark, *self.buttons, self.help_btn, self.settings_btn]
        step = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}.get(event.key())
        focus = self.focusWidget()
        if step is not None and focus in order:
            order[(order.index(focus) + step) % len(order)].setFocus()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        super().paintEvent(event)
        if not 0 <= self._current < len(self.buttons):
            return
        # The 3 × 20 px accent bar against the rail's left edge: this, not the
        # fill, is what meets 3:1 (S2).
        button = self.buttons[self._current]
        centre = button.geometry().center().y()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.token("ACCENT")))
        painter.drawRoundedRect(QRectF(0, centre - 10, 3, 20), 1.5, 1.5)
