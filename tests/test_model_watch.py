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
    price_efficiency, provider_configured, text_candidates,
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

def test_being_new_earns_no_edge():
    """A newer model is not automatically the better choice: with the same
    price and the same name pattern, a successor scores exactly the same."""
    prices = {"qwen": {"default": (1.65, 4.95)}}
    by_id = {c.model_id: c for c in text_candidates(
        ["qwen"], {"qwen": ["qwen3.8-max", "qwen4-max"]}, prices)}
    assert by_id["qwen4-max"].quality == by_id["qwen3.8-max"].quality
    assert by_id["qwen4-max"].cost_efficiency == by_id["qwen3.8-max"].cost_efficiency


def test_cost_comes_from_the_real_price_when_there_is_one():
    prices = {"qwen": {"default": (1.65, 4.95), "qwen4-max": (8.0, 40.0)}}
    by_id = {c.model_id: c for c in text_candidates(
        ["qwen"], {"qwen": ["qwen3.8-max", "qwen4-max"]}, prices)}
    # The dearer successor is the less cost-efficient one.
    assert by_id["qwen4-max"].cost_efficiency < by_id["qwen3.8-max"].cost_efficiency
    assert by_id["qwen3.8-max"].cost_efficiency == price_efficiency(1.65, 4.95)
    assert price_efficiency(0.1, 0.1) == 1.0
    assert price_efficiency(0.28, 0.42) > price_efficiency(3, 15) > price_efficiency(15, 75)


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

    # Ranked like everything else — and only like everything else: priced at
    # the same Qwen default, being new does not make it score any higher.
    from services.recommendations import RecommendationContext
    from agents.recommendation_profiles import profile_for
    candidates = {c.model_id: c for c in text_candidates(
        ["qwen"], {"qwen": window.model_list_cache["qwen"]},
        window._price_index())}
    context = RecommendationContext(agent="author", task="draft a chapter")
    score = lambda model: window.recommendation_engine.score(
        profile_for("author"), candidates[model], context)
    assert score("qwen4-max") == score("qwen3.8-max")

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


# ── Update selected ─────────────────────────────────────────────────────────

def test_acknowledging_some_models_keeps_the_rest(watch):
    watch.observe("qwen", ["qwen-plus"])
    watch.observe("qwen", ["qwen-plus", "qwen4-max", "qwen4-flash"])
    watch.acknowledge([("qwen", "qwen4-max")])
    assert [n.model_id for n in watch.pending()] == ["qwen4-flash"]
    assert watch.observe("qwen", ["qwen-plus", "qwen4-max", "qwen4-flash"]) == []


def _select(app, window, agent, provider, model=None):
    panel = window._find_control(f"{agent}_panel_base")
    panel.provider_box.setCurrentText(provider)
    for _ in range(6):
        app.processEvents()
    if model is not None:
        index = panel.model_box.findText(model)
        assert index >= 0, [panel.model_box.itemText(i)
                            for i in range(panel.model_box.count())]
        panel.model_box.setCurrentIndex(index)
    return panel


def _row(window, model_id):
    return next(r for r in window.model_updates_card.rows
                if r.notice.model_id == model_id)


@pytest.fixture
def priced(window):
    """Write pricing rows for the test, and drop them afterwards."""
    from services.database import get_connection
    written = []

    def put(provider, model, inp, out):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO pricing (backend, model, input_per_1m_usd, "
            "output_per_1m_usd) VALUES (?, ?, ?, ?)", (provider, model, inp, out))
        conn.commit()
        conn.close()
        written.append((provider, model))
        window._price_index_cache = None

    yield put
    conn = get_connection()
    for provider, model in written:
        conn.execute("DELETE FROM pricing WHERE backend = ? AND model = ?",
                     (provider, model))
    conn.commit()
    conn.close()
    window._price_index_cache = None


def test_clicking_a_row_marks_it_and_enables_update(app, watched_window):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus"])
    _run_check(app, window)
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    card = window.model_updates_card
    assert not card.update_btn.isEnabled()
    row = _row(window, "qwen4-max")
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=QPoint(60, 30))
    assert row.mark.isChecked()
    assert card.marked() == [("qwen", "qwen4-max")]
    assert card.update_btn.isEnabled()
    assert card.update_btn.text() == "Update 1 selected"
    # A repaint of the tile (a panel's fetch landing) keeps the mark.
    window.refresh_model_updates()
    assert card.marked() == [("qwen", "qwen4-max")]
    QTest.mouseClick(_row(window, "qwen4-max"), Qt.MouseButton.LeftButton,
                     pos=QPoint(60, 30))
    assert card.marked() == []
    assert not card.update_btn.isEnabled()


def test_a_marked_model_that_is_not_the_best_fit_switches_nothing(
        app, watched_window, priced):
    """New and marked is not enough: a dearer successor with the same fit
    loses the assessment, and the agent stays where it is."""
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus", "qwen-flash"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen3.8-max")
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    priced("qwen", "qwen4-max", 30.0, 120.0)        # far dearer, same tier

    _row(window, "qwen4-max").mark.setChecked(True)
    window.update_selected_models()
    assert author.model_box.currentText() == "qwen3.8-max"
    assert "nothing switched" in window.model_updates_card.result_label.text()
    assert window.model_watch.pending() == []        # the notice is handled


def test_a_marked_model_that_is_the_best_fit_is_switched_to(
        app, watched_window, priced):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus", "qwen-flash"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen3.8-max")
    window.qwen.models += ["qwen4-max", "qwen4-flash"]
    _run_check(app, window)
    priced("qwen", "qwen4-max", 0.20, 0.60)         # same tier, a tenth the price
    assert "Quill" in window._agents_preferring("qwen", "qwen4-max")

    card = window.model_updates_card
    _row(window, "qwen4-max").mark.setChecked(True)
    card.update_btn.click()
    for _ in range(6):
        app.processEvents()
    assert author.model_box.currentText() == "qwen4-max"
    assert "qwen4-max → " in card.result_label.text()
    assert "Quill" in card.result_label.text()
    # Only the marked notice is cleared.
    assert [n.model_id for n in window.model_watch.pending()] == ["qwen4-flash"]
    assert [r.notice.model_id for r in card.rows] == ["qwen4-flash"]


def test_update_never_moves_to_a_provider_that_is_not_permitted(
        app, watched_window, priced):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max"])
    _run_check(app, window)
    panel = _select(app, window, "author", "anthropic")
    before = panel.model_box.currentText()
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    priced("qwen", "qwen4-max", 0.20, 0.60)
    assert not window.allow_qwen_checkbox.isChecked()
    _row(window, "qwen4-max").mark.setChecked(True)
    window.update_selected_models()
    assert panel.provider_box.currentText() == "anthropic"
    assert panel.model_box.currentText() == before


# ── Every paid request is assessed ─────────────────────────────────────────

@pytest.fixture
def qwen_permitted(window, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    window.allow_qwen_checkbox.setChecked(True)
    yield
    window.allow_qwen_checkbox.setChecked(False)


def test_a_request_on_a_worse_choice_is_told_the_better_one(
        app, watched_window, priced, qwen_permitted):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen4-max"])
    window.model_list_cache["qwen"] = list(window.qwen.models)
    priced("qwen", "qwen4-max", 0.20, 0.60)
    _select(app, window, "author", "qwen", "qwen3.8-max")
    window._find_control("author_panel_base").load_models()

    assessment = window.assess_request(
        "author", "qwen", "qwen3.8-max", "Draft chapter three of the thriller")
    assert assessment is not None
    assert (assessment.best_provider, assessment.best_model) == ("qwen", "qwen4-max")
    assert not assessment.selected_is_best
    assert assessment.best_score > assessment.selected_score
    text = window._assessment_text(assessment, 0.05)
    assert "qwen · qwen4-max" in text and "Your selection" in text


def test_apply_switches_and_does_not_send(app, watched_window, priced,
                                         qwen_permitted, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen4-max"])
    window.model_list_cache["qwen"] = list(window.qwen.models)
    priced("qwen", "qwen4-max", 0.20, 0.60)
    panel = _select(app, window, "author", "qwen", "qwen3.8-max")
    panel.load_models()
    panel.model_box.setCurrentIndex(panel.model_box.findText("qwen3.8-max"))

    asked = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: (asked.append(a[2]), QMessageBox.Apply)[1]))
    assessment = window.assess_request("author", "qwen", "qwen3.8-max", "chapter")
    sent = window.confirm_external_api_request(
        "qwen", "qwen3.8-max", 0.05, 900, assessment)
    assert sent is False
    assert panel.model_box.currentText() == "qwen4-max"
    assert "Best fit: qwen · qwen4-max" in asked[0]


def test_a_request_already_on_the_best_choice_says_so(
        app, watched_window, priced, qwen_permitted):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen4-max"])
    window.model_list_cache["qwen"] = list(window.qwen.models)
    priced("qwen", "qwen4-max", 0.20, 0.60)
    assessment = window.assess_request("author", "qwen", "qwen4-max", "chapter")
    assert assessment.selected_is_best
    assert "your selection is the best fit" in window._assessment_text(assessment, 0.01)


def test_no_assessment_offer_when_nothing_is_permitted(app, watched_window):
    window = watched_window
    assert not window.allow_qwen_checkbox.isChecked()
    assert window.assess_request("author", "anthropic", "claude-sonnet-4-6",
                                 "chapter") is None


def test_a_tie_is_never_reported_or_acted_on_as_a_win(app, watched_window):
    """Same price, same name pattern: qwen4-max and qwen3.8-max tie. The id
    order decides the tie, and "qwen4" sorts after "qwen3.8" — which must not
    surface as "best", nor move anyone."""
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen3.8-max")
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    assert window._agents_preferring("qwen", "qwen4-max") == ()
    assert window._agents_preferring("qwen", "qwen3.8-max") == ()
    _row(window, "qwen4-max").mark.setChecked(True)
    window.update_selected_models()
    assert author.model_box.currentText() == "qwen3.8-max"
