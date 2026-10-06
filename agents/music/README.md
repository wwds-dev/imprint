# Label

Owns artist positioning, release setup, distribution planning, Spotify strategy
and income-roadmap generation.  Its public API is `agents.music.MusicAgent`.
Provider execution and project persistence stay in the umbrella.

User guidance: `docs/agents/music.md`.  Run focused coverage with
`pytest tests/test_agents_scenarios.py -k music` and `pytest tests/test_music_plans.py`.

The package owns the Music workspace layout and release-plan lifecycle in
`panel.py`, plus its **Songs & Albums** tab in `suno_panel.py`. Imprint still
owns provider execution, the shared spending guard and run history. The
host-control aliases were retired 2026-09-21 (Music was the first package to
drop them): shared tooltip/recommendation/context wiring resolves controls
through `host._find_control()`, and `HOST_CONTROLS` stays only as the
published contract of what the panel owns. Every generated release plan is
also stored as a record (`plans.py`), and self-reported outcomes of past
releases feed the next plan's prompt. See `SUNO_WORKFLOW.md`.

## Files

- **`__init__.py`** — the package's public surface: re-exports `MusicAgent`.

- **`agent.py`** — the implementation. `SYSTEM_PROMPT` casts the model as a
  Music Business Consultant and Spotify Artist Setup Specialist, and pins
  every response to one fixed five-section structure so output is
  consistent and directly actionable:
  1. **Artist Profile** — short bio (≤150 chars, Spotify header) and long
     bio (300–500 words), genre tags, artist description, 3 realistic
     "similar artists," plus the manual steps to paste the bio in and claim
     the Spotify artist profile.
  2. **Release Setup** — title options, track listing/order, per-track
     metadata descriptions, a release-date recommendation with reasoning,
     a cover-art brief, and an ISRC/UPC explainer, plus the pre-upload file
     checklist and distributor upload steps.
  3. **Distribution Guide** — a recommendation tailored to budget, release
     frequency, royalty split and verification needs, comparing DistroKid,
     TuneCore and CD Baby on pricing/royalty %/pros-cons, plus the signup
     and territory/rights/pre-save walkthrough.
  4. **Spotify Strategy** — an editorial playlist pitch (≤500 chars, the
     Spotify limit), a Canvas video brief, a profile-optimization checklist,
     and 5 curator-type targets, plus how to submit the pitch and Canvas
     (minimum 7 days before release).
  5. **Income Roadmap** — streaming payout math at $0.003–$0.005/stream
     projected at 1k/10k/100k streams, revenue streams beyond streaming
     (sync, merch, live, Patreon/Bandcamp, YouTube Content ID, TikTok/Meta
     licensing), a Month 1/3/6 priority list, and tracking tools, plus payout
     setup and PRO registration (ASCAP/BMI/SESAC/PRS/SOCAN) and SoundExchange
     steps.

  Every AI-generated block is marked `[AI OUTPUT — COPY-PASTE READY]` and
  every manual step `[HUMAN ACTION REQUIRED]`, per the format rules. If the
  brief is missing artist name, genre/sound, release type/readiness, or
  distributor status, the prompt directs the model to ask rather than
  invent. It is also told never to invent Spotify features that don't exist
  and to flag anything that may have changed since its training cutoff.

  `MusicAgent` is intentionally the simplest agent class in this codebase:
  - `build_messages(prompt)` — wraps a prompt with `SYSTEM_PROMPT`. There
    are no specialised builder methods (unlike Creator or Publish); the
    entire five-section behaviour lives in the one static system prompt.

- **`suno_panel.py`** — the "Songs & Albums" tab: drafts lyrics and
  Suno-ready style prompts from a title/track-count/brief through the shared
  budget/permission-gated request path, lets the user edit and copy them into
  their own Suno account (no API key, no auto-generation — Suno's own
  generation/download costs are not tracked here), then imports the
  downloaded audio into `data/music_library` (via
  `services.runtime_paths.user_data_base()`) without moving the originals.
  Each album folder holds its audio plus an `album.json` recording title,
  brief, lyrics/prompts and track order. See `SUNO_WORKFLOW.md`.

- **`panel.py`** — the Music workspace's form, provider/model pair, action row,
  six result tabs, and guarded request/result lifecycle. The umbrella composes
  `MusicPanel`; it no longer defines Music's layout or plan handlers in
  `main.py`. A rejected paid request leaves Generate available.
  **Generate Plan** prepends `plans.outcomes_context(artist)` to the prompt
  when the artist has releases with recorded outcomes, and on completion
  stores the plan with `plans.save_plan()` (status line: "tabs populated and
  stored"); **Save Full Plan** remains a plain-text export. **Record
  Outcome…** refuses an empty Artist field, then opens a dialog listing that
  artist's last 10 stored plans (dated, marked when an outcome already
  exists, prefilled from stored numbers) so the user picks the plan that
  actually shipped and enters streams / revenue (USD) / notes; an all-blank
  entry records nothing.

- **`plans.py`** — structured release plans in the `music_release_plans`
  table (schema in `services/database.py`), Qt-free. `save_plan()` stores
  the inputs (artist, genre, release type, distributor, audience,
  description), the full prose, the parsed sections as JSON and the owning
  Project id; `get_plan()` and `list_plans(artist=, project=, limit=)`
  (newest first) read them back; `record_outcome()` writes self-reported
  streams, revenue and notes (no platform API is wired);
  `outcomes_context(artist)` builds a compact "Past releases and measured
  outcomes (self-reported…)" block from the artist's newest plans that
  actually have an outcome, and returns an empty string otherwise so a
  debut's prompt is untouched. Covered by `tests/test_music_plans.py`.

- **`recommendations.py`** — registers Music's `RECOMMENDATION_PROFILE` (an
  `AgentProfile` from `services.recommendations.models`) with the shared
  model-recommendation engine: task tags `creative` / `planning` /
  `marketing`, using the engine's default quality/reliability/cost/speed
  weights (no overrides passed), and only overriding `provider_affinity` —
  ranking Anthropic (.98) above OpenAI (.91), Gemini (.88), Qwen (.83),
  Kimi (.82), DeepSeek (.78), with Ollama (.68) included as a local
  fallback option.
