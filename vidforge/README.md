# vidforge

Autonomously turns a topic into a finished, narrated, illustrated video:
script → voiceover → per-scene imagery → Ken Burns motion → burned-in captions →
music bed → thumbnail → metadata.

Output geometry is configuration, not a fixed target: the same `produce()` call
makes a long-form 16:9 video or a vertical 9:16 clip for social feeds and ads —
which is how Imprint's Social mode asks for clips without owning a pipeline of
its own. YouTube is the one *upload* integration (manual, behind two opt-ins);
everything else is a file you take where you like.

Also generates structured PowerPoint course presentations from topics or outlines.

Reached through Imprint's **Reel** agent, or from a CLI (`python -m
vidforge.cli`) for headless runs.

> **This is Imprint source.** Until 30 September 2026 vidforge was a separate
> git repository with its own `vidforge.app`; Imprint imported it, so one
> pipeline had two front doors writing one config, one output library and one
> history. The standalone app, its build script and its `launchctl` nightly job
> were removed, and the old repository's history is archived as a git bundle in
> `~/Documents/lab/archive/vidforge_standalone_2026-09-30/`. Three things still
> matter when changing anything here:
>
> * **`pipeline.produce()`, `progress.Reporter` and `config.Config` are a
>   public API.** Imprint's Qt worker subclasses `Reporter` and drives
>   `produce()` directly through `agents/video/studio.py`. Renaming a stage key
>   in `progress.STAGES` or changing `produce()`'s signature breaks the Reel
>   tab.
> * **Config keys are the extension point.** Imprint renders vertical social
>   clips by overriding `video.width` / `video.height`, `visuals.image_size`,
>   `script.target_seconds` and `script.scene_seconds` — no second code path.
>   Keep those keys working.
> * **This directory is also the data directory.** In a checkout `config.py`
>   resolves `PROJECT_ROOT` here, so `config.yaml`, `topics.txt`, `assets/` and
>   the render library live alongside the package — which is why the package
>   was not moved when the repository was absorbed. Frozen, `PROJECT_ROOT` is
>   `~/Library/Application Support/vidforge/`.
>
> `Imprint.spec` ships this package as source plus `config.yaml`, `topics.txt`
> and `assets/`.


```bash
python -m vidforge.cli run --topic "How undersea cables carry the entire internet"
python -m vidforge.cli doctor     # check tools, keys and dependencies
```

## The GUI

Imprint's **Reel** agent is the interface: topic, format, visual provider and
model, aspect and clip length, with a live stage log, a Library of everything
produced, and the shared budget approval in front of every paid request.
`agents/video/studio.py` drives `produce()` directly.

The standalone five-tab `vidforge.app` was removed on 2026-09-30. Its Scanner
and Topics tabs survive as `python -m vidforge.cli scan` and
`python -m vidforge.cli topics`.

## Setup

```bash
brew install ffmpeg uv
uv venv && uv pip install -r requirements.txt
cp .env.example .env      # add OPENAI_API_KEY
python -m vidforge.cli doctor
```

`doctor` checks ffmpeg filters, fonts, API keys and Python deps, and tells you
what's missing before you spend anything.

## CLI

| Command | What it does |
|---|---|
| `run` | Produce a video. `--topic`, `--count N`, `--resume SLUG`, `--seconds`, `--visuals`, `--provider` |
| `course` | Generate a PowerPoint course. `--topic "..."`, `--outline FILE`, `--output FILENAME`, `--open` |
| `scan` | Trending videos + topic veins. `--region`, `--category`, `--limit`, `--queue`, `--refresh`, `--json` |
| `topics` | Show the queue; `--suggest 10` generates new ideas, `--add "..."` appends |
| `list` | Everything produced so far |
| `upload SLUG` | Upload to YouTube (private by default — see below) |
| `doctor` | Environment check |
| `schedule --at 03:30` | Write a launchd plist for unattended nightly renders |

Runs are resumable. Every stage caches to disk, so a crash, a rate limit, or
Ctrl-C costs you only the unfinished stage:

```bash
python -m vidforge.cli run --resume 20260802-1844-norways-giant-mirrors
```

## Cost and speed

Roughly **$1.50–2.50** and **20–35 minutes** for an 8-minute video, dominated by
image generation (one `gpt-image-2.5-flare` render per ~14s of narration) and the x264
encode. The exact estimate for each render is written to `manifest.json`.

To iterate on pacing and captions for free, skip the paid stages:

```bash
python -m vidforge.cli run --visuals gradient --seconds 90   # no image spend
```
and set `captions.align: estimate` in `config.yaml` to skip Whisper.

## Configuration

`config.yaml` holds the channel identity and every render knob; the flags above
override it per-run. The parts worth knowing:

- **`script.provider`** — `openai` (default, `gpt-4o`) or `anthropic`
  (`claude-opus-5`). Narration, imagery and caption alignment always use OpenAI.
- **`visuals.source`** — `ai` (`visuals.image_model`, default `gpt-image-2.5-flare`),
  `pexels` (stock, needs a key), or `gradient` (free procedural cards). A failure
  on any one scene degrades to a gradient rather than failing the render.
- **`video.transition`** — `xfade` for crossfades, `cut` for hard cuts. Cuts are
  substantially faster; crossfades re-encode the overlap.
- **`captions.renderer`** — `auto` picks `ass` when your ffmpeg has libass, and
  otherwise `overlay`, which draws cues with Pillow and composites them. The
  Homebrew ffmpeg bottle ships **without** libass, so `overlay` is what runs
  here. Both produce the same karaoke-highlighted style.
- **`audio.normalize`** — masters to −14 LUFS / −1.5 dBTP. YouTube turns loud
  audio down but never turns quiet audio up, so leaving this off makes your
  videos noticeably quieter than everything around them.

Drop `.mp3`s into `assets/music/` for a ducked music bed (see the README there
for sources cleared for monetisation). With the folder empty, videos render
narration-only.

## Uploading

Upload is deliberately **not** part of producing a video — nothing reaches
YouTube unless you ask for it, from the Library tab or the CLI:

```bash
python -m vidforge.cli upload 20260802-1844-norways-giant-mirrors                    # private
python -m vidforge.cli upload 20260802-1844-norways-giant-mirrors --privacy public   # needs the flag below
```

Publishing publicly needs **two** keys turned at once: `youtube.enabled: true`
in `config.yaml` *and* `--privacy public` on the command line. That way a
scheduled unattended run can never publish to your channel by accident.

One-time OAuth setup: Google Cloud Console → enable *YouTube Data API v3* →
Credentials → OAuth client ID → **Desktop app** → save the JSON to
`.secrets/client_secret.json`. The first upload opens a browser once and caches
a token.

## Unattended runs

Removed on 2026-09-30 along with the standalone app. `schedule` wrote a launchd
plist that rendered nightly with nobody present — a paid path outside Imprint's
request guard, which is the thing that guard exists to prevent. Run
`python -m vidforge.cli run` yourself, or render from Reel.

## The Scanner

What is pulling views on YouTube right now, and which topic veins sit underneath
it. Available as the **Scanner** tab or `python -m vidforge.cli scan`.

```bash
python -m vidforge.cli scan --region US --category 27 --queue
```

It reads YouTube's official trending chart (`videos.list(chart="mostPopular")`).
That is public data, so it needs a plain **`YOUTUBE_API_KEY`** — *not* the OAuth
client used for uploading; the two are separate credentials. Create one by
enabling [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
→ Credentials → API key. A full scan costs about 4 of the 10,000 free daily
quota units and is cached for 6 hours, so browsing is free.

**Raw views are the least useful column.** The derived metrics are what "right
now" actually means:

| Metric | Why it's there |
|---|---|
| **Views/h** | Velocity. A 400K-view video 2 hours old is climbing faster than a 9M-view video from four days ago — and the table sorts on this by default. |
| **Engage** | (likes + comments) / views. Separates something people *react to* from something merely served to them. |
| **V/sub** | Views per subscriber. Did the topic travel beyond the channel's own base, or is it just a big channel posting? |
| **Age** | Separates a spike from a slow burn. |
| **Format** | Duration bucket — which length is winning in this category right now. |

Click any column to re-sort (numerically, not alphabetically), or double-click a
row to open the video.

**Topic veins** are the point of the tab. The chart returns individual videos, so
the configured LLM groups them into themes with aggregate view totals, a note on
why each is travelling, and a suggested topic in that vein that fits *your*
niche. **Send suggestion to queue** drops it straight into `topics.txt`, ready
for the Produce tab.

Scans are cached to `output/trends/<region>-<date>.json`. The tab opens showing
the most recent one, and keeping the files means week-over-week deltas are
possible later.

**Two limits worth keeping in view.** This is trending **videos in a region**,
not search demand — Google Trends has no official API and `pytrends` is
unofficial and rate-limited, so treat the chart as a proxy. And chasing whatever
spikes today is precisely the mass-produced-repetition pattern YouTube
demonetises (see below). The value here is spotting durable veins inside your
own niche, which is why the clustering prompt is told to prefer durable interest
over passing news and to flag clusters that don't suit the channel.

## Roadmap

- **Week-over-week deltas** — two or more cached scans are enough to show which
  veins are growing rather than merely large; the data is already on disk.
- `visuals.source: pexels` is implemented but has never been run — there was no
  `PEXELS_API_KEY` available when it was built.
- `video.transition: cut` is implemented and compiles into the filter graph, but
  only the `xfade` path has been exercised end to end.

## Before you point this at a real channel

Two things worth knowing, because they determine whether any of this earns
anything:

1. **Monetisation has a floor.** The YouTube Partner Programme needs 1,000
   subscribers plus 4,000 valid public watch hours (or 10M Shorts views) in 12
   months. Nothing here shortcuts that.
2. **Volume alone is a losing strategy.** YouTube's inauthentic-content policy
   targets mass-produced, repetitive material, and channels that publish
   undifferentiated AI output at scale get demonetised rather than rewarded.
   This tool is worth most as a production pipeline for a channel with a real
   editorial angle — pick topics you can stand behind, read the scripts before
   they go out, and check the facts. The script prompt refuses invented
   statistics and URLs, but an LLM writing narration unsupervised will still get
   things wrong, and the images are illustrations, not documentary footage.

## Layout

```
config.yaml         pipeline settings (also the seed for a frozen build)
topics.txt          the topic queue
assets/             music and fonts the pipeline composites in
output/             the render library (gitignored)

vidforge/
├── config.py       paths, .env, config.yaml (bundle-aware when frozen)
├── progress.py     stage/cancellation protocol shared by CLI and GUI
├── ffmpeg_utils.py binary discovery, probe, concat, filter detection
├── llm.py          provider-agnostic JSON completion (openai | anthropic)
├── ideation.py     topic queue + LLM idea generation
├── script.py       topic -> scenes, metadata, cost estimate
├── voice.py        per-scene TTS -> single narration track + timings
├── captions.py     word timing (whisper|estimate) -> ASS or PNG overlay
├── courses.py      PowerPoint course generation (topic or outline -> .pptx)
├── visuals.py      per-scene imagery, with graceful degradation
├── motion.py       Ken Burns clips (supersampled to kill zoompan jitter)
├── assemble.py     xfade chain, caption burn, music duck, loudness master
├── thumbnail.py    background + outlined text
├── trends.py       YouTube trending chart, metrics, topic clustering
├── metadata.py     title/description/tags/chapters
├── youtube.py      gated OAuth upload
├── pipeline.py     stage orchestration + resume
└── cli.py          argparse entry points
```

## Version

vidforge no longer carries its own version. It was `v<MAJOR>.<BUILD>` derived
from this repository's `VERSION` file and `git rev-list --count HEAD`, shown in
the standalone app's window title; `VERSION`, `vidforge/version.py` and
`scripts/stamp_version.py` went with that app on 2026-09-30. The build you are
running is Imprint's, reported by `services/version.py` and shown in Imprint's
header — one number for one app, which is the point of absorbing this.
