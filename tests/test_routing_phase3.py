"""Routing phase 3 in Imprint: rated local models in BEST FIT, and the
automatic, guarded, background measurement of a new local model.

The rating module itself is tested in tests/test_local_ratings.py (shared with
Sentinel). Here: the band rule with a rated local candidate, the trigger that
measures a new model once, the request guard's refusal, and that the work never
runs on the GUI thread. Nothing switches a selection: Imprint's never-auto-switch
rule stands, a rating only moves the badge. No test reaches a network, a cloud
API or LM Studio.
"""

import os
import threading
from types import SimpleNamespace

import pytest

from agents.recommendation_profiles import profile_for
from services import benchmarks
from services import local_ratings as lr
from services.local_models import LocalInventory, LocalModel, Snapshot
from services.recommendations import RecommendationContext, RecommendationEngine
from services.recommendations import ratings as model_ratings
from services.recommendations.catalog import text_candidate

DOLPHIN = LocalModel(provider="lmstudio", id="dolphin-3.0-llama3.1-8b",
                     name="Dolphin 3.0 8B", quant="Q8_0")
GEMMA = LocalModel(provider="lmstudio", id="gemma-3-27b-it", name="Gemma 3 27B",
                   quant="Q4_K_M")


def table(rows):
    return benchmarks.RatingTable({
        "published": "2026-10-19",
        "categories": {f"text_style_control/{cat}": [
            [name, score, score - 5, score + 5, 10_000, org]
            for name, score, org in rows]
            for cat in ("overall", "creative_writing", "coding", "hard_prompts")},
    }, origin="snapshot")


TABLE = table([("claude-opus-5-5", 1400, "anthropic"),
               ("gpt-4.1-mini", 1390, "openai"),
               ("gemma-3-27b-it", 1395, "google")])
# Author's work is creative, longform and editing (rated as overall): kinds a
# measurement covers. Chat's includes analysis, which it does not (see the
# "not covered" test below).
AUTHOR = profile_for("author")
WRITING = RecommendationContext(agent="author")
CHAT = profile_for("chat")


@pytest.fixture
def local_lookup(tmp_path):
    inv = LocalInventory()
    inv.store(Snapshot(models=(DOLPHIN, GEMMA)))
    store = lr.RatingStore(tmp_path / "r.json")
    ratings = lr.LocalRatings(store, inv, lambda: TABLE)
    model_ratings.set_local_lookup(ratings.rating)
    try:
        yield store
    finally:
        model_ratings.set_local_lookup(None)


def _measure(store, model, score):
    store.record_result(model, lr.MeasureResult(lr.STATUS_MEASURED, kinds={
        kind: {"score": score, "n": 20} for kind in lr.KINDS}))


def _candidates():
    return [text_candidate("anthropic", "claude-opus-5-5", price=(4.0, 20.0),
                           ratings=TABLE, available=True),
            text_candidate("openai", "gpt-4.1-mini", price=(0.4, 1.6),
                           ratings=TABLE, available=True),
            text_candidate("lmstudio", DOLPHIN.id, ratings=TABLE, available=True)]


def test_a_rated_local_model_within_the_band_wins_at_price_zero(local_lookup):
    _measure(local_lookup, DOLPHIN, 1385.0)
    local = _candidates()[2]
    assert local.price_per_1m == 0.0 and local.ratings["general"] == 1385.0
    assert "(measured)" in local.quality_evidence["general"]
    result = RecommendationEngine().recommend(AUTHOR, _candidates(), WRITING)
    assert result.basis == "rating"
    assert (result.candidate.provider, result.candidate.model_id) == ("lmstudio", DOLPHIN.id)


def test_a_free_local_model_beats_a_cloud_model_whose_cost_score_is_saturated(local_lookup):
    """Cost efficiency tops out at 1.0, so a very cheap cloud model ties a
    free local one on score; inside the band the cheaper goes first."""
    _measure(local_lookup, DOLPHIN, 1385.0)
    penny = text_candidate("openai", "gpt-4.1-mini", price=(0.01, 0.02),
                           ratings=TABLE, available=True)
    local = text_candidate("lmstudio", DOLPHIN.id, ratings=TABLE, available=True)
    assert penny.cost_efficiency == local.cost_efficiency == 1.0
    result = RecommendationEngine().recommend(AUTHOR, [penny, local], WRITING)
    assert result.candidate.provider == "lmstudio"


def test_a_rated_local_model_outside_the_band_does_not_win(local_lookup):
    _measure(local_lookup, DOLPHIN, 1300.0)
    result = RecommendationEngine().recommend(AUTHOR, _candidates(), WRITING)
    assert result.candidate.model_id == "gpt-4.1-mini"


def test_an_unrated_local_model_still_never_wins(local_lookup):
    local = _candidates()[2]
    assert not local.ratings
    result = RecommendationEngine().recommend(AUTHOR, _candidates(), WRITING)
    assert result.candidate.provider != "lmstudio"
    assert "unrated" in result.reason


def test_a_local_model_is_unrated_for_work_its_evidence_does_not_cover(local_lookup):
    """Measured on writing only: no overall fallback for code or reasoning."""
    local_lookup.record_result(DOLPHIN, lr.MeasureResult(lr.STATUS_MEASURED, kinds={
        "writing": {"score": 1395.0, "n": 20}}))
    local = _candidates()[2]
    assert local.ratings["creative"] == 1395.0
    assert local.ratings["code"] is None and local.ratings["general"] is None
    engine = RecommendationEngine()
    code = RecommendationContext(agent="chat", task="code")
    assert engine.request_rating(CHAT, local, code) is None
    # Fully measured, it is still unrated for Chat, whose work includes
    # analysis (hard prompts): no measured kind and no base model covers it.
    _measure(local_lookup, DOLPHIN, 1395.0)
    local = _candidates()[2]
    assert engine.request_rating(CHAT, local, RecommendationContext(agent="chat")) is None


def test_an_inherited_rating_reaches_the_candidate(local_lookup):
    gemma = text_candidate("lmstudio", GEMMA.id, ratings=TABLE, available=True)
    assert gemma.ratings["general"] == pytest.approx(1385.0)          # 1395 − 10
    assert "rated (base model)" in gemma.quality_evidence["general"]


def test_zero_still_means_unknown_for_a_cloud_model(local_lookup):
    free_cloud = text_candidate("openai", "gpt-4.1-mini", price=(0.0, 0.0),
                                ratings=TABLE, available=True)
    assert free_cloud.price_per_1m is None


# ── the app: automatic, once, guarded, off the GUI thread ──────────────────

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(qapp):
    import main
    from PySide6.QtWidgets import QMessageBox
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in self.slots:
            slot(*args)


class FakeWorker:
    """Stands in for LocalMeasureWorker: records what would run, runs nothing."""
    started = []

    def __init__(self, model, plan, prompts, ask, store, cost, budget):
        self.model, self.plan, self.ask, self.budget = model, plan, ask, budget
        self.progress_signal, self.usage_signal = _Signal(), _Signal()
        self.finished_signal = _Signal()
        self._running = False

    def start(self):
        FakeWorker.started.append(self)
        self._running = True

    def isRunning(self):
        return self._running


PLAN = lr.Plan(references={k: ("anthropic", "claude-opus-5-5", 1400.0)
                           for k in lr.KINDS}, judge=("gemini", "gemini-3.8-flash"))


@pytest.fixture
def app(window, tmp_path, monkeypatch):
    import main
    store = lr.RatingStore(tmp_path / "local_ratings.json")
    monkeypatch.setattr(window, "local_rating_store", store)
    monkeypatch.setattr(window, "local_ratings",
                        lr.LocalRatings(store, window.local_inventory,
                                        lambda: window.ratings))
    monkeypatch.setattr(window, "local_measure_worker", None)
    monkeypatch.setattr(lr, "AUTOMATIC", True)
    monkeypatch.setattr(main, "LocalMeasureWorker", FakeWorker)
    FakeWorker.started = []
    saved = window.local_inventory.snapshot()
    window.local_inventory.store(Snapshot(models=(DOLPHIN,), lmstudio_up=True))
    monkeypatch.setattr(window, "_measurement_plan", lambda: (PLAN, ""))
    yield window
    window.local_inventory.store(saved)


def _allow(window, monkeypatch, allowed=True, key=True):
    import main
    monkeypatch.setattr(main, "provider_configured", lambda p: key)
    monkeypatch.setattr(window, "current_api_permissions",
                        lambda: {f"allow_{p}": allowed for p in
                                 ("openai", "deepseek", "kimi", "gemini", "anthropic",
                                  "qwen", "higgsfield", "elevenlabs")})
    monkeypatch.setattr(window, "session_budget_eur", 100.0)
    monkeypatch.setattr(window, "daily_budget_eur", 100.0)


def test_a_new_model_is_measured_automatically_once(app, monkeypatch):
    _allow(app, monkeypatch)
    app._on_local_discovery(app.local_inventory.snapshot())
    assert len(FakeWorker.started) == 1
    worker = FakeWorker.started[0]
    assert worker.model == DOLPHIN and worker.budget > 0
    assert app.local_ratings.text(DOLPHIN.provider, DOLPHIN.id) == "measuring… 0/80"
    worker.progress_signal.emit(12, 80)
    assert app.local_ratings.text(DOLPHIN.provider, DOLPHIN.id) == "measuring… 12/80"
    app._on_local_discovery(app.local_inventory.snapshot())
    assert len(FakeWorker.started) == 1                 # one run at a time
    worker._running = False
    worker.finished_signal.emit(lr.MeasureResult(
        lr.STATUS_MEASURED, kinds={"writing": {"score": 1281.0, "n": 20}}))
    assert app.local_ratings.text(DOLPHIN.provider, DOLPHIN.id) == "measured writing 1281"
    assert app.local_rating_store.entry(DOLPHIN)["automatic"] is True
    app._on_local_discovery(app.local_inventory.snapshot())
    app.maybe_measure_local_models()
    assert len(FakeWorker.started) == 1                 # measured once


def test_measurement_calls_are_billed_like_any_request(app, monkeypatch):
    logged = []
    monkeypatch.setattr(app.usage_tracker, "log_request",
                        lambda **kw: logged.append(kw) or {"estimated_cost": 0.002})
    before = app.session_cost_total
    app._on_measure_usage("gemini", "gemini-3.8-flash", "judge this", "A")
    assert logged[0]["agent"] == "chat" and logged[0]["backend"] == "gemini"
    assert app.session_cost_total == pytest.approx(before + 0.002)


def test_guard_refusal_leaves_the_model_unrated_with_a_measure_button(app, monkeypatch):
    _allow(app, monkeypatch, allowed=False)
    app._on_local_discovery(app.local_inventory.snapshot())
    assert FakeWorker.started == []
    entry = app.local_rating_store.entry(DOLPHIN)
    assert entry["status"] == lr.STATUS_REFUSED and "API permissions" in entry["reason"]
    assert app.local_ratings.text(DOLPHIN.provider, DOLPHIN.id) is None
    assert app.local_ratings.action(DOLPHIN) == "Measure"
    app.maybe_measure_local_models()
    assert FakeWorker.started == []                     # refused was the one try
    assert app.start_local_measure(DOLPHIN, automatic=False)   # Measure: confirm once
    assert len(FakeWorker.started) == 1


def test_budget_refusal_and_no_key(app, monkeypatch):
    _allow(app, monkeypatch)
    monkeypatch.setattr(app, "daily_budget_eur", 0.0)
    assert not app.start_local_measure(DOLPHIN, automatic=True)
    # The guard's refusal wording changed with the billing audit: it names the
    # cap and what is left rather than the word "budget".
    reason = app.local_rating_store.entry(DOLPHIN)["reason"].lower()
    assert "not sent" in reason and "cap" in reason and "left" in reason
    _allow(app, monkeypatch, key=False)
    assert not app.start_local_measure(DOLPHIN, automatic=True)
    assert "API key" in app.local_rating_store.entry(DOLPHIN)["reason"]
    assert FakeWorker.started == []


def test_the_real_plan_needs_a_cloud_key_and_ratings(window, monkeypatch):
    import main
    monkeypatch.setattr(window, "ratings", benchmarks.RatingTable())
    plan, why = window._measurement_plan()
    assert plan is None and "ratings" in why
    monkeypatch.setattr(window, "ratings", model_ratings.load())
    monkeypatch.setattr(main, "provider_configured", lambda p: False)
    plan, why = window._measurement_plan()
    assert plan is None and "key" in why
    monkeypatch.setattr(main, "provider_configured",
                        lambda p: p in {"anthropic", "gemini"})
    plan, why = window._measurement_plan()
    assert why == "" and plan.judge[0] in {"anthropic", "gemini"}
    assert {p for p, _, _ in plan.references.values()} <= {"anthropic", "gemini"}


def test_starting_a_measurement_does_no_model_work_on_the_gui_thread(app, monkeypatch):
    _allow(app, monkeypatch)
    calls = []
    monkeypatch.setattr(app, "run_backend", lambda *a, **k: calls.append(a) or "x")
    assert app.start_local_measure(DOLPHIN, automatic=False)
    assert calls == []


def test_the_measure_worker_runs_the_engine_off_the_gui_thread(qapp, tmp_path):
    from ui.workers import LocalMeasureWorker
    seen = []

    def ask(provider, model, prompt):
        seen.append(threading.current_thread())
        return "A" if provider == "gemini" else "answer"

    prompts = lr.PromptSet(1, {k: (("x", "p"),) for k in lr.KINDS})
    worker = LocalMeasureWorker(DOLPHIN, PLAN, prompts, ask,
                                lr.RatingStore(tmp_path / "r.json"), None, None)
    results = []
    worker.finished_signal.connect(results.append)
    worker.start()
    assert worker.wait(5000)
    qapp.processEvents()
    assert seen and all(t is not threading.main_thread() for t in seen)
    assert results and results[0].status == lr.STATUS_MEASURED


def test_closing_the_window_cancels_a_running_measurement():
    import inspect
    import main
    assert '"local_measure_worker"' in inspect.getsource(main.GodAI.closeEvent)
