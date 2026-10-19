# QA report: audit-p1-billing (Verify, loop 0, 2026-10-14)

Role: qa-engineer. Imports confirmed in the worktree. Playbook `status: baseline`.

## Verdict: FAIL (one gap)
Suite green in random and file order; every success measure proven by an exact-value offline test. But the Video and Social
clip signal wiring is untested: three mutants that bring back B-F3 ("€0 on failure") survive the whole suite.

## 1. Full suite
| Run | Result |
|---|---|
| `--randomly-seed=7` | 1617 passed, 6 skipped, 6 subtests (21:42) |
| file order (under a coverage tracer) | 1617 passed, 6 skipped (29:37) |
Skips are environmental (no lab_hub/sentinel checkout, heygen/synthesia, no version stamp).

## 2. test_webdesign_panel segfault
25/25 passes on the worktree and 25/25 on a `git archive HEAD` copy; three full runs, no crash. Crash site
`ui/widgets.py:73` is unchanged code. Likely the existing Qt-lifecycle hazard (panels closed, not deleted; leaked combos polished
in `processEvents`). Known flake to track, not a regression.

## 3. Spec mapping
X-1 `tests/test_social.py` (9 normalisation, 6 refusal cases, no login/post on refusal): PASS. B-F1 `tests/test_gemini_usage.py`
(chat + stream, €0.1150, thoughts None → 800): PASS. B-F2 cap per client (12 cases), estimate/guard/recommendation exact
agreement on full messages, D2 refusal at €0.95 and "Up to €0.44", 12 stop-at-cap cases and notices: PASS. B-F3
`tests/test_partial_billing.py` handler level: PASS; wiring not covered. Architecture items 1, 2, 4-8, 10 covered; 3 partly;
9 handler level only.

Weak spots: panel tests set private attributes and call handlers directly; the video window test computes its expected value with
production `partial_render_cost_usd` and its trace makes amount = cap = total; `authorized_messages` in music/webdesign FakeHosts
never asserted; Social clip test checks neither daily total nor "no Saved Chat"; Fiverr tests don't check session/daily totals.

## 4. Mutation (copy only)
Killed: webdesign drops `messages=`; Anthropic stream without cap / back to 8096; `record_partial` €0 row; social handler body
calls `abandon_request`; Creator `usage_signal` disconnected; Reddit `lstrip` back (2 variants); Gemini thoughts dropped; plus
13 extra (estimate ignores messages, no thinking reserve, no trace before error, stream stop reason dropped, uncapped partial,
Chat always `[Finished]`, `up_to` rounding, Gemini stream no config, Fiverr images not counted, …).
**Survived:** (d1) Social clip `error_signal` wired back to the abandon handler; (h) Video `trace_signal.connect(self._on_trace)`
removed; (i) Social clip `trace_signal` connection removed. Never executed by any test: `agents/social/panel.py:631,633`,
`agents/video/panel.py:537,852`.

Changed-line coverage (own tracer): 608/690 lines (88.1%), 92/108 branch outcomes. 100% for the six clients, `stream_usage`,
`usage_tracker`, `validator`, `output_limits`, `money_text`. Lowest: `agents/author/panel.py` 5/17, `agents/manuscript/panel.py`
8/17, `agents/creator/panel.py` 6/10, `agents/social/panel.py` 26/43, `main.py` 117/129 (live line `:592-594`, popup
`:613-615`, `_assessment_text` `:1262-1264`, `send_prompt` build failure `:3567-3569`).

## 5. User-visible "up to" (100-token prompt, defaults session €1.00, daily €5.00)
gpt-4o-mini €0.01; gpt-6-astra €0.38; deepseek-flash €0.09; deepseek-v4-pro €0.27; gemini-2.5-flash €0.02;
gemini-3.1-pro-preview €0.14; kimi-k2.7-code €0.28; kimi-k2.7-code-highspeed €0.55; **kimi-k3 €1.02 and any Kimi model without its
own price row €1.02: refused on a fresh session**; qwen3.8-max €0.41; claude-sonnet-5-5 €0.08; claude-fable-5-1 €0.38.

## Ranked gaps
1. **P1** Video and Social clip wiring untested (d1, h, i). Add one test per panel driving `render()` / the clip render with a fake
   `VideoWorker`: emit `trace_signal` then `error_signal`, assert one `partial` row.
2. **P1 (owner)** 65,536 thinking stand-in for Kimi/Qwen (see code review P1-1).
3. **P2** Cut-off notices never executed for Creator, Author publishing/marketing, Manuscript Ask, Fiverr delivery/gig, Music.
4. **P2** Live line, Cost Estimate popup and `_assessment_text` "up to" wording never executed.
5. **P3** The messages AST check looks only for the keyword; a wrong list (`messages[:1]`) would pass.
6. **P3** Weak checks listed in §3.
7. **P3** Live line builds messages on every keystroke without the try/except `send_prompt` uses (`main.py:546` vs `:3563`).
8. **P3** A model with no price shows "Up to €0.00" (B-F5, non-goal).
9. **P3, pre-existing** The suite writes Saved Chats into `data/chats/` and rewrites `data/model_watch.json` (gitignored).
