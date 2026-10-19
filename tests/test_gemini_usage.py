"""
Imprint — Gemini usage: thinking and cached tokens are recorded
===============================================================
Type: unit, no network (the SDK client is replaced by a stub; temp DB).

google-genai counts a thinking model's thoughts apart from its answer, and
Google bills them at the output rate. The client recorded
`candidates_token_count` only, so a gemini-3.1-pro-preview reply with 800
visible and 6,000 thinking tokens was recorded at about a sixth of its bill,
and the daily, agent and project caps tripped late (audit B-F1). Cached prompt
tokens were not passed either, so a cache hit was recorded at the full input
rate. Both paths are covered: `chat()` and `stream_chat()`.

Run with:  pytest tests/test_gemini_usage.py -v
"""

import os
import sqlite3
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import database  # noqa: E402
from services import gemini_client as gc  # noqa: E402
from services.usage_tracker import UsageTracker  # noqa: E402

MODEL = "gemini-3.1-pro-preview"
MESSAGES = [{"role": "user", "content": "Outline chapter 3."}]


def _meta(prompt=1000, cached=400, candidates=800, thoughts=6000):
    return types.SimpleNamespace(
        prompt_token_count=prompt, cached_content_token_count=cached,
        candidates_token_count=candidates, thoughts_token_count=thoughts,
        total_token_count=None)


def _wrapper(meta):
    """A wrapper whose SDK answers with `meta`, for both call shapes.

    The stream's earlier chunk carries a smaller running count, as the real
    stream does; the last one seen is the bill.
    """
    response = types.SimpleNamespace(text="Answer.", usage_metadata=meta)
    early = _meta(candidates=1, thoughts=6000) if meta is not None else None
    chunks = [types.SimpleNamespace(text="Ans", usage_metadata=early),
              types.SimpleNamespace(text="wer.", usage_metadata=meta)]
    wrapper = gc.GeminiClientWrapper.__new__(gc.GeminiClientWrapper)
    wrapper.client = types.SimpleNamespace(models=types.SimpleNamespace(
        generate_content=lambda **kwargs: response,
        generate_content_stream=lambda **kwargs: iter(chunks)))
    return wrapper


def _via_chat(meta):
    text, usage = _wrapper(meta).chat(MESSAGES, model=MODEL)
    assert text == "Answer."
    return usage


def _via_stream(meta):
    stream = _wrapper(meta).stream_chat(MESSAGES, model=MODEL)
    assert "".join(stream) == "Answer."
    return stream.usage


CALLS = pytest.mark.parametrize("call", [_via_chat, _via_stream],
                                ids=["chat", "stream_chat"])


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    """A temp DB holding the spec's price row, so the example's euros do not
    move when config/pricing.json is re-priced."""
    path = tmp_path / "usage.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(database.SCHEMA)
    conn.execute(
        "INSERT OR REPLACE INTO pricing (backend, model, input_per_1m_usd, "
        "output_per_1m_usd, cached_input_per_1m_usd) VALUES (?,?,?,?,?)",
        ("gemini", MODEL, 4.0, 18.0, 0.40))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) "
                 "VALUES ('eur_per_usd', '0.92')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", path)
    return UsageTracker()


@CALLS
def test_thinking_is_output_and_the_cached_slice_is_named(call):
    usage = call(_meta())
    assert usage["input_tokens"] == 1000
    assert usage["cached_input_tokens"] == 400
    assert usage["output_tokens"] == 6800


@CALLS
def test_a_reply_without_thinking_bills_its_answer_only(call):
    """Fields the API leaves out come back None, which must count as 0."""
    usage = call(_meta(cached=None, thoughts=None))
    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 800
    assert usage["cached_input_tokens"] == 0


@CALLS
def test_the_recorded_cost_is_what_google_bills(call, tracker):
    """Spec example: 600 x $4 + 400 x $0.40 + 6,800 x $18 per 1M, x 0.92.
    Before the fix this recorded about EUR 0.0206 for the same reply."""
    entry = tracker.log_request("chat", "gemini", MODEL, "prompt", "Answer.",
                                usage=call(_meta()))
    expected = (600 * 4.0 + 400 * 0.40 + 6800 * 18.0) / 1_000_000 * 0.92
    assert entry["cost_eur"] == pytest.approx(expected, abs=1e-6)
    assert round(entry["cost_eur"], 4) == 0.1150
    assert (entry["input_tokens"], entry["output_tokens"]) == (1000, 6800)
    assert entry["cost_type"] == "exact"
    rows = tracker.load_log()
    assert [r["cost_eur"] for r in rows] == [entry["cost_eur"]]


def test_no_usage_metadata_counts_nothing():
    """A response without usage leaves billing to the tracker's estimate,
    as before; it must not raise."""
    assert gc._usage(None) == {"input_tokens": 0, "output_tokens": 0,
                               "cached_input_tokens": 0}
    assert _via_chat(None)["output_tokens"] == 0
