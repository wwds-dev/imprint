# Changelog

All notable changes to Imprint, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## How versions are numbered

Imprint's version is `v<MAJOR>.<BUILD>` (for example `v2.400`), shown in the
header bar. `MAJOR` is the single integer in the `VERSION` file (currently 2).
`BUILD` is the number of commits on the branch (`git rev-list --count HEAD`),
so it goes up by one with every commit and is never typed by hand. This is
not semantic versioning: the number says which commit you run, not what
changed (README section 18.1 explains why).

There are no git tags and `VERSION` has changed once (set to 2 on
2026-09-22), so there are no named releases to group by. Entries are grouped
by date, and by month for older work. The build number is not recorded next to
each entry, because commits were rewritten in September (see 2026-09) and a
number written here would drift from `git rev-list --count`. To find the build
a change shipped in, look up its commit.

This file is generated from `git log`; see the note at the bottom for how to
regenerate it. It states what the code does, not how well it works for you:
nothing here is a claim about income, sales or publishing results.

Work that is on a branch or in `main` but not yet in a released build is
listed under **Unreleased** until it ships.

## Unreleased

### Changed
- **Both side rails redesigned** (2026-11-24, `docs/specs/side-rails-redesign.md`). Left: the
  project selector has an actions menu beside it (New Project, Project Overview, Save Current
  Setup); the agent filter is a button beside Search; saved chats are grouped under Today,
  Yesterday and Earlier with the agent beside each title and no sideways scrollbar; New Chat is
  the button under the list; Remove Chat moved to the chat's right-click menu and the Delete key.
  Right: Session and Today each show spend "of €" an editable limit over a bar, saved with Enter
  (the Limits block and Save Limits are gone); Requests, Last request, Saved by local and Advice
  spent are one list; System, Chat routing, API keys and Model updates show their state while
  collapsed. A limit with decimals is no longer shown truncated (1.5 read "1"). The session and
  daily refusal messages point at the new fields.
- **Routing advisor re-synced with Sentinel** (2026-11-23): `services/routing_advisor.py` gains
  `HYBRID_MODE` (what "Hybrid allowed" restores from Local only or Cloud only) and a test that a saved
  mode is never overwritten. The default stays "Local, advise per job", the best-fit route; the owner
  decided both apps keep it.
- **The app is called Imprint Studio; three agents are renamed** (2026-11-22,
  `docs/specs/rename-imprint-studio.md`, with package 5 of the docs readiness
  spec). The window title, header wordmark, tray menu, version tooltip,
  menu-bar name, sub-window titles, bundle and executable say "Imprint
  Studio"; the bundle is now `/Applications/Imprint Studio.app`, and both
  install scripts remove the old `/Applications/Imprint.app` (that exact path,
  only with this app's bundle id, only once it has quit). The data folder
  `~/Library/Application Support/Imprint/`, the database, the repository and
  the bundle id do not change. Agents: Chat is now **Kernel**, Muse is
  **Nova**, Stamp is **Vector**; an existing database shows the new names on
  the next launch. "Open Muse" and "use Stamp" no longer route (no aliases),
  and the router no longer treats "use the nova voice", "use vector files" or
  "use nova's voice" as naming an agent. That check covers only Kernel, Nova
  and Vector: "open Booth again" or "use Quill on chapter 3" still open the
  agent, as before. Docs, sheets, lessons and the hand-test script use the
  new names; the Kernel, Nova and Vector sheets gained "Deliberate
  limitations".

- **Model updates is easier to spot.** Its section in the side rail is open by
  default (it was collapsed, and the owner could not find the tile). Nothing
  else changes; saying so in a status line when a check finds something (G5 of
  `docs/specs/model-updates.md`) and that spec's review window are not built.
- **Documentation and Learning Centre made ready for the hand test**
  (`docs/specs/docs-learning-centre-readiness.md`, packages 1 to 4). README:
  a "Start here" block, the two parts marked (*Using the app*, *Engineering
  reference*), section 1 rewritten, sections 6, 7, 9 and 13 brought up to the
  current app (ten agents in eight workspaces, eight Settings tabs, eight
  permission boxes, Booth's three narrators and real requirements, Quill's
  draft safety, the real button labels), and the hidden income chapter
  deleted. Learning Centre: Quill's "What Write changes", Press's "Make a
  release kit" (with F1 help), "Add a key", and two new lessons,
  Troubleshooting and Glossary (28 lessons); the seven legacy pages that were
  shipped but never shown are deleted. Agent sheets: a "Deliberate
  limitations" section on nine sheets, a release-kit section on Press's, Veo
  in the past tense. Hand-test script: cases for draft safety and the release
  kit. Readiness gate and test plan carry a banner naming the 2026-11-18
  audit as the current verdict. No screenshots (they were removed on
  2026-11-05; Show me points at the real control).

### Added
- **`tests/test_docs_integrity.py`**: links and anchors, README section
  references, orphan lessons, quoted controls (`tests/docs_controls.txt`),
  retired names, titles, income wording, local paths, limitation sections and
  the Settings tabs and permission boxes, checked in the normal suite. Cases
  that wait for the rename are strict expected failures. After review
  (`docs/audit/docs-learning-centre-readiness-code-reviewer.md`, R-3 and R-4):
  the label check also covers README sections 3 to 7 and 13, every sheet and
  every lesson, ignores docstrings, and Troubleshooting's quoted messages are
  checked against the app's strings.

### Fixed
- **Local only keeps its promise, and a "local" model on another machine is
  named before anything goes there** (2026-11-24, `docs/specs/local-model-routing.md`,
  review L-3 and security P1-1). Under Local only no agent sends anything to a
  cloud service, images, narration and renders included, and the Mode box's
  Local only now beats an agent's own mode. Apply recommended setup no longer
  switches the whole app to Local only. If Ollama or LM Studio is set to
  another machine, Imprint refuses under Local only and otherwise asks once
  per address, naming the host and whether the link is unencrypted.
- **Measuring a local model costs what it said it would** (review L-1, L-2).
  Each cloud call has an output cap, the run's ceiling is priced on those caps
  and held against your budget while it runs, and each call is billed from the
  provider's own token counts. A judge that answers nothing, refuses or always
  picks the same slot no longer rates a local model level with the best cloud
  model: such pairs count for nothing, and a kind of work needs three in four
  usable pairs or stays unrated.
- **Four leftover widgets now belong to the window** (2026-11-23). The agent
  box, Quill's Sources box, Press's "Done" button and Nova's channel field
  were built without a parent, so they outlived the window; in the test suite
  that ended in an intermittent crash. Nothing looks different, except that
  the Sources box now shows the same text caret as the other editors. A test
  fails if a new parentless widget appears.
- **Booth authorizes the whole book when its text changed or its cache is gone**
  (2026-11-24, audit QB-2, `docs/specs/audit-p0-money-fixes.md`). An interrupted
  conversion remembers a fingerprint of the book's text. If the text changed,
  Start asks "Book changed since the interrupted run" and confirms the full
  estimate, because the narrator discards its cache and narrates everything
  again; No starts nothing. If the cached chapters were deleted, the missing
  ones are confirmed again instead of €0.
- **Herald checks the image provider before making a clip** (2026-11-24, audit
  QB-3). A clip whose scene images come from Gemini or Qwen needs that
  provider's key and its box ticked in the API permissions row, the same check
  the Video tab makes, and it runs before the brief is paid for. An image model
  Imprint does not know is refused.
- **A Gemini Omni clip is no longer thrown away by Stop, and quitting asks first** (2026-11-24,
  audit QH-2). Omni renders in one call, so Reel shows **Cannot Stop** while it
  runs and asks before quitting. A clip that arrives while Imprint closes is
  saved, and the next launch adds it to the Library and records its cost once.
  An Omni render cut off by a quit with no clip is recorded at its confirmed
  cost, since Gemini may have charged; any Omni render stranded by the old Stop
  is recorded on the next launch, at that day's date.
- **Quill's Revise keeps the whole text even when a reply carries a section
  marker** (2026-11-24, `quill-draft-safety` security review P1-1). A Revise
  reply is used whole, less a [DRAFT] heading on its first line; it is never
  split into sections and never writes the Outline, Characters or World tabs.
  A marker in the manuscript no longer changes what a Revise keeps, and a
  reply that still holds one says so. A Write stopped or failed mid-stream
  keeps its text but drops its section markers.
- **Quill keeps a Draft written with no Project** (2026-11-24, audit UX-01,
  `docs/specs/quill-unfiled-and-clear.md`). It autosaves like a Project's and
  is there after a quit and relaunch, and when you switch back from a Project.
- **Quill's Clear asks first and can be undone** (2026-11-24, audit UX-02). It
  names what it empties, Cancel is the default, Cmd-Z in a box brings its text
  back (until you switch Project or Write again), it is disabled while a Write
  runs, and Title and the Book Profile are no longer cleared.
- **Vector no longer promises vector files or an invented track record**
  (audit QM-18). Its prompt dropped the "5-star reputation", leaves prices as
  `[PRICE]` unless you give them, and asks for a flat logo on a plain
  background; the panel, sheet and lesson say "Vector makes PNG images, not
  vector files". The ban now covers delivery messages too, and the README no
  longer says the prompt asks for a transparent, vector-like logo.
  The image-model tooltip says "Best image model for Vector", not the retired
  "Client Gigs".
- **Docs after review (R-1, R-2, R-4, R-7, R-12):** Herald's Pinterest posting
  is described as not working yet everywhere (it did say both); Label's two
  tabs, not Label and Muse, share the "music" authorization; Troubleshooting
  quotes the real "[Too long]", "too big now" and "_API_KEY is not set."
  messages and points to the video, posting and audiobook lessons; the
  Tighten Structure threshold (a quarter) is named; seven labels quoted with
  the wrong wording or case now match the panels.

## 2026-11-21

### Added
- **MIT licence** (`LICENSE`, copyright 2026 wwds-dev). Until now the public repository carried no licence.
- **Make Release Kit** (slice 1, the free path; merged into local
  `main`, not yet pushed or released). In
  Press's Quote Finder tab, next to **Export Approved…**, one button turns an
  approved Project version into a set of files with one confirmation, all on
  this Mac, with no charge. Nothing is posted, scheduled or submitted. Eight
  steps run one at a time: EPUB (with its SHA-256 receipt), quotes, a 4-week
  calendar, one graphic per unique quote, one Short per Short slot, captions,
  `calendar.csv`, then every file is linked to the Project and a
  `release-kit-report.md` and `provenance.json` are written to the kit's own
  folder (`<Title>_v<N>_<date>`, never reused). The audiobook step is shown as
  "Not included": narration is always paid and this version cannot approve a
  paid step.
- Quotes and captions run on a local model (Ollama or LM Studio); an address
  that is not this Mac is refused so the book never leaves it. The quote step
  samples the whole book (12 windows of up to 2,500 characters; a book of
  30,000 characters or fewer is sent whole) and keeps only quotes found word
  for word, at most 280 characters, up to 20. Press's own Quote Finder still
  sends the first 30,000 characters. The caption reply is capped at 8,192
  tokens; posts left without a caption are listed in the report and the step
  is marked Incomplete.
- Shorts use the on-device macOS `say` voice, for testing only. Apple's licence
  limits its built-in voices to personal, non-commercial use, so the
  confirmation and the report carry a notice (N2): decide before posting these
  Shorts publicly. The report and the CSV's new **AI used** column record which
  model chose the quotes and wrote the captions and that the voice is
  synthetic; no marking is written into any file.
- The kit keeps the Mac awake while it runs (`caffeinate -i`, tied to
  Imprint's process, so it ends if Imprint exits or crashes; the display may
  sleep and a closed lid still sleeps the Mac). Only one kit runs at a time.
- A **Release Kits** window (from Start, **Open Release Kit…** or Project
  Overview's new **Release Kits…** button, which also shows a release-kit
  line) lists each kit's steps, with Stop, Resume, Discard, Show Folder and
  Show Report. Quitting while a kit runs asks to Keep Running or Quit and Pause.
- Resume after a crash or quit: progress is written to four new tables
  (`release_jobs`, `release_job_approvals`, `release_job_stages`,
  `release_job_items`; additive migration) as it happens. At the next launch
  the window opens once; Resume checks each finished file against its SHA-256,
  skips the good ones and runs the rest again. A kit pauses, and never asks
  during the run, when a model does not answer, a render fails or a request is
  larger than its bound.
- `usage` and `runs` gained a `job_id` column (and `usage` a `job_item`
  column) so each local request is recorded against its kit.
- Calendar CSV export (Press and the kit share
  `agents/manuscript/calendar_export.py`) prefixes a cell that starts with
  `=`, `+`, `-`, `@`, a tab or a carriage return with `'`, so a spreadsheet
  keeps quotes and captions as text instead of running them as formulas.
- Not in slice 1: paid cloud models, ElevenLabs Shorts, the audiobook step,
  the job-level budget reservation and re-approval of remaining steps.

### Fixed
- Found in code review of the kit before release: an error inside any step or
  callback now pauses the kit (it used to leave it "running" with the Mac held
  awake); a local model address that is not this Mac is refused; the guard
  checks each item against the approved route, the running step and the kit's
  own items; the 8,192-token reply cap is sent to Ollama (`num_predict`) and LM
  Studio (`max_tokens`) and a cut reply is reported; the CSV formula guard
  covers a leading tab and carriage return; Resume reports a file-check error
  instead of stalling; the quote request bound is derived from the prompt
  rather than fixed; a missing `caffeinate` is shown in the window instead of
  claiming the Mac stays awake; the ledger accepts only known column names;
  quitting while a local request runs now stops reading the model's reply and
  closes the stream (before, the request kept running after Quit and Pause);
  only the wait for the first token cannot be cut, and then the item is left
  for the next launch to resolve and runs again on Resume. Open from that review: a pending request token can leak if
  the driver raises between granting an item and starting it, and the cost
  clamp in `record_job_item` must be replaced before any paid route ships.

## 2026-11-20

### Fixed
- Quill never loses the Draft (audit QB-1, `docs/specs/quill-draft-safety.md`).
  Write no longer empties the Draft: a prose task (Write Scene, Write Chapter,
  Write Dialogue, Add Case Study / Example, Continue Draft) adds its text after
  the existing Draft. Generate Outline, Develop Characters and Build World go
  only to their own tab. An error or Stop keeps the Draft, so the autosave can
  no longer store an emptied one. Revise / Improve, Tighten Structure and
  Strengthen Argument now send the whole selection (or the whole Draft) instead
  of its last 3,000 characters, replace exactly that text as one edit (Ctrl+Z
  brings it back), and work on up to 20,000 characters per run (6,000 with
  a local model); a longer text
  is refused with a note to select a passage, and a revision cut off at the
  length limit, or under half the length of its text, leaves the Draft
  unchanged. The Draft is read-only while a revision runs.

## 2026-10-14

### Fixed
- Budget caps now hold for text requests. Every paid text client (OpenAI,
  DeepSeek, Kimi, Qwen, Gemini, Anthropic) sends one output cap of 8,192 tokens,
  and the guard reserves that much output plus every message the request sends
  (system prompt, context, history, project instructions), not the typed prompt
  alone. Before, five clients sent no cap and one request could run past what was
  left of a budget many times over. DeepSeek also reserves up to 65,536 thinking
  tokens; Qwen is sent a thinking limit of 8,192 and reserves that on top (the
  parameter name is unverified until a paid run); Kimi reserves the cap alone,
  because its thinking counts against it. A 100-token prompt is "up to" €0.12
  on kimi-k3 (which a reserve of 65,536 for every Kimi model had refused under
  the default €1.00 session cap), €0.10 on qwen3.8-max and €0.27 on
  deepseek-v4-pro.
- A video render, Herald clip or Stamp logo batch that fails or is stopped now
  records what it already paid for (each started paid step at its confirmed
  line, each saved image at the per-image rate, never more than you confirmed)
  as a `partial` row in Cost History, and the Run Log says "recorded €X of €Y".
  Before, it recorded €0 and a retry paid everything again under the same caps.
  Stopping before the first paid step still records nothing.
- Muse drafts report their real token counts (they were billed on an estimate).
- A cut-off or empty Stamp image prompt or Herald clip brief no longer goes on
  to a paid image batch or render (an empty clip topic rendered the next topic
  from topics.txt).
- Stopping a Stamp batch closes it only when the image worker's last signal
  arrives, so images it had already returned are billed; a video Stop during
  the last scene image counts that image.
- A Gemini stream that reported the length limit no longer loses it to a later
  chunk; a refusal can no longer show the same figure twice ("up to €0.43 …
  €0.43 left").
- Token and per-unit pricing read one EUR/USD rate, and a rate of 0, below 0,
  NaN or infinity falls back to 0.92 instead of making requests free or
  negative. Settings refuses to save such a rate. Settings and **Save Limits**
  both refuse a NaN, infinite or negative Session or Daily budget and keep the
  old limits (Save Limits took "inf", which removed the cap, and "nan", which
  made every paid request fail).
- Reddit: a subreddit must be one valid name ("r/r/rust", "r/ rust" or a URL is
  refused before login), and "Post now?" names it (`r/rust`).
- Run Log, Cost History, the Video log and the agents' status lines show
  provider and error text as text, not HTML.
- An Anthropic 404 during a stream names the missing model instead of raising
  a NameError.

### Changed
- The paid-request dialog shows "Up to €X; you pay for what it writes" and the
  tokens it is based on; renders and image batches add that finished paid steps
  are recorded if they fail or are stopped. The live line and the Cost Estimate
  popup use the same "up to" figure.
- A budget refusal says "Not sent: this request can cost up to €X and your
  session cap has €Y left (of €Z)" and what to do, instead of "Session budget
  exceeded". The local-model offer is titled "Not enough budget left".
- A reply that stops at the length limit shows "[Cut off] …" beside the text
  instead of "[Finished]" or "[Done]"; Quill points at Continue.
- Video and Stamp Stop messages say what was recorded ("[Stopped] After 10 of 35
  images: €0.73 of €2.11 recorded."); Stamp's errors use the `[Error]` tag.

### Added
- Settings -> API keys has a **Qwen workspace ID** field (`DASHSCOPE_WORKSPACE_ID`,
  Singapore only). Entering the ID sends Qwen chat to
  `https://<id>.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`, the host
  Alibaba recommends. The ID must be one plain label (letters, digits, hyphens);
  anything else is ignored with a visible message, so the ID can only point the
  key at a `*.ap-southeast-1.maas.aliyuncs.com` host. `DASHSCOPE_BASE_URL`
  still overrides it; when that URL is the standard host, the Qwen note says to
  clear it rather than to set the ID. Wan video and Qwen Image are not changed.
  An ID that is set but invalid is also named, without its value, in the Qwen
  hover note and `scripts/check_keys.py`.
- When a Qwen key check on a workspace host returns 401, the note says the key
  may belong to a different workspace or region.
- The Qwen **Test** result names the host that answered: "via workspace host",
  "via standard host" (plus "(workspace ID ignored)" when a typed ID did not
  apply), or the host name of a typed endpoint, such as "via dashscope.aliyuncs.com".
- The **Model updates** tile has a **Video and image** section. The startup
  check and **Check now** also read Gemini's and Qwen's image and video model
  lists (both free). A new model is listed in the tile only; it is not added to
  the Video menus or to any chat menu. The Qwen list call has not been verified
  against a live account, and is skipped without a note if Qwen does not serve
  it.
- Shutdown dates from the Video catalogue show in the tile: "Veo 3.1, Fast and
  Lite: earliest shutdown 22 October 2026". In the final 14 days the row is a
  warning with the days left; after the date it says the models are no longer
  offered, for 14 days. These rows cannot be dismissed.
- Removed-model warnings: a video or image model Imprint offers, or a chat
  model an agent has selected, is flagged when the provider stops listing it.
  It takes two misses on two different UTC days, from the Model updates check
  only; an empty or failed list never counts. The notice drops on its own if
  the model is listed again. Nothing is switched for you.
- An optional check that Higgsfield's Seedance paths still answer. It is **off
  by default** and has no switch in the app: set
  `"model_watch_probe_higgsfield": true` in `config/settings.json` only after
  confirming by hand that Higgsfield's `/estimate` call costs nothing (TODO.md).
  It also needs a Higgsfield key, the **Higgsfield** chip on and the request
  guard's checks to pass, and runs at most once per UTC day: one estimate call
  per path of Seedance 2.5 and 2.0, never a render or an upload.
- The tile's title counts warnings as well as new models
  ("Model updates · 2 new · 1 warning"), and the video and image notices have
  their own **Dismiss**.
- A hand-typed `DASHSCOPE_BASE_URL` or `DASHSCOPE_VIDEO_BASE_URL` that is not
  https (plain http to localhost is fine) or not on `aliyuncs.com` is still used,
  but its Settings row, the Qwen hover note and `scripts/check_keys.py` warn that
  the key is sent there.

### Fixed
- A blank `DASHSCOPE_BASE_URL=` or `DASHSCOPE_VIDEO_BASE_URL=` (as shipped in
  `.env.example`) is now treated as unset and falls back to the default host.
  Before, the empty string was used as the base URL, so every Qwen call (or Wan
  video or Qwen Image call) from a `.env` with the blank line failed. It failed
  before sending anything: the URL had no host, so the key went nowhere
  (checked against openai 2.31.0 and requests).
- Chat model dropdowns no longer show image or video models. A provider's list
  is now filtered before it reaches them, and the filter also drops every model
  in the Video catalogue (for example `gemini-nano-banana-2.1`, whose id does
  not say "image"). Those models also stop being ranked as text models.
- `.env.example` and the README said the Higgsfield endpoints default to
  Seedance 1.0 Lite; the default is Seedance 2.5. `.env.example` now leaves the
  two endpoint overrides blank.
- The README said the test suite has just over 1,000 tests. It has 1,605, and
  a full run takes 13 to 17 minutes.
- `tests/test_app_identity.py` failed on the macOS CI runner, whose python.org
  Python already names its bundle *Python*. The tests now accept that name; the
  menu-bar bug itself is still open (TODO.md).

### Security
- Settings -> API keys refuses a value with a line break, such as a two-line
  paste, and names the field ("must be one line only"); nothing on the page is
  written. Before, pasting `ws1`, a new line and `DASHSCOPE_BASE_URL=…` into one
  box could leave a second line in `.env` that Settings read back as
  `DASHSCOPE_BASE_URL`; one more Save made it a setting the app loads at launch.
- Pinned dependencies raised to the minimum versions that clear the 97
  pip-audit advisories in nine packages: pypdf 6.19.0 (also in
  `cloud/requirements.txt`), urllib3 2.8.0, soupsieve 2.9.0, pillow 12.3.0,
  lxml 6.1.0, anyio 4.14.2, idna 3.18, and new pins for httpx2 and httpcore2
  2.12.0. No app code changed; reinstall `requirements.txt` into the `.venv`.
- `.gitleaksignore` pins three more copies of the known settings-key false
  positive, quoted in `docs/audit/security.md`.

### Changed
- The Qwen endpoint note no longer says the international host is in
  "maintenance mode since 2026-09-30", which no primary source confirmed. It now
  says a workspace host is recommended and the standard host still works.
- The Veo 3.1 notes now say Google *may* shut the previews down from
  22 October 2026, its earliest date, rather than that it will on that day.

## 2026-10-12

### Security
- A new `.env` file is now created readable by its owner only (permissions
  0600), including when it is seeded from the template on first launch.
- If moving the old "Create & Publish" data folder to the new Imprint folder
  fails, the app now keeps using the old folder for that run and tries again
  next launch. Before, a failed move could leave a blank new folder behind
  that hid your keys and database on every later launch.
- The folder move is now a single atomic step, and a test checks that a legacy
  database keeps writes that were still in its write-ahead log.

### Added
- Two GitHub Actions workflows: `quality.yml` (tests with coverage, and a
  lint count that may not rise) and `security.yml` (gitleaks secret scan and a
  pip-audit of `requirements.txt`). Also a gitleaks config, `ruff.toml`, a
  Dependabot config and a pre-commit hook file. The hook is not switched on
  by default; run `git config core.hooksPath .githooks` to use it.
- Company process files: role playbooks, `AGENTS.md`, and a tooling baseline
  (`docs/company/tooling/baseline.json`) that the ratchet script checks so
  lint counts cannot rise.

### Changed
- The test that checks for retired names now also scans files that are not yet
  committed (new but not ignored), so a retired name cannot slip in before its
  first commit.
- Press: the Overview sidebar no longer adds a second scrollbar; the
  to-do list is a checklist that gives way before the panel scrolls.

## 2026-10-11

### Added
- Settings -> API keys: paste a key, press Test, then Save All. The window
  rebuilds its provider clients, so there is no file editing and no restart.
  `services/api_keys.py` is the single list of credentials the code reads.

### Fixed
- The model-ratings fetch remembers a failed try, so an offline Mac waits a
  day instead of fetching again at every launch.

## 2026-10-09

### Added
- `tests/TEST_PLAN.md` and `tests/READINESS_GATE.md`: the test plan and the
  check of each agent's promise against its code before QA starts.
- `scripts/check_setup.py`: checks Python 3.11+, the data folder, ffmpeg and
  ffprobe (required), and Calibre, `say` and Ollama (optional).

### Changed
- Six catalog lines now say only what ships (for example Herald: publish to
  Reddit, YouTube and Pinterest; Label: audio is made in Suno).
- Docs in four places now say Booth narrates by three routes, not OpenAI only.

### Fixed
- `PUBLISHDRIVE_API_KEY` was read by the code but missing from `.env.example`
  and `scripts/check_keys.py`; a test now requires every secret the code reads
  to be in the template.
- The on-device voice fallback used to write a silent MP3 and call it success;
  it now fails with an error.
- `scripts/check_keys.py` imported classes that do not exist; fixed.
- Stamp orders close and keep their edits; the Glimmer pull drives Chat's
  progress bar.
- Tooltips: setting them to Off no longer hid a clipped field's full value in
  every window after the first.

## 2026-10-08

### Added
- Text model "best fit" now uses LMArena ratings (credited, CC BY 4.0): the
  cheapest model rated within 20 points of the best wins.
- Muse Glimmer shows download progress.

### Changed
- Every panel is lined up on one grid.
- Booth keeps its own conversion log instead of writing into Chat's.

## 2026-10-07

### Added
- Every paid request is assessed for which provider and model fits it best,
  including image, video and speech requests. A model is not switched for
  being new. The Model updates tile in the rail applies marked updates only
  where the marked model wins the assessment.
- Narration routes in Booth: OpenAI, Gemini or ElevenLabs, chosen per book.
- Images from Gemini and Qwen as well as the existing providers; Muse teasers
  from Higgsfield, Gemini Omni or Wan 3.0.
- Learning Centre pages for paid-request assessment and Model updates.

### Changed
- Model lists and prices brought current; every offered model has a price row.
- The live launcher is a small C program, so the app is named Imprint (not
  "python") in Activity Monitor and the Dock, and no longer shows as Not
  Responding.
- Quill, Manuscript and Booth's Listen tab scroll instead of squeezing rows;
  spin boxes and date edits keep their own widths.

### Fixed
- Veo is removed on its shutdown date; ElevenLabs and Higgsfield requests
  match what their APIs read; a paid Gemini render is never posted twice.
- Ranking: no unpriced winner, and ties do not move the badge.

## 2026-10-06

### Added
- Three themes, picked from three dots.
- A menu bar item with Open and Quit. Closing the window still quits the app.

### Changed
- Narrator tools run in the launch environment; one conversion per book folder
  at a time.
- `.env` is created from the template with every secret blank; README section
  19 now lists every provider key and what it unlocks.
- Docs for Imprint and six agents brought back in line with the code.

### Fixed
- A test-suite hang: the media engine no longer outlives its widget.
- Muse's teaser resume never worked on an existing database (a duplicated key
  left four columns unadded).
- Narrator: a chunk stopped mid-stream is no longer marked done; a chunk cut
  short by a stop is redone.
- The free-local-model offer now names a model that is actually pulled.

## 2026-10-05

### Added
- Local-model offer: when a budget cap refuses a request, the app asks whether
  to switch the agent to Ollama. The request is not re-sent for you.
- Music plans are saved records; Client Gigs keeps one durable order per
  client with a reusable brand kit; Site Builder exports in a project shape
  with checks you rule on.
- Booth offers AZW3 where the converter accepts it; Publishing Manager shows
  each integration's last sync outcome; Social explains what connecting grants.
- `ui/charts`: a bar chart, first used for KDP royalties.
- Learning Centre: every agent lesson has a Show me recipe.
- UAT scenarios for the ten agents that exist (`tests/manual_test_cases.md`).

### Changed
- Money readouts and source/scope handling hardened across the second feature
  wave (thirteen confirmed defects fixed in one pass).

## 2026-09-30

### Added
- Audiobooks: save to this Mac or a synced Google Drive folder; progress
  follows the same choice. M4B with chapters; EPUBs read in spine order.
  `cloud/` holds a web agent that is not deployed.
- Router can reach an agent by its own name and says how sure it is.

### Changed
- Agents renamed to codenames (Quill, Press, Booth, Label, Reel, Herald,
  Sitebuilder, Stamp, Muse, Chat); each workspace shows a one-line description.
  Catalog keys, settings and the database are unchanged.
- vidforge is part of this repository rather than a separate nested one.
- Audiobook Studio merged into Imprint.

### Removed
- Muse's platform-specific features, which Backstage owns.
- The Primer course generator (never shipped) and `creator_earnings`.
- vidforge's standalone GUI and its `schedule` command, which could start
  paid renders outside the request guard. `python -m vidforge.cli` still runs.

## 2026-09 (summary)

Mostly Sept 7-29; the repository history was rewritten on 2026-09-24 and
2026-09-27 (the commits say so), so build numbers from before then no longer
match.

### Added
- The app was renamed Imprint (2026-09-08). On launch it moves the old data
  folder and database forward, with their write-ahead files, without
  overwriting newer data.
- GUI rebuilt: one header bar and two fixed rails, a shared form system,
  rebuilt panels for each agent, a Learning Centre with guide pages and
  screenshots, and "Show me" recipes.
- Agents: Creator (planning, persona, calendar week view), Video (vidforge as
  an agent), Social (posting where an API exists), an audiobook library with a
  resuming player.
- Projects: shared work identity across agents, a cross-agent overview, and
  immutable approved manuscript versions.
- Durable jobs: video renders, Creator teasers, audiobook conversions and the
  Social publishing queue survive a restart. A publish with an unclear result
  becomes "Verify platform" instead of being retried.
- Header version badge (`v<MAJOR>.<BUILD>`), 2026-09-22.
- Chat streams from every provider, including Ollama.

### Changed
- Pricing: prompt-cache rates, per-unit work (renders, narration) is priced,
  and both budget limits sit on one row.
- Each agent lives in its own package; the host-control aliases are gone.
- Higgsfield defaults to Seedance 2.5 with a 2.0 fallback.

### Fixed
- Money integrity and lifecycle gaps from the 2026-09-20 re-analysis; several
  review rounds of defects in video, teaser, calendar and audiobook
  persistence.

### Removed
- Sora (the Videos API is gone) and the venture dashboard workspace.
- Creator's adult-platform rules and performer records.

### Security
- The secret-scan allowlist is re-pinned after each history rewrite, and one
  deployment note was kept out of the public repository.

## 2026-08

- Forked from `sentinel_ai` (08-18) as Atelier, then Create & Publish; the
  security verticals were stripped from the fork.
- Anthropic pricing corrected; Qwen pricing added. Request-guard and book
  pipeline tests; `ui/` extracted from `main.py`.

## 2026-06 to 2026-07

- Initial commit (06-16); narrator merged in as an in-process module; project
  prepared for GitHub. July holds only automatic sync commits.

## Regenerating this file

Run `git log --reverse --format='%ad %h %s' --date=short`, drop lines that
start with `autosync:` and pure merges, and group by date. Read the commit
body where a subject is unclear. Keep one line per user-visible change.
Cross-check each line against the code.
