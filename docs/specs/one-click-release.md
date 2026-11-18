# Spec: One-click release (approved manuscript → release kit overnight)

Status: **Define approved by the owner 2026-11-18 (freeze exception granted); Design and Architect in progress.** Source: `SUGGESTIONS.md` #79 (portfolio review 2026-11-18). Priority: not set (owner). Product-manager playbook: `status: current`, last-reviewed 2026-10-14.

> **Feature freeze (2026-10-09) applies.** `TODO.md` allows bug fixes, tests and wording only until `tests/READINESS_GATE.md` §3 A–E are ticked on one commit. This feature needs an explicit owner exception, like local-model routing got on 2026-10-21. Declining it is a valid outcome of this gate.
>
> **No paid stage can be tested today.** `TODO.md` P1 `@me`: the Anthropic, Gemini and DeepSeek keys in `.env` are rejected by their providers (found 2026-10-09), and `OPENAI_API_KEY` is unset. Every Booth narration route is paid (OpenAI, Gemini, ElevenLabs). Until that owner item is done, only the free stages can run for real; paid stages can be built and tested only against fakes.

`/radar-check` and the read-only legal consult ran after the Define gate (owner decision 10); findings in `docs/foundry/radar-notes/2026-11-18-one-click-release.md` and `docs/audit/one-click-release-legal-consult.md`.

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

## Design (ux-designer, 2026-11-18)
Playbook `ux-designer`: `status: current`, last-reviewed 2026-11-11. Read: `ui/forms.py`, `ui/theme.py`, `ui/project_overview.py`, `services/money_text.py`, `services/validator.py` (refusal wording), `agents/audiobook/panel.py` (`start_conversion`, `resume_pending_conversions`), `agents/manuscript/panel.py` (approved-version row), `main.py` (`authorize_request`, `confirm_external_api_request`, `_assessment_text`). **UNVERIFIED:** `docs/audit/one-click-release-radar.md` and `-legal-consult.md` are not in this worktree, so no copy below is checked against them (for example an AI-disclosure line). Euro figures in examples are illustrative.

**The user's question:** "What will this make, what is the most it can cost, and can I leave it overnight?" **The one primary figure:** the total maximum, "Up to €7.69", or "No charge" when every step runs on this Mac.

**Wording rules** (as the guard already does): a maximum is "up to €x" (`money_text.up_to`, rounds up); an amount left is "€x left" (`money_text.left`, rounds down); a recorded amount uses `money_text.paid` ("under €0.01", never "€0.00"). Never "estimated", never "exceeded" (nothing is spent at a refusal). Short sentences. No claim of income, sales, reach or results. Agents by codename (Press, Booth). Layout is the aligned form: `section()` headings, `field()` labels above inputs, spacing 4/8/16/24, 32-px controls. Colour: `WARNING` for a paid line, `DANGER` for a blocking reason, muted for local; every state is also a word.

### D1. Entry point
- **Start:** a **Make Release Kit…** button in Press, Quote Finder tab, on the approved-version row right after "Export Approved…" (`agents/manuscript/panel.py:344-378`). The kit uses the version selected in that row's combo.
- **Project Overview** stays read-only (its docstring says so). Its summary line gains "Release kit: none" / "v3 running, step 2 of 8" / "v3 paused, needs you" / "v3 made 19 Nov", and a **Release Kits…** button that opens the window in D3.
- When this Project has a running or paused kit, the Press button reads **Open Release Kit…** and opens D3 instead.
- When the button is disabled, the reason is a visible note under the row (`field_note`) and the button's accessible description. A tooltip alone is not enough: a disabled button cannot take keyboard focus.

| Condition | Note text |
|---|---|
| No Project selected | "Select a Project to make a release kit." |
| No approved version | "Approve the Write draft first. A release kit is made only from an approved version." |
| Selected version has an empty title or byline | "Version 3 has no title or byline. Set them in the Project, then approve a new version." (same rule and words as `export_approved`) |
| A kit is running for another Project | "A release kit is running for <Project>. One kit runs at a time." |

### D2. The one confirmation screen: "Make Release Kit"
A modal dialog. It is not a `QMessageBox` because each row needs its own controls. The dialog is about 720 px wide and shows, top to bottom:

1. **Primary figure** (`StatValue` style): "Up to €7.69", caption "TOTAL MAXIMUM FOR THIS KIT". All local: "No charge", caption "EVERY STEP RUNS ON THIS MAC".
2. **Source:** "From <Project>, approved version 3 · 84,210 words · <Title> by <Byline>".
3. **Output folder:** the path and a **Change…** button. By default it is a new folder named `<Title>_v3_<date>` under the folder Export Approved already uses (`user_data_base()`). Note: "A new folder. Nothing in it is overwritten."
4. **STEPS** table, one row per step. Columns: Step · Route · Basis · Maximum.

| # | Step | Route (default) | Basis shown | Maximum |
|---|---|---|---|---|
| 1 | EPUB | "EbookLib, on this Mac" | "1 file from version 3" | local, no charge |
| 2 | Audiobook | route and voice combos; Booth's current route and voice | "512,300 characters · about 9 h 40 min of audio" | up to €7.69 |
| 3 | Quotes | model combo; first local model | "Up to 20 quotes from 12 passages across the whole book · replies capped at 8,192 tokens each" | local, no charge |
| 4 | Calendar | "4 weeks (28 days)" (fixed text), Start date (as Press Calendar: today), chips TikTok / Instagram / Pinterest, all on | "56 posts: 22 Shorts, 34 graphic posts" | local, no charge |
| 5 | Quote graphics | "On this Mac" | "One per unique quote: up to 20" | local, no charge |
| 6 | Shorts | voice combo; "On-device voice (macOS)" | "22 Shorts, narration up to <max> characters each" | local, no charge |
| 7 | Captions and CSV | model combo; first local model | "56 captions in one request · reply capped at 8,192 tokens" | local, no charge |
| 8 | Link and report | "On this Mac" | "Every file linked to <Project>" | local, no charge |

   Passage count and maximum quote length are Architect's numbers. Any change on this screen re-estimates the whole screen.
5. **Assessment** under each paid row, in the guard's own words (`_assessment_text`, `_media_assessment_text`, `_rating_assessment_text`):
   - Best fit: "Assessment: your choice is the best fit among the providers you have permitted (82/100)."
   - Not best: "Assessment: best fit is Gemini · gemini-3.8-flash-tts, up to €3.90. Your choice: 74/100, up to €7.69." followed by an **Apply** button.
   - Apply switches that row's route and re-estimates. It never sends. The line then reads "Applied: Gemini · gemini-3.8-flash-tts. Figures updated. Nothing was sent." Focus returns to that row's route combo.
6. **CAPS AFTER THIS KIT** table (shown only when something is paid). Columns: Cap · Left now · This kit reserves · Left after. Rows: Session; Today (18 Nov); Booth; Press; Project "<name>". A cap that is not set reads "no cap set". A row that cannot hold the kit reads "Not enough" in its last cell. Note: "The whole maximum is reserved against today's cap, even for steps that run after midnight. A step that may run after midnight is priced at the higher of today's and tomorrow's rate."
7. **Notes** (micro text):
   - "Steps run one at a time, in this order."
   - "Imprint keeps this Mac awake until the kit finishes or pauses. The display may sleep. Keep the Mac plugged in with the lid open." Architect: confirm that the chosen power assertion does not hold the Mac awake with the lid closed.
   - "If a route or a price would change, the kit pauses and waits for you. It never switches route by itself and never asks during the night."
   - "Nothing is posted, scheduled or submitted. The calendar is a CSV file."
8. **Buttons:** Cancel · **Start**. Start is labelled "Start" when everything is local and "Start (up to €7.69)" when something is paid. Any blocking reason sits on one line above the buttons, starting "Cannot start:".

| State | What the screen shows | Start |
|---|---|---|
| Estimating (on open, after any change) | Figure "Estimating…"; Maximum cells "…"; note "Counting the book and checking prices." | disabled |
| All local | "No charge". Instead of the caps table: "No cap is used: no step calls a paid provider." | "Start" |
| One paid line (default from slice 2) | "Up to €7.69"; caps table | "Start (up to €7.69)" |
| Cannot be priced | Maximum cell "cannot be priced"; figure "Cannot be priced: Audiobook"; "Cannot start: Audiobook cannot be priced. ElevenLabs · eleven_multilingual_v2 has no rate in config/pricing.json, and 0 means unknown, not free. Add a rate in Settings → Pricing, or choose another route." With more than one: "Cannot be priced: Audiobook, Captions and CSV." | disabled |
| A cap cannot hold the total | That row reads "Not enough"; "Cannot start: this kit can cost up to €12.40, and today's cap has €5.00 left (of €10.00). Choose cheaper or local routes, or raise Daily € under Limits." Each cap uses the validator's own remedy. The message names the first failing cap in the validator's order; every failing row is marked. | disabled |
| Key missing / provider switched off | "Cannot start: the OpenAI route needs OPENAI_API_KEY, which is not set. Add it in Settings, then restart Imprint, or choose another route." / "Cannot start: OpenAI is switched off under API permissions." | disabled |
| No local model answers | "Cannot start: no local model answered. Start Ollama or LM Studio, then press Check again." A **Check again** button appears. | disabled |
| Output folder unusable | "Cannot start: <folder> already has files. Choose a new folder." / "Cannot start: Imprint cannot write to <folder>." | disabled |
| Caps or prices changed while open | When Start is pressed, the screen re-validates. If anything moved, it stays open: "Caps or prices changed since this screen opened. Check the figures, then press Start again." | enabled after refresh |
| **Slice 1** | The Audiobook row stays visible so the kit's shape is honest: Route "Not included", Basis "Narration is always paid, and this screen cannot approve paid steps yet. Narrate in Booth.", Maximum "—". The Quotes and Captions combos list local models only; the Shorts voice is on-device only. Note under the table: "This version runs local steps only. Cloud models and ElevenLabs are not offered here." Figure "No charge"; no caps table. | "Start" |

### D3. Running: the "Release Kits" window
- A non-modal window. It opens on Start (the confirmation closes), from **Open Release Kit…** in Press, from **Release Kits…** in Project Overview, and at launch (D4). Closing it never stops a kit. A note while running says so: "Closing this window does not stop the kit."
- **Headline:** "Step 2 of 8: Audiobook". Caption: "<Project> v3 · started 22:14". Under it, the step's own progress as a bar *and* text: "Chapter 4 of 31".
- **Step table** (Step · State · Spent · Line). States in words: Waiting, Running, Done, Done earlier (verified on resume), Paused, Incomplete, Verify, Not included. Spent uses `paid`; Line is "up to €7.69" or "local, no charge".
- Note while running: "This Mac stays awake while the kit runs. The display may sleep." When the kit ends or pauses: "This Mac may sleep again."
- **Stop** (shown only while running) has no confirmation, because it deletes nothing. First it shows "Stopping after the current item…", then "Paused by you. Finished steps stay done. Resume continues from Shorts." During Audiobook the stop line is "Stopping Audiobook. Narrated chapters are kept and recorded." Other buttons: Show Folder, Close.
- **Quitting Imprint while a kit runs** (the owner is present, so a dialog is fine). Title "A release kit is running". Text "Quitting pauses it. Finished work is kept, and you can resume next time you open Imprint." Buttons: **Keep Running** (default, Escape) and Quit and Pause. UNVERIFIED: how cleanly the narrator subprocess stops on quit is Architect's to confirm.

### D4. Resume list on launch
- At launch, if any kit is unfinished, the Release Kits window opens once: non-modal, no sound. Launching the app is the owner's own action, so this is not a night-time prompt.
- Each unfinished kit row reads "<Project> v3 · started 18 Nov, 22:14 · paused at Shorts". The detail below it:
  - "Done: EPUB, Audiobook, Quotes, Calendar, Quote graphics."
  - "Left: Shorts, Captions and CSV, Link and report."
  - "Left to spend: up to €3.10 of the €7.69 you approved." (all local: "Left to spend: nothing, every remaining step is local.")
  - The pause reason from D5.
- **Resume** is one click with no dialog, and stays within the original approval. It first shows "Checking finished files…" (file present, SHA matches) and skips verified steps ("Done earlier").
- **Session cap cannot hold the rest:** an inline line under the row: "Cannot resume yet: this kit still needs up to €3.10, and your session cap has €2.00 left (of €5.00). Raise Session € under Limits and press Save Limits, then press Resume." Resume stays enabled; each press checks again.
- **A finished file is missing or changed:**
  - Local step: "Quote graphics will run again: 2 of its files are missing or changed." Resume stays the action.
  - Paid step: "The audiobook file is missing or changed. Making it again costs up to €7.69, so it needs a new approval." Action: Review and Approve…
- **Discard** (secondary button) asks first. Title "Discard this release kit?". Text "Nothing more will run for it. Files already made stay in <folder> and stay linked to <Project>. Spending already recorded stays recorded." Buttons Discard and **Cancel** (default, Escape).
- **Review and Approve…** opens D2 titled "Approve Remaining Steps". Finished steps show as "Done" with no controls, and only the remaining steps are priced and reserved. This is a new approval.

### D5. Paused states (no dialog at night)
Each pause appears only in the Release Kits window and in the report, plus the Press and Overview status line "Release kit v3 paused, needs you". The power assertion is released. There is one action per state.

| Cause | Message | Action |
|---|---|---|
| Retired model | "Paused before Audiobook: OpenAI retired gpt-4o-mini-tts on 6 Jan 2027. Nothing was sent on it. Choose another route to continue." | Review and Approve… |
| Route unavailable | "Paused during Quotes: Ollama did not answer (connection refused). Nothing more was sent. Start it, then resume." For a paid route: "OpenAI refused the request (key rejected)." | Resume |
| Price rose above the line | "Paused before Audiobook: its rate in config/pricing.json rose since you approved. It can now cost up to €8.40, above its approved €7.69. Nothing was sent." | Review and Approve… |
| A step would exceed its line | "Paused during Captions and CSV: the request is larger than approved (up to €0.52 against its €0.40 line). Nothing was sent." | Review and Approve… |
| Routing-advisor hold | "Paused before Quotes: the routing advisor says <model> may fall short for this step (<advisor's reason>). Nothing was sent. Keep it or choose another model." | Review and Approve… |
| Cap refusal mid-run | "Paused before Captions and CSV: your session cap has €1.00 left (of €5.00), and this step can cost up to €1.40. Nothing was sent. Raise Session € under Limits and press Save Limits, then resume." The validator's wording and remedy, per cap. | Resume |
| Crash during a paid text step | State **Verify**. "Needs checking: Imprint stopped while Captions and CSV was waiting for Anthropic's reply. Whether it was charged is unknown, so it is recorded at its maximum, €0.40. Compare with your Anthropic usage page. This step runs again only after you approve it again." | Review and Approve… |
| Booth settings changed since an interrupted book | "Paused before Audiobook: Booth has an unfinished narration of this book with other settings (Gemini, voice Kore, chunk size 2,000; 12 of 31 chapters saved). The kit will not choose between them for you." In the re-approval, the Audiobook row then offers "Reuse the 12 saved chapters (original settings)" or "Start again with these settings (whole book at full cost)", the same choice as Booth's own dialog. | Review and Approve… |
| Mac slept / Imprint quit | "Interrupted: Imprint closed or the Mac slept during Shorts. 9 of 22 Shorts are made and kept." For Audiobook: "Narrated chapters are kept; you pay only for the rest." UNVERIFIED: whether sleep can be told apart from a quit; until it can, the wording names both. | Resume |

### D6. Job report
- **Where:** the window shows it when the kit finishes, and through **Show Report** on any kit. It is saved as `release-kit-report.md` in the output folder, rewritten at every pause and at the end, and linked to the Project (kind `release_kit_report`). Kit files appear in Overview's Files tab labelled "Release kit v3 · <file name>".
- **Content (headings and lines as written):**
  - Title line: "Release kit: <Title>, version 3"
  - "Project: <name> · source SHA-256 <first 12 characters> · 84,210 words"
  - "Started 18 Nov 2026, 22:14 · ended 19 Nov 2026, 03:52 · <state>". State is one of: "Made", "Made, with items to check", "Paused", "Discarded".
  - A table with columns Step · Route (provider · model · voice) · Result · Cost · Approved line. Example rows: "Done, 31 chapters"; "Incomplete, 42 of 56 captions"; "€7.12 | up to €7.69"; "local, no charge"; "€0.40 (at maximum, check)".
  - "Total recorded: €7.12 of up to €7.69 approved."
  - **Incomplete:** for example "Captions and CSV: 14 of 56 posts have no caption. The reply stopped at the 8,192-token limit. Write them in Press → Calendar, or approve this step again." Any truncation applied to stay within a bound is also listed, for example "Shorts: 3 quotes were shortened to <max> characters for narration."
  - **Check:** each Verify item with its recorded maximum and the provider whose usage page to compare.
  - **Files:** each path, all linked to <Project>.
  - Last line: "Nothing was posted, scheduled or submitted."

### D7. Accessibility and keyboard (WCAG 2.2 AA by analogy, per playbook)
- **Confirmation, focus order:**
  1. Output folder Change…
  2. Each step row, top to bottom; within a row, route, then voice, then Apply.
  3. Calendar Start date.
  4. Platform chips.
  5. Check again (when shown).
  6. Cancel.
  7. Start.

  Initial focus is the first editable control (Audiobook route; in slice 1, the Quotes model). Start is the default button, so Return starts, as in the guard's dialog; when Start is disabled, Return does nothing. **Escape = Cancel**: nothing is reserved or written.
- **Release Kits window:** initial focus goes to the selected kit's one action (Stop, Resume or Review and Approve…). **Escape closes the window and never stops or discards.** Cmd-period = Stop while running. In Discard and quit-while-running, the safe button is the default and Escape chooses it.
- **Accessible names:**
  - Combos: "Audiobook route", "Audiobook voice", "Quotes model", "Shorts voice", "Captions model", "Calendar start date".
  - Apply buttons: "Apply suggested route for Audiobook".
  - Each step row reads as one string: "Audiobook, OpenAI gpt-4o-mini-tts, voice alloy, up to €7.69".
  - Start's description: "Starts all 8 steps. Up to €7.69 in total."
  - Progress bar: "Audiobook progress, chapter 4 of 31".

  Spoken announcements of state changes (`QAccessibleAnnouncementEvent`) need Qt 6.8 or later; the installed PySide6 version is unpinned, so this is UNVERIFIED. Without it, the headline label's text change is the signal.
- **Colour is never the only signal:** each state is a word; paid lines say "up to €"; blocked rows say "Not enough" or "cannot be priced"; every blocking reason is a sentence.
- **Contrast:** text needs at least 4.5:1. The progress-bar fill against its track, focus rings and control borders need at least 3:1. The app has no contrast test today (`tests/test_theme.py` computes no luminance ratio), which the playbook requires: a QA item for Verify. Controls are 32 px, above the 24-px minimum target. Money figures and reasons wrap and are never cut off, down to a 640-px-wide window.

## Risks
- **The guard change is the riskiest part.** A job-level reservation that leaks, double-counts or survives a cancel would spend money outside what was approved. Mitigation: Architect gate, contract test 6, mutation checks on the reservation logic.
- **Extracting the panel logic** (Booth's estimate and resume dialogs, Press's widget-held quotes) could change today's behaviour. Mitigation: the existing panel tests must pass unchanged; the extraction lands before the job uses it.
- **An unattended run meets a condition that today shows a dialog** (settings changed since an interrupted book, a retired route). Mitigation: every such case pauses the job; no dialog runs at night.
- **Cut-off captions** for a 56-slot calendar. Mitigation: mark the stage incomplete. Splitting the request is a possible follow-up that would raise the estimate.
- **Price drift between approval and run.** Mitigation: re-check the rate at stage start; if it rose above the line, pause.
- **Scope creep toward posting.** Mitigation: non-goals above; no Herald or Muse code in this change.
