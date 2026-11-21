"""The release kit's 8,192-token reply cap reaches the local runtimes
(review P2-3): Ollama `num_predict`, LM Studio `max_tokens`, and a reply that
hit the cap reports stop_reason "length"."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services import lmstudio_client, ollama_client


def _response(lines):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        @staticmethod
        def iter_lines():
            yield from lines
    return FakeResponse()


def test_ollama_sends_num_predict_and_reports_a_capped_reply(monkeypatch):
    sent = {}
    frames = [{"message": {"content": "Hi"}},
              {"done": True, "done_reason": "length", "eval_count": 8192}]

    def post(url, **kwargs):
        sent.update(kwargs["json"])
        return _response([json.dumps(f).encode() for f in frames])
    monkeypatch.setattr(ollama_client.requests, "post", post)
    stream = ollama_client.OllamaClient("http://127.0.0.1:11434").stream_chat(
        "m", [{"role": "user", "content": "x"}], max_tokens=8192)
    assert "".join(stream) == "Hi"
    assert sent["options"] == {"num_predict": 8192}
    assert stream.stop_reason == "length"


def test_ollama_without_a_cap_sends_no_options(monkeypatch):
    sent = {}

    def post(url, **kwargs):
        sent.update(kwargs["json"])
        return _response([b'{"done": true, "done_reason": "stop"}'])
    monkeypatch.setattr(ollama_client.requests, "post", post)
    stream = ollama_client.OllamaClient("http://127.0.0.1:11434").stream_chat(
        "m", [{"role": "user", "content": "x"}])
    assert "".join(stream) == "" and "options" not in sent
    assert stream.stop_reason is None


def test_lm_studio_sends_max_tokens_and_reports_a_capped_reply(monkeypatch):
    sent = {}
    chunks = [{"choices": [{"delta": {"content": "Hi"}}]},
              {"choices": [{"delta": {}, "finish_reason": "length"}]}]

    def post(url, **kwargs):
        sent.update(kwargs["json"])
        return _response([f"data: {json.dumps(c)}".encode()
                          for c in chunks] + [b"data: [DONE]"])
    monkeypatch.setattr(lmstudio_client.requests, "post", post)
    client = lmstudio_client.LMStudioClient("http://127.0.0.1:1234/v1")
    stream = client.stream_chat("m", [{"role": "user", "content": "x"}],
                                max_tokens=8192)
    assert "".join(stream) == "Hi"
    assert sent["max_tokens"] == 8192 and stream.stop_reason == "length"


def test_run_backend_passes_the_cap_to_a_local_stream_and_refuses_otherwise():
    from main import GodAI
    seen = {}

    class Local:
        def stream_chat(self, *, messages, model, max_tokens=None):
            seen["max_tokens"] = max_tokens
            return "ok"
    host = SimpleNamespace(ollama=Local(), assess_local_model=lambda *a: None)
    msgs = [{"role": "user", "content": "x"}]
    assert GodAI.run_backend(host, "ollama", "m", msgs, "x", max_tokens=8192) == "ok"
    assert seen["max_tokens"] == 8192

    class ChatOnly:
        def chat(self, *, messages, model):
            raise AssertionError("an uncapped request was sent")
    host = SimpleNamespace(ollama=ChatOnly(), assess_local_model=lambda *a: None)
    with pytest.raises(RuntimeError, match="cannot cap"):
        GodAI.run_backend(host, "ollama", "m", msgs, "x", max_tokens=8192)
