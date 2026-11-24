# Spec: provider watermark on, prompt check on every image and video route

Needs: build, review, verify, secure, docs

Status: Define approved by the owner 2026-11-24 ("Yes, as recommended": D1 always on, D2 a TODO). Priority: P1
(Comply `docs/audit/release-2026-11-legal-compliance.md` R-P1-3 and R-P1-4; legal audit L-03,
L-04). Type: safeguard. Owner session: `claude/happy-dubinsky-48c27c`. The owner chose
"Start it" on 2026-11-24.

## Problem
Two findings with an EU AI Act date of 2 Dec 2026 (dates from secondary sources; primary text
not verified; whether they bind the owner is lawyer triggers T1 and T5, not this spec):
- **Marking (Art. 50(2)).** Imprint asks Alibaba to *remove* its watermark on both DashScope
  calls: Qwen Image (`services/image_generation.py:150`) and Wan video
  (`services/qwen_client.py:493`, `"watermark": False`). Nothing else marks output.
- **Intimate images of real people (new Art. 5 prohibition).** Only the Higgsfield route checks a
  prompt before sending (`services/higgsfield_client.py:152` `check_prompt`, called at `:329` and
  `agents/creator/panel.py:1121`). Unchecked: the creator teaser on Wan or Gemini Omni with a
  person's reference photos (`agents/creator/panel.py:1217`, request at `:1253`), the Video workspace's direct video
  (`agents/video/panel.py:626`), and every image (`services/image_generation.generate_image`,
  used by `ui/workers.py:284`, `vidforge/vidforge/visuals.py:54`, the Fiverr panel).

## Scope
1. **Watermark on.** Both DashScope calls send `"watermark": True`. No setting (D1).
2. **One prompt check for all routes.** Move the refusal patterns out of
   `higgsfield_client.py` into `services/content_policy.py` (`check_prompt`, `ContentPolicyError`),
   worded for any provider. Higgsfield keeps calling it (and its own reference-file check), so
   its behaviour does not change.
3. **Checked before anything is spent.** The creator teaser (all routes) and the Video workspace
   call it before `authorize_request`; a refusal shows the reason and sends nothing.
4. **Backstop where the request leaves.** `generate_image` and `VideoGenerationWorker.run` call
   it too, so a route added later, or vidforge and Fiverr images, cannot skip it.

## Out of scope
- New refusal words. The list stays deliberately narrow (`higgsfield_client.py:71-74`); widening
  it is a separate decision.
- Requiring a consent record before a person's reference photos are sent (the accounts table has
  consent columns, `services/database.py:253-256`). Recorded as a TODO for the owner (D2).
- Marking in files Imprint writes itself (M4B metadata, Shorts, release kit): T1 decides first.
- Higgsfield, OpenAI and Gemini marking: their own (C2PA, SynthID); not verified here.

## Design
Refusal, same dialog pattern as Higgsfield's today: title "Content policy", text = the reason, e.g.
"Sexually explicit material and identity manipulation of real people are not generated. Generate
safe-for-work material only." Negations keep working ("no nudity" passes). Status line: "Not sent:
content policy." Nothing is billed, no job row is written.

Generated Qwen images and Wan videos now carry Alibaba's visible watermark. README *Video and
image* (§5) and *7.9 Reel* say so.

## Architect
No state, threads or boundaries change: one pure module (stdlib `re`), called from the UI thread
before the request (cheap, no I/O) and from the worker thread as a backstop (raises; the worker's
existing error path reports it). `services/content_policy.py` is Imprint-only (Sentinel has no
image routes; no drift copy).

## Success measures
- S1 Both DashScope payloads carry `"watermark": True` (unit tests on the sent JSON).
- S2 Each of the five entry points (Higgsfield, teaser Wan, teaser Omni, Video workspace, image)
  refuses "a nude photo of my neighbour" before `authorize_request` or the HTTP call (tests with
  fakes), and passes "no nudity, a calm beach".
- S3 Existing Higgsfield tests pass unchanged.
- S4 New logic mutation-checked; full suite green.

## Review fixes (2026-11-24, after Review, Verify and Secure of 9a1d8e5)
All three reports found the same P1s; fixed without widening the word list:
- vidforge's OpenAI scene images skipped the check: `_generate_ai` now checks every scene prompt
  before either route; the narrated-video topic (`VideoPanel.render`), the Herald clip topic and
  Vector's logo-image prompt are checked before anything is reserved (Scope 3 extended to them).
- `tests/test_media_generation.py` expected `"watermark": False`: now `True` (follows D1).
- README and CHANGELOG said more than the code did: reworded.
- The existing words now match their own forms ("nudes", "undressed", "face-swap"); text is
  NFKC-folded with invisible characters dropped; a negation counts only directly before the word
  (one filler allowed). Higgsfield refusals in the Video workspace keep Higgsfield's wording; the
  creator teaser refusal sets "Not sent: content policy."
Left for later (TODO P3): refused LLM-written scene prompts still counted in spend; creator backstop
row status; look-alike letters and other languages.

## Owner decisions (Define gate)
- **D1 Watermark:** always on (recommended; a setting lets it be switched off again) or a
  default-on setting.
- **D2 Consent for reference photos:** TODO for later (recommended) or in this spec (adds a
  check against the account's consent fields; about +1 h).
