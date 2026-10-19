# Audit P1 fixes: Reddit subreddit and billing accuracy (2026-10-14)

Phase: Define, waiting for the owner gate. Sources: `docs/audit/SUMMARY.md` (P1 table), `docs/audit/security.md`
part 2 (B-F1 to B-F3) and "Outside this scope" (X-1); backlog: the four P1 lines at the top of TODO.md §v2. Feature
freeze (TODO.md §v2): every item here is a bug fix. Parts that would add features are listed under Non-goals.
Provider facts: `docs/company/radar-notes/2026-10-14-feature-billing.md`. Playbook `product-manager.md` is `status: baseline`.

## Problem
The single author/creator user is hurt in two ways.
- **Public post in the wrong place (X-1).** In `agents/social/publishing.py:151`, `lstrip("r/")` strips every leading
  `r` and `/`, so `rust` becomes `ust` and `r/rpg` becomes `pg` (the audit verified this). The post is public and in the
  user's name. `tests/test_social.py:378` only tests "books".
- **Budget caps that don't hold (B-F1 to B-F3).** Every paid call goes through the guard, but the cost it checks and
  the cost it records both run low, so the caps trip late or not at all.
  - B-F1: `services/gemini_client.py:185` and `:396` record only `candidates_token_count`. The installed
    google-genai 2.21.0 sums total = prompt + candidates + tool-use + thoughts, so thinking tokens are not in candidates,
    and Google bills them as output. Audit example: €0.0206 recorded, €0.1200 billed (×5.8). Cached tokens are not
    passed either, so cache hits are recorded at the full input rate.
  - B-F2: the estimate assumes `max(250, 1.2×input)` output tokens (`main.py:503-504`; router `:1507-1508`). The
    OpenAI, DeepSeek, Kimi, Qwen and Gemini clients send no output cap. Anthropic sends 8096. DeepSeek's own default
    is 8K, or 64K in thinking mode. Panels estimate from the user's prompt alone, not the system prompt and context
    they actually send (e.g. `agents/author/panel.py:1017-1035`). One request can overshoot what is left 30× or more.
  - B-F3: failed or stopped renders (`agents/video/panel.py:867-869`, Social clip `agents/social/panel.py:682-690`)
    and partial Fiverr batches (`agents/fiverr/panel.py:540-546`) call `abandon_request` and record €0. A default
    8-minute render that fails at assembly has already paid about €2.1, and €1.9 of that is its 35 images. A retry
    pays the full amount again while the caps stay where they were.

Evidence: code paths and offline reproductions. Live billing was not verified because there are no working keys
(TODO.md P1 `infra`).

## Target user and goal
The owner-user who sets session caps (default €1.00) and daily caps (default €5.00) (`main.py:305-306`) and will rely
on them in the PAID UAT pass. Goal: a Reddit post goes to the subreddit the user typed. Every amount the guard checks
or records on these paths is at least what the provider can bill, and is never more than the user confirmed.

## Success measures
All tests run offline: fake SDK clients and a stubbed `requests.post`, the temp DB, no network, no keys. Each test is
mutation-checked.

| ID | P | Measure |
|---|---|---|
| X-1 | P1 | `sr` sent for `rust`, `r/rust`, `/r/rust/`, ` R/rust `, `r/rpg`, `books` is `rust, rust, rust, rust, rpg, books`. Empty, `r/` and `/` raise `PublishError` before any post. Putting `lstrip` back fails the test. |
| B-F1 | P1 | Fake `usage_metadata` (prompt 1,000, cached 400, candidates 800, thoughts 6,000) through both `chat()` and `stream_chat()` gives input 1,000, cached 400, output 6,800. Recorded cost on `gemini-3.1-pro-preview` is €0.1150 (600×$4 + 400×$0.40 + 6,800×$18 per 1M, ×0.92). With `thoughts=None`, output is 800. |
| B-F2 | P1 | (a) All 6 paid text clients send the cap in both chat and stream calls (today: 1 of 6), seen on a fake SDK: OpenAI `max_completion_tokens`, DeepSeek/Kimi/Qwen `max_tokens`, Gemini `config.max_output_tokens`, Anthropic `max_tokens`. (b) For a fixed `messages` list, the guard, the Chat estimate and `_priced_for_request` all return the same euros: input counted from every message, output at the cap. (c) The D2 example is refused with €0.95 spent (today it is allowed). (d) A reply that ends at the cap (`length`, `MAX_TOKENS`, `max_tokens`) shows the length-limit notice. |
| B-F3 | P1 | Fake render states record: €0 and run "cancelled" for a cancel before the script stage. After 35 images, a failure in motion records the script, narration and captions lines + 35 × image rate, never more than the confirmed reserve. A failure at image 10 records the same lines + 10 images. Social clip: the same rule. Fiverr, 4 requested and #4 fails: 3 × per-image rate. Cancel before image 1: €0. Session and daily totals rise by exactly the recorded amount, and the run status stays "error"/"cancelled". |

## Owner decisions (my recommendation first)
**D1 Output cap. Recommend one default of 8,192 tokens** for all six clients, in one constant; Anthropic's 8096
moves to it too. Per-agent values would add a new settings surface, which is a feature during the freeze, so they go
to SUGGESTIONS. **When the model hits the cap: truncate and tell the user**, e.g. "Stopped at the length limit (8,192
tokens). Use Continue." Author already has Continue. A cut-off answer must never look complete. A per-request "long
answer" allowance in the confirm dialog is a feature: defer it.

**D2 Reserve at the cap. Recommend yes.** The confirm dialog shows the most the request can cost ("up to €X; you pay
for what it writes"), and the caps hold that amount while the request runs. Example: gpt-6-astra ($10 in / $50 out
per 1M, €0.92 per $), Author asked to "write chapter 3, about 5,000 words", with a 400-character prompt but 24,400
characters actually sent (≈6,100 tokens):

| | Today | Proposed |
|---|---|---|
| Dialog shows | ~€0.01 (100 in + 250 out) | up to €0.43 (6,100 in + 8,192 out) |
| Billed (≈6,700 tokens out, English) | €0.36 | €0.36 |
| Session cap €1.00, €0.95 spent | sent; session ends at €1.31 | refused before sending; local model offered |

The cost of this choice: a short request ("three titles", about €0.01) also shows "up to €0.38". With the default
€1.00 session cap, gpt-6-astra is refused once less than about €0.38 is left. The alternative is a typical-case
estimate plus stopping the stream at the remaining budget. That is not a hard cap, because reasoning tokens are only
counted at the end of a request. Not recommended.

**D3 Billing on failure or cancel. Recommend billing each paid stage that started, at the line the user confirmed**
in `pre_estimate` (`agents/video/studio.py:265-324`: script, narration, captions). Images are the exception: they are
about 90% of a render, so bill each image actually saved × the per-image reserve. Cap the total at the confirmed
reserve; reconciling above it belongs to B-F6. Read the stages from `build.manifest["stages"]`
(`vidforge/vidforge/pipeline.py:73-78`) and count the images in the image dir, because `visuals` is only marked after
the last image. A failure in the script stage bills the script line ($0.03-0.05); that slightly over-records if the call
never reached the provider. **A cancel before the pipeline starts its script stage bills €0.** Fiverr: bill the
images the provider returned × `image_cost_eur`. Alternatives: bill a started stage in full (up to €1.9 over-recorded
on an early cancel), or bill the whole reserve on any failure (simplest, but over-records the most).

**D4 Thinking tokens in the estimate. Recommend no separate term for now.** Reserving at the cap already covers
thinking wherever the cap includes it: OpenAI `max_completion_tokens` and Gemini `max_output_tokens` both do
(verified). For DeepSeek, Kimi and Qwen this is unverified (open question 1). If their cap does not bound thinking, the
Architect proposes a bound and the owner picks. Known cost: on a Gemini model thinking at its default high level, a
long answer can come back cut short or empty and still be billed (Google documents this). The notice must say so.
Revisit once the PAID UAT pass gives a real thinking ratio.

## Scope and phases
- X-1: normalise the name, refuse an empty one, add a test.
- B-F1: fix both Gemini usage builders.
- B-F2: add the cap to the six clients. Put one estimate function (full `messages` in, the cap out) behind
  `estimate_chat_cost`, `authorize_request` and `_priced_for_request`. Change the wording of the dialog and the notice.
- B-F3: add one way to close a request with an explicit partial cost and status (B-F7 can reuse it later), and use it in
  the three panels.

X-1 and B-F1 skip Design and Architect: there is no UI and each touches one function. B-F2 and B-F3 need Design (the
wording) and the Architect gate: `authorize_request` appears 26 times in 12 files, `record_request` changes, and usage
rows are written. A smaller B-F2, if the Architect finds the call-site change too wide: ship the cap and reserve-at-cap
first (in the example, output is about 90% of the reserve) and do full-`messages` input next. Manuscript-sized inputs
make that follow-up P1 as well.

## Non-goals
- B-F4: Chat gets the new estimate through `estimate_chat_cost`, not through `authorize_request`.
- B-F5: an unknown price still reserves €0.
- B-F6: B-F3 caps at the reserve and does not reconcile above it.
- B-F7: it reuses the partial-cost close from B-F3 later.
- B-F8, K-P2-1, K-P2-2.
- Per-agent caps, the long-answer allowance, resume-on-retry for renders, a stream budget stop, Gemini
  `tool_use_prompt_token_count` (no tools are sent), and default budget changes.

## Open questions
1. Kimi and Qwen cap parameter names, and whether they bound thinking. Whether DeepSeek's `max_tokens` includes
   reasoning. Whether OpenAI and DeepSeek `completion_tokens` include reasoning tokens. All UNVERIFIED; check primary
   docs before Build.
2. Google's thinking page (updated 2026-10-13) calls the count `total_thought_tokens`, while the SDK's
   `generate_content` metadata uses `thoughts_token_count`. Build against the SDK field and confirm on the first paid
   run.
3. A failed render with its partial cost: in the run log (proposed yes) and in Saved Chats (proposed no)?
4. Keep the €1.00 default session cap under D2 (proposed: keep)?

## Risks
- Truncated outputs could be saved or exported as complete. German runs about 1.5-2 tokens per word, so 5,000 words
  can go past 8,192. Design checks the panels that have no Continue.
- A provider that rejects the cap parameter name would fail every request on it. Mitigation: one fake-SDK test per
  client, then the PAID UAT pass.
- More "Request Blocked" dialogs under the default caps (D2). Small over-recording on script-stage failures (D3).

## Owner decisions (2026-10-14: "do the recommended")
- **D1** One output cap, 8,192 tokens, on all six text clients (Anthropic's 8096 moves to it). On hitting it: cut and tell the user ("Stopped at the length limit. Use Continue"); for Gemini thinking models the notice also says an empty answer can still be billed. Per-agent caps and a long-answer allowance go to SUGGESTIONS (feature freeze).
- **D2** Reserve at the cap; the confirm dialog says "up to €X; you pay for what it writes". Input estimated from the full messages sent.
- **D3** On failure or Stop, bill each paid stage that started at its confirmed line, and each saved image at the per-image rate; never above the confirmed total; Stop before the script stage bills €0; Fiverr bills only the images the provider returned.
- **D4** No separate thinking term in the estimate; reserving at the cap covers it. Revisit after the PAID UAT pass.

## Design
B-F2 and B-F3 only. Playbook `ux-designer.md` is `status: baseline` (last-reviewed 2026-10-10). Wording only: no new controls or dialogs; titles and buttons stay as they are unless stated.

**User's question.** Before a paid send: "What is the most this can cost, and do I have that left?" Afterwards: "Is this answer complete?" and "What did the failed or stopped run cost me?" **Primary figure:** "up to €X" before; "€X of €Y recorded" after.

**Money format (every string below).** Two decimals. A maximum ("up to") rounds up and an amount left rounds down, so the figures shown always agree with the decision. A paid amount under €0.01 reads "under €0.01", never "€0.00".

**B-F2 confirm dialog** (`confirm_external_api_request`, main.py:3654-3662; title "Confirm External API Request"; Yes/No/Apply unchanged). Before:
`This request will use an external API.\n\nProvider: {p}\nModel: {m}\nApprox tokens: {n}\nEstimated cost/quota impact: ~€{c}{assessment}\n\nContinue?`
After (text requests):
`This request will use an external API.\n\nProvider: {p}\nModel: {m}\nUp to €{max}; you pay for what it writes.\nBased on about {in:,} tokens sent and up to 8,192 written (the length limit).{assessment}\n\nContinue?`
- Per-unit requests (`flat_cost_eur`) keep their line. Renders and image batches add: "If it fails or you stop it, the paid steps already done are recorded."
- `_assessment_text` (main.py:1237-1238): both "~€" become "up to €" for text requests (both figures are now at the cap).
- Same figure, same words: live line (main.py:575) `Next request: up to €{max} · paid · {backend} {model} · ~{in:,} tokens + up to 8,192`; Cost Estimate popup (main.py:600) `Most it can cost: €{max} (you pay for what it writes)`.

**B-F2 refusal** (`services/validator.py:118-143`; shown in "Request Blocked" or inside the local-model offer). Before: `Session budget exceeded. Remaining: €0.0500, request: ~€0.4300.` ("exceeded" is false: nothing was spent.) After:
- Session: `Not sent: this request can cost up to €0.43 and your session cap has €0.05 left (of €1.00). Pick a cheaper or local model, or raise Session € under Limits and press Save Limits.`
- Daily: `Not sent: this request can cost up to €0.43 and today's cap has €0.20 left (of €5.00). Pick a cheaper or local model, raise Daily € under Limits, or wait until tomorrow.`
- Project and agent caps: same shape, naming the cap ("Project 'X' has €0.10 left today"); remedy "Pick a cheaper or local model."
- Never suggest a shorter prompt: output is reserved at 8,192 tokens whatever the prompt, so shortening barely moves the figure.
- Local offer (main.py:4269-4273): title "Budget cap reached" becomes "Not enough budget left" (the cap was not reached); body = the reason above + today's switch sentence, unchanged.

**B-F2 length-limit notice.** Shown next to the cut-off text, never inserted into the answer (it would be saved and exported). A cut answer never shows "[Finished]" or "[Done]".
- Chat transcript (replaces `[Finished]`, main.py:4543): `[Cut off] Stopped at the length limit (8,192 tokens); this answer is incomplete. To get the rest, send "continue" as your next message (a new paid request).` Chat has no Continue button, but it keeps the conversation (`_conversation_context_text`), so this works today.
- Author Write/Continue (`author_status_label`, agents/author/panel.py:1122): `[Cut off] {n:,} words, stopped at the length limit. Press Continue to write more.` The [UNSOURCED] suffix still follows. Only Author has a Continue control.
- Every other text result (Author publishing/marketing, Manuscript, Social, Creator, Fiverr text, Web design, Music), in that panel's status label instead of "[Done] …": `[Cut off] Stopped at the length limit (8,192 tokens); the result is incomplete. Ask for less or split the task, then run it again.` If the panel parses the output (e.g. Manuscript calendar JSON) and parsing fails, show this line, not the parse error.
- Gemini, when thought tokens > 0, append: `Gemini spent part of the limit thinking.` Empty answer: `[No answer] Gemini used the whole length limit (8,192 tokens) thinking and wrote nothing. It is still billed; see Cost History.`

**B-F3 failed or stopped render or batch.** One status line, detail in the log. €X = recorded, €Y = confirmed total.
- Video (`_reset`, agents/video/panel.py:889). Failure: `[Error] {error}. €X of €Y recorded (script, narration, captions, 35 of 35 images).` Stop: today shows `[Error] Cancelled.`; instead `[Stopped] After 35 of 35 images: €1.87 of €2.12 recorded.` Stop before the script stage: `[Stopped] Before any paid step: nothing recorded.`
- While stopping (agents/video/panel.py:1136, today "Cancelling after this stage…"): `Stopping after this step… paid steps already done are recorded.`
- `video_log`, one line per close: `[Billing] Recorded €X of €Y confirmed: script €a, narration €b, captions €c, 35 images × €d. A new render starts from the beginning and is paid again.` (Resume-on-retry is a non-goal; the user must know.)
- Social clip (`social_status_label`, agents/social/panel.py:691): the same lines, prefixed `Clip: `.
- Fiverr (`fiverr_status_label` :547, `fiverr_preview_status` :548, Stop :894): `[Error] Concept 4 failed: {reason}. 3 of 4 concepts made; €X of €Y recorded.` / `[Stopped] 2 of 4 concepts made; €X of €Y recorded.` / `[Stopped] Before the first concept: nothing recorded.` (moves "Error:" and "Stopped." to the `[Tag]` convention).
- Cost History: agent, provider, model as today; Cost = €X; Type `partial` (a new value in the existing column, beside exact, mixed, estimated, per_unit).
- Run Log: status `error`, or `cancelled` for a user Stop; Cost = €X; Error cell `{error}; recorded €X of €Y`. Saved Chats: no entry (answers open question 3).

**Keyboard and contrast.** No new focus stops, shortcuts or default-button changes. Meaning is carried by the `[Tag]` word, not colour; Run Log colours keep their status word. `author_status_label`, `social_status_label` and `manuscript_status_label` do not wrap today (video and Fiverr do): turn word wrap on so the longer lines do not clip at 125-200% text size.

**Flagged, out of scope:** the Run Log status filter (ui/dialogs.py:221) has no "stopped", but Author, Social and Fiverr Stops write `stopped`, so those runs only appear under "all".

## Architecture
B-F2 and B-F3 only. Playbook `architect.md` is `status: baseline` (2026-10-10); the 2026-10-14 billing radar note is reused. No ADR: there is
no schema change, and partial rows are ordinary usage rows.

**B-F2: the cap.** A new `services/output_limits.py` (no imports) holds `MAX_OUTPUT_TOKENS = 8192` and `stop_kind(raw)`, which maps `"length"`,
`"max_tokens"` and Gemini `FinishReason.MAX_TOKENS` (by `.name`) to "length", else None. Each client's `chat()` and `stream_chat()` takes
`max_output_tokens=MAX_OUTPUT_TOKENS` (per-agent caps later need no signature change) and sends: OpenAI `max_completion_tokens`
(openai_client.py:87, :145); DeepSeek, Kimi, Qwen `max_tokens` (deepseek :67/:92, kimi :63/:89, qwen :269/:294); Gemini
`config=GenerateContentConfig(max_output_tokens=…)` (:196, :404); Anthropic the constant instead of 8096 (:113, :173). `run_backend`
(main.py:4447-4494) uses `stream_chat` for all six, so streams are the live path; tests cover both. D4 (open question 1): if a DeepSeek, Kimi or
Qwen cap does not bound thinking, the owner picks (a) that provider's thinking budget, so thinking plus answer stays ≤ 8,192 (Qwen `thinking_budget`, UNVERIFIED), or (b) reserving the cap plus the model's documented thinking maximum.

**B-F2: reporting a cut-off.** `UsageStream` (stream_usage.py:19-24) gets `stop_reason`, set from the last chunk (`choices[0].finish_reason`;
Anthropic `final.stop_reason` :131; Gemini `candidates[0].finish_reason`). `chat()` puts `"stop_reason"` in its usage dict; B-F1's `_usage`
(:71-90) adds `"thought_tokens"`. `ChatWorker.run` (ui/workers.py:84-108) merges it into the usage dict it sends on the existing `usage_signal`.
That signal is sent before `finished_signal` from the same thread, so it arrives first; replies without usage keep their estimated cost_type.
`note_request_usage` stores it. `record_request` (main.py:4372) returns its entry (today None) with both keys. One helper,
`result_notice(entry, response, kind)`, builds every Design string ([Cut off], the Gemini suffix, [No answer]). Chat uses it at :4543; panels use it in their finished handlers before parsing.

**B-F2: one estimate.** usage_tracker.py gets `estimate_input_tokens(messages)` (chars/4 over every message's text) and
`max_cost_eur(backend, model, in_tokens, conn=None)`: input plus `MAX_OUTPUT_TOKENS` × output rate, None if unpriced. It shares a factored
row-cost function and eur reader with `calculate_cost_eur` (:51-86). `estimate_chat_cost(…, messages=None)` (main.py:492) prices
`with_project_instructions(messages or [prompt])`, the same idempotent call ChatWorker makes, and returns `(cost or 0.0, in_tokens)`: unknown stays
€0 (B-F5). `_priced_for_request(candidates, in_tokens)` (:1503) calls `max_cost_eur` on its one connection, without
`per_unit_pricing.eur_per_usd()`, so all three paths agree (b). `assess_request` and `_text_recommendations` (:1161, :1527) pass `in_tokens`.
**authorize_request** (main.py:3751) gains keyword-only `messages=None` and `partial_billing=False`. Of its 24 GUI calls: 6 flat calls are unchanged;
3 renders or batches (video:503, social:593, fiverr:463) add `partial_billing=True` (dialog line); 15 text calls add `messages=messages`. 12 of
those already build the messages first; music/panel.py:206, music/suno_panel.py:196 and webdesign/panel.py:187 move their pure build line up.
A text call without messages falls back to `[prompt]`; an AST test blocks that. Rejected: estimating at the worker hand-off (the dialog needs
the reserve first). This is not too wide, so B-F2 is not split. **Chat inline** (main.py:3518-3637): build `messages` (:3585) before the
estimate (:3536); `get_current_cost_estimate` (:526) builds the same messages, so live line, popup, dialog and guard agree. Still no reservation (B-F4).
**Wording**: a new `services/money_text.py` (`up_to()` rounds up, `left()` rounds down, "under €0.01"). `Validator.validate` (validator.py:103-143)
words each refusal from the totals and `scope` it already has. Also: confirm (main.py:3654), `_assessment_text` (:1237), live line (:575),
popup (:600), local-offer title (:4270).

**B-F3: the API.** `record_partial(token, cost_eur, *, status, error) -> (recorded, confirmed) | None` sits beside `abandon_request`
(main.py:4420). Token only; an unknown or closed token is a no-op. recorded = min(max(0, cost), `context["estimated_cost"]`); a non-finite cost
records the reserve. If recorded > 0, `log_request(…, flat_cost_eur=recorded, cost_type="partial")` (new keyword, usage_tracker.py:88-106)
and the session totals rise. €0 writes no row; never a Saved Chat. Run Log: `finish(status="error"|"cancelled", cost_eur=recorded,
error="{error}; recorded €X of €Y")`. B-F7 can reuse it with a token-priced amount; B-F6 changes the success path, not this.
**Stages across the thread.** `VideoWorker` (ui/workers.py:499-577) gets `trace_signal(dict)`, sent once just before done or error. Its
`QtReporter` (worker thread) records each `on_stage` key. A `substep` override sets `images = done` during `visuals` before calling `super()`:
reaching scene k proves images 0 to k-1 were saved, and a Stop raises inside `super()`. A later stage sets `images = total`. vidforge is
unchanged. Rejected: the manifest or image dir (the GUI never gets `build` on a failure, and Video and Social clip can render at once); parsing
progress text. A pure `partial_render_cost_usd(estimate, trace)` (agents/video/studio.py) bills script, narration (`voice`) and captions for
started stages, plus (images, +1 if `thumbnail` started) × `per_image`, a new `pre_estimate` key (:265-324). A Stop before `begin("script")` has no stages, so €0.
**Panels** keep the estimate and eur rate taken at authorize. Video (panel.py:499-526, :837-889, :1129-1136), pipeline only: `stop()` sets
`_stop_requested` (status "cancelled"); `_on_error` calls `record_partial` instead of `abandon_request` (:869). Social clip (:576-617, :682-691):
the same for `_clip_video_token`. The brief stays abandoned (B-F7), and the clip render has no Stop, so only failure applies. Fiverr (:463-549, :880-895):
rate = `image_cost / count`; signals bound to the run's token; count `image_ready`. Stop cancels the worker but closes only on its final
"Cancelled.", so an image paid in flight is billed. Buttons stay disabled until the worker exits.

**Files.** New services/output_limits.py and services/money_text.py, plus the anchors above: six clients, stream_usage.py, usage_tracker.py,
validator.py, ui/workers.py, main.py, video/studio.py and the video, social and fiverr panels, plus the 15 text call sites and their finished handlers.
Word wrap: author/panel.py:635, manuscript/panel.py:300, social/panel.py:185. For Design: creator:240, webdesign:127, music:138 and
fiverr_preview_status:212 also get long notices and do not wrap. Creator drafts (creator/panel.py:675-679) need `usage_signal` connected for the notice. That is F8's one-line fix: fold it in.

**Tests** (offline: fake SDKs, temp DB, `window` fixture; test_output_cap.py, test_request_estimate.py, test_partial_billing.py):
1. Each of the 6 clients sends 8,192 under its own name, in chat and stream (12 cases); no cap literal outside output_limits.
2. "length", "max_tokens" and MAX_TOKENS give "length", normal stops give None; ChatWorker sends it before finished, with or without a usage frame.
3. Notices: Chat shows [Cut off] and no [Finished]; Author shows "{n:,} words"; generic panels; Gemini suffix and [No answer]; a cut Manuscript calendar shows the cut-off line, not the parse error.
4. (b) the estimate, the guard's validated cost (spy) and `_priced_for_request` give equal euros, counting system, history and project text.
5. (c) refused at €0.95 spent, allowed at €0.55. The dialog reads "up to €0.44" (€0.4330 rounds up; the spec's €0.43 was unrounded). Wording for each scope; never "exceeded".
6. AST: every non-flat `authorize_request` passes `messages=`; `send_prompt` validates the worker's own messages.
7. `partial_render_cost_usd`: empty trace 0; script only; 35 images; 10 images; thumbnail +1; never above the total.
8. VideoWorker with a fake `produce`: cancel before start gives no stages; Cancelled at scene 11 gives 10 images; motion failure gives 35; trace before error.
9. Video failure: one `partial` row, run `error` with "recorded €X of €Y", session and daily up by exactly X, no Saved Chat. Stop before script: no row, `cancelled`. Social clip: same.
10. Fiverr 3 of 4 bills 3 × rate; Stop during image 2 bills 2 after the worker exits; Stop before image 1 bills €0. `record_partial` caps at the reserve (also for NaN), floors at 0, ignores names and closed tokens; successful rows unchanged.

**GATE: yes**, owner approval before Build. State: new `partial` usage rows on failure and Stop paths feed the daily, agent and project caps;
run rows gain cost and error; `record_request` returns its entry. No schema change, no migration, no existing row touched. Contracts: a new
cross-thread signal, `stop_reason` on `usage_signal`, a later Fiverr Stop close, new keyword parameters. Concurrency: guard state still changes
only on the GUI thread; workers hand over copies by queued signal, in order. No new paid path.

**Risks.** Kimi and Qwen parameter names and thinking bounds are UNVERIFIED: a rejected parameter fails every request to that provider, and only PAID
UAT shows it. gemini_client.py is open for B-F1, so B-F2 builds after it lands. Approximations, all capped at the reserve: a started stage bills in
full (up to $0.05 high on a script failure); gradient-fallback scenes count as images; an image paid but unsaved at a failure is missed (≤ 1);
scenes beyond the estimate are missed (B-F6). Quitting mid-render still records nothing (main.py:5290-5310). A hung Fiverr image call holds the
reserve until it times out. The live line builds messages on every keystroke (main.py:2371). tests/manual_test_cases.md:264 says "Budget cap
reached". Without a usage frame, billing still uses chars/4 of the prompt only (B-F7/F8).

## Architect gate (2026-10-14: owner "approve")
Approved as written, with: (1) Creator panel connects `usage_signal` (also closes audit B-F8); (2) word wrap on every
status label that shows the new notices: author, social, manuscript, creator, webdesign, music, fiverr preview;
(3) for DeepSeek, Kimi and Qwen thinking models, reserve the cap plus the model's documented thinking maximum until a paid
run confirms whether the cap bounds thinking. "Up to" figures round up (worked example: €0.44).

## Review loop 1 decision (2026-10-14: owner "do recommendations")
Thinking reserve per provider, replacing the provider-wide 65,536 stand-in:
- **Kimi:** no extra reserve. Kimi's thinking-model doc says `reasoning_content` counts against `max_tokens`, so the 8,192 cap bounds it.
- **Qwen:** send an explicit thinking limit of 8,192 (DashScope `thinking_budget`; parameter name from a search summary, unverified)
  and reserve cap + 8,192. Confirm on the first paid run (TODO `@me`).
- **DeepSeek:** keep 65,536 (documented default in thinking mode; whether it counts inside `max_tokens` is unknown).
The dialog's "plus up to N for thinking" clause appears only for models with a non-zero thinking reserve.
