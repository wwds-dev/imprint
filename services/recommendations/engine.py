"""Deterministic, explainable recommendation ranking.

Hard constraints are applied before preferences.  The result is a useful
default, not a claim that one vendor is universally superior: each agent owns
its requirement profile and every score can be explained from that profile.

Two rules decide, and the result says which (`RecommendationResult.basis`):

* **rating** — a text request where public ratings rate any candidate.
  Sentinel's rule, chosen for Imprint on 2026-10-08: among the candidates
  rated within RATING_BAND points of the best-rated one *for this kind of
  work*, the cheapest wins. 20 points is about a 53/47 split when two models
  meet, so inside the band a dearer model buys nothing measurable. A model
  without a rating is not chosen while a rated one can be — nothing shows it
  is good enough — and an unknown price is never the cheap one.
* **score** — everything else (images, video, speech, a text request where
  nothing is rated, and Chat's Local only mode, whose privacy priority is
  what prefers the local models): the agent-weighted blend of task fit,
  quality, reliability, cost, speed, context and privacy.
"""

from __future__ import annotations

from .models import AgentProfile, Candidate, RecommendationContext, RecommendationResult

# Rating points a candidate may sit below the best-rated one and still count
# as good enough, by priority. Priorities without an entry (privacy) use the
# blend.
RATING_BAND = {"balanced": 20, "cost": 50, "speed": 20, "quality": 0}

# The rating rule as one number, so the badge, the paid-request dialog and
# Update selected keep comparing scores and asking for a one-point lead:
#
#   in the band       0.50 + 0.50 × cost efficiency (0 when the price is unknown)
#   rated, below it   0.10 + 0.35 × its expected score against the band's edge
#   unrated           0.10 × the agent-weighted blend
#
# Any model in the band outranks every model outside it, the cheapest in the
# band wins, a rated model outranks an unrated one, and inside the band a
# one-point lead means about 13% cheaper (cost efficiency is a log scale).
UNRATED_CEILING = 0.10


class RecommendationEngine:
    """Rank candidates for one agent and one concrete request context."""

    def recommend(
        self,
        profile: AgentProfile,
        candidates: list[Candidate] | tuple[Candidate, ...],
        context: RecommendationContext,
    ) -> RecommendationResult | None:
        eligible = [item for item in candidates if self._eligible(item, context)]
        if context.selected_provider:
            wanted = context.selected_provider.casefold()
            eligible = [item for item in eligible
                        if item.provider.casefold() == wanted]
        if not eligible:
            return None

        # Availability is a hard constraint when at least one eligible option
        # is known to work.  If none is configured, still return the best setup
        # target and say so instead of leaving every menu without guidance.
        ready = [item for item in eligible if item.available is True]
        fallback = not ready
        pool = ready or [item for item in eligible if item.available is not False]
        if not pool:
            pool = eligible

        reference = self._rating_reference(profile, pool, context)
        ranked = self._ranked(profile, pool, context, reference)
        score, winner = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
        gap = score - runner_up
        confidence = "high" if gap >= 0.10 else "medium" if gap >= 0.035 else "low"
        if reference is None:
            reason = self._explain(profile, winner, context, score, fallback)
        else:
            reason = self._explain_rating(profile, winner, context, fallback,
                                          pool, *reference)
        return RecommendationResult(
            candidate=winner,
            score=score,
            confidence=confidence,
            reason=reason,
            fallback=fallback,
            margin=gap if len(ranked) > 1 else 1.0,
            basis="score" if reference is None else "rating",
            reference=None if reference is None else reference[0],
            band=None if reference is None else reference[1],
        )

    def rank(self, profile: AgentProfile,
             candidates: list[Candidate] | tuple[Candidate, ...],
             context: RecommendationContext) -> list[tuple[float, Candidate]]:
        """Every eligible candidate with its score, best first.

        Eligibility (modality, kind, aspect, duration, budget) applies;
        availability does not — the caller decides what can run. Ties keep a
        deterministic order, but a caller must not read a tie as a win.
        """
        eligible = [item for item in candidates if self._eligible(item, context)]
        return self._ranked(profile, eligible, context,
                            self._rating_reference(profile, eligible, context))

    def score(self, profile: AgentProfile, item: Candidate,
              context: RecommendationContext,
              result: RecommendationResult | None = None) -> float:
        """The score `recommend` ranked by, for any one candidate.

        Used to put the user's own selection beside the winner, so the two
        numbers must be directly comparable: pass the `result` they are being
        compared with, and a rating-decided result scores the candidate
        against the same best rating and band. Without it, the blend.
        """
        if result is not None and result.basis == "rating":
            return self._value(profile, item, context,
                               result.reference, result.band)
        return self._score(profile, item, context)

    def request_rating(self, profile: AgentProfile, item: Candidate,
                       context: RecommendationContext) -> float | None:
        """The candidate's public rating for this request's kinds of work."""
        return self._request_rating(item, self._tags(profile, context))

    # ── ranking ─────────────────────────────────────────────────────────────

    def _ranked(self, profile, items, context, reference):
        def key(pair):
            score, item = pair
            rating = (self._request_rating(item, self._tags(profile, context))
                      if reference is not None else None)
            # Equal scores: the better rated first (Sentinel's tie-break),
            # then a fixed order of ids that is never reported as a win.
            return (score, rating if rating is not None else float("-inf"),
                    item.provider.casefold(), item.model_id.casefold())
        if reference is None:
            scored = ((self._score(profile, item, context), item) for item in items)
        else:
            scored = ((self._value(profile, item, context, *reference), item)
                      for item in items)
        return sorted(scored, key=key, reverse=True)

    def _rating_reference(self, profile, items, context):
        """(best rating, band) when the rating rule decides, else None."""
        if context.modality != "text" or context.priority not in RATING_BAND:
            return None
        tags = self._tags(profile, context)
        rated = [r for item in items
                 if (r := self._request_rating(item, tags)) is not None]
        if not rated:
            return None
        return max(rated), RATING_BAND[context.priority]

    @staticmethod
    def _request_rating(item: Candidate, tags: list[str]) -> float | None:
        """Mean of the candidate's ratings over the request's tags.

        A tag rated on its own (coding, creative writing, hard prompts) uses
        that rating; every other tag the overall one. A model missing a
        rating the request needs is unrated for it.
        """
        if not item.ratings:
            return None
        values = []
        for tag in tags or ["general"]:
            value = item.ratings.get(tag, item.ratings.get("general"))
            if value is None:
                return None
            values.append(value)
        return sum(values) / len(values)

    def _value(self, profile: AgentProfile, item: Candidate,
               context: RecommendationContext, best: float, band: int) -> float:
        tags = self._tags(profile, context)
        rating = self._request_rating(item, tags)
        if rating is None:
            return round(UNRATED_CEILING * self._score(profile, item, context), 6)
        if rating >= best - band:
            known = item.price_per_1m is not None and (
                item.price_per_1m > 0 or item.provider.casefold() == "ollama")
            return round(0.50 + 0.50 * (item.cost_efficiency if known else 0.0), 6)
        edge = best - band
        below = 2.0 / (1.0 + 10 ** ((edge - rating) / 400.0))
        return round(0.10 + 0.35 * below, 6)

    @staticmethod
    def _eligible(item: Candidate, context: RecommendationContext) -> bool:
        if item.retired or item.modality != context.modality:
            return False
        if context.required_kind and item.kind != context.required_kind:
            return False
        if context.aspect and item.aspects and context.aspect not in item.aspects:
            return False
        if (context.duration is not None and item.kind == "direct_video"
                and item.durations and context.duration not in item.durations):
            return False
        if (context.budget_remaining is not None and item.estimated_cost is not None
                and item.estimated_cost > max(0.0, context.budget_remaining)):
            return False
        return True

    @staticmethod
    def _weights(profile: AgentProfile, priority: str) -> dict[str, float]:
        weights = {
            "quality": profile.quality_weight,
            "reliability": profile.reliability_weight,
            "cost": profile.cost_weight,
            "speed": profile.speed_weight,
            "context": profile.context_weight,
            "privacy": profile.privacy_weight,
        }
        focus = {
            "quality": "quality", "cost": "cost", "speed": "speed",
            "privacy": "privacy",
        }.get(priority)
        if focus:
            weights[focus] *= 1.8
        total = sum(weights.values()) or 1.0
        return {key: value / total for key, value in weights.items()}

    @staticmethod
    def _tags(profile: AgentProfile, context: RecommendationContext) -> list[str]:
        """The agent's task tags plus those the request's own words name."""
        tags = list(profile.task_tags)
        if context.task:
            normalized = context.task.casefold().replace("/", " ").replace("-", " ")
            synonyms = {
                "creative": ("write", "scene", "dialogue", "story", "fiction", "hook"),
                "longform": ("chapter", "draft", "outline", "book", "album"),
                "editing": ("revise", "improve", "tighten", "edit", "polish"),
                "analysis": ("analyse", "analyze", "research", "argument", "metrics"),
                "code": ("website", "dashboard", "framework", "component", "code"),
                "marketing": ("campaign", "promo", "sales", "release", "landing"),
                "social": ("social", "caption", "post", "tiktok", "instagram"),
                "planning": ("plan", "strategy", "calendar", "schedule"),
                "structured": ("report", "export", "publish", "format"),
            }
            tags.extend(tag for tag, words in synonyms.items()
                        if any(word in normalized for word in words))
        return tags

    @staticmethod
    def _quality(item: Candidate, tags: list[str]) -> float:
        """Quality for this request: each tag's rated figure where the
        candidate has one, else its overall `quality`, averaged like task fit."""
        if not item.task_quality or not tags:
            return item.quality
        values = [item.task_quality.get(tag, item.quality) for tag in tags]
        return sum(values) / len(values)

    def _score(self, profile: AgentProfile, item: Candidate,
               context: RecommendationContext) -> float:
        tags = self._tags(profile, context)
        tag_scores = [item.task_fit.get(tag, item.task_fit.get("general", 0.62))
                      for tag in tags]
        task_fit = sum(tag_scores) / len(tag_scores) if tag_scores else 0.62
        affinity = profile.provider_affinity.get(item.provider.casefold(), 0.72)
        fit = 0.72 * task_fit + 0.28 * affinity

        weights = self._weights(profile, context.priority)
        preference = (
            self._quality(item, tags) * weights["quality"]
            + item.reliability * weights["reliability"]
            + item.cost_efficiency * weights["cost"]
            + item.speed * weights["speed"]
            + item.context * weights["context"]
            + item.privacy * weights["privacy"]
        )
        # Task fit is intentionally outside the preference weights: changing
        # to "cost" must not turn an unsuitable modality/model into the winner.
        return round(0.52 * fit + 0.48 * preference, 6)

    def _explain(self, profile: AgentProfile, item: Candidate,
                 context: RecommendationContext, score: float,
                 fallback: bool) -> str:
        tags = self._tags(profile, context)
        strengths = sorted(
            ((self._quality(item, tags), "output quality"),
             (item.reliability, "reliability"),
             (item.cost_efficiency, "cost efficiency"),
             (item.speed, "speed"),
             (item.context, "long-context handling"),
             (item.privacy, "local privacy")),
            reverse=True,
        )
        top = " and ".join(label for _value, label in strengths[:2])
        task = context.task.strip() or ", ".join(profile.task_tags[:2])
        setup = (" No eligible configured provider was detected, so this is the "
                 "best setup target; add its API key or local model before running."
                 if fallback else " It is available in the current setup.")
        return (
            f"Best match for {profile.label} ({task}): {top}. "
            f"Fit score {round(score * 100)}/100.{setup}"
            f"{self._evidence(item, tags)}"
        )

    def _explain_rating(self, profile: AgentProfile, item: Candidate,
                        context: RecommendationContext, fallback: bool,
                        pool, best: float, band: int) -> str:
        tags = self._tags(profile, context)
        rated = [(c, r) for c in pool
                 if (r := self._request_rating(c, tags)) is not None]
        in_band = [c for c, r in rated if r >= best - band]
        top, top_rating = max(
            rated, key=lambda pair: (pair[1], -_price_order(pair[0])))
        mine = self._request_rating(item, tags)
        task = context.task.strip() or ", ".join(profile.task_tags[:2])
        if mine is None:            # cannot win while a rated one exists
            text = (f"Best match for {profile.label} ({task}): "
                    f"{item.model_id} is not rated.")
        elif mine >= top_rating and len(in_band) == 1:
            text = (f"Best match for {profile.label} ({task}): {item.model_id} "
                    f"is rated highest for this work ({mine:.0f}, "
                    f"{_price_text(item)}); nothing else is within {band} "
                    "points of it.")
        elif mine >= top_rating:
            text = (f"Best match for {profile.label} ({task}): {item.model_id} "
                    f"is rated highest for this work ({mine:.0f}) and is the "
                    f"cheapest of the {len(in_band)} rated within {band} "
                    f"points of it ({_price_text(item)}).")
        else:
            lead = f"Best value for {profile.label} ({task}): {item.model_id}"
            text = (f"{lead} is rated {mine:.0f} for this work, within {band} "
                    f"points of the best available ({top.model_id}, "
                    f"{top_rating:.0f}, {_price_text(top)}), and is the "
                    f"cheapest of the {len(in_band)} that are "
                    f"({_price_text(item)}).")
        if item.price_per_1m is None and len(in_band) > 1:
            text += (" No model in that range has a known price, so the "
                     "better rated one is named.")
        unrated = len(pool) - len(rated)
        if unrated == 1:
            text += (" 1 unrated model was not considered: no rating shows it "
                     "is good enough.")
        elif unrated:
            text += (f" {unrated} unrated models were not considered: no "
                     "rating shows they are good enough.")
        text += (" No eligible configured provider was detected, so this is "
                 "the best setup target; add its API key or local model "
                 "before running." if fallback
                 else " It is available in the current setup.")
        return text + self._evidence(item, tags)

    @staticmethod
    def _evidence(item: Candidate, tags: list[str]) -> str:
        """The ratings this request's quality rests on, credited, or nothing.

        A tag rated on its own cites its own figure; every other tag was
        scored on the overall one ("general"). Each figure is named once.
        """
        cited: list[str] = []
        for tag in tags or ["general"]:
            key = tag if tag in item.task_quality else "general"
            line = item.quality_evidence.get(key)
            if line and line not in cited:
                cited.append(line)
        if not cited:
            return ""
        credit = f" ({item.quality_credit})" if item.quality_credit else ""
        return f" Quality ratings{credit}: {', '.join(cited)}."


def _price_order(item: Candidate) -> float:
    """Blended price for ordering; unknown sorts as dearest."""
    return float("inf") if item.price_per_1m is None else item.price_per_1m


def _price_text(item: Candidate) -> str:
    if item.price_per_1m is None:
        return "price unknown"
    if item.price_per_1m == 0:
        return "free, local"
    return f"${item.price_per_1m:.2f} per 1M tokens blended"
