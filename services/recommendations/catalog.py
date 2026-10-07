"""Turn Imprint's selectable model ids into comparable candidates.

This catalog describes stable product characteristics (fast/small/pro/local),
not marketing claims or a frozen universal leaderboard. Unknown live model ids
receive conservative provider-family defaults and are still rankable.

Release order is deliberately *not* a signal. A newer model is not
automatically the better choice for a given task — it is often dearer, and
"newer" says nothing about fit — so a model released yesterday is ranked on
the same evidence as every other: task fit, the agent's weights and, where the
pricing table has them, its real per-token rates.
"""

from __future__ import annotations

import math

import os
from datetime import date

from services.model_watch import is_chat_model

from .models import Candidate


# Each provider's key, as alternatives: any one entry counts, and an entry
# that is a tuple needs every variable in it. Gemini's client accepts either
# GOOGLE_API_KEY (what .env.example ships) or GEMINI_API_KEY; reading only
# the second ranked a configured Gemini as "setup needed". Higgsfield retired
# its single bearer token for an id + secret pair.
_KEY_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "kimi": ("KIMI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "qwen": ("DASHSCOPE_API_KEY",),
    "higgsfield": (("HF_API_KEY_ID", "HF_API_KEY_SECRET"),),
    "pexels": ("PEXELS_API_KEY",),
    "elevenlabs": ("ELEVENLABS_API_KEY",),
}


_PROVIDER_DEFAULTS = {
    "openai":       (0.84, 0.86, 0.55, 0.72, 0.78),
    "anthropic":    (0.88, 0.87, 0.48, 0.67, 0.90),
    "deepseek":     (0.82, 0.76, 0.88, 0.72, 0.78),
    "kimi":         (0.82, 0.76, 0.61, 0.76, 0.88),
    "gemini":       (0.82, 0.80, 0.78, 0.82, 0.86),
    "qwen":         (0.82, 0.76, 0.67, 0.72, 0.94),
    "ollama":       (0.66, 0.70, 1.00, 0.48, 0.62),
}

_PROVIDER_TASKS = {
    "openai": {"general": .86, "code": .92, "analysis": .87,
               "marketing": .88, "social": .90, "structured": .88},
    "anthropic": {"general": .90, "creative": .96, "longform": .96,
                  "editing": .94, "analysis": .91, "code": .89,
                  "planning": .92, "marketing": .90, "social": .87},
    "deepseek": {"general": .79, "analysis": .94, "code": .95,
                 "structured": .88, "planning": .82},
    "kimi": {"general": .83, "analysis": .88, "code": .95,
             "longform": .87, "planning": .86},
    "gemini": {"general": .84, "analysis": .89, "marketing": .86,
               "social": .88, "longform": .85, "planning": .86},
    "qwen": {"general": .84, "analysis": .88, "code": .90,
             "longform": .87, "structured": .88},
    "ollama": {"general": .68, "creative": .70, "analysis": .72,
               "code": .72, "privacy": 1.0},
}


def provider_configured(provider: str) -> bool | None:
    provider = provider.casefold()
    if provider == "local":
        return True
    if provider == "ollama":
        # Unknown local tags must not beat a usable cloud fallback merely
        # because they need no API key.  The GUI can promote Ollama candidates
        # to available when its live list contains them.
        return False
    options = _KEY_ENV.get(provider)
    if options is None:
        return None
    for option in options:
        names = option if isinstance(option, tuple) else (option,)
        if all(os.getenv(name, "").strip() for name in names):
            return True
    return False



# Blended $ per 1M tokens (three parts input to one part output — a prompt
# is usually longer than its answer) mapped onto 0..1 on a log scale:
# $0.10 scores 1.0, $30 scores 0.05. Log, because the step from $0.30 to $3
# matters as much to a budget as the step from $3 to $30.
CHEAP_BLENDED_USD = 0.10
DEAR_BLENDED_USD = 30.0


def price_efficiency(input_per_1m: float, output_per_1m: float) -> float:
    blended = max(1e-6, 0.75 * input_per_1m + 0.25 * output_per_1m)
    span = math.log10(DEAR_BLENDED_USD) - math.log10(CHEAP_BLENDED_USD)
    position = (math.log10(blended) - math.log10(CHEAP_BLENDED_USD)) / span
    return max(0.05, min(1.0, 1.0 - 0.95 * position))

def text_candidate(provider: str, model_id: str,
                   *, available: bool | None = None,
                   price: tuple[float, float] | None = None) -> Candidate:
    """One model as a candidate. `price` is (input, output) USD per 1M tokens
    from the pricing table; with it, cost efficiency is the real rate rather
    than a guess from the model's name."""
    key = provider.casefold()
    name = model_id.casefold()
    quality, reliability, cost, speed, context = _PROVIDER_DEFAULTS.get(
        key, (0.65, 0.65, 0.55, 0.60, 0.65))
    tasks = dict(_PROVIDER_TASKS.get(key, {"general": .65}))

    if any(token in name for token in ("opus", "pro", "max", "reasoner", "k3")):
        quality, speed, cost = min(1.0, quality + .10), speed - .14, cost - .15
        tasks["analysis"] = max(tasks.get("analysis", 0), .94)
    if any(token in name for token in ("mini", "flash", "haiku", "lite", "1.5b")):
        quality, speed, cost = quality - .10, min(1.0, speed + .17), min(1.0, cost + .18)
    if any(token in name for token in ("sonnet", "4o", "plus", "chat")):
        quality, speed = min(1.0, quality + .035), min(1.0, speed + .04)
    if "fable" in name:
        tasks["creative"], tasks["longform"] = 1.0, .98
    if "coder" in name or "code" in name:
        tasks["code"] = .98
    if "reasoner" in name or "r1" in name:
        tasks["analysis"] = .97
    if key == "ollama":
        privacy = 1.0
    else:
        privacy = 0.10
    if price is not None and key != "ollama":
        cost = price_efficiency(*price)

    return Candidate(
        provider=provider,
        model_id=model_id,
        label=model_id,
        task_fit=tasks,
        quality=max(0.0, min(1.0, quality)),
        reliability=max(0.0, min(1.0, reliability)),
        cost_efficiency=max(0.0, min(1.0, cost)),
        speed=max(0.0, min(1.0, speed)),
        context=max(0.0, min(1.0, context)),
        privacy=privacy,
        available=provider_configured(provider) if available is None else available,
    )


def known_text_models(provider: str) -> tuple[str, ...]:
    """Read each provider client's canonical offline list without an API call."""
    key = provider.casefold()
    classes = {
        "openai": ("services.openai_client", "OpenAIClientWrapper"),
        "anthropic": ("services.anthropic_client", "AnthropicClientWrapper"),
        "deepseek": ("services.deepseek_client", "DeepSeekClientWrapper"),
        "kimi": ("services.kimi_client", "KimiClientWrapper"),
        "gemini": ("services.gemini_client", "GeminiClientWrapper"),
        "qwen": ("services.qwen_client", "QwenClientWrapper"),
        "ollama": ("services.ollama_client", "OllamaClient"),
    }
    target = classes.get(key)
    if target is None:
        return ()
    module_name, class_name = target
    module = __import__(module_name, fromlist=[class_name])
    return tuple(getattr(getattr(module, class_name), "KNOWN_MODELS", ()))


def _alias_price(table: dict, model: str):
    """The price of the model `model` is a dated snapshot or alias of."""
    from services.model_watch import canonical
    base = canonical(model)
    return next((price for name, price in sorted(table.items())
                 if name != "default" and canonical(name) == base), None)


def text_candidates(providers: list[str] | tuple[str, ...],
                    live_models: dict[str, list[str]] | None = None,
                    prices: dict[str, dict[str, tuple[float, float]]] | None = None,
                    ) -> list[Candidate]:
    """Every selectable text model, ranked-ready.

    Live lists can carry embedding, speech and image ids beside the chat
    models; those are not candidates. `prices` is the pricing table as
    {provider: {model: (input, output)}} in USD per 1M tokens, with an
    optional "default" row per provider. A model is costed at its own rate,
    else at its provider's default — the same fallback the bill uses — and
    only without either is the cost guessed from its name.
    """
    live_models = live_models or {}
    prices = prices or {}
    result: list[Candidate] = []
    for provider in providers:
        models = live_models.get(provider, []) or list(known_text_models(provider))
        table = prices.get(provider.casefold(), {})
        for model in models:
            if not is_chat_model(model):
                continue
            price = table.get(model) or _alias_price(table, model) \
                or table.get("default")
            result.append(text_candidate(provider, model, price=price))
    return result


def media_candidate(model, duration: int | None = None) -> Candidate:
    """Adapt a services.media_catalog.MediaModel without coupling the engine."""
    from services.media_catalog import direct_video_rate_usd

    name = model.model_id.casefold()
    if model.kind == "local":
        quality, reliability, cost, speed, privacy = .42, .99, 1.0, .95, 1.0
        available = True
    elif model.kind == "stock":
        quality, reliability, cost, speed, privacy = .68, .92, .96, .92, .10
        available = provider_configured(model.provider)
    elif model.kind == "scene_images":
        quality = .94 if "sunburst" in name else .84 if "flare" in name else .80
        reliability, cost, speed, privacy = .88, .62, .62, .10
        if "flare" in name:
            speed = .88
        available = provider_configured(model.provider)
    else:
        quality = (.96 if "veo-3.1-generate" in name
                   else .91 if "wan3.0" in name else .86)
        reliability = .78
        speed = .88 if any(x in name for x in ("fast", "prime", "lite")) else .58
        rate = direct_video_rate_usd(model.model_id)
        cost = max(.10, 1.0 - (rate or .20) / .45)
        privacy = .08
        available = provider_configured(model.provider)
    estimated = None
    if duration and model.kind == "direct_video":
        rate = direct_video_rate_usd(model.model_id)
        estimated = rate * duration if rate is not None else None
    # No retirement gate is needed: Sora's rows left the media catalog ahead
    # of the scheduled 2026-09-24 shutdown.
    retired = False
    return Candidate(
        provider=model.provider,
        model_id=model.model_id,
        label=model.label,
        modality="visual",
        kind=model.kind,
        task_fit={"general": .80, "video": quality,
                  "social": min(1.0, speed + .05), "longform": quality},
        quality=quality,
        reliability=reliability,
        cost_efficiency=cost,
        speed=speed,
        context=.60,
        privacy=privacy,
        available=available,
        retired=retired,
        aspects=tuple(model.aspects),
        durations=tuple(model.durations),
        estimated_cost=estimated,
    )


# ── Per-request media assessment ────────────────────────────────────────────
# Images, video and speech are the most expensive things Imprint does, and a
# render is billed per image, per second or per character — so they are
# compared on what *this* request would cost on each route, not on a rate.
# €0.01 scores 1.0 and €20 scores 0.05, on a log scale for the same reason as
# price_efficiency: €0.50 against €5 matters as much as €5 against €50.
CHEAP_REQUEST_EUR = 0.01
DEAR_REQUEST_EUR = 20.0


def request_cost_efficiency(cost_eur: float) -> float:
    if cost_eur <= 0:
        return 1.0
    span = math.log10(DEAR_REQUEST_EUR) - math.log10(CHEAP_REQUEST_EUR)
    position = (math.log10(max(cost_eur, CHEAP_REQUEST_EUR))
                - math.log10(CHEAP_REQUEST_EUR)) / span
    return max(0.05, min(1.0, 1.0 - 0.95 * position))


# Stable characteristics of each implemented speech route, in the same spirit
# as media_candidate's visual numbers: (quality, reliability, speed, privacy).
# The on-device voice is free and private and sounds like a system voice;
# ElevenLabs is the most natural; OpenAI's TTS sits between them.
_SPEECH_ROUTES = {
    "system": (0.45, 0.97, 0.92, 1.0),
    "elevenlabs": (0.93, 0.86, 0.70, 0.10),
    "openai": (0.84, 0.90, 0.75, 0.10),
}


def speech_candidate(provider: str, model_id: str, label: str,
                     cost_eur: float | None,
                     available: bool | None = None) -> Candidate:
    key = provider.casefold()
    quality, reliability, speed, privacy = _SPEECH_ROUTES.get(
        key, (0.70, 0.80, 0.70, 0.10))
    cost = (request_cost_efficiency(cost_eur) if cost_eur is not None
            else 0.40)
    return Candidate(
        provider=provider,
        model_id=model_id,
        label=label,
        modality="speech",
        kind="speech",
        task_fit={"general": .80, "narration": quality, "social": quality},
        quality=quality,
        reliability=reliability,
        cost_efficiency=cost,
        speed=speed,
        context=.60,
        privacy=privacy,
        available=(True if key == "system" else provider_configured(key))
        if available is None else available,
        estimated_cost=cost_eur,
    )
