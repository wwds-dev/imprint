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
from pathlib import Path
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


@pytest.fixture(autouse=True)
def generous_budget(request, monkeypatch):
    """The assessment honours the session, daily and project caps (as the
    guard does), and spend logged by earlier test modules lands in the shared
    test database's daily total. Tests here are about ranking, not caps, so
    they run with room to spare; the budget tests set their own."""
    if "window" not in request.fixturenames:
        return
    window = request.getfixturevalue("window")
    monkeypatch.setattr(window, "session_budget_eur", 1000.0)
    monkeypatch.setattr(window, "daily_budget_eur", 1000.0)


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
    # With the window's own ratings too: qwen4-max is unrated, and is held
    # at Qwen's best rating rather than credited with its name's estimate.
    candidates = {c.model_id: c for c in text_candidates(
        ["qwen"], {"qwen": window.model_list_cache["qwen"]},
        window._price_index(), window.ratings)}
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
def rate(window):
    """Rate a model as LMArena would once it has: the shipped ratings plus,
    in every text category, a row for `model` copied from `like`.

    Since 2026-10-08 a text model with no rating is never chosen while a rated
    one can be, so a test about a new model *winning* must first have it
    rated — which is also the only way it wins in the app.
    """
    import json
    from services import benchmarks
    from services.recommendations import ratings as ratings_module
    saved = window.ratings
    data = json.loads(ratings_module.snapshot_file().read_text(encoding="utf-8"))

    def rate_as(model, like):
        copied = 0
        for table, rows in data["categories"].items():
            if not table.startswith("text_style_control/"):
                continue
            source = next((row for row in rows if row[0] == like), None)
            if source is not None:
                rows.append([model, *source[1:]])
                copied += 1
        assert copied, f"{like} is not in the snapshot"
        window.ratings = benchmarks.RatingTable(data, origin="snapshot")

    yield rate_as
    window.ratings = saved


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
        app, watched_window, priced, rate):
    """New and marked is not enough: a dearer successor rated the same
    loses the assessment, and the agent stays where it is."""
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus", "qwen-flash"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen3.8-max")
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    rate("qwen4-max", like="qwen3.8-max")
    priced("qwen", "qwen4-max", 30.0, 120.0)        # far dearer, same rating

    _row(window, "qwen4-max").mark.setChecked(True)
    window.update_selected_models()
    assert author.model_box.currentText() == "qwen3.8-max"
    assert "nothing switched" in window.model_updates_card.result_label.text()
    assert window.model_watch.pending() == []        # the notice is handled


def test_a_marked_model_that_is_the_best_fit_is_switched_to(
        app, watched_window, priced, rate):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus", "qwen-flash"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen3.8-max")
    window.qwen.models += ["qwen4-max", "qwen4-flash"]
    _run_check(app, window)
    rate("qwen4-max", like="qwen3.8-max")           # rated the same...
    priced("qwen", "qwen4-max", 0.20, 0.60)         # ...at a tenth the price
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
        app, watched_window, priced, monkeypatch):
    """Qwen has a key here, so the only thing keeping the agent off it is
    the missing permission. (The first version of this test passed only
    because the suite blanks every key — a review proved the permission rule
    could be deleted with no test failing.)"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
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
    # The same ranking with the permission given does pick Qwen — so it was
    # the permission, not some other rule, that kept the agent where it was.
    window.allow_qwen_checkbox.setChecked(True)
    try:
        overall, _within = window._text_recommendations("author")
        assert overall.candidate.provider == "qwen"
    finally:
        window.allow_qwen_checkbox.setChecked(False)


# ── Every paid request is assessed ─────────────────────────────────────────

@pytest.fixture
def qwen_permitted(window, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    window.allow_qwen_checkbox.setChecked(True)
    yield
    window.allow_qwen_checkbox.setChecked(False)


def test_a_request_on_a_worse_choice_is_told_the_better_one(
        app, watched_window, priced, qwen_permitted, rate):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen4-max"])
    window.model_list_cache["qwen"] = list(window.qwen.models)
    rate("qwen4-max", like="qwen3.8-max")
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
    # Decided on the ratings, and said in their terms, credited.
    assert assessment.basis == "rating"
    assert "about the same quality" in text
    assert "the best value has the lower rate ($0.30 against" in text
    assert "LMArena leaderboard, CC BY 4.0" in text


def test_apply_switches_and_does_not_send(app, watched_window, priced,
                                         qwen_permitted, monkeypatch, rate):
    from PySide6.QtWidgets import QMessageBox
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen4-max"])
    window.model_list_cache["qwen"] = list(window.qwen.models)
    rate("qwen4-max", like="qwen3.8-max")
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
    assert "Best value: qwen · qwen4-max" in asked[0]


def test_a_request_already_on_the_best_choice_says_so(
        app, watched_window, priced, qwen_permitted, rate):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen4-max"])
    window.model_list_cache["qwen"] = list(window.qwen.models)
    rate("qwen4-max", like="qwen3.8-max")
    priced("qwen", "qwen4-max", 0.20, 0.60)
    assessment = window.assess_request("author", "qwen", "qwen4-max", "chapter")
    assert assessment.selected_is_best
    assert "your selection is the best value" in \
        window._assessment_text(assessment, 0.01)


def test_no_assessment_offer_when_nothing_is_permitted(app, watched_window,
                                                      monkeypatch):
    """Keys present, permissions absent: nothing can run, so nothing is
    offered. With the keys blanked this passed for the wrong reason."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    window = watched_window
    assert not window.allow_qwen_checkbox.isChecked()
    assert not window.allow_anthropic_checkbox.isChecked()
    assert window.assess_request("author", "anthropic", "claude-sonnet-4-6",
                                 "chapter") is None


def test_a_tie_is_never_reported_or_acted_on_as_a_win(app, watched_window, rate):
    """Same price, same ratings: qwen4-max and qwen3.8-max tie. The id order
    decides the tie, and "qwen4" sorts after "qwen3.8" — which must not
    surface as "best", nor move anyone."""
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen3.8-max")
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    rate("qwen4-max", like="qwen3.8-max")
    assert window._agents_preferring("qwen", "qwen4-max") == ()
    assert window._agents_preferring("qwen", "qwen3.8-max") == ()
    _row(window, "qwen4-max").mark.setChecked(True)
    window.update_selected_models()
    assert author.model_box.currentText() == "qwen3.8-max"


def test_the_last_live_list_follows_the_provider_and_drops_retired_models(watch):
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"])
    assert watch.last_live("qwen") == ["qwen-plus", "qwen3.8-max"]
    watch.observe("qwen", ["qwen-plus", "qwen4-max"])          # 3.8 retired
    assert watch.last_live("qwen") == ["qwen-plus", "qwen4-max"]
    # Still seen, so a return of the same id is not news.
    assert watch.observe("qwen", ["qwen-plus", "qwen4-max", "qwen3.8-max"]) == []
    assert watch.last_live("kimi") == []


def test_ranking_uses_an_earlier_sessions_live_list_before_the_check(
        app, watched_window):
    window = watched_window
    window.model_watch.observe("qwen", ["qwen3.8-max", "qwen-ultra"])
    window.model_list_cache.pop("qwen", None)
    assert window._best_known_models("qwen") == ["qwen-ultra", "qwen3.8-max"]
    window.model_list_cache["qwen"] = ["qwen-plus"]
    assert window._best_known_models("qwen") == ["qwen-plus"]


def test_the_badge_stays_on_a_selection_within_a_point_of_the_top(
        app, watched_window, qwen_permitted, rate):
    """qwen4-max and qwen3.8-max tie (same price, same ratings); the id
    order alone would hand qwen4-max the BEST FIT badge. The selection keeps
    it instead, and the tooltip says why."""
    from ui.widgets import RECOMMENDED_ROLE
    window = watched_window
    rate("qwen4-max", like="qwen3.8-max")
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen4-max"])
    window.model_list_cache["qwen"] = list(window.qwen.models)
    panel = _select(app, window, "author", "qwen")
    panel.load_models()
    _pump = lambda: [app.processEvents() for _ in range(4)]
    _pump()
    box = panel.model_box
    box.setCurrentIndex(box.findText("qwen3.8-max"))
    _pump()
    window.refresh_recommendation_marks("author")
    marked = [box.itemText(i) for i in range(box.count())
              if box.itemData(i, RECOMMENDED_ROLE)]
    assert marked == ["qwen3.8-max"]
    assert "costs about the same as the best value" in box.toolTip()



# ── Review of 2026-10-07: findings pinned ───────────────────────────────────

def test_a_lead_too_small_to_see_moves_nobody(app, watched_window, priced,
                                              qwen_permitted, rate):
    """qwen4-max one cent per 1M cheaper than qwen3.8-max: a lead of a few
    thousandths of a point. Update selected moved four agents on that."""
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen3.8-max")
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    rate("qwen4-max", like="qwen3.8-max")             # rated the same, so
    priced("qwen", "qwen4-max", 1.99, 6.0)            # vs 2.00 / 6.00
    assert window._agents_preferring("qwen", "qwen4-max") == ()
    assert window._agents_choosing_overall("qwen", "qwen4-max") == ()
    _row(window, "qwen4-max").mark.setChecked(True)
    window.update_selected_models()
    assert author.model_box.currentText() == "qwen3.8-max"


def test_a_model_found_later_reaches_a_menu_already_on_a_live_list(
        app, watched_window):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen-plus")
    author.load_models()
    for _ in range(4):
        app.processEvents()
    assert author.model_box.property("imprintModelsLive")
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    items = [author.model_box.itemText(i) for i in range(author.model_box.count())]
    assert "qwen4-max" in items, items
    assert author.model_box.currentText() == "qwen-plus"   # the choice is kept


def test_apply_never_leaves_an_agent_on_another_providers_wrong_model(
        app, watched_window):
    window = watched_window
    panel = _select(app, window, "author", "anthropic")
    before = (panel.provider_box.currentText(), panel.model_box.currentText())
    assert window._switch_agent_setup("author", "qwen", "qwen-nonexistent") is False
    assert (panel.provider_box.currentText(), panel.model_box.currentText()) == before


def test_the_dialog_reports_the_selections_own_score(window):
    import types as _types
    text = window._assessment_text(_types.SimpleNamespace(
        kind="text", agent="author", selected_is_best=True,
        selected_score=0.801, best_score=0.809, best_provider="qwen",
        best_model="x", best_cost_eur=0.01), 0.02)
    assert "(80/100)" in text


def test_an_offline_list_is_never_recorded_as_the_providers(app, watched_window):
    """A wrapper built before its key was set answers with KNOWN_MODELS while
    the key now reads as present; that list must not become the baseline."""
    window = watched_window
    stale = _FakeQwen(["qwen3.8-max"])
    stale.client = None
    window.qwen = stale
    assert window._observe_live_models("qwen", ["qwen3.8-max"]) is False
    assert not window.model_watch.has_baseline("qwen")


def test_quitting_during_a_model_check_does_not_abort(tmp_path):
    """A QThread still running at quit is destroyed under it and Qt aborts
    (SIGABRT, exit 134). The check starts by itself and a provider can take
    two minutes; the workers are daemon threads now."""
    import subprocess
    import sys as _sys
    script = tmp_path / "quit.py"
    script.write_text(
        "import os, sys, time\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parent.parent)!r})\n"
        "os.environ['QT_QPA_PLATFORM'] = 'offscreen'\n"
        "from PySide6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from ui.workers import ModelScanWorker\n"
        "class Slow:\n"
        "    def list_models_live(self):\n"
        "        time.sleep(30); return ['x']\n"
        "worker = ModelScanWorker({'qwen': Slow()})\n"
        "worker.start()\n"
        "time.sleep(0.2)\n"
        "assert not worker.wait(100)\n"
        "del worker\n"
        "app.quit()\n"
        "sys.exit(0)\n")
    result = subprocess.run([_sys.executable, str(script)], capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 0, (result.returncode, result.stderr[-800:])


def test_the_text_assessment_never_offers_what_the_guard_would_refuse(
        app, watched_window, monkeypatch):
    """Review finding: with €1 of session budget left, the dialog offered
    claude-opus-4-6 at €2.42 for a long chapter, and Apply switched to a
    request the guard then refused. Candidates now carry this request's cost
    and the engine's budget rule drops what the caps would refuse."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-not-a-real-key")
    window = watched_window
    window.allow_anthropic_checkbox.setChecked(True)
    window.allow_deepseek_checkbox.setChecked(True)
    monkeypatch.setattr(window, "session_budget_eur", 0.10)
    monkeypatch.setattr(window, "session_cost_total", 0.0)
    try:
        chapter = "The storm rolled in over the harbour. " * 4000   # ~150k chars
        remaining = window._remaining_budget_eur()
        assert remaining <= 0.10
        assessment = window.assess_request(
            "author", "deepseek", "deepseek-flash", chapter)
        if assessment is not None and not assessment.selected_is_best:
            assert assessment.best_cost_eur <= remaining, (
                assessment.best_provider, assessment.best_model,
                assessment.best_cost_eur)
    finally:
        window.allow_anthropic_checkbox.setChecked(False)
        window.allow_deepseek_checkbox.setChecked(False)


# ── public quality ratings ──────────────────────────────────────────────────

def test_the_window_ranks_on_the_shipped_ratings_and_credits_them(window):
    """conftest keeps the cache empty, so the snapshot in config/ is what
    loads; the tile names it, and its licence (CC BY 4.0) is credited."""
    assert window.ratings and window.ratings.origin == "snapshot"
    window.refresh_model_updates()
    label = window.model_updates_card.ratings_label
    assert label.text().startswith("Quality ratings: LMArena, published ")
    assert "CC BY 4.0" in label.text()
    assert "huggingface.co/datasets/lmarena-ai" in label.toolTip()


def test_a_ratings_refresh_re_ranks_and_a_failed_one_keeps_the_last(
        app, window, monkeypatch):
    from services import benchmarks
    from services.recommendations import ratings
    fresh = benchmarks.RatingTable({
        "published": "2026-10-08",
        "categories": {"text_style_control/overall": [
            ["claude-opus-5.5", 1500, 1495, 1505, 10_000, "anthropic"]]},
    }, origin="live")
    shipped = window.ratings
    monkeypatch.setattr(benchmarks, "is_stale", lambda *a, **k: True)
    try:
        monkeypatch.setattr(ratings, "refresh", lambda: fresh)
        window.refresh_model_ratings()
        assert window.ratings_worker.wait(5000)
        for _ in range(10):
            app.processEvents()
        assert window.ratings is fresh
        assert "published 2026-10-08 (fetched now)" in \
            window.model_updates_card.ratings_label.text()

        def loading():
            raise RuntimeError("the dataset index is loading")
        monkeypatch.setattr(ratings, "refresh", loading)
        window.refresh_model_ratings()
        assert window.ratings_worker.wait(5000)
        for _ in range(10):
            app.processEvents()
        assert window.ratings is fresh          # kept, not dropped to none
    finally:
        window.ratings = shipped
        window.refresh_model_updates()


def test_no_refresh_while_the_cached_ratings_are_fresh(window, monkeypatch):
    from services import benchmarks
    monkeypatch.setattr(benchmarks, "is_stale", lambda *a, **k: False)
    before = window.ratings_worker
    window.refresh_model_ratings()
    assert window.ratings_worker is before


# ── The rating rule (2026-10-08): the cheapest well-rated model wins ─────────

def test_an_unrated_new_model_is_not_chosen_however_cheap(
        app, watched_window, priced):
    """Sentinel's rule, chosen for Imprint: a model no rating covers is not
    chosen while a rated one can be — nothing shows it is good enough. The
    tile says so, so a NEW model that never wins is not a mystery."""
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus"])
    _run_check(app, window)
    author = _select(app, window, "author", "qwen", "qwen3.8-max")
    window.qwen.models += ["qwen4-max"]
    _run_check(app, window)
    priced("qwen", "qwen4-max", 0.01, 0.01)        # nearly free
    assert window._agents_preferring("qwen", "qwen4-max") == ()
    row = _row(window, "qwen4-max")
    texts = [label.text() for label in row.findChildren(type(window.model_updates_card.headline))]
    assert "Not rated yet — ranked below rated models" in texts
    row.mark.setChecked(True)
    window.update_selected_models()
    assert author.model_box.currentText() == "qwen3.8-max"


def test_the_dialog_says_why_in_ratings(app, watched_window, priced,
                                        qwen_permitted, rate):
    window = watched_window
    window.qwen = _FakeQwen(["qwen3.8-max", "qwen-plus", "qwen4-max"])
    window.model_list_cache["qwen"] = list(window.qwen.models)
    # qwen-plus is rated far below the best Qwen: told so, with the figure.
    below = window.assess_request("author", "qwen", "qwen-plus", "chapter")
    text = window._assessment_text(below, 0.01)
    assert below.basis == "rating" and not below.selected_is_best
    assert "Best value: qwen · qwen3.8-max" in text
    assert "more than 20 points below the best available" in text
    # qwen4-max has no rating: nothing shows it is good enough.
    unrated = window.assess_request("author", "qwen", "qwen4-max", "chapter")
    text = window._assessment_text(unrated, 0.01)
    assert unrated.selected_rating is None and not unrated.selected_is_best
    assert "Your selection: not rated" in text
    assert "No public rating covers your selection yet" in text
