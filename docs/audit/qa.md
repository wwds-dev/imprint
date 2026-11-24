# QA audit: Imprint (whole repo), `main` at 45f705d

Foundry phase: Verify (7), read-only. Citations were re-anchored on 45f705d; the cited files other than `main.py` and `ui/dialogs.py` are unchanged since ec1cda5, and the lines cited in those two were re-checked. Playbook `docs/playbooks/qa-engineer.md` is `status: current`, last reviewed 2026-10-14 (41 days), so it is not stale. Its model-testing rule is still marked baseline (2026-11-11, not verified by a radar run).

## Verdict: FAIL — not at a professional level, not ready to be used with paid keys

- **Open money bugs:** four known paid-path defects are still open and no test fails because of them (QB-2 Booth resume, QB-3 Herald clip, QH-2 Omni Stop, QH-1 Reading Compass).
- **Red CI:** `quality` is red on the default branch, and the run cannot be replayed because the seed is not printed.
- **Flaky tests:** one CI failure is a confirmed order-dependent state leak through the shared test database (reproduced). The other is most likely a fixed-sleep race (not reproduced).
- **Mutation check not done:** eight mutants were prepared but not run, because both plugin-injected test runs were declined at the permission prompt. I did not retry them by another route.
- **What is good:** the validator and the core guard have real tests that assert refusals, reservations and billed amounts; isolation of keys, settings and the database is solid; only nine fixed `qWait` calls exist in the whole suite.

The local full run you reported (2596 passed, 2 skipped, 31 xfailed, 0 failed on ec1cda5) is consistent with both CI failures being order- and load-dependent.

## Success-measure checks

| Check | Result |
|---|---|
| Success measure demonstrated | No. "Agents deliver what they promise" fails on the four open money findings. |
| Suite green in every listed mode | Local: green once (your run). CI: red (run 45069135153; 2 failed, lint also failed). |
| Mutation check | Not executed (see table). |
| Branch coverage | No number exists. CI runs `coverage run` but never `coverage report`, and there is no threshold (`.github/workflows/quality.yml:22`). |
| Unit tests never call a live model | Holds by construction for keys (`tests/conftest.py:92-113`) and ratings (`:183-188`). There is no socket-level tripwire, so an unmocked keyless call would not fail loudly. |
| Live eval suite, cost recorded | Not done. `docs/foundry/model_use.jsonl` does not exist, and `docs/foundry/plan.toml` has no `eval_budget_usd`. By the playbook this counts as over budget until entered. |

## Root cause of the two CI failures

### 1. `test_refresh_books_keeps_non_default_settings` ('Kore' == 'verse'): confirmed, reproduced

It is a three-module chain through the session-wide temp database (`tests/conftest.py:71`), not the module's own `window` fixture.

1. `tests/test_booth_routes.py:120` starts a Gemini conversion with `run_conversion` stubbed. That leaves a `running` row with provider `gemini`, voice `Kore`. The `booth` fixture deletes rows at setup only (`:62`), never at teardown.
2. Any later module that builds a window and spins the event loop fires `QTimer.singleShot(0, self._resume_provider_jobs)` (`main.py:439`). Booth's startup scan then switches the route to the dead row's provider (`agents/audiobook/panel.py:1100`), and `_route_changed` saves it (`:533`) into the shared database.
3. Every window built afterwards starts on Gemini voices (`agents/audiobook/panel.py:223`). `setCurrentText("verse")` at `tests/test_audiobook_conversions.py:314` is then a no-op on a non-editable combo.

Reproduction (deterministic, fails with the exact CI message):

```
.venv/bin/python -m pytest -q -p no:cacheprovider -p no:randomly \
  "tests/test_booth_routes.py::test_the_chosen_route_is_what_runs_and_what_is_billed" \
  "tests/test_settings_keys.py::test_endpoint_rows_warn_about_http_and_foreign_hosts_but_still_save" \
  "tests/test_audiobook_conversions.py::test_refresh_books_keeps_non_default_settings"
→ 1 failed, 2 passed   (E AssertionError: assert 'Kore' == 'verse')
```

Alone it passed 3 of 3; with only the Booth test before it, it passed. The CI seed is unknown, so the CI order itself could not be replayed.

### 2. `test_endpoint_rows_warn_about_http_and_foreign_hosts_but_still_save` (status "default"): probable, not reproduced

The test waits a fixed `QTest.qWait(600)` (`tests/test_settings_keys.py:293`) for a 400 ms single-shot timer (`ui/dialogs.py:605-611`). That leaves 200 ms for everything else on the GUI thread. The same file already has `_wait_until` (`:111`), whose docstring says a fixed sleep is "flaky under load"; it was applied to one test (`:342-350`) and not to this one or to `:266-273`.

- Alone: passed 3 of 3.
- With a 0.3 s and a 0.7 s stall posted before the wait: passed both, so a stall at the start of the wait is harmless.
- First event-loop turn after building the window: 117 ms locally.
- Remaining hypothesis: a slow slot that starts before 400 ms and ends after 600 ms, such as the module window's deferred startup work (`main.py:439-446`) under coverage tracing on a CI runner. The experiment for this was declined, so it is unconfirmed.

## Findings

### P0

| ID | Where | Scenario | Fix |
|---|---|---|---|
| P0-1 | `agents/audiobook/panel.py:706-749`; no test | QB-2 is open: after the source text changes, Booth authorizes only the remaining share while the converter re-narrates the whole book. No test changes a source between runs. | Fix per the audit, with a failing-first test that edits the book between two `start_conversion` calls and asserts the full estimate is authorized. |
| P0-2 | `agents/social/panel.py:616-619`; no test | QB-3 is open: a Herald clip is authorized as `"openai"` whatever provider renders the scene images. No test sets Gemini or Qwen visuals with that box unticked. | Reuse the Video tab's provider check; test that an unticked image provider refuses the clip. |
| P0-3 | `ui/workers.py:407-409`; no test | QH-2 is open: Stop on a Gemini Omni render returns before saving the paid clip. No test stops an Omni render. | Fix per the audit; test with a fake client that completes after cancel and assert the bytes are saved and the row closed. |

### P1

| ID | Where | Scenario | Fix |
|---|---|---|---|
| P1-1 | `tests/test_booth_routes.py:54-93`; `tests/conftest.py:71` | CI failure 1 above. Any module that leaves a `running` conversion row changes Booth's saved route for all later windows. | Delete `audiobook_conversions` rows in the `booth` fixture's teardown, and reset the saved route. Better: give each module-scoped window a fresh database. |
| P1-2 | `tests/test_settings_keys.py:266,270,273,293` | CI failure 2 above: fixed 600 ms wait on a 400 ms timer. | Replace the four `qWait(600)` calls with `_wait_until(...)` on the expected label text. |
| P1-3 | `.github/workflows/quality.yml:22` | CI runs `pytest -q`, which hides the pytest-randomly seed and skip reasons; it sets no `--timeout=120` and no `-W error::pytest.PytestDeprecationWarning` (playbook practices). The failed run cannot be replayed, and the 27 CI skips against 2 local are unexplained. | Add `-p randomly -rs`, print the seed (`-v` header or `--randomly-seed=$RANDOM` echoed), add the timeout and the warning filter, add `coverage report`. |
| P1-4 | `cloud/reading_compass.py:358,387,573`; `tests/test_reading_compass_contracts.py` | QH-1 is open: the four existing tests cover `cloud/contracts.py` only. `enqueue` and `run_worker`, which narrate whole books with no cap, have no test. | Test that `enqueue` refuses without an acknowledged estimate and that a failed job is not re-queued at full cost, once the fix exists. |
| P1-5 | process | The mutation check and the live eval were not done, and no eval budget is defined. | Run the prepared mutants (below) with the owner's approval; set `eval_budget_usd` and record one eval run. |
| P1-6 | `tests/TEST_PLAN.md` §5 P0 | The plan's two P0 items do not exist: `tests/test_no_paid_path_outside_guard.py` and `tests/test_crash_recovery.py`. `tests/fixtures/` (database snapshots) does not exist either. | Build the guard sweep first; it would have caught P0-2. |

### P2

| ID | Where | Scenario | Fix |
|---|---|---|---|
| P2-1 | `tests/test_booth_routes.py:186-207` | Only the "Yes, resume" answer to "Settings changed" is tested. The "No, start fresh at full cost" branch (`agents/audiobook/panel.py:745-748`) has no panel-level test. | Add a test answering No and asserting the authorized amount equals the whole estimate. |
| P2-2 | `tests/test_cost_and_limits.py:142-147` | The permission-checkbox test covers six providers; `higgsfield` and `elevenlabs` are missing, though both have boxes (`main.py` `current_api_permissions`). | Add both to the parametrize list. |
| P2-3 | `tests/conftest.py` | No socket tripwire (the plan's own rule, `tests/TEST_PLAN.md:211-213`). Seven test files name loopback or host addresses; I did not confirm each is mocked. | Autouse fixture that makes `socket.socket.connect` raise outside an allowlist. |
| P2-4 | `tests/test_booth_routes.py:162` | `pytest.skip` inside a test when the ranking does not offer a cheaper narrator: the assertion silently disappears when the profile shifts. | Pin the profile in the test so the branch is always exercised. |
| P2-5 | `pytest.ini` | No markers registered and no `addopts`; the plan's tiers T3 to T6 (`live`, `recovery`, `build`, `soak`) have zero tests. | Register markers when the first such test lands. |

### P3

- `tests/test_audiobook_conversions.py:267-271`: the docstring sits after the first statement, so it is not a docstring.
- `pytest.ini:12-13` and `CLAUDE.md` still say the suite takes about 90 s; it takes 39 to 46 minutes.
- `tests/READINESS_GATE.md` §3 E ("green on three seeds, no flake") is no longer true.

## Test quality on the money paths

| Path | Verdict | Evidence |
|---|---|---|
| Validator (permissions, caps) | Real. Asserts refusal, scope and wording; includes the exact-boundary case. | `tests/test_cost_and_limits.py:142-186`, `:565-575` |
| Request guard (flat cost, in-flight reservation) | Real. Drives `authorize_request` and checks refusal and the billed figure. | `tests/test_request_guard.py:455-493` |
| Per-unit pricing (zero means unknown) | Has a named test. | `tests/test_cost_and_limits.py:546` |
| Booth ledger maths | Real for the Qt-free ledger. Panel tests call `_close_request` and `handle_finished` directly with restored tokens, never a converter run. | `tests/test_audiobook_conversions.py:56-68`, `:103-146` |
| Booth resume after a changed source | No test (P0-1). | |
| Herald clip provider | No test (P0-2). | |
| Omni Stop | No test (P0-3). | |
| `cloud/reading_compass.py` | No test of the paid worker (P1-4). | |

## Mutation table

None of these was executed. The "expected" column is my reading of the tests, not a result.

| ID | Mutation | Run? | Expected, by reading |
|---|---|---|---|
| M1 | `services/validator.py:124` drop the permission-box check | No | Caught by `test_paid_provider_requires_its_checkbox` |
| M2 | `services/validator.py:183` drop the daily cap | No | Caught by `test_request_over_daily_budget_is_refused` |
| M3 | `services/validator.py:140` agent cap ignores today's spend | No | Not caught by `test_cost_and_limits.py:175` (no prior spend); probably caught at `:570-575` |
| M4 | `main.py:4529` in-flight reservation set to 0 | No | Caught by `test_in_flight_reservations_count_against_the_caps` |
| M5 | `agents/audiobook/conversions.py` `run_spend_eur` drops `run_baseline` | No | Caught by `test_remaining_fraction_and_run_spend_math` (7.0 against 3.0) |
| M6 | `services/per_unit_pricing.py` zero rate returned as free | No | Probably caught by `test_zero_in_the_price_table_reads_as_unknown_not_free` |
| M7 | `main.py` flat cost validated as 0 | No | Caught by `test_flat_cost_is_what_gets_validated` |
| M8 | `agents/audiobook/panel.py:747` fresh start authorizes the remaining share | No | Likely survives (P2-1) |

The harness and the eight specs are ready outside the repo in the session's temporary scratch folder (`qa_mutant.py`, `M1.json` to `M8.json`). It patches one module in memory and writes nothing to the repo. That folder is temporary, and I did not confirm it still exists after the session's scratch location moved.

## xfails, skips, sleeps

- **31 xfails:** all in `tests/test_docs_integrity.py`, `strict=True`, each tied to an open documentation row (`:38-43`, `:396`). Justified: a strict xfail that starts passing fails the suite. None hides a code or money defect.
- **Skips:** 2 locally, 27 on CI. The candidates are 13 "vidforge is not importable" skips in `tests/test_video_jobs.py`, the three sibling-checkout drift tests, and the ffmpeg-dependent tests. If so, the shared-copy drift guards and the video job tests do not run on CI at all. Reasons are not printed, so this is unconfirmed (P1-3).
- **Fixed waits:** 9 `qWait` calls in total, 8 in `tests/test_settings_keys.py` and 1 in `tests/test_fiverr_orders.py`. The `time.sleep` calls are 1 to 5 ms in three release-kit tests.

## Prior audit (2026-11-18): what has tests now

| Item | Now |
|---|---|
| QB-1 Quill draft loss | Fixed 2026-11-20; `tests/test_author_draft_safety.py` exists. I did not check whether it streams. |
| QB-2, QB-3, QH-1, QH-2, QH-6 | Still open in `TODO.md:61,62,95,96,100`; no tests. |
| `services/runtime_paths.py` (test plan gap 3) | `tests/test_runtime_paths.py` exists. |
| DeepSeek and Kimi clients | No test file names them. |
| CI (test plan gap 1) | Exists, red. |

## Could not verify

- The settings-test race (failure 2): hypothesis only.
- All eight mutants: not run.
- The CI seed and order; the reasons for the 27 CI skips.
- Branch coverage: no report produced anywhere.
- Whether any test touched `data/imprint.db`: the file was modified 2026-11-23 00:39, and I cannot tell whether the app, another session or a test wrote it.
- Whether the seven test files that name loopback addresses are fully mocked.
- The lint job failure (ruff ratchet 232 against 189): taken from commit ec1cda5's message, not re-run.
- Anything in the money files after 45f705d.

Repo state at the end: `git status` clean on 45f705d; no tracked file changed, no untracked file left.
