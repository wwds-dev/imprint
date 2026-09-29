"""Every provider streams; nobody waits-then-dumps.

Six of seven providers already streamed end-to-end (run_backend prefers
stream_chat, ChatWorker drains iterators, the UI appends per token). The
one holdout was ollama — the slowest responder in the app — whose branch
called the blocking chat() first. These tests pin the full contract:
run_backend prefers the stream for every backend, ollama's stream carries
the daemon's real token counts through UsageStream, and ChatWorker
delivers tokens incrementally with the stream's usage.
"""

import json
import os
import types

import pytest

from services.stream_usage import UsageStream


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question,
             QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved


def test_run_backend_prefers_the_stream_for_every_provider(
        window, monkeypatch):
    sentinel = object()

    def blocking(*a, **k):
        raise AssertionError("the blocking path must not be used")

    for backend in ("ollama", "openai", "deepseek", "kimi", "qwen",
                    "gemini", "anthropic"):
        monkeypatch.setattr(
            window, backend, types.SimpleNamespace(
                stream_chat=lambda *a, **k: sentinel, chat=blocking))
        if backend == "ollama":
            monkeypatch.setattr(window, "assess_local_model",
                                lambda model: None)
        result = window.run_backend(backend, "some-model",
                                    [{"role": "user", "content": "hi"}], "hi")
        assert result is sentinel, f"{backend} did not stream"


def test_ollama_stream_yields_tokens_and_real_usage(monkeypatch):
    from services import ollama_client

    frames = [
        {"message": {"content": "Hel"}},
        {"message": {"content": "lo"}},
        {"done": True, "prompt_eval_count": 12, "eval_count": 34},
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        @staticmethod
        def iter_lines():
            for frame in frames:
                yield json.dumps(frame).encode("utf-8")

    monkeypatch.setattr(ollama_client.requests, "post",
                        lambda *a, **k: FakeResponse())
    client = ollama_client.OllamaClient()
    stream = client.stream_chat("local", [{"role": "user", "content": "hi"}])
    assert isinstance(stream, UsageStream)
    assert "".join(stream) == "Hello"
    # The daemon's final frame becomes exact stats, like the cloud streams.
    assert stream.usage == {"input_tokens": 12, "output_tokens": 34}


def test_chat_worker_delivers_stream_tokens_and_usage(app):
    from ui.workers import ChatWorker

    def make_stream(*_args):
        def _gen(out):
            yield "one "
            yield "two"
            out.usage = {"input_tokens": 5, "output_tokens": 7}
        return UsageStream(_gen)

    worker = ChatWorker(make_stream, "ollama", "local",
                        [{"role": "user", "content": "hi"}], "hi")
    tokens, usages, finished = [], [], []
    worker.token_signal.connect(tokens.append)
    worker.usage_signal.connect(usages.append)
    worker.finished_signal.connect(finished.append)
    worker.run()
    assert tokens == ["one ", "two"]          # incremental, not one dump
    assert finished == ["one two"]
    assert usages == [{"input_tokens": 5, "output_tokens": 7}]


def test_cancelled_stream_is_not_billed_or_finished(app):
    from ui.workers import ChatWorker

    def make_stream(*_args):
        def _gen(out):
            yield "first"
            yield "never-seen"
            out.usage = {"input_tokens": 1, "output_tokens": 1}
        return UsageStream(_gen)

    worker = ChatWorker(make_stream, "ollama", "local",
                        [{"role": "user", "content": "hi"}], "hi")
    tokens, errors, usages, finished = [], [], [], []
    worker.token_signal.connect(
        lambda t: (tokens.append(t), worker.cancel()))
    worker.error_signal.connect(errors.append)
    worker.usage_signal.connect(usages.append)
    worker.finished_signal.connect(finished.append)
    worker.run()
    assert tokens == ["first"]
    assert errors == ["Request cancelled by user."]
    assert finished == [] and usages == []
