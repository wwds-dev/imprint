# Imprint — Readiness Gate (before the test campaign)

**Status:** audit, 2026-10-09 at `e23f3cd` · **Owner:** `@me` · **Precedes:** `tests/TEST_PLAN.md`

The test plan assumes the build under test does what the app says it does.
This document checks that assumption agent by agent — the promise (catalog
line, README, agent sheet, UAT script) against the code — and lists what has
to be true before the campaign starts. A campaign run against a build that
fails this gate produces a defect list, not a verdict.

**Principle.** "100 % of what the agents promise" is reachable only when every
promise is precise. Where the code has a deliberate limit (Muse has no send
path; Press never submits to a retailer), the fix is the wording, not a
feature. Where the code has a half-built path (an order that can never be
closed; a key no template names), the fix is the code. Both are listed below;
neither is optional.

---

## 1. Verdict by agent

| Agent | Catalog promise | Reality today | Gate |
|---|---|---|---|
| **Quill** | Plan, draft and revise long-form fiction and non-fiction | Matches. Draft/Publish/Market prompts, Book Profile, continuity, EPUB/DOCX/PDF export. 0 open functional cards | ✅ ready |
| **Press** | Prepare, export, **distribute** and measure finished books | Prepare/export/measure are real (approved snapshots, exports with fingerprints, KDP CSV parsing, charts). **Distribution is not**: the Submission Ledger is self-reported and "never submits to or verifies a retailer". The PublishDrive client (`agents/manuscript/publishdrive_client.py`) reads `PUBLISHDRIVE_API_KEY`, which is in **neither `.env.example` nor `scripts/check_keys.py`**, and `tests/test_env_template.py` scans only `services/*_client.py` and `providers/` so it cannot notice. The endpoint `api.publishdrive.com/v1` has never been exercised against a live account | ⛔ wording + key hygiene |
| **Booth** | Convert books into resumable, production-ready audiobooks | Matches. Three narration routes, resume, quota detection, M4B/MP3. Depends on `ffmpeg`/`ffprobe` and, for MOBI/AZW3, Calibre's `ebook-convert`. OpenAI `gpt-4o-mini-tts` retires 2027-01-06 (handled by the route choice) | ✅ ready, needs tool preflight |
| **Label** | Develop songs and albums, artist identities, releases, promotion and income plans | Plans, identities and release/income documents are real. "Songs & Albums" **drafts prompts and opens suno.com in the browser**; the app imports audio back, it does not generate it. Honest in `docs/agents/music.md`; the catalog line reads as generation. Tab label renders as "Songs _Albums" (P3 mnemonic bug) | ⚠️ wording |
| **Reel** | Script, generate, narrate and assemble long-form or vertical video | Matches. Direct routes (Gemini, Wan, Higgsfield), scene routes across three image providers, vidforge assembly, YouTube upload via OAuth. **Veo 3.1 previews retire 2026-10-22** — inside any realistic test window — so the menu will change mid-campaign. 0 open cards | ✅ ready; test the retirement date with a frozen clock |
| **Herald** | Draft, schedule and **publish** platform-native campaign content | Drafts for 8 platforms (YouTube, Reddit, Pinterest, X, Instagram, TikTok, Threads, LinkedIn); **publishes to 3** (Reddit, YouTube, Pinterest). The panel says which are drafting-only (`status_lines()`), so the UI is honest; the catalog line is not scoped. Open P2 `@me`: the per-platform posting notes were "written from general knowledge rather than checked against the live APIs" | ⛔ wording + verify-or-descope the notes |
| **Sitebuilder** | Create responsive HTML, CSS and JavaScript experiences | Generation, single-file save, project export with heuristic accessibility checks — all real. **No live preview** ("future work", P3). Status says "Exported" before the save dialog is answered (P3) | ✅ ready; say "no preview" in the sheet |
| **Stamp** | Create client-ready concepts, listings and delivery messages (+ README: *a durable per-client order record*) | Logos across seven image models, delivery/gig copy, brand kit — real. **Two P2 functional gaps contradict "durable order record":** an order can never be closed (`status` is accepted by `orders.attach()` but nothing sets it, so a returning client is folded into an unrelated open order), and edits the user makes to the Delivery / Gig text are never saved back (only the streamed draft is) | ⛔ two P2 fixes |
| **Muse** | Create reusable campaigns, captions and promotional assets | Matches. Teasers via Higgsfield / Gemini Omni / Wan with persona reference images; calendar; resume. No send path **by design** and documented. Open P2 `@me`: the Backstage handoff contract is undefined — a decision, not a bug | ✅ ready; decide the contract or park it explicitly |
| **Chat** | General-purpose chat and tool-assisted conversation | Matches; one tool (Audiobook Converter) is wired. Open P2: a Muse Glimmer pull drives **Booth's** progress bar instead of Chat's — a cross-agent UI bug that would confound Booth's UAT | ⛔ one P2 fix |
| **Router** | Internal intent classification | Matches; confidence levels and WHY are pinned by tests | ✅ ready |

Shared: **Press Shorts narration uses the free on-device voice** (`MockVoiceProvider`,
macOS `say`) unless ElevenLabs is chosen. The panel labels it as such, which is
fine. What was not fine (fixed 2026-10-09): the provider wrote a *silent* MP3
whenever `say`, `espeak` or ffmpeg failed and returned it as success, so a
Short could finish with no narration and no error. It now raises, the worker
shows the error and releases the reservation, and `tests/test_on_device_voice.py` pins it.

---

## 2. Open cards that block the gate

Everything P0–P2 that is open anywhere in the repo, as of this audit. P3s do
not block (10 in the root, ~12 across agents, mostly screenshot re-captures).

| # | Where | Card | Kind | Blocks |
|---|---|---|---|---|
| 1 | `agents/fiverr/TODO.md` ✅ done 2026-10-09 | Orders can never be closed; returning client folded into an unrelated order — `close_order`/`reopen_order`, Orders-tab controls, 8 tests | code, P2 | Stamp |
| 2 | `agents/fiverr/TODO.md` ✅ done 2026-10-09 | User edits to Delivery / Gig text not saved to the order — autosave 800 ms after the last keystroke and before any reload/clear/close, 4 tests | code, P2 | Stamp |
| 3 | `TODO.md` ✅ done 2026-10-09 | Glimmer download progress moves Booth's bar, not Chat's — now Chat's bar, determinate while pulling; 2 tests | code, P2 | Chat, Booth UAT |
| 4 | `TODO.md` ✅ done 2026-10-09 | Settings Appearance copy says "two themes"; three ship — copy now derived from `theme.THEMES`; 1 test | copy, P2 | professional finish |
| 5 | `TODO.md` → P3, honest note shipped 2026-10-09 | DashScope intl endpoint in maintenance mode; the tile, key check and template now say so; the WorkspaceId itself is `@me`'s | infra, P3 | Qwen routes (Chat text; Stamp and Reel scene images) |
| 6 | `agents/social/TODO.md` ✅ split 2026-10-09 | Publishers' API terms → precondition of UAT B6's posting cases (P2 `@me`); drafting-only notes → P3, and the Accounts tab now says they are unverified guidance | decision, P2 | Herald |
| 7 | `SUGGESTIONS.md` #65 ✅ parked 2026-10-09 | Backstage handoff contract — de-facto contract stated in one line; nothing promised depends on it | decision, P2 | Muse (documentation only) |
| 8 | `TODO.md` §140 | Should `RunLogger` grow a `note` method | `@me` research, P2 | nothing — reclassify P3 |
| 9 | `TODO.md` ✅ done 2026-10-09 | `PUBLISHDRIVE_API_KEY` absent from `.env.example`, `check_keys.py` **and** `conftest.py`'s scrub list; env-template test did not scan `agents/**` | code, **P1** | Press "measure" |
| 10 | `TODO.md` ✅ done 2026-10-09 | Six lines (three agent, three workspace) reworded; Herald's held to `PLATFORMS`/`PUBLISHERS` by a test | wording, P2 | three agents |
| 11 | `TODO.md` ✅ done 2026-10-09 | No preflight for external binaries — now `scripts/check_setup.py`, called by the UAT preconditions before `check_keys.py` | code, P2 | Booth, Reel, Press Shorts |
| 12 | `TODO.md` ✅ done 2026-10-09 | Verified: the UI wording ("free on-device voice") was fine, but `MockVoiceProvider` **rendered silence as success** when `say`/`espeak`/ffmpeg failed. Now raises; 12 tests, mutation-verified | code, P2 | Press |

Items 1–4, 9, 11 and 12 are closed cards; item 10 is an open `@me` card; item 5 needs a value only `@me` has. Also fixed on the way: four places still said Booth narrates only with OpenAI TTS (README §19, `.env.example`, `check_keys.py`, UAT preconditions).

---

## 3. The gate — all of these, then the campaign starts

**A. Promises are precise**
- [x] Catalog lines and workspace descriptions say what ships (2026-10-09):
      Press *"Prepare, export, log submissions and measure finished books"*;
      Herald *"Draft and schedule posts for eight platforms; publish to Reddit,
      YouTube and Pinterest"*; Label *"Plan songs and albums …; audio is made in
      Suno"*; and the Author, Social and Audio + Music workspace lines likewise.
      The rule is a comment above `WORKSPACE_DESCRIPTIONS`; Herald's line is
      held to the code by a test.
- [ ] Every agent sheet in `docs/agents/` has a **Deliberate limitations**
      section that matches the code (`overview.md` already promises this).
- [ ] `manual_test_cases.md` A2's table, README §2 and `agents/catalog.py`
      agree (a T0 test in the plan pins it).

**B. No open P0–P2 functional card**
- [x] Items 1–4 and 9 fixed, each with a failing-first test (full suite green on
      the Mac, 2026-10-09 12:01). Item 5 (DashScope) waits on the WorkspaceId.
- [x] Items 6–7 answered 2026-10-09 (Herald split; Muse parked). Item 8
      reclassified.
- [x] A one-line **feature freeze** note at the top of `TODO.md` until the
      gate passes. The log shows a feature a day for two weeks (narration
      routes, image providers, BEST FIT rules); each one re-opens the surface
      the campaign is about to measure.

**C. Every selectable route is real or labelled**
- [x] Every credential-reading module under `main.py`, `services/`, `providers/`
      **and `agents/`** has every secret it reads in `.env.example`, a line in
      `check_keys.py` and an entry in `conftest.py`'s scrub list;
      `test_env_template.py` widened and tightened to prove it (2026-10-09).
- [x] Every fallback that substitutes a free output (Shorts voice; the
      free-local offer) labels the result — and a free route that cannot
      actually produce fails loudly instead of fabricating output (2026-10-09).
- [ ] Dated retirements (Veo 3.1 → 2026-10-22; `gpt-4o-mini-tts` → 2027-01-06)
      each have a test that freezes the clock on both sides of the date. The
      DashScope endpoint now states its status (`endpoint_note`, tested) rather
      than retiring — campaign-time item, not a gate item.
- [ ] `providers/avatar/` stays unwired (pinned) and appears in no menu.

**D. Setup is checkable, not assumed**
- [x] `scripts/check_setup.py` (2026-10-09): Python ≥ 3.11, `ffmpeg`/`ffprobe`
      present and version printed, `ebook-convert` present or MOBI/AZW3 shown
      as unavailable, `ollama` reachable with ≥ 1 model (warns when only
      reasoning models are pulled), `say` present on macOS, writable data dir
      outside any bundle. The UAT preconditions call it before `check_keys.py`.
- [x] `--selftest`: all 16 checks passed (2026-10-09 16:05).
- [ ] Launch from a terminal prints only Qt's FFmpeg line (no `[warn]`), and
      the eight tabs show the six reworded lines — the last by-hand step.

**E. The floor is green and stable**
- [x] `pytest -q` passes three times with different `--randomly-seed`s (1, 2, 3 on
      `c72ec4b`, 2026-10-09 17:05: 1 377 passed, 2 skipped each; 190–207 s, no
      per-test timeout). The first randomised run found 5 order-dependent
      failures — a budget-cap leak across 4 request-guard tests and a tooltip
      test that passed on the previous test's fading tip — all fixed.
- [x] No test in quarantine.

**F. Professional finish (not blocking, but do it in the same pass)**
- [ ] The nine stale Learning Centre screenshots re-captured in one sitting
      after the wording changes land, so they are not re-done twice.
- [ ] "Songs && Albums" mnemonic fix; Sitebuilder status-after-cancel fix.

---

## 4. What happens next — in order

1. **Today:** file items 9–12 as cards; add the feature-freeze line; `@me`
   answers items 6–8 (an hour of decisions, not code).
2. **Fix wave (one or two sessions, `@ai`):** items 1–5, 9, 11, 12 and the
   wording in A — each with its failing-first test. Re-run the floor after
   each.
3. **Gate check (`@me`, ~30 min):** walk §3 A–E on a fresh launch. Anything
   unticked goes back to step 2.
4. **Campaign opens** per `TEST_PLAN.md` §8: T0–T2 green → UAT **FREE** pass →
   backlog items 1–5 (guard sweep, kill-and-resume, DB snapshots, money
   maths, secrets) → budgeted **PAID / PAID-UNIT** pass → T5 build smoke.
5. **Veo date:** if the campaign straddles 2026-10-22, run Reel's UAT B5 once
   before and once after, and keep the frozen-clock test from C.

The gate is passed when §3 A–E are all ticked on the same commit, and that
commit hash is written at the top of `TEST_PLAN.md` as the campaign baseline.
