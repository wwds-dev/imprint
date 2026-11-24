"""
Herald clips check the scene-image provider's key and permission (audit QB-3)
============================================================================
Type: window-level, run headless. No worker runs and no key is real: the
render worker is a recorder and the guard is replaced by one that records
what it was asked and refuses.

A Herald clip is authorized as provider "openai" (vidforge's script and
narration), but its scene images may be drawn by Gemini or Qwen when Apply on
the assessment picked one of their image models. The Video tab already
refused that render when the image provider had no key or was not ticked in
the API permissions row; Herald did not, so an unticked Gemini still spent.
Both flows now go through agents.video.panel.scene_provider_refused.

Run with:  pytest tests/test_herald_clip_provider.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ESTIMATE = {"script": 0.03, "narration": 0.112, "captions": 0.048,
            "images": 2.10, "per_image": 0.06, "scenes": 34, "total": 2.29}


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information,
             QMessageBox.critical)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.critical = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question, QMessageBox.information,
         QMessageBox.critical) = saved


@pytest.fixture
def herald(window, monkeypatch):
    """Herald one step before a clip render: the brief is written, OpenAI is
    keyed and permitted, the render worker and the guard are recorders."""
    import ui.workers as workers
    from agents.video import video_studio
    from PySide6.QtWidgets import QMessageBox
    panel = window.social_panel
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    for name in ("openai", "gemini", "qwen"):
        box = getattr(window, f"allow_{name}_checkbox")
        monkeypatch.setattr(box, "isChecked", lambda b=box: b._test_checked,
                            raising=False)
        box._test_checked = name == "openai"
    made = []
    monkeypatch.setattr(workers, "VideoWorker",
                        lambda *a, **k: made.append(k) or None)
    monkeypatch.setattr(video_studio, "pre_estimate",
                        lambda cfg: dict(ESTIMATE))
    monkeypatch.setattr(panel, "_clip_assessment", lambda *a, **k: None)
    asked = []

    def guard(agent, provider, model, *args, **kwargs):
        asked.append((agent, provider, model))
        return False                       # refuse: nothing renders

    monkeypatch.setattr(window, "authorize_request", guard)
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda parent, title, text, *a, **k: shown.append(title)))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(
        lambda parent, title, text, *a, **k: shown.append(title)))
    panel._brief_token = None
    panel._pending_clip = ("tiktok", 30)
    saved_visuals = panel._clip_visuals
    yield window, panel, asked, made, shown
    panel._clip_visuals = saved_visuals


def _scene_images(monkeypatch, model_id):
    from agents.video import video_studio
    monkeypatch.setattr(
        video_studio, "load_config",
        lambda overrides=None: {"visuals.source": "ai",
                                "visuals.image_model": model_id})


BRIEF = "A fox finds the lost library\nScene notes follow."


def test_an_unticked_gemini_refuses_the_clip(herald, monkeypatch):
    window, panel, asked, made, shown = herald
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    _scene_images(monkeypatch, "gemini-nano-banana-2.1")
    panel._on_clip_brief(BRIEF)
    assert asked == [], "the clip reached the guard as an openai request"
    assert made == []
    assert shown == ["Gemini Not Enabled"]
    assert "[Refused]" in panel.social_status_label.text()
    assert panel.social_clip_btn.isEnabled()


def test_a_qwen_image_model_without_a_key_refuses_the_clip(
        herald, monkeypatch):
    window, panel, asked, made, shown = herald
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    window.allow_qwen_checkbox._test_checked = True
    _scene_images(monkeypatch, "qwen-image-3.0")
    panel._on_clip_brief(BRIEF)
    assert asked == [] and made == []
    assert shown == ["Qwen Key Needed"]


def test_a_keyed_and_ticked_gemini_reaches_the_guard(herald, monkeypatch):
    window, panel, asked, made, shown = herald
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    window.allow_gemini_checkbox._test_checked = True
    _scene_images(monkeypatch, "gemini-nano-banana-2.1")
    panel._on_clip_brief(BRIEF)
    assert asked == [("video", "openai", "vidforge-pipeline")]
    assert shown == []


@pytest.mark.parametrize("cfg", [
    {"visuals.source": "ai", "visuals.image_model": "gpt-image-2.5-flare"},
    {"visuals.source": "pexels"},
    {"visuals.source": "gradient"},
])
def test_openai_stock_and_local_visuals_need_no_other_provider(
        herald, monkeypatch, cfg):
    from agents.video import video_studio
    window, panel, asked, made, shown = herald
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(video_studio, "load_config",
                        lambda overrides=None, c=cfg: dict(c))
    panel._on_clip_brief(BRIEF)
    assert asked == [("video", "openai", "vidforge-pipeline")]
    assert shown == []


def test_the_video_tab_still_refuses_an_unticked_image_provider(
        herald, monkeypatch):
    """The check moved into a shared function; the Video tab keeps it."""
    from agents.video.panel import scene_provider_refused
    from services.media_catalog import find_model
    window, panel, asked, made, shown = herald
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    gemini = find_model("Gemini", "gemini-3-pro-image")
    assert scene_provider_refused(window, window, gemini) is True
    window.allow_gemini_checkbox._test_checked = True
    assert scene_provider_refused(window, window, gemini) is False
    assert scene_provider_refused(
        window, window, find_model("OpenAI", "gpt-image-2")) is False
    assert scene_provider_refused(window, window, None) is False


def test_an_image_model_missing_from_the_catalog_is_refused(
        herald, monkeypatch):
    """Fail closed: an unknown id's provider cannot be checked."""
    window, panel, asked, made, shown = herald
    _scene_images(monkeypatch, "someone-elses-image-model")
    panel._on_clip_brief(BRIEF)
    assert asked == [] and made == []
    assert shown == ["Unknown Image Model"]


def test_the_check_runs_before_the_brief_is_paid_for(herald, monkeypatch):
    """Code review P3-1: refusing after the brief still billed the brief."""
    window, panel, asked, made, shown = herald
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    _scene_images(monkeypatch, "gemini-nano-banana-2.1")
    from agents.video import video_studio
    monkeypatch.setattr(video_studio, "available", lambda: True)
    monkeypatch.setattr(panel, "current_campaign",
                        lambda: {"id": 1, "name": "Launch", "brief": "x"})
    monkeypatch.setattr(panel, "_platform", lambda: __import__("types")
                        .SimpleNamespace(key="tiktok", name="TikTok",
                                         formats=("clip",)))
    panel.make_clip()
    assert asked == []                     # neither the brief nor the clip
    assert shown == ["Gemini Not Enabled"]
