"""
Imprint — Model updates tests
=============================
Type: unit (Qt-free rules) + window-level (the rail tile, the NEW badge and
the re-ranking), run headless.

The tile under API keys says when a provider has shipped a model Imprint has
not seen. Each rule here is one way that signal could lie: announcing the whole
catalogue on first launch, baselining an offline list, calling an embedding
model a new chat option, or flagging a dated snapshot as a release.

Run with:  pytest tests/test_model_watch.py -v
"""

import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.model_watch import ModelWatch, canonical, is_chat_model  # noqa: E402
from services.recommendations.catalog import (  # noqa: E402
    family, generation, provider_configured, text_candidates,
)


class _Clock:
    def __init__(self):
        self.ticks = 0

    def __call__(self):
        self.ticks += 1
        return f"2026-10-07T10:{self.ticks:02d}:00+00:00"


@pytest.fixture
def watch(tmp_path):
    return ModelWatch(tmp_path / "model_watch.json", clock=_Clock())


# ── the rules ───────────────────────────────────────────────────────────────

def test_first_look_is_a_baseline_not_news(watch):
    assert watch.observe("qwen", ["qwen3.8-max", "qwen-plus"]) == []
    assert watch.pending() == []
    assert watch.has_baseline("qwen")


def test_a_model_listed_for_the_first_time_is_announced_once(watch):
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"])
    news = watch.observe("qwen", ["qwen3.8-max", "qwen-plus", "qwen4-max"])
    assert [(n.provider, n.model_id) for n in news] == [("qwen", "qwen4-max")]
    assert watch.observe("qwen", ["qwen3.8-max", "qwen-plus", "qwen4-max"]) == []
    assert [n.model_id for n in watch.pending()] == ["qwen4-max"]


def test_dismissing_keeps_the_model_seen(watch):
    watch.observe("openai", ["gpt-5"])
    watch.observe("openai", ["gpt-5", "gpt-6"])
    watch.acknowledge()
    assert watch.pending() == []
    assert watch.observe("openai", ["gpt-5", "gpt-6"]) == []


def test_non_chat_models_are_never_announced(watch):
    watch.observe("qwen", ["qwen-plus"])
    news = watch.observe("qwen", ["qwen-plus", "text-embedding-v4",
                                  "qwen3-tts-flash", "wan3.0-video"])
    assert news == []


def test_a_dated_snapshot_of_a_known_model_is_not_a_release(watch):
    watch.observe("openai", ["gpt-5"])
    assert watch.observe("openai", ["gpt-5", "gpt-5-2026-10-01"]) == []
    # …but a new model arriving with its snapshot is one release, not two.
    news = watch.observe("openai", ["gpt-5", "gpt-6", "gpt-6-2026-10-05"])
    assert [n.model_id for n in news] == ["gpt-6"]


def test_an_empty_answer_is_not_recorded(watch):
    assert watch.observe("kimi", []) == []
    assert not watch.has_baseline("kimi")


def test_state_survives_a_restart(tmp_path):
    path = tmp_path / "model_watch.json"
    first = ModelWatch(path, clock=_Clock())
    first.observe("deepseek", ["deepseek-chat"])
    first.observe("deepseek", ["deepseek-chat", "deepseek-v5"])
    again = ModelWatch(path)
    assert [n.model_id for n in again.pending()] == ["deepseek-v5"]
    assert again.last_checked is not None


def test_a_corrupt_file_starts_over_instead_of_crashing(tmp_path):
    path = tmp_path / "model_watch.json"
    path.write_text("{not json", encoding="utf-8")
    watch = ModelWatch(path)
    assert watch.pending() == []
    watch.observe("qwen", ["qwen-plus"])
    assert json.loads(path.read_text())["providers"]["qwen"]["seen"] == ["qwen-plus"]


def test_helpers():
    assert canonical("claude-haiku-4-5-20251001") == "claude-haiku-4-5"
    assert canonical("gpt-5-2026-10-01") == "gpt-5"
    assert canonical("claude-opus-5-5") == "claude-opus-5-5"
    assert is_chat_model("qwen3.8-max")
    assert not is_chat_model("gemini-2.5-flash-image")
    assert not is_chat_model("text-embedding-3-large")


# ── the assessment ──────────────────────────────────────────────────────────

def test_a_newer_generation_outranks_the_one_it_replaces():
    assert family("qwen3.8-max") == family("qwen4-max") == "qwen-max"
    assert generation("claude-opus-5-5") > generation("claude-opus-4-6")
    by_id = {c.model_id: c for c in text_candidates(
        ["qwen"], {"qwen": ["qwen3.8-max", "qwen4-max", "qwen-plus"]})}
    assert by_id["qwen4-max"].quality > by_id["qwen3.8-max"].quality
    # A different tier is not "replaced" and gets no bonus.
    plain = {c.model_id: c for c in text_candidates(["qwen"], {"qwen": ["qwen-plus"]})}
    assert by_id["qwen-plus"].quality == plain["qwen-plus"].quality


def test_non_chat_ids_are_not_candidates():
    ids = {c.model_id for c in text_candidates(
        ["qwen"], {"qwen": ["qwen-plus", "text-embedding-v4"]})}
    assert ids == {"qwen-plus"}


def test_gemini_counts_as_configured_with_either_key_name(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert provider_configured("gemini") is False
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    assert provider_configured("gemini") is True


def test_higgsfield_needs_both_halves_of_its_key(monkeypatch):
    monkeypatch.setenv("HF_API_KEY_ID", "id")
    monkeypatch.delenv("HF_API_KEY_SECRET", raising=False)
    assert provider_configured("higgsfield") is False
    monkeypatch.setenv("HF_API_KEY_SECRET", "secret")
    assert provider_configured("higgsfield") is True


# ── the window ──────────────────────────────────────────────────────────────

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


class _FakeQwen:
    """A keyed Qwen client whose catalogue the test controls. No network."""

    KNOWN_MODELS = ["qwen3.8-max", "qwen3-max", "qwen-plus", "qwen-flash"]

    def __init__(self, models):
        self.models = list(models)
        self.calls = 0

    @staticmethod
    def key_available():
        return True

    def list_models_live(self):
        self.calls += 1
        return list(self.models)

    list_models = list_models_live


def _run_check(app, window):
    window.check_for_new_models()
    worker = window.model_scan_worker
    assert worker is not None
    assert worker.wait(5000)
    for _ in range(10):
        app.processEvents()


@pytest.fixture
def watched_window(app, window, tmp_path, monkeypatch):
    import main
    window.model_watch = ModelWatch(tmp_path / "model_watch.json")
    window.model_list_cache.pop("qwen", None)
    monkeypatch.setattr(main, "WATCHED_PROVIDERS", ("qwen",))
    original = window.qwen
    yield window
    window.qwen = original
    window.model_list_cache.pop("qwen", None)
    window.model_watch.acknowledge()
    window.refresh_model_updates()


def test_check_with_no_keys_says_so_and_calls_nothing(app, watched_window,
                                                      monkeypatch):
    window = watched_window
    window.qwen = types.SimpleNamespace(key_available=lambda: False)
    window.check_for_new_models()
    assert window.model_scan_worker is None or not window.model_scan_worker.isRunning()
    assert "Add a provider key" in window.model_updates_card.skipped_label.text()


def test_a_new_model_reaches_the_tile_the_menu_and_the_ranking(app, watched_window):
    from ui.widgets import NEW_MODEL_ROLE
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus", "qwen-flash"])
    _run_check(app, window)                         # baseline
    assert window.model_updates_card.headline.text() == "No new models"
    assert window.model_updates_section._title == "Model updates"

    window.qwen.models.append("qwen4-max")
    _run_check(app, window)
    card = window.model_updates_card
    assert card.headline.text() == "1 new model"
    assert window.model_updates_section._title == "Model updates · 1 new"
    assert card.dismiss_btn.isVisibleTo(card)

    # Ranked like everything else: the successor wins inside Qwen for the
    # agents that offer Qwen, and the tile says which.
    best_for = window._agents_preferring("qwen", "qwen4-max")
    assert best_for, "qwen4-max should be the best Qwen pick for some agent"
    assert window._agents_preferring("qwen", "qwen3.8-max") == ()

    # In the menu, marked NEW, on a panel that offers Qwen.
    panel = window._find_control("author_panel_base")
    panel.provider_box.setCurrentText("qwen")
    for _ in range(6):
        app.processEvents()
    box = panel.model_box
    index = box.findText("qwen4-max")
    assert index >= 0, [box.itemText(i) for i in range(box.count())]
    assert box.itemData(index, NEW_MODEL_ROLE) is True
    assert box.itemData(box.findText("qwen-plus"), NEW_MODEL_ROLE) is None

    window.dismiss_new_models()
    assert card.headline.text() == "No new models"
    assert box.itemData(box.findText("qwen4-max"), NEW_MODEL_ROLE) is None


def test_a_model_without_its_own_price_says_it_is_estimated(app, watched_window):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max"])
    _run_check(app, window)
    window.qwen.models.append("qwen-ultra-preview")
    _run_check(app, window)
    assert window._has_exact_price("qwen", "qwen3.8-max")
    assert not window._has_exact_price("qwen", "qwen-ultra-preview")


def test_the_startup_preference_is_saved(app, window, tmp_path, monkeypatch):
    import main
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(main, "SETTINGS_FILE", settings_file)
    window.model_updates_card.startup_checkbox.setChecked(False)
    assert json.loads(settings_file.read_text())["model_check_on_startup"] is False
    window.model_updates_card.startup_checkbox.setChecked(True)
    assert json.loads(settings_file.read_text())["model_check_on_startup"] is True
