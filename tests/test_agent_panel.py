"""
Imprint — AgentPanel / AgentHost tests
===============================================
Type: Unit tests for the phase 3 refactor seam.

`ui/panels/base.py` absorbed five near-identical `*_load_models` methods. Two of
those five differed in ways that mattered, so this file pins both the shared
behaviour and the differences that had to survive:

  - manuscript offers a restricted provider list (no ollama), matching the
    allowed_providers on its registry row;
  - failures are reported through the host rather than swallowed, which the
    music panel used not to do.

Since the async-refresh change, load_models seeds the box synchronously from
the host's session cache or the client's KNOWN_MODELS (imprintModelsLive
False), and the live list arrives from one shared ModelListWorker per
provider. A host without `model_list_workers` (like the bare FakeHost here)
never spawns threads — the seeded list is the whole answer.

Run with:  pytest tests/test_agent_panel.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ui.host import AgentHost
from ui.panels.base import ALL_PROVIDERS, AgentPanel


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class FakeClient:
    def __init__(self, models, live=None):
        # KNOWN_MODELS is the synchronous seed; list_models the live answer.
        self.KNOWN_MODELS = list(models)
        self._live = list(live) if live is not None else list(models)

    def list_models(self):
        return list(self._live)


class ExplodingClient:
    """No KNOWN_MODELS and a failing live call — the worst provider."""

    def list_models(self):
        raise RuntimeError("provider unreachable")


class AsyncHostMixin:
    """The three attributes GodAI adds for the shared-worker refresh."""

    def _arm_async(self):
        self.model_list_workers = {}
        self.model_list_cache = {}
        self.listed = []

    def _on_models_listed(self, provider, models, error):
        self.listed.append((provider, models, error))
        if models:
            self.model_list_cache[provider] = list(models)
        elif error:
            # Mirrors GodAI: a failed fetch re-arms the retry.
            self.model_list_workers.pop(provider, None)
            self._note_failure(f"models: {provider}", RuntimeError(error))


class FakeHost:
    """Minimal stand-in for GodAI — only what AgentHost promises."""

    def __init__(self, **clients):
        for name in ALL_PROVIDERS:
            setattr(self, name, clients.get(name, FakeClient([f"{name}-a", f"{name}-b"])))
        self.agent_instances = {}
        self.failures = []

    def run_backend(self, backend, model, messages, prompt): ...
    def _new_chat_worker(self, backend, model, messages, prompt): ...
    def authorize_request(self, agent, provider, model, prompt, tool=None, label=None): ...
    def record_request(self, agent, response, messages=None): ...
    def abandon_request(self, agent, reason="error"): ...
    def note_request_usage(self, agent, usage): ...
    def pending_request_snapshot(self, token): ...
    def restore_request(self, agent, provider, model, prompt, *, label=None,
                        flat_cost_eur=None, project=None, run_id=""): ...
    def show_agent_docs(self): ...

    def _note_failure(self, context, exc, widget=None):
        self.failures.append((context, exc))


def test_fake_host_satisfies_the_protocol():
    """The point of a runtime-checkable protocol: a stand-in can be verified."""
    assert isinstance(FakeHost(), AgentHost)


def test_provider_box_lists_every_provider_by_default(app):
    panel = AgentPanel(FakeHost(), "author")
    items = [panel.provider_box.itemText(i) for i in range(panel.provider_box.count())]
    assert items == list(ALL_PROVIDERS)


def test_restricted_provider_list_is_honoured(app):
    """manuscript must not offer ollama — the validator would refuse it."""
    panel = AgentPanel(FakeHost(), "manuscript",
                       providers=("anthropic", "openai", "deepseek", "kimi", "gemini", "qwen"))
    items = [panel.provider_box.itemText(i) for i in range(panel.provider_box.count())]
    assert "ollama" not in items
    assert items[0] == "anthropic"


def test_default_provider_is_selected(app):
    panel = AgentPanel(FakeHost(), "author", default_provider="anthropic")
    assert panel.provider_box.currentText() == "anthropic"


def test_a_default_outside_the_list_is_ignored(app):
    """Asking for a provider this agent may not use must not add it."""
    panel = AgentPanel(FakeHost(), "manuscript",
                       providers=("anthropic", "openai"), default_provider="ollama")
    assert panel.provider_box.currentText() == "anthropic"


def test_load_models_fills_the_box_from_the_selected_provider(app):
    host = FakeHost(openai=FakeClient(["gpt-4o-mini", "gpt-4.1"]))
    panel = AgentPanel(host, "author", default_provider="openai")
    panel.load_models()
    assert [panel.model_box.itemText(i) for i in range(panel.model_box.count())] == \
        ["gpt-4o-mini", "gpt-4.1"]


def test_switching_provider_reloads_the_models(app):
    host = FakeHost(openai=FakeClient(["gpt-4o-mini"]),
                    anthropic=FakeClient(["claude-sonnet-5"]))
    panel = AgentPanel(host, "author", default_provider="openai")
    panel.provider_box.setCurrentText("anthropic")
    assert panel.model == "claude-sonnet-5"


def test_reloading_does_not_duplicate_entries(app):
    panel = AgentPanel(FakeHost(), "author", default_provider="openai")
    panel.load_models()
    panel.load_models()
    assert panel.model_box.count() == 2


def test_every_listed_provider_can_load(app):
    """manuscript listed qwen but its old loader had no qwen branch, so picking
    it silently produced an empty model box. Every listed provider must load."""
    panel = AgentPanel(FakeHost(), "manuscript",
                       providers=("anthropic", "openai", "deepseek", "kimi", "gemini", "qwen"))
    for provider in ("anthropic", "openai", "deepseek", "kimi", "gemini", "qwen"):
        panel.provider_box.setCurrentText(provider)
        # Explicit: setting the box to the value it already holds emits no
        # currentTextChanged, so the first provider would never load itself.
        panel.load_models()
        assert panel.model_box.count() > 0, f"{provider} loaded nothing"


def _async_host(**clients):
    class AsyncFakeHost(AsyncHostMixin, FakeHost):
        pass
    host = AsyncFakeHost(**clients)
    host._arm_async()
    return host


def _run_worker_synchronously(monkeypatch):
    from ui.workers import ModelListWorker
    monkeypatch.setattr(ModelListWorker, "start", ModelListWorker.run)


def test_a_failing_provider_is_reported_not_swallowed(app, monkeypatch):
    """The music panel used to do `except Exception: models = []`, leaving an
    empty dropdown and no explanation. The report now comes from the shared
    worker through the host's _on_models_listed."""
    _run_worker_synchronously(monkeypatch)
    host = _async_host(openai=ExplodingClient())
    panel = AgentPanel(host, "music", default_provider="openai")
    panel.load_models()
    assert host.failures, "failure was swallowed"
    context, exc = host.failures[-1]
    assert context == "models: openai"
    assert isinstance(exc, RuntimeError)


def test_a_failing_provider_leaves_the_box_empty_rather_than_stale(app):
    host = FakeHost(openai=FakeClient(["gpt-4o-mini"]), anthropic=ExplodingClient())
    panel = AgentPanel(host, "music", default_provider="openai")
    panel.load_models()
    panel.provider_box.setCurrentText("anthropic")
    assert panel.model_box.count() == 0


# ── the async half: seeding, the shared worker, the live swap ───────────────

def test_seeded_box_is_marked_not_live(app):
    panel = AgentPanel(FakeHost(), "author", default_provider="openai")
    panel.load_models()
    assert panel.model_box.property("imprintModelsLive") is False


def test_bare_fakehost_never_spawns_a_worker(app, monkeypatch):
    started = []
    from ui.workers import ModelListWorker
    monkeypatch.setattr(ModelListWorker, "start",
                        lambda self: started.append(self))
    panel = AgentPanel(FakeHost(), "author", default_provider="openai")
    panel.load_models()
    assert started == []


def test_live_list_replaces_the_seed_and_preserves_selection(
        app, monkeypatch):
    _run_worker_synchronously(monkeypatch)
    host = _async_host(anthropic=FakeClient(
        ["claude-sonnet-4-6", "claude-haiku-4-5"],
        live=["claude-haiku-4-5-20251001", "claude-sonnet-4-6-20260112"]))
    refreshed = []
    panel = AgentPanel(host, "author", default_provider="anthropic")
    panel.models_refreshed.connect(refreshed.append)
    panel.load_models()
    # Seed selected the bare name; the worker already ran synchronously and
    # swapped in the dated live ids.
    assert panel.model_box.property("imprintModelsLive") is True
    items = [panel.model_box.itemText(i)
             for i in range(panel.model_box.count())]
    assert items == ["claude-haiku-4-5-20251001", "claude-sonnet-4-6-20260112"]
    assert refreshed == ["author"]
    assert host.model_list_cache["anthropic"] == items


def test_selection_survives_the_swap_via_the_host_reconciler(
        app, monkeypatch):
    _run_worker_synchronously(monkeypatch)
    host = _async_host(anthropic=FakeClient(
        ["claude-sonnet-4-6"], live=["claude-sonnet-4-6-20260112"]))
    # GodAI reconciles bare seeded names against dated live ids.
    host._find_model_index = staticmethod(
        lambda combo, wanted: next(
            (i for i in range(combo.count())
             if combo.itemText(i).startswith(wanted)), -1))
    panel = AgentPanel(host, "author", default_provider="anthropic")
    panel.load_models()
    assert panel.model == "claude-sonnet-4-6-20260112"


def test_cached_provider_seeds_live_and_skips_the_worker(app, monkeypatch):
    started = []
    from ui.workers import ModelListWorker
    monkeypatch.setattr(ModelListWorker, "start",
                        lambda self: started.append(self))
    host = _async_host(openai=FakeClient(["gpt-4o-mini"]))
    host.model_list_cache["openai"] = ["gpt-live-1", "gpt-live-2"]
    panel = AgentPanel(host, "author", default_provider="openai")
    panel.load_models()
    assert [panel.model_box.itemText(i)
            for i in range(panel.model_box.count())] ==         ["gpt-live-1", "gpt-live-2"]
    assert panel.model_box.property("imprintModelsLive") is True
    assert started == []


def test_missing_key_skips_the_fetch(app, monkeypatch):
    started = []
    from ui.workers import ModelListWorker
    monkeypatch.setattr(ModelListWorker, "start",
                        lambda self: started.append(self))
    client = FakeClient(["gpt-4o-mini"])
    client.key_available = lambda: False
    host = _async_host(openai=client)
    panel = AgentPanel(host, "author", default_provider="openai")
    panel.load_models()
    assert started == []
    assert panel.model_box.count() == 1   # the seed is the whole answer


def test_stale_result_for_another_provider_is_ignored(app, monkeypatch):
    from ui.workers import ModelListWorker
    monkeypatch.setattr(ModelListWorker, "start", lambda self: None)
    host = _async_host()
    panel = AgentPanel(host, "author", default_provider="openai")
    panel.load_models()
    before = [panel.model_box.itemText(i)
              for i in range(panel.model_box.count())]
    panel._apply_live("anthropic", ["claude-x"], "")
    assert [panel.model_box.itemText(i)
            for i in range(panel.model_box.count())] == before


def test_one_fetch_per_provider_per_session(app, monkeypatch):
    """The worker MAP records "fetched this session": the cache write
    arrives by queued signal, so keying on isRunning() let a second panel
    respawn the fetch in the finished-but-not-yet-cached window."""
    created = []
    from ui import workers

    class RecordingWorker(workers.ModelListWorker):
        def __init__(self, client, provider):
            super().__init__(client, provider)
            created.append(self)

        def start(self):   # never runs: simulates any pre-result moment
            pass

    monkeypatch.setattr(workers, "ModelListWorker", RecordingWorker)
    host = _async_host()
    first = AgentPanel(host, "author", default_provider="openai")
    second = AgentPanel(host, "music", default_provider="openai")
    first.load_models()
    second.load_models()   # cache still empty — must NOT respawn
    assert len(created) == 1


def test_failed_fetch_is_not_cached_and_rearms_the_retry(app, monkeypatch):
    """A network failure must stay distinguishable from a live answer:
    caching KNOWN_MODELS as live froze the box stale for the session."""
    _run_worker_synchronously(monkeypatch)

    class LiveAwareClient(FakeClient):
        def __init__(self):
            super().__init__(["known-a"], live=["live-a"])
            self.calls = 0

        def list_models_live(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("network down")
            return list(self._live)

    client = LiveAwareClient()
    host = _async_host(openai=client)
    panel = AgentPanel(host, "author", default_provider="openai")
    panel.load_models()
    # First fetch failed: nothing cached, box keeps the seed, not live.
    assert "openai" not in host.model_list_cache
    assert panel.model_box.property("imprintModelsLive") is False
    assert host.failures and host.failures[-1][0] == "models: openai"
    # The map was re-armed, so the next load retries and self-heals.
    panel.load_models()
    assert host.model_list_cache["openai"] == ["live-a"]
    assert panel.model_box.property("imprintModelsLive") is True


def test_revisiting_an_inflight_provider_does_not_double_connect(
        app, monkeypatch):
    """One live connection per panel: every duplicate re-runs the whole
    swap (reproduced as models_refreshed firing twice per emission)."""
    from ui.workers import ModelListWorker
    monkeypatch.setattr(ModelListWorker, "start", lambda self: None)
    host = _async_host()
    panel = AgentPanel(host, "author", default_provider="openai")
    panel.load_models()               # connect to W_openai (in flight)
    panel.provider_box.setCurrentText("anthropic")   # connect W_anthropic
    panel.provider_box.setCurrentText("openai")      # revisit mid-flight
    refreshed = []
    panel.models_refreshed.connect(refreshed.append)
    worker = host.model_list_workers["openai"]
    worker.models_signal.emit("openai", ["gpt-live"], "")
    assert refreshed == ["author"]    # exactly one swap per emission
