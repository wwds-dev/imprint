# Provider and model recommendations

Status: deterministic v1, September 2026.

## Contract

Every agent with a provider/model selector owns an immutable requirement
profile in `agents/<key>/recommendations.py`. The umbrella discovers that
profile through `agents/recommendation_profiles.py`; agents never hard-code a
provider or model id as the universal answer.

`services/recommendations/` owns the shared mechanism:

- `models.py` defines profiles, candidates, request context and results.
- `catalog.py` adapts selectable text and media models into comparable,
  conservative capability records. Unknown live text models receive family
  defaults instead of disappearing.
- `ratings.py` turns public LMArena ratings into a text model's quality (see
  *Quality* below).
- `engine.py` first removes incompatible, retired, unavailable and over-budget
  choices, then applies the agent's quality, reliability, cost, speed, context
  and privacy weights.

The provider menu marks the provider containing the best eligible model. The
model menu marks the best eligible model inside the provider the user currently
selected. A manual provider choice is therefore still supported with useful
guidance rather than treated as an error.

## Quality

Since 2026-10-08 a text model's quality is its LMArena rating for the kind of
work, not its provider's base number plus name words — which scored gpt-5.5
and gpt-4.1 alike, and let price alone make gpt-4o-mini Sitebuilder's BEST FIT
for code over Claude Opus 5.5 (rated 1348 against 1538 for coding).

- `services/benchmarks.py` is a copy of Sentinel's ratings module (drift
  guard: `tests/test_benchmarks_drift.py`). Ratings come from the cached daily
  fetch (`data/lmarena_ratings.json`), else the shipped
  `config/lmarena_snapshot.json`. `RatingsWorker` refreshes them beside the
  Model updates check; nothing waits on it.
- `ratings.RATED_TAGS` maps task tags to leaderboard categories: creative and
  longform → creative writing, code → coding, analysis → hard prompts,
  general → overall. `Candidate.quality` is the overall figure;
  `Candidate.task_quality` holds the per-tag ones, and the engine averages
  over the request's tags exactly as it averages task fit.
- quality = 2 / (1 + 10^((best − rating) / 400)): the expected score against
  the best-rated model on the table, doubled. The reference is the table, not
  the candidate list, so `RecommendationEngine.score()` on one candidate and
  `recommend()` over many agree.
- A model the table does not rate keeps the name-based estimate, capped at the
  best rating its provider has for that kind of work, so being unmeasured is
  never an edge. Ollama is never rated.
- The explanation ends with the figures used and their credit
  (`Candidate.quality_evidence`, `quality_credit`), because the ratings are
  CC BY 4.0 and must be credited wherever shown.

The blend is unchanged: 0.52 × (task fit and provider affinity) + 0.48 ×
(the agent's weighted quality, reliability, cost, speed, context, privacy).

## Explanation and UI data

Recommendations never change provider/model display text. The GUI stores the
marker, explanation, score, confidence and badge in dedicated Qt item roles
defined by `ui/widgets.py`. This keeps recommendations separate from semantic
foreground colours such as the warning for a local model that is too large for
the current machine.

The explanation names the task, strongest dimensions, normalized fit score,
confidence, and whether the result is merely a setup target because no eligible
provider is configured. Tooltips expose this reasoning on both the field and
the marked menu row.

## Recalculation

The ranker runs again when relevant task/format controls, selected provider,
budget limits, API permissions, video aspect or video duration change. It uses
only local metadata and UI state; opening a dropdown never makes a network or
paid model call.

## Safety and evolution

The current score is deterministic and covered by contract tests. Future
learning may adjust reliability and retry estimates from aggregate completed
runs, but it must not silently optimize for provider usage or gross revenue.
Any income-oriented utility function must subtract generation cost, retry cost,
time and measured risk, and must distinguish observed results from forecasts.
