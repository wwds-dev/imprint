# ADR 0003: Local models are rated from evidence — inherited or measured

Status: proposed (2026-10-19, architect, for the owner's gate). Plan: `docs/local_model_routing_plan.html` in the lab root, section 3 "Rating local models", mockup D, phase 3.

## Context
The router's rule is that the cheapest model rated within 20 LMArena points of the best wins, and an unrated model never beats a rated one. LMArena does not rate quantised community builds, so every local model was unrated and could only win in Privacy first or Local only. The owner decided (2026-10-19) that a new local model is measured automatically, once, through the spend guard; a refused or keyless measurement leaves it unrated with a Measure button; re-measure is manual.

## Decision
- `services/local_ratings.py` (byte-identical in Sentinel, with `config/local_rating_prompts.json` and `tests/test_local_ratings.py`, all in `tests/test_providers_drift.py`) gives a local model a rating from one of two kinds of evidence, and every display names which.
- **Inherited**: only an unmodified build of a model LMArena rates, matched by exact normalised name that includes the parameter count. Rating = base rating − `quant_penalty(quant)`: 0 (8-bit and wider), 10 (4–6 bit), 25 (3-bit and below, and unknown). Fine-tunes, merges, distills and abliterations inherit nothing.
- **Measured**: 20 prompts for each of writing, code, summarising, extraction. Reference = the best-rated usable cloud model for that kind's router task; judge = the cheapest usable cloud model with a known price. Each pair is judged in both orders; a split is a tie. Share p (half-verdict prior) → gap 400·log10(p/(1−p)), placed below the reference and capped at it. Stored per model + quant + kind with reference, judge, record and date; reference answers cached per reference and prompt-set version.
- Measured beats inherited for the tasks it covers (writing, coding, summarize, general/simple); other tasks fall back to inherited or stay unrated.
- The engine takes its model calls as callables, so it is mockable; it runs only in `LocalMeasureWorker` (a QThread). The UI reads caches only.
- **Imprint's request guard for a run**: every cloud provider in the plan needs a key; automatically, it also needs its API permission already ticked (no dialog can be shown to nobody); `Validator.validate` must allow the run's estimate × 1.5 as agent `chat` (the Studio Assistant, so its registry permissions and daily cap apply), with in-flight reservations counted. From the Measure button, one confirmation covers the run and stands in for the permission tick for that run only. The run stops if what it spends passes the authorised amount. Every cloud call is billed through `UsageTracker.log_request` as `chat`. `LocalMeasureWorker` is a QThread, cancelled and waited for in `closeEvent`.
- `services/recommendations/ratings.py` feeds the ratings into each local candidate's per-tag ratings through `set_local_lookup`. A tag with no evidence is stored as None, so the engine reads the model as unrated for it instead of falling back to its overall rating.
- The engine orders equal scores inside the band cheaper first (Sentinel's order), because cost efficiency saturates at 1.0 and a free local model otherwise tied a cheap cloud model and lost on rating.
- Imprint's never-auto-switch rule is unchanged: a rating moves the BEST FIT badge only.
- In the router, a rated local model enters the band at a known price of 0 (kind local only); the price rule for cloud providers is unchanged.

## Consequences
- With a cloud key and ratings loaded, a good-enough local model can now win BEST FIT on price. Phase 4 adds the advisor and modes that decide when that should happen silently.
- A cheap judge's verdicts are an estimate; SUGGESTIONS #69 proposes calibrating it. *Analysis* stays unrated for measured-only local models, so Chat, Sitebuilder and Manuscript cannot pick one yet (#68).
- The first launch with Phase 3 measures every downloaded model that can run, one at a time, if the permissions and budgets allow it.
- Rejected: crediting an abliterated build with its base rating (its weights were changed); placing a local model above its reference (a cheap judge cannot establish that).
