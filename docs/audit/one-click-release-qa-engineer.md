# QA: one-click-release, slice 1 (free path)

Role: `qa-engineer`, read-only on code and tests. Did not write the code. 2026-11-21.
Spec `docs/specs/one-click-release.md`, ADR 0005, review `docs/audit/one-click-release-code-reviewer.md`.
Branch `claude/one-click-release-slice1-599646`. **Final commit verified: 274092e** (HEAD at the end).
The branch moved while this ran: mutations began on 3a75f1a, the survivors and the new code were rerun on
41ddc70 (P2-4, P2-5 tests, P3 fixes) and 274092e (P2-5 cancel path). Each result below names its tree.

## Verdict
**Ready for Secure: yes. No P0, no P1.** Slice 1's free path meets its slice-1 success measures with fakes.
Two P2 test gaps and several P3s remain (below); none blocks Secure. The money measures (2, 3 paid, 4) are
slice 2 and are **not verified** here.

## How the runs were made (no overlap)
The worktree was never edited by the mutations. The full suite ran from a detached `git worktree` of the
exact commit (a first copy without `.git` failed three git-dependent tests: artifacts, discarded);
mutations ran on separate scratch copies. `git status` at the end: only `docs/foundry/activity.jsonl`
(the activity log) and this report.

## 1. Success measures (slice-1 form)
| SM | Result | Evidence |
|---|---|---|
| 1 One action → EPUB (SHA = receipt), N PNGs, M MP4s = Short slots, CSV, all in `project_artifacts`, exactly one dialog | **Covered** (audiobook is `not_included` by design) | `test_release_kit_e2e.py::test_one_click_makes_every_output_after_exactly_one_dialog`: 20 PNG = unique quotes, 22 MP4 = Short slots, 57 CSV rows, every file linked, dialogs == 1, usage rows carry job id and cost 0. **Fakes only** for model, voice, ffmpeg. |
| 2 Money ≤ approved, clamp at line | **Not verified** (slice 2). Local cost is always 0. `record_job_item` clamp is unreachable in slice 1 (M45 survives, equivalent today; P3-8 stands) | |
| 3 Unpriced / paid blocks, zero provider calls | **Partly**: slice-1 form covered. Paid text or voice route blocks the estimate; `authorize_job_item` refuses a paid provider with no token and no backend call (`test_a_paid_text_route_blocks…`, `…_refused_by_the_guard_without_a_dialog`). Rate-0 pricing path does not exist yet | |
| 4 Caps refuse before start / pause mid-run | **Not verified** (slice 2; a local route never reaches the validator) | |
| 5 Kill after stage k, resume at k+1, no re-run | **Covered**: `test_killed_after_graphics_resumes_at_the_next_item_without_rerunning` (no second quote request, EPUB and graphics not re-run, s05 redone), `test_resume_verifies_files_and_reopens_only_changed_local_stages`, `test_recovery_pauses_a_running_kit_and_resolves_local_intents`. Booth's chunk cache: n/a in slice 1 | |
| 6 Contract: no provider call without a checked job token | **Covered, static + runtime**. Static walk plus (new in 41ddc70) by-reference and renderer tests. P2-4 verified fixed: planting `return host.run_backend` in the driver now fails `test_a_guarded_function_is_never_passed_around_without_a_grant` (it passed before the fix). Gap: the runtime `grant.check()` itself is untested (F-1) | |
| 7 Existing tests unchanged, migration on an old DB | **Covered**: full suite below; `test_database_migrations.py` +156 lines (old-DB test, `ux_usage_job_item`, one-running index: M39 killed) | |
| Power | **Covered + measured**: see §6 | |

## 2. Review fixes hold (all confirmed by a test that fails when the fix is removed)
| Fix | Mutation | Killed by |
|---|---|---|
| P1-1 `_guarded`/`_crash` (17408bf) | M19 `_guarded` re-raises | `test_an_error_inside_a_step_pauses_the_kit_instead_of_stranding_it[quotes_result]` |
| P2-1 `endpoint_problem` (365f300) | M10 ignore client URL; M11 `is_private` for `is_loopback`; M12 drop check in `authorize_job_item`; M13 drop check in `estimate` | `test_a_local_runtime_pointed_at_another_machine_blocks[…]`, `test_the_job_entry_point_grants_only_the_approved_route_and_step` |
| P2-2 route, stage, item checks | M14 route compare, M15 stage running, M16 item exists, M17 paid refusal | `…grants_only_the_approved_route_and_step`, `…paid_route_is_refused…` |
| P2-3 reply cap (3a2e017) | M05 drop kwarg in `ask_text`, M06 `run_backend` ignores cap, M07 `num_predict`×2, M08 no LM Studio `max_tokens`, M09 no `stop_reason` | `test_one_click…`, `test_local_reply_cap.py` (3 tests) |
| P2-4 contract by reference (af363ef) | planted bypass | killed (see SM6) |
| P2-5 cancel path (274092e) | Q03 no `close()`, Q04 no cancel hook installed, Q05 `cancel()` no-op, Q02 no in-stream check, Q06 cancel always false | killed (Q02, Q06 by a hang caught by my 300 s timeout: the endless-reply test never ends) by `test_ask_text_stops_and_closes_the_stream_when_cancelled`, `test_a_cancelled_worker_ends_quickly_with_an_endless_local_reply` |
| P3-1 CSV `\t` `\r` | drop each of `=` `@` `\t` `\r` in turn | each killed by `test_csv_cells_starting_with_a_formula_trigger_stay_text[…]` |
| P3-3, P3-4, P3-7 | N05 awake line, N03 bound derived from prompt, N01/N02 column allow-list | all killed |

## 3. Mutation results: 58 mutations, 45 killed, 13 survived
Targets include the spec's list for slice 1 (quote parser verbatim/280 filters, window count and size, ledger
transitions, one-running index, SHA resume, recovery). Survivors, by importance:

- **M02 `grant.check()` disabled (survives on all trees).** Static contract checks only that the call is present.
  No test proves a closed grant stops `ask_text`/`render_short_item`. → **F-1 (P2)**.
- **M21, M22 worker-result callbacks unguarded** (`_on_unit_done`/`_on_unit_error` without `_guarded`). The P1-1
  tests use the inline scheduler; the threaded path (the one that runs overnight) has no raising-callback test.
  → **F-2 (P2)**.
- M20 (`_crash` does not close the open grant), M23 (the `_leave("interrupted")` fallback inside `_crash`):
  untested. → F-3 (P3).
- M24 (`stop_now` drops `worker.cancel()`/`wait(2000)`): survives; the new tests cover the stream side, not
  `stop_now`'s own call. M25 (grant close in `stop_now`) is killed. → F-4 (P3).
- Q01 (pre-send cancel check in `ask_text`): survives. → F-4 (P3).
- M43 (`recover(active=…)` exclusion, the Build-time bug "recovery paused a kit started in the same process"):
  survives (it was killed once under load by an unrelated threaded test; rerun clean: survives). → F-5 (P3).
- M44 (link stage re-opened when a file is re-made), M32 (window size 2,500 → 2,400), M18 (job-running check
  in `authorize_job_item`; the stage-running check covers the same case, near-equivalent): untested. → F-5 (P3).
- M45 clamp and M41 paid-intent skip: equivalent in slice 1 (no paid route). Slice 2 must test them.
- Note M37 (`made → running`) was killed once by the quit test; not re-verified on a quiet machine.

Process note: seven mutations first showed "killed" by `test_the_threaded_driver_runs_each_item…` while the
suite ran in parallel; reruns on a quiet machine gave different results (M24, M32, M43, M44 survive). Verdicts
above are the reruns. The harness restores each file from the worktree after every mutation.

## 4. Test quality
- Fakes only: model, `say`/voice, ffmpeg, Pillow output, caffeinate. The e2e proves orchestration and the
  guard, not output quality. The e2e leaves parentless widgets (known TODO P2 GC segfault class).
- Good: one-dialog count; SHA and file-existence resume; the real `usage` tracker; exit-path release
  parametrised; the contract's runtime half; drift tests untouched.
- Gaps: F-1, F-2 above; no test that Stop during the wait for the *first* token behaves (documented as
  uncancellable); no kit-level test with a closed lid or sleep; N5 wording is a draft (owner or lawyer).

## 5. Full suite (final tree 274092e, git worktree, `.venv` from the main checkout)
`2263 passed, 17 skipped, 2 failed` in 34 min. Failures: `test_audiobook_player::test_stopping_does_not_overwrite_the_saved_position`
(known timing flake, TODO P2) and `test_fiverr_orders::test_edit_autosave_timer_flushes_on_its_own`
(a `qWait` timer test, **new flake**, not in TODO: **F-6 P3**). Both pass alone, twice
(`49 passed` ×2, machine load average ~10 during the suite). No GC segfault this run, so no second full run was needed.
Earlier run on 3a75f1a from a copy without `.git`: 4 failed, three explained by the missing `.git`; the fourth
(`test_creator_resume::test_pre_feature_rows_are_never_reconciled`) was not rerun alone and passed in the final run.
A run on 41ddc70 was aborted at ~75 % (stopped, no failures seen) when 274092e arrived.

## 6. Environment checks (this Mac, no paid calls)
- **Keep-awake: verified.** `caffeinate -i -w <pid>` held a `PreventUserIdleSystemSleep` assertion in
  `pmset -g assertions` ("caffeinate asserting on behalf of Process ID …"); when the bound pid exited the
  assertion disappeared and caffeinate exited (the crash backstop works).
- **macOS `say`:** works (`say -v Samantha -o` wrote an AIFF).
- **Real Ollama run: not done.** Ollama answers on 127.0.0.1:11434 but `api/tags` lists **no models**; I did
  not pull one.
- Not verified: App Nap over a long run, contrast, quote quality from a real model, real ffmpeg Shorts through
  the kit, closed-lid behaviour (out of scope per spec).

## Findings
- **F-1 P2** Runtime guard untested: no test that `grant.check()` in `ask_text`/`render_short_item` raises
  `GrantClosed` for a closed grant (M02). Add one per function.
- **F-2 P2** P1-1 fix is untested on the threaded result-callback path (M21, M22). Add a threaded-driver case where
  a result callback raises and the kit pauses `item_failed`.
- **F-3 P3** `_crash` closing the grant (M20) and its `interrupted` fallback (M23) untested.
- **F-4 P3** `stop_now`'s cancel/wait (M24) and the pre-send cancel check (Q01) untested.
- **F-5 P3** `recover(active=…)` (M43), link re-open after a re-made file (M44), Short window size (M32) untested.
- **F-6 P3** `test_fiverr_orders::test_edit_autosave_timer_flushes_on_its_own` flakes under load; add to TODO P2 flakes.
- Carried: P3-8 (`record_job_item` clamp) needs real tests in slice 2; N5 wording awaits the owner or a lawyer.
