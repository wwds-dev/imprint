"""No text field is squeezed to a sliver, and a cut-off value can be read.

The Quill project bar showed "P…" in the Title field and "Pe…" in Author at a
1440px window while each dropdown beside them kept 177px. A QLineEdit's
minimum size hint is about one character wide, so whenever a grid ran short of
room the text inputs gave up their width to the combos first. That failure is
not specific to one panel: any layout that is short of width shrinks the
widget with the smallest minimum, and that is always the line edit.

Two app-wide guards, installed once on the QApplication like the dropdown
polisher in `ui/widgets.py`, so a field built tomorrow in a dialog nobody has
opened yet gets them too:

* **A floor.** Every QLineEdit that did not set its own width limits is given
  a minimum of `FLOOR_CHARS` average characters. A layout can still be tight,
  but it can no longer take a field below a readable width.
* **The full text on hover.** When a field or a dropdown cannot show its whole
  value (or its placeholder, when empty), hovering shows it. The widget's own
  explanatory tooltip, if it has one, follows underneath.

`tests/test_panel_layout.py` walks every panel at every tested window size and
fails when a visible field sits below the floor.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import (
    QApplication, QComboBox, QLineEdit, QStyle, QStyleOptionComboBox,
    QStyleOptionFrame, QToolTip, QWidget,
)

# Average characters a single-line field always has room for. Ten is
# "Project ti" — enough to recognise what is in the box; the rest is a hover.
FLOOR_CHARS = 10
# QLineEdit's own frame and the stylesheet's horizontal padding.
FIELD_CHROME = 24

_FILTER: "_TextFitFilter | None" = None
_REMEASURE = (QEvent.Type.Polish, QEvent.Type.FontChange,
              QEvent.Type.StyleChange, QEvent.Type.Show)


def floor_width(widget: QWidget) -> int:
    """The narrowest a single-line field may be drawn, in pixels."""
    return widget.fontMetrics().averageCharWidth() * FLOOR_CHARS + FIELD_CHROME


def apply_floor(edit: QLineEdit) -> None:
    """Give `edit` the readable minimum, unless it chose its own limits.

    A field with a fixed or capped width (a two-digit chunk size, a budget
    box in the rail) was sized deliberately; overriding that would push its
    row wider than the column it was designed for. The floor is re-measured
    whenever the font or style changes — a field is first polished before the
    app stylesheet sets its real font size, and a floor measured then is a
    character or two short.
    """
    mine = edit.property("imprintTextFloor")
    current = edit.minimumWidth()
    if current not in (0, mine):
        return
    floor = floor_width(edit)
    if edit.maximumWidth() < floor or current == floor:
        return
    edit.setProperty("imprintTextFloor", floor)
    edit.setMinimumWidth(floor)


def _line_edit_room(edit: QLineEdit) -> int:
    option = QStyleOptionFrame()
    edit.initStyleOption(option)
    rect = edit.style().subElementRect(
        QStyle.SubElement.SE_LineEditContents, option, edit)
    margins = edit.textMargins()
    # QLineEdit keeps a couple of pixels each side for the cursor.
    return rect.width() - margins.left() - margins.right() - 4


def _combo_room(combo: QComboBox) -> int:
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    rect = combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox, option,
        QStyle.SubControl.SC_ComboBoxEditField, combo)
    return rect.width()


def clipped_text(widget: QWidget) -> str:
    """The text `widget` is showing only part of, or "" when it all fits."""
    if isinstance(widget, QLineEdit):
        text = widget.text() if widget.text() else widget.placeholderText()
        if widget.echoMode() != QLineEdit.EchoMode.Normal and widget.text():
            return ""   # never reveal a password field on hover
        room = _line_edit_room(widget)
    elif isinstance(widget, QComboBox):
        text = widget.currentText()
        room = _combo_room(widget)
    else:
        return ""
    if not text:
        return ""
    return text if widget.fontMetrics().horizontalAdvance(text) > room else ""


class _TextFitFilter(QObject):
    def __init__(self, parent: QObject,
                 explanations_enabled: Callable[[], bool] | None):
        super().__init__(parent)
        self.explanations_enabled = explanations_enabled

    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        kind = event.type()
        if kind in _REMEASURE and isinstance(watched, QLineEdit):
            apply_floor(watched)
        elif kind == QEvent.Type.ToolTip and isinstance(
                watched, (QLineEdit, QComboBox)):
            full = clipped_text(watched)
            if full:
                tip = full
                explain = watched.toolTip()
                if explain and explain != full and (
                        self.explanations_enabled is None
                        or self.explanations_enabled()):
                    tip = f"{full}\n\n{explain}"
                QToolTip.showText(event.globalPos(), tip, watched)
                return True
        return False


def install_text_fit(app: QApplication | None,
                     explanations_enabled: Callable[[], bool] | None = None
                     ) -> None:
    """Install the floor and the hover once for the whole application.

    `explanations_enabled` is the header's Tooltips toggle. It governs the
    explanatory half only: the full value of a cut-off field is content, not
    help, so it is shown either way. Call this after any other application
    filter that swallows tooltips, because the filter installed last runs
    first.
    """
    if app is None:
        return
    global _FILTER
    if _FILTER is None:
        _FILTER = _TextFitFilter(app, explanations_enabled)
        app.installEventFilter(_FILTER)
    elif explanations_enabled is not None:
        _FILTER.explanations_enabled = explanations_enabled
    for widget in app.allWidgets():
        if isinstance(widget, QLineEdit):
            apply_floor(widget)
