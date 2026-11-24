# Code review: whole-repo audit (correctness, concurrency, error handling, maintainability)

Reviewer: code-reviewer, read-only; no file in the repo was changed. Foundry phase: Review (6).

- **Base.** Started on `main` at `ec1cda5`; `main` moved three times during the review. Every file:line below is at `45f705d`. Between the two, the only code changes are the display-name rename (Chat is now Kernel, Stamp is Vector, Muse is Nova) and one line in `main.py:3948`.
- **Playbook.** `docs/playbooks/code-reviewer.md` is `status: current`, `last-reviewed: 2026-10-14` (41 days), so not stale.
- **Checks run.**
  - `compileall` over the app packages: exit 0.
  - An AST pass over the broad exception handlers.
  - Two standalone PySide6 experiments in the repo's venv.
  - One `load_text` call.
- **Not run.** The full suite, any provider or network call, and ruff (not installed locally).

## Verdict

Not yet at a professional level, and not ready for the QA campaign, though the gap is narrow and mostly mechanical. The newer money paths are careful work: token-keyed reservations, settle-before-bill on video, teaser and Booth rows, partial billing, the release-kit driver, and the QB-1 draft fix. The older half of the app does not meet that standard:

- **Crashes.** Several panels replace a running `QThread`, which aborts the process (SIGABRT). One path needs only two ordinary clicks in Herald. Quill and Reel already carry the guard that prevents this; the other panels do not.
- **Shutdown.** `closeEvent` misses two workers and gives up after 2 s on the rest, so some quits end in a crash report.
- **UI-thread fetches.** Network work still runs on the UI thread in five places. The YouTube consent wait has no timeout and can freeze the window for good.
- **Money invariant.** The two blockers from the 2026-11-18 audit (QB-2, QB-3) are untouched.

`main.py` is 6,725 lines in one class. It is workable only because the newer code routes around it; it is a maintainability risk, not a correctness finding. I found no `QThread.terminate()` anywhere.

## P0

Both are carried over from the 2026-11-18 audit and break the invariant "no paid call outside the request guard". The files are byte-identical to `63cefbf` (`git diff --quiet`).

**P0-1 (QB-2). Booth authorizes less than the converter spends after the source text changes.**
- Where: `agents/audiobook/panel.py:706-712` compares only voice, chunk size, provider and model. `agents/audiobook/conversions.py:39-44` returns the remaining fraction. `services/narrator/converter.py:656-697` discards the cache on a text-hash mismatch.
- Scenario: stop a book at 180 of 200 chunks, edit the manuscript, press Start. The guard confirms 10% of the estimate; the converter narrates 100%.
- Fix: store the source's size and mtime (or text hash) on the row and treat a mismatch as `fresh_start`. Panel-side only.

**P0-2 (QB-3). A Herald clip is authorized as `openai` whatever provider draws its images.**
- Where: `agents/social/panel.py:616-619` authorizes `("video", "openai", "vidforge-pipeline")`. `:595-596` merges `_clip_visuals`, which Apply can set to Gemini or Qwen (`:687-688`). The Video tab checks key and permission for the same case (`agents/video/panel.py:494-512`).
- Scenario: Gemini's permission box is unticked, Apply picks a Gemini image model, and the clip spends on Gemini.
- Fix: reuse the Video tab's provider check before `authorize_request`.

## P1

**P1-1. Replacing a running `QThread` aborts the app.**

Evidence: a scratch script outside the repo (`qthread_drop.py`) mirrors the assignment pattern. Output: `QThread: Destroyed while thread '' is still running`, exit 134. The pattern is reproduced in isolation, not inside the app. The code knows this crash: the guard and its comment are at `agents/author/panel.py:1076-1083`, with the same guard at `:1603`, `:1725`, `agents/video/panel.py:481` and `agents/music/suno_panel.py:184-191`.

Unguarded sites:

| Panel | Sequence | Where |
|---|---|---|
| Herald (no Stop needed) | Write Posts, then Make a Clip while it writes | `write()` disables only the Write button (`agents/social/panel.py:470`); `make_clip` overwrites `host.social_worker` (`:565`) |
| Press shorts (QM-12, upgraded) | Generate a Short, then "Short" on a Quote Finder row or a calendar asset | `host.shorts_worker` replaced at `agents/manuscript/panel.py:1112`, `:1533`, `:1722`; `generate_short` (`:1074-1116`) never sets `_quote_finder_busy`, the only flag the others check (`:1498`, `:1695`) |
| Kernel chat | Stop, then Send | `main.py:5781-5791`, then `:4340` |
| Label | Stop, then Generate | `agents/music/panel.py:279-284`, then `:224` |
| Sitebuilder | Stop, then Generate | `agents/webdesign/panel.py:243-248`, then `:205` |
| Herald write | Stop, then Write | `agents/social/panel.py:507-514`, then `:476` |
| Vector text flows | Stop, then any text action | `agents/fiverr/panel.py:960-993`, then `:419`, `:642`, `:687` |
| Nova draft | Stop, then Draft | `agents/creator/panel.py:715-729`, then `:683` |

- **Why the window is real.** `ChatWorker` sees a cancel only between tokens (`ui/workers.py:65-73`) and never during a non-streaming call. A cold Ollama load can stay silent up to `READ_TIMEOUT = 300` s (`services/ollama_client.py:49-50`); a cloud call up to 120 s (`services/api_limits.py`).
- **Press side effect.** `_authorize_short_narration` sets `self._shorts_token = None` first (`:1026`), so the first run's reservation is orphaned for the session and its narration is never billed.
- **Fix.** One host helper that every start site calls and that refuses while the old worker `isRunning()`, as Quill does. Give Press one busy flag for all three entry points. Do not solve it by parking the old worker: a superseded worker's late `error_signal` would close the new run's token (`_on_text_error`, `agents/fiverr/panel.py:609-617`). The image flow's token-bound lambdas (`:524-529`) are the model if parking is ever needed.
- **Tests.** No test covers a restart while a cancelled worker is still alive (`grep "still finishing" tests` matches nothing).

**P1-2. Herald's Post Now runs the upload and the Google consent wait on the UI thread, with no timeout (QM-11, sharpened).**
- Where: `agents/social/panel.py:1072` calls `publisher.publish(...)` in the click handler. For YouTube that reaches `flow.run_local_server(port=0)` (`vidforge/vidforge/youtube.py:65-70`).
- Scenario: first YouTube post; the browser opens for consent; the user closes the tab. The window is frozen until force-quit, and the job stays `publishing` until `recover_interrupted` at the next launch. Even on the happy path the window is frozen for the whole upload.
- Rule: the lab Qt rule "nothing on the UI thread may fetch".
- Fix: move `publish` into a worker and bound the consent wait.

## P2

**P2-1. `closeEvent` does not name every QThread, and a timed-out wait still ends in an abort.**
- `music_worker` and `webdesign_worker` (declared `main.py:365-366`) are missing from the sweep list (`main.py:6502-6511`). Quitting during a Label or Sitebuilder generation neither cancels nor waits.
- For listed workers the sweep is `cancel(); wait(2000); accept` (`:6513-6527`). `ShortsWorker` and `ModelPullWorker` have no `cancel` (`agents/manuscript/workers.py:13-38`, `ui/workers.py:215-244`), so quitting during a Short render or a model download always outlives the wait.
- Evidence: a scratch script outside the repo (`qthread_quit.py`) exits 134 both with no wait and after a timed-out wait.
- Impact: a macOS crash report at quit. The manuscript is saved first (`:6481-6485`), so no data loss.
- Fix: derive the sweep from one registry of live workers; add `cancel` to the two workers; for a worker still alive after the wait, flush and leave with `os._exit(0)`.

**P2-2. Other network calls on the UI thread.**
- Kernel provider switch and startup: `main.py:2824` connects to `load_provider_models`, which at `:3549` calls `models_for_provider`, which at `:1396` makes a live `client.list_models()` call (120 s timeout, one retry).
- Startup: `main.py:424` calls `load_models`, which at `:3778` calls `self.ollama.list_models()` (10 s).
- Press Refresh Data: `agents/manuscript/panel.py:728-743` (`requests.get`).
- Reel Stop on a Wan render: `agents/video/panel.py:1147` calls `cancel_video` (`services/qwen_client.py:517-532`, 120 s).
- A dialog calls `app.ollama.list_models()` at `ui/dialogs.py:1250`.
- Fix: use the existing `ModelListWorker` and cache (`ui/panels/base.py:112-155`) for Kernel; small workers for the rest.

**P2-3. MOBI and AZW3 are offered but can never be loaded from the GUI.**
- Where: Booth lists them (`agents/audiobook/panel.py:27`), but `_text` calls `load_text(path)` with no `work_dir` (`:601-608`), which raises for those suffixes (`services/narrator/converter.py:492-494`). `_estimate` swallows it (`:616-624`) and Start answers "Unreadable Book" (`:685-691`).
- Press has the same defect: the file filter offers `*.mobi` (`agents/manuscript/panel.py:1147`) and `:1153` makes the same call.
- Evidence: ran `load_text(Path("/nonexistent/book.mobi"))`; result `ValueError work_dir is required for .mobi conversion`.
- Promise broken: `docs/agents/audiobook.md:8`, `docs/learn/modules/22-audiobooks.md:8-9,121`.
- Fix: pass a temp `work_dir` in both callers. No converter change, so no shared-copy edit.

**P2-4. Book parsing on the UI thread (confirms the coordinator's question 1).**
- `quote_finder_load_file` (`agents/manuscript/panel.py:1144-1157`) calls `services.narrator.converter.load_text` in the click handler, so a PDF or EPUB is parsed on the UI thread.
- Booth does the same on every book selection (`estimate_cost_from_selection`, `agents/audiobook/panel.py:628-640`, via `_text`).
- This is CPU and disk, not network; the duration on a long PDF was not measured.
- Fix: a small worker, keeping the existing `_text_cache`.

**P2-5. A truncated `settings.json` stops the app from launching.**
- Where: `load_json` has no error handling (`main.py:509-515`) and runs in `__init__` (`:265-273`). `float(self.settings.get(...))` at `:389-390` is also unguarded.
- The file is rewritten in place with `open(..., "w")` at `main.py:3579`, `:3963` and `:5170`; the first runs on every model-box change. Other stores already write atomically (`services/model_watch.py:211-215`, `services/routing_advisor.py:638-642`).
- Scenario: a kill or full disk between truncate and close leaves a 0-byte file. The next launch raises `JSONDecodeError` with no window; a frozen build shows nothing.
- Fix: one atomic `save_settings()` (temp file plus `os.replace`), and a tolerant load that keeps the bad file as `.bak` and starts on defaults.

**P2-6. A deliberate Booth Stop is reported as a crash (QH-6, stands).**
- `stop_conversion` kills the process with no stop flag (`agents/audiobook/panel.py:1133-1142`).
- `handle_error` then shows a critical dialog for `QProcess.Crashed` (`:842-856`), and `handle_finished` shows a second one (`:937-945`). The count of two is from reading Qt's kill semantics, not from a run.
- In-flight chunks are still paid and unrecorded (`conversions.py:119-130`, `converter.py:90`).
- Fix: set a `_stopping` flag in `stop_conversion` and branch on it in both handlers.

**P2-7. Label, the Suno panel and Sitebuilder still resolve requests by agent name (QM-15, stands).**
- Where: `agents/music/panel.py:211,240,269`; `agents/music/suno_panel.py:217`; `agents/webdesign/panel.py:192,221,233`. The `authorize_request` docstring forbids it (`main.py:4503-4510`).
- Their Stop also closes the run as "error": Label through the default reason (`music/panel.py:268-269`), Sitebuilder with `error=error` (`webdesign/panel.py:232-233`), which calls `offer_failover` after a user's own Stop (`main.py:5554-5557`).
- Fix: keep the token and abandon with `reason="stopped"` in `stop()`, as Herald does (`social/panel.py:511-513`).

**P2-8. The lint ratchet compares counts from an unpinned tool.**
- `.github/workflows/quality.yml:31` runs `pip install ruff` against `baseline.json` (`"ruff": 189`). `TODO.md:63` records CI red at 232.
- The playbook's current practice is to compare lint findings only at a pinned version, so the delta cannot be split between new findings and a tool bump.
- Fix: pin ruff in `requirements-dev.txt` and CI in its own commit, then re-measure.

## P3

- **Usage write after the pop.** `record_request` pops the pending context (`main.py:5502`) before `log_request` writes (`:5506`). An sqlite error then loses both the reservation and the usage row, and the panel's finish handler aborts half-way. Fix: write first, pop after.
- **Non-atomic manifest.** `json_dump` (`converter.py:237-238`) is not atomic and Stop is a kill. A truncated manifest fails `json_load` (`:656`) on every resume as a "Fatal error" (`:1402-1405`). The window is microseconds. Fix: temp file plus `os.replace`, and rebuild from chunk files when unreadable. Shared copy: change all copies in one session.
- **Whitespace-only chunking.** `chunk_text` (`converter.py:581-611`) splits on whitespace only. Text with no spaces (CJK) or one oversized token becomes a chunk over the provider limit, and the book can never finish. It also re-encodes the whole chunk per word. Read only, not run.
- **Converter globals.** `convert()` mutates module globals (`converter.py:1262-1287`). Harmless for the desktop (one subprocess per run); a second in-process call inherits the first call's provider and voice.
- **Quill Publish and Market.** Controls are cleared and disabled before the busy check, so a "[Busy]" return leaves Generate disabled and the output erased until Stop is pressed (`agents/author/panel.py:1597-1607`, `:1718-1729`). Fix: move the check up.
- **Connections never closed.** `with get_connection() as conn:` commits but never closes; 125 sites rely on refcounting (`services/database.py:665-670`). Fix: wrap in `contextlib.closing`.
- **Pricing seed.** `_seed_pricing_from_json` does `float(prices.get(...))` unguarded (`database.py:883-893`). A `null` in the user-editable `pricing.json` raises inside `init_db` and blocks launch.
- **Broad handlers.**
  - Count: I count 245 `except Exception` in app code by AST (the brief says 248), and 54 with no call and no raise in the body.
  - Those 54: fallbacks to a default, a seeded list or "unknown". None sits on a billing write.
  - Where real failures are swallowed: handlers that log and carry on. `agents/audiobook/panel.py:788-798` (QM-7, stands) runs a paid conversion with no ledger row. `main.py:1313-1314` loses a measurement call's bill to a stderr line.
  - Logging: `_note_failure` only prints to stderr (`main.py:4439-4454`), and its docstring still names `/tmp/sentinelai_launch.log`.
- **Daily caps skip in-flight reservations (QM-2, stands).** `main.py:4529-4541`.
- **Kernel validates inline.** It never enters `_pending_requests` (`main.py:4246-4270`), and that block duplicates `current_api_permissions()` (`:4246-4255` against `:4456-4467`).
- **Unknown price estimates €0 (QM-3, stands).** `main.py:605` and `services/usage_tracker.py:134-135`, against the lab rule "a zero price means unknown, not free".
- **Stop and error bill €0 (QM-4, stands).** `main.py:5781-5796`, `:5550-5557`.
- **Automatic measurement spends without a click (QM-1, stands).** `services/local_ratings.py:56`; `main.py:1169-1179`, `:1211-1248`. It is billed on chars/4 (`:1304-1314`).
- **Schedule Drafts overwrites status (QM-14, stands).** `agents/social/panel.py:793-812`. The queue's job row still blocks a duplicate publish for posts sent through the queue (`agents/social/queue.py:116-121`); a manual Mark Posted was not traced.
- **Hard-coded path.** `services/narrator/converter.py:30` holds `a hard-coded home-directory path`, against the lab rule. Shared copy.
- **Dead code.** `main.py:3757`, `services/tool_runner.py:14`, and the disabled "Realtime Monitor" button (`main.py:3444`).
- **No throttle in the cloud companion (coordinator's question 2).** `cloud/reading_compass.py` has none on `/auth/start` (`:243-258`), `/auth/callback` (`:261-300`) or `/api/session` (`:318-323`). A grep for limit, throttle, 429 and Limiter finds nothing, and `cloud/requirements.txt` has no limiter. An unauthenticated caller who sets a matching `state` cookie and parameter makes `/auth/callback` send one outbound POST to Google per request (`:269-273`). Severity belongs to the security review.
- **Maintainability.** `main.py` is 6,725 lines in one class. Chat keeps a second request model in `pending_*` attributes (`main.py:4298-4309`) beside the token model. Suggested next extraction: the request guard (`:4479-4592`, `:5417-5617`) into its own class with the worker registry from P1-1 and P2-1.

## Earlier audit findings in this area: status today

| ID | Status | Current evidence |
|---|---|---|
| QB-1 | Fixed | Draft never cleared, revise sends the full selection, error and Stop apply nothing: `agents/author/panel.py:1125-1160`, `:1186-1218`, `:1255-1337` |
| QB-2, QB-3 | Stand | P0-1, P0-2 |
| QH-2 | Stands | `ui/workers.py:405-409` returns silently after an Omni Stop; `agents/video/panel.py:1137-1200`; `gemini_client.py` unchanged, not re-read |
| QH-6 | Stands | P2-6 |
| QM-1 to QM-4 | Stand | P3 list |
| QM-5 | Stands | `converter.py:181`, `:89`; vidforge files unchanged, not re-read |
| QM-7 | Stands | `agents/audiobook/panel.py:788-798` |
| QM-11 | Stands, wider | P1-2, P2-2 |
| QM-12 | Stands, now a crash | P1-1 |
| QM-13 | Not re-read | `kdp_csv_parser.py` unchanged since `63cefbf` |
| QM-14, QM-15 | Stand | P3 list, P2-7 |

## Checked and fine

- No `QThread.terminate()` anywhere; the only `terminate()` calls are on subprocesses.
- The release-kit driver waits for and retires each worker (`ui/release_kit/driver.py:246-254`).
- `local_ratings.measure` cannot strand its worker (`services/local_ratings.py:672-725`).
- Booth defines success by the output file, not the exit code (`agents/audiobook/panel.py:895-897`).
- Video, teaser and Booth rows settle before billing.
- `DaemonWorker` is sound for read-only fetches (`ui/workers.py:132-182`).

## Could not verify

- P1-1 and P2-1 inside the running app; only the isolated pattern was run.
- Whether CI is green, and the cause of the ruff delta.
- Durations of the UI-thread blocks, and the dialog count on Booth Stop.
- `agents/video/workers.py`, `ui/panel_routing.py`, most of `ui/dialogs.py`, the release-kit `ledger`, `runner` and `stages`, the vidforge internals, and `main.py` outside the regions cited.
- Whether a Reel render and a Herald clip can safely run `video_studio.produce` at the same time.
- Deployment-level limits for `cloud/` (kept outside the repo).
