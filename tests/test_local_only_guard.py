"""Local only holds for every request, and a "local" model on another machine
is named before anything is sent to it.

local-model-routing review L-3: under Local only, Press, Nova, Label and media
requests still reached the cloud (each through the paid dialog), the advised
agents failed open when the advisor could not look, and an agent's own mode
beat the Mode box. Security review P1-1: OLLAMA_HOST or LMSTUDIO_URL set to
another machine was still "on this Mac", with no question and over plain http.
Nothing here leaves the machine: no request is sent, the guard only answers.
"""

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    import main
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question, QMessageBox.information) = saved


@pytest.fixture
def guard(window, monkeypatch):
    """The window with every cloud provider permitted and room in every cap,
    the paid dialog answered Yes, and each warning and question recorded."""
    from services import routing_advisor as ra
    shown = {"warning": [], "question": []}
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda parent, title, text, *a, **k: shown["warning"].append(text)))

    def question(parent, title, text, *a, **k):
        shown["question"].append(text)
        return shown.get("answer", QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    monkeypatch.setattr(window, "confirm_external_api_request", lambda *a, **k: True)
    monkeypatch.setattr(window, "current_api_permissions", lambda: {
        f"allow_{p}": True for p in ("openai", "deepseek", "kimi", "gemini",
                                      "anthropic", "qwen", "higgsfield", "elevenlabs")})
    monkeypatch.setattr(window, "session_budget_eur", 1000.0)
    monkeypatch.setattr(window, "daily_budget_eur", 1000.0)
    monkeypatch.setattr(window.usage_tracker, "get_agent_today_total", lambda agent: 0.0)
    monkeypatch.setattr(window.usage_tracker, "get_today_total", lambda: 0.0)
    monkeypatch.setitem(window.settings, ra.OVERRIDES_KEY, {})
    monkeypatch.setattr(window, "_remote_runtime_ok", set())
    box = window.execution_mode_box
    before = box.currentText()
    box.blockSignals(True)
    yield window, shown
    box.setCurrentText(before)
    box.blockSignals(False)
    for token in list(window._pending_requests):
        window.abandon_request(token)


def _mode(window, text):
    window.execution_mode_box.setCurrentText(text)


@pytest.mark.parametrize("agent", ["manuscript", "creator", "music", "audiobook",
                                   "video", "author", "webdesign"])
def test_local_only_refuses_a_cloud_request_from_every_agent(guard, agent):
    window, shown = guard
    _mode(window, "Local only")
    token = window.authorize_request(agent, "anthropic", "claude-sonnet-5-5", "a prompt")
    assert token is False
    assert "Local only" in shown["warning"][-1]
    assert not window._pending_requests


def test_local_only_refuses_per_unit_requests_too(guard):
    window, shown = guard
    _mode(window, "Local only")
    assert window.authorize_request("video", "gemini", "veo-4", "a scene",
                                    flat_cost_eur=0.40) is False


def test_a_failing_advisor_cannot_let_a_cloud_request_through(guard, monkeypatch):
    window, shown = guard
    _mode(window, "Local only")
    monkeypatch.setattr(window, "_advisor_context",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert window.authorize_request("webdesign", "anthropic", "claude-sonnet-5-5",
                                    "a site", resume=lambda: None) is False


def test_the_box_beats_an_agents_own_mode(guard, monkeypatch):
    import main
    from services import routing_advisor as ra
    window, _ = guard
    monkeypatch.setitem(window.settings, ra.OVERRIDES_KEY, {"chat": ra.SUGGEST_LOCAL})
    _mode(window, "Local only")
    assert main.execution_mode_for(window, "chat") == "Local only"
    assert window.routing_mode("chat") == ra.LOCAL_ONLY
    _mode(window, "Hybrid allowed")
    assert window.routing_mode("chat") == ra.SUGGEST_LOCAL      # the override still counts


def test_hybrid_still_sends_to_a_permitted_cloud_provider(guard):
    window, shown = guard
    _mode(window, "Hybrid allowed")
    token = window.authorize_request("manuscript", "anthropic", "claude-sonnet-5-5", "a prompt")
    assert token and not shown["warning"]


def test_a_local_model_on_this_mac_asks_nothing(guard, monkeypatch):
    window, shown = guard
    _mode(window, "Local only")
    monkeypatch.setattr(window.ollama, "base_url", "http://127.0.0.1:11434")
    assert window.authorize_request("author", "ollama", "gemma3:27b", "a prompt")
    assert not shown["question"] and not shown["warning"]


def test_a_local_runtime_on_another_machine_is_asked_about_once(guard, monkeypatch):
    window, shown = guard
    _mode(window, "Hybrid allowed")
    monkeypatch.setattr(window.ollama, "base_url", "http://203.0.113.9:11434")
    shown["answer"] = QMessageBox.No
    assert window.authorize_request("author", "ollama", "gemma3:27b", "a prompt") is False
    assert "203.0.113.9" in shown["question"][-1] and "plain http" in shown["question"][-1]
    shown["answer"] = QMessageBox.Yes
    assert window.authorize_request("author", "ollama", "gemma3:27b", "a prompt")
    asked = len(shown["question"])
    assert window.authorize_request("author", "ollama", "gemma3:27b", "a prompt")
    assert len(shown["question"]) == asked                     # once per address


def test_a_local_runtime_on_another_machine_is_refused_under_local_only(guard, monkeypatch):
    window, shown = guard
    _mode(window, "Local only")
    monkeypatch.setattr(window.lmstudio, "base_url", "http://192.0.2.7:1234/v1")
    assert window.authorize_request("author", "lmstudio", "dolphin", "a prompt") is False
    assert "192.0.2.7" in shown["warning"][-1] and not shown["question"]


def test_measuring_asks_no_cloud_model_under_local_only(guard):
    window, _ = guard
    _mode(window, "Local only")
    allowed, reason = window._authorize_measurement(None, None, 0.5, interactive=True)
    assert not allowed and "Local only" in reason


# ── Kernel's own send path (re-review RC-7) ─────────────────────────────────

def _kernel(window, monkeypatch):
    """Kernel with text typed; the validator, which runs after the route check,
    records that the request got that far and stops it there."""
    from services.validator import ValidationResult
    reached = []
    monkeypatch.setattr(window.validator, "validate",
                        lambda **kw: reached.append(kw["provider"])
                        or ValidationResult(False, "stopped by the test"))
    window.agent_box.setCurrentText("chat")
    window.input_box.setPlainText("Summarise chapter one")
    return reached


def test_kernel_refuses_a_cloud_route_under_local_only(guard, monkeypatch):
    window, shown = guard
    reached = _kernel(window, monkeypatch)
    _mode(window, "Local only")
    window._send_chat(route_override=("anthropic", "claude-sonnet-5-5"), advised=True)
    assert reached == [] and "Local only" in shown["warning"][-1]


def test_kernel_asks_before_a_local_runtime_on_another_machine(guard, monkeypatch):
    window, shown = guard
    reached = _kernel(window, monkeypatch)
    _mode(window, "Hybrid allowed")
    monkeypatch.setattr(window.ollama, "base_url", "http://203.0.113.9:11434")
    shown["answer"] = QMessageBox.No
    window._send_chat(route_override=("ollama", "gemma3:27b"), advised=True)
    assert reached == [] and "203.0.113.9" in shown["question"][-1]
    shown["answer"] = QMessageBox.Yes
    window._send_chat(route_override=("ollama", "gemma3:27b"), advised=True)
    assert reached == ["ollama"]


def test_a_yes_to_another_machine_does_not_outlive_a_switch_to_local_only(guard, monkeypatch):
    """Verify M8: the address agreed to under Hybrid is refused once Mode is
    Local only."""
    window, shown = guard
    _mode(window, "Hybrid allowed")
    monkeypatch.setattr(window.ollama, "base_url", "http://203.0.113.9:11434")
    shown["answer"] = QMessageBox.Yes
    assert window.authorize_request("author", "ollama", "gemma3:27b", "a prompt")
    _mode(window, "Local only")
    assert window.authorize_request("author", "ollama", "gemma3:27b", "a prompt") is False
    assert "203.0.113.9" in shown["warning"][-1]
