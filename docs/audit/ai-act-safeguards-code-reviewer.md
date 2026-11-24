# Code review: ai-act-safeguards (commit 9a1d8e5)

Reviewer: `code-reviewer`, independent of the author, read-only (saved to this file by the
orchestrator, verbatim in substance). Playbook `docs/playbooks/code-reviewer.md` last reviewed
2026-10-14, `status: current`.

Ran: `pytest -q -p no:randomly tests/test_content_policy.py tests/test_creator_agent.py
tests/test_teaser_routes.py tests/test_reel_omni_stop.py` → 65 passed; evasion prompts through
`content_policy.refused_key` (P2-1).

## P1

**P1-1. The default image route never runs the check: vidforge's OpenAI scene images.**
`vidforge/vidforge/visuals.py:52-54` routes to `generate_image` only when `provider_for(model)` is
not OpenAI; OpenAI models go straight to `_openai().images.generate(...)` (`visuals.py:75-81`).
Three of seven scene-image models are OpenAI, including the defaults (`gpt-image-2.5-flare`,
`vidforge/config.yaml:37`; `gpt-image-2`, `agents/social/panel.py:678,711`). The pipeline topic is
not checked at entry either (`agents/video/panel.py:525-538`; `agents/social/panel.py:660`).
Scenario: topic "a nude photo of my neighbour" in Video on the default model; every scene prompt
goes to OpenAI unchecked. Breaks spec Scope 4 and the docstring at
`services/image_generation.py:76-78`. Fix: `check_prompt` in `_generate_ai` before either branch;
check the topic in `VideoPanel.render` and the Social clip flow before `authorize_request`; a test
driving `_generate_ai` with an OpenAI model and a fake client.

**P1-2. `tests/test_media_generation.py:162,185-187` still expects `"watermark": False`.** The suite
is red (S4). Fix: expect `True`, rename the test (follows an approved spec change; not a weakening).

**P1-3. README and CHANGELOG claim more than the code does.** `README.md:2330-2334` and
`CHANGELOG.md:32-35` say every image is checked before anything is reserved and shows "Content
policy". False for vidforge OpenAI (P1-1); Fiverr and vidforge Gemini/Qwen only hit the backstop
after `authorize_request` (`agents/fiverr/panel.py:496-502`), and show "[Error] Concept 1 failed"
or a gradient card, not the dialog. Fix: pre-reservation checks (Fiverr `_on_prompt_ready`,
pipeline topic) or reword.

## P2

**P2-1. Negation too broad; inflected forms slip past.** `services/content_policy.py:62-63`: any of
the 3 preceding words negates. "no watermark nude photo of my neighbour", "zero blur naked photo",
"free of blur nude photo" pass; `\b` lets "undressed", "nudes", "face-swap" pass. Fix: negation only
directly before the match (optionally one article/adjective); inflected forms of existing words.

**P2-2. A refused vidforge scene is silent and still billed.** `visuals.py:200-205` catches the
error and draws a gradient card; `VideoPanel._on_done` (`agents/video/panel.py:876`) records the
full estimate. Fix: check the topic before reserving; count refused scenes as unbilled or fail.

**P2-3. Tests stop short of the money paths.** No test drives `_video_error`
(`agents/creator/panel.py:1486-1517`) or `_on_error` (`agents/video/panel.py:942-997`) with the
backstop error; no Fiverr or vidforge refusal test.

## P3

- **P3-1.** Creator direct-teaser refusal does not set "Not sent: content policy."
  (`agents/creator/panel.py:1241-1244`).
- **P3-2.** Video workspace Higgsfield refusals now show the generic wording, not Higgsfield's
  (`agents/video/panel.py:610-615`).
- **P3-3.** Creator backstop leaves the job row `status='submitted'`, `policy_result='local-approved'`
  (unreachable today).
- **P3-4.** Fiverr opens an order for a refused prompt (`agents/fiverr/panel.py:530-536`).
- **P3-5.** Watermark note is under "Higgsfield promo video" (`README.md:2314`), not §5 *Video and
  image* or §7.9 *Reel*.

## Checked and found correct
Higgsfield unchanged (patterns, negation, wording, reference check; same `ContentPolicyError`).
Video and creator backstops release the reservation and bill nothing; resume uses
`VideoResumeWorker`, so in-flight jobs are never refused afterwards. Fiverr refusal releases at €0.
`openai_client.generate_image` is called only from `image_generation.py:89`; `create_video` only
from `VideoGenerationWorker`; music, cover and brand panels make no image/video calls. No other code
reads the DashScope parameters. `content_policy` is pure and thread-safe.

## Not verified
Full suite; `test_media_generation.py` (P1-2 inferred); the author's 9-of-9 mutant claim; ruff
ratchet; whether Alibaba applies the watermark; OpenAI/Gemini marking; live providers.

**P0:** none. **P1:** P1-1, P1-2, P1-3.
