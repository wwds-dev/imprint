"""Keep every workspace tab in the header whole, at any window width.

Qt's scroll buttons were the old answer to a narrow header, and a poor one:
the last tab was clipped mid-word ("Assist") and the two arrows sat on top of
it, so the one place meant for navigation became a place to guess. There are
no arrows now. When the header runs out of room it first drops chrome nobody
navigates by, then moves the trailing workspaces into a More menu. A tab that
is shown is always shown in full, and the selected workspace is always a real
tab, never tucked into the menu.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QMenu, QTabBar, QToolButton, QWidget


class HeaderFitter(QObject):
    """Fit ``tabs`` into ``header``'s row by shedding, then overflowing.

    ``sheddable`` is hidden in order, one widget at a time, before any tab is
    moved into the menu — list the least useful first. The fitter owns those
    widgets' visibility; nothing else should hide or show them.
    """

    def __init__(self, header: QWidget, tabs: QTabBar, more: QToolButton,
                 sheddable: list[QWidget]):
        super().__init__(header)
        self.header = header
        self.tabs = tabs
        self.more = more
        self.sheddable = list(sheddable)
        self._fitting = False
        self._widths: list[int] = []
        self._listed: set[int] = set()
        self.menu = QMenu(more)
        more.setMenu(self.menu)
        more.setPopupMode(QToolButton.InstantPopup)
        more.hide()
        header.installEventFilter(self)
        tabs.currentChanged.connect(lambda _index: self.refit())

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        # LayoutRequest covers a sibling appearing or changing size (the
        # project pill), not just the window being resized.
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest):
            self.refit()
        return False

    def hidden_tabs(self) -> list[int]:
        """Indices of the workspaces currently listed under More."""
        return [i for i in range(self.tabs.count()) if not self.tabs.isTabVisible(i)]

    def refit(self) -> None:
        if self._fitting or not self.header.isVisible():
            return
        self._fitting = True
        try:
            self._refit()
        finally:
            self._fitting = False

    def _refit(self) -> None:
        # Decide on paper, then touch only what changes. Showing every tab to
        # measure it and hiding them again would invalidate the layout each
        # pass, and the LayoutRequest that follows would start another pass.
        # Widths come from tabRect, which lays the bar out on demand; the
        # bar's sizeHint lags a pass behind a visibility change, and deriving
        # anything from it made the fit oscillate.
        tabs = self.tabs
        widths = self._tab_widths()
        needed = sum(widths)

        # Chrome is shed from the front of the list: shedding `cut` widgets
        # keeps the tail from `cut` on.
        shed = [_width(w) for w in self.sheddable]
        room = self._room_without_sheddable()
        cut = 0
        while cut < len(shed) and needed > room - sum(shed[cut:]):
            cut += 1
        overflow = needed > room
        for index, widget in enumerate(self.sheddable):
            widget.setVisible(index >= cut)

        hide: set[int] = set()
        if overflow:
            # Everything optional is already gone: keep a prefix of the tabs,
            # plus the current one wherever it sits, and list the rest.
            current = tabs.currentIndex()
            budget = room - _width(self.more)
            used = widths[current] if current >= 0 else 0
            for index, width in enumerate(widths):
                if index == current:
                    continue
                if hide or used + width > budget:
                    hide.add(index)
                else:
                    used += width
        changed = [i for i in range(tabs.count())
                   if tabs.isTabVisible(i) == (i in hide)]
        # Only the tabs that change: setTabVisible with an unchanged value
        # clears the bar's layout-dirty flag, so a pass over every tab left
        # hidden tabs holding their old space.
        for index in changed:
            tabs.setTabVisible(index, index not in hide)
        if changed:
            # It also leaves the header layout's cached size hint for the bar
            # alone, so the bar would keep its old width.
            tabs.updateGeometry()

        if hide != self._listed:
            self._listed = hide
            self.menu.clear()
            for index in sorted(hide):
                action = self.menu.addAction(tabs.tabText(index))
                action.triggered.connect(
                    lambda _checked=False, i=index: tabs.setCurrentIndex(i))
        self.more.setVisible(bool(hide))

    def _tab_widths(self) -> list[int]:
        """Each tab's width: measured when shown, remembered while hidden.

        Re-measured every pass for the shown tabs because the selected tab is
        set bolder and so wider; the current tab is never hidden, so a hidden
        tab's remembered width is at worst from when it was bold — generous.
        """
        tabs = self.tabs
        if len(self._widths) != tabs.count():
            self._widths = [0] * tabs.count()
        for index in range(tabs.count()):
            if tabs.isTabVisible(index):
                self._widths[index] = tabs.tabRect(index).width()
        return list(self._widths)

    def _room_without_sheddable(self) -> int:
        """Header width left for the tabs once the sheddable chrome is gone
        and everything else that is shown has its size hint."""
        layout = self.header.layout()
        margins = layout.contentsMargins()
        taken = margins.left() + margins.right()
        skip = {self.tabs, self.more, *self.sheddable}
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget()
            if widget is None:
                taken += item.sizeHint().width()
            elif widget not in skip and not widget.isHidden():
                taken += _width(widget)
        return self.header.width() - taken


def _width(widget: QWidget) -> int:
    """Width a layout would give ``widget`` — its hint, within its limits.

    Asked of the widget rather than its layout item, whose cached hint can
    lag behind a tab that was just hidden.
    """
    return max(widget.minimumWidth(),
               min(widget.maximumWidth(), widget.sizeHint().width()))
