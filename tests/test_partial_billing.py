"""
Imprint — failed or stopped renders and batches bill what they already paid
===========================================================================
Type: unit + window, no network (fake vidforge produce, fake image worker,
temp DB per test, offscreen Qt, no keys).

Audit B-F3 (spec docs/specs/audit-p1-billing.md, owner decision D3): a render
that failed or was stopped, a Social clip that failed and a Fiverr batch that
stopped short all called abandon_request and recorded €0, although the
provider had billed the script, the narration and every image already made —
about €2.1 for a default render failing at assembly, and a retry paid it all
again under the same caps. Now each closes with record_partial(): each paid
stage that started at its confirmed line, each saved image at the per-image
rate, never above the confirmed total; a Stop before the script stage, or
before the first image, records nothing.

Run with:  pytest tests/test_partial_billing.py -v
"""

import math

import pytest

from agents.video.studio import partial_render_cost_usd, partial_render_notice
from services import database, money_text

EUR = 0.92
# A default eight-minute render, priced by hand so the test does not move
# when config/pricing.json is re-priced: 34 scenes + a thumbnail = 35 images.
ESTIMATE = {"script": 0.03, "narration": 0.112, "captions": 0.048,
            "images": 2.10, "per_image": 0.06, "scenes": 34, "total": 2.29}
ALL_PIPELINE = ["script", "voice", "captions", "visuals", "motion", "audio",
                "assemble"]


def _trace(stages=(), images=0):
    return {"stages": list(stages), "images": images}


# ── 7. The cost of a partial render ──────────────────────────────────────────

def test_nothing_started_costs_nothing():
    assert partial_render_cost_usd(ESTIMATE, _trace()) == 0.0
    assert partial_render_cost_usd(ESTIMATE, None) == 0.0


def test_a_started_stage_bills_its_whole_line():
    assert partial_render_cost_usd(ESTIMATE, _trace(["script"])) == 0.03
    assert partial_render_cost_usd(
        ESTIMATE, _trace(["script", "voice", "captions"])) == pytest.approx(0.19)


def test_images_bill_per_image_saved():
    lines = 0.03 + 0.112 + 0.048
    after_10 = partial_render_cost_usd(
        ESTIMATE, _trace(["script", "voice", "captions", "visuals"], 10))
    assert after_10 == pytest.approx(lines + 10 * 0.06)
    # A failure in motion: every scene image was made.
    after_34 = partial_render_cost_usd(ESTIMATE, _trace(ALL_PIPELINE[:5], 34))
    assert after_34 == pytest.approx(lines + 34 * 0.06)


def test_the_thumbnail_counts_once_its_stage_began():
    with_thumb = partial_render_cost_usd(
        ESTIMATE, _trace(ALL_PIPELINE + ["thumbnail"], 34))
    without = partial_render_cost_usd(ESTIMATE, _trace(ALL_PIPELINE, 34))
    assert with_thumb - without == pytest.approx(0.06)


def test_never_above_the_confirmed_total():
    """Scenes beyond the estimate are not billed above it (B-F6)."""
    over = partial_render_cost_usd(ESTIMATE, _trace(ALL_PIPELINE + ["thumbnail"], 60))
    assert over == ESTIMATE["total"]


def test_status_and_log_lines():
    status, log = partial_render_notice(
        ESTIMATE, _trace(ALL_PIPELINE[:5], 34), recorded_eur=2.05,
        confirmed_eur=2.1068, eur_rate=EUR, error="RuntimeError: ffmpeg died",
        stopped=False)
    assert status == ("[Error] RuntimeError: ffmpeg died. €2.05 of €2.11 "
                      "recorded (script, narration, captions, 34 of 35 images).")
    assert log == ("[Billing] Recorded €2.05 of €2.11 confirmed: script €0.03, "
                   "narration €0.10, captions €0.04, 34 images × €0.06. A new "
                   "render starts from the beginning and is paid again.")
    stopped, _ = partial_render_notice(
        ESTIMATE, _trace(ALL_PIPELINE[:4], 10), recorded_eur=0.73,
        confirmed_eur=2.1068, eur_rate=EUR, error="Cancelled.", stopped=True)
    assert stopped == "[Stopped] After 10 of 35 images: €0.73 of €2.11 recorded."
    before, _ = partial_render_notice(
        ESTIMATE, _trace(), recorded_eur=0.0, confirmed_eur=2.1068,
        eur_rate=EUR, error="Cancelled.", stopped=True)
    assert before == "[Stopped] Before any paid step: nothing recorded."


# ── 8. The worker reports what the render did ────────────────────────────────

@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class Cancelled(Exception):
    """Named like vidforge's: the worker matches on the class name."""


class Reporter:
    """vidforge's Reporter contract (begin, substep, cancel), as
    tests/test_vidforge_contract.py pins it."""

    def __init__(self):
        self._cancelled = False
        self.stage_key = None

    def cancel(self):
        self._cancelled = True

    def raise_if_cancelled(self):
        if self._cancelled:
            raise Cancelled()

    def begin(self, stage_key, detail=""):
        self.raise_if_cancelled()
        self.stage_key = stage_key
        self.on_stage(stage_key, detail)

    def substep(self, done, total, detail=""):
        self.raise_if_cancelled()
        self.on_progress(self.stage_key or "", done / total if total else 0, detail)

    def log(self, message):
        self.on_log(message)

    def on_stage(self, stage_key, detail):
        pass

    def on_progress(self, stage_key, fraction, detail):
        pass

    def on_log(self, message):
        pass


def _run_worker(monkeypatch, produce, *, cancel_first=False):
    from agents.video import video_studio
    from ui.workers import VideoWorker

    monkeypatch.setattr(video_studio, "reporter_base", lambda: Reporter)
    monkeypatch.setattr(video_studio, "load_config", lambda overrides=None: {})
    monkeypatch.setattr(video_studio, "produce", produce)
    worker = VideoWorker(topic="t")
    events = []
    worker.trace_signal.connect(lambda t: events.append(("trace", t)))
    worker.error_signal.connect(lambda e: events.append(("error", e)))
    worker.done_signal.connect(lambda *a: events.append(("done", a)))
    if cancel_first:
        worker.cancel()
    worker.run()
    return worker, events


def _fake_produce(*, stop_at_scene=None, fail_in=None, scenes=35,
                  stop_in_last_image=False):
    def produce(cfg, *, topic=None, resume_slug=None, reporter=None):
        for stage in ("script", "voice", "captions"):
            reporter.begin(stage)
        reporter.begin("visuals")
        for i in range(scenes):
            if i == stop_at_scene:
                reporter.cancel()          # the user pressed Stop
            reporter.substep(i, scenes)
        if stop_in_last_image:
            reporter.cancel()              # Stop while the last image was made
        reporter.begin("motion")
        if fail_in == "motion":
            raise RuntimeError("ffmpeg died")
        raise AssertionError("not reached in these tests")
    return produce


def test_a_cancel_before_start_reports_no_stage(app, monkeypatch):
    _worker, events = _run_worker(monkeypatch, _fake_produce(), cancel_first=True)
    assert events == [("trace", {"stages": [], "images": 0}),
                      ("error", "Cancelled.")]


def test_a_stop_at_scene_11_reports_10_images(app, monkeypatch):
    _worker, events = _run_worker(monkeypatch, _fake_produce(stop_at_scene=10))
    assert events == [
        ("trace", {"stages": ["script", "voice", "captions", "visuals"],
                   "images": 10}),
        ("error", "Cancelled.")]


def test_a_stop_during_the_last_scene_image_counts_every_saved_image(
        app, monkeypatch):
    """vidforge saves the last image, then asks for the motion stage, which
    raises on the Stop before on_stage records it: 35 saved, 34 billed
    (security review P3-2). Leaving visuals now counts them all."""
    _worker, events = _run_worker(monkeypatch,
                                  _fake_produce(stop_in_last_image=True))
    assert events == [
        ("trace", {"stages": ["script", "voice", "captions", "visuals"],
                   "images": 35}),
        ("error", "Cancelled.")]


def test_a_failure_in_motion_reports_every_image(app, monkeypatch):
    _worker, events = _run_worker(monkeypatch, _fake_produce(fail_in="motion"))
    trace, error = events
    assert trace == ("trace", {"stages": ["script", "voice", "captions",
                                          "visuals", "motion"], "images": 35})
    assert error == ("error", "RuntimeError: ffmpeg died")


# ── The window: record_partial and the three panels ─────────────────────────

@pytest.fixture(scope="module")
def _window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved


ALL_ALLOWED = {f"allow_{p}": True for p in (
    "openai", "deepseek", "kimi", "gemini", "anthropic", "qwen",
    "higgsfield", "elevenlabs")}


@pytest.fixture
def win(_window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "imprint.db")
    database.init_db()
    w = _window
    w._pending_requests = {}
    w._pending_by_agent = {}
    w.session_cost_total = 0.0
    w.session_request_count = 0
    w.session_budget_eur = 10.0
    w.daily_budget_eur = 10.0
    monkeypatch.setattr(w, "current_api_permissions", lambda: dict(ALL_ALLOWED))
    monkeypatch.setattr(w, "_active_project", lambda: None)
    monkeypatch.setattr(w, "load_history_list", lambda: None)
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    w.saved_chats = []
    monkeypatch.setattr(w.history, "save_chat",
                        lambda **kw: w.saved_chats.append(kw))
    return w


def _rows():
    conn = database.get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT agent, backend, model, cost_eur, cost_type FROM usage "
            "ORDER BY id")]
    finally:
        conn.close()


def _run(run_id):
    conn = database.get_connection()
    try:
        row = conn.execute("SELECT status, cost_eur, error FROM runs "
                           "WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _authorize(win, cost, agent="video", label="long-form"):
    token = win.authorize_request(agent, "openai", "vidforge-pipeline",
                                  "a topic", label=label, flat_cost_eur=cost,
                                  partial_billing=True)
    assert token
    return token, win.pending_request_snapshot(token)["run_id"]


# ── 10. record_partial itself ────────────────────────────────────────────────

def test_record_partial_caps_at_the_reserve_and_writes_one_partial_row(win):
    token, run_id = _authorize(win, 0.50)
    assert win.record_partial(token, 0.80, status="error", error="boom") == (0.50, 0.50)
    assert _rows() == [{"agent": "video", "backend": "openai",
                        "model": "vidforge-pipeline", "cost_eur": 0.50,
                        "cost_type": "partial"}]
    assert win.session_cost_total == pytest.approx(0.50)
    run = _run(run_id)
    assert (run["status"], run["cost_eur"]) == ("error", 0.50)
    assert run["error"] == "boom; recorded €0.50 of €0.50"
    assert token not in win._pending_requests
    assert win.saved_chats == []                     # never a Saved Chat


@pytest.mark.parametrize("bad", [math.nan, math.inf, None, "x"])
def test_a_cost_that_is_not_a_number_records_the_reserve(win, bad):
    token, _run_id = _authorize(win, 0.30)
    assert win.record_partial(token, bad, status="error", error="e") == (0.30, 0.30)


def test_record_partial_floors_at_zero_and_writes_no_row_at_zero(win):
    token, run_id = _authorize(win, 0.30)
    assert win.record_partial(token, -1.0, status="cancelled",
                              error="Cancelled.") == (0.0, 0.30)
    assert _rows() == []
    assert win.session_cost_total == 0.0
    run = _run(run_id)
    assert run["status"] == "cancelled"
    assert run["error"] == "Cancelled.; recorded €0.00 of €0.30"


def test_record_partial_ignores_agent_names_and_closed_tokens(win):
    token, _run_id = _authorize(win, 0.30)
    assert win.record_partial("video", 0.10, status="error", error="e") is None
    assert token in win._pending_requests            # a name never resolves
    assert win.record_partial(token, 0.10, status="error", error="e") == (0.10, 0.30)
    assert win.record_partial(token, 0.10, status="error", error="e") is None
    assert len(_rows()) == 1


def test_successful_rows_are_unchanged(win):
    token, _run_id = _authorize(win, 0.25)
    entry = win.record_request(token, "rendered")
    assert entry["cost_type"] == "per_unit"
    assert _rows()[0]["cost_type"] == "per_unit"
    assert entry["stop_reason"] is None


# ── 9. Video and Social clip failures ────────────────────────────────────────

def _video(win):
    panel = win.video_panel
    if not panel._available:
        pytest.skip("vidforge is not importable in this checkout")
    return panel


def _arm_video(win, panel, trace, *, stopped=False):
    confirmed = round(ESTIMATE["total"] * EUR, 4)
    token, run_id = _authorize(win, confirmed)
    panel._active_kind = "pipeline"
    panel._request_token = token
    panel._render_estimate = dict(ESTIMATE)
    panel._render_eur_rate = EUR
    panel._render_trace = trace
    panel._stop_requested = stopped
    return confirmed, run_id


def test_a_video_failure_records_its_finished_steps(win):
    panel = _video(win)
    # A failure in motion: all 34 scene images made, the thumbnail not yet.
    trace = _trace(ALL_PIPELINE[:5], 34)
    confirmed, run_id = _arm_video(win, panel, trace)
    # (0.03 + 0.112 + 0.048 + 34 x 0.06) USD x 0.92, below the €2.1068 cap.
    expected = 2.0516
    assert expected < confirmed == 2.1068
    today_before = win.usage_tracker.get_today_total()

    panel._on_error("RuntimeError: ffmpeg died")

    rows = _rows()
    assert [(r["cost_type"], r["cost_eur"]) for r in rows] == [
        ("partial", pytest.approx(expected, abs=1e-9))]
    assert win.session_cost_total == pytest.approx(expected)
    assert win.usage_tracker.get_today_total() - today_before == pytest.approx(expected)
    assert win.usage_tracker.get_agent_today_total("video") == pytest.approx(expected)
    run = _run(run_id)
    assert run["status"] == "error"
    assert run["error"] == ("RuntimeError: ffmpeg died; recorded €2.05 of €2.11")
    assert win.saved_chats == []
    assert panel.video_status_label.text() == (
        "[Error] RuntimeError: ffmpeg died. €2.05 of €2.11 recorded "
        "(script, narration, captions, 34 of 35 images).")
    assert "[Billing] Recorded" in panel.video_log.toPlainText()


def test_a_video_stop_before_the_script_records_nothing(win):
    panel = _video(win)
    _confirmed, run_id = _arm_video(win, panel, _trace(), stopped=True)
    panel._on_error("Cancelled.")
    assert _rows() == []
    assert win.session_cost_total == 0.0
    assert _run(run_id)["status"] == "cancelled"
    assert panel.video_status_label.text() == (
        "[Stopped] Before any paid step: nothing recorded.")


def test_stop_marks_a_pipeline_render_as_cancelled(win):
    panel = _video(win)

    class Worker:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    _arm_video(win, panel, None)
    win.video_worker = worker = Worker()
    try:
        panel.stop()
    finally:
        win.video_worker = None
    assert worker.cancelled and panel._stop_requested
    assert panel.video_status_label.text() == (
        "Stopping after this step… paid steps already done are recorded.")
    panel._on_error("Cancelled.")          # close the armed request


def test_a_social_clip_failure_records_its_finished_steps(win):
    panel = win.social_panel
    trace = _trace(["script", "voice", "captions", "visuals"], 10)
    confirmed = round(ESTIMATE["total"] * EUR, 4)
    token, run_id = _authorize(win, confirmed, label="tiktok clip")
    panel._clip_video_token = token
    panel._clip_estimate = dict(ESTIMATE)
    panel._clip_eur_rate = EUR
    panel._on_clip_trace(trace)
    # (0.03 + 0.112 + 0.048 + 10 x 0.06) USD x 0.92, by hand rather than
    # through partial_render_cost_usd, so a wrong formula cannot agree
    # with itself; below the €2.1068 confirmed.
    expected = 0.7268
    assert expected < confirmed

    panel._on_clip_render_error("RuntimeError: boom")

    assert [(r["cost_type"], r["cost_eur"]) for r in _rows()] == [
        ("partial", pytest.approx(expected, abs=1e-9))]
    assert win.session_cost_total == pytest.approx(expected)
    assert _run(run_id)["status"] == "error"
    assert panel.social_status_label.text().startswith("Clip: [Error] RuntimeError: boom. €")
    assert "10 of 35 images" in panel.social_status_label.text()
    assert panel._clip_video_token is None


# ── 9. The wiring: the real render paths with a fake VideoWorker ────────────
# The handler tests above set the panel's state by hand, so a render whose
# trace or error signal was not connected (or connected to the €0 abandon
# handler) still passed them (QA loop 0: mutants d1, h, i survived).

def _fake_video_worker_class(made):
    from PySide6.QtCore import QObject, Signal

    class FakeVideoWorker(QObject):
        stage_signal = Signal(str, str)
        progress_signal = Signal(int, str)
        log_signal = Signal(str)
        done_signal = Signal(str, str)
        error_signal = Signal(str)
        trace_signal = Signal(dict)

        def __init__(self, topic="", overrides=None, resume_slug=""):
            super().__init__()
            self.topic = topic
            made.append(self)

        def start(self):
            pass

        def isRunning(self):
            return False

        def cancel(self):
            pass

    return FakeVideoWorker


# Script, narration, captions and 10 scene images, then a failure:
# (0.03 + 0.112 + 0.048 + 10 x 0.06) USD x 0.92 = €0.7268, below the
# €2.1068 confirmed for the whole render.
TEN_IMAGES = {"stages": ["script", "voice", "captions", "visuals"], "images": 10}
TEN_IMAGES_EUR = 0.7268


def test_video_render_bills_the_steps_its_worker_reports(win, monkeypatch):
    import ui.workers as workers
    panel = _video(win)
    made = []
    monkeypatch.setattr(workers, "VideoWorker", _fake_video_worker_class(made))
    monkeypatch.setattr(panel, "_media_selection", lambda: None)
    monkeypatch.setattr(panel, "_estimate", lambda: dict(ESTIMATE))
    monkeypatch.setattr(panel, "_assessment", lambda *a, **k: None)
    monkeypatch.setattr(panel, "_overrides", lambda *a, **k: {})
    win.video_worker = None
    today_before = win.usage_tracker.get_today_total()
    try:
        panel.render()
        (worker,) = made
        assert win._pending_requests[panel._request_token]["estimated_cost"] == 2.1068
        worker.trace_signal.emit(dict(TEN_IMAGES))
        worker.error_signal.emit("RuntimeError: boom")
    finally:
        win.video_worker = None
    assert [(r["cost_type"], r["cost_eur"]) for r in _rows()] == [
        ("partial", pytest.approx(TEN_IMAGES_EUR, abs=1e-9))]
    assert win.session_cost_total == pytest.approx(TEN_IMAGES_EUR)
    assert win.usage_tracker.get_today_total() - today_before == pytest.approx(
        TEN_IMAGES_EUR)
    assert win._pending_requests == {}
    assert win.saved_chats == []
    assert panel.video_status_label.text() == (
        "[Error] RuntimeError: boom. €0.73 of €2.11 recorded "
        "(script, narration, captions, 10 of 35 images).")


def test_social_clip_render_bills_the_steps_its_worker_reports(win, monkeypatch):
    import ui.workers as workers
    from agents.video import video_studio
    panel = win.social_panel
    made = []
    monkeypatch.setattr(workers, "VideoWorker", _fake_video_worker_class(made))
    monkeypatch.setattr(video_studio, "load_config", lambda overrides=None: {})
    monkeypatch.setattr(video_studio, "pre_estimate", lambda cfg: dict(ESTIMATE))
    monkeypatch.setattr(panel, "_clip_assessment", lambda *a, **k: None)
    panel._brief_token = None
    panel._pending_clip = ("tiktok", 30)
    today_before = win.usage_tracker.get_today_total()

    panel._on_clip_brief("A fox finds the lost library\nScene notes follow.")

    (worker,) = made
    assert worker.topic == "A fox finds the lost library"
    token = panel._clip_video_token
    assert win._pending_requests[token]["estimated_cost"] == 2.1068
    worker.trace_signal.emit(dict(TEN_IMAGES))
    worker.error_signal.emit("RuntimeError: boom")
    win._social_clip_worker = None
    assert [(r["cost_type"], r["cost_eur"]) for r in _rows()] == [
        ("partial", pytest.approx(TEN_IMAGES_EUR, abs=1e-9))]
    assert win.session_cost_total == pytest.approx(TEN_IMAGES_EUR)
    assert win.usage_tracker.get_today_total() - today_before == pytest.approx(
        TEN_IMAGES_EUR)
    assert win._pending_requests == {}
    assert win.saved_chats == []
    assert panel.social_status_label.text() == (
        "Clip: [Error] RuntimeError: boom. €0.73 of €2.11 recorded "
        "(script, narration, captions, 10 of 35 images).")


def _text_token(win, agent, content, usage):
    """A real paid text request whose worker reported `usage`."""
    messages = [{"role": "user", "content": content}]
    token = win.authorize_request(agent, "openai", "gpt-4o-mini", content,
                                  messages=messages)
    assert token
    win.note_request_usage(token, usage)
    return token


CUT = {"input_tokens": 40, "output_tokens": 8192, "stop_reason": "length"}


def test_a_cut_off_clip_brief_is_not_rendered(win, monkeypatch):
    """Code review P3-1: a brief cut at the length limit, or an empty one,
    chained into a paid render (an empty topic renders the next topic from
    topics.txt, about €2)."""
    import ui.workers as workers
    from services.output_limits import RESULT_CUT_OFF
    from PySide6.QtWidgets import QMessageBox
    panel = win.social_panel
    made = []
    monkeypatch.setattr(workers, "VideoWorker", _fake_video_worker_class(made))
    panel._brief_token = _text_token(win, "social", "Write a clip brief.", CUT)
    asked = []                             # "Render this clip?" and the guard
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: asked.append(a[1]) or QMessageBox.Yes))

    panel._on_clip_brief("A fox finds the lost lib")
    assert panel.social_status_label.text() == f"Clip: {RESULT_CUT_OFF}"
    assert [r["cost_type"] for r in _rows()] == ["exact"]     # the brief only

    panel._brief_token = None
    panel._on_clip_brief("   \n  ")
    assert panel.social_status_label.text() == (
        "Clip: [Error] The clip brief came back empty; nothing was rendered.")

    assert made == [] and asked == []
    assert win._pending_requests == {}
    assert panel.social_clip_btn.isEnabled()


def test_a_cut_off_fiverr_image_prompt_requests_no_images(win, monkeypatch):
    import services.recommendations.catalog as catalog
    import ui.workers as workers
    from services.output_limits import RESULT_CUT_OFF

    def no_worker(*a, **k):
        raise AssertionError("no image may be requested")

    monkeypatch.setattr(workers, "FiverrImageWorker", no_worker)
    monkeypatch.setattr(catalog, "provider_configured", lambda provider: True)
    panel = win.fiverr_panel
    monkeypatch.setattr(panel, "_image_assessment", lambda *a, **k: None)
    panel._pending_count = 4
    panel._pending_brief = {"business_name": "Acme"}

    panel._set_busy("Building image prompt...")
    panel._prompt_token = _text_token(win, "fiverr", "Write a logo prompt.", CUT)
    panel._on_prompt_ready("A fox logo, flat, two col")
    assert panel.fiverr_status_label.text() == RESULT_CUT_OFF
    assert panel.fiverr_preview_status.text() == RESULT_CUT_OFF
    assert [r["cost_type"] for r in _rows()] == ["exact"]     # the prompt only
    assert panel.fiverr_generate_btn.isEnabled()

    panel._set_busy("Building image prompt...")
    panel._prompt_token = None
    panel._on_prompt_ready("  ")
    assert panel.fiverr_status_label.text() == (
        "[Error] The image prompt came back empty; no images were requested.")
    assert panel._image_token is None
    assert win._pending_requests == {}
    assert panel.fiverr_generate_btn.isEnabled()


# ── 10. Fiverr: only the concepts the provider returned ──────────────────────

@pytest.fixture
def fiverr(win, monkeypatch):
    """The Fiverr panel up to its image request, with a fake image worker."""
    from PySide6.QtCore import QObject, Signal
    import services.recommendations.catalog as catalog
    import ui.workers as workers

    class FakeImageWorker(QObject):
        image_ready_signal = Signal(str, int)
        all_done_signal = Signal(list)
        error_signal = Signal(str)
        status_signal = Signal(str)

        def __init__(self, *args, **kwargs):
            super().__init__()
            self.running = True
            self.cancelled = False

        def start(self):
            pass

        def cancel(self):
            self.cancelled = True

        def isRunning(self):
            return self.running

    monkeypatch.setattr(workers, "FiverrImageWorker", FakeImageWorker)
    monkeypatch.setattr(catalog, "provider_configured", lambda provider: True)
    panel = win.fiverr_panel
    monkeypatch.setattr(panel, "_image_assessment", lambda *a, **k: None)
    monkeypatch.setattr(panel, "refresh_orders", lambda: None)
    panel._prompt_token = None
    panel._pending_count = 4
    panel._pending_brief = {"business_name": "Acme"}
    panel._set_busy("Building image prompt...")     # as generate() does
    panel._on_prompt_ready("A fox logo")
    token = panel._image_token
    assert token, "the image request was not authorized"
    worker = win.fiverr_image_worker
    run_id = win.pending_request_snapshot(token)["run_id"]
    confirmed = win.pending_request_snapshot(token)["estimated_cost"]
    yield panel, worker, run_id, confirmed / 4, confirmed
    win.fiverr_image_worker = None


def test_fiverr_bills_three_of_four_when_the_fourth_fails(win, fiverr):
    panel, worker, run_id, rate, confirmed = fiverr
    for i in range(3):
        worker.image_ready_signal.emit(f"/nowhere/logo_{i + 1}.png", i)
    worker.running = False
    worker.error_signal.emit("Concept 4 failed: content policy")
    assert [(r["cost_type"], r["cost_eur"]) for r in _rows()] == [
        ("partial", round(3 * rate, 6))]
    assert _run(run_id)["status"] == "error"
    assert panel.fiverr_status_label.text() == (
        f"[Error] Concept 4 failed: content policy. 3 of 4 concepts made; "
        f"{money_text.paid(3 * rate)} of {money_text.up_to(confirmed)} recorded.")
    assert panel.fiverr_preview_status.text() == panel.fiverr_status_label.text()
    assert panel.fiverr_generate_btn.isEnabled()


def test_fiverr_stop_bills_the_concept_in_flight_once_the_worker_exits(
        win, fiverr):
    panel, worker, run_id, rate, confirmed = fiverr
    worker.image_ready_signal.emit("/nowhere/logo_1.png", 0)
    panel.stop()                                   # during concept 2
    assert worker.cancelled
    assert _rows() == []                           # not closed yet
    assert not panel.fiverr_generate_btn.isEnabled()
    worker.image_ready_signal.emit("/nowhere/logo_2.png", 1)   # paid in flight
    worker.running = False
    worker.error_signal.emit("Cancelled.")
    assert [r["cost_eur"] for r in _rows()] == [round(2 * rate, 6)]
    assert _run(run_id)["status"] == "cancelled"
    assert panel.fiverr_status_label.text() == (
        f"[Stopped] 2 of 4 concepts made; {money_text.paid(2 * rate)} of "
        f"{money_text.up_to(confirmed)} recorded.")
    assert panel.fiverr_generate_btn.isEnabled()


def test_fiverr_stop_after_the_worker_finished_bills_every_concept_made(
        win, fiverr):
    """Security review P3-1: all four concepts made, one delivered, the
    worker already exited with three images and its last signal still
    queued. Closing on isRunning() billed 1 of 4; the close now waits for
    the worker's last signal."""
    panel, worker, run_id, rate, confirmed = fiverr
    paths = [f"/nowhere/logo_{i + 1}.png" for i in range(4)]
    worker.image_ready_signal.emit(paths[0], 0)
    worker.running = False                 # finished; the rest still queued
    panel.stop()
    assert _rows() == []                   # not closed by the Stop
    assert not panel.fiverr_generate_btn.isEnabled()
    for i in range(1, 4):                  # the queued signals arrive
        worker.image_ready_signal.emit(paths[i], i)
    worker.all_done_signal.emit(paths)
    assert [(r["cost_type"], r["cost_eur"]) for r in _rows()] == [
        ("per_unit", pytest.approx(4 * rate, abs=1e-6))]
    assert confirmed == pytest.approx(4 * rate, abs=1e-6)
    assert _run(run_id)["status"] == "success"
    assert panel._image_stop_requested is False
    assert panel.fiverr_generate_btn.isEnabled()


def test_fiverr_stop_after_a_failure_already_queued_bills_what_was_made(
        win, fiverr):
    panel, worker, run_id, rate, _confirmed = fiverr
    worker.image_ready_signal.emit("/nowhere/logo_1.png", 0)
    worker.running = False
    panel.stop()
    assert _rows() == []
    worker.image_ready_signal.emit("/nowhere/logo_2.png", 1)
    worker.error_signal.emit("Concept 3 failed: timeout")
    assert [(r["cost_type"], r["cost_eur"]) for r in _rows()] == [
        ("partial", round(2 * rate, 6))]
    assert _run(run_id)["status"] == "cancelled"


def test_the_image_worker_always_ends_with_a_last_signal(app, tmp_path):
    """Stop waits for that signal, so a worker that cannot even make its
    folder must still send one."""
    from ui.workers import FiverrImageWorker
    blocker = tmp_path / "a_file"
    blocker.write_text("x")
    worker = FiverrImageWorker(None, "prompt", 2, blocker / "logos")
    ended = []
    worker.error_signal.connect(lambda e: ended.append(("error", e)))
    worker.all_done_signal.connect(lambda p: ended.append(("done", p)))
    worker.run()
    assert len(ended) == 1 and ended[0][0] == "error"
    assert ended[0][1].startswith("Could not create ")


def test_fiverr_stop_before_the_first_concept_records_nothing(win, fiverr):
    panel, worker, run_id, _rate, _confirmed = fiverr
    panel.stop()
    worker.running = False
    worker.error_signal.emit("Cancelled.")
    assert _rows() == []
    assert _run(run_id)["status"] == "cancelled"
    assert panel.fiverr_status_label.text() == (
        "[Stopped] Before the first concept: nothing recorded.")


def test_a_late_signal_from_a_closed_run_counts_for_nothing(win, fiverr):
    panel, worker, _run_id, _rate, _confirmed = fiverr
    worker.running = False
    worker.error_signal.emit("Concept 1 failed: x")
    worker.image_ready_signal.emit("/nowhere/late.png", 3)
    worker.error_signal.emit("Concept 2 failed: y")
    assert _rows() == []
    assert panel._images_made == 0


# ── The logs render HTML: every field is escaped (security review P3-4) ─────

def _log_host(runs=(), usage=()):
    """Just what the two log dialogs read from the window."""
    from types import SimpleNamespace
    from PySide6.QtWidgets import QWidget
    host = QWidget()
    host.run_logger = SimpleNamespace(load_recent=lambda _n: list(runs))
    host.usage_tracker = SimpleNamespace(load_log=lambda: list(usage))
    return host


def _browser_text(monkeypatch, show, host):
    from PySide6.QtWidgets import QDialog, QTextBrowser
    opened = []
    monkeypatch.setattr(QDialog, "exec", lambda self: opened.append(self) or 0)
    show(host)
    (dialog,) = opened
    return dialog.findChild(QTextBrowser).toPlainText()


MARKUP = "<b>bold</b> & <a href='x'>link</a>"


def test_the_run_log_shows_markup_as_text(app, monkeypatch):
    from ui.dialogs import show_run_log
    host = _log_host(runs=[{
        "timestamp": "2026-10-14T10:00:00", "run_id": "r1", "agent": MARKUP,
        "tool": "t", "provider": "openai", "model": MARKUP, "status": "error",
        "input_tokens": 1, "output_tokens": 2, "cost_eur": 0.5,
        "duration_sec": 1.0, "error": f"{MARKUP}; recorded €0.50 of €0.50"}])
    text = _browser_text(monkeypatch, show_run_log, host)
    assert f"{MARKUP}; recorded €0.50 of €0.50" in text
    assert text.count(MARKUP) == 3


def test_cost_history_shows_markup_as_text(app, monkeypatch):
    from ui.dialogs import show_cost_history
    host = _log_host(usage=[{
        "timestamp": "2026-10-14T10:00:00", "agent": MARKUP,
        "backend": "openai", "model": MARKUP, "input_tokens": 1,
        "output_tokens": 2, "total_tokens": 3, "cost_eur": 0.5,
        "cost_type": "partial"}])
    text = _browser_text(monkeypatch, show_cost_history, host)
    assert text.count(MARKUP) == 2
