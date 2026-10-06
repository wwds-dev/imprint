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

## Files

- `__init__.py` — public interface; re-exports `AudiobookConnector` and lazily
  exposes `AudiobookPanel` so converter/CLI imports do not require Qt.
- `agent.py` — `AudiobookConnector.parse_input(text)` parses a `key=value`-per-line
  config block into a dict with defaults (`voice="alloy"`, `chunk_tokens=1500`),
  and raises `ValueError` if `input=` or `output=` is missing.
- `panel.py` — owns the Convert and Listen layouts, source discovery, exact-text
  cost estimation, paid conversion authorization/process/result lifecycle,
  library scan, resume and playback actions, wiring `audiobook_library.scan()`
  into the Listen table and hosting one `audio_player.AudiobookPlayer` for
  playback. Host-control aliases were retired 2026-09-21: the panel no longer
  mirrors its widgets onto the umbrella (`HOST_CONTROLS` stays only as the
  published contract of what it owns); shared consumers such as the
  voice-recommendation install now resolve controls through
  `GodAI._find_control()` instead.
- `audio_player.py` — `AudiobookPlayer`, a self-contained `QMediaPlayer` widget:
  transport controls, scrubber, playback speed and a sleep timer, plus a
  Chapters & marks menu over embedded chapters and saved marks. A resume
  position is only applied once the media reports `LoadedMedia`/
  `BufferedMedia` (an earlier seek is silently dropped), and the playhead is
  persisted on a 5s timer and on pause/stop rather than only on clean exit —
  a bare `position <= 0` is never written, since both "not loaded yet" and
  "just stopped" report position 0.
- `audiobook_library.py` — the audiobook library and its per-book resume
  state: `scan(folder)` recursively lists audio files with saved progress
  attached; `save_position()`/`load_position()` persist the playhead keyed by
  file path rather than library index (files get renamed/re-converted, so an
  index would quietly point at the wrong book) and mark a book `finished`
  once played past 99% rather than parked at the last second;
  `embedded_chapters()` (via `ffprobe`), `saved_marks()`, `save_mark()` and
  `delete_mark()` back the Chapters & marks menu.
  `release()` (2026-10-06) saves the playhead, stops both timers, clears the
  source and drops the audio output. `stop()` ends playback but leaves the
  source set, and a `QMediaPlayer` holding a source keeps the FFmpeg backend's
  demuxer, decoder and renderer threads open — threads that are not `QThread`
  workers, so `GodAI.closeEvent`'s shutdown sweep never saw them. It now calls
  `release()` there. The same leak in `tests/test_audiobook_player.py` (six
  players, none released) wedged a full suite run for 25 minutes: a later
  `QComboBox.setStyle()` deadlocked in `QObject::disconnect` against the live
  audio threads. The tests build players through a `make_player` fixture that
  releases them, and four tests pin the method itself.
- `recommendations.py` — exports `RECOMMENDATION_PROFILE`, an `AgentProfile`
  (from `services.recommendations`) describing what this agent needs from an
  AI provider/model: tagged `narration`, `longform`, `reliability`, weighted
  toward reliability (0.32) and quality (0.38), with a strong affinity for
  OpenAI (0.95). It is discovered dynamically by
  `agents.recommendation_profiles.profile_for("audiobook")` and scored by the
  shared `RecommendationEngine` to recommend a provider/model for narration jobs.

User guidance: `docs/agents/audiobook.md`.  Run focused coverage with
`pytest tests/test_audiobook_player.py tests/test_request_guard.py -k audiobook`.
