# QA report: local-model-routing (Verify, 2026-11-24)

Role: qa-engineer. Code under test: `d6b72b6` (`claude/happy-dubinsky-48c27c`; HEAD has since moved to `e3cb7da`, audit
files only, no code change). Imprint venv (Python 3.11), `QT_QPA_PLATFORM=offscreen` from `tests/conftest.py`. No network,
no model server, app not started. Full suite not re-run (2877 passed on `2d427e2` earlier today, per the brief).
Playbook `docs/playbooks/qa-engineer.md`: `status: current`, `last-reviewed: 2026-10-14` (41 days, not stale).

**Where the tests ran.** Another agent was mutating `main.py` in this same worktree at the same time, through the same scratchpad
(`mutate.sh`; a one-line mutant at `main.py:3619` was visible at about 11:00 GMT). My first in-place mutant pass ran from
10:55 to 10:59 GMT on top of that agent's mutant (my backup's SHA-1 was `a5bd005…`, HEAD's is `476ad71…`), so I **threw those
results away**. Everything below ran in two exports of `d6b72b6` (`git archive d6b72b6 | tar -x`) under the scratchpad
(`lmr-qa-9839/tree`, `tree2`). Each export passed the same tests as the worktree, and it imports its own code
(`services.local_ratings.__file__` points into the export). One side effect: during that window my restores may have put the
other agent's mutant back into `main.py` after it had restored the file itself, so its results from 10:55 to 10:59 are
suspect. At 10:59 `git hash-object main.py` equalled the index (`789f727`). Now `git status` shows no code changes.

## Verdict: PASS with gaps
All the routing tests pass in fixed order and under three random seeds, with no order dependence. 21 of 29 success measures
are met by a test that exercises the behaviour, and 18 of 21 mutants were killed. Not ready for Release: measure 25 (the
Sentinel copies match) fails against Sentinel `main`, three mutants survive in the money and privacy paths, four measures have
no test, and no live eval has been run or recorded.

## 1. Runs
| Run | Command (from the export or the worktree) | Result |
|---|---|---|
| Baseline, 12 files, fixed order (worktree) | `pytest -q -p no:randomly tests/test_local_ratings.py … tests/test_settings_pricing.py tests/test_providers_drift.py` | 378 passed, 11 skipped (drift: "sentinel is not checked out beside this repository"), 249 s |
| Drift vs Sentinel `main` (`1ee934e`) | `SIBLING_REPO_DIR=/Users/as/Documents/lab/active/sentinel pytest -q -p no:randomly tests/test_providers_drift.py` | **2 failed**, 9 passed: `services/local_ratings.py`, `tests/test_local_ratings.py` |
| Drift vs Sentinel `claude/ratings-judge-l2` worktree | `SIBLING_REPO_DIR=…/sentinel/.claude/worktrees/ratings-judge-l2 pytest -q -p no:randomly tests/test_providers_drift.py` | 11 passed |
| Export baseline, 4 files | `pytest -q -p no:randomly -p no:cacheprovider tests/test_local_only_guard.py tests/test_routing_phase3.py tests/test_local_ratings.py tests/test_routing_phase4.py` | 130 passed, 90 s |

## 2. Success measures
| # | Measure (short) | Status | Note |
|---|---|---|---|
| 1 | LM Studio local everywhere; no `== "ollama"` | met | `test_routing_phase1.py:38`, `:116` (real `Validator`), `:185` (source scan with a 6-line allow-list); `test_local_only_guard.py:117` shows no dialog for a local model |
| 2 | Zero cloud price is unknown | met | three tests, engine, candidate and catalogue levels |
| 3 | No key; client talks only to its address | weak | `test_providers_registry.py:378` checks only the `base_url` and `root` strings, so a call to a hard-coded host would pass. `:256` and the chat test do intercept the URL for those two calls |
| 4 | `OLLAMA_HOST`, `LMSTUDIO_URL`; pinned address kept | met | parametrised table, including `0.0.0.0` |
| 5 | Discovery on/off, MLX, no projectors | met | quality: `:276` leaves `running_port` unstubbed, so it runs the real `lms server status` on this Mac (`~/.lmstudio/bin/lms` exists). The result does not depend on it, but it is a host subprocess with a timeout of up to 5 s |
| 6 | Fit check × 1.2 | met | boundary tested exactly |
| 7 | Uncensored tag | met | `test_routing_phase1.py:222` reads `~/.lmstudio/models` (skips on CI) and its oracle is a word list close to the code's own; the parametrised tables carry the measure |
| 8 | Picker and advisor read caches | met | `test_routing_phase4.py:337` is a name-based AST scan; it would miss a fetch by a new name |
| 9 | Local model is a BEST FIT candidate | met | spies on the engine's candidates |
| 10 | Unrated never wins; rated in band wins on price | met | |
| 11 | Inherited = base − 0/10/25; modified builds inherit nothing | met | |
| 12 | Measured never above reference | met | |
| 13 | No usable verdict rates nothing; 75%; empty reference | met | R1 to R5 all killed |
| 14 | Measured once, automatically; refusal leaves Measure | met | |
| 15 | Caps, usage billing, ceiling held, late finish | weak | M1, M2, M2b, M3, M4 killed; **M1b and M3b survive** (§3) |
| 16 | Local only holds everywhere | met | M5, M6, M7, M10, M12 killed |
| 17 | Remote runtime refused, asked once, not measured silently | weak | M9 killed; **M8 survives**; the interactive Measure of a remote runtime and the "not a plain address" branch are never run (§4) |
| 18 | Advisor names limits; 20-point band; unmeasured not urged | met | |
| 19 | Paid model only through the dialog; No sends nothing | met | real button clicks, `FakeChatWorker` |
| 20 | Always rule per agent and kind, listed, removable, under Local only | met | |
| 21 | Failover offers, never sends; Stop offers nothing; no cloud under Local only | met | |
| 22 | Default mode; saved mode kept; recommendation never Local only | met | M11 killed, but `test_routing_phase3.py:448` sets up no local winner, so it depends on what the module's window ranks first; `test_routing_phase4.py:257` sets `_applying_recommendation` by hand rather than calling the apply path |
| 23 | Only Quill, Herald, Sitebuilder, Vector advised | met | Nova = `creator`, Press = `manuscript` (`agents/catalog.py:35`, `:77`); test name says "muse" |
| 24 | OpenAI narration route retires 2027-01-06 | met | dates are passed in, no clock dependence |
| 25 | Shared files equal Sentinel's | **unmet** | skips in every worktree (11 skipped). Against Sentinel `main` it fails 2; it passes only against the unmerged Sentinel branch `claude/ratings-judge-l2` |
| 26 | Selection unchanged after Switch | no test (panels) | the Kernel path *is* tested (`test_routing_phase4.py:186`, `_selection_unchanged`); the panels are not, and review L-4 says they keep the switched model |
| 27 | Tag wherever a model is named | no test | |
| 28 | "Saved" = cloud cost | no test | `test_routing_phase4.py:278` only checks that the tally equals the stubbed estimate 0.19 |
| 29 | Works against live LM Studio | no test | manual, TODO.md:149 |

Totals: **21 met, 3 weak, 1 unmet, 4 no test.**

## 3. Mutation check (isolated export; each file restored and byte-compared after every mutant)
Tests run: `main.py` mutants against `tests/test_local_only_guard.py tests/test_routing_phase3.py` (39 tests; M11 adds
`tests/test_routing_phase4.py`); `local_ratings.py` mutants against `tests/test_local_ratings.py`. `-p no:randomly`, no `-x`.

| ID | Change | File:line | Caught | Killed by |
|---|---|---|---|---|
| R1 | verdict = last word of the reply (a sentence counts) | `services/local_ratings.py:610` | yes | `test_a_judge_that_gives_no_usable_verdict_rates_nothing[judge3]`, `test_parse_verdict` ×2 |
| R2a | `math.ceil` → `int` in the 75% rule | `services/local_ratings.py:740` | yes | `test_a_kind_with_too_few_usable_verdicts_stays_unrated_and_says_why` |
| R2b | `<` → `<=` in the 75% rule | `services/local_ratings.py:740` | yes | `test_measure_scores_every_kind_and_records_its_evidence` and 2 more |
| R3 | one-sided judge (same slot in both orders) counted | `services/local_ratings.py:722` | yes | `…rates_nothing[judge0]` |
| R4 | empty reference answer judged anyway | `services/local_ratings.py:713` | yes | `test_an_empty_reference_answer_is_neither_judged_nor_cached` |
| R5 | `MIN_USABLE_SHARE` 0.75 → 0.5 | `services/local_ratings.py:599` | yes | `…stays_unrated_and_says_why` |
| M1 | ceiling counts one judge call per pair, not two | `main.py:1252` | yes | `test_the_ceiling_is_priced_on_the_caps_and_held_for_the_run` |
| **M1b** | ceiling drops the judge's thinking reserve | `main.py:1253` | **no** | none |
| M2 | bill ignores the provider's usage (`usage=None`) | `main.py:1395` | yes | `test_measurement_calls_carry_an_output_cap_and_keep_their_usage` |
| M2b | `by_usage` ignores the provider's usage | `main.py:1228` | yes | same |
| M3 | ceiling not reserved at start | `main.py:1339` | yes | ceiling test, late-finish test |
| **M3b** | measurement's guard ignores other requests in flight (`reserved = 0.0`) | `main.py:1281` | **no** | none |
| M4 | any finish clears the reserve (RC-12 undone) | `main.py:1408` | yes | `test_a_late_finish_does_not_release_the_next_runs_reserve` |
| M5 | Mode box's Local only no longer beats an agent's own mode | `main.py:4014` | yes | `test_the_box_beats_an_agents_own_mode` |
| M6 | route check skipped for per-unit (`flat_cost_eur`) requests | `main.py:4688` | yes | `test_local_only_refuses_per_unit_requests_too` |
| M7 | Kernel's route check removed | `main.py:4417` | yes | both Kernel tests |
| **M8** | an address said yes to once is let through before the Local only check | `main.py:4062` | **no** | none |
| M9 | automatic measure of a remote runtime no longer refused | `main.py:1265` | yes | `test_a_model_on_another_machine_is_not_measured_without_asking` |
| M10 | measuring allowed under Local only | `main.py:1259` | yes | `test_measuring_asks_no_cloud_model_under_local_only` |
| M11 | recommendation says Local only for a local winner (RC-4 undone) | `main.py:885` | yes | `test_a_recommendation_never_sets_local_only` |
| M12 | moving Mode to Local only no longer stops a running measurement | `main.py:4127` | yes | `test_switching_to_local_only_stops_a_running_measurement` |

**18 of 21 killed.** What the survivors mean:
- **M1b (money).** The judge is "the cheapest priced cloud model", and DeepSeek and Qwen carry a 65,536-token thinking reserve
  (`services/output_limits.py:45-48`). The test's plan uses Anthropic and Gemini, whose reserve is 0, so the ceiling could
  under-price a DeepSeek judge by about 64k output tokens per call and no test would notice.
- **M3b (money).** A measurement started while other paid requests are in flight is checked against the caps as if nothing
  else were reserved. No test has a pending request when a measurement starts.
- **M8 (privacy).** Every remote-runtime test starts with an empty `_remote_runtime_ok`. Nothing tests "said yes under Hybrid,
  then switched to Local only"; with the order regressed, the next request goes to the other machine.

## 4. Changed-line coverage (fix commits `ba870c4`, `e57644a`, `2d427e2`; lines from `git blame d6b72b6`)
Measured with a `sys.settrace` arc recorder (coverage.py is not in the venv; CI installs it on the fly) over
`test_local_only_guard`, `test_routing_phase3`, `test_local_ratings`, `test_routing_phase4`, `test_routing_panels` (145 passed).
- `services/local_ratings.py`: statements 32/32, branch arms 20/20.
- `main.py`: statements 99/104, branch arms 41/48. Not run: `:1243-1244` (a kind with no reference), `:1247` false arm (a
  cached reference answer left out of the ceiling), `:1265` false and `:1268-1269` (the **interactive** Measure of a
  remote runtime, both answers), `:1367-1368` (a cloud client without `chat`), `:4032-4033` (an address that is **not a plain
  address**, for example with user info or a backslash, treated as remote).

## 5. Random order
From `lmr-qa-9839/tree2` (an export of `d6b72b6`), with `PYTHONDONTWRITEBYTECODE=1`:

    pytest -q -p no:cacheprovider -p randomly --randomly-seed=N tests/test_local_ratings.py tests/test_local_only_guard.py tests/test_routing_phase1.py tests/test_routing_phase2.py tests/test_routing_phase3.py tests/test_routing_phase4.py tests/test_routing_panels.py tests/test_routing_advisor.py tests/test_narration_route_retirement.py

| Seed | Summary line |
|---|---|
| 11 | `284 passed, 1 warning in 242.96s (0:04:02)` |
| 12 | `284 passed, 1 warning in 236.82s (0:03:56)` |
| 13 | `284 passed, 1 warning in 228.95s (0:03:48)` |

No order-dependent failure. RC-2 (the ceiling test depending on order) did not come back in any of the three orders. The one
warning is pytest's `CallSpec2` deprecation from the anyio plugin.

## 6. Models: fakes and live eval
- Unit tests call no live model. Cloud clients are fakes (`_CappedClient`, `FakeChatWorker`, `Asker`); LM Studio and Ollama are
  fakes or recorded API shapes; `tests/conftest.py:169-187` refuses ratings fetches, and `:191-213` seeds the local inventory with
  no socket. Two tests read this Mac (measure 5 runs `lms`; measure 7 reads `~/.lmstudio/models`), and neither uses the network.
- Live eval: **not run and not recorded.** `docs/foundry/model_use.jsonl` does not exist, and `docs/foundry/plan.toml` has no
  `eval_budget_usd`. The judge calls a real cloud model in production, so before Release a small live eval (one model, one kind,
  cheapest adequate judge) belongs with `model_use.py . --purpose eval`. Measure 29 and TODO.md:149 are the manual part.

## 7. Gaps, ranked (tests to add; none added)
1. **Measure 25, release blocker.** Sentinel `main` differs from this branch in `services/local_ratings.py` and
   `tests/test_local_ratings.py`; the port is on the unmerged Sentinel `claude/ratings-judge-l2`. The drift test also skips in every
   worktree (TODO.md:73), so this never shows. Merge the Sentinel side (recheck RC-1 says it turns a Sentinel test red), then make
   the drift test fail instead of skipping.
2. **M1b.** A ceiling test with a DeepSeek or Qwen judge and reference, expecting the thinking reserve in the figure.
3. **M8.** Say yes to a remote address under Hybrid, switch to Local only, expect the next request refused (`authorize_request`
   and Kernel).
4. **M3b.** A pending request of €X when a measurement starts: the guard must see X plus the ceiling (refuse when the two
   together pass the cap).
5. **Interactive Measure of a remote runtime** (`main.py:1265-1269`): No gives "cancelled" and starts nothing; Yes starts the
   run and remembers the address.
6. **Non-plain address** (`main.py:4032-4033`): `LMSTUDIO_URL=http://evil.example\@127.0.0.1:1234/v1` is refused under Local
   only and asked about otherwise.
7. **Measure 26 for the panels:** after Switch for this job, `_boxes(panel)` still shows the local model (expected to fail today,
   L-4).
8. **Measure 3:** intercept `requests` for every `LMStudioClient` method with a custom address and assert that no other host is
   dialled.
9. **Measure 28:** the tally with real `config/pricing.json` prices for the suggested cloud model.
10. **Measure 27:** every place that names a model (status line, banner, failover text, rules table) shows the tag for an
    abliterated model.
11. Hygiene: stub `running_port` in `test_server_off_falls_back_to_the_disk_listing`. Give
    `test_a_recommendation_never_sets_local_only` an explicit local winner. `test_closing_the_window_cancels_a_running_measurement`
    is a source-text check (TODO.md:151).

## Not verified
- The full suite (not re-run, per the brief). CI on GitHub.
- Anything against a live provider, LM Studio or Ollama: real usage numbers, a thinking judge (RC-13), MLX end to end.
- Sentinel's own suite on `claude/ratings-judge-l2` (RC-1).
- Branch coverage by coverage.py: the figures above come from a settrace recorder whose branch rule (an arc from the condition
  into or out of the body) is an approximation.
- The results of the other agent that shared this worktree between 10:55 and 10:59 GMT (see the top of this report).
