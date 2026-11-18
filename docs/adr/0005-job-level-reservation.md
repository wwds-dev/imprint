# ADR 0005: Job-level reservation in the request guard

Status: **Proposed, awaiting owner approval at the Architect gate** (architect, 2026-11-18). Spec: `docs/specs/one-click-release.md`, section "Architecture (architect, 2026-11-18)", A1–A3. Amends one clause of ADR 0004 (see Decision).

## Context
Today the request guard confirms each paid request on its own.
- `GodAI.authorize_request` (`main.py:4467-4580`) validates the request against the caps (`services/validator.py:76-202`), shows one `QMessageBox` (`confirm_external_api_request`, `main.py:4340-4407`) and keeps a token context in memory (`_pending_requests`).
- `record_request`, `record_partial` and `abandon_request` close the request (`main.py:5310-5422`).
- A refusal opens a dialog of its own (`main.py:4532-4536`).

The one-click release kit (owner decisions 2026-11-18) needs three things the per-request guard cannot give:
- one confirmation for up to eight stages and many requests;
- an unattended run overnight;
- every cap still holding.

The options today are a dialog per request, which is not unattended, or bypassing the guard, which the first app invariant forbids.

Things the design must respect:
- In-flight reservations are summed for the session and daily checks only. Agent and project checks ignore them (`main.py:4517-4530`).
- The token's Project and the prompt's project instructions follow the active Project (`main.py:567-574, 3801-3807, 4568-4569`).
- An unpriced cloud model estimates €0 in `estimate_chat_cost` (`main.py:576-595`).
- `record_request` has no ceiling.
- A by-name request lookup takes the oldest request for an agent key (`main.py:5270-5291`).
- Session spend resets on restart. Daily totals are summed by row timestamp (`services/usage_tracker.py:199-227`).

## Decision
1. **One modal per job.** The kit's confirmation screen (spec D2) is the only modal. On Start, `authorize_job(plan, shown_estimate)` does four things, in order. It re-estimates (a changed figure refuses). It validates per agent and for the total against the job's own Project. It appends an approval row to the ledger. Then it reserves the whole maximum in an in-memory `ReservationBook` (`services/job_reservation.py`, Qt-free).
2. **Child tokens without a dialog.** Before each provider call, `authorize_job_item` mints a child token. Before minting, the guard checks:
   - the route equals the approved route;
   - the price is known;
   - the item's maximum fits the stage line's remainder;
   - the validator still holds the job's unspent reservation under every cap, excluding the job's own amounts.

   The token moves money from the line to itself, so nothing is counted twice. Child tokens carry `job_id`, the stage, the item and the job's Project, and are never added to the by-name queue. On any refusal the job pauses; no dialog opens.
3. **Clamp at the line.** `record_job_item` records `min(actual, granted)`. When actual exceeds granted, or is €0 on a paid route, the row is recorded at `granted`, gets `cost_type='capped'` and is flagged in the report. Partial closes use `record_partial` semantics. Unspent amounts return to the line.
4. **Release.** Every stage end releases its line. Every exit from "running" (pause, stop, quit, discard, end) releases the job.
5. **Durability.** The book lives in memory. A crash cannot leak a reservation into a later process, because caps are summed from `usage` rows and the session total resets. Before each paid call, the ledger commits an intent row. Usage rows gain `job_id` and `job_item`, under a partial unique index. Recovery then adopts an existing row. With no row, a paid text or per-unit item is recorded at its maximum and marked Verify (owner decision 7); narration is settled from Booth's chunk counts.
6. **Resume re-validates.** A resume (after a pause or a restart) re-reserves the remaining maximum against the current caps. This differs from `restore_request` (`main.py:5242-5268`) on purpose: unstarted stages have spent nothing.
7. **Daily cap.** The budget day is the day of the latest approval or resume. Grants skip the daily check once the date has passed it (owner decision 6). How a later-day resume counts is owner question 2 in the spec.
8. **Zero means unknown** over the whole estimate. Text stages are priced with `max_cost_eur`, never `estimate_chat_cost`. `None` or ≤0 on a paid route blocks Start, and `authorize_job` refuses even when called directly.
9. **Job reservations count in the agent and project checks** of every other request while a kit holds money.
10. **Amends ADR 0004.** ADR 0004 says every paid job still meets the paid-request dialog. For job child tokens that dialog is replaced by the kit's single confirmation, which shows the same assessment per paid stage. Apply on that screen changes only the screen's row, never the agent's selection. Everything else in ADR 0004 stands.

## Alternatives considered
- **One dialog per stage (or per request).** It needs no guard change, but a night run would stop at the first paid stage until morning. That defeats the goal, and the owner's "ask me once" would become "ask me three to five times". Rejected.
- **A pre-approved standing budget** ("the kit may spend up to €X per night", set once in Settings). It is unattended and simple, but the owner never sees this kit's routes, maxima or assessment before it spends. That breaks "the approval covers exactly those routes and those maxima" (spec, Scope). It also turns the guard from per-decision into per-period, which every other agent could then copy. Rejected.
- **A persistent reservation table** (reservations in SQLite rather than memory). It survives a restart, but it duplicates the truth that `usage` rows and intent rows already hold. It would also need its own sweep for stale reservations, which is a leak class of its own. Rejected in favour of an in-memory book plus durable intent rows.
- **A runner on its own thread** calling the guard through blocking queued calls. The guard state is a GUI-thread dict and recording updates widgets, and this app has a Qt deadlock history (TODO.md:173). Rejected: the runner lives on the GUI thread and workers never touch the guard.
- **Reusing `authorize_request` with a "silent" flag.** It is the smallest diff, but it leaves the refusal dialogs, the active-Project coupling, the by-name queue and the unclamped record in the money path. Rejected.

## Consequences
- **New guard surface**, all Qt-free at the core and mutation-tested:
  - `authorize_job`, `authorize_job_item`, `record_job_item`, `close_job_item_partial`, `void_job_item`, `release_job_stage`, `release_job`;
  - `Validator.validate(..., check_daily=True)`, with existing calls unchanged;
  - `per_unit_pricing.max_dated_rate_usd`.
- **Additive state:** new tables `release_jobs`, `release_job_approvals`, `release_job_stages`, `release_job_items`; new columns `usage.job_id`, `usage.job_item`, `runs.job_id`, `audiobook_conversions.job_id`; a partial unique index on `usage(job_id, job_item)`. All are covered by a migration test on an old database.
- **Other requests see less room while a kit runs.** The in-flight sum includes the job's remainder, now also for agent and project caps. The confirmation screen's caps table shows this before Start.
- **Usage after midnight** lands in the next day's totals (row timestamps are real). The daily check at approval is the approval day's.
- **Recording at the maximum** on an unknown outcome over-records on purpose. The report names the provider page to check.
- **A contract test** fails if any provider call in the kit's code path is reachable without a job-scoped token (spec A8, success measure 6).
- **Hard to reverse:** once usage rows carry job ids and reports rely on them, removing the job path needs a data migration. So does moving the reservation to a persistent table. Slice 1 ships only the local-only entry point. This ADR's money side lands in slice 2, after this gate.
