"""Public per-task ratings, turned into the quality the ranker weighs.

A text model's quality used to be read off its provider and its name: the
provider's base number plus a bonus for "opus" or "pro" and a penalty for
"mini". That cannot tell models apart — gpt-5.5 and gpt-4.1 both scored 0.84,
Claude Opus 5.5 and Opus 4.1 both 0.98, and gpt-6-luna, OpenAI's cheapest,
got OpenAI's flagship number because "luna" is not a known word. With quality
flat, price decided, and Sitebuilder's BEST FIT for landing-page code was
gpt-4o-mini over Claude Opus 5.5, which LMArena rates 1348 against 1538 for
coding: Opus wins about three meetings in four.

Where LMArena rates a model for the kind of work at hand
(`services/benchmarks.py`, a copy of Sentinel's), the quality is now that
rating against the best rating on the table for the same kind of work:

    quality = 2 / (1 + 10 ** ((best - rating) / 400))

— the model's expected score against the best-rated model, doubled. The best
scores 1.0, a model 20 points below it 0.94 (a 47/53 underdog), 100 points
below 0.72, 200 below 0.48. That curve is what an Elo rating *means*, so the
number is the rating restated rather than a scale chosen here; and the
reference is the table's best, so a model's quality does not move when the
list of candidates beside it does.

Imprint's task tags map onto leaderboard categories through `RATED_TAGS`.
A tag without a category of its own (editing, marketing, social, planning,
structured) is scored on the overall rating, which is `Candidate.quality`.

An unrated model keeps the estimate from its provider and name — but once
ratings are loaded, never above the best rating its own provider has for that
kind of work. Otherwise a model would gain an edge for being too new to have
been measured: the estimate for a Qwen "max" is 0.92, LMArena puts qwen3.8-max
at 0.88, and a qwen4-max would have outranked it the day it shipped. Being new
earns nothing. Ollama models are never rated (the leaderboard rates the full
model, not the quantised copy on this Mac).

CC BY 4.0: wherever a rating is shown it is credited — `CREDIT` travels on
the candidate into the recommendation's explanation, and the Model updates
tile says which ratings are loaded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from services import benchmarks
from services.runtime_paths import resource_base, user_data_base

# Imprint task tag -> the benchmarks task (Sentinel's names) whose leaderboard
# category rates it.
RATED_TAGS: Mapping[str, str] = {
    "general": "general",        # overall
    "creative": "writing",       # creative writing
    "longform": "writing",       # creative writing
    "code": "coding",            # coding
    "analysis": "reasoning",     # hard prompts
}

CREDIT = f"{benchmarks.SOURCE} leaderboard, {benchmarks.LICENSE}"
SOURCE_URL = benchmarks.SOURCE_URL

# Redirectable by tests (tests/conftest.py); None means the default place.
CACHE_FILE: Path | None = None
SNAPSHOT_FILE: Path | None = None


def cache_file() -> Path:
    """The last live fetch, in the data folder beside model_watch.json."""
    return CACHE_FILE or user_data_base() / "data" / "lmarena_ratings.json"


def snapshot_file() -> Path:
    """The ratings shipped with this build, used until a fetch succeeds."""
    return SNAPSHOT_FILE or resource_base() / "config" / "lmarena_snapshot.json"


def load() -> benchmarks.RatingTable:
    """The cached fetch if there is one, else the shipped snapshot, else none."""
    try:
        return benchmarks.load(cache_file(), snapshot_file())
    except Exception:
        return benchmarks.RatingTable()


def is_stale() -> bool:
    """Whether the cached fetch is missing or more than a day old."""
    return benchmarks.is_stale(cache_file())


def refresh() -> benchmarks.RatingTable:
    """Fetch and cache fresh ratings. Blocking and paced — a minute or so —
    so only ever from a background worker."""
    return benchmarks.refresh(cache_file())


def describe(table: benchmarks.RatingTable) -> str:
    """One line for the Model updates tile: which ratings, and their credit."""
    if not table:
        return "Quality ratings: none loaded — estimated from provider and name."
    where = {"live": "fetched now", "cache": "fetched",
             "snapshot": "shipped with Imprint"}.get(table.origin, table.origin)
    return (f"Quality ratings: {benchmarks.SOURCE}, published "
            f"{table.published or 'date unknown'} ({where}) · {benchmarks.LICENSE}")


def quality_from_rating(score: float, best: float) -> float:
    """Expected score against the best-rated model, doubled (1.0 for the best)."""
    return min(1.0, 2.0 / (1.0 + 10 ** ((best - score) / 400.0)))


def rated_quality(table: benchmarks.RatingTable, provider: str, model_id: str,
                  estimate: float,
                  ) -> tuple[float, dict[str, float], dict[str, str]] | None:
    """(quality, quality per tag, evidence per tag) for one model, or None.

    `estimate` is the provider-and-name quality, used where the model has no
    rating of its own and capped at its provider's best. None when the table
    says nothing about this provider (Ollama, or no table loaded): the
    estimate then stands unchanged.
    """
    key = provider.casefold()
    if not table or key == "ollama":
        return None
    quality, per_tag, evidence = estimate, {}, {}
    said_anything = False
    for tag, task in RATED_TAGS.items():
        best = benchmarks.best_rating(table, task)
        ceiling = benchmarks.best_rating(table, task, key)
        if best is None or ceiling is None:
            continue
        said_anything = True
        label = benchmarks.CATEGORY_LABELS.get(
            benchmarks.TASK_CATEGORIES[task][1], task)
        rating = table.rating(key, model_id, task)
        if rating is not None:
            value = quality_from_rating(rating.score, best)
            evidence[tag] = f"{label} {rating.score:.0f}"
        else:
            cap = quality_from_rating(ceiling, best)
            value = min(estimate, cap)
            if estimate > cap:
                evidence[tag] = (f"{label} unrated, held at {key}'s best "
                                 f"({ceiling:.0f})")
        if tag == "general":
            quality = value
        else:
            per_tag[tag] = value
    return (quality, per_tag, evidence) if said_anything else None
