# Verify: deps-security-upgrade-2026-10 (2026-10-14)

Commands (seed `--randomly-seed=28367`, `QT_QPA_PLATFORM=offscreen`, fresh uv venv per tree):
- Upgrade branch: `3 failed, 1428 passed, 3 skipped, 6 subtests passed (15:12)`.
- Clean `origin/main`, old pins: `3 failed, 1428 passed, 3 skipped, 6 subtests passed (13:45)`.
- Identical failures in both: `test_creator_resume::test_pre_feature_rows_are_never_reconciled` (order-dependent: row `qwen-live-1` from `tests/test_teaser_routes.py:226` leaks; passes in isolation and after test_teaser_routes in fixed order), `test_audiobook_player::test_stopping_does_not_overwrite_the_saved_position` (known timing flake; passes alone), `test_benchmarks_drift[sentinel]` (Sentinel carries the WRITE_GUARD port 67bb302, which is only on the model-watch-media branch).
- No regression from the upgrade. Success measure met: `uvx pip-audit -r requirements.txt` -> "No known vulnerabilities found"; ruff ratchet 189 = baseline 189.
- Note: baseline process exited 139 (segfault at interpreter teardown, "shared QObject was deleted directly") after the summary on origin/main; the upgrade run exited 1. Not caused by this change; not investigated.
- Mutation check: not applicable (no new logic).
- Order-dependent `creator_resume` failure is a latent test bug (AGENTS.md); deferred, not part of this change.
