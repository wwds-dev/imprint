# Secure phase: audit P0 money fixes (QB-2, QB-3, QH-2)

- Spec slug: `audit-p0-money-fixes`
- Commit reviewed: `2a66694` (diff `git diff 776828d 2a66694`), worktree `wizardly-hertz-78be15`
- Role: security-engineer, read-only. Date: 2026-11-24.
- Playbook: `docs/playbooks/security-engineer.md`, `status: current`, `last-reviewed: 2026-11-11` (13 days; not stale).
- Verdict: **one P1 (the QH-2 quit path does not work as claimed), no P0.** Booth (QB-2) and the
  Herald and Video key and permission checks (QB-3) hold for the paths they target.

## Threat model (scope of this diff)

- **Assets:** the user's provider API keys and money (OpenAI, Gemini, DashScope/Qwen spend); the
  request guard's ledger and budget caps (a release or under-count lets later spend go past a cap);
  paid output files (Omni clips, audiobook chunk cache).
- **Trust boundaries:** GUI thread and QThread workers (signals are queued across them); the app
  and the provider APIs (provider bytes and statuses are untrusted); the app and its own state on
  disk (SQLite `video_jobs` / `audiobook_conversions`, vidforge `config.yaml`, the output library).
  These are same-user local files: tampering with them requires the user's own account, so they
  are not an attacker boundary here.
- **Entry points touched:** Booth Start (`AudiobookPanel`, user-chosen book file), Herald Make clip
  (LLM brief, then vidforge render), Reel `render_direct` (Gemini Omni) and Stop, the window-close
  shutdown sweep (`main.py:6500-6522`), and the launch-time resume (`VideoPanel.resume_pending_jobs`).

STRIDE in short: **Tampering/Repudiation** of the spend ledger is the real risk class here (wrong
release or wrong bill); **Elevation** means spending on a provider that is not keyed or permitted;
**Information disclosure** means key values in UI or logs (none found); **DoS** covers malformed
input files (pre-existing, tracked).

## Findings

### P1-1: An Omni render interrupted by quitting is swept as "lost" and released, so the QH-2 quit fix never runs

- **Where:** `ui/workers.py:408-417` (write on cancel), `agents/video/panel.py:686`
  (`job_signal` is a queued cross-thread connection), `main.py:6512-6516` (shutdown blocks the GUI
  thread in `worker.wait(2000)`), `agents/video/jobs.py:105-110` (`pending_rows` requires
  `job_id != ''`), `agents/video/jobs.py:115-133` (`sweep_lost` releases every `job_id = ''` row),
  `agents/video/panel.py:1039-1081, 1086` (`_settle_omni_row`, reachable only through `pending_rows`).
- **Scenario:** the user starts a Gemini Omni render and closes the window during the synchronous
  `interactions.create` call (the realistic case, since the call takes as long as the render). The
  job id reaches the DB only through `job_signal -> _external_job -> _persist_transition` on the GUI
  thread. That thread is blocked in `wait(2000)` and then accepts the close, so the id is never
  written.
  - (a) If the call returns within the 2 s, the worker writes the paid clip to `output_path`. On
    the next launch `sweep_lost()` marks the row `status='lost', spend_state='released'` and logs
    "Nothing was billed here". The clip sits orphaned in the library folder with no manifest, and
    the charge never reaches the ledger.
  - (b) If the call does not return, the bytes are lost and the row is released in the same way.
  - In both cases `_settle_omni_row` is never called.
- **Evidence:** reproduced against a temporary DB with
  `scratchpad/repro_omni_lost.py`. A `record_submission` Omni row with no job id, plus the clip on
  disk, gives `swept_lost: [(1, 'gemini-omni-1.1-flash')]`, `pending_rows: []`,
  `row: {'status': 'lost', 'spend_state': 'released'}`, `clip on disk: True`. The new tests
  (`tests/test_reel_omni_stop.py:199-204`) set `job_id="omni-1"` by hand, which is exactly the state
  the real quit path does not produce. Not verified end-to-end in a running app.
- **Impact:** the Stop half of QH-2 is fixed, but the quit half (the commit message and docstring
  say "a cancel at shutdown still writes the bytes, and the next launch settles an Omni row from
  disk") is not. A confirmed Omni spend that the provider most likely charged is released from
  the ledger, so the daily and session caps under-count and later requests can go past them. Case
  (a) also loses a paid clip that is sitting on disk.
- **Fix (pick one, test first with a row that has no job id):**
  - Settle Omni rows before `sweep_lost()` (or exclude them from it): any
    `provider='gemini' AND model=OMNI_MODEL AND spend_state='reserved'` row goes to
    `_settle_omni_row` whatever its `job_id`.
  - Or persist the job id and status from the worker thread itself, using its own short-lived
    SQLite connection, before `job_signal.emit`.
  - In either case, an Omni row with no file and no completed status should not read as free.
    Prefer billing the reservation with a "may have been charged, check Gemini usage" note, in line
    with the rule that unknown is not free. If the owner chooses release, the log line must not say
    "Nothing was billed".

### P3-1: The scene-provider check keys on a different value than the code that spends

- **Where:** `agents/social/panel.py:659-666` (`_scene_model`), `agents/video/panel.py:526`;
  compare `vidforge/vidforge/visuals.py:184` and `vidforge/vidforge/thumbnail.py:25`.
- **Scenario:**
  - Herald compares `cfg.get("visuals.source") != "ai"` exactly, but vidforge lower-cases the
    value. A `config.yaml` with `source: AI` and `image_model: gemini-nano-banana-2.1` skips the
    check, and vidforge then calls Gemini under a request authorized as `"openai"`.
  - The Video tab checks the combo-box `selection`. When `_media_selection()` is `None`,
    `_overrides()` adds no visuals and `config.yaml` decides the image model with no check at all.
  - Both cases need a hand-edited `config.yaml`, so likelihood is low.
- **Impact:** a paid Gemini or Qwen image call with no key or permission check. If the key is
  absent, the call fails and vidforge falls back to a gradient card, so money moves only when the
  key is set but the provider is not ticked.
- **Fix:** in `_scene_model`, use `str(cfg.get("visuals.source", "ai")).lower()` and the same
  default image model as vidforge (`gpt-image-2.5-flare`). On the Video tab, run the check on the
  effective config (`_scene_model(video_studio.load_config(self._overrides(selection)))`), not on
  the selection.

### P3-2: Herald pays for the clip brief before the scene-provider refusal

- **Where:** `agents/social/panel.py:551-571` (brief authorized and sent) versus `:602` (refusal in
  `_on_clip_brief`).
- **Scenario:** with Gemini or Qwen visuals selected but not keyed or ticked, every Make clip pays
  for a chat-model brief and then refuses the render.
- **Impact:** small wasted spend. It was confirmed by the guard, so it is not unconfirmed spend.
- **Fix:** load the config in `make_clip` (aspect and seconds are already known there) and call
  `scene_provider_refused` before authorizing the brief. Keep the second check in `_on_clip_brief`
  for the Apply path.

### P3-3: The Omni clip is written in place, not atomically

- **Where:** `ui/workers.py:416` (and the pre-existing `:431`); `agents/video/panel.py:1052` treats
  any non-empty file as saved.
- **Scenario:** the process exits while `write_bytes` is running (the shutdown wait is 2 s). The
  next launch finds a truncated non-zero file, bills it (correctly, since it was charged) and adds
  a broken clip to the library as "finished and was saved".
- **Fix:** write to `output_path.with_suffix(".part")` and `os.replace` it into place, as vidforge
  already does (`visuals.py:197-198`).

### P3-4: Booth's legacy-row mtime fallback can read an edited book as unchanged

- **Where:** `agents/audiobook/conversions.py:66-77`; `updated_at` is refreshed on every progress
  tick (`conversions.py:154`).
- **Scenario:** this only affects a row written before this commit (no stored hash). If the book was
  edited while that run was still converting (after the converter had loaded the text), later
  progress ticks move `updated_at` past the file's mtime, so `source_changed` returns False. Booth
  then authorizes the remaining fraction while the converter rebuilds the whole book.
- **Impact:** a one-time under-authorization for a narrow migration case. New rows use the stored
  hash and are fine.
- **Fix:** compare the mtime with `created_at` (or the run's start) rather than `updated_at`, or
  treat every row with no hash as changed and accept one extra prompt.

### P3-5: Booth hashes the text before the converter reads it (TOCTOU)

- **Where:** `agents/audiobook/panel.py:711` (hash) and `:817` (stored), then `run_conversion`
  starts the converter, which reads the file again.
- **Scenario:** the book file changes in the seconds between Start and the converter loading it. The
  panel authorizes the remaining fraction and the converter narrates the whole book.
- **Impact:** low; the user has to edit the file during that window. The next interruption is
  detected correctly because the stored hash no longer matches.
- **Fix (optional):** pass the hash, or the extracted text, to the converter and have it refuse
  when its own text hash differs from the authorized one.

## Checked and found fine

- **Spend on providers that are not keyed or permitted (QB-3):**
  - `scene_provider_refused` (`agents/video/panel.py:35-61`) fails closed.
  - `provider_configured` returns `None` for an unknown provider, and `not None` refuses.
  - Every scene-image provider in `services/media_catalog.py` (OpenAI, Gemini, Qwen) maps to a
    `_KEY_ENV` key (`services/recommendations/catalog.py:38-48`).
  - Herald's Apply path re-enters `_on_clip_brief`, so the check runs again on the newly applied
    route.
  - No import cycle: `agents/video/panel.py` imports nothing from `agents.social`.
- **Spend beyond what was confirmed (QB-2):**
  - A changed book now forces the full-cost prompt, and declining sends nothing.
  - The fresh start authorizes `fraction = 1.0`.
  - The hash compare is internally consistent: both sides come from the same `load_text`, and
    chunking inputs are covered by the existing settings branch.
  - The `CASE WHEN ? = ''` update never blanks a stored hash.
- **Omni Stop:**
  - Stop is disabled at `_begin(..., can_cancel=False)`, and `stop()` returns early for an Omni
    context (`panel.py:1208-1212`), so a stray Stop can no longer throw away a paid clip.
  - The Veo and Wan behaviour is unchanged.
- **Settle never spends:** `_settle_omni_row` makes no provider call. `restore_request` re-reserves
  the confirmed `flat_cost_eur`, and the bill equals the confirmed amount. `_resume_done` settles
  before billing, so a crash cannot double-bill.
- **File writes and path trust:**
  - `output_path` comes from `external_output_path`, which joins `output_root()` and
    `history.new_slug`. The slug is reduced to `[a-z0-9-]` (`vidforge/vidforge/history.py:101-109`),
    so there is no traversal from the topic or the LLM brief.
  - The settle path reads `output_path` from the app's own DB row, which is same-user state.
    `is_file()` following symlinks is acceptable at that trust level.
  - An empty file is not treated as saved (`st_size > 0`).
- **SQL:**
  - All new statements are parameterized (`conversions.py:103-143`).
  - The new column is added through the existing constant-string migration list
    (`services/database.py:805`), with no interpolation of row data.
- **Untrusted data in UI or logs:**
  - New UI strings carry only the book's file name (the user's own), chapter counts, the estimate,
    and catalog labels.
  - Omni log lines use the slugified `row['slug']`.
  - No provider response text was added to the UI.
- **Secrets:** no key value is printed or logged anywhere in the diff. The messages name only the
  provider or the env-var family.
- **Tests:**
  - `tests/test_reel_omni_stop.py`, `tests/test_herald_clip_provider.py` and
    `tests/test_booth_source_changed.py` use fake clients and workers, use the placeholder key
    `test-not-a-real-key`, and replace Booth's converter with a recorder (`run_conversion`
    monkeypatched).
  - `tests/conftest.py` isolates the DB and strips credential env vars.
  - Run:
    `/Users/as/Documents/lab/active/imprint/.venv/bin/python -m pytest -q -p no:randomly tests/test_reel_omni_stop.py tests/test_herald_clip_provider.py tests/test_booth_source_changed.py`
    gave `19 passed, 1 warning in 13.02s`. The full suite was not run (not asked).
- **Dependencies:**
  - The diff adds no dependency (only `hashlib` and `os`, both stdlib).
  - The installed set (`imprint/.venv`, one site-packages, 82 dists) was checked through the OSV
    querybatch API, because pip-audit and osv-scanner are not installed. Results:
    - `pypdf==6.21.1`: 10 HIGH (DoS on a crafted PDF; fixed by 6.21.4).
    - `soupsieve==2.9`: 2 HIGH and 2 MODERATE (ReDoS and recursion; fixed by 4.0.0).
    - `pip==24.0` and `setuptools==79.0.1`: advisories in tooling, which do not block release.
  - All of these predate this commit and are already tracked (`TODO.md:75`; audit S-3/S-4). Under
    the playbook, the HIGH runtime advisories block release unless the owner defers them in writing.

## Not verified

- P1-1 was shown on the job table directly, not by quitting a running app with a live Omni call.
  Whether Gemini bills an interaction whose client disconnected is not documented in the code.
- Whether the guard stops the converter when its billed amount passes the authorized reservation
  (relevant to P3-4 and P3-5) is outside this diff and was not checked.

## Resolution (author session, 2026-11-24)
- **P1-1 fixed:** synchronous (Omni) rows are excluded from `sweep_lost` and settled by
  `_settle_omni_row` (a saved clip lands and bills once; no clip bills the confirmed cost as
  "may have charged"); `closeEvent` also asks before quitting during an Omni render.
- **P3:** case-insensitive `visuals.source` and the pre-brief check in Herald fixed; atomic clip
  write fixed; the Video tab's menu-vs-config check and Booth's mtime/TOCTOU windows are
  `TODO.md` rows. The dependency advisories (`pypdf`, `soupsieve`) predate this change and stay on
  `TODO.md:75` for the owner's release decision.
