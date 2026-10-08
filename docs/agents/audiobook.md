# AUDIOBOOK PRODUCER — Ebook → MP3 audiobook

`key: audiobook` · converter: `services/narrator/converter.py` · owner: `agents.audiobook.AudiobookPanel`

> Narrated by the route chosen in the **Narrator** menu — OpenAI, Gemini or ElevenLabs — regardless of the text provider selected elsewhere. Each route needs its own API key and its permission box.

## What it does
Converts `.pdf` / `.epub` / `.txt` / `.mobi` / `.azw3` ebooks into MP3 audiobooks: extracts text, chunks it, synthesises speech with the selected narrator, and stitches the audio — running as a background process so the GUI stays responsive.

## Inputs (panel controls)
| Control | Purpose |
|---|---|
| Book list + Refresh | Books found in the configured input folder. |
| Use Project Book | Adds the selected named Project's latest supported Write export or saved TXT draft to the book list without changing the input folder. |
| Input / Output folders | Source ebooks, MP3 destination (Change to pick). |
| Narrator | OpenAI · gpt-4o-mini-tts, Gemini · 3.8 Flash TTS or ElevenLabs · Multilingual v2. Remembered between sessions. |
| Voice | Voices for the selected narrator. ElevenLabs lists the account's own voices, fetched in the background. |
| Chunk Tokens | Text per TTS call (default 1400) — trades API calls vs chunk size. |
| Start / Stop | Begin / kill the conversion. |

## Narrators
OpenAI removes `gpt-4o-mini-tts` on 2027-01-06 and offers no drop-in successor on `/v1/audio/speech`, which is why there is a choice at all.

| Route | Model | Voices | Key | Price (`config/pricing.json` → `per_unit_usd`) |
|---|---|---|---|---|
| OpenAI | `gpt-4o-mini-tts` | alloy, marin, cedar, verse, coral, sage | `OPENAI_API_KEY` | Token-billed, about $0.016 per 1k characters. |
| Gemini | `gemini-3.8-flash-tts` | Kore, Charon, Aoede, Puck, Leda, Orus, Fenrir, Zephyr | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | $0.0137 per minute of narration; $0.0272 from 2027-01-01, applied by a dated rate on the day. |
| ElevenLabs | `eleven_multilingual_v2` | The account's own, from `/v2/voices` | `ELEVENLABS_API_KEY` | $0.08 per 1k characters — about five times OpenAI for a whole book. |

A route without its key, its permission (`allow_openai` / `allow_gemini` / `allow_elevenlabs`) or a price on file starts nothing and says which is missing. A rate of 0 means unknown, not free.

Every conversion is **assessed before approval** across the narrators that can run, each priced for this book: the selected one at what the run still owes after cached chunks, the others at the whole book, because switching starts over. A switch is offered only when another narrator wins by at least one point. **Apply** switches the narrator and asks again; it never starts a run.

Chunks are cached per narrator. A book interrupted under one narrator is never resumed on another: the settings-changed question names the narrator it was started with. OpenAI books paused before the routes existed resume unchanged, because OpenAI's chunking did not change.

## Outputs
MP3(s) in the output folder + a live **Conversion log** — a collapsed section under the progress bar (chunk progress, resume state, quota/error detection). Progress bar reflects completed chunks. A completed MP3 is linked to the Project selected when conversion began; Listen still shows the shared output folder, not a Project-filtered library.

If the expected MP3 already exists, **Convert audiobook** does not send a new paid request. Open the file from Listen instead.

## How it works
The converter runs as a separate process via `QProcess`:
- **Dev**: `python -u -m services.narrator.converter --input ... --output ... --voice ... --chunk-tokens ... --format ... --provider ... --model ...`
- **Frozen app**: the bundle has no `python -m`, so it re-invokes its own executable with the `--narrator-worker` sentinel (intercepted at the top of `main.py`, which runs `converter.main()` and exits). Args are otherwise identical.

`converter.convert()` does extraction (pypdf / ebooklib / BeautifulSoup), tiktoken chunking, and parallel TTS calls. `TTS_PROVIDERS` holds each route's model, default voice, key names and a per-request character cap on top of the token budget: none for OpenAI (so its chunk boundaries are unchanged), 9,000 for ElevenLabs, 6,000 for Gemini. Gemini returns WAV, which ffmpeg encodes to MP3 per chunk so the cache and the merge work as for the other routes. The first chunk that fails stops the run: queued chunks are skipped rather than narrated and paid for, and the cache keeps everything finished for a resume.

## Under the hood — files & functions
| Location | Role |
|---|---|
| `agents/audiobook/panel.py` | Owns the Convert and Listen layouts, source discovery, exact-text estimate, guarded conversion process/result lifecycle, library scan, selection, resume and playback. |
| `services/narrator/converter.py` | `convert()`, `main()`, extraction + TTS + chunking; `TTS_PROVIDERS` defines the three routes. |
| `agents/audiobook/panel.py: NARRATION_ROUTES` | The Narrator menu: label, model, voices, key name and a one-line note per route. |
| `agents/audiobook/panel.py: start_conversion()/run_conversion()` | Checks the route's key and price, assesses the narrators, authorizes the paid request and builds the QProcess command (dev vs frozen branch). |
| `services/per_unit_pricing.py` | `gemini_tts_cost_eur()` (dated per-minute rate) and `elevenlabs_tts_cost_eur()` (per 1k characters, per model). |
| `providers/voice/elevenlabs.py: list_voices()` | The account's ElevenLabs voices for the Voice menu. |
| `agents/audiobook/panel.py: handle_stdout()/handle_finished()/handle_error()` | Streams logs, follows the converter exit-code protocol, closes the exact billing token, and reports done/blocked/paused/quota states. |
| `main.py` compatibility entries | Delegate older umbrella call sites to the owned panel; they contain no conversion implementation. |
| `services/tool_runner.py: run_audiobook()` | In-process convert path (used by ToolRunner). |
| `config/tools.json` (`audiobook.module`) | Points at the converter module. |

## Extend it
- **Per-chapter files**: have `convert()` emit one MP3 per chapter instead of stitching.
- **Another narrator**: add it to `TTS_PROVIDERS` (converter) and `NARRATION_ROUTES` (panel), give it a rate in `config/pricing.json`, and add the provider to Booth's `allowed_providers` in both `config/registry.json` (new installs) and the seeded `audiobook` row in `services/database.py` — the second is what `_reconcile_agent_providers` reads to add it to existing installs. The guard refuses a provider the registry row does not name.

## Requirements
The chosen narrator's **API key** and its permission box. A novel costs roughly $7–10 on OpenAI, about the same on Gemini through 2026 and twice that from 2027-01-01, and about five times as much on ElevenLabs. Booth's own daily cap ships at €10, which a whole ElevenLabs book exceeds — the guard refuses it until the cap is raised in Settings → Agents. `ffmpeg` on PATH (merging, and Gemini's per-chunk MP3 encode). Input folder configured in `config/tools.json`.

---

## Listening (the Listen tab)

Converting a book used to be the end of it: the MP3 existed and nothing in the
app could find or play it. The **Listen** tab is the other half.

- **Library** — a recursive scan of the configured output folder for audio
  files (`.mp3 .m4a .m4b .wav .aac .flac .ogg`), showing progress, position and
  when each was last played.
- **Player** — play/pause, 30-second skips, a scrubber and playback speed from
  0.75× to 2×, built on `QMediaPlayer`.
- **Resume** — the button reads *Resume at 1:24:03* and picks up exactly there.

### How resume works, and the two traps

Position is keyed by **file path**, not by a library index: the library is a
directory scan, and files get renamed, moved and re-converted, so an index would
quietly point at the wrong book.

It is saved **on a five-second timer as well as on stop**, because people close
laptops and quit apps — a resume that only survives a clean exit is not a
resume.

Two bugs found by actually playing a file, each of which silently defeated the
whole feature:

1. **`stop()` overwrote the position it had just saved.** `QMediaPlayer` resets
   position to 0 on stop, and the resulting state change called the save path
   again. Every listen recorded 0 and nothing ever resumed. The player now
   never persists a zero; starting over is an explicit action instead.
2. **The resume seek was applied too early.** `durationChanged` arrives before
   the media is seekable, so the seek was accepted and then discarded, and
   playback began from the beginning while appearing to work. It now waits for
   `LoadedMedia`.

A book played to ~99% is marked **finished** rather than parked at the last
second, so the next play starts from the beginning rather than resuming and
immediately stopping. **Start Over** clears that flag.

| Location | Role |
|---|---|
| `agents/audiobook/audiobook_library.py` | Scan, resume bookkeeping, time formatting. |
| `agents/audiobook/conversions.py` | Durable conversion ledger: chunk progress, per-run billing baseline, and the startup scan that surfaces an interrupted book and settles its real partial spend. |
| `agents/audiobook/audio_player.py` | `AudiobookPlayer` widget. |
| `agents/audiobook/panel.py: _build_library_tab()` | The Listen tab layout and actions; the host retains compatibility entry points for workspace switching. |
| `audiobook_progress` table | Path, position, duration, finished, last played. |
