# Brand Creator

Owns shared content production for Imprint ventures: voice profiles, concepts,
captions, campaigns, promotional assets, calendars, account consent and
performance-informed drafting.  Its public API is `agents.creator` (see
`__init__.py` for the exact re-exports).

Creator is platform-neutral.  User guidance:
`docs/agents/creator.md`.  Run focused coverage with
`pytest tests/test_creator_agent.py tests/test_creator_v2.py`.

Projects are optional work associations, not platform accounts. A scheduled
draft keeps the Project and account captured when generation was approved;
switching accounts before scheduling is refused. Teaser jobs and imported or
generated media can also be linked to a Project. Deleting that Project unfiles
content and jobs but does not delete the account, consent, earnings or media.
Calendar and Media default to all work under the selected account; each has a
**Current Project** view for linked content or files.

## Files

- **`__init__.py`** — the package's public surface: re-exports `CreatorAgent`,
  `require_ready`, `ConsentError`, and the constants `ACCOUNT_TYPES`, `KINDS`,
  `PROMO_CHANNELS`. Callers should import from the package, not `agent.py`
  directly.

- **`agent.py`** — the implementation. Creator is a drafting tool, not an
  unattended publisher — it has no send path, which matters most for
  subscription platforms (few offer a public posting API, and automation that
  *replaces* a human rather than assisting one risks a ban). Key pieces:
  - `ACCOUNT_TYPES = ("own", "managed", "persona")` — the three account
    kinds, each carrying different obligations.
  - `KINDS` — every draft type Creator can produce (`post`, `caption`,
    `posting_plan`, `promo_assets`, `ppv`, `welcome`, `promo`, `bio`,
    `campaign`, `hooks`), each mapped to the description injected into the
    prompt.
  - `PROMO_CHANNELS` — the off-platform channels ("X / Twitter", "Reddit",
    "TikTok", "Instagram", "Threads") promo drafts target, since the
    subscription platform itself is a poor discovery surface.
  - `ConsentError(ValueError)` — raised when a `managed` account has no
    recorded consent holder.
  - `require_ready(account)` — the guard called before every generation.
    Validates `account_type` is known and, for `managed` accounts, that a
    `consent_holder` is recorded, so an agency cannot quietly accumulate
    accounts nobody authorised.
  - `_account_context(account)` — builds the per-account framing block: own
    accounts write in the user's voice, managed accounts write in the
    consent holder's established voice without inventing biographical facts,
    persona accounts stay explicitly fictional and surface their disclosure
    line.
  - `SYSTEM_PROMPT` — the ground rules every draft operates under: it's for
    human review before sending; no fabricated claims, false scarcity, or
    fake testimonials; personas stay fictional; zero tolerance for any
    minors framing.
  - `CreatorAgent` — the class the rest of the app calls:
    - `build_messages(prompt)` — wraps a prompt with `SYSTEM_PROMPT`.
    - `build_draft_prompt(account, kind, brief, *, price_usd=0.0,
      channel="", segment="", price_history="")` — the main entry point.
      Calls `require_ready` first, then assembles account context, the
      persona bible and voice-sample block (via
      `agents.creator.profile.persona_block` / `voice_block`) — the voice
      block is what keeps output from reading like generic AI copy — the
      requested `kind`, audience-segment notes
      (`agents.creator.profile.SEGMENTS`), PPV price / price-history
      framing, promo-channel framing, and finally the brief itself.
    - `build_video_prompt(account, brief)` — builds a Higgsfield
      teaser-clip prompt. Deliberately safe-for-work only (Higgsfield
      moderates prompts, references and output, and prohibits explicit
      material), and pulls a persona's locked `appearance` via
      `agents.creator.profile.load_persona` so repeated renders stay the
      same character rather than drifting between requests.

- **`recommendations.py`** — registers Creator's `RECOMMENDATION_PROFILE`
  (an `AgentProfile` from `services.recommendations.models`) with the shared
  model-recommendation engine: task tags `creative` / `marketing` / `social`,
  `reliability_weight=.23` and `speed_weight=.14` — both raised above the
  engine defaults (.20 / .10), since a bad draft or a slow turnaround both
  hurt a live content calendar — and a `provider_affinity` table ranking
  Anthropic (.98) and OpenAI (.96) above Gemini (.91), Qwen (.85), Kimi (.83)
  and DeepSeek (.78) for this task type.

- **`panel.py`** — owns the complete Brand Creator workspace: the profile
  form, consent-aware compose controls, and all six tabs (Draft, Calendar,
  Earnings, Voice, Media, Agency) with every handler, moved here
  from `main.py` in the Phase 4 extraction. Request tokens live on the
  panel — "creator" is shared by the text drafting flow and the Higgsfield
  teaser (whose token rides in its own job context) — so nothing resolves a
  request by agent name alone. The Earnings tab wires `earnings_csv.py`'s
  importer and `insights.py`'s outcome recorder to `CreatorEarningsView`; the
  Voice/persona tab reads and writes through `profile.py`; the account form's
  policy status/button go through `platform_policy.py`. The old
  `setattr(host, name, ...)` alias loop that mirrored every `HOST_CONTROLS`
  widget onto the umbrella was retired 2026-09-21 (commit `8de6d7c`) — shared
  code that used to read `window.<control>` directly now goes through
  `host._find_control()`; `HOST_CONTROLS` stays defined as the published
  contract of what this panel owns. Workers (chat generation, video estimate,
  video render) stay host attributes so the umbrella's global shutdown sweep
  keeps seeing them.

- **`profile.py`** — voice profiles and persona bibles, kept out of `agent.py`
  so the prompt builder stays about prompts and this stays about storage.
  `load_voice`/`save_voice`/`voice_block(account_id)` hold an account's own
  writing samples (capped at `MAX_SAMPLES=6`), tone, emoji style, banned
  words and typical length — `voice_block()` is what stops drafts reading
  like generic AI copy, since the model is shown how the account actually
  writes rather than told to be "engaging." `load_persona`/`save_persona`/
  `persona_block(account_id)` hold a synthetic persona's appearance,
  backstory, personality and boundaries plus a locked `seed` and
  `reference_images`, so repeated Higgsfield renders stay the same character
  rather than drifting between requests; `save_persona` explicitly preserves
  any field the caller doesn't pass (a past bug wiped `reference_images` on
  every save by defaulting every omitted field to `""`). Also defines
  `SEGMENTS` — the new-subscriber / loyal / lapsed / big-spender audience
  notes `agent.py.build_draft_prompt` injects into the brief.

- **`platform_policy.py`** — the reviewed, per-platform rule store behind
  `require_ready()`'s persona/AI-disclosure checks in `agent.py`. `get_policy`/
  `save_policy` persist whether synthetic personas and AI disclosure are
  `unknown` / `allowed` / `prohibited` for a platform, with `save_policy`
  refusing to record a definite (non-`unknown`) rule unless a source URL and
  a reviewed-on date are given — an unverified guess about a platform's rules
  is treated as worse than not knowing, per the module's own docstring
  ("unknown rules never imply permission").

- **`earnings_csv.py`** — statement importer for subscription platforms with
  no public API: `parse_creator_csv(path)` matches gross/net/subscriber/
  period columns by case-insensitive substring (header names differ between
  platforms and change over time) and keeps each parsed row's raw source data
  alongside the totals, so a number that looks wrong can be traced back.
  `ingest_creator_csv(account_id, path)` stores the parsed statement into
  `creator_earnings`, keyed on `(account_id, source_file)` so re-importing the
  same export updates it instead of double-counting revenue. Modelled
  directly on `agents/manuscript/kdp_csv_parser.py`, for the same reason.

- **`insights.py`** — the loop back from posted content to the next draft.
  `record_outcome(...)` attaches a manually verified outcome (reach, clicks,
  subscriptions, PPV purchases, revenue, attributable cost, source and
  measurement window) to a piece of content; `price_history(account_id)`
  summarizes revenue by PPV price point and feeds straight into
  `agent.py.build_draft_prompt`'s `price_history` argument, so a PPV price is
  pitched against what has actually converted rather than picked blind.
  Below `CONFIDENT_SAMPLE = 5` sends at a price point, the summary flags it as
  "(few sends)" rather than presenting an anecdote as a finding.
  `agency_overview()` backs the Agency tab (every account's net, subscribers
  and open drafts side by side); `commission()` splits a managed account's
  net between creator and manager at an agreed rate.
