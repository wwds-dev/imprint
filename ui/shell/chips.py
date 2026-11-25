"""The spend chip and the status chip (Design S6; ADR 0006, decisions 5, 10).

Their text and state are pure functions of values the window already holds,
so every row of S6's tables is a unit test. A zero is never read as "free":
the unknown form comes from the recorded count of unpriced requests
(``UsageTracker.get_unpriced_requests_today``), never from a €0.00 total.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QToolButton

from ui import theme

FULL, SHORT, COMPACT = "full", "short", "compact"
CHIP_HEIGHT = 32
CHIP_PAD = 12


def format_limit(value: float) -> str:
    """A limit as the fields show it: "€5", "€1.5", never "€5.0"
    (the same rule as ``ui.rail.format_limit``)."""
    text = repr(float(value))
    return "€" + (text[:-2] if text.endswith(".0") else text)


def colour(token: str) -> QColor:
    """A theme token as a QColor; washes are written as css rgba()."""
    value = theme.token(token)
    if value.startswith("rgba("):
        r, g, b, a = (part.strip() for part in value[5:-1].split(","))
        return QColor(int(r), int(g), int(b), round(float(a) * 255))
    return QColor(value)


def _amount(value: float) -> str:
    return f"€{value:.2f}"


def _euros(value: float) -> str:
    """For the accessible name: "1.20 euros"."""
    return f"{value:.2f} euros"


@dataclass(frozen=True)
class SpendText:
    text: str
    tone: str           # "normal", "warning", "danger" or "unknown"
    tooltip: str
    accessible: str


def spend_chip_text(spent: float, limit: float, unpriced: int,
                    form: str = FULL) -> SpendText:
    """The spend chip for today's `spent` euros against the daily `limit`
    (0 or less means no limit), with `unpriced` requests whose price was
    unknown. `form` is S3's collapse: FULL, SHORT (no " today") or COMPACT
    (the amount only; the limit moves to the tooltip)."""
    spent = max(0.0, float(spent or 0.0))
    unpriced = max(0, int(unpriced or 0))
    has_limit = limit is not None and float(limit) > 0
    limit_text = format_limit(limit) if has_limit else ""

    # A known part that rounds to €0.00 is no figure at all next to an
    # unknown one: "€0.00 + unknown" would still read as nothing spent.
    if unpriced and round(spent, 2) == 0:
        amount = "Unknown"
        spoken = "an unknown amount"
    elif unpriced:
        amount = f"{_amount(spent)} + unknown"
        spoken = f"{_euros(spent)}, plus an unknown amount"
    else:
        amount = _amount(spent)
        spoken = _euros(spent)

    if unpriced:
        tone = "unknown"
    elif has_limit and spent >= float(limit):
        tone = "danger"
    elif has_limit and spent >= 0.8 * float(limit):
        tone = "warning"
    else:
        tone = "normal"

    if form == COMPACT:
        text = amount
    elif has_limit:
        text = f"{amount} of {limit_text}" + (" today" if form == FULL else "")
    else:
        text = f"{amount} today · no limit" if form == FULL else \
            f"{amount} · no limit"

    tips = []
    if unpriced:
        noun = "request" if unpriced == 1 else "requests"
        known = _amount(spent)
        tips.append(f"{unpriced} {noun} today had no price, so the real "
                    f"total is more than {known}.")
    if tone == "danger":
        tips.append("Daily limit reached.")
    if form == COMPACT or not tips:
        tips.insert(0, f"Spent today: {amount}"
                    + (f" of {limit_text} (daily limit)." if has_limit
                       else ". No daily limit is set."))

    if has_limit:
        accessible = (f"Spent today: {spoken} of a "
                      f"{format_limit(limit)[1:]} euro limit")
    else:
        accessible = f"Spent today: {spoken}, no daily limit"
    if tone == "danger":
        accessible += ". Daily limit reached"
    return SpendText(text, tone, "\n".join(tips), accessible)


@dataclass(frozen=True)
class StatusState:
    word: str
    dot: str            # a theme token name
    count: int          # waiting model updates; 0 means no badge
    tooltip: str
    accessible: str


def status_state(system_level: str | None, keys_tone: str | None,
                 busy: bool, updates: int) -> StatusState:
    """The worst state wins (S6): machine stressed, a key check failed,
    machine busy, a request running, else ready. `system_level` is the
    System card's summary level ("green", "yellow", "red"); `keys_tone` the
    API-keys card's tone ("warning" when a check failed; "Not configured" is
    normal). `updates` is the number of waiting model updates."""
    if system_level == "red":
        word, dot = "Machine stressed", "DANGER"
    elif keys_tone == "warning":
        word, dot = "Key check failed", "WARNING_DOT"
    elif system_level == "yellow":
        word, dot = "Machine busy", "WARNING_DOT"
    elif busy:
        word, dot = "Working", "INFO"
    else:
        word, dot = "Ready", "ACCENT"
    count = max(0, int(updates or 0))
    accessible = f"Status: {word}."
    if count:
        noun = "update" if count == 1 else "updates"
        accessible += f" {count} model {noun} waiting."
    return StatusState(word, dot, count, accessible, accessible)


class SpendChip(QToolButton):
    """"€1.20 of €5 today"; opens the spend popover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SpendChip")
        self.setFixedHeight(CHIP_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.form = FULL
        self._values = (0.0, 0.0, 0)
        self.state = spend_chip_text(0.0, 0.0, 0)
        self.refresh(0.0, 0.0, 0)

    def refresh(self, spent: float, limit: float, unpriced: int) -> None:
        self._values = (spent, limit, unpriced)
        self._apply()

    def set_form(self, form: str) -> None:
        if form != self.form:
            self.form = form
            self._apply()

    def text_for(self, form: str) -> str:
        return spend_chip_text(*self._values, form=form).text

    def width_for(self, form: str) -> int:
        """The chip's width in `form`, measured with its own font."""
        metrics = QFontMetrics(self.font())
        return metrics.horizontalAdvance(self.text_for(form)) + 2 * CHIP_PAD + 2

    def _apply(self) -> None:
        self.state = spend_chip_text(*self._values, form=self.form)
        self.setText(self.state.text)
        self.setToolTip(self.state.tooltip)
        self.setAccessibleName(self.state.accessible)
        if self.property("tone") != self.state.tone:
            self.setProperty("tone", self.state.tone)
            self.style().unpolish(self)
            self.style().polish(self)
        self.setFixedWidth(self.width_for(self.form))


class StatusChip(QAbstractButton):
    """A dot, the state word and a count badge; opens the status popover.

    Painted, not a row of labels, so the whole chip is one button with one
    accessible name. In compact form only the dot and the badge show; the word
    moves to the tooltip and stays in the accessible name.
    """

    DOT = 8
    GAP = 8
    BADGE_PAD = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusChip")
        self.setFixedHeight(CHIP_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.compact = False
        self._hover = False
        self.state = status_state(None, None, False, 0)
        self.set_state(self.state)

    def set_state(self, state: StatusState) -> None:
        self.state = state
        self.setText(state.word)
        self.setAccessibleName(state.accessible)
        self._tip()
        self.setFixedWidth(self.width_for(self.compact))
        self.update()

    def set_compact(self, compact: bool) -> None:
        if compact != self.compact:
            self.compact = compact
            self._tip()
            self.setFixedWidth(self.width_for(compact))
            self.update()

    def _tip(self) -> None:
        tip = "System, chat routing, API keys and model updates"
        self.setToolTip(f"{self.state.accessible}\n{tip}" if self.compact
                        else tip)

    def _badge_text(self) -> str:
        return str(self.state.count) if self.state.count else ""

    def width_for(self, compact: bool) -> int:
        metrics = QFontMetrics(self.font())
        width = CHIP_PAD * 2 + self.DOT + 2
        if not compact:
            width += self.GAP + metrics.horizontalAdvance(self.state.word)
        badge = self._badge_text()
        if badge:
            width += self.GAP + metrics.horizontalAdvance(badge) + 2 * self.BADGE_PAD
        return width

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(self.width_for(self.compact), CHIP_HEIGHT)

    def enterEvent(self, event):  # noqa: N802 - Qt API
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - Qt API
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = "ELEVATED" if (self._hover or self.isDown()) else "SURFACE"
        painter.setBrush(colour(fill))
        painter.setPen(QPen(colour("BORDER_STRONG"), 1))
        painter.drawRoundedRect(rect, CHIP_HEIGHT / 2, CHIP_HEIGHT / 2)
        if self.hasFocus():
            painter.setPen(QPen(colour("ACCENT"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1),
                                    CHIP_HEIGHT / 2 - 1, CHIP_HEIGHT / 2 - 1)

        x = CHIP_PAD
        middle = self.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour(self.state.dot))
        painter.drawEllipse(QRectF(x, middle - self.DOT / 2, self.DOT, self.DOT))
        x += self.DOT
        metrics = QFontMetrics(self.font())
        painter.setFont(self.font())
        if not self.compact:
            x += self.GAP
            painter.setPen(colour("TEXT_DIM"))
            width = metrics.horizontalAdvance(self.state.word)
            painter.drawText(QRectF(x, 0, width + 2, self.height()),
                             Qt.AlignmentFlag.AlignVCenter, self.state.word)
            x += width
        badge = self._badge_text()
        if badge:
            x += self.GAP
            width = metrics.horizontalAdvance(badge) + 2 * self.BADGE_PAD
            pill = QRectF(x, middle - 9, width, 18)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour("ACCENT_WASH"))
            painter.drawRoundedRect(pill, 9, 9)
            painter.setPen(colour("TEXT"))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, badge)
