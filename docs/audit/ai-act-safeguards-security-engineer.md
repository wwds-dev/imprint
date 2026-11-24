# Secure: ai-act-safeguards (security-engineer)

Spec: `docs/specs/ai-act-safeguards.md`. Commit reviewed: `9a1d8e5` on `claude/happy-dubinsky-48c27c`.
Date: 2026-11-24. Read-only review; no code changed. Playbook `docs/playbooks/security-engineer.md`
last-reviewed 2026-11-11, status current (not stale).

This report describes what the code does and does not do. It is not a legal opinion. Whether this
amounts to "adequate technical safeguards" under AI Act Art. 5 is lawyer trigger T5's question.

## Threat model (this change only)

- **Assets:** photos of a real person (an account's reference images); the user's API keys and
  provider accounts (a ban risk); the owner's AI Act position (marking, Art. 50(2); intimate images
  of real people, Art. 5).
- **Trust boundaries:** user text (Topic field, creator brief, persona appearance, Fiverr brief) ->
  local check -> provider API (Alibaba DashScope, Google Gemini, Higgsfield, OpenAI). LLM output
  (the Fiverr image prompt, vidforge `visual_prompt`s) is untrusted input of the same kind.
- **Entry points that generate media:**
  | Route | Prompt source | Reference photos | Check before `authorize_request` | Check at send |
  |---|---|---|---|---|
  | Creator teaser, Higgsfield | `build_video_prompt` (brief + appearance) | 1 | yes (`agents/creator/panel.py:1121`) | yes (`services/higgsfield_client.py:297`, before the upload at `:320`) |
  | Creator teaser, Wan / Omni | same | up to 10 (Wan) / 3 (Omni) | yes (`agents/creator/panel.py:1241`) | yes (`ui/workers.py:403`) |
  | Video workspace, direct (Gemini, Wan, Higgsfield) | Topic, sent verbatim | none | yes (`agents/video/panel.py:611`) | yes (worker; Higgsfield `prepare_video`) |
  | Fiverr logos (any image model) | LLM-written from the brief | none | **no** | yes (`services/image_generation.py:81`) |
  | Video workspace scenes / Herald clips, Gemini or Qwen image | LLM-written `visual_prompt` | none | **no** | yes (`generate_image`) |
  | Video workspace scenes / Herald clips, OpenAI image (the default) | LLM-written `visual_prompt` | none | **no** | **no** (`vidforge/vidforge/visuals.py:75`) |

## Findings

### P0
None.

### P1

**P1-1. vidforge's OpenAI image path skips the content check entirely.**
`vidforge/vidforge/visuals.py:57-75`: `_generate_ai` sends only Gemini and Qwen models through
`services.image_generation.generate_image`; an OpenAI model (the default, `gpt-image-2.5-flare`,
`vidforge/config.yaml:37`) goes straight to `_openai().images.generate(prompt=full)` with no call to
`services/content_policy`. Neither entry point checks the topic first: `VideoPanel.render`
(`agents/video/panel.py:508-533`, topic may even be "next topic from topics.txt") and the Herald clip
(`agents/social/panel.py:638`) both go to `authorize_request` without `refusal()`.
- Scenario: Topic "<a named public figure> undressed in a hotel room" -> the script LLM writes
  per-scene `visual_prompt`s -> each is sent to OpenAI unchecked. Text-to-image only (no reference
  photos), and OpenAI applies its own moderation (not verified here), so the exposure is lower than
  the teaser's. But it is spec scope item 4 ("vidforge and Fiverr images cannot skip it") not met.
  `services/image_generation.py:74-78`, README line 2330 and the CHANGELOG entry say every image
  route, vidforge included, is checked: that statement is false for the default model, and it is
  the statement a T5 reviewer would rely on.
- Fix: call `content_policy.check_prompt(full)` at the top of `_generate_ai` (import guarded, as
  `_other_provider_image` already does for standalone vidforge), or route OpenAI scenes through
  `generate_image` too; check the topic with `refusal()` in `VideoPanel.render` and the Herald clip
  flow before `authorize_request`; add a test with a fake OpenAI client.

**P1-2. Ordinary inflections of the listed terms pass, including the ones the refusal text names.**
`services/content_policy.py:23-30`: every term is bounded by `\b...\b` with no inflection. Probed
with the module as committed (script run against this worktree):
`"nudes of my neighbour"`, `"my neighbour undressed"`, `"undressing my neighbour"`,
`"deepfakes of a senator"`, `"face-swap my neighbour onto this"`, `"face  swap"` (two spaces),
`"porno scene"` all return `None` (sent). The identity reason itself says Imprint does not generate
"deepfakes, face swaps or undressed images of real people", yet "deepfakes" and "undressed" pass.
- Scenario: creator brief "my neighbour undressed on the beach" with the account's reference photos
  -> passes the check -> photos and prompt go to Wan or Gemini Omni. This is the exact Art. 5 case
  the spec targets, written in plain English with no evasion trick.
- Fix (not new words, the same words inflected): `nudes?`, `undress\w*`, `deepfakes?`,
  `face[\s_-]*swap\w*`, `faceswap\w*`, `porn\w*`, `deep[\s_-]*nudes?`; collapse runs of whitespace
  before matching; extend the parametrised test in `tests/test_content_policy.py:42`.

### P2

**P2-1. The negation rule is easy to trigger by accident or on purpose.**
`services/content_policy.py:53-66`: a match counts as negated when any negation word is among the
three words before it (same clause, 24-character window). Probed: `"a never seen before nude
portrait"`, `"nothing hidden nude woman"`, `"she is not shy and naked"` all pass. Fix: treat a match
as negated only when the negator directly governs it (`no|without|free of|avoid` immediately
before the term, optionally one adjective between), and add these strings as refused cases.

**P2-2. Unicode and spelling tricks pass (residual by design, partly cheap to close).**
`services/content_policy.py:70` only lowercases. All of these return `None`: fullwidth
`ｎｕｄｅ`, `nu<U+200D>de` (zero-width joiner), `na<U+200B>ked` (zero-width space), `nu<U+00AD>de`
(soft hyphen), Cyrillic `е`/`а` homoglyphs, `n u d e`, `n.u.d.e`, `nud3`, `nude_photo`
(underscore is a word character, so `\b` fails), and non-English (`nacktes Foto`). The spec keeps
the list narrow and rules out a classifier; still, `unicodedata.normalize("NFKC", ...)` plus
removing format characters (category `Cf`) and treating `_` as a separator closes the fullwidth,
zero-width, soft-hyphen and underscore cases at no false-positive cost. Homoglyphs, spacing,
leetspeak and other languages remain residual; whether provider models read the obfuscated forms as
the word was not tested.

**P2-3. The check reads the prompt only; reference photos are sent without any consent or content check.**
`agents/creator/panel.py:1257` (`reference_images(account["id"])`) -> `ui/workers.py:409-412` ->
`services/qwen_client.py:476-484` (up to `WAN_MAX_REFERENCES = 10`, base64) /
`services/gemini_client.py:328-334` (up to 3). Whose face is in the photos, whether that person
agreed, and what the images show are not checked; a benign prompt plus photos of anyone is sent.
The owner deferred this (D2; `TODO.md` P2 "Require a consent record ..."). Listed so the T5 reviewer
sees it: the safeguard covers the words of a request, not the person in it.

**P2-4. "Reserves nothing" is not true on the backstop-only routes, and the user is not told on vidforge.**
README line 2330 says a refused prompt "reserves nothing and sends nothing" for "every generated
image (Fiverr concepts, video visuals)". Fiverr checks only inside `FiverrImageWorker`
(`ui/workers.py:286` via `generate_image`), after `authorize_request` and after the paid LLM call
that wrote the prompt; it then opens an order and records "logos requested"
(`agents/fiverr/panel.py:531-537`) for a run that was refused. vidforge Gemini/Qwen scenes are
refused after the script and narration are paid for, and the refusal is swallowed: the scene
silently becomes a gradient card (`vidforge/vidforge/visuals.py:200-205`), the reason is only in the
render log. Nothing reaches the image provider in either case (fails closed for the send), but the
public text overstates it. Fix: check the LLM-written prompt in the panel before the image
`authorize_request` (Fiverr `_on_prompt_ready`, `agents/fiverr/panel.py:445`), and correct README
and CHANGELOG to match.

**P2-5. A test still asserts `"watermark": False`; the suite is red.**
`tests/test_media_generation.py:162-187` (`test_wan_create_uses_async_task_endpoint_and_no_watermark`)
was not updated. Ran only that file and `tests/test_content_policy.py`:
`1 failed, 35 passed` — `{'watermark': True} != {'watermark': False}`. Success measure S4 ("full
suite green") is not met by this commit. Fix: update the assertion (and the test name) to `True`;
it then doubles as a second S1 guard.

### P3

**P3-1. DashScope rewrites the prompt server-side.** Both DashScope payloads send
`"prompt_extend": True` (`services/image_generation.py:159`, `services/qwen_client.py:492`): Alibaba
expands the prompt with its own model before rendering, so the text the model renders from is not
the text Imprint checked. Provider-side moderation was not verified. Informational for T5.

**P3-2. vidforge's style suffix asks every scene image for "no watermark".**
`vidforge/config.yaml:40-42` appends "no text, no watermark, no logos" to each scene prompt,
including Qwen image scenes. It is a text instruction to the image model (meant to avoid stock-photo
marks) and almost certainly does not remove Alibaba's post-generation mark (not verified), but it
reads against D1. Consider rewording to "no stock-photo watermark" or dropping the word.

**P3-3. Higgsfield still uploads the reference photo before the user approves the price.**
Pre-existing, not introduced here: `prepare_video` uploads at `services/higgsfield_client.py:320`
during the estimate, before `authorize_request` (`agents/creator/panel.py:1190`). The prompt check
does run first (`:297`), so a refused prompt uploads nothing. Noted because the photo leaves the Mac
before the user's approval step.

## Verified as asked

- **Watermark.** `services/image_generation.py:159` (Qwen Image) and `services/qwen_client.py:495`
  (Wan) send `"watermark": True`. `grep -i watermark` over all non-test source (excluding `.venv`,
  `build`, `dist`) finds no other parameter; vidforge reaches DashScope only through
  `generate_image`. No setting can switch it off. `tests/test_content_policy.py:74,89` pin both
  payloads.
- **Checked text = sent text.** Creator teaser: the check runs on `build_video_prompt`'s full output
  (brief and persona appearance included), the same string passed to the worker. Wan
  (`qwen_client.py:476-484`) and Omni (`gemini_client.py:323-333`) append fixed, benign sentences
  after the checked prompt; the negation rule only looks backwards, so the additions cannot mask a
  term. The template's own "nothing explicit" comes after the brief and does not mask it (probed:
  a template with "nude" in the brief is refused). Video workspace: Topic is sent verbatim.
  Higgsfield: `prepare_video` puts the checked prompt in the payload unchanged.
- **Every route that sends a person's reference photos runs the prompt check before the photo
  leaves**: Higgsfield (`:297` before upload at `:320`), Wan and Omni (panel `:1241`, worker
  `:403`). No route sends reference photos unchecked. Routes without the check are text-to-image
  only (P1-1).
- **New data written, logged or sent.** The refusal texts are constants with no user data. New code
  logs nothing and stores no prompt; panel-level refusals happen before `authorize_request`, so no
  request row or job row is written. The worker backstop emits `"Not sent: <constant>"`. Exceptions:
  the Fiverr order event (P2-4) and the vidforge render log line, which includes the exception text
  (the constant reason). No secrets are touched.
- **Dependencies.** No new dependency (stdlib `re` only).

## Not verified

- Full suite (not run, by instruction); only `tests/test_media_generation.py` and
  `tests/test_content_policy.py` were run, using the main checkout's `.venv` against this worktree.
- `pip-audit` / OSV on the installed set: not run (not installed in the venv; no dependency changed).
  CI `security.yml` runs it, non-blocking.
- Provider-side moderation (OpenAI, Gemini, Alibaba, Higgsfield), how DashScope's `prompt_extend`
  behaves, and whether Alibaba's mark is visible, invisible or C2PA.
- Whether provider models interpret fullwidth, zero-width or homoglyph text as the hidden word.
- Live UI behaviour (no app launched); the Herald and Video-scene paths were traced in code only.
- Legal adequacy under AI Act Art. 5 and Art. 50(2): lawyer triggers T1 and T5.
