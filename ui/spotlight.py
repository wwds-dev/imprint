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

from PySide6.QtCore import QElapsedTimer, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget,
    QTabWidget, QVBoxLayout, QWidget,
)

from ui.style import ACCENT, BORDER_STRONG, ELEVATED, TEXT, TEXT_DIM
from ui import theme

RING_PAD = 5
#: How long after it starts a spotlight reopens the popover or drawer that
#: holds its control, if Qt closed it on a window change.
REVEAL_RETRY_MS = 800
CALLOUT_GAP = 10


def reveal(widget: QWidget) -> None:
    """Switch every tab page and stack page above ``widget`` to the one
    holding it, then scroll each enclosing scroll area to it.

    Works outward from the control, so a lesson names only the control and
    never the tab it currently happens to live on. A container that is
    closed until asked — the History drawer, a popover (ADR 0006, decision
    6) — opens first: any ancestor with ``reveal_for_lesson()`` is asked,
    outermost first, before the tabs switch and the scroll areas scroll.
    """
    hosts = []
    ancestor = widget
    while ancestor is not None:
        hook = getattr(ancestor, "reveal_for_lesson", None)
        if callable(hook):
            hosts.append(hook)
        ancestor = ancestor.parentWidget()
    for hook in reversed(hosts):
        hook()
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
                 detail: str = "", on_back: Callable[[], None] | None = None,
                 ring_host: QWidget | None = None):
        super().__init__(window)
        self.window_ = window
        # The ring is drawn in the target's own window: a control inside a
        # popover is in a separate top-level window above the main one.
        self.ring_host = ring_host or window
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

        self.ring = _Ring(self.ring_host)
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
        # A popover or drawer opened for the lesson can be closed by Qt when
        # the active window changes — the Learning Centre closes right after
        # it asks for the ring. For a short while, open it again.
        self._revealing = QElapsedTimer()
        self._revealing.start()
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
        return self._rect_in(self.window_)

    def _rect_in(self, host: QWidget) -> QRect:
        visible = self.target.visibleRegion().boundingRect()
        if visible.isEmpty():
            return QRect()
        if host is self.target.window():
            origin = self.target.mapTo(host, QPoint(0, 0))
        else:
            origin = host.mapFromGlobal(self.target.mapToGlobal(QPoint(0, 0)))
        return visible.translated(origin)

    def follow(self) -> None:
        """Keep the ring on the control and the callout beside it.

        The ring goes when the control is not on screen — another workspace
        was opened — and comes back when it is; the callout stays so the way
        back to the lesson is never lost."""
        revealing = getattr(self, "_revealing", None)
        if (not self.target.isVisible() and revealing is not None
                and revealing.elapsed() < REVEAL_RETRY_MS):
            reveal(self.target)
        target = self.target_rect()
        on_screen = self.target.isVisible() and not target.isEmpty()
        rect = target.adjusted(-RING_PAD, -RING_PAD, RING_PAD, RING_PAD)
        self.ring.setVisible(on_screen)
        if on_screen:
            ring_rect = self._rect_in(self.ring_host).adjusted(
                -RING_PAD, -RING_PAD, RING_PAD, RING_PAD)
            self.ring.setGeometry(ring_rect)
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


def anchor_for(action: QAction) -> QWidget | None:
    """The button that opens the menu holding `action`.

    A lesson cannot ring a menu item: ``QMenu.exec`` is modal and would
    swallow the callout. Actions in the "?" and project menus name their
    opener in the ``lessonAnchor`` property (ADR 0006, decision 6)."""
    name = action.property("lessonAnchor")
    owner = action.parent()
    while name and owner is not None:
        widget = getattr(owner, name, None)
        if isinstance(widget, QWidget):
            return widget
        owner = owner.parent()
    return None


def spotlight(target, title: str, detail: str = "",
              on_back: Callable[[], None] | None = None) -> Spotlight:
    """Bring ``target`` into view and ring it, replacing any earlier ring.

    `target` may be a ``QAction`` in a menu; then its menu's button is ringed
    and the callout says which item to pick. Before ADR 0006 this called
    ``window()`` on the action and raised (the "Show me" crash for
    ``new_project_btn``)."""
    if isinstance(target, QAction):
        anchor = anchor_for(target)
        if anchor is None:
            raise ValueError(f"no lessonAnchor for the action {target.text()!r}")
        item = target.text().split("\t")[0]
        detail = f"In this menu: {item}" + (f" · {detail}" if detail else "")
        target = anchor
    reveal(target)
    ring_host = target.window()
    window = ring_host
    if ring_host.windowFlags() & Qt.WindowType.Popup and ring_host.parentWidget():
        window = ring_host.parentWidget().window()
    previous = getattr(window, "_spotlight", None)
    if previous is not None:
        previous.dismiss()
    marker = Spotlight(window, target, title, detail, on_back,
                       ring_host=ring_host)
    window._spotlight = marker
    # Place it once the tab switches and scrolling have been laid out.
    QTimer.singleShot(0, marker.start)
    return marker
