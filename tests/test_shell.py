"""The Manuscript shell against the real window (spec manuscript-redesign,
slice 1: measures 4, 5 and 7; Design S2–S11; ADR 0006).

Fit at the three sizes in a light and a dark theme, the top bar's collapse
order, the drawer's motion under the calm rule, the keyboard map, accessible
names, the states S11 lists, and the theme switch while Booth plays.
"""

import pytest

from ui import motion, theme
from ui.shell.chips import COMPACT, FULL, SHORT, status_state

SIZES = [(1000, 600), (1440, 900), (1500, 950)]
THEMES = [theme.LIGHT_GREEN, theme.GREEN]
LONG_PROJECT = "A Very Long Project Name For Testing"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(qapp):
    from PySide6.QtWidgets import QMessageBox
    import main

    saved = (QMessageBox.warning, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        built = main.GodAI()
        built.resize(1440, 900)
        built.show()
        _settle(qapp)
        yield built
    finally:
        QMessageBox.warning, QMessageBox.information = saved
        theme.set_current(theme.DEFAULT)
        built.resource_timer.stop()
        qapp.removeEventFilter(built)
        built.hide()


def _settle(qapp, rounds=8):
    for _ in range(rounds):
        qapp.processEvents()


def _long_values(window):
    """S3's worst case: a long project name, a four-figure spend, a status
    with a two-digit badge."""
    combo = window.history_project_filter
    combo.blockSignals(True)
    if combo.findText(LONG_PROJECT) < 0:
        combo.addItem(LONG_PROJECT, "__test_long__")
    combo.setCurrentIndex(combo.findText(LONG_PROJECT))
    combo.blockSignals(False)
    window.spend_chip.refresh(1234.56, 5000, 0)
    window.agent_status_pill.set_state(status_state(None, "warning", False, 12))


def _reset_values(window):
    combo = window.history_project_filter
    combo.blockSignals(True)
    index = combo.findText(LONG_PROJECT)
    if index >= 0:
        combo.removeItem(index)
    combo.setCurrentIndex(0)
    combo.blockSignals(False)
    window.update_usage_labels()
    window.refresh_status_chip()


# ── Measure 4: fit ───────────────────────────────────────────────────

@pytest.mark.parametrize("name", THEMES)
@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("agent", ["author", "audiobook", "video"])
def test_the_shell_fits_at_every_size(qapp, window, size, name, agent):
    from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget
    from ui.text_fit import clipped_text

    theme.set_current(name)
    window.apply_global_style()
    window.select_agent(agent)
    window.resize(*size)
    _long_values(window)
    window.top_bar.fitter.fit()
    _settle(qapp)
    try:
        assert window.size().width() == size[0]

        rail = window.workspace_tabs
        for button in (*rail.buttons, rail.help_btn, rail.settings_btn,
                       rail.app_mark):
            assert button.isVisible()
            assert rail.rect().contains(button.geometry()), button.accessibleName()

        bar = window.top_bar
        children = [w for w in (bar.switch, bar.agent_label,
                                bar.project_selector, bar.project_button,
                                bar.history_button, bar.spend_chip,
                                bar.status_chip) if w.isVisible()]
        for widget in children:
            assert bar.rect().contains(widget.geometry()), type(widget).__name__
        ordered = sorted(children, key=lambda w: w.geometry().left())
        for left, right in zip(ordered, ordered[1:]):
            assert left.geometry().right() < right.geometry().left(), (
                f"{type(left).__name__} overlaps {type(right).__name__}")

        # Chips are painted to their own measure: never narrower than it.
        assert bar.spend_chip.width() >= bar.spend_chip.width_for(
            bar.spend_chip.form)
        assert bar.status_chip.width() >= bar.status_chip.width_for(
            bar.status_chip.compact)
        # The money figure never disappears.
        assert "1234.56" in bar.spend_chip.text()
        # The selector elides by design (S3 #2) and stays 140–260 px; its
        # full name is on hover (text_fit) and in its tooltip.
        assert 140 <= bar.project_selector.width() <= 260

        window.history_drawer.open_drawer(animate=False)
        _settle(qapp, 4)
        cut = [clipped_text(w) for w in window.history_drawer.findChildren(QWidget)
               if isinstance(w, (QComboBox, QLineEdit)) and w.isVisible()
               and clipped_text(w)]
        window.history_drawer.close_drawer()
        assert not cut, cut
        assert window.history_drawer.width() == 320

        for opener, popover in ((window.open_spend_popover, window.spend_popover),
                                (window.open_status_popover, window.status_popover)):
            opener()
            _settle(qapp, 4)
            cut = [clipped_text(w) for w in popover.findChildren(QWidget)
                   if isinstance(w, (QComboBox, QLineEdit)) and w.isVisible()
                   and clipped_text(w)]
            popover.hide()
            assert not cut, cut
    finally:
        _reset_values(window)
        window.history_drawer.close_drawer()
        _settle(qapp, 4)


def test_the_collapse_steps_happen_in_order(qapp, window):
    """S3: as the bar narrows, each step only after the one before it."""
    window.select_agent("author")              # the switch is showing
    _long_values(window)
    fitter = window.top_bar.fitter
    seen = []
    try:
        for width in range(1500, 999, -20):
            window.resize(width, 700)
            fitter.fit()
            _settle(qapp, 2)
            level = fitter.level
            seen.append(level)
            bar = window.top_bar
            # Every step at or below the level is in force, none above it.
            assert (bar.spend_chip.form != FULL) == (level >= 1)
            assert (bar.project_selector.maximumWidth() == 140) == (level >= 2)
            assert bar.status_chip.compact == (level >= 3)
            assert (bar.spend_chip.form == COMPACT) == (level >= 4)
            assert bool(bar.switch.property("tight")) == (level >= 5)
            assert fitter.required(level) <= bar.width() - 32 or level == 5
        assert seen == sorted(seen), seen
        # And back: widening undoes them.
        window.resize(1500, 950)
        fitter.fit()
        _settle(qapp, 2)
        assert fitter.level <= seen[0]
    finally:
        _reset_values(window)
        window.resize(1440, 900)
        _settle(qapp, 2)


def test_short_form_drops_today_first(window):
    window.spend_chip.refresh(12.34, 50, 0)
    try:
        window.spend_chip.set_form(SHORT)
        assert window.spend_chip.text() == "€12.34 of €50"
    finally:
        window.spend_chip.set_form(FULL)
        window.update_usage_labels()


# ── Measure 5: money, in the window ──────────────────────────────────

def test_the_spend_chip_reads_the_usage_tally(qapp, window, monkeypatch):
    tracker = window.usage_tracker
    monkeypatch.setattr(tracker, "get_today_total", lambda: 1.2)
    monkeypatch.setattr(tracker, "get_unpriced_requests_today", lambda: 2)
    window.refresh_spend_chip()
    assert window.spend_chip.text().startswith("€1.20 + unknown")
    assert window.unpriced_note.isVisibleTo(window.spend_popover)
    assert "2 requests had no price" in window.unpriced_note.text()

    monkeypatch.setattr(tracker, "get_today_total", lambda: 0.0)
    window.refresh_spend_chip()
    assert "€0.00" not in window.spend_chip.text()
    assert window.spend_chip.text().startswith("Unknown")

    saved = window.daily_budget_eur
    monkeypatch.setattr(tracker, "get_unpriced_requests_today", lambda: 0)
    try:
        window.daily_budget_eur = 0.0
        window.refresh_spend_chip()
        assert window.spend_chip.text().endswith("today · no limit")
        window.daily_budget_eur = 5.0
        monkeypatch.setattr(tracker, "get_today_total", lambda: 5.1)
        window.refresh_spend_chip()
        assert window.spend_chip.property("tone") == "danger"
    finally:
        window.daily_budget_eur = saved
        monkeypatch.undo()
        window.refresh_spend_chip()


def test_closing_the_spend_popover_commits_a_limit_being_edited(qapp, window,
                                                               monkeypatch):
    calls = []
    monkeypatch.setattr(window, "_commit_budget_limits",
                        lambda *a: calls.append(1))
    window.open_spend_popover()
    _settle(qapp, 2)
    window.spend_popover.hide()
    _settle(qapp, 4)
    assert calls, "the close did not commit"


# ── Measure 7: the drawer under the calm rule ───────────────────────

@pytest.fixture
def motion_allowed(monkeypatch):
    monkeypatch.setattr(motion, "system_reduce_motion", lambda: False)
    monkeypatch.setattr(motion, "in_app_setting", lambda: False)


def _wait_idle(qapp, ms=1500):
    from PySide6.QtCore import QElapsedTimer
    clock = QElapsedTimer()
    clock.start()
    while motion.running() and clock.elapsed() < ms:
        qapp.processEvents()


def test_opening_the_drawer_starts_exactly_one_short_animation(
        qapp, window, motion_allowed):
    drawer = window.history_drawer
    try:
        assert motion.running() == []
        drawer.open_drawer()
        running = motion.running()
        assert len(running) == 1
        assert running[0].duration() <= motion.MAX_MS
        assert running[0].loopCount() == 1
        _wait_idle(qapp)
        assert motion.running() == []
        assert drawer.isVisible() and drawer.x() == 0
        # Focus went into the drawer first, so nothing typed moves. (The
        # window's own focus child: offscreen may not activate the window.)
        assert window.focusWidget() is window.history_search
    finally:
        drawer.close_drawer()
        _wait_idle(qapp)
    assert not drawer.isVisible()
    assert window.focusWidget() is window.history_btn


def test_no_animation_when_motion_is_reduced(qapp, window, monkeypatch):
    monkeypatch.setattr(motion, "system_reduce_motion", lambda: False)
    monkeypatch.setattr(motion, "in_app_setting", lambda: True)
    drawer = window.history_drawer
    try:
        drawer.open_drawer()
        assert motion.running() == []
        assert drawer.isVisible() and drawer.progress == 1.0
    finally:
        drawer.close_drawer()
    assert motion.running() == [] and not drawer.isVisible()


def test_hiding_the_drawer_mid_slide_leaves_nothing_running(
        qapp, window, motion_allowed):
    drawer = window.history_drawer
    drawer.open_drawer()
    assert motion.running()
    drawer.hide()
    qapp.processEvents()
    assert motion.running() == []
    assert not drawer.is_open()


def test_nothing_runs_while_a_content_field_has_focus(qapp, window,
                                                      motion_allowed):
    """No ambient motion while someone types; and the drawer, opened over
    the panel with ⌘Y mid-sentence, moves no field (D5, S7)."""
    window.select_agent("chat")
    _settle(qapp, 4)
    window.input_box.setFocus()
    _settle(qapp, 4)
    assert window.focusWidget() is window.input_box
    for _ in range(3):
        qapp.processEvents()
        assert motion.running() == []
    before = window.input_box.mapTo(window, window.input_box.rect().topLeft())
    try:
        window.toggle_history()
        _wait_idle(qapp)
        after = window.input_box.mapTo(window, window.input_box.rect().topLeft())
        assert before == after
        assert window.focusWidget() is window.history_search
    finally:
        window.history_drawer.close_drawer()
        _wait_idle(qapp)


def test_reopening_mid_close_keeps_the_drawer_open(qapp, window,
                                                   motion_allowed):
    """Found in Build: the close slide finished later and hid the drawer
    that had been opened again."""
    drawer = window.history_drawer
    try:
        drawer.open_drawer(animate=False)
        drawer.close_drawer()
        drawer.open_drawer()
        _wait_idle(qapp)
        assert drawer.isVisible() and drawer.is_open()
    finally:
        drawer.close_drawer()
        _wait_idle(qapp)


# ── S9: keyboard ─────────────────────────────────────────────────────

def _shortcut(window, keys):
    from PySide6.QtGui import QKeySequence
    wanted = QKeySequence(keys)
    return next(s for s in window.shell_shortcuts if s.key() == wanted)


def test_the_keyboard_map(qapp, window):
    names = list(window.workspace_tabs._names)
    for index in range(len(names)):
        _shortcut(window, f"Ctrl+{index + 1}").activated.emit()
        _settle(qapp, 2)
        assert window.workspace_tabs.currentIndex() == index

    window.select_agent("author")
    _shortcut(window, "Ctrl+]").activated.emit()
    assert window._current_agent == "manuscript"
    _shortcut(window, "Ctrl+[").activated.emit()
    assert window._current_agent == "author"

    drawer = window.history_drawer
    _shortcut(window, "Ctrl+Y").activated.emit()
    try:
        assert drawer.is_open()
    finally:
        _shortcut(window, "Ctrl+Y").activated.emit()
    assert not drawer.is_open()
    assert window.learning_shortcut.key().toString() == "F1"


def test_escape_closes_the_drawer(qapp, window):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    drawer = window.history_drawer
    drawer.open_drawer(animate=False)
    drawer.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    assert not drawer.is_open()


def test_tab_stays_inside_the_open_drawer(qapp, window):
    drawer = window.history_drawer
    drawer.open_drawer(animate=False)
    _settle(qapp, 2)
    try:
        seen = set()
        for _ in range(8):
            drawer.focusNextPrevChild(True)
            qapp.processEvents()
            focus = qapp.focusWidget()
            if focus is not None:
                assert drawer.isAncestorOf(focus), type(focus).__name__
                seen.add(focus)
        if seen:
            assert len(seen) >= 3
    finally:
        drawer.close_drawer()


# ── Accessible names ─────────────────────────────────────────────────

def test_every_icon_only_control_has_a_name(window):
    rail = window.workspace_tabs
    for index, button in enumerate(rail.buttons):
        assert button.accessibleName() == rail.tabText(index)
        assert button.accessibleDescription()
        assert rail.tabText(index) in rail.tabToolTip(index)
    for widget in (rail.help_btn, rail.settings_btn, window.history_btn,
                   window.project_menu_btn, window.history_drawer.close_btn):
        assert widget.accessibleName(), widget
    assert window.spend_chip.accessibleName().startswith("Spent today:")
    assert window.agent_status_pill.accessibleName().startswith("Status:")


def test_the_selected_workspace_says_so(window):
    window.select_agent("video")
    rail = window.workspace_tabs
    selected = rail.buttons[rail.currentIndex()]
    assert selected.isChecked()
    assert selected.accessibleDescription().endswith("(selected)")


# ── S11 states ───────────────────────────────────────────────────────

def test_no_project(qapp, window, monkeypatch):
    assert window.history_project_filter.currentText() == "All projects"
    # On the instance: a class-level patch does not reach the binding's
    # exec, and a real modal menu would wait forever offscreen.
    monkeypatch.setattr(window.project_menu, "exec", lambda *a, **k: None)
    window._open_project_menu()
    assert not window.project_menu_header.isVisible()
    window.update_usage_labels()
    assert not window.project_spend_stat.isVisibleTo(window.spend_popover)


def test_no_chats_says_so(window):
    drawer = window.history_drawer
    if window.history_list.count() == 0:
        assert drawer.empty_label.isVisibleTo(drawer)
        assert window.new_chat_btn.isVisibleTo(drawer)
    window.history_list.addItem("a chat")
    try:
        assert not drawer.empty_label.isVisibleTo(drawer)
    finally:
        window.history_list.takeItem(window.history_list.count() - 1)


@pytest.mark.parametrize("count", [0, 1, 12])
def test_the_model_updates_badge(window, count):
    chip = window.agent_status_pill
    window.model_updates_waiting = count
    try:
        window.refresh_status_chip()
        assert chip.state.count == count
        plain = status_state(None, None, False, 0)
        if count:
            assert chip.width_for(True) > status_chip_width(chip, plain, True)
            assert f"{count} model update" in chip.accessibleName()
        else:
            assert "model update" not in chip.accessibleName()
    finally:
        window.model_updates_waiting = 0
        window.refresh_status_chip()


def status_chip_width(chip, state, compact):
    saved = chip.state
    chip.state = state
    try:
        return chip.width_for(compact)
    finally:
        chip.state = saved


def test_the_status_popover_opens_the_section_that_explains_the_chip(
        qapp, window):
    window.model_updates_waiting = 3
    window.refresh_status_chip()
    try:
        window.open_status_popover()
        _settle(qapp, 2)
        assert window.model_updates_section._expanded
        window.status_popover.hide()
    finally:
        window.model_updates_waiting = 0
        window.refresh_status_chip()


# ── A8: the theme switch while Booth plays ──────────────────────────

@pytest.fixture(scope="module")
def audio_file(tmp_path_factory):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available")
    path = tmp_path_factory.mktemp("audio") / "theme-switch.mp3"
    subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=220:duration=6",
                    "-q:a", "9", str(path), "-y"], capture_output=True, timeout=60)
    if not path.exists():
        pytest.skip("ffmpeg could not produce a test file")
    return path


@pytest.mark.timeout(30)
def test_switching_all_six_themes_while_booth_plays(qapp, window, audio_file,
                                                    monkeypatch):
    """The 2026-10-05 deadlock was QComboBox.setStyle against live FFmpeg
    threads. The switch is set_current + apply_global_style, no setStyle;
    a hang fails fast here instead of wedging the run."""
    import agents.audiobook.audio_player as player_module
    from PySide6.QtWidgets import QComboBox
    from ui.widgets import polish_combo

    monkeypatch.setattr(player_module, "save_position", lambda *a, **k: None)
    window.select_agent("audiobook")
    player = window.audiobook_panel.audiobook_player
    player.load(audio_file, title="Theme switch")
    player.play()
    _settle(qapp, 6)
    try:
        for name in theme.THEMES:
            theme.set_current(name)
            window.apply_global_style()
            _settle(qapp, 2)
            assert theme.accent(name) in window.styleSheet()
        # A combo built while the player holds its source still polishes.
        combo = QComboBox(window)
        polish_combo(combo)
        combo.deleteLater()
    finally:
        player.release()
        _settle(qapp, 4)
        theme.set_current(theme.DEFAULT)
        window.apply_global_style()
