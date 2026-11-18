# Spec: One-click release (approved manuscript → release kit overnight)

Status: **Define approved by the owner 2026-11-18 (freeze exception granted); Design and Architect in progress.** Source: `SUGGESTIONS.md` #79 (portfolio review 2026-11-18). Priority: not set (owner). Product-manager playbook: `status: current`, last-reviewed 2026-10-14.

> **Feature freeze (2026-10-09) applies.** `TODO.md` allows bug fixes, tests and wording only until `tests/READINESS_GATE.md` §3 A–E are ticked on one commit. This feature needs an explicit owner exception, like local-model routing got on 2026-10-21. Declining it is a valid outcome of this gate.
>
> **No paid stage can be tested today.** `TODO.md` P1 `@me`: the Anthropic, Gemini and DeepSeek keys in `.env` are rejected by their providers (found 2026-10-09), and `OPENAI_API_KEY` is unset. Every Booth narration route is paid (OpenAI, Gemini, ElevenLabs). Until that owner item is done, only the free stages can run for real; paid stages can be built and tested only against fakes.

`/radar-check` and the read-only legal consult ran after the Define gate (owner decision 10); findings in `docs/audit/one-click-release-radar.md` and `docs/audit/one-click-release-legal-consult.md`.

## Problem
Who: one author with a finished book in a Project.
How it hurts: turning an approved manuscript into a release kit today takes five separate trips through three agents, each with its own confirmation dialog, its own cost line and its own output folder. Quill (or Press, for an approved version) exports the EPUB. Booth narrates it. In Press, Quote Finder suggests quotes, each graphic and each Short is rendered by hand one at a time, and the calendar writes captions and exports a CSV. Nothing totals the cost in advance. Graphics, Shorts and the calendar are not linked to the Project, so Project Overview cannot show the kit as one piece.
Evidence: see "Premise checked against the code" below.

## Target user and job
The owner as an author: "My book is approved. Tonight, make everything I need to release it, tell me up front what it costs at most, and ask me once."

## Premise checked against the code (2026-11-18, at `5137be8`)
The row assumes the five outputs already exist as callable steps. Mostly true. What differs:

| Output | Where today | Paid? | Callable without the UI? | Linked to the Project? |
|---|---|---|---|---|
| EPUB | `agents/author/book_exporter.export_epub`; approved-version export `services/project_publication.export_approved` (SHA-256 receipt) | no (local EbookLib) | yes, Qt-free | yes (`agents/manuscript/panel.py:1271`) |
| Audiobook | Booth, `agents/audiobook/panel.py:start_conversion` → narrator subprocess (`services/narrator/converter.py`); durable `audiobook_conversions` row with chunk cache and resume | **always**: OpenAI `gpt-4o-mini-tts` (retires 2027-01-06), Gemini `gemini-3.8-flash-tts` (rate doubles 2027-01-01), ElevenLabs. No free route | no: the estimate, assessment and `authorize_request` sit in the panel and use `QMessageBox` | yes (`panel.py:972`) |
| Quotes (input to the next three) | Press Quote Finder, `panel.py:~1330`: one text request | if a cloud model is chosen; free on Ollama/LM Studio | no: the result lives in list widgets, read back from `QLabel`s (`_calendar_quotes_from_finder`) | no |
| Quote graphics | `agents/manuscript/quote_graphics.render_quote_graphic` | no (local Pillow) | yes, Qt-free | **no** |
| Shorts | `agents/manuscript/shorts_generator.render_short` (static graphic + narration + ffmpeg) | free with the on-device voice (macOS `say`); ElevenLabs is per character, guarded by `_authorize_short_narration` (`panel.py:1005`) | the render is Qt-free; the guard is in the panel | **no** |
| Calendar | `agents/manuscript/content_calendar.build_calendar` (pure) + one caption text request (`panel.py:1541`) + CSV export | captions are paid if a cloud model is chosen | schedule yes; captions no | **no** |

Differences from the row:
1. **The calendar is not 30 days.** It offers 1, 2 or 4 weeks (`panel.py`, `calendar_weeks_box`); 4 weeks is 28 days. Cadence is fixed: TikTok 4/week (Shorts), Instagram 3/week (alternating), Pinterest 7/week (graphics) (`content_calendar.CADENCE`). Four weeks with all three platforms is 56 slots, about 22 of them Shorts.
2. **Quotes come only from the start of the book.** Quote Finder sends the first 30,000 characters (`panel.py`: `truncated = text[:30000]`), about 5,000 words. A release kit drawn from chapter one alone is a real limitation.
3. **The calendar does not render anything.** It assigns a quote and a format to each slot; graphics and Shorts are rendered separately by hand. The job has to connect them.
4. **Captions for a full calendar may be cut off.** All slots go in one request with the 8,192-token output cap. A cut reply leaves later slots blank (`_on_captions_done` already reports this honestly).
5. **"The durable job ledger in the video pipeline"** is `agents/video/jobs.py` (`video_jobs` table): an intent row written before the paid POST, a job id, terminal states, `sweep_lost()` for rows that never got an id, and `resume_pending_jobs()` that restores the budget reservation through the host guard on the next launch. It is Qt-free and per render. Booth has its own durable row with a chunk cache (`audiobook_conversions`) that already avoids re-paying finished chapters. Neither covers a job made of several stages.
6. **The Project object (#42)** links outputs through `services/project_artifacts.record(project_id, agent, kind, path)`. Quill, Booth, Reel and Muse call it; Press calls it only for approved exports. The immutable approved version (`services/project_manuscripts.get_version`) is the right source for a release: later edits in Write do not change it.
7. **The request guard is one modal dialog per request.** `GodAI.authorize_request` (`main.py:4467`) confirms and reserves one request and returns a token. There is no job-level reservation, so an unattended overnight run is impossible today without either one dialog per stage (not unattended) or bypassing the guard (forbidden).
8. **Reel and Herald are not needed.** The Shorts in the row are Press Shorts (still image plus voice). Reel renders and Herald posting are separate.

## Goal and success measure
One action on an approved Project version produces the EPUB, an audiobook, quote graphics, Shorts and a calendar, after exactly one confirmation that shows one total maximum cost. Every output is linked to the Project. Nothing is posted or submitted.

Measured by offscreen tests with `.env` scrubbed and fakes for every provider (no network):
1. A job on a fixture Project version produces: one EPUB matching its receipt SHA-256; one audiobook file; N PNGs; M MP4s, where M equals the calendar's Short slots; one calendar CSV covering the agreed window (question 2). Every file appears in `project_artifacts` for that Project. The run shows **exactly one** confirmation dialog.
2. Money: the sum of recorded usage rows for the job is ≤ the approved total, and each stage's rows are ≤ its own approved line. A test plants a fake that reports more and asserts it is capped and flagged, never silently charged above the line.
3. Unpriced: if any paid stage's rate is missing or 0 in `config/pricing.json`, the estimate shows "cannot be priced: <stage>", Start is disabled, no token is issued and every fake provider receives zero calls.
4. Caps: a total above what the session, daily, agent or project cap has left is refused before any stage starts (message names the cap, as §12 does today). A cap refusal mid-run pauses the job; no later stage calls a provider.
5. Resume: killing the process after stage k and relaunching resumes at stage k+1. Finished stages are not re-run; Booth's cached chapters are not re-billed.
6. Guard coverage: a contract test, in the style of `tests/test_request_estimate.py`, fails if any provider call in the job's code path is reachable without a job-scoped request token.
7. Existing tests pass unchanged; `test_database_migrations.py` covers the new table on an old database.

A real paid run (one short book, cheapest route) is part of Verify but **blocked** by the rejected keys.

## Scope

### Stages (fixed order; each records its outputs before the next starts)
0. **Freeze the source.** The selected approved version (`project_manuscripts`) plus its title and byline. Refuse if the Project has no approved version, or if title or byline is empty (the rule `export_approved` already enforces).
1. **EPUB.** `export_approved(..., "epub", ...)` into the job's output folder. Free, local.
2. **Audiobook.** Booth narration of that EPUB on the route, model and voice named in the approval. Paid.
3. **Quotes.** Quote suggestion on the model named in the approval. Paid on a cloud model, free on a local one.
4. **Calendar schedule.** `build_calendar` over the quotes for the agreed window and platforms. Free, pure.
5. **Quote graphics.** One per graphic slot (or per unique quote; question 4). Free, local.
6. **Shorts.** One per Short slot. Free with the on-device voice; paid per character with ElevenLabs.
7. **Captions and CSV.** Caption request on the approved model, then the CSV. Paid on a cloud model, free on a local one. A cut-off reply marks the stage incomplete (blank captions listed), not done.
8. **Link and report.** Record every file with `project_artifacts.record`, then write a job report: what ran, on which route, what each stage cost against its line, what is incomplete.

Stages 3–7 do not depend on stage 2. The job may run them while narration runs in its subprocess, but only if Architect shows this is safe for Qt threads (FFmpeg and audio threads once deadlocked the suite, 2026-10-05). Default: strictly sequential.

### What the single approval covers
One confirmation screen, shown once, lists:
- the source: Project, approved version number, word count;
- the output folder;
- each stage with its route (provider, model, voice), its basis (characters, minutes, tokens sent plus the 8,192 output cap, number of Shorts) and its **maximum** in EUR, or "local, no charge" for a stage that makes no provider call at all;
- the total maximum, and how much each cap (session, daily, Booth's and Press's agent caps, project cap) has left after reserving it;
- the paid-request assessment per paid stage, with **Apply** available only on this screen (Apply switches and re-estimates; it never sends).

The approval covers exactly those routes and those maxima. During the run, anything that would change them pauses the job and asks again in the morning, never during the night: a retired model, an unavailable route, a price that rose, a stage that would exceed its line, a routing-advisor hold. The job never switches route by itself.

### How the one estimate is built
- **Total = sum of each paid stage's maximum**, rounded up to the cent, with the same arithmetic the guard already uses: `usage_tracker.max_cost_eur` over every message for text stages; `per_unit_pricing` (`elevenlabs_tts_cost_eur`, `gemini_tts_cost_eur`, OpenAI per 1k characters) for speech.
- Stages whose input is not known at approval time are **bounded**: the caption request is priced at a maximum per-quote length times the number of slots plus the fixed prompt, plus the 8,192-token output reserve; Shorts narration at the number of Short slots times the maximum quote length. The job enforces those maxima when it builds the real request (it truncates or refuses rather than exceeding the bound).
- **Zero means unknown.** A missing or 0 rate for any paid stage blocks the whole estimate; it is never added as EUR 0. Only a stage that makes no provider call (Pillow, ffmpeg, EbookLib, macOS `say`, Ollama, LM Studio) is "local, no charge".
- **Dated rates:** a stage that may run after midnight is priced at the higher of the rates for today and tomorrow (Gemini TTS doubles on 2027-01-01, `dated_rate_usd`).
- The approved total is reserved against every cap at once. If any cap cannot hold it, nothing starts.

### Budget caps across the whole job
- The reservation is the job's, not a single request's. Each stage then authorizes against that reservation with its own token, without a dialog, and still passes the validator's caps. Usage rows keep the stage's real agent key (`author`, `audiobook`, `manuscript`) so per-agent reports stay true; the Run Log gains the job id.
- **Session cap:** session spend resets on restart. A resumed job re-reserves what it still has to spend, the way `video/jobs.py` restores its reservation.
- **Daily cap:** an overnight job crosses midnight. Question 6 asks which day's cap it counts against.

### Failure and resume
- A Qt-free job ledger (new table, additive migration) on the pattern of `video_jobs`: one job row (source version and SHA, routes, per-stage maxima, approved total, status) and one row per stage (status, spend state `reserved` / `recorded` / `partial` / `abandoned`, outputs with SHA-256).
- On launch, unfinished jobs are listed with what is done and what is left; resume is one click and stays within the original approval. Finished stages are verified (file present, SHA matches) and skipped.
- Booth's own chunk cache keeps paid chapters; a stopped narration records what was paid (`record_partial` semantics).
- A paid text stage cut off by a crash has an unknown outcome. Default proposal: record it at its maximum, mark it "verify", and never re-run it without a new approval (question 7).
- Stop is always available; it closes the current stage the way each agent does today and leaves the job paused, not deleted.
- Overnight means the app stays open and the Mac stays awake. The job may hold a macOS power assertion while it runs (question 8).

### Code areas (for Architect; not a design)
New Qt-free stage functions extracted from `agents/audiobook/panel.py` and `agents/manuscript/panel.py` (the quote list and captions currently live in widgets); a job runner and ledger (new module plus a table in `services/database.py`); a job-level reservation in the request guard (`main.py`, `services/api_limits.py`, `services/validator.py`); one confirmation screen; Project links for graphics, Shorts and the CSV. This touches state, concurrency and module boundaries: **Architect gate**. Secure is required (file writes, untrusted manuscript input, paid calls).

## Non-goals
- Posting or scheduling anywhere. Herald, Muse and their queues are not touched. The calendar is a CSV and a table.
- Retailer submission, including **PublishDrive** (its endpoint is untested against a live account). The Submission Ledger stays manual and self-reported.
- Any claim of income, sales, reach or publishing results, in the app, the report or the docs.
- Reel video renders, avatar video, music.
- A single release calendar replacing Press Calendar, Herald and Muse (that is #80), and the work-first navigation (#78).
- Translated editions (#84), a series bible (#83).
- Choosing the cheapest route automatically. The assessment advises; the owner approves.

## Invariants touched
- **Request guard:** no paid call outside it; every per-unit path (Booth TTS, ElevenLabs Shorts) stays priced through `per_unit_pricing` and capped. The new job reservation is a change to the guard itself.
- **Zero means unknown**, applied to the whole estimate.
- **No unverified claims;** PublishDrive out.
- **State:** a new table only through a tested additive migration; `APP_NAME` and paths unchanged.
- **Tests:** offscreen, temp DB, fakes, no network or real keys.
- **Qt threads:** workers stopped in tests; no new thread mix without Architect's say.
- **Narrow edits;** the panel extraction is the largest change and is stated here before Build.

## Smallest first slice
**Slice 1: the free path, no guard change.** Approved version → EPUB → quotes on a local model → schedule → graphics → Shorts with the on-device voice → captions on a local model → CSV → Project links → job report, with the job ledger and resume. The confirmation screen lists every stage and shows "local, no charge"; paid routes are not selectable yet. It can run end to end on this Mac today despite the rejected keys, and it proves the ledger, resume, links and the one-approval flow.
**Slice 2:** job-level reservation in the guard plus the paid audiobook stage (needs Architect approval; real-run verification waits for working keys).
**Slice 3:** paid cloud models for quotes and captions, and ElevenLabs Shorts.

## Open questions for the owner (Define gate)
1. **Freeze exception:** grant one for this feature, defer it until the readiness gate's baseline commit exists, or decline?
2. **Calendar window:** keep 4 weeks (28 days, what exists), or add a true 30-day option?
3. **Quote coverage:** keep the first 30,000 characters, or sample across the whole book? Whole-book sampling means more text requests and a higher maximum.
4. **Graphics count:** one graphic per graphic slot (about 34 for 4 weeks on all platforms), or one per unique quote?
5. **Default routes in the approval screen:** pre-select local models for quotes and captions and the on-device voice for Shorts, so that the only paid line by default is the audiobook?
6. **Daily cap at midnight:** count the whole job against the approval day's cap, or check each stage against the cap of the day it runs (which may pause the job after midnight)?
7. **Crash during a paid text stage:** record it at its maximum and require a new approval before re-running (proposed), or something else?
8. **Keep the Mac awake** while a job runs (power assertion), or leave sleep to the owner?
9. **Parallel stages:** allow quotes, graphics and Shorts to run while narration runs, if Architect shows it is safe, or keep it strictly sequential?
10. **Process:** run `/radar-check` and the read-only legal consult before Architect? The legal consult would cover disclosure of AI-generated narration and images where the owner later publishes them. That is a question for a person to decide, not an agent's opinion.
11. **Keys:** the paid slices cannot be verified until the rejected keys are replaced (`TODO.md` P1 `@me`). Is slice 1 alone worth building before that?

## Owner decisions (2026-11-18, Define gate)
Answered by the owner in chat on 2026-11-18; Define approved in the owner's words "Approve Define" (`docs/foundry/approvals.jsonl`).
1. **Freeze exception: granted** for this feature (like local-model routing, 2026-10-21).
2. **Calendar window: keep 4 weeks** (28 days, what exists). No 30-day option.
3. **Quote coverage: sample the whole book**, in fixed-size windows spread across the approved version, not the first 30,000 characters only.
4. **Graphics: one per unique quote.** Each graphic slot points to its quote's graphic.
5. **Default routes: local by default.** Quotes and captions pre-select a local model, Shorts the on-device voice; the audiobook is the only paid line by default. Cloud routes stay selectable on the one screen.
6. **Daily cap: the approval day's.** The whole approved total is reserved against the daily cap of the day the owner approves; the job does not pause at midnight.
7. **Crash in a paid text stage: record at its maximum, mark "verify", and re-run only after a new approval.**
8. **Keep the Mac awake** with a power assertion while a job runs; released when the job ends or pauses.
9. **Strictly sequential stages.** No stage runs in parallel with narration.
10. **Radar check and legal consult: run before Architect.**
11. **Build slice 1 (the free path) first**, before the rejected keys are replaced. Architect still designs the slice-2 guard change.

Not decided at this gate: the `SUGGESTIONS.md` #79 status (left at IDEA; the owner did not ask to change it) and the spec's priority.

## Risks
- **The guard change is the riskiest part.** A job-level reservation that leaks, double-counts or survives a cancel would spend money outside what was approved. Mitigation: Architect gate, contract test 6, mutation checks on the reservation logic.
- **Extracting the panel logic** (Booth's estimate and resume dialogs, Press's widget-held quotes) could change today's behaviour. Mitigation: the existing panel tests must pass unchanged; the extraction lands before the job uses it.
- **An unattended run meets a condition that today shows a dialog** (settings changed since an interrupted book, a retired route). Mitigation: every such case pauses the job; no dialog runs at night.
- **Cut-off captions** for a 56-slot calendar. Mitigation: mark the stage incomplete. Splitting the request is a possible follow-up that would raise the estimate.
- **Price drift between approval and run.** Mitigation: re-check the rate at stage start; if it rose above the line, pause.
- **Scope creep toward posting.** Mitigation: non-goals above; no Herald or Muse code in this change.
