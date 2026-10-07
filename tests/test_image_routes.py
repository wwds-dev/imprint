"""
Imprint — image routes beyond OpenAI
====================================
Type: unit + window-level, offline. Gemini runs through the real google-genai
SDK against an httpx MockTransport; DashScope's HTTP calls are replaced.

Stamp's logos and the video pipeline's scene images were OpenAI-only, so the
image assessment compared three OpenAI models and nothing else. Gemini (Nano
Banana) and Alibaba (Qwen Image) now generate too. Pinned here: the request
each provider documents, one request per image (a paid image is never
replayed), refusals that stop instead of retrying, a price for every model,
and the right provider authorized for each.

Run with:  pytest tests/test_image_routes.py -v
"""

import base64
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import image_generation as ig  # noqa: E402


def test_every_image_model_has_a_route_and_a_price():
    from services.per_unit_pricing import image_cost_eur
    models = ig.image_models()
    assert {"gemini-nano-banana-2.1", "gemini-3-pro-image", "qwen-image-3.0",
            "qwen-image-3.0-pro", "gpt-image-2"} <= set(models)
    for model in models:
        assert ig.provider_for(model) in {"OpenAI", "Gemini", "Qwen"}, model
        assert image_cost_eur(model, 1) and image_cost_eur(model, 1) > 0, model


def test_a_size_maps_to_its_nearest_ratio():
    assert ig.aspect_for_size("1536x1024") == "3:2"
    assert ig.aspect_for_size("1024x1536") == "2:3"
    assert ig.aspect_for_size("1920x1080") == "16:9"
    assert ig.aspect_for_size("nonsense") == "1:1"


def test_gemini_image_is_one_request_with_the_documented_shape(monkeypatch):
    import httpx
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    sent = []
    png = b"\x89PNG fake"

    def handler(request):
        sent.append(json.loads(request.content))
        if len(sent) == 1:
            return httpx.Response(503, json={"error": {"code": 503, "message": "busy",
                                                       "status": "UNAVAILABLE"}})
        return httpx.Response(200, json={
            "id": "i1", "status": "completed",
            "steps": [{"type": "model_output", "content": [
                {"type": "image", "mime_type": "image/png",
                 "data": base64.b64encode(png).decode()}]}]})

    mock = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(Exception):
        ig._gemini_image("gemini-nano-banana-2.1", "a fox mark", "1:1",
                         httpx_client=mock)
    assert len(sent) == 1                   # the 503 was not replayed
    assert ig._gemini_image("gemini-nano-banana-2.1", "a fox mark", "9:16",
                            httpx_client=mock) == png
    body = sent[1]
    assert body["model"] == "gemini-nano-banana-2.1"
    assert body["response_format"] == {"type": "image", "aspect_ratio": "9:16",
                                       "image_size": "1K"}
    assert body["store"] is False


def _qwen_post(responses, seen):
    def post(url, timeout=None, headers=None, json=None):
        seen.append({"url": url, "headers": headers, "json": json})
        status, body = responses.pop(0)
        return types.SimpleNamespace(status_code=status, json=lambda: body,
                                     text=str(body))
    return post


def test_qwen_image_sends_the_documented_request_and_downloads_the_result(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    seen = []
    monkeypatch.setattr(ig.requests, "post", _qwen_post([(200, {
        "output": {"choices": [{"message": {"content": [
            {"image": "https://result.example.test/img.png"}]}}]}})], seen))
    monkeypatch.setattr(ig.requests, "get", lambda url, timeout=None:
                        types.SimpleNamespace(content=b"PNG", raise_for_status=lambda: None))
    assert ig.generate_image("qwen-image-3.0", "a fox mark", aspect="16:9") == b"PNG"
    call = seen[0]
    assert call["url"].endswith("/services/aigc/multimodal-generation/generation")
    assert "X-DashScope-Async" not in call["headers"]      # 3.0-pro answers 429 to it
    assert call["json"]["model"] == "qwen-image-3.0"
    assert call["json"]["input"]["messages"][0]["content"] == [{"text": "a fox mark"}]
    assert call["json"]["parameters"]["size"] == "1376*768"
    assert call["json"]["parameters"]["n"] == 1


def test_a_qwen_account_problem_is_a_refusal(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(ig.requests, "post", _qwen_post(
        [(400, {"code": "Arrearage", "message": "overdue"})], []))
    with pytest.raises(ig.ImageRefused):
        ig.generate_image("qwen-image-3.0", "a fox mark")


def test_the_video_pipeline_sends_a_gemini_scene_to_gemini(monkeypatch):
    # Imported the way agents/video/studio.py does: `vidforge.vidforge`
    # would bind the outer folder as the `vidforge` package and break the
    # studio's own import for every later test.
    from agents.video import video_studio
    if not video_studio.available():
        pytest.skip(video_studio.unavailable_reason())
    from vidforge import visuals
    asked = []
    monkeypatch.setattr(ig, "generate_image",
                        lambda model, prompt, aspect="1:1", **k:
                        asked.append((model, aspect)) or b"img")
    assert visuals._other_provider_image(
        "gemini-nano-banana-2.1", "a lighthouse", "1024x1536") == b"img"
    assert asked == [("gemini-nano-banana-2.1", "2:3")]
    assert visuals._other_provider_image("gpt-image-2", "x", "1024x1024") is None


# ── Stamp and Reel in the window ────────────────────────────────────────────

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
        w = main.GodAI()
        w.show()
        app.processEvents()
        yield w
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


def test_stamp_offers_every_route_and_authorizes_the_models_provider(
        app, window, monkeypatch):
    for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "DASHSCOPE_API_KEY"):
        monkeypatch.setenv(key, "test-not-a-real-key")
    for name in ("openai", "gemini", "qwen"):
        getattr(window, f"allow_{name}_checkbox").setChecked(True)
    monkeypatch.setattr(window, "session_budget_eur", 1000.0)
    monkeypatch.setattr(window, "daily_budget_eur", 1000.0)
    asked = []
    monkeypatch.setattr(window, "authorize_request",
                        lambda agent, provider, model, prompt, **k:
                        asked.append((provider, model, k.get("assessment"))) and False)
    try:
        panel = window.fiverr_panel
        items = [panel.fiverr_image_model_box.itemText(i)
                 for i in range(panel.fiverr_image_model_box.count())]
        assert "gemini-nano-banana-2.1" in items and "qwen-image-3.0" in items
        panel._pending_count = 2
        panel._pending_brief = {}
        panel.fiverr_image_model_box.setCurrentText("gemini-nano-banana-2.1")
        panel._on_prompt_ready("a fox mark for a bakery")
        provider, model, assessment = asked[-1]
        assert (provider, model) == ("gemini", "gemini-nano-banana-2.1")
        offered = {o.candidate.provider for _s, o in assessment.ranked}
        assert offered == {"OpenAI", "Gemini", "Qwen"}
    finally:
        for name in ("openai", "gemini", "qwen"):
            getattr(window, f"allow_{name}_checkbox").setChecked(False)


def test_reel_will_not_render_gemini_scenes_without_gemini_permission(
        app, window, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    assert not window.allow_gemini_checkbox.isChecked()
    asked = []
    monkeypatch.setattr(window, "authorize_request",
                        lambda *a, **k: asked.append(a) and False)
    window.select_agent("video")
    for _ in range(4):
        app.processEvents()
    panel = window.video_panel
    panel.video_visual_provider_box.setCurrentText("Gemini")
    for _ in range(4):
        app.processEvents()
    box = panel.video_visual_model_box
    box.setCurrentIndex(next(i for i in range(box.count())
                             if box.itemData(i).model_id == "gemini-nano-banana-2.1"))
    panel.video_format_box.setEnabled(True)
    panel.video_format_box.setCurrentText("Long-form")
    panel.video_topic_input.setText("the history of lighthouses")
    for _ in range(4):
        app.processEvents()
    panel.render()
    assert asked == []


def test_a_gemini_scene_is_sent_once_even_when_it_fails(monkeypatch, tmp_path):
    """vidforge retries an OpenAI scene image up to three times; a Gemini or
    Qwen image is paid per request and must not be replayed."""
    from agents.video import video_studio
    if not video_studio.available():
        pytest.skip(video_studio.unavailable_reason())
    from vidforge import visuals
    calls = []

    def refuse(model, prompt, aspect="1:1", **kw):
        calls.append(model)
        raise ig.ImageRefused("Gemini refused the request")

    monkeypatch.setattr(ig, "generate_image", refuse)
    cfg = video_studio.load_config({"visuals.source": "ai",
                                    "visuals.image_model": "gemini-nano-banana-2.1"})
    with pytest.raises(ig.ImageRefused):
        visuals._generate_ai(cfg, "a lighthouse", tmp_path / "scene.png")
    assert calls == ["gemini-nano-banana-2.1"]
