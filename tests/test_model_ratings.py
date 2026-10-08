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
(services/recommendations/ratings.py), and — the user's choice the same day —
a text request where any candidate is rated is decided by Sentinel's rule:
the cheapest model rated within 20 points of the best available wins
(services/recommendations/engine.py). These tests pin both with small
synthetic tables, and the findings against the shipped snapshot.

Run with:  pytest tests/test_model_ratings.py -v
"""

from dataclasses import replace

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
    pair = {"openai": ["gpt-4o-mini"], "anthropic": ["claude-opus-5-5"]}
    # Before: price decided, and gpt-4o-mini outranked Opus 5.5.
    before = engine.recommend(profile, [
        replace(c, available=True)
        for c in text_candidates(["openai", "anthropic"], pair, prices)], context)
    assert before.basis == "score"
    assert before.candidate.model_id == "gpt-4o-mini"
    # Rated 190 points apart for coding, gpt-4o-mini is not in the band.
    after = engine.recommend(profile, [
        replace(c, available=True)
        for c in text_candidates(["openai", "anthropic"], pair, prices,
                                 shipped)], context)
    assert after.basis == "rating"
    assert after.candidate.model_id == "claude-opus-5-5"
    assert after.margin > .10


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



# ── 4. the rating rule: the cheapest model within 20 points of the best ─────

def rated(provider, model, rating, price, **extra):
    """A text candidate with one overall rating and a blended price."""
    from services.recommendations import Candidate
    values = dict(
        provider=provider, model_id=model, label=model,
        task_fit={"general": .8}, quality=.8, reliability=.8,
        cost_efficiency=(ratings_price_efficiency(price) if price else .55),
        speed=.7, context=.7, available=True,
        ratings={"general": rating} if rating is not None else {},
        price_per_1m=price)
    values.update(extra)
    return Candidate(**values)


def ratings_price_efficiency(blended):
    from services.recommendations.catalog import price_efficiency
    return price_efficiency(blended, blended)


CHAT = profile_for("chat")
GENERAL = RecommendationContext(agent="chat")


def test_the_cheapest_inside_the_band_wins_and_a_cheaper_one_outside_does_not():
    engine = RecommendationEngine()
    result = engine.recommend(CHAT, [
        rated("a", "best", 1500, 10.0),
        rated("b", "close", 1485, 2.0),       # 15 below: in the band
        rated("c", "cheap", 1470, 0.2),       # 30 below: out
    ], GENERAL)
    assert result.basis == "rating" and result.band == 20
    assert result.reference == 1500
    assert result.candidate.model_id == "close"
    assert "within 20 points of the best available (best, 1500" in result.reason
    assert "cheapest of the 2 that are ($2.00 per 1M tokens blended)" in result.reason


def test_the_best_rated_wins_when_nothing_else_is_close():
    engine = RecommendationEngine()
    result = engine.recommend(CHAT, [
        rated("a", "best", 1500, 10.0),
        rated("c", "cheap", 1400, 0.2),
    ], GENERAL)
    assert result.candidate.model_id == "best"
    assert "rated highest for this work (1500" in result.reason
    assert "nothing else is within 20 points" in result.reason
    assert result.margin > .05               # a band member beats any outsider


def test_an_unrated_model_is_not_chosen_while_a_rated_one_can_be():
    engine = RecommendationEngine()
    result = engine.recommend(CHAT, [
        rated("a", "rated", 1300, 30.0),
        rated("b", "unrated-and-free", None, 0.1, quality=1.0),
    ], GENERAL)
    assert result.candidate.model_id == "rated"
    assert "1 unrated model was not considered" in result.reason


def test_an_unknown_price_is_never_the_cheap_one():
    engine = RecommendationEngine()
    result = engine.recommend(CHAT, [
        rated("a", "priced", 1490, 25.0),
        rated("b", "unknown", 1500, None),
    ], GENERAL)
    assert result.candidate.model_id == "priced"


def test_with_nothing_rated_the_blend_decides_as_before():
    engine = RecommendationEngine()
    result = engine.recommend(CHAT, [
        rated("a", "one", None, 1.0, quality=.95),
        rated("b", "two", None, 1.0, quality=.60),
    ], GENERAL)
    assert result.basis == "score" and result.reference is None
    assert result.candidate.model_id == "one"
    assert "Fit score" in result.reason


def test_privacy_keeps_the_blend_and_media_never_uses_ratings():
    engine = RecommendationEngine()
    local = RecommendationContext(agent="chat", priority="privacy")
    result = engine.recommend(CHAT, [
        rated("a", "cloud", 1500, 1.0),
        rated("ollama", "local", None, 0.0, privacy=1.0),
    ], local)
    assert result.basis == "score"
    visual = RecommendationContext(agent="video", modality="visual")
    result = engine.recommend(profile_for("video"), [
        rated("a", "clip", 1500, 1.0, modality="visual"),
        rated("b", "other", None, 1.0, modality="visual"),
    ], visual)
    assert result.basis == "score"


def test_the_selection_is_scored_on_the_same_terms_as_the_winner():
    """The dialog and the badge compare engine.score(selection, result) with
    the winner's score: the same band, the same reference, one-point leads."""
    engine = RecommendationEngine()
    pool = [rated("a", "best", 1500, 10.0), rated("b", "close", 1485, 2.0)]
    result = engine.recommend(CHAT, pool, GENERAL)
    assert engine.score(CHAT, result.candidate, GENERAL, result) == result.score
    # Same band, about 5% dearer: within a point — it keeps the badge.
    near = rated("c", "near", 1490, 2.1)
    assert result.score - engine.score(CHAT, near, GENERAL, result) < .01
    # Same band, a third dearer: a visible lead.
    dearer = rated("d", "dearer", 1490, 2.7)
    assert result.score - engine.score(CHAT, dearer, GENERAL, result) >= .01
    # Below the band or unrated: never within a point.
    assert result.score - engine.score(
        CHAT, rated("e", "weak", 1450, 0.2), GENERAL, result) > .05
    assert result.score - engine.score(
        CHAT, rated("f", "new", None, 0.2), GENERAL, result) > .40
    # Without the result, score() is still the blend.
    assert engine.score(CHAT, near, GENERAL) == engine._score(CHAT, near, GENERAL)


def test_on_the_shipped_ratings_every_text_agent_gets_the_cheapest_good_enough_model(shipped):
    """The rule's invariant, for every agent with a text menu, with every
    provider available: the winner is rated within the band of the best, and
    no other model in the band is cheaper."""
    engine = RecommendationEngine()
    prices = snapshot_prices()
    candidates = [replace(c, available=True) for c in text_candidates(
        ["openai", "anthropic", "gemini", "deepseek", "kimi", "qwen"],
        None, prices, shipped)]
    for agent in ("chat", "author", "manuscript", "music", "webdesign",
                  "fiverr", "creator", "social"):
        profile = profile_for(agent)
        context = RecommendationContext(agent=agent)
        result = engine.recommend(profile, candidates, context)
        assert result.basis == "rating", agent
        rating = lambda c: engine.request_rating(profile, c, context)  # noqa: E731
        band = [c for c in candidates
                if rating(c) is not None and rating(c) >= result.reference - 20]
        assert result.candidate in band, agent
        assert result.candidate.price_per_1m == min(
            c.price_per_1m for c in band if c.price_per_1m is not None), agent
        assert result.candidate.model_id != "gpt-4o-mini"
