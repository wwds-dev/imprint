"""The Muse calendar: week view, rescheduling, and export.

Qt-free contract (agents/creator/calendar.py): tolerant ISO parsing that
never guesses at legacy prose, week arithmetic, RFC-5545 ICS export with
undated rows skipped and counted, CSV export preserving raw text.

Panel contract: dated items land in the right weekday column carrying
their content id in item data, unparseable rows surface in the Undated
lane, rescheduling is the first UPDATE of scheduled_for and follows the
item to its new week, and selected_content_id() replaces the old
row-order ids list for teaser attach and revenue flows.
"""

import os
from datetime import date, datetime, timedelta

import pytest

from agents.creator import calendar as cal
from services.database import get_connection


# ── Qt-free: parsing and week arithmetic ────────────────────────────────────

def test_parse_scheduled_accepts_iso_and_rejects_prose():
    when, has_time = cal.parse_scheduled("2026-10-02T18:00")
    assert (when, has_time) == (datetime(2026, 10, 2, 18, 0), True)
    assert cal.parse_scheduled("2026-10-02 18:00")[0].hour == 18
    assert cal.parse_scheduled("2026-10-02T18:00:05")[1] is True
    # datetime.isoformat() emits microseconds; the parser must not choke.
    assert cal.parse_scheduled("2026-10-02T18:00:05.123456")[1] is True
    when, has_time = cal.parse_scheduled("2026-10-02")
    assert (when.date(), has_time) == (date(2026, 10, 2), False)
    for prose in ("Friday evening", "next week", "", None, "tomorrow 6pm"):
        assert cal.parse_scheduled(prose) is None


def test_week_helpers():
    assert cal.week_start(date(2026, 10, 1)) == date(2026, 9, 28)  # Thu -> Mon
    assert cal.week_start(date(2026, 9, 28)) == date(2026, 9, 28)
    assert cal.week_label(date(2026, 10, 5)) == "5–11 Oct 2026"
    assert cal.week_label(date(2026, 9, 28)) == "28 Sep – 4 Oct 2026"
    headers = cal.day_headers(date(2026, 9, 28))
    assert len(headers) == 7
    assert headers[0].startswith("Mon") and headers[6].startswith("Sun")


# ── Qt-free: exports ────────────────────────────────────────────────────────

def _rows():
    return [
        {"id": 1, "scheduled_for": "2026-10-02T18:00", "kind": "post",
         "title": "Launch, part one", "status": "draft", "price_usd": 5.0,
         "channel": "feed", "campaign": "launch", "body": "line one\nline two"},
        {"id": 2, "scheduled_for": "2026-10-03", "kind": "teaser",
         "title": "Date-only", "status": "approved", "price_usd": 0.0,
         "channel": "", "campaign": "", "body": ""},
        {"id": 3, "scheduled_for": "Friday evening", "kind": "post",
         "title": "Legacy prose", "status": "draft", "price_usd": 0.0,
         "channel": "", "campaign": "", "body": ""},
    ]


def test_export_ics_writes_dated_events_and_counts_skipped(tmp_path):
    target = tmp_path / "plan.ics"
    written, skipped = cal.export_ics(_rows(), target)
    assert (written, skipped) == (2, 1)
    text = target.read_text(encoding="utf-8")
    assert text.startswith("BEGIN:VCALENDAR")
    assert text.count("BEGIN:VEVENT") == 2
    assert "UID:creator-content-1@imprint" in text
    assert "DTSTART:20261002T180000" in text
    assert "DTSTART;VALUE=DATE:20261003" in text
    # RFC escaping: the comma in the title and the newline in the body.
    assert "Launch\\, part one" in text
    assert "line one\\nline two" in text
    assert "Legacy prose" not in text


def test_export_ics_folds_long_lines(tmp_path):
    rows = [{"id": 9, "scheduled_for": "2026-10-02T09:00", "kind": "post",
             "title": "T" * 200, "status": "draft", "price_usd": 0.0,
             "channel": "", "campaign": "", "body": ""}]
    target = tmp_path / "long.ics"
    cal.export_ics(rows, target)
    for line in target.read_bytes().split(b"\r\n"):
        assert len(line) <= 76, line


def test_export_csv_preserves_every_row_and_raw_text(tmp_path):
    target = tmp_path / "plan.csv"
    assert cal.export_csv(_rows(), target) == 3
    text = target.read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("scheduled_for,")
    assert "Friday evening" in text          # undated rows are not dropped
    assert "Launch, part one" in text.replace('"', "")


# ── the panel week view ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question,
             QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved


@pytest.fixture()
def panel(window, monkeypatch):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO creator_accounts (handle, created_at) "
            "VALUES ('cal-test', '2026-09-29T00:00:00')")
        account_id = conn.execute(
            "SELECT id FROM creator_accounts WHERE handle = 'cal-test'"
        ).fetchone()["id"]
    p = window.creator_panel
    monkeypatch.setattr(
        p, "current_account",
        lambda: {"id": account_id, "handle": "cal-test"})
    monkeypatch.setattr(window, "_active_project", lambda: None)
    p.creator_calendar_scope.setCurrentIndex(0)
    p._calendar_week_start = cal.week_start(date.today())
    p._test_account_id = account_id
    yield p
    with get_connection() as conn:
        conn.execute("DELETE FROM creator_content WHERE account_id = ?",
                     (account_id,))


def _insert(account_id, title, scheduled_for, kind="post"):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO creator_content "
            "(account_id, created_at, scheduled_for, kind, title, body, "
            "price_usd, status) VALUES (?, ?, ?, ?, ?, 'body', 0, 'draft')",
            (account_id, datetime.now().isoformat(timespec="seconds"),
             scheduled_for, kind, title))
        return cursor.lastrowid


def _grid_cell(panel, content_id):
    from PySide6.QtCore import Qt
    grid = panel.creator_calendar_table
    for r in range(grid.rowCount()):
        for c in range(grid.columnCount()):
            item = grid.item(r, c)
            if item is not None and item.data(Qt.UserRole) == content_id:
                return r, c, item
    return None


def test_week_grid_places_items_and_undated_lane(panel):
    monday = cal.week_start(date.today())
    timed_id = _insert(panel._test_account_id, "Timed post",
                       (monday + timedelta(days=1)).isoformat() + "T09:00")
    dated_id = _insert(panel._test_account_id, "Date only",
                       (monday + timedelta(days=3)).isoformat())
    prose_id = _insert(panel._test_account_id, "Legacy", "Friday evening")
    panel.refresh_calendar()

    row, column, item = _grid_cell(panel, timed_id)
    assert column == 1                       # Tuesday
    assert item.text().startswith("09:00")
    _, column, item = _grid_cell(panel, dated_id)
    assert column == 3                       # Thursday
    assert item.text().startswith("—")
    assert _grid_cell(panel, prose_id) is None
    undated = panel.creator_calendar_undated_table
    assert undated.isVisibleTo(panel.creator_calendar_undated_table.parent())
    assert undated.rowCount() == 1
    assert undated.item(0, 0).text() == "Friday evening"
    from PySide6.QtCore import Qt
    assert undated.item(0, 0).data(Qt.UserRole) == prose_id
    # The header names the shown week.
    assert panel.creator_calendar_week_label.text() == cal.week_label(monday)

    # Navigation: nothing scheduled next week; Today brings it back.
    panel._shift_week(1)
    assert _grid_cell(panel, timed_id) is None
    panel._shift_week(0)
    assert _grid_cell(panel, timed_id) is not None


def test_selected_content_id_reads_both_tables(panel):
    monday = cal.week_start(date.today())
    timed_id = _insert(panel._test_account_id, "Pick me",
                       (monday + timedelta(days=2)).isoformat() + "T12:00")
    prose_id = _insert(panel._test_account_id, "Undated pick", "later")
    panel.refresh_calendar()
    assert panel.selected_content_id() is None

    row, column, _item = _grid_cell(panel, timed_id)
    panel.creator_calendar_table.setCurrentCell(row, column)
    assert panel.selected_content_id() == timed_id

    panel.creator_calendar_table.clearSelection()
    panel.creator_calendar_undated_table.setCurrentCell(0, 0)
    assert panel.selected_content_id() == prose_id


def test_reschedule_gives_an_undated_item_its_first_date(panel, monkeypatch):
    prose_id = _insert(panel._test_account_id, "Needs a date", "sometime")
    panel.refresh_calendar()
    panel.creator_calendar_undated_table.setCurrentCell(0, 0)
    target = cal.week_start(date.today()) + timedelta(weeks=1, days=2)
    monkeypatch.setattr(
        panel, "_ask_schedule_datetime",
        lambda *a, **k: target.isoformat() + "T10:30")
    panel.reschedule_selected()
    with get_connection() as conn:
        stored = conn.execute(
            "SELECT scheduled_for FROM creator_content WHERE id = ?",
            (prose_id,)).fetchone()["scheduled_for"]
    assert stored == target.isoformat() + "T10:30"
    # The view followed the item to its new week and placed it Wednesday.
    assert panel._calendar_week_start == cal.week_start(target)
    _row, column, item = _grid_cell(panel, prose_id)
    assert column == 2
    assert item.text().startswith("10:30")
    assert panel.creator_calendar_undated_table.rowCount() == 0


def test_schedule_writes_iso_from_the_picker(panel, monkeypatch):
    panel.creator_output.setPlainText("A drafted post")
    panel._draft_origin = None
    monkeypatch.setattr(
        panel, "_ask_schedule_datetime", lambda *a, **k: "2026-10-06T08:00")
    panel.schedule()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT scheduled_for FROM creator_content "
            "WHERE account_id = ? ORDER BY id DESC LIMIT 1",
            (panel._test_account_id,)).fetchone()
    assert row["scheduled_for"] == "2026-10-06T08:00"
    assert cal.parse_scheduled(row["scheduled_for"]) is not None


def test_export_calendar_reports_skipped_undated(panel, tmp_path,
                                                 monkeypatch):
    monday = cal.week_start(date.today())
    _insert(panel._test_account_id, "Dated",
            monday.isoformat() + "T09:00")
    _insert(panel._test_account_id, "Prose", "whenever")
    target = tmp_path / "plan.ics"
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "Calendar (*.ics)")))
    panel.export_calendar()
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert text.count("BEGIN:VEVENT") == 1
    note = panel.creator_status_label.text()
    assert "[Done]" in note and "1 undated" in note


def test_export_calendar_csv_takes_everything(panel, tmp_path, monkeypatch):
    _insert(panel._test_account_id, "Dated",
            cal.week_start(date.today()).isoformat() + "T09:00")
    _insert(panel._test_account_id, "Prose", "whenever")
    target = tmp_path / "plan.csv"
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "CSV (*.csv)")))
    panel.export_calendar()
    text = target.read_text(encoding="utf-8")
    assert "Dated" in text and "whenever" in text
    assert "Exported 2 items" in panel.creator_status_label.text()


# ── regressions from the adversarial review (2026-09-29) ────────────────────

def test_empty_grid_cell_click_clears_the_undated_selection(panel):
    """The HIGH finding: an itemless grid cell is still a selection and
    must clear the undated lane, or money flows attach to a stale id."""
    monday = cal.week_start(date.today())
    _insert(panel._test_account_id, "Busy Tuesday",
            (monday + timedelta(days=1)).isoformat() + "T09:00")
    _insert(panel._test_account_id, "Busy Tuesday II",
            (monday + timedelta(days=1)).isoformat() + "T10:00")
    prose_id = _insert(panel._test_account_id, "Stale pick", "later")
    panel.refresh_calendar()
    panel.creator_calendar_undated_table.setCurrentCell(0, 0)
    assert panel.selected_content_id() == prose_id
    # Wednesday row 1 exists (depth 2) but holds no item.
    assert panel.creator_calendar_table.item(1, 2) is None
    panel.creator_calendar_table.setCurrentCell(1, 2)
    assert panel.selected_content_id() is None
    assert not (panel.creator_calendar_undated_table
                .selectionModel().hasSelection())


def test_schedule_jumps_to_the_items_week(panel, monkeypatch):
    """A correct-but-empty current week after scheduling reads as failure
    and invites a duplicate."""
    target = cal.week_start(date.today()) + timedelta(weeks=3, days=1)
    panel.creator_output.setPlainText("A future post")
    panel._draft_origin = None
    monkeypatch.setattr(
        panel, "_ask_schedule_datetime",
        lambda *a, **k: target.isoformat() + "T09:00")
    panel.schedule()
    assert panel._calendar_week_start == cal.week_start(target)
    assert panel.creator_calendar_week_label.text() == cal.week_label(
        cal.week_start(target))


def test_export_filter_wins_over_an_unrelated_suffix(panel, tmp_path,
                                                     monkeypatch):
    """Typing "october.plan" with the CSV filter chosen must not silently
    produce ICS (dropping the undated rows the filter promised to keep)."""
    _insert(panel._test_account_id, "Prose entry", "whenever")
    typed = tmp_path / "october.plan"
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(typed), "CSV (*.csv)")))
    panel.export_calendar()
    written = tmp_path / "october.plan.csv"
    assert written.exists()
    assert "Prose entry" in written.read_text(encoding="utf-8")


def test_reschedule_can_keep_an_item_whole_day(panel, monkeypatch):
    prose_id = _insert(panel._test_account_id, "Whole day", "sometime")
    panel.refresh_calendar()
    panel.creator_calendar_undated_table.setCurrentCell(0, 0)
    target = cal.week_start(date.today()) + timedelta(days=4)
    monkeypatch.setattr(
        panel, "_ask_schedule_datetime", lambda *a, **k: target.isoformat())
    panel.reschedule_selected()
    _row, column, item = _grid_cell(panel, prose_id)
    assert column == 4
    assert item.text().startswith("—")     # no invented midnight


def test_ics_dtstamp_is_utc():
    import re
    rows = [{"id": 4, "scheduled_for": "2026-10-02T09:00", "kind": "post",
             "title": "T", "status": "draft", "price_usd": 0.0,
             "channel": "", "campaign": "", "body": ""}]
    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as tmp:
        target = _P(tmp) / "z.ics"
        cal.export_ics(rows, target)
        text = target.read_text(encoding="utf-8")
    assert re.search(r"DTSTAMP:\d{8}T\d{6}Z", text)


def test_csv_export_defuses_formula_cells(tmp_path):
    rows = [{"id": 5, "scheduled_for": "2026-10-02", "kind": "post",
             "title": "=SUM(A1:A9)", "status": "draft", "price_usd": 0.0,
             "channel": "@handle", "campaign": "+launch", "body": "-x"}]
    target = tmp_path / "d.csv"
    cal.export_csv(rows, target)
    text = target.read_text(encoding="utf-8")
    assert "'=SUM(A1:A9)" in text
    assert "'@handle" in text and "'+launch" in text and "'-x" in text


def test_week_labels_are_locale_independent():
    """strftime %b follows the process locale; the hard-coded names
    must not."""
    import locale
    saved = locale.setlocale(locale.LC_TIME)
    try:
        for candidate in ("de_DE.UTF-8", "de_DE", "C"):
            try:
                locale.setlocale(locale.LC_TIME, candidate)
                break
            except locale.Error:
                continue
        assert cal.week_label(date(2026, 10, 5)) == "5–11 Oct 2026"
        assert cal.day_headers(date(2026, 9, 28))[0] == "Mon 28 Sep"
    finally:
        locale.setlocale(locale.LC_TIME, saved)
