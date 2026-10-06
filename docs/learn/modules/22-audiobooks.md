# Audiobooks

> **Outcome:** create and inspect a short narration sample before authorising a
> full book conversion, then recover listening progress and partial output.

## Prerequisites

- PDF, EPUB, TXT, MOBI, or AZW3 source you are authorised to process
  (MOBI and AZW3 also need Calibre's `ebook-convert` installed).
- OpenAI TTS access; audiobook narration uses it independently of text choices
  elsewhere.
- Writable input/output folders and sufficient cap for the estimated length.

## Control atlas

| Tab | Controls | Meaning |
|---|---|---|
| Convert | Book list, input folder, output folder, Voice, Chunk tokens, Start, Refresh List, Stop, progress/log | Extract, chunk, narrate, and assemble; completed chunks may survive a stop |
| Listen | Rescan, library, Listen, Start Over, Show in Finder | Play completed audio and persist progress keyed to its full path |
| Player | Chapters & marks, Add mark, Speed, Sleep, ±30s | Jump to embedded chapters or saved marks, adjust speed, and pause after 15–60 minutes |

## Worked run

1. Put one short authorised sample in the input folder and press **Refresh List**.
2. Select the book and explicitly verify the output folder.
3. Choose Voice. Treat Chunk tokens as a stability/context trade-off: larger
   chunks reduce joins but increase the impact of one failure.
4. Read the automatic cost state. If price or extracted length is unknown, do
   not infer zero cost.
5. Press **Start** once and follow extraction, chunks, narration, assembly, and
   output messages in the log.
6. Listen to beginning, one join, difficult names, and the ending. Inspect the
   MP3 in Finder.
7. In Listen, pause, leave, return, and verify progress resumes. **Start Over**
   deliberately resets that path's listening position.
8. Open **Chapters & marks** to jump to chapter metadata when the file has it,
   or add your own labelled marks. Space pauses/plays; Left and Right skip 30
   seconds. Choose a Sleep interval to pause automatically; Off cancels it.

## How to read the output

A progress value reports pipeline stage, not pronunciation quality or final
rights clearance. A partial job may contain billable, reusable chunks even when
the assembled MP3 is absent.

## Acceptance checklist

- [ ] Source extraction is complete and ordered correctly.
- [ ] Voice, names, punctuation, joins, silence, and loudness are acceptable.
- [ ] Output path and file duration are correct.
- [ ] Full-book estimate/cap includes retries and review time.
- [ ] Rights to narrate and distribute the source are documented.

## Cost, cancellation, and gates

Speech can be billed by characters/tokens. Stop requests the subprocess to end;
it does not reverse completed chunks or charges. Human approval is required
before full conversion and distribution.

## Verification

Play the local sample from its real output path, inspect at least one chunk join,
and confirm Listen restores progress before approving a full conversion.

## Common failures

**No books:** verify format/folder, then Refresh List.  
**Stopped part-way:** inspect output/log and completed chunks before restarting.  
**Resume disappeared:** moving or renaming the MP3 changes its path identity.  
**Bad pronunciation:** test a shorter excerpt/voice; do not discover it after a
full book.

## Done when

The sample passes audio review, the output and cost state are known, and a full
conversion has a reviewed budget and recovery plan.

## Next action

For a catalogue, connect the accepted audiobook to [Publish](21-publish.md) and
measure the release as a cohort rather than an output count.

## Recipe: convert one book and keep your place

You will turn one short text you own into a finished MP3 audiobook called
*The Night Shift*, prove that an interrupted conversion resumes without paying
twice, and listen to the result inside Imprint. Copy the example inputs exactly
the first time, then swap in your own. Each **Show me** closes this lesson,
opens the control it names and rings it; **Back to lesson** in the callout
brings you back to that step.

**Time:** about 15 minutes of your attention; the narration itself runs
unattended. **Cost:** one OpenAI text-to-speech job — the estimate line under
the Convert button shows the expected audio length and price in euros, and you
approve exactly that amount before anything is sent. There is no free local
option for narration: every narrated chunk bills your OpenAI account, so start
with a short text. On a resume, only the chapters still missing are put up for
approval — chapters already cached are not re-paid.

### Step 1 — Put one short book in the input folder

Click **Open input** to open the input folder in Finder, then save a text you
hold the rights to into it. Short is the point of the first run: you are
testing voice and joins, not producing a catalogue.

```
File name:  the-night-shift.txt
Contents:   one chapter or short story you own the rights to
            (roughly 1,500–3,000 words keeps the first run cheap)
```

PDF, EPUB, MOBI and AZW3 work too (MOBI and AZW3 need Calibre installed);
a plain .txt removes extraction surprises on the first try.

[Show me](show:audiobook_open_input_btn)

### Step 2 — Refresh the list and select the book

Click **Refresh List**. Your file appears in the book list; with a single book
it is selected automatically. The moment a book is selected the estimate line
fills in, in the form `~12 min audio · ≈ €0.35` — if it says the file could
not be read, fix the source before going further rather than assuming the run
is free. If your book is a draft or export from a Write Project, **Use Project
Book** adds it to this list without changing your input folder.

[Show me](show:audiobook_book_list)

### Step 3 — Decide where the audio goes

**Save converted audio** offers two homes: **On this Mac**, or a **Google
Drive folder** you have synced — pick Drive if you want to listen from
another machine. Check the output folder path below it and use **Set output**
to change it. Decide now: the finished file's path is also its identity for
listening progress, so moving it later loses your place.

[Show me](show:audiobook_output_mode)

### Step 4 — Pick voice, chunk size and format

Set the three conversion options. Open the Voice menu to see Imprint's
best-fit default before overriding it.

```
Voice:                marin
Chunk size (tokens):  1400
Format:               MP3
```

1400 is a stable chunk default; smaller chunks recover more easily if one
request fails, at the price of more joins. MP3 copies the narrated chunks
losslessly and plays anywhere; **M4B (chapters)** re-encodes to AAC and
carries chapter marks taken from an EPUB's own sections — pointless for a
.txt, worth it for a real EPUB.

[Show me](show:audiobook_voice_box)

### Step 5 — Convert, and approve the cost first

Click **Convert audiobook**. Imprint asks you to approve the estimated euro
amount from Step 2 — nothing is sent until you do. Then watch the progress
bar and the log walk through extraction, chunks, narration and assembly until
the status reads `[Done] Audiobook created successfully.` A **Stop** button
is visible while the run is live. Be clear about what Stop does: it ends the
run, but the chunks already narrated were real paid requests — they are
logged as spend and kept in the cache so a later resume does not pay for them
again. If the file already exists in the output folder, Imprint refuses to
convert it again and points you at Listen instead.

[Show me](show:audiobook_start_btn)

### Step 6 — Resume an interrupted run without paying twice

If the run was stopped, the Mac slept, or your OpenAI quota ran out, the
status line tells you on your next visit: `[Interrupted] … 3 of 11 chapters
are already generated and cached — you only pay for the rest.` Select the same
book and click **Convert audiobook** again; the approval covers only the
missing chapters. If you changed Voice or Chunk size in between, Imprint asks
before starting: resume with the original settings and reuse the paid
chapters, or start fresh with the new settings at full cost — never a silent
restart. A quota stop shows `[Blocked]`; top up your OpenAI account, then
convert the same book to resume.

[Show me](show:audiobook_status_label)

### Step 7 — Listen, leave, and come back

Open the **Listen** tab — Show me takes you there. Click **Rescan** if the new
book is not in the table yet, select it and click **Listen**. **Good result:**
the opening reads cleanly, a chunk join passes without a seam, and difficult
names are pronounced right. **Weak result:** mispronounced names or audible
joins — test a shorter excerpt or another voice before converting anything
long. Pause and leave; when you come back the button reads **Resume at** your
exact position. **Start Over** deliberately resets that book's position, and
**Show in Finder** reveals the file itself. The scope menu filters the table
to the current Project, and **Save listening progress** can live on this Mac
or in your synced Google Drive folder so your place follows you between
machines.

[Show me](show:audiobook_play_btn)
