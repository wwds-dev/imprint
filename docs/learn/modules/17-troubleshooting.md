# Troubleshooting

> **Outcome:** match the message on screen to its cause and fix it in one
> step, without a blind retry and without paying twice.

## Prerequisites

- The exact text of the message, copied or written down as it appears.
- Which agent you were using and which provider and model were selected.

Search this lesson for a word from the message: each entry below starts with
the text Imprint Studio shows.

## Keys and providers

**"…_API_KEY is not set."** (for example `ANTHROPIC_API_KEY is not set.`)
The provider has no key. Add one in **Settings → API keys**, press **Test**,
then **Save All** ([Add a key](13-access-privacy.md#add-a-key)), or switch to a
local model.

**Test says "unreachable — …"** The provider refused the key, or could not be
reached. Copy the key again from the provider's account page as one line, with
no spaces, and test before saving. For Qwen, a refusal from a workspace host
can mean the key belongs to a different workspace or region.

**"API access for '…' is not enabled. Enable it in the API Permissions panel."**
The provider's permission box is unticked. Open the **Assistant** workspace and
tick it under **Cloud text models** (Higgsfield and ElevenLabs: **Paid media**).
The boxes start unticked at every launch and apply to every agent.

**"Agent '…' does not permit provider '…'."** That agent cannot use that
provider (Press and Nova, for example, offer no local provider). Pick another
provider in the agent's own menu.

## Local models

**"Ollama is not running"** (in the model menu or on hover) The Ollama app or
server is not started. Open Ollama, wait until it is running, then press
**Refresh Models** beside the Model menu.

**A local model shows "on disk, server off"** (or "LM Studio server off")
LM Studio's server is off. Start it in LM Studio, or press **Start server** in
**Settings → Local models**.

**"too big now"** (in the model menu) or **"… needs ~… GB; … GB free."** The
model needs more free memory than the Mac has at the moment. Close other apps, or pick a smaller model. A model that can never
fit this Mac is refused.

## Spend and budgets

**"Not sent: this request can cost up to … and …"** A budget check stopped the
request before anything was sent, so nothing was spent. The rest of the
sentence names the cap (the agent's daily cap, the project's, the session's or
today's) and what is left. Pick a cheaper or local model, or raise the cap: the
session and daily caps are the limit fields under **Spend** in the right rail
(type a number and press Enter), an agent's cap in **Settings → Agents**. See
[Costs, estimates, and limits](14-costs-limits.md).

**"[Cut off] … stopped at the length limit"** The reply reached the most one
request may write (8,192 tokens). In Quill, press **Continue** to write more;
in the Assistant, send "continue"; elsewhere, ask for less or split the task.
You pay for what was written.

## Audiobooks (Booth)

**"ffmpeg was not found on your PATH."** Booth needs ffmpeg to join the audio.
Install it (`brew install ffmpeg` in Terminal), then quit and reopen Imprint.
"ffprobe was not found" has the same fix: ffprobe ships with ffmpeg.

**A MOBI or AZW3 book will not convert.** These are converted to EPUB first
with Calibre's `ebook-convert`. Install Calibre, or convert the book to EPUB
yourself.

**`[Blocked]` with a quota or billing message** The narrator's provider has no
credit left. Top it up, then click **Convert audiobook** again: finished chunks
are kept and not paid for twice. The message names OpenAI's billing page
whichever narrator ran; top up the provider you chose.

## Quill

**"[Too long] Revise works on up to …" and nothing was sent** A revise task's
text is longer than it can handle in one run (20,000 characters, 6,000 with a
local model). Select one chapter or passage in the Draft and press **Write**
again.

**The same chapter appears twice in the Draft** A prose task adds after the
existing Draft; it never replaces it. Delete the copy you do not want, or
select it and use **Revise / Improve**. See
[Quill: What Write changes](20-draft.md#what-write-changes).

## Other agents

**A video seems stuck, or Stop does not stop it** See
[Video: Common failures](24-video.md#common-failures).  
**Herald cannot post** See [Social: Common failures](25-social.md#common-failures).  
**Booth finds no books** See
[Audiobooks: Common failures](22-audiobooks.md#common-failures).

## The app itself

**Imprint does not open, or opens an older version** See
[Files, launcher, and recovery](15-files-recovery.md#launcher-recovery-walkthrough):
the live launcher writes its reason to `/tmp/imprint_launch.log`.

**A status you cannot find here** Keep its exact wording, note the time, and
open **Run Log** in the right rail: every request's lifecycle is recorded
there. For a bug report, give that wording, the time, the agent, provider and
model, and what you clicked last; never a key or a screenshot of Settings.

## Verification

- [ ] The message is gone after the fix, or it has changed to a different one
      that points at the next cause.
- [ ] Nothing was sent twice: **Cost History** shows one entry per paid request.

## Common failures

**Retrying unchanged:** the same request with the same selection meets the same
check. Change the one thing the message names first.  
**Fixing the wrong build:** a frozen app reads its keys and data from
`~/Library/Application Support/Imprint/`, the live launcher from the project
folder ([Files, launcher, and recovery](15-files-recovery.md)).

## Next action

Return to the lesson you were following, or start with
[First verified result](01-first-result.md). Unknown terms are in the
[Glossary](18-glossary.md).
