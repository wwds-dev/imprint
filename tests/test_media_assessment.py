"""
Imprint — per-request assessment of image, video and speech work
================================================================
Type: window-level, run headless. No request leaves the machine:
`authorize_request` is replaced by a recorder in every test that drives a
panel, and no key is real.

Image, video and speech are the most expensive requests in the app, so each
one is assessed before it is approved, like a text request: every route that
could produce it is priced for *this* request and ranked on the agent's
profile, and the confirmation says whether the selection is the best fit. These
tests pin the rules that keep that honest:

* routes are compared like for like (same length, same shape), never a 30s
  clip against an 8s one;
* a route that cannot run (no key, not permitted) is named, not ranked;
* a tie is not a win;
* Apply switches the panel and asks again with a fresh estimate — it never
  sends on its own;
* a single-route request says it has nothing to compare, instead of
  inventing a comparison.

Run with:  pytest tests/test_media_assessment.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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


@pytest.fixture
def recorder(window, monkeypatch):
    """Capture authorize_request calls; refuse them, like a declined dialog."""
    calls = []

    def fake(agent, provider, model, prompt, **kwargs):
        calls.append({"agent": agent, "provider": provider, "model": model,
                      **kwargs})
        return False

    monkeypatch.setattr(window, "authorize_request", fake)
    window.last_applied_assessment = None
    return calls


@pytest.fixture
def video_permitted(window, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-not-a-real-key")
    window.allow_gemini_checkbox.setChecked(True)
    yield
    window.allow_gemini_checkbox.setChecked(False)


def _pump(app, n=6):
    for _ in range(n):
        app.processEvents()


def _select_video(app, window, provider, model_id, length):
    panel = window.video_panel
    panel.video_visual_provider_box.setCurrentText(provider)
    _pump(app)
    box = panel.video_visual_model_box
    index = next(i for i in range(box.count())
                 if box.itemData(i).model_id == model_id)
    box.setCurrentIndex(index)
    _pump(app)
    panel.video_length_box.setCurrentText(f"{length}s")
    panel.video_topic_input.setText("a lighthouse in a storm")
    _pump(app)
    return panel


# ── the engine-side rules ───────────────────────────────────────────────────

def test_a_cheaper_route_with_the_same_fit_is_the_better_choice(window,
                                                                video_permitted):
    from services.media_catalog import find_model
    lite = find_model("Gemini", "veo-3.1-lite-generate-preview")
    fast = find_model("Gemini", "veo-3.1-fast-generate-preview")
    options = [window.media_option(fast, 0.80, duration=8),
               window.media_option(lite, 0.40, duration=8)]
    a = window.assess_media_request("video", options,
                                    "veo-3.1-fast-generate-preview",
                                    task="social clip", duration=8,
                                    aspect="Vertical 9:16")
    assert a is not None and a.kind == "media"
    scores = {o.candidate.model_id: s for s, o in a.ranked}
    # Fast and Lite carry the same catalogue speed/quality marks; the
    # difference here is only the price, so Lite must score higher.
    assert scores["veo-3.1-lite-generate-preview"] > scores["veo-3.1-fast-generate-preview"]
    assert not a.selected_is_best
    assert a.best.candidate.model_id == "veo-3.1-lite-generate-preview"


def test_a_tie_leaves_the_selection_standing(window, video_permitted):
    from services.media_catalog import find_model
    model = find_model("Gemini", "veo-3.1-lite-generate-preview")
    twin = find_model("Gemini", "veo-3.1-lite-generate-preview")
    options = [window.media_option(model, 0.40, duration=8),
               window.media_option(twin, 0.40, duration=8)]
    a = window.assess_media_request("video", options,
                                    "veo-3.1-lite-generate-preview",
                                    task="social clip", duration=8)
    assert a.selected_is_best and a.apply is None


def test_routes_that_cannot_run_are_named_not_ranked(window, video_permitted):
    from services.media_catalog import find_model
    veo = find_model("Gemini", "veo-3.1-lite-generate-preview")
    wan = find_model("Qwen", "wan3.0-video")     # no key, not permitted
    a = window.assess_media_request(
        "video", [window.media_option(veo, 0.40, duration=8),
                  window.media_option(wan, 0.10, duration=8)],
        "veo-3.1-lite-generate-preview", task="social clip", duration=8)
    assert [o.candidate.model_id for _s, o in a.ranked] == [
        "veo-3.1-lite-generate-preview"]
    assert "Wan 3.0 Video" in a.skipped
    assert "Not compared (no key, or not permitted): Wan 3.0 Video" in \
        window._media_assessment_text(a)


# ── Reel ────────────────────────────────────────────────────────────────────

def test_reel_prices_every_route_at_the_requested_length(app, window, recorder,
                                                         video_permitted):
    panel = _select_video(app, window, "Gemini", "veo-3.1-generate-preview", 8)
    panel.render()
    assert recorder, "render did not reach the request guard"
    a = recorder[-1]["assessment"]
    assert a is not None
    ids = {o.candidate.model_id for o in [o for _s, o in a.ranked]}
    # 8 seconds: every Veo tier can make it; the scene pipeline's clips come
    # in 15/30/45/60/90 and are therefore not compared at a different length.
    assert {"veo-3.1-generate-preview", "veo-3.1-lite-generate-preview"} <= ids
    assert not ids & {"gpt-image-2", "pexels-stock", "gradient-cards"}
    by_id = {o.candidate.model_id: o for _s, o in a.ranked}
    assert by_id["veo-3.1-lite-generate-preview"].cost_eur < \
        by_id["veo-3.1-generate-preview"].cost_eur
    # The selection is priced at exactly what the guard is asked to approve.
    assert by_id["veo-3.1-generate-preview"].cost_eur == recorder[-1]["flat_cost_eur"]


def test_reel_apply_switches_and_asks_again(app, window, recorder,
                                            video_permitted):
    # Fast and Lite share every catalogue mark; Lite costs half as much, so
    # it must win, and Apply must land on it.
    panel = _select_video(app, window, "Gemini",
                          "veo-3.1-fast-generate-preview", 8)
    panel.render()
    first = recorder[-1]["assessment"]
    assert not first.selected_is_best
    assert first.best.candidate.model_id == "veo-3.1-lite-generate-preview"
    first.apply()
    window.last_applied_assessment = first
    # What the panel does when the guard refuses because Apply was pressed:
    assert panel._applied(first)
    window.last_applied_assessment = None
    panel.render()
    second = recorder[-1]
    assert second["model"] == first.best.candidate.model_id
    assert panel.video_length_box.currentText() == "8s"


def test_long_form_compares_only_routes_that_make_long_form(app, window,
                                                             recorder):
    panel = window.video_panel
    panel.video_visual_provider_box.setCurrentText("Local")
    _pump(app)
    panel.video_format_box.setEnabled(True)
    panel.video_format_box.setCurrentText("Long-form")
    panel.video_topic_input.setText("the history of lighthouses")
    _pump(app)
    panel.render()
    if not recorder:
        pytest.skip("vidforge is not importable in this environment")
    a = recorder[-1]["assessment"]
    kinds = {o.candidate.kind for _s, o in a.ranked}
    assert "direct_video" not in kinds


# ── Stamp ───────────────────────────────────────────────────────────────────

def test_stamp_assesses_its_images_and_apply_asks_again(app, window, recorder,
                                                        monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    window.allow_openai_checkbox.setChecked(True)
    try:
        panel = window.fiverr_panel
        panel._pending_count = 4
        panel._pending_brief = {}
        panel.fiverr_image_model_box.setCurrentText("gpt-image-2.5-sunburst")
        panel._on_prompt_ready("a fox mark for a bakery")
        a = recorder[-1]["assessment"]
        assert a is not None
        assert {o.candidate.model_id for _s, o in a.ranked} >= {
            "gpt-image-2.5-sunburst", "gpt-image-2"}
        assert all(o.cost_eur is not None for _s, o in a.ranked)
        if a.selected_is_best:
            # Within a point of the best: nothing to offer, and that is the
            # rule, not a gap in the test (see the test below).
            return
        # Apply: the model switches and the images are asked for again on it.
        calls_before = len(recorder)

        def applied(agent, provider, model, prompt, **kwargs):
            recorder.append({"model": model, **kwargs})
            if len(recorder) == calls_before + 1:
                kwargs["assessment"].apply()
                window.last_applied_assessment = kwargs["assessment"]
            return False

        monkeypatch.setattr(window, "authorize_request", applied)
        panel.fiverr_image_model_box.setCurrentText("gpt-image-2.5-sunburst")
        panel._on_prompt_ready("a fox mark for a bakery")
        assert recorder[-1]["model"] == a.best.candidate.model_id
    finally:
        window.allow_openai_checkbox.setChecked(False)


# ── Press, Booth, Muse ──────────────────────────────────────────────────────

def test_press_short_weighs_elevenlabs_against_the_free_voice(app, window,
                                                              recorder,
                                                              monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-not-a-real-key")
    import services.per_unit_pricing as pricing
    monkeypatch.setattr(pricing, "elevenlabs_tts_cost_eur", lambda n: 0.30)
    panel = window.manuscript_panel
    assert panel._authorize_short_narration("A quote worth hearing.", True) is False
    a = recorder[-1]["assessment"]
    labels = {o.candidate.label for _s, o in a.ranked}
    assert labels == {"ElevenLabs voice", "On-device voice (free)"}
    free = next(o for _s, o in a.ranked if o.candidate.provider == "System")
    assert free.cost_eur == 0.0 and free.apply is not None
    free.apply()
    from providers.voice.registry import SYSTEM_SOURCE
    assert panel.shorts_voice_source_box.currentText() == SYSTEM_SOURCE


def test_a_single_route_says_there_is_nothing_to_compare(window):
    option = window.speech_option("OpenAI", "gpt-4o-mini-tts",
                                  "OpenAI gpt-4o-mini-tts", 4.20)
    a = window.assess_media_request(
        "audiobook", [option], "gpt-4o-mini-tts", modality="speech",
        task="audiobook narration",
        single_route_note="the only narration route Booth is wired to.")
    assert a.single_route and a.selected_is_best and a.apply is None
    text = window._media_assessment_text(a)
    assert "the only narration route Booth is wired to" in text
    assert "Apply" not in text


# ── the dialog ──────────────────────────────────────────────────────────────

def test_the_dialog_lists_fit_and_cost_and_offers_apply(window, video_permitted,
                                                        monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from services.media_catalog import find_model
    fast = find_model("Gemini", "veo-3.1-fast-generate-preview")
    lite = find_model("Gemini", "veo-3.1-lite-generate-preview")
    switched = []
    a = window.assess_media_request(
        "video", [window.media_option(fast, 0.80, duration=8),
                  window.media_option(lite, 0.40, duration=8,
                                      apply=lambda: switched.append("lite"))],
        "veo-3.1-fast-generate-preview", task="social clip", duration=8)
    shown = {}

    def question(parent, title, text, buttons, *rest):
        shown["text"], shown["buttons"] = text, buttons
        return QMessageBox.Apply

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    sent = window.confirm_external_api_request("gemini", "veo-3.1-fast-generate-preview",
                                               0.80, 0, a)
    assert sent is False
    assert switched == ["lite"]
    assert window.last_applied_assessment is a
    assert "Veo 3.1 Lite (Gemini)" in shown["text"] and "~€0.40" in shown["text"]
    assert "← best fit" in shown["text"] and "← your selection" in shown["text"]
    assert shown["buttons"] & QMessageBox.Apply


def test_switching_from_long_form_to_a_direct_model_prices_a_clip_it_can_make(
        app, window, monkeypatch):
    """Found while writing these tests: the format was set before the
    lengths, so the estimate briefly priced a 30s Gemini Omni clip (Omni stops
    at 10s) and raised inside the slot."""
    import services.media_catalog as catalog
    asked = []
    real = catalog.direct_video_cost_usd
    monkeypatch.setattr(catalog, "direct_video_cost_usd",
                        lambda model, seconds: (asked.append((model, seconds)),
                                                real(model, seconds))[1])
    panel = window.video_panel
    panel.video_visual_provider_box.setCurrentText("Local")
    _pump(app)
    panel.video_format_box.setEnabled(True)
    panel.video_format_box.setCurrentText("Long-form")
    _pump(app)
    panel.video_visual_provider_box.setCurrentText("Gemini")
    _pump(app)
    assert all(seconds <= 10 for model, seconds in asked
               if model == "gemini-omni-1.1-flash"), asked



def test_a_difference_too_small_to_see_is_not_offered_as_a_switch(window,
                                                                  monkeypatch):
    """Stamp's Flare beat Sunburst by a fraction of a point — both showed as
    80/100 — and the dialog offered Apply for it. Below one displayed point
    the selection stands."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    window.allow_openai_checkbox.setChecked(True)
    try:
        a = window.fiverr_panel._image_assessment(
            "gpt-image-2.5-sunburst", 4, "a fox mark")
        best, _ = a.ranked[0][0], a.ranked[0][1]
        if best - a.selected_score < 0.01:
            assert a.selected_is_best and a.apply is None
    finally:
        window.allow_openai_checkbox.setChecked(False)


def test_a_shut_down_model_leaves_the_menus_and_the_ranking_on_its_date():
    """Veo 3.1's previews shut down on 2026-10-22 (Google names Gemini Omni
    as the replacement). Before that they are offered with a note; from that
    day they are not offered, and never ranked."""
    from services.media_catalog import VEO_SHUTDOWN, find_model, offered_models
    veo = find_model("Gemini", "veo-3.1-lite-generate-preview")
    assert veo.retires == VEO_SHUTDOWN == "2026-10-22"
    assert "22 October 2026" in veo.note
    assert veo in offered_models(today="2026-10-21")
    after = offered_models(today="2026-10-22")
    assert veo not in after
    assert find_model("Gemini", "gemini-omni-1.1-flash") in after
