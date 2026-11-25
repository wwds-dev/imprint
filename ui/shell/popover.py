"""A ``Qt.Popup`` frame under a chip (Design S6; ADR 0006, decision 4).

Not a ``QMenu``: the spend popover holds text fields, and a menu closes on the
first key that is not navigation. Parented to the window, so ``findChild``
and ``_find_control`` still reach what it holds. It closes on Escape, on a
click outside (``Qt.Popup`` does that) and when the app is deactivated,
because macOS may not close a popup on a click into another window's title
bar (QTBUG-30312). ``closed`` fires on every hide, so the owner can commit
an edit in progress one event-loop turn later.

Known macOS limit (QTBUG-133560): a ``QLineEdit`` inside a popup has no
right-click menu; ⌘C, ⌘V and ⌘A still work.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (QApplication, QFrame, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)


class Popover(QFrame):
    closed = Signal()

    def __init__(self, window: QWidget, title: str, width: int, *,
                 max_height_ratio: float | None = None):
        super().__init__(window, Qt.WindowType.Popup
                         | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("Popover")
        self.setAccessibleName(title)
        self.setFixedWidth(width)
        self._anchor: QWidget | None = None
        self._max_height_ratio = max_height_ratio
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.body = QWidget()
        self.body.setObjectName("PopoverBody")
        self.layout_ = QVBoxLayout(self.body)
        self.layout_.setContentsMargins(16, 16, 16, 16)
        self.layout_.setSpacing(10)
        if max_height_ratio:
            self.scroll = QScrollArea(self)
            self.scroll.setObjectName("PopoverScroll")
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll.setWidget(self.body)
            outer.addWidget(self.scroll)
        else:
            self.scroll = None
            outer.addWidget(self.body)
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._on_app_state)

    def heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("PopoverHeading")
        return label

    # ── opening ─────────────────────────────────────────────────────
    def open_below(self, anchor: QWidget, *, from_keyboard: bool = False
                   ) -> None:
        """Show under `anchor`, right edges aligned; focus the first field
        when opened from the keyboard (S6)."""
        self._anchor = anchor
        self._fit_height()
        self.adjustSize()
        corner = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height() + 6))
        self.move(corner.x() - self.width(), corner.y())
        self.show()
        self.raise_()
        if from_keyboard:
            self.focusNextPrevChild(True)

    def _fit_height(self) -> None:
        if not self._max_height_ratio:
            return
        # The parent, not a stored reference: this object is connected to the
        # application's state signal, which outlives every window.
        window = self.parentWidget() or self
        limit = int(window.height() * self._max_height_ratio)
        # Sections may have just opened or closed: measure the layout as it
        # is now, not as it was last painted.
        self.layout_.invalidate()
        self.layout_.activate()
        hint = self.body.sizeHint().height() + 2
        self.setFixedHeight(min(hint, max(160, limit)))

    def reveal_for_lesson(self) -> None:
        """Help lessons: show without taking focus from the callout."""
        if self.isVisible() or self._anchor is None:
            return
        self.open_below(self._anchor)

    def set_anchor(self, anchor: QWidget) -> None:
        self._anchor = anchor

    # ── closing ─────────────────────────────────────────────────────
    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event):  # noqa: N802 - Qt API
        super().hideEvent(event)
        self.closed.emit()
        anchor = self._anchor
        if anchor is not None and anchor.isVisible():
            anchor.setFocus(Qt.FocusReason.PopupFocusReason)

    def _on_app_state(self, state) -> None:
        if state != Qt.ApplicationState.ApplicationActive and self.isVisible():
            self.hide()
