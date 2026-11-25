# Verify: worker-crash-class (QA)

Role: `qa-engineer` agent, independent of the author; read-only on the real branch. Date: 2026-11-25.
Commit verified: `973d03d` (scratch worktree, detached). Playbook `docs/playbooks/qa-engineer.md`:
`status: current`, `last-reviewed: 2026-10-14` (42 days; not stale).

## Verdict: PASS WITH GAPS

No P0 or P1. The success measure is demonstrated for every defect, with one condition: the
**full suite** was not run by QA (a full run is in progress in the real checkout); the "full suite
green" line of the success measure stands or falls on that run. 22 of 27 mutants killed, including
all 13 the orchestrator listed; the 5 survivors are QA's own extra mutants and are listed as gaps
(G1 P2, G3-G5 P3; one is near-equivalent).

## 1. Success measure

| Measure | Evidence | Met |
|---|---|---|
| Tests fail on `main`, pass on the branch | New test file run against `839836c` (git archive, with only `ui/worker_registry.py` grafted in so it imports): **40 failed, 6 passed**. The 6 that pass are the 5 registry unit tests (the module is new on this branch) and `quill write after stop` (already guarded on main, as the spec says). The 20 busy-site cases fail on main with `_Reached` (the start went on into pricing), i.e. for the right reason. On `973d03d`: 46 passed. | yes |
| 1. Busy slot refused at every listed site, no replacement; Press Shorts refuse each other | `test_a_start_into_a_busy_slot_is_refused_before_pricing` (19 cases), `test_kernel_send_...`, `test_press_shorts_entry_points_share_one_busy_rule` (3). Each case has a control run that proves the start reaches pricing when idle, so the refusal assertion can fail. | yes, except Suno (gap G1) |
| 2. Post Now returns before `publish()`; consent bounded; consent timeout safe to retry | `test_post_now_publishes_off_the_ui_thread_...` (publish on a non-main thread, handler returns < 2.5 s while publish blocks, result slot on the GUI thread, button re-enabled), `test_youtube_consent_wait_is_bounded_...`, `test_youtube_publisher_marks_only_a_consent_failure_safe` | yes |
| 3. Quit cancels and waits for an unnamed worker; a survivor never reaches Qt's destructor | `test_close_cancels_and_waits_for_workers_it_was_never_told_about` (music, webdesign, no slot), `test_stop_all_uses_one_budget_...`, `test_the_process_leaves_...` (injected `exit_fn`), source test that `main()` calls the guard after `app.exec()`. QA added a process-level check (below). | yes |
| Source test: no direct `QThread` subclass | `test_no_app_class_subclasses_qthread_directly` (fails on main listing 12 classes) | yes |
| Full suite green; ruff <= 150 | ruff (uvx ruff 0.17.6, CI's command): **150** = baseline 150. Full suite: **not verified by QA**. | partly |

**Process-level evidence (QA, not in the suite).** A 15-line script (scratchpad `qa/proc_exit.py`)
starts a `TrackedThread` that ignores `cancel()`, runs `stop_all(300)`, drops the reference and exits:

```
guard   rc=0    still after stop_all: ['Stubborn'] / Leaving with workers still running: Stubborn
noguard rc=134  still after stop_all: ['Stubborn'] / QThread: Destroyed while thread '' is still running
```

So the abort the spec says the tests "do not prove" is reproducible in a subprocess in about a
second, and `leave_if_workers_alive` demonstrably prevents it. Mutant M2 also reproduces it inside
pytest (exit 134).

**What the tests do not prove** (beyond the spec's own list): the real `main()` quit path end to end
(closeEvent, then `app.exec()` returning, then the guard) in a process; that queued result signals
are delivered during shutdown; Suno's and the chained starts' (Herald clip render, Nova render after
estimate, Reel estimate/render/resume, Vector image after prompt) refusal paths; that the happy-path
`start_in_slot` store-and-start lines at most sites run (they are exercised only by other suites, if
at all: 75% of changed statements and 83% of changed branches are hit by these two test files).

## 2. Mutation check

Each mutant applied alone in the scratch tree, `tests/test_worker_crash_class.py` +
`tests/test_routing_phase3.py` run (`-p no:randomly --timeout=120`), then `git checkout -- <file>`.
Script: scratchpad `qa/mutate.py`.

| # | Mutant | File | Result | Killed by |
|---|---|---|---|---|
| M1 | `slot_busy` always False | ui/worker_registry.py:69 | KILLED | 29 tests (slot rule, every site) |
| M2 | `TrackedThread.start` does not register | ui/worker_registry.py:52 | KILLED (process abort, rc 134, "QThread: Destroyed while thread is still running") | `test_a_running_tracked_thread_is_held_by_the_registry` |
| M3 | `_prune` keeps `not w.isRunning()` (drops running workers) | ui/worker_registry.py:43 | KILLED (6 failures, then rc 134) | registry-held, close sweep x3, stop_all, leave |
| M3b | `_prune` drops everything | ui/worker_registry.py:43 | KILLED | 6 tests |
| M4 | `stop_all` skips `cancel()` | ui/worker_registry.py:108 | KILLED | close sweep x3, stop_all |
| M5 | `stop_all` waits full budget per worker | ui/worker_registry.py:115 | KILLED | `test_stop_all_uses_one_budget_for_every_worker` |
| M6 | `leave_if_workers_alive` skips `exit_fn` | ui/worker_registry.py:140 | KILLED | `test_the_process_leaves_...` |
| M7 | Label: `refuse_if_busy` moved after `authorize_request` | agents/music/panel.py:210 | KILLED | `...refused_before_pricing[label after stop]` |
| M8 | `delete_post` without `_publishing()` fence | agents/social/panel.py:1081 | KILLED | `test_a_post_in_flight_...[delete_post]` |
| M9 | `run_local_server(port=0)` without `timeout_seconds` | vidforge/vidforge/youtube.py:83 | KILLED | `test_youtube_consent_wait_is_bounded_...` |
| M10 | publisher never sets `safe_to_retry` for consent | agents/social/publishing.py:303 | KILLED | `test_youtube_publisher_marks_only_a_consent_failure_safe` |
| M11 | `render_short` checks `should_stop` after `synthesize` | agents/manuscript/shorts_generator.py:61 | KILLED | `test_shorts_worker_cancel_skips_the_render` |
| M12 | `ModelPullWorker._progress` does not raise after cancel | ui/workers.py:254 | KILLED | `test_model_pull_worker_cancel_ends_the_download` |
| M13 | `PublishWorker` run synchronously in `post_selected` (`worker.start = worker.run`) | agents/social/panel.py:1196 | KILLED | `test_post_now_publishes_off_the_ui_thread_...` |
| X1 | `slot_busy` checks only the first slot | ui/worker_registry.py:67 | KILLED | 4 tests |
| X2 | `closeEvent` does not call `stop_all` | main.py:6815 | KILLED | close sweep x3, `test_routing_phase3::test_closing_the_window_cancels_a_running_measurement` |
| X3 | `_on_publish_failed` treats every failure as safe | agents/social/panel.py:1215 | KILLED | 2 tests |
| X4 | `ShortsWorker.cancel` does not set the flag | agents/manuscript/workers.py:37 | KILLED | `test_shorts_worker_cancel_skips_the_render` |
| X5 | Quill publish: busy check after disabling Generate | agents/author/panel.py:1765 | KILLED | `...[quill publish after stop]` |
| X7 | `main()` no longer calls `leave_if_workers_alive` | main.py:7023 | KILLED | `test_main_leaves_through_the_guard_...` (source test) |
| X8 | Press Shorts busy rule never refuses | agents/manuscript/panel.py:1084 | KILLED | 3 Shorts tests |
| X9 | `refuse_if_busy` does not set the busy label | ui/worker_registry.py:81 | KILLED | 22 tests |
| X6 | Nova estimate handler keeps its slot | agents/creator/panel.py:1293 | **SURVIVED** | near-equivalent: only matters in the moment the estimate thread is returning from `run()` (G5) |
| X10 | Suno draft: `refuse_if_busy` removed | agents/music/suno_panel.py:193 | **SURVIVED** (also against test_music_panel, test_partial_billing, test_output_cap: 127 passed) | G1 |
| X11 | Herald clip render: `slot_busy` check removed | agents/social/panel.py:669 | **SURVIVED** (also against test_herald_clip_provider, test_partial_billing, test_content_policy: 138 passed) | G3 |
| X12 | Muse pull "cancelled at quit" branch removed (review P3-2 fix) | main.py:1157 | **SURVIVED** (also against test_chat_streaming) | G4 |
| X13 | `stop_all`: a raising `cancel()` aborts the sweep | ui/worker_registry.py:107-110 | **SURVIVED** | G4 |

Planted 27 (14 M, 13 X), killed 22 (M2 and M3 by a process abort), survived 5 (X10-X13, and X6
near-equivalent). All 13 mutants the orchestrator asked for were killed.
Tree restored after each (`git checkout -- <file>`).

## 3. Seeds

`tests/test_worker_crash_class.py`, `-p randomly`:

| Seed | Result |
|---|---|
| 1 | 46 passed, 7.23 s |
| 42 | 46 passed, 7.37 s |
| 20261125 | 46 passed, 6.97 s |
| 7 (with `test_routing_phase3.py`) | 70 passed, 11.82 s |

Baseline unseeded run of both files: 70 passed. No order-dependent failure seen.

## 4. Branch coverage of changed lines

coverage.py 7.17.5 (`--branch`, loaded from the uv cache via `PYTHONPATH`; the venv has no
coverage and was not modified), these two test files only, changed lines of `839836c..973d03d`
(non-test `.py`): **statements 218/290 (75%), branches 80/96 (83%)**. `ui/worker_registry.py`:
59/67 changed statements; missed: `stop_all`'s `except` for a raising `cancel()` (109-110),
`_flush_for_exit` (120-125), branches "worker already registered" (51), `label is None` (79),
"worker finished before the wait" (113). `agents/social/workers.py` 42-44 (`PublishWorker` failure
emit) never runs. Note: coverage does not trace code inside a `QThread.run`, so worker bodies run
on a QThread are under-reported. Uncovered elsewhere: every site's happy-path `start_in_slot`, Suno
193/221, Herald clip render 669-674/710, `publishing.youtube_consent_minutes` 368-372, main 1157-1161,
6817.

## 5. Models

No test in the file calls a model or the network: fakes for publisher, OAuth flow, voice, Ollama
client; `authorize_request` is replaced by a raiser. The spec changes no prompt or model route, so a
live eval is not needed for this change. No `--purpose eval` record exists in
`docs/foundry/model_use.jsonl` and `plan.toml` has no `eval_budget_usd`: Release must check the
app-wide requirement separately (not verified here).

## Gaps (ranked)

- **G1 (P2) Suno draft's refusal is untested.** X10 survives every related file. Without the check,
  `start_in_slot` raises `WorkerSlotBusy` *after* `authorize_request` (money reserved, panel left
  disabled by `self.setEnabled(False)`). Suno and Label share `music_worker`, so this is the one
  cross-panel case. Add Suno `draft` to `SITES` (busy `music_worker`).
- **G2 (P2) No committed test that every `start_in_slot` is preceded by `refuse_if_busy`/`slot_busy`
  on the same slot before `authorize_request`.** The reviewer did this as a one-off AST scan; the suite
  only has per-site cases for 19 of 29 call sites. A new site that forgets the check passes the AST
  "no host assignment" test and fails only at runtime, after pricing. An AST test over `agents/` and
  `main.py` would close G1 and G3 at once.
- **G3 (P3) Chained starts' busy checks are untested** (X11: Herald clip render; also Nova render after
  estimate, Reel estimate to render, Vector image after prompt). Defensive, low reachability.
- **G4 (P3) Small untested branches:** X12 (Muse pull stopped at quit shows no "Download Failed"
  dialog; review P3-2 fix has no test), X13 (`stop_all` survives a `cancel()` that raises),
  `PublishWorker`'s failure emit across threads (slot tested only by direct call),
  `youtube_consent_minutes()` status text.
- **G5 (P3) X6 near-equivalent survivor:** the estimate handlers' slot release (build note) has no
  test; its effect is a spurious busy notice in a short window.
- **G6 (P3) Test quality.** Two wall-clock assertions (`elapsed < 0.8` for a 0.3 s budget,
  `returned_after < 2.5`) can flake on a loaded CI runner; `test_the_process_leaves_...` skips its
  empty-registry check when an earlier test leaked a running worker (order-dependent, silent);
  `test_chat_send_...` and `test_main_leaves_...` are source-string checks (they killed X7 but break on
  a harmless rename); the host-slot AST test scans `agents/` only, not `main.py`.
- **G7 (P3) Process-level abort test missing from the suite.** QA's `proc_exit.py` shows it costs about
  a second in a subprocess (rc 0 with the guard, 134 without); worth adding as the direct proof of
  defect 3.
- **G8 (P3, pre-existing, not this spec)** The playbook's `-W error::pytest.PytestDeprecationWarning`
  mode fails at collection: anyio's pytest plugin imports `CallSpec2` (PytestRemovedIn10Warning).

## Commands run (scratch worktree `973d03d`)

- `pytest -q tests/test_worker_crash_class.py tests/test_routing_phase3.py` -> 70 passed, 17.4 s
- `python qa/mutate.py` (27 mutants, one at a time, restored each time) -> table above
- M2/M3 alone -> rc 134, "Fatal Python error: Aborted" / "QThread: Destroyed while thread '' is still running"
- `pytest -q -p randomly --randomly-seed={1,42,20261125} tests/test_worker_crash_class.py` -> 46 passed each
- Against `839836c` + grafted registry -> 40 failed, 6 passed
- `uvx ruff check --no-cache --quiet --output-format=concise --exit-zero .` -> 150 (baseline 150)
- `coverage run --branch ...` + changed-line script -> 75% statements, 83% branches
- `python qa/proc_exit.py <tree> guard|noguard` -> rc 0 / rc 134

## Not verified

Full suite (in progress elsewhere); CI on GitHub; the packaged app; a real Google consent; a live
eval.

`git -C <scratch> status --short` after all mutations: empty (clean).

## Author's disposition (2026-11-25, tests only; no production code changed)
- G1: Suno draft added to `SITES` (busy `music_worker`). X10 now killed.
- G2: `test_every_priced_start_checks_its_slot_before_pricing` (AST): every function that prices
  and then calls `start_in_slot` checks or clears that slot before the first `authorize_request`;
  five chained helpers are listed with their reason, and a second test pins that the two
  helper-only paths keep their single checked caller.
- G3: `test_herald_clip_render_refuses_while_a_clip_renders`. X11 now killed.
- G4: `test_a_raising_cancel_does_not_stop_the_quit_sweep` (X13 killed) and
  `test_a_model_download_stopped_by_quit_shows_no_failure_dialog` (X12 killed).
- G5 (near-equivalent), G6 (wall-clock margins), G7 (process-level abort test), G8 (pre-existing
  warning filter): left as P3, not done here.
