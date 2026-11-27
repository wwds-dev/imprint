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
        for left, right in zip(ordered, ordered[1:], strict=False):
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
    a hang fails fast here instead of wedging the run. This test hung once in
    a full Build run, so the decision-8 fallback is in: the player is
    released for the restyle and reloaded where it was."""
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
        # The fallback (decision 8) put the listener back: same book, playing.
        assert player._path == audio_file
        assert player._player.audioOutput() is not None
    finally:
        player.release()
        _settle(qapp, 4)
        theme.set_current(theme.DEFAULT)
        window.apply_global_style()


def test_the_packaged_app_ships_the_shell_icons():
    """The frozen app reads assets/shell/*.svg; Imprint.spec must bundle them."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    spec = (root / "Imprint.spec").read_text(encoding="utf-8")
    assert '("assets/shell", "assets/shell")' in spec
    import main
    icons = {p.stem for p in (root / "assets" / "shell").glob("*.svg")}
    assert set(main.WORKSPACE_ICONS.values()) | {"help", "settings", "history"} <= icons


def test_a_restyle_releases_and_reloads_the_player(qapp, window, audio_file,
                                                   monkeypatch):
    """ADR 0006 decision 8's fallback, step by step: the same position, the
    same playing state, and the sleep timer with the time it had left
    (review P2-2, P2-3)."""
    import agents.audiobook.audio_player as player_module
    from PySide6.QtMultimedia import QMediaPlayer
    monkeypatch.setattr(player_module, "save_position", lambda *a, **k: None)
    player = window.audiobook_panel.audiobook_player
    calls = []
    real_release, real_load = player.release, player.load
    monkeypatch.setattr(player, "release",
                        lambda: calls.append("release") or real_release())
    monkeypatch.setattr(player, "load",
                        lambda *a, **k: calls.append(("load", k.get("resume_ms")))
                        or real_load(*a, **k))
    monkeypatch.setattr(player, "play", lambda: calls.append("play"))
    window.apply_global_style()
    assert calls == []                      # nothing loaded: nothing to do
    real_load(audio_file, title="T", resume_ms=1500)
    # Offscreen playback does not advance, so the engine's answers are set.
    monkeypatch.setattr(player._player, "position", lambda: 4200)
    monkeypatch.setattr(player._player, "playbackState",
                        lambda: QMediaPlayer.PlaybackState.PlayingState)
    player.sleep_box.setCurrentIndex(player.sleep_box.findData(30))
    assert player._sleep_timer.isActive()
    # Twenty of the thirty minutes have passed: a restyle that restarted the
    # timer would read ~30 min again, one that kept it reads ~10 min.
    player._sleep_timer.start(10 * 60_000)
    left_before = player._sleep_timer.remainingTime()
    try:
        window.apply_global_style()
        assert calls == ["release", ("load", 4200), "play"]
        assert player._path == audio_file
        assert player.sleep_box.currentData() == 30
        assert player._sleep_timer.isActive()
        # The time it had left, not a fresh 30 minutes and not Off. Qt's
        # coarse timers may read a few ms past the nominal value.
        left_after = player._sleep_timer.remainingTime()
        assert left_before - 60_000 < left_after <= left_before + 1_000
    finally:
        player._sleep_timer.stop()
        player.sleep_box.setCurrentIndex(0)
        real_release()
        _settle(qapp, 4)


def test_a_failed_restyle_still_reloads_the_player(qapp, window, audio_file,
                                                   monkeypatch):
    """The restyle raising must not leave Booth released (review P2-3)."""
    import agents.audiobook.audio_player as player_module
    monkeypatch.setattr(player_module, "save_position", lambda *a, **k: None)
    player = window.audiobook_panel.audiobook_player
    player.load(audio_file, title="T", resume_ms=0)

    def boom():
        raise RuntimeError("restyle failed")

    monkeypatch.setattr(theme, "repaint", boom)
    try:
        with pytest.raises(RuntimeError, match="restyle failed"):
            window.apply_global_style()
        assert player._path == audio_file
        assert player._player.audioOutput() is not None
    finally:
        player.release()
        _settle(qapp, 4)



# ── Review fixes ─────────────────────────────────────────────────────

def test_the_popover_figures_say_unknown(qapp, window, monkeypatch):
    """Review P1-1: Last request, Session and Today read "Unknown" for an
    unpriced request, not "€0.00"."""
    tracker = window.usage_tracker
    monkeypatch.setattr(tracker, "get_today_total", lambda: 0.0)
    monkeypatch.setattr(tracker, "get_unpriced_requests_today", lambda: 1)
    saved = (window.last_request_unpriced, window.session_unpriced_count,
             window.last_request_cost, window.session_cost_total)
    try:
        window.last_request_cost = 0.0
        window.session_cost_total = 0.0
        window.session_unpriced_count = 0
        window._note_request_price({"cost_type": "unpriced", "cost_eur": 0.0})
        window.update_usage_labels()
        assert window.last_request_stat.value_label.text() == "Unknown"
        assert window.daily_meter.value_label.text() == "Unknown"
        assert window.session_meter.value_label.text() == "Unknown"
        window._note_request_price({"cost_type": "exact", "cost_eur": 0.3})
        window.last_request_cost = 0.3
        window.update_usage_labels()
        assert window.last_request_stat.value_label.text() == "€0.30"
    finally:
        (window.last_request_unpriced, window.session_unpriced_count,
         window.last_request_cost, window.session_cost_total) = saved
        monkeypatch.undo()
        window.update_usage_labels()


def test_reset_session_spend_forgets_the_unknowns(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(window, "refresh_all_recommendations", lambda: None)
    window.session_unpriced_count = 3
    window.reset_session_spend()
    assert window.session_unpriced_count == 0


def test_the_drawer_survives_the_window_being_hidden(qapp, window):
    """Review P2-1: hide the window with History open, show it again; the
    drawer must still be open, its scrim with it, and still close."""
    drawer = window.history_drawer
    drawer.open_drawer(animate=False)
    _settle(qapp, 2)
    window.hide()
    _settle(qapp, 2)
    window.show()
    _settle(qapp, 4)
    try:
        assert drawer.is_open() and drawer.isVisible()
        assert drawer.scrim.isVisible()
        assert window.history_btn.isChecked()
    finally:
        drawer.close_drawer()
        _settle(qapp, 4)
    assert not drawer.is_open()
    assert not window.history_btn.isChecked()


def test_a_closing_drawer_stays_closed_after_a_window_hide(qapp, window,
                                                           motion_allowed):
    """Hidden mid-close, the drawer finishes closing rather than coming back
    half-way across the panel."""
    drawer = window.history_drawer
    drawer.open_drawer(animate=False)
    drawer.close_drawer()                    # a 160 ms slide starts
    window.hide()
    _settle(qapp, 2)
    window.show()
    _settle(qapp, 4)
    assert not drawer.isVisible() and not drawer.scrim.isVisible()
    assert motion.running() == []


# ── QA F1: the collapse order, on a bar narrow enough to need it ─────

@pytest.fixture
def narrow_bar(qapp):
    """A top bar on its own, with S3's long values: the window's 1000 px
    minimum leaves the real bar at level 0, so the steps are driven here."""
    from PySide6.QtWidgets import QComboBox, QPushButton, QToolButton, QWidget
    from ui.shell.chips import SpendChip, StatusChip
    from ui.shell.top_bar import AgentSwitch, TopBar

    from PySide6.QtCore import QSize

    class WideSelector(QComboBox):
        """Asks for 300 px whatever the app-wide dropdown polish did to its
        size policy (that polish runs only once a window exists, so the
        real combo's hint depends on test order)."""

        def sizeHint(self):  # noqa: N802 - Qt API
            return QSize(300, 36)

    host = QWidget()
    switch = AgentSwitch()
    for label in ("Quill", "Press"):
        switch.add_segment(QPushButton(label))
    selector = WideSelector()
    selector.addItem(LONG_PROJECT)
    spend, status = SpendChip(), StatusChip()
    spend.refresh(1234.56, 5000, 0)
    status.set_state(status_state(None, "warning", False, 12))
    project, history = QPushButton("…"), QToolButton()
    bar = TopBar(switch=switch, project_selector=selector,
                 project_button=project, history_button=history,
                 spend_chip=spend, status_chip=status, parent=host)
    host.resize(1200, 56)
    host.show()
    _settle(qapp, 2)
    yield bar
    host.close()
    host.deleteLater()
    _settle(qapp, 2)


def _forms(bar):
    return {
        "spend_short": bar.spend_chip.form != FULL,
        "selector_min": bar.project_selector.maximumWidth() == 140,
        "status_compact": bar.status_chip.compact,
        "spend_compact": bar.spend_chip.form == COMPACT,
        "switch_tight": bool(bar.switch.property("tight")),
    }


def test_the_collapse_steps_come_in_s3_order(qapp, narrow_bar):
    """Each step first appears at a strictly narrower width than the one
    before it, in S3's order, and none is undone while the bar narrows."""
    bar = narrow_bar
    order = ["spend_short", "selector_min", "status_compact",
             "spend_compact", "switch_tight"]
    first_seen = {}
    previous = {name: False for name in order}
    for width in range(1100, 300, -2):
        bar.resize(width, bar.height())
        bar.fitter.fit()
        forms = _forms(bar)
        for name in order:
            assert not (previous[name] and not forms[name]), (
                f"{name} undone at {width}px")
            if forms[name] and name not in first_seen:
                first_seen[name] = width
        previous = forms
        # The money figure never disappears.
        assert "1234.56" in bar.spend_chip.text()
    assert list(first_seen) == order, first_seen
    widths = [first_seen[name] for name in order]
    assert widths == sorted(widths, reverse=True) and len(set(widths)) == 5, (
        first_seen)
    assert bar.fitter.level == bar.fitter.LEVELS - 1

    # Widening undoes them all.
    bar.resize(1100, bar.height())
    bar.fitter.fit()
    assert bar.fitter.level == 0 and not any(_forms(bar).values())


def test_each_level_fits_where_it_is_chosen(qapp, narrow_bar):
    bar = narrow_bar
    for width in range(1100, 300, -10):
        bar.resize(width, bar.height())
        bar.fitter.fit()
        level = bar.fitter.level
        room = width - 2 * bar.fitter._padding()   # padding follows the window
        if level < bar.fitter.LEVELS - 1:
            assert bar.fitter.required(level) <= room, (width, level)
        if level > 0:
            # It collapsed only because the level above did not fit.
            assert bar.fitter.required(level - 1) > room, (width, level)


def test_hiding_the_open_drawer_directly_unchecks_history(qapp, window):
    """QA F2 (mutant M24): a direct hide of the open drawer reports it closed,
    so the History button is not left checked."""
    drawer = window.history_drawer
    closed = []
    drawer.closed.connect(lambda: closed.append(1))
    drawer.open_drawer(animate=False)
    _settle(qapp, 2)
    assert window.history_btn.isChecked()
    drawer.hide()
    _settle(qapp, 2)
    assert closed == [1]
    assert not drawer.is_open()
    assert not window.history_btn.isChecked()
    assert not drawer.scrim.isVisible()
