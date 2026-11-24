# Spec: Local model routing (retroactive record)

Needs: review, verify, secure, docs

Status: Retroactive record written 2026-11-24 for a feature built 2026-10-19 to 2026-10-21 and merged without a spec. Define was not run at the time; the owner's freeze exception for phases 0-4 is recorded in TODO.md (commit 1d481e3). Owner session: claude/happy-dubinsky-48c27c.

This file describes what the code does today on `claude/happy-dubinsky-48c27c` (after `2d427e2`). It is a
reference for Review, Verify, Comply and Release. It asks for no new work. Line numbers are from that tree.

## Problem (why it was built)
The owner runs local models in LM Studio (DeepSeek R1 distills, Dolphin) on this Mac. Imprint could not use
them, so every job that a free local model could do went to a paid cloud model. The plan's audit
(`docs/local_model_routing_plan.html` in the lab root, §1, 2026-10-19) names three blockers:
- "Ollama is the only local provider, and its address is hardcoded."
- "Imprint compares the provider name to the string `"ollama"` in roughly 20 places", so a second local
  runtime "would be priced as unknown and treated as a paid cloud call".
- "Local models are never rated, and an unrated model can never beat a rated one."
It also found a deadline: `gpt-4o-mini-tts` was still the default narration model, and OpenAI removes it on
2027-01-06 (plan §1, table).

## What was built
**Phase 0 (`d4d39c1`): narration retirement and one price source.** The OpenAI narration route carries the
retirement date 2027-01-06 in the converter and in Booth; the default route is the first one not yet retired;
a new job without a route gets the current default. `config/pricing.json` is the one price source; the code
fallback is `database.SEED_FALLBACK_PRICES` (TODO.md:157). The plan's other phase 0 items name Sentinel code
(plan §1 table, §5).

**Phase 1 (`0c0efcb`, `96a51dd`): provider registry and LM Studio.**
- `services/providers.py`: one `ProviderSpec` per provider (`:46`); `is_local` (`:95`) replaces the
  `== "ollama"` checks; `expand_allowed` (`:110`) lets an agent that allows one local runtime use all of them.
- Default addresses are loopback: `http://127.0.0.1:11434` and `http://localhost:1234/v1` (`:41-42`).
  `OLLAMA_HOST` and `LMSTUDIO_URL` override them (`:124`, `:145`).
- A local provider is priced €0, scored private, needs no permission tick and opens no paid-request dialog;
  a zero price for a cloud model still means unknown (README §6.2.1, `README.md:891`).
- `services/lmstudio_client.py`: model list from `/api/v0/models` (`:200`), disk scan of `~/.lmstudio/models`
  when the server is off (`:57`), `lms server start` (`:251`), and the real port from `lms server status` (`:142`).
- Memory fit check: file size × 1.2 against free memory (`providers.fit_check`, `:214`).
- Uncensored and abliterated models get an amber tag derived from name and publisher (`uncensored_tag`, `:183`).
- `run_backend` dispatches by provider spec (`main.py:5798`). ADR `docs/adr/0002-provider-registry.md`
  (its heading says "ADR 0001"; status "proposed").

**Phase 2 (`74436b4`): picker and Settings → Local models.** `services/local_models.py` caches discovery from a
background worker (`discover`, `:152`; `LocalInventory`, `:214`). The picker shows sections "On this Mac · LM
Studio" and "On this Mac · Ollama" (`:34-35`) with state, size, rating and €0 per row. A local model is a BEST
FIT candidate whichever provider is selected. New page `ui/local_models_page.py` with status, free RAM, table
and Start server (TODO.md:155). Follow-up on 2026-10-21: the budget-cap local fallback offers LM Studio or
Ollama models from the cached inventory (TODO.md:156).

**Phase 3 (`95747d3`): local ratings.** `services/local_ratings.py`, ADR `docs/adr/0003-local-model-ratings.md`
(status "proposed").
- Inherited: an unmodified build of a model LMArena rates takes that rating minus 0, 10 or 25 for its quant
  (`:89-91`). Modified builds inherit nothing.
- Measured: 80 fixed prompts, 20 each of writing, code, summarising, extraction (`:71`;
  `config/local_rating_prompts.json`). The best-rated cloud model answers too; the cheapest priced cloud model
  judges each pair in both orders. The result is placed below the reference rating, never above it.
- A new model is measured once, automatically (`AUTOMATIC = True`, `:56`; `main.py:1188-1198`). Re-measure is
  manual. A refused run leaves the model unrated with a Measure button (`main.py:1331-1336`).

**Phase 4 (`45fb54a`): hybrid routing.** `services/routing_advisor.py`, `ui/routing_advice.py`,
`ui/routing_page.py`; ADR `docs/adr/0004-hybrid-routing.md` (status "accepted").
- Five modes with labels and hints (`routing_advisor.py:58-89`), one app setting plus an override per agent in
  Settings → Models.
- One check per new Kernel job: run as selected, or hold the job and suggest one model with named reasons
  (quality gap outside the 20-point band, `:106`; context; not runnable; unmeasured), cost and time.
- Answers: Switch for this job, Always for this kind (a rule in `data/routing_rules.json`, `main.py:142`),
  Keep local. A failed local run offers the next candidate; nothing is resent by itself.
- Savings tally in `data/routing_savings.json` (`main.py:143`), shown in the Spend rail.

**Panels (`44c6b18`, 2026-10-21).** Quill, Herald, Sitebuilder and Vector are advised through
`authorize_request` (`ui/panel_routing.py:36`). Nova is never advised (`:37`); Press offers no local provider;
media and per-unit requests are not advised (`:16-23`). An answer puts the chosen model in the panel's boxes
and re-runs the action (`:11-14`).

**Sync with Sentinel (`45f705d`).** `HYBRID_MODE = LOCAL_ADVISE` (`routing_advisor.py:68`): "Hybrid allowed" on
the Mode box maps to *Local, advise per job*. Brought into this branch by the merge `0cc1ad2`.

**Fixes of 2026-11-24.**
- `ba870c4` (review L-2): a verdict counts only if the whole reply is A, B or TIE (`local_ratings.py:602`); a
  kind needs 75% usable pairs (`MIN_USABLE_SHARE`, `:599`) or stays unrated.
- `e57644a` (reviews L-1, L-3, security P1-1): `_route_allowed` (`main.py:4041-4084`) runs in
  `authorize_request` (`:4688`) and in Kernel's `_send_chat` (`:4417`). Under Local only it refuses every cloud
  provider, for every agent. A local runtime whose address is not this Mac is refused under Local only and
  otherwise asked about once per address (`:4059-4084`). Measurement calls carry caps of 1,024 and 512 tokens
  (`main.py:135-136`), are billed from the provider's usage (`:1370-1376`, `:1387-1395`), and their ceiling is
  held against the caps for the run (`:1234-1255`, `:1339`). No measurement starts under Local only (`:1259-1261`).
- `2d427e2` (recheck RC-2 to RC-7, RC-12): a remote runtime is not measured without asking (`:1262-1269`);
  moving the Mode box to Local only stops a running measurement (`:4104`); a recommendation no longer sets
  Local only (`:4105-4113`); a late finish cannot clear the next run's reserve (`:1406-1411`); usage is read, not
  taken, by the bill (`:1393-1395`).

## Owner decisions on record
1. Default mode. Plan §7.1: "Decided 19 Oct 2026: Local, advise per job." Confirmed again in Sentinel's
   `CHANGELOG.md:17`: "owner decision 2026-11-23, reversing the same day's testing-readiness H4 change to
   Local only"; the shared code says the same (`services/routing_advisor.py:21`).
2. When to measure. Plan §7.2: "Decided 19 Oct 2026: a new local model is measured automatically when it first
   appears. The judge calls go through each app's spend guard, Imprint's request guard included. If the guard
   refuses, the model stays unrated and shows a Measure button. A model is measured once; Re-measure is manual."
   TODO.md:65 after the L-1 fix: "Still automatic, as decided 2026-10-19."
3. Uncensored models. Plan §7.3: "Decided 19 Oct 2026: offered everywhere, always tagged uncensored or
   abliterated." Plan §2: "They are offered in every agent of both apps (owner's decision, 19 Oct 2026)." In
   Imprint, Press and Nova offer no local provider at all (`README.md:891`).
4. Freeze exception. TODO.md:165-168: "**Exception, 2026-10-21 (owner):** local-model routing phases 0–4
   (`d4d39c1` … `45fb54a`, merged to `main` in `87f5fed`) are kept on `main` even though they landed during the
   freeze."
5. Panels. TODO.md:58: "Routing advisor for the other text agents (2026-10-21, owner-directed despite the
   freeze)."
6. Never auto-switch. ADR 0004 (status "accepted (owner decisions of 19 Oct 2026 in
   `docs/local_model_routing_plan.html`)"): "The agent's provider/model selection is never changed by the
   advisor, a rule or Local first".

No owner gate is recorded for ADR 0002 or 0003 (both "proposed"), and `docs/foundry/approvals.jsonl` has no row
for this change.

## Success measures
Each is a statement a test checks today. "No test" means none was found.
1. LM Studio is local everywhere: €0, private, no permission tick, no paid dialog; no `== "ollama"` comparison
   is left. `tests/test_routing_phase1.py:38`, `:116`, `:185`; `tests/test_providers_registry.py:31`.
2. A zero cloud price stays unknown, never free. `tests/test_routing_phase1.py:90`;
   `tests/test_routing_phase3.py:137`; `tests/test_settings_pricing.py:51`.
3. Local providers have no key and the client talks only to its configured address.
   `tests/test_providers_registry.py:39`, `:378`.
4. `OLLAMA_HOST` and `LMSTUDIO_URL` are honoured; a pinned address is never rewritten.
   `tests/test_providers_registry.py:70`, `:76`, `:82`, `:418`.
5. LM Studio discovery works with the server on and off, lists MLX models and skips vision projectors.
   `tests/test_providers_registry.py:256`, `:276`, `:390`, `:457`.
6. The fit check uses × 1.2 against free and total memory. `tests/test_providers_registry.py:156`, `:166`.
7. Known uncensored and abliterated names and publishers are tagged; ordinary models are not.
   `tests/test_providers_registry.py:103-146`; `tests/test_routing_phase1.py:222`.
8. The picker and the advisor read caches and never fetch. `tests/test_routing_phase2.py:119`, `:237`;
   `tests/test_routing_phase4.py:337`.
9. A local model is a BEST FIT candidate whatever provider is selected. `tests/test_routing_phase2.py:218`.
10. An unrated local model never wins; a rated one inside the band wins on price.
    `tests/test_routing_phase1.py:70`, `:81`; `tests/test_routing_phase3.py:78`, `:106`, `:114`.
11. Inherited rating is base minus 0/10/25; modified builds inherit nothing. `tests/test_local_ratings.py:28`,
    `:86`, `:91`.
12. A measured rating is never above its reference. `tests/test_local_ratings.py:125`.
13. A judge with no usable verdicts rates nothing; a kind under 75% usable pairs stays unrated; an empty
    reference answer is neither judged nor cached. `tests/test_local_ratings.py:253`, `:269`, `:281`.
14. A new model is measured once, automatically; a refusal leaves it unrated with a Measure button.
    `tests/test_routing_phase3.py:234`, `:265`.
15. Measurement calls carry an output cap and keep their usage; the ceiling is priced on the caps and held for
    the run; a late finish does not release the next run's reserve. `tests/test_routing_phase3.py:357`, `:392`, `:413`.
16. Under Local only nothing is sent to the cloud: every agent, per-unit requests, a failing advisor, the box
    over an agent's own mode, Kernel, and measuring. `tests/test_local_only_guard.py:73`, `:82`, `:89`, `:98`,
    `:147`, `:169`; `tests/test_routing_phase3.py:424`.
17. A runtime on another machine is refused under Local only, asked about once otherwise, and not measured
    without asking. `tests/test_local_only_guard.py:125`, `:139`, `:177`; `tests/test_routing_phase3.py:439`.
18. The advisor names each limit, keeps the 20-point band, and suggests an unmeasured model without urging.
    `tests/test_routing_advisor.py:45`, `:54`, `:59`, `:75`, `:83`.
19. A paid model runs only through the paid-request dialog; declining sends nothing.
    `tests/test_routing_phase4.py:181`, `:190`; `tests/test_routing_panels.py:72`, `:80`;
    `tests/test_routing_advisor.py:226`.
20. An Always rule is per agent and kind, listed, removable, and never overrides Local only.
    `tests/test_routing_advisor.py:243`, `:250`, `:258`; `tests/test_routing_phase4.py:234`.
21. A failed run offers and never sends; a stopped run offers nothing; Local only never falls back to the
    cloud. `tests/test_routing_advisor.py:304`, `:315`; `tests/test_routing_phase4.py:291`, `:329`;
    `tests/test_routing_panels.py:126`, `:137`.
22. The default mode is Local, advise per job; a saved mode is never overwritten; a recommendation never sets
    Local only. `tests/test_routing_advisor.py:116`, `:122`; `tests/test_routing_phase4.py:257`;
    `tests/test_routing_phase3.py:448`.
23. Only Quill, Herald, Sitebuilder and Vector are advised; Nova, Press and media never.
    `tests/test_routing_panels.py:157`, `:165`, `:171`.
24. The OpenAI narration route leaves the menu on 2027-01-06 and the default moves.
    `tests/test_narration_route_retirement.py`.
25. The shared files equal Sentinel's. `tests/test_providers_drift.py`; it skips outside the main checkout
    (TODO.md:73).
26. After "Switch for this job" the agent's selection is unchanged (ADR 0004). No test; review L-4 found the
    panels keep the switched model, and L-20 notes no test reads the boxes.
27. The tag shows wherever a model is named (plan §2). No test; review L-12 lists texts without it.
28. "Saved" is what the cloud run would have cost. No test with real prices (review L-6, L-20).
29. The advisor works against a live LM Studio model. No test; manual row TODO.md:149.

## Known gaps
Open P2 and P3 rows in `TODO.md`, in its words:
- P2 design (TODO.md:68, RC-6): "A local runtime on another machine is still labelled "On this Mac"."
- P3 design (TODO.md:69, RC-9): "Under Local only, the four advised panels show a plain refusal instead of
  naming the local model that could do the job."
- P3 docs (TODO.md:70, RC-10): "Texts still describe the old mode precedence, and the Mode box's Cloud only
  still loses to an agent's own mode."
- P3 bug (TODO.md:71, RC-11): "A failed re-measure says "stays unrated" while an older score for that kind
  stays on screen."
- P3 bug (TODO.md:72, RC-13): "A thinking judge can spend its 512-token verdict cap and answer nothing."
- P2 testing (TODO.md:73, L-10): "The Sentinel drift tests skip silently in every worktree and, as far as
  seen, in CI."
- P3 infra (TODO.md:76): "12 ruff findings sit in files copied byte-for-byte to Sentinel or Lab Hub".
- P2 bug (TODO.md:134, QM-1): "Automatic local-model measurement makes paid cloud calls without a
  confirmation, and its ceiling is not reserved in flight." (The ceiling part changed in `e57644a`; the
  automatic start stands by decision 2.)
- P3 feature (TODO.md:150): "Show a dot on an agent's rail entry while it holds a job on the advice banner
  (SUGGESTIONS #74)."
- P3 testing (TODO.md:151): "Stabilise `tests/test_routing_phase3.py::test_closing_the_window_cancels_a_running_measurement`".
- P2 testing (TODO.md:153): "Verify an MLX model end to end through LM Studio".
- P2 security (TODO.md:422): "The shared LM Studio client's other calls still honour proxy settings".

Also open, for Release: the P1 rows TODO.md:64-67 read "Fixed 2026-11-24 … re-review pending"; the recheck
(`docs/audit/local-model-routing-code-reviewer-recheck.md`) and `2d427e2` have since run. TODO.md:149 (P1, live
test by the owner) is open. Review findings with no `TODO.md` row, status not re-checked here: L-4 to L-9,
L-12 to L-20; security P2-3, P3-1, P3-3 to P3-6; recheck RC-1 (Sentinel's own test).

## Shared code
`tests/test_providers_drift.py:30-35` holds these byte-identical with Sentinel, with no allowed differences
(`:16-17`): `services/providers.py`, `services/lmstudio_client.py`, `services/local_models.py`,
`services/local_ratings.py`, `config/local_rating_prompts.json`, `tests/test_local_ratings.py`,
`ui/local_models_page.py`, `services/routing_advisor.py`, `tests/test_routing_advisor.py`,
`ui/routing_advice.py`, `ui/routing_page.py`.
Rule: a change to any of them lands in both repositories in one session (lab `AGENTS.md`, "Copied code
changes everywhere in one session"; test docstring `:16`: "port the change to both copies"). Imprint-only:
`main.py`, `ui/panel_routing.py`, `services/local_endpoint.py`, `services/ollama_client.py`.

## Out of scope
- New routing work of any kind; this record proposes none.
- Advising Nova, Press, Booth, video, images or any per-unit request (`ui/panel_routing.py:16-23`).
- Context limits for cloud candidates, which carry no window (ADR 0004; SUGGESTIONS #73).
- Calibrating the judge (SUGGESTIONS #69) and measuring the *analysis* tag (#68) (ADR 0003).
- Sentinel's own code beyond the shared files.
- EU AI Act Art. 50: the feature chooses where a request runs; it publishes nothing and adds no conversation
  with a third party.
