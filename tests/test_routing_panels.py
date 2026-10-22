"""The routing advisor on Imprint's text agents beyond Chat.

Chat is covered by test_routing_phase4.py. Here Sitebuilder (webdesign) stands
in for Quill, Herald and Stamp, which pass `resume=` to the same guard. The
banner sits on the panel and holds the job; each answer puts the model in the
agent's boxes and runs the action again, so the paid-request dialog and the
budget caps still decide; the answer is stored for that agent and kind only;
Muse and Press are never advised; media (flat-cost) requests never are.
No test reaches a network, a cloud API or LM Studio.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from services import routing_advisor as ra
from tests.test_routing_phase4 import (FakeChatWorker, LOCAL_ID, SONNET,  # noqa: F401
                                       _worker, qapp, win)

AGENT = "webdesign"


@pytest.fixture
def panel(win, monkeypatch):
    panel = win.webdesign_panel
    # The live model list arrives on a worker thread and would replace the
    # box under the test; the box is filled by hand below.
    monkeypatch.setattr(type(panel.webdesign_panel_base), "load_models", lambda self: None)
    panel.webdesign_provider_box.setCurrentText("lmstudio")
    panel.webdesign_model_box.clear()
    panel.webdesign_model_box.addItems([LOCAL_ID])
    panel.webdesign_model_box.setCurrentText(LOCAL_ID)
    panel.webdesign_brief_input.setPlainText("A one-page site for a bakery")
    return panel


def _generate(win, panel, local=1290):
    win.ratings_for_test["local"] = local
    panel.generate()
    QApplication.processEvents()


def _boxes(panel):
    return (panel.webdesign_provider_box.currentText().casefold(),
            panel.webdesign_model_box.currentText())


def test_a_good_enough_local_model_runs_without_a_banner(win, panel):
    _generate(win, panel)
    assert panel._advice_banner.isHidden()
    assert (_worker().backend, _worker().model) == ("lmstudio", LOCAL_ID)


def test_a_quality_gap_holds_the_agent_job_on_its_own_banner(win, panel):
    _generate(win, panel, local=1200)
    banner = panel._advice_banner
    assert _worker() is None and not banner.isHidden()
    assert banner is not win.advice_banner and win.advice_banner.isHidden()
    assert banner.advice.codes == (ra.QUALITY_GAP,) and banner.advice.suggestion.key == SONNET
    assert panel.layout().indexOf(banner) == 0
    assert _boxes(panel) == ("lmstudio", LOCAL_ID)       # the selection is not touched yet


def test_switch_for_this_job_reruns_the_action_through_the_paid_dialog(win, panel):
    _generate(win, panel, local=1200)
    panel._advice_banner.switch_button.click()
    assert (_worker().backend, _worker().model) == SONNET
    assert len(win.questions) == 1 and "external API" in win.questions[0]
    assert win.routing_rules.all() == []


def test_declining_the_paid_dialog_sends_nothing(win, panel, monkeypatch):
    _generate(win, panel, local=1200)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    panel._advice_banner.switch_button.click()
    assert _worker() is None


def test_keep_local_runs_the_selected_model(win, panel):
    _generate(win, panel, local=1200)
    panel._advice_banner.keep_button.click()
    assert (_worker().backend, _worker().model) == ("lmstudio", LOCAL_ID)
    assert win.questions == []


def test_always_stores_a_rule_for_this_agent_and_the_next_job_follows_it(win, panel):
    _generate(win, panel, local=1200)
    panel._advice_banner.always_button.click()
    rules = win.routing_rules.all()
    assert len(rules) == 1 and rules[0].agent == AGENT
    assert (rules[0].provider, rules[0].model) == SONNET
    assert win.routing_rules.get("chat", rules[0].kind) is None
    FakeChatWorker.instances.clear()
    panel.webdesign_provider_box.setCurrentText("lmstudio")
    panel.webdesign_model_box.clear()
    panel.webdesign_model_box.addItems([LOCAL_ID])
    panel.webdesign_model_box.setCurrentText(LOCAL_ID)
    _generate(win, panel, local=1200)
    assert panel._advice_banner.isHidden()
    assert (_worker().backend, _worker().model) == SONNET
    assert len(win.questions) == 2                         # still asked each time


def test_cancel_drops_the_job(win, panel):
    _generate(win, panel, local=1200)
    panel._advice_banner.dismiss_button.click()
    assert _worker() is None and AGENT not in win.panel_routing.held


def test_local_only_never_offers_the_cloud(win, panel):
    win.settings[ra.OVERRIDES_KEY] = {AGENT: ra.LOCAL_ONLY}
    _generate(win, panel, local=1200)
    advice = panel._advice_banner.advice
    assert advice is None or advice.suggestion is None or advice.suggestion.local
    assert win.questions == []


def test_a_failed_run_offers_the_next_candidate_and_sends_nothing(win, panel):
    _generate(win, panel)
    FakeChatWorker.instances[-1].fail("model crashed")
    banner = panel._advice_banner
    assert not banner.isHidden() and banner.offer is not None
    assert len(FakeChatWorker.instances) == 1               # nothing new was sent
    assert "model crashed" in banner.detail.text()
    banner.switch_button.click()                            # Send to Anthropic
    assert (_worker().backend, _worker().model) == SONNET and len(win.questions) == 1


def test_a_stopped_run_offers_no_failover(win, panel):
    _generate(win, panel)
    win.abandon_request(AGENT, reason="stopped")
    assert panel._advice_banner.isHidden()


def test_a_finished_local_run_is_tallied(win, panel):
    _generate(win, panel)
    FakeChatWorker.instances[-1].finish("<html></html>")
    today = win.savings_tally.today()
    assert today["local_runs"] == 1 and today["saved"] > 0


def test_an_accepted_paid_suggestion_is_tallied_as_spent(win, panel):
    _generate(win, panel, local=1200)
    panel._advice_banner.switch_button.click()
    _worker().finish("<html></html>")
    assert win.savings_tally.today()["accepted"] == 1


def test_flat_cost_media_requests_and_calls_without_resume_are_never_advised(win, panel):
    win.ratings_for_test["local"] = 1200
    assert win.panel_routing.advise(AGENT, "lmstudio", LOCAL_ID, "x", resume=None) is True
    token = win.authorize_request(AGENT, "lmstudio", LOCAL_ID, "x",
                                  flat_cost_eur=0.1, resume=lambda: None)
    assert token and win.panel_routing.held == {}


def test_muse_and_press_are_never_advised(win):
    for agent in ("creator", "manuscript"):
        assert win.panel_routing.eligible(agent) is False
    assert "creator" in __import__("ui.panel_routing", fromlist=["x"]).NEVER_ADVISED


def test_advised_panels_pass_a_resume_and_the_rest_do_not():
    root = Path(__file__).resolve().parents[1] / "agents"
    advised = {"author", "webdesign", "social", "fiverr"}
    for path in root.glob("*/panel.py"):
        agent = path.parent.name
        for node in ast.walk(ast.parse(path.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "authorize_request"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value in {"author", "webdesign", "social", "fiverr"}):
                has = any(k.arg == "resume" for k in node.keywords)
                flat = any(k.arg == "flat_cost_eur" for k in node.keywords)
                assert flat or has, (path.parent.name, node.lineno)
            if agent in ("creator", "manuscript") and isinstance(node, ast.Call):
                assert not any(k.arg == "resume" for k in node.keywords), (agent, node.lineno)
