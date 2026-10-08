"""
Imprint — panel layout tests
=====================================
Type: Layout regression tests, run headless.

Every agent panel used to draw its own controls on top of each other once the
window got small enough: the direction box landed over the Task and Provider
rows beneath it, and the Client Gigs buttons overlapped one another sideways.

The cause is the one `ui/widgets.FlowLayout` already documents for the
horizontal axis — a box layout reports the sum of its children as its minimum,
and a splitter pane dropped below that compresses children past their own
minimums rather than clipping. `ui/widgets.scrollable()` is the vertical
counterpart.

These assert the property directly rather than comparing screenshots: no two
sibling widgets inside a panel may occupy the same pixels.

Run with:  pytest tests/test_panel_layout.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

AGENTS = [
    "author", "manuscript", "audiobook", "music", "webdesign", "fiverr",
    "video",
]

# Agents whose panel holds more than one page. Testing only the page that
# happens to be showing is how the Publish column's overlapping Generate button
# survived the first pass — each of these has its own control column.
SUB_MODES = {
    "author": [
        ("write", lambda w: w._author_set_mode("write")),
        ("publish", lambda w: (w._author_set_mode("pubmkt"), w._author_set_sub_mode("publish"))),
        ("market", lambda w: (w._author_set_mode("pubmkt"), w._author_set_sub_mode("market"))),
    ],
}

# Down to the window's own minimum (1000x600, set in GodAI.__init__).
SIZES = [(1900, 1200), (1500, 950), (1280, 820), (1100, 700), (1000, 600)]


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    """One window for the module — building it costs ~10s."""
    from PySide6.QtWidgets import QMessageBox
    import main

    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        w = main.GodAI()
        w.show()
        app.processEvents()
        yield w
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


def _settle(app, window, size, agent):
    window.resize(*size)
    for _ in range(6):
        app.processEvents()
    window.select_agent(agent)
    for _ in range(6):
        app.processEvents()


def test_music_workspace_layout_is_owned_by_music_package(window):
    """Music dropped its host aliases first (2026-09-21): the panel owns
    every published control, the host no longer mirrors them, and shared
    wiring reaches them only through the _find_control resolver."""
    from agents.music.panel import MusicPanel

    assert isinstance(window.music_panel, MusicPanel)
    assert window.music_panel.music_tabs.count() == 6
    for name in MusicPanel.HOST_CONTROLS:
        owned = getattr(window.music_panel, name)
        assert owned is not None
        assert window._find_control(name) is owned
        assert getattr(window, name, None) is None, (
            f"{name} is still aliased onto the host")


def test_site_builder_workspace_is_owned_by_its_package(window):
    from agents.webdesign import WebdesignPanel

    assert isinstance(window.webdesign_panel, WebdesignPanel)
    assert window.webdesign_panel.webdesign_tabs.count() == 3
    for name in WebdesignPanel.HOST_CONTROLS:
        owned = getattr(window.webdesign_panel, name)
        assert owned is not None
        assert window._find_control(name) is owned
        assert getattr(window, name, None) is None, (
            f"{name} is still aliased onto the host")


def test_audiobook_workspace_is_owned_by_its_package(window):
    from agents.audiobook import AudiobookPanel

    assert isinstance(window.audiobook_panel, AudiobookPanel)
    assert window.audiobook_panel.audiobook_tabs.count() == 2
    for name in AudiobookPanel.HOST_CONTROLS:
        owned = getattr(window.audiobook_panel, name)
        assert owned is not None
        assert window._find_control(name) is owned
        assert getattr(window, name, None) is None, (
            f"{name} is still aliased onto the host")


def test_client_gigs_workspace_is_owned_by_fiverr_package(window):
    from agents.fiverr import FiverrPanel

    assert isinstance(window.fiverr_panel, FiverrPanel)
    assert window.fiverr_panel.fiverr_tabs.count() == 4
    for name in FiverrPanel.HOST_CONTROLS:
        owned = getattr(window.fiverr_panel, name)
        assert owned is not None
        assert window._find_control(name) is owned
        assert getattr(window, name, None) is None, (
            f"{name} is still aliased onto the host")


def test_video_workspace_is_owned_by_video_package(window):
    from agents.video import VideoPanel

    assert isinstance(window.video_panel, VideoPanel)
    assert window.video_panel.video_tabs.count() == 2
    for name in VideoPanel.HOST_CONTROLS:
        owned = getattr(window.video_panel, name)
        assert owned is not None
        assert window._find_control(name) is owned
        assert getattr(window, name, None) is None, (
            f"{name} is still aliased onto the host")


def test_video_compatibility_entries_delegate_to_owned_panel(window, monkeypatch):
    calls = []
    panel = window.video_panel
    monkeypatch.setattr(panel, "render", lambda: calls.append("render"))
    monkeypatch.setattr(panel, "stop", lambda: calls.append("stop"))
    monkeypatch.setattr(panel, "refresh_library",
                        lambda: calls.append("refresh"))

    window.video_render()
    window.video_stop()
    window.refresh_video_library()

    assert calls == ["render", "stop", "refresh"]


def test_fiverr_compatibility_entries_delegate_to_owned_panel(window, monkeypatch):
    calls = []
    panel = window.fiverr_panel
    monkeypatch.setattr(panel, "generate_logos",
                        lambda: calls.append("generate"))
    monkeypatch.setattr(panel, "write_delivery",
                        lambda: calls.append("delivery"))
    monkeypatch.setattr(panel, "write_gig", lambda: calls.append("gig"))
    monkeypatch.setattr(panel, "stop", lambda: calls.append("stop"))

    window.fiverr_generate_logos()
    window.fiverr_write_delivery()
    window.fiverr_write_gig()
    window.fiverr_stop()

    assert calls == ["generate", "delivery", "gig", "stop"]


def test_audiobook_library_actions_use_owned_panel(window, monkeypatch, tmp_path):
    audio = tmp_path / "Example_Book.mp3"
    audio.write_bytes(b"audio")
    monkeypatch.setattr(window, "get_audiobook_defaults",
                        lambda: {"output": str(tmp_path)})
    panel = window.audiobook_panel
    window.refresh_audiobook_library()

    assert panel.audiobook_library_table.rowCount() == 1
    assert panel.audiobook_library_table.item(0, 0).text() == "Example Book"
    panel.audiobook_library_table.selectRow(0)
    assert panel.audiobook_play_btn.isEnabled()

    calls = []
    monkeypatch.setattr(panel.audiobook_player, "load",
                        lambda path, **kwargs: calls.append((path, kwargs)))
    monkeypatch.setattr(panel.audiobook_player, "play", lambda: None)
    panel.audiobook_play_btn.click()
    assert calls[0][0] == audio
    assert panel.audiobook_status_label.text() == "[Playing] Example Book"


def test_audiobook_output_location_switches_between_local_and_drive(
        window, monkeypatch, tmp_path):
    from agents.audiobook import panel as panel_module

    panel = window.audiobook_panel
    drive = tmp_path / "audiobooks - gdrive"
    drive.mkdir()
    settings = {}
    monkeypatch.setattr(panel_module, "get_setting",
                        lambda key, default="": settings.get(key, default))
    monkeypatch.setattr(panel_module, "save_setting",
                        lambda key, value: settings.__setitem__(key, value))
    monkeypatch.setattr(panel_module, "suggested_drive_audiobook_folder",
                        lambda: drive)

    panel.audiobook_output_mode.setCurrentIndex(
        panel.audiobook_output_mode.findData("drive"))
    assert panel.defaults()["output"] == str(drive)
    assert panel.audiobook_output_path.text() == str(drive)

    panel.audiobook_output_mode.setCurrentIndex(
        panel.audiobook_output_mode.findData("local"))
    assert panel.defaults()["output"] == \
        panel.host.tool_runner.tools["audiobook"]["default_output"]


def test_audiobook_library_can_filter_to_current_project(window, monkeypatch, tmp_path):
    from services import project_artifacts

    linked = tmp_path / "Linked_Book.mp3"
    other = tmp_path / "Other_Book.mp3"
    linked.write_bytes(b"linked")
    other.write_bytes(b"other")
    monkeypatch.setattr(window, "get_audiobook_defaults",
                        lambda: {"output": str(tmp_path)})
    monkeypatch.setattr(window, "_active_project",
                        lambda: {"id": "book-1", "name": "Book One"})
    monkeypatch.setattr(project_artifacts, "list_for_project",
                        lambda project_id, *, kinds: [
                            {"path": str(linked.resolve())}])
    panel = window.audiobook_panel
    try:
        panel.audiobook_library_scope.setCurrentIndex(0)
        panel.refresh_library()
        assert panel.audiobook_library_table.rowCount() == 2
        panel.audiobook_library_scope.setCurrentIndex(1)
        assert panel.audiobook_library_scope.itemText(1) == "Project: Book One"
        assert panel.audiobook_library_table.rowCount() == 1
        assert panel.audiobook_library_table.item(0, 0).text() == "Linked Book"
        panel.audiobook_library_table.selectRow(0)
        assert panel._selected_book().path == linked
    finally:
        panel.audiobook_library_scope.setCurrentIndex(0)


def test_video_library_keeps_global_entries_and_filters_project(
        window, monkeypatch, tmp_path):
    from agents.video import video_studio
    from services import project_artifacts

    panel = window.video_panel
    if not panel._available:
        pytest.skip("Vidforge is unavailable")
    linked = tmp_path / "linked.mp4"
    other = tmp_path / "standalone.mp4"
    linked.write_bytes(b"linked")
    other.write_bytes(b"other")
    monkeypatch.setattr(video_studio, "library", lambda: [
        {"title": "Project render", "path": str(linked), "complete": True},
        {"title": "Standalone render", "path": str(other), "complete": True},
    ])
    monkeypatch.setattr(window, "_active_project",
                        lambda: {"id": "video-1", "name": "Campaign One"})
    monkeypatch.setattr(project_artifacts, "list_for_project",
                        lambda project_id, *, kinds: [
                            {"path": str(linked.resolve())}])
    try:
        panel.video_library_scope.setCurrentIndex(0)
        panel.refresh_library()
        assert panel.video_library_table.rowCount() == 2
        panel.video_library_scope.setCurrentIndex(1)
        assert panel.video_library_scope.itemText(1) == "Project: Campaign One"
        assert panel.video_library_table.rowCount() == 1
        assert panel.video_library_table.item(0, 0).text() == "Project render"
        assert panel._selected_path() is None
        panel.video_library_table.selectRow(0)
        assert panel._selected_path() == linked
    finally:
        panel.video_library_scope.setCurrentIndex(0)


def _overlapping_pairs(panel):
    """Sibling widgets sharing pixels — i.e. one drawn over the other."""
    from PySide6.QtWidgets import (
        QWidget, QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit,
    )
    watch = (QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit)
    kids = [c for c in panel.findChildren(QWidget)
            if isinstance(c, watch) and c.isVisible()
            and c.width() > 2 and c.height() > 2]

    found = []
    for i, a in enumerate(kids):
        for b in kids[i + 1:]:
            # Only siblings: a child sitting inside its own parent is normal.
            if a.parentWidget() is not b.parentWidget():
                continue
            if a.isAncestorOf(b) or b.isAncestorOf(a):
                continue
            rect = a.geometry().intersected(b.geometry())
            # A couple of pixels is a border touching, not an overlap.
            if rect.width() > 2 and rect.height() > 2:
                found.append((a, b, rect))
    return found


def _describe(widget):
    text = ""
    for attr in ("text", "currentText", "placeholderText"):
        if hasattr(widget, attr):
            try:
                text = getattr(widget, attr)() or text
            except Exception:
                pass
            if text:
                break
    return f"{type(widget).__name__}({text[:30]!r})"


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("agent", AGENTS)
def test_panel_controls_never_overlap(app, window, agent, size):
    _settle(app, window, size, agent)
    panel = getattr(window, f"{agent}_panel")
    bad = _overlapping_pairs(panel)
    assert not bad, "\n".join(
        f"{_describe(a)} overlaps {_describe(b)} by {r.width()}x{r.height()}px"
        for a, b, r in bad[:6]
    )


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize(
    "agent,mode",
    [(a, m) for a, modes in SUB_MODES.items() for m, _ in modes],
)
def test_sub_mode_pages_never_overlap(app, window, agent, mode, size):
    """Each page of a multi-page panel carries its own control column."""
    _settle(app, window, size, agent)
    switch = dict((m, fn) for m, fn in SUB_MODES[agent])[mode]
    switch(window)
    for _ in range(6):
        app.processEvents()
    panel = getattr(window, f"{agent}_panel")
    bad = _overlapping_pairs(panel)
    assert not bad, f"[{agent}/{mode}] " + "\n".join(
        f"{_describe(a)} overlaps {_describe(b)} by {r.width()}x{r.height()}px"
        for a, b, r in bad[:6]
    )


# The overlap tests compare siblings, so they never saw Quill at 1000x600:
# its QVBoxLayout got 362px against a 1061px minimum and squeezed every row —
# the editor stack to 102px of its 448px, the project bar to 103px of the
# 152px its folded second row needs. A child clipped by its own parent is not
# a sibling of anything. This asks the layout directly instead.

def _scrolls_vertically(widget):
    """True when `widget` sits inside a scroll area that can scroll down to
    whatever its parent layout could not fit."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea
    node = widget
    while node is not None:
        if (isinstance(node, QScrollArea) and node is not widget
                and node.widget() is not None
                and (node.widget() is widget or node.widget().isAncestorOf(widget))
                and node.verticalScrollBarPolicy() != Qt.ScrollBarAlwaysOff):
            return True
        node = node.parentWidget()
    return False


def _crushed_children(panel):
    """Direct children of the panel's top-level layout given less height than
    their minimum (or than their height-for-width at the width they got)."""
    layout = panel.layout()
    found = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        widget = item.widget()
        if item.isEmpty() or (widget is not None and not widget.isVisible()):
            continue
        rect = item.geometry()
        if item.hasHeightForWidth():
            need = item.heightForWidth(rect.width())
        else:
            need = item.minimumSize().height()
        if rect.height() >= need - 1:
            continue
        if _scrolls_vertically(widget if widget is not None else panel):
            continue
        name = (widget.objectName() or type(widget).__name__) if widget \
            else f"layout {type(item.layout()).__name__}"
        found.append(f"{name} gets {rect.height()}px of {need}px")
    return found


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize(
    "agent,mode",
    [(a, None) for a in AGENTS if a not in SUB_MODES]
    + [(a, m) for a, modes in SUB_MODES.items() for m, _ in modes],
)
def test_no_panel_row_is_crushed_below_its_minimum(app, window, agent, mode, size):
    _settle(app, window, size, agent)
    if mode is not None:
        dict(SUB_MODES[agent])[mode](window)
        for _ in range(6):
            app.processEvents()
    crushed = _crushed_children(getattr(window, f"{agent}_panel"))
    assert not crushed, f"[{agent}/{mode or '-'}] " + "; ".join(crushed)


@pytest.mark.parametrize("agent", ["author", "manuscript"])
def test_whole_panel_scroll_only_scrolls_below_the_minimum(app, window, agent):
    """A folding form grid makes these panels height-for-width, and a
    QScrollArea sizes such content to its preferred height — Manuscript
    scrolled 225px in a 1900x1200 window it fits. ui.widgets.ScrollContent
    asks for the minimum instead."""
    _settle(app, window, (1900, 1200), agent)
    area = getattr(window, f"{agent}_panel").layout().itemAt(0).widget()
    assert area.widget().minimumSizeHint().height() <= area.viewport().height()
    assert area.verticalScrollBar().maximum() == 0


@pytest.mark.parametrize("agent", AGENTS)
def test_panel_controls_stay_inside_the_window(app, window, agent):
    """Overlap is not the only failure — a control pushed outside the window is
    equally unusable, and a scroll area that is not resizable causes it."""
    from PySide6.QtWidgets import QWidget, QPushButton, QComboBox
    _settle(app, window, (1100, 700), agent)
    panel = getattr(window, f"{agent}_panel")
    escaped = []
    for child in panel.findChildren(QWidget):
        if not isinstance(child, (QPushButton, QComboBox)) or not child.isVisible():
            continue
        top_left = child.mapTo(window, child.rect().topLeft())
        if top_left.x() < -2 or top_left.y() < -2:
            escaped.append(f"{_describe(child)} at {top_left.x()},{top_left.y()}")
    assert not escaped, "controls positioned outside the window: " + "; ".join(escaped[:5])


@pytest.mark.parametrize("size", [(1900, 1200), (1500, 950), (1280, 820), (1100, 700)],
                         ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("agent", AGENTS)
def test_no_control_is_unreachable(app, window, agent, size):
    """Content wider than its pane is only a bug when you cannot scroll to it.

    This replaces an earlier version that asserted "nothing is ever wider than
    its pane" and carried a growing exclusion list — music, then webdesign,
    then fiverr — as more panels were made to scroll as a whole. Excluding
    panels one by one was weakening the test to fit the code. The property
    that actually matters is that every control can be reached: a column may
    overflow, but only if it can scroll.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea
    _settle(app, window, size, agent)
    panel = getattr(window, f"{agent}_panel")
    unreachable = []
    for area in panel.findChildren(QScrollArea):
        if not area.isVisible() or area.widget() is None:
            continue
        need = area.widget().minimumSizeHint().width()
        have = area.viewport().width()
        if need > have and area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff:
            unreachable.append(f"needs {need}px in a {have}px pane with no scrollbar")
    assert not unreachable, f"[{agent}] " + "; ".join(unreachable)


def test_author_workbench_has_no_nested_control_scroller(app, window):
    """Compose, Task and Model belong in the canvas, not a tiny scroll pane.

    The panel itself scrolls as a whole below its minimum height (see
    test_no_panel_row_is_crushed_below_its_minimum); that one outer scroller
    is the panel's frame. Nothing inside it may scroll on its own."""
    from PySide6.QtWidgets import QScrollArea

    _settle(app, window, (1760, 820), "author")
    window._author_set_mode("write")
    app.processEvents()
    panel = window.author_panel
    scrollers = panel.findChildren(QScrollArea)
    assert len(scrollers) == 1, scrollers
    outer = scrollers[0]
    assert panel.layout().indexOf(outer) == 0
    for control in (panel.author_compose_card, panel.author_task_box,
                    panel.author_model_box, panel.author_tabs):
        assert outer.widget().isAncestorOf(control)


def test_section_headings_are_readable_not_field_label_small_caps(app, window):
    from ui.forms import section

    heading = section("Conversion settings")
    assert heading.text() == "Conversion settings"
    assert heading.objectName() == "SectionLabel"


def test_audiobook_source_list_does_not_push_settings_below_the_fold(app, window):
    window.select_agent("audiobook")
    _settle(app, window, (1400, 900), "audiobook")
    assert window.audiobook_panel.audiobook_book_list.maximumHeight() <= 180
    assert window.audiobook_panel.audiobook_source_stack.height() <= 180
    assert window.audiobook_panel.audiobook_start_btn.text() == "Convert audiobook"


def test_audiobook_convert_form_is_one_vertical_scroll_surface(app, window):
    """Every convert control must scroll together instead of being compressed."""
    from PySide6.QtCore import Qt

    _settle(app, window, (1000, 600), "audiobook")
    area = window.audiobook_panel.audiobook_convert_scroll
    content = area.widget()
    assert content is not None
    assert content.isAncestorOf(window.audiobook_panel.audiobook_input_path)
    assert content.isAncestorOf(window.audiobook_panel.audiobook_output_path)
    assert content.isAncestorOf(window.audiobook_panel.audiobook_start_btn)
    assert area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert area.verticalScrollBar().maximum() > 0


def test_audiobook_refresh_controls_keep_separate_jobs(app, window):
    assert window.audiobook_panel.audiobook_refresh_btn.text() == "Refresh List"
    assert window.audiobook_panel.audiobook_library_refresh_btn.text() == "Rescan"


def test_fixed_utility_rail_never_grows_a_horizontal_scrollbar(app, window):
    """The right rail is deliberately one fixed width; only vertical travel is useful."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea, QWidget

    rail = window.findChild(QWidget, "RailRight")
    area = rail.findChild(QScrollArea)
    assert area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff


def test_author_compose_remains_whole_with_profile_open(app, window):
    """Opening Book Profile must not crop the command deck below it."""
    from PySide6.QtCore import QPoint

    _settle(app, window, (1760, 820), "author")
    window._author_set_mode("write")
    was_open = window.author_panel.author_profile_section.content.isVisible()
    if not was_open:
        window.author_panel.author_profile_section.header_btn.click()
    for _ in range(6):
        app.processEvents()

    card = window.author_panel.author_compose_card
    for control in (
        window.author_panel.author_direction_input,
        window.author_panel.author_task_box,
        window.author_panel.author_provider_box,
        window.author_panel.author_model_box,
        window.author_panel.author_write_btn,
        window.author_panel.author_continue_btn,
        window.author_panel.author_stop_btn,
    ):
        top_left = control.mapTo(card, QPoint(0, 0))
        bottom_right = control.mapTo(card, control.rect().bottomRight())
        assert card.rect().contains(top_left), _describe(control)
        assert card.rect().contains(bottom_right), _describe(control)

    if not was_open:
        window.author_panel.author_profile_section.header_btn.click()


def test_author_footer_prioritises_primary_actions_when_narrow(app, window):
    """Low-priority metadata gives way before Save or Export can be clipped."""
    _settle(app, window, (1000, 600), "author")
    window._author_set_mode("write")
    for _ in range(6):
        app.processEvents()

    assert not window.author_panel.author_word_metric.isVisible()
    assert not window.author_panel.author_export_author_input.isVisible()
    assert window.author_panel.author_save_btn.isVisible()
    assert window.author_panel.author_export_format_box.isVisible()
    assert window.author_panel.author_export_btn.isVisible()
    assert window.author_panel.author_save_btn.text() == "Save"
    assert window.author_panel.author_export_btn.text() == "Export"


def test_dropdowns_use_the_shared_polished_popup(app, window):
    """Dropdowns must not fall back to macOS's plain native text menu."""
    from PySide6.QtWidgets import QAbstractItemView, QStyle
    from ui.widgets import DropdownItemDelegate, POPUP_MAX_WIDTH

    _settle(app, window, (1760, 820), "author")
    combo = window.author_panel.author_model_box
    view = combo.view()

    assert combo.property("imprintModernDropdown") is True
    assert combo.style().styleHint(QStyle.SH_ComboBox_Popup, None, combo) == 0
    assert isinstance(view.itemDelegate(), DropdownItemDelegate)
    assert view.objectName() == "ImprintComboPopup"
    assert view.sizeHintForRow(0) >= DropdownItemDelegate.ROW_HEIGHT
    assert view.minimumWidth() == view.maximumWidth()
    assert view.width() <= POPUP_MAX_WIDTH
    assert combo.maxVisibleItems() == 9
    assert view.verticalScrollMode() == QAbstractItemView.ScrollPerPixel
    assert "combobox-popup: 0" in window.styleSheet()
    assert "dropdown-chevron.svg" in window.styleSheet()

    spec = os.path.join(os.path.dirname(__file__), "..", "Imprint.spec")
    assert '("assets/dropdown-chevron.svg", "assets")' in open(
        spec, encoding="utf-8").read()


def test_dropdowns_created_after_startup_are_polished(app, window):
    """Dialogs created later must receive the same popup as main panels."""
    from PySide6.QtWidgets import QComboBox, QStyle
    from ui.widgets import DropdownItemDelegate

    combo = QComboBox()
    combo.addItems(["First", "Second"])
    combo.show()
    for _ in range(3):
        app.processEvents()
    try:
        assert combo.property("imprintModernDropdown") is True
        assert combo.style().styleHint(QStyle.SH_ComboBox_Popup, None, combo) == 0
        assert isinstance(combo.itemDelegate(), DropdownItemDelegate)
    finally:
        combo.close()
        combo.deleteLater()


def test_short_dropdown_popup_tracks_its_field_instead_of_defaulting_to_640(app, window):
    """A two-item selector must not span most of the author canvas."""
    _settle(app, window, (1760, 820), "author")
    combo = window.author_panel.author_content_type_box
    combo.showPopup()
    for _ in range(3):
        app.processEvents()
    try:
        popup_width = combo.view().window().width()
        assert popup_width <= combo.width() + 20
        assert popup_width < 500
    finally:
        combo.hidePopup()


def test_every_provider_model_selector_has_an_explained_best_fit(app, window):
    """A newly added panel cannot silently miss recommendation integration."""
    from main import AGENT_SETUP_WIDGETS
    from ui.widgets import (
        RECOMMENDED_ROLE, RECOMMENDATION_CONFIDENCE_ROLE,
        RECOMMENDATION_REASON_ROLE,
    )

    for agent, (provider_name, model_name) in AGENT_SETUP_WIDGETS.items():
        # Through the resolver, not host attributes: panels are dropping
        # their host aliases (music first, 2026-09-21).
        provider = window._find_control(provider_name)
        model = window._find_control(model_name)
        assert provider is not None and model is not None, agent
        window.refresh_recommendation_marks(agent)
        for kind, combo in (("provider", provider), ("model", model)):
            marked = [i for i in range(combo.count())
                      if combo.itemData(i, RECOMMENDED_ROLE)]
            assert len(marked) == 1, f"{agent} {kind}: {marked}"
            index = marked[0]
            assert combo.itemData(index, RECOMMENDATION_REASON_ROLE)
            assert combo.itemData(index, RECOMMENDATION_CONFIDENCE_ROLE) in {
                "low", "medium", "high"
            }

    window.refresh_video_recommendations()
    for combo in (window.video_panel.video_visual_provider_box,
                  window.video_panel.video_visual_model_box,
                  window.fiverr_panel.fiverr_image_model_box):
        assert sum(bool(combo.itemData(i, RECOMMENDED_ROLE))
                   for i in range(combo.count())) == 1


def test_model_best_fit_recomputes_inside_each_selected_provider(app, window):
    from ui.widgets import RECOMMENDED_ROLE

    window.select_agent("social")
    for provider in ("openai", "deepseek", "gemini", "anthropic", "qwen"):
        window.social_panel.social_provider_box.setCurrentText(provider)
        for _ in range(3):
            app.processEvents()
        marked = [i for i in range(window.social_panel.social_model_box.count())
                  if window.social_panel.social_model_box.itemData(i, RECOMMENDED_ROLE)]
        assert len(marked) == 1, provider


# ── Conditional fields ───────────────────────────────────────────────────────
CREATOR_KINDS = [
    ("post", 2),       # kind + campaign
    ("promo", 3),      # kind + campaign + channel
    ("bio", 2),
    ("campaign", 2),
    ("hooks", 2),
]


@pytest.mark.parametrize("kind,expected", CREATOR_KINDS, ids=[k for k, _ in CREATOR_KINDS])
def test_creator_compose_grid_has_no_empty_cells(app, window, kind, expected):
    """Fields that do not apply give up their cell instead of leaving a hole.

Channel is the off-platform funnel and only applies to a promo.
    Hiding a widget inside a QGridLayout leaves its cell reserved and empty,
    so switching away from "promo" left a gap where Channel had been — the
    same "nothing lines up" complaint, produced by an empty cell rather than
    a misplaced one.

    Also guards the subtler bug this replaced: the first implementation asked
    the widgets whether they were hidden, and a widget that has never been
    shown reports isHidden() as True, so the grid came up empty.
    """
    window.select_agent("creator")
    window._creator_kind_changed(kind)
    _settle(app, window, (1500, 950), "creator")

    grid = window.creator_panel.creator_compose_grid
    positions = sorted(grid.getItemPosition(i)[:2] for i in range(grid.count()))
    assert len(positions) == expected, (
        f"[{kind}] expected {expected} fields, packed {len(positions)}")
    # Packed from (0,0) rightwards with no gaps.
    assert positions == [(i // 3, i % 3) for i in range(expected)], (
        f"[{kind}] fields are not packed contiguously: {positions}")


def test_video_provider_model_controls_only_offer_working_routes(app, window):
    """Every visible provider/model pair must change to its real constraints."""
    from services.media_catalog import RETIRED_DALLE_MODELS

    window.select_agent("video")
    offered = set()
    for provider in ("OpenAI", "Higgsfield", "Pexels", "Local"):
        window.video_panel.video_visual_provider_box.setCurrentText(provider)
        app.processEvents()
        assert window.video_panel.video_visual_model_box.count() > 0
        offered.update(
            window.video_panel.video_visual_model_box.itemData(i).model_id
            for i in range(window.video_panel.video_visual_model_box.count()))

    assert offered.isdisjoint(RETIRED_DALLE_MODELS)
    # Sora ids were removed ahead of the 2026-09-24 shutdown.
    assert not any(m.startswith("sora") for m in offered)
    window.video_panel.video_visual_provider_box.setCurrentText("OpenAI")
    image_index = next(
        i for i in range(window.video_panel.video_visual_model_box.count())
        if window.video_panel.video_visual_model_box.itemData(i).kind == "scene_images")
    window.video_panel.video_visual_model_box.setCurrentIndex(image_index)
    app.processEvents()
    assert window.video_panel.video_format_box.isEnabled()
    assert "Sora is no longer offered" in window.video_panel.video_visual_note.text()
    assert "no successor" in window.video_panel.video_visual_note.text()

    window.video_panel.video_visual_provider_box.setCurrentText("Gemini")
    direct_index = next(
        i for i in range(window.video_panel.video_visual_model_box.count())
        if window.video_panel.video_visual_model_box.itemData(i).kind == "direct_video")
    window.video_panel.video_visual_model_box.setCurrentIndex(direct_index)
    app.processEvents()
    assert not window.video_panel.video_format_box.isEnabled()


def test_video_refuses_a_legacy_sora_selection_before_authorization(window, monkeypatch):
    from services.media_catalog import MediaModel

    warnings = []
    monkeypatch.setattr("main.QMessageBox.warning",
                        lambda *_args: warnings.append(_args[2]))
    monkeypatch.setattr(window, "authorize_request",
                        lambda *_args, **_kwargs: pytest.fail("paid call was reached"))
    # The catalog carries no OpenAI direct_video row any more; this pins the
    # defensive refusal for a stale selection object.
    window._video_render_direct(MediaModel(
        "OpenAI", "sora-2", "Sora 2", "direct_video"))
    assert "no longer starts Sora jobs" in warnings[0]


def test_no_control_label_carries_an_emoji(app, window):
    """Emoji render at a different size and baseline from the text beside them.

    A column of buttons whose labels start with one has a ragged left edge
    that no padding fixes, which is most of why the rails read as untidy. The
    audio player's transport glyphs are exempt — ▶ on a play button is a
    universal symbol, not decoration.
    """
    from PySide6.QtWidgets import QPushButton, QLabel

    transport = set("▶⏸⏹⏪⏩⏵⏴×")
    offenders = []
    widgets = list(window.findChildren(QPushButton)) + list(window.findChildren(QLabel))
    for widget in widgets:
        text = widget.text()
        for char in text:
            if char in transport:
                continue
            if 0x1F300 <= ord(char) <= 0x1FAFF or char in "✅❌⚠✨🔌🔍💬📥📅⬇⛔↻↺⬛":
                offenders.append(f"{widget.objectName() or type(widget).__name__}: {text!r}")
                break
    assert not offenders, "emoji in control labels: " + "; ".join(sorted(set(offenders))[:8])


# ── The shell ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_shell_chrome_never_overlaps(app, window, size):
    """The header and the two rails, not just the panel between them.

    The panel tests only ever looked inside `<agent>_panel`, so the rails were
    unchecked — and at the window's own 600px minimum the spend rail drew
    "€0.00" straight over the caption beneath it. Same cause the panels use
    scrollable() for: a QVBoxLayout given less height than its children need
    compresses them past their own minimums instead of clipping.
    """
    _settle(app, window, size, "fiverr")
    bad = []
    for name in ("RailLeft", "RailRight", "AppHeader"):
        chrome = window.findChild(object, name)
        if chrome is None:
            continue
        bad += [(name, a, b) for a, b, _ in _overlapping_pairs(chrome)]
    assert not bad, "\n".join(
        f"  [{where}] {_describe(a)} overlaps {_describe(b)}"
        for where, a, b in bad[:6])


def test_workspace_names_are_never_elided(app, window):
    """Product-area names must remain meaningful after the professional rename."""
    from PySide6.QtCore import Qt

    _settle(app, window, (1500, 950), "author")
    assert window.workspace_tabs.elideMode() == Qt.ElideNone
    assert [window.workspace_tabs.tabText(i)
            for i in range(window.workspace_tabs.count())] == [
        "Author", "Audio + Music", "Video + Ads", "Social", "Web",
        "Brand Design", "Brand Content", "Assistant",
    ]


def test_narrow_header_overflows_workspaces_instead_of_scrolling(app, window):
    """Scroll arrows clipped "Assistant" to "Assist" and sat on top of it.

    Narrow headers now drop chrome, then list trailing workspaces under
    More; a tab that is shown is shown whole, and the selected workspace is
    always a real tab.
    """
    tabs = window.workspace_tabs
    assert not tabs.usesScrollButtons()

    _settle(app, window, (1500, 950), "author")
    assert window.header_fitter.hidden_tabs() == []
    assert not window.workspace_more_btn.isVisible()

    for size in ((1100, 700), (1000, 600)):
        _settle(app, window, size, "chat")
        hidden = window.header_fitter.hidden_tabs()
        assert hidden and window.workspace_more_btn.isVisible()
        assert tabs.isTabVisible(tabs.currentIndex())
        assert tabs.tabText(tabs.currentIndex()) == "Assistant"
        assert tabs.width() >= tabs.sizeHint().width()
        assert [a.text() for a in window.header_fitter.menu.actions()] == [
            tabs.tabText(i) for i in hidden]
        assert window.workspace_more_btn.geometry().right() < (
            window.settings_btn.geometry().left())

    # Picking from the menu opens that workspace and makes it a real tab.
    target = window.header_fitter.hidden_tabs()[0]
    window.header_fitter.menu.actions()[0].trigger()
    for _ in range(6):
        app.processEvents()
    assert tabs.currentIndex() == target and tabs.isTabVisible(target)

    _settle(app, window, (1500, 950), "author")
    assert window.header_fitter.hidden_tabs() == []


def test_studio_assistant_workspace_opens_the_existing_chat_panel(app, window):
    window.select_agent("chat")
    app.processEvents()
    assert window.workspace_tabs.tabText(window.workspace_tabs.currentIndex()) == "Assistant"
    assert window.normal_panel.isVisible()
    assert window.agent_title_label.text() == "Chat"


def test_audiobook_selection_refreshes_the_cost_estimate(app, window):
    """Fires the book list's real selection signal, not just construction.

    The panel once connected currentItemChanged to a slot that did not
    exist; PySide6 swallows slot exceptions, so every selection raised
    AttributeError silently and the per-book cost estimate never updated.
    Since the 2026-09-21 extraction the slot lives on the panel itself —
    this test stays implementation-agnostic by patching the panel instance,
    and keeps guarding the signal-time wiring class that construction-time
    tests let through twice.
    """
    calls = []
    panel = window.audiobook_panel
    lst = panel.audiobook_book_list
    panel.estimate_cost_from_selection = lambda: calls.append(1)
    try:
        lst.addItem("A Book.epub")
        lst.setCurrentRow(lst.count() - 1)
        app.processEvents()
        assert calls, "selecting a book must refresh the cost estimate"
    finally:
        del panel.estimate_cost_from_selection
        lst.takeItem(lst.count() - 1)


def test_audiobook_conversion_entries_delegate_to_owned_panel(window, monkeypatch):
    calls = []
    panel = window.audiobook_panel
    monkeypatch.setattr(panel, "start_conversion",
                        lambda: calls.append("start"))
    monkeypatch.setattr(panel, "stop_conversion",
                        lambda: calls.append("stop"))

    window.start_selected_audiobook_book()
    window.stop_current_task()

    assert calls == ["start", "stop"]


# ── Text that fits ──────────────────────────────────────────────────────────
# The Quill project bar drew "P…" in Title and "Pe…" in Author at a 1440px
# window while each dropdown beside them kept 177px: a short-of-width grid
# takes the room from the widget with the smallest minimum, and a QLineEdit's
# is one character. ui/text_fit.py puts a floor under every field, and
# form_grid folds into more rows instead of squeezing. These keep it that way
# in every panel, not just the one that was reported.

def _squeezed_fields(root):
    """Fields below the floor, or cut off by a container too narrow for them.

    Width alone could not fail once the floor pinned every edit at 104px —
    two such edits forced into a 120px container passed (review of
    9777f0c). So each field is also walked up its containers, up to the
    nearest scroll viewport, and must lie inside every one of them: a field
    sticking out of its container is drawn clipped or over its neighbour.
    The viewport itself is not a limit — content wider than it scrolls, which
    test_no_control_is_unreachable already holds to account.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import (
        QAbstractScrollArea, QAbstractSpinBox, QComboBox, QLineEdit)
    from ui.text_fit import floor_width
    found = []
    for edit in root.findChildren(QLineEdit):
        if not edit.isVisible() or isinstance(
                edit.parent(), (QAbstractSpinBox, QComboBox)):
            continue
        label = edit.text() or edit.placeholderText() or edit.objectName()
        if (edit.maximumWidth() >= floor_width(edit)
                and edit.width() < floor_width(edit) - 1):
            found.append(f"{label[:30]!r} is {edit.width()}px "
                         f"(floor {floor_width(edit)}px)")
            continue
        ancestor = edit.parentWidget()
        while ancestor is not None:
            outer = ancestor.parentWidget()
            if isinstance(outer, QAbstractScrollArea) and ancestor is outer.viewport():
                break       # scrolled content can be scrolled into view
            x = edit.mapTo(ancestor, QPoint(0, 0)).x()
            if x < -1 or x + edit.width() > ancestor.width() + 1:
                found.append(f"{label[:30]!r} ({edit.width()}px at x={x}) sticks "
                             f"out of a {ancestor.width()}px "
                             f"{type(ancestor).__name__}")
                break
            if ancestor is root:
                break
            ancestor = outer
    return found


def test_the_squeeze_check_can_fail(app):
    """The helper above must catch the case the old one passed."""
    from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget
    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    for _ in range(2):
        edit = QLineEdit("value")
        edit.setMinimumWidth(104)
        row.addWidget(edit)
    host.setFixedWidth(120)
    host.show()
    for _ in range(4):
        app.processEvents()
    assert _squeezed_fields(host), "two 104px fields in a 120px host went unnoticed"


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("agent", AGENTS)
def test_no_text_field_is_squeezed_below_readable(app, window, agent, size):
    _settle(app, window, size, agent)
    squeezed = _squeezed_fields(getattr(window, f"{agent}_panel"))
    assert not squeezed, f"[{agent}] " + "; ".join(squeezed[:6])


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize(
    "agent,mode",
    [(a, m) for a, modes in SUB_MODES.items() for m, _ in modes],
)
def test_sub_mode_text_fields_are_not_squeezed(app, window, agent, mode, size):
    _settle(app, window, size, agent)
    dict(SUB_MODES[agent])[mode](window)
    for _ in range(6):
        app.processEvents()
    squeezed = _squeezed_fields(getattr(window, f"{agent}_panel"))
    assert not squeezed, f"[{agent}/{mode}] " + "; ".join(squeezed[:6])


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_quill_project_bar_columns_are_equal_and_never_squeezed(app, window, size):
    """The reported screen: every column the same width, none below the
    grid's minimum, and the placeholders whole wherever there is room."""
    from ui.forms import FIELD_MIN_WIDTH
    from ui.text_fit import clipped_text
    _settle(app, window, size, "author")
    window._author_set_mode("write")
    for _ in range(6):
        app.processEvents()
    panel = window.author_panel
    fields = (panel.author_title_input, panel.author_name_input,
              panel.author_content_type_box, panel.author_genre_box,
              panel.author_tone_box, panel.author_pov_box)
    widths = {f.width() for f in fields}
    assert max(widths) - min(widths) <= 1, widths
    assert min(widths) >= FIELD_MIN_WIDTH - 1, widths
    for edit in fields[:2]:
        edit.clear()
        assert not clipped_text(edit), (
            f"{edit.placeholderText()!r} cut off at {edit.width()}px")


def test_a_clipped_field_shows_its_full_text_on_hover(app, window):
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QLineEdit, QToolTip
    from ui.text_fit import clipped_text
    _settle(app, window, (1000, 600), "author")
    edit = window.author_panel.author_title_input
    long_title = "The Unbearable Persistence of Very Long Working Titles"
    edit.setText(long_title)
    try:
        assert clipped_text(edit) == long_title
        event = QHelpEvent(QEvent.Type.ToolTip, QPoint(4, 4),
                           edit.mapToGlobal(QPoint(4, 4)))
        app.sendEvent(edit, event)
        assert QToolTip.isVisible()
        assert QToolTip.text().startswith(long_title)
    finally:
        QToolTip.hideText()
        edit.clear()
    password = QLineEdit()
    password.setEchoMode(QLineEdit.EchoMode.Password)
    password.setText("x" * 200)
    password.resize(60, 30)
    assert clipped_text(password) == ""


def test_the_full_text_shows_even_with_explanatory_tooltips_off(app, window):
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QToolTip
    _settle(app, window, (1000, 600), "author")
    edit = window.author_panel.author_title_input
    edit.setToolTip("Explanation that the toggle hides")
    edit.setText("A title far too long for the box it has been given to live in")
    window.tooltips_enabled = False
    try:
        app.sendEvent(edit, QHelpEvent(QEvent.Type.ToolTip, QPoint(4, 4),
                                       edit.mapToGlobal(QPoint(4, 4))))
        assert QToolTip.isVisible()
        assert "Explanation" not in QToolTip.text()
    finally:
        window.tooltips_enabled = True
        QToolTip.hideText()
        edit.clear()
        edit.setToolTip("")


def test_form_grid_folds_into_balanced_rows():
    from ui.forms import FieldGridLayout
    from PySide6.QtWidgets import QLabel, QWidget
    host = QWidget()
    grid = FieldGridLayout(columns=6, min_column_width=100)
    host.setLayout(grid)
    for _ in range(6):
        grid.addWidget(QLabel("x"))
    # 16px gaps: six columns need 680, five 564, three 332.
    assert grid.columns_for(680) == 6
    assert grid.columns_for(600) == 3     # never five over a lone sixth
    assert grid.columns_for(332) == 3
    assert grid.columns_for(250) == 2
    assert grid.columns_for(90) == 1


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_every_rail_control_fits_inside_the_rail(app, window, size):
    """The policy test above only says no scrollbar appears — so content wider
    than the rail was simply cut off. The text floor did exactly that to the
    Session € / Daily € row and Save Limits (review of 9777f0c). Every control
    must end inside the rail's viewport, with every section open."""
    from PySide6.QtWidgets import (
        QAbstractButton, QComboBox, QLineEdit, QScrollArea, QWidget)
    from ui.widgets import CollapsibleSection
    _settle(app, window, size, "author")
    rail = window.findChild(QWidget, "RailRight")
    area = rail.findChild(QScrollArea)
    opened = [sec for sec in rail.findChildren(CollapsibleSection)
              if not sec._expanded]
    for sec in opened:
        sec._toggle()
    try:
        for _ in range(6):
            app.processEvents()
        viewport = area.viewport()
        clipped = []
        for child in area.widget().findChildren(QWidget):
            if not isinstance(child, (QLineEdit, QComboBox, QAbstractButton)):
                continue
            if not child.isVisible():
                continue
            right = child.mapTo(viewport, child.rect().topRight()).x()
            if right > viewport.width():
                clipped.append(f"{_describe(child)} ends at {right}px "
                               f"in a {viewport.width()}px rail")
        assert not clipped, "; ".join(clipped[:5])
    finally:
        for sec in opened:
            sec._toggle()


def test_the_text_floor_leaves_spin_box_and_date_edits_alone(app):
    """The floor grew the edit inside a QDateEdit over its arrow button, so
    Press's calendar picker stopped opening (review of 9777f0c)."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDateEdit, QLineEdit, QSpinBox, QWidget
    from ui.text_fit import apply_floor, floor_width
    host = QWidget()
    spin = QSpinBox(host)
    spin.setRange(0, 10)
    spin.setGeometry(0, 0, 64, 30)
    date = QDateEdit(host)
    host.show()
    for _ in range(4):
        app.processEvents()
    for owner in (spin, date):
        inner = owner.findChild(QLineEdit)
        apply_floor(inner)
        assert inner.minimumWidth() < floor_width(inner), type(owner).__name__
    # And the arrows still work on a narrow spin box.
    value = spin.value()
    QTest.mouseClick(spin, Qt.MouseButton.LeftButton,
                     pos=QPoint(spin.width() - 6, 6))
    assert spin.value() == value + 1


# ── The aligned-form pass (2026-10-08) ──────────────────────────────────────
# The Chat panel was three rows built three ways; other panels had colon
# captions, fields painting the page colour inside cards, and wrapped rows that
# hung buttons from the top of the line. These pin the shared fixes.

def test_form_grid_rows_and_spans_keep_columns_aligned(app):
    """A deliberate short row does not rebalance: the next row's columns
    still sit under the first's, and a span covers its columns and the gap."""
    from PySide6.QtWidgets import QLabel, QWidget
    from ui.forms import FieldGridLayout
    host = QWidget()
    grid = FieldGridLayout(columns=3, min_column_width=100)
    host.setLayout(grid)
    tool, command, provider, model, mode, wide, narrow = (
        QLabel(name) for name in ("tool", "command", "provider", "model",
                                  "mode", "wide", "narrow"))
    grid.add_field(tool)
    grid.add_field(command)
    grid.add_field(provider, new_row=True)
    grid.add_field(model)
    grid.add_field(mode)
    grid.add_field(wide, span=2, new_row=True)
    grid.add_field(narrow)
    host.resize(632, 400)
    host.show()
    for _ in range(4):
        app.processEvents()
    assert grid.columns_for(632) == 3
    assert tool.x() == provider.x() == wide.x()
    assert command.x() == model.x()
    assert mode.x() == narrow.x()
    assert provider.y() > tool.y()
    assert wide.y() > provider.y()
    assert wide.x() + wide.width() + 16 == narrow.x()     # two columns + gap


def test_toggle_chip_is_wide_enough_for_its_label(app):
    """macOS sizes a styled checkbox with no spare pixel, and every row that
    placed checkboxes at their hint clipped the last letters ("OpenA")."""
    from ui.forms import ToggleChip, toggle_chip
    for text in ("OpenAI", "DeepSeek", "Anthropic", "ElevenLabs", "Auto-Apply"):
        chip = toggle_chip(text)
        needed = (chip.fontMetrics().horizontalAdvance(text)
                  + ToggleChip._INDICATOR + ToggleChip._GAP)
        assert chip.sizeHint().width() >= needed + 20, text
        assert chip.sizeHint().height() >= 44, text


def test_flow_row_sits_buttons_level_with_the_controls(app):
    """A button or checkbox beside a labelled field sits on the field's
    control line, not up beside its caption."""
    from PySide6.QtWidgets import QCheckBox, QComboBox, QPushButton, QWidget
    from ui.forms import field
    from ui.widgets import FlowLayout
    host = QWidget()
    flow = FlowLayout(host, spacing=8)
    box = QComboBox()
    box.setFixedHeight(44)      # the app sheet's control height
    labelled = field("Provider", box)
    button = QPushButton("Refresh")
    button.setFixedHeight(44)
    check = QCheckBox("Auto-Apply")
    for widget in (labelled, button, check):
        flow.addWidget(widget)
    host.resize(800, 200)
    host.show()
    for _ in range(4):
        app.processEvents()
    assert button.geometry().bottom() == labelled.geometry().bottom()
    assert abs(check.geometry().center().y()
               - button.geometry().center().y()) <= 1


def test_flow_spring_pushes_the_last_group_to_the_right_edge(app):
    from PySide6.QtWidgets import QPushButton, QWidget
    from ui.widgets import FlowLayout
    host = QWidget()
    flow = FlowLayout(host, spacing=8)
    left, right = QPushButton("Send"), QPushButton("Export Report")
    flow.addWidget(left)
    flow.add_spring()
    flow.addWidget(right)
    host.resize(600, 100)
    host.show()
    for _ in range(4):
        app.processEvents()
    assert left.x() == 0
    assert right.geometry().right() == host.width() - 1
    assert right.y() == left.y()


def test_fields_do_not_paint_the_page_colour_inside_cards(app):
    from ui.forms import field
    from PySide6.QtWidgets import QLineEdit
    assert field("Direction", QLineEdit()).objectName() == "Transparent"


def test_chat_setup_is_one_grid(app, window):
    """Tool and Command sit over Provider and Model; no colon captions."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QLabel
    _settle(app, window, (1440, 900), "chat")
    origin = window.normal_panel
    x = lambda w: w.mapTo(origin, QPoint(0, 0)).x()
    assert x(window.tool_box) == x(window.provider_box)
    assert x(window.command_box) == x(window.model_box)
    captions = [label.text() for label in window.normal_panel.findChildren(QLabel)
                if label.isVisible() and label.text().rstrip().endswith(":")]
    assert not captions, captions


def test_cloud_permissions_grey_out_under_local_only(app, window):
    _settle(app, window, (1440, 900), "chat")
    mode = window.execution_mode_box
    saved = mode.currentText()
    try:
        mode.setCurrentText("Local only")
        assert not any(chip.isEnabled() for chip in window.cloud_permission_chips)
        assert "Local only" in window.cloud_permission_note.text()
        # Paid media is not routed by Mode and stays live.
        assert window.allow_higgsfield_checkbox.isEnabled()
        mode.setCurrentText("Hybrid allowed")
        assert all(chip.isEnabled() for chip in window.cloud_permission_chips)
        assert window.cloud_permission_note.text().endswith("allowed")
    finally:
        mode.setCurrentText(saved)


def test_an_empty_next_step_banner_is_hidden(app, window, monkeypatch):
    """An empty NextStepBanner was a bare teal bar above Book Profile."""
    _settle(app, window, (1440, 900), "author")
    label = window.author_panel.author_next_step_label
    monkeypatch.setattr(window, "_compute_next_step_tip", lambda: "")
    window._refresh_next_step_tip()
    assert label.isHidden()
    monkeypatch.setattr(window, "_compute_next_step_tip", lambda: "Save a draft")
    window._refresh_next_step_tip()
    assert not label.isHidden()
    assert label.text().endswith("Save a draft")


def test_no_button_or_tab_label_has_a_lone_ampersand(app, window):
    """Qt reads one "&" as a mnemonic marker, swallows it and underlines the
    next letter: "Songs & Albums" drew as "Songs _Albums"."""
    import re
    from PySide6.QtWidgets import QAbstractButton, QTabWidget
    lone = re.compile(r"(?<!&)&(?!&)")
    offenders = [button.text() for button in window.findChildren(QAbstractButton)
                 if lone.search(button.text() or "")]
    for tabs in window.findChildren(QTabWidget):
        offenders += [tabs.tabText(i) for i in range(tabs.count())
                      if lone.search(tabs.tabText(i))]
    assert not offenders, offenders
