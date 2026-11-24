"""
Quill keeps a Draft written with no Project, and asks before Clear
=================================================================
Spec: docs/specs/quill-unfiled-and-clear.md (audit UX-01, UX-02).
Type: window-level, run headless on the test database. No model is called.

UX-01: with no Project selected the workspace lived only in memory; the
autosave and the quit handler's save both returned early, so quitting lost
the Draft. UX-02: Clear emptied the Draft, every note and the Title in one
click, with no question, through QTextEdit.clear(), which drops undo.

Run with:  pytest tests/test_author_unfiled_and_clear.py -v
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.database import get_setting  # noqa: E402

KEY = "author_unfiled_workspace"


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _new_window():
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question,
             QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        return main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved


@pytest.fixture(scope="module")
def window(app):
    return _new_window()


@pytest.fixture
def quill(window):
    """Quill with no Project and an empty workspace."""
    panel = window.author_panel
    panel.activate_project(None)
    panel._project_save_timer.stop()
    panel._loading_project_state = True
    try:
        for box in panel._writing_boxes():
            box.clear()
        panel.author_direction_input.clear()
        panel.author_title_input.clear()
    finally:
        panel._loading_project_state = False
    panel._unfiled_state = None
    yield panel
    panel._project_save_timer.stop()
    panel.activate_project(None)


def _fire_autosave(panel):
    assert panel._project_save_timer.isActive(), \
        "an edit with no Project did not schedule a save"
    panel._project_save_timer.stop()
    panel._project_save_timer.timeout.emit()


def _saved():
    raw = get_setting(KEY, "")
    return json.loads(raw) if raw else {}


# ── UX-01: unfiled work is saved and restored ───────────────────────────────

def test_an_unfiled_draft_autosaves_and_comes_back_in_a_new_window(
        app, quill):
    quill.author_draft_box.setPlainText("Chapter one. The rain began.")
    quill.author_outline_box.setPlainText("1. Rain")
    _fire_autosave(quill)
    assert _saved()["draft"] == "Chapter one. The rain began."
    second = _new_window()
    try:
        panel = second.author_panel
        assert panel._project_id is None
        assert panel.author_draft_box.toPlainText() == \
            "Chapter one. The rain began."
        assert panel.author_outline_box.toPlainText() == "1. Rain"
    finally:
        second.author_panel._project_save_timer.stop()
        second.deleteLater()


def test_the_quit_save_keeps_an_unfiled_draft_the_timer_never_saved(quill):
    quill.author_draft_box.setPlainText("Typed a second before quitting.")
    quill._project_save_timer.stop()          # quit before the timer fires
    quill._persist_project_state()            # what closeEvent calls
    assert _saved()["draft"] == "Typed a second before quitting."


def test_unfiled_work_survives_a_round_trip_through_projects(window, quill):
    from services.project_workspaces import load
    window.registry.upsert_project("quill-a", "Book A")
    window.registry.upsert_project("quill-b", "Book B")
    book_a = window.registry.get_project("quill-a")
    book_b = window.registry.get_project("quill-b")

    quill.author_draft_box.setPlainText("Unfiled, first version.")
    quill.activate_project(book_a)
    quill.author_draft_box.setPlainText("Book A's own text.")
    quill.activate_project(None)
    assert quill.author_draft_box.toPlainText() == "Unfiled, first version."

    # Edited again before going to another Project: the newer text returns.
    quill.author_draft_box.setPlainText("Unfiled, second version.")
    quill.activate_project(book_b)
    quill.activate_project(None)
    assert quill.author_draft_box.toPlainText() == "Unfiled, second version."
    assert _saved()["draft"] == "Unfiled, second version."
    # The unfiled text never moved into a Project.
    assert load("quill-a", "author").get("draft") == "Book A's own text."
    assert (load("quill-b", "author").get("draft") or "") == ""


# ── UX-02: Clear asks first, is undoable, keeps Title ───────────────────────

@pytest.fixture
def dialog(monkeypatch):
    """Replace QMessageBox.exec: record the box, press `choice` (or none)."""
    from PySide6.QtWidgets import QMessageBox
    shown = []
    state = {"choice": None}

    def exec_(box):
        shown.append({"title": box.text(), "text": box.informativeText(),
                      "default": box.defaultButton().text(),
                      "escape": box.escapeButton().text()})
        for button in box.buttons():
            if button.text() == state["choice"]:
                button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", exec_)
    return shown, state


def _fill(panel):
    panel.author_title_input.setText("The Long Rain")
    panel.author_draft_box.setPlainText("The whole manuscript.")
    panel.author_outline_box.setPlainText("Outline")
    panel.author_characters_box.setPlainText("Characters")
    panel.author_world_box.setPlainText("World")
    panel.author_direction_input.setText("Make it darker")


def test_clear_asks_first_and_cancel_changes_nothing(quill, dialog):
    shown, state = dialog
    _fill(quill)
    state["choice"] = "Cancel"
    quill.clear()
    assert len(shown) == 1
    assert shown[0]["default"] == "Cancel" and shown[0]["escape"] == "Cancel"
    assert "The Long Rain" in shown[0]["text"]
    assert quill.author_draft_box.toPlainText() == "The whole manuscript."
    assert quill.author_direction_input.text() == "Make it darker"

    state["choice"] = None                   # the box closed some other way
    quill.clear()
    assert quill.author_draft_box.toPlainText() == "The whole manuscript."


def test_a_confirmed_clear_is_undoable_and_keeps_the_title(quill, dialog):
    shown, state = dialog
    _fill(quill)
    state["choice"] = "Clear"
    quill.clear()
    for box in quill._writing_boxes():
        assert box.toPlainText() == ""
    assert quill.author_direction_input.text() == ""
    assert quill.author_title_input.text() == "The Long Rain"
    assert quill.author_draft_box.document().isUndoAvailable()
    quill.author_draft_box.undo()
    assert quill.author_draft_box.toPlainText() == "The whole manuscript."


def test_clear_on_an_empty_workspace_asks_nothing(quill, dialog):
    shown, _state = dialog
    quill.clear()
    assert shown == []


def test_clear_is_unavailable_while_a_write_runs(quill, dialog):
    """Review 2026-11-24 P2-1: Clear mid-run cut the stream's anchor (the
    reply came back duplicated) or the revise selection (the incomplete-
    revision guard was skipped)."""
    shown, state = dialog
    _fill(quill)
    state["choice"] = "Clear"
    quill._begin_stream("append")
    try:
        quill.clear()
        assert shown == []
        assert quill.author_draft_box.toPlainText().startswith(
            "The whole manuscript.")
        assert "[Busy]" in quill.author_status_label.text()
    finally:
        quill._stream_mode = None
        quill._stream_anchor = None
        quill._finish_buttons()
    assert quill.author_clear_btn.isEnabled()


def test_the_clear_button_is_disabled_once_a_write_is_authorized(
        window, quill, monkeypatch):
    class Worker:
        def __init__(self):
            from types import SimpleNamespace
            sig = SimpleNamespace(connect=lambda *a: None)
            self.token_signal = self.finished_signal = sig
            self.error_signal = self.usage_signal = sig

        def start(self):
            pass

        def isRunning(self):
            return False

    monkeypatch.setattr(window, "authorize_request", lambda *a, **k: "tok")
    monkeypatch.setattr(window, "_new_chat_worker", lambda *a, **k: Worker())
    quill._start_worker("openai", "gpt-4o-mini", "go")
    try:
        assert not quill.author_clear_btn.isEnabled()
    finally:
        quill._write_token = None
        quill._stream_mode = None
        quill._finish_buttons()
        window.author_worker = None
