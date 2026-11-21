# Code review: one-click-release, slice 1 (free path)

Role: `code-reviewer`, read-only. Reviewer did not write the code. Date 2026-11-21.
Branch `claude/one-click-release-slice1-599646`, diff `3e0a761..HEAD` (HEAD 3ca9535).
Spec `docs/specs/one-click-release.md`, ADR 0005. Method: read every file in scope; ran
`pytest -q -p no:randomly` on test_release_kit_core/contract/e2e, test_quote_finder,
test_calendar_export, test_database_migrations: **77 passed** (83 s). Full suite not run.
Not verified: a real Ollama + `say` run, `pmset -g assertions`, App Nap, contrast.

## Verdict
No P0. **One P1** (a stage handler exception strands a "running" kit), four P2, several P3.
The money guard holds for slice 1: nothing paid can be reached. Fix the P1 and P2-1..P2-3 before Verify.

## P1

**P1-1. An exception in any stage handler or callback leaves the kit `running` forever, Mac held awake.**
`ui/release_kit/driver.py` `_step` (l.238-259) and every `done`/`failed` closure (l.399-426, 468-478, 510-524, 556-580) run as bare Qt slots or `QTimer.singleShot` callbacks. Nothing wraps them in try/except, and `_leave` (l.272) is reached only by explicit calls. Qt prints the traceback and carries on. Examples that can raise inside a callback:
- `record_job_item` → `UsageTracker.log_request` hits `ux_usage_job_item` (IntegrityError), or disk/DB locked;
- `write_calendar_csv` (disk full, folder removed) or `file_sha256` in `_finish_item` (l.314-317);
- `get_version`, `cal["quote_ids"]` KeyError, `ids[slot['quote']]` (l.498) on a ledger edited by a recovery;
- `_stage_epub` handles render errors but not `ledger` errors after it.

Result: ledger status stays `running`, stage stays `running`, `caffeinate` stays held until Imprint quits, no report rewrite, Stop only sets `_stop` and nothing is scheduled to read it, `_recover_release_kits` never runs again, and "one kit at a time" blocks every other kit. For an unattended overnight run this is the worst failure shape: silent, and the Mac never sleeps.
Fix: one wrapper around `_step` and each callback that turns an exception into `_pause("item_failed", …)` (or `_leave("paused","interrupted")` if even that fails), plus a test that injects a raising renderer after `record_job_item`.

## P2

**P2-1. "On this Mac, no charge" is not guaranteed for local routes.** `services/release_kit/plan.py:179-199` and the dialog label every Ollama/LM Studio route as "on this Mac". `services/providers.py:124-149` honours `OLLAMA_HOST` and `LMSTUDIO_URL`; `main.py:272` builds the client from it. If either points at another machine, the whole book is sent off-device while the confirmation, report ("Every step ran on this Mac", report.py:122) and provenance say otherwise, and `is_local_route` still authorizes it. Slice 1's promise is "free and local". Either refuse non-loopback endpoints in `estimate()`/`authorize_job_item`, or word the row by the actual host. (Security phase should look too.)

**P2-2. `authorize_job_item` trusts its caller on route and stage.** `main.py` (`authorize_job_item`) checks only `is_local_route(provider)`, job running, model non-empty. ADR 0005 §2 says it checks the route equals the approved route; here it never compares `provider`/`model` to the job's stage row or approval, and never checks `stage` is the one running or that the item belongs to it (`STAGE_BY_KEY[stage]` also raises KeyError on an unknown stage). Safe today only because the driver passes the stage row. Slice 2 builds the money checks on top of this seam, so close it now: read the stage row, refuse a mismatch with scope `route`.

**P2-3. The 8,192-token reply cap shown to the owner is not enforced, and nothing times out.** `plan.py:211,234` ("one reply capped at 8,192 tokens") and `driver.py:572` ("stopped at the 8,192-token limit") imply a cap. `stages.ask_text` → `run_backend` → `client.stream_chat(messages, model)` passes no output limit (grep: no `num_predict`/`max_tokens` on the local path). A looping local model, or one that never answers, holds the single running kit, and Stop only acts after the item. Either pass a limit on the local clients, or drop the claim and add a per-item deadline that pauses with `route_unavailable`. (Local client request timeout: not verified.)

**P2-4. The contract test is name-based and can be bypassed by passing the function as a value.** `tests/test_release_kit_contract.py` flags direct calls to `run_backend`, `render_short`, etc. The driver passes `self.host.run_backend` as an argument (driver.py:429, 589) and calls renderers through `self.render[...]` (a replaceable dict, l.80), neither of which the walk sees. The real guarantee is the `grant.check()` inside `ask_text`/`render_short_item`, which the test does cover, but a new stage calling `self.host.run_backend` by reference would pass. Add `run_backend` as an attribute *reference* (not only a call) to the walk, and assert `default_renderers()` values all take `grant` or are on an explicit local-only list.

**P2-5. Quit during a long item.** `stop_now` (driver.py:126-148) waits 2 s, then `closeEvent` (main.py ~6470) waits 2 s again and accepts. A local request is not interruptible, so the QThread can still be running at process exit (the Qt "destroyed while running" abort class in the workspace rules). `shutdown()` does name `release_kit_worker` and nothing calls `terminate()`, which is correct; the residual risk is the same as the other workers' pattern. Note for Verify: test quit mid-quotes with a sleeping fake.

## P3

- **P3-1. CSV guard misses tab and carriage return.** `calendar_export.py:22` guards `= + - @` only; OWASP also lists leading `\t` and `\r`. Add them. (Guard otherwise correct: applied to every cell including the AI cell; Press shares it.)
- **P3-2. Captions `incomplete` has no re-run path.** `incomplete` is terminal (`runner.TERMINAL_STAGE`), so Resume never re-asks; report.py:131 says "or run this step again". Remove the words or add the action.
- **P3-3. `KeepAwake.acquire()` returns False silently** (power.py:36-40) when `caffeinate` is missing; the window still says "This Mac stays awake" (window.py:216). Surface it, or drop the sentence when not held.
- **P3-4. Quote bound margin is thin.** `QUOTES_INPUT_BOUND` 32,000 vs a real request of 30,854-31,292 chars (measured). Growing `QUOTE_SUGGESTION_PROMPT` by ~700 chars would pause every kit with `over_line` and no way out. Derive the bound from the prompt length as the captions bound does.
- **P3-5. `driver.resume` / `window.resume` do not catch non-KitBusy errors** from `ledger.resume` (e.g. OSError during `verify_finished`); the slot raises and the note stays "Checking finished files…".
- **P3-6. Pending token leak** if the driver raises between `authorize_job_item` and `_run_unit` (token stays in `_pending_requests`, run logged `running`). Covered once P1-1 is wrapped (close the grant in the handler).
- **P3-7. `set_stage`/`mark_item` build SQL from keyword names** (ledger.py:215, 273). Internal callers only; add an allow-list of columns so a future caller cannot inject.
- **P3-8. `record_job_item` clamps any cost above €0 to `capped`** (main.py, granted always 0.0). Right for slice 1; slice 2 must replace `granted` with the item's real grant before it ships paid routes (ADR 0005 §3).

## Checks requested, result

| Check | Result |
|---|---|
| No paid call outside the guard; only local routes | Holds. `authorize_job_item` refuses non-`is_local_route`; the dialog offers only local models/`system`; estimate blocks paid routes (plan.py:195). See P2-1/P2-2 for the two soft spots. |
| JobGrant minted only by `authorize_job_item` | Holds (private `_MINT`, `__slots__`, AST test). Token never enters `_pending_by_agent` (test). |
| Zero price = unknown, blocks | Not reachable in slice 1 (no priced route; cost fixed €0). `record_job_item` records `capped` rather than trusting a price. Re-check in slice 2 (P3-8). |
| Ledger transitions, resume, SHA verify | Correct as written: `JOB_TRANSITIONS` enforced, pause reason validated, `verify_finished` re-opens changed items and the link stage. Gap: P3-2. |
| Crash recovery `recover(active=…)` | Correct: running job → paused/interrupted, intent local request → failed, local file → planned, active job untouched, run before Booth's scan. Paid cases deferred to slice 2 as specced. |
| One kit at a time | Partial unique index `ux_release_jobs_one_running` plus `KitBusy` mapping (ledger.py:107); tested. Migration adds `ux_usage_job_item` after columns exist (old-DB test present). |
| Qt threading | No `terminate()`. Worker touches neither DB nor guard (stages.py docstring true; `ask_text` only calls `run_backend`). `_finish_unit` joins a worker that already emitted. `release_kit_worker` is named in closeEvent. No UI-thread fetch. Residual: P2-5. |
| Keep-awake released on every exit | `_leave` finally-block releases on every path that reaches it (stop, error pause, finish, quit). Paths that never reach it: P1-1. `-w <pid>` backstop covers a crash. |
| CSV formula guard | Present and applied; P3-1. |
| Nothing is posted | Holds. No network import in kit code (test), report ends "Nothing was posted…", CSV is a file. |
| No income/result claims | None found in report.py, window.py, confirm_dialog.py, plan.py. |
| Extractions (quote_finder, calendar_export, shorts_generator) | Behaviour-preserving; Press delegates. `quote_finder` verbatim check normalises whitespace and curly quotes only; too-long dropped not cut; deterministic windows. `render_short` gets an explicit voice provider (legal L1). |

## Build decisions the design did not cover

**`no_quotes` and `item_failed` pause reasons: acceptable, with two reservations.**
- Both are in `PAUSE_REASONS` (ledger.py:37) and `REASON_ACTION` (window.py:26), and a pause needs a known reason, so nothing is unlabelled. D5 should gain rows for them (UX/owner).
- `no_quotes` re-asks the same model with the same deterministic windows, so Resume will usually repeat the failure. The pause text should tell the owner to pick another model (needs a way to change the route after approval, which the spec forbids mid-kit), or the kit should be discarded. Owner call.
- `item_failed` mixes transient causes (disk full) with permanent ones (title/byline missing, version gone). Resume on a permanent cause loops. Consider a distinct reason for "needs a change in the Project" with Discard as the offered action.

**Notice N5 slice-1 adaptation (`plan.NOTICES["N5"]`, plan.py:61): flagged, not decided.** The wording is the owner's or a lawyer's. Facts for them: the legal draft (`docs/audit/one-click-release-legal-consult.md:58`) reads "This kit contains AI-generated narration and captions. See the report."; Build changed it to "AI-generated captions and quote choices", dropping narration (none in slice 1) and adding quotes. It shows only in the Release Kits window when a kit is made (window.py:221), not in the report (the report carries N2 and the N4 "AI used" list), and `plan_json` records N2 only, not N5. Also note the synthetic Shorts voice is AI-generated audio that the adapted text no longer mentions (N2 covers the licence, not the AI label). Mark the string as a draft awaiting sign-off; do not treat it as cleared.

## Tests reviewed
`test_release_kit_core.py`, `_contract.py`, `_e2e.py` cover transitions, recovery, resume/SHA, keep-awake kill path, report/provenance claims, exit-path release, one-dialog run, paid-route refusal, threaded driver. Missing for P1-1 (raising callback), P2-1 (remote endpoint), P2-2 (route mismatch), P2-5 (quit mid-item with a slow worker), and the CSV tab/CR case. Fakes only (as noted in Build); the e2e leaves parentless widgets per GodAI (known TODO P2 segfault, out of scope).
