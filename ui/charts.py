"""One small chart widget for every workspace that outgrew monospace text.

A horizontal bar chart drawn with QPainter — no charting dependency, the
house palette, and honest emptiness: no data renders as a sentence, not an
empty axis pretending to be a chart. Horizontal bars on purpose: every
panel that needs this is a narrow column, and horizontal bars keep labels
readable at any width.

Values are whatever the caller measures (euros, units, clicks); the
caller supplies the format. A second series renders as a thinner bar
under the first — enough for "reach vs clicks" without inventing a
plotting library.
"""

import re

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui.style import ACCENT_LINE, BORDER, SUNKEN, TEXT, TEXT_MUTE


def _qcolor(css: str) -> QColor:
    """The stylesheet constants include CSS rgba() strings, which QColor
    does not parse — convert those; pass hex/names through."""
    match = re.fullmatch(
        r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)",
        css.strip())
    if match:
        r, g, b, a = match.groups()
        return QColor(int(r), int(g), int(b), round(float(a) * 255))
    return QColor(css)


_ROW_HEIGHT = 26
_SECOND_SERIES = _qcolor(TEXT_MUTE)


class BarChart(QWidget):
    """Labelled horizontal bars; optionally a second, thinner series."""

    def __init__(self, *, empty_text: str = "No data yet.", parent=None):
        super().__init__(parent)
        self._labels: list[str] = []
        self._series: list[tuple[str, list[float]]] = []
        self._value_format = "{:,.2f}"
        self._empty_text = empty_text
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(_ROW_HEIGHT * 3)

    def set_data(self, labels: list[str], values: list[float], *,
                 series_name: str = "", second: list[float] | None = None,
                 second_name: str = "", value_format: str = "{:,.2f}") -> None:
        assert len(labels) == len(values), "labels and values must align"
        if second is not None:
            assert len(second) == len(values), "second series must align"
        self._labels = list(labels)
        self._series = [(series_name, list(values))]
        if second is not None:
            self._series.append((second_name, list(second)))
        self._value_format = value_format
        rows = max(1, len(labels))
        per_row = _ROW_HEIGHT * (2 if second is not None else 1)
        self.setMinimumHeight(max(_ROW_HEIGHT * 3, rows * per_row + 24))
        self.update()

    def clear(self) -> None:
        self._labels = []
        self._series = []
        self.update()

    # ── painting ─────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), _qcolor(SUNKEN))
        if not self._labels or not self._series:
            painter.setPen(_qcolor(TEXT_MUTE))
            painter.drawText(self.rect(), Qt.AlignCenter, self._empty_text)
            painter.end()
            return

        metrics = QFontMetrics(self.font())
        label_width = min(
            max((metrics.horizontalAdvance(label) for label in self._labels),
                default=0) + 12,
            int(self.width() * 0.4))
        peak = max((abs(v) for _name, values in self._series
                    for v in values), default=0.0) or 1.0
        bar_left = label_width + 8
        bar_span = max(10, self.width() - bar_left - 90)
        per_row = _ROW_HEIGHT * len(self._series)

        for index, label in enumerate(self._labels):
            top = 8 + index * per_row
            painter.setPen(_qcolor(TEXT))
            painter.drawText(
                QRectF(4, top, label_width, _ROW_HEIGHT),
                Qt.AlignVCenter | Qt.AlignLeft,
                metrics.elidedText(label, Qt.ElideRight, label_width))
            for series_index, (_name, values) in enumerate(self._series):
                value = values[index]
                bar_height = 14 if series_index == 0 else 8
                bar_top = (top + series_index * _ROW_HEIGHT
                           + (_ROW_HEIGHT - bar_height) / 2)
                width = bar_span * (abs(value) / peak)
                color = (_qcolor(ACCENT_LINE) if series_index == 0
                         else _SECOND_SERIES)
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawRoundedRect(
                    QRectF(bar_left, bar_top, width, bar_height), 3, 3)
                painter.setPen(_qcolor(TEXT_MUTE))
                painter.drawText(
                    QRectF(bar_left + width + 6,
                           top + series_index * _ROW_HEIGHT,
                           84, _ROW_HEIGHT),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    self._value_format.format(value))
        painter.setPen(_qcolor(BORDER))
        painter.drawLine(bar_left - 4, 4, bar_left - 4, self.height() - 4)
        painter.end()

    # ── introspection for tests (painting is not assertable offscreen) ──
    @property
    def row_count(self) -> int:
        return len(self._labels)

    @property
    def series_names(self) -> list[str]:
        return [name for name, _values in self._series]

    def value_at(self, label: str, series: int = 0) -> float | None:
        if label not in self._labels:
            return None
        return self._series[series][1][self._labels.index(label)]
