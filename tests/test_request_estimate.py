"""
Imprint — one estimate: every message sent, output at the length limit
======================================================================
Type: unit + window, no network (temp DB per test; offscreen Qt; no keys).

Audit B-F2 (spec docs/specs/audit-p1-billing.md, owner decision D2): the guard
priced the user's prompt alone with `max(250, 1.2 x input)` tokens of output,
while panels sent a system prompt, context and project instructions and the
clients set no output cap. One function now prices a request — input counted
from every message the worker sends, output at the cap every client sends —
behind the Chat estimate, the guard (authorize_request) and the recommendation
engine's budget rule (_priced_for_request), so the three agree to the cent.
The confirmation and the refusals say "up to", rounded up.

Run with:  pytest tests/test_request_estimate.py -v
"""

import ast
from pathlib import Path

import pytest

from services import database, money_text
from services.chat_projects import with_project_instructions
from services import output_limits
from services.output_limits import MAX_OUTPUT_TOKENS, THINKING_MAX_TOKENS
from services.usage_tracker import estimate_input_tokens, max_cost_eur
from services.validator import Validator

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gpt-estimate-test"          # priced in each test's own DB below
EUR = 0.92


def _price(model=MODEL, backend="openai", inp=10.0, out=50.0):
    conn = database.get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO pricing (backend, model, input_per_1m_usd, "
        "output_per_1m_usd, cached_input_per_1m_usd) VALUES (?,?,?,?,NULL)",
        (backend, model, inp, out))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) "
                 "VALUES ('eur_per_usd', ?)", (str(EUR),))
    conn.commit()
    conn.close()


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "imprint.db")
    database.init_db()
    _price()


# ── The money words ──────────────────────────────────────────────────────────

def test_maxima_round_up_amounts_left_round_down_and_cents_never_vanish():
    assert money_text.up_to(0.4330) == "€0.44"     # the spec's D2 example
    assert money_text.up_to(0.43) == "€0.43"       # no float creep upward
    assert money_text.up_to(0.1 + 0.2) == "€0.30"
    assert money_text.left(0.0599) == "€0.05"
    assert money_text.left(-0.20) == "€0.00"
    assert money_text.paid(0.004) == "under €0.01"
    assert money_text.paid(0) == "€0.00"
    assert money_text.paid(1.875) == "€1.88"


# ── The one estimate function ────────────────────────────────────────────────

def test_input_is_counted_from_every_message():
    messages = [{"role": "system", "content": "s" * 400},
                {"role": "user", "content": "h" * 800},
                {"role": "assistant", "content": "a" * 800},
                {"role": "user", "content": "u" * 400}]
    assert estimate_input_tokens(messages) == 600
    assert estimate_input_tokens([]) == 1


def test_the_maximum_reserves_the_whole_length_limit(db):
    expected = (6100 * 10.0 + MAX_OUTPUT_TOKENS * 50.0) / 1_000_000 * EUR
    assert max_cost_eur("openai", MODEL, 6100) == pytest.approx(expected, abs=1e-6)
    assert round(max_cost_eur("openai", MODEL, 6100), 4) == 0.4330
    assert max_cost_eur("ollama", "llama3", 6100) == 0.0
    assert max_cost_eur("nobody", "unpriced", 6100) is None


@pytest.mark.parametrize("backend, thinking", [("deepseek", 65_536),
                                               ("qwen", 8_192)])
def test_thinking_models_reserve_the_cap_plus_their_thinking_limit(
        db, backend, thinking):
    """Owner decision, review loop 1: DeepSeek keeps its documented 64K
    thinking default on top of the cap; Qwen is sent a thinking budget of
    8,192 and reserves that much on top."""
    _price("thinking-test", backend, 1.0, 4.0)
    assert THINKING_MAX_TOKENS[backend] == thinking
    reserved = MAX_OUTPUT_TOKENS + thinking
    expected = (100 * 1.0 + reserved * 4.0) / 1_000_000 * EUR
    assert max_cost_eur(backend, "thinking-test", 100) == pytest.approx(
        expected, abs=1e-6)


@pytest.mark.parametrize("backend", ["openai", "gemini", "anthropic", "kimi"])
def test_a_cap_that_includes_thinking_reserves_the_cap_only(db, backend):
    """Kimi too: its doc says reasoning counts against `max_tokens`."""
    _price("cap-test", backend, 1.0, 4.0)
    expected = (100 * 1.0 + MAX_OUTPUT_TOKENS * 4.0) / 1_000_000 * EUR
    assert max_cost_eur(backend, "cap-test", 100) == pytest.approx(expected, abs=1e-6)


def test_a_models_own_thinking_row_wins_over_its_providers(db, monkeypatch):
    """The reserve is looked up by (provider, model) first, so a paid run
    that shows one model differs needs one table row, no caller change."""
    _price("kimi-own-row", "kimi", 1.0, 4.0)
    _price("kimi-other", "kimi", 1.0, 4.0)
    monkeypatch.setitem(THINKING_MAX_TOKENS, ("kimi", "kimi-own-row"), 1_000)
    assert output_limits.thinking_reserve_tokens("kimi", "kimi-own-row") == 1_000
    assert output_limits.thinking_reserve_tokens("kimi", "kimi-other") == 0
    assert output_limits.thinking_reserve_tokens("kimi") == 0
    own = (100 * 1.0 + (MAX_OUTPUT_TOKENS + 1_000) * 4.0) / 1_000_000 * EUR
    assert max_cost_eur("kimi", "kimi-own-row", 100) == pytest.approx(own, abs=1e-6)
    other = (100 * 1.0 + MAX_OUTPUT_TOKENS * 4.0) / 1_000_000 * EUR
    assert max_cost_eur("kimi", "kimi-other", 100) == pytest.approx(other, abs=1e-6)
    assert output_limits.output_reserve_text("kimi", "kimi-own-row").endswith(
        ", plus up to 1,000 for thinking")
    assert output_limits.output_reserve_short("kimi", "kimi-own-row") == (
        "up to 8,192 + 1,000 thinking")


def test_the_thinking_words_appear_only_where_thinking_is_reserved():
    assert output_limits.output_reserve_text("kimi", "kimi-k3") == (
        "up to 8,192 written (the length limit)")
    assert output_limits.output_reserve_short("kimi", "kimi-k3") == "up to 8,192"
    assert output_limits.output_reserve_text("qwen", "qwen3.8-max") == (
        "up to 8,192 written (the length limit), plus up to 8,192 for thinking")
    assert output_limits.output_reserve_short("deepseek", "deepseek-v4-pro") == (
        "up to 8,192 + 65,536 thinking")


# ── The window: guard, Chat estimate and recommendation pricing agree ───────

@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved


ALL_ALLOWED = {f"allow_{p}": True for p in (
    "openai", "deepseek", "kimi", "gemini", "anthropic", "qwen",
    "higgsfield", "elevenlabs")}


@pytest.fixture
def win(_window, db, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    w = _window
    w._pending_requests = {}
    w._pending_by_agent = {}
    w.session_cost_total = 0.0
    w.session_request_count = 0
    w.session_budget_eur = 1.0
    w.daily_budget_eur = 5.0
    monkeypatch.setattr(w, "current_api_permissions", lambda: dict(ALL_ALLOWED))
    monkeypatch.setattr(w, "_active_project", lambda: None)
    monkeypatch.setattr(w, "load_history_list", lambda: None)
    monkeypatch.setattr(w, "update_usage_labels", lambda: None)
    # No daemon in the suite: the local-model offer must find nothing.
    monkeypatch.setattr(w.ollama, "list_models", lambda: [])
    w.shown = {"question": [], "warning": []}
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: w.shown["question"].append(a[2]) or QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda *a, **k: w.shown["warning"].append(a[2])))
    return w


INSTRUCTIONS = "Keep to the series bible. " * 20
MESSAGES = [
    {"role": "system", "content": "You are Quill, a novelist. " * 40},
    {"role": "user", "content": "Earlier: chapter two. " * 30},
    {"role": "assistant", "content": "Chapter two text. " * 50},
    {"role": "user", "content": "Write chapter 3, about 5,000 words."},
]


def test_estimate_guard_and_recommendations_agree_on_the_full_messages(
        win, monkeypatch):
    """Spec success measure B-F2 (b), with system, history and project text."""
    from services.recommendations.catalog import text_candidates

    monkeypatch.setattr(win, "_active_project", lambda: {
        "id": "novel", "name": "Novel", "instructions": INSTRUCTIONS,
        "budget_eur": None})
    sent = with_project_instructions(MESSAGES, INSTRUCTIONS)
    chars = (sum(len(m["content"]) for m in MESSAGES)
             + len("Project instructions:\n" + INSTRUCTIONS.strip()) + 2)
    in_tokens = chars // 4
    assert estimate_input_tokens(sent) == in_tokens
    expected = round((in_tokens * 10.0 + MAX_OUTPUT_TOKENS * 50.0)
                     / 1_000_000 * EUR, 6)

    chat_cost, chat_tokens = win.estimate_chat_cost(
        "openai", MODEL, MESSAGES[-1]["content"], messages=MESSAGES)
    assert (chat_cost, chat_tokens) == (expected, in_tokens)

    validated = []
    real_validate = win.validator.validate
    monkeypatch.setattr(win.validator, "validate", lambda **kw: (
        validated.append(kw["estimated_cost"]), real_validate(**kw))[1])
    token = win.authorize_request("author", "openai", MODEL,
                                  MESSAGES[-1]["content"], messages=MESSAGES)
    assert token
    assert validated == [expected]
    assert win._pending_requests[token]["estimated_cost"] == expected

    candidates = text_candidates(["openai"], {"openai": [MODEL]},
                                 win._price_index(), win.ratings)
    (priced,) = win._priced_for_request(candidates, in_tokens)
    assert priced.estimated_cost == expected
    # The prompt alone would have been ~10 tokens: the old estimate's input.
    assert in_tokens > 50 * estimate_input_tokens([MESSAGES[-1]])


def _d2_messages():
    """The spec's D2 example: a 400-character prompt, 24,400 characters sent
    (about 6,100 tokens)."""
    prompt = "p" * 400
    return prompt, [{"role": "system", "content": "s" * 24_000},
                    {"role": "user", "content": prompt}]


def test_the_d2_example_is_refused_with_95_cents_spent(win):
    """Spec success measure B-F2 (c): today the request is sent and the
    session ends at €1.31; now it is refused before anything is spent."""
    prompt, messages = _d2_messages()
    win.session_cost_total = 0.95
    assert not win.authorize_request("author", "openai", MODEL, prompt,
                                     messages=messages)
    assert win._pending_requests == {}
    (reason,) = win.shown["warning"]
    assert reason == (
        "Not sent: this request can cost up to €0.44 and your session cap has "
        "€0.05 left (of €1.00). Pick a cheaper or local model, or raise "
        "Session € under Limits and press Save Limits.")


def test_the_d2_example_is_allowed_at_55_cents_and_says_up_to(win):
    prompt, messages = _d2_messages()
    win.session_cost_total = 0.55
    token = win.authorize_request("author", "openai", MODEL, prompt,
                                  messages=messages)
    assert token
    dialog = win.shown["question"][-1]
    assert "Up to €0.44; you pay for what it writes." in dialog
    assert ("Based on about 6,100 tokens sent and up to 8,192 written "
            "(the length limit).") in dialog
    assert "~€" not in dialog.split("Assessment")[0]


def test_renders_and_batches_warn_that_finished_steps_are_recorded(win):
    token = win.authorize_request("video", "openai", "vidforge-pipeline",
                                  "a topic", label="long-form",
                                  flat_cost_eur=0.40, partial_billing=True)
    assert token
    dialog = win.shown["question"][-1]
    assert "Estimated cost/quota impact: ~€0.40" in dialog        # per-unit line
    assert ("If it fails or you stop it, the paid steps already done are "
            "recorded.") in dialog


def test_thinking_providers_say_what_they_reserve(win):
    _price("thinking-test", "deepseek", 1.0, 4.0)
    win.confirm_external_api_request("deepseek", "thinking-test", 0.3, 100)
    assert ("up to 8,192 written (the length limit), plus up to 65,536 for "
            "thinking") in win.shown["question"][-1]
    win.confirm_external_api_request("qwen", "qwen3.8-max", 0.1, 100)
    assert ("up to 8,192 written (the length limit), plus up to 8,192 for "
            "thinking.") in win.shown["question"][-1]
    win.confirm_external_api_request("kimi", "kimi-k3", 0.1, 100)
    assert "thinking" not in win.shown["question"][-1]


# ── Review loop 1: the tracked default Kimi model is usable again ───────────
# With 65,536 thinking tokens reserved for every Kimi model, kimi-k3 (the
# default in config/settings.json) reserved about €1.02 for any request and
# was refused on a fresh session under the default €1.00 cap.

THREE_TITLES = [{"role": "user", "content": "Suggest three titles for my novel."}]


@pytest.mark.parametrize("model, figure", [
    ("kimi-k3", "€0.12"),                 # its own price row
    ("kimi-k9-unlisted", "€0.12"),        # the provider default row
])
def test_kimi_three_titles_is_allowed_on_a_fresh_session(win, model, figure):
    token = win.authorize_request("author", "kimi", model,
                                  THREE_TITLES[-1]["content"],
                                  messages=THREE_TITLES)
    assert token, win.shown["warning"]
    assert win.shown["warning"] == []
    dialog = win.shown["question"][-1]
    assert f"Up to {figure}; you pay for what it writes." in dialog
    assert "thinking" not in dialog.split("Assessment")[0]
    assert win._pending_requests[token]["estimated_cost"] < 0.20


@pytest.mark.parametrize("backend, model, cost", [
    ("kimi", "kimi-k3", 0.113326),            # up to €0.12
    ("qwen", "qwen3.8-max", 0.090624),        # up to €0.10
    ("deepseek", "deepseek-v4-pro", 0.268727),  # up to €0.27
])
def test_what_a_100_token_prompt_reserves_on_the_shipped_prices(
        db, backend, model, cost):
    """Pinned on config/pricing.json's rows: kimi-k3 at the cap alone,
    qwen3.8-max at cap + 8,192, deepseek-v4-pro at cap + 65,536."""
    assert max_cost_eur(backend, model, 100) == pytest.approx(cost, abs=1e-6)


def test_the_live_line_and_popup_name_the_thinking_reserve(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(
        lambda *a, **k: shown.append(a[2])))
    monkeypatch.setattr(win.agent_box, "currentText", lambda: "chat")
    for backend, model, tail in [
            ("qwen", "qwen3.8-max", "+ up to 8,192 + 8,192 thinking"),
            ("kimi", "kimi-k3", "+ up to 8,192")]:
        monkeypatch.setattr(win, "get_current_cost_estimate",
                            lambda b=backend, m=model: (0.0906, 100, b, m))
        win.update_live_cost_estimate()
        assert win.live_estimate_label.text() == (
            f"Next request: up to €0.10 · paid · {backend} {model} · "
            f"~100 tokens {tail}")
        win.show_cost_estimate_popup()
        assert f"~100 sent {tail} written" in shown[-1]
        assert "Most it can cost: €0.10 (you pay for what it writes)" in shown[-1]


# ── Refusal wording, every scope ─────────────────────────────────────────────

class _Registry:
    def __init__(self, agent_budget=None):
        self.agent_budget = agent_budget

    def is_agent_enabled(self, _a):
        return True

    def is_tool_enabled(self, _t):
        return True

    def agent_allows_provider(self, _a, _p):
        return True

    def tool_allows_provider(self, _t, _p):
        return True

    def agent_allows_tool(self, _a, _t):
        return True

    def get_agent_budget(self, _a):
        return self.agent_budget

    def agent_requires_approval(self, _a):
        return False


def _refusal(registry=None, **overrides):
    fields = dict(agent_name="author", tool_name=None, provider="openai",
                  api_permissions={"allow_openai": True}, session_cost=0.0,
                  session_budget=10.0, daily_cost=0.0, daily_budget=10.0,
                  estimated_cost=0.4330)
    fields.update(overrides)
    return Validator(registry or _Registry()).validate(**fields)


@pytest.mark.parametrize("case, scope, text", [
    (dict(session_cost=0.95, session_budget=1.0), "session_cap",
     "Not sent: this request can cost up to €0.44 and your session cap has "
     "€0.05 left (of €1.00). Pick a cheaper or local model, or raise Session € "
     "under Limits and press Save Limits."),
    (dict(daily_cost=4.80, daily_budget=5.0), "daily_cap",
     "Not sent: this request can cost up to €0.44 and today's cap has €0.20 "
     "left (of €5.00). Pick a cheaper or local model, raise Daily € under "
     "Limits, or wait until tomorrow."),
    (dict(project_name="X", project_cost=0.40, project_budget=0.50),
     "project_cap",
     "Not sent: this request can cost up to €0.44 and Project 'X' has €0.10 "
     "left today (of €0.50). Pick a cheaper or local model."),
])
def test_every_scope_is_worded_from_its_own_figures(case, scope, text):
    result = _refusal(**case)
    assert (result.allowed, result.scope, result.reason) == (False, scope, text)


def test_the_agent_cap_names_the_agent_and_what_it_has_left():
    result = _refusal(_Registry(agent_budget=1.00), agent_daily_cost=0.80)
    assert result.scope == "agent_cap"
    assert result.reason == (
        "Not sent: this request can cost up to €0.44 and Agent 'author' has "
        "€0.20 left today (of €1.00). Pick a cheaper or local model.")


def test_a_float_summed_total_never_refuses_against_equal_figures():
    """Code review P3-4: 0.1 + 0.2 + 0.27 is 0.5700000000000001 in floats, so
    €0.43 was refused against "€0.43 left". Both sides are compared to the
    micro-euro now, as the words are written."""
    spent = 0.1 + 0.2 + 0.27
    assert spent != 0.57
    assert _refusal(session_cost=spent, session_budget=1.0,
                    estimated_cost=0.43).allowed
    refused = _refusal(session_cost=spent, session_budget=1.0,
                       estimated_cost=0.430001)
    assert not refused.allowed
    assert "up to €0.44 and your session cap has €0.43 left" in refused.reason
    # No sum of small amounts gives a refusal whose two figures are equal.
    import re
    for cents in range(1, 60):
        spent = sum([0.01] * cents) + 0.27
        for estimate in (0.73 - cents / 100, 0.7300004 - cents / 100):
            result = _refusal(session_cost=spent, session_budget=1.0,
                              estimated_cost=estimate)
            if not result.allowed:
                up_to, left = re.findall(r"€(\d+\.\d\d)", result.reason)[:2]
                assert up_to != left, result.reason


@pytest.mark.parametrize("case", [
    dict(session_cost=0.95, session_budget=1.0),
    dict(daily_cost=4.80, daily_budget=5.0),
    dict(project_name="X", project_cost=0.40, project_budget=0.50),
])
def test_no_refusal_says_exceeded_or_suggests_a_shorter_prompt(case):
    reason = _refusal(**case).reason.lower()
    assert "exceeded" not in reason
    assert "shorter" not in reason and "prompt" not in reason


def test_the_local_offer_title_says_not_enough_left(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    titles = []
    monkeypatch.setattr(win.ollama, "list_models", lambda: ["llama3.1:8b"])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda parent, title, *a, **k: titles.append(title) or QMessageBox.No))
    prompt, messages = _d2_messages()
    win.session_cost_total = 0.95
    assert not win.authorize_request("author", "openai", MODEL, prompt,
                                     messages=messages)
    assert titles == ["Not enough budget left"]


# ── One exchange rate, and Settings cannot switch the caps off ──────────────
# Security review P2-2: the token path read eur_per_usd raw, so -0.92 made
# every text request's reserve negative and 0 made it free, while per-unit
# pricing rejected both. Settings saved any float.

def _set_rate(value):
    conn = database.get_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) "
                 "VALUES ('eur_per_usd', ?)", (value,))
    conn.commit()
    conn.close()


@pytest.mark.parametrize("bad", ["-0.92", "0", "nan", "inf", "-inf", "abc", ""])
def test_a_rate_that_is_not_above_zero_falls_back_to_0_92_everywhere(db, bad):
    from services import per_unit_pricing
    from services.usage_tracker import UsageTracker
    _set_rate(bad)
    expected = (6100 * 10.0 + MAX_OUTPUT_TOKENS * 50.0) / 1_000_000 * 0.92
    assert max_cost_eur("openai", MODEL, 6100) == pytest.approx(expected, abs=1e-6)
    assert per_unit_pricing.eur_per_usd() == 0.92
    conn = database.get_connection()
    try:
        assert per_unit_pricing.eur_per_usd(conn) == 0.92
    finally:
        conn.close()
    assert UsageTracker().calculate_cost_eur("openai", MODEL, 1_000_000, 0) == (
        pytest.approx(10.0 * 0.92))


def test_a_valid_rate_is_read_the_same_by_both_paths(db):
    from services import per_unit_pricing
    _set_rate("0.85")
    assert per_unit_pricing.eur_per_usd() == 0.85
    expected = (100 * 10.0 + MAX_OUTPUT_TOKENS * 50.0) / 1_000_000 * 0.85
    assert max_cost_eur("openai", MODEL, 100) == pytest.approx(expected, abs=1e-6)


@pytest.fixture
def settings_dialog(app, db, tmp_path, monkeypatch):
    """Settings on a stand-in window; the .env it shows is a tmp file."""
    from PySide6.QtWidgets import QDialog, QMessageBox, QWidget
    from services import api_keys
    from services.registry import Registry
    from ui.dialogs import show_settings

    monkeypatch.setattr(api_keys, "env_path", lambda: tmp_path / ".env")
    monkeypatch.setattr(api_keys, "template_path", lambda: tmp_path / "none")
    monkeypatch.setattr(QDialog, "exec", lambda self: None)
    said = []
    for kind in ("warning", "information"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(
            lambda _p, title, text, *a, **k: said.append((title, text))))

    class Host(QWidget):
        def __init__(self):
            super().__init__()
            self.registry = Registry()
            self.session_budget_eur = 1.0
            self.daily_budget_eur = 5.0

        def update_usage_labels(self):
            pass

    host = Host()
    dialog = show_settings(host)
    return dialog, host, said


def _save_general(dialog, **typed):
    from PySide6.QtWidgets import QLineEdit, QPushButton
    for name, text in typed.items():
        dialog.findChild(QLineEdit, name).setText(text)
    dialog.findChild(QPushButton, "SettingsSave").click()


RATE_REFUSED = ("General: EUR per USD must be a number above zero, such as "
                "0.92. The General settings were not saved.")
BUDGET_REFUSED = ("General: Session and Daily budgets must be numbers of 0 or "
                  "more. The General settings were not saved.")


@pytest.mark.parametrize("typed, message", [
    ({"EurUsdRate": "-0.92"}, RATE_REFUSED),
    ({"EurUsdRate": "0"}, RATE_REFUSED),
    ({"EurUsdRate": "nan"}, RATE_REFUSED),
    ({"EurUsdRate": "inf"}, RATE_REFUSED),
    ({"EurUsdRate": "x"}, RATE_REFUSED),
    ({"SessionBudget": "nan"}, BUDGET_REFUSED),
    ({"SessionBudget": "-1"}, BUDGET_REFUSED),
    ({"DailyBudget": "inf"}, BUDGET_REFUSED),
    ({"DailyBudget": "-0.01"}, BUDGET_REFUSED),
    ({"DailyBudget": "five"}, BUDGET_REFUSED),
])
def test_settings_refuses_a_rate_or_budget_that_switches_the_caps_off(
        settings_dialog, typed, message):
    from services.database import get_setting
    dialog, host, said = settings_dialog
    _save_general(dialog, **{"EurUsdRate": "0.95", "SessionBudget": "2",
                             "DailyBudget": "6", **typed})
    (title, text) = said[-1]
    assert title == "Saved with errors"
    assert message in text.split("\n")
    assert get_setting("eur_per_usd") == str(EUR)          # nothing written
    assert get_setting("session_budget_eur", "unset") == "unset"
    assert (host.session_budget_eur, host.daily_budget_eur) == (1.0, 5.0)


def test_settings_saves_a_valid_rate_and_zero_budgets(settings_dialog):
    from services.database import get_setting
    dialog, host, said = settings_dialog
    _save_general(dialog, EurUsdRate="0.95", SessionBudget="0", DailyBudget="6")
    assert said[-1][0] == "Saved"
    assert get_setting("eur_per_usd") == "0.95"
    assert (host.session_budget_eur, host.daily_budget_eur) == (0.0, 6.0)


# ── Every text call site passes its messages ─────────────────────────────────

def _guard_calls():
    for path in sorted((ROOT / "agents").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "authorize_request"):
                keywords = {k.arg for k in node.keywords}
                yield f"{path.relative_to(ROOT)}:{node.lineno}", keywords


def test_every_text_request_passes_the_messages_it_sends():
    """A text call without `messages=` falls back to pricing the prompt
    alone, which is what ran 30x low. Per-unit calls price their own units."""
    calls = list(_guard_calls())
    text = [(where, kw) for where, kw in calls if "flat_cost_eur" not in kw]
    missing = [where for where, kw in text if "messages" not in kw]
    assert not missing, f"text requests priced without their messages: {missing}"
    assert len(text) >= 15
    partial = sorted(where.split(":")[0] for where, kw in calls
                     if "partial_billing" in kw)
    assert partial == ["agents/fiverr/panel.py", "agents/social/panel.py",
                       "agents/video/panel.py"]


def test_chat_send_validates_the_messages_its_worker_sends(win, monkeypatch):
    """Chat is not routed through authorize_request (B-F4), so its own
    estimate must price the worker's messages, project instructions too."""
    monkeypatch.setattr(win, "_active_project", lambda: {
        "id": "novel", "name": "Novel", "instructions": INSTRUCTIONS,
        "budget_eur": None})
    monkeypatch.setattr(win, "resolve_backend_model", lambda: ("openai", MODEL))
    monkeypatch.setattr(win, "_assess_safely", lambda *a, **k: None)
    monkeypatch.setattr(win, "check_memory_before_request", lambda *a: True)
    monkeypatch.setattr(win, "start_chat_timer", lambda *a: None)
    monkeypatch.setattr(win, "_conversation_context_text", lambda *a: "")
    estimates = []
    real_estimate = win.estimate_chat_cost
    monkeypatch.setattr(win, "estimate_chat_cost", lambda *a, **k: (
        estimates.append(k.get("messages")), real_estimate(*a, **k))[1])
    real_factory = win._new_chat_worker

    def factory(*a, **k):
        worker = real_factory(*a, **k)
        worker.start = lambda: None          # never run a request here
        return worker

    monkeypatch.setattr(win, "_new_chat_worker", factory)
    validated = []
    real_validate = win.validator.validate
    monkeypatch.setattr(win.validator, "validate", lambda **kw: (
        validated.append(kw["estimated_cost"]), real_validate(**kw))[1])
    win.chat_worker = None
    allowed = win.allow_openai_checkbox.isChecked()
    win.allow_openai_checkbox.setChecked(True)
    win.input_box.setPlainText("Write chapter 3.")
    estimates.clear()          # typing also updates the live line
    try:
        win.send_prompt()
        sent_estimates = list(estimates)
    finally:
        win.input_box.clear()
        win.allow_openai_checkbox.setChecked(allowed)
        win.send_btn.setEnabled(True)
        win.stop_chat_btn.setEnabled(False)
    assert win.chat_worker is not None, win.shown["warning"]
    (messages,) = sent_estimates
    worker_messages = win.chat_worker.messages
    assert with_project_instructions(messages, INSTRUCTIONS) == worker_messages
    expected = max_cost_eur("openai", MODEL,
                            estimate_input_tokens(worker_messages))
    assert validated == [expected]
    win.chat_worker = None
    win.active_run_id = None
