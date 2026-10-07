"""Notice when a provider ships a model Imprint has not seen before.

Every cloud client already answers `list_models_live()` from the provider's
own `/models` endpoint — the same free, unbilled call the model dropdowns use.
This module remembers which ids each provider has listed before and reports
the ones it has not: the rail's **Model updates** tile shows them, the model
dropdowns mark them NEW, and the recommendation engine ranks them alongside
everything else.

Rules that keep the signal honest:

* **A first look is a baseline, not news.** The first live list from a
  provider is recorded silently; otherwise the first launch would announce
  every model the provider has ever shipped.
* **Only live answers count.** A client without a key answers with its
  offline `KNOWN_MODELS`; the caller must not pass that here (it would
  baseline a list the provider never sent).
* **Chat models only.** Embeddings, speech, image and video ids are not
  options for a text dropdown, so a new one is not announced.
* **A dated snapshot of a known model is not a new model.** OpenAI and
  Anthropic list both `name` and `name-2026-08-01`; the second is recorded
  as seen without a notice when the first is already known.

Qt-free, so the rules are tested without a window.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

# Cloud providers with a model-list endpoint. Ollama is left out on purpose:
# its list is what *you* pulled onto this Mac, not what the vendor released.
WATCHED_PROVIDERS = ("openai", "anthropic", "deepseek", "kimi", "gemini", "qwen")

# Substrings that mark an id as something other than a chat/completions
# model. Checked against the lower-cased id.
NON_CHAT_MARKERS = (
    "embed", "tts", "whisper", "transcribe", "audio", "realtime", "speech",
    "asr", "image", "dall-e", "imagen", "moderation", "rerank", "video",
    "veo", "sora", "wanx", "wan2", "wan3", "search", "aqa",
)

_DATE_SUFFIX = re.compile(r"[-_@](?:20\d{2}-?\d{2}-?\d{2}|\d{4})$")


def is_chat_model(model_id: str) -> bool:
    """True when `model_id` belongs in a text model dropdown."""
    name = model_id.casefold()
    return bool(name) and not any(marker in name for marker in NON_CHAT_MARKERS)


def canonical(model_id: str) -> str:
    """`model_id` without a trailing release date (`-2026-08-01`, `-0806`)."""
    return _DATE_SUFFIX.sub("", model_id.strip())


@dataclass(frozen=True)
class NewModel:
    provider: str
    model_id: str
    first_seen: str          # ISO-8601 UTC timestamp


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ModelWatch:
    """The seen-before memory, persisted as one small JSON file."""

    VERSION = 1

    def __init__(self, path: Path, clock: Callable[[], str] = _now):
        self.path = Path(path)
        self.clock = clock
        self._state = self._load()

    # ── persistence ─────────────────────────────────────────────────────
    def _empty(self) -> dict:
        return {"version": self.VERSION, "last_checked": None,
                "providers": {}, "pending": []}

    def _load(self) -> dict:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._empty()
        if not isinstance(state, dict) or state.get("version") != self.VERSION:
            return self._empty()
        state.setdefault("providers", {})
        state.setdefault("pending", [])
        state.setdefault("last_checked", None)
        return state

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename: a crash mid-write must not leave half a file,
        # which would read as "no baseline" and stay silent about news.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._state, handle, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ── the rules ───────────────────────────────────────────────────────
    def has_baseline(self, provider: str) -> bool:
        return provider.casefold() in self._state["providers"]

    def observe(self, provider: str, model_ids: Iterable[str]) -> list[NewModel]:
        """Record one live list; return the models it introduced.

        An empty list is ignored rather than recorded: a provider that
        answers with nothing has not withdrawn its whole catalogue.
        """
        key = provider.casefold()
        listed = sorted({m for m in model_ids if m and is_chat_model(m)})
        if not listed:
            return []
        stamp = self.clock()
        self._state["last_checked"] = stamp
        record = self._state["providers"].get(key)
        if record is None:
            self._state["providers"][key] = {
                "baseline_at": stamp, "seen": listed}
            self._save()
            return []

        seen = set(record["seen"])
        seen_bases = {canonical(m) for m in seen}
        fresh = [m for m in listed if m not in seen]
        announced: list[NewModel] = []
        fresh_bases: set[str] = set()
        for model in fresh:
            base = canonical(model)
            if base in seen_bases or base in fresh_bases:
                continue    # a dated snapshot of something already known
            fresh_bases.add(base)
            announced.append(NewModel(key, model, stamp))
        record["seen"] = sorted(seen | set(fresh))
        pending = {(p["provider"], p["model_id"]) for p in self._state["pending"]}
        self._state["pending"].extend(
            {"provider": n.provider, "model_id": n.model_id,
             "first_seen": n.first_seen}
            for n in announced if (n.provider, n.model_id) not in pending)
        self._save()
        return announced

    def pending(self) -> list[NewModel]:
        """Announced and not yet dismissed, newest first."""
        items = [NewModel(p["provider"], p["model_id"], p["first_seen"])
                 for p in self._state["pending"]]
        return sorted(items, key=lambda n: (n.first_seen, n.provider, n.model_id),
                      reverse=True)

    def is_pending(self, provider: str, model_id: str) -> bool:
        key = provider.casefold()
        return any(p["provider"] == key and p["model_id"] == model_id
                   for p in self._state["pending"])

    def acknowledge(self, models: Iterable[tuple[str, str]] | None = None) -> None:
        """Clear notices: all of them, or only the `(provider, model_id)` pairs
        given. The models stay seen either way, so they are not re-announced."""
        if models is None:
            keep = []
        else:
            drop = {(provider.casefold(), model) for provider, model in models}
            keep = [p for p in self._state["pending"]
                    if (p["provider"], p["model_id"]) not in drop]
        if len(keep) != len(self._state["pending"]):
            self._state["pending"] = keep
            self._save()

    def mark_checked(self) -> None:
        self._state["last_checked"] = self.clock()
        self._save()

    @property
    def last_checked(self) -> str | None:
        return self._state.get("last_checked")
