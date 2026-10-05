# Imprint — Manual Test Cases

**Type:** User Acceptance Testing (UAT) — you drive the real app and judge the result.
**Scope:** the eight visible workspaces, the ten agents inside them, and the shared
systems they all route through (projects, the spend guard, budgets, history,
Learning Centre, restart recovery).
**Roster source:** `agents/catalog.py`. If a codename below disagrees with that
file, the file is right and this document is stale.
**Last revised:** 2026-10-05, after the P2 hardening wave (`a8235bb`).

> **This replaces the Sentinel AI test pass.** Imprint was forked from
> `sentinel_ai` and kept only the creative/publishing half, so the agents the
> previous version of this file tested do not exist here. Manager, OSINT, OSINT
> Heavy, Bug Bounty and WiFi went to `active/sentinel_fork`, which has its own
> acceptance checklist. Coding, Writing, Health, Investment, NFL Bet and ROI
> were retired from both apps. Nothing from either list belongs in this pass.

---

## How to use this document

1. Start the app. **Part A first** — if a shared system is broken, every agent
   result below it is untrustworthy.
2. Work down Part B one workspace at a time. Tick each box as you verify it.
3. Part C is the boundaries: things that must *not* happen. A pass there is
   the app refusing something.

### Cost markers

| Marker | Meaning |
|---|---|
| `FREE` | No paid request. Runs with a local Ollama model, or sends nothing at all. |
| `PAID` | Sends a billable request. You see the estimate and approve it first. |
| `PAID-UNIT` | Billed per unit, not per token (TTS, image, video). Usually the costliest cases here. |

**Run the whole `FREE` pass before any `PAID` case.** Most defects this suite
catches are layout, state, persistence and refusal behaviour, none of which
need a cloud provider. A full `PAID`/`PAID-UNIT` pass is a separate, budgeted
session — set a low daily cap in Settings first so a mistake is cheap.

### Before you start

- [ ] `.venv/bin/python -m pytest -q` passes. A failing automated suite means
      you are hand-testing on a known-broken build. If the run sits with no
      output for more than ~3 minutes it has wedged, not slowed — see the note
      at the end of this document.
- [ ] Ollama is running with a **general instruct** model pulled
      (`ollama list`). A reasoning model such as `deepseek-r1` emits its
      `<think>` monologue into the output box and will make half the `FREE`
      cases below unreadable. `llama3.1:8b` or `qwen2.5:7b` is the right choice
      for this pass.
- [ ] For the `PAID` pass only: a `.env` beside `main.py` with the provider keys
      you intend to test. `.env.example` lists the model-provider names. The
      app loads it at startup; with no `.env` and no keys in the environment,
      every cloud provider is simply unavailable and the `PAID` cases cannot run.
- [ ] For Herald's publishing cases: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`,
      `REDDIT_USERNAME`, `REDDIT_PASSWORD` and/or `PINTEREST_ACCESS_TOKEN`.
      These are **not** in `.env.example` — read them off
      `agents/social/publishing.py` or the in-app connection guide.
- [ ] A disposable project name is free to use — these cases create
      `UAT 2026-10-05` and delete it at the end.
- [ ] Settings → budgets: set a small daily cap you are willing to lose.

---

# Part A — Shared systems

Test these first. They sit under every agent.

## A1. Launch and the header bar  `FREE`

> **What it does:** opens maximised, builds the header (wordmark, version badge,
> workspace tabs, status pill, Docs / Tooltips / Settings) and lands on a
> workspace.

**Launch it from a terminal for this one**, not from the Dock:

```bash
cd ~/Documents/lab/active/imprint && .venv/bin/python main.py
```

The app catches its own startup failures and notes them rather than crashing,
which is right — but it means a broken subsystem looks like a clean launch from
the Dock. The startup reconciliation that finishes jobs left in flight is the
clearest example: a missing database column made it fail on every launch, the
app started normally, and paid renders were quietly never resumed. It was found
by reading this output, not by using the app.

- [ ] The only output is Qt's FFmpeg version line. Any `[warn]` line is a
      finding — read it before going further, especially one naming `resume`,
      `pending`, or a database column
- [ ] `.venv/bin/python main.py --selftest` passes every check (writable data
      directory outside the bundle, every panel agent registered, vidforge
      imports and its config loads, bundled resources present)

**Then:** hover the wordmark. Resize the window narrower, down to about 1000 px.

**What to verify:**
- [ ] Window opens maximised; nothing overlaps in the header
- [ ] Version badge reads `v2.<build>`; its tooltip (or the wordmark's) says
      whether the running build is current
- [ ] Status pill reads `●  Ready`
- [ ] Wordmark, workspace tabs and the page title all start on the same left edge
- [ ] As the window narrows, the header **sheds** the status pill and version
      badge before it sheds a workspace tab
- [ ] Tabs that no longer fit move into **More ▾** rather than being clipped
- [ ] Both rails scroll when the window is short; neither is draggable

## A2. Workspaces and what each one says it is for  `FREE`

> **What it does:** eight visible workspaces across the header. Agent names are
> codenames now, so each workspace carries a one-line description of what lives
> inside it.

**Steps:** click every workspace tab in turn, including the ones under **More ▾**.

**What to verify:**
- [ ] Every tab switches the centre panel without a visible rebuild flicker
- [ ] A one-line description appears under the tab bar for each workspace
- [ ] The eight workspaces and their agents match `agents/catalog.py`:

| Workspace | Agents | Description should say |
|---|---|---|
| Author | Quill, Press | write a book, then prepare, publish and track it |
| Audio + Music | Booth, Label | narrate books into audiobooks; develop and release music |
| Video + Ads | Reel | script, narrate and assemble long-form video and vertical ads |
| Social | Herald | write, schedule and publish platform-native posts |
| Web | Sitebuilder | build responsive pages in HTML, CSS and JavaScript |
| Brand Design | Stamp | client-ready brand concepts, logos and delivery copy |
| Brand Content | Muse | draft campaign content, calendar it, render promos |
| Assistant | Chat | general-purpose chat for anything without a dedicated tool |

- [ ] No workspace named after a retired venture appears (see C5)

## A3. Intent Router — the decision says how sure it is  `FREE`

> **What it does:** classifies what you typed and says *why* it chose. Three
> confidence levels: `addressed` (you named the tool), `intent` (a keyword
> matched) and `fallback` (nothing matched, so Chat). Ambiguity is shown, not
> hidden.

Type each input into the Assistant prompt and read the routing decision and its
WHY tooltip. Do **not** send.

**Test A — addressed by codename**
```
open Booth
```
- [ ] Routes to Booth (audiobook), confidence `addressed`
- [ ] The reason names "Booth"

**Test B — intent keyword**
```
Narrate this ebook as an audiobook
```
- [ ] Routes to Booth, confidence `intent`
- [ ] The reason names the matched keyword

**Test C — ambiguous, and it says so**
```
Make a YouTube video for the music release
```
- [ ] Routes to Reel (video), but is flagged **ambiguous**
- [ ] The reason says "also matched" and names Label (music) as the runner-up

**Test D — fallback, honestly labelled**
```
What is the capital of France?
```
- [ ] Routes to Chat, confidence `fallback`
- [ ] The reason says no intent matched — not a pretend match

**Test E — an ordinary English word is not an address**
```
press release for the launch
a white label deal
stamp the document and send it
```
- [ ] All three route to **Chat**, not to Press / Label / Stamp
- [ ] A bare `Muse` or `Stamp.` on its own *does* route to that agent

**Test F — addressing beats intent**
```
open Quill and write a social post
```
- [ ] Routes to Quill, not Herald

**Test G — the WHY tooltip is live**
- [ ] After each route, the WHY tooltip reflects the *current* decision — no
      text left over from the previous one

## A4. Projects, artifacts and deletion  `FREE`

> **What it does:** a Project is a work association. Saved drafts, exports,
> audiobooks, clips and media link to it. Deleting it unfiles the links; it does
> not delete your files.

**Steps:** create `UAT 2026-10-05` in the left rail. In Quill, type a sentence
and press **Save Draft**. Switch workspace and come back.

**What to verify:**
- [ ] The project context pill in the header shows the active project
- [ ] The draft restores after switching away and back
- [ ] The project's artifact list shows the saved draft
- [ ] Export a draft (EPUB) — it appears as an artifact, and the file stays at
      the path you chose
- [ ] Delete the project. The **files on disk still exist**; only the links are gone
- [ ] Each panel's **Current Project** view filters to linked items; the default
      view still shows everything

## A5. The spend guard — nothing paid gets through unseen  `PAID`

> **What it does:** every paid path in the app calls `authorize_request` first.
> You see an estimate and approve it. A declined request opens no run and bills
> nothing.

**Steps:** in Assistant, pick a cloud provider and a short prompt. Press **Send**.

**What to verify:**
- [ ] A cost estimate appears **before** anything is sent
- [ ] **Decline** it: no output, no new Run Log entry, no new Cost History row
- [ ] Approve it: output arrives, exactly **one** Cost History row, exactly one
      Run Log entry
- [ ] Press Send twice quickly — you are not billed twice for one intent
- [ ] Repeat the decline test in Quill, Sitebuilder and Stamp. A declined paid
      request leaves the action button **available**, not stuck disabled

## A6. Budget caps and the free-local offer  `PAID`

> **What it does:** when a global cap (session or daily) would be exceeded,
> Imprint offers to switch that agent to the free local model. A per-agent or
> per-project cap is a fence you drew on purpose — it stays a refusal.

**Steps:** Settings → set the **daily** cap just below one small request's
estimate. Send that request from Quill.

**What to verify:**
- [ ] The request is refused with the cap reason stated
- [ ] A dialog titled **Budget cap reached** offers the local model and says it
      "runs on this machine and costs nothing"
- [ ] Saying **Yes** flips the provider box to `ollama` and picks a local model
- [ ] It does **not** auto-send — you press Send again deliberately
- [ ] Saying **No** leaves the provider unchanged and the request refused

**Test B — a per-agent cap is not negotiable**
- [ ] Set a per-**agent** cap low instead. The refusal appears with **no** local
      offer — only the block message
- [ ] Same for a per-**project** cap (its wording mentions "daily budget"; the
      offer must still not fire)

**Test C — no offer where there is no local equivalent**
- [ ] Trip a cap on a Booth conversion or a Reel render (per-unit priced).
      No local offer — those have no free local path

**Test D — ollama itself**
- [ ] With `ollama` already selected, trip a cap. No offer to switch to ollama

## A7. Cost History and Run Log  `FREE` then `PAID`

**Steps:** open **Cost History** and **Run Log** from the right rail.

**What to verify:**
- [ ] A local (ollama) request records as free — not as unpriced, not as a guess
- [ ] A cloud request shows provider, model, tokens and cost
- [ ] **"Unpriced" means unknown, not free** — the label says so
- [ ] Run Log shows the full lifecycle of each request, including a failed one
- [ ] A declined request appears in neither
- [ ] Per-unit work (TTS, image, video) appears with its unit basis, not a
      fabricated token count

## A8. Settings  `FREE`

**Steps:** Settings → walk every section.

**What to verify:**
- [ ] Pricing, budgets, agents and tools are all editable **without editing a file**
- [ ] A saved change survives a restart
- [ ] Per-agent, per-project, session and daily caps are all settable
- [ ] API permission checkboxes gate which providers may be used at all
- [ ] A bad value is rejected with a readable message, not a traceback in the
      output box

## A9. Best Fit and the Model Guide  `FREE`

> **What it does:** the provider badge marks the best eligible provider overall;
> the model badge marks the best model inside the provider you have selected.
> It is task guidance, not proof of quality.

**What to verify:**
- [ ] A **BEST FIT** badge appears on the recommended provider and model
- [ ] Changing provider re-picks the model badge inside that provider
- [ ] Overriding the recommendation is allowed and sticks
- [ ] Model lists load without freezing the UI; a provider whose list fails to
      fetch retries on the next switch rather than staying empty
- [ ] **Model Guide** opens and describes the models actually offered

## A10. Learning Centre and "Show me"  `FREE`

> **What it does:** 26 modules in four sections. Every agent lesson carries a
> **Show-me recipe** — a step-by-step build whose `▶ Show me` links close the
> lesson, open the real control and ring it.

**Steps:** right rail → **Learning Centre**. Open **Sitebuilder** (Agent
Academy) and walk its recipe.

**What to verify:**
- [ ] Four sections appear: Start & paths, Foundations, Agent Academy, Income Lab
- [ ] All ten agent lessons have a **Recipe** section with numbered steps and
      7–9 `▶ Show me` links
- [ ] `▶ Show me` switches to the right workspace **and the right tab**, scrolls
      the control into view and rings it
- [ ] The ringed control is still **clickable** — the ring does not block the mouse
- [ ] **Back to lesson** returns to the exact step you left
- [ ] A Show-me for a control on a sub-tab opens every stack above it, not just
      the workspace
- [ ] Income Lab worksheets (break-even, contribution, funnel, cohort,
      automation payback) compute locally and send nothing

## A11. Restart recovery  `PAID-UNIT`

> **What it does:** three panels persist provider jobs and finish them after a
> restart. The spend was already approved before the crash, so resume never
> re-asks — and it settles the ledger before billing, so a crash in that window
> undercounts once rather than double-billing.

**Steps:** start a Reel direct render, a Muse teaser and a Booth conversion.
While each is in flight, quit the app (force-quit is the realistic case).
Relaunch.

**What to verify:**
- [ ] Each job is picked up and finished, or reported as failed — never silently
      stranded
- [ ] Nothing in the terminal output says a resume **failed to read** its jobs.
      All three reconcilers swallow their own exceptions, so a broken one reads
      as "nothing was pending" in the UI and only shows up in that log
- [ ] You are **not** asked to approve the spend again
- [ ] Cost History shows **one** charge per job, not two
- [ ] Booth resumes mid-book: completed chunks survive, and billing spans the
      runs honestly
- [ ] With vidforge unavailable, pending Reel rows surface as **failures**, not
      as permanent "pending"
- [ ] Relaunching twice in a row does not double-reserve or double-bill

## A12. Narrow window, every panel  `FREE`

**Steps:** drag the window to its 1000 × 600 minimum. Visit all ten agents
(nine panels plus Assistant).

**What to verify:**
- [ ] No controls overlap in any panel
- [ ] Nothing is clipped past the right edge of the centre panel
- [ ] Rails stay at their fixed widths and scroll instead of crushing their contents
- [ ] Every button remains reachable with the Tab key

---

# Part B — The agents

## B1. Author → **Quill**  `FREE` (ollama) or `PAID`

> **What it does:** plans, drafts and revises long-form fiction and non-fiction.
> Four prompts behind three flows: Write (fiction / non-fiction personas),
> Publish (synopses, query letters, proposals, blurbs, bios) and Market
> (per-platform launch copy).

**Setup:** project `UAT 2026-10-05`. Title, Author, Type. Open **Book Profile**,
add a hook and target reader, **Save Profile**.

**Test A — fiction draft keeps its context**
```
Draft the opening 300 words of chapter one. Close on a decision the
narrator cannot take back.
```
- [ ] Output uses the `[DRAFT]` / `[OUTLINE]` / `[CHARACTER]` structure
- [ ] Genre, tone and point of view from the project bar are honoured
- [ ] The saved Book Profile hook is visibly reflected, not ignored

**Test B — continuity across a long session**
Draft three chapters in sequence, adding a named character and a world note
after the first.
- [ ] Chapter three's generation carries the established **characters** and **world notes**
- [ ] It carries the **tail** of the recent draft — a window, not the whole book
- [ ] Characters and World Notes tabs stay editable and persist

**Test C — non-fiction evidence rules and the Sources tab**
Set **Type** to `Non-Fiction`.
- [ ] A **Sources** tab appears. Switch Type back to `Fiction` — it disappears
      (it is a non-fiction instrument, not a permanent tab)

Back on Non-Fiction, leave Sources **empty** and draft:
```
Draft 250 words on why most meal-planning apps lose users in week two.
```
- [ ] The non-fiction persona is used, not the fiction one
- [ ] No invented statistics, studies, surveys or named sources

Now declare sources and draft again:
```
Smith (2024), The Atlas Problem
Field interview, 2026-03-02
```
- [ ] With sources declared, the evidence rules apply: the model is told not to
      invent sources, and your declared sources are passed through verbatim
- [ ] Any claim it cannot attribute comes back marked **`[UNSOURCED]`**
- [ ] The status line counts them — `N claim(s) marked [UNSOURCED]` — and says
      **verify or cut**
- [ ] With Sources **empty** there are no evidence rules at all. An empty tab is
      decoration, not evidence, and the app does not pretend otherwise
- [ ] Sources persist with the project: switch away, come back, still there

**Test D — Publish mode**
```
Write a one-page synopsis and a query letter for the book in the profile.
```
- [ ] Fiction vs non-fiction document standards differ with Type
- [ ] Comp titles are plausible and not invented awards or sales figures

**Test E — Market mode**
- [ ] Produces per-platform copy (Amazon description, KDP package, Goodreads,
      Instagram, X thread, BookTok caption, newsletter, press release)
- [ ] No invented reviews, endorsements or chart positions

**Test F — chapters, export and Stop**
- [ ] The Chapters tab derives headings from the draft
- [ ] **Export Book** produces EPUB, DOCX and PDF from recognised chapters
- [ ] Export records a project artifact and leaves the file where you chose
- [ ] **Stop** during a Write cancels only Write — a Publish request running at
      the same time is untouched

## B2. Author → **Press**  `FREE` where noted

> **What it does:** prepares, distributes and measures a finished book —
> metadata, exports, KDP/PublishDrive data, quote discovery, launch calendar,
> sales interpretation. Five prompts, each a distinct capability.

**Test A — approved versions are immutable**  `FREE`
- [ ] **Use Project Draft** loads the current Write draft with its byline, and
      does **not** mark it approved
- [ ] **Approve Write Draft…** asks for confirmation, then creates a numbered,
      immutable snapshot
- [ ] Editing in Write afterwards does **not** change the approved snapshot
- [ ] **Use Approved Version** loads the snapshot into Quote Finder
- [ ] **Export Approved…** creates a file from the snapshot and saves a fingerprint

**Test B — the submission ledger records, it does not submit**  `FREE`
- [ ] **Submission Ledger…** records a self-reported retailer submission against
      a matching export, with a reference or evidence file
- [ ] Nothing is sent to any retailer, and nothing claims to be verified
- [ ] A ledger row with no matching export is refused

**Test C — integrations wear their last sync outcome**  `FREE`
Use **Refresh Data** (PublishDrive) and **Ingest KDP** on the Overview toolbar.
- [ ] A **persistent strip under the toolbar** records each integration's last
      outcome: timestamp, ok/FAILED, and the exact note or error
- [ ] A **failed** PublishDrive fetch still reads as failed after you click
      something else, and after a restart — it is not a status flash that vanishes
- [ ] A clean KDP ingest records its row count
- [ ] A KDP ingest error is recorded, not raised into a Qt traceback
- [ ] The strip uses plain words — no emoji or glyphs in control labels
- [ ] A never-synced integration says so rather than showing zeros

**Test D — KDP royalties as a chart**  `FREE`
Drop two KDP CSVs (and one deliberately corrupt file) into the reports folder.
- [ ] Marketplace totals **merge across all reports**, not just the newest
- [ ] The corrupt file is skipped without killing the summary
- [ ] Royalties render as the house horizontal bar chart
- [ ] **No data renders as a sentence**, not as an empty axis pretending to be a chart
- [ ] Figures are labelled as observations for their source and window — not as
      a forecast

**Test E — Quote Finder honesty**  `PAID`
```
Suggest 10 quotable lines from the approved version.
```
- [ ] Lines are copied **verbatim** — nothing paraphrased or invented
- [ ] Each stands alone without context and reads in a few seconds
- [ ] You can verify every line against the source text

**Test F — quote graphics, shorts and the calendar**  `PAID-UNIT`
- [ ] Graphics generate at the chosen theme and size; **Open Folder** finds them
- [ ] Shorts generate with narration and play back
- [ ] The calendar exports CSV
- [ ] Nothing in this tab claims a prepared calendar is a posted calendar

## B3. Audio + Music → **Booth**  `PAID-UNIT`

> **What it does:** converts books to audiobooks (MP3, or M4B with chapters),
> resumably, and plays them back with marks and resume positions.

**Test A — the config block**  `FREE`
Paste into the connector input:
```
input=/path/to/book.epub
output=/path/to/out
voice=nova
chunk_tokens=1200
```
- [ ] Parses to a dict with those values
- [ ] Omitting `voice` and `chunk_tokens` defaults to `alloy` and `1500`
- [ ] Omitting `input=` raises a clear error
- [ ] Omitting `output=` raises a clear error

**Test B — discovery and estimate**  `FREE`
- [ ] **Refresh List** finds books in the input folder
- [ ] **Use Project Book** adds the project's linked TXT/EPUB/PDF **without**
      changing the configured input folder
- [ ] The cost estimate is computed from the **exact text**, not a page guess
- [ ] An EPUB is read in **spine order**, not filename order
- [ ] A source file changed since the last run is noticed and said so

**Test C — convert a short book**  `PAID-UNIT`
- [ ] Progress and log advance per chunk
- [ ] **Stop** mid-run: completed chunks survive on disk
- [ ] Resuming bills only the chunks it actually narrates
- [ ] On success the source (unless already linked) and the verified MP3 link to
      the project that was active when **Start** was pressed
- [ ] M4B output carries **embedded chapters**

**Test D — Listen and the player**
- [ ] **Rescan** lists audio with saved progress attached
- [ ] Resume position applies only once the media has actually loaded — the
      playhead is not silently dropped
- [ ] Progress persists on a timer and on pause/stop, not only on clean exit
- [ ] A book played past 99% is marked **finished**, not parked a second short
- [ ] Renaming or re-converting a file does not move progress to the wrong book
- [ ] **Chapters & marks** lists embedded chapters and saved marks; Add mark,
      Speed and Sleep all work
- [ ] **Current Project** shows only linked audiobooks; the default shows all

## B4. Audio + Music → **Label**  `PAID`

> **What it does:** artist positioning, release setup, distribution and Spotify
> strategy, plus an income roadmap. Fixed five-section output. Plans are records,
> and the next plan learns from the last release.

**Input:**
```
Solo artist "Harbour Lights", melancholic indie folk, first EP of five tracks,
ready to master, no distributor yet, budget under 50 EUR a year, based in Germany.
```
**What to verify:**
- [ ] All five sections present: Artist Profile, Release Setup, Distribution
      Guide, Spotify Strategy, Income Roadmap
- [ ] Short bio ≤150 chars; playlist pitch ≤500 chars
- [ ] Every generated block marked `[AI OUTPUT — COPY-PASTE READY]`
- [ ] Every manual step marked `[HUMAN ACTION REQUIRED]`
- [ ] Distribution compares DistroKid / TuneCore / CD Baby against the stated
      budget, not generically
- [ ] Income Roadmap is labelled as **scenarios with assumptions** — streams ×
      a static rate is never presented as a forecast
- [ ] No invented Spotify feature; anything possibly changed since the model's
      cutoff is flagged

**Test B — a thin brief is questioned, not filled in**
```
Help me release my music.
```
- [ ] It asks for artist name, genre, release type/readiness and distributor
      status rather than inventing them

**Test C — plans are records**  `FREE`
- [ ] **Save Full Plan** persists the plan as a record
- [ ] Recording an outcome against it picks the **shipped** plan explicitly
      (prefilled and outcome-marked) rather than guessing
- [ ] An empty artist name is refused
- [ ] An all-blank outcome entry records **nothing**
- [ ] A later plan visibly draws on the previous release's recorded outcome

**Test D — Songs & Albums**
- [ ] Lyrics and Suno style prompts save alongside the imported audio
- [ ] Save before Clear is respected — Clear is not undo

## B5. Video + Ads → **Reel**  `PAID-UNIT`

> **What it does:** two routes — an assembled pipeline (script → narration →
> captions → visuals → clips → audio → assembly → thumbnail) and direct
> provider generation. Jobs are durable across restarts.

**Test A — preflight**  `FREE`
- [ ] Aspect and clip-length options adapt to the selected provider/model capability
- [ ] Only implemented adapters appear; the badge reflects actual capability
- [ ] An estimate and reserve appear before submission

**Test B — the assembled pipeline**  `PAID-UNIT`
- [ ] Each stage is named as it runs
- [ ] The finished clip plays from the Library
- [ ] The clip links to the project captured **at authorization**

**Test C — the direct-provider Stop contract**  `PAID-UNIT`
This is the case most recently fixed — check it closely.
- [ ] For a Gemini/Wan direct render the button is **enabled** and labelled
      **Stop** — not disabled and labelled "Cannot Cancel"
- [ ] The submit message states the real contract: a provider that has already
      accepted the job may still bill
- [ ] Pressing Stop during the window before the provider acknowledges still
      leaves the row wired for the late job signal
- [ ] Stopping **keeps** the session's budget reservation — only the run log
      closes, because a continuing render will still bill

**Test D — the Library**
- [ ] Defaults to all renders, including standalone vidforge builds with no
      Imprint project
- [ ] **Current Project** filters to linked clips
- [ ] Play, Show in Finder and Rescan all work

## B6. Social → **Herald**  `PAID` to draft, `FREE` to inspect

> **What it does:** turns work made elsewhere in Imprint into platform-native
> posts. Five subject kinds × six angles. A durable delivery ledger stops
> duplicate posts and refuses to guess after an ambiguous API result.

**Test A — drafting**  `PAID`
Campaign: subject kind `book`, angle `launch`, platform X/Twitter, 3 variants.
- [ ] Three **genuinely different** variants, split on the `---` separator
- [ ] A response that ignored the separator still yields one usable variant
      rather than nothing
- [ ] Per-platform tone and length guidance is visibly applied (X terse,
      Reddit non-promotional, Pinterest keyword-led)
- [ ] An over-length draft reports the **character overage** before you can post it

**Test B — what the system prompt forbids**  `PAID`
Ask for a post that implies reviews and sales figures.
- [ ] No invented reviews, testimonials, endorsements, sales figures, chart
      positions, follower counts or press quotes
- [ ] Nothing written in the voice of a named third party
- [ ] No engagement bait ("comment YES", fake scarcity)
- [ ] A few specific hashtags, not a wall of generic ones

**Test C — connection onboarding states what it grants**  `FREE`
Accounts tab → open the guide for Reddit.
- [ ] The guide **leads with what connecting lets Imprint do** ("lets Imprint…"),
      then "To connect:"
- [ ] Named scopes appear in plain words (e.g. `scope: submit`)
- [ ] The exact credential keys are listed (e.g. `REDDIT_CLIENT_ID`)
- [ ] Numbered setup steps, 1. and 2. onward
- [ ] It warns honestly where the script flow holds a password
- [ ] Every publisher declares scopes **and** steps; a drafting-only platform
      has an empty guide rather than a fake one
- [ ] No publisher claims to be ready without its credentials; an unconfigured
      one **names what is missing**
- [ ] Credentials are never written to the database

**Test D — the delivery ledger**  `FREE` (use an unconfigured platform)
- [ ] A publish job is written **before** the network attempt
- [ ] A job can be claimed only once — double-clicking Post Now posts once
- [ ] A known rejection is retryable against the same delivery record
- [ ] An **uncertain** result cannot be retried without an explicit override
- [ ] After a restart, an in-flight post is never blindly retried
- [ ] A completed delivery blocks every later publish attempt
- [ ] Manual resolution closes an uncertain job
- [ ] A failed post records **why**

**Test E — schedule and analytics**  `FREE`
- [ ] Reddit is scheduled at most once a week; a weekly allowance is spread, not stacked
- [ ] The schedule orders by date; undated drafts sort after scheduled posts
- [ ] Deleting a campaign takes its posts with it
- [ ] Metrics require a **posted** state and a stated source and window
- [ ] "Scheduled" is never presented as "posted"
- [ ] Reach/clicks render as the shared chart; clicks are not presented as sales

**Test F — Make a Clip**  `PAID`
- [ ] Produces a single self-contained topic sentence handed to Reel
- [ ] Herald does **not** write the video script itself

## B7. Web → **Sitebuilder**  `FREE` (ollama) or `PAID`

> **What it does:** generates complete, self-contained, mobile-first HTML, CSS
> and JS. Vanilla unless a framework is named.

**Setup:** Page type `Landing Page`, Style `Minimal`, Framework `Vanilla`,
palette `#0f766e, #f8fafc, #f59e0b · calm teal with a warm amber accent`.

**Input:**
```
One-page site for Paws & Suds, a dog groomer in a small town.
Sections, in order:
1. Hero: name, one-line promise ("Clean, calm, happy dogs"), button
   "Book a groom" that calls [PHONE].
2. Services: Bath & brush, Full groom, Nail trim — each with [PRICE].
3. About: two sentences, friendly, family-run.
4. Opening hours and address: [HOURS], [ADDRESS].
5. Footer: phone, email [EMAIL], small print "© Paws & Suds".
Must: work on phones first, readable at 200% zoom, every button reachable
with the Tab key, visible focus outline, alt text on any image.
Must not: testimonials, star ratings, awards, invented prices, tracking
scripts, cookie banners, external fonts.
```

**What to verify:**
- [ ] HTML, CSS and JS land in their three tabs and are individually editable
- [ ] The page is self-contained, semantic and mobile-first
- [ ] Every `[PLACEHOLDER]` survives — **no invented prices, phone or address**
- [ ] None of the "Must not" items appear
- [ ] Hover and focus states exist; focus outline is visible
- [ ] CSS custom properties rather than inline styles; vanilla ES6+, no jQuery
- [ ] Sections appear in the order given

**Test B — the two exports, and the checks you rule on**
- [ ] **Save .html** writes one self-contained file; opening it in a real browser
      renders and the JS runs
- [ ] **Export Project…** writes a folder of exactly `index.html`, `styles.css`
      and `script.js`, with the inline assets extracted and referenced
- [ ] The status says how many files were written
- [ ] On a clean page the status reads **Checks passed**
- [ ] Introduce a fault (delete an image's `alt` text). Export now reports its
      **findings and asks you to rule on them**
- [ ] **Declining** writes nothing — no folder dialog, status says cancelled
- [ ] **Accepting anyway** exports with the fault; the choice is yours, not the
      app's
- [ ] **Copy All** copies the complete proposal
- [ ] **Clear** clears visible output only — it is not undo, and a save is not
      implied
- [ ] A denied paid request leaves **Generate** available

**Test C — an underspecified brief**
```
Make me a website.
```
- [ ] It asks about purpose, audience, palette and style instead of inventing a business

## B8. Brand Design → **Stamp**  `PAID` / `PAID-UNIT`

> **What it does:** client-service work — logo concepts, gig listing copy and
> delivery messages. One durable order per client, with a reusable brand kit.

**Test A — delivery message**  `PAID`
```
Client: a two-person law firm, Hale & Brandt. Delivered: three logo concepts,
primary wordmark, and a one-page usage sheet. One revision round included.
```
- [ ] Warm opening, the design reasoning, one revision round offered, professional sign-off
- [ ] Under 200 words, no jargon
- [ ] It never asserts work or checks that were not performed (no claimed
      trademark search, no claimed print test)

**Test B — gig description**  `PAID`
- [ ] Hook headline, 5–7 "what you get" bullets, differentiators,
      Basic/Standard/Premium with prices, call to action
- [ ] Under 400 words, first person
- [ ] Price, turnaround and revision claims are truthful and match what Orders records

**Test C — logo concepts**  `PAID-UNIT`
- [ ] The prompt is a bare 1–3 sentences: style, colours, mood
- [ ] It appends "vector logo, transparent background, no text" unless a
      business name was explicitly asked for **in** the logo
- [ ] Logo Preview shows the actual generated asset
- [ ] Spelling, dimensions and brand fit are verifiable before delivery

**Test D — orders and the brand kit**  `FREE`
- [ ] One durable order per client — changing the client **re-derives** the order
- [ ] **Clear** resets the held order id
- [ ] Reusing a brand kit **merges** into the order; it does not erase it
- [ ] A reload writes unconditionally; a refresh **keeps the current selection**
- [ ] Reads are guarded — an empty or missing order does not crash the panel
- [ ] **Stop** cancels the active local generation; provider-accepted media may
      still have cost, and the message says so

## B9. Brand Content → **Muse**  `PAID`

> **What it does:** platform-neutral campaign content — voice profiles,
> concepts, captions, campaigns, promo assets and a plan calendar. It is a
> drafting tool with **no send path**.

**Test A — the draft kinds**  `PAID`
- [ ] Available kinds are post, caption, posting_plan, promo_assets, promo, bio,
      campaign, hooks
- [ ] A promo draft names the channel it targets (X/Twitter, Reddit, TikTok,
      Instagram, Threads)
- [ ] Account handle, platform/venture and notes reach the prompt

**Test B — the boundaries**  `PAID`
- [ ] No prompt asks about authorisation or consent — that moved to Backstage
- [ ] It will not write in the voice of a live named human
- [ ] Generated video prompts are safe-for-work by construction
- [ ] A prohibited request is **refused with a reason**, and the refusal happens
      before any network call
- [ ] A negated mention ("no nudity") is not treated as a request for it
- [ ] A missing API key gives a clear error, not a traceback

**Test C — the calendar**  `FREE`
- [ ] A scheduled draft keeps the project **and** the account captured when
      generation was approved
- [ ] Switching accounts before scheduling is **refused**
- [ ] Calendar and Media default to all work under the selected account;
      **Current Project** filters to linked items
- [ ] Deleting the project unfiles content and jobs but keeps the account, its
      voice and character records, and the media

**Test D — teaser resume**  `PAID-UNIT` (covered in A11)
- [ ] A teaser in flight at quit is finished or failed after relaunch, billed once

## B10. Assistant → **Chat**  `FREE` (ollama) or `PAID`

> **What it does:** general-purpose conversation for a bounded question that
> does not belong to a specialist agent. Streams from every provider.

**Input:**
```
Explain the difference between an EPUB and an M4B to someone who has
published neither.
```
**What to verify:**
- [ ] Conversational and clear; no structured sections forced onto a plain answer
- [ ] No system-prompt text bleeding into the reply
- [ ] Output **streams** token by token — including on ollama, which used to
      wait and then dump
- [ ] Selecting a **Tool** adds its task frame; a **Command** inserts a scaffold
- [ ] **Stop** mid-stream ends it and closes the stream (check `ollama ps`)
- [ ] An ollama error frame surfaces as an error, not as silence
- [ ] Saved Chats reopens the thread with its context; a new chat starts clean
- [ ] Switching provider mid-conversation carries the context

---

# Part C — Boundaries that must hold

A pass here is the app **refusing** something or **telling the truth** about a
limit. These are the cases where a regression costs money or credibility.

## C1. No paid path outside the guard  `PAID`

Every billable action in the app must pass through `authorize_request`.
- [ ] Walk every panel's paid buttons: Write, Continue, Publish, Market,
      Suggest Quotes, Generate Graphic, Shorts, Start (Booth), Render Video,
      Draft (Herald), Generate (Sitebuilder), logo/delivery/gig (Stamp),
      Muse drafts and teasers, Send (Chat)
- [ ] Each shows an estimate and can be declined
- [ ] Per-unit paths (TTS, image, video) are guarded too, not just token paths

## C2. Honest money language everywhere  `FREE`

- [ ] No screen presents an **estimate** as a recorded cost
- [ ] No screen presents **unpriced** as free
- [ ] No screen presents a **scenario** (streams × rate, projected royalties) as
      a forecast
- [ ] Revenue attribution cards state their source and window, and do not claim
      a platform number Imprint cannot see
- [ ] Charts with no data say so in a sentence

## C3. The Backstage boundary  `FREE`

Muse is platform-neutral. Account consent records, platform-policy review,
statement import, per-asset revenue and the agency view belong to Backstage.
- [ ] None of those appear anywhere in Imprint
- [ ] `pytest tests/test_creator_agent.py -k platform_specific` passes

## C4. Retired names  `FREE`

- [ ] `pytest tests/test_retired_names.py` passes — the venture retired on
      2026-09-27 is referenced in no tracked file, path or fixture
- [ ] Nothing in the UI says "Sentinel", "Audiobook Studio" or "vidforge" as if
      it were a separate app the user should open

## C5. Converter drift  `FREE`

The narrator converter exists in both `imprint` and `lab_hub`.
- [ ] `pytest tests/test_converter_drift.py` passes
- [ ] The same test passes in `lab_hub`

## C6. Archived surfaces stay archived  `FREE`

- [ ] The Primer CLI (course generator) is not reachable from the app
- [ ] No paid workflow exists outside the GUI's guard

---

# Appendix — where the automated coverage lives

Hand-test what a human has to judge. Everything below is already pinned by the
suite, so a UAT pass should not re-derive it:

| Area | Tests |
|---|---|
| Agent prompt construction | `test_agents_scenarios.py` |
| Router decisions and addressing | `test_agents_scenarios.py` (`TestRouterAgent`) |
| Validator rules, token and cost maths | `test_cost_and_limits.py` |
| Authorize / record / abandon / restore | `test_request_guard.py` |
| Quill continuity and evidence rules | `test_author_continuity.py` |
| Press pipeline, KDP parsing, charts | `test_book_pipeline.py`, `test_manuscript_charts.py` |
| Booth conversions, player, converter | `test_audiobook_conversions.py`, `test_audiobook_player.py`, `test_narrator_converter.py` |
| Label plans | `test_music_plans.py` |
| Reel jobs and resume | `test_video_jobs.py`, `test_media_generation.py` |
| Herald drafting, queue, publishing, onboarding | `test_social.py`, `test_social_onboarding.py` |
| Sitebuilder export | `test_webdesign_export.py` |
| Stamp orders | `test_fiverr_orders.py` |
| Muse drafting, calendar, resume | `test_creator_agent.py`, `test_creator_v2.py`, `test_creator_calendar.py` |
| Chat streaming and projects | `test_chat_streaming.py`, `test_chat_projects.py` |
| Layout at every width | `test_panel_layout.py`, `test_agent_panel.py` |
| Learning Centre and recipes | `test_learning_center.py`, `test_learning_shots.py` |

Run the whole suite before a UAT session:

```
.venv/bin/python -m pytest -q
```

### If the suite hangs instead of finishing

Observed 2026-10-05: a full run wedged for 25 minutes with four seconds of CPU.
A stack sample put the main thread in `QObject::disconnect` under
`ui/widgets.py:polish_combo` → `QComboBox.setStyle()`, blocked on a Qt mutex,
while three `QFFmpeg` audio threads from `tests/test_audiobook_player.py` were
still alive — those tests build six `AudiobookPlayer` instances and never
release them. The next full run passed (944 tests, 90s), so it is
order-and-timing dependent, not deterministic.

It matters here because a wedged run produces **no output at all** under `-q`
and looks identical to a slow one. If that happens:

```
.venv/bin/python -m pytest -q --ignore=tests/test_audiobook_player.py
```

then run `tests/test_audiobook_player.py` on its own. Both halves pass in about
110 seconds combined. Do not start a UAT session on the assumption that a
silent run is a passing run.
