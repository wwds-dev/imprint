# Spec: Model updates also watch video and image routes

Status: Built and documented 2026-10-14 (uncommitted on `feature/model-watch-media`; see "As built" at the end). Defined 2026-10-14. Priority: P2 overall (feature). Part 4 (doc drift) is P2 and can ship alone today. Radar: `docs/company/radar-notes/2026-10-14-feature.md`. Product-manager playbook: `status: current`, last-reviewed 2026-10-14.

## Problem
Who: the single owner, who renders paid video and images through Gemini (Veo, Omni, Nano Banana), Qwen (Wan, Qwen Image) and Higgsfield (Seedance).
How it hurts: the Model updates tile only covers chat models. `NON_CHAT_MARKERS` (`services/model_watch.py:44`) drops every media id. `GeminiClient.list_models_live()` also keeps only `generateContent` models, which excludes Veo and Imagen before the filter even runs. So a new video model, a vanished one, or a Seedance path that stops answering is first noticed when a render fails.
Evidence: Google retires the three Veo 3.1 previews at the **earliest** on 2026-10-22, 8 days from now (deprecations page, updated 2026-10-12). `media_catalog.py` already hand-codes that date. Sora's API was removed the same way, by hand. Two docs still say Higgsfield defaults to Seedance 1.0 Lite: `.env.example:16-18` and `README.md:2978` (the brief says ~2961). The code default is `seedance-2.5` (`services/higgsfield_client.py:60`).

Challenge:
- **New Seedance versions: cut.** Higgsfield publishes no machine-readable model list (radar). Scraping its docs is fragile and the content is untrusted. Keep path liveness only.
- **The Higgsfield probe is gated on a manual check.** `/estimate/<path>` is not in Higgsfield's public docs. That it is unbilled, and that it returns a 404 for a retired path, are both **not verified**. Build the probe only after the owner confirms both by hand (credits before and after).
- **Removals: only for ids Imprint offers.** Reporting every id that leaves a provider's list is noise. Flag a removal only when it is an id in `media_catalog.MODELS`, or a chat id the user has selected.

## Target user
The owner, at launch or on "Check now", asking: "Will the video or image route I am about to pay for still work, and is there a newer one?"

## Goal and success measure
Media news shows up in its own section of the Model updates tile, and no media id ever reaches a chat dropdown. Measure: this test list passes offscreen with `.env` scrubbed (`tests/conftest.py:92-113`) and with fakes for every client. No network call is made in the suite.
1. Gemini or Qwen listings containing `veo-*`, `imagen-*`, `*-image*`, `wan*` or `qwen-image*` ids: the first look records a silent baseline. An id added at a second look appears in `pending_media()`, never in `pending()`. No chat dropdown's item list contains any of them.
2. Dated-snapshot rule: `veo-3.1-generate-preview` known, `veo-3.1-generate-preview-001` added → no notice.
3. Removal: an offered id present at look N and absent at looks N+1 **and** N+2 → one removal notice. Absent once → none. An empty or failed list → none. A provider with no key → never baselined and never "removed".
4. Upcoming shutdown: with a fake clock set within 14 days before (open question 3) `MediaModel.retires`, the tile lists that model with its date. The date is read from `media_catalog`. The test asserts that no second date literal exists (grep test: `"2026-10-22"` appears only in `media_catalog.py` and tests).
5. Higgsfield: with no key, or with `allow_higgsfield` unchecked, the probe client receives zero calls. With both set, it receives exactly one unbilled call per path in `SEEDANCE_ENDPOINTS` and **never** `generate_video` or a submit. A fake 404 → the tile shows "path not answering". A fake 5xx or timeout → "not checked", not "gone".
6. Existing `test_model_watch*` tests pass unchanged. An old v1 state file loads without losing chat baselines or pending notices.
7. Doc drift: `.env.example` and README name Seedance 2.5 as the default. `tests/test_env_template.py` still passes.

## Non-goals
Kling, Runway, Soul ID, new providers. OpenAI image ids (no change asked). Discovering new Seedance versions. Auto-switching a user's selected model. Adding newly found media ids to the Video workspace menus: `media_catalog` stays the only source of "has an execution path". Any billed render or test call. EU AI Act Art. 50 does not apply: this feature generates and publishes no content. CRA does not apply: no change to commercial availability.

## Scope
- `services/model_watch.py`: a media classifier alongside `is_chat_model`. The state gains a per-provider `media` record (seen, last_live, missing_count) and `pending_media` and `removals` lists. These are additive keys, so existing state is not reset. Do not bump `VERSION` without a migration, because a reset would discard pending chat notices. The docstring rules apply to media unchanged.
- `services/gemini_client.py`, `services/qwen_client.py`: new `list_media_models_live()`. For Gemini, this is an unfiltered `models.list`. For Qwen, it is the native `GET /api/v1/models` with capabilities `IG` and `VG` (the compatible-mode list is **not verified** to include them). Same key, and the same "live or exception" contract as `list_models_live()`.
- `services/higgsfield_client.py`: `probe_endpoint(path)` using the unbilled call the owner confirms (Q1).
- `main.py` `check_for_new_models` (:3894): add media listings to the scan. The Higgsfield probe requires `key_available()` and `current_api_permissions()["allow_higgsfield"]` (:3737; off by default, `tests/test_creator_v2.py:163`).
- The Model updates tile: a separate "Video and image" section (new / removed / shutting down / path not answering), dismissed through `acknowledge`-style calls.
- `.env.example:16-18`, `README.md:2978`: Seedance 2.5 default.
- `services/media_catalog.py:58`: soften `VEO_SHUTDOWN_NOTE` to "earliest shutdown", if approved (Q4).

## Open questions (owner)
1. Higgsfield: will you confirm by hand that `/estimate/<path>` is unbilled (credits unchanged) and returns 404 for a nonexistent path? Until then, should the probe ship disabled, or not ship at all?
2. Qwen media listing uses a second endpoint (`/api/v1/models`, native host). Is that acceptable? With a workspace ID set, does that host serve it? (**not verified**)
3. Shutdown warning window: 14 days before `retires`, or always shown once a date is known?
4. Google calls 2026-10-22 the "earliest possible" date. Soften the Veo note and the tile copy to match?
5. Removal of a chat model the user has selected: include it now, or keep removals media-only?

## Risks
- A truncated or regional list could produce a false "removed". Mitigation: two consecutive absences, and an empty list is ignored.
- An undocumented Higgsfield endpoint changes behaviour, and the probe either costs credits or reports a false "gone". Mitigation: Q1, and 5xx/timeouts never count as "gone".
- Media ids leak into chat menus through `model_list_cache`. Covered by measure 1.
- Veo shuts down on 2026-10-22, before this ships. Removal detection will then only confirm what `offered_models()` already does. The time-critical part is already handled in code.

## Owner decisions (2026-10-14, Define gate approved)
1. Higgsfield probe ships **off by default** until the owner has confirmed by hand that `/estimate/<path>` costs nothing and returns 404 for a missing path.
2. The extra Qwen call to native `GET /api/v1/models` is accepted; Build verifies the workspace host answers it and falls back silently (no notice) if it does not.
3. Shutdown warnings show as soon as a date is known, emphasised in the final 14 days.
4. Veo copy says "earliest shutdown 22 October 2026", matching Google's deprecations page.
5. Removal warnings cover offered media models **and** the currently selected chat model.

## Design (ux-designer, 2026-10-14)
Screen: the right-rail "Model updates" section (`main.py:3049`), widget `ModelUpdatesCard` (`ui/status_cards.py:360`). Reuse its object names and styles (`RailPrimaryValue`, `RailDetail`, `RailAvailability[status]`, `RailModelRow`, `RailCardButton`, `RailCardDivider`); add no new colours.

**User's question:** "Will the video or image route I am about to pay for still work, and is there a newer one?"
**Primary figure:** the media section's headline. Most urgent state wins: a removal or "not answering" first, then a shutdown within 14 days, then new models. Example: "Veo 3.1 shuts down in 8 days".

### Layout (top to bottom, one card)
1. Chat section, unchanged: headline, hint, rows (max 5), Update selected, result. A **removed selected chat model** shows here as the first row (see below). Media rows never go here, and never get the "mark for update" checkbox, because nothing auto-switches for media (non-goal).
2. Divider, then the field name `VIDEO AND IMAGE` (`RailFieldName`). Then its own headline (`RailPrimaryValue`) and up to 5 rows, ordered removed / not answering → shutting down (soonest first) → new. Overflow: "+N more video and image notices". The section is hidden when there is nothing to report **and** no offered model has a `retires` date. Today that cannot happen, because Veo has a date.
3. Media Dismiss button (see below), then the existing footer: Checked …, skipped/failed notes, ratings credit, Check now, Dismiss, startup checkbox.
- Section title (collapsed): "Model updates · 2 new · 1 warning". "warning" counts removals, paths not answering, and shutdowns within 14 days. Shutdowns further out do not count, so the collapsed title stays quiet.

### States and exact copy
| State | Where | Copy |
|---|---|---|
| Checking | Check now button (existing) | "Checking…"; the media headline keeps its last value |
| Never checked | media headline | "Not checked yet" |
| Nothing new, no warnings | media headline | "No video or image changes" |
| New media model(s) | headline / row | "1 new video or image model" / "N new video or image models". Row: provider label (bold), id (`RailModelId`), then `RailDetail` "Not in Imprint's Video menus yet — listed by {Provider}". This is true because `media_catalog` stays the only source of menu entries. |
| Offered media model removed (2 absences) | row, `RailAvailability[status=warning]` | "{Label} ({id}) is no longer listed by {Provider}. Renders with it will fail; pick another model in Video." |
| Selected chat model removed | chat section, first row, warning style | "{Provider} no longer lists {id}, which {Agent, Agent} use. Choose another model in their setup." No checkbox; it is cleared by Dismiss like other chat notices. If it reappears, the notice drops on its own. |
| Upcoming shutdown, more than 14 days out | row, `RailDetail` | "{Label}: earliest shutdown {d Month yyyy}" |
| Upcoming shutdown, 14 days or fewer | row, warning style; headline | Row: "{Label}: earliest shutdown {d Month yyyy} — in {n} days". With n = 1, "in 1 day"; on the day before, "tomorrow". Headline (when it is the top state): "{Label} shuts down in {n} days" (several: "3 Veo models shut down in 8 days"). Veo today: "Veo 3.1: earliest shutdown 22 October 2026 — in 8 days". Group the three Veo previews into one row when they share a date: "Veo 3.1, Fast and Lite: earliest shutdown 22 October 2026 — in 8 days". |
| On/after the date | row, `RailDetail` | "{Label}: past its earliest shutdown date ({date}); no longer offered in Video". Shown for 14 days after the date, then dropped. |
| Higgsfield path not answering (404) | row, warning | "Seedance {version}: Higgsfield's path is not answering. Renders on it will likely fail." |
| Higgsfield 5xx / timeout | footer (`skipped_label`) | Joins the existing "Could not reach: …" line as "Higgsfield (Seedance paths)". Never a row, never "gone". |
| Higgsfield probe off (default) | footer | "Seedance paths not checked: the Higgsfield check is off." Tooltip: "It turns on once its call is confirmed to cost nothing." Shown only when a Higgsfield key exists; with no key, Higgsfield joins the existing "No key, not checked" list. |
| Higgsfield permitted off | footer | "Seedance paths not checked: the Higgsfield chip under Paid media is off." |
| Provider media list failed / Qwen native host fallback | footer | Failures join "Could not reach: Gemini (video and image list)". The Qwen silent fallback (owner decision 2) shows nothing. |
| No key at all | footer (existing) | "Add a provider key to check for new models." |

Dates: always render as "22 October 2026" (`%-d %B %Y`), never ISO, in tile copy. The date value comes only from `media_catalog`, as measure 4 requires. Also update `VEO_SHUTDOWN_NOTE` to say "earliest" (owner decision 4): "Google may shut this preview down from 22 October 2026 (earliest date); Gemini Omni is its replacement."

### Acknowledge / dismiss
- The existing **Dismiss** clears chat notices only, as today, including a removed selected chat model. Its tooltip stays.
- A new **Dismiss** button (`RailCardButton`) sits under the media rows. Visible only when there are new or removed media notices. Accessible name "Dismiss video and image notices". Tooltip: "Clear new and removed video and image notices. Shutdown dates stay until the date has passed." It calls the media `acknowledge`.
- **Shutdown rows cannot be dismissed.** They are catalog facts with a deadline, not news. "Not answering" rows clear on their own when a later probe answers. Dismiss also hides them until the next probe result changes.

### Accessibility
- Not colour-only: every warning row starts with words that carry the meaning ("no longer listed", "shuts down in", "not answering"). The warning style is extra. The headline repeats the most urgent item in text.
- Contrast: `WARNING` on `WARNING_WASH` and `TEXT_DIM` on `SUNKEN` are already used in this tile. Build checks the 10–11 px text is at least 4.5:1 in light and dark themes. If a pair fails, use `TEXT` for the row's first line.
- Keyboard: media rows are not focusable (nothing to act on). The media Dismiss is in the tab order after the media rows and before Check now. Space/Return activate it.
- Screen reader: give each media row an accessible name with the full sentence, e.g. "Warning: Veo 3.1, Fast and Lite, earliest shutdown 22 October 2026, in 8 days". Ids elided by `ElidedLabel` keep the full id in the accessible name. Set the `VIDEO AND IMAGE` label as the group's accessible name. Update the card's accessible name to "New AI models and video and image changes from configured providers".
- Compact: there are no icons and no new widgets beyond one button, and rows follow `ModelNoticeRow` padding. The rail is 244 px wide, so the copy above is written to wrap to 2 lines at most.

## Architecture (architect, 2026-10-14)
Playbook `docs/playbooks/architect.md`: `status: current`, last-reviewed 2026-10-14. Radar `stack` note: no new dependency. No domain specialist is installed. **GATE: this touches persisted state (`data/model_watch.json`), a worker thread and a module boundary (`model_watch` now reads `media_catalog`).** The state decision is recorded in `docs/adr/0001-model-watch-state-additive-v1.md`.

### Approach
Media runs as a **second lane** beside the chat lane. It shares the worker, the state file and the tile, but never the chat cache, the chat slots or the chat menus. Each step lives in one place:

| Step | Owner (file → function) | Qt? |
|---|---|---|
| List media ids | `services/gemini_client.py` → new `GeminiClient.list_media_models_live()`; `services/qwen_client.py` → new `QwenClient.list_media_models_live()` | no |
| Probe Seedance paths | `services/higgsfield_client.py` → new `HiggsfieldClient.probe_endpoint(path) -> str` | no |
| Remember / decide | `services/model_watch.py` → `ModelWatch` (new methods below) | no |
| Shutdown dates | `services/media_catalog.py` → `MediaModel.retires` (sole source) | no |
| Order and copy rows | new `services/model_watch_digest.py` → `media_digest(watch, today) -> MediaDigest` (headline, rows, warning count) | no |
| Run off the GUI thread | `ui/workers.py` → `ModelScanWorker` (extended) | yes |
| Wire and gate | `main.py` → `check_for_new_models`, new slots, `refresh_model_updates` | yes |
| Paint | `ui/status_cards.py` → `ModelUpdatesCard.set_media(digest)`, `media_dismiss_btn` | yes |

**1. Media listing.**
- `GeminiClient.list_media_models_live()` is `self.client.models.list()` **without** the `supports_generate` filter (`gemini_client.py:150-162`). It returns ids that pass `model_watch.is_media_model`. Contract, unlike `list_models_live()`: with no client, or with an empty answer, it returns `[]`, **never `KNOWN_MODELS`**. A media baseline must never come from an offline list (docstring rule 2). An exception propagates.
- `QwenClient.list_media_models_live()` sends `GET {video_base_url()}/models` (`qwen_client.py:164-167`, the native `/api/v1` host or the owner's `DASHSCOPE_VIDEO_BASE_URL`). It uses `requests` with `REQUEST_TIMEOUT_SECONDS`, the DashScope bearer key, filter `capabilities` ∈ {IG, VG}, and follows pagination. The workspace host is not used: `video_base_url()` already ignores it, which is the same rule as Wan renders. A 404 or 405, or a body without the expected list shape, raises a dedicated `MediaListUnsupported`. Any other failure (401/403, 5xx, timeout) raises normally.
- **Silent fallback (owner decision 2):** when it gets `MediaListUnsupported`, the worker emits `(provider, [], "unsupported")`. `main.py` drops that silently: no footer, no observe, no miss counted. It does **not** fall back to the compatible-mode list. A partial list would count real models as missing, or announce them all as new once the native list answers.
- `offline_time` from DashScope is **not** used as a shutdown date. Dates stay single-sourced in `media_catalog` (measure 4). A later spec may surface it as a hint.

**2. Classification (P1 fix inside scope).** Add `MEDIA_MARKERS = ("veo", "imagen", "image", "wan", "nano-banana")` and `is_media_model(id)` to `model_watch.py`. `is_media_model` is true when a marker matches **or** the id is one of `media_catalog.MODELS`' ids. `is_chat_model` gains `and not is_media_model(id)`. This is needed because today `is_chat_model("gemini-nano-banana-2.1")` and `is_chat_model("gemini-omni-1.1-flash")` are both **True**: no marker matches. So Imprint's own media ids sit in the chat baseline and would never be media news. Impact: `services/recommendations/catalog.py:248` stops treating those two ids as text candidates, which is correct. Ids already in a chat `seen` list stay there, harmlessly. `model_watch` importing `media_catalog` is a new edge, but that is a pure data module with no Qt and no import side effects (its pricing imports are lazy).

**3. State growth (`ModelWatch`, file stays `VERSION = 1`; ADR 0001).** These are additive keys. `_load` adds `setdefault` for each one, and `_empty` includes them:
```
"media":         {provider: {baseline_at, seen[], last_live[], listed_at, missing{id: {count, day}}}}
"pending_media": [{provider, model_id, first_seen}]
"removals":      [{kind: "media"|"chat", provider, model_id, confirmed_at}]
"probes":        {path: {status: "answering"|"missing", at, dismissed: bool}}
providers[p]["missing"]  (chat lane, same shape as media)
```
New or changed methods:
- `observe_media(provider, ids, *, tracked=()) -> list[NewModel]`. It applies the same rules as `observe` (empty is ignored, the first look is a baseline, `canonical()` handles dated snapshots) against `media[p].seen`, and writes `pending_media`.
- `observe(provider, ids, *, tracked=())`. The new keyword defaults to `()`, so the panel-fetch call site (`main.py:3863`) and every existing test behave the same.
- `pending_media()`, `acknowledge_media(models=None)` (clears `pending_media` and media `removals`, and sets `dismissed` on current probe rows).
- `removals(kind=None)`. `acknowledge()` with no args now also clears chat removals; with a list it touches only `pending`, as today.
- `observe_probe(path, status)`, `probe_rows()`.

**Removal rule** (shared `_count_misses(record, listed, tracked, day)`):
- Only ids in `tracked` are considered. For media, that is `offered_models(today)` for the provider. For chat, it is the ids currently selected in `AGENT_SETUP_WIDGETS` for that provider, which `main.py` collects on the GUI thread. There is no global "everything that left" diff (spec challenge).
- An id is **present** when it, or any listed id with the same `canonical()`, is in the list. This stops `veo-3.1-generate-preview` from reading as removed when only its `-001` snapshot is listed.
- A miss counts only if the id was in the previous `last_live`, which proves the "present at look N" requirement. A selected chat model that was only ever in `KNOWN_MODELS` can never be "removed".
- **At most one miss per provider per UTC day** (`day` field). A miss counts only from a **Model updates scan**. Panel fetches pass no `tracked`. Without the day rule, the startup check plus one Check now would turn a single regional blip into a confirmed removal within minutes.
- `count == 2` → append one `removals` entry. Presence resets `count` and deletes any matching removal, so the notice "drops on its own" (Design).
- An empty, failed, unsupported or no-key list never calls `observe*`. So it can never baseline and never count a miss (measure 3).

**4. Migration of existing state.** A v1 file from today has `providers` (chat baselines), `pending` and `last_checked`. It loads unchanged. The new keys arrive through `setdefault`.
- **Baseline per lane:** `media[p]` is absent, so the first media look per provider is a **silent media baseline**, even though the chat baseline exists. That look announces nothing (measure 1).
- Existing `pending` chat notices are kept (measure 6).
- `missing` starts empty. The first removal therefore needs two further scan days after the update, by design.
- Rollback: the current build loads any `version == 1` dict and `_save` dumps the whole dict back (`model_watch.py:93-117`). Running an older build therefore keeps the media keys intact. A version bump would instead make every older build reset the file and lose pending chat notices.
- Corrupt file: the existing behaviour stays (start over). The cost is one silent re-baseline per lane, never a flood of notices.

**5. Shutdown dates, single source.**
- `model_watch_digest.media_digest(watch, today: date)` reads `media_catalog.MODELS` (all of them, not `offered_models`, because past-date rows show for 14 days after). It computes days-left, the 14-day emphasis and the "past" rows, and groups models with the same provider and the same `retires` into one row ("Veo 3.1, Fast and Lite").
- No module other than `media_catalog.py` holds the date. `VEO_SHUTDOWN_NOTE` is built **from `VEO_SHUTDOWN`** through a small `human_date(iso)` helper in `media_catalog` (`%-d %B %Y`). Then even the prose "22 October 2026" is not a second literal. Final text, per owner decision 4: "Google may shut this preview down from 22 October 2026 (earliest date); Gemini Omni is its replacement."
- Update the comment at `media_catalog.py:96` and the docstring at `tests/test_media_assessment.py:397` to "earliest".
- `today` is injected, defaulting to `date.today()`. This is a separate clock from `ModelWatch.clock`, which returns an ISO timestamp and stays as is.

**6. Higgsfield probe.** It runs only when **all** of these hold. They are evaluated on the GUI thread in a new `main.py` `_higgsfield_probe_allowed() -> str`, which returns `"ok"`, `"off"`, `"no_key"` or `"not_permitted"` for the footer copy:
- (a) `self.settings.get("model_watch_probe_higgsfield", False)` is true. It is off by default (owner decision 1), and no UI toggle ships in this change. The owner flips it in `settings.json` after the manual credit check.
- (b) `HiggsfieldClient().configured`. Note: the client has a `configured` property, **not** `key_available()` as the spec's Scope says. `main.py` holds no `self.higgsfield`, so the client is built per scan through an injectable `self._higgsfield_factory = HiggsfieldClient`.
- (c) `current_api_permissions()["allow_higgsfield"]`.
- (d) **The request guard's validator** passes: `self.validator.validate(agent_name="video", tool_name=None, provider="higgsfield", api_permissions=…, estimated_cost=0.0, …current spend/budgets as in authorize_request…)`. Build confirms the registry lets `video` use `higgsfield`. This reuses the guard's permission, agent and budget checks. It deliberately does **not** call `authorize_request`, which opens a confirmation dialog and reserves a token. A zero-cost background check must not prompt at launch, and the Video panel's own `/estimate` (`agents/video/panel.py:646-661`) is gated by the same key and permission checks today, also without `authorize_request`. If Q1's "unbilled" ever proves false, the off switch, not the guard, is the protection. That is why the switch exists.

What `probe_endpoint(path)` does:
- It sends one `POST /estimate/<path>` with a fixed minimal JSON body (`{"duration": <min bound>, "prompt": "status check"}`). It goes straight through `self._client().post` with a short `PROBE_TIMEOUT_SECONDS = 15` and **no retry**.
- It never calls `prepare_video`, because for image-to-video that runs `upload_file`, a network write. It also never calls `generate_prepared`, `generate_video` or a submit.
- Status mapping: 2xx, 400 or 422 → `"answering"` (the route exists, only the payload was judged). 404 → `"missing"`. 401, 403, 429, 5xx, `requests.Timeout` or `ConnectionError` → `"unreachable"`.
- `"unreachable"` is **never** stored and never becomes a row. It only adds "Higgsfield (Seedance paths)" to the session's `_model_scan_failed` (measure 5).

Probe scope:
- **Probe only the paths of Higgsfield models in `media_catalog.MODELS`** (seedance-2.5 and 2.0, which is 4 paths), not all of `SEEDANCE_ENDPOINTS`.
- This deviates from measure 5's wording ("every path in `SEEDANCE_ENDPOINTS`"), which would also probe the legacy `seedance-1.0-lite` paths. Imprint does not offer those, so they would produce permanent "not answering" noise. Measure 5 should read "every path of an offered Seedance model".

**7. Threading.**
- `ModelScanWorker.__init__(clients, media_clients=None, probe=None, probe_paths=())`. The defaults keep today's behaviour, and existing tests construct it positionally.
- `run()` order: chat lists as today, then media lists, emitted through a new `media_listed = Signal(str, list, str)`, then probes **one after another**, through `path_probed = Signal(str, str, str)` (model, path, status). Each step checks `_cancelled`.
- No probe can run concurrently with another:
  - They are sequential inside one worker.
  - `check_for_new_models` already refuses to start while `model_scan_worker.isRunning()` (`main.py:3903`).
  - The panel-fetch path never probes.
- A probe can overlap a user's own Video `/estimate` from `HiggsfieldEstimateWorker`. Both are reads of a price, so this is accepted.
- The worker stays a `DaemonWorker`. It holds no Qt objects and writes nothing locally, and if it is abandoned at quit mid-POST, an unbilled estimate costs nothing (and Q1 gates that assumption).
- `ModelWatch` is touched **only in GUI-thread slots**, as today, so the file has one writer and needs no lock. New slots: `_on_media_scan_listed(provider, models, error)`, which calls `observe_media` with `tracked` from `offered_models()`, and `_on_path_probed(model, path, status)`. `_on_model_scan_listed` passes `tracked=self._selected_chat_models(provider)`.
- `_on_model_scan_finished` is unchanged except that the early return in `check_for_new_models` (`if not clients`) becomes "no chat clients, no media clients and no probe". An owner with only a Higgsfield key still gets the probe.
- Two app instances (dev launcher and the built app) use different data dirs (`runtime_paths`). Two copies of the *same* build race last-writer-wins on write-then-rename. That race exists today and is not made worse.

**8. Chat dropdowns stay untouched.** The media lane never writes `model_list_cache`, never calls `_refresh_model_menus` or `_mark_new_models`, and its notices live in `pending_media`, which `is_pending()` does not read. So no NEW badge and no menu item can come from it. These are structural guarantees: separate signal, separate slot, separate state key.

**9. Tile.** `ModelUpdatesCard` gets one media block (a `RailFieldName` label, a headline, up to 5 rows, `media_dismiss_btn`) and a `media_dismissed` signal. `set_media(digest)` paints a `MediaDigest` and makes no decisions. All ordering and copy from the Design table live in `model_watch_digest.py`, so each copy row is a plain unit test. `refresh_model_updates` builds the digest and folds `digest.warning_count` into the section title. A removed selected chat model goes to the chat section as a first row without a checkbox. That needs a `ModelNotice` flag, `removed=True`, which `ModelNoticeRow` renders without `mark`. `marked()` and `update_selected_models` skip it.

### Alternatives rejected
- **Reuse `list_models_live()` and widen its filter.** That would change what every Gemini chat dropdown holds, and the Qwen compatible list is not known to contain Wan or Qwen Image ids at all (radar).
- **Bump `ModelWatch.VERSION` to 2 with a migration.** Every older build would reset the file (`model_watch.py:94`) on rollback and lose pending chat notices. The keys are additive, so no migration is needed (ADR 0001).
- **A second state file (`media_watch.json`).** It would give two baselines' worth of write-then-rename and `last_checked` to keep consistent. The lanes share a check timestamp and a dismiss model, so one file is simpler. Rejected, but cheap to revisit.
- **Probe through `authorize_request`.** It would pop a paid-request confirmation at launch for a call that is meant to cost nothing.
- **Take shutdown dates from DashScope `offline_time` or Google's page.** That makes two sources, and Google's `models.list` has no lifecycle field (radar).
- **Count removals from any listing.** Panel fetches would double-count within a session.

### Failure modes
| Failure | Behaviour |
|---|---|
| Gemini or Qwen media list raises | Footer "Could not reach: Gemini (video and image list)"; no observe, no miss |
| Qwen native host 404/405/odd shape | Silent skip (owner decision 2); no miss |
| Truncated or regional list | Needs 2 misses on 2 different days for a previously-present id; empty list ignored |
| Provider lists only a dated snapshot | `canonical()` match counts as present |
| Higgsfield 5xx/timeout/401/429 | Footer only; stored probe status unchanged |
| Higgsfield 404 | "not answering" row; clears when a later probe answers |
| Probe slow | Each probe is capped at 15 s, and probes run last, so chat and media results are already painted |
| State file corrupt | Starts over: a silent re-baseline per lane, no flood |
| Older build runs on the new file | Keeps the media keys (whole-dict round-trip) |
| Veo shutdown passes before this ships | `offered_models` already hides Veo; the digest shows the "past" row for 14 days |

### Test strategy (offscreen, `.env` scrubbed, no network)
Existing `tests/test_model_watch.py`, `tests/test_status_cards.py`, `tests/test_higgsfield_client.py` and `tests/test_media_assessment.py` stay unchanged and green. The exception is the one docstring wording in `test_media_assessment.py:397`, which is not an assertion. New or extended tests, by measure:
- **M1, M2, M3** (pure, `tmp_path` + `_Clock`): `observe_media` baseline, new, snapshot and the separation of `pending()` from `pending_media()`. Removal cases: two misses on two days → one removal; two misses on one day → none; empty list → none; never-present id → none; reappearance clears it; `tracked=()` → none.
- **Migration:** a v1 fixture file with chat `providers` and `pending` loads, the first media look is silent, and chat pending is intact (M6). A round-trip with the *current* `_load`/`_save` keeps the media keys.
- **Classifier:** `is_chat_model` is False for every `media_catalog.MODELS` id. A test also asserts that `recommendations.catalog` drops them.
- **M4** (pure): `media_digest(watch, today=date(2026,10,14))` gives the grouped Veo row with "in 8 days", plus the 1-day, tomorrow, past and >14-day copies. A grep test walks the repo's `*.py` (excluding `tests/`, `build/`, `dist/`) and asserts that `"2026-10-22"` occurs only in `services/media_catalog.py`. A test asserts `VEO_SHUTDOWN_NOTE` contains `human_date(VEO_SHUTDOWN)` and "earliest".
- **Clients:** `GeminiClient.list_media_models_live` with a fake `client.models.list()` that includes a Veo model without `generateContent` returns it; no client → `[]`. `QwenClient.list_media_models_live` takes a monkeypatched `requests.Session.get` covering a 200 paged list, a 404 → `MediaListUnsupported`, and a 500 → raises. Every test asserts the URL host equals `video_base_url()`'s host.
- **M5:** `probe_endpoint` with a fake session covers 200/422 → answering, 404 → missing, 500/Timeout/401 → unreachable. It asserts every posted URL starts with `/estimate/`, there is no `upload`, and no retry. In `main`, `_higgsfield_probe_allowed()` returns each of `off`, `no_key` and `not_permitted` with a factory fake that **records zero calls**. With everything on, there is exactly one call per offered Seedance path, and `generate_prepared` and `generate_video` are spies with zero calls.
- **Worker:** `ModelScanWorker(clients, media_clients=fakes, probe=fake)` is run and `wait()`ed as in `test_model_watch.py:225`. Signals arrive in order, and the probe calls never overlap (the fake asserts a non-reentrant flag).
- **M1, dropdown half:** in a `watched_window`-style fixture, a media-lane result containing `veo-*` and `qwen-image-*` leaves every `AGENT_SETUP_WIDGETS` model box's items and `model_list_cache` unchanged.
- **Mutation-check targets for Verify:** the `count == 2` threshold, the one-miss-per-day guard, the canonical-presence rule, the 404-vs-5xx mapping, and the 14-day boundary.

### Plan notes
- Part 4 (doc drift) and the **shutdown rows** need no network or new state beyond `media_digest`. They can ship first, before 22 October, so the owner sees the Veo warning in the tile in time. The listing, removal and probe work can follow.
- **Out of scope, flagged (P1, owner decision):** `model_list_cache` is written **unfiltered** (`main.py:3860`, `:3965`). Any non-chat id a chat listing returns (Gemini `generateContent` image models such as `gemini-3-pro-image`, which is **not verified live**) already reaches the chat dropdowns today. Measure 1's "no chat dropdown contains any of them" holds for the new media lane by construction. It does **not** hold for the existing chat lane unless both cache writes filter through `is_chat_model`. That is a one-line change each, but it alters chat dropdown contents, which this spec promised to leave untouched.

### After Build, docs likely out of date
README §Model updates (media section, probe setting), `.env.example` / README Seedance default (Part 4), `TODO.md` entry for the probe switch, and CHANGELOG.

## Owner decisions at Architect gate (2026-10-14, approved)
- Approved as written, including fixing the existing dropdown leak: filter `model_list_cache` writes (`main.py` ~3860, ~3965) with the corrected `is_chat_model` (which excludes every `media_catalog` id). This deliberately changes chat dropdowns only by removing non-chat ids.
- Measure 5 reworded: probe only paths of offered Seedance models.

## As built (tech-writer, 2026-10-14)
Checked against the working tree on `feature/model-watch-media`: `services/model_watch.py`, `services/model_watch_digest.py`, `services/media_catalog.py`, `services/higgsfield_client.py`, `services/gemini_client.py`, `services/qwen_client.py`, `ui/workers.py`, `ui/status_cards.py` and `main.py` (`check_for_new_models`, `_higgsfield_probe_allowed`, `refresh_model_updates`). The Design, the Architecture and both sets of owner decisions hold as written, except for the points below. User docs: README §5 *Model updates* (subsections *Removed models*, *Video and image*, *Seedance path check*), `docs/agents/overview.md`, CHANGELOG 2026-10-14.

Owner decisions, as built:
1. Probe off by default: `_higgsfield_probe_allowed()` returns `"off"` unless `settings["model_watch_probe_higgsfield"] is True`. Only the JSON value `true` turns it on; `"true"` or `1` do not. No UI toggle. The manual check is `TODO.md` item P2 `research` `@me` ("Confirm by hand that Higgsfield's `/estimate/<path>` costs nothing…").
2. Qwen native list: `QwenClient.list_media_models_live()` sends `GET {video_base_url}/models`, keeps capabilities `IG`/`VG`, pages 100 at a time up to 20 pages. 404/405 or a wrong shape raises `MediaListUnsupported`, which the scan drops silently. Still **not verified** against a live account.
3. Shutdown rows always show while a date is known, as warnings in the final 14 days (`SHUTDOWN_WARNING_DAYS`), and as "past" rows from the date itself for 14 days (`PAST_SHUTDOWN_DAYS`).
4. Copy: `VEO_SHUTDOWN_NOTE` is built from `VEO_SHUTDOWN` with `human_date()`: "Google may shut this preview down from 22 October 2026 (earliest date); Gemini Omni is its replacement." `"2026-10-22"` appears once, in `media_catalog.py`.
5. Removals cover offered media models (`offered_models(today)` per provider) and the chat models selected in `AGENT_SETUP_WIDGETS` (`_selected_chat_models`).
- Architect-gate decision: both `model_list_cache` writes (`_on_models_listed`, `_on_model_scan_listed`) keep only `is_chat_model` ids, and `is_chat_model` excludes every `media_catalog.MODELS` id.

Differences from the Architecture:
- **Gate order and a fifth result.** `_higgsfield_probe_allowed()` checks the key first (`"no_key"`), then the switch (`"off"`), then the Higgsfield chip (`"not_permitted"`), then the validator. A validator refusal returns `"refused"`, with the footer "Seedance paths not checked: the request guard refused the check (agent, budget or permission)."
- **At most once per UTC day.** New state key `probe_day`. `check_for_new_models` probes only when `probed_today()` is false, and calls `mark_probed(paths)` before the worker starts. `mark_probed` also forgets stored answers for paths no longer probed.
- **Stored answers are cleared when the probe may not run.** Any result other than `"ok"` calls `clear_probes()`, so a "not answering" row cannot outlive the check that found it.
- **Removal details.** The miss count is capped at 2, so a removal that was dismissed is not raised again while the model stays missing. A scan forgets counters for models it no longer tracks. Presence is read from the whole live list, chat or not (`valid_ids`), so a selected id that is no longer classed as chat is not "removed" while it is still listed.
- **Bounds.** Ids must match `[A-Za-z0-9._:/@+-]{1,128}`. At most 2000 ids are stored per list (`MAX_LISTED_IDS`), and `pending_media` keeps the newest 50 (`MAX_PENDING_MEDIA`).
- **Extra copy.** A new media id that is already in `media_catalog` reads "Already in Imprint's Video menus — listed by {Provider}". Headlines: a single removal is "{Label} is no longer listed"; a single path is "Seedance {version} path not answering"; several urgent items are "N video or image warnings". A removed chat model no agent uses reads "… Choose another model in the agent's setup."
- **Footer copy mismatch (fixed 2026-10-14 by the orchestrator; copy now names the chip).** The `"not_permitted"` footer says "Higgsfield is not permitted in Settings → Permissions." The switch it means is the **Higgsfield** chip under **Paid media** in the control bar (`main.py` `allow_higgsfield_checkbox`); there is no Settings → Permissions page. The README explains this; the copy itself is unchanged.

Not verified by this pass: that `/estimate/<path>` is unbilled and returns 404 for a missing path (owner TODO); that Qwen's native host serves `/api/v1/models` for this account; the 4.5:1 contrast check in the Design's Accessibility section.
