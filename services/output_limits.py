"""The one output cap every paid text request is sent with, and what hitting it
looks like to the user.

No client sent a cap before 2026-10-14 except Anthropic (8096), so OpenAI,
DeepSeek, Kimi, Qwen and Gemini wrote as long as they liked while the guard
reserved `max(250, 1.2 × input)` tokens of output: one request could overshoot
what was left of a budget thirty times over (audit B-F2). Now every client sends
MAX_OUTPUT_TOKENS under its own parameter name, the guard reserves exactly that
much output, and a reply that stops at the cap says so next to the text.

Deliberately imports nothing: the clients, the tracker, the workers and the
panels all read it.
"""

from __future__ import annotations

# One cap for all six text clients (owner decision D1). Per-agent caps would be
# a new settings surface, which the feature freeze rules out; every client
# takes it as a keyword so they need no signature change later.
MAX_OUTPUT_TOKENS = 8192

# The limit on a Qwen model's thinking, sent by services/qwen_client.py on
# chat() and stream_chat() as DashScope's `thinking_budget` (owner decision,
# review loop 1). Unverified parameter, confirm on first paid run: the name
# comes from a search summary, not a fetched page (TODO.md `@me`). A rejected
# parameter would fail every Qwen request.
QWEN_THINKING_BUDGET = 8192

# Thinking tokens the guard reserves on top of the cap, where the cap may not
# bound them (owner decision, review loop 1, replacing a provider-wide 65,536
# stand-in that refused kimi-k3 on a fresh session). OpenAI's
# `max_completion_tokens` and Gemini's `max_output_tokens` are documented to
# include reasoning, so they need no extra term (spec D4).
#
# Sources: docs/company/radar-notes/2026-10-14-feature-billing.md and the
# review loop 1 decision in docs/specs/audit-p1-billing.md.
# - deepseek: 65,536. DeepSeek documents the default `max_tokens` as 64K in
#   thinking mode (128K only with reasoning_effort=max, which Imprint never
#   sends). Whether reasoning counts toward `max_tokens` is NOT documented.
# - qwen: the thinking budget Imprint now sends, above.
# - kimi: none. Kimi's thinking-model doc (search summary) says
#   `reasoning_content` counts against `max_tokens`, so the cap bounds it.
# A ("provider", "model") row wins over its provider's, for when a paid run
# shows one model differs; there is none yet.
THINKING_MAX_TOKENS = {
    "deepseek": 65_536,
    "qwen": QWEN_THINKING_BUDGET,
}

# The finish reasons that mean "stopped at the cap": OpenAI-compatible APIs
# (OpenAI, DeepSeek, Kimi, Qwen) say "length", Anthropic says "max_tokens" and
# Gemini's FinishReason.MAX_TOKENS is read by its name.
_LENGTH_REASONS = {"length", "max_tokens"}


def stop_kind(raw) -> str | None:
    """"length" when a provider's finish reason means the cap was hit, else
    None. Idempotent, so a value that was already mapped maps to itself."""
    if raw is None:
        return None
    name = getattr(raw, "name", None)       # Gemini's FinishReason enum
    text = name if isinstance(name, str) else str(raw)
    return "length" if text.strip().lower() in _LENGTH_REASONS else None


def thinking_reserve_tokens(backend: str, model: str | None = None) -> int:
    """Output tokens reserved for thinking on top of the cap: the model's
    own row, else its provider's, else 0 (the cap bounds thinking)."""
    provider = (backend or "").lower()
    if model and (provider, model) in THINKING_MAX_TOKENS:
        return THINKING_MAX_TOKENS[(provider, model)]
    return THINKING_MAX_TOKENS.get(provider, 0)


def reserved_output_tokens(backend: str, model: str | None = None) -> int:
    """The most output one request can be billed for, as the guard reserves it."""
    return MAX_OUTPUT_TOKENS + thinking_reserve_tokens(backend, model)


def output_reserve_short(backend: str, model: str | None = None) -> str:
    """The output reserve for the one-line estimates: "up to 8,192"."""
    text = f"up to {MAX_OUTPUT_TOKENS:,}"
    extra = thinking_reserve_tokens(backend, model)
    return text + (f" + {extra:,} thinking" if extra else "")


def output_reserve_text(backend: str, model: str | None = None) -> str:
    """The output half of "N tokens sent and up to M written", in words."""
    text = f"up to {MAX_OUTPUT_TOKENS:,} written (the length limit)"
    extra = thinking_reserve_tokens(backend, model)
    if extra:
        text += f", plus up to {extra:,} for thinking"
    return text


# ── What a cut-off reply says (spec Design, "B-F2 length-limit notice") ─────
# Shown next to the text, never inserted into it: a notice inside the answer
# would be saved and exported with it.

CHAT_CUT_OFF = (
    f"[Cut off] Stopped at the length limit ({MAX_OUTPUT_TOKENS:,} tokens); "
    "this answer is incomplete. To get the rest, send \"continue\" as your "
    "next message (a new paid request).")
RESULT_CUT_OFF = (
    f"[Cut off] Stopped at the length limit ({MAX_OUTPUT_TOKENS:,} tokens); "
    "the result is incomplete. Ask for less or split the task, then run it "
    "again.")
GEMINI_THINKING_SUFFIX = " Gemini spent part of the limit thinking."
GEMINI_NO_ANSWER = (
    f"[No answer] Gemini used the whole length limit ({MAX_OUTPUT_TOKENS:,} "
    "tokens) thinking and wrote nothing. It is still billed; see Cost History.")


def result_notice(entry, response: str, kind: str = "result", *,
                  words: int | None = None) -> str | None:
    """The status line for a reply that stopped at the cap, else None.

    `entry` is what `record_request` returns (or Chat's own usage entry):
    its "stop_reason" and "thought_tokens" come from the worker's usage
    signal. `kind` is "chat" (the transcript), "author" (Write/Continue,
    the only panel with a Continue control) or anything else for a panel's
    status label. `words` is Author's draft count; it defaults to the
    reply's own.
    """
    if not entry or stop_kind(entry.get("stop_reason")) != "length":
        return None
    # Only Gemini reports thought tokens apart from the answer.
    thinking = (str(entry.get("backend") or "").lower() == "gemini"
                and int(entry.get("thought_tokens") or 0) > 0)
    if thinking and not (response or "").strip():
        return GEMINI_NO_ANSWER
    if kind == "chat":
        text = CHAT_CUT_OFF
    elif kind == "author":
        count = len((response or "").split()) if words is None else int(words)
        text = (f"[Cut off] {count:,} words, stopped at the length limit. "
                "Press Continue to write more.")
    else:
        text = RESULT_CUT_OFF
    if thinking:
        text += GEMINI_THINKING_SUFFIX
    return text
