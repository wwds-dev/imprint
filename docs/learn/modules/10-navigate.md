# Navigate Imprint Studio

> **Outcome:** move to the correct workspace and agent, identify the current
> state, and know where to look before pressing a paid action.

## Prerequisites

- Imprint is open. No provider key is required to learn the shell.
- If the window looks clipped, maximise it once and confirm you are opening the
  current live launcher or packaged build.

## The interface map

| Region | Purpose | Do not confuse it with |
|---|---|---|
| Icon rail (left edge) | One icon per workspace: Author, Audio + Music, Video + Ads, Social, Web, Brand Design, Brand Content, Assistant. Hover an icon to read what the workspace is for. At the bottom: **?** (this agent's **Docs**, the **Learning Centre**, **Keyboard shortcuts**) and **Settings**. The app mark at the top shows the version on hover | A model family or autonomous business process |
| Agent switch (top bar, left) | Selects related agents inside a workspace, such as Quill/Press under Author or Booth/Label under Audio + Music. A workspace with one agent shows its name instead | A project; switching tools does not create one |
| Project selector and **Project actions** (top bar) | Choose a saved context, or create one, open its overview or save its setup | A file browser |
| History (clock button, ⌘Y) | Opens a drawer to search, filter, open, rename and remove saved chats, or start a **New Chat** | An undo history |
| Spend chip (top bar, right) | Today's spend against its limit. Click it for Session and Today limits, Requests, **Cost History** and **Run Log** | Proof that a provider charged that amount: an unpriced request reads "unknown", never €0.00 |
| Status chip (top bar, right) | The worst current state: machine stressed, key check failed, machine busy, working or ready, plus a count of new model updates. Click it for **System**, **Chat routing**, **API keys** and **Model updates** | Proof that an external provider or platform accepted a job |
| Centre canvas | The current agent's brief, actions, status, and output | A universal form; each agent has different contracts |

## Walkthrough

1. Click each workspace icon in the rail and note which ones contain more than
   one tool. (⌘1 to ⌘8 do the same.)
2. Return to **Author** and switch between **Quill** and **Press** with the
   switch at the left of the top bar. The page title and controls change; the
   selected project does not.
3. Click the status chip and open **System**. Treat **Ready** as local
   readiness, not output quality.
4. Open **Chat routing**. A recommendation is guidance for the current task and
   eligible configuration; inspect the visible provider/model badges where the
   dedicated agent exposes them.
5. Open **API keys** in the status popover. This card shows readiness, not secrets; keys are pasted in **Settings → API keys** ([Add a key](13-access-privacy.md#add-a-key)).
   Below it, **Model updates** lists models your providers released since
   Imprint last looked, and under **Video and image** any removed video or
   image models and known shutdown dates; its title shows the counts
   (*Model updates · 2 new · 1 warning*), and the chip shows the count too.
   See [Best Fit](12-best-fit.md#new-models) before switching to one.
6. Click the spend chip. Inspect the session and daily limits, **Cost History**
   and **Run Log** before a long job.
7. Open the **?** menu at the bottom of the rail. **Docs** opens an agent's
   technical sheet; **Learning Centre** (also **F1**) opens the operating
   lessons and cross-agent workflows; **Keyboard shortcuts** lists the keys.
8. Optional: open **Settings → General → Appearance**. **Look** switches between
   Light (the default) and Dark, and **Accent** picks Green, Rose or Teal. It
   applies at once and is saved. Only the accent, the greys and the colour of
   text you type change: a "ready" badge takes the theme's accent, while the
   danger colour still means stop and the warning colour still means paid.

## How to read the result

**Ready** means the local preconditions Imprint can inspect passed. **Running**
means a local worker or provider operation is active. **Blocked** should state a
missing requirement. A completed local step does not necessarily mean an
asynchronous provider upload, platform post, sale, or payment completed.

## Verification

- [ ] I can name the active workspace, agent and project.
- [ ] I know where route readiness, cost, and the exact run record appear.
- [ ] I can distinguish app state from external-provider or business outcome.

## Common failures

**The expected tool is absent:** confirm the workspace; a single-tool workspace
shows the agent's name instead of a switch.  
**A status is unclear:** preserve its exact wording and search it here.  
**Controls overlap:** confirm the current app instance, window size, and text
scale before treating it as a data/provider problem.

## Next action

Learn [Projects, saving, and exports](11-projects.md), then open the relevant
Agent Academy lesson.
