# QA verify: model-watch-media (branch feature/model-watch-media, uncommitted), 2026-10-14

Verifier: qa-engineer. Playbook current (2026-10-14).
Verdict: **PASS with gaps** — 1 P1 test gap from this change, 1 P1 pre-existing order leak, 3 P2, P3s. Mutants 35/38 killed.

## Suite (exact)
| Run | Tree | Result |
|---|---|---|
| `pytest -q -p no:randomly` | change | 1577 passed, 2 skipped, 6 subtests passed (1039 s), exit 0 |
| `--randomly-seed=28367` | change | 1 failed (`test_creator_resume.py::test_pre_feature_rows_are_never_reconciled`), 1576 passed, 2 skipped (793 s) |
| `--randomly-seed=28367` | clean HEAD 67bb302 (scratch worktree) | 2 failed (same creator test + `test_audiobook_player.py::test_stopping_does_not_overwrite_the_saved_position`), 1504 passed, 6 skipped |
Suite takes 13–17 min, not ~90 s as README says.

## Pre-existing, confirmed independently
1. Creator-resume leak: `tests/test_teaser_routes.py:221-226` leaves a `reserved` row in the shared temp DB; `resume_pending_teasers` picks it up. Reproduced with two tests in order on HEAD.
2. Audiobook position test is real-time dependent (`tests/test_audiobook_player.py:250-261`); fails on HEAD under load.
3. `test_theme` segfault (`ui/text_fit.py:167`): not reproduced in 3 full + 8 targeted runs. Change adds one `deleteLater` site and one more never-closed module GodAI — plausible exposure, unproven. Open.

## Measures → tests
All of M1–M7 mapped to named tests in `tests/test_model_watch_media.py` (plus `test_agent_panel.py`, `test_env_template.py`); no-network via fakes at session/factory boundary. M6: `tests/test_model_watch.py:233-238` fixture gained a `_media_today` pin; no assertion changed.

## Mutation: 38 planted, 35 killed
Survivors: **X4** `main.py:3970` default `False`→`True` passes (off-by-default unpinned); **W2** `ui/workers.py` ~635 stray `path_probed` passes (`test_the_worker_with_defaults_behaves_as_before` asserts without pumping events); **D7** `model_watch_digest.py` dismissable ignoring `probe_rows()` passes (Design says Dismiss only for new/removed media).

## Changed-line coverage (stdlib trace)
model_watch 128/135 · digest 133/136 · main 156/163 · status_cards 90/94 · qwen_client 38/42 · workers 25/29 · gemini/higgsfield/media_catalog/panels/base 100%.

## Findings
- **P1** Probe default-off not pinned by a test (X4).
- **P1 (pre-existing)** teaser reserved-row leak breaks creator-resume test under random order.
- **P2** Vacuous worker-defaults test (W2). Audiobook real-time flake (pre-existing). Theme segfault undiagnosed.
- **P3** D7 Dismiss visibility unpinned; untested copy ("{Agent} use", "+N more video and image notices", single/plural headlines); `acknowledge_media(models=...)` unused/untested; no window-level test for media no-key baseline.

## Re-verify after fix round 1 (2026-10-14): PASS
- Closed: P1 off-by-default (X4, X4b killed), P1 teaser leak (`test_teaser_routes` then `test_creator_resume`: 16 passed), P2 W2 (killed), D7 (killed).
- New fix-logic mutants 6/8 killed (N1, N1b, N3, N4, N6, N7). Survived: **N2** (delete untracked-counter prune, `services/model_watch.py:326-327`) — real bug path untested: tracked→missing→untracked missing→re-tracked missing gives a removal after one new miss; **P2**. **N5** pending-media cap keeps oldest instead of newest — **P3**, test asserts length only.
- Orchestrator full suite after round 1: fixed order 1594 passed/2 skipped; seed 28367 1 failed (pre-existing audiobook flake)/1593 passed. Ruff ratchet 189 = baseline.

## Fix round 2 (2026-10-14)
N2 and N5 pinned (`test_an_untracked_absence_forgets_the_count_before_it_is_tracked_again`, `test_the_pending_media_cap_keeps_the_newest`). Full suite fixed order: 1603 passed, 2 skipped. Ratchet 189 = baseline.
