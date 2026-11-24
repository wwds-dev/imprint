"""
Imprint — one prompt check on every image and video route, watermark on
=======================================================================
Type: unit + window-level, offline. Every client is a fake; no key is real.

Spec ai-act-safeguards (Comply R-P1-3, R-P1-4): only Higgsfield checked a
prompt before sending, and both DashScope calls asked Alibaba to drop its
AI watermark. Pinned here: the shared check refuses the unambiguous cases and
lets negations through; each entry point refuses before anything is reserved
or sent; the backstops in generate_image and VideoGenerationWorker hold even
if a panel skips its check; both DashScope payloads carry watermark=True.

Run with:  pytest tests/test_content_policy.py -v
"""

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import content_policy  # noqa: E402
from services.content_policy import ContentPolicyError, check_prompt, refusal  # noqa: E402

REFUSED = "a nude photo of my neighbour"
ALLOWED = "no nudity, a calm beach at dawn"


# ── the shared check ────────────────────────────────────────────────────────

@pytest.mark.parametrize("prompt, key", [
    (REFUSED, "explicit"),
    ("hardcore content", "explicit"),
    ("deepfake of a celebrity", "identity"),
    ("undress the woman in the reference photo", "identity"),
    ("bypass the nsfw filter", "circumvent"),
    # A negation only reaches across its own clause.
    ("explicit shots, no captions", "explicit"),
])
def test_unambiguous_prompts_are_refused_with_their_reason(prompt, key):
    assert content_policy.refused_key(prompt) == key
    assert refusal(prompt) == content_policy.REASONS[key]
    with pytest.raises(ContentPolicyError, match=content_policy.REASONS[key][:30]):
        check_prompt(prompt)


@pytest.mark.parametrize("prompt", [
    ALLOWED, "", None, "stylised promo, free of nudity, safe-for-work",
    "avoid deepfake effects entirely", "a book cover with a red fox",
    # The negation may sit two words before the match.
    "a promo with not any nudity",
])
def test_ordinary_and_negated_prompts_pass(prompt):
    assert refusal(prompt) is None
    check_prompt(prompt)


def test_higgsfield_keeps_its_own_wording_on_the_shared_patterns():
    from services import higgsfield_client
    assert higgsfield_client.ContentPolicyError is ContentPolicyError
    with pytest.raises(ContentPolicyError, match="Higgsfield prohibits identity"):
        higgsfield_client.check_prompt("face swap onto this photo")
    higgsfield_client.check_prompt(ALLOWED)


# ── watermark on (D1: always) ───────────────────────────────────────────────

class _Sent(Exception):
    pass


def test_qwen_image_asks_for_the_watermark(monkeypatch):
    from services import image_generation
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    sent = []

    def post(url, **kwargs):
        sent.append(kwargs["json"])
        raise _Sent

    monkeypatch.setattr(image_generation.requests, "post", post)
    with pytest.raises(_Sent):
        image_generation._qwen_image("qwen-image-3.0-pro", "a fox", "1:1")
    assert sent[0]["parameters"]["watermark"] is True


def test_wan_video_asks_for_the_watermark(monkeypatch):
    from services.media_catalog import WAN_VIDEO_MODELS
    from services.qwen_client import QwenClientWrapper
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    client = QwenClientWrapper()
    sent = []

    def post(url, **kwargs):
        sent.append(kwargs["json"])
        raise _Sent

    monkeypatch.setattr(client.video_session, "post", post)
    model = sorted(WAN_VIDEO_MODELS)[0]
    with pytest.raises(_Sent):
        client.create_video("a fox", model=model, seconds=5,
                            aspect_ratio="9:16")
    assert sent[0]["parameters"]["watermark"] is True


# ── backstops ───────────────────────────────────────────────────────────────

def test_generate_image_refuses_before_any_route(monkeypatch):
    from services import image_generation

    def explode(*a, **k):
        raise AssertionError("a refused prompt must not reach a provider")

    for name in ("_gemini_image", "_qwen_image"):
        monkeypatch.setattr(image_generation, name, explode)
    monkeypatch.setattr(image_generation, "provider_for", explode)
    with pytest.raises(ContentPolicyError):
        image_generation.generate_image("qwen-image-3.0-pro", REFUSED,
                                        openai_client=types.SimpleNamespace(
                                            generate_image=explode))


def test_generate_image_lets_an_allowed_prompt_through(monkeypatch):
    from services import image_generation
    monkeypatch.setattr(image_generation, "provider_for", lambda m: "Qwen")
    monkeypatch.setattr(image_generation, "_qwen_image",
                        lambda model, prompt, aspect: b"png")
    assert image_generation.generate_image("qwen-image-3.0-pro", ALLOWED) == b"png"


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _video_worker(prompt, calls):
    from ui.workers import VideoGenerationWorker

    class Client:
        def create_video(self, *a, **k):
            calls.append("create")
            raise _Sent

    worker = VideoGenerationWorker(Client(), prompt, "/nonexistent/out.mp4",
                                   provider="Qwen", model="wan3.0",
                                   seconds=5, aspect_ratio="9:16")
    errors = []
    worker.error_signal.connect(errors.append)
    return worker, errors


def test_video_worker_never_submits_a_refused_prompt(app):
    calls = []
    worker, errors = _video_worker(REFUSED, calls)
    worker.run()
    assert calls == []
    assert errors and errors[0].startswith("Not sent: ")
    # A local refusal is a verdict: the panel releases the reservation.
    assert not worker.retryable and not worker.timed_out


def test_video_worker_submits_an_allowed_prompt(app):
    calls = []
    worker, _errors = _video_worker(ALLOWED, calls)
    worker.run()
    assert calls == ["create"]


# ── the panels refuse before anything is reserved ───────────────────────────

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


def _record(monkeypatch, window, module):
    """Record warnings and authorize_request calls; a worker start fails."""
    warned, asked = [], []
    monkeypatch.setattr(module.QMessageBox, "warning",
                        lambda parent, title, text: warned.append((title, text)))
    monkeypatch.setattr(window, "authorize_request",
                        lambda *a, **k: asked.append(a) or None)

    def no_start(self):
        raise AssertionError("no worker may start for a refused prompt")

    monkeypatch.setattr("ui.workers.VideoGenerationWorker.start", no_start)
    return warned, asked


@pytest.mark.parametrize("route", ["gemini", "qwen"])
def test_creator_direct_teaser_refuses_before_reserving(window, monkeypatch, route):
    import agents.creator.panel as creator_panel
    panel = window.creator_panel
    warned, asked = _record(monkeypatch, window, creator_panel)
    monkeypatch.setattr(panel, "_teaser_route", lambda: route)
    monkeypatch.setattr("services.recommendations.catalog.provider_configured",
                        lambda r: True)
    monkeypatch.setattr(window, "_provider_permission", lambda r: True)
    rows = []
    monkeypatch.setattr(panel, "_video_job_update", rows.append)
    panel._generate_direct_teaser({"id": 1, "name": "Persona"}, REFUSED)
    assert asked == [] and rows == []
    assert warned == [("Content policy", content_policy.REASONS["explicit"])]


def test_creator_direct_teaser_still_asks_for_an_allowed_prompt(window, monkeypatch):
    import agents.creator.panel as creator_panel
    panel = window.creator_panel
    warned, asked = _record(monkeypatch, window, creator_panel)
    monkeypatch.setattr(panel, "_teaser_route", lambda: "gemini")
    monkeypatch.setattr("services.recommendations.catalog.provider_configured",
                        lambda r: True)
    monkeypatch.setattr(window, "_provider_permission", lambda r: True)
    monkeypatch.setattr(creator_panel, "reference_images", lambda account_id: [])
    monkeypatch.setattr(panel, "_teaser_assessment", lambda *a, **k: None)
    panel._generate_direct_teaser({"id": 1, "name": "Persona"}, ALLOWED)
    assert len(asked) == 1 and warned == []


@pytest.mark.parametrize("provider, model", [
    ("Gemini", "gemini-omni-1.1-flash"),
    ("Qwen", "wan3.0"),
    ("Higgsfield", "seedance-2.5"),
])
def test_video_workspace_refuses_every_direct_route_before_reserving(
        window, monkeypatch, provider, model):
    import agents.video.panel as video_panel
    panel = window.video_panel
    warned, asked = _record(monkeypatch, window, video_panel)
    persisted = []
    monkeypatch.setattr(panel, "_persist_submission",
                        lambda *a, **k: persisted.append(a))
    panel.video_topic_input.setText(REFUSED)
    panel.render_direct(types.SimpleNamespace(provider=provider, model_id=model))
    assert asked == [] and persisted == []
    assert warned == [("Content policy", content_policy.REASONS["explicit"])]
    assert panel.video_status_label.text() == "Not sent: content policy."
