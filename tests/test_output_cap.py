"""
Imprint — one output cap on every paid text client, and a cut-off that says so
==============================================================================
Type: unit + panel, no network (fake SDK clients; temp DB; offscreen Qt).

Audit B-F2 (spec docs/specs/audit-p1-billing.md): five of the six paid text
clients sent no output cap, so the guard's "max(250, 1.2 x input)" reservation
could be overshot thirty times over. Now every client sends
MAX_OUTPUT_TOKENS under its own parameter name in chat() and stream_chat(),
the stop reason comes back on the worker's usage signal, and a reply that
stopped at the cap shows the length-limit notice instead of "[Finished]" or
"[Done]" — next to the text, never inside it.

Run with:  pytest tests/test_output_cap.py -v
"""

import re
import types
from pathlib import Path

import pytest

from services import output_limits
from services.output_limits import MAX_OUTPUT_TOKENS, result_notice, stop_kind
from services.stream_usage import UsageStream

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = [{"role": "system", "content": "Be brief."},
            {"role": "user", "content": "Write chapter 3."}]


# ── Fake SDKs ────────────────────────────────────────────────────────────────

def _compat(finish="stop"):
    """An OpenAI-compatible SDK (OpenAI, DeepSeek, Kimi, Qwen) that records
    the keyword arguments of every create() call."""
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        usage = types.SimpleNamespace(prompt_tokens=10, completion_tokens=20,
                                      total_tokens=30)
        if kwargs.get("stream"):
            def chunks():
                yield types.SimpleNamespace(usage=None, choices=[
                    types.SimpleNamespace(delta=types.SimpleNamespace(content="Hi"),
                                          finish_reason=None)])
                yield types.SimpleNamespace(usage=None, choices=[
                    types.SimpleNamespace(delta=types.SimpleNamespace(content="."),
                                          finish_reason=finish)])
                # The usage-only frame comes last and carries no choices.
                yield types.SimpleNamespace(usage=usage, choices=[])
            return chunks()
        return types.SimpleNamespace(
            usage=usage,
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="Hi."),
                finish_reason=finish)])

    sdk = types.SimpleNamespace(chat=types.SimpleNamespace(
        completions=types.SimpleNamespace(create=create)))
    return sdk, calls


def _gemini(finish="STOP"):
    from google.genai import types as genai_types
    calls = []
    reason = getattr(genai_types.FinishReason, finish)
    meta = types.SimpleNamespace(prompt_token_count=10, candidates_token_count=20,
                                 thoughts_token_count=5,
                                 cached_content_token_count=None,
                                 total_token_count=35)

    def generate_content(**kwargs):
        calls.append(kwargs)
        return types.SimpleNamespace(
            text="Hi.", usage_metadata=meta,
            candidates=[types.SimpleNamespace(finish_reason=reason)])

    def generate_content_stream(**kwargs):
        calls.append(kwargs)
        return iter([
            types.SimpleNamespace(text="Hi", usage_metadata=meta, candidates=[
                types.SimpleNamespace(finish_reason=None)]),
            types.SimpleNamespace(text=".", usage_metadata=meta, candidates=[
                types.SimpleNamespace(finish_reason=reason)]),
        ])

    sdk = types.SimpleNamespace(models=types.SimpleNamespace(
        generate_content=generate_content,
        generate_content_stream=generate_content_stream))
    return sdk, calls


def _anthropic(finish="end_turn"):
    calls = []
    usage = types.SimpleNamespace(input_tokens=10, output_tokens=20,
                                  cache_read_input_tokens=0,
                                  cache_creation_input_tokens=0)
    message = types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text="Hi.")],
        stop_reason=finish, stop_details=None, usage=usage)

    class Stream:
        text_stream = iter(["Hi", "."])

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        @staticmethod
        def get_final_message():
            return message

    def create(**kwargs):
        calls.append(kwargs)
        return message

    def stream(**kwargs):
        calls.append(kwargs)
        return Stream()

    sdk = types.SimpleNamespace(messages=types.SimpleNamespace(
        create=create, stream=stream))
    return sdk, calls


def _client(name, finish=None):
    """(wrapper, recorded calls, parameter name, model) for one provider."""
    from services import (anthropic_client, deepseek_client, gemini_client,
                          kimi_client, openai_client, qwen_client)
    table = {
        "openai": (openai_client.OpenAIClientWrapper, _compat,
                   "max_completion_tokens", "gpt-4o-mini", "length"),
        "deepseek": (deepseek_client.DeepSeekClientWrapper, _compat,
                     "max_tokens", "deepseek-flash", "length"),
        "kimi": (kimi_client.KimiClientWrapper, _compat,
                 "max_tokens", "kimi-k2.7-code", "length"),
        "qwen": (qwen_client.QwenClientWrapper, _compat,
                 "max_tokens", "qwen-plus", "length"),
        "gemini": (gemini_client.GeminiClientWrapper, _gemini,
                   "config.max_output_tokens", "gemini-2.5-flash", "MAX_TOKENS"),
        "anthropic": (anthropic_client.AnthropicClientWrapper, _anthropic,
                      "max_tokens", "claude-sonnet-5-5", "max_tokens"),
    }
    cls, fake, param, model, cut = table[name]
    sdk, calls = fake(cut) if finish == "cut" else fake()
    wrapper = cls.__new__(cls)
    wrapper.client = sdk
    return wrapper, calls, param, model


def _sent_cap(kwargs, param):
    if param == "config.max_output_tokens":
        return kwargs["config"].max_output_tokens
    return kwargs[param]


PROVIDERS = ["openai", "deepseek", "kimi", "qwen", "gemini", "anthropic"]


def _run(wrapper, mode, model):
    if mode == "chat":
        text, usage = wrapper.chat(MESSAGES, model=model)
        return text, usage.get("stop_reason")
    stream = wrapper.stream_chat(MESSAGES, model=model)
    text = "".join(stream)
    return text, stream.stop_reason


# ── 1. Every client sends the cap under its own name ─────────────────────────

@pytest.mark.parametrize("mode", ["chat", "stream"])
@pytest.mark.parametrize("provider", PROVIDERS)
def test_each_client_sends_the_cap_under_its_own_name(provider, mode):
    wrapper, calls, param, model = _client(provider)
    text, stop = _run(wrapper, mode, model)
    assert text == "Hi."
    assert len(calls) == 1
    assert _sent_cap(calls[0], param) == MAX_OUTPUT_TOKENS == 8192
    if provider == "openai":
        # The deprecated name is rejected by o-series models; never send both.
        assert "max_tokens" not in calls[0]
    assert stop is None                 # a normal stop is not a cut-off


@pytest.mark.parametrize("mode", ["chat", "stream"])
def test_qwen_sends_its_thinking_budget(mode):
    """Owner decision, review loop 1: Qwen's thinking gets its own limit
    (DashScope `thinking_budget`, unverified name), which the guard reserves
    on top of the cap. The other clients send no thinking parameter."""
    wrapper, calls, _param, model = _client("qwen")
    _run(wrapper, mode, model)
    assert calls[0]["extra_body"] == {
        "thinking_budget": output_limits.QWEN_THINKING_BUDGET}
    assert output_limits.QWEN_THINKING_BUDGET == 8192
    assert output_limits.thinking_reserve_tokens("qwen", model) == 8192
    for other in ("openai", "deepseek", "kimi"):
        wrapper, calls, _param, model = _client(other)
        _run(wrapper, mode, model)
        assert "extra_body" not in calls[0], other


@pytest.mark.parametrize("mode", ["chat", "stream"])
@pytest.mark.parametrize("provider", PROVIDERS)
def test_each_client_reports_a_reply_that_stopped_at_the_cap(provider, mode):
    wrapper, _calls, _param, model = _client(provider, finish="cut")
    _text, stop = _run(wrapper, mode, model)
    assert stop == "length"


def test_no_cap_literal_outside_output_limits():
    """One constant. Anthropic's old 8096 is gone, and no client hard-codes
    its own figure again."""
    clients = sorted((ROOT / "services").glob("*_client.py"))
    assert len(clients) >= 6
    for path in clients + [ROOT / "main.py", ROOT / "ui" / "workers.py"]:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\b(8096|8192|8_192)\b", text), path.name


# ── 2. Stop reasons, and the worker's usage signal ──────────────────────────

def test_stop_kind_maps_every_providers_length_reason():
    from google.genai import types as genai_types
    for raw in ("length", "max_tokens", genai_types.FinishReason.MAX_TOKENS,
                "MAX_TOKENS", " Length "):
        assert stop_kind(raw) == "length", raw
    for raw in (None, "", "stop", "end_turn", "tool_use", "content_filter",
                genai_types.FinishReason.STOP, genai_types.FinishReason.SAFETY):
        assert stop_kind(raw) is None, raw
    assert stop_kind(stop_kind("max_tokens")) == "length"     # idempotent


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _worker_events(result):
    from ui.workers import ChatWorker
    worker = ChatWorker(lambda *_a: result, "openai", "m",
                        [{"role": "user", "content": "hi"}], "hi")
    events = []
    worker.usage_signal.connect(lambda u: events.append(("usage", u)))
    worker.finished_signal.connect(lambda r: events.append(("finished", r)))
    worker.error_signal.connect(lambda e: events.append(("error", e)))
    worker.run()
    return events


def _stream(usage=None, stop=None):
    def _gen(out):
        yield "cut "
        yield "here"
        out.usage = usage
        out.stop_reason = stop
    return UsageStream(_gen)


def test_worker_sends_the_stop_reason_before_finished_with_a_usage_frame(app):
    events = _worker_events(_stream({"input_tokens": 5, "output_tokens": 7},
                                    "length"))
    assert events == [
        ("usage", {"input_tokens": 5, "output_tokens": 7, "stop_reason": "length"}),
        ("finished", "cut here")]


def test_worker_sends_the_stop_reason_without_a_usage_frame(app):
    """No usage frame still means an estimated bill — but the cut-off must
    reach the panel all the same."""
    events = _worker_events(_stream(None, "length"))
    assert events[0] == ("usage", {"cost_type_override": "stream-estimated",
                                   "stop_reason": "length"})
    assert events[1] == ("finished", "cut here")


def test_worker_maps_a_tuple_replys_stop_reason(app):
    events = _worker_events(("all of it", {"input_tokens": 1,
                                           "output_tokens": 2,
                                           "stop_reason": "max_tokens"}))
    assert events[0][1]["stop_reason"] == "length"
    assert [kind for kind, _ in events] == ["usage", "finished"]


def test_a_complete_reply_carries_no_stop_reason(app):
    events = _worker_events(_stream({"input_tokens": 5, "output_tokens": 7}))
    assert events[0] == ("usage", {"input_tokens": 5, "output_tokens": 7})


# ── 3. Notices ───────────────────────────────────────────────────────────────

def test_notice_wording_per_kind():
    cut = {"stop_reason": "length", "backend": "openai"}
    assert result_notice(cut, "text", "chat") == output_limits.CHAT_CUT_OFF
    assert output_limits.CHAT_CUT_OFF.startswith(
        "[Cut off] Stopped at the length limit (8,192 tokens); this answer is "
        "incomplete. To get the rest, send \"continue\"")
    assert result_notice(cut, "a b c", "author", words=5234) == (
        "[Cut off] 5,234 words, stopped at the length limit. Press Continue "
        "to write more.")
    assert result_notice(cut, "x") == (
        "[Cut off] Stopped at the length limit (8,192 tokens); the result is "
        "incomplete. Ask for less or split the task, then run it again.")
    # Complete, unknown or missing entries say nothing.
    assert result_notice({"stop_reason": None}, "x") is None
    assert result_notice(None, "x") is None
    assert result_notice({}, "x") is None


def test_gemini_thinking_suffix_and_the_empty_billed_answer():
    thinking = {"stop_reason": "length", "backend": "gemini", "thought_tokens": 900}
    assert result_notice(thinking, "partial").endswith(
        " Gemini spent part of the limit thinking.")
    assert result_notice(thinking, "  ") == (
        "[No answer] Gemini used the whole length limit (8,192 tokens) "
        "thinking and wrote nothing. It is still billed; see Cost History.")
    # No thought tokens: the plain notice, no suffix.
    plain = {"stop_reason": "length", "backend": "gemini", "thought_tokens": 0}
    assert "thinking" not in result_notice(plain, "partial")


def test_gemini_reports_thought_tokens_for_the_notice():
    wrapper, _calls, _param, model = _client("gemini", finish="cut")
    _text, usage = wrapper.chat(MESSAGES, model=model)
    assert usage["thought_tokens"] == 5
    stream = wrapper.stream_chat(MESSAGES, model=model)
    "".join(stream)
    assert stream.usage["thought_tokens"] == 5


# ── Notices in the window (Chat, Author, a generic panel, Manuscript) ───────

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


@pytest.fixture
def win(_window, tmp_path, monkeypatch):
    from services import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "imprint.db")
    database.init_db()
    monkeypatch.setattr(_window, "load_history_list", lambda: None)
    monkeypatch.setattr(_window.history, "save_chat", lambda **kw: None)
    _window._pending_requests = {}
    _window._pending_by_agent = {}
    return _window


def _chat_reply(win, response, usage):
    win.pending_agent, win.pending_tool = "chat", "General Chat"
    win.pending_backend, win.pending_model = "openai", "gpt-4o-mini"
    win.pending_command = ""
    win.pending_messages = [{"role": "user", "content": "Write it all."}]
    win.pending_prompt = win.pending_billing_prompt = "Write it all."
    win.pending_project, win.pending_project_instructions = None, ""
    win.pending_usage = usage
    win.active_run_id = None
    win.output_box.clear()
    win.handle_chat_finished(response)
    return win.output_box.toPlainText()


def test_chat_shows_cut_off_and_never_finished(win):
    shown = _chat_reply(win, "Half a chapter",
                        {"input_tokens": 10, "output_tokens": 8192,
                         "stop_reason": "length"})
    assert "[Cut off] Stopped at the length limit (8,192 tokens)" in shown
    assert "[Finished]" not in shown
    # The notice is beside the answer, never part of the saved conversation.
    assert win.current_messages[-1] == {"role": "assistant",
                                        "content": "Half a chapter"}


def test_chat_still_finishes_a_complete_reply(win):
    shown = _chat_reply(win, "All of it", {"input_tokens": 10, "output_tokens": 30})
    assert "[Finished]" in shown and "[Cut off]" not in shown


def test_author_reports_words_and_points_at_continue(win, monkeypatch):
    panel = win.author_panel
    monkeypatch.setattr(win, "record_request", lambda token, response, messages=None:
                        {"stop_reason": "length", "backend": "openai"})
    panel._write_token = "token"
    panel._is_continuing = False
    panel.author_task_box.setCurrentIndex(0)
    if panel.author_task_box.currentText() in {
            "Generate Outline", "Develop Characters", "Build World"}:
        pytest.skip("the first Author task routes to a side tab")
    panel._on_finished("word " * 1234)
    assert panel.author_status_label.text().startswith(
        "[Cut off] 1,234 words, stopped at the length limit. Press Continue")
    assert panel.author_status_label.wordWrap()


def test_a_generic_panel_shows_the_cut_off_line_instead_of_done(win, monkeypatch):
    panel = win.social_panel
    monkeypatch.setattr(win, "record_request", lambda token, response, messages=None:
                        {"stop_reason": "length", "backend": "openai"})
    panel._write_token = "token"
    panel._on_written("Variant one, cut mid-")
    assert panel.social_status_label.text() == output_limits.RESULT_CUT_OFF
    assert panel.social_status_label.wordWrap()


def test_a_cut_manuscript_list_shows_the_cut_off_line_not_the_parse_error(
        win, monkeypatch):
    panel = win.manuscript_panel
    monkeypatch.setattr(win, "record_request", lambda token, response, messages=None:
                        {"stop_reason": "length", "backend": "openai"})
    panel._quote_finder_token = "token"
    panel._on_quotes_found('["The first quote", "The sec')
    assert panel.manuscript_status_label.text() == output_limits.RESULT_CUT_OFF
    assert "parse" not in panel.manuscript_status_label.text()
    # The calendar captions say the same rather than "[Done] … generated".
    panel._calendar_captions_token = "token"
    panel._calendar_slots = []
    panel._on_captions_done('["caption one", "capt')
    assert panel.manuscript_status_label.text() == output_limits.RESULT_CUT_OFF


def test_status_labels_that_show_notices_wrap(win):
    labels = [win.author_panel.author_status_label,
              win.social_panel.social_status_label,
              win.manuscript_panel.manuscript_status_label,
              win.creator_panel.creator_status_label,
              win.webdesign_panel.webdesign_status_label,
              win.music_panel.music_status_label,
              win.fiverr_panel.fiverr_preview_status]
    assert all(label.wordWrap() for label in labels)


def test_creator_drafts_report_usage_and_the_stop_reason(win, monkeypatch):
    """Creator never connected usage_signal (audit B-F8), so a draft was
    billed on chars/4 and a cut-off could not be seen."""
    from PySide6.QtCore import QObject, Signal

    class FakeWorker(QObject):
        finished_signal = Signal(str)
        error_signal = Signal(str)
        usage_signal = Signal(dict)
        token_signal = Signal(str)

        def start(self):
            pass

    panel = win.creator_panel
    worker = FakeWorker()
    noted = []
    monkeypatch.setattr(win, "_new_chat_worker", lambda *a, **k: worker)
    monkeypatch.setattr(win, "authorize_request", lambda *a, **k: "draft-token")
    monkeypatch.setattr(win, "pending_request_snapshot", lambda token: {})
    monkeypatch.setattr(win, "note_request_usage",
                        lambda token, usage: noted.append((token, usage)))
    monkeypatch.setattr(panel, "current_account", lambda: {"id": 1})
    monkeypatch.setattr(win.agent_instances["creator"], "build_draft_prompt",
                        lambda *a, **k: [{"role": "user", "content": "Draft."}])
    monkeypatch.setattr(panel.creator_model_box, "currentText", lambda: "m")
    panel.generate()
    worker.usage_signal.emit({"input_tokens": 1, "output_tokens": 2,
                              "stop_reason": "length"})
    assert noted == [("draft-token", {"input_tokens": 1, "output_tokens": 2,
                                      "stop_reason": "length"})]


def test_gemini_stream_keeps_the_stop_reason_once_set():
    """A chunk after the one that said MAX_TOKENS, with a candidate but no
    finish reason, used to reset the stop reason to None (code review P3-2),
    and a cut-off reply showed as complete."""
    from google.genai import types as genai_types
    wrapper, calls, _param, model = _client("gemini")
    meta = types.SimpleNamespace(prompt_token_count=10, candidates_token_count=20,
                                 thoughts_token_count=0,
                                 cached_content_token_count=None,
                                 total_token_count=30)
    wrapper.client.models.generate_content_stream = lambda **kw: iter([
        types.SimpleNamespace(text="Hi", usage_metadata=meta, candidates=[
            types.SimpleNamespace(
                finish_reason=genai_types.FinishReason.MAX_TOKENS)]),
        types.SimpleNamespace(text="", usage_metadata=meta, candidates=[
            types.SimpleNamespace(finish_reason=None)]),
    ])
    stream = wrapper.stream_chat(MESSAGES, model=model)
    assert "".join(stream) == "Hi"
    assert stream.stop_reason == "length"


# ── The stop reason through the real guard (code review P2-2) ───────────────

ALL_ALLOWED = {f"allow_{p}": True for p in (
    "openai", "deepseek", "kimi", "gemini", "anthropic", "qwen",
    "higgsfield", "elevenlabs")}


@pytest.fixture
def guarded(win, monkeypatch):
    """The window with paid requests allowed, so authorize_request mints a
    real token and record_request bills it."""
    monkeypatch.setattr(win, "current_api_permissions", lambda: dict(ALL_ALLOWED))
    monkeypatch.setattr(win, "_active_project", lambda: None)
    monkeypatch.setattr(win, "update_usage_labels", lambda: None)
    monkeypatch.setattr(win, "session_cost_total", 0.0)
    monkeypatch.setattr(win, "session_budget_eur", 10.0)
    monkeypatch.setattr(win, "daily_budget_eur", 10.0)
    return win


def test_record_request_returns_the_workers_stop_reason_and_thought_tokens(
        guarded):
    """authorize → the worker's usage signal (note_request_usage) → the real
    record_request: the entry a panel reads its notice from carries both."""
    win = guarded
    messages = [{"role": "user", "content": "Write it all."}]
    token = win.authorize_request("social", "gemini", "gemini-2.5-flash",
                                  messages[-1]["content"], messages=messages)
    assert token
    win.note_request_usage(token, {"input_tokens": 10, "output_tokens": 8192,
                                   "stop_reason": "length",
                                   "thought_tokens": 6000})
    entry = win.record_request(token, "Half an answer")
    assert (entry["stop_reason"], entry["thought_tokens"]) == ("length", 6000)
    assert (entry["output_tokens"], entry["cost_type"]) == (8192, "exact")
    assert result_notice(entry, "Half an answer") == (
        output_limits.RESULT_CUT_OFF + output_limits.GEMINI_THINKING_SUFFIX)
    # A complete reply through the same path says nothing.
    token = win.authorize_request("social", "openai", "gpt-4o-mini",
                                  messages[-1]["content"], messages=messages)
    win.note_request_usage(token, {"input_tokens": 10, "output_tokens": 30})
    entry = win.record_request(token, "All of it")
    assert (entry["stop_reason"], entry["thought_tokens"]) == (None, 0)


def test_a_panel_shows_the_cut_off_line_from_the_real_record_request(guarded):
    win = guarded
    panel = win.social_panel
    messages = [{"role": "user", "content": "Three posts about the launch."}]
    token = win.authorize_request("social", "openai", "gpt-4o-mini",
                                  messages[-1]["content"], messages=messages)
    assert token
    panel._write_token = token
    win.note_request_usage(token, {"input_tokens": 12, "output_tokens": 8192,
                                   "stop_reason": "length"})
    panel._on_written("Variant one, cut mid-")
    assert panel.social_status_label.text() == output_limits.RESULT_CUT_OFF
    assert token not in win._pending_requests
