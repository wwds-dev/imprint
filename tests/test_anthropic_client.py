"""
Imprint — Anthropic client: refusals and cached tokens
======================================================
Type: unit, no network (the SDK client is replaced by a stub).

Claude Opus 5.5, Sonnet 5.5 and Fable 5.1 can stop a turn with
stop_reason "refusal" and HTTP 200. The client used to return that turn's empty
text, so a refusal looked like a blank reply. And Anthropic reports
input_tokens *excluding* prompt-cache reads, which the usage tracker needs
added back and named so the cached slice bills at the cached rate.

Run with:  pytest tests/test_anthropic_client.py -v
"""

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import anthropic_client as ac  # noqa: E402


def _message(text="", stop_reason="end_turn", category=None, read=0, written=0):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text=text)] if text else [],
        stop_reason=stop_reason,
        stop_details=(types.SimpleNamespace(category=category,
                                            explanation="Declined.")
                      if stop_reason == "refusal" else None),
        usage=types.SimpleNamespace(input_tokens=100, output_tokens=20,
                                    cache_read_input_tokens=read,
                                    cache_creation_input_tokens=written),
    )


def _wrapper(message):
    wrapper = ac.AnthropicClientWrapper.__new__(ac.AnthropicClientWrapper)
    wrapper.client = types.SimpleNamespace(messages=types.SimpleNamespace(
        create=lambda **kwargs: message))
    return wrapper


def test_a_refusal_is_an_error_not_an_empty_reply():
    wrapper = _wrapper(_message(stop_reason="refusal", category="cyber"))
    with pytest.raises(RuntimeError, match=r"declined this request \(cyber\)"):
        wrapper.chat([{"role": "user", "content": "hello"}], model="claude-opus-5-5")


def test_a_normal_reply_still_returns_its_text():
    text, usage = _wrapper(_message("Hi.")).chat(
        [{"role": "user", "content": "hello"}], model="claude-sonnet-5-5")
    assert text == "Hi."
    assert usage == {"input_tokens": 100, "output_tokens": 20,
                     "cached_input_tokens": 0}


def test_cache_reads_are_counted_as_input_and_named_as_cached():
    _text, usage = _wrapper(_message("Hi.", read=900, written=50)).chat(
        [{"role": "user", "content": "hello"}], model="claude-sonnet-5-5")
    assert usage == {"input_tokens": 1050, "output_tokens": 20,
                     "cached_input_tokens": 900}


def test_the_offline_list_carries_no_retired_model():
    assert not [m for m in ac.AnthropicClientWrapper.KNOWN_MODELS
                if m.startswith("claude-3")]
    assert "claude-opus-5-5" in ac.AnthropicClientWrapper.KNOWN_MODELS
