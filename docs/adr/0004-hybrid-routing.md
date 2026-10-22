# 0004 — Hybrid routing: an advisor per job, never an automatic switch of the selection

Date: 2026-10-19 · Status: accepted (owner decisions of 19 Oct 2026 in
`docs/local_model_routing_plan.html`, lab root). Sentinel's ADR 0003 is the twin.

## Context
Phases 1–3 made local models first-class and rated. The owner chose
*Local, advise per job* as the default: jobs run local and each new job is
checked against the engine's BEST FIT. Imprint's never-auto-switch rule and
one-point-lead rule stay.

## Decision
- One pure module, `services/routing_advisor.py`, byte-identical with
  Sentinel's and drift-tested, decides per job: run, suggest one alternative
  (named reasons, cost, time) or refuse. It never switches anything itself.
- The agent's provider/model selection is never changed by the advisor, a
  rule or Local first: an override applies to one job only. Every paid job
  still meets the paid-request dialog, including a rule's and a fallback's.
- Runs on a model other than the selection without a banner: a rule the user
  made (*Always for this kind of job*, removable in Settings → Models), and
  *Local first* picking a free, rated, good-enough local model. Neither picks
  a paid model the user did not choose.
- Five modes, app setting plus per-agent overrides; the Mode box's Local only /
  Cloud only remain hard limits (`effective_mode`).
- Failover is an offer from the engine's ranking, not a retry; Local only
  never offers, suggests or follows a rule to the cloud.
- Candidates come from `_text_candidates_for`, which reads caches only, so
  the advisor may run on the UI thread.

## Consequences
- Only the Studio Assistant is advised in this phase (TODO).
- Cloud candidates carry no context window, so the context limit is checked
  for local models only (SUGGESTIONS #73).
