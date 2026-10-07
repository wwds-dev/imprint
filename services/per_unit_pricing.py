"""Prices for work that is not billed per token.

The budget guard is denominated in tokens. That is correct for chat and wrong
for everything else this app does: an image is priced per image, a video render
per image and per audio-minute, speech per thousand characters. None of those
can be expressed as an input/output token pair, so every one of them counted as
€0.00 against the session and daily caps regardless of what it actually cost.

This module is the other half of the cost model. Rates live in
`config/pricing.json` under `per_unit_usd`, so they are data the user can
correct rather than constants buried in a client.

**Zero means unknown, not free.** A provider whose rate has never been filled
in returns `None` from `rate()`, and the callers say "cost unknown" and warn
rather than billing nothing — the failure mode that let Gemini, image models and
Higgsfield all silently bill zero for months.
"""

from __future__ import annotations

import json

from services.runtime_paths import resource_base, user_data_base

# Frozen builds seed an editable copy of config/ into Application Support
# (ensure_seeded); reading only the bundled file meant a user's corrections
# there were silently ignored. Prefer the editable copy; in development both
# paths are the project root, so this is the same file.
USER_CONFIG_PATH = user_data_base() / "config" / "pricing.json"
CONFIG_PATH = resource_base() / "config" / "pricing.json"

DEFAULT_EUR_PER_USD = 0.92


def _tables() -> list[dict]:
    """The editable copy first, then the bundled file.

    A frozen build seeds the editable copy once and never updates it, so a
    rate added in a later release (a new image or speech route) exists only
    in the bundled file. Reading the editable copy alone made every such
    rate "unknown" and the route refused. Edits made in Settings live in
    SQLite and win over both (rate_usd).
    """
    tables = []
    seen = set()
    for path in (USER_CONFIG_PATH, CONFIG_PATH):
        if path in seen:
            continue
        seen.add(path)
        try:
            with path.open("r", encoding="utf-8") as fh:
                tables.append(json.load(fh))
        except Exception:
            continue
    return tables


def _table() -> dict:
    tables = _tables()
    return tables[0] if tables else {}


def eur_per_usd() -> float:
    try:
        from services.database import get_setting
        override = get_setting("eur_per_usd", "").strip()
        if override:
            value = float(override)
            if value > 0:
                return value
    except Exception:
        pass
    try:
        return float(_table().get("eur_per_usd") or DEFAULT_EUR_PER_USD)
    except (TypeError, ValueError):
        return DEFAULT_EUR_PER_USD


def rate_usd(*path: str) -> float | None:
    """Look up a per-unit rate. `None` means the rate is unknown.

    A rate of exactly 0 in the file is treated as unknown rather than free —
    an unfilled placeholder and a genuinely free service look identical in
    JSON, and of the two, silently billing nothing is the expensive mistake.
    """
    # Settings stores user overrides in SQLite so they survive app upgrades
    # without modifying the read-only application bundle.
    try:
        from services.database import get_setting
        override = get_setting("pricing.per_unit." + ".".join(path), "").strip()
    except Exception:
        override = ""
    if override:
        try:
            value = float(override)
        except (TypeError, ValueError):
            value = 0.0
        return value if value > 0 else None

    for table in _tables():
        node = table.get("per_unit_usd") or {}
        found = True
        for part in path:
            if not isinstance(node, dict) or part not in node:
                found = False
                break
            node = node[part]
        if not found:
            continue        # this copy predates the key; try the next
        try:
            value = float(node)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None
    return None


def to_eur(usd: float | None) -> float | None:
    return None if usd is None else round(usd * eur_per_usd(), 6)


def image_cost_eur(model: str, count: int = 1) -> float | None:
    """What `count` images from `model` will cost, or None if unpriced —
    for any provider's image model (OpenAI, Gemini, Qwen)."""
    from services.media_catalog import image_reserve_usd
    try:
        usd = image_reserve_usd(model)
    except ValueError:
        return None
    return to_eur(usd * max(0, int(count)))


def tts_cost_eur(characters: int) -> float | None:
    usd = rate_usd("openai_tts_per_1k_chars")
    return None if usd is None else to_eur(usd * max(0, characters) / 1000.0)


ELEVENLABS_SHORTS_MODEL = "eleven_flash_v2_5"


def elevenlabs_rate_usd(model: str = ELEVENLABS_SHORTS_MODEL) -> float | None:
    """USD per 1k characters for one ElevenLabs model, or None if unknown.

    Per model, because they differ twofold (flash $0.04, multilingual_v2
    and v3 $0.08 — elevenlabs.io/pricing/api, checked 2026-10-07). The old
    single `elevenlabs_tts_per_1k_chars` key is still read for the Shorts
    model, so a rate entered there before per-model rates existed counts.
    """
    rate = rate_usd("elevenlabs_tts", model)
    if rate is None and model == ELEVENLABS_SHORTS_MODEL:
        rate = rate_usd("elevenlabs_tts_per_1k_chars")
    return rate


def elevenlabs_tts_cost_eur(characters: int,
                            model: str = ELEVENLABS_SHORTS_MODEL) -> float | None:
    """ElevenLabs narration. None when the model has no rate — the caller
    must refuse rather than bill €0.00."""
    usd = elevenlabs_rate_usd(model)
    return None if usd is None else to_eur(usd * max(0, characters) / 1000.0)


def dated_rate_usd(table: str, model: str, today: str | None = None) -> float | None:
    """A per-unit rate that changes on announced dates.

    `table.model` is the rate now; `table.model@YYYY-MM-DD` is the rate from
    that date. The latest dated key on or before today wins — so a price rise
    Google has announced applies itself on the day, without a release.
    """
    from datetime import date
    today = today or date.today().isoformat()
    rate = rate_usd(table, model)
    best = ""
    for source in _tables():
        node = (source.get("per_unit_usd") or {}).get(table) or {}
        if not isinstance(node, dict):
            continue
        for key in node:
            if key.startswith(model + "@"):
                effective = key.split("@", 1)[1]
                if best < effective <= today:
                    candidate = rate_usd(table, key)
                    if candidate is not None:
                        best, rate = effective, candidate
    return rate


def gemini_tts_cost_eur(minutes: float,
                        model: str = "gemini-3.8-flash-tts") -> float | None:
    usd = dated_rate_usd("gemini_tts_per_minute", model)
    return None if usd is None else to_eur(usd * max(0.0, minutes))


def whisper_cost_eur(minutes: float) -> float | None:
    usd = rate_usd("openai_whisper_per_minute")
    return None if usd is None else to_eur(usd * max(0.0, minutes))


def render_cost_eur(provider: str = "higgsfield_render") -> float | None:
    return to_eur(rate_usd(provider))


def describe(cost_eur: float | None, unit: str) -> str:
    """One phrase for a cost that may not be known.

    Used verbatim next to the buttons that spend, so that an unpriced action
    says so instead of showing a confident €0.00.
    """
    if cost_eur is None:
        return f"{unit} · cost not priced yet"
    return f"{unit} · ≈ €{cost_eur:.2f}"
