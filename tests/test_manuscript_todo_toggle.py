"""Ticking a Press checklist item saves it at once; only the reload waits.

The reload is deferred (it clears the list, which must not happen inside the
item's own itemChanged) and its timer names the panel as context, so Qt
drops it if the panel is deleted first. The tick itself must not wait on
that timer, or a panel closed in the same event-loop turn loses it (review
of PR #32)."""

import os
import sqlite3

import pytest
from PySide6.QtCore import Qt

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    import main
    return main.GodAI()


def _status(todo_id):
    from services.database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute("SELECT status FROM manuscript_todos WHERE id=?",
                            (todo_id,)).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def todo_id():
    from services.database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    row_id = conn.execute(
        "INSERT INTO manuscript_todos (created_at, updated_at, title) "
        "VALUES ('2026-11-27', '2026-11-27', 'Tick me (test)')").lastrowid
    conn.commit()
    conn.close()
    yield row_id
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM manuscript_todos WHERE id=?", (row_id,))
    conn.commit()
    conn.close()


def _item(panel, todo_id):
    panel.load_todos()
    lst = panel.manuscript_todo_list
    return next(lst.item(r) for r in range(lst.count())
                if lst.item(r).data(Qt.UserRole) == todo_id)


def test_a_tick_is_saved_before_the_event_loop_runs(window, app, todo_id):
    panel = window.manuscript_panel
    _item(panel, todo_id).setCheckState(Qt.Checked)     # emits itemChanged
    assert _status(todo_id) == "done"                   # no event loop yet
    app.processEvents()


def test_the_list_reloads_on_the_next_turn(window, app, todo_id):
    panel = window.manuscript_panel
    item = _item(panel, todo_id)
    item.setCheckState(Qt.Checked)
    assert not item.font().strikeOut()                  # not reloaded yet
    app.processEvents()
    lst = panel.manuscript_todo_list
    reloaded = next(lst.item(r) for r in range(lst.count())
                    if lst.item(r).data(Qt.UserRole) == todo_id)
    assert reloaded.font().strikeOut()
