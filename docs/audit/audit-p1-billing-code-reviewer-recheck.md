# Code review recheck: audit-p1-billing, 2026-11-24

Role: code-reviewer (read-only), a different session from the author. Playbook `docs/playbooks/code-reviewer.md`: `status: current`, `last-reviewed: 2026-10-14` (41 days, not stale).

Scope: were the P0/P1 findings of the three 2026-10-14/19 reports fixed, did the Build round of 2026-10-19 12:22 to 12:51 (never reviewed) add anything, and is the hidden-imports fix real and guarded. Not a new review of the whole feature.

Reviewed: branch `claude/happy-dubinsky-48c27c` at `e79f696`. The unreviewed round cannot be separated by commit: `12604e9` (2026-10-19 12:52) holds both the loop-1 fixes that were reviewed uncommitted and the later round. Its whole code diff was read (`main.py`, `services/validator.py`, `ui/dialogs.py`, nine panels, three test files), then each fix was checked in today's code, because the merge `c04e20a` (2026-10-22) had conflicts in `main.py`, `services/validator.py` and four panels.

## Verdict

**No fix needed before release for this spec.** Every P0/P1 from the three reports is fixed in today's code and proven by a passing test. The unreviewed round is small and sound. One new P2 was found beside it (saved limits are not read back at launch); it is older than this spec. The hidden-imports fix is real; its guard is a text check and has gaps (P3).

**Counts:** P0: 0 · P1: 0 · P2: 1 · P3: 3

One owner task from this spec is still open in writing: `TODO.md:143` (`P1` `research` `@me`, confirm the Kimi, Qwen and DeepSeek cap and thinking bounds on the first paid run). Other open P0 rows in `TODO.md` (`:61` QB-2, `:62` QB-3, `:97` QH-2) come from later audits and are outside this spec; they still stand in the way of a release of the app.

## Findings

### B-1 · P2 · Saved budget limits are not read back at launch
- **Where:** `main.py:382-383` (start-up reads `self.settings`, which is `config/settings.json`, `main.py:266`); `main.py:831-832` and `ui/dialogs.py:1040-1041` (both save to the database with `save_setting`); `ui/dialogs.py:402`, `:407` (Settings shows the database value).
- **Evidence:** `grep -n "get_setting(" main.py` returns nothing; `grep -n budget config/settings.json` returns nothing; the only assignments to `session_budget_eur` / `daily_budget_eur` are `main.py:382-383`, `:829-830` and `ui/dialogs.py:1042-1043`. Read from the code, not run on a relaunch.
- **Failure:** the user sets Session € 0.25 and Daily € 2 and presses Save Limits ("Budget limits saved."). After quit and relaunch the guard checks against €1.00 and €5.00 again. A request of up to €0.44 that the user's own cap should refuse is offered for confirmation and can be sent. Settings > General still shows 0.25 and 2, so the screen and the guard disagree. A raised cap falls back the same way (more refusals, no loss).
- **Why it is here:** it predates this spec (`main.py:382-383` date from 2026-06-16), but the unreviewed round rewrote `save_budget_limits`, the new refusal text sends the user to Save Limits, and the new test `tests/test_request_estimate.py:708` checks the database row only, never that the saved value is the one enforced next time.
- **Fix:** at start-up read both values with `get_setting`, pass them through `valid_budget_eur`, and fall back to 1.00 / 5.00 when the result is None. Add a test that saves, builds a second window on the same database and asserts the caps. The same check also closes the path where a hand-edited `settings.json` holds "inf" or "nan" (`float()` at `main.py:382-383` accepts both).

### B-2 · P3 · The Video log still takes untrusted text as markup in three places
- **Where:** `agents/video/panel.py:1117` (`[Resume] {slug}: {error}` from a resumed job), `:543` and `:1048` (worker log and status signals connected straight to `video_log.append`).
- **Evidence:** loop-1 finding P3-5 was fixed with `_log_text` (`agents/video/panel.py:861-873`) at the two error sites (`:890`, `:960`) only. The helper's own docstring says `append()` renders anything that looks like HTML.
- **Failure:** a provider error with markup in a resumed render shows as formatted text instead of what was sent. Display only; no script runs in a QTextEdit.
- **Fix:** route `:1117` through `_log_text`; connect the two signals to `_log_text` as well.

### B-3 · P3 · The hidden-imports guard checks the spec's text, not what gets bundled
- **Where:** `tests/test_spec_hiddenimports.py:47-57`; `Imprint.spec:33-34`.
- **Evidence:** the scan covers `agents`, `services`, `providers`, `ui` (`:52`). `main.py` is in the `known` set (`:50`) but is never scanned, so that entry does nothing; `main.py:6613` and `vidforge/vidforge/cli.py:349` both call `__import__`. Only `agents` and `services` are collected whole; `providers` and `ui` are not.
- **Failure:** a later `import_module(f"providers.{name}")` written in `main.py` passes the guard and the frozen build fails at run time the way it did on 2026-10-22. `collect_submodules` also only warns and skips a package that fails to import at build time; no test would see that.
- **Fix:** scan `main.py` and the other top-level modules too; keep the frozen `--selftest` (it ran in the 2026-10-22 retry) as a required release step and add a `profile_for` call for every catalog agent to it.

### B-4 · P3 · Wording beyond the Design still has no recorded sign-off
- **Where:** loop-1 P3-4 (`agents/video/studio.py:384-387`, `agents/fiverr/panel.py`, `agents/social/panel.py` status and tooltip lines).
- **Evidence:** nothing in the spec, `TODO.md` or the reports records a decision on these strings. Not rechecked line by line.
- **Fix:** the owner reads the strings once, or the row goes to `TODO.md`.

## Earlier finding -> status

| Report | Finding | Status | Code | Test |
|---|---|---|---|---|
| Audit | X-1 Reddit name (P1) | fixed | `agents/social/publishing.py:100-117` | `tests/test_social.py:387`, `:414`, `:435`, `:458` |
| Audit | B-F1 Gemini thinking tokens (P1) | fixed | `services/gemini_client.py:72-91` | `tests/test_gemini_usage.py:94`, `:102`, `:111` |
| Audit | B-F2 output cap and reserve (P1) | fixed | cap sent at `openai_client.py:95`, `:157`; `deepseek_client.py:75`, `:104`; `kimi_client.py:71`, `:101`; `qwen_client.py:360`, `:390`; `gemini_client.py:239`, `:451`; `anthropic_client.py:115`, `:181`. No text SDK call exists outside these six files in `main.py`, `agents/`, `services/`, `providers/` and `ui/` (grep); `vidforge/` makes its own calls inside a render and was not rechecked. | `tests/test_output_cap.py:177`, `:208`, `:214`; `tests/test_request_estimate.py:201`, `:735`, `:767` |
| Audit | B-F3 partial billing (P1) | fixed | `main.py:5553` (`record_partial`); `agents/video/panel.py:523`, `agents/social/panel.py:619`, `agents/fiverr/panel.py:501` | `tests/test_partial_billing.py:342`, `:362`, `:373`, `:789`, `:807`, `:885` |
| Code review | P1-1 thinking reserve on every DeepSeek/Kimi/Qwen model | fixed per the owner decision written in the spec (`docs/specs/audit-p1-billing.md:263-269`) | `services/output_limits.py:45-48`, `:66-72`; `services/qwen_client.py:361`, `:391` | `tests/test_request_estimate.py:88`, `:102`, `:310` (kimi-k3 allowed at €0 spent, "Up to €0.12"), `:327`; `tests/test_output_cap.py:190` |
| QA | P1 Video and Social clip signal wiring untested | fixed | `agents/video/panel.py:544`, `:546`; `agents/social/panel.py:643`, `:645` | `tests/test_partial_billing.py:588`, `:619` |
| QA | P1 (owner) 65,536 stand-in for Kimi/Qwen | fixed, same as P1-1 | as above | as above |
| Security | no P0/P1 | n/a | | |
| Security | P2-1 Qwen thinking bound | fixed in code; parameter name unverified, owner row open | `services/qwen_client.py:361`, `:391` | `tests/test_output_cap.py:190`; `TODO.md:143` |
| Security | P2-2 two EUR readers | fixed | `services/usage_tracker.py:12-17`; `services/per_unit_pricing.py:64`, `:78` | not rechecked by name |
| Code review loop 1 | P2-1 cut-off notice untested in panels | fixed (unreviewed round) | n/a | `tests/test_output_cap.py:599-653` |
| Code review loop 1 | P3-1 Save Limits takes inf/nan/negative | fixed (unreviewed round) | `main.py:815-836`; `services/validator.py:10-24`; `ui/dialogs.py:1030-1031` | `tests/test_request_estimate.py:697`, `:708` |
| Code review loop 1 | P3-2 stream keep-once-set untested | fixed | n/a | `tests/test_output_cap.py:503` |
| Code review loop 1 | P3-3 AST test keyword only | fixed | n/a | `tests/test_request_estimate.py:767` |
| Code review loop 1 | P3-4 wording without sign-off | open (B-4) | | |
| Code review loop 1 | P3-5 Video log renders error HTML | fixed at two sites; three left (B-2) | `agents/video/panel.py:861-873`, `:890`, `:960` | `tests/test_partial_billing.py:964` |
| Code review loop 1 | P3-6 suite writes into `data/` | not rechecked | | |
| Code review loop 1 | live line without try/except; assessment wording unasserted | fixed | `main.py:627-633` | `tests/test_request_estimate.py:367`, `:411`, `:418` |
| Release 2026-10-22 | frozen build: `ModuleNotFoundError: agents.chat.recommendations` | fixed | `Imprint.spec:33-34` | `tests/test_spec_hiddenimports.py:28`, `:38`, `:47`; gaps in B-3 |
| Release 2026-10-22 | plist version 1.0.1 typed | fixed | `Imprint.spec:143-148`, `:158-159` | `tests/test_spec_hiddenimports.py:60` |

Deferred in writing, still open in `TODO.md`: `:143` first paid run (`P1`, `@me`); B-F4, B-F5 (`:145`), B-F6, B-F7 (`P2`, spec Non-goals).

## The unreviewed round (2026-10-19 12:22 to 12:51): what it changed

1. `save_budget_limits` checks both fields with `valid_budget_eur` before keeping either (`main.py:815-836`). Sound. `valid_budget_eur` returns None for "inf", "nan", "-1", "1e999" and "" and 0.0 / 2.5 for "0" / " 2.5 " (run in this recheck).
2. Settings uses the same function (`ui/dialogs.py:1030-1031`). Sound.
3. The live estimate catches a failed message build and prices the prompt alone (`main.py:627-633`); nothing is sent at that figure. Sound.
4. `_log_text` escapes provider errors in the Video log. Sound; see B-2 for the sites it does not cover.
5. Nine status labels became plain text. No panel sets markup on any of them (grep for tags in the nine files: the only HTML goes to `social_accounts_box` and to `_log_text`).
6. Tests only: cut-off notices for nine handlers, stream stop reason, assessment wording, Save Limits, the stricter messages check.

No new paid path, no change to `authorize_request`, `record_request` or `record_partial` in that round.

## Hidden imports: is the fix real and guarded

- Real: `Imprint.spec:33-34` collects every submodule of `agents` and `services`. All ten `agents/<key>/recommendations.py` files exist, every catalog `recommendation_profile` (`agents/catalog.py:32-86`) points into `agents.`, and every directory with Python files under `agents/` and `services/` has an `__init__.py`. `scripts/build_app.sh:41` changes to the project root before the build, so both packages are importable when the spec runs. The 2026-10-22 retry found all ten modules in the archive.
- Guarded: by a text check of the spec plus the list of dynamic-import files. It passes today. Its gaps are in B-3.

## Tests run (this worktree, main checkout's venv)

- `tests/test_output_cap.py`, `tests/test_partial_billing.py`, `tests/test_request_estimate.py`, `tests/test_spec_hiddenimports.py`: 184 passed.
- `tests/test_gemini_usage.py`, `tests/test_social.py`: 84 passed.
- The worktree was unchanged after the runs (`git status`: only `docs/foundry/activity.jsonl`, modified before this recheck started).

## Not verified

- The full suite (a full run was in progress in this worktree; not started here).
- B-1 on a real relaunch; it rests on the code reading above.
- A frozen build of today's tree. The last recorded one is 2026-10-22; the spec has since changed the bundle name to "Imprint Studio". `collect_submodules` was not run.
- Live billing on any provider; the Kimi and Qwen `max_tokens` and Qwen `thinking_budget` parameter names (`TODO.md:143`).
- Mutation checks; none were run in this recheck. The loop-1 mutation results are the QA report's.
- Loop-1 P3-6 and the Security P3 list beyond what the table cites.
- CI status on GitHub.
