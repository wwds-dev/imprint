# Security review: audit P1 fixes (B-F1, B-F2, B-F3, X-1), 2026-10-14

Role: security-engineer (read-only). Uncommitted diff on `foundry/imprint-audit-p1-2026-10-14`. Playbook `status: baseline`.

## Verdict
No P0/P1. The budget guard holds for the paths these fixes cover; nothing serious opened.
- **B-F1 closed:** output = candidates + thoughts, cached slice passed (google-genai 2.21.0 field docs).
- **B-F2 closed** for OpenAI, Anthropic, Gemini, DeepSeek, Kimi; **conditionally open for Qwen** (P2-1). Cap sent on chat,
  stream and SDK retry (OpenAI-compatible SDKs probed with a 500→200 mock transport: both attempts carry the cap; Gemini text
  does not retry). Guard, Chat estimate and recommendation pricing give the same euros; every text call site prices the same
  list object its worker sends (checked by hand).
- **B-F3 closed:** `record_partial` capped at the reserve, token-only, closes once; trace cannot exceed the reserve; late
  Fiverr signals ignored. Small under-records P3-1, P3-2; quitting mid-render still records nothing (known).
- **X-1 closed:** spec cases pass; no form-body injection (`&`, `%`, CR/LF, NUL, unicode stay encoded); empty names refused
  before any post.

## Findings
**P2-1 Qwen thinking reserve is a placeholder below a documented maximum.** `services/output_limits.py:40-44` (comment
`:33-39` "UNVERIFIED stand-in"); `services/qwen_client.py:212-220`. Reserve = 8,192 + 65,536. Whether DashScope `max_tokens`
bounds reasoning is unverified; Alibaba's Coding Plan FAQ (search summary) lists max thinking 262,144 for `qwen3.7-plus`,
81,920 for qwen3.6-plus/3.5-plus/3-max. Probe (1,000 tokens in): qwen3.7-plus reserve €0.1089 vs €0.3983 at full thinking;
qwen3.8-max €0.4088 vs €1.4941. Kimi is the opposite: its doc (search summary) says `reasoning_content` counts against
`max_tokens`, so the add-on only over-reserves (kimi-k2.7-code €0.27 vs real max ~€0.03). Fix (owner): (a) send an explicit
Qwen thinking bound (`thinking_budget`, or `enable_thinking: false` on hybrid models) and reserve cap + bound; or (b) per-model
documented maxima. Test that each Qwen `KNOWN_MODELS` id maps to a sourced figure.

**P2-2 Two EUR readers; the text one accepts `eur_per_usd` ≤ 0 (audit B-F5; the reserve now depends on it).**
`services/usage_tracker.py:11-13` (raw float) used by `max_cost_eur` (`:61`); `services/per_unit_pricing.py:63-76` rejects ≤ 0;
Settings saves any float (`ui/dialogs.py:976-979`). Probe: at -0.92 `max_cost_eur` = -0.432952, at 0 = 0.0; negative
reserves summed into `_reserved_in_flight_eur` (`main.py:4368-4371`). One typo removes every text cap. Fix: one reader,
finite > 0 else 0.92, shared; Settings rejects ≤ 0, NaN, inf.

## P3
1. Fiverr Stop can close before queued `image_ready` signals arrive (`agents/fiverr/panel.py:939`, `:950-963`): probe recorded
   €0.0552 of €0.2208 with 4 images saved. Close only from the worker's terminal signal, or flush queued events first.
2. Stop during the last scene image bills one image too few (`ui/workers.py:553-565`, `:583-588`;
   `vidforge/vidforge/pipeline.py:241-242`): 35 saved, trace 34. Override `QtReporter.begin` to set images to total when leaving visuals.
3. Priced messages not tied to the worker payload (`tests/test_request_estimate.py:346-368` checks presence only;
   `main.py:3446-3452`). Store `in_tokens` with the token; the worker factory refuses a larger payload.
4. Run Log renders new partial-billing error text as unescaped HTML (`main.py:4555-4563` → `ui/dialogs.py:265`;
   pre-existing for Chat errors). `html.escape` every field.
5. Reddit: confirmation doesn't show the normalised name; `r/r/rust` → `r/rust`, `r/ rust` → `" rust"`, URLs sent as typed
   (`agents/social/publishing.py:77-91`, `:159-170`; `agents/social/panel.py:1030-1033`). Validate
   `^[A-Za-z0-9][A-Za-z0-9_]{1,20}$` and show `r/<name>` in the confirmation.

## Could not verify
Live billing on any provider; whether DeepSeek/DashScope `max_tokens` bounds reasoning; Gemini `thoughtsTokenCount` sometimes
missing (community report; hardening: output ≥ total − prompt − tool_use_prompt); Gemini `max_output_tokens` enforcement on
gemini-2.5-flash (forum report). Sources were search summaries, not fetched pages.

Outside scope (pre-existing): `services/anthropic_client.py:163` references undefined `model` in `_stream`, so a 404 surfaces
as NameError.

Probes (read-only, temp DB, sockets blocked): session scratchpad `sec_probe/`.
