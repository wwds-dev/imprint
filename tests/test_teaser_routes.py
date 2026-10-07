"""
Imprint — Muse's teaser routes
==============================
Type: unit + window-level, offline. Gemini runs through the real SDK on an
httpx MockTransport; Wan's HTTP session is a recorder; no worker is started.

Muse's teasers came only from Higgsfield, because only Higgsfield took the
persona's reference image. Gemini Omni and Wan 3.0 take reference images too,
so a teaser is now assessed across three routes. Pinned: the reference images
reach each API in its documented form; the job row exists before the paid
request; an interrupted Wan task resumes from its id; an interrupted Omni
render (nothing to look up) is released and surfaced, never billed on a guess.

Run with:  pytest tests/test_teaser_routes.py -v
"""

import base64
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def portrait(tmp_path):
    path = tmp_path / "persona.png"
    path.write_bytes(b"\x89PNG persona")
    return path


def test_omni_sends_reference_images_inline_with_their_tags(portrait):
    import httpx
    from services.gemini_client import GeminiClientWrapper, one_attempt_client
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "i1", "status": "completed",
            "steps": [{"type": "model_output", "content": [
                {"type": "video", "mime_type": "video/mp4",
                 "data": base64.b64encode(b"mp4").decode()}]}]})

    wrapper = GeminiClientWrapper.__new__(GeminiClientWrapper)
    wrapper.api_key = "test-not-a-real-key"
    wrapper.media_client = one_attempt_client(
        "test-not-a-real-key", httpx_client=httpx.Client(
            transport=httpx.MockTransport(handler)))
    job = wrapper.create_video("a teaser", model="gemini-omni-1.1-flash",
                               seconds=5, aspect_ratio="9:16",
                               reference_images=[portrait])
    assert job.video_bytes == b"mp4"
    content = sent[0]["input"][0]["content"]
    image, text = content[0], content[-1]
    assert image["type"] == "image" and image["mime_type"] == "image/png"
    assert base64.b64decode(image["data"]) == b"\x89PNG persona"
    assert "<IMAGE_REF_0>" in text["text"]
    assert sent[0]["generation_config"] == {
        "video_config": {"task": "reference_to_video"}}


def test_veo_refuses_reference_images_rather_than_ignoring_them(portrait):
    from services.gemini_client import GeminiClientWrapper
    wrapper = GeminiClientWrapper.__new__(GeminiClientWrapper)
    with pytest.raises(ValueError, match="reference images"):
        wrapper.create_video("x", model="veo-3.1-lite-generate-preview",
                             seconds=4, reference_images=[portrait])


def test_wan_sends_reference_images_as_data_uris(portrait):
    from services.qwen_client import QwenClientWrapper
    posted = []

    class Session:
        def post(self, url, headers=None, json=None, timeout=None):
            posted.append(json)
            return types.SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"output": {"task_id": "t-1",
                                         "task_status": "PENDING"}})

    client = QwenClientWrapper.__new__(QwenClientWrapper)
    client.api_key = "test-not-a-real-key"
    client.video_session = Session()
    client.video_base_url = "https://dashscope-intl.aliyuncs.com/api/v1"
    job = client.create_video("a teaser", model="wan3.0-video", seconds=5,
                              aspect_ratio="9:16", reference_images=[portrait])
    assert job.job_id == "t-1"
    media = posted[0]["input"]["media"]
    assert media == [{"type": "reference_image",
                      "url": "data:image/png;base64,"
                             + base64.b64encode(b"\x89PNG persona").decode()}]
    assert "Image 1" in posted[0]["input"]["prompt"]


# ── Muse in the window ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


def _account_id() -> int:
    """A real Muse account: the job table's account_id is a foreign key."""
    from datetime import datetime
    from services.database import get_connection
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM creator_accounts WHERE handle = ?",
                           ("teaser-routes-test",)).fetchone()
        if row:
            return row[0]
        cursor = conn.execute(
            "INSERT INTO creator_accounts (handle, created_at) VALUES (?, ?)",
            ("teaser-routes-test", datetime.now().isoformat(timespec="seconds")))
        conn.commit()
        return cursor.lastrowid


def _row(request_id):
    from services.database import get_connection
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM creator_video_jobs WHERE request_id = ?",
                           (request_id,)).fetchone()
    return dict(row) if row else None


def test_a_gemini_teaser_is_recorded_before_it_is_requested(
        app, window, monkeypatch, portrait):
    import agents.creator.panel as creator_panel
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    window.allow_gemini_checkbox.setChecked(True)
    window.allow_qwen_checkbox.setChecked(True)
    monkeypatch.setattr(window, "session_budget_eur", 1000.0)
    monkeypatch.setattr(window, "daily_budget_eur", 1000.0)
    monkeypatch.setattr(creator_panel, "reference_images",
                        lambda account_id: [str(portrait)])
    started = []

    def fake_start(worker):
        # The row must already exist when the paid request would go out.
        started.append((worker.model, worker.reference_images,
                        _row(window.creator_panel._video_context["fixed_request_id"])))

    monkeypatch.setattr("ui.workers.VideoGenerationWorker.start", fake_start)
    asked = []
    real = window.authorize_request
    monkeypatch.setattr(window, "authorize_request",
                        lambda *a, **k: (asked.append(a[:3] + (k.get("assessment"),)),
                                         real(*a, **k))[1])
    try:
        panel = window.creator_panel
        account = _account_id()
        monkeypatch.setattr(panel, "current_account",
                            lambda: {"id": account, "name": "Test persona"})
        panel._switch_teaser_route("gemini")
        panel.generate_video()
        agent, provider, model, assessment = asked[-1]
        assert (agent, provider, model) == ("creator", "gemini", "gemini-omni-1.1-flash")
        routes = {o.candidate.provider: o.cost_eur for _s, o in assessment.ranked}
        assert set(routes) >= {"Gemini", "Qwen"}
        assert routes["Gemini"] and routes["Qwen"]
        model, refs, row = started[0]
        assert model == "gemini-omni-1.1-flash" and refs == [str(portrait)]
        assert row is not None and row["spend_state"] == "reserved"
        assert row["endpoint"] == "gemini:gemini-omni-1.1-flash"
    finally:
        window.allow_gemini_checkbox.setChecked(False)
        window.allow_qwen_checkbox.setChecked(False)
        for token in list(window._pending_requests):
            window.abandon_request(token)
        window.creator_panel._video_context = {}
        window.creator_panel._switch_teaser_route("higgsfield")


def _insert(request_id, endpoint, correlation=""):
    from datetime import datetime
    from services.database import get_connection
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO creator_video_jobs
                 (request_id, account_id, created_at, updated_at, endpoint,
                  prompt, status, correlation_id, spend_state, flat_cost_eur,
                  output_path)
               VALUES (?, ?, ?, ?, ?, 'a teaser', 'submitted', ?, 'reserved',
                       0.5, '/tmp/teaser.mp4')""",
            (request_id, _account_id(), now, now, endpoint, correlation))
        conn.commit()


def test_an_interrupted_omni_teaser_is_released_and_surfaced(window):
    _insert("gemini-lost-1", "gemini:gemini-omni-1.1-flash")
    before = len(window._pending_requests)
    window.creator_panel._spawn_teaser_resume(_row("gemini-lost-1"))
    row = _row("gemini-lost-1")
    assert (row["spend_state"], row["status"]) == ("released", "lost")
    assert len(window._pending_requests) == before       # nothing billed


def test_an_interrupted_wan_teaser_is_watched_again_from_its_task(window,
                                                                 monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    spawned = []
    monkeypatch.setattr("agents.video.workers.VideoResumeWorker.start",
                        lambda self: spawned.append((self.provider, self.job_id)))
    _insert("qwen-live-1", "qwen:wan3.0-video", correlation="task-77")
    window.creator_panel._spawn_teaser_resume(_row("qwen-live-1"))
    assert spawned == [("qwen", "task-77")]
    assert _row("qwen-live-1")["spend_state"] == "reserved"   # until it settles
    for token in list(window._pending_requests):
        window.abandon_request(token)
