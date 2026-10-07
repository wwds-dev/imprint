# Video

> **Outcome:** choose an implemented visual route, render one bounded video,
> monitor it safely, and find the accepted output without blind retries.

![Video workspace](../img/agent-video.png)

## Prerequisites

- The nested vidforge project is present and importable.
- Topic/source facts, target format, and acceptance checklist are ready.
- Script/narration/visual/stock keys required by the chosen route are eligible.
- The output directory is writable and ffmpeg is available for assembly routes.
- Sora and its adapter are removed ahead of its 24 September 2026 API
  shutdown. Choose Gemini, Qwen or Higgsfield for direct video, or a
  scene-image model — GPT Image, Nano Banana or Qwen Image — for an assembled
  video. A Gemini or Qwen scene route needs that provider's key and
  permission as well as OpenAI's, which still writes and narrates the script.
- Google shuts the Veo 3.1 previews down on 22 October 2026 and names Gemini
  Omni as the replacement; from that day Veo leaves the menus and the
  assessment, though a job already in flight is still collected.

## Control atlas

| Area | Meaning |
|---|---|
| Topic | Explicit brief; empty can consume the next configured topics-file item |
| Format | Long-form assembled pipeline or social/direct-capable clip context |
| Visual provider/model | Only implemented image/video adapters; badge reflects current capability |
| Aspect / Clip length | Options adapt to provider/model capability |
| Render Video / Stop | Submit once; cancellation differs after provider acceptance |
| Cost/status/progress/log | Reserve and stages: script, narration, captions, visuals, clips, audio, assembly, thumbnail |
| Library | Shared vidforge history with Play, Show in Finder, and Rescan |

## Worked run

1. Enter a small topic with audience, factual boundaries, duration, and CTA.
2. Select format, then provider/model. Recheck aspect, length, recommendation,
   note, and estimate after each capability-changing selection.
3. For a first test choose the minimum practical duration and press **Render
   Video** once.
4. Watch the log to identify whether this is an assembled narrated pipeline or
   a direct asynchronous provider job.
5. If stopping, press once and read the result: either the provider cancelled
   a job that had not started (nothing charged), or Imprint only stopped
   watching a job that keeps rendering and will still bill. Closing Imprint
   does not lose an accepted job: reopening it re-polls, downloads and
   bills it exactly once on the next launch. A submission that never got a
   provider job id (the app closed between the paid request and the
   provider's reply) is marked lost instead and needs checking on the
   provider's own dashboard.
6. Open Library, play the actual file, reveal it in Finder, and verify duration,
   dimensions, audio, captions, visuals, claims, pacing, and CTA.

## How to read the output

Text providers can prepare scripts/prompts but are not video providers. A 100%
local progress bar does not replace playback QA. Provider completion does not
prove copyright, likeness, disclosure, platform compliance, or marketing value.

## Acceptance checklist

- [ ] Correct dimensions, duration, codecs, audio, captions, and safe areas.
- [ ] Factual claims and visual/voice/likeness rights are reviewed.
- [ ] No missing/duplicate scenes or expired hosted asset remains.
- [ ] Actual output path, provider job state, and cost are recorded.
- [ ] CTA maps to one measurable next action.

## Cost, cancellation, and gates

Images/video may bill by asset or duration; narration and script may add costs.
Before approval every render is assessed across the routes that can make the
requested length and shape, each priced at that length; Higgsfield, priced only
by its later quote, is listed but never recommended on a guess, and a switch is
offered only when another route wins by at least a point. The assessment
respects the same session, daily, project and per-agent caps as the guard. Stop
works for every direct provider, but it only cancels at the provider where that
is possible before rendering starts (a queued Wan or Higgsfield job). For an
accepted Veo/Gemini job, or one already rendering, Stop stops watching: the
budget reservation stays, the provider may still bill, and the next launch
saves the result and bills it once. Humans approve paid submission and public
release.

## Verification

Play the local file from Library/Finder and compare its actual duration,
dimensions, captions, sound, visuals, claims, and cost with the submitted brief.

## Common failures

**vidforge unavailable:** restore the nested project/dependency.  
**Stop appears ineffective:** identify the active provider state; do not submit
a duplicate.  
**Assembly fails:** preserve the log and verify ffmpeg/output permissions.  
**Output missing:** check Library/output folder and hosted URL expiry first.

## Done when

The actual file passes playback QA, is saved locally, its route/cost/job state
are known, and publication remains a separate approved step.

## Next action

Prepare distribution in [Social](25-social.md) and measurement in
[Funnels, attribution, and cohorts](34-funnels-attribution.md).

## Recipe: make one short ad clip

You will render one 8-second vertical teaser ad for a paperback called *Night
Bus* — a single direct-provider clip, prompt to playback, saved in the shared
Library. Copy the example inputs exactly the first time, then swap in your own
product. Each **Show me** closes this lesson, opens the control it names and
rings it; **Back to lesson** in the callout brings you back to that step.

**Time:** about 10 minutes, most of it the provider's render wait. **Cost:**
one direct video render — you see its flat estimate and approve it before
anything is sent. This example (Gemini Omni 1.1 Flash at Imprint's budget
reserve of $0.10 per 720p second, 8 seconds) reserves $0.80, with the euro
conversion shown live. No text request is involved, so there is no free local
route: every direct render is a paid provider job. Failed Veo and Wan
generations are not billed by their APIs; Higgsfield quotes its exact price
before you approve.

### Step 1 — Write the ad as the Topic

For a direct model the Topic field is the entire prompt, so write the ad in
it: what is on screen, the mood, the end-card text, and what must not appear.
Direct models refuse an empty Topic — only the assembled pipeline may take
the next line from topics.txt.

```
8-second vertical teaser for the paperback "Night Bus": a rainy city-bus
window at night, warm interior light, a paperback lying on an empty seat;
slow push-in; calm late-night mood, soft ambient sound. End-card text:
NIGHT BUS — OUT NOW. No real people's faces, no logos, no spoken words.
```

[Show me](show:video_topic_input)

### Step 2 — Choose a direct video provider

Open **Visual provider**. Gemini, Qwen and Higgsfield carry direct
text-to-video models; Gemini and Qwen also list scene-image models for
assembled videos, and OpenAI now supplies only those, since Sora is gone.
**BEST FIT** marks the provider the
recommendation engine ranks best for your current format, aspect, length,
remaining budget and enabled API permissions — hover it for the reason. It is
capability-and-cost guidance, not evidence anyone will watch the ad. Pick
**Gemini** for this run.

[Show me](show:video_visual_provider_box)

### Step 3 — Pick the model and let it set the rules

Choose **Gemini Omni 1.1 Flash**. The moment a direct model is selected,
**Format** locks itself to *Social clip*, and the note under the dropdowns
says what this model actually does — here, fast text-to-video with generated
audio, with the length expressed in the prompt. BEST FIT in this list is
scoped to the provider you just chose. Until 22 October 2026 the list also
shows the Veo 3.1 previews, each with its shutdown note; Omni is the model
Google names as their replacement, which is why this recipe uses it.

[Show me](show:video_visual_model_box)

### Step 4 — Set length and aspect

**Clip length** now offers only what Gemini Omni accepts — 3 to 10 seconds.
Choose **8s**. Check that **Aspect** reads *Vertical 9:16*; a social clip
left on Landscape is switched to vertical for you. Every change here
re-prices the run.

[Show me](show:video_length_box)

### Step 5 — Read the estimate before you spend

The line beside the buttons now reads `Budget reserve · $0.80 · ≈ €…`. The
dollar figure is Imprint's configured rate, not a provider invoice: Gemini
Omni is token-billed, so the number is a cap, not a quote. Two other labels
mean something different: *Direct clip* (Veo and Wan, priced from their 720p
per-second list rate) and *Exact provider quote before approval* (Higgsfield
prices the job itself before you approve).

[Show me](show:video_cost_label)

### Step 6 — Render once, approve the cost

Press **Render Video** once. Gemini needs its key in Imprint's private .env
(GOOGLE_API_KEY or GEMINI_API_KEY) and must be enabled in the API permissions
row — the panel tells you which is missing. Then the approval dialog shows
the flat cost; nothing is sent until you approve it. The same dialog ranks
every route that can make an 8-second vertical clip, each with its price; if
another wins by at least a point, **Apply** switches the selectors to it and
asks again — it never submits on its own. The request is posted exactly
once: Imprint switches off the Gemini client's own hidden retry, so a slow
answer cannot become a second paid render.

**Good result:** the status line reports the submission, then progress, then
`Done — <file>.mp4`, and Library gains a Ready row. **Weak result:** an
`[Error]` line in the log — read it before touching anything, because a line
starting `[Resume]` means the provider may still finish and bill; the next
launch checks. Do not submit a duplicate.

[Show me](show:video_render_btn)

### Step 7 — Stop without losing the money

One Stop contract covers every direct provider. Press **Stop** once: a Wan
job still queued may be cancelled at the provider — the status then says
nothing was charged; a Gemini render already accepted cannot be cancelled, so
Stop stops *watching* — the job stays tracked, and the next launch re-polls,
downloads and bills the paid result exactly once. Stopping, or even closing
Imprint, never loses a paid render; only a submission that never got a job id
is marked lost, and that one you check on the provider's own dashboard.

[Show me](show:video_stop_btn)

### Step 8 — Find it, play it, judge it

Open the **Library** tab. The clip is listed with its length and a Ready
status; the scope dropdown narrows the list to the current Project. Select
the row, **Play** the actual file and watch it to the end — a full progress
bar is not QA. **Show in Finder** reveals the file; **Rescan** re-reads the
shared vidforge history. Only after you have seen the end card, heard the
audio and checked the claims is the ad ready for the separate, approved step
of publishing it.

[Show me](show:video_library_table)
