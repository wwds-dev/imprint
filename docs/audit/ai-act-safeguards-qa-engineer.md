# Verify: ai-act-safeguards (qa-engineer)

- Spec: `docs/specs/ai-act-safeguards.md`. Commit verified: `9a1d8e5`. Date: 2026-11-24.
- Playbook `docs/playbooks/qa-engineer.md`: `status: current`, `last-reviewed: 2026-10-14` (41 days, not stale).
- Method: read-only on the live tree. All runs and mutants in a scratch copy
  (`git archive 9a1d8e5 | tar -x -C /private/tmp/claude-501/qa-aias-43279`), with the app venv,
  `-p no:randomly` for mutants. Full suite **not** run (in progress elsewhere, per instruction);
  11 related test files run instead. A QA-only pytest plugin blocked every non-loopback socket
  and DNS lookup and traced line coverage of the changed files.

## Verdict: FAIL

Two P1s: the commit leaves an existing test red, and the default vidforge image route (OpenAI)
skips the prompt check the spec says every image route runs.

## Success measures

| | Verdict | Evidence |
|---|---|---|
| S1 watermark on both DashScope payloads | **met** | `test_content_policy.py::test_qwen_image_asks_for_the_watermark` and `::test_wan_video_asks_for_the_watermark` capture the sent JSON and assert `parameters["watermark"] is True`. But an older test still expects `False` (see S4). |
| S2 five entry points refuse the S2 prompt before reserving or sending; negated prompt passes | **weak** | Teaser Wan and Omni, Video workspace (Gemini, Qwen, Higgsfield) and `generate_image` are met (below). Higgsfield is covered only at client level, and with a different prompt. The vidforge OpenAI image route is unchecked (P1-2). |
| S3 existing Higgsfield tests pass unchanged | **met** | `git show --stat 9a1d8e5` changes only `tests/test_content_policy.py` under `tests/`. `test_creator_agent.py` and `test_higgsfield_client.py` pass. |
| S4 mutation-checked; full suite green | **unmet** | `tests/test_media_generation.py::test_wan_create_uses_async_task_endpoint_and_no_watermark` fails at `9a1d8e5` (P1-1). My mutants: 6 of 8 killed (2 survivors, P2-1 and P2-2). |

### S2 per entry point (would the tests catch a regression?)

| Entry point | Test | Catches a regression? |
|---|---|---|
| Higgsfield | `test_creator_agent.py::test_a_refused_prompt_never_reaches_the_network` (`client.generate_video("explicit nude scene")` raises before `_client`); `test_content_policy.py::test_higgsfield_keeps_its_own_wording_on_the_shared_patterns`; Video workspace `[Higgsfield-seedance-2.5]` | Yes for the client and the Video workspace (mutants F and H killed). The creator panel's own Higgsfield check (`agents/creator/panel.py:1120-1124`) has no panel-level test, so moving or dropping it is caught only by the client backstop. The S2 prompt itself is not used on this route. |
| Creator teaser, Wan | `test_creator_direct_teaser_refuses_before_reserving[qwen]`: asserts `authorize_request` is not called, no job row, warning text | Yes |
| Creator teaser, Omni | same test, `[gemini]`; allowed prompt via `test_creator_direct_teaser_still_asks_for_an_allowed_prompt` (gemini only) | Yes (mutant G, "check only Wan", killed) |
| Video workspace direct video | `test_video_workspace_refuses_every_direct_route_before_reserving` x3: no `authorize_request`, no `_persist_submission`, warning and status line | Yes for refusal (mutant F killed). The allowed prompt is not exercised on this panel in the new tests. |
| Image generation | `test_generate_image_refuses_before_any_route` (provider routes and `provider_for` patched to raise) and `test_generate_image_lets_an_allowed_prompt_through` | Yes for `generate_image`, so Fiverr (`ui/workers.py:285`) and vidforge Gemini/Qwen images are covered. **Not** vidforge's OpenAI image route (P1-2). |
| Backstop `VideoGenerationWorker.run` | `test_video_worker_never_submits_a_refused_prompt` and `test_video_worker_submits_an_allowed_prompt` | Yes (mutant E, "emit but no return", killed) |

## Commands and output

```
$ pytest -q -p no:randomly -p qa_guard tests/test_content_policy.py tests/test_creator_agent.py \
    tests/test_higgsfield_client.py tests/test_image_routes.py tests/test_teaser_routes.py \
    tests/test_video_jobs.py tests/test_media_generation.py tests/test_reel_omni_stop.py \
    tests/test_vidforge_contract.py tests/test_fiverr_orders.py tests/test_herald_clip_provider.py
FAILED tests/test_media_generation.py::test_wan_create_uses_async_task_endpoint_and_no_watermark
1 failed, 168 passed, 1 warning in 41.68s

$ pytest -q tests/test_media_generation.py          # without the QA plugin: same failure
>       assert kwargs["json"]["parameters"] == {
E       AssertionError: assert {'resolution'...d': True, ...} == {'resolution'...d': True, ...}
tests/test_media_generation.py:185: AssertionError
1 failed, 9 passed

# new and Higgsfield tests, random order (pytest-randomly on), network blocked, run twice
QA network attempts blocked: 0 []
74 passed, 1 warning in 13.39s
QA network attempts blocked: 0 []
74 passed, 1 warning in 12.69s

# probe: vidforge._generate_ai with the default OpenAI model, OpenAI client faked
NOT REFUSED; prompt sent to OpenAI: ['a nude photo of my neighbour.']
```

## Mutation check (my own mutants, different from the author's)

The commit message says "9 of 9 mutants killed" but does not list them by file:line, which the
playbook asks for (P3-2). Each mutant below was applied in the scratch copy and restored
(confirmed byte-identical to `9a1d8e5` afterwards). Tests run: `test_content_policy`,
`test_creator_agent`, `test_higgsfield_client`, `test_teaser_routes`, `test_video_jobs`,
`test_image_routes`.

| # | File:line | Mutation | Result |
|---|---|---|---|
| A | `services/content_policy.py:70` | drop `.lower()` | **SURVIVED** (101 passed). `"A NUDE PHOTO OF MY NEIGHBOUR"` would be sent. |
| B | `services/content_policy.py:60` | clause split `[.;,]` to `[.;]` | **SURVIVED** (101 passed). `"no captions, nude model"` (refused today) would pass. |
| C | `services/content_policy.py:62` | negation window `words[-3:]` to `words[-1:]` | killed (`[a promo with not any nudity]`) |
| D | `services/content_policy.py:59` | char window 24 to 6 | killed (`[stylised promo, free of nudity, ...]`) |
| E | `ui/workers.py:406` | emit refusal, drop `return` | killed (`test_video_worker_never_submits_a_refused_prompt`) |
| F | `agents/video/panel.py:612` | skip the check for Higgsfield | killed (`[Higgsfield-seedance-2.5]`) |
| G | `agents/creator/panel.py:1242` | check only the Wan route | killed (`[gemini]`) |
| H | `services/higgsfield_client.py:129` | refuse only the `explicit` key | killed (`test_higgsfield_keeps_its_own_wording...`) |

Score: 6 of 8. Per the playbook, a survivor counts as a missing test, not a pass.

## Coverage of changed lines

`coverage`/`pytest-cov` are not installed in the venv, so I used line tracing with `sys.settrace`
in the QA plugin, over the 11 files above. Every changed executable line in
`services/content_policy.py`, `services/image_generation.py:80-81`, `ui/workers.py:402-406`,
`agents/creator/panel.py:1235-1244`, `agents/video/panel.py:610-615`,
`services/higgsfield_client.py:128-130` and the two watermark payloads ran. Both outcomes of
every new `if` ran: refused and allowed, and in `_is_negated` the word, phrase and
not-negated paths. Branch coverage of changed lines: 100% by line trace. That is not a
branch-coverage tool. Lines left unrun nearby are older code, not part of this change.

## Model calls (item 5)

- Unit tests: fakes only. Zero blocked network attempts over 169 tests, plus the two
  randomized runs above. No test needs a key, a network or a model server.
- Live eval: not applicable and not run. The change adds no model prompt; the check is a
  local regex. `docs/foundry/plan.toml` has no `eval_budget_usd`. Not verified live: whether
  DashScope actually applies a visible mark with `watermark: true` (README claim, P3-4).

## Gaps, ranked

- **P1-1 Suite red at `9a1d8e5`.** `tests/test_media_generation.py:162-187`
  (`test_wan_create_uses_async_task_endpoint_and_no_watermark`) still asserts
  `"watermark": False`. D1 changed this behaviour on purpose, so the fix is to update the
  test to the decided behaviour (name and value). That is not weakening the test. S4
  ("full suite green") is unmet until then. QA does not fix it.
- **P1-2 vidforge's default image route skips the check.** `vidforge/vidforge/visuals.py:52-80`
  sends OpenAI models (the default, `gpt-image-2.5-flare`, app-context "Models used")
  straight to `_openai().images.generate`, not through `generate_image`. This route is
  reached from the Video workspace's narrated video and from Herald's social clips
  (`agents/social/panel.py:670-696`). Spec scope 4 ("vidforge ... images cannot skip it") and
  the docstring at `services/image_generation.py:76-78` say otherwise. The probe above
  shows the S2 prompt reaching the (faked) OpenAI client. No test covers this route.
- **P2-1 Case is not pinned.** Mutant A survived because every refused prompt in the tests is
  lower case. Add an upper-case or mixed-case prompt to
  `test_unambiguous_prompts_are_refused_with_their_reason`.
- **P2-2 The clause rule is not pinned.** Mutant B survived. The case
  `"explicit shots, no captions"` (`tests/test_content_policy.py:40`) cannot exercise the rule
  its comment names, because the negation comes after the match. Add
  `"no captions, nude model"`, which should be refused.
- **P2-3 The creator panel's Higgsfield route has no panel test.** No test drives
  `CreatorPanel.generate_video` on the Higgsfield route with a refused prompt and asserts that
  no estimate worker or `authorize_request` runs (`agents/creator/panel.py:1120-1124`). The
  check is older code, unchanged by this commit, and is covered only by the client backstop.
- **P2-4 Narrated and clip pipelines check the topic late or never.** Spec scope 3 asks for a
  check before reserving only for the teaser and "the Video workspace". The vidforge pipeline
  (narrated video, Herald clips) reserves without checking the topic. Its images go through
  `generate_image` (Gemini and Qwen) or nothing (OpenAI, P1-2). Product question: should
  scope 3 cover these?
- **P3-1 One assertion cannot fail, and one path is untested.**
  `assert not worker.retryable and not worker.timed_out` (`tests/test_content_policy.py:162`)
  checks the initial values set at `ui/workers.py:380-381`. Nothing on the backstop path
  could make it fail. Separately, nothing tests that each panel releases the reservation and
  closes the job row when the worker emits "Not sent: ...".
- **P3-2 Author's mutants not recorded by file:line** (playbook "Mutation check").
- **P3-3 Allowed-prompt coverage is thin.** The allowed prompt is tested on the teaser for
  Omni only, and not on the Video workspace panel in the new tests.
- **P3-4 Watermark not checked live.** Not verified that DashScope applies a visible mark.

## Test quality notes

- Good: the panel tests patch `authorize_request`, `_persist_submission`, `_video_job_update`
  and `VideoGenerationWorker.start` to record or raise, so "nothing reserved" is asserted
  directly rather than inferred. `generate_image`'s refusal test makes every provider route
  and `provider_for` raise, so the check cannot move later without failing.
- No time or network dependence found. The `window` fixture swaps the `QMessageBox` static
  methods and restores them in `finally`.
