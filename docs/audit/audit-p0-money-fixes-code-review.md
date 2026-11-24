# Code review: audit P0 money fixes (commit 2a66694)

- Diff: `git diff 776828d 2a66694`; worktree `wizardly-hertz-78be15`
- Phase: 6 Review (code-reviewer, read-only, not the author). Saved by the author session, as
  returned by the reviewer; the resolution section at the end is the author's.
- Playbook `docs/playbooks/code-reviewer.md`: status current, last-reviewed 2026-10-14 (41 days; not stale)
- Tests run: `pytest -q tests/test_booth_source_changed.py tests/test_herald_clip_provider.py tests/test_reel_omni_stop.py` -> 19 passed in 12.61 s (nothing skipped; vidforge importable)
- Mutation check (10 hand mutants on a scratch copy, relevant test files): 8 killed, 2 survived (M4, M9 below)
- Lint: not verified (ruff not installed in `.venv` or on PATH)

## P0
None.

## P1

**P1-1 (QB-2 residual). Booth still authorizes the "remaining" share when the chunk cache is gone; done == total authorizes €0.**
- Where: `agents/audiobook/panel.py:769-771`; `agents/audiobook/conversions.py:41-46`; converter `services/narrator/converter.py:715-721` (`sync_manifest_with_files` marks every missing chunk file `pending`).
- Scenario: a run stops at 10/10 (merge failed) or 7/10 and `<output>/<book>/temp_audio/` is deleted. Text unchanged, so the hash matches. Start authorizes 0% (or 30%); the guard accepts €0 (`main.py:4520-4521`). The converter narrates every chunk. The 2026-11-18 audit names this case under QB-2.
- Fix: derive the fraction from disk (count non-empty `chunk_*.mp3`), `max(remaining_fraction(row), 1 - present/total)`; test that deletes the temp dir.

**P1-2 (QH-2 residual). Quitting during an Omni render loses the paid clip and records €0.**
- Where: `main.py:6514-6516` (`cancel()` + `wait(2000)`); `ui/workers.py:409-417`; `agents/video/jobs.py:114-133` (`sweep_lost`); `tests/test_reel_omni_stop.py:1-13`.
- Scenario: quit while the blocking `interactions.create` runs. Nothing is written, the row never gets a job id, and the next launch's `sweep_lost()` marks it `lost` and releases it. Gemini still charges; the ledger shows €0. `_settle_omni_row` never sees the row.
- Fix: ask in `closeEvent` while an Omni render is in flight; settle an Omni row with no job id conservatively (bill the reserved cost as unknown, probably charged); test a lost Omni row at startup.

## P2

**P2-1. Booth's fingerprint is not the converter's.** `agents/audiobook/panel.py:711` hashes raw `load_text`; the converter hashes `"\0".join(chunks)` after `light_normalize` (`converter.py:219-234`, `:622`, `:1371`). A CRLF or trailing-space re-save (or a touched pre-hash row) triggers a full-cost restart, counts reset, and the run bills cached chunks again. Over-counts. Fix: compare the converter's own hash (its functions read-only, or `manifest.json`).

**P2-2. Two new money branches survive mutation.** M9: the Omni "nothing to resume" branch `released` -> `billed` killed nothing. M4: removing `source_sha256` from the migration list killed nothing (every test builds from `SCHEMA`). Fix: an old-schema migration test; a settle test for an Omni row with a job id, not completed, no file.

## P3
- **P3-1.** Herald pays for the brief before refusing the clip (`agents/social/panel.py:602-607`). Check in `make_clip` too.
- **P3-2.** `_scene_model` fails open for an image id not in the catalog (`agents/social/panel.py:659-666`). Refuse instead.
- **P3-3.** The Omni "cannot be stopped" text is overwritten by the worker's first status, and the disabled button still reads "Stop" (`agents/video/panel.py:570-573`, `:671-684`).
- **P3-4.** The cancel-path write is not atomic (`ui/workers.py:415-416`); a truncated file passes `saved`.
- **P3-5.** Omni rows stranded by the old Stop are billed at the next launch's date; say so.
- **P3-6.** Definition of Done not met in the commit: no CHANGELOG, TODO rows open, manual-test caution row not updated, ruff not run.

## Checked and fine
- Migration is valid and idempotent; both INSERT and UPDATE name their columns; no other writer.
- `open_job` keeps a stored hash when none is passed; `billed_eur` survives a fresh start; decline sends nothing.
- A real text change authorizes and bills the full estimate with counts restarted; the text check correctly takes precedence over the settings dialog.
- Apply re-entry repeats the new checks in Booth and Herald.
- `scene_provider_refused` keeps the Video tab's behaviour.
- Omni settle bills once; `_resume_done` ignores its `worker` argument; completed-but-unsaved bills once and closes.
- `stop()` guard and `can_cancel=False` for Omni; Veo cancel writes nothing.
- Qt: no `QThread.terminate()`; nothing new blocks the UI thread. A PySide6 probe showed a `job_signal` queued during `closeEvent`'s `wait()` is still delivered (probe, not the real window).
- Mutants killed: 8 of 10 (listed in the reviewer's run).

## Resolution (author session, 2026-11-24)
- **P1-1 fixed:** `conversions.cached_chunks()` counts the chunk files the converter will reuse; fewer than the row counts authorizes the missing share and measures the run from that count (`open_job(cached=...)`). Tests: `test_a_finished_run_with_its_cache_deleted_is_not_authorized_at_zero`, `test_a_partly_deleted_cache_authorizes_the_missing_chunks`.
- **P1-2 fixed:** `closeEvent` asks while an Omni render is in flight (`VideoPanel.omni_rendering()`); `sweep_lost` leaves synchronous models alone and `unacknowledged_synchronous()` rows go to `_settle_omni_row`, which lands a saved clip or bills the confirmed cost as "may have charged". Same as the security pass's P1-1. Tests: `test_a_quit_during_the_omni_call_*`, `test_sweep_lost_still_releases_an_asynchronous_submission`.
- **P2-1 deferred** to `TODO.md` (P2; over-counts only).
- **P2-2 fixed:** `test_an_older_database_gains_the_booth_text_fingerprint`, `test_an_acknowledged_omni_row_that_never_completed_is_released`.
- **P3-1, P3-2, P3-3, P3-4 fixed** (pre-brief check, unknown model refused, "Cannot Stop" plus the note in the log, atomic write); **P3-5** stated in the CHANGELOG; **P3-6** done in the same commit.
