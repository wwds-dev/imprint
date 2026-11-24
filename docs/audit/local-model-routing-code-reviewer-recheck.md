# Code review recheck: local-model-routing (L-1, L-2, L-3, security P1-1), 2026-11-24

Role: code-reviewer (read-only), a different session from the author of `ba870c4` and `e57644a`. Playbook `docs/playbooks/code-reviewer.md`: `status: current`, `last-reviewed: 2026-10-14` (41 days, not stale).

Scope: does each fix close its finding as `docs/audit/local-model-routing-code-reviewer.md` (L-1, L-2, L-3) and `docs/audit/local-model-routing-security-engineer.md` (P1-1) describe it, and did the fixes break anything. Not a new review of the feature. Reviewed on branch `claude/happy-dubinsky-48c27c` at `0cc1ad2`. The merge after the fixes changes one line of `main.py` (`:4098`, `DEFAULT_MODE` to `HYBRID_MODE`) and no file of the two fix commits otherwise (`git diff e57644a HEAD -- main.py services/local_ratings.py tests/...`).

## Verdict

**Fix first.** The four fixes do what their findings ask on the main paths: a judge that answers empty, refuses or picks one slot no longer rates a local model; every request through `authorize_request` and Kernel's `_send_chat` is refused under Local only, whatever the agent and whether or not the advisor answers; measurement calls carry an output cap and are billed from the provider's usage, with the ceiling held against the caps; and a runtime on another machine is refused under Local only and asked about otherwise. Two things should be fixed before this lands: Sentinel's copy of the ratings change turns one of Sentinel's own tests red (RC-1), and one of the new Imprint tests fails depending on test order (RC-2). Five P2 gaps remain, among them a race that can still count a measurement call from its visible text (RC-3), and "Apply recommended setup" now putting every agent under Local only (RC-4).

**Counts:** P0: 0 · P1: 2 · P2: 5 · P3: 6

## Earlier finding -> status

| ID | Was | Status | Where it is fixed | Test | Still open |
|---|---|---|---|---|---|
| L-1 | P1, measurement uncapped, billed on chars/4, ceiling not reserved | fixed, with gaps | caps `main.py:135-137`, `:1357-1361`; local answer cut `:1350-1353`; ceiling on caps plus thinking reserve `:1231-1252`; reserved `:1328`, `:5572-5575`, shrinks per bill `:1385-1387`, cleared `:1395`; usage billed `:1380-1384` and counted `:1222-1228`; no run under Local only `:1256-1258` | `tests/test_routing_phase3.py:353`, `:378`, `:384` | RC-3 (usage race), RC-5 (a run in progress ignores a later Local only), RC-2 (test is order-dependent). Automatic start without a click is unchanged; the finding allowed that once the rest is fixed (owner decision of 2026-10-19). DeepSeek and Qwen, whose caps may not bound thinking, are priced with `thinking_reserve_tokens` (`:1248`, `:1251`) and counted from usage, so that path is covered |
| L-2 | P1, an empty, refusing or one-sided judge read as ties | fixed in code | `services/local_ratings.py:602-612` (whole reply must be the verdict), `:708-712` (empty reference neither judged nor cached, an old empty one asked again), `:719-726` (unreadable or same slot in both orders is unusable), `:740-744` (75% usable per kind), `:756-760` (no kind rated: run fails) | `tests/test_local_ratings.py:253`, `:262`, `:269`, `:281`, `:329` | RC-1 (Sentinel test red), RC-11 (an older score survives a failed re-measure) |
| L-3 | P1, Local only did not hold for most agents; advisor failed open; override beat the box | fixed for both send gates | `main.py:4027-4044` called first in `authorize_request` (`:4664`) and after any route override in `_send_chat` (`:4393`); box beats override in `execution_mode_for` (`:190-191`) and `routing_mode` (`:4000-4001`) | `tests/test_local_only_guard.py:73`, `:82`, `:89`, `:98`, `:110` | RC-4, RC-5, RC-7 (Kernel path untested), RC-8, RC-9. A held job or failover offer is not cleared when the mode changes; pressing Switch is now refused at `:4393`, so nothing is sent, but the banner still offers it |
| Security P1-1 | P1, a runtime on another machine was "on this Mac" | fixed at both send gates | `main.py:4009-4025` (address from the client, as the release kit does), `:4045-4070` (refused under Local only; else asked once per provider and address, default No, names the host and plain http) | `tests/test_local_only_guard.py:117`, `:125`, `:139` | RC-6: the measurement's local calls go through `run_backend` with no question, and the picker, settings and status texts still say "On this Mac" |

## Findings

### RC-1 · P1 · Sentinel's copy of the ratings fix breaks a Sentinel test
- **Where:** Sentinel worktree `ratings-judge-l2`, `tests/test_routing_phase3.py:294` and `:307` (not a shared file); the shared change is `services/local_ratings.py:719-726`, `:756-760`.
- **Evidence:** `cmp` of `services/local_ratings.py` and `tests/test_local_ratings.py` against Sentinel's branch: exit 0 for both, byte-identical. Sentinel's worker test stubs a judge that always answers "A" and expects `STATUS_MEASURED`; under the fix that judge is one-sided, so the run fails. Run in the Sentinel worktree: `pytest -q -p no:randomly tests/test_routing_phase3.py -k measure_worker_runs_the_engine` -> `1 failed` at `:307` (status `failed`). Imprint's twin test was updated in `ba870c4` (`tests/test_routing_phase3.py:316`, verdicts `("B", "A")`); Sentinel's was not.
- **Scenario:** Sentinel's branch is merged as it is -> its suite is red on every run.
- **Fix:** in Sentinel, give that stub alternating verdicts as Imprint's does. Nothing in the shared files assumes Imprint: no paths, no app names; the comments cite "review L-2", which is Imprint's report, and are harmless.

### RC-2 · P1 · `test_the_ceiling_is_priced_on_the_caps_and_held_for_the_run` fails depending on order
- **Where:** `tests/test_routing_phase3.py:384-399`; fixture `:201-216`; `main.py:1328`.
- **Evidence:** the five files `test_local_ratings`, `test_local_only_guard`, `test_routing_phase3`, `test_routing_phase4`, `test_routing_panels`: `1 failed, 138 passed`. The test alone: passed. `test_routing_phase3.py` with `--randomly-seed=1`: failed, `assert 2.12 == 4.24` at `:397`; seeds 2 and 3: passed. In seed 1, `test_starting_a_measurement_does_no_model_work_on_the_gui_thread` (`:305`) runs earlier, starts a measurement on the shared window with a `FakeWorker` that never finishes, and leaves `_measure_reserved_eur` at 2.12. The fixture does not reset it, so `before` is 2.12; `start_local_measure` then assigns (not adds) the ceiling, and the reserve stays 2.12.
- **Scenario:** CI or a full run shuffles these two tests in that order -> the suite is red. The project rule is that an order-dependent failure is a bug.
- **Fix:** reset `_measure_reserved_eur` to 0.0 and `_measure_usage` to `{}` in the `app` fixture (monkeypatch), and assert the reserve after the start equals the worker's budget plus what `_pending_requests` holds.

### RC-3 · P2 · A measurement call can still be counted from its visible text: the GUI pops the usage the worker is about to read
- **Where:** `services/local_ratings.py:675-679` (shared: `on_usage` is emitted before `cost` is asked); `main.py:1222-1228` (`by_usage` reads with `get` on the worker thread), `:1383-1384` (the GUI slot reads with `pop=True`), `:1363-1364` (the key is provider, model, prompt, reply).
- **Evidence (code reading, not run):** the usage signal is queued to the GUI thread. If the GUI thread handles it before the worker reaches `cost(...)`, the entry is gone, `normalize_usage(None, ...)` estimates chars/4 (`services/usage_tracker.py:81-83`), and the run's spend count misses the real tokens (a thinking judge's reasoning, for example). A second case: when the local answer equals the reference answer (short factual replies), both judge prompts are the same text, so both calls share one key; the second overwrites the first and the second bill is a chars/4 guess.
- **Scenario:** judge thinks 400 tokens per verdict; for a handful of calls the GUI wins the race -> the stop at `:680` sees one token per verdict for those, the run can pass its ceiling, and the reservation (clamped at 0, `main.py:1386`) no longer covers it. The bill itself is right in the first case, wrong in the second.
- **Fix (Imprint-only):** read without popping in the GUI slot and clear the dict at the end of the run (already done at `:1396-1397`); or key each entry by a per-call counter kept in `_measure_ask` and handed back through the reply. Add a test that bills before the worker counts.

### RC-4 · P2 · "Apply recommended setup" now puts every agent under Local only, including agents set to Cloud only
- **Where:** `main.py:882` (a local winner for Chat gives mode "Local only"), `:906-914` (moves the box without saving the mode), with the new precedence at `:190-191`, `:4000-4001` and the guard at `:4036-4043`.
- **Evidence (code reading):** before `e57644a` an agent's own mode answered for itself and only advised agents were checked, so moving the box mainly changed Chat. Now the box's Local only beats every override and is enforced for every agent and every per-unit request.
- **Scenario:** BEST FIT picks a local model for Chat (the usual case: free and rated). The user presses Apply. The box says Local only, the saved mode still says Hybrid. Vector's logo images, Booth's narration and Reel's renders are then refused with "Request Blocked", also for an agent set to Cloud only in Settings → Models, after a click that only claimed to pick Chat's model.
- **Fix:** have the recommendation set "Hybrid allowed" (it is about one model, not a hard limit), or say in the rail that it switched the whole app to Local only. Owner decision if the hard-limit reading is wanted.

### RC-5 · P2 · A measurement already running keeps asking cloud models after Mode is set to Local only
- **Where:** `main.py:1256-1258` (checked once, at start); `:1354-1365` (each cloud call; no check).
- **Scenario:** a run starts under Hybrid; the user picks Local only a minute later -> the remaining reference and judge calls (up to 240 for the 80-prompt set) still go to the cloud, against the hint "Nothing is sent to a cloud service".
- **Fix:** when the box or saved mode becomes Local only, call `cancel()` on `local_measure_worker` (the worker stops between prompts). Reading the box from the worker thread is not safe, so do it on the GUI side.

### RC-6 · P2 · Security P1-1: the measurement path and the "On this Mac" texts are still open
- **Where:** `main.py:1350-1351` (`_measure_ask` sends the local prompts through `run_backend`, which has no address check: `:5774-5815`); `services/local_models.py:34-35` ("On this Mac · LM Studio", "On this Mac · Ollama"); `main.py:5539` ("It runs on this machine and costs nothing").
- **Evidence:** `_route_allowed` is called only from `authorize_request` (`:4664`) and `_send_chat` (`:4393`) (grep). Other content paths to a local runtime: none found besides the measurement (grep of `.ollama.`, `.lmstudio.`, `run_backend`); the release kit has its own refusal (`:4785-4788`).
- **Scenario:** `OLLAMA_HOST=203.0.113.9` under Hybrid, a new model listed -> the automatic run sends the 80 fixed measurement prompts there over plain http with no question, and rates that machine's model as local. The prompts are made up, so no user text leaves this way; the claim on screen is what fails. The security review's fix asked to show the host instead of "On this Mac" once the user has said yes; the dialog says instead "The app shows it as a local model" (`:4062-4063`).
- **Fix:** run `_remote_runtime` before a measurement starts (refuse, or ask once on the GUI thread); label a non-loopback runtime "on <host>" in the section label, the banner and the status line.

### RC-7 · P2 · The Kernel path of L-3 and P1-1 has no test
- **Where:** `main.py:4393`; `tests/test_local_only_guard.py` calls `authorize_request` only.
- **Evidence:** L-3's reproduction was Kernel: a job held on the banner, Mode moved to Local only, Switch pressed, sent to Anthropic. No test sends through `_send_chat` with a route override, a failover offer or a remote runtime. Removing the line at `:4393` would leave every new test green (not mutation-run; by reading the tests).
- **Fix:** one test per entry: held job plus Switch, failover offer, rule target, and a remote runtime under Hybrid and Local only, each through `_send_chat`.

### RC-8 · P3 · `ba870c4` alone fails its own tests
- **Where:** `ba870c4` adds `tests/test_routing_phase3.py:341-399`, which use `main.MEASURE_VERDICT_TOKENS`, `_measurement_ceiling` and `_measure_usage`; they arrive in `e57644a`. `git show ba870c4:main.py | grep -c "MEASURE_VERDICT_TOKENS\|_measurement_ceiling"` -> 0.
- **Scenario:** a bisect or a cherry-pick of the L-2 commit alone -> three failing tests unrelated to L-2. **Fix:** none needed now; keep tests with the commit they test next time.

### RC-9 · P3 · On the four advised panels the guard now pre-empts the advisor's local suggestion
- **Where:** `main.py:4664` (guard) runs before `:4666` (advisor); `services/routing_advisor.py:470-475` ("… is a cloud model … X could do it.").
- **Scenario:** Sitebuilder with a cloud model under Local only -> a plain "Request Blocked" naming no local model; Kernel, where the guard runs after the advice (`:4393`), still names one. **Fix:** run the guard after the advisor for requests the advisor looks at (the guard still catches its failure), or name the best local model in the warning.

### RC-10 · P3 · Texts that still describe the old precedence; Cloud only in the box still loses to an override
- **Where:** `main.py:183-185` and `:3997-3998` (docstrings: the override answers for itself); `services/routing_advisor.py:141` (shared: "An agent's own override wins"), whose `effective_mode` Imprint now wraps differently from Sentinel; `README.md:903` ("a Local only or Cloud only picked in the box still limits the job, whatever the saved mode").
- **Evidence:** box on Cloud only and an agent set to *Local first*: `routing_mode` returns `local_first` (`effective_mode`, `routing_advisor.py:148-149`), so that agent can still run locally while the box says Cloud only. This was there before; L-3 made the box win for Local only only. Settings → Models still offers each agent a mode with no note that Local only in the box overrides it.
- **Fix:** update the two docstrings; either let the box's Cloud only win too, or narrow the README sentence; add the note on the Models page. The shared docstring change goes to both repos.

### RC-11 · P3 · A failed re-measure says "stays unrated" while an older score for that kind stays on screen
- **Where:** `services/local_ratings.py:323-324` (`record_result` merges kinds), `:741-744`, `:756-760`; `main.py:1404-1405`.
- **Scenario:** a model measured earlier is measured again with a judge that now refuses -> status "… stays unrated: the judge gave too few usable verdicts", but `kinds` keeps the earlier scores and the picker still shows "measured writing …". No ratings file exists on this Mac (`data/local_ratings.json` and Application Support: not found), so no pre-fix score from the broken judge is stored today. **Fix:** on a failed or partial run say that earlier scores were kept, or drop the kinds that came back unrated. Shared file.

### RC-12 · P3 · Late finish of one run can clear the next run's reserve and usage
- **Where:** `main.py:1394-1397`, `:1306-1307`, `:1407`.
- **Scenario (not run):** the worker's thread has ended (`isRunning()` is False) but its queued finished signal is not yet handled; a Measure press in that gap starts a second run (`:1328`); the first finish then sets the reserve to 0 and clears the second run's usage, which is then billed at chars/4. **Fix:** ignore a finish whose worker is not `self.local_measure_worker`.

### RC-13 · P3 · A judge that thinks can spend its whole 512-token verdict cap and give nothing
- **Where:** `main.py:136`, `:1360`; `services/gemini_client.py:95-97` (the cap includes thinking; a reply can come back empty and is billed); `services/openai_client.py:92-95` (same for `max_completion_tokens`).
- **Scenario (not verified against a provider):** the cheapest judge is a thinking model -> empty verdicts, each pair unusable, every kind unrated, the run fails after paying for 160 verdicts, and the reason says "too few usable verdicts" rather than "the judge hit its cap". The L-2 fix makes this safe (no false rating); the cost is the waste. **Fix:** put the stop reason (`length`) into the run's reason, and prefer a judge whose thinking can be turned off or bounded.

## Answers to the brief's questions

1. **Hybrid, Cloud only, local addresses, a yes to a remote runtime.** Hybrid with a permitted cloud provider is allowed (`tests/test_local_only_guard.py:110`, passed). Cloud only with a cloud provider: `_local_only` is False, so `_route_allowed` returns True (`main.py:4036-4043`, by reading). Loopback forms, probed through `services/local_endpoint.py` and `providers.ollama_host()`: `http://127.0.0.1:11434`, `http://localhost:1234/v1`, `http://LOCALHOST:1234/v1`, `http://[::1]:11434`, `https://localhost:1234/v1` and `OLLAMA_HOST=0.0.0.0` (rewritten to 127.0.0.1, `services/providers.py:140`) all count as this Mac. `http://localhost.:1234` and `http://mac.local:11434` count as another machine and are asked about (rare spellings; not a finding). A yes is kept per provider and address for the session (`main.py:4056`, `:4069`; test `:125`).
2. **Precedence callers.** `execution_mode_for`: `main.py:1638` (Chat's privacy priority), `:2048` (Chat's provider list), `:3947` (`resolve_backend_model`), `:4073`. `routing_mode`: `:4007` (`_local_only`), `:4166` (Kernel's advice). No caller outside `main.py` (grep of `agents`, `ui`, `services`). All read the box's Local only first now; the side effect is RC-4.
3. **Reserve leaks.** Every status (measured, failed, stopped, budget) ends in `_on_measure_finished`, which sets the reserve to 0 (`:1395`); `measure` returns a result instead of raising (`services/local_ratings.py:753-760`). A worker that never starts: only if `QThread.start()` failed, not seen. The leak that was found is in the tests (RC-2) and a narrow race (RC-12).
4. **Thread safety of `_measure_usage`.** The dict is under a lock (`:1363`, `:1368`); the problem is the order of read and pop across threads (RC-3), not a torn write.
5. **Judge detection by its last line.** `_JUDGE_ASK` is `'Reply with exactly one word: A, B or TIE.'`; the formatted judge prompt ends with it; none of the 80 measurement prompts does (script, `config/local_rating_prompts.json`). A miss would only give a verdict the 1,024 cap.
6. **A dialog off the GUI thread.** Every `authorize_request` caller is a panel slot (grep: 24 call sites in `agents/*/panel.py` and `suno_panel.py`); the release kit uses `authorize_job_item` and the measurement worker does not reach `_route_allowed`. No non-GUI caller found.

## Tests

- **Behaviour, not implementation:** the L-2 tests drive `measure` with a stub judge and check the stored result; the guard tests call `authorize_request` and read the refusal and the dialogs. `test_measurement_calls_carry_an_output_cap_and_keep_their_usage` (`tests/test_routing_phase3.py:353`) sets `_measure_usage` by hand, which ties it to the dict's key shape; acceptable, but it cannot catch RC-3.
- **Weakened assertions:** none found. `test_split_verdicts_are_ties_so_position_bias_cancels` asserted that an always-"A" judge rates the model at the reference, which is the behaviour L-2 found wrong; replacing it with `test_a_judge_that_gives_no_usable_verdict_rates_nothing` and keeping the score check in `test_genuine_ties_still_count` (`:262-266`, 1400.0 as before) is right. The `parse_verdict` rows for `""` and "I cannot decide" changed from `TIE` to `None` for the same reason. The worker test's stub (`:316`) changed from always "A" to alternating so the run still measures; the assertion is unchanged.
- **Missing:** RC-7 (Kernel path), RC-3 (usage race), stopped and cancelled runs releasing the reserve, `localhost` and `::1` through the guard (only 127.0.0.1 is tested, `tests/test_local_only_guard.py:121`).

## Tests run (this worktree, main checkout's venv; no network, no model server)

- `tests/test_local_ratings.py tests/test_local_only_guard.py tests/test_routing_phase3.py tests/test_routing_phase4.py tests/test_routing_panels.py`: 1 failed (RC-2), 138 passed, 272 s.
- `tests/test_routing_phase3.py` with `--randomly-seed` 1, 2, 3: failed, passed, passed. The failing test alone: passed.
- Sentinel worktree, `tests/test_routing_phase3.py -k measure_worker_runs_the_engine` with Sentinel's venv: 1 failed (RC-1).
- `cmp` of the two shared files against Sentinel's `claude/ratings-judge-l2`: identical (exit 0).
- Two read-only scripts: loopback detection for the addresses in answer 1, and the judge-prompt suffix check in answer 5.

## Not verified

- The full suite (a full run was in progress in this worktree) and Sentinel's full suite; ruff and the lint ratchet; CI on GitHub.
- Anything against a live provider or model server: real usage numbers, a thinking judge's verdicts (RC-13), what DeepSeek counts as completion tokens.
- RC-3 and RC-12 were found by reading the order of calls and signals; neither race was reproduced.
- RC-4 and RC-5 were not run in a window; both follow from the lines cited.
- Sentinel's own measurement code in its `main.py` (not read; whether it shares the L-1 problems is open).
- No mutation run of the new logic.
