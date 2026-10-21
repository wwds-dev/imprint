# Booth agent (`agents.audiobook`)

Owns ebook discovery, narration configuration, conversion progress, listening,
resume state and audiobook output management. Imprint imports its connector and
Convert/Listen workspace from `agents.audiobook`. Discovery, estimation,
conversion process lifecycle, billing closure, library and playback actions all
belong to that workspace; only shared budgets, usage storage, output and the
narration/library services remain on the umbrella side.

**Use Project Book** adds a named Project's linked Write TXT/EPUB/PDF to the
Convert list without changing the configured input folder. After a successful
conversion, the source (unless already linked) and verified MP3 are linked to
the Project active when Start was pressed. Listen still scans the global output
folder by default; **Current Project** shows only linked audiobooks.

Convert lists PDF, EPUB, TXT, MOBI and AZW3 sources (`SUPPORTED_EBOOKS` in
`panel.py`, matching `services/narrator/converter.py`'s `SUPPORTED_SUFFIXES`).
MOBI and AZW3 are turned into EPUB by Calibre first, so they also need
`ebook-convert` installed on the machine. AZW3 was added 2026-10-06 (`703c111`).

Narration has three routes since 2026-10-07 (`47c2434`), chosen in the
**Narrator** menu (`audiobook_route_box`, remembered under the
`audiobook_narration_route` setting) and defined in `NARRATION_ROUTES`, keyed
like the converter's `TTS_PROVIDERS`: OpenAI `gpt-4o-mini-tts`, Gemini
`gemini-3.8-flash-tts` and ElevenLabs `eleven_multilingual_v2`. OpenAI removes
`gpt-4o-mini-tts` on 2027-01-06 with no drop-in successor, which is why there
is a choice. The route is what the converter is told (`--provider`/`--model`),
what the guard authorizes, what the conversion row records and what the usage
log bills. Booth's seeded registry row names all three narrators; it used to
allow only openai/qwen, and since the launch reconciliation adds a provider
only when the seeded row names it, the guard would have refused both new
narrators on every existing install. Booth's own daily cap ships at €10, which
a whole ElevenLabs book exceeds; the assessment honours it as the guard does.

Since routing phase 0 (2026-10-19, `d4d39c1`) the retirement is in the code,
not only in a tooltip: the OpenAI route carries `retires` (`OPENAI_TTS_RETIRES`
= 2027-01-06). `offered_routes()` is what the Narrator menu and the assessment
list — every route whose model has not retired — and `default_route()` is the
first of those, used when no route is saved. `NARRATION_ROUTES` keeps a retired
route so a book narrated with it can still be named, priced and resumed. The
same rule lives in the converter (`default_tts_provider()`, in
`DEFAULT_ROUTE_ORDER` openai → gemini → elevenlabs), so from 2027-01-06 the
default narrator moves to Gemini with no code change. Neither `open_job()` nor
the converter command line hardcodes `gpt-4o-mini-tts` any more. Prices come
from `config/pricing.json`, the one price source.

The converter's own output (start banner, progress lines, `[Blocked]`/
`[Paused]`/`[Error]`/`[Done]` outcomes) appears in Booth's collapsible
**Conversion log** under the status line (2026-10-19, `21d957b`). It used to be
written into the Chat panel's output box, which Booth never shows, so the log
was invisible on Booth and visiting Booth overwrote whatever Chat was showing.

## Files

- `__init__.py` — public interface; re-exports `AudiobookConnector` and lazily
  exposes `AudiobookPanel` so converter/CLI imports do not require Qt.
- `agent.py` — `AudiobookConnector.parse_input(text)` parses a `key=value`-per-line
  config block into a dict with defaults (`voice="alloy"`, `chunk_tokens=1500`),
  and raises `ValueError` if `input=` or `output=` is missing.
- `panel.py` — owns the Convert and Listen layouts (each tab its own vertical
  scroll surface, so neither is squeezed in a short window), source discovery, exact-text
  cost estimation, paid conversion authorization/process/result lifecycle,
  library scan, resume and playback actions, wiring `audiobook_library.scan()`
  into the Listen table and hosting one `audio_player.AudiobookPlayer` for
  playback. Before approval, `start_conversion()` checks the route's key and
  price (a route without either starts nothing) and assesses every narrator
  through `host.assess_media_request(..., modality="speech")`: the selected
  one at what this run still owes after cached chunks, the others at the
  whole book, since a switch starts over. Apply switches the narrator and
  asks again; it never starts a run. ElevenLabs voices are the account's
  own, listed by a `VoiceListWorker` so a slow provider never freezes the
  panel. The narrator outcome checks in `handle_finished()` read the run's
  own `_run_output` buffer, filled from stdout alongside the
  `audiobook_log` widget, so nothing can clear it between Start and exit.
  Listen's **Save listening progress** and **Progress folder** are labelled
  fields on one control line; the folder field and its label hide together
  while progress is saved on this Mac.
  Host-control aliases were retired 2026-09-21: the panel no longer
  mirrors its widgets onto the umbrella (`HOST_CONTROLS` stays only as the
  published contract of what it owns); shared consumers such as the
  voice-recommendation install now resolve controls through
  `GodAI._find_control()` instead.
- `audio_player.py` — `AudiobookPlayer`, a self-contained `QMediaPlayer` widget:
  transport controls, scrubber, playback speed and a sleep timer (labelled
  **Speed** and **Sleep** fields, like every other form), plus a
  **Chapters && marks** button (`&&` so Qt shows a literal `&` instead of a
  mnemonic underline) over embedded chapters and saved marks. A resume
  position is only applied once the media reports `LoadedMedia`/
  `BufferedMedia` (an earlier seek is silently dropped), and the playhead is
  persisted on a 5s timer and on pause/stop rather than only on clean exit —
  a bare `position <= 0` is never written, since both "not loaded yet" and
  "just stopped" report position 0.
  `AudiobookPlayer.release()` (2026-10-06) saves the playhead, stops both timers, clears the
  source and drops the audio output. `stop()` ends playback but leaves the
  source set, and a `QMediaPlayer` holding a source keeps the FFmpeg backend's
  demuxer, decoder and renderer threads open — threads that are not `QThread`
  workers, so `GodAI.closeEvent`'s shutdown sweep never saw them. It now calls
  `release()` there. The same leak in `tests/test_audiobook_player.py` (six
  players, none released) wedged a full suite run for 25 minutes: a later
  `QComboBox.setStyle()` deadlocked in `QObject::disconnect` against the live
  audio threads. The tests build players through a `make_player` fixture that
  releases them, and four tests pin the method itself.
- `audiobook_library.py` — the audiobook library and its per-book resume
  state: `scan(folder)` recursively lists audio files with saved progress
  attached; `save_position()`/`load_position()` persist the playhead keyed by
  file path rather than library index (files get renamed/re-converted, so an
  index would quietly point at the wrong book) and mark a book `finished`
  once played past 99% rather than parked at the last second;
  `embedded_chapters()` (via `ffprobe`), `saved_marks()`, `save_mark()` and
  `delete_mark()` back the Chapters & marks menu.
- `conversions.py` — the durable, Qt-free record of conversions in the
  `audiobook_conversions` table: one row per book (source + output path),
  reused across runs, holding provider/model/voice/chunk settings, live
  chunk progress,
  `estimate_eur` (the whole-book estimate captured at first start),
  `billed_eur` (what has actually been logged) and `run_baseline` (where this
  run started). `find_open()` returns a book's unfinished row;
  `remaining_fraction()` is the unpaid share of it; `open_job()` reuses that
  row — when no provider is named it records the converter's current
  `default_tts_provider()` and its model, never a hardcoded one —
  (or `reset_progress=True` for a confirmed fresh start after changed
  settings — a different narrator counts as changed, so a book is never
  resumed on another narrator's cache) or creates one; `update_progress()`,
  `run_spend_eur()`,
  `settle()`, `get_job()` and `dead_runs()` complete the lifecycle. The panel
  uses it on Convert to authorize only the remaining fraction of the estimate,
  updates progress from the converter's stdout, settles before it bills on
  stop/failure/success, and `resume_pending_conversions()` (called from
  `main.py` at startup) settles rows the previous process died in and names
  every interrupted book in the status label. Any number of interruptions
  therefore converges on one estimate, never more.
  Covered by `tests/test_audiobook_conversions.py`.
- `recommendations.py` — exports `RECOMMENDATION_PROFILE`, an `AgentProfile`
  (from `services.recommendations`) describing what this agent needs from an
  AI provider/model: tagged `narration`, `longform`, `reliability`, weighted
  toward reliability (0.32) and quality (0.38), with a strong affinity for
  OpenAI (0.95). It is discovered dynamically by
  `agents.recommendation_profiles.profile_for("audiobook")` and scored by the
  shared `RecommendationEngine` to recommend a provider/model for narration jobs
  and to assess each conversion across the narrators.

User guidance: `docs/agents/audiobook.md`.  Run focused coverage with
`pytest tests/test_audiobook_player.py tests/test_audiobook_conversions.py
tests/test_booth_routes.py tests/test_narration_route_retirement.py`
and `pytest tests/test_request_guard.py -k audiobook`.
