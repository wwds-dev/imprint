# Video & Ad Generator

Owns Imprint's video workflow: idea and script, visual-provider selection,
narration, direct generation, assembly, job status and output library.

Vidforge remains a separately versioned companion repository.  This package is
the ownership boundary for Imprint orchestration; `studio.py` is its adapter to
Vidforge.  User guidance: `docs/agents/video.md`.

Successful pipeline and direct renders also link their local clip to the
Project captured at request authorization; resumed provider jobs use the
Project ID persisted with the job. The shared vidforge Library defaults to all
renders, including standalone builds with no Imprint Project context; its
**Current Project** view filters to linked clips.

Run focused coverage with `pytest tests/test_media_generation.py tests/test_vidforge_contract.py tests/test_panel_layout.py -k video`.

## Files

- `__init__.py` — package ownership boundary: sets `AGENT_KEY = "video"`,
  re-exports `studio` as `video_studio`, and lazily exposes `VideoPanel` so
  non-GUI consumers do not import Qt.
- `panel.py` — owns the Render/Library workspace, provider/model constraints,
  preflight estimates, exact request tokens, pipeline and direct-provider
  lifecycles, safe cancellation semantics, progress, errors and the shared
  vidforge output library. It also owns `resume_pending_jobs()`/
  `_spawn_resume()`: run once per launch (a `_resume_started` guard blocks
  a second pass, which would double-reserve and double-bill), it restores
  each pending job's budget reservation via `host.restore_request()`
  (never re-asks — the spend was already approved pre-restart), watches
  it with `VideoResumeWorker`, and always settles the ledger row before
  billing so a crash in that window undercounts once instead of
  double-billing; when vidforge itself is unavailable, pending/lost rows
  are still surfaced as failures instead of being silently stranded.
  Host-control aliases were retired 2026-09-21: the panel no longer
  mirrors its widgets onto the umbrella (`HOST_CONTROLS`
  stays only as the published contract of what it owns); the umbrella now
  retains only thin compatibility delegates plus the worker attributes its
  global shutdown sweep watches, with shared consumers resolving controls
  through `GodAI._find_control()`.
- `jobs.py` — the durable `video_jobs` record behind direct-provider render
  resume: `record_submission()` writes the intent row before the create POST
  (so a row with no `job_id` means the app died between the POST and the
  provider's reply, not that money definitely moved); `update_job()` persists
  each provider transition; `mark_terminal()` closes a row while keeping
  whatever terminal status the provider already stamped; `pending_rows()`
  lists acknowledged-but-unfinished jobs for `VideoPanel.resume_pending_jobs()`
  to pick back up after a restart — keyed on `spend_state = 'reserved'`,
  not on provider status, since a completed-but-undownloaded job still
  needs settling; `sweep_lost()` marks never-acknowledged
  submissions `lost` and releases their budget reservation instead of
  silently billing or dropping them. Qt-free on purpose so tests and CLI
  tools can use it.
- `workers.py` — `VideoResumeWorker` (`QThread`), the resume half of the
  render workers (the submit-and-wait workers live in `ui/workers.py`):
  re-polls a persisted provider job by rebuilding the provider-specific job
  object (Higgsfield/Qwen from the saved job id, Gemini via `resume_video()`,
  since reconstructing that job is itself a network poll), then waits,
  downloads and reports completion — it only ever reads status and
  downloads, so resuming can never double-spend. A local poll timeout is
  tracked separately from a provider-reported terminal status, so a
  timed-out row stays pending for the next launch instead of being marked
  failed; the same goes for a local exception mid-poll (network/DNS/bad
  key), which sets `retryable` rather than being treated as a provider
  verdict, unless the provider had already reported completion first.
  `cancel()` is shutdown-only — it stops the worker watching, never
  cancels the render at the provider (`cancel_at_provider=False` for
  Higgsfield), so a closing window can't destroy a paid job; the row
  stays `reserved` and resumes again on the next launch.
- `studio.py` — the adapter to `vidforge`, a **separate git repository**
  nested at `imprint/vidforge/` and imported rather than vendored, so the
  standalone `vidforge.app` and Imprint's Video mode share one checkout, one
  config and one output history — "two front doors" onto one pipeline —
  instead of drifting apart the way the workspace's one existing
  vendored-copy pair (`lab_hub/tools/convert` vs `toolbox/convert_epub`)
  already has. Key surface:
  - `available()` / `unavailable_reason()` — `_load()` lazily imports
    vidforge's `config`, `pipeline` and `progress` modules and records any
    failure instead of raising at import time, so a checkout without
    `vidforge/` (or one missing PyYAML, or the YouTube-upload extras
    `google-api-python-client` / `google-auth-oauthlib`) gets an explanatory
    message in the panel rather than a crash on startup.
  - `ASPECTS` (Landscape 16:9, Vertical 9:16, Square 1:1) and `CLIP_SECONDS`
    (15/30/45/60/90) — the platform-native shapes and lengths the Social
    mode schedules clips against.
  - `clip_overrides()` — turns the long-form pipeline into a social clip
    purely through config overrides (render width/height, matching image
    size/orientation, and a `script.scene_seconds` floor of 6 for
    faster-cut short-form) rather than a second rendering path, since
    `produce()` already sizes every stage from `video.width`/`height`.
  - `load_config()`, `produce()`, `output_root()`, `library()` — load
    vidforge's `Config` (seeding `config.yaml`/`topics.txt` into the
    writable app-support directory on first run of a frozen build), run
    `pipeline.produce()`, and read vidforge's own output directory and
    build history, so a render started in the standalone app appears here
    too and vice versa.
  - `external_output_path()` / `record_external()` — reserve a slot in the
    shared vidforge library and write its manifest/history entry for a
    direct provider-rendered clip (e.g. Gemini, Higgsfield) that bypassed
    vidforge's own pipeline.
  - `pre_estimate()` — reproduces vidforge's own cost-estimate arithmetic
    (word budget from target seconds and words-per-minute, scene count from
    scene length, then script/TTS/image/caption cost) so the panel can show
    a cost figure *before* a script exists, using
    `services/media_catalog.openai_image_reserve_usd()` for per-image
    pricing when `visuals.source == "ai"`.
  - `stages()`, `reporter_base()`, `cancelled_error()`,
    `overall_fraction()` — expose vidforge's progress-reporting contract
    (stage list, `Reporter` base class, `Cancelled` exception, overall
    fraction) for the Qt worker in `ui/workers.py`.
- `recommendations.py` — registers this agent's `RECOMMENDATION_PROFILE` (an
  `AgentProfile` from `services.recommendations`) with the provider
  recommendation engine: task tags `video`/`creative`/`social`, weighted
  heavily toward quality (.44) with reliability (.23) and cost (.16), and
  per-provider affinity from gemini (.98) down to local (.62).
