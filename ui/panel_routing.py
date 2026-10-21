"""The routing advisor for Imprint's text agents beyond Chat.

Chat holds a job on its own banner (main.py `_advise_job`); Quill (author),
Herald (social), Sitebuilder (webdesign) and Stamp (fiverr) hold theirs here,
on a banner at the top of the agent's panel. Both ask the same question of
services/routing_advisor.py and keep the answers in the same place, per agent
and kind of work, in data/routing_rules.json.

The seam is `GodAI.authorize_request`, which every paid request already passes.
A panel that passes `resume=` (the method that restarts its action) is advised;
one that does not is left exactly as it was. The panel reads its provider and
model from its boxes when the action starts, so an answer is applied by putting
the chosen model in the boxes and running the action again, never by swapping
the model inside the guard.

Left out on purpose:
  * Muse (creator) and Press (manuscript) offer no local provider, on
    purpose, so there is nothing local to prefer and no panel call passes
    `resume=`. creator is named in `NEVER_ADVISED`, and `eligible()` also asks
    for a local provider in the agent's box, so a later change to either panel
    cannot start advising it by accident.
  * Booth (audiobook, music), video and the image flows are media: billed per
    unit (`flat_cost_eur`), never advised.
Nothing here ever sends: a paid answer still meets the paid-request dialog and
the budget caps when the action runs again.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer

from services import routing_advisor as ra
from services.providers import is_local as is_local_provider
from ui.routing_advice import AdviceBanner

ADVISED_AGENTS = ("author", "social", "webdesign", "fiverr")
NEVER_ADVISED = ("creator",)


class PanelRouting:
    def __init__(self, host) -> None:
        self.host = host
        self.held: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.failed: dict[str, dict] = {}
        self.cleared: set[str] = set()       # agents whose next request is already advised

    # ── Which agents ────────────────────────────────────────────────────────
    def panel(self, agent: str):
        return getattr(self.host, f"{agent}_panel", None)

    def boxes(self, agent: str):
        from main import AGENT_SETUP_WIDGETS
        names = AGENT_SETUP_WIDGETS.get(agent)
        if not names:
            return None, None
        return self.host._find_control(names[0]), self.host._find_control(names[1])

    def eligible(self, agent: str) -> bool:
        """An advised agent whose panel can use a local provider at all."""
        if agent in NEVER_ADVISED or agent not in ADVISED_AGENTS:
            return False
        provider_box, _ = self.boxes(agent)
        if provider_box is None or self.panel(agent) is None:
            return False
        return any(is_local_provider(provider_box.itemText(i))
                   for i in range(provider_box.count()))

    # ── Banner ──────────────────────────────────────────────────────────────
    def banner(self, agent: str) -> AdviceBanner | None:
        panel = self.panel(agent)
        if panel is None:
            return None
        banner = getattr(panel, "_advice_banner", None)
        if banner is None:
            banner = AdviceBanner(panel)
            layout = panel.layout()
            if layout is not None:
                layout.insertWidget(0, banner)
            banner.switch_requested.connect(lambda: self.switch(agent))
            banner.always_requested.connect(lambda: self.always(agent))
            banner.keep_requested.connect(lambda: self.keep(agent))
            banner.dismissed.connect(lambda: self.dismiss(agent))
            panel._advice_banner = banner
        return banner

    # ── Before the job ──────────────────────────────────────────────────────
    def advise(self, agent, provider, model, prompt, *, tool="", resume=None) -> bool:
        """True: carry on as selected. False: the job is held on the banner,
        refused there, or restarted on a remembered rule's model."""
        if resume is None or not self.eligible(agent):
            return True
        if agent in self.cleared:
            self.cleared.discard(agent)
            return True
        self.held.pop(agent, None)
        self.failed.pop(agent, None)
        self.jobs.pop(agent, None)
        banner = self.banner(agent)
        banner.clear()
        host = self.host
        try:
            context = host._advisor_context(agent, tool, prompt, prompt,
                                            provider.casefold(), model)
        except Exception as exc:  # noqa: BLE001 - advice must never block a run
            host._note_failure("routing advisor", exc)
            return True
        if context is None:
            return True
        advice = context.advice
        if advice.action == ra.RUN:
            target = advice.run
            if target is None or target.same(context.selected):
                self._start(agent, context, context.selected, resume=resume)
                return True
            # A remembered rule (or Local first) chose another model: put it in
            # the boxes and run the action again, so the guard sees that route.
            self.held[agent] = {"context": context, "resume": resume}
            self._point(agent, target)
            self._status(agent, advice.message)
            QTimer.singleShot(0, lambda: self._resume(
                agent, target, accepted=advice.rule is not None))
            return False
        self.held[agent] = {"context": context, "resume": resume}
        banner.show_advice(advice, context.job, context.selected)
        if advice.action == ra.REFUSE:
            self.held.pop(agent, None)
        return False

    def _start(self, agent, context, target, *, accepted=False, resume=None) -> None:
        self.jobs[agent] = {"context": context, "provider": target.provider,
                            "model": target.model, "resume": resume,
                            "accepted": bool(accepted) and not target.local}

    def _status(self, agent, text: str) -> None:
        label = next((getattr(self.panel(agent), name, None) for name in
                      (f"{agent}_status_label", "status_label")
                      if getattr(self.panel(agent), name, None) is not None), None)
        if text and label is not None:
            label.setText(text)

    def _point(self, agent, target) -> None:
        """Put `target` in the agent's provider and model boxes."""
        provider_box, model_box = self.boxes(agent)
        if provider_box is None or model_box is None:
            return
        for box in (provider_box, model_box):
            box.blockSignals(True)
        try:
            index = next((i for i in range(provider_box.count())
                          if provider_box.itemText(i).casefold() == target.provider.casefold()), -1)
            changed = index >= 0 and provider_box.currentIndex() != index
            if index >= 0:
                provider_box.setCurrentIndex(index)
            listed = (list(self.host._best_known_models(target.provider)) if changed
                      else [model_box.itemText(i) for i in range(model_box.count())])
            if target.model not in listed:
                listed.insert(0, target.model)
            model_box.clear()
            model_box.addItems(listed)
            model_box.setCurrentText(target.model)
        finally:
            for box in (provider_box, model_box):
                box.blockSignals(False)

    # ── The user's answer ───────────────────────────────────────────────────
    def _resume(self, agent, target=None, *, accepted=False) -> None:
        held = self.held.pop(agent, None)
        if held is None:
            return
        context = held["context"]
        target = target or context.selected
        if not target.same(context.selected):
            self._point(agent, target)
        resume = held["resume"]
        self._start(agent, context, target, accepted=accepted, resume=resume)
        self.cleared.add(agent)             # authorize_request must not ask twice
        try:
            resume()
        finally:
            self.cleared.discard(agent)

    def switch(self, agent) -> None:
        offer = self.banner(agent).offer
        if offer is not None:
            self._redo(agent, offer.cloud)
            return
        held = self.held.get(agent)
        if held is None or held["context"].advice.suggestion is None:
            return
        target = held["context"].advice.suggestion
        self._resume(agent, target, accepted=not target.local)

    def always(self, agent) -> None:
        held = self.held.get(agent)
        if held is None or held["context"].advice.suggestion is None:
            return
        context, target = held["context"], held["context"].advice.suggestion
        try:
            self.host.routing_rules.add(context.job.agent, context.job.kind, target.provider,
                                        target.model, context.job.label)
        except OSError as exc:
            self.host._note_failure("routing rules: save", exc)
        self._resume(agent, target, accepted=not target.local)

    def keep(self, agent) -> None:
        offer = self.banner(agent).offer
        if offer is not None:
            self._redo(agent, offer.local)
            return
        self._resume(agent)

    def dismiss(self, agent) -> None:
        self.held.pop(agent, None)
        self.failed.pop(agent, None)

    # ── After the job ───────────────────────────────────────────────────────
    def offer_failover(self, agent, error) -> None:
        """A run failed: offer the engine's next candidate. Never sends."""
        job = self.jobs.pop(agent, None)
        self.failed.pop(agent, None)
        if job is None or self.banner(agent) is None:
            return
        context = job["context"]
        failed = next((c for c in context.fallbacks + [context.selected]
                       if c.key == (job["provider"], job["model"])), None)
        if failed is None:
            return
        offer = ra.failover(failed, context.fallbacks, mode=context.mode,
                            error=str(error or "The request failed.")[:160],
                            job=context.job,
                            budget_left_eur=self.host._remaining_budget_eur(agent))
        if offer.empty:
            return
        self.failed[agent] = {"job": job}
        self.banner(agent).show_failover(offer)

    def _redo(self, agent, target) -> None:
        failed = self.failed.pop(agent, None)
        self.banner(agent).clear()
        if failed is None or target is None or failed["job"].get("resume") is None:
            return
        job = failed["job"]
        self.held[agent] = {"context": job["context"], "resume": job["resume"]}
        self._resume(agent, target, accepted=not target.local)

    def finished(self, agent, cost_eur) -> None:
        """Count what a finished job saved (local) or spent (accepted)."""
        job = self.jobs.pop(agent, None)
        if job is None:
            return
        context, host = job["context"], self.host
        try:
            if is_local_provider(job["provider"]):
                host.savings_tally.record_local_run(context.saved_eur)
            elif job.get("accepted"):
                host.savings_tally.record_accepted(cost_eur)
        except OSError as exc:
            host._note_failure("routing savings: save", exc)
