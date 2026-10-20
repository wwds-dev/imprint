"""Routing phase 4 in Imprint: the advisor on a real Chat send.

The advisor itself is tested in tests/test_routing_advisor.py (shared with
Sentinel). Here, on a real offscreen window with a fake worker: the banner
holds a job and starts nothing; each answer runs the right model, and a paid
one still meets the paid-request dialog; the agent's own selection is never
changed (Imprint's never-auto-switch rule); a rule is followed next time; a
local run is tallied; a failed run offers the next candidate and never sends
it; Local only never offers the cloud. No test reaches a network, a cloud API
or LM Studio, and the advisor never asks a provider for its models.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal

from services import routing_advisor as ra
from services.local_models import LocalModel, Snapshot
from services.recommendations.models import Candidate as EngineCandidate

LOCAL_ID = "deepseek-r1-distill-qwen-14b"
SMALL_ID = "dolphin3.0-llama3.1-8b"
LOCAL = LocalModel(provider="lmstudio", id=LOCAL_ID, name="DeepSeek R1 Distill 14B",
                   quant="Q6_K", size_bytes=12_000_000_000, max_context=32_000)
SMALL = LocalModel(provider="lmstudio", id=SMALL_ID, name="Dolphin 3.0 8B",
                   quant="Q8_0", size_bytes=9_000_000_000, max_context=32_000)
SONNET = ("anthropic", "claude-sonnet-5-5")


class FakeChatWorker(QObject):
    token_signal = Signal(str)
    status_signal = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str)
    usage_signal = Signal(dict)
    instances: list = []

    def __init__(self, backend, model, messages):
        super().__init__()
        self.backend, self.model, self.messages = backend, model, list(messages)
        self.running = False
        FakeChatWorker.instances.append(self)

    def start(self):
        self.running = True

    def isRunning(self):          # noqa: N802 - Qt name
        return self.running

    def cancel(self):
        self.running = False
        self.error_signal.emit("Cancelled")

    def finish(self, text, usage=None):
        if usage is not None:
            self.usage_signal.emit(usage)
        self.running = False
        self.finished_signal.emit(text)

    def fail(self, message):
        self.running = False
        self.error_signal.emit(message)


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _engine(provider, model, score, price=None, cost=None, local=False):
    return EngineCandidate(
        provider, model, model, ratings={} if score is None else {"general": score},
        quality_evidence={"general": "measured"} if local and score else {},
        price_per_1m=0.0 if local else price, estimated_cost=0.0 if local else cost,
        available=True)


@pytest.fixture
def win(qapp, monkeypatch, tmp_path):
    import main
    from PySide6.QtWidgets import QMessageBox

    FakeChatWorker.instances.clear()
    questions: list = []
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: None))

    def question(*a, **k):
        questions.append(a[2] if len(a) > 2 else "")
        return QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))

    # Mode changes save the settings: never into the session's shared copy,
    # or every later window would start in this test's mode.
    settings_copy = tmp_path / "settings.json"
    settings_copy.write_text(main.SETTINGS_FILE.read_text() if main.SETTINGS_FILE.is_file() else "{}")
    monkeypatch.setattr(main, "SETTINGS_FILE", settings_copy)
    # A database of its own: the suite's session database carries spend from
    # every other test, and that spend decides whether a paid suggestion fits
    # today's budget.
    from services import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "imprint.db")
    database.init_db()
    window = main.GodAI()
    window.questions = questions
    window._new_chat_worker = lambda b, m, msgs, p: FakeChatWorker(b, m, msgs)
    window.check_memory_before_request = lambda *a, **k: True
    window.routing_rules = ra.RoutingRules(tmp_path / "rules.json")
    window.savings_tally = ra.SavingsTally(tmp_path / "savings.json")
    window.local_inventory.store(Snapshot(models=(LOCAL, SMALL), lmstudio_up=True,
                                          ram_free_bytes=20e9, ram_total_bytes=24e9,
                                          taken_at=1.0))
    window.agent_box.setCurrentText("chat")
    window.settings.pop(ra.OVERRIDES_KEY, None)
    window.settings[ra.MODE_KEY] = ra.LOCAL_ADVISE
    window._sync_execution_mode()
    window.allow_anthropic_checkbox.setChecked(True)
    window.selected = ("lmstudio", LOCAL_ID)
    window.resolve_backend_model = lambda: window.selected
    window.ratings_for_test = {}
    real = window._text_candidates_for

    def candidates(agent, prompt=None, task=None):
        built = real(agent, prompt, task)
        if built is None:
            return None
        _c, profile, context = built
        r = window.ratings_for_test
        mode = window.routing_mode(agent)
        cloud = [] if mode == ra.LOCAL_ONLY else [
            _engine(*SONNET, r.get("sonnet", 1300), price=4.5, cost=0.19)]
        return ([_engine("lmstudio", LOCAL_ID, r.get("local"), local=True),
                 _engine("lmstudio", SMALL_ID, r.get("small", 1205), local=True)]
                + cloud, profile, context)
    window._text_candidates_for = candidates
    selection = (window.provider_box.currentText(), window.model_box.currentText())
    window.selection_before = selection
    yield window
    window.chat_worker = None


def _send(win, text="Write a short note to my landlord about the heating", local=1290):
    win.ratings_for_test["local"] = local
    win.input_box.setPlainText(text)
    real = win.model_list_cache
    win.send_prompt()
    assert win.model_list_cache is real


def _worker():
    return FakeChatWorker.instances[-1] if FakeChatWorker.instances else None


def _selection_unchanged(win):
    return (win.provider_box.currentText(), win.model_box.currentText()) == win.selection_before


# ── The banner holds the job ─────────────────────────────────────────────────
def test_a_good_enough_local_model_runs_without_a_banner(win):
    _send(win)
    assert win.advice_banner.isHidden()
    assert (_worker().backend, _worker().model) == ("lmstudio", LOCAL_ID)
    assert win.questions == []


def test_a_quality_gap_holds_the_job_and_starts_nothing(win):
    _send(win, local=1200)
    assert not win.advice_banner.isHidden() and _worker() is None
    advice = win.advice_banner.advice
    assert advice.codes == (ra.QUALITY_GAP,) and advice.suggestion.key == SONNET
    assert _selection_unchanged(win)


def test_switch_for_this_job_goes_through_the_paid_request_dialog(win):
    _send(win, local=1200)
    win.advice_banner.switch_button.click()
    assert (_worker().backend, _worker().model) == SONNET
    assert len(win.questions) == 1 and "external API" in win.questions[0]
    assert _selection_unchanged(win)              # never-auto-switch
    assert win.routing_rules.all() == []


def test_declining_the_paid_request_dialog_sends_nothing(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    _send(win, local=1200)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    win.advice_banner.switch_button.click()
    assert _worker() is None


def test_keep_local_runs_the_local_model(win):
    _send(win, local=1200)
    win.advice_banner.keep_button.click()
    assert (_worker().backend, _worker().model) == ("lmstudio", LOCAL_ID)
    assert win.questions == []


def test_unmeasured_suggests_without_urging(win):
    _send(win, local=None)
    advice = win.advice_banner.advice
    assert advice.codes == (ra.UNMEASURED,) and not advice.urge


def test_server_off_is_named(win):
    win.local_inventory.store(Snapshot(models=(LOCAL, SMALL), lmstudio_up=False,
                                       ram_free_bytes=20e9, taken_at=2.0))
    _send(win)
    assert ra.NOT_RUNNABLE in win.advice_banner.advice.codes
    assert win.advice_banner.keep_button.isHidden()


# ── Rules ────────────────────────────────────────────────────────────────────
def test_always_is_remembered_and_followed_through_the_dialog(win):
    _send(win, local=1200)
    win.advice_banner.always_button.click()
    rules = win.routing_rules.all()
    assert len(rules) == 1 and (rules[0].provider, rules[0].model) == SONNET
    _worker().finish("ok")
    FakeChatWorker.instances.clear()
    _send(win, "Write a thank-you note to my neighbour", local=1200)
    assert win.advice_banner.isHidden()
    assert (_worker().backend, _worker().model) == SONNET
    assert len(win.questions) == 2                 # the dialog still asks
    assert _selection_unchanged(win)


def test_settings_dialog_has_models_tab_and_lists_rules(win, monkeypatch):
    from PySide6.QtWidgets import QDialog, QTabWidget
    from ui import dialogs
    from ui.routing_page import RoutingModesPage

    win.routing_rules.add("chat", "code", *SONNET, "code")
    seen = {}

    def capture(self):
        tabs = self.findChild(QTabWidget)
        seen["tabs"] = [tabs.tabText(i) for i in range(tabs.count())]
        seen["page"] = self.findChild(RoutingModesPage)
    monkeypatch.setattr(QDialog, "exec", capture)
    dialogs.show_settings(win)
    assert "Models" in seen["tabs"]
    page = seen["page"]
    assert page.rules_table.rowCount() == 1
    page.rules_table.cellWidget(0, 3).click()
    assert win.routing_rules.all() == []
    page.mode_buttons[ra.CLOUD_ONLY].click()
    assert win.execution_mode_box.currentText() == "Cloud only"


def test_applying_a_recommendation_keeps_the_saved_mode(win):
    win.settings[ra.MODE_KEY] = ra.SUGGEST_LOCAL
    win._applying_recommendation = True
    try:
        win.execution_mode_box.setCurrentText("Local only")
    finally:
        win._applying_recommendation = False
    assert win.settings[ra.MODE_KEY] == ra.SUGGEST_LOCAL
    assert win.routing_mode() == ra.LOCAL_ONLY


def test_user_moving_the_mode_box_updates_the_setting(win):
    win.execution_mode_box.setCurrentText("Cloud only")
    assert win.settings[ra.MODE_KEY] == ra.CLOUD_ONLY


# ── Tally ────────────────────────────────────────────────────────────────────
def test_a_local_run_is_tallied_with_its_status_line(win):
    _send(win)
    _worker().finish("done")
    assert win.savings_tally.today()["local_runs"] == 1
    assert win.savings_tally.today()["saved"] == pytest.approx(0.19)
    assert win.chat_status_label.text().startswith(f"✓ Ran on {LOCAL_ID} (local)")
    assert win.local_savings_stat is not None


def test_an_accepted_suggestion_is_tallied(win):
    _send(win, local=1200)
    win.advice_banner.switch_button.click()
    _worker().finish("done", {"input_tokens": 100, "output_tokens": 100})
    assert win.savings_tally.today()["accepted"] == 1


# ── Failover ─────────────────────────────────────────────────────────────────
def test_a_failed_local_run_offers_and_never_sends(win):
    _send(win)
    _worker().fail("model ran out of memory")
    offer = win.advice_banner.offer
    assert offer.cloud.key == SONNET and offer.local.model == SMALL_ID
    assert len(FakeChatWorker.instances) == 1


def test_send_to_cloud_after_failure_asks_first(win):
    _send(win)
    _worker().fail("timeout")
    win.advice_banner.switch_button.click()
    assert (_worker().backend, _worker().model) == SONNET
    assert len(win.questions) == 1 and _selection_unchanged(win)


def test_try_a_smaller_local_model(win):
    _send(win)
    _worker().fail("out of memory")
    win.advice_banner.keep_button.click()
    assert (_worker().backend, _worker().model) == ("lmstudio", SMALL_ID)


def test_local_only_never_offers_or_sends_to_cloud(win):
    win.settings[ra.MODE_KEY] = ra.LOCAL_ONLY
    win._sync_execution_mode()
    _send(win, local=1200)
    advice = win.advice_banner.advice
    assert advice is None or advice.suggestion is None or advice.suggestion.local
    if not win.advice_banner.isHidden():
        win.advice_banner.keep_button.click()
    if _worker() is not None:
        _worker().fail("server went away")
        offer = win.advice_banner.offer
        assert offer is None or offer.cloud is None
    assert not any(w.backend == "anthropic" for w in FakeChatWorker.instances)


def test_stop_offers_no_failover(win):
    _send(win)
    win.chat_worker = _worker()
    win.stop_chat_worker()
    assert win.advice_banner.offer is None


# ── Nothing on the UI thread fetches ─────────────────────────────────────────
def test_advisor_methods_never_call_a_fetching_api():
    tree = ast.parse(Path(__file__).resolve().parents[1].joinpath("main.py").read_text())
    names = {"_advisor_context", "_advisor_candidate", "_advise_job", "_text_candidates_for",
             "_offer_failover", "_tally_finished_job", "_resume_held"}
    banned = {"list_models", "list_models_live", "load_models", "refresh", "discover",
              "start_local_discovery", "urlopen", "request"}
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            for call in ast.walk(node):
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                        and call.func.attr in banned):
                    found.setdefault(node.name, []).append(call.func.attr)
    assert found == {}
    assert names <= {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
