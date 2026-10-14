# Code review: model-watch-media (branch feature/model-watch-media, uncommitted), 2026-10-14

Reviewer: code-reviewer (read-only). Playbook current (2026-10-14). Targeted tests: 183 passed, 2 skipped; full suite `-p no:randomly` exit 0 (no count line). ruff not available to reviewer. Two P2s reproduced against real `ModelWatch` (scratch script).
Verdict: **no P0/P1**; 2 P2, 8 P3.

## P2
- **P2-1 Upgrade raises a false chat removal for a still-listed model.** `services/model_watch.py:204` (listed filtered by new `is_chat_model`), `:283-288` (`_count_misses` checks presence against the filtered list); trigger `main.py:4087`. A v1 `last_live` with `gemini-omni-1.1-flash`, selected by an agent (selection kept per main.py:4150), still listed by Google → removal after two UTC days. Reproduced. Fix: check presence against raw `model_ids`, or drop tracked non-chat ids from the chat lane; test with a v1 fixture + selected omni id.
- **P2-2 Miss counter never reset while untracked.** `services/model_watch.py:283-288`. Absent while selected (1) → untracked and listed again (no reset) → re-selected months later, one blip confirms. Reproduced (10-02 absent, 10-03 present untracked, 12-01 absent → Removal). Breaks "present N, absent N+1 and N+2". Fix: reset `missing` for every listed id regardless of tracking; prune untracked entries; add sequence test.

## P3
- P3-1 Chat overflow copy "+N more — all are in the model menus, marked NEW" counts removed rows. `ui/status_cards.py:530-533`.
- P3-2 Chat removal persists after the model reappears if it is no longer tracked; Design says it drops on its own. `services/model_watch.py:283-286`, copy `ui/status_cards.py:361`. Fix: drop any removal whose id/canonical is in new `listed`.
- P3-3 Qwen page without `total` stops after page 1 → false media removals. `services/qwen_client.py:318`. Fix: page while `len==MEDIA_PAGE_SIZE`, or raise `MediaListUnsupported`.
- P3-4 Qwen media list uses shared `video_session` from scan thread while Video panel uses it from another worker. `services/qwen_client.py:285`; `agents/video/panel.py:953,1075`. Fix: private Session.
- P3-5 Stale "missing" probe rows never pruned. `services/model_watch.py:398-421`.
- P3-6 Probe checks catalog paths, not `.env` override paths actually used for renders. `main.py:3991`. Fix: include override paths or note override in footer.
- P3-7 `dismiss_media_notices` unhandled `OSError` on save. `main.py:4172` (same gap in `dismiss_new_models`). Wrap with `_note_failure`.
- P3-8 Doc drift: `docs/company/app-context.md:27` says no `docs/adr`; ADR 0001 still "proposed" though approved.

## Verified correct
Removal rule (UTC-day dedupe, canonical snapshot present, cap 2, failed/empty lists never observed, panels pass `tracked=()`); ADR 0001 additive migration and silent media baseline; threading (single GUI-thread writer, Qt-free model_watch/digest, sequential worker lanes, cancel checks); probe gate (configured + setting default False + chip + validator, `/estimate` only, 15 s, no retry, zero calls when gated); chat dropdown filters (main.py:3880-3885, 4083-4089, AgentPanel._apply_live); single shutdown literal in `media_catalog.VEO_SHUTDOWN` with grep test; Gemini/Qwen error handling.

## Re-review after fix round 1 (2026-10-14)
Targeted (fixed order, teaser before creator_resume): 164 passed. **No new P0–P2.**
- Fixed and pinned by tests: CR P2-1, P2-2, P3-1, P3-2, P3-3, P3-7, P3-8; Sec P2-1 (usage row optional, not added), P3-1, P3-3, P3-4 (also kills QA X4); QA D7, W2.
- CR P3-4 fixed (private session); test weak. CR P3-5 partly (pruned only on probe days). Sec P3-2 partly (no cancel between Qwen pages, no per-page cap).
- Teaser leak fix sound (`tests/test_teaser_routes.py:227-241`). Segfault fix (`tests/conftest.py:151-166`, module gc.collect + `owned` fixture) is a mitigation; root fix = close windows in fixture teardown (TODO).
- **New P3-A** stale "Seedance path not answering" row can never clear once the probe is switched off/gated (D7 hid Dismiss; pruning only runs on probe days). Reproduced. Fix: show/keep probe rows only while gate is "ok", or clear `probes` when not.
- **New P3-B** id cap `sorted(...)[:MAX_LISTED_IDS]` (`services/model_watch.py:123`) can cause a false removal for a tracked id past the 2,000th. Reproduced. Fix: presence against uncapped valid set; cap only storage.

## Fix round 2 (2026-10-14)
P3-A fixed via `ModelWatch.clear_probes()` when the gate is not "ok" (`test_a_not_answering_row_clears_once_the_probe_may_not_run`). P3-B fixed: presence against uncapped `valid_ids()` (`test_a_tracked_id_past_the_cap_is_still_present`). Each test fails with its fix removed.
