# PUBLISHING MANAGER — Publishing metrics, marketing content, and launch tracking

`key: manuscript` · class: `agents/manuscript/agent.py → ManuscriptAgent` · panel: `build_manuscript_panel()` · handlers: `manuscript_refresh()`, `manuscript_ingest_kdp()`, `manuscript_ask()`, `quote_finder_suggest()`, `manuscript_generate_quote_graphic()`, `manuscript_generate_short()`, `manuscript_generate_calendar()`, `manuscript_add_todo()`

> The **Quill** (`key: author`, see [author.md](author.md)) owns the writing studio. Press picks up once a draft exists: sales data, launch content, and the publishing checklist.

## What it does
Five tabs covering the post-draft, pre/post-launch side of publishing a book:

1. **Overview** — PublishDrive sales/royalty summary, a question box grounded in that data, and the publishing todo checklist.
2. **Quote Finder** — load the selected Project's current working text with **Use Project Draft**, approve a numbered immutable snapshot with **Approve Write Draft…**, select it with **Use Approved Version**, load a file (`.txt`/`.pdf`/`.epub`/`.mobi`), or paste an excerpt; the agent extracts a batch of verbatim, screenshot-worthy lines. Each candidate has inline buttons to turn it directly into a graphic or a narrated short. Project draft loading remains explicit and unapproved; only the approval action captures a reviewed version.
3. **Quote Graphics** — turn one quote into a styled PNG (3 themes, square or vertical) for Instagram/Pinterest/TikTok — pure Pillow, no API cost.
4. **Shorts** — narrate a quote (free on-device TTS by default, ElevenLabs optional) and combine it with a quote graphic into a vertical MP4 via ffmpeg.
5. **Calendar** — turn the Quote Finder candidates into a dated posting schedule across TikTok/Instagram/Pinterest, with a platform-native caption per post and a one-click Graphic / Short button per row, then export the whole plan as a CSV punch list for manual posting.

## Inputs (panel controls)
| Control | Purpose |
|---|---|
| Period selector / Refresh Data | Pull PublishDrive sales for the selected window. |
| Ingest KDP CSV | Parse new files dropped in `data/kdp_reports/`, dedup by filename. |
| Ask box + Provider/Model | Chat Q&A grounded in the last-fetched sales JSON. |
| Publishing Todos list + Add/Done | Lightweight checklist, seeded with a standard launch checklist on first use. |
| Quote Finder: text box / Load File / quote count / theme / voice / attribution | Source text and generation settings for batch quote extraction. |
| Use Project Draft | Copies the selected named Project's current Write draft into Quote Finder and uses its byline for attribution. If no draft is present, prompts for one rather than borrowing text from another Project. |
| Approve Write Draft / Use Approved Version | Captures an immutable numbered text/title/byline snapshot after confirmation, then loads the selected version. Later Write changes do not alter it. |
| Export Approved / Submission Ledger | Exports EPUB/DOCX/PDF from the selected approved version with a saved file hash. The separate ledger accepts a user-entered retailer, date and confirmation reference or evidence file only while that export still matches. Entries are self-reported, not retailer-verified; no upload occurs. |
| Quote Graphics: quote / attribution / theme / size | Single-graphic generation settings. |
| Shorts: quote / attribution / theme / voice source / voice | Single-short generation settings. |
| Calendar: weeks / start date / platform checkboxes / theme / voice / attribution | Scheduling + asset-generation settings for the whole batch. |

## Outputs
Sales JSON and chat responses in the Overview text browser. PNGs in `data/quote_graphics/`. MP4s in `data/shorts/`. Todos persisted in the `manuscript_todos` DB table. Calendar exports a CSV wherever you choose to save it.

## How it works
`ManuscriptAgent.build_messages()` injects the last-fetched sales JSON as system-prompt context so Q&A stays grounded. `build_quote_suggestions_messages()` uses a dedicated prompt that requires quotes to be exact substrings of the source (verified in testing — the model does not paraphrase). `agents/manuscript/quote_graphics.py` renders a vertical gradient + wrapped serif text with Pillow — no external API. `agents/manuscript/shorts_generator.py` narrates via `providers/voice/` (mock/system `say` by default, ElevenLabs optional) then combines the narration with the quote-graphic PNG via a single `ffmpeg -loop 1 -i image -i audio` call — the exact pattern used by `agents/course/video_assembler.py`.

**Calendar** splits scheduling from writing deliberately: `agents/manuscript/content_calendar.py: build_calendar()` is pure Python (no LLM) that assigns quotes to day/platform/format slots by a fixed weekly cadence per platform (TikTok 4/wk short, Instagram 3/wk alternating graphic/short, Pinterest 7/wk graphic), cycling quotes if there are more slots than quotes — deterministic and free. Captions are the one LLM step: all slots go out in a *single* batched call (`build_calendar_caption_messages()`), not one call per post, and come back as a JSON array parsed by the same `_parse_quote_list()` helper Quote Finder uses. Each row's Graphic / Short button reuses the exact same generation path as Quote Finder and Shorts — `render_quote_graphic()` / `ShortsWorker` — so there's one asset pipeline, not three.

## Make Release Kit
**Make Release Kit…** (Quote Finder tab, right after **Export Approved…**) makes a set of release files from the approved version selected in that row, on this Mac, with one confirmation. Slice 1, shipped 2026-11-21, runs the free path only. Lesson: Learning Centre → Press → *Make a release kit*. Full description: README §7.7.

| Step | What it makes |
|---|---|
| 1 EPUB | The approved version as EPUB, with a SHA-256 receipt. |
| 2 Audiobook | Not included: narration is always paid; use Booth. |
| 3 Quotes | Up to 20, from 12 windows of up to 2,500 characters across the book (a book of 30,000 characters or fewer is sent whole); a quote is kept only if it is in the book word for word and at most 280 characters. Local model only (Ollama or LM Studio on this Mac). |
| 4 Calendar | 4 weeks from the start date, for the platforms ticked, with the Calendar tab's cadence. |
| 5 Graphics | One quote graphic (PNG) per unique quote. |
| 6 Shorts | One MP4 per Short slot, with the macOS `say` voice (personal, non-commercial use only under Apple's licence). |
| 7 Captions | One request for every post (reply capped at 8,192 tokens), then `calendar.csv` with an **AI used** column. Short replies leave later posts blank and mark the step Incomplete. |
| 8 Report | Links every file to the Project; writes `release-kit-report.md` and `provenance.json`. |

The confirmation shows "No charge"; any paid route blocks Start with a "Cannot start:" line. The **Release Kits** window (non-modal) shows the step, a Step · State · Spent · Line table, **Stop** (pauses; deletes nothing), **Resume** (checks each finished file's SHA-256 and skips the good ones), **Discard**, **Show Folder** and **Show Report**. Quitting while a kit runs asks **Keep Running** or **Quit and Pause**; progress is in the database (`release_jobs` and related tables), so a paused or crashed kit resumes at the next launch. The Mac is kept awake with `caffeinate -i` while a kit runs. Nothing is posted, scheduled or submitted, and the kit makes no claim about income, reach or results.

## Deliberate limitations
What Press does not do, on purpose or not yet. Rows marked *open* have a `TODO.md` item from the code audit of 2026-11-18.

- **Nothing is submitted to a store.** The submission ledger is self-reported: it records what you say you sent. The release kit does not post, schedule or submit.
- **No local provider.** Press's text tasks need a cloud model; the release kit's quotes and captions are the exception and run on a local model only.
- **PublishDrive has never been called against a live account.** Connections shows "connected" when a key is present, not when a fetch has worked (*open*, audit QH-5).
- **Ask sees only the last PublishDrive data.** Ingested KDP reports are not given to it, though its prompt mentions them (*open*, QH-5).
- **The Period selector is not read yet;** Refresh fetches 30 days (*open*, QM-10).
- **A KDP CSV with unexpected headers reads as zero sales, not as an error** (*open*, QM-13). Check the totals against the KDP report.
- **Quote Finder sends the first ~30,000 characters** of the text; only the release kit samples the whole book.

## Under the hood — files & functions
| Location | Role |
|---|---|
| `agents/manuscript_agent.py` | `ManuscriptAgent` — sales-summary, PublishDrive/KDP parsing, quote-suggestion, and calendar-caption prompts. |
| `agents/manuscript/publishdrive_client.py` | PublishDrive REST wrapper (`PUBLISHDRIVE_API_KEY`). |
| `agents/manuscript/kdp_csv_parser.py` | KDP CSV ingestion + dedup; `manuscript_seed_todos()` seeds the checklist. |
| `agents/manuscript/quote_graphics.py` | `render_quote_graphic()` — Pillow gradient + text render, 3 themes, 2 sizes. |
| `agents/manuscript/shorts_generator.py` | `render_short()` — TTS + ffmpeg image/audio combine. |
| `agents/manuscript/content_calendar.py` | `build_calendar()` — pure scheduling, no LLM, no deps. |
| `providers/voice/mock.py` / `elevenlabs.py` | TTS backends (free macOS `say`, or ElevenLabs). |
| `services/narrator/converter.py: load_text()` | Reused for Quote Finder's file loader (pdf/epub/mobi/txt extraction). |
| `main.py: build_manuscript_panel()` + tab builders | 5-tab UI. |
| `agents/manuscript/panel.py` | Handlers (`quote_finder_*`, `manuscript_generate_*`, `_quote_finder_*`) + the `ShortsWorker` background thread (`agents/manuscript/workers.py`). |
| `main.py: manuscript_generate_calendar()`, `calendar_generate_asset()`, `manuscript_export_calendar_csv()` | Calendar handlers. |
| `services/database.py` | `manuscript_metrics`, `manuscript_kdp_ingested`, `manuscript_todos` tables. |

## Extend it
- **Distribution integration**: a Buffer/Metricool API push from the exported calendar CSV — the natural next step once you're generating more content than you want to upload by hand.
- **Ad-campaign briefs**: KDP/Amazon Ads keyword lists and Meta boost structuring — Market mode covers organic copy, not paid.
- **Review-outreach tracking**: extend `manuscript_todos` into a light contact tracker (who got an ARC, follow-up date, status).
- None of the tabs write back into the manuscript itself — this agent only consumes a finished or in-progress draft (see [author.md](author.md) for drafting).

## Requirements
Pillow and ffmpeg (both already project dependencies) cover Quote Graphics/Shorts entirely for free. PublishDrive sales data needs `PUBLISHDRIVE_API_KEY` in `.env`. Better short-form narration needs `ELEVENLABS_API_KEY` (optional — free macOS `say` is the default). Quote Finder's LLM step uses whatever provider/model is selected on the Overview tab.
