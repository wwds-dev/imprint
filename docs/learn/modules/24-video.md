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
  shutdown. Choose Gemini, Qwen or Higgsfield for direct video, or GPT Image
  for an assembled video.

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
5. If stopping, press once and read the result. Keep monitoring accepted jobs
   that cannot be cancelled so the paid file is not lost. Closing Imprint
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
Veo/Gemini, Wan/Qwen, and other direct jobs may have no safe cancellation
after acceptance. Higgsfield cancellation can depend on queued/processing state.
Humans approve paid submission and public release.

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
anything is sent. This example (Veo 3.1 Fast at Imprint's listed $0.10 per
720p second, 8 seconds) reserves $0.80, with the euro conversion shown live.
No text request is involved, so there is no free local route: every direct
render is a paid provider job. Failed Veo and Wan generations are not billed
by their APIs; Higgsfield quotes its exact price before you approve.

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
text-to-video models; OpenAI now supplies only scene images for assembled
videos, since Sora is gone. **BEST FIT** marks the provider the
recommendation engine ranks best for your current format, aspect, length,
remaining budget and enabled API permissions — hover it for the reason. It is
capability-and-cost guidance, not evidence anyone will watch the ad. Pick
**Gemini** for this run.

[Show me](show:video_visual_provider_box)

### Step 3 — Pick the model and let it set the rules

Choose **Veo 3.1 Fast**. The moment a direct model is selected, **Format**
locks itself to *Social clip*, and the note under the dropdowns says what
this model actually does — here, 720p with generated audio. BEST FIT in this
list is scoped to the provider you just chose.

[Show me](show:video_visual_model_box)

### Step 4 — Set length and aspect

**Clip length** now offers only what Veo 3.1 Fast accepts — 4s, 6s or 8s.
Choose **8s**. Check that **Aspect** reads *Vertical 9:16*; a social clip
left on Landscape is switched to vertical for you. Every change here
re-prices the run.

[Show me](show:video_length_box)

### Step 5 — Read the estimate before you spend

The line beside the buttons now reads `Direct clip · $0.80 · ≈ €…`. The
dollar figure is Imprint's configured 720p list rate, not a provider invoice.
Two labels mean something different: *Budget reserve* (Gemini Omni is
token-billed, so the number is a cap, not a quote) and *Exact provider quote
before approval* (Higgsfield prices the job itself before you approve).

[Show me](show:video_cost_label)

### Step 6 — Render once, approve the cost

Press **Render Video** once. Gemini needs its key in Imprint's private .env
(GOOGLE_API_KEY or GEMINI_API_KEY) and must be enabled in the API permissions
row — the panel tells you which is missing. Then the approval dialog shows
the flat cost; nothing is sent until you approve it.

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
