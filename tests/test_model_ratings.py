"""
Imprint — text model quality from names and from public ratings
================================================================
Type: unit, Qt-free.

Two findings from comparing Imprint's ranker with Sentinel's (2026-10-08):

1. The name heuristics matched substrings, and every Gemini id contains
   "mini" — so gemini-3.1-pro-preview took the small-model penalty, which
   cancelled its "pro" bonus.
2. Quality was the provider's base number plus name words, so it could not
   tell gpt-5.5 from gpt-4.1, or Opus 5.5 from Opus 4.1, and price decided:
   Sitebuilder's BEST FIT for landing-page code was gpt-4o-mini over Claude
   Opus 5.5, which LMArena rates 1348 against 1538 for coding.

Quality now comes from LMArena's per-task ratings where they rate a model
(services/recommendations/ratings.py). These tests pin the rule with small
synthetic tables, and the two findings against the shipped snapshot.

Run with:  pytest tests/test_model_ratings.py -v
"""

import pytest

from agents.recommendation_profiles import profile_for
from services import benchmarks, database
from services.recommendations import (
    RecommendationContext, RecommendationEngine, ratings,
)
from services.recommendations.catalog import (
    name_tokens, text_candidate, text_candidates,
)


def table(**categories):
    """A RatingTable from {category: [(name, score, organisation), ...]}."""
    return benchmarks.RatingTable({
        "published": "2026-10-02",
        "categories": {
            f"text_style_control/{category}": [
                [name, score, score - 5, score + 5, 10_000, org]
                for name, score, org in rows]
            for category, rows in categories.items()},
    }, origin="snapshot")


def snapshot_prices() -> dict:
    """The pricing table as the window's _price_index reads it."""
    index: dict = {}
    conn = database.get_connection()
    try:
        for row in conn.execute(
                "SELECT backend, model, input_per_1m_usd, output_per_1m_usd "
                "FROM pricing WHERE input_per_1m_usd > 0 "
                "AND output_per_1m_usd > 0"):
            index.setdefault(row["backend"].casefold(), {})[row["model"]] = (
                float(row["input_per_1m_usd"]), float(row["output_per_1m_usd"]))
    finally:
        conn.close()
    return index


@pytest.fixture(scope="module")
def shipped():
    loaded = ratings.load()
    assert loaded, "config/lmarena_snapshot.json did not load"
    assert loaded.origin == "snapshot"      # conftest keeps the cache empty
    return loaded


# ── 1. names are words ──────────────────────────────────────────────────────

def test_gemini_is_not_a_mini_model():
    assert "mini" not in name_tokens("gemini-3.1-pro-preview")
    # Gemini's base quality is 0.82 and "pro" adds 0.10; the substring match
    # used to take 0.10 straight back off.
    assert text_candidate("gemini", "gemini-3.1-pro-preview").quality == \
        pytest.approx(0.92)
    assert text_candidate("gemini", "gemini-4").quality == pytest.approx(0.82)
    assert text_candidate("gemini", "gemini-3.8-flash").quality == \
        pytest.approx(0.72)                 # "flash" is a real small-model word


def test_the_small_and_capability_words_still_match_as_words():
    assert text_candidate("openai", "gpt-4o-mini").quality < \
        text_candidate("openai", "gpt-4o").quality
    # The Ollama size tag survives the split on dots.
    assert "1.5b" in name_tokens("deepseek-r1:1.5b")
    assert text_candidate("ollama", "deepseek-r1:1.5b").quality < \
        text_candidate("ollama", "deepseek-r1:8b").quality
    assert text_candidate("kimi", "kimi-k2.7-code").task_fit["code"] == .98
    assert text_candidate("openai", "gpt-5-codex").task_fit["code"] == .98
    assert text_candidate("deepseek", "deepseek-r1").task_fit["analysis"] == .97
    # A word inside another word is not that word.
    assert "chat" not in name_tokens("chatgpt-4o-latest")
    assert "pro" not in name_tokens("qwen-prompt-2")


# ── 2. the rule, on synthetic tables ────────────────────────────────────────

def test_quality_is_the_expected_score_against_the_best_doubled():
    assert ratings.quality_from_rating(1500, 1500) == 1.0
    assert ratings.quality_from_rating(1480, 1500) == pytest.approx(0.943, abs=1e-3)
    assert ratings.quality_from_rating(1400, 1500) == pytest.approx(0.720, abs=1e-3)
    assert ratings.quality_from_rating(1300, 1500) == pytest.approx(0.480, abs=1e-3)


def test_a_rated_model_takes_each_task_rating_and_cites_it():
    rated = table(
        overall=[("claude-opus-5.5", 1500, "anthropic"),
                 ("gpt-4.1-2025-04-14", 1400, "openai")],
        coding=[("claude-opus-5.5", 1540, "anthropic"),
                ("gpt-4.1-2025-04-14", 1460, "openai")])
    opus = text_candidate("anthropic", "claude-opus-5-5", ratings=rated)
    gpt = text_candidate("openai", "gpt-4.1", ratings=rated)
    assert opus.quality == 1.0 and opus.task_quality["code"] == 1.0
    assert gpt.quality == pytest.approx(0.720, abs=1e-3)
    assert gpt.task_quality["code"] == pytest.approx(
        ratings.quality_from_rating(1460, 1540))
    # No creative-writing table: that tag falls back to `quality`.
    assert "creative" not in gpt.task_quality
    assert gpt.quality_evidence == {"general": "overall 1400", "code": "coding 1460"}
    assert gpt.quality_credit == "LMArena leaderboard, CC BY 4.0"


def test_an_unrated_model_is_held_at_its_providers_best():
    """Being too new to be rated must not be an edge: the estimate for a Qwen
    "max" (0.92) is above what the ratings give qwen3.8-max."""
    rated = table(overall=[("claude-opus-5.5", 1500, "anthropic"),
                           ("qwen3.8-max", 1460, "alibaba")])
    old = text_candidate("qwen", "qwen3.8-max", ratings=rated)
    new = text_candidate("qwen", "qwen4-max", ratings=rated)
    assert text_candidate("qwen", "qwen4-max").quality == pytest.approx(0.92)
    assert new.quality == old.quality == pytest.approx(
        ratings.quality_from_rating(1460, 1500))
    assert "unrated, held at qwen's best (1460)" in new.quality_evidence["general"]
    # An estimate already below the cap is left alone and cites nothing.
    small = text_candidate("qwen", "qwen-flash", ratings=rated)
    assert small.quality == pytest.approx(0.72)
    assert small.quality_evidence == {}


def test_a_provider_the_ratings_do_not_cover_keeps_its_estimate():
    rated = table(overall=[("claude-opus-5.5", 1500, "anthropic")])
    assert text_candidate("kimi", "kimi-k3", ratings=rated).quality == \
        text_candidate("kimi", "kimi-k3").quality
    # Never Ollama: the leaderboard rates the full model, not a local quant.
    local = text_candidate("ollama", "deepseek-r1:8b", ratings=rated)
    assert local.quality == text_candidate("ollama", "deepseek-r1:8b").quality
    assert local.quality_evidence == {} and local.quality_credit == ""


def test_the_engine_scores_quality_per_task_and_credits_the_ratings():
    rated = table(
        overall=[("claude-opus-5.5", 1500, "anthropic"),
                 ("gpt-4o-mini-2024-07-18", 1320, "openai")],
        coding=[("claude-opus-5.5", 1540, "anthropic"),
                ("gpt-4o-mini-2024-07-18", 1350, "openai")])
    engine = RecommendationEngine()
    candidates = text_candidates(["anthropic", "openai"], {
        "anthropic": ["claude-opus-5-5"], "openai": ["gpt-4o-mini"]},
        ratings=rated)
    result = engine.recommend(profile_for("webdesign"), candidates,
                              RecommendationContext(agent="webdesign",
                                                    task="landing page code"))
    assert result.candidate.model_id == "claude-opus-5-5"
    assert "Quality ratings (LMArena leaderboard, CC BY 4.0): coding 1540, " \
           "overall 1500." in result.reason


def test_without_ratings_the_explanation_cites_nothing():
    engine = RecommendationEngine()
    result = engine.recommend(
        profile_for("chat"), text_candidates(["anthropic"]),
        RecommendationContext(agent="chat"))
    assert "Quality ratings" not in result.reason


# ── 3. the findings, against the shipped snapshot ───────────────────────────

def test_quality_now_tells_the_reported_pairs_apart(shipped):
    q = lambda provider, model: text_candidate(  # noqa: E731
        provider, model, ratings=shipped).quality
    assert q("openai", "gpt-5.5") > q("openai", "gpt-4.1") + .1
    assert q("anthropic", "claude-opus-5-5") > q("anthropic", "claude-opus-4-1") + .1
    # OpenAI's cheapest no longer gets OpenAI's flagship number.
    assert q("openai", "gpt-6-luna") < q("openai", "gpt-6.1-sol")


def test_sitebuilder_no_longer_prefers_gpt_4o_mini_for_landing_page_code(shipped):
    engine = RecommendationEngine()
    profile = profile_for("webdesign")
    context = RecommendationContext(agent="webdesign", task="landing page code")
    prices = snapshot_prices()
    score = lambda provider, model, **kw: engine.score(  # noqa: E731
        profile, text_candidates([provider], {provider: [model]}, prices,
                                 **kw)[0], context)
    # Before: price decided, and gpt-4o-mini outranked Opus 5.5.
    assert score("openai", "gpt-4o-mini") > score("anthropic", "claude-opus-5-5")
    # With the ratings, the model rated 190 points better for coding wins.
    assert score("anthropic", "claude-opus-5-5", ratings=shipped) > \
        score("openai", "gpt-4o-mini", ratings=shipped) + .03


def test_every_known_text_model_is_rated_or_deliberately_estimated(shipped):
    """A model Imprint offers by default that the ratings miss is ranked on the
    estimate — say which, so a renamed id that silently lost its rating shows
    up here rather than as a quietly different BEST FIT."""
    from services.recommendations.catalog import known_text_models
    unrated = sorted(
        f"{provider}/{model}"
        for provider in ("openai", "anthropic", "gemini", "deepseek", "kimi", "qwen")
        for model in known_text_models(provider)
        if shipped.rating(provider, model, "general") is None)
    assert unrated == [
        "kimi/kimi-k2.7-code", "kimi/kimi-k2.7-code-highspeed",
        "qwen/qwen-flash", "qwen/qwen3.8-flash",
    ]
