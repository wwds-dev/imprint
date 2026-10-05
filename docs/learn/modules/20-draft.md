# Draft

> **Outcome:** produce an approved section that remains consistent with a saved
> project profile and can be recovered or exported.

![Draft workspace](../img/workspace-draft.png)

## Prerequisites

- One project for this book or long-form work.
- A target reader and concrete outcome for the next section.
- An eligible provider/model and comfortable limit.

## Control atlas

| Area | Controls | Operating meaning |
|---|---|---|
| Project bar | Title, Author, Type, Genre, Tone, Point of View | Stable identity and creative constraints; Type changes available tasks |
| Book Profile | Hook, Target reader, Comp titles, Publishing path, Save Profile | Reusable authoritative context for Write, Publish, and Market |
| Compose | Task, Direction, Provider, Model, Write, Continue, Stop | One bounded generation; Continue extends current draft context |
| Working tabs | Draft, Outline, Characters, World Notes, Chapters | Editable manuscript/context plus a derived heading navigator |
| Document actions | Save Draft, Author name, export format, Export Book | Persist current text and produce EPUB/DOCX/PDF from recognised chapters |
| Mode switch | Write, Publish & Market; Publish/Market sub-tabs | Draft prose versus packaging and launch-copy tasks |

## Worked input and run

1. Fill Title, Author, Type and the Book Profile. Keep comp titles factual and
   use them for reader expectation, not imitation.
2. Approve an outline before paying for full prose.
3. Select a Task and write a Direction with scene/argument purpose, required
   facts, length, continuity facts, and an acceptance checklist.
4. Inspect BEST FIT, then press **Write** once. Use **Continue** only when the
   next text truly extends the existing Draft.
5. Review structure before sentence polish. Update Outline, Characters, and
   World Notes with stable facts—not speculative alternatives.
6. Save Draft. Refresh Chapters after adding headings and verify navigation.
7. Enter the export author, choose format, and export only an approved version.

Example Direction:

```text
Draft a 700-word scene in which Mara must refuse the promotion she pursued.
The refusal must follow from the contract fact in World Notes. End with a new
decision, keep third-person limited, and do not introduce a new character.
```

## How to read the output

Draft is editable source material, not a final manuscript. Outline adherence,
causal continuity, factual accuracy, voice consistency, and reader promise must
be reviewed separately. Word/scene counters indicate scope, not quality.

## Acceptance checklist

- [ ] The section performs the requested narrative/argument job.
- [ ] Stable facts match the profile and notes.
- [ ] Unsupported facts, quotations, and claims are removed or sourced.
- [ ] No accidental imitation of a living author or comp title remains.
- [ ] The saved project restores and exported headings render correctly.

## Cost, cancellation, and gates

Text streaming can stop locally, but already accepted provider work may still
bill. Human approval is required before factual publication, rights claims,
store submission, or replacing the authoritative manuscript.

## Verification

Run the acceptance checklist against the saved—not merely visible—draft, switch
projects, return, and confirm that the authoritative version restores.

## Common failures

**Generic prose:** add authoritative context and a scene/argument decision.  
**Continuity drift:** shorten factual notes; do not rely on the entire draft as
perfect memory.  
**Empty Chapters:** use consistent Markdown-style headings and refresh.  
**Export looks wrong:** verify chapter headings and author metadata first.

## Done when

The section passes the checklist, is saved in the correct project, appears in
the intended structure, and has one explicit next editorial decision.

## Next action

Continue section by section or move an approved manuscript to [Publish](21-publish.md).

## Recipe: draft one chapter that keeps its facts straight

You will draft the opening chapter of a non-fiction book called *Night Shift
City* — reportage about the people who run a city overnight — with Quill's
continuity notes and source rules doing the remembering. Copy the example
inputs exactly the first time, then swap in your own. Each **Show me** closes
this lesson, opens the control it names and rings it; **Back to lesson** in
the callout brings you back to that step.

**Time:** about 15 minutes. **Cost:** one text request in Imprint — you see
its estimate and approve it before anything is sent (free with a local
Ollama model). The notes, sources and save in the other steps cost nothing.

### Step 1 — Set the project identity

Fill the project bar at the top of the Write page. These six fields travel
with every request, and **Type** does real work: switching it to Non-Fiction
swaps the Task list to chapter-and-argument tasks and adds a **Sources** tab
to the manuscript tabs.

```
Title:          Night Shift City
Author:         M. Averill
Type:           Non-Fiction
Genre:          Other
Tone:           Neutral
Point of view:  First Person
```

[Show me](show:author_content_type_box)

### Step 2 — Save the Book Profile

Open **Book Profile**, fill it, and click **Save Profile**. The profile is
injected into every Write, Publish and Market request, so you state the
book's promise once instead of re-explaining it each time.

```
Hook:            The city you wake up in is rebuilt every night by people you never see.
Target reader:   Curious general readers who like workplace reportage
Comp titles:     For readers of Nickel and Dimed and The Works
Publishing path: Undecided
```

Comp titles set reader expectation; they are not something to imitate.

[Show me](show:author_profile_save_btn)

### Step 3 — Write down what must stay true

Open the **Characters** tab and list the recurring people, then put
established facts and terms in **World Notes**. Everything in these two tabs
is sent with every Write and Continue request as continuity the model must
not contradict — Quill also sends the tail of the current draft, so a fresh
Write knows what came before. Keep the notes short, stable and factual.

```
Rosa Imbert — overnight baker at Beaumont & Co, 23 years on the job.
  Interviewed 2026-09-12. Short sentences; hates the word "gritty".
Darius Cole — transit control supervisor, night desk. Interviewed 2026-09-18.
```

And in World Notes:

```
"The gap" = 01:10–04:40, when the metro runs no passenger service.
Maintenance trains own the tunnels during the gap.
Ovens at Beaumont & Co fire at 02:00; the first delivery van leaves 05:15.
```

[Show me](show:author_characters_box)

### Step 4 — Declare your sources

Open the **Sources** tab — it exists only while Type is Non-Fiction — and
list one source per line. The rule it switches on is strict: once anything is
listed here, drafting may only assert facts these sources support, must cite
the supporting source inline, and must mark every other factual claim
`[UNSOURCED]`. An empty tab imposes nothing — no sources, no rule.

```
Interview notes: R. Imbert, 2026-09-12 (audio + transcript, my files)
Interview notes: D. Cole, 2026-09-18 (transcript, my files)
City Transit Authority, "Night Maintenance Window Review", 2025 report
```

Interview notes are self-reported accounts: the chapter can say what Rosa
told you, not present it as independently verified.

[Show me](show:author_sources_box)

### Step 5 — Pick the task and give one direction

In Compose, set **Task** to `Write Chapter` and put one concrete instruction
in **Direction**. One decision per request beats a paragraph of vibes.

```
Draft an 800-word opening chapter titled "The Gap". Follow one night from
01:10 to 05:15 through Rosa and Darius. Assert only what the Sources
support and cite them in parentheses; mark anything else [UNSOURCED].
First person, present tense. Quote only lines that appear in the
interview notes.
```

[Show me](show:author_task_box)

### Step 6 — Choose who writes

Pick a provider and model. **BEST FIT** marks the recommended choice for this
task; any capable model is fine. Choose Ollama if the chapter should stay on
your Mac and the request should cost nothing.

[Show me](show:author_provider_box)

### Step 7 — Write, and judge the result

Click **Write** once. Imprint shows the request's estimate; approve it, and
the chapter streams into the Draft tab. **Stop** cancels locally, but work
the provider has already accepted may still bill.

**Good result:** the chapter follows the direction, sourced facts carry their
citation in parentheses, and anything the sources do not cover wears
`[UNSOURCED]`. **Weak result:** generic night-city atmosphere with no sourced
facts — tighten World Notes and the Direction, then write again. Use
**Continue** only when the next text truly extends what is already in Draft.

[Show me](show:author_write_btn)

### Step 8 — Clear the [UNSOURCED] marks, then save

The status line under the workbench counts the `[UNSOURCED]` claims for you
and says so in the done message. Deal with each one: verify it against a real
source (and add that source to the tab) or cut it — deleting the mark without
checking defeats the whole mechanism. Then click **Save Draft**; with a
project active, the saved file is linked to that project's outputs.

[Show me](show:author_save_btn)
