# Publish

> **Outcome:** move an approved manuscript through one traceable packaging,
> promotional-asset, scheduling, or sales-data task.

## Prerequisites

- Final or deliberately versioned manuscript/metadata.
- Rights and factual claims reviewed.
- Real platform data exported where an API is unavailable.

## Control atlas

| Tab/area | What it does | Required interpretation |
|---|---|---|
| Overview | Sync strip, reporting period, royalties-by-marketplace chart, metrics box, Ask, publishing todos, Connections | Imported/refreshed rows are observations only for their source/window |
| Quote Finder | Load File, candidate count, voice, Suggest Quotes; Approve Write Draft, approved-version picker, Export Approved, Make Release Kit, Submission Ledger | Suggestions require source-text verification; a release kit is made from an approved version only ([Make a release kit](#make-a-release-kit)) |
| Quote Graphics | Quote, attribution, theme, size, Generate Graphic, Open Folder | A generated asset is not licensed proof or performance evidence |
| Shorts | Quote/narration, attribution, theme, voice source/narrator, Generate, Play, Folder | Review audio, claims, timing, and platform rules |
| Calendar | Weeks, start, platforms, theme, voice, attribution, Generate, Export CSV | A prepared calendar is not a post or measured distribution |

## Worked run

1. In Overview, refresh only configured sources. For KDP, ingest the correct
   CSV once and retain the source file. State its account, currency, and window.
2. Add one publishing todo with a verifiable completion condition.
3. Load the authoritative manuscript in Quote Finder. Request a small candidate
   set and verify every quote character-for-character against the source.
4. Create one graphic and one short from an approved quote. Open the output
   folder and inspect the real files.
5. Generate a one-week calendar from the approved candidates. Review captions
   and dates, then export CSV.
6. Ask a narrow question of owned data, preserving unknown attribution instead
   of forcing a causal story.

## How to read the output

Connections show configured access, not guaranteed freshness. A report row is
only as current as its refresh/import and definition. Quote candidates and
captions are model proposals. Calendar items are prepared work. None proves
reach, sale, or contribution until matching platform/transaction data exists.

## Acceptance checklist

- [ ] Manuscript quote and attribution match the source.
- [ ] Reporting source, window, currency, and import filename are recorded.
- [ ] Duplicate/overlapping statements are not added to one total.
- [ ] Graphics/shorts pass rights, readability, audio, and platform review.
- [ ] Calendar items link to one offer and measurable next action.

## Cost, cancellation, and gates

Text, image, and speech routes can have separate providers and prices. Include
discarded variants and correction time. Human gates remain for store submission,
pricing, public claims, publishing, and final asset selection.

## Common failures

**Metrics are empty:** no owned report was refreshed/imported.  
**Calendar is empty:** run Suggest Quotes first.  
**A quote is persuasive but wrong:** reject it; model fluency is not provenance.  
**Sales changed after reimport:** check overlapping periods and deduplication.

## Done when

One approved asset/task is saved, its source and cost are known, and its later
distribution/outcome can be matched to a platform record.

## Next action

Use [Social](25-social.md) for reviewed distribution preparation and
[Funnels, attribution, and cohorts](34-funnels-attribution.md) for measurement.

## Recipe: take one book from finished draft to first sales report

You will take one finished draft — *You Don't Chase* in the examples — through
an immutable approved version, an exported file, a self-reported submission
record, and its first ingested KDP sales report, so that what you sent, where
you sent it and what it earned sit in one place. Copy the example inputs
exactly the first time, then swap in your own. Each **▶ Show me** closes this
lesson, opens the control it names and rings it; **Back to lesson** in the
callout brings you back to that step.

**Time:** about 20 minutes at the desk — the sales report itself appears on
Amazon's schedule, not yours. **Cost:** one text request in Imprint, at the
Ask step — you see its estimate and approve it before anything is sent. This
panel's provider list has no local Ollama option, so that one request is
always metered. Every other step is free: approving, exporting, the ledger,
the CSV ingest and the todo list are local file and database writes.

### Step 1 — Approve the draft as a version

Open the **Quote Finder** tab — Show me opens it for you. With the book's
Project selected, click **Approve Write Draft…**. Imprint reads the Write
editor as it stands right now (unsaved edits included) and shows the title,
byline and word count before you confirm. The captured version is immutable:
later Write edits do not change it, and it appears in the picker as
*Approved v1* with its character count and SHA-256 fingerprint in the
tooltip. Approving unchanged text again does not mint a new version.

[Show me](show:quote_approve_btn)

### Step 2 — Export the file you will actually submit

Leave the format box on **EPUB** (DOCX and PDF are the other options) and
click **Export Approved…**. The file is built from the approved snapshot you
selected, never from whatever the Write editor shows today; for the example
book the proposed name is `You_Dont_Chase_v1.epub`. The status line ends with
the sentence that matters: submission is separate and must be recorded
explicitly. There is no KDP or Draft2Digital API — the upload itself is
yours, in their dashboards.

[Show me](show:quote_export_approved_btn)

### Step 3 — Record the submission, labelled as yours

After you have uploaded the export to the store yourself, click
**Submission Ledger…** and select the export — Imprint checks its file hash
first, so the row can say *Matches receipt*, *Changed file* or *Missing
file*. Then fill the form:

```
Retailer / distributor:  KDP
Date you submitted:      2026-10-05
Reference:               KDP Bookshelf, status "In Review"
Evidence file:           (optional) a saved confirmation receipt
```

The button is named honestly: **Record self-reported submission**, listed
under *Recorded submissions — not retailer-verified*. The ledger never sends
a file to a retailer and never verifies their receipt; it is your evidence
trail, only as true as you keep it.

[Show me](show:quote_submission_ledger_btn)

### Step 4 — Ingest the first KDP report

KDP has no API, so the report starts as a manual download:

```
KDP Dashboard > Reports > Sales Dashboard > Download
Drop the CSV into:   data/kdp_reports/
```

Back on the **Overview** tab, click **Ingest KDP CSV**. Files already
ingested are skipped by filename — the status says *No new KDP reports
found* — and that is the only deduplication: a renamed copy or an
overlapping date range counts twice. Keep one file per period and keep the
original filename.

[Show me](show:manuscript_ingest_btn)

### Step 5 — Read the sync strip, not your memory

The line under the top bar wears each integration's last outcome. After
step 4 it reads something like `KDP reports: ok 2026-10-05 14:02 — 1 new
report(s)`, and it persists: a failed import still says `FAILED` with the
exact error after a restart, instead of vanishing with the status flash.
Read it as the last outcome, not as freshness — an import from March stays
*ok* forever. *Never synced* means step 4 has not happened.

[Show me](show:manuscript_sync_label)

### Step 6 — Read royalties by marketplace

The chart now shows royalties per marketplace, largest first, with units as
the thin second bar. It re-reads every CSV in `data/kdp_reports/` each time,
so it shows exactly what is in that folder — including any overlap you left
there. Two cautions. First, the numbers are summed straight from the Royalty
column with no currency conversion: the bars carry a `$` only when every row
in your reports says USD, and otherwise show plain figures — hover the chart
to see whether the reports are in one named currency, mixed (summed as
reported, not converted) or state no currency at all. If a report file cannot
be read, or rows have numbers it cannot parse (a decimal comma, say), the
status line warns that they are missing from the chart. Second, everything
here is a past observation for the windows your reports cover. Nothing on
this chart predicts next month.

[Show me](show:manuscript_royalty_chart)

### Step 7 — Ask one narrow question of loaded data

Ask sends your question together with the JSON that **Refresh Data** last
loaded into the metrics box — and only that. The ingested KDP rows and the
chart are not part of the context, so if PublishDrive is connected, click
**Refresh Data** first; if nothing is loaded, the model gets your question
alone. Type the question, pick a provider and model, click **Ask**, and
approve the estimate Imprint shows you. The answer streams into the metrics
box.

```
Using only the CURRENT DATA you were given: which store sold the most
units, and what royalty does the data show for it? Answer "not in the
data" for anything the data does not contain.
```

**Good result:** the answer cites figures you can see in the metrics box and
says "not in the data" where the data runs out. **Weak result:** confident
numbers about your sales when no data was loaded — that is invention, not
analysis; read the chart instead.

[Show me](show:manuscript_query_input)

### Step 8 — Leave the next gate on the todo list

The list arrives pre-seeded with the real account-creation and upload steps
for KDP, Draft2Digital, IngramSpark, BookBub and the social platforms —
hover an item for its notes. Add one todo for this book with a completion
condition someone else could verify, then press **Add**:

```
Submit You_Dont_Chase_v1.epub to KDP — done when the Bookshelf status
reads "Live" and the ledger row carries that date
```

Select it and click **Done** only when that condition is actually true.
Marking it done is self-reported: it changes your list, not the store.

[Show me](show:manuscript_todo_input)

## Make a release kit

**Make Release Kit…** turns one approved version into a folder of release
files on this Mac, with one confirmation. Nothing is posted, scheduled or
submitted, and the kit claims nothing about income, reach or results. This
first version runs free, local steps only.

**Before you start:** a Project with an approved version ([Step 1 — Approve the draft as a version](#step-1--approve-the-draft-as-a-version)), a
title and byline on that version, and a local model running in Ollama or LM
Studio for the quotes and captions. One kit runs at a time. When the button
is off, the note under the row says why.

### Step 1 — Open the kit's confirmation

In **Quote Finder**, pick the approved version in the picker and click
**Make Release Kit…** (right after **Export Approved…**).

[Show me](show:release_kit_btn)

### Step 2 — Read the confirmation, then start

Read the confirmation. It lists the source (Project, version, word count,
title, byline), a new output folder named `<Title>_v<N>_<date>` (**Change…**
picks another empty folder), and eight steps with their routes. It says "No
charge": every step runs on this Mac. The Audiobook row is "Not included",
because narration is always paid; narrate in Booth.
Anything paid blocks Start with a "Cannot start:" line. Escape cancels;
nothing is written until **Start**.

Click **Start**. The **Release Kits** window shows "Step N of 8", a table of
Step · State · Spent · Line, and **Stop**, **Resume**, **Discard**, **Show
Folder** and **Show Report**. Closing the window does not stop the kit. When
it finishes, click **Show Report** and read `release-kit-report.md`.

### What the kit contains

The eight steps: an EPUB of the approved version with its SHA-256
receipt; Audiobook (not included); up to 20 quotes, each kept only if it
appears word for word in the book and is at most 280 characters; a 4-week
calendar for the platforms you tick; one quote graphic per quote; one Short
per Short slot; captions for every post in one request, then `calendar.csv`
with an **AI used** column; last, every file is linked to the Project and the
report and `provenance.json` are written.

**How to read the result:**

- **Incomplete** on the captions step means the reply stopped early: the
  later posts have no caption, and the report says how many.
- Quotes the model returned that are not in the book word for word, or are
  too long, are not used; the report counts them.
- **Shorts use the macOS voice for testing only.** Apple's licence limits its
  built-in voices to personal, non-commercial use; decide before posting
  these Shorts publicly.
- The report's "AI used in this kit" section and the CSV's **AI used**
  column are records of fact, not labels: nothing is embedded in the files,
  and each store or platform has its own rules for AI content.

**Stop, quit and resume.** **Stop** finishes the current item and pauses;
it deletes nothing. Quitting while a kit runs asks: **Keep Running** or
**Quit and Pause**. A paused kit, or one interrupted by a crash, is offered
at the next launch; **Resume** checks each finished file against its SHA-256,
skips the good ones ("Done earlier") and runs the rest. **Discard** asks
first and keeps the files. A local model that does not answer, a failed
render or any error pauses the kit with the reason; it is never re-routed by
itself. The Mac is kept awake while a kit runs (a closed lid still sleeps
it).

**Done when:** the report lists every step as done, or names why one is
incomplete, and you have checked each quote against the book before using
it anywhere.
