"""Widgets for the two fixed side rails.

The project rail (left) and the spend rail (right) are narrow and always on
screen, so each widget here does one job in one line: a budget whose limit is
edited in place, a number beside its name, a chat row with its agent, a filter
that is a button until it is opened. Spec: docs/specs/side-rails-redesign.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMenu, QProgressBar,
    QPushButton, QSizePolicy, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from services.runtime_paths import resource_base
from ui import theme
from ui.forms import SM, XS, style_icon_button
from ui.style import ACCENT, ELEVATED, TEXT_DIM, TEXT_MUTE

# What a saved-chat row carries beside its file path (Qt.UserRole).
TITLE_ROLE = Qt.ItemDataRole.UserRole + 1   # the title without its "agent: " prefix
AGENT_ROLE = Qt.ItemDataRole.UserRole + 2   # the agent's label, drawn at the right
DAY_ROLE = Qt.ItemDataRole.UserRole + 3     # "Today", "Yesterday" or "Earlier"

CHAT_STAMP = "%Y-%m-%d_%H-%M-%S"


def _colour(token: str) -> QColor:
    """One of ui.style's colours under the current theme."""
    return QColor(theme.recolour(token))


def _smaller(font: QFont, by: int = 2) -> QFont:
    """`font` a step down. The app sheet sizes text in pixels, and a font
    sized that way reports a point size of -1."""
    small = QFont(font)
    if small.pixelSize() > 0:
        small.setPixelSize(max(10, small.pixelSize() - by))
    else:
        small.setPointSizeF(max(8.0, small.pointSizeF() - by))
    return small


def format_limit(value: float) -> str:
    """A budget as the user would type it: 1, 1.5, 0.25 — never 1.0 or a
    truncated 1 for 1.5.

    Lossless: committing one limit field saves both, so a rounded display of
    the other (1234.567 shown as 1234.57) would quietly become the cap.
    """
    text = repr(float(value))
    return text[:-2] if text.endswith(".0") else text


def chat_when(name: str, data: dict, mtime: float | None = None) -> datetime | None:
    """When a saved chat was written: its own stamp, its file name, its file."""
    for raw in (data.get("timestamp"), name[:19]):
        try:
            return datetime.strptime(str(raw), CHAT_STAMP)
        except (TypeError, ValueError):
            continue
    return datetime.fromtimestamp(mtime) if mtime else None


def day_group(when: datetime | None, today: date) -> str:
    """The heading a chat from `when` is listed under."""
    if when is None:
        return "Earlier"
    age = (today - when.date()).days
    if age <= 0:
        return "Today"
    return "Yesterday" if age == 1 else "Earlier"


class ChatRowDelegate(QStyledItemDelegate):
    """A saved chat: title cut to fit, its agent beside it, a day heading above
    the first row of each day.

    The heading is painted, not inserted as an item, so the list's count stays
    the number of chats and every item is one that can be opened.
    """

    ROW_HEIGHT = 32
    HEADER_HEIGHT = 26
    PADDING = 8

    @staticmethod
    def heading(index) -> str:
        day = index.data(DAY_ROLE)
        if not day:
            return ""
        if index.row() > 0:
            previous = index.sibling(index.row() - 1, index.column())
            if previous.isValid() and previous.data(DAY_ROLE) == day:
                return ""
        return str(day)

    def sizeHint(self, option, index):  # noqa: N802 - Qt API
        header = self.HEADER_HEIGHT if self.heading(index) else 0
        # Width 0: the row takes the list's width and elides, so the list
        # never asks for a horizontal scrollbar.
        return QSize(0, self.ROW_HEIGHT + header)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRect(option.rect)
        heading = self.heading(index)
        if heading:
            head_font = _smaller(option.font)
            head_font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(head_font)
            painter.setPen(_colour(TEXT_MUTE))
            painter.drawText(
                QRect(rect.left() + self.PADDING, rect.top(),
                      rect.width() - self.PADDING, self.HEADER_HEIGHT),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                heading)
            rect.adjust(0, self.HEADER_HEIGHT, 0, 0)

        row = rect.adjusted(0, 1, 0, -1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setPen(Qt.PenStyle.NoPen)
        if selected:
            wash = _colour(ACCENT)
            wash.setAlpha(30)
            painter.setBrush(wash)
            painter.drawRoundedRect(row, 6, 6)
        elif hovered:
            painter.setBrush(_colour(ELEVATED))
            painter.drawRoundedRect(row, 6, 6)

        inner = row.adjusted(self.PADDING, 0, -self.PADDING, 0)
        agent = str(index.data(AGENT_ROLE) or "")
        agent_width = 0
        if agent:
            agent_font = _smaller(option.font)
            painter.setFont(agent_font)
            metrics = QFontMetrics(agent_font)
            # The agent never takes more than two fifths of the row: the title
            # is what tells two chats apart. Two spare pixels, because the
            # advance is rounded down and eliding measures exactly.
            agent_width = min(metrics.horizontalAdvance(agent) + 2,
                              inner.width() * 2 // 5)
            painter.setPen(_colour(TEXT_MUTE))
            painter.drawText(
                QRect(inner.right() - agent_width + 1, inner.top(),
                      agent_width, inner.height()),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                metrics.elidedText(agent, Qt.TextElideMode.ElideRight, agent_width))
            agent_width += SM

        font = QFont(option.font)
        if selected:
            font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(_colour(ACCENT if selected else TEXT_DIM))
        title = str(index.data(TITLE_ROLE)
                    or index.data(Qt.ItemDataRole.DisplayRole) or "")
        title_rect = inner.adjusted(0, 0, -agent_width, 0)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(font).elidedText(
                title, Qt.TextElideMode.ElideRight, title_rect.width()))
        painter.restore()


class ChatList(QListWidget):
    """The saved-chat list. A day heading is painted inside the first row of
    its day, so a click on the heading would open (and a double-click rename)
    the chat under it; the list swallows those."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(ChatRowDelegate(self))
        self.setMouseTracking(True)
        # Titles elide in the row and are whole in the tooltip; a sideways
        # scrollbar under a 184px list helps nobody.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)

    def on_heading(self, pos: QPoint) -> bool:
        index = self.indexAt(pos)
        if not index.isValid() or not ChatRowDelegate.heading(index):
            return False
        top = self.visualRect(index).top()
        return pos.y() < top + ChatRowDelegate.HEADER_HEIGHT

    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        if not self.on_heading(event.position().toPoint()):
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        if not self.on_heading(event.position().toPoint()):
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802 - Qt API
        if not self.on_heading(event.position().toPoint()):
            super().mouseDoubleClickEvent(event)


class MenuFilterButton(QPushButton):
    """A one-of-many filter that is an icon until it is opened.

    Speaks the part of QComboBox the chat list uses — currentText,
    setCurrentText, currentTextChanged — so the list code does not care which
    it has. The first option is "everything"; the button is marked while any
    other is chosen, because a filter you cannot see is a list that looks
    broken.
    """

    currentTextChanged = Signal(str)  # noqa: N815 - QComboBox's name

    def __init__(self, everything: str, tooltip: str,
                 label_for: Callable[[str], str] | None = None, parent=None):
        super().__init__(parent)
        self._everything = everything
        self._options = [everything]
        self._current = everything
        self._tooltip = tooltip
        self._label_for = label_for or (lambda option: option)
        style_icon_button(self, "filter", tooltip)
        self.clicked.connect(self._open)
        self._sync()

    def options(self) -> list[str]:
        return list(self._options)

    def set_options(self, options: list[str]) -> None:
        """Replace the choices. Like repopulating a combo with its signals
        blocked: a choice that no longer exists falls back to everything, and
        nothing is emitted."""
        self._options = list(options) or [self._everything]
        if self._current not in self._options:
            self._current = self._everything
        self._sync()

    def currentText(self) -> str:  # noqa: N802 - QComboBox's name
        return self._current

    def setCurrentText(self, text: str) -> None:  # noqa: N802 - QComboBox's name
        if text not in self._options or text == self._current:
            return
        self._current = text
        self._sync()
        self.currentTextChanged.emit(text)

    def label(self, option: str) -> str:
        return option if option == self._everything else self._label_for(option)

    def _sync(self) -> None:
        active = self._current != self._everything
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setToolTip(f"{self._tooltip}\nShowing: {self.label(self._current)}"
                        if active else self._tooltip)

    def build_menu(self) -> QMenu:
        menu = QMenu(self)
        for option in self._options:
            action = menu.addAction(self.label(option))
            action.setCheckable(True)
            action.setChecked(option == self._current)
            action.setData(option)
        return menu

    def _open(self) -> None:
        menu = self.build_menu()
        chosen = menu.exec(self.mapToGlobal(QPoint(0, self.height() + 2)))
        if chosen is not None:
            self.setCurrentText(chosen.data())


class BudgetRow(QWidget):
    """Spend against a cap, with the cap as the field that sets it.

    The rail used to show each budget twice: a bar reading "€0.00 / €1.00",
    then the same €1.00 again as an input with a Save button under both. Here
    the number after "of" is the input. `set()` never writes to it, so a
    refresh cannot overwrite a limit that is being typed.
    """

    def __init__(self, label: str, limit_text: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Transparent")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(XS + 1)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(XS + 2)
        name = QLabel(label)
        name.setObjectName("RailRowName")
        top.addWidget(name)
        top.addStretch()
        self.value_label = QLabel("€0.00")
        self.value_label.setObjectName("RailRowValue")
        top.addWidget(self.value_label)
        of = QLabel("of €")
        of.setObjectName("RailRowNote")
        top.addWidget(of)
        self.limit_input = QLineEdit(limit_text)
        self.limit_input.setObjectName("RailLimit")
        self.limit_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.limit_input.setFixedWidth(56)
        self.limit_input.setAccessibleName(f"{label} limit in euros")
        top.addWidget(self.limit_input)
        layout.addLayout(top)

        self.bar = QProgressBar()
        self.bar.setObjectName("BudgetBar")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)

    def set(self, used: float, cap: float, unknown: int = 0) -> None:
        """`unknown` counts requests in this total that had no price: the
        figure then says so instead of reading as the whole spend (a zero
        price means unknown, never free)."""
        if unknown and round(used, 2) == 0:
            self.value_label.setText("Unknown")
        elif unknown:
            self.value_label.setText(f"€{used:.2f} + unknown")
        else:
            self.value_label.setText(f"€{used:.2f}")
        if unknown:
            noun = "request" if unknown == 1 else "requests"
            self.value_label.setToolTip(
                f"{unknown} {noun} had no price, so "
                + ("what was spent is unknown." if round(used, 2) == 0 else
                   f"the real total is more than €{used:.2f}."))
        else:
            self.value_label.setToolTip("")
        # A zero cap is "no limit", not "fully spent" — showing a full bar there
        # would read as blocked when nothing is.
        percent = 0 if cap <= 0 else min(100, int(round(used / cap * 100)))
        self.bar.setValue(percent)
        self.bar.setProperty("over", percent >= 100)
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)


class KeyValueRow(QWidget):
    """A name and its number on one line. StatBlock's surface (set_value,
    set_caption, value_label, caption_label) at a third of its height."""

    def __init__(self, caption: str, value: str = "—", parent=None):
        super().__init__(parent)
        self.setObjectName("Transparent")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SM)
        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("RailRowName")
        layout.addWidget(self.caption_label)
        layout.addStretch()
        self.value_label = QLabel(value)
        self.value_label.setObjectName("RailRowValue")
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_caption(self, caption: str) -> None:
        self.caption_label.setText(caption)


class IconMark(QWidget):
    """An SVG from assets/ drawn at a fixed size; clicks pass through."""

    def __init__(self, icon_name: str, size: int = 14, parent=None):
        super().__init__(parent)
        self._icon = QIcon(str(resource_base() / "assets" / f"{icon_name}.svg"))
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        self._icon.paint(painter, self.rect())
        painter.end()


def nav_row(text: str) -> QPushButton:
    """A full-width row that opens a window: its name, and a chevron saying so."""
    button = QPushButton(text)
    button.setObjectName("RailNav")
    button.setFixedHeight(34)
    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    layout = QHBoxLayout(button)
    layout.setContentsMargins(0, 0, XS, 0)
    layout.addStretch()
    layout.addWidget(IconMark("chevron-right"))
    return button
