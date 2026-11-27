"""The 56 px top bar (Design S3; ADR 0006, decision 3).

Left to right: the agent switch (two-agent workspaces) or the agent's name,
the project selector, the project actions button, History, a stretch (slice
2's stepper), the spend chip and the status chip. As room runs out
``TopBarFitter`` applies S3's collapse steps in order, from measured size
hints rather than fixed pixels, so cocoa and offscreen fonts both fit; it
undoes them in reverse as room returns. Nothing is ever hidden or moved into
an overflow menu, and the money figure never disappears.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QWidget)

from ui.shell.chips import COMPACT, FULL, SHORT, SpendChip, StatusChip

BAR_HEIGHT = 56
GAP = 12
PAD_WIDE = 24
PAD_NARROW = 16
NARROW_BELOW = 1200          # window width (S3)
SELECTOR_MIN = 140
SELECTOR_MAX = 260


class AgentSwitch(QFrame):
    """Quill / Press, Booth / Label: one segment per agent of the workspace.

    The window keeps its names: this is ``workspace_tool_row`` and its
    segments are ``workspace_tool_buttons[key]``, each still calling
    ``select_agent``. Left and Right move between the visible segments.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AgentSwitch")
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(2, 2, 2, 2)
        self.row.setSpacing(2)
        self.segments: list[QPushButton] = []
        self.setProperty("tight", False)

    def add_segment(self, button: QPushButton) -> QPushButton:
        button.setObjectName("AgentSegment")
        button.setCheckable(True)
        button.setFixedHeight(32)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.installEventFilter(self)
        self.row.addWidget(button)
        self.segments.append(button)
        return button

    def set_tight(self, tight: bool) -> None:
        """S3 step 6: side padding 14 → 8 px."""
        if bool(self.property("tight")) == tight:
            return
        self.setProperty("tight", tight)
        for button in self.segments:
            button.setProperty("tight", tight)
            button.style().unpolish(button)
            button.style().polish(button)
            button.updateGeometry()
        self.adjustSize()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and obj in self.segments:
            step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(event.key())
            if step is not None:
                visible = [b for b in self.segments if b.isVisible()]
                if obj in visible and len(visible) > 1:
                    target = visible[(visible.index(obj) + step) % len(visible)]
                    target.setFocus()
                    target.click()
                    return True
        return False


class TopBar(QFrame):
    def __init__(self, *, switch: AgentSwitch, project_selector: QComboBox,
                 project_button: QWidget, history_button: QWidget,
                 spend_chip: SpendChip, status_chip: StatusChip,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(BAR_HEIGHT)
        self.switch = switch
        self.agent_label = QLabel("")
        self.agent_label.setObjectName("TopBarAgent")
        self.project_selector = project_selector
        self.project_button = project_button
        self.history_button = history_button
        self.spend_chip = spend_chip
        self.status_chip = status_chip

        project_selector.setObjectName("ProjectSelector")
        project_selector.setFixedHeight(36)
        project_selector.setMinimumWidth(SELECTOR_MIN)
        project_selector.setMaximumWidth(SELECTOR_MAX)
        project_selector.setSizePolicy(QSizePolicy.Policy.Preferred,
                                       QSizePolicy.Policy.Fixed)

        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(PAD_WIDE, 0, PAD_WIDE, 0)
        self.row.setSpacing(GAP)
        for widget in (switch, self.agent_label, project_selector,
                       project_button, history_button):
            self.row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        self.row.addStretch(1)
        self.row.addWidget(spend_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        self.row.addWidget(status_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        self.fitter = TopBarFitter(self)

    def show_switch(self, two_agents: bool, agent_name: str) -> None:
        """The switch for a two-agent workspace, else the agent's name."""
        self.switch.setVisible(two_agents)
        self.agent_label.setVisible(not two_agents)
        self.agent_label.setText(agent_name)
        self.fitter.fit()


class TopBarFitter(QObject):
    """S3's collapse rule, applied in order as the bar narrows.

    Level 0 is the full form. Each level adds one step: 1 spend chip drops
    " today", 2 the project selector shrinks to its minimum, 3 the status chip
    goes compact, 4 the spend chip goes compact, 5 the switch segments
    tighten. (Step 1 of S3 belongs to slice 2's stepper.)
    """

    LEVELS = 6

    def __init__(self, bar: TopBar):
        super().__init__(bar)
        self.bar = bar
        self.level = 0
        bar.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.bar and event.type() in (QEvent.Type.Resize,
                                                QEvent.Type.Show):
            self.fit()
        return False

    def _padding(self) -> int:
        window = self.bar.window()
        width = window.width() if window is not None else self.bar.width()
        return PAD_NARROW if width < NARROW_BELOW else PAD_WIDE

    def _apply(self, level: int) -> None:
        bar = self.bar
        bar.spend_chip.set_form(COMPACT if level >= 4
                                else SHORT if level >= 1 else FULL)
        bar.status_chip.set_compact(level >= 3)
        bar.switch.set_tight(level >= 5)
        selector = bar.project_selector
        if level >= 2:
            selector.setMaximumWidth(SELECTOR_MIN)
        else:
            selector.setMaximumWidth(SELECTOR_MAX)
        self.level = level

    def _selector_width(self, level: int) -> int:
        hint = self.bar.project_selector.sizeHint().width()
        top = SELECTOR_MIN if level >= 2 else SELECTOR_MAX
        return max(SELECTOR_MIN, min(hint, top))

    def required(self, level: int) -> int:
        """The bar's content width at `level`, from measured hints."""
        bar = self.bar
        widths = []
        if bar.switch.isVisibleTo(bar):
            widths.append(bar.switch.sizeHint().width())
        if bar.agent_label.isVisibleTo(bar):
            widths.append(bar.agent_label.sizeHint().width())
        widths.append(self._selector_width(level))
        widths.append(bar.project_button.sizeHint().width())
        widths.append(bar.history_button.sizeHint().width())
        widths.append(bar.spend_chip.width_for(
            COMPACT if level >= 4 else SHORT if level >= 1 else FULL))
        widths.append(bar.status_chip.width_for(level >= 3))
        if level >= 5 and bar.switch.isVisibleTo(bar):
            # Each segment loses 2 × 6 px of side padding.
            widths[0] -= 12 * len([s for s in bar.switch.segments
                                   if s.isVisibleTo(bar)])
        return sum(widths) + GAP * (len(widths) - 1) + GAP   # + the stretch

    def fit(self) -> None:
        pad = self._padding()
        self.bar.row.setContentsMargins(pad, 0, pad, 0)
        room = self.bar.width() - 2 * pad
        for level in range(self.LEVELS):
            if self.required(level) <= room or level == self.LEVELS - 1:
                self._apply(level)
                return
