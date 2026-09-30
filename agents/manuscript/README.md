# Press agent (`agents.manuscript`)

Owns finished-manuscript preparation: metadata, export, KDP/PublishDrive data,
quote discovery, launch planning and sales interpretation.  Its public API is
`agents.manuscript.ManuscriptAgent`.

The umbrella owns provider execution and the request guard.  Publishing data
adapters remain shared until they are proven exclusive to this package.  User
guidance: `docs/agents/manuscript.md`.

Quote Finder's **Use Project Draft** action loads the selected Project's
current Write draft (or linked saved draft) on demand, using its byline for
attribution. It does not mark that working text as approved for publication.
**Approve Write Draft…** creates an immutable numbered snapshot after a user
confirmation. **Use Approved Version** loads the selected snapshot into Quote
Finder; subsequent Write edits do not rewrite approved content.
**Export Approved…** creates a new ebook/document from the selected approved
version and saves a file fingerprint. **Submission Ledger…** records a manual,
self-reported retailer submission against a matching export, with a reference
or evidence file; it never submits to or verifies a retailer.

Run focused coverage with `pytest tests/test_book_pipeline.py`.

## Files

- **`__init__.py`** — the package's public surface: re-exports
  `ManuscriptAgent`.

- **`agent.py`** — the implementation, described in its own docstring as
  "extends the author_agent with distribution intelligence." It holds five
  system prompts, each backing a distinct capability:
  - `SYSTEM_PROMPT` — the general publishing-intelligence assistant: answers
    sales/royalty questions, platform health ("which stores are still
    pending?"), ranking and revenue trends, todo/checklist management, and
    metadata-sync status. Response style leads with the number, uses short
    tables for cross-platform comparisons, proactively flags anomalies (a
    sudden drop, a platform going inactive), and must say when data is
    missing or stale rather than guess — it is always grounded in JSON data
    injected ahead of the user's question.
  - `PUBLISHDRIVE_PROMPT` — parses raw PublishDrive API data into a strict
    JSON summary: `total_units`, `total_revenue_usd`, `by_platform`,
    `by_country`, `pending_stores`, `rejected_stores`, `period`. JSON only,
    no prose.
  - `KDP_PROMPT` — parses an already-JSON-parsed KDP sales CSV into
    `total_units_sold`, `total_royalties_usd`, `by_marketplace`,
    `kenp_pages_read` (if present), `period_start`, `period_end`. JSON only.
  - `QUOTE_SUGGESTION_PROMPT` — extracts quotable lines from a manuscript for
    Instagram/Pinterest quote graphics and short-form video. Lines must
    stand alone with no context, be emotionally sharp or screenshot-worthy,
    read in 3–6 seconds (~6–20 words), and be copied **verbatim** — no
    paraphrasing or invention. Returns a bare JSON array of strings.
  - `CALENDAR_CAPTION_PROMPT` — given a JSON array of `{quote, platform}`
    items (`tiktok` / `instagram` / `pinterest`), writes one short
    platform-native caption per item (TikTok: conversational + hashtags;
    Instagram: warmer/polished + hashtags; Pinterest: keyword-rich, no
    hashtags, soft CTA). Returns a bare JSON array in the same order/length
    as the input.

  `ManuscriptAgent` is the class the app calls:
  - `build_messages(prompt, context_json="")` — appends `context_json` to
    `SYSTEM_PROMPT` when given, for general Q&A grounded in current data.
  - `build_publishdrive_parse_messages(raw_json)` — messages for the
    PublishDrive parser.
  - `build_kdp_parse_messages(rows_json)` — messages for the KDP parser.
  - `build_quote_suggestions_messages(manuscript_text, count=10)` —
    messages requesting the top `count` quotable lines from the given text.
  - `build_calendar_caption_messages(items_json)` — messages for the
    caption generator.

- **`recommendations.py`** — registers Publish's `RECOMMENDATION_PROFILE`
  (an `AgentProfile` from `services.recommendations.models`) with the shared
  model-recommendation engine: task tags `analysis` / `structured` /
  `planning`, `reliability_weight=.27` and `cost_weight=.20` — both raised
  above the engine defaults (.20 / .15), since this agent reports real
  financial figures (accuracy matters) under frequent, routine queries (cost
  adds up) — and a `provider_affinity` table ranking OpenAI (.94) above
  Anthropic (.92), DeepSeek (.90), Gemini (.88), Qwen (.84) and Kimi (.83).

- **`panel.py`** — owns the complete Press workspace: Overview
  (metrics, Ask, publishing todos, Connections status), Quote Finder, Quote
  Graphics, Shorts and Calendar tabs, moved here from `main.py` in the Phase 4
  extraction. Request tokens live on this panel — "manuscript" is shared by
  four paid flows (Ask, quote suggestions, calendar captions, ElevenLabs
  narration) — so nothing here resolves a request by agent name. The old
  `setattr(host, name, ...)` alias loop that mirrored every `HOST_CONTROLS`
  widget onto the umbrella was retired 2026-09-21 (commit `8de6d7c`) — shared
  code that used to read `window.<control>` directly now goes through
  `host._find_control()`; `HOST_CONTROLS` stays defined as the published
  contract of what this panel owns. Workers stay host attributes so the
  umbrella's global shutdown sweep keeps seeing them. It wires every module
  below (KDP/PublishDrive ingest in Overview and Connections, quote/shorts/
  calendar generation in their own tabs) and the Quote Finder's Project-draft/
  approved-version/export/submission-ledger flow described above.

  The rest of the package supports `panel.py` and splits into four groups:

  **KDP / PublishDrive data** — the two publishing-platform adapters neither
  has a public consumer API for, so both are manual-import/manual-key designs:
  - **`kdp_csv_parser.py`** — Amazon KDP has no sales API. Watches
    `data/kdp_reports/` for CSV reports the user downloads by hand from the
    KDP dashboard, `parse_kdp_csv`/`summarise_kdp_rows` turn a report into
    per-marketplace units/royalties/KENP-pages-read totals, and
    `ingest_new_reports()` stores each newly-seen file into
    `manuscript_kdp_ingested`, deduplicated by filename. Also defines
    `INITIAL_TODOS` — the ~24-item standard publishing checklist (KDP/
    Draft2Digital/IngramSpark accounts, cover specs, ARC/BookBub/BookTok
    outreach, and a batch of "(Dev)" engineering-backlog items) that
    `manuscript_seed_todos()` seeds into `manuscript_todos` the first time
    it's empty.
  - **`publishdrive_client.py`** — a thin REST client for PublishDrive's API
    (which *does* have one, keyed via `PUBLISHDRIVE_API_KEY`): sales reports,
    catalog listing, per-title distribution status, and metadata push
    (`update_metadata`), plus `get_last_30_days()`/`get_this_month()`
    convenience windows used by the Overview tab and Connections status.

  **LLM response parsing:**
  - **`llm_parsing.py`** — `parse_string_list(text)`, shared by the quote-
    suggestion and quote-graphics flows: models are asked for a bare JSON
    array but don't always comply, so it falls back through raw JSON → a
    JSON array embedded in surrounding prose → a line-by-line strip of
    bullets/numbering/quotes, always returning a list rather than failing.

  **Promo asset generation** — quotes to shareable graphics, narrated shorts,
  and a posting schedule:
  - **`quote_graphics.py`** — renders a quote as a styled PNG with no external
    API or paid image generation: three gradient `THEMES` (midnight, blush,
    zodiac), `square`/`vertical` `SIZES` for feed vs. Story/Reel/Pin, word-
    wrapped centered quote text plus an optional attribution line.
    `render_quote_graphic()` is the entry point; output goes to
    `data/quote_graphics/`.
  - **`shorts_generator.py`** — combines one of those graphics with narrated
    audio into a vertical MP4 sized for TikTok/Reels/Shorts via `ffmpeg`.
    `get_voice_provider()` picks free on-device `say`-based TTS
    (`MockVoiceProvider`) by default or ElevenLabs when
    `ELEVENLABS_API_KEY` is set and requested; `render_short()` synthesizes
    the narration, then scales/pads the still image to 1080×1920 and muxes
    it with the audio.
  - **`workers.py`** — `ShortsWorker`, the `QThread` that runs
    `shorts_generator.render_short()` off the UI thread and emits
    status/done/error signals back to the Shorts tab; moved here from the
    old `ui/workers.py`, with the host still holding the instance as
    `host.shorts_worker` for the umbrella's shutdown sweep.
  - **`content_calendar.py`** — pure scheduling logic, no LLM call: given a
    list of quotes and a set of platforms, `build_calendar()` assigns each a
    day/platform/format slot following a per-platform weekly `CADENCE`
    (TikTok 4/week short-form, Instagram 3/week alternating graphic/short,
    Pinterest 7/week graphic), cycling quotes if there are more slots than
    quotes, and distributing per-week rather than across the whole window so
    a stated cadence actually holds every week instead of front-loading.
    Caption text for each slot is a separate LLM step
    (`ManuscriptAgent.build_calendar_caption_messages`, above).
  - **`book_widgets.py`** — shared `QComboBox`/helper factories for the
    theme, size, and voice-source/voice controls that Quote Graphics, Shorts,
    Quote Finder and Calendar all offer identically, so adding a theme or a
    voice source is a one-place change. Also has `unique_output_path()`,
    which appends a counter to a millisecond timestamp so generating several
    assets in a tight loop (e.g. clicking through Calendar rows quickly)
    can't silently collide and overwrite an earlier file.
