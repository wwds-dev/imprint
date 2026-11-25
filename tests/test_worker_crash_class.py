"""
Worker crash class (audit 2026-11-23 fix-order step 4; spec worker-crash-class)
==============================================================================
Type: unit + window-level, run headless; fakes only, no network, no key.

TODO.md cards:
1. "Replacing a running `QThread` aborts the app" (code-review P1-1).
2. "Herald's Post Now runs the upload and the Google consent wait on the UI
   thread, with no timeout" (code-review P1-2).
3. "`closeEvent` does not name `music_worker` and `webdesign_worker`, and gives
   up after 2 s on the rest" (architecture A-1).

What these tests prove: the preconditions of the abort are gone. A start into
a busy slot is refused before anything is priced (the slot keeps its worker);
a running TrackedThread is held by the registry even when nothing else holds
it; Post Now leaves the network call to a background thread and bounds
Google's consent wait; quit cancels and waits for workers it was never told
about by name, on one budget, and the process leaves before Qt can destroy a
running QThread. What they do not prove: the Qt abort itself (a process-level
SIGABRT) is not reproduced inside the app, the packaged app is not launched,
and no real Google consent page is opened.

Mutations checked (each fails at least one test here):
- `slot_busy` always False (busy starts go through and replace the slot);
- `TrackedThread.start` not appending to the registry;
- `stop_all` skipping `cancel()`, or waiting `budget_ms` per worker;
- `leave_if_workers_alive` not calling `exit_fn`;
- `run_local_server` called without `timeout_seconds`;
- the YouTube publisher not marking a consent failure `safe_to_retry`;
- `ShortsWorker`/`render_short` ignoring `should_stop`;
- `ModelPullWorker._progress` not raising after `cancel()`.
"""

import ast
import gc
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "venv", "build", "dist", "tests", "backups", "archive",
             "_to_delete", ".git", ".claude", "node_modules"}


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _Busy:
    """Stands in for a worker that is still inside a blocking call."""

    def __init__(self):
        self.cancelled = False

    def isRunning(self):  # noqa: N802 - QThread's name
        return True

    def cancel(self):
        self.cancelled = True


class _Reached(Exception):
    """The start went past the busy check into pricing."""


def _blocking_thread_class():
    from ui.worker_registry import TrackedThread

    class Blocking(TrackedThread):
        def __init__(self, cancellable=True):
            super().__init__()
            self.release = threading.Event()
            self.cancellable = cancellable
            self.cancel_calls = 0

        def cancel(self):
            self.cancel_calls += 1
            if self.cancellable:
                self.release.set()

        def run(self):
            self.release.wait(10)

    return Blocking


def _app_python_files():
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield path, rel


# ── registry and slot rule (defects 1 and 3) ────────────────────────────────

def test_no_app_class_subclasses_qthread_directly():
    """ADR 0006 point 1: every QThread is a TrackedThread, so the registry
    holds every running worker and the quit sweep finds it."""
    offenders = []
    for path, rel in _app_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                name = (base.id if isinstance(base, ast.Name) else
                        base.attr if isinstance(base, ast.Attribute) else "")
                if name == "QThread" and str(rel) != "ui/worker_registry.py":
                    offenders.append(f"{rel}:{node.lineno} {node.name}")
    assert not offenders, offenders


def test_no_agent_stores_a_worker_in_a_host_slot_by_hand():
    """ADR 0006 point 2: `host.<slot> = worker` replaced a running QThread
    (Herald: Write Posts, then Make a Clip). Only start_in_slot may store one;
    clearing a slot to None is allowed (the registry holds the thread)."""
    offenders = []
    for path in sorted((ROOT / "agents").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if isinstance(node.value, ast.Constant) and node.value.value is None:
                continue
            for target in node.targets:
                if not (isinstance(target, ast.Attribute)
                        and target.attr.endswith("worker")):
                    continue
                owner = target.value
                on_host = ((isinstance(owner, ast.Attribute)
                            and owner.attr == "host")
                           or (isinstance(owner, ast.Name)
                               and owner.id == "host"))
                if on_host:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{node.lineno} "
                        f"{ast.unparse(target)}")
    assert not offenders, offenders


def test_chat_send_stores_its_worker_through_the_slot_rule():
    import inspect
    import main
    source = inspect.getsource(main.GodAI._send_chat)
    assert "self.chat_worker = " not in source
    assert 'start_in_slot(self, "chat_worker"' in source


def test_a_running_tracked_thread_is_held_by_the_registry(app):
    from ui.worker_registry import live_workers
    worker = _blocking_thread_class()()
    worker.start()
    ident = id(worker)
    del worker
    gc.collect()
    held = [w for w in live_workers() if id(w) == ident]
    assert held, "a running worker was left to the garbage collector"
    held[0].release.set()
    assert held[0].wait(5000)
    assert all(id(w) != ident for w in live_workers())


def test_start_in_slot_refuses_to_replace_a_running_worker(app):
    from types import SimpleNamespace
    from ui.worker_registry import WorkerSlotBusy, start_in_slot
    old = _Busy()
    host = SimpleNamespace(social_worker=old)

    class New:
        started = False

        def start(self):
            self.started = True

    new = New()
    with pytest.raises(WorkerSlotBusy):
        start_in_slot(host, "social_worker", new)
    assert host.social_worker is old and not new.started
    host.social_worker = None
    start_in_slot(host, "social_worker", new)
    assert host.social_worker is new and new.started


def test_refuse_if_busy_names_the_wait_and_checks_every_slot(app):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QLabel
    from ui.worker_registry import BUSY_TEXT, refuse_if_busy
    label = QLabel()
    host = SimpleNamespace(a=None, b=_Busy())
    assert not refuse_if_busy(host, label, "a")
    assert label.text() == ""
    assert refuse_if_busy(host, label, "a", "b")
    assert label.text() == BUSY_TEXT


# ── defect 1 in the window: every listed start refuses a busy slot ──────────

@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    from tests.qt_teardown import dispose
    saved = (QMessageBox.warning, QMessageBox.question,
             QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    win = main.GodAI()
    try:
        yield win
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved
        dispose(win)


def _model_box(monkeypatch, box, name="test-model"):
    monkeypatch.setattr(box, "currentText", lambda: name)


def _herald_write(window, monkeypatch):
    import agents.social.panel as social
    panel = window.social_panel
    monkeypatch.setattr(panel, "current_campaign", lambda: {"id": 1})
    monkeypatch.setattr(social, "build_post_messages",
                        lambda *a, **k: [{"role": "user", "content": "x"}])
    _model_box(monkeypatch, panel.social_model_box)
    return panel.write, panel.social_status_label


def _herald_clip(window, monkeypatch):
    import agents.social.panel as social
    from agents.social import platforms
    from agents.video import video_studio
    panel = window.social_panel
    monkeypatch.setattr(panel, "current_campaign", lambda: {"id": 1})
    monkeypatch.setattr(video_studio, "available", lambda: True)
    monkeypatch.setattr(video_studio, "load_config",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    monkeypatch.setattr(panel, "_platform", lambda: platforms.get("youtube"))
    monkeypatch.setattr(social, "build_clip_brief_messages",
                        lambda *a, **k: [{"role": "user", "content": "x"}])
    _model_box(monkeypatch, panel.social_model_box)
    return panel.make_clip, panel.social_status_label


def _label(window, monkeypatch):
    panel = window.music_panel
    panel.music_query_input.setPlainText("A four-track ambient release")
    _model_box(monkeypatch, panel.music_model_box)
    return panel.analyse, panel.music_status_label


def _sitebuilder(window, monkeypatch):
    panel = window.webdesign_panel
    panel.webdesign_brief_input.setPlainText("A landing page")
    _model_box(monkeypatch, panel.webdesign_model_box)
    return panel.generate, panel.webdesign_status_label


def _vector_delivery(window, monkeypatch):
    panel = window.fiverr_panel
    _model_box(monkeypatch, panel.fiverr_model_box)
    return panel.write_delivery, panel.fiverr_status_label


def _vector_gig(window, monkeypatch):
    panel = window.fiverr_panel
    _model_box(monkeypatch, panel.fiverr_model_box)
    return panel.write_gig, panel.fiverr_status_label


def _quill(window, monkeypatch):
    panel = window.author_panel
    panel.author_direction_input.setText("Continue the scene")
    _model_box(monkeypatch, panel.author_model_box)
    monkeypatch.setattr(panel.author_task_box, "currentText",
                        lambda: "Continue")
    return panel.write, panel.author_status_label


def _quill_publish(window, monkeypatch):
    panel = window.author_panel
    _model_box(monkeypatch, panel.author_model_box)
    return panel.pub_generate, panel.author_status_label


def _quill_market(window, monkeypatch):
    panel = window.author_panel
    _model_box(monkeypatch, panel.author_model_box)
    return panel.mkt_generate, panel.author_status_label


def _press_ask(window, monkeypatch):
    panel = window.manuscript_panel
    panel.manuscript_query_input.setPlainText("How are sales?")
    _model_box(monkeypatch, panel.manuscript_model_box)
    return panel.ask, panel.manuscript_status_label


def _press_quotes(window, monkeypatch):
    panel = window.manuscript_panel
    panel.quote_finder_text.setPlainText("A long passage. " * 20)
    _model_box(monkeypatch, panel.manuscript_model_box)
    return panel.quote_finder_suggest, panel.manuscript_status_label


def _press_calendar(window, monkeypatch):
    panel = window.manuscript_panel
    monkeypatch.setattr(panel, "_calendar_quotes_from_finder",
                        lambda: ["One line.", "Another line."])
    panel.calendar_tiktok_check.setChecked(True)
    _model_box(monkeypatch, panel.manuscript_model_box)
    return panel.generate_calendar, panel.manuscript_status_label


def _vector_logos(window, monkeypatch):
    import services.recommendations.catalog as catalog
    panel = window.fiverr_panel
    monkeypatch.setattr(panel, "_get_brief", lambda: {"business_name": "Acme"})
    monkeypatch.setattr(catalog, "provider_configured", lambda *_a: True)
    monkeypatch.setattr(window.agent_instances["fiverr"],
                        "build_image_prompt_request",
                        lambda brief: [{"role": "user", "content": "x"}])
    _model_box(monkeypatch, panel.fiverr_model_box)
    return panel.generate_logos, panel.fiverr_status_label


def _nova_draft(window, monkeypatch):
    panel = window.creator_panel
    monkeypatch.setattr(panel, "current_account", lambda: {"id": 1})
    monkeypatch.setattr(window.agent_instances["creator"], "build_draft_prompt",
                        lambda *a, **k: [{"role": "user", "content": "x"}])
    _model_box(monkeypatch, panel.creator_model_box)
    return panel.generate, panel.creator_status_label


def _nova_video(window, monkeypatch):
    panel = window.creator_panel
    monkeypatch.setattr(panel, "current_account", lambda: {"id": 1})
    # The first step after the busy check stands in for pricing here.
    monkeypatch.setattr(window.agent_instances["creator"], "build_video_prompt",
                        _reach_pricing)
    return panel.generate_video, panel.creator_video_status


def _reel_render(window, monkeypatch):
    panel = window.video_panel
    monkeypatch.setattr(panel, "_media_selection", _reach_pricing)
    return panel.render, panel.video_status_label


SITES = [
    # (name, setup, slot that is busy, slot the start would store into)
    ("herald write after stop", _herald_write, "social_worker", "social_worker"),
    ("herald clip while writing", _herald_clip, "social_worker", "social_worker"),
    ("herald clip while rendering", _herald_clip, "_social_clip_worker",
     "social_worker"),
    ("label after stop", _label, "music_worker", "music_worker"),
    ("sitebuilder after stop", _sitebuilder, "webdesign_worker",
     "webdesign_worker"),
    ("vector delivery after stop", _vector_delivery, "fiverr_text_worker",
     "fiverr_text_worker"),
    ("vector gig after stop", _vector_gig, "fiverr_text_worker",
     "fiverr_text_worker"),
    ("vector logos while prompting", _vector_logos, "fiverr_text_worker",
     "fiverr_text_worker"),
    ("vector logos while imaging", _vector_logos, "fiverr_image_worker",
     "fiverr_text_worker"),
    ("quill write after stop", _quill, "author_worker", "author_worker"),
    ("quill publish after stop", _quill_publish, "author_pub_worker",
     "author_pub_worker"),
    ("quill market after stop", _quill_market, "author_mkt_worker",
     "author_mkt_worker"),
    ("press ask", _press_ask, "manuscript_worker", "manuscript_worker"),
    ("press quote finder", _press_quotes, "quote_finder_worker",
     "quote_finder_worker"),
    ("press calendar captions", _press_calendar, "calendar_worker",
     "calendar_worker"),
    ("nova draft after stop", _nova_draft, "creator_worker", "creator_worker"),
    ("nova teaser while estimating", _nova_video,
     "creator_video_estimate_worker", "creator_video_worker"),
    ("nova teaser while rendering", _nova_video, "creator_video_worker",
     "creator_video_worker"),
    ("reel render after stop", _reel_render, "video_worker", "video_worker"),
]


def _reach_pricing(*_a, **_k):
    raise _Reached()


@pytest.mark.parametrize("name,setup,busy_slot,slot", SITES,
                         ids=[s[0] for s in SITES])
def test_a_start_into_a_busy_slot_is_refused_before_pricing(
        window, monkeypatch, name, setup, busy_slot, slot):
    from ui.worker_registry import BUSY_TEXT
    start, label = setup(window, monkeypatch)
    monkeypatch.setattr(window, "authorize_request", _reach_pricing)
    for attr in {busy_slot, slot}:
        monkeypatch.setattr(window, attr, None, raising=False)
    # Control: with nothing running, the same start reaches the guard.
    with pytest.raises(_Reached):
        start()
    old = _Busy()
    monkeypatch.setattr(window, busy_slot, old, raising=False)
    quill = window.author_panel
    for button in (quill.author_pub_generate_btn, quill.author_mkt_generate_btn):
        button.setEnabled(True)               # the control run disabled it
    start()                                   # must not raise _Reached
    assert getattr(window, busy_slot) is old
    assert label.text().endswith(BUSY_TEXT)
    if name.startswith("quill publish"):
        assert window.author_panel.author_pub_generate_btn.isEnabled()
    if name.startswith("quill market"):
        assert window.author_panel.author_mkt_generate_btn.isEnabled()


def test_kernel_send_after_stop_is_refused_before_pricing(window, monkeypatch):
    from ui.worker_registry import BUSY_TEXT
    window.input_box.setPlainText("hello")
    monkeypatch.setattr(window.agent_box, "currentText", lambda: "chat")
    monkeypatch.setattr(window, "build_user_prompt", _reach_pricing)
    monkeypatch.setattr(window, "chat_worker", None)
    with pytest.raises(_Reached):
        window._send_chat()
    old = _Busy()
    monkeypatch.setattr(window, "chat_worker", old)
    window._send_chat()
    assert window.chat_worker is old
    assert window.chat_status_label.text() == BUSY_TEXT


@pytest.mark.parametrize("entry", ["generate", "quote_finder", "calendar"])
def test_press_shorts_entry_points_share_one_busy_rule(window, monkeypatch,
                                                       entry):
    """QM-12: Generate a Short did not set the flag the other two checked, so
    a Quote Finder or calendar Short replaced the running ShortsWorker and
    orphaned the first narration's reservation."""
    import agents.manuscript.quote_graphics as graphics
    from PySide6.QtWidgets import QPushButton
    from types import SimpleNamespace
    panel = window.manuscript_panel
    monkeypatch.setattr(graphics, "render_quote_graphic", lambda *a, **k: None)
    monkeypatch.setattr(panel, "_authorize_short_narration", _reach_pricing)
    panel.shorts_quote_text.setPlainText("A line worth a short.")
    button = QPushButton()
    if entry == "calendar":
        monkeypatch.setattr(panel, "_calendar_slots", [SimpleNamespace(
            quote="A line worth a short.", format="short")])

    def start():
        if entry == "generate":
            panel.generate_short()
        elif entry == "quote_finder":
            panel.quote_finder_generate_short("A line worth a short.", button)
        else:
            panel.calendar_generate_asset(0, button)

    monkeypatch.setattr(window, "shorts_worker", None)
    with pytest.raises(_Reached):
        start()
    old = _Busy()
    monkeypatch.setattr(window, "shorts_worker", old)
    start()
    assert window.shorts_worker is old


# ── defect 2: Post Now off the UI thread, bounded consent ───────────────────

def test_post_now_publishes_off_the_ui_thread_and_records_the_result(
        window, monkeypatch, app):
    from PySide6.QtWidgets import QInputDialog, QMessageBox
    from agents.social import publishing, queue
    panel = window.social_panel
    seen = {}
    entered = threading.Event()
    release = threading.Event()

    class Ready:
        configured = True

        def publish(self, body, media_path, **kwargs):
            seen["main_thread"] = (threading.current_thread()
                                   is threading.main_thread())
            entered.set()
            release.wait(5)
            return publishing.PublishResult(permalink="https://example.test/p")

    monkeypatch.setattr(panel, "_selected_post", lambda: {
        "id": 7, "platform": "reddit", "status": "draft", "body": "b",
        "media_path": ""})
    monkeypatch.setattr(publishing, "publisher_for", lambda key: Ready())
    answers = iter([("rust", True), ("A title", True)])
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(
        lambda *a, **k: next(answers)))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(queue, "queue_post", lambda post_id, extra, **k: {
        "id": 99})
    monkeypatch.setattr(queue, "claim", lambda job_id: {
        "id": job_id, "idempotency_key": "k"})
    monkeypatch.setattr(queue, "request_args", lambda job: {})
    posted = []
    monkeypatch.setattr(queue, "mark_posted", lambda job_id, link: posted.append(
        (job_id, link, threading.current_thread() is threading.main_thread())))
    monkeypatch.setattr(panel, "refresh_schedule",
                        lambda: panel.social_post_btn.setEnabled(True))
    monkeypatch.setattr(window, "social_publish_worker", None, raising=False)

    started = time.monotonic()
    timer = threading.Timer(3, release.set)   # a UI-thread call would block
    timer.start()
    try:
        panel.post_selected()
        returned_after = time.monotonic() - started
    finally:
        timer.cancel()
    assert entered.wait(5)
    assert seen["main_thread"] is False
    assert returned_after < 2.5, "Post Now waited for the upload"
    assert not panel.social_post_btn.isEnabled()
    assert posted == []                       # not before the upload returns
    release.set()
    assert window.social_publish_worker.wait(5000)
    deadline = time.monotonic() + 5
    while not posted and time.monotonic() < deadline:
        app.processEvents()
    assert posted == [(99, "https://example.test/p", True)]   # on the GUI thread
    assert panel.social_post_btn.isEnabled()


def test_a_second_post_now_is_refused_while_one_is_publishing(
        window, monkeypatch):
    from agents.social import publishing
    from ui.worker_registry import BUSY_TEXT
    panel = window.social_panel
    monkeypatch.setattr(panel, "_selected_post", lambda: {
        "id": 7, "platform": "reddit", "status": "draft", "body": "b"})
    monkeypatch.setattr(publishing, "publisher_for", _reach_pricing)
    monkeypatch.setattr(window, "social_publish_worker", _Busy(),
                        raising=False)
    panel.post_selected()
    assert panel.social_status_label.text() == BUSY_TEXT


def test_a_failed_post_is_classified_on_the_ui_thread(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from agents.social import publishing, queue
    panel = window.social_panel
    calls = []
    monkeypatch.setattr(queue, "mark_retryable",
                        lambda job, msg: calls.append(("retryable", job)))
    monkeypatch.setattr(queue, "mark_uncertain",
                        lambda job, msg: calls.append(("uncertain", job)))
    monkeypatch.setattr(panel, "refresh_schedule", lambda: None)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda *a, **k: None))
    panel._on_publish_failed(1, publishing.PublishError("no", safe_to_retry=True))
    panel._on_publish_failed(2, RuntimeError("timeout"))
    assert calls == [("retryable", 1), ("uncertain", 2)]
    assert panel.social_status_label.text() == "Verification required"


def test_youtube_consent_wait_is_bounded_and_safe_to_retry(tmp_path,
                                                           monkeypatch):
    pytest.importorskip("google_auth_oauthlib")
    from google_auth_oauthlib import flow as oauth_flow
    from vidforge import youtube
    seen = {}

    class FakeFlow:
        def run_local_server(self, **kwargs):
            seen.update(kwargs)
            raise oauth_flow.WSGITimeoutError("Timed out")

    monkeypatch.setattr(youtube, "SECRETS_DIR", tmp_path)
    monkeypatch.setattr(youtube, "_client_secret_path",
                        lambda: tmp_path / "client_secret.json")
    monkeypatch.setattr(oauth_flow.InstalledAppFlow, "from_client_secrets_file",
                        classmethod(lambda cls, *a, **k: FakeFlow()))
    with pytest.raises(youtube.YouTubeConsentError):
        youtube._service()
    assert seen.get("timeout_seconds") == youtube.CONSENT_TIMEOUT_S
    assert 0 < youtube.CONSENT_TIMEOUT_S <= 600
    assert not (tmp_path / "youtube_token.json").exists()


def test_youtube_publisher_marks_only_a_consent_failure_safe(tmp_path,
                                                            monkeypatch):
    from agents.social import publishing
    from agents.video import video_studio
    from vidforge import youtube
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    monkeypatch.setattr(video_studio, "load_config", lambda *a, **k: {})
    publisher = publishing.YouTubePublisher()
    for raised, safe in ((youtube.YouTubeConsentError("closed"), True),
                         (youtube.YouTubeError("rejected"), False)):
        monkeypatch.setattr(youtube, "upload",
                            lambda *a, r=raised, **k: (_ for _ in ()).throw(r))
        with pytest.raises(publishing.PublishError) as caught:
            publisher.publish("body", str(clip), title="t")
        assert caught.value.safe_to_retry is safe


# ── defect 3: quit stops every worker, on one budget ────────────────────────

@pytest.mark.parametrize("slot", ["music_worker", "webdesign_worker", None])
def test_close_cancels_and_waits_for_workers_it_was_never_told_about(
        window, monkeypatch, slot):
    """A-1: music_worker and webdesign_worker were missing from the sweep;
    a worker in no slot at all (None) is found by the registry too."""
    from PySide6.QtGui import QCloseEvent
    worker = _blocking_thread_class()()
    if slot:
        monkeypatch.setattr(window, slot, worker)
    worker.start()
    try:
        window.closeEvent(QCloseEvent())
        assert worker.cancel_calls == 1
        assert worker.isFinished()
    finally:
        worker.release.set()
        worker.wait(5000)


def test_stop_all_uses_one_budget_for_every_worker(app):
    from ui.worker_registry import stop_all
    Blocking = _blocking_thread_class()
    stubborn = [Blocking(cancellable=False) for _ in range(3)]
    for worker in stubborn:
        worker.start()
    try:
        started = time.monotonic()
        still = stop_all(budget_ms=300)
        elapsed = time.monotonic() - started
        assert elapsed < 0.8, f"waited {elapsed:.2f}s for a 0.3s budget"
        assert still.count("Blocking") == 3
        assert all(w.cancel_calls == 1 for w in stubborn)
    finally:
        for worker in stubborn:
            worker.release.set()
            worker.wait(5000)


def test_the_process_leaves_before_qt_can_destroy_a_running_worker(app):
    from ui.worker_registry import leave_if_workers_alive, live_workers
    exits, flushed = [], []
    if not any(w.isRunning() for w in live_workers()):
        assert leave_if_workers_alive(exits.append, flushed.append) == []
        assert exits == [] and flushed == []
    worker = _blocking_thread_class()()
    worker.start()
    try:
        alive = leave_if_workers_alive(exits.append, lambda: flushed.append(1))
        assert "Blocking" in alive
        assert exits == [0] and flushed == [1]
    finally:
        worker.release.set()
        worker.wait(5000)


def test_main_leaves_through_the_guard_after_the_event_loop():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    run = source[source.rindex("    app.exec()"):]
    assert "\n    leave_if_workers_alive()" in run


def test_shorts_worker_cancel_skips_the_render(tmp_path, monkeypatch):
    from agents.manuscript import shorts_generator
    from agents.manuscript.workers import ShortsWorker
    rendered = []
    monkeypatch.setattr(shorts_generator, "_ffmpeg",
                        lambda *a: rendered.append(a))

    narrated = []

    class Voice:
        def synthesize(self, text, path, config):
            narrated.append(text)
            Path(path).write_bytes(b"mp3")

    # Review P2-1: a cancel must come before the narration, the only step
    # that can be paid; once narrated, the free render runs to the end.
    with pytest.raises(shorts_generator.ShortCancelled):
        shorts_generator.render_short(
            "q", tmp_path / "g.png", tmp_path / "s.mp4",
            voice_provider=Voice(), should_stop=lambda: True)
    assert narrated == [] and rendered == []
    asked = iter([False, True])
    shorts_generator.render_short(
        "q", tmp_path / "g.png", tmp_path / "s.mp4",
        voice_provider=Voice(), should_stop=lambda: next(asked))
    assert narrated == ["q"] and len(rendered) == 1
    narrated.clear()
    rendered.clear()

    worker = ShortsWorker("q", tmp_path / "g.png", tmp_path / "s.mp4",
                          False, "default")
    errors = []
    worker.error_signal.connect(errors.append)
    monkeypatch.setattr(shorts_generator, "get_voice_provider",
                        lambda *_a: Voice())
    worker.cancel()
    worker.run()                              # synchronously, on purpose
    assert narrated == [] and rendered == []
    assert errors and "cancelled" in errors[0]


def test_model_pull_worker_cancel_ends_the_download(app):
    from ui.workers import ModelPullWorker
    lines = []

    class Client:
        def pull_model(self, model, on_progress=None):
            for n in range(100):
                lines.append(n)
                on_progress("pulling", n, 100)

    worker = ModelPullWorker(Client(), "muse:test")
    errors, done = [], []
    worker.error_signal.connect(errors.append)
    worker.finished_signal.connect(done.append)
    worker.cancel()
    worker.run()                              # synchronously, on purpose
    assert lines == [0]
    assert done == [] and "stopped" in errors[0]
    assert worker.cancelled


@pytest.mark.parametrize("action", ["delete_post", "mark_posted",
                                    "delete_campaign"])
def test_a_post_in_flight_cannot_be_deleted_or_re_marked(window, monkeypatch,
                                                        action):
    """Security review P2-1: with the window live during an upload, Delete,
    Mark Posted and Delete campaign removed or overwrote the record the
    upload's result is written to."""
    from agents.social import store
    panel = window.social_panel
    touched = []
    for name in ("delete_post", "mark_posted", "delete_campaign"):
        monkeypatch.setattr(store, name, lambda *a, n=name: touched.append(n))
    monkeypatch.setattr(panel, "_selected_post", lambda: {
        "id": 7, "platform": "reddit", "status": "publishing", "body": "b"})
    monkeypatch.setattr(panel, "current_campaign",
                        lambda: {"id": 1, "name": "C"})
    monkeypatch.setattr(panel, "refresh_schedule", lambda: None)
    monkeypatch.setattr(panel, "refresh_campaigns", lambda: None)
    monkeypatch.setattr(window, "social_publish_worker", _Busy(),
                        raising=False)
    getattr(panel, action)()
    assert touched == []
    assert "being published" in panel.social_status_label.text()
    monkeypatch.setattr(window, "social_publish_worker", None)
    getattr(panel, action)()
    assert touched == [action]


def test_a_result_whose_record_is_gone_still_reaches_the_user(window,
                                                              monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from agents.social import publishing, queue
    panel = window.social_panel
    warned, noted = [], []

    def gone(*_a):
        raise queue.QueueError("That publish job no longer exists.")

    for name in ("mark_posted", "mark_retryable", "mark_uncertain"):
        monkeypatch.setattr(queue, name, gone)
    monkeypatch.setattr(panel, "refresh_schedule", lambda: None)
    monkeypatch.setattr(window, "_note_failure",
                        lambda where, exc: noted.append(where))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda _p, title, *a, **k: warned.append(title)))
    panel._on_published(1, publishing.PublishResult(permalink="https://x.test"))
    panel._on_publish_failed(2, RuntimeError("timeout"))
    assert warned == ["Posted, but not recorded",
                      "Result unknown — check the platform"]
    assert len(noted) == 2
