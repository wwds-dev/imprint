"""Complete, UI-ready pricing catalogs for every selectable provider.

The database contains explicit price overrides.  Provider clients contain the
models that can actually appear in Imprint's selectors.  Settings needs the
union of both: showing database rows alone made an older install look as if it
only supported Anthropic.

An unpriced model inherits its provider's ``default`` estimate when one exists.
That inheritance is surfaced explicitly; it is never presented as an exact
model price.  A zero rate means unknown, not free.  Ollama is labelled as local
compute because it has no provider API token charge.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.recommendations.catalog import known_text_models


TEXT_PROVIDERS = (
    "openai",
    "anthropic",
    "deepseek",
    "kimi",
    "gemini",
    "qwen",
    "ollama",
)

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "deepseek": "DeepSeek",
    "kimi": "Kimi",
    "gemini": "Gemini",
    "qwen": "Qwen",
    "ollama": "Ollama",
}


@dataclass(frozen=True)
class TokenPriceEntry:
    provider: str
    model: str
    input_usd: float | None
    cached_input_usd: float | None
    output_usd: float | None
    source: str

    @property
    def provider_label(self) -> str:
        return PROVIDER_LABELS.get(self.provider, self.provider.title())

    @property
    def status(self) -> str:
        return {
            "exact": "Exact model rate",
            "default": "Uses provider default",
            "unknown": "Price unknown",
            "local": "Local compute",
        }[self.source]


def _positive(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def build_token_price_catalog(conn) -> list[TokenPriceEntry]:
    """Return every known selectable text model plus explicit database rows."""
    rows = conn.execute(
        "SELECT backend, model, input_per_1m_usd, output_per_1m_usd, "
        "cached_input_per_1m_usd FROM pricing ORDER BY backend, model"
    ).fetchall()
    exact = {(r["backend"].casefold(), r["model"]): r for r in rows}

    providers = list(TEXT_PROVIDERS)
    for backend, _model in exact:
        if backend not in providers and backend != "per_unit_usd":
            providers.append(backend)

    catalog: list[TokenPriceEntry] = []
    for provider in providers:
        models = set(known_text_models(provider))
        models.update(model for backend, model in exact if backend == provider)
        # Keep the provider default visible because it controls estimates for
        # any live model the app has not learned by name yet.
        if provider != "ollama" and (provider, "default") in exact:
            models.add("default")

        default = exact.get((provider, "default"))
        for model in sorted(models, key=lambda value: (value != "default", value.casefold())):
            row = exact.get((provider, model))
            if provider == "ollama" and row is None:
                catalog.append(TokenPriceEntry(provider, model, None, None, None, "local"))
                continue

            source = "exact"
            effective = row
            if effective is None:
                effective = default
                source = "default" if default is not None else "unknown"

            if effective is None:
                values = (None, None, None)
            else:
                values = (
                    _positive(effective["input_per_1m_usd"]),
                    _positive(effective["cached_input_per_1m_usd"]),
                    _positive(effective["output_per_1m_usd"]),
                )
                if values[0] is None or values[2] is None:
                    source = "unknown"

            catalog.append(TokenPriceEntry(provider, model, *values, source))
    return catalog



def resolve_price_row(conn, provider: str, model: str):
    """The pricing row that bills `model`, and how it was found.

    Returns (row, source) with source "exact", "alias" or "default", or
    (None, "unknown"). The middle step is what stops a dated snapshot or an
    alias from falling to the provider default: providers list both
    `gpt-4o` and `gpt-4o-2024-08-06`, Anthropic both `claude-haiku-4-5` and
    `claude-haiku-4-5-20251001`, and only one of each has a row. Matching is
    by canonical id (the release date stripped), both ways round. Only rows
    with positive input and output rates count — 0 means unknown.
    """
    from services.model_watch import canonical

    rows = conn.execute(
        "SELECT model, input_per_1m_usd, output_per_1m_usd, "
        "cached_input_per_1m_usd FROM pricing WHERE backend = ? "
        "AND input_per_1m_usd > 0 AND output_per_1m_usd > 0",
        (provider,),
    ).fetchall()
    by_model = {r["model"]: r for r in rows}
    if model in by_model:
        return by_model[model], "exact"
    base = canonical(model)
    for candidate, row in sorted(by_model.items()):
        if candidate != "default" and canonical(candidate) == base:
            return row, "alias"
    if "default" in by_model:
        return by_model["default"], "default"
    return None, "unknown"


def has_exact_price(conn, provider: str, model: str) -> bool:
    """Whether `model` has its own positive rates, not the provider default.

    A dated snapshot or alias of a priced model counts as priced: it bills at
    that model's rate (resolve_price_row). A model the provider has only just
    released lands on the provider's `default` row, and the Model updates
    tile says so.
    """
    _row, source = resolve_price_row(conn, provider, model)
    return source in {"exact", "alias"}
