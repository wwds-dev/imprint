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

## Architecture (architect, 2026-11-18)
Playbook `architect`: `status: current`, last-reviewed 2026-10-14 (35 days, not stale). Read at `6630397`: app-context, ADRs 0001–0004, the radar note, `docs/audit/one-click-release-legal-consult.md` (L1–L14, added mid-phase by the coordinator), and the code cited below. Measured with the app venv (read-only): SQLite **3.53.1** (past the 3.51.3 WAL-reset fix, radar #2); a default `get_connection()` in WAL mode reports `synchronous=2` (FULL) and `busy_timeout=5000`; PySide6 **6.11.2**. ADR: `docs/adr/0005-job-level-reservation.md` (Proposed).

### A0. What the code does today that shapes this design
| # | Fact | Where | Consequence for the kit |
|---|---|---|---|
| F1 | `authorize_request` validates, shows `confirm_external_api_request` (a `QMessageBox`), then stores the token context only in memory (`_pending_requests`). | `main.py:4467-4580`, `:4340-4407` | A second modal per paid request; a crash loses every reservation. |
| F2 | A refused request shows a dialog: the local-fallback offer or "Request Blocked". | `main.py:4532-4536` | Any refusal at night would open a dialog. The job path must never reach these. |
| F3 | Session and daily checks add `_reserved_in_flight_eur()`; agent and project checks do **not**. | `main.py:4517-4530`; validator `services/validator.py:138-163` | A long-lived job reservation must also count in the agent and project checks, or the Booth agent cap can be passed while the kit holds money. |
| F4 | The token's project, the estimate's project instructions and the chat worker's instructions all come from the **active** Project. | `main.py:4568-4569`, `:567-574`, `:3801-3807`, `:4457-4465` | If the owner switches Project during the night, usage rows, the project cap and the prompt would follow the UI. The kit must pin its own Project. |
| F5 | `estimate_chat_cost` returns €0 for an unpriced cloud model ("still estimates €0 (B-F5)"). `max_cost_eur` returns None. `resolve_price_row` ignores 0-rate rows and may fall back to the provider's `default` row. | `main.py:576-595`; `services/usage_tracker.py:46-73`; `services/pricing_catalog.py:127-155` | The kit estimator calls `max_cost_eur` directly and treats `None` or ≤0 as unknown. It never calls `estimate_chat_cost`. |
| F6 | `record_request` bills real usage with no ceiling; `record_partial` clamps to the confirmed reserve. | `main.py:5310-5363`, `:5374-5422` | Job items need a clamp: success measure 2. |
| F7 | `_resolve_request` falls back to "oldest request for this agent name". | `main.py:5270-5291` | A job token in `_pending_by_agent` could be taken by a Press or Booth by-name call. Job tokens are never put there. |
| F8 | Daily, agent and project totals are summed by the `usage.timestamp` date. | `services/usage_tracker.py:199-227` | Spend recorded after midnight lands on the next day (A2). |
| F9 | Booth bills by chunk fraction of a flat estimate. A dead `running` row is settled at the next launch by Booth's own scan, which logs a usage row. | `agents/audiobook/conversions.py:119-159`; `agents/audiobook/panel.py:996-1097` | The kit reuses this. Kit recovery must run **before** Booth's scan, or that spend is logged without the job id. |
| F10 | The routing advisor applies only to `ADVISED_AGENTS = ("author", "social", "webdesign", "fiverr")`. | `ui/panel_routing.py:36-67, 88-128` | Today a hold can never fire for `manuscript` or `audiobook`. The kit still asks (hook), so a later change to that list takes effect. |
| F11 | `video_jobs` writes an intent row before the paid POST. `sweep_lost` **releases** a row with no job id. `restore_request` re-mints a reservation without re-validating. | `agents/video/jobs.py:28-133`; `main.py:5242-5268` | The kit follows the intent-row pattern but **not** the release-on-unknown rule: decision 7 records at the maximum. Resume re-validates, because unstarted stages have spent nothing. |
| F12 | Narration runs as a `QProcess` (`--narrator-worker` when frozen). Stop is `kill()`. `closeEvent` kills Booth's process and waits up to 2 s on named workers. | `agents/audiobook/panel.py:813-842, 1133-1143`; `main.py:6266-6300` | The kit drives its own `QProcess` and its own worker attribute, and both join the quit sweep. |
| F13 | Press keeps quotes only in widgets (`_calendar_quotes_from_finder` reads `QLabel`s). The CSV writer and the caption fill sit inside panel methods. | `agents/manuscript/panel.py:1500-1508, 1570-1582, 1682-1699` | These are the extraction targets (A5). |
| F14 | `render_short` picks its voice from the environment: ElevenLabs if `use_elevenlabs` and a key is set, else macOS `say`. | `agents/manuscript/shorts_generator.py:27-47` | The kit passes an explicit voice provider, so the route is a job field (legal L1). |

### A1. Job-level reservation in the request guard (slice 2; designed now)
**Data model (in memory, Qt-free): `services/job_reservation.py`.** `ReservationBook` holds `JobReservation(job_id, project_id, budget_day, lines)`. Each `Line` is `(stage, agent, provider, model, approved_eur, remaining_eur, open: {token: granted_eur}, recorded_eur)`. Invariant, checked after every operation and pinned by tests:
`recorded + Σ open + remaining == approved` for each line (to the micro-euro), with every term ≥ 0.
GodAI keeps one book. Its job-path methods are thin wrappers around the book, the validator and `usage_tracker`. **No job-path method opens a dialog.** Each returns a token or a `JobRefusal(scope, reason)` whose `reason` is the validator's own sentence.

| API (GodAI) | When | Does |
|---|---|---|
| `estimate_job(plan) -> JobEstimate` | D2 open and every change | Per-stage maximum, basis and notices; `blocked` lists every unpriced stage. Pure apart from price reads. |
| `authorize_job(plan, shown_estimate) -> JobAuthorization \| JobRefusal` | D2 **Start**, the one modal's accept | Re-estimates. If it differs from `shown_estimate` → refusal "Caps or prices changed…". Validates (below), writes the ledger approval, then `book.reserve(...)`. |
| `authorize_job_item(job_id, stage, item_key, *, provider, model, messages=… \| flat_cost_eur=…) -> token \| JobRefusal` | Before each provider call, GUI thread | Route must equal the approved route. Price must be known. Item maximum ≤ line remaining. Validator re-check (below). Moves `granted` from `remaining` to `open`. Mints a child token whose context carries `job_id`, `job_stage`, `job_item`, the **job's** Project and `estimated_cost = granted`. Not added to `_pending_by_agent`. |
| `record_job_item(token, response, usage) -> entry` | Item finished | Bills like `record_request`, then clamps: recorded = `min(actual, granted)`. If actual > granted, or actual is 0 on a paid route, the row is recorded at `granted`, gets `cost_type='capped'` and is flagged for the report. Returns `granted − recorded` to the line. Writes `usage.job_id` and `usage.job_item`. |
| `close_job_item_partial(token, cost_eur, status)` | Stop or failure of a render or narration | `record_partial` semantics (clamped to `granted`), plus the job columns; the remainder goes back to the line. |
| `void_job_item(token)` | Refused before sending (e.g. a builder bound check) | Returns `granted` to the line; no row. |
| `release_job_stage(job_id, stage)` / `release_job(job_id)` | Stage done; pause, stop, discard or end | Sets `remaining` to 0, so unspent money goes back to the caps at once. `release_job` with an open token keeps only that token's amount until the item resolves. |

`_reserved_in_flight_eur()` becomes the sum over `_pending_requests` (child tokens included) plus `book.remaining_total()`. Because a grant moves money from `remaining` to `open`, nothing is counted twice. A new `_reserved_for(agent=…, project=…)` feeds the agent and project checks for **every** request while a job holds money (fixes F3 for jobs; ordinary single requests stay as they are, owner question 9).

**Validation.** At `authorize_job`, the validator runs once per distinct agent (enabled, permission, `requires_approval`, agent cap with that agent's lines as the estimate) and once for the total (session, daily and project caps of the **job's** Project). The D2 caps table is computed from the same figures. The "Cannot start" line uses the first failing scope in the validator's order (`validator.py:92-200`). At each grant, the guard asks: **does this job's unspent reservation still fit, given everything else in flight?** The estimate is the job's remaining plus open; the costs exclude this job's own amounts. A cap lowered mid-run (Save Limits), a provider unticked or an agent disabled refuses the grant, and the job pauses before the item (success measure 4). The daily check is skipped once `today != budget_day` (decision 6, A2), via a new keyword `Validator.validate(..., check_daily=True)`. Its default keeps every existing call unchanged.

**Exactly one modal.** The D2 dialog is the job's only modal. The job path never calls `confirm_external_api_request`, `_offer_local_fallback` or `QMessageBox`. Assessments are computed for D2 rows with `_assess_safely` / `assess_media_request` (`main.py:1728`). D2's **Apply** changes the D2 row only and never calls `_switch_agent_setup` (`main.py:1857`): the agent's selection is never changed (ADR 0004). This **amends ADR 0004's "every paid job still meets the paid-request dialog"** for job child tokens only; see ADR 0005.

**Zero means unknown, over the whole estimate.** `estimate_job` prices text stages with `max_cost_eur` (F5) and speech with `per_unit_pricing`. `None` or ≤0 on a non-local route puts the stage in `blocked`. `blocked` is non-empty → Start disabled, and `authorize_job` refuses again even if called directly (defence in depth; success measure 3). A row priced from the provider's `default` row (F5) counts as priced, the way the guard treats it today, but the Basis cell names it ("priced at <provider>'s default rate").

**Bounded estimates, enforced at request build time.** These are Architect's numbers for D2 (Design asked):

| Stage | Bound | Priced input | Enforcement |
|---|---|---|---|
| Quotes | 12 passages × 2,500 characters, **one** request, up to 20 quotes | ≤ 32,000 characters (passages, labels, `QUOTE_SUGGESTION_PROMPT`) → `chars // 4` tokens + full output reserve | The builder raises `BoundExceeded` if `estimate_input_tokens(messages)` exceeds the bound → `void_job_item`, pause "would exceed its line". |
| Maximum quote length | **280 characters** | — | Parser drops longer quotes (never truncates, so quotes stay verbatim). It also drops quotes not found verbatim in their passage (whitespace and curly quotes normalised) and duplicates (casefold). |
| Captions | 56 slots × 600 characters (280 × 2 for worst-case JSON escaping + 40 for keys) + prompt | ≤ 35,100 characters → tokens + full output reserve | The kit serialises with `ensure_ascii=False` and checks the bound before the grant. A cut-off reply → stage **Incomplete**, not paused. |
| Shorts (ElevenLabs, slice 3) | Short slots × 280 characters at the model's per-1k rate | per-character | Each item is priced from its real quote (≤ 280) and checked against the line remaining. |
| Audiobook | Characters of the EPUB text that `load_text` returns, on the route's rate | per route (`agents/audiobook/panel.py:582-600`) | Re-estimated from the real EPUB at stage start (A1, price re-check). |

Design copy follow-ups for ux-designer: D2 Quotes basis becomes "Up to 20 quotes from 12 passages across the whole book · one reply capped at 8,192 tokens". D6's "quotes were shortened" line becomes "N suggested quotes were longer than 280 characters and were not used."

**Price and route re-check at stage start.** Before a paid stage's first grant, the runner re-runs that stage's estimator at today's prices. Pause before sending if any of these holds:
- the new maximum exceeds the line remaining ("price rose");
- the model is retired (`offered_routes(today)`, `agents/audiobook/panel.py:59-68`; `media_catalog` dates);
- the key is missing or the provider is switched off;
- the advisor, for an eligible agent, would not run the approved model (F10).

The job never switches route by itself.

**Dated rates.** New `per_unit_pricing.max_dated_rate_usd(table, model, days)` takes the maximum of `dated_rate_usd(table, model, today=d)` over `days` (`services/per_unit_pricing.py:187-209` already accepts `today`). `days` = {budget day, budget day + 1} at approval and resume; {today, tomorrow} at the stage-start re-check.

**Idempotency and crash between reserve and record.** The reservation lives only in memory and dies with the process. Daily, agent and project totals come only from `usage` rows, and the session total resets on restart (`main.py:375`). So a crash cannot leak a reservation into a later process. What must survive is the **intent**. For every paid item the ledger writes `release_job_items.state='intent'` (with `granted_eur`) in its own committed transaction **before** the provider call. It writes the usage row with `(job_id, job_item)`, then `state='done'`. A partial unique index `usage(job_id, job_item) WHERE job_id != ''` makes a second row for the same item impossible. At launch, recovery (A4) resolves each `intent` item:
- **(a)** a usage row exists → adopt it; no second charge;
- **(b)** no row, paid text or per-unit item → insert one row at `granted`, `cost_type='unverified_max'`, item and stage **Verify** (decision 7);
- **(c)** local item → back to planned; it costs nothing to redo;
- **(d)** audiobook → settle from the chunk counts (A4).

| Hazard | Prevented by |
|---|---|
| **Leak** (money stays reserved after the job stops using it) | `release_job_stage` on every stage end. `release_job` on every non-running transition (one state-machine exit hook; tested per transition). `book.assert_consistent()` after each operation. |
| **Double count** | The grant moves money rather than copying it. A token pops once. The usage unique index. Recovery checks for a row before recording at the maximum. Booth's settle-before-log order (`panel.py:1010-1013`) is kept. Kit recovery runs before Booth's scan (F9). |
| **Surviving a cancel** | Stop: let the current item finish (text, Short, graphic), or kill and close-partial the narration. Then `release_job`. Discard releases and marks the job `discarded`. The book refuses grants for a job that is not active. |

**Usage and Run Log rows.** Rows keep the stage's real agent key (`manuscript` for EPUB, quotes, captions and Shorts; `audiobook` for narration), so per-agent reports and the agent caps stay true. They gain `job_id` and `job_item` (additive, A4). `run_logger.start` gains an optional `job_id`, written to a new `runs.job_id`.

### A2. Daily cap (decision 6) and the open Design question
**Rule proposed: a job's budget day is the day of its latest approval or resume.**
- At approval: the whole maximum is validated against that day's daily cap (decision 6).
- During the run: grants skip the daily check once the date passes the budget day, so the job never pauses at midnight.
- Usage rows keep their real timestamps (F8). Spend after midnight therefore appears in the next day's total, as does the job's still-reserved remainder. Other requests that day see both: the safe direction.
- A paused job resumed on a **later** day is a new owner action. Its remaining maximum is re-validated against **the resume day's** caps (all of them, not only the session cap; see A3). That day becomes its budget day.
- **Alternative (not recommended now):** a `usage.budget_day` column, so the job's spend counts only against the approval day. It matches decision 6 more literally, but every cap query (`usage_tracker.py:199-227`) and every report would change. Owner question 2.

### A3. Session-cap re-reservation on resume
The session total is in memory and resets on restart (`main.py:375`). Pattern from `video/jobs.py` and `restore_request` (`main.py:5242-5268`), with one deliberate difference.
- The video path never re-validates, because its money is already committed at the provider.
- A kit's remaining stages have sent nothing, so resume **re-validates and re-reserves** the remaining maximum through `authorize_job(..., resume=True)`, which writes no new approval:
  - the remaining paid lines, minus `recorded_eur`;
  - the audiobook line at the estimate × `conversions.remaining_fraction(row)`;
  - excluding Verify stages, which need a new approval.
- If any cap cannot hold it, the D4 inline "Cannot resume yet: …" line is shown, worded per scope (Design shows only the session case; the same line covers daily, agent and project).
- Spend already settled at the provider (narration chunks done before a crash) is never re-reserved. It is settled from the chunk counts (A4).

### A4. Qt-free job ledger
**Placement.** The kit is an orchestrator across agents, not a catalog agent, so its core goes under `services/`. Widgets go under `ui/release_kit/`.

| Module | Qt? | Role |
|---|---|---|
| `services/job_reservation.py` | no | A1 book (pure; main mutation target) |
| `services/release_kit/ledger.py` | no | Table access, recovery, verification (pattern of `agents/video/jobs.py`) |
| `services/release_kit/plan.py` | no | Plan, routes, bounds, `estimate_job` core, notices per route |
| `services/release_kit/stages.py` | no | One function per stage item; provider calls only through a `JobGrant` (A8) |
| `services/release_kit/runner.py` | no | Pure state machine: `next_action(snapshot) -> Action` |
| `services/release_kit/report.py` | no | `release-kit-report.md` from the ledger only |
| `services/release_kit/provenance.py` | no | AI-use facts per output; marking writers behind a switch (A4, legal) |
| `services/release_kit/power.py` | no | Keep-awake holder (A6) |
| `ui/release_kit/driver.py` | yes | `QObject` on the GUI thread: runs the runner, one worker or `QProcess` at a time |
| `ui/release_kit/confirm_dialog.py`, `window.py` | yes | D2, D3/D4 |

**Tables** (new, in `SCHEMA` as `CREATE TABLE IF NOT EXISTS`, so `init_db`'s `executescript` creates them on an old DB, `services/database.py:645-670`):
- `release_jobs`:
  - identity and source: `id TEXT PK` (uuid hex; the usage `job_id`), `project_id TEXT REFERENCES projects(id) ON DELETE SET NULL`, `version INTEGER`, `source_sha256`, `title`, `byline`, `words INTEGER`, `characters INTEGER`, `project_instructions` (frozen, F4), `output_dir`;
  - state: `status` (`running` · `paused` · `made` · `made_check` · `discarded`), `pause_reason` (code: `retired`, `route_unavailable`, `price_rose`, `over_line`, `advisor_hold`, `cap_refused`, `verify`, `booth_settings_changed`, `user_stop`, `quit`, `interrupted`, `paid_output_changed`), `pause_detail`;
  - money and timing: `approved_total_eur`, `budget_day`, `approval_seq`, `created_at`, `started_at`, `ended_at`, `updated_at`.
  - A partial unique index `ON release_jobs(status) WHERE status='running'` enforces one running kit in the database (owner question 8).
- `release_job_approvals`: `job_id`, `seq`, `approved_at`, `budget_day`, `total_eur`, `plan_json` (routes, lines, bounds, calendar inputs, the assessment text and notices shown), `start_label` ("Start (up to €7.69)"). Append-only: the record of what the owner approved.
- `release_job_stages`:
  - `PK(job_id, stage)`, `ordinal`;
  - route: `agent`, `provider`, `model`, `voice`, `route_kind` (`local` · `paid` · `not_included`);
  - money: `line_eur`, `recorded_eur`, `spend_state` (`none` · `reserved` · `recorded` · `partial` · `abandoned`);
  - progress: `status` (`waiting` · `running` · `done` · `done_verified` · `incomplete` · `verify` · `paused` · `not_included`), `result_json` (quotes, slots and captions, so later stages never read widgets), `conversion_id`, `attempt`, `detail`, `started_at`, `ended_at`.
- `release_job_items`:
  - `UNIQUE(job_id, stage, item_key)`; `item_key` examples: `quotes:request#1`, `graphic:q07`, `short:s12`, `captions:request#1`, `audiobook:narration`;
  - `state` (`planned` · `intent` · `done` · `failed` · `verify` · `partial`), `granted_eur`, `recorded_eur`, `usage_id`;
  - outputs: `output_path`, `output_sha256`, `output_kind`, `artifact_id`;
  - `ai_json` (route, provider, model and voice facts for the report's "AI used" section and the CSV column; legal L2, L5, N4), `created_at`, `updated_at`.

**Additive columns** (`_add_missing_columns` `wanted` dict *and* `SCHEMA`, so `tests/test_database_migrations.py:184` stays green):
- `usage`: `job_id TEXT NOT NULL DEFAULT ''`, `job_item TEXT NOT NULL DEFAULT ''`;
- `runs`: `job_id TEXT NOT NULL DEFAULT ''`;
- `audiobook_conversions`: `job_id TEXT NOT NULL DEFAULT ''`;
- after the columns, `CREATE UNIQUE INDEX IF NOT EXISTS ux_usage_job_item ON usage(job_id, job_item) WHERE job_id != ''` and an index on `usage(job_id)`.

**Migration test** (new tests in `tests/test_database_migrations.py`; existing ones unchanged, and `_wanted()` picks up the new columns automatically, `:50-63`):
- build a database from a frozen copy of today's `SCHEMA` with usage, runs and conversion rows;
- run `init_db` twice;
- assert the new tables, columns and indexes exist;
- assert old rows have `job_id=''`;
- assert `get_today_total`, `get_agent_today_total` and `get_project_today_total` give the same figures before and after;
- assert a second `(job_id, job_item)` insert raises.

**Ledger writes.** GUI thread only (workers return results by signal). Short transactions, default `synchronous=FULL` (measured; the ledger must not lower it, radar #2), and each intent row is committed before its provider call. One writer thread for the kit plus Booth's progress writes, also on the GUI thread, keeps the two-connection WAL window narrow.

**Runner state machine** (pure; the driver performs each `Action`):
- **Job:** `running → paused | made | made_check`; `paused → running` (Resume) `| discarded`. Every exit from `running` goes through one hook: `release_job` + power release + report rewrite.
- **Stage:** `waiting → running → done | incomplete | verify | paused`. Paused goes back to `waiting` on resume. On resume `done` becomes `done_verified` or is re-opened (below).
- **Item:** `planned → intent → done | failed | verify | partial`.
- The order is fixed (0–8). Each stage records its outputs before the next starts (decision 9).

**Resume verification.** Each `done` item's file must exist and its SHA-256 must match. For the EPUB, `project_publication.verify_export` (`services/project_publication.py:90-106`) checks against its receipt.
- A changed **local** item re-opens its stage.
- A changed **paid** output sets `paid_output_changed` → "Review and Approve…" (D4).
- **Verify** stages are never re-run without a new approval (decision 7). The re-run uses a new `item_key` attempt suffix (`#2`), so the unique index still holds and the Verify row stays recorded.

**Recovery at launch.** `release_kit.recover()` runs **first** in `_resume_provider_jobs` (`main.py:4582-4587`), before `audiobook_panel.resume_pending_conversions()`:
1. `running` jobs → `paused/interrupted`.
2. Intent items resolved as in A1 (a)–(d).
3. A kit-owned `audiobook_conversions` row still `running` → settled by `conversions.settle_dead(row, job_id=…)`, the Qt-free core extracted from `panel.py:1057-1097`. It logs with the job columns, so Booth's scan finds nothing left to settle.
4. The Release Kits window opens once, non-modal (D4).

**Crash in a paid text stage (decision 7).** This is recovery case (b): recorded at the maximum, `cost_type='unverified_max'`, state Verify. The report names the provider's usage page. Re-run only through Review and Approve…, which appends an approval row.

**One kit running at a time** (proposed): enforced by the partial unique index. Other kits may stay paused. D1's "A release kit is running for <Project>" reads that row.

**Legal hooks (from the consult; none decided here):**
- **L1, voice route is a field.** `release_job_stages.voice` and `provider` for Shorts take a route value: `system` (macOS `say`), `elevenlabs` (slice 3), or `none` (vertical graphic plus caption, no MP4). A later `own_recording` fits the same field. The default is one constant in `plan.py` (`DEFAULT_SHORTS_VOICE_ROUTE`), so changing it needs no redesign. `render_short` gains an optional `voice_provider` argument (default unchanged), so the kit never picks a voice from the environment (F14). Owner question 6.
- **L2, provenance step per output.** After each output is written, `provenance.stamp(path, kind, ai_facts)` runs. In slice 1 it is a recorder only: it writes `ai_json`, a `provenance.json` sidecar in the output folder and the report's "AI used in this kit" section. Behind a switch, writers for the actual marking:
  - ID3 `TXXX` / MP4 `©cmt` via ffmpeg `-metadata` for MP3, M4B and Shorts MP4;
  - an OPF `<meta>` for the EPUB;
  - a PNG `tEXt` chunk;
  - later, a C2PA manifest.
  The M4B merge maps metadata only from the chapter file (`services/narrator/converter.py:984-986`), so marking the audiobook needs that merge to pass `-metadata` keys. A test then checks that the merge keeps them. Whether marking is required, and in what form, is lawyer trigger T1. Owner question 7.
- **N1–N5, notice slots.** `plan.notices(stage_route)` returns notice ids per row (N1 for paid text or voice rows that send book text, with the provider's country; N2 for the on-device voice; N3 for ElevenLabs). D2 renders them, and `plan_json` records which were shown. The report model has an "AI used in this kit" section (N4) and a CSV "AI used" column (L5), filled from `ai_json`. The wording stays the owner's or a lawyer's. L6 (cloned voices in the ElevenLabs list) is a slice-3 hook on the voice combo: mark them or ask.

### A5. Extraction plan (Qt-free stage functions)
Rule: every panel method that tests call keeps its name, signature and dialogs, and becomes a thin wrapper. Tests that touch these paths: `tests/test_audiobook_conversions.py` (`_close_request`, `resume_pending_conversions`), `test_booth_routes.py`, `test_narration_route_retirement.py`, `test_media_assessment.py` (`_authorize_short_narration`), `test_creator_calendar.py` (`export_calendar_csv`), `test_output_cap.py` (`_on_captions_done`). These must pass **unchanged**. Each extraction lands as its own commit, before the kit uses it, with the full suite green.

| # | Slice | New Qt-free function(s) | Moved from | Approx. lines |
|---|---|---|---|---|
| E1 | 1 | `agents/manuscript/quote_finder.py`: `sample_windows(text, k=12, w=2500)`, `build_quote_messages(windows, count)` (the prompt constants stay in `agent.py`, whose methods delegate), `parse_verified_quotes(reply, windows, max_chars=280, limit=20)` | new, plus `panel.py:1389-1391`; `agent.py:94-98` | ~120 new |
| E2 | 1 | `agents/manuscript/calendar_export.py`: `caption_items(slots, ensure_ascii)`, `apply_captions(slots, reply) -> blank_indices`, `write_calendar_csv(slots, path, ai_column=None)` (cells starting with `= + - @` are prefixed with `'`; a Secure item) | `panel.py:1550-1551, 1576-1578, 1693-1697` | ~60 moved |
| E3 | 1 | `shorts_generator.render_short(..., voice_provider=None)`, `quote_graphics.render_quote_graphic` as is | `shorts_generator.py:35-47` | ~5 changed |
| E4 | 1 | EPUB: `project_publication.export_approved` as is (already Qt-free) | — | 0 |
| E5 | 2 | `agents/audiobook/narration.py`: `route_cost_eur(route, model, text, seconds, days)`, `estimate(path, route, model, days)`, `settings_conflict(open_row, route, model, voice, chunk_tokens)`, `converter_arguments(config, frozen)`, `parse_progress(chunk)`, `classify_finish(exit_code, crashed, output_text, output_ok) -> Outcome` | `panel.py:582-627, 706-713, 826-837, 870-871, 892-908` | ~170 moved |
| E6 | 2 | `conversions.close_run(job_id, success, flat_eur, log)` and `conversions.settle_dead(row, log, job_id='')` | `panel.py:996-1056, 1057-1097` (settle-before-log order kept) | ~90 moved |
| E7 | 3 | `short_narration_cost(quote, model)` | `panel.py:1016-1025` | ~15 moved |

**Windowing (decision 3), exact:**
- If the approved body has `L ≤ 30,000` characters, there is one window (the whole text).
- Otherwise there are K = 12 windows of up to W = 2,500 characters. The ideal start is `s_i = floor(i·(L−W)/(K−1))`. It snaps forward to the next paragraph start within 400 characters, else to the next sentence start within 200. The window ends at the last sentence end before `s_i + W`, keeping at least 1,500 characters, clamped to `s_{i+1}`.
- Each window is sent as `[Passage i of 12, about p% into the book]`.
- The result is deterministic: no randomness, reproducible in tests and across resumes.

Press's own Quote Finder keeps `text[:30000]` (`panel.py:1338`). Moving it to windows is a separate, user-visible change, so the kit does not do it silently.

**Slice boundaries:**
- **Slice 1:**
  - E1–E4, the ledger, the runner, driver and windows, report and provenance (recorder only), the keep-awake holder;
  - **a local-only job entry point:** `authorize_job_item` that refuses any non-local provider with `JobRefusal('not_in_this_version')`. The book and money arithmetic are not built yet. Its existence keeps call sites stable for slice 2 and avoids F2 dialogs (owner question 3);
  - local text items still get child tokens (cost €0), so the Run Log and usage rows carry the job id.
- **Slice 2:** `services/job_reservation.py`, the money side of A1–A3, `check_daily`, E5–E6, the paid audiobook stage, marking writers (if T1 says so).
- **Slice 3:** paid cloud quotes and captions, ElevenLabs Shorts (E7), L6 voice hook.

### A6. Threads, processes and keep-awake
- **Runner:** `ui/release_kit/driver.py` is a `QObject` on the **GUI thread**. It holds the state machine and is the only caller of the guard and the ledger (`_pending_requests` is an unlocked dict, and `record_*` updates widgets, F6). This rejects a runner on its own thread that calls back into the guard with `BlockingQueuedConnection`, a deadlock risk this app's history argues against.
- **One unit of work at a time** (decision 9):
  - text items run on a `ChatWorker` built by the kit with the job's frozen project instructions, not `_new_chat_worker` (F4);
  - EPUB, graphics and Shorts (Pillow, `say`, `subprocess.run(ffmpeg)`) run one item per `StageItemWorker(QThread)` with a Qt-free callable. It never touches the DB or the guard, and emits `done`/`error`;
  - narration runs as a `QProcess` like Booth's (`panel.py:813-841`), held as `host.release_kit_process`.
  - The worker is `host.release_kit_worker`. Both join `closeEvent`'s sweep (`main.py:6272-6297`): `cancel()` + `wait(2000)`, never `terminate()`.
- **Stop:**
  - sets the driver's stop flag; the current item finishes ("Stopping after the current item…");
  - during narration: `kill()` (the converter has no SIGTERM handler, as Booth does today), then `close_job_item_partial` with `conversions.run_spend_eur`. A TTS call in flight at kill time is not billed; this undercount of at most one chunk is inherited from Booth;
  - then `release_job`, status `paused/user_stop`, power released.
- **Quit while running** (D3 dialog, owner present): Quit and Pause does the Stop path synchronously. A text reply still outstanding after 2 s stays `intent` → recovery case (b) on the next launch.
- **Sleep vs quit** (Design UNVERIFIED): a clean quit records `quit`; a crash or power loss shows as `interrupted` at recovery. Sleep does not end the process: work continues after wake, or a dropped connection pauses as `route_unavailable`. So the three can be told apart, and D5's "Mac slept / Imprint quit" row can name the real cause.
- **2026-10-05 deadlock** (TODO.md:173): `QComboBox.setStyle` on the GUI thread against live `QFFmpeg` threads from `QMediaPlayer`. The kit's ffmpeg is a **subprocess**, not QtMultimedia, and the kit creates **no** `QMediaPlayer` (no preview playback; Show Folder opens Finder). Tests drive the pure runner synchronously with fakes. Driver tests replace `QProcess` and the worker with fakes, and any real `QThread` is `wait()`ed in fixture teardown. `pytest-timeout` (300 s) turns a wedge into a failure.
- **Keep-awake (decision 8): `caffeinate -i -w <app pid>`**, spawned by `power.py` with `subprocess.Popen`:
  - acquired when a run starts or resumes;
  - released (terminate, then wait) on every exit from `running` through the single exit hook;
  - `-w` ends it if Imprint crashes.
  - Chosen over a ctypes IOKit assertion for three reasons: no native calls in-process (the macOS 27 AppKit abort is why `ui/appkit_guard.py` exists); it is trivially faked in tests; and both behave the same ("prevent idle system sleep", radar #1).
  - It does **not** keep a closed-lid Mac awake, and the display may sleep. D2's copy is correct; QA confirms on this Mac with `pmset -g assertions`.
- **Risk, UNVERIFIED:** App Nap may throttle a hidden app overnight. If QA sees it, the fallback is `NSProcessInfo beginActivityWithOptions:` through the objc-runtime technique `appkit_guard.py` already uses.

### A7. Project links
Each output is recorded with `project_artifacts.record(project_id, agent, kind, path, label)` (`services/project_artifacts.py:11-31`, upsert on `(project_id, path)`) **when its item finishes**, and the item stores `artifact_id`. Stage 8 re-checks and links any that are missing, so a crash in between never leaves files unlinked.

| Output | agent | kind |
|---|---|---|
| EPUB | `manuscript` | `approved_epub` (as `panel.py:1300-1301`) |
| Audiobook | `audiobook` | `audiobook` (as `panel.py:990`) |
| Graphics | `manuscript` | `quote_graphic` |
| Shorts | `manuscript` | `short` |
| Calendar | `manuscript` | `calendar_csv` |
| Report | `manuscript` | `release_kit_report` |

The label is "Release kit v<version> · <file name>" (D6). The provenance sidecar is linked too (`provenance`). The Project comes from the job row, never from `_active_project()` (F4).

### A8. Test plan hooks (success measures 1–7)
| SM | Test | Kind |
|---|---|---|
| 1 | `test_release_kit_e2e.py`: fixture Project and version; fake local text provider answering verbatim quotes; fake voice and ffmpeg. Asserts EPUB SHA = receipt; N PNGs = unique quotes; M MP4s = Short slots (22 on the 4-week, 3-platform plan); CSV 56 rows; every file in `project_artifacts`. Counts `QDialog.exec` + every `QMessageBox` static → **exactly 1**. | window, offscreen |
| 2 | `test_job_reservation.py`: seeded random sequences of reserve/grant/record/partial/void/release keep the invariant. A fake reporting 3× usage is recorded at `granted`, `cost_type='capped'` and flagged. Σ job rows ≤ approved; Σ stage rows ≤ line. | unit (pure) |
| 3 | A rate 0 or missing for each paid stage → `blocked` names it, Start disabled. `authorize_job` refuses when called directly. Every fake provider has 0 calls. `estimate_chat_cost` is never called on the job path (spy). | unit + window |
| 4 | Each scope (agent, project, session, daily) refuses before start with the validator's sentence. Save Limits lowered mid-run → pause before the next item, and later fakes get 0 calls. After midnight (frozen clock), grants skip daily. A resume on a later day re-checks daily. | window |
| 5 | Run to stage k; drop the window and driver; `recover()` on the same temp DB; resume → stage k+1. Done stages are SHA-verified, not re-run. Fake narrator with a chunk manifest: Σ audiobook usage = one estimate. Intent-item cases (a)–(d), each once. | window |
| 6 | **Contract:** AST walk of `services/release_kit/**`, `ui/release_kit/**` in the style of `tests/test_request_estimate.py:726-775`. Any call to `run_backend`, `ChatWorker(`, `_new_chat_worker`, `ElevenLabsProvider(`, `get_voice_provider(`, `render_short(`, `QProcess(...).start` for the narrator, `requests.`/`httpx.` must sit in a function that takes `grant: JobGrant` and calls `grant.check()` first. `JobGrant` is constructible only by `authorize_job_item`. Runtime: every fake provider asserts its token is open in `_pending_requests` with the right `job_id`. | static + runtime |
| 7 | Migration tests (A4). The full suite runs unchanged after each extraction commit (E1–E7). | migration |
| — | Power: every runner exit path (parametrised over all transitions) calls `release()`, and a crash leaves no holder (`-w`). Ledger: one `running` row max (index). Report: built from the ledger alone. | unit |

**Mutation targets (Verify):**
- `ReservationBook.grant`: `<=` vs `<` against remaining; the move rather than a copy;
- the `record_job_item` clamp (`min`), and the `capped` flag when actual is 0 on a paid route;
- `release_job` zeroing;
- `_reserved_in_flight_eur` including `book.remaining_total()`, and agent/project inclusion;
- the `check_daily` condition `today != budget_day`;
- `None`/≤0 → blocked in `estimate_job`;
- `max` (not `min`) in `max_dated_rate_usd`;
- recovery case (a) vs (b) (no second row);
- the quote parser's verbatim and 280-character filters;
- the window count and size.

### A9. Risks, scope and the cheaper alternative
- **Scope (estimate, not measured):**
  - new code ≈ 1,800–2,200 lines plus ≈ 1,300 lines of tests;
  - edits: `main.py` ≈ 150 lines (job API, in-flight sum, `_resume_provider_jobs` order, `closeEvent`); `services/database.py` ≈ 90; `usage_tracker`/`run_logger`/`validator` ≈ 30;
  - panel extraction: ≈ 65 lines out of `agents/manuscript/panel.py` (1,699) and ≈ 260 out of `agents/audiobook/panel.py` (1,426), across E1–E7, about 10 files.
- **Cheaper alternative for the extraction:** call nothing in Booth's panel. Instead, the kit duplicates the ~80 lines it needs (cost, args, outcome) and leaves Booth untouched. It is faster and leaves no risk to Booth's tests, but two copies of billing logic will drift. **Rejected for E5/E6**: billing must have one source. **Acceptable for E2's 15-line CSV writer** if the owner prefers zero Press edits.
- **Cheaper alternative for the guard:** slice 2 could ship "one dialog per paid stage, shown in the morning". That is not unattended, so it misses the goal. See ADR 0005 for the alternatives.
- **Risks:**
  - the in-flight sum now includes job reservations, so ordinary requests see less room while a kit runs (intended; D2's caps table shows it);
  - recording at the maximum on an unknown outcome over-records by design (decision 7);
  - provider tokenisers can exceed `chars // 4` on non-English text. The clamp records at most the line and flags it; the provider may bill more, which the report says. This affects the whole guard, not only the kit;
  - the App Nap throttling risk (UNVERIFIED);
  - one-chunk narration undercount on Stop (inherited);
  - the `default`-row pricing fallback (F5).

### A10. Architect-gate questions for the owner
1. **Approve ADR 0005** (job-level reservation: one modal, child tokens without a dialog, clamp at the line, in-memory book plus durable intent rows)? *Recommend: yes.*
2. **Daily cap after midnight and on a later resume:** the budget day is the day of approval or latest resume; spend after midnight shows in the next day's total; a resume on a later day re-checks that day's caps. Or add `usage.budget_day` so job spend counts only against the approval day? *Recommend: the first (no change to cap queries).*
3. **Slice 1 adds a local-only, dialog-free job entry point** (`authorize_job_item` refusing every paid provider) and the `usage`/`runs` job columns. That is a small guard addition with no money path. Accept it as "no guard change" for slice 1? *Recommend: yes; without it a refusal at night would open a dialog (F2).*
4. **Quotes:** 12 passages × 2,500 characters in one request, up to 20 quotes, a maximum of 280 characters, non-verbatim quotes dropped. *Recommend: yes; the input size equals today's Quote Finder.*
5. **Keep-awake:** `caffeinate -i -w <pid>`, released on end, pause, stop, quit and crash; it does not keep a closed-lid Mac awake. *Recommend: yes.*
6. **Shorts default voice (legal L1, P1):** macOS `say`'s licence (EA2005 §2F) limits its voices to personal, non-commercial use. Options: keep `system` as the default with notice N2; make `none` (graphic plus caption, no MP4) the default; or wait for lawyer trigger T2. *Recommend: keep `system` for slice 1 Build and QA (local files only, nothing posted) with N2 on D2 and in the report. Decide the default for publishing before any kit Short is posted. This is the owner's call, with a lawyer on T2.*
7. **AI marking (legal L2, AI Act Art. 50(2), transition to 2026-12-02):** slice 1 records the AI facts (`provenance.json`, the report's "AI used" section, the CSV column). Embedded tags in MP3/M4B/MP4/EPUB/PNG, and the M4B merge change, wait for lawyer trigger T1, to be decided before slice 2 ships paid narration. *Recommend: yes; whether marking is required is for a lawyer, not an agent.*
8. **One kit running at a time;** paused kits for other Projects may wait. *Recommend: yes.*
9. **Agent and project caps count job reservations** for every other request while a kit holds money; ordinary single requests stay as today (their own gap, F3, to TODO). *Recommend: yes.*
10. **Decision 7 extended to per-unit items:** an ElevenLabs Short whose outcome is unknown after a crash is recorded at its maximum and marked Verify. *Recommend: yes (slice 3).*

## Risks
- **The guard change is the riskiest part.** A job-level reservation that leaks, double-counts or survives a cancel would spend money outside what was approved. Mitigation: Architect gate, contract test 6, mutation checks on the reservation logic.
- **Extracting the panel logic** (Booth's estimate and resume dialogs, Press's widget-held quotes) could change today's behaviour. Mitigation: the existing panel tests must pass unchanged; the extraction lands before the job uses it.
- **An unattended run meets a condition that today shows a dialog** (settings changed since an interrupted book, a retired route). Mitigation: every such case pauses the job; no dialog runs at night.
- **Cut-off captions** for a 56-slot calendar. Mitigation: mark the stage incomplete. Splitting the request is a possible follow-up that would raise the estimate.
- **Price drift between approval and run.** Mitigation: re-check the rate at stage start; if it rose above the line, pause.
- **Scope creep toward posting.** Mitigation: non-goals above; no Herald or Muse code in this change.
