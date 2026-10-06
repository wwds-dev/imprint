# Music

> **Outcome:** make one finished song — lyrics, Suno prompt and audio kept
> together in Imprint — and, when it is worth releasing, a verified release
> checklist. Earnings figures are scenarios with assumptions, never
> “realistic” predictions.

![Music workspace](../img/agent-music.png)

## Prerequisites

- Rights/credits for the recording, composition, samples, artwork, likenesses,
  and collaborators.
- One audience hypothesis and release objective.
- One primary post-release action or cohort metric.

## Control atlas

| Area/tab | Purpose | Human check |
|---|---|---|
| Brief/provider/model | Generate a structured release plan | Best Fit is task guidance, not audience evidence |
| Artist Profile | Positioning, audience, identity, catalogue context | Facts and claims match the artist |
| Release Setup | Metadata, assets, dates, credits, identifiers | Distributor/platform requirements are current |
| Distribution | Delivery and rights checklist | No generated rights assertion is accepted |
| Spotify Strategy | Discovery/content proposals | Follows current platform rules and maps to a measured action |
| Income Roadmap | Scenario variables and revenue-route ideas | Label assumptions; never treat streams × static rate as a forecast |
| Songs & Albums | Lyrics and Suno style prompts, saved with the imported audio | Lyrics are original and your Suno plan covers how you use the audio |
| Save Full Plan / Clear / Stop | Export the plan as text, reset visible work, or request cancellation | Every generated plan is already stored as a record; Save Full Plan is the plain-text copy |
| Record Outcome… | Attach what a shipped release actually did (streams, revenue, notes) to the stored plan you pick | Numbers are self-reported; the next plan for that artist plans against them |

## Recipe: make one song, start to finish

You will make one finished, listenable song called *Night Bus* and keep its
lyrics, prompt and audio together in Imprint. Copy the example inputs exactly
the first time, then swap in your own. Each **▶ Show me** closes this lesson,
opens the control it names and rings it; **Back to lesson** in the callout
brings you back to that step.

**Time:** about 20 minutes. **Cost:** one text request in Imprint — you see
its estimate and approve it before anything is sent (free with a local
Ollama model) — plus the song credits in your own Suno account, which Imprint
neither sees nor tracks.

### Step 1 — Set the artist basics

Fill in the artist fields at the top of Music. They are sent with every song
request, so the lyrics and style fit the same artist.

```
Artist / project name:  Night Owl Radio
Genre:                  Electronic
Release type:           Single
Target audience:        late-night lo-fi listeners, 20–35, studying or commuting
```

[Show me](show:music_artist_input)

### Step 2 — Choose who writes the lyrics

Pick a provider and model. **BEST FIT** marks the recommended choice for this
task; any model that writes well is fine. Choose Ollama if you want the
request to stay on your Mac and cost nothing.

[Show me](show:music_provider_box)

### Step 3 — Name the song

Open the **Songs & Albums** tab — Show me opens it for you. Enter the title
`Night Bus` and leave **Tracks** at 1.

[Show me](show:music_suno_panel.title)

### Step 4 — Write the creative brief

The brief is what makes the song yours. Say what it should *feel* like, what
it is about, and what it must not do.

```
Mood: warm, a little lonely, hopeful at the end. Slow lo-fi beat, ~80 BPM.
Instruments: dusty Rhodes piano, soft vinyl crackle, brushed drums, sub bass.
Vocals: soft female vocal, mostly spoken-sung, English.
Story: the last bus home after a long shift; city lights through a rainy
window; small moment of peace. Chorus should be short and easy to hum.
Avoid: brand names, real people, explicit lyrics.
```

[Show me](show:music_suno_panel.brief)

### Step 5 — Draft the lyrics and the Suno prompt

Click **Draft songs & Suno prompts**. Imprint shows the estimate; approve it.
After a few seconds the big box fills with a title, a short **style prompt**
and full lyrics labelled `[Verse]`, `[Chorus]`, `[Bridge]`.

**Good result:** the style prompt is one or two lines of sound words (genre,
tempo, instruments, voice); the chorus repeats; nothing in it claims audio
already exists. **Weak result:** a vague style prompt, or no chorus — tighten
the brief and draft again.

[Show me](show:music_suno_panel.generate)

### Step 6 — Edit, then save

Read the lyrics aloud once and fix any line you would not sing. The box is
yours to edit. Click **Save**: the song now appears in the dropdown at the top
of the tab and survives a restart.

[Show me](show:music_suno_panel.save_btn)

### Step 7 — Create the audio in Suno

1. Select only the style prompt and click **Copy selected / all**.
2. Click **Open Suno**. In Suno's create page switch to custom mode and paste
   it into the style box. (Suno renames its labels from time to time; look for
   the boxes for *lyrics* and *style*.)
3. Back in Imprint, select the lyrics, copy, and paste them into Suno's lyrics
   box. Create.
4. Listen to both versions Suno makes and download the better one.

Before you release anything, check that your Suno plan allows commercial use
of what it made.

[Show me](show:music_suno_panel.open_suno_btn)

### Step 8 — Import and listen

Click **Import audio** and choose the file you downloaded. Imprint copies it
next to the lyrics and prompt — your original stays where it was.
Double-click the track to play it. You have a finished song.

[Show me](show:music_suno_panel.import_btn)

### Step 9 — Optional: plan the release

When a song is worth releasing, describe it under **Describe your music** and
click **Generate Plan** for a release checklist: metadata, distribution and
promotion. Treat every number in it as a scenario to check, not a forecast.
When it finishes the status line reads `Plan complete — tabs populated and
stored.`: the plan is kept as a record for this artist, whether or not you
also click **Save Full Plan** for a text copy.

[Show me](show:music_analyse_btn)

### Step 10 — Optional: record what the release actually did

Weeks after release, with the artist name still in **Artist / project name**,
click **Record Outcome…**. Pick the plan that actually shipped from the list
(dated; one marked *outcome recorded* already has numbers, which are
prefilled), then type what your distributor dashboard shows:

```
Streams:        4200
Revenue (USD):  14.70
Notes:          playlist pitch landed one indie list; TikTok clip did nothing
```

The numbers are self-reported — Imprint does not read any platform. The next
time you click **Generate Plan** for the same artist, the prompt carries a
short *past releases and measured outcomes* block, so the new plan starts
from what really happened instead of from zero. Leaving all three fields
blank records nothing.

[Show me](show:music_outcome_btn)

## How to read the output

Release tasks are a draft operating checklist. A stream count is a platform
event, not collected revenue. A per-stream range varies by service, geography,
subscription, rights split, and period. Model-generated numbers are
`MODEL-GENERATED` until replaced with sourced scenario inputs; neither is a
forecast of future listening.

## Acceptance checklist

- [ ] Metadata, credits, ownership, and dates are independently verified.
- [ ] Every promotional item points to one measurable next action.
- [ ] Scenario numbers show source/date/range/currency and all material costs.
- [ ] No guaranteed, passive, or “realistic monthly income” claim remains.
- [ ] The saved plan names owners, deadlines, and human approval gates.

## Cost, cancellation, and gates

Generation cost is separate from production, distribution, promotion, splits,
and correction time. Humans approve rights, credits, release submission,
payments, public claims, and final creative.

## Verification

Open the saved plan independently and confirm that every external price,
platform step, payout input, and rights claim is either source-dated or marked
for current official verification.

## Common failures

**Suno won't take the lyrics:** paste them in smaller parts or shorten
the bridge; very long lyrics are cut or refused.  
**The plan predicts revenue:** replace the prediction with low/base/high
hypothetical scenarios and identify which unknown needs observation.  
**Many posts, no learning:** choose one trackable destination and denominator.  
**“Spotify-ready” is asserted:** verify current distributor/platform rules.

## Done when

The release plan is saved, fact/rights checked, every task has an owner, and the
post-release scoreboard can distinguish reach, action, receipt, and cost.

## Next action

Design the measurement in [Funnels, attribution, and cohorts](34-funnels-attribution.md).
