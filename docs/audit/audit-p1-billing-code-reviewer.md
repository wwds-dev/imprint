# Code review: audit-p1-billing (X-1, B-F1, B-F2, B-F3), 2026-10-14

Role: code-reviewer (read-only). Uncommitted diff (36 files, +1139/−241, 8 untracked) on `foundry/imprint-audit-p1-2026-10-14`.
Playbook `status: baseline`. Full suite, random order: 1617 passed, 6 skipped, 6 subtests (26.5 min under load).
11 new/changed test files: 296 passed. pyflakes: pre-existing findings only. ruff not installed (ratchet not run).

## Verdict
No P0. One P1 (needs an owner decision). All four audit P1s fixed with evidence.

## P1
**P1-1 Thinking reserve applied to every DeepSeek, Kimi and Qwen model; the owner approved it for thinking models at their
documented maximum.** `services/output_limits.py:37-44`, `:62-70`; used by `max_cost_eur` (`services/usage_tracker.py:67`)
for the guard, Chat estimate, `_priced_for_request` (`main.py:1529`) and assessment. No model was classified; Kimi/Qwen
65,536 is a stand-in. Reproduced on the real window: `kimi-k3` (the tracked default, `config/settings.json:12`) refused at
€0 spent: "Not sent: this request can cost up to €1.02 and your session cap has €1.00 left (of €1.00)."

| Model (100 tokens in) | With thinking | Cap only |
|---|---|---|
| kimi-k3 | €1.0177 | €0.1133 |
| kimi-k2.7-code-highspeed | €0.5428 | €0.0605 |
| qwen3.8-max | €0.4072 | €0.0454 |
| kimi-k2.7-code, kimi-k2.6 | €0.2714 | €0.0302 |
| deepseek-v4-pro | €0.2687 | €0.0300 |
| deepseek-flash, qwen-plus | €0.0814 | €0.0091 |

No usable thinking metadata exists (`config/pricing.json` rates only; `KNOWN_MODELS` bare ids;
`services/recommendations/catalog.py:143-155` name heuristics must not be reused). Fix: key the table by (provider, model),
`thinking_reserve_tokens(backend, model)` → 0 when absent; pass `model` through the reserve helpers (~10 lines); owner picks the
rows; per-model tests incl. kimi-k3 "three titles" allowed at €0 spent.

## P2
1. Wording beyond Design states the unverified figure as fact: `services/output_limits.py:85` ", plus up to 65,536 for
   thinking" (confirm dialog, `main.py:3700`), `:77` " + 65,536 thinking" (live line/popup), README, CHANGELOG. D4 said no
   thinking term. Show only for listed models; wording needs sign-off.
2. No test covers stop reason → panel notice: `main.py:4498` `self._with_stop(entry, context["usage"])`; mutant
   `_with_stop(entry, None)` survived 170/170. Add a window test (authorize → `note_request_usage` with `stop_reason: "length"`
   → real `record_request`) and one panel test with the real `record_request`.

## P3
1. Fiverr image prompt (`agents/fiverr/panel.py:434-440`) and Social clip brief (`agents/social/panel.py:570-577`) chain into a
   paid step without the cut-off notice; an empty Gemini answer gives an empty Fiverr prompt or a blank Social topic (vidforge
   then renders the next topic from topics.txt, ~€2). Show the notice and don't chain; refuse empty prompt/topic.
2. `services/gemini_client.py:446-447`: a later chunk without finish_reason resets `stop_reason` to None. Set only when not None.
3. Fiverr Stop race on `isRunning()` (`agents/fiverr/panel.py:937-966`); same as security P3-1.
4. Refusal can show two equal figures: validator compares raw floats (`services/validator.py:8-16`, `:143`) while `money_text`
   rounds to 6 decimals (`services/money_text.py:20-23`); reproduced "up to €0.43 … €0.43 left". Quantize in `validator._money`.
5. Wording extrapolated beyond Design (needs UX sign-off): `agents/video/studio.py:385`, `:386`, `:396`;
   `agents/fiverr/panel.py:929-936`, `:957`, `:965`; `agents/social/panel.py:732` (tooltip).
6. README says the notice is "never saved or exported"; Chat's Export Report (`main.py:5210-5216`) exports the [Cut off] line.
7. One-off Qt segfault in test_webdesign_panel: 0 of 20 isolated runs reproduced; `ui/widgets.py` unchanged; only UI change there
   is `setWordWrap(True)` (`agents/webdesign/panel.py:131`). Add a `testing` TODO with the stack; not blocking.
8. Pre-existing: `services/anthropic_client.py:163` undefined `model` in `_stream` 404 handler (F821). Use `kwargs["model"]`.

## Checked and sound
X-1 (`agents/social/publishing.py:77-91`, `:158-170`; tests `tests/test_social.py:381-428`). B-F1 (`services/gemini_client.py:72-111`,
`:226-233`, `:440-447`; €0.1150 asserted). Cap on all six clients, chat and stream, correct parameter names; no hard-coded
8096/8192 left; only paid text SDK calls. stop_reason reaches the notice for every provider. One estimate (`max_cost_eur`) for
`estimate_chat_cost`, `authorize_request`, `_priced_for_request`; Chat builds messages before estimating. All 15 text call sites
pass `messages=` (same variable handed to `_new_chat_worker`); 6 flat calls unchanged; 3 renders/batches `partial_billing=True`.
`record_partial` (`main.py:4506-4564`) token-only, clamped [0, confirmed], no €0 row, closes once. D3 rules in
`agents/video/studio.py:331-361`; Stop before script bills €0; Fiverr signals bound to the run token. Qt hand-off: trace written on
the worker thread, emitted as a copy; no new deadlock path. `estimate_chat_cost` return change: all callers updated.
`cost_type` TEXT without CHECK; totals sum regardless of type.

Doc drift: app-context says 1512 tests collected; now 1623.

---

# Loop 1 re-review and Secure re-check (2026-10-19): PASS

Scope `git diff b0db81e` (50 files) plus uncommitted TODO/activity. Playbook `status: current` (2026-10-14).
Targeted 13 files: 458 passed; 29 related files: 917 passed, 2 skipped. Mutation on a `git archive HEAD` copy: loop-0 fixes
19 mutants, 18 killed (P3-2 survived); panel cut-off notices 5 mutants, 5 survived (P2-1). pyflakes: no new findings; F821 gone.

All loop-0 P1s fixed and mutant-proven: thinking reserve per owner decision (`services/output_limits.py:27`, `:45-48`, `:66-72`;
`services/qwen_client.py:361`, `:391`; kimi-k3 up to €0.12, qwen3.8-max €0.10, deepseek-v4-pro €0.27 recomputed from
`config/pricing.json`); thinking clause only when non-zero; stop reason through the real guard (`main.py:4707`); Video/Social
wiring tests; single eur_per_usd reader + Settings validation; no chaining after cut-off/empty; Gemini stop_reason kept;
validator quantize; Fiverr Stop on terminal signal; last image counted; html.escape in Run Log and Cost History; Reddit name rule
and "r/<name>" in the confirmation; README Export sentence; Anthropic 404.

## Open
- **P2-1** Cut-off notice untested in most panel handlers (`agents/fiverr/panel.py:649`, `:694`; `agents/creator/panel.py:699`;
  `agents/music/panel.py:241`; `agents/music/suno_panel.py:226`; `agents/manuscript/panel.py:850`; `agents/webdesign/panel.py:225`;
  `agents/author/panel.py:1421`, `:1542`). Five `result_notice → None` mutants survived. Fix: one parametrized window test per handler.
- **P3-1** Right-rail Save Limits (`main.py:743-756`) accepts inf/nan/negative budgets; the refusal text points users there. inf
  removes the cap; nan makes `authorize_request` raise and can leave Fiverr's buttons disabled. Pre-existing. Share the Settings
  `budget()` check; test "inf", "nan", "-1".
- **P3-2** `services/stream_usage.py:56-58` keep-once-set guard for OpenAI-compatible streams untested (mutant survived).
- **P3-3** AST test checks only the `messages=` keyword (`tests/test_request_estimate.py:594-605`); today all 15 sites pass the
  same variable they hand the worker.
- **P3-4** Wording beyond Design without sign-off: `agents/video/studio.py:384-387`, `agents/fiverr/panel.py:445-446`, `:973-975`,
  `agents/social/panel.py:585-587`, `:742`.
- **P3-5** Video log renders provider error HTML (`agents/video/panel.py:869` `video_log.append(error)`); escape it.
- **P3-6** Suite writes Saved Chats and `data/model_watch.json` into the worktree's gitignored `data/` (pre-existing).
- Also open: `_assessment_text` "up to" wording not asserted (`main.py:1277-1283`, `:1330-1336`); live line builds messages without
  try/except (`main.py:564-565`); Fiverr tests don't assert session/daily totals; app-context test count stale.

## Secure re-check
No new budget-guard bypass; no double billing via `record_partial` (`main.py:4715-4773`); Reddit name validated before login, only
`[A-Za-z0-9_]` reaches the form; Run Log and Cost History escaped. Model-watch `list_media_models_live` uses free list calls.
Higgsfield `/estimate` probe (`services/higgsfield_client.py:394-427`) is one POST, catalog paths only, never a submit, €0-gated
and off by default; whether `/estimate` is free remains the TODO `@me`.
