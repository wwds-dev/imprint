# Muse

Owns shared content production for Imprint ventures: voice profiles, concepts,
captions, campaigns, promotional assets and the plan calendar.  Its public API
is `agents.creator` (see `__init__.py` for the exact re-exports).

Muse is platform-neutral.  Account consent records, platform-policy review,
statement import, per-asset revenue and the agency view were removed on
2026-09-30 — **Backstage** (`active/backstage`) owns that work, shares no code
or data with this app, and a test enforces the boundary.  User guidance:
`docs/agents/creator.md`.  Run focused coverage with
`pytest tests/test_creator_agent.py tests/test_creator_v2.py`.

Projects are optional work associations, not platform accounts. A scheduled
draft keeps the Project and account captured when generation was approved;
switching accounts before scheduling is refused. Teaser jobs and imported or
generated media can also be linked to a Project. Deleting that Project unfiles
content and jobs but does not delete the account, its voice and character
records, or media.
Calendar and Media default to all work under the selected account; each has a
**Current Project** view for linked content or files.

## Files

- **`__init__.py`** — the package's public surface: re-exports
  `CreatorAgent` and the constants `KINDS` and `PROMO_CHANNELS`. Callers
  should import from the package, not `agent.py` directly.

- **`agent.py`** — the implementation. Muse is a drafting tool, not an
  unattended publisher — it has no send path, because automation that
  *replaces* a human rather than assisting one risks the account. Key pieces:
  - `KINDS` — every draft type Muse can produce (`post`, `caption`,
    `posting_plan`, `promo_assets`, `promo`, `bio`, `campaign`, `hooks`),
    each mapped to the description injected into the prompt. `ppv` and
    `welcome` were subscription-platform messages and went to Backstage.
  - `PROMO_CHANNELS` — the off-platform channels ("X / Twitter", "Reddit",
    "TikTok", "Instagram", "Threads") promo drafts target, since a
    destination account is a poor discovery surface on its own.
  - `_account_context(account)` — the per-account framing block: the handle,
    its platform or venture, and any account notes.
  - `SYSTEM_PROMPT` — the ground rules every draft operates under: it's for
    human review before sending; no fabricated claims, false scarcity, or
    fake testimonials; a written character stays fictional; zero tolerance
    for any minors framing.
  - `CreatorAgent` — the class the rest of the app calls:
    - `build_messages(prompt)` — wraps a prompt with `SYSTEM_PROMPT`.
    - `build_draft_prompt(account, kind, brief, *, channel="")` — the main
      entry point. Assembles account context, the character bible and
      voice-sample block (via `agents.creator.profile.persona_block` /
      `voice_block`) — the voice block is what keeps output from reading
      like generic AI copy — the requested `kind`, promo-channel framing,
      and finally the brief itself. The character block is applied whenever
      a record exists: it used to be gated on an account type that no longer
      exists, and a recorded character is itself the signal to stay
      consistent.
    - `build_video_prompt(account, brief)` — builds a Higgsfield
      teaser-clip prompt. Deliberately safe-for-work only (Higgsfield
      moderates prompts, references and output, and prohibits explicit
      material), and pulls the locked `appearance` via
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

- **`panel.py`** — owns the complete Muse workspace: the profile
  form, the compose controls, and all four tabs (Draft, Calendar, Voice,
  Media) with every handler, moved here
  from `main.py` in the Phase 4 extraction. Request tokens live on the
  panel — "creator" is shared by the text drafting flow and the Higgsfield
  teaser (whose token rides in its own job context) — so nothing resolves a
  request by agent name alone. The Voice/character tab reads and writes
  through `profile.py`. The old
  `setattr(host, name, ...)` alias loop that mirrored every `HOST_CONTROLS`
  widget onto the umbrella was retired 2026-09-21 (commit `8de6d7c`) — shared
  code that used to read `window.<control>` directly now goes through
  `host._find_control()`; `HOST_CONTROLS` stays defined as the published
  contract of what this panel owns. Workers (chat generation, video estimate,
  video render) stay host attributes so the umbrella's global shutdown sweep
  keeps seeing them.

- **`calendar.py`** — Qt-free week-calendar logic for the Calendar tab,
  imported into `panel.py` as `content_calendar`. `parse_scheduled(text)`
  tolerantly reads every ISO shape the app has ever written and returns
  `(when, has_time)`; anything else (legacy free text typed into the old
  input box) returns `None` so those items surface in the Undated lane
  instead of being guessed at. `week_start`/`week_label`/`day_headers` do
  the week arithmetic with hard-coded English day/month names, since Qt
  resets `strftime`'s locale to the OS's and the calendar header shouldn't
  change language with it. `export_ics(rows, path)` writes RFC 5545
  VEVENTs — line-folded, UTC `DTSTAMP`, a date-only item gets
  `DTSTART;VALUE=DATE` instead of an invented time — and returns
  `(written, skipped)`, since an undated row can't become an event without
  inventing one. `export_csv(rows, path)` writes every row, dated or not,
  defusing any cell whose first character would trigger spreadsheet
  formula execution.

- **`profile.py`** — voice profiles and persona bibles, kept out of `agent.py`
  so the prompt builder stays about prompts and this stays about storage.
  `load_voice`/`save_voice`/`voice_block(account_id)` hold an account's own
  writing samples (capped at `MAX_SAMPLES=6`), tone, emoji style, banned
  words and typical length — `voice_block()` is what stops drafts reading
  like generic AI copy, since the model is shown how the account actually
  writes rather than told to be "engaging." `load_persona`/`save_persona`/
  `persona_block(account_id)` hold a written character's appearance,
  backstory, personality and boundaries plus a locked `seed` and
  `reference_images`, so repeated Higgsfield renders stay the same character
  rather than drifting between requests; `save_persona` explicitly preserves
  any field the caller doesn't pass (a past bug wiped `reference_images` on
  every save by defaulting every omitted field to `""`).

## Removed on 2026-09-30

`platform_policy.py`, `earnings_csv.py` and `insights.py` were deleted with the
Earnings and Agency tabs, the `ui/creator_*` dialogs and views, and the
account-type and consent model in `agent.py`. **Backstage** already held the
reviewed platform-policy record, the statement importer, the consent gate and
the per-account comparison, and two implementations of one record is how they
drift apart.

The `creator_*` tables were left in the live database, and `creator_content`
keeps its `price_usd` and `revenue_usd` columns: dropping them would be a
migration on a user's data for no gain. Nothing writes or reads them now.

The pre-cut files are archived at
`~/Documents/lab/archive/imprint_creator_pre_cut_2026-09-30/`.
