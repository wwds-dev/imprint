"""Point at one real control in the main window: "Show me" from a lesson.

A screenshot of a control goes stale the week the layout changes; the control
itself cannot. A lesson step names the control, and this module brings it
into view — agent selected, every tab and stack above it switched to the page
that holds it, its scroll area scrolled — then rings it and puts a callout
beside it with the step's title and a way back to the lesson.

The ring ignores the mouse, so the control underneath stays clickable: the
point is to do the step, not to look at it.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget,
    QTabWidget, QVBoxLayout, QWidget,
)

from ui.style import ACCENT, BORDER_STRONG, ELEVATED, TEXT, TEXT_DIM
from ui import theme

RING_PAD = 5
CALLOUT_GAP = 10


def reveal(widget: QWidget) -> None:
    """Switch every tab page and stack page above ``widget`` to the one
    holding it, then scroll each enclosing scroll area to it.

    Works outward from the control, so a lesson names only the control and
    never the tab it currently happens to live on.
    """
    child, parent = widget, widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QStackedWidget) and parent.indexOf(child) >= 0:
            # A tab widget's pages sit in its own private stack; switch the
            # tab widget so its tab bar follows.
            tabs = parent.parentWidget()
            if isinstance(tabs, QTabWidget) and tabs.indexOf(child) >= 0:
                tabs.setCurrentWidget(child)
            else:
                parent.setCurrentWidget(child)
        child, parent = parent, parent.parentWidget()
    # Scroll only after the pages switched: a hidden page has no geometry.
    ancestor = widget.parentWidget()
    while ancestor is not None:
        if isinstance(ancestor, QScrollArea):
            ancestor.ensureWidgetVisible(widget, 40, 40)
        ancestor = ancestor.parentWidget()


class _Ring(QWidget):
    """A rounded accent outline drawn over the window, transparent to clicks."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.pulse = 0

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(theme.accent())
        # A slow breath rather than a blink: noticeable, never frantic.
        color.setAlpha(255 if self.pulse % 2 == 0 else 150)
        painter.setPen(QPen(color, 3))
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)


class Spotlight(QFrame):
    """Ring one control and explain it; one at a time per window."""

    def __init__(self, window: QWidget, target: QWidget, title: str,
                 detail: str = "", on_back: Callable[[], None] | None = None):
        super().__init__(window)
        self.window_ = window
        self.target = target
        self.on_back = on_back
        self.setObjectName("Spotlight")
        self.setMaximumWidth(340)
        theme.themed(self, f"""
            QFrame#Spotlight {{ background: {ELEVATED};
                border: 1px solid {ACCENT}; border-radius: 10px; }}
            QLabel#SpotlightEyebrow {{ color: {ACCENT}; font-size: 10px;
                font-weight: 700; letter-spacing: 1px; }}
            QLabel#SpotlightTitle {{ color: {TEXT}; font-size: 13px; font-weight: 650; }}
            QLabel#SpotlightDetail {{ color: {TEXT_DIM}; font-size: 12px; }}
            QPushButton {{ padding: 5px 10px; }}
            QPushButton#SpotlightClose {{ border: 1px solid {BORDER_STRONG}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(5)
        eyebrow = QLabel("SHOW ME")
        eyebrow.setObjectName("SpotlightEyebrow")
        layout.addWidget(eyebrow)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SpotlightTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        if detail:
            self.detail_label = QLabel(detail)
            self.detail_label.setObjectName("SpotlightDetail")
            self.detail_label.setWordWrap(True)
            layout.addWidget(self.detail_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.back_btn = QPushButton("Back to lesson")
        self.back_btn.setVisible(on_back is not None)
        self.back_btn.clicked.connect(self._back)
        self.close_btn = QPushButton("Got it")
        self.close_btn.setObjectName("SpotlightClose")
        self.close_btn.clicked.connect(self.dismiss)
        buttons.addWidget(self.back_btn)
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.ring = _Ring(window)
        # Follow the control rather than hook every ancestor's move: scroll
        # areas move the content, not the control, and a timer sees both.
        self.timer = QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.follow)
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(600)
        self.pulse_timer.timeout.connect(self._pulse)
        target.destroyed.connect(self.dismiss)

    def start(self) -> None:
        self.follow()
        self.timer.start()
        self.pulse_timer.start()

    def _pulse(self) -> None:
        self.ring.pulse += 1
        self.ring.update()

    def target_rect(self) -> QRect:
        """The part of the control actually on screen, in window coordinates.

        Its visible region, not its size: a control half inside a scroll
        area would otherwise get a ring running out over the next panel."""
        visible = self.target.visibleRegion().boundingRect()
        if visible.isEmpty():
            return QRect()
        return visible.translated(self.target.mapTo(self.window_, QPoint(0, 0)))

    def follow(self) -> None:
        """Keep the ring on the control and the callout beside it.

        The ring goes when the control is not on screen — another workspace
        was opened — and comes back when it is; the callout stays so the way
        back to the lesson is never lost."""
        target = self.target_rect()
        on_screen = self.target.isVisible() and not target.isEmpty()
        rect = target.adjusted(-RING_PAD, -RING_PAD, RING_PAD, RING_PAD)
        self.ring.setVisible(on_screen)
        if on_screen:
            self.ring.setGeometry(rect)
            self.ring.raise_()
        self.adjustSize()
        size = self.sizeHint()
        bounds = self.window_.rect().adjusted(8, 8, -8, -8)
        below = rect.bottom() + CALLOUT_GAP
        if on_screen and below + size.height() <= bounds.bottom():
            y = below
        elif on_screen and rect.top() - CALLOUT_GAP - size.height() >= bounds.top():
            y = rect.top() - CALLOUT_GAP - size.height()
        else:
            y = bounds.bottom() - size.height()
        x = rect.left() if on_screen else bounds.right() - size.width()
        x = max(bounds.left(), min(x, bounds.right() - size.width()))
        self.setGeometry(x, y, size.width(), size.height())
        self.show()
        self.raise_()

    def _back(self) -> None:
        callback = self.on_back
        self.dismiss()
        if callback is not None:
            # After this event returns: the lesson opens modally.
            QTimer.singleShot(0, callback)

    def dismiss(self, *_args) -> None:
        self.timer.stop()
        self.pulse_timer.stop()
        self.ring.hide()
        self.ring.deleteLater()
        self.hide()
        self.deleteLater()
        if getattr(self.window_, "_spotlight", None) is self:
            self.window_._spotlight = None


def spotlight(target: QWidget, title: str, detail: str = "",
              on_back: Callable[[], None] | None = None) -> Spotlight:
    """Bring ``target`` into view and ring it, replacing any earlier ring."""
    window = target.window()
    previous = getattr(window, "_spotlight", None)
    if previous is not None:
        previous.dismiss()
    reveal(target)
    marker = Spotlight(window, target, title, detail, on_back)
    window._spotlight = marker
    # Place it once the tab switches and scrolling have been laid out.
    QTimer.singleShot(0, marker.start)
    return marker
