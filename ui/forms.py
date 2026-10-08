"""Layout primitives — one spacing scale, one form idiom.

The panels were built one at a time over a long period, and it showed: eight
different spacing values (3, 4, 5, 6, 8, 10, 12, 0), eight margin combinations
including asymmetric ones like ``(10, 6, 10, 10)``, and two competing ways to
label a field — 58 label-beside-input rows against 22 group boxes. Nothing was
individually wrong, and the result read as chaotic because no two panels agreed.

This module is the agreement. Building a panel out of these helpers makes the
rules structural rather than something to remember:

* **One scale.** ``XS/SM/MD/LG`` = 4/8/16/24. Any other gap is a bug.
* **One form idiom.** ``field()`` — a small-caps label above its input, both
  flush to the same left edge. Labels then line up down a column instead of
  landing wherever the previous widget happened to end.
* **Sections, not boxes.** ``section()`` and ``rule()`` group without adding a
  border and a title bar for every four fields.
* **One control height**, so a row of mixed inputs and buttons sits on a line.

`form_grid()` is the reason the project bar stops looking ragged: equal
columns, rather than a FlowLayout that wraps to wherever the previous widget
ended — and, when the row is short of width, fewer equal columns rather than
one field squeezed to a single character.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit,
    QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

# The scale. Four numbers; nothing between them.
XS, SM, MD, LG = 4, 8, 16, 24

# One height for every single-line control, so a mixed row sits on one line.
CONTROL_HEIGHT = 32


def micro(text: str) -> QLabel:
    """A field label: small caps, muted, sitting above its input."""
    label = QLabel(text.upper())
    label.setObjectName("MicroLabel")
    return label


def section(text: str) -> QLabel:
    """A readable group heading. Field labels alone use small uppercase text."""
    label = QLabel(text)
    label.setObjectName("SectionLabel")
    label.setAccessibleName(text)
    return label


def rule() -> QFrame:
    """A hairline divider — the other half of grouping without a box."""
    line = QFrame()
    line.setObjectName("CardDivider")
    line.setFrameShape(QFrame.HLine)
    return line


def field(label: str, widget: QWidget, *, stretch_label: bool = False,
          note: QWidget | None = None,
          aside: QWidget | None = None) -> QWidget:
    """The one form idiom: label above input, both flush left.

    Returns a container so the pair can be dropped into any layout and stay
    together — which is what keeps a column of fields aligned when one of them
    wraps or is hidden.

    The container is transparent. A plain QWidget paints the page colour, so
    inside a card every field's label used to sit on a strip of BG — a dark
    band across the Compose card and the spend rail's Limits.

    `note` follows the label: a `field_note` saying what the choice implies
    right now. It used to go in `aside`, which on a field spanning two columns
    left "Ignored while Mode is Local only" hanging past the end of the chips,
    read as belonging to nothing.

    `aside` sits at the far end of the label row: a `link_button` for an
    affordance that belongs to this one field (Model Guide beside Model),
    rather than another button in the row competing with the real actions.
    """
    box = QWidget()
    box.setObjectName("Transparent")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(XS)
    label_widget = micro(label)
    if stretch_label:
        label_widget.setWordWrap(True)
    if note is None and aside is None:
        layout.addWidget(label_widget)
    else:
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(SM)
        head.addWidget(label_widget)
        if note is not None:
            head.addWidget(note)
        head.addStretch()
        if aside is not None:
            head.addWidget(aside)
        layout.addLayout(head)
    layout.addWidget(widget)
    return box


def link_button(text: str) -> QPushButton:
    """A small text affordance for a field's label row.

    Shorter than the micro label beside it, so a field with one is exactly as
    tall as a field without — the controls in a grid row stay on one line.
    """
    button = QPushButton(text)
    button.setObjectName("LinkAction")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return button


# The total height every single-line control lands on (see the "One control
# height, enforced" rule in ui/style.py). CONTROL_HEIGHT above is the content
# box that rule starts from; this is what a row of controls actually measures.
CONTROL_TOTAL_HEIGHT = 44


def icon_button(icon_name: str, tooltip: str) -> QPushButton:
    """A square button that carries an icon instead of a word.

    For a utility that acts on the field beside it (refresh a model list). The
    icon is an SVG from assets/, not a glyph: a text arrow renders at the
    emoji baseline and the label test rejects it. The accessible name is the
    tooltip, so a screen reader still hears what it does.
    """
    from PySide6.QtGui import QIcon
    from services.runtime_paths import resource_base

    button = QPushButton()
    button.setObjectName("IconAction")
    button.setIcon(QIcon(str(resource_base() / "assets" / f"{icon_name}.svg")))
    button.setIconSize(QSize(16, 16))
    button.setFixedSize(CONTROL_TOTAL_HEIGHT, CONTROL_TOTAL_HEIGHT)
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class ToggleChip(QCheckBox):
    """A permission or filter drawn as a chip, still a QCheckBox underneath.

    Kept a QCheckBox so `isChecked`, `stateChanged` and every call site that
    reads one keep working. The reason it exists is the size hint: macOS
    reports a styled checkbox exactly as wide as its glyphs with nothing to
    spare, so any row that places checkboxes at their hint — FlowLayout, an
    HBox with a stretch — clipped the last letters under the next box
    ("OpenA", "DeepSee"). This one measures itself from the font.
    """

    _INDICATOR = 14
    _GAP = 7          # matches `spacing` in the ToggleChip rule
    _PAD_LEFT = 10
    _PAD_RIGHT = 12
    _BORDER = 1

    def __init__(self, text: str, *, paid: bool = False, parent=None):
        super().__init__(text, parent)
        self.setObjectName("ToggleChip")
        # A paid permission turns WARNING when on — the colour the design
        # system reserves for a step that costs money.
        self.setProperty("paid", "true" if paid else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        self.ensurePolished()
        width = (self._PAD_LEFT + self._INDICATOR + self._GAP
                 + self.fontMetrics().horizontalAdvance(self.text())
                 + self._PAD_RIGHT + 2 * self._BORDER)
        base = super().sizeHint()
        return QSize(max(width, base.width()),
                     max(CONTROL_TOTAL_HEIGHT, base.height()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return self.sizeHint()


def toggle_chip(text: str, *, paid: bool = False, checked: bool = False) -> ToggleChip:
    chip = ToggleChip(text, paid=paid)
    chip.setChecked(checked)
    return chip


def field_note(text: str = "") -> QLabel:
    """A quiet note that follows a field's label (via `note`)."""
    label = QLabel(text)
    label.setObjectName("FieldNote")
    return label


# The narrowest a form_grid column may become before the grid folds into more
# rows. Sixteen average characters plus the field's chrome: wide enough for a
# placeholder like "Project title…" or a dropdown's current value.
FIELD_MIN_WIDTH = 136


class FieldGridLayout(QLayout):
    """Equal columns that fold into more rows instead of squeezing a field.

    `form_grid` used to be a QGridLayout with equal stretch. Stretch decides
    how *spare* width is shared; when a row is short of width, Qt takes it
    from whichever widget has the smallest minimum, and a QLineEdit's minimum
    is about one character. The Quill project bar showed "P…" in Title while
    each dropdown beside it kept 177px. This layout never draws a column
    narrower than `min_column_width`: it drops to fewer columns first.

    Column counts stay balanced — six fields fold 6 → 3 → 2 → 1, never into
    a row of five over a lone sixth — so the labels of every row still line
    up under the first row's.
    """

    #: `span` value for a field that takes the whole row at any column count.
    FULL_ROW = 0

    def __init__(self, columns: int = 3, min_column_width: int = FIELD_MIN_WIDTH,
                 parent=None):
        super().__init__(parent)
        self.max_columns = max(1, columns)
        self.min_column_width = min_column_width
        self._items = []
        self._placement: dict[int, tuple[int, bool]] = {}
        self._hspace = MD
        self._vspace = MD
        self.setContentsMargins(0, 0, 0, 0)

    def add_field(self, widget: QWidget, *, span: int = 1,
                  new_row: bool = False) -> None:
        """Add `widget` spanning `span` columns, optionally starting a row.

        For a form whose rows mean something — Tool and Command over Provider,
        Model and Mode — so the second row's columns stay under the first's
        even though the first is one field short. `span` is capped at the
        column count when the grid folds; `FULL_ROW` always takes the row.
        A grid that uses either gives up the balanced fold below, because a
        deliberate row cannot be rebalanced without breaking it.
        """
        self.addWidget(widget)
        self._placement[id(widget)] = (span, new_row)

    # ── QLayout plumbing ────────────────────────────────────────────────
    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def setHorizontalSpacing(self, spacing: int) -> None:
        self._hspace = spacing
        self.invalidate()

    def setVerticalSpacing(self, spacing: int) -> None:
        self._vspace = spacing
        self.invalidate()

    def expandingDirections(self):
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self):
        margins = self.contentsMargins()
        columns = min(self.max_columns, len(self._visible()) or 1)
        width = (columns * self.min_column_width
                 + (columns - 1) * self._hspace
                 + margins.left() + margins.right())
        return QSize(width, self.heightForWidth(width))

    def minimumSize(self):
        # Height as one spread-out row, like FlowLayout's: the real height at
        # any given width comes from heightForWidth, which box layouts ask
        # for. Reporting the one-column height here instead added ~300px to
        # the whole panel's minimum for a fold that only happens when narrow.
        margins = self.contentsMargins()
        width = self.min_column_width + margins.left() + margins.right()
        return QSize(width, self.heightForWidth(self.sizeHint().width()))

    # ── geometry ────────────────────────────────────────────────────────
    def _visible(self):
        return [item for item in self._items
                if item.widget() is None or not item.widget().isHidden()]

    def _placed(self, item) -> tuple[int, bool] | None:
        widget = item.widget()
        return self._placement.get(id(widget)) if widget is not None else None

    def columns_for(self, inner_width: int) -> int:
        """How many columns fit `inner_width`, balanced across the rows."""
        items = self._visible()
        count = len(items)
        if count == 0:
            return 1
        fit = (inner_width + self._hspace) // (self.min_column_width + self._hspace)
        if any(self._placed(item) for item in items):
            return max(1, min(self.max_columns, fit))
        columns = max(1, min(self.max_columns, count, fit))
        rows = -(-count // columns)
        # The fewest columns that still need only that many rows: a row of
        # five over a lone sixth becomes two rows of three.
        while columns > 1 and -(-count // (columns - 1)) == rows:
            columns -= 1
        return columns

    def _rows(self, items, columns: int):
        """Group items into rows of (item, first column, span)."""
        rows, current, column = [], [], 0
        for item in items:
            span, new_row = self._placed(item) or (1, False)
            span = columns if span == self.FULL_ROW else max(1, min(span, columns))
            if current and (new_row or column + span > columns):
                rows.append(current)
                current, column = [], 0
            current.append((item, column, span))
            column += span
        if current:
            rows.append(current)
        return rows

    def _arrange(self, rect: QRect, apply: bool) -> int:
        margins = self.contentsMargins()
        inner = rect.adjusted(margins.left(), margins.top(),
                              -margins.right(), -margins.bottom())
        items = self._visible()
        if not items:
            return margins.top() + margins.bottom()
        columns = self.columns_for(inner.width())
        spare = max(0, inner.width() - (columns - 1) * self._hspace)

        def edge(column: int) -> int:
            # Spread the remainder pixel by pixel so every column edge lands
            # on the same x in every row.
            return inner.x() + (spare * column) // columns + column * self._hspace

        y = inner.y()
        for row in self._rows(items, columns):
            placed = []
            for item, column, span in row:
                x = edge(column)
                width = edge(column + span) - self._hspace - x
                # A field holding a wrapping row (permission chips) is taller
                # when narrow; its size hint is only its one-line height.
                height = (item.heightForWidth(width) if item.hasHeightForWidth()
                          else item.sizeHint().height())
                placed.append((item, x, width, height))
            if apply:
                for item, x, width, height in placed:
                    item.setGeometry(QRect(x, y, width, height))
            y += max(height for *_rest, height in placed) + self._vspace
        return y - self._vspace - rect.y() + margins.bottom()


def form_grid(pairs: list[tuple[str, QWidget]], *,
              columns: int = 3,
              min_column_width: int = FIELD_MIN_WIDTH) -> FieldGridLayout:
    """A grid of `field()`s with equal columns that fold when narrow.

    Equal columns are the point: they are what make the second row's labels
    sit directly under the first row's. `columns` is the most it will use;
    below `columns × min_column_width` it folds into more rows instead of
    narrowing a field until its text no longer fits.
    """
    grid = FieldGridLayout(columns, min_column_width)
    for label, widget in pairs:
        grid.addWidget(field(label, widget))
    return grid


def stack(*widgets, spacing: int = MD, margins: int = 0) -> QVBoxLayout:
    """A vertical layout on the scale. `margins` is applied on all four sides —
    asymmetric margins are most of why panels failed to line up with each
    other."""
    layout = QVBoxLayout()
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(spacing)
    for widget in widgets:
        if widget is None:
            layout.addStretch()
        elif isinstance(widget, QWidget):
            layout.addWidget(widget)
        else:
            layout.addLayout(widget)
    return layout


def row(*widgets, spacing: int = SM) -> QHBoxLayout:
    """A horizontal layout on the scale. `None` inserts a stretch."""
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        if widget is None:
            layout.addStretch()
        elif isinstance(widget, QWidget):
            layout.addWidget(widget)
        else:
            layout.addLayout(widget)
    return layout


def stat(value: str, caption: str) -> QWidget:
    """A number over its unit. Zero spacing between them is deliberate: they
    read as one object rather than two stacked labels."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    number = QLabel(value)
    number.setObjectName("StatValue")
    layout.addWidget(number)
    layout.addWidget(micro(caption))
    return box


def primary(text: str) -> QPushButton:
    """The one filled button on a screen."""
    button = QPushButton(text)
    button.setObjectName("PrimaryAction")
    button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return button


def combo(items: list[str] | tuple[str, ...] = (), current: str = "") -> QComboBox:
    widget = QComboBox()
    if items:
        widget.addItems(list(items))
    if current:
        widget.setCurrentText(current)
    return widget


def line_edit(placeholder: str = "", text: str = "") -> QLineEdit:
    widget = QLineEdit(text)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


# Style for the primitives above. Appended to the global sheet rather than set
# per widget, so a panel never carries its own copy of the type scale.
FORM_STYLES = """
        QLabel#MicroLabel {{
            color: {muted};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.1px;
        }}
        QLabel#SectionLabel {{
            color: {text};
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 0.1px;
        }}
        QLabel#StatValue {{
            color: {text};
            font-size: 20px;
            font-weight: 600;
        }}
        QLineEdit, QComboBox {{ min-height: {height}px; }}
        QPushButton {{ min-height: {height}px; }}
"""


def form_stylesheet(text: str, muted: str) -> str:
    return FORM_STYLES.format(text=text, muted=muted, height=CONTROL_HEIGHT)


# ── Shell primitives ─────────────────────────────────────────────────────────
# The chrome around the panels: one header bar, two fixed rails. Fixed rather
# than a QSplitter because a splitter is allowed to compress a pane past its
# children's minimum widths, and every overlapping-widget bug this app has had
# started that way. Two numbers you cannot drag are worth more than three you
# can.

HEADER_HEIGHT = 56
RAIL_LEFT_WIDTH = 216
RAIL_RIGHT_WIDTH = 244
# A form field wider than this stops being readable, so the centre column caps
# out rather than stretching a text input across a 27" display.
CONTENT_MAX_WIDTH = 1080


def nav_tab(text: str) -> QPushButton:
    """A mode tab: text with an accent underline when current.

    Checkable rather than a QTabBar so it lives in the header row beside the
    wordmark. The visual difference from `primary()` is the point — navigation
    that looks like a button competes with the buttons that actually do work.
    """
    button = QPushButton(text)
    button.setObjectName("NavTab")
    button.setCheckable(True)
    button.setFixedHeight(HEADER_HEIGHT)
    return button


def quiet(text: str) -> QPushButton:
    """A utility affordance: reads as a link, still behaves as a button.

    Used for the things that open a window and change nothing — Run Log, Cost
    History, Settings. They were full-weight buttons stacked in a card, which
    gave five inert utilities the same visual weight as "Generate".
    """
    button = QPushButton(text)
    button.setObjectName("QuietAction")
    button.setFixedHeight(30)
    button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return button


class StatBlock(QWidget):
    """One number over its caption.

    Replaces a line of prose like ``Session Cost: €0.00``. The number is the
    content; putting it on its own line at a larger size is what makes a column
    of them scannable instead of five sentences to read.
    """

    def __init__(self, caption: str, value: str = "—", parent=None):
        super().__init__(parent)
        self.setObjectName("Transparent")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        layout.addWidget(self.value_label)
        self.caption_label = micro(caption)
        layout.addWidget(self.caption_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_caption(self, caption: str) -> None:
        self.caption_label.setText(caption.upper())


class Meter(QWidget):
    """A budget as a bar, with used/cap beside the label.

    "Session remaining: €1 / €1" is two numbers you have to subtract to
    understand. A bar answers the actual question — how much is left — before
    you have read anything.
    """

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Transparent")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(XS + 1)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(SM)
        top.addWidget(micro(label))
        top.addStretch()
        self.amount_label = micro("—")
        top.addWidget(self.amount_label)
        layout.addLayout(top)

        self.bar = QProgressBar()
        self.bar.setObjectName("BudgetBar")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)

    def set(self, used: float, cap: float) -> None:
        self.amount_label.setText(f"€{used:.2f} / €{cap:.2f}".upper())
        # A zero cap is "no limit", not "fully spent" — showing a full bar there
        # would read as blocked when nothing is.
        percent = 0 if cap <= 0 else min(100, int(round(used / cap * 100)))
        self.bar.setValue(percent)
        self.bar.setProperty("over", percent >= 100)
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)


def rail(object_name: str, width: int) -> QFrame:
    """A fixed-width side column."""
    frame = QFrame()
    frame.setObjectName(object_name)
    frame.setFixedWidth(width)
    return frame
