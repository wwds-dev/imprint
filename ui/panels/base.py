"""What every agent panel repeats: a provider box, a model box, and the code
that fills the second from the first.

Five panels carried their own `*_load_models` — webdesign, fiverr and author
byte-identical, manuscript and music differing in ways that turned out to
matter (see `ALL_PROVIDERS` and `load_models` below). This is the composition
half of phase 3: `GodAI` owns one `AgentPanel` per agent and delegates to it,
rather than a mixin reaching back into the window.

Phase 4 turns each panel into its own module built on this class. Nothing here
constructs a layout for that reason — a panel's arrangement is its own; only the
provider/model pair and its wiring are shared.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QComboBox

from ui.host import AgentHost

# Every provider the app can talk to, in the order the panels list them.
ALL_PROVIDERS = ("ollama", "openai", "deepseek", "kimi", "gemini", "anthropic", "qwen")


class AgentPanel(QObject):
    """The provider/model pair for one agent.

    `providers` is the subset that agent may use. It is not cosmetic: the
    manuscript panel deliberately omits `ollama` and `qwen`, matching the
    allowed_providers on its registry row, and a panel that offered them would
    let the user pick a provider the validator then refuses.

    A QObject since the async-refresh change so the live model list can be
    delivered by queued signal from the worker thread.
    """

    # Emitted (agent key) after the live list replaces the seeded one, so
    # the host can repaint recommendation marks the replacement cleared.
    models_refreshed = Signal(str)

    def __init__(self, host: AgentHost, agent: str,
                 providers: tuple[str, ...] = ALL_PROVIDERS,
                 default_provider: str | None = None):
        super().__init__()
        self.host = host
        self.agent = agent
        self.providers = tuple(providers)
        self._live_worker = None

        self.provider_box = QComboBox()
        self.provider_box.addItems(self.providers)
        if default_provider and default_provider in self.providers:
            self.provider_box.setCurrentText(default_provider)

        self.model_box = QComboBox()

        # Reloading on change is why every panel had this method at all.
        self.provider_box.currentTextChanged.connect(self.load_models)

    # ── the part that was copied five times ─────────────────────────────
    def load_models(self) -> None:
        """Seed the model box instantly; refresh it off the GUI thread.

        The old version called client.list_models() synchronously — up to
        two REQUEST_TIMEOUT_SECONDS windows per configured provider, on
        startup and every provider switch, on the GUI thread. Now the box
        fills immediately from the host's session cache of an earlier live
        answer, or from the client's static KNOWN_MODELS, and one shared
        worker per provider fetches the live list once per session.
        `imprintModelsLive` stays False until a live answer holds the box.
        Worker failures reach the host through `_on_models_listed`, not a
        silent except — the music-panel lesson still applies.
        """
        provider = self.provider_box.currentText()
        keep = self.model_box.currentText()
        self.model_box.clear()
        client = getattr(self.host, provider, None)
        cache = getattr(self.host, "model_list_cache", None)
        cached = cache.get(provider) if cache is not None else None
        if cached:
            models, live = list(cached), True
        else:
            models = list(getattr(client, "KNOWN_MODELS", None) or [])
            live = False
        self.model_box.setProperty("imprintModelsLive", live)
        for model in models:
            self.model_box.addItem(model)
        self._restore_selection(keep)
        if client is not None and not live:
            self._request_refresh(provider, client)

    def _restore_selection(self, wanted: str) -> None:
        """Reselect `wanted`, tolerating dated live ids vs bare seeded names."""
        if not wanted:
            return
        finder = getattr(self.host, "_find_model_index", None)
        index = (finder(self.model_box, wanted) if finder is not None
                 else self.model_box.findText(wanted))
        if index >= 0:
            self.model_box.setCurrentIndex(index)

    def _request_refresh(self, provider: str, client) -> None:
        """Share one live fetch per provider across every panel."""
        workers = getattr(self.host, "model_list_workers", None)
        if workers is None:
            # The host has not opted into async refresh (unit-test hosts):
            # the seeded list is the whole answer.
            return
        key_check = getattr(client, "key_available", None)
        if key_check is not None and not key_check():
            # Without a key, list_models returns KNOWN_MODELS verbatim —
            # there is nothing to fetch.
            return
        worker = workers.get(provider)
        # The worker MAP records "fetched this session", not the thread's
        # liveness: the cache write arrives by queued signal, so keying on
        # isRunning() let a second panel respawn the fetch in the window
        # between a worker finishing and its result landing. A failed fetch
        # is popped from the map by the host, which is what re-enables the
        # retry on the next load_models.
        fresh = worker is None
        if fresh:
            from ui.workers import ModelListWorker
            worker = ModelListWorker(client, provider)
            host_hook = getattr(self.host, "_on_models_listed", None)
            if host_hook is not None:
                worker.models_signal.connect(host_hook)
            workers[provider] = worker
        # One live connection per panel: revisiting a provider whose fetch
        # is still in flight must not double-connect (Qt connections are
        # not unique, and each duplicate re-runs the whole swap). Subscribe
        # BEFORE start(): a worker can emit in the first microseconds, and
        # a signal with no connection yet is simply lost.
        if self._live_worker is not worker:
            if self._live_worker is not None:
                try:
                    self._live_worker.models_signal.disconnect(
                        self._apply_live)
                except (RuntimeError, TypeError):
                    pass   # already gone with its thread
            worker.models_signal.connect(self._apply_live)
            self._live_worker = worker
        if fresh:
            worker.start()

    def _apply_live(self, provider: str, models: list, error: str) -> None:
        """Swap the live list in, preserving the user's selection."""
        if provider != self.provider_box.currentText():
            return   # stale: the user switched provider before this landed
        if not models:
            # The host already noted the failure; the seeded list stays.
            self.model_box.setProperty("imprintModelsLive", False)
            return
        keep = self.model_box.currentText()
        self.model_box.clear()
        self.model_box.setProperty("imprintModelsLive", True)
        for model in models:
            self.model_box.addItem(model)
        self._restore_selection(keep)
        if self.model_box.currentIndex() < 0 and self.model_box.count():
            self.model_box.setCurrentIndex(0)
        self.models_refreshed.emit(self.agent)

    # ── convenience for the call sites that read the pair ───────────────
    @property
    def provider(self) -> str:
        return self.provider_box.currentText()

    @property
    def model(self) -> str:
        return self.model_box.currentText()
