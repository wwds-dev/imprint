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
* **Chat models only, in the chat lane.** Embeddings, speech, image and
  video ids are not options for a text dropdown, so a new one is not
  announced there. Image and video ids have their own lane (`observe_media`,
  `pending_media`), which never reaches a chat menu.
* **A dated snapshot of a known model is not a new model.** OpenAI and
  Anthropic list both `name` and `name-2026-08-01`; the second is recorded
  as seen without a notice when the first is already known.
* **A removal takes two absences on two days.** Only a model Imprint offers
  (media) or one an agent has selected (chat) is watched for removal, and
  only by the Model updates scan: absent from two live lists on two
  different UTC days after being listed. An empty or failed list is not an
  absence. Seen again, the notice drops on its own.

The state file stays `VERSION = 1` and grows only by new keys
(docs/adr/0001-model-watch-state-additive-v1.md): read every key added after
1 with `.get`/`setdefault`.

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

from services import media_catalog

# Cloud providers with a model-list endpoint. Ollama is left out on purpose:
# its list is what *you* pulled onto this Mac, not what the vendor released.
WATCHED_PROVIDERS = ("openai", "anthropic", "deepseek", "kimi", "gemini", "qwen")
# Of those, the ones whose clients also list image and video models
# (`list_media_models_live`). Higgsfield has no list; its paths are probed.
MEDIA_WATCHED_PROVIDERS = ("gemini", "qwen")

# Substrings that mark an id as something other than a chat/completions
# model. Checked against the lower-cased id.
NON_CHAT_MARKERS = (
    "embed", "tts", "whisper", "transcribe", "audio", "realtime", "speech",
    "asr", "image", "dall-e", "imagen", "moderation", "rerank", "video",
    "veo", "sora", "wanx", "wan2", "wan3", "search", "aqa",
)

# Substrings that mark an id as an image or video model, for the media lane.
# Imprint's own media ids count too (is_media_model), because two of them
# ("gemini-nano-banana-2.1", "gemini-omni-1.1-flash") match no marker.
MEDIA_MARKERS = ("veo", "imagen", "image", "wan", "nano-banana")

# What a media listing raises when the endpoint is not there for this account
# or host (a 404/405, or a body of the wrong shape). The scan drops it
# silently: it is not a failure to report, and not an absence to count.
MEDIA_LIST_UNSUPPORTED = "unsupported"


class MediaListUnsupported(RuntimeError):
    """The provider does not serve a media model list here."""


# A trailing release marker: a date (-2026-08-01, -20251001), a four-digit
# month-day (-0806) or Gemini's three-digit version (-001).
_DATE_SUFFIX = re.compile(r"[-_@](?:20\d{2}-?\d{2}-?\d{2}|\d{4}|\d{3})$")


def is_media_model(model_id: str) -> bool:
    """True for an image or video model id, including every Imprint offers."""
    name = (model_id or "").casefold()
    if not name:
        return False
    return (any(marker in name for marker in MEDIA_MARKERS)
            or model_id.strip() in _catalog_ids())


def _catalog_ids() -> frozenset[str]:
    return frozenset(model.model_id for model in media_catalog.MODELS)


def is_chat_model(model_id: str) -> bool:
    """True when `model_id` belongs in a text model dropdown."""
    name = model_id.casefold()
    return (bool(name) and not any(marker in name for marker in NON_CHAT_MARKERS)
            and not is_media_model(model_id))


# What a model id may look like before it is stored or shown: provider ids
# are short and plain, and anything else (markup, control characters, a
# kilobyte of text) is dropped at the edge rather than painted in the tile.
_VALID_ID = re.compile(r"[A-Za-z0-9._:/@+-]{1,128}")
# Bounds on what one live list can add, so a broken or hostile answer cannot
# grow the state file (saved on the GUI thread) without limit.
MAX_LISTED_IDS = 2000
MAX_PENDING_MEDIA = 50


def valid_model_id(model_id) -> bool:
    return isinstance(model_id, str) and bool(_VALID_ID.fullmatch(model_id))


def valid_ids(model_ids: Iterable[str]) -> list[str]:
    """The valid ids in a live list, de-duplicated and sorted, uncapped.

    What presence is read from: a tracked id sorted past the cap is still
    listed, so it must not count as an absence."""
    ids = {m.strip() for m in model_ids if isinstance(m, str)}
    return sorted(m for m in ids if valid_model_id(m))


def clean_ids(model_ids: Iterable[str]) -> list[str]:
    """The valid ids in a live list, de-duplicated, sorted and capped: what
    is stored."""
    return valid_ids(model_ids)[:MAX_LISTED_IDS]


def canonical(model_id: str) -> str:
    """`model_id` without a trailing release marker (`-2026-08-01`, `-0806`, `-001`)."""
    return _DATE_SUFFIX.sub("", model_id.strip())


@dataclass(frozen=True)
class NewModel:
    provider: str
    model_id: str
    first_seen: str          # ISO-8601 UTC timestamp


@dataclass(frozen=True)
class Removal:
    kind: str                # "media" | "chat"
    provider: str
    model_id: str
    confirmed_at: str        # ISO-8601 UTC timestamp


@dataclass(frozen=True)
class ProbeResult:
    path: str                # a Higgsfield endpoint path
    status: str              # "answering" | "missing"
    at: str
    dismissed: bool = False


PROBE_STATUSES = ("answering", "missing")


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
                "providers": {}, "pending": [],
                "media": {}, "pending_media": [], "removals": [], "probes": {},
                "probe_day": None}

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
        # Added after version 1 shipped (ADR 0001): an older file gains them
        # here, and an older build keeps them, since _save writes the whole
        # dict back.
        state.setdefault("media", {})
        state.setdefault("pending_media", [])
        state.setdefault("removals", [])
        state.setdefault("probes", {})
        state.setdefault("probe_day", None)
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

    def observe(self, provider: str, model_ids: Iterable[str], *,
                tracked: Iterable[str] | None = None) -> list[NewModel]:
        """Record one live list; return the models it introduced.

        An empty list is ignored rather than recorded: a provider that
        answers with nothing has not withdrawn its whole catalogue.

        `tracked` is what to watch for removal: the chat models agents have
        selected on this provider. Only the Model updates scan passes it, so
        a panel's own fetch never counts an absence. Presence is read from
        the whole list, chat or not: a selected id that is no longer
        classed as chat (an upgrade can do that) is not "removed" while the
        provider still lists it.
        """
        present = valid_ids(model_ids)
        listed = [m for m in present if is_chat_model(m)][:MAX_LISTED_IDS]
        return self._observe_lane(
            self._state["providers"], self._state["pending"], "chat",
            provider, listed, present, tracked)

    def observe_media(self, provider: str, model_ids: Iterable[str], *,
                      tracked: Iterable[str] | None = None) -> list[NewModel]:
        """`observe` for the image and video lane: one live media list.

        The same rules, against its own baseline — a provider with a chat
        baseline still gets a silent first media look. Its notices go to
        `pending_media`, which nothing that marks a chat menu reads.
        `tracked` is the provider's offered media models.
        """
        present = valid_ids(model_ids)
        return self._observe_lane(
            self._state["media"], self._state["pending_media"], "media",
            provider, present[:MAX_LISTED_IDS], present, tracked)

    def _observe_lane(self, records: dict, pending_list: list, kind: str,
                      provider: str, listed: list[str], present: list[str],
                      tracked: Iterable[str] | None) -> list[NewModel]:
        key = provider.casefold()
        if not listed:
            return []
        stamp = self.clock()
        self._state["last_checked"] = stamp
        record = records.get(key)
        if record is None:
            records[key] = {
                "baseline_at": stamp, "seen": listed,
                "last_live": listed, "listed_at": stamp, "missing": {}}
            self._save()
            return []
        self._count_misses(record, present, tracked, stamp, kind, key)
        # What the provider offers *now*, separately from everything it has
        # ever offered: a retired model stays seen (so it is never announced
        # again) but leaves this list, which the ranking reads at startup.
        record["last_live"] = listed
        record["listed_at"] = stamp

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
        pending = {(p["provider"], p["model_id"]) for p in pending_list}
        pending_list.extend(
            {"provider": n.provider, "model_id": n.model_id,
             "first_seen": n.first_seen}
            for n in announced if (n.provider, n.model_id) not in pending)
        if kind == "media" and len(pending_list) > MAX_PENDING_MEDIA:
            del pending_list[:-MAX_PENDING_MEDIA]       # keep the newest
        self._save()
        return announced

    def _count_misses(self, record: dict, present: list[str],
                      tracked: Iterable[str] | None, stamp: str, kind: str,
                      provider: str) -> None:
        """Count one absence per tracked model and confirm a removal at two.

        Present means the id, or a listed id with the same `canonical()`, is
        in the list, so a model listed only as its dated snapshot is not
        missing. An absence counts only for a model that was listed before
        (in the previous live list, or already counted once), and at most
        once per UTC day: a startup check plus a Check now must not turn one
        regional blip into a confirmed removal within minutes.

        Any listed model is present whether tracked or not: its counter and
        its removal go, so a notice drops on its own and a model that was
        absent once while selected starts again from zero. With `tracked`
        None (not a scan) nothing else happens; a scan also forgets the
        counters of models it no longer tracks.
        """
        missing = record.setdefault("missing", {})
        present_set = set(present)
        present_bases = {canonical(m) for m in present}

        def is_present(model: str) -> bool:
            return model in present_set or canonical(model) in present_bases

        for model in [m for m in missing if is_present(m)]:
            del missing[model]
        for removal in self.removals(kind):
            if removal.provider == provider and is_present(removal.model_id):
                self._drop_removal(kind, provider, removal.model_id)
        if tracked is None:
            return
        tracked_set = {m for m in tracked if m}
        for model in [m for m in missing if m not in tracked_set]:
            del missing[model]
        before = set(record.get("last_live") or [])
        before_bases = {canonical(m) for m in before}
        day = stamp[:10]
        for model in sorted(tracked_set):
            if is_present(model):
                continue
            entry = missing.get(model)
            if entry is None:
                if model not in before and canonical(model) not in before_bases:
                    continue        # never listed: nothing to have removed
                entry = {"count": 0, "day": ""}
            if entry["day"] == day:
                continue            # this day's absence is already counted
            count = entry["count"] + 1
            missing[model] = {"count": min(2, count), "day": day}
            # Confirmed once, on the second absence: a removal the user has
            # dismissed is not raised again by the third.
            if count == 2 and not self._has_removal(kind, provider, model):
                self._state["removals"].append(
                    {"kind": kind, "provider": provider, "model_id": model,
                     "confirmed_at": stamp})

    def _has_removal(self, kind: str, provider: str, model: str) -> bool:
        return any((r["kind"], r["provider"], r["model_id"]) == (kind, provider, model)
                   for r in self._state["removals"])

    def _drop_removal(self, kind: str, provider: str, model: str) -> None:
        self._state["removals"] = [
            r for r in self._state["removals"]
            if (r["kind"], r["provider"], r["model_id"]) != (kind, provider, model)]

    def last_live(self, provider: str) -> list[str]:
        """The chat models the provider listed at the last live look.

        Lets the startup ranking consider a model found in an earlier session
        before this session's own check has answered. Empty when the provider
        has never been looked at with a key.
        """
        record = self._state["providers"].get(provider.casefold()) or {}
        return list(record.get("last_live") or [])

    def pending(self) -> list[NewModel]:
        """Announced and not yet dismissed, newest first."""
        return self._newest_first(self._state["pending"])

    def pending_media(self) -> list[NewModel]:
        """Image and video models announced and not yet dismissed, newest first."""
        return self._newest_first(self._state["pending_media"])

    @staticmethod
    def _newest_first(entries: list) -> list[NewModel]:
        items = [NewModel(p["provider"], p["model_id"], p["first_seen"])
                 for p in entries]
        return sorted(items, key=lambda n: (n.first_seen, n.provider, n.model_id),
                      reverse=True)

    def has_media_baseline(self, provider: str) -> bool:
        return provider.casefold() in self._state["media"]

    def removals(self, kind: str | None = None) -> list[Removal]:
        """Confirmed removals not yet dismissed: all, or one lane's."""
        return [Removal(r["kind"], r["provider"], r["model_id"], r["confirmed_at"])
                for r in self._state["removals"]
                if kind is None or r["kind"] == kind]

    def is_pending(self, provider: str, model_id: str) -> bool:
        key = provider.casefold()
        return any(p["provider"] == key and p["model_id"] == model_id
                   for p in self._state["pending"])

    def acknowledge(self, models: Iterable[tuple[str, str]] | None = None) -> None:
        """Clear notices: all of them, or only the `(provider, model_id)` pairs
        given. The models stay seen either way, so they are not re-announced.
        Clearing all also clears the chat removals (a selected model a
        provider stopped listing); clearing pairs touches only new models."""
        changed = False
        if models is None:
            keep = []
            removals = [r for r in self._state["removals"] if r["kind"] != "chat"]
            if len(removals) != len(self._state["removals"]):
                self._state["removals"] = removals
                changed = True
        else:
            drop = {(provider.casefold(), model) for provider, model in models}
            keep = [p for p in self._state["pending"]
                    if (p["provider"], p["model_id"]) not in drop]
        if len(keep) != len(self._state["pending"]):
            self._state["pending"] = keep
            changed = True
        if changed:
            self._save()

    def acknowledge_media(self,
                          models: Iterable[tuple[str, str]] | None = None) -> None:
        """Clear the image and video notices: new models and removals (all,
        or the `(provider, model_id)` pairs given). Clearing all also hides
        the current "not answering" probe rows until a probe's answer
        changes. Shutdown dates are catalog facts and are not stored here,
        so nothing can dismiss them."""
        if models is None:
            self._state["pending_media"] = []
            self._state["removals"] = [
                r for r in self._state["removals"] if r["kind"] != "media"]
            for entry in self._state["probes"].values():
                entry["dismissed"] = True
        else:
            drop = {(provider.casefold(), model) for provider, model in models}
            self._state["pending_media"] = [
                p for p in self._state["pending_media"]
                if (p["provider"], p["model_id"]) not in drop]
            self._state["removals"] = [
                r for r in self._state["removals"]
                if r["kind"] != "media" or (r["provider"], r["model_id"]) not in drop]
        self._save()

    # ── Higgsfield path probes ──────────────────────────────────────────
    def observe_probe(self, path: str, status: str) -> None:
        """Record one probe answer for a Higgsfield path.

        Only "answering" and "missing" are stored: an unreachable host says
        nothing about the path, so it never becomes a row (or "gone"). A
        dismissed row stays hidden while the answer is the same, and shows
        again when it changes.
        """
        if status not in PROBE_STATUSES:
            return
        entry = self._state["probes"].get(path)
        dismissed = bool(entry and entry.get("status") == status
                         and entry.get("dismissed"))
        self._state["probes"][path] = {
            "status": status, "at": self.clock(), "dismissed": dismissed}
        self._save()

    def probed_today(self) -> bool:
        """True once the Seedance paths were probed this UTC day: the probe
        is a POST to an endpoint Higgsfield does not document, so it runs at
        most once a day however often Model updates is checked."""
        return self._state.get("probe_day") == self.clock()[:10]

    def mark_probed(self, paths: Iterable[str]) -> None:
        """Record today's probe run, before it starts, and forget stored
        answers for paths no longer probed (a model Imprint stopped
        offering must not keep a "not answering" row)."""
        keep = set(paths)
        self._state["probe_day"] = self.clock()[:10]
        self._state["probes"] = {path: entry for path, entry
                                 in self._state["probes"].items() if path in keep}
        self._save()

    def clear_probes(self) -> None:
        """Forget every stored probe answer: called when a scan may not
        probe (the check is off, not permitted, refused or has no key), so
        a "not answering" row cannot outlive the check that found it."""
        if self._state["probes"]:
            self._state["probes"] = {}
            self._save()

    def probe_rows(self) -> list[ProbeResult]:
        """Paths whose last probe found nothing there, not dismissed."""
        return [ProbeResult(path, entry["status"], entry.get("at", ""),
                            bool(entry.get("dismissed")))
                for path, entry in sorted(self._state["probes"].items())
                if entry.get("status") == "missing" and not entry.get("dismissed")]

    def mark_checked(self) -> None:
        self._state["last_checked"] = self.clock()
        self._save()

    @property
    def last_checked(self) -> str | None:
        return self._state.get("last_checked")
