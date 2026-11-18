# Code-level readiness audit: promises against code (2026-11-18)

Foundry phase: Verify (7), read-only, before the QA test campaign (`tests/READINESS_GATE.md`,
`tests/TEST_PLAN.md`). Scope: every promise in `README.md`, `docs/agents/*.md` and `manifest.json`,
the per-agent READMEs, `docs/foundry/app-context.md`, the Learning Centre recipes and UI strings,
checked against the code for all ten agents (Chat, Router, Quill, Press, Booth, Label, Muse, Reel,
Herald, Sitebuilder, Stamp), the request guard and billing, routing, vidforge, the audiobook work,
publishing and the `cloud/` companion. Base: `main` at `63cefbf`. Nothing was changed in the code,
no provider was called, nothing was rendered, uploaded or posted.

Method: the money paths, guard, routing and keys were read by the audit's lead (Opus); the agent
folders were read by three read-only subagents (Sonnet), whose working notes stay outside the repo.
Every High and Blocker finding below was re-checked in the code by the lead; the remaining
subagent findings are marked *(sub)*. "Confirmed" means the code path was read end to end, not run.

## Verdict: not ready for the QA campaign

Five blockers, three of them code and two the owner's:

1. **QB-1** Quill's Write empties the autosaved Draft; outline and character tasks land in it, and
   Revise sees only the last 3,000 characters. Data loss on the app's core writing path.
2. **QB-2** Booth authorizes only the "remaining" share of a book after the source text changed,
   while the converter re-narrates the whole book: a paid call the guard did not authorize.
3. **QB-3** A Herald clip is authorized as "openai" while its scene images can go to Gemini or Qwen,
   so it spends on a provider whose permission box is unticked.
4. **QB-4** (`@me`) No cloud key works (`TODO.md` P1, 2026-10-09): every paid path the campaign
   tests is unreachable until the keys are replaced.
5. **QB-5** (docs) Readiness gate §3 A is still open: `docs/agents/overview.md:48-51` promises that
   every agent sheet names its *deliberate limitations*; none of the twelve sheets has that section.

Suite: green, 2174 passed and 2 skipped in 18 min (*Test run* below). It does not exercise the paths behind the blockers.

## Findings

Severity: **Blocker** stops the campaign; **High** breaks a stated promise or the money invariant
on a normal action; **Medium** wrong in a narrower case; **Low** wording, dead code, drift.

### Blocker

| ID | Promise (where) | What the code does | Evidence | Smallest fix |
|---|---|---|---|---|
| QB-1 | Quill "plan, draft and revise" (`agents/catalog.py`, `docs/agents/author.md`); Revise / Tighten Structure / Strengthen Argument tasks | `write()` clears the Draft box before sending (`agents/author/panel.py:1073-1074`) and streams every reply into it (`:1110-1115`). For Generate Outline / Develop Characters / Build World the reply is also copied to its tab (`:1263-1268`) but stays in the Draft. The old draft is restored only when the guard refuses (`:1043-1051`), not on error (`:1151`) or Stop (`:1160`). Every Draft change is autosaved (`:672-677`), so the loss persists. Revise tasks run through `write()`, which sends the draft only as `recent_draft_text[-3000:]` (`:983-985`) and the reply replaces the whole manuscript. | Confirmed by reading; not reproduced live. Tests call `_on_finished` directly and never stream. | Keep the draft: stream non-draft tasks into a separate buffer, restore the draft on error/Stop, and send the full draft (or a chosen chapter) to Revise tasks; add a streaming test. |
| QB-2 | Booth resumes "without paying twice" (`docs/learn/modules/22-audiobooks.md`); invariant "no paid call outside the request guard" | Panel compares only voice, chunk size, provider and model with the open conversion row (`agents/audiobook/panel.py:706-712`), then authorizes estimate × `remaining_fraction(row)` (`agents/audiobook/conversions.py:39-44`). The converter discards the cache when the text hash differs (`services/narrator/converter.py:657-665`) and narrates the whole book. A deleted cache with done == total authorizes €0. | Confirmed by reading both sides. | Store the source's text hash (or size+mtime) on the row and treat a mismatch like "settings changed" (full-cost authorize). Panel-side only: no converter copy changes. |
| QB-3 | Every paid call passes its provider's permission box (validator step 6, `services/validator.py`) | `agents/social/panel.py:616-619` authorizes the clip as provider `"openai"`, model `"vidforge-pipeline"`; scene images can be set to Gemini or Qwen by Apply (`_clip_visuals`, `:597`). The Video tab checks the image provider's key and box (`agents/video/panel.py:488-512`); Herald does not. | Confirmed. | Reuse the Video tab's provider check (or authorize per provider) before the clip's `authorize_request`. |
| QB-4 | Campaign runs live paths (`tests/TEST_PLAN.md`) | `TODO.md` P1 `@me`: Anthropic 401, Gemini 400, DeepSeek 401 on 2026-10-09; no other cloud key confirmed. | `TODO.md` (existing item). | Owner replaces keys, then `scripts/check_keys.py`. |
| QB-5 | "Each agent sheet names … deliberate limitations" (`docs/agents/overview.md:48-51`); gate §3 A (`tests/READINESS_GATE.md`) | `grep -i '^#.*deliberate limitation' docs/agents/*.md` matches nothing; the gate's two A items are unticked. | Confirmed. | Add the section to each sheet from this audit's Narrower/Stub rows. |

### High

| ID | Promise (where) | What the code does | Evidence | Smallest fix |
|---|---|---|---|---|
| QH-1 | Invariant "no paid call outside the request guard" (`docs/foundry/app-context.md`) | `cloud/reading_compass.py` (Reading Compass, Cloud Run) narrates a whole ebook with the shared converter (`run_worker`, `:573-617`): no budget, no cap, no usage record; the estimate endpoint (`:358-385`) is optional and `enqueue` (`:387-430`) needs no acknowledgment. A `failed` job can be queued again (`:407`) and pays again in full. Not in app-context's *Models used*. `convert()` has no budget parameter (`converter.py:1251`). | Confirmed by reading. Whether it is deployed: unconfirmed (status kept outside the repo). | Require an acknowledged estimate and a per-job cap in `enqueue`; record the spend; list the route in app-context. Or state in app-context that `cloud/` is outside the desktop guard and why. |
| QH-2 | Reel: "Stop … next launch checks and saves the paid result" (`agents/video/panel.py:1184-1190`) | Gemini Omni renders synchronously; on Stop the worker returns before downloading (`ui/workers.py:394-409`); `resume_video` raises for Omni (`services/gemini_client.py:416-419`), so the job row stays reserved and fails on every launch (`agents/video/workers.py:63-75`). The paid clip is lost and nothing is recorded. | Confirmed. | For Omni, finish the synchronous call and save the bytes even after Stop (or disable Stop once submitted); close the row. |
| QH-3 | Herald "publish to Reddit, YouTube and Pinterest" (`agents/catalog.py:59`, `docs/agents/social.md:48`) | Pinterest: the panel has no way to attach an image; the only media is the MP4 from Make a Clip, which `publishing.py:340-343` sends as `image_base64` / `image/png`. | Confirmed. | Image picker for Pinterest posts and video upload via Pinterest's video flow, or drop Pinterest from the promise until then. |
| QH-4 | Herald YouTube "ready to post" | `configured` accepts any `client_secret*.json` (`agents/social/publishing.py:243-255`); the uploader opens exactly `client_secret.json` or `VIDFORGE_YT_CLIENT_SECRET` (`vidforge/vidforge/youtube.py:35-43`). The click then fails and is filed as non-retryable "Verify platform". *(sub; uploader side confirmed)* | Confirmed. | One shared resolver for the secret path used by both. |
| QH-5 | Invariant "never claim … results it cannot show"; README:1874-1878 shows Press answering "What did I earn this month?" | Press Ask is grounded only in the last PublishDrive JSON (`agents/manuscript/panel.py:102,726,820`); KDP data is never injected, and the system prompt claims KDP reports, metadata sync and store status (`agents/manuscript/agent.py:5-20`) that nothing feeds. Connections shows "connected" when a key is present (`panel.py:646-668`) and any HTTP 200 is logged "ok" (`:727`). The endpoint (`publishdrive_client.py:11,57-60`) has never been called live. *(sub; panel lines confirmed)* | Confirmed. | Inject the KDP summary; cut the prompt to what is wired; show "key set, not verified" until a fetch parses. |
| QH-6 | Booth Stop | Stop kills the converter (`agents/audiobook/panel.py:1133-1143`) while up to four chunks are being generated (`converter.py:90`); spend is counted only from progress lines (`conversions.py:119-130`), so in-flight chunks are paid, unrecorded and paid again on resume. A deliberate Stop also shows "[Error] Conversion failed." and a critical dialog (`panel.py:884-960`). *(sub)* | Confirmed by reading; dialog count unconfirmed. | Count in-flight chunks at the confirmed rate on Stop; a stop flag so Stop reads as stopped. |

### Medium

| ID | Finding | Evidence | Smallest fix |
|---|---|---|---|
| QM-1 | Automatic local-model measurement spends without a confirmation dialog. A newly discovered local model triggers up to ~160 reference and judge calls to cloud models once a key exists and the box is ticked. Its ceiling is validated once but never reserved in flight, and it is billed on a chars/4 estimate, not provider usage. Documented in README:818, so not a hidden path, but it is the one paid run that needs no click. | `services/local_ratings.py:56` (`AUTOMATIC = True`); `main.py:1159-1169`, `:1201-1239` (dialog only `if interactive`), `:1294-1305` | Default `AUTOMATIC` off, or one confirmation per new model; add the ceiling to `_pending_requests` while it runs. |
| QM-2 | B-F4 (existing item) confirmed. The TODO line refs are stale; current lines: `authorize_request` adds in-flight reservations to session and daily only (`main.py:4517-4529`), not to `agent_daily_cost` or `_project_budget_fields` (`:4457-4465`). Chat validates inline (`main.py:4243-4258`) and never enters `_pending_requests` (`:5232`). | as cited | As in TODO. |
| QM-3 | B-F5 (existing item) narrowed. `eur_per_usd ≤ 0` is fixed (`services/per_unit_pricing.py:64-100`). An unknown text model bills at its provider's `default` row, and all six text providers ship a positive one (`config/pricing.json`; `services/pricing_catalog.py:153`). €0 happens only if the user blanks that row in Settings → Pricing (`ui/dialogs.py:1080-1107` turns blank into 0): estimate `main.py:594-595`, bill `services/usage_tracker.py:134-135`. Related: a Higgsfield quote of exactly $0 passes as a free flat request (`services/higgsfield_client.py:388`). | as cited | Refuse when `resolve_price_row` is unknown; treat a $0 Higgsfield quote as invalid. |
| QM-4 | B-F7 (existing item) confirmed. Chat Stop and error bill nothing (`main.py:5571-5600`); every panel's Stop and error goes to `abandon_request` (`main.py:5365-5372`), which records €0. | as cited | As in TODO. |
| QM-5 | B-F6 (existing item) quantified *(sub)*. vidforge loops `RETRIES=3` over OpenAI SDK clients with the default `max_retries=2`: up to 9 billed attempts per call, against the app's `MAX_RETRIES=1`. Booth's converter builds its OpenAI client without `max_retries` (`converter.py:181`) on top of `RETRIES=2` (`:89`). A Gemini ffmpeg encode failure retries a call that already returned audio (`:788-808`, `:889-928`). | `vidforge/vidforge/visuals.py:25,79`, `voice.py:18`, `llm.py:21`; converter as cited | `max_retries=0` on the SDK clients; move the encode outside the retry. The converter is a shared copy: change all copies in one session. |
| QM-6 | Short clips overshoot their length and their reservation *(sub)*: script floors of 4 scenes and 20 words make a 15 s clip about 31 s; the estimate assumes 2 scenes. | `vidforge/vidforge/script.py:108-111`; `agents/video/studio.py:286-288` | Scale the floors to the target length; estimate from the same rule. |
| QM-7 | Booth runs and bills €0 on Stop or failure when its ledger row cannot be written *(sub)*. | `agents/audiobook/panel.py:789-798` (exception swallowed), `:1033` | Refuse to start without a row. |
| QM-8 | Choosing M4B after an MP3 exists re-narrates the book; the confirmation does not say so *(sub)*. | `agents/audiobook/panel.py:671-679`; `converter.py:1339-1346` | Check both formats before the estimate. |
| QM-9 | Muse's Gemini Omni and Qwen Wan teasers skip the content-policy check that Higgsfield gets; prompt and reference images go out unchecked. | `agents/creator/panel.py:1117` (Higgsfield only), `:1213-1301` | Call `check_prompt` on every route, or document it as Higgsfield-only. |
| QM-10 | Press's Period selector is never read; Refresh always fetches 30 days. | `agents/manuscript/panel.py:129-131`, `:725` | Wire it or remove it. |
| QM-11 | Network work on the UI thread, against the lab's Qt rule: Press Refresh (`requests.get`, 30 s, `agents/manuscript/panel.py:717-732`); Herald posting, including the YouTube upload and OAuth consent (`agents/social/panel.py:1071-1076`) *(sub)*. | as cited | Move both to workers. |
| QM-12 | Press Shorts has three entry points sharing one worker and token with inconsistent busy guards; a second start can replace a running QThread and orphan the first reservation *(sub)*. | `agents/manuscript/panel.py:1085-1103`, `:1424-1450`, `:1535-1550` | One busy flag for all three. |
| QM-13 | KDP CSV ingest fails open: wrong headers parse as zero units and royalty, and the file is marked ingested and "ok" *(sub)*. The headers have never been checked against a real export. | `agents/manuscript/kdp_csv_parser.py:100-134`, `:172-205` | Refuse a file with none of the expected columns. |
| QM-14 | Herald's Schedule Drafts sets `scheduled` on every undated post, including posted and needs-review ones. | `agents/social/panel.py:785-816` | Filter on draft status. |
| QM-15 | Muse and the Suno panel both authorize as `"music"` and resolve by agent name (oldest outstanding), so concurrent runs bill each other's usage and model. The `authorize_request` docstring forbids new by-name sites (`main.py:4491-4498`). | `agents/music/panel.py:211,240,269`; `agents/music/suno_panel.py:208,225,236`; `main.py:5270-5291` | Keep the token in both panels (and in Sitebuilder). |
| QM-16 | The vidforge CLI (`run --count`, `course`, `topics --suggest`, `scan`) is a paid path with no guard, estimate or confirmation *(sub)*. Its README still lists a removed `schedule` command and a Scanner tab. | `vidforge/vidforge/cli.py`; `vidforge/README.md:109-160` | State in the README that the CLI is outside the app's guard, or add a `--max-usd` stop. |
| QM-17 | Dated retirement outside Booth: vidforge's voice uses `gpt-4o-mini-tts` with no retirement handling (removed 2027-01-06, seven weeks away); Booth handles the date (`converter.py:38-47`, tested). The cloud job defaults to the OpenAI route. | `vidforge/config.yaml:28`, `vidforge/vidforge/voice.py:33` | Move vidforge's voice to the successor model before the date. |
| QM-18 | Stamp's persona invents trust claims and fixed prices ("5-star reputation", Basic/Standard/Premium). Its logo prompt asks for a "vector, transparent background" result that the raster PNG pipeline does not produce. Quill's Publish and Market output (KDP categories, keywords, prices, comps) carries no "verify" notice *(sub)*. | `agents/fiverr/agent.py:3,19,26,38`; `ui/workers.py:285-290`; `agents/author/agent.py` | Remove the claims; add a verify line to market-facing output. |

### Low

- K-P2-1 (existing) confirmed. `write_values` rewrites only the named key (`services/api_keys.py:183-238`); `apply` drops the aliases for this process only (`:243-254`); `main.py:42` reloads them at launch; `gemini_client.py:20` reads `GEMINI_API_KEY` first.
- K-P2-2 (existing) confirmed. `.gitignore:12` has only `.env`; `git check-ignore` matches none of `.env.ABCDEFGH`, a root `client_secret_x.json` or `token.json`. There is no pre-commit hook and `core.hooksPath` is unset. No secret is tracked (only the `.env.example` files).
- Booth's OpenAI price is hard-coded in the converter (`converter.py:150-151,528`), not in `config/pricing.json` as README:1620 implies. Its "production-ready" claim (`agents/catalog.py:43`) has no loudness, ID3 or ACX handling *(sub)*.
- `services/narrator/converter.py:30` hard-codes `/Users/as/Documents/Files/Narrator`, against the lab rule. It is a shared copy: fix it in all copies in one session.
- Dead code: `ToolRunner.run_audiobook` (`services/tool_runner.py:14`), `run_audiobook_live` (`main.py:3745`), `PublishDriveClient.update_metadata` and the get_catalog/get_distribution_status helpers have no caller. `providers/avatar/` is imported nowhere; its env-template test pins that. README:3681 still prices "Course (HeyGen avatar)".
- vidforge's `pexels` source and `cut` transition have never run (`cut` has no GUI control). Pexels has no key check, so with no key it silently falls back to gradient cards *(sub)*.
- A disabled "Realtime Monitor" button sits in the System card (`main.py:3433-3435`, tooltip "(Coming soon)", `ui/tooltips.py:76`).
- ElevenLabs voice listing ignores the permission box (`agents/audiobook/panel.py:539-557`), and `elevenlabs` is missing from `CLOUD_BACKENDS` (`services/usage_tracker.py:8`). That affects only the cloud flag, not the caps.
- Sitebuilder's "framework used" echoes the selection and "responsive" is a substring test (`agents/webdesign/panel.py:362-365`). `split_project` moves JSON-LD and module scripts into `script.js` (`export.py:19-21`) *(sub)*.
- The chapter regex turns prose lines starting "Part…" or "Chapter…" into chapters in exports, and EPUB has no title page (`agents/author/book_exporter.py:17-20`) *(sub)*.
- Router: `author` is last in ROUTES and no "logo" trigger reaches Stamp (`agents/router/agent.py:58-72`) *(sub)*.
- Doc drift:
  - `main.py` is 6,511 lines; `TODO.md`'s header says 4,384 and app-context says about 4,400.
  - `CLAUDE.md` says the suite takes about 90 s; app-context says 13–17 min (29 on 2026-11-16).
  - App-context names `services/api_limits.py` as the guard; it holds only timeout and retry constants (22 lines).
  - README still uses the old names Maestro, Narrator, Site Builder and Atelier, says Booth is OpenAI-only, and lists `agents/manuscript_agent.py`.
  - `docs/audiobooks-iphone-manual.md:47` names a UI entry that does not exist.
- `TODO.md`'s "Merge the PySide6 pin that missed PR #28" is stale: `7754eec` is an ancestor of `main` and `requirements.txt:35` pins 6.11.2. The worktree `worktrees/imprint-harden-ship` still exists; this audit left it untouched.

### Leads from the doc sweep: verdicts

| Lead | Verdict |
|---|---|
| Three cloud keys rejected | Stands (QB-4); not re-tested, since that would need a live call. |
| B-F4 reservations | Confirmed (QM-2); line refs updated. |
| B-F5 unknown price / rate ≤ 0 | Rate half fixed; unknown-price half narrowed to a blanked `default` row (QM-3). |
| B-F6 vidforge reservation | Confirmed and quantified (QM-5, QM-6). |
| B-F7 €0 on stop or ambiguous submit | Confirmed (QM-4). New neighbours: QH-2, QH-6. |
| Output-cap names for Kimi, Qwen, DeepSeek | Unverified, as the code comments say (`kimi_client.py:68-71`, `qwen_client.py:357-361`, `deepseek_client.py:72-75`). Owner check. |
| PublishDrive endpoint untested | Confirmed, and the UI overstates it (QH-5). |
| Gemini and DashScope media lists | Unverifiable without keys. |
| Dev `.env` routes Seedance 2.5 to 1.0 Lite | Mechanism confirmed: an env override replaces the default model's endpoint (`higgsfield_client.py:176-184,340-345`). The `.env` values were not read, by rule. Unconfirmed here; the existing `@me` item stands. |
| Cleared key returns (K-P2-1) | Confirmed. |
| `.gitignore` gaps, gitleaks hook off (K-P2-2) | Confirmed. |
| `providers/avatar/` unwired | Confirmed. |
| `main.py` about 4,400 lines | Refuted: 6,511. |
| vidforge `pexels` and `cut` never run | Confirmed. |
| Flaky tests | See *Test run*. |

### Checked and fine

- **Never post without the user's action** holds. There is one publish call site (`agents/social/panel.py:1072`), after an explicit "Post now?". There is no timer or scheduler in `agents/social`.
- Every GUI media route reaches `authorize_request` with a flat cost, and an unknown per-unit rate refuses (`services/per_unit_pricing.py:103-137`). Exceptions: QB-3 and the Higgsfield $0 quote.
- Every text panel in Quill, Press, Stamp, Muse, Label and Sitebuilder authorizes before sending, and the paid-request dialog is a real per-request confirmation (`main.py:4340-4410`).
- The Higgsfield path probe is off by default and passes the validator (`main.py:4675-4709`). Model-list probes send only the key (`scripts/check_keys.py:62`).
- Suno is a link only; no music API is called (`agents/music/suno_panel.py:147-148`).
- The frozen-build crash from the 2026-10-22 release attempt is fixed: `Imprint.spec` collects the agent submodules, guarded by `tests/test_spec_hiddenimports.py`.

## Checks only the owner can run (real keys or accounts)

1. Replace the three rejected keys, then run `scripts/check_keys.py` (QB-4).
2. Run the first paid Kimi, Qwen and DeepSeek requests, and confirm `max_tokens` and `thinking_budget` are accepted and bounded (existing P1 item).
3. Run one Press Refresh Data with a real PublishDrive key and inspect the host, path, auth and JSON shape. Ingest one real KDP report and compare the columns.
4. Run each Booth route (OpenAI, Gemini, ElevenLabs) on a ~1,500-word TXT. Compare the provider dashboard with the estimate. Stop one ElevenLabs run mid-way and compare the dashboard with the usage log (QH-6).
5. Read `HIGGSFIELD_*_VIDEO_ENDPOINT` in `.env` yourself (Seedance lite lead). Confirm `/estimate` costs nothing before switching the probe on.
6. Run one Omni clip and press Stop after submission (QH-2). Do the same for a Wan task resume after a kill.
7. Post one Pinterest pin and one YouTube upload with real accounts once QH-3 and QH-4 are fixed.
8. List the Gemini and DashScope media models with a key.
9. Check whether the Reading Compass Cloud Run job is deployed, and if so what one book cost (QH-1).
10. Generate one Stamp concept on each of OpenAI, Gemini and Qwen.

## Test run

Run on 2026-11-18 with `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -p no:cacheprovider`. The suite ran in
random order (pytest-randomly) while two other audits loaded the machine.

**2174 passed, 2 skipped, 0 failed, 6 subtests passed, 1 warning, in 1,089.87 s (18 min 09 s).**

- The warning comes from the dependency's own plugin, not Imprint: `PytestRemovedIn10Warning` from anyio's pytest plugin, which imports `CallSpec2`.
- No hang and no segfault this run.
- The three flaky tests named in `TODO.md` all passed on this run, which does not prove they are fixed: the `test_routing_phase3` measurement cancel, the audiobook player's saved position, and the Qt window teardown.
- The collected count grew from 1,826 (2026-10-19) to 2,176.

The green suite does not cover QB-1 to QB-3, QH-2 and QH-6. Their tests call the finish handlers directly or use fake workers, so no test streams into Quill's Draft, changes a Booth source between runs, or stops an Omni render.
