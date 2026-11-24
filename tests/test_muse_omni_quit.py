"""
Muse: a Gemini Omni teaser cut off by a quit follows Reel's rule (review P2-2)
=============================================================================
Type: window-level, run headless; fakes only, no network, no key.

Omni is one synchronous call: the create request returns the finished, paid
clip. Reel (audit QH-2) asks before quitting while one renders; on the next
launch a saved clip lands and bills once, and a call with no clip is counted
at its confirmed cost because Gemini may have charged. Muse used to mark any
interrupted `gemini:` row lost and release it as free, and quitting did not
ask. The owner chose Reel's rule for both (2026-11-24).

Run with:  pytest tests/test_muse_omni_quit.py -v
"""

import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.database import get_connection  # noqa: E402

OMNI_ENDPOINT = "gemini:gemini-omni-1.1-flash"


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
def account():
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO creator_accounts (handle, created_at) "
            "VALUES ('omni-quit-test', '2026-11-24T00:00:00')")
        row = conn.execute(
            "SELECT id FROM creator_accounts WHERE handle = 'omni-quit-test'"
        ).fetchone()
    yield row["id"]
    with get_connection() as conn:
        conn.execute("DELETE FROM creator_video_jobs")
        conn.execute("DELETE FROM creator_media")


def _insert(account_id, request_id, output_path):
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO creator_video_jobs
                 (request_id, account_id, created_at, updated_at, endpoint,
                  prompt, status, spend_state, flat_cost_eur, output_path,
                  estimated_usd)
               VALUES (?, ?, ?, ?, ?, 'a teaser', 'submitted', 'reserved',
                       0.5, ?, 0.6)""",
            (request_id, account_id, now, now, OMNI_ENDPOINT,
             str(output_path)))
        conn.commit()


def _row(request_id):
    with get_connection() as conn:
        return dict(conn.execute(
            "SELECT * FROM creator_video_jobs WHERE request_id = ?",
            (request_id,)).fetchone())


def _resume(window, monkeypatch, row):
    """Run the resume with the pieces that touch the library stubbed."""
    panel = window.creator_panel
    stored = []
    monkeypatch.setattr(panel, "_store_media",
                        lambda *a, **k: stored.append((a, k)))
    monkeypatch.setattr(panel, "_link_project_media", lambda *a, **k: None)
    monkeypatch.setattr(panel, "refresh_media", lambda: None)
    billed = []
    real = window.record_request
    monkeypatch.setattr(
        window, "record_request",
        lambda token, note="", *a, **k: (billed.append(note),
                                         real(token, note, *a, **k))[1])
    panel._spawn_teaser_resume(row)
    return stored, billed


def test_a_saved_omni_teaser_lands_and_bills_once_next_launch(
        window, account, tmp_path, monkeypatch):
    clip = tmp_path / "teaser.mp4"
    clip.write_bytes(b"paid-clip")
    _insert(account, "gemini-saved-1", clip)
    before = len(window._pending_requests)
    stored, billed = _resume(window, monkeypatch, _row("gemini-saved-1"))
    row = _row("gemini-saved-1")
    assert row["spend_state"] == "billed"
    assert row["local_path"] == str(clip)
    assert len(stored) == 1 and len(billed) == 1
    assert len(window._pending_requests) == before


def test_an_omni_teaser_with_no_clip_is_counted_not_released_as_free(
        window, account, tmp_path, monkeypatch):
    _insert(account, "gemini-lost-2", tmp_path / "never.mp4")
    before = len(window._pending_requests)
    stored, billed = _resume(window, monkeypatch, _row("gemini-lost-2"))
    row = _row("gemini-lost-2")
    assert row["spend_state"] == "billed"
    assert row["actual_usd"] == pytest.approx(0.6)
    assert "may have charged" in row["error"]
    assert stored == [] and len(billed) == 1
    assert len(window._pending_requests) == before


def test_quitting_during_an_omni_teaser_asks_and_keep_running_stays(
        window, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox
    asked = []

    def exec_(box):
        asked.append(box.text())
        for button in box.buttons():
            if button.text() == "Keep Running":
                button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", exec_)
    monkeypatch.setattr(window.creator_panel, "omni_rendering", lambda: True)
    event = QCloseEvent()
    window.closeEvent(event)
    assert asked == ["A Gemini Omni clip is rendering"]
    assert not event.isAccepted()


def test_omni_rendering_is_true_only_inside_the_create_call(window):
    panel = window.creator_panel
    saved = (panel._video_context, window.creator_video_worker)

    class _Running:
        def __init__(self, running):
            self._running = running

        def isRunning(self):
            return self._running

    try:
        panel._video_context = {"endpoint": OMNI_ENDPOINT}
        window.creator_video_worker = _Running(True)
        assert panel.omni_rendering() is True
        window.creator_video_worker = _Running(False)
        assert panel.omni_rendering() is False
        panel._video_context = {"endpoint": "qwen:wan3.0-video"}
        window.creator_video_worker = _Running(True)
        assert panel.omni_rendering() is False
    finally:
        panel._video_context, window.creator_video_worker = saved
