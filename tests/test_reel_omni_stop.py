"""
Reel: a Gemini Omni clip is never thrown away by Stop or a quit (audit QH-2)
===========================================================================
Type: window-level and worker-level, run headless. Every client is a fake
and no key is real; workers run synchronously on the test thread.

Gemini Omni renders in one synchronous call: the create request returns the
finished, paid clip. Reel's Stop "stops watching and saves the paid result on
the next launch", which holds for Veo and Wan but not for Omni: the worker
returned before writing the bytes, and the next launch could not resume
(GeminiClient.resume_video refuses Omni), so the row failed on every launch
and the clip was gone. Now Stop is not offered for Omni, a cancel at shutdown
still writes the bytes, and the next launch settles an Omni row from disk.

Run with:  pytest tests/test_reel_omni_stop.py -v
"""

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.video import jobs  # noqa: E402
from services.gemini_client import GeminiVideoJob  # noqa: E402

OMNI = "gemini-omni-1.1-flash"


@pytest.fixture(scope="module")
def app():
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
def clean_jobs_table():
    from services.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM video_jobs")
    yield
    with get_connection() as conn:
        conn.execute("DELETE FROM video_jobs")


class _OmniClient:
    """Gemini's synchronous create: the call returns the finished clip.
    `during_create` runs while the call is in flight (where a user's Stop or
    the shutdown sweep lands)."""

    def __init__(self, during_create=None, model=OMNI):
        self.during_create = during_create
        self.model = model

    def create_video(self, prompt, *, model, seconds, aspect_ratio, **kw):
        if self.during_create:
            self.during_create()
        if model == OMNI:
            return GeminiVideoJob("omni-1", "completed", model, seconds,
                                  aspect_ratio, 100, video_bytes=b"paid-clip")
        return GeminiVideoJob("op-1", "running", model, seconds, aspect_ratio)

    def wait_video(self, job, *, timeout, on_progress, should_cancel):
        if should_cancel():
            return job
        return job

    def download_video(self, job):
        return job.video_bytes


def _worker(client, tmp_path, model=OMNI):
    from ui.workers import VideoGenerationWorker
    return VideoGenerationWorker(
        client, "a fox in the snow", tmp_path / "clip" / "fox.mp4",
        provider="Gemini", model=model, seconds=6, aspect_ratio="9:16")


# ── the worker ──────────────────────────────────────────────────────────────

def test_a_cancel_during_an_omni_call_still_saves_the_paid_clip(
        app, tmp_path):
    holder = {}
    worker = _worker(_OmniClient(lambda: holder["w"].cancel()), tmp_path)
    holder["w"] = worker
    done, errors = [], []
    worker.done_signal.connect(done.append)
    worker.error_signal.connect(errors.append)
    worker.run()
    assert (tmp_path / "clip" / "fox.mp4").read_bytes() == b"paid-clip"
    # A cancel is the shutdown sweep: nothing is emitted to a closing window.
    assert done == [] and errors == []


def test_a_cancelled_veo_render_writes_nothing(app, tmp_path):
    """Veo is asynchronous: the clip is downloaded by the next launch."""
    holder = {}
    model = "veo-3.1-fast-generate-preview"
    worker = _worker(_OmniClient(lambda: holder["w"].cancel()), tmp_path,
                     model=model)
    holder["w"] = worker
    worker.run()
    assert not (tmp_path / "clip" / "fox.mp4").exists()


# ── the panel: Stop is not offered for Omni ─────────────────────────────────

def _render_direct(window, monkeypatch, tmp_path, model_id):
    """Run Reel's render_direct up to the worker start, with fakes."""
    from agents.video import video_studio
    from services.media_catalog import find_model
    import ui.workers as workers
    panel = window.video_panel
    started = []

    class FakeWorker:
        def __init__(self, *a, **k):
            self.status_signal = self.progress_signal = types.SimpleNamespace(
                connect=lambda *a: None)
            self.job_signal = self.done_signal = self.error_signal = \
                self.status_signal

        def start(self):
            started.append(True)

        def isRunning(self):
            return False

        def cancel(self):
            started.append("cancelled")

    monkeypatch.setattr(workers, "VideoGenerationWorker", FakeWorker)
    monkeypatch.setattr(window, "gemini", types.SimpleNamespace(
        key_available=lambda: True))
    monkeypatch.setattr(window.allow_gemini_checkbox, "isChecked",
                        lambda: True, raising=False)
    monkeypatch.setattr(panel, "_assessment", lambda *a, **k: None)
    monkeypatch.setattr(panel, "_direct_parameters", lambda: (6, "9:16"))
    monkeypatch.setattr(window, "authorize_request", lambda *a, **k: "tok-1")
    monkeypatch.setattr(window, "pending_request_snapshot", lambda t: {})
    monkeypatch.setattr(panel, "_persist_submission", lambda *a, **k: None)
    monkeypatch.setattr(video_studio, "external_output_path",
                        lambda topic, model: ("fox", tmp_path / "fox.mp4"))
    panel.video_topic_input.setText("a fox in the snow")
    panel.render_direct(find_model("Gemini", model_id))
    return panel, started


def test_omni_offers_no_stop_once_submitted(window, monkeypatch, tmp_path):
    panel, started = _render_direct(window, monkeypatch, tmp_path, OMNI)
    try:
        assert started == [True]
        assert not panel.video_stop_btn.isEnabled()
        assert panel.video_stop_btn.text() == "Cannot Stop"
        assert "cannot be stopped" in panel.video_log.toPlainText()
        window.video_worker = types.SimpleNamespace(isRunning=lambda: True)
        assert panel.omni_rendering() is True
        # A stray Stop changes nothing: the token and the worker stay.
        window.video_worker = types.SimpleNamespace(
            cancel=lambda: started.append("cancelled"))
        panel.stop()
        assert "cancelled" not in started
        assert panel._request_token == "tok-1"
    finally:
        window.video_worker = None
        panel._request_token = None
        panel._reset("")


def test_veo_still_offers_stop(window, monkeypatch, tmp_path):
    panel, started = _render_direct(
        window, monkeypatch, tmp_path, "veo-3.1-fast-generate-preview")
    try:
        assert started == [True]
        assert panel.video_stop_btn.isEnabled()
    finally:
        window.video_worker = None
        panel._request_token = None
        panel._reset("")


# ── the next launch settles an Omni row instead of failing on it ────────────

def _omni_row(output_path, *, status="completed"):
    row_id = jobs.record_submission(
        provider="gemini", model=OMNI, topic="a fox in the snow",
        slug="fox", output_path=str(output_path), seconds=6,
        aspect_ratio="9:16", flat_cost_eur=0.5, project=None, run_id="run-1")
    jobs.update_job(row_id, job_id="omni-1", status=status)
    return row_id


def _resume(window, monkeypatch, tmp_path):
    from agents.video import video_studio, workers
    from services.history_store import HistoryStore

    class RealGeminiResume:
        """What GeminiClient.resume_video does for Omni."""

        def key_available(self):
            return True

        def resume_video(self, job_id, **kw):
            raise ValueError("gemini-omni-1.1-flash renders synchronously; "
                             "there is no job to resume.")

    monkeypatch.setattr(window, "gemini", RealGeminiResume())
    monkeypatch.setattr(window, "history", HistoryStore(tmp_path / "chats"))
    recorded = []
    monkeypatch.setattr(video_studio, "record_external",
                        lambda **kw: recorded.append(kw))
    monkeypatch.setattr(window.video_panel, "refresh_library", lambda: None)
    monkeypatch.setattr(workers.VideoResumeWorker, "start",
                        workers.VideoResumeWorker.run)
    window.video_panel._resume_started = False
    window.video_panel.resume_pending_jobs()
    return recorded


def _row(row_id):
    from services.database import get_connection
    with get_connection() as conn:
        return dict(conn.execute(
            "SELECT status, spend_state, error FROM video_jobs WHERE id = ?",
            (row_id,)).fetchone())


def test_a_saved_omni_clip_lands_and_bills_once_next_launch(
        window, clean_jobs_table, tmp_path, monkeypatch):
    if not window.video_panel._available:
        pytest.skip("vidforge is not importable in this checkout")
    clip = tmp_path / "fox.mp4"
    clip.write_bytes(b"paid-clip")
    row_id = _omni_row(clip)
    before = window.usage_tracker.get_agent_today_total("video")
    recorded = _resume(window, monkeypatch, tmp_path)
    assert recorded and recorded[0]["slug"] == "fox"
    assert window.usage_tracker.get_agent_today_total("video") == \
        pytest.approx(before + 0.5)
    assert _row(row_id)["spend_state"] == "billed"
    assert jobs.pending_rows() == []
    assert not window._pending_requests


def test_a_completed_omni_clip_that_never_reached_disk_bills_and_closes(
        window, clean_jobs_table, tmp_path, monkeypatch):
    if not window.video_panel._available:
        pytest.skip("vidforge is not importable in this checkout")
    row_id = _omni_row(tmp_path / "missing.mp4")
    before = window.usage_tracker.get_agent_today_total("video")
    recorded = _resume(window, monkeypatch, tmp_path)
    assert recorded == []
    row = _row(row_id)
    assert (row["status"], row["spend_state"]) == ("completed", "billed")
    assert "not saved" in row["error"]
    assert window.usage_tracker.get_agent_today_total("video") == \
        pytest.approx(before + 0.5)
    assert jobs.pending_rows() == []
    assert not window._pending_requests


def _omni_row_at_quit(output_path):
    """What a quit during the create call really leaves: no job id, because
    the id is written on the window thread, which was waiting to close."""
    return jobs.record_submission(
        provider="gemini", model=OMNI, topic="a fox in the snow",
        slug="fox", output_path=str(output_path), seconds=6,
        aspect_ratio="9:16", flat_cost_eur=0.5, project=None, run_id="run-1")


def test_a_quit_during_the_omni_call_lands_the_saved_clip_next_launch(
        window, clean_jobs_table, tmp_path, monkeypatch):
    """Security review P1: sweep_lost used to release this row as free."""
    if not window.video_panel._available:
        pytest.skip("vidforge is not importable in this checkout")
    clip = tmp_path / "fox.mp4"
    clip.write_bytes(b"paid-clip")
    row_id = _omni_row_at_quit(clip)
    before = window.usage_tracker.get_agent_today_total("video")
    recorded = _resume(window, monkeypatch, tmp_path)
    assert recorded and recorded[0]["slug"] == "fox"
    row = _row(row_id)
    assert (row["status"], row["spend_state"]) == ("completed", "billed")
    assert window.usage_tracker.get_agent_today_total("video") == \
        pytest.approx(before + 0.5)
    assert not window._pending_requests


def test_a_quit_during_the_omni_call_with_no_clip_is_not_counted_as_free(
        window, clean_jobs_table, tmp_path, monkeypatch):
    if not window.video_panel._available:
        pytest.skip("vidforge is not importable in this checkout")
    row_id = _omni_row_at_quit(tmp_path / "never.mp4")
    before = window.usage_tracker.get_agent_today_total("video")
    _resume(window, monkeypatch, tmp_path)
    row = _row(row_id)
    assert row["spend_state"] == "billed"
    assert "may have charged" in row["error"]
    assert window.usage_tracker.get_agent_today_total("video") == \
        pytest.approx(before + 0.5)
    assert not window._pending_requests


def test_sweep_lost_still_releases_an_asynchronous_submission(
        clean_jobs_table):
    veo = jobs.record_submission(
        provider="gemini", model="veo-3.1-fast-generate-preview", topic="t",
        slug="veo", output_path="/tmp/veo.mp4", seconds=6,
        aspect_ratio="9:16", flat_cost_eur=0.5, project=None, run_id="r")
    omni = _omni_row_at_quit("/tmp/omni.mp4")
    assert [r["id"] for r in jobs.sweep_lost()] == [veo]
    assert [r["id"] for r in jobs.unacknowledged_synchronous()] == [omni]


def test_the_shutdown_save_leaves_no_partial_file(app, tmp_path):
    holder = {}
    worker = _worker(_OmniClient(lambda: holder["w"].cancel()), tmp_path)
    holder["w"] = worker
    worker.run()
    assert sorted(p.name for p in (tmp_path / "clip").iterdir()) == ["fox.mp4"]


def test_an_acknowledged_omni_row_that_never_completed_is_released(
        window, clean_jobs_table, tmp_path, monkeypatch):
    """Code review P2-2: the release branch had no test."""
    if not window.video_panel._available:
        pytest.skip("vidforge is not importable in this checkout")
    row_id = _omni_row(tmp_path / "none.mp4", status="failed")
    before = window.usage_tracker.get_agent_today_total("video")
    _resume(window, monkeypatch, tmp_path)
    row = _row(row_id)
    assert row["spend_state"] == "released"
    assert window.usage_tracker.get_agent_today_total("video") == \
        pytest.approx(before)
    assert not window._pending_requests


def test_quitting_during_an_omni_render_asks_and_keep_running_stays(
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
    monkeypatch.setattr(window.video_panel, "omni_rendering", lambda: True)
    event = QCloseEvent()
    window.closeEvent(event)
    assert asked == ["A Gemini Omni clip is rendering"]
    assert not event.isAccepted()
