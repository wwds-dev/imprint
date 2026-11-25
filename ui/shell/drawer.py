"""The History drawer (Design S7; ADR 0006, decisions 6-7).

A 320 px panel over the left of the content column, full height below the top
bar, with a 12 % scrim over the rest. It overlays and does not reflow the
panel, so nothing being typed moves (D5). It opens with one 160 ms slide
through ``ui.motion`` (none under Reduce Motion), takes focus to the search
field first, keeps Tab inside itself while open, and gives focus back to the
History button when it closes.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget,
                               QToolButton, QVBoxLayout, QWidget)

from ui import motion, theme

DRAWER_WIDTH = 320
SLIDE_MS = 160
SCRIM_ALPHA = 0.12


class Scrim(QWidget):
    """The dimmed content beside the drawer; a click closes the drawer."""

    clicked = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("DrawerScrim")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.progress = 0.0
        self.hide()

    def paintEvent(self, event):  # noqa: N802 - Qt API
        colour = QColor(theme.token("TEXT"))
        colour.setAlphaF(SCRIM_ALPHA * self.progress)
        QPainter(self).fillRect(self.rect(), colour)

    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        self.clicked.emit()


class _FollowHost(QObject):
    def __init__(self, drawer: "HistoryDrawer"):
        super().__init__(drawer)
        self.drawer = drawer

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.drawer.place()
        return False


class HistoryDrawer(QFrame):
    """Chats: New chat, search, agent filter and the saved-chat list."""

    opened = Signal()
    closed = Signal()

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.setObjectName("HistoryDrawer")
        self.setAccessibleName("Chat history")
        self.host = host
        self.opener: QWidget | None = None
        self.progress = 0.0
        self._open = False
        self.list_widget: QListWidget | None = None
        self._slide = None

        self.scrim = Scrim(host)
        self.scrim.clicked.connect(self.close_drawer)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        self.heading_row = QHBoxLayout()
        self.heading_row.setSpacing(8)
        self.heading = QLabel("Chats")
        self.heading.setObjectName("DrawerHeading")
        self.heading_row.addWidget(self.heading)
        self.heading_row.addStretch(1)
        self.close_btn = QToolButton(self)
        self.close_btn.setObjectName("DrawerClose")
        self.close_btn.setText("×")
        self.close_btn.setAccessibleName("Close history")
        self.close_btn.setToolTip("Close history (⌘Y)")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.clicked.connect(self.close_drawer)
        layout.addLayout(self.heading_row)

        self.filter_row = QHBoxLayout()
        self.filter_row.setSpacing(8)
        layout.addLayout(self.filter_row)

        self.empty_label = QLabel("No saved chats yet.")
        self.empty_label.setObjectName("DrawerEmpty")
        self.empty_label.hide()
        self._content = layout

        host.installEventFilter(_FollowHost(self))
        self.hide()

    # ── filling ─────────────────────────────────────────────────────
    def set_contents(self, new_chat: QWidget, search: QWidget,
                     agent_filter: QWidget, chat_list: QListWidget) -> None:
        """Place the window's own controls: heading row (New chat, close),
        search and filter, then the list (S7 order, which is also Tab order)."""
        self.heading_row.addWidget(new_chat)
        self.heading_row.addWidget(self.close_btn)
        self.filter_row.addWidget(search, 1)
        self.filter_row.addWidget(agent_filter)
        self._content.addWidget(self.empty_label)
        self._content.addWidget(chat_list, 1)
        self.list_widget = chat_list
        model = chat_list.model()
        for signal in (model.rowsInserted, model.rowsRemoved,
                       model.modelReset):
            signal.connect(self._sync_empty)
        self._sync_empty()
        self._focus_order = [new_chat, self.close_btn, search, agent_filter,
                             chat_list]

    def _sync_empty(self, *_args) -> None:
        if self.list_widget is not None:
            self.empty_label.setVisible(self.list_widget.count() == 0)

    # ── geometry ────────────────────────────────────────────────────
    def place(self) -> None:
        height = self.host.height()
        x = round(-DRAWER_WIDTH * (1.0 - self.progress))
        self.setGeometry(x, 0, DRAWER_WIDTH, height)
        self.scrim.setGeometry(0, 0, self.host.width(), height)

    def _apply(self, progress) -> None:
        self.progress = float(progress)
        self.scrim.progress = self.progress
        self.place()
        self.scrim.update()

    # ── open and close ──────────────────────────────────────────────
    def is_open(self) -> bool:
        return self._open

    def toggle(self) -> None:
        if self._open:
            self.close_drawer()
        else:
            self.open_drawer()

    def _stop_slide(self) -> None:
        """A slide still running (closing, say) must not finish later and
        undo the opposite move that replaced it."""
        slide, self._slide = self._slide, None
        if slide is not None:
            try:
                slide.stop()
            except RuntimeError:
                pass        # already finished and deleted

    def open_drawer(self, *, animate: bool = True,
                    take_focus: bool = True) -> None:
        if self._open:
            return
        self._stop_slide()
        self._open = True
        self._apply(0.0 if animate else 1.0)
        self.scrim.show()
        self.scrim.raise_()
        self.show()
        self.raise_()
        if take_focus:
            # Focus first, so nothing being typed in the panel is left with
            # focus while the drawer moves (D5).
            search = self._focus_order[2] if hasattr(self, "_focus_order") \
                else None
            (search or self).setFocus(Qt.FocusReason.OtherFocusReason)
        if animate:
            self._slide = motion.animate(self, self.progress, 1.0, SLIDE_MS,
                                         self._apply)
        else:
            self._apply(1.0)
        self.opened.emit()

    def close_drawer(self) -> None:
        if not self._open:
            return
        self._stop_slide()
        self._open = False

        def _hide():
            self._slide = None
            self.hide()
            self.scrim.hide()

        self._slide = motion.animate(self, self.progress, 0.0, SLIDE_MS,
                                     self._apply, on_finished=_hide)
        if self.opener is not None and self.opener.isVisible():
            self.opener.setFocus(Qt.FocusReason.OtherFocusReason)
        self.closed.emit()

    def reveal_for_lesson(self) -> None:
        """Help lessons: open at once, leaving focus to the callout."""
        self.open_drawer(animate=False, take_focus=False)

    def hideEvent(self, event):  # noqa: N802 - Qt API
        super().hideEvent(event)
        if self._open:                  # hidden from outside mid-slide
            self._open = False
            self.progress = 0.0
            self.scrim.hide()

    # ── keyboard ────────────────────────────────────────────────────
    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Escape:
            self.close_drawer()
            return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, forward: bool) -> bool:  # noqa: N802
        """Keep Tab inside the drawer while it is open (S7, S9)."""
        order = [w for w in getattr(self, "_focus_order", [])
                 if w.isVisible() and w.isEnabled()]
        if not self._open or not order:
            return super().focusNextPrevChild(forward)
        from PySide6.QtWidgets import QApplication
        focus = QApplication.focusWidget()
        current = next((i for i, w in enumerate(order)
                        if w is focus or w.isAncestorOf(focus)), -1)
        step = 1 if forward else -1
        order[(current + step) % len(order)].setFocus(
            Qt.FocusReason.TabFocusReason)
        return True
