# Imprint — Suggestions

Ideas not yet committed to. Status: `IDEA` · `CONSIDERING` · `PLANNED` · `DONE` · `REJECTED`

---

## v2 — in the current arc

| # | Suggestion | Category | Effort | Status |
|---|---|---|---|---|
| 1 | Agent-project architecture — package-per-agent implementation, catalog and local README/TODO/SUGGESTIONS are DONE. Moving panels from `main.py` into their owning packages remains planned in each agent's TODO. | design | L | DONE |
| 3 | Remove the dead `ops_identity` sidebar entry — listed in `agent_titles` with no implementation behind it | bug | XS | DONE |
| 5 | DONE — Budget card layout. Both caps are progress bars now, and the four spend figures are stat blocks rather than nine lines of prose. The bar turns red at 100%. | design | S | DONE |
| 6 | Per-agent cost breakdown in the cost dialog, so it's visible which agent is eating the daily cap | feature | M | IDEA |
| 13 | DONE — mode tabs, now in the header bar rather than centred over the canvas. | design | L | DONE |
| 56 | **Add a model id by hand**, per provider, in the Model updates tile. For an id the provider's `/models` does not list (a gated preview, or no key yet so only the offline list shows). Validate against the live list when there is a key; store beside `model_watch.json`; merge into the dropdowns with the same NEW mark; refuse to send until it has a price or the user accepts the provider default. Low risk — the client, guard and pricing already exist. | feature | S | CONSIDERING |
| 57 | **Add a provider from the app** — but only as an *OpenAI-compatible* provider with explicit fields (name, base URL, key variable, prices), not a free-text box. A provider name alone cannot become working code: it needs a client, an auth scheme, a key, prices for the budget guard, an `allow_*` permission and registry rows. Most newcomers (Mistral, Groq, Together, xAI, OpenRouter) do speak the OpenAI shape, which is what makes this tractable; anything else stays a code change. Needs the request guard to treat a user-defined provider as paid and unknown-priced by default. | feature | L | IDEA |
| 58 | **Remember the last live model lists across launches**, so the startup BEST FIT pre-selection can pick a new model before the four-second check has run. Today the first pass ranks the offline lists and the marks move when the check lands; the selection itself is left alone mid-session on purpose. | feature | S | IDEA |

## Creator agent — next arc

Written after building v1. The first three are things I left half-done rather
than ideas: unused schema, an unfinished API loop, and untested handlers.

| # | Suggestion | Category | Effort | Status |
|---|---|---|---|---|
| 20 | DONE — **Voice profile per account.** The biggest quality lever there is. Every draft currently starts from nothing, which is exactly why AI copy reads like AI copy. Store 3–5 of the creator's own posts, plus tone rules, emoji habits, banned words and typical length; inject into every prompt. Without it the drafts are competent and generic — with it they sound like the person. | feature | M | IDEA |
| 21 | DONE — **Finish the Higgsfield loop.** `generate_video()` submits a job and the panel says "check Higgsfield for the result". `HiggsfieldClient.wait()` exists and nothing calls it. Poll on a worker thread, download the mp4, store it against the account and attach it to a calendar item. A half-wired feature is worse than an absent one. | bug | M | IDEA |
| 22 | DONE — **Use `media_path`, or drop it.** The column is in `creator_content` and referenced nowhere in `main.py`. Creator work is media-first: a caption without the photoset it belongs to is half a draft. An asset library that links drafts to the actual files is the missing half. | feature | M | IDEA |
| 23 | DONE — **Close the loop from draft to revenue.** Earnings import currently prints a text summary. What makes it worth having is attribution: which PPV price converted, which hook earned, what a subscriber is worth over time. Chart it, and let the PPV drafter read from it instead of taking a price as a blind argument. **Removed 2026-09-30 — moved to Backstage.** | feature | L | IDEA |
| 24 | DONE — **Persona bible.** For `persona` accounts there is a disclosure line and nothing else, so nothing keeps a character consistent between sessions. Appearance, backstory, voice and locked reference images — paired with Higgsfield Soul for visual consistency — is the difference between a persona and a series of unrelated posts. **Kept 2026-09-30, without the `persona` account type: the bible, seed and reference images are now applied to any account that has one.** | feature | M | IDEA |
| 25 | DONE — **Hook variants with outcomes.** Creators test openers; the app writes one and forgets it. Generate three, record which was used, join it to what it earned. This is what turns the earnings data into a feedback loop rather than a report. **Removed 2026-09-30 — moved to Backstage.** | feature | M | IDEA |
| 27 | DONE — **Fan segments.** A welcome message, a re-engagement message to someone lapsed, and a thank-you to a two-year subscriber are three different messages. The drafter treats them as one. **Removed 2026-09-30 — moved to Backstage.** | feature | S | IDEA |
| 28 | DONE — **A calendar that behaves like one.** `agents/creator/calendar.py` (2026-09-29) turned it into a real 7-day week-view grid with an Undated lane, Reschedule (button/double-click, jumps to the target week), and export to `.ics` (RFC 5545) or CSV. | design | M | DONE |
| 29 | DONE — **Panel handler tests.** `test_creator_agent.py` covers the agent, the content guard and the CSV parser. The panel handlers — save/delete account, schedule, import, the worker lifecycle — have no coverage, which is where the consent rule is actually enforced for a real user. | testing | S | IDEA |
| 30 | DONE — **Agency view across managed accounts.** Consent is recorded per account, but there is no cross-account reporting, no per-account voice, and no commission calculation — the things that make managing several accounts different from managing one. | feature | L | IDEA |

## After the Imprint merge

Written with all five modes shipped and the app rebuilt. The first two are
consequences of what just landed rather than new ideas.

| # | Suggestion | Category | Effort | Status |
|---|---|---|---|---|
| 40 | DONE — **Price the second provider.** Per-unit billing now covers Fiverr images and TTS; Creator renders use Higgsfield's authenticated estimate for the exact prepared payload and pass that amount through the same budget guard. | security | M | DONE |
| 41 | **A doc test that fails when an agent has no guide.** The Learning Centre silently fell a full agent behind twice. `WORKSPACES` is now checked against both `docs/learn/02-agents.md` and `docs/agents/*.md`; a missing agent sheet was added with the test. | testing | S | DONE |
| 43 | DONE — **Video mode.** vidforge imported from the nested repo (not vendored), long-form and clips as one pipeline, cost estimated per stage and charged against the caps. | feature | L | DONE |
| 44 | DONE — **Social mode.** Campaigns, per-platform drafting, cadence scheduling, and real posting for the three platforms where that is possible from a personal account. | feature | L | DONE |
| 45 | **Charts, not monospace.** Three panels now compute genuinely interesting numbers (KDP royalties, creator price points, cost history) and all three render them as aligned text. One small charting layer would serve all of them. **Partly done:** the layer exists — `ui/charts.py` (`4c488f9`), a themed QPainter bar chart — and Press's KDP royalties use it; cost history is still text. | design | M | IDEA |
| 46 | **A "what should I do today" view.** The app knows the publishing todos, the content calendar, which drafts are unposted and which books are part-listened. Nothing assembles that into the one screen a person actually opens in the morning. | feature | M | IDEA |
| 48 | **Back up the writable directory.** Everything that matters — database, keys, chats, logs — lives in one Application Support folder that nothing in this workspace backs up, while `_Admin/backup/` exists and is good at exactly this. One line in `backup_folders.txt`. | infra | XS | IDEA |
| 49 | DONE — **Sleep timer and keyboard control for the player.** Resume was the ask and it works; space-to-pause and a sleep timer are what make it something you would actually listen to a novel on. Shipped: `agents/audiobook/audio_player.py` has a sleep timer, chapter and saved-mark navigation, and space/arrow-key controls (TODO.md). | feature | S | DONE |
| 50 | DONE — **Make Video's visual provider/model choice real.** Current GPT Image models run through the scene pipeline; Gemini Omni/Veo, Qwen/Wan and Higgsfield create direct clips; Pexels and Local select their actual visual sources. Retired DALL·E and Sora IDs and providers without a video-output API are not offered. | feature | M | DONE |
| 52 | DONE — **Documentation centre.** Searchable technical reference browser (`ui/docs_center.py`) driven by `docs/agents/manifest.json`, opened from both the header Docs button (active agent) and the right rail's general Docs button (shared-system overview). | docs | M | DONE |
| 53 | DONE — **Learning Centre v2 / Income Lab.** Replaced the five-page guide with a 26-lesson manifest-driven academy built around an evidence-gated income methodology (label evidence → pre-register a fair experiment → unit economics → honest attribution → decide under uncertainty → automate only after the gates pass), rather than dated per-stream/platform earnings figures. | docs | L | DONE |
| 54 | DONE — **Structured status cards.** `ui/status_cards.py` replaced the collapsed System/Routing/API-key panels' prose with scannable rows, state badges and a separate "last decision" vs. "best fit recommendation" view. | design | M | DONE |
| 55 | DONE — **Suno-assisted Songs & Albums.** A new Music tab drafts lyrics and Suno-ready style prompts, hands off to the user's own Suno account for generation (no API key, no auto-generation), and imports the downloaded audio into the music library. | feature | M | DONE |

## v3 — bigger swings

| # | Suggestion | Category | Effort | Status |
|---|---|---|---|---|
| 8 | Local model provider (Ollama) as a zero-cost fallback when the budget cap is hit. Shipped 2026-09-30 as an offer at the refusal, never a silent re-route; see TODO.md. | feature | L | DONE |
| 9 | Retry-with-backoff wrapper shared by every provider client, instead of per-client handling | infra | M | IDEA |
| 10 | Export a run (prompt + response + usage + cost) as a single markdown file for archiving | feature | S | IDEA |

## Done

| Suggestion | When |
|---|---|
| Three colour themes — Green (Matrix), Red, Blue (Cyberpunk) — picked from three dots in the header or Settings → General → Appearance; only accent, phosphor and grey tint change, status colours never do; plus an underscore caret in editable text fields (`ui/theme.py`, `ui/vibe.py`, `aec5342`) | Oct 2026 |
| #49 Audiobook player sleep timer and keyboard control (`4e0fdb6`) | Sep 2026 |
| #42 Project as the shared production object — work identity and Write state, cross-agent output links and Project views, immutable approved manuscript versions, fingerprinted exports, and clearly self-reported retailer submission notes | Sep 2026 |
| Documentation centre + Learning Centre v2 / Income Lab — searchable technical reference browser, and a 26-lesson evidence-gated income academy replacing dated forecast-style earnings guidance | Sep 2026 |
| Structured System/Routing/API-key status cards replacing collapsed diagnostic paragraphs | Sep 2026 |
| Suno-assisted Songs & Albums workflow in the Music agent | Sep 2026 |
| Agents renamed to role-based, self-explanatory labels — `Draft`/`Publish` → `Book Author`/`Publishing Manager`, `Music` → `Music Artist Generator`, `Site Builder` → `Web Developer`, `Audiobooks` → `Audiobook Producer`, `Client Gigs` → `Brand & Logo Designer`, `Creator` → `Brand Creator`, `Social` → `Social Media Campaign Manager` — and matching workspace groupings (`Write` → `Author`, `Audio` → `Audio + Music`, `Video` → `Video + Ads`, `Gigs` → `Brand Design`) in `agents/catalog.py`'s `AgentSpec`. Resolves the `Write`/`Draft`/`Publish` naming collision tracked in TODO. | Sep 2026 |
| Video mode — vidforge as an eighth agent, imported from its nested repo rather than vendored; long-form and social clips are one pipeline | Sep 2026 |
| Social mode — the public funnel: campaigns, per-platform drafting, cadence scheduling, and posting for YouTube/Reddit/Pinterest | Sep 2026 |
| Per-unit billing — images, renders and TTS count against the budget caps instead of pricing a $0.04 image at €0.000001 | Sep 2026 |
| `main.py --selftest` — the packaging traps AGENTS.md names, plus proof that vidforge shipped in the bundle | Sep 2026 |
| GUI overhaul — header bar plus two fixed rails instead of a splitter; every panel rebuilt on `ui/forms.py`; one control height enforced in the stylesheet; 58 emoji and 36 colon captions removed; spend as stat blocks and budget bars | Sep 2026 |
| The Gigs and Video image model is a control using the current GPT Image catalog rather than a hardcoded retired DALL·E call; `generate_image()` returns bytes so every model has one caller | Sep 2026 |
| Refactor Phase 3 — `ui/host.py`'s `AgentHost` protocol and `ui/panels/base.py`'s `AgentPanel`, absorbing the five `*_load_models` methods | Sep 2026 |
| `_pending_requests` keyed by request token instead of agent name — two concurrent runs of one agent no longer clobber each other's context | Sep 2026 |
| Kimi prompt caching — `cached_input_per_1m_usd` on the pricing table, captured from the response and billed at the cached rate. Uncovered a bigger bug while wiring it up: the pricing table had no reconciliation path against `config/pricing.json` outside first-run migration, so Kimi/OpenAI/DeepSeek/Gemini were all silently billing €0.00 on this project's own database. `_seed_pricing_from_json()` now reconciles on every launch. | Sep 2026 |
| Cleaned up `main.py` dead code left by the security-vertical strip (unreachable icon/label dicts, the `osint` keyword branch relabelled rather than removed since it's a prompt-keyword branch, the `agent_box` combo no longer injects `"manager"`) | Sep 2026 |
| Pruned `Imprint.spec`'s stale `whois`/`dns` hidden-imports, left over from the deleted `providers/domain_lookup` | Sep 2026 |
| `docs/agents/course.md` reference page for the CLI-only Primer | Sep 2026 |
| Removed the dead `ops_identity` sidebar entry (gone by the time this was checked — likely swept up in the security-vertical strip rather than fixed deliberately) | Aug 2026 |
| Saved Chats: agent filter and rename | Aug 2026 |
| `authorize_request` / `record_request` guard applied to all 19 unguarded `ChatWorker` sites | Aug 2026 |
| `FlowLayout` on 13 control rows — panels no longer crush when narrow | Aug 2026 |
| Timeouts on all cloud clients | Aug 2026 |
| Phase 1+2 of the refactor: `ui/workers.py`, `ui/widgets.py`, `ui/style.py`, `ui/tooltips.py`, `ui/dialogs.py` | Aug 2026 |

## Rejected

| Suggestion | Why |
|---|---|
| Fork the ROI / investment agents back in | They moved to SONAR on purpose; two homes for the same logic is worse than one |
