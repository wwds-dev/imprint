"""The two side rails (spec: docs/specs/side-rails-redesign.md).

Left: project dropdown with an actions button, search with an agent filter
button, saved chats grouped by day, New Chat. Right: budgets whose limit is
the field, a plain list of figures, Activity rows, Status sections that say
their state while closed. Run headless.
"""

import json
from datetime import date, datetime

import pytest


def _dispose(widget):
    """Delete a top-level test widget now rather than leaving it to the
    collector: freed inside a later gc.collect(), its children are destroyed
    while the app-wide dropdown and text-fit filters still see their events
    (the suite's intermittent segfault; see tests/test_webdesign_panel.py)."""
    from PySide6.QtCore import QCoreApplication, QEvent
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(scope="module")
def app():
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
        w.resize(1280, 820)
        w.show()
        for _ in range(6):
            app.processEvents()
        yield w
        w.resource_timer.stop()
        app.removeEventFilter(w)
        _dispose(w)
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


# ── pure helpers ─────────────────────────────────────────────────────────────

def test_a_limit_is_shown_as_typed_not_truncated():
    """The rail built its fields with str(int(budget)): 1.5 read "1", and
    committing that field would have saved 1."""
    from ui.rail import format_limit
    assert format_limit(1.0) == "1"
    assert format_limit(1.5) == "1.5"
    assert format_limit(0.25) == "0.25"
    assert format_limit(0) == "0"
    # Lossless: committing one field saves both, so a rounded display of
    # the other would quietly become the cap (code review P2).
    for value in (1234.567, 12345.67, 0.1234567, 1000000.0):
        assert float(format_limit(value)) == value
    assert format_limit(1000000.0) == "1000000"


def test_a_chat_is_dated_by_its_stamp_then_its_name_then_its_file():
    from ui.rail import chat_when
    stamp = datetime(2026, 11, 24, 14, 2, 5)
    assert chat_when("x.json", {"timestamp": "2026-11-24_14-02-05"}) == stamp
    assert chat_when("2026-11-24_14-02-05_ab12cd34.json", {}) == stamp
    assert chat_when("project.json", {}, stamp.timestamp()) == stamp
    assert chat_when("project.json", {"timestamp": "soon"}) is None


def test_chats_fall_under_today_yesterday_or_earlier():
    from ui.rail import day_group
    today = date(2026, 11, 24)
    assert day_group(datetime(2026, 11, 24, 0, 0, 1), today) == "Today"
    assert day_group(datetime(2026, 11, 23, 23, 59), today) == "Yesterday"
    assert day_group(datetime(2026, 11, 22, 12, 0), today) == "Earlier"
    assert day_group(None, today) == "Earlier"
    # A clock set back must not invent a fourth group.
    assert day_group(datetime(2026, 11, 25, 9, 0), today) == "Today"


# ── widgets ──────────────────────────────────────────────────────────────────

def test_the_filter_button_keeps_the_combo_surface_the_list_uses(app):
    from ui.rail import MenuFilterButton
    button = MenuFilterButton("All agents", "Filter", label_for=str.upper)
    heard = []
    button.currentTextChanged.connect(heard.append)

    button.set_options(["All agents", "audiobook", "chat"])
    assert button.currentText() == "All agents" and heard == []
    assert not button.property("active")

    button.setCurrentText("audiobook")
    assert button.currentText() == "audiobook" and heard == ["audiobook"]
    assert button.property("active")
    assert "AUDIOBOOK" in button.toolTip()

    button.setCurrentText("audiobook")          # no change, no signal
    button.setCurrentText("nobody")             # not an option, ignored
    assert heard == ["audiobook"]

    # Repopulating keeps a choice that survives and says nothing.
    button.set_options(["All agents", "audiobook"])
    assert button.currentText() == "audiobook" and heard == ["audiobook"]
    # A choice whose chats are gone falls back, still without a signal:
    # the caller is the list refresh, and a signal would recurse into it.
    button.set_options(["All agents", "chat"])
    assert button.currentText() == "All agents" and heard == ["audiobook"]
    assert not button.property("active")

    menu = button.build_menu()
    assert [a.text() for a in menu.actions()] == ["All agents", "CHAT"]
    assert [a.isChecked() for a in menu.actions()] == [True, False]


def test_icon_buttons_carry_no_qt_menu_so_the_icon_stays_centred(app):
    """setMenu() makes Qt reserve room for a menu indicator; the icon then
    sits left of centre. These buttons open their menu on click instead."""
    from ui.forms import icon_button
    from ui.rail import MenuFilterButton
    for button in (icon_button("more", "Project actions"),
                   MenuFilterButton("All", "Filter")):
        assert button.menu() is None
        assert not button.icon().isNull()
        assert button.text() == ""
        assert button.width() == button.height()


def test_a_day_heading_is_drawn_once_per_day_and_is_not_an_item(app):
    from PySide6.QtWidgets import QListWidget, QListWidgetItem
    from ui.rail import DAY_ROLE, ChatRowDelegate
    view = QListWidget()
    view.setItemDelegate(ChatRowDelegate(view))
    assert isinstance(__import__("ui.rail").rail.ChatList().itemDelegate(),
                      ChatRowDelegate)
    for day in ("Today", "Today", "Yesterday", "Earlier", "Earlier"):
        item = QListWidgetItem("chat")
        item.setData(DAY_ROLE, day)
        view.addItem(item)
    model = view.model()
    headings = [ChatRowDelegate.heading(model.index(r, 0)) for r in range(5)]
    assert headings == ["Today", "", "Yesterday", "Earlier", ""]
    assert view.count() == 5
    delegate = view.itemDelegate()
    tall = delegate.sizeHint(None, model.index(0, 0))
    plain = delegate.sizeHint(None, model.index(1, 0))
    assert tall.height() == plain.height() + ChatRowDelegate.HEADER_HEIGHT
    assert tall.width() == 0        # rows never ask for a sideways scrollbar


def test_a_budget_refresh_never_overwrites_the_limit_being_typed(app):
    from ui.rail import BudgetRow
    row = BudgetRow("Session", "1")
    row.limit_input.setText("2.5")
    row.set(0.5, 1.0)
    assert row.limit_input.text() == "2.5"
    assert row.value_label.text() == "€0.50"
    assert row.bar.value() == 50 and not row.bar.property("over")
    row.set(3.0, 1.0)
    assert row.bar.value() == 100 and row.bar.property("over")
    row.set(3.0, 0.0)               # no cap is not "fully spent"
    assert row.bar.value() == 0 and not row.bar.property("over")


def test_a_closed_section_says_its_state(app):
    from ui.widgets import CollapsibleSection
    section = CollapsibleSection("API keys", expanded=False)
    assert section.summary_label.isHidden()
    section.set_summary("4 of 6", "warning")
    assert section.summary_label.text() == "4 of 6"
    assert section.summary_label.property("tone") == "warning"
    assert not section.summary_label.isHidden()
    assert "API keys" in section.header_btn.text()
    assert "4 of 6" not in section.header_btn.text()


def test_a_count_in_a_title_moves_to_the_pill_and_the_title_stays_whole(app):
    from ui.widgets import CollapsibleSection
    section = CollapsibleSection("Model updates", summary_from_title=True)
    assert section.summary_label.isHidden()
    section.set_title("Model updates · 1 new · 1 warning")
    assert section._title == "Model updates · 1 new · 1 warning"
    assert section.header_btn.accessibleName() == "Model updates · 1 new · 1 warning"
    assert section.header_btn.text().endswith("Model updates")
    assert section.summary_label.text() == "1 new · 1 warning"
    assert section.summary_label.property("tone") == "warning"
    section.set_title("Model updates · 2 new")
    assert section.summary_label.property("tone") == "accent"
    # Other sections keep their titles as written.
    plain = CollapsibleSection("Finance · Business")
    assert plain.header_btn.text().endswith("Finance · Business")
    assert plain.summary_label.isHidden()


def test_a_long_summary_never_sits_on_the_title(app):
    """Code review P2: in the 204px rail header "1 new · 1 warning" covered
    the last letters of "Model updates"."""
    from ui.widgets import CollapsibleSection
    section = CollapsibleSection("Model updates", summary_from_title=True)
    section.setFixedWidth(204)
    section.show()
    section.set_title("Model updates · 1 new · 1 warning")
    for _ in range(4):
        app.processEvents()
    header, pill = section.header_btn, section.summary_label
    title_end = 10 + header.fontMetrics().horizontalAdvance(header.text())
    assert pill.geometry().left() >= title_end, (pill.geometry(), title_end)
    assert pill.text() == "1 new +1"                # shortened to fit
    assert pill.property("tone") == "warning"       # still says there is one
    assert "1 new · 1 warning" in header.toolTip()  # whole on hover
    # With room, nothing is shortened and there is no tooltip to need.
    section.setFixedWidth(420)
    for _ in range(4):
        app.processEvents()
    assert pill.text() == "1 new · 1 warning" and header.toolTip() == ""
    _dispose(section)


def test_a_click_on_a_day_heading_opens_nothing(app):
    """Code review P3: the heading is painted inside the first row of its
    day, so clicking it opened the chat underneath."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QListWidgetItem
    from ui.rail import DAY_ROLE, ChatList, ChatRowDelegate
    view = ChatList()
    view.resize(184, 300)
    for day in ("Today", "Today"):
        item = QListWidgetItem("chat")
        item.setData(DAY_ROLE, day)
        view.addItem(item)
    view.show()
    for _ in range(4):
        app.processEvents()
    clicked = []
    view.itemClicked.connect(clicked.append)
    top = view.visualRect(view.model().index(0, 0)).top()
    heading = QPoint(40, top + ChatRowDelegate.HEADER_HEIGHT // 2)
    row = QPoint(40, top + ChatRowDelegate.HEADER_HEIGHT + 10)
    assert view.on_heading(heading) and not view.on_heading(row)
    view.setCurrentItem(view.item(1))
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=heading)
    QTest.mouseDClick(view.viewport(), Qt.LeftButton, pos=heading)
    assert clicked == [] and view.currentItem() is view.item(1)
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=row)
    assert clicked == [view.item(0)]
    _dispose(view)


def test_the_key_card_counts_configured_keys(app):
    from ui.status_cards import ApiKeysStatusCard
    card = ApiKeysStatusCard(("OpenAI", "Gemini", "Qwen"))
    heard = []
    card.summary_changed.connect(lambda text, tone: heard.append((text, tone)))
    card.set_status("OpenAI", "available")
    card.set_status("Gemini", "not set")
    assert heard[-1] == ("1 of 3", "")
    card.set_status("Qwen", "unknown")
    assert heard[-1] == ("1 of 3", "warning")


def test_the_system_card_reports_its_worst_reading_once(app):
    from ui.status_cards import ResourceStatusCard
    card = ResourceStatusCard()
    heard = []
    card.summary_changed.connect(lambda text, tone: heard.append((text, tone)))

    def snapshot(ram="green", cpu="green", swap="green", battery="green"):
        return {
            "ram_percent": 10, "ram_level": ram, "ram_used_gb": 1,
            "ram_available_gb": 7, "cpu_percent": 5, "cpu_level": cpu,
            "swap_percent": 0, "swap_level": swap, "swap_used_gb": 0,
            "swap_total_gb": 1, "battery_percent": 80,
            "battery_level": battery, "battery_note": "",
        }

    card.set_snapshot(snapshot())
    card.set_snapshot(snapshot())               # every second: no repeat
    assert heard == [("OK", "")]
    card.set_snapshot(snapshot(cpu="yellow"))
    card.set_snapshot(snapshot(cpu="yellow", swap="red"))
    assert heard[1:] == [("Busy", "warning"), ("Stressed", "danger")]
    card.set_snapshot(snapshot(battery="red"))  # a low battery is not load
    assert heard[-1] == ("OK", "")


# ── the window ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("size", [(1900, 1200), (1280, 820), (1000, 600)],
                         ids=lambda s: f"{s[0]}x{s[1]}")
def test_every_left_rail_control_ends_inside_the_rail(app, window, size):
    """The dropdown beside the actions button once asked for the whole row
    and pushed the button 29px past the rail's edge."""
    from PySide6.QtWidgets import (
        QAbstractButton, QComboBox, QLineEdit, QListWidget, QScrollArea, QWidget)
    window.resize(*size)
    for _ in range(6):
        app.processEvents()
    rail = window.findChild(QWidget, "RailLeft")
    viewport = rail.findChild(QScrollArea).viewport()
    clipped = []
    for child in rail.findChild(QScrollArea).widget().findChildren(QWidget):
        if not isinstance(child, (QLineEdit, QComboBox, QAbstractButton, QListWidget)):
            continue
        if not child.isVisible():
            continue
        right = child.mapTo(viewport, child.rect().topRight()).x()
        if right > viewport.width():
            clipped.append(f"{type(child).__name__} ends at {right}px "
                           f"in a {viewport.width()}px rail")
    assert not clipped, "; ".join(clipped)


def test_no_rail_field_shows_a_cut_off_value_at_rest(app, window):
    from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget
    from ui.text_fit import clipped_text
    window.resize(1280, 820)
    for _ in range(6):
        app.processEvents()
    cut = []
    for name in ("RailLeft", "RailRight"):
        rail = window.findChild(QWidget, name)
        for child in rail.findChildren(QWidget):
            if isinstance(child, (QComboBox, QLineEdit)) and child.isVisible():
                if clipped_text(child):
                    cut.append(f"{name}: {clipped_text(child)!r}")
    assert not cut, cut
    assert window.history_project_filter.currentText() == "All projects"


def test_the_chat_list_groups_by_day_and_stays_a_list_of_chats(
        app, window, tmp_path, monkeypatch):
    import main
    from PySide6.QtCore import Qt
    from ui.rail import AGENT_ROLE, DAY_ROLE, TITLE_ROLE

    def write(name, agent, stamp=None, title=None, prompt="hello there"):
        payload = {"agent": agent, "response": "ok",
                   "messages": [{"role": "user", "content": prompt}]}
        if stamp:
            payload["timestamp"] = stamp
        if title:
            payload["title"] = title
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")

    now = datetime.now()
    today = now.strftime("%Y-%m-%d") + "_00-00-01"
    write("2020-01-01_10-00-00_aaaaaaaa.json", "audiobook",
          "2020-01-01_10-00-00", prompt="novel.epub")
    write(f"{today}_bbbbbbbb.json", "chat", today, title="My named chat")
    write("2020-01-02_10-00-00_cccccccc.json", "nobody-knows",
          "2020-01-02_10-00-00")
    monkeypatch.setattr(main, "CHATS_DIR", tmp_path)
    window.history_search.clear()
    window.history_agent_filter.setCurrentText(main.ALL_AGENTS_FILTER)
    window.history_project_filter.setCurrentIndex(0)
    window.load_history_list()

    rows = [window.history_list.item(i) for i in range(window.history_list.count())]
    assert len(rows) == 3                       # headings are not items
    assert [r.data(DAY_ROLE) for r in rows] == ["Today", "Earlier", "Earlier"]
    assert all(r.data(Qt.UserRole) for r in rows)
    # A stored title is shown whole; a generated one loses its "agent: "
    # prefix, because the agent has its own column.
    assert rows[0].data(TITLE_ROLE) == "My named chat"
    assert rows[2].text() == "audiobook: novel.epub"
    assert rows[2].data(TITLE_ROLE) == "novel.epub"
    assert rows[2].data(AGENT_ROLE) == main.AGENTS_BY_KEY["audiobook"].label
    assert rows[1].data(AGENT_ROLE) == "Nobody-Knows"
    assert "novel.epub" in rows[2].toolTip() and "2020" in rows[2].toolTip()
    assert (window.history_list.horizontalScrollBarPolicy()
            == Qt.ScrollBarAlwaysOff)

    # The filter offers the agents that have chats, and filtering still works.
    assert window.history_agent_filter.options() == [
        main.ALL_AGENTS_FILTER, "audiobook", "chat", "nobody-knows"]
    window.history_agent_filter.setCurrentText("audiobook")
    assert window.history_list.count() == 1
    window.history_agent_filter.setCurrentText(main.ALL_AGENTS_FILTER)
    assert window.history_list.count() == 3


def test_project_actions_live_in_one_menu(window):
    labels = [a.text() for a in window.project_menu.actions()]
    assert labels == ["New Project", "Project Overview", "Save Current Setup"]
    assert window.new_project_btn.isEnabled()
    # The two that act on a project wait for one.
    assert not window.project_overview_btn.isEnabled()
    assert not window.project_defaults_btn.isEnabled()
    assert window.project_menu_btn.menu() is None
    assert not hasattr(window, "delete_chat_btn")
    assert not hasattr(window, "save_budget_btn")


@pytest.fixture
def limits(window):
    """Run a test against known limits and put the session's back."""
    from services.database import get_setting, save_setting
    from ui.rail import format_limit
    before = (window.session_budget_eur, window.daily_budget_eur,
              get_setting("session_budget_eur"), get_setting("daily_budget_eur"))
    window.session_budget_eur, window.daily_budget_eur = 1.0, 5.0
    window.session_budget_input.setText("1")
    window.daily_budget_input.setText("5")
    yield window
    window.session_budget_eur, window.daily_budget_eur = before[0], before[1]
    window.session_budget_input.setText(format_limit(before[0]))
    window.daily_budget_input.setText(format_limit(before[1]))
    for key, value in (("session_budget_eur", before[2]),
                       ("daily_budget_eur", before[3])):
        if value is not None:
            save_setting(key, value)


def _boxes(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    for kind in ("warning", "information"):
        monkeypatch.setattr(
            QMessageBox, kind,
            staticmethod(lambda _p, title, _m, *a, _k=kind, **k:
                         shown.append((_k, title))))
    return shown


def test_committing_a_new_limit_saves_it_without_a_dialog(limits, monkeypatch):
    from services.database import get_setting
    shown = _boxes(monkeypatch)
    limits.session_budget_input.setText("2.5")
    limits.session_budget_input.editingFinished.emit()
    assert limits.session_budget_eur == 2.5 and limits.daily_budget_eur == 5.0
    assert get_setting("session_budget_eur") == "2.5"
    assert shown == []
    assert limits.session_budget_input.text() == "2.5"


def test_leaving_an_unchanged_limit_saves_and_says_nothing(limits, monkeypatch):
    shown = _boxes(monkeypatch)
    saves = []
    monkeypatch.setattr(limits, "save_budget_limits",
                        lambda **k: saves.append(k) or True)
    limits.session_budget_input.setText("1.0")      # the same limit, retyped
    limits.session_budget_input.editingFinished.emit()
    limits.daily_budget_input.editingFinished.emit()
    assert saves == [] and shown == []


@pytest.mark.parametrize("bad", ["inf", "nan", "-1", "five", ""])
def test_a_bad_limit_is_refused_aloud_and_put_back(limits, monkeypatch, bad):
    from services.database import get_setting
    before = get_setting("daily_budget_eur")
    shown = _boxes(monkeypatch)
    limits.session_budget_input.setText("3")        # valid, but its row-mate is not
    limits.daily_budget_input.setText(bad)
    limits.daily_budget_input.editingFinished.emit()
    assert (limits.session_budget_eur, limits.daily_budget_eur) == (1.0, 5.0)
    assert get_setting("daily_budget_eur") == before
    assert shown == [("warning", "Invalid Budget")]
    # The rail never shows a cap that is not the one being applied.
    assert limits.session_budget_input.text() == "1"
    assert limits.daily_budget_input.text() == "5"


def test_the_explicit_save_still_announces_itself(limits, monkeypatch):
    """Settings and older callers use save_budget_limits() directly."""
    shown = _boxes(monkeypatch)
    limits.daily_budget_input.setText("6")
    assert limits.save_budget_limits() is True
    assert shown == [("information", "Budget Saved")]
    assert limits.daily_budget_eur == 6.0


def test_the_status_sections_start_with_a_state(window):
    from ui.widgets import CollapsibleSection
    rail = window.findChild(__import__("PySide6.QtWidgets").QtWidgets.QWidget,
                            "RailRight")
    sections = {s._title.split(" · ")[0]: s
                for s in rail.findChildren(CollapsibleSection)}
    assert sections["System"].summary_label.text() in ("OK", "Busy", "Stressed")
    assert sections["API keys"].summary_label.text().endswith(" of 6")
    # No request yet: the routing section has nothing to claim.
    assert sections["Chat routing"].summary_label.text() == ""
    window.routing_status_card.set_route("chat", "openai", "gpt-4o")
    assert sections["Chat routing"].summary_label.text() == "openai"
    window.routing_status_card.reset_route()
    assert sections["Chat routing"].summary_label.text() == ""


def test_each_item_sits_on_the_rail_the_rebalance_spec_gives_it(window):
    """docs/specs/rails-rebalance.md, option B."""
    from PySide6.QtWidgets import QWidget
    left = window.findChild(QWidget, "RailLeft")
    right = window.findChild(QWidget, "RailRight")
    for name in ("cost_history_btn", "run_log_btn", "learn_btn", "project_meter"):
        widget = getattr(window, name)
        assert left.isAncestorOf(widget), f"{name} belongs on the left rail"
        assert not right.isAncestorOf(widget), f"{name} left on the right rail"
    for name in ("session_meter", "daily_meter", "model_updates_section"):
        assert right.isAncestorOf(getattr(window, name)), f"{name} belongs on the right"
    assert not window.model_updates_section.header_btn.isChecked()


def test_the_moved_rows_keep_the_order_the_spec_gives_them(window):
    from PySide6.QtCore import QPoint
    def y(widget):
        return widget.mapTo(window, QPoint(0, 0)).y()
    window.project_meter.show()
    for _ in range(4):
        __import__("PySide6.QtWidgets").QtWidgets.QApplication.processEvents()
    try:
        assert y(window.history_project_filter) < y(window.project_meter) < y(window.history_search)
        assert y(window.new_chat_btn) < y(window.cost_history_btn) \
            < y(window.run_log_btn) < y(window.learn_btn)
    finally:
        window.project_meter.hide()


def test_a_collapsed_model_updates_section_still_shows_its_count(window):
    section = window.model_updates_section
    assert not section.header_btn.isChecked()
    section.set_title("Model updates \u00b7 2 new")
    try:
        assert "2 new" in section.summary_label.text()
        assert section.content.isHidden()
    finally:
        section.set_title("Model updates")
