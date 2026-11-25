# Spec: Manuscript redesign (new look, direction B)

Needs: design, architect, build, review, verify, docs

Status: **Define approved by the owner 2026-11-25 ("do as recommended"): D1 to D12 are decided
as recommended, alternatives not taken.** Design for slice 1 was written 2026-11-25 at the owner's
request, before testing ("no testing"; section "Design (slice 1)"), and approved the same day,
owner: "Approve as recommended" (O1 to O3 as recommended). Architect for slice 1 was written 2026-11-25 (section "Architecture (slice 1)", ADR 0006) and approved the same day, owner: "Approve as recommended" (AO1 to AO3 as recommended). No Build has started. Priority: P3 (TODO.md: testing comes first; no redesign row
starts until the owner asks, after testing). Type: user-visible redesign of the whole window,
new UI capability (stepper, next-step card, word goal, cover, focus mode, light theme), no new
paid path, no change to what agents do. Owner session: `claude/spec-manuscript-redesign-9236ea`
(this spec's slug is `manuscript-redesign`). Phases skipped: Case (tier `public`). Secure is
expected to be light (no network, secrets or untrusted input; bundled fonts would touch
packaging, see D11). Comply only if fonts or icons are bundled (licence inventory).

Source of the look: the owner's private design canvas "Imprint Studio New Look", direction B
"Manuscript", pages "Three directions" (`B-Press`, `B-Quill`) and "B · all agents" (`B-Booth`,
`B-Label`, `B-Reel`, `B-Herald`, `B-Sitebuilder`, `B-Vector`, `B-Nova`, `B-Kernel`). Directions A
and C were not chosen and are not specified here. The mockups' dropdown options, palette names,
platform list, Kernel suggestion chips and the manuscript text are placeholders, not requirements.

## Problem
On 2026-11-25 the owner asked for "a completely new look ... modern, intuitive and well designed,
no clutter, no overload, focus on functionality, on what is relevant. add some gimmicks", compared
three directions and chose this one: "ok B it is". The complaint behind the request was clutter:
three tab rows, two rails, empty panels. Measured in today's code:

- **Three tab rows before any content, four in Quill.** Header workspace tabs (`main.py:2545`),
  the workspace tool row that switches Quill / Press and Booth / Label (`main.py:2771`), then each
  agent's own `QTabWidget` (for example `agents/author/panel.py:390`). Quill adds a fourth level:
  a Write / Publish & Market mode switch with Publish and Market sub-tabs
  (`agents/author/panel.py:508`, `:519`, `:543`, `:552`).
- **Two rails around every screen.** Left 216 px, right 244 px (`ui/forms.py:512-513`), built in
  `build_left_panel` (`main.py:2619`) and `build_right_panel` (`main.py:3502`). The left holds
  projects, saved chats (`main.py:2704`), the project budget meter (`main.py:2682`) and the window
  links (Cost History, Run Log, Learning Centre, `main.py:2732`); the right holds Spend and Status
  (System, Chat routing, API keys, Model updates, `main.py:3655`). On a 1400 px window that is 460
  px of chrome around one form.
- **The header carries everything else on one row** (`main.py:2499`): wordmark, version badge,
  workspace tabs with a More overflow (`ui/header_fit.py`), project pill, status pill, theme dots
  (`ui/widgets.py:818`), Docs, Tooltips and Settings buttons, plus a description strip under it
  (`main.py:2479`).
- **Empty panels look like forms.** Press's Overview shows metric fields, Refresh Data and Ingest
  KDP CSV (`agents/manuscript/panel.py:134-138`) before any data exists; its five tabs
  (Overview, Quote Finder, Quote Graphics, Shorts, Calendar, `:285-297`) are all visible at once.
- **The composer is a settings form.** Tool, provider and model rows plus nine provider permission
  chips (`main.py:2836-2902`) and Auto-Apply (`main.py:2978`) sit above the message box.

**Who it is for:** the one author/creator who uses Imprint (app-context: one user, ten agents),
working on one book or project at a time, mostly in Quill and Press, sometimes in the others. Later,
if the app is sold (`commercial` is a recorded intent, not the tier), a new user who must find the
next thing to do without reading the README.

## What B is (the target, from the mockups)
- **Light look**: off-white background, white cards, one accent (the mockups offer the three
  accents the themes have today: green, rose, teal).
- **Icon rail**, 72 px, left: the app mark, then one icon per workspace (eight), Settings at the
  bottom. Replaces the header workspace tabs, the More overflow and the description strip.
- **Top bar**: a project (book) selector, a **stepper** of the open agent's stages, a **spend
  chip** ("€0.00 of €5 today") and a **status chip** ("Ready"). A two-agent workspace gets a small
  agent switch at the left of the bar (Booth / Label). Some agents add one side button (Herald
  Accounts, Vector Orders, Nova "Voice and character") or one action (Herald "New campaign",
  Kernel "New chat").
- **One primary action per screen**, every other button quiet.
- **Empty panels reduced to one action** ("Drop a KDP CSV here" with Choose CSV).
- **Provider and model collapsed into one chip**; **one ask bar** per screen.
- No left or right rail beyond the icon rail.

## What changes for the user, screen by screen
"Today" cites the code; "B" is the mockup; **new** marks scope that does not exist in the app.

| Agent | Today | B |
|---|---|---|
| **Quill** (Author) | Six tabs: Draft, Outline, Characters, World Notes, Chapters, Sources (`agents/author/panel.py:390-856`); Write / Publish & Market switch; Write, Continue, Stop, Save Draft, Export Book, Clear (`:357-496`); word count label (`:456`) | Stepper Write → Prepare → Export → Promote → Track, Write current (**new**). Chapter list left, the page centre in a serif face, an "Ask Quill" card right with three suggested asks, a free ask field and the model chip. **Word-goal ring** in the top bar ("x of 250 words today", **new**). **Focus** button hides the icon rail, chapters and ask card (**new**). Outline, Characters, World Notes, Sources: not shown in the mockup (D1). |
| **Press** (Author) | Five tabs; Overview has metrics, Ask, a publishing todo list (`agents/manuscript/panel.py:45`, `:251`, `:270`) | Same stepper, Prepare current. A **cover** whose spine fills as todos are done and a "READY TO SHIP" stamp when all are done (**new**). A **next-step card**: the first open todo as a heading, Mark done, the rest listed below (**new**, replaces the todo list). "Royalties by marketplace" as the KDP CSV drop target. A Promote card with four tiles (Quote Finder, Quote Graphics, Shorts, Calendar) replacing those tabs. One ask bar ("Ask Press: …") with the model chip. |
| **Booth** | Tabs Convert, Listen (`agents/audiobook/panel.py:318-323`) | Booth / Label switch; book selector; stepper Convert → Listen. Both stages side by side as numbered cards on one screen; Convert is the primary action, with "A paid voice shows its price before anything is spent." Listen shows waveform bars that **animate while playing** (**new**, D5). |
| **Label** | Six tabs: Artist Profile, Release Setup, Distribution, Spotify Strategy, Income Roadmap, Songs & Albums (`agents/music/panel.py:149-159`) | Booth / Label switch; the six tabs as a stepper (D1: they are not a sequence the app enforces). Artist profile form with "Plan the release" primary; an Outcome card (Streams, Revenue, "A blank means unknown, never zero.") and a Plan card with an empty state. |
| **Reel** | Tabs Render, Library (`agents/video/panel.py:220-269`) | Stepper Render → Library. Topic, Aspect, Format, Clip length, Visual model; Render primary with "Clips are paid per unit. The price is shown first." A preview frame that **reshapes with the chosen aspect** (**new**, D5). Library empty state with Open output folder. |
| **Herald** | Tabs Draft, Schedule, Analytics, Accounts (`agents/social/panel.py:225-313`) | Stepper Draft → Schedule → Analytics; Accounts becomes a side button (D1); "New campaign" action. Brief form, platform picker, Drafts as one card per platform (Copy text, Save to schedule, Make a clip, Post now), a "This week" strip. "Nothing is posted without your click." |
| **Sitebuilder** | Tabs HTML, CSS, JS (`agents/webdesign/panel.py:152-158`) | Stepper Brief → Code → Export (the tabs are not these stages; D1). Page type, Framework, Brief, Style, a colour palette that **recolours a wireframe preview** (**new**, D5); Build page primary; HTML / CSS / JS as views of the preview; Copy all, Save .html, Export project. |
| **Vector** | Tabs Logo Preview, Delivery Message, Gig Description, Orders (`agents/fiverr/panel.py:253-309`) | Stepper Brief → Logo → Delivery message → Gig description; Orders becomes a side button (D1). Brief form, concept count, create action with "Images are paid per unit. The price is shown first." |
| **Nova** | Tabs Draft, Calendar, Voice, Media (`agents/creator/panel.py:275-379`) | Stepper Draft → Calendar → Media; Voice becomes the side button "Voice and character" (D1); a "Cinematic promo" action. Brief, campaign, channel, kind, profile; Draft primary; Teaser card ("Rendering is paid per clip. The price is shown first."); "This week" strip. |
| **Kernel** | The shared chat screen (`normal_panel`; tool, provider, model rows and permission chips, `main.py:2836-2978`; message box `main.py:2934`) | No stepper. "New chat" in the top bar. A chat list with search on the left of the screen, then "What do you need?", three suggestion chips, one message bar with the model chip and Attach. |

**Explicitly stays:**
- What every agent does, every handler, every stored value, every file the app writes.
- The request guard: every paid call still shows its price first and waits for the user; a zero
  price means unknown and is shown as unknown, never as free (spend chip included).
- Every control that exists today stays reachable (some move behind one click; none is dropped
  without an owner decision recorded in this spec).
- The type scale, spacing scale and dropdown component in `docs/gui_redesign.md`; the aligned-form
  rules (`ui/forms.py`: `field`, `FieldGridLayout`, `toggle_chip`) inside stage forms. The mockups'
  forms already use label-above grids.
- Attribute names that tests and `docs/learn/help_map.json` reach (for example `history_list`,
  `cost_history_btn`, `run_log_btn`, `learn_btn`, `project_meter`, `model_updates_section`, the
  limit fields), so help lessons and tests move with their widgets; the icon rail replacing
  `workspace_tabs` keeps a handle tests can reach.
- Window minimum 1000 × 600 (`main.py:269`), the version string (moves, see D2), the underscore
  caret.

## Goal and success measure
The redesign is done when all of these are shown, per slice for the agents that slice covers:
1. **Navigation depth:** at most one row of stage navigation (the stepper) between the top bar and
   the content on every agent screen, against three today (four in Quill). Test: count visible
   tab bars, tool rows and mode switches per agent.
2. **Nothing lost:** a snapshot of every action button, field and menu action reachable today
   (taken before Build, by attribute name) is still reachable after: visible, or one click away
   (popover, side button, menu). A test walks the snapshot; any removal needs an owner line here.
3. **One primary action** per stage screen: exactly one visible button with the primary style.
4. **Fit:** no control outside its container and no clipped text (`ui.text_fit.clipped_text`
   empty) at 1000 × 600, 1440 × 900 and 1500 × 950, for every agent and stage (extends the
   existing rail and crush tests, `test_no_panel_row_is_crushed_below_its_minimum`).
5. **Money:** the spend chip shows today's spend against the daily limit; with no limit it says
   so; with an unpriced request it says "unknown", never €0.00. The request-guard tests pass
   unchanged.
6. **Readable:** every text token on its background in the light palette meets WCAG AA contrast
   (4.5:1 body, 3:1 large text and icons). Test computes it from the tokens in `ui/theme.py`.
7. **Motion rule** (as decided in D5): a test asserts no animation timer runs while a text field
   in the pane has focus, and none runs at all when reduced motion is on.
8. **Seen by the owner:** native (cocoa) renders of each changed screen at 1440 × 900 and
   1000 × 600, beside the matching mockup, shown with each slice's build.
9. Full suite green, shuffled.

## Scope: slices, smallest useful first
Each slice ships on its own, through Review and Verify, and leaves the rest of the app working.

| # | Slice | Contains | Leaves untouched |
|---|---|---|---|
| 1 | **Shell** | Light palette as a fourth theme (**new**) in `ui/theme.py` (today `THEMES = (GREEN, RED, BLUE)`, `:43`); icon rail replacing the header tabs, More overflow and description strip; top bar with project selector, agent switch (Quill / Press, Booth / Label, replacing the tool row), spend chip and status chip with their popovers (D3); both side rails removed, their contents moved per D2 and D3. | Every agent panel's inside, including its tabs; the composer; all behaviour. |
| 2 | **Stepper and ask bar, straight agents** | The stepper component (**new**) and the model chip plus ask bar component (D10). Applied where today's tabs already are the stages: Booth, Reel, Herald, Nova (side buttons for Accounts and Voice per D1). | Author, Label, Sitebuilder, Vector, Kernel. Agent logic. |
| 3 | **Author** | One stepper across Quill and Press (D6); next-step card replacing the todo list (**new**, D7); Promote tiles; KDP CSV drop target; Quill's page, chapter list and Ask card. | Word goal, cover, focus mode (slice 5). Other agents. |
| 4 | **The rest** | Label, Sitebuilder, Vector (stages that are not today's tabs, D1), Kernel's chat screen with its chat list (D2). | Gimmicks. |
| 5 | **Gimmicks** | Each one the owner keeps under D5, one at a time: cover and spine progress with the stamp (**new**), word-goal ring (**new**, D8), focus mode (**new**, D9), Booth bars, Reel preview reshape, Sitebuilder palette preview. | Everything else. |

Slices 1 and 2 are the smallest that change how the app feels; slice 3 is the most value for the
main user. Each slice gets its own Architect pass; slice 1 almost certainly needs an ADR (window
structure, theme state, where chrome lives).

## Not in the app today (new scope)
Stepper; next-step card; word goal and its ring; cover with spine progress and the "ready to ship"
stamp; focus mode; the light theme; the icon rail; spend and status chips with popovers; the
single ask bar with a model chip; empty-state drop targets; Booth's animated bars; Reel's
reshaping preview; Sitebuilder's palette preview; side buttons for non-stage tabs. Nothing here
exists in code; each is built, reviewed and verified like a feature.

## Decisions (Define gate)
Decided 2026-11-25, owner: "do as recommended". Each item below is decided as its *Recommended*
text says; the alternatives were not taken.

**D1. Tabs that are not steps.** Label's six tabs are planning areas, not a sequence; Herald's
Accounts, Vector's Orders and Nova's Voice are setup or records; Quill's Outline, Characters, World
Notes and Sources are reference while writing; Sitebuilder's HTML / CSS / JS are views, not
stages; Vector's "Brief" stage is today's form, not a tab.
*Recommended:* a stepper shows only real stages and never marks a stage done by itself (see D6).
Setup and record tabs become one side button at the right of the stepper (as the mockups do:
Accounts, Orders, Voice and character). Quill's reference tabs become a "Notes" side button in the
Write stage that opens them in the chapter column. Sitebuilder's HTML / CSS / JS are tabs inside
the Code stage's preview. Label keeps its six as a stepper with no order enforced and no done
marks. *Alternative:* Label gets a plain segmented control instead of a stepper.

**D2. Where chat history, Cost History, Run Log, Learning Centre, Docs, Tooltips, Settings,
projects and the version go** (the mockups place only Settings, as a gear at the bottom of the
icon rail, and Kernel's chat list inside Kernel).
*Recommended:*
- Projects: the top-bar selector (today's project dropdown and its more menu, `main.py:2619`
  onward), with New Project, Project Overview and Save Current Setup in its menu; the project
  budget meter in that menu's header.
- Chat history: Kernel shows its list inline (mockup). Other agents get a History icon in the top
  bar opening a drawer with the same `history_list` (search, filter, day groups, right-click
  actions from `side-rails-redesign`).
- Cost History and Run Log: links in the spend chip's popover (D3).
- Learning Centre and Docs: one "?" icon above Settings at the bottom of the icon rail, opening a
  menu with this agent's Docs and the Learning Centre.
- Tooltips on/off and the theme choice: into Settings (set once, not used mid-task).
- Version: on the app mark's tooltip and in Settings > About; a stale build still shows an amber
  dot on the app mark (today's stale badge, `main.py:2530-2535`).

**D3. The right rail's Spend and Status detail.**
*Recommended:* the spend chip shows "€used of €limit today" and opens a popover with what the
spend rail holds today: Session and Today rows with their limit fields, the project row when a
project is active, Requests, Last request, Saved by local, Advice spent, Reset session spend, Cost
History, Run Log. The live estimate line moves next to the model chip in the ask bar, where the
money is about to be spent. The status chip shows the worst state ("Ready", "Busy", "Stressed",
an API-key problem) and opens a popover with System, Chat routing, API keys and Model updates. When
model updates are waiting, the chip carries their count, so `model-updates-visibility`'s promise
(updates are visible without opening anything) holds. *Alternative:* keep a slim right rail with
Spend only.

**D4. Do the three dark themes stay beside the light look?**
*Recommended:* light becomes the default look, with the three accents the themes have today
(green, rose, teal, which the mockups already offer). The three dark palettes stay selectable in
Settings as "Dark", each with its accent, so nothing the owner chose on 2026-10-06 is removed. Cost:
every new component is checked in four palettes (the contrast test in measure 6 covers it).
*Alternative:* light only, dark themes retired: less to build and test, but removes an existing
choice.

**D5. Does the 2026-10-06 rule still hold: "nothing moves in a pane someone is working in"?** The
owner asked for gimmicks this time but did not revisit that rule.
*Recommended:* keep the rule, and allow motion only when all are true: it is the answer to the
user's own action, it is short (300 ms or less) and does not loop, and it is outside the field
being typed in. The one loop allowed is Booth's bars, and only while audio plays. All motion stops
when macOS Reduce Motion is on (the radar check found Qt has no API for that setting, so
Architect picks how to read it) or when an in-app "Reduce motion" setting is on. Under that rule:
spine fill on Mark done, yes; stamp, yes (static); word-goal ring, yes, updated when typing pauses
(it sits in the top bar, not the page); focus mode, yes (hides, does not move); Reel preview
reshape on an aspect change, yes; Sitebuilder recolour on a palette pick, yes; Booth bars while
playing, yes. *Alternative:* the owner lifts the rule for this redesign.

**D6. One stepper across Quill and Press, and what "done" means.** Today Quill and Press are two
agents switched by the tool row. B shows one five-stage stepper over both.
*Recommended:* Write = Quill's draft and chapters; Prepare = Quill's Publish sub-tab plus Press's
next-step card; Export = Quill's Export Book plus Press's Export Approved, Make Release Kit and
Submission Ledger (`agents/manuscript/panel.py:367-378`); Promote = Quill's Market sub-tab plus
Press's Quote Finder, Quote Graphics, Shorts and Calendar; Track = Press's metrics, KDP CSV ingest
and connection status. A stage shows a tick only from a recorded fact (a file exported, a CSV
ingested, all todos done) or the user's own mark, never from a guess, because the app must not
claim results it cannot show. Clicking any stage opens it; the order is a suggestion, not a lock.

**D7. Next-step card instead of the todo list.**
*Recommended:* the card shows the first open todo with Mark done and the rest below it; adding,
editing, reordering and deleting todos stay, behind an "Edit list" link. The stamp appears when
every todo is done, whatever their number (the mockup's "5 of 5" is sample data). The mockup's
"Start over" un-marks everything; recommended to drop it, or to ask for confirmation if kept.

**D8. Word goal.** *Recommended:* off until the user sets a goal; set per project; "words today"
is the growth of the draft's word count since local midnight (deleting words can make it fall);
stored with the project. No goal, no ring.

**D9. Focus mode.** *Recommended:* hides the icon rail, chapter list and Ask card, keeps the top
bar's word ring and an Exit focus button; Escape also exits; the state is not remembered across
launches.

**D10. The single ask bar replaces the composer form.** On 2026-10-08 the owner chose the aligned
form over a "run bar" that put routing behind a popover (`docs/gui_redesign.md`, "One run bar
instead of three rows"). B's ask bar with a model chip is that run bar.
*Recommended:* confirm the reversal for the ask bar only: the chip shows provider and model with
BEST FIT; its popover holds provider, model, refresh, Tool, the nine provider permission chips and
Auto-Apply. Forms inside stages keep the aligned form.

**D11. Fonts.** The mockups use Inter, Space Grotesk and Newsreader (web fonts).
*Recommended:* the system font (SF Pro) for the interface and one bundled serif for the manuscript
page only (Newsreader is under the SIL Open Font Licence; bundling it adds a line to the licence
inventory in Comply). *Alternative:* system fonts only (no bundling, no Comply step).

**D12. Rails specs.** *Recommended:* release `rails-rebalance` as built (verify is done), so the
app tested in the testing phase is the current one; slice 1 then replaces both rails and keeps
that spec's measure 4 (moved controls keep their names, handlers, tooltips and help entries).

## Design (slice 1)
Phase 2, `ux-designer`, 2026-11-25. The owner started it before testing ("no testing").
It covers slice 1, the **Shell**, only. Agent panels' insides, the composer and all behaviour stay
as they are. Source: today's code (`main.py` `build_header_bar` 2499, `build_workspace_description`
2479, `build_left_panel` 2619, `build_center_panel` 2754, `build_right_panel` 3502) and the B
mockups (`B-Press`, `B-Booth`, `B-Kernel`; read 2026-11-25). Where this section and the mockup
differ, this section wins and says why.

### S1. Window structure
```
┌──────┬──────────────────────────────────────────────────────────────┐
│ mark │ TOP BAR (56 px): [switch or name] [project ▾][…] [⧖] ··· [spend chip] [status chip] │
│ ──── ├──────────────────────────────────────────────────────────────┤
│ ws×8 │                                                              │
│      │   centre panel as today (agent title, subtitle, the agent's  │
│      │   own panel), now the full width beside the rail             │
│ ──── │                                                              │
│  ?   │                                                              │
│  ⚙   │                                                              │
└──────┴──────────────────────────────────────────────────────────────┘
  72 px
```
- The **rail** runs the full window height. The top bar sits over the content column only, as in
  the mockups. No other chrome: `RailLeft`, `RailRight`, `AppHeader` (as a row) and
  `WorkspaceDescriptionStrip` are gone.
- The **top bar is 56 px tall**, the same as today's `HEADER_HEIGHT` (the mockup's 68 px would take
  12 px from every panel at the 600 px minimum height). The 20 px description strip is gone, so
  panels gain 20 px of height at every size. Controls in the bar are 32 px tall (chips) or 36 px
  (selector, switch), all over the 24 × 24 px minimum target.
- In slice 1 the centre panel keeps its margins, `agent_title_label` and `agent_subtitle_label`.
  Only `workspace_tool_row` leaves it (S3). Panels fill the width; the mockups' 1160 px content
  cap starts with slice 2.

### S2. Icon rail
| Part | Spec |
|---|---|
| Width, surface | 72 px, `SURFACE`, 1 px `BORDER` on the right. Padding 16 px top and bottom. |
| App mark | 36 × 36 px, radius 10, `TEXT` fill with the letter "i" in `SURFACE` (the mockup's mark). Tooltip and accessible description: `app_version.tooltip()` (the version, D2). Not a button, but it takes focus so VoiceOver reads the version. 10 px below it. |
| Stale build dot | When `app_version.staleness()["current"]` is false: an 8 px dot in `WARNING_DOT` at the mark's top-right corner, with a 2 px `SURFACE` ring so it reads on both the mark and the rail. Tooltip and accessible name gain "This build is older than the code: rebuild to update". Replaces today's amber `VersionBadge` state. |
| Workspace buttons | One per workspace in `WORKSPACES` order (Author, Audio + Music, Video + Ads, Social, Web, Brand Design, Brand Content, Assistant). 44 × 44 px, radius 12, 4 px gap, 20 px stroke icon (1.8 px stroke, from the mockup's paths, saved as SVG in `assets/` and drawn through the same `QIcon` path as `icon_button`; no icon font, so D11's Comply step is not triggered). |
| States | Default: icon `TEXT_DIM`, no fill. Hover: `ELEVATED` fill. Selected: `ELEVATED` fill, icon `TEXT`, plus a 3 × 20 px `ACCENT` bar against the rail's left edge, level with the button. The bar is what meets 3:1 (WCAG 1.4.11); the fill alone is 1.12:1 and only decorates. Focus: 2 px `ACCENT` ring, 2 px out. Pressed: `ACCENT_WASH` fill. |
| Names | Tooltip: the workspace name, a line break, then the text the description strip shows today (`workspace_description_label`'s source for that workspace). Accessible name: the workspace name. Accessible description: the description text. So the codename explanation the strip existed for (`main.py:2482`) is one hover away. |
| Bottom group | Pinned to the bottom, 8 px gap: **"?"** (help), then the **Settings gear**. Same 44 px buttons and states, no selected state. |
| "?" menu | A `QMenu` (follows `appkit_guard`): "`<Agent>` docs" (today's `agent_docs_btn` → `show_agent_docs`, label naming the open agent, for example "Press docs"), "Learning Centre   F1" (`learn_btn` → `show_learning_center`), separator, "Keyboard shortcuts" (S9 list, read-only). |
| Settings gear | `settings_btn` → `show_settings`. Tooltip "Settings (⌘,)". |
| Fit | 16 + 46 (mark) + 8 × 48 + 8 + 2 × 48 + 16 = 566 px, under the 600 px minimum height. No overflow menu exists or is needed. A test asserts every rail button is fully visible at 1000 × 600. |

`workspace_tabs` stays the handle for the workspace selection with today's contract: the same
names, order, `count()`, `currentIndex()`, `setCurrentIndex()` and `currentChanged`, which
`_workspace_changed` and `help_map.json` use. Architect chooses how (a hidden `QTabBar` that drives
the buttons, or a rail class with that API). `header_fitter` and `workspace_more_btn` retire: their
tests (`test_panel_layout.py:848-896`) are replaced by the rail fit test, with the change named in
the Build PR, not deleted silently.

### S3. Top bar
Left to right, with a 12 px gap and horizontal padding of 24 px (16 px below 1200 px window width).

| # | Element | Spec | Today's control |
|---|---|---|---|
| 1 | **Agent switch** (two-agent workspaces) | Segmented control, 36 px: Quill / Press, Booth / Label. Selected segment: `TEXT` fill, `SURFACE` text, weight 600 (mockup B-Booth). Other segment: no fill, `TEXT_DIM`. Left and Right arrows move between segments when it has focus. | `workspace_tool_row` and `workspace_tool_buttons[key]` (keep both names: the row is the switch, the dict holds its two buttons, each still calling `select_agent(name)`) |
| 1′ | **Agent name** (one-agent workspaces) | The agent's codename in the title style (14 px, 600), for example "Reel", "Kernel" (mockup B-Kernel). Not interactive. | new label `topbar_agent_label` |
| 2 | **Project selector** | `history_project_filter` itself (the existing combo, its items, its `_switch_project` handler and the dropdown component of `docs/gui_redesign.md`), restyled as a 36 px bordered field with the project name in 13 px weight 600. Width 140 to 260 px, eliding. Tooltip: "Working in `<project>`" or "No project selected". | `history_project_filter`; also takes over the job of `project_context_pill` (S4) |
| 3 | **Project actions** | `project_menu_btn` (the `more` icon button) right beside the selector, opening `project_menu` (S5). | `project_menu_btn`, `project_menu` |
| 4 | **History** | 32 px icon button (clock icon), tooltip "Chat history (⌘Y)", opens the History drawer (S7). Checked style while the drawer is open. | new `history_btn` |
| 5 | *Stretch* | Slice 2 puts the stepper here, centred. Slice 1 leaves it empty. | |
| 6 | **Spend chip** | S6. | new `spend_chip` |
| 7 | **Status chip** | S6. | `agent_status_pill` (the chip keeps this name; `status_chip` may be an alias) |

**Widths.** Natural widths at 13 px system font: switch ~140 px, selector 140 to 260 px, actions 32
px, history 32 px, spend chip full ~175 px ("€12.34 of €50 today"), status chip full ~165 px
("Key check failed · 3"). Room for the bar is the window width minus 72 px for the rail, minus
padding.

| Window width | Bar content width | Fits in full form? | Room left for the stretch (slice 2 stepper) |
|---|---|---|---|
| 1000 px (minimum) | 928 − 32 = 896 px | yes: ~140 + 260 + 32 + 32 + 175 + 165 + 6 × 12 = 876 px | ~20 px, so slice 2 needs the collapse steps below |
| 1440 px | 1368 − 48 = 1320 px | yes | ~444 px |
| 1500 px | 1428 − 48 = 1380 px | yes | ~504 px |

**Collapse rule** (applied in this order as room runs out, and undone in reverse as it returns;
each step is one width threshold, computed from measured hints and not hard-coded pixels, so
cocoa and offscreen fonts both work):
1. *(Slice 2)* Stepper stages show their number only, except the current stage, which keeps its
   label. Full names stay in each stage's tooltip and accessible name.
2. Spend chip drops " today": "€12.34 of €50".
3. Project selector shrinks to its 140 px minimum and elides.
4. Status chip goes compact: the dot and the count badge only. Its text moves to the tooltip and
   stays in the accessible name.
5. Spend chip goes compact: the amount only, "€12.34". The unknown form keeps its word:
   "€12.34 + unknown". The limit moves to the tooltip.
6. Agent switch segments drop their side padding from 14 to 8 px.

**Nothing goes into an overflow menu, and nothing is hidden.** Both chips, the selector and History
are visible at every width from 1000 px; the money figure never disappears. After step 6 the bar
fits 1000 px with a full five-stage stepper in numbers-only form (~5 × 40 px). Measure 4's fit
test runs at 1000, 1440 and 1500 px with long values: the project name "A Very Long Project Name
For Testing", "€1234.56 of €5000 today", the unknown form and the status "Key check failed · 12".

Inherited by slice 3, so Quill's three columns fit: the content column (928 px at minimum, less
2 × 24 px padding = 880 px) keeps the page at least 560 px wide. Side columns give way first. The
chapter list becomes a "Chapters" button that opens the same left drawer as History (S7) below
1180 px window width, and the Ask card keeps 280 px. Slice 3's Design confirms this against its
own mockup.

### S4. Where every control in today's header and both rails goes
Every attribute keeps its name, handler, tooltip and `help_map.json` entry (D12, and
`rails-rebalance` measure 4). "Popover" means S6's popovers; "drawer" means S7.

**Header (`build_header_bar`, `build_workspace_description`)**

| Today | Goes to |
|---|---|
| `WordmarkDot`, `Wordmark` ("IMPRINT") | Retired; the app mark (S2) replaces them. The window title still says "Imprint". |
| `version_badge` (text, tooltip, `state=stale`) | Retired as a visible label; its text and tooltip go to the app mark's tooltip, and its stale state becomes the stale dot (S2). Settings > General gets an "About" line with the version string. `test_version.py:164-167` moves to the mark's tooltip and the About line. |
| `HeaderDivider` | Retired (no row to divide). |
| `workspace_tabs` | Icon rail (S2), handle kept. |
| `workspace_more_btn`, `header_fitter` | Retired; the rail never overflows (S2). |
| `project_context_pill` | Retired: the project selector now shows the project name in the bar at all times. Its tooltip text moves to the selector. It is a label, not a control, so measure 2 is not affected. |
| `agent_status_pill` | Status chip (S6), name kept. |
| `theme_dots` (`ThemeDots`) | Settings > General, under "Look" (S8). Same widget and keys, so `test_theme.py:276-312` keeps working once it opens Settings. |
| `agent_docs_btn` | "?" menu, first item (S2). Kept as a `QAction` named `agent_docs_btn`. |
| `tooltips_toggle_btn` | Settings > General, "Show tooltips" (S8). The window keeps the checkable control (or a checkable `QAction`) under this name, so `_toggle_tooltips` and `main.py:484` still read `isChecked()`. |
| `settings_btn` | Rail gear (S2). |
| `workspace_description_label` (strip) | Retired; its text goes to each rail button's tooltip and accessible description (S2). `main.py:3825` writes to the rail instead. |

**Left rail (`build_left_panel`)**

| Today | Goes to |
|---|---|
| `history_project_filter` | Top-bar project selector (S3 #2). |
| `project_menu_btn`, `project_menu`, `new_project_btn`, `project_overview_btn`, `project_defaults_btn` | Top bar beside the selector (S3 #3); the menu and its three actions unchanged (S5). |
| `active_project_label` | Header of `project_menu` (S5). |
| `project_meter` | Header of `project_menu` (S5, D2). |
| `history_search`, `history_agent_filter`, `history_list`, `new_chat_btn` | History drawer (S7). The context menu, Delete and Backspace shortcuts, double-click to rename and day groups come with `history_list` unchanged. |
| `cost_history_btn`, `run_log_btn` | Spend popover footer (S6). |
| `learn_btn` | "?" menu (S2). Kept as a `QAction` named `learn_btn`; F1 still opens it. |
| `agent_buttons` (empty dict) | Kept as is. |

**Right rail (`build_right_panel`)**

| Today | Goes to |
|---|---|
| Spend heading, `reset_session_budget_btn` | Spend popover header. |
| `session_meter`, `daily_meter` with `session_budget_input`, `daily_budget_input` | Spend popover. They still save on Enter or on leaving the field (`_commit_budget_limits`). |
| `request_count_stat`, `last_request_stat`, `local_savings_stat`, `local_spent_stat` | Spend popover, same order and hover detail. |
| `live_estimate_label` | Slice 1: one caption line under the composer's model row in `normal_panel`. This is the only change to the composer in slice 1. Slice 2 moves it beside the model chip (D3). See open point O1. |
| Status heading | Status popover heading. |
| System card: `resource_status_card` (`resource_label`), `realtime_monitor_btn` | Status popover, "System" section. |
| Chat routing: `routing_status_card`, `route_result_label`, `recommendation_label` | Status popover, "Chat routing" section. |
| API keys: `api_keys_status_card`, the six `*_key_label` aliases | Status popover, "API keys" section. |
| `model_updates_section`, `model_updates_card` (check, dismiss, update, startup checkbox, media notices) | Status popover, "Model updates" section; its count also shows on the chip (S6). |

Before Build, Build takes measure 2's snapshot (every action button, field and menu action reachable
today, by attribute name). The removals above (wordmark, divider, `version_badge` label,
`project_context_pill`, `workspace_more_btn`, the strip) are labels or overflow chrome, not
actions. The owner approving this Design is the owner line measure 2 asks for.

### S5. Project menu
`project_menu` (`QMenu`, `appkit_guard` rules) opens under `project_menu_btn`. Its header is a
`QWidgetAction`, shown only while a project is active: `active_project_label` ("Working in …",
`TEXT_DIM`, 12 px) above `project_meter` (the project budget bar). Then a separator and today's
three actions in today's order: New Project, Project Overview, Save Current Setup, with their
enabled rules and tooltips. With no project active the header is absent and the menu starts with
New Project.

### S6. Spend chip and status chip
Both chips are 32 px tall, radius 16, 1 px `BORDER_STRONG`, `SURFACE` fill, 13 px text, 12 px side
padding. They are buttons: hover `ELEVATED`, focus ring as in S2, Space or Return opens the popover.

**Spend chip text** (today's daily figures; the session figures are in the popover):

| State | Full form | Tone |
|---|---|---|
| Normal (under 80 % of the daily limit) | "€1.20 of €5 today" | `TEXT_DIM` text |
| Nothing spent yet, nothing unpriced | "€0.00 of €5 today": true, because nothing was spent | `TEXT_DIM` |
| No daily limit (`daily_budget_eur` is 0, which `BudgetRow.set` already reads as no limit) | "€1.20 today · no limit" | `TEXT_DIM` |
| 80 % to under 100 % | "€4.10 of €5 today" | `WARNING` text and border |
| At or over the limit | "€5.10 of €5 today" | `DANGER` text and border. Tooltip: "Daily limit reached." The request guard's behaviour is unchanged |
| Some of today's requests had no price | "€1.20 + unknown of €5 today" | `TEXT` text; tooltip: "N requests today had no price, so the real total is more than €1.20." |
| Every one of today's requests had no price | "Unknown of €5 today" (never "€0.00") | as above |

Limits are formatted like the fields (`format_limit`: "€5", "€1.5"), and amounts with two decimals.
The accessible name is the full sentence, for example "Spent today: 1.20 euros of a 5 euro limit,
plus an unknown amount". **Data dependency for Architect:** the chip needs today's count of
requests whose price was unknown. If the usage tally does not record that now, Architect adds it;
the figure is never inferred from a zero.

**Spend popover** (`Qt.Popup` frame, not a `QMenu`, because it holds text fields; 320 px wide;
opens below the chip, right edges aligned; 16 px padding; `SURFACE` with `BORDER` and the card
shadow):
1. Heading "Spend" and `reset_session_budget_btn` (link) on one row.
2. `session_meter`, `daily_meter` (bars and limit fields, unchanged).
3. Project row while a project is active: a read-only `KeyValueRow` "Project" with "€x of €y" (new
   `project_spend_stat`, fed from the same numbers as `project_meter`; the bar itself stays in the
   project menu per D2).
4. `request_count_stat`, `last_request_stat`, `local_savings_stat`, `local_spent_stat`.
5. A line in `TEXT_DIM` when anything today was unpriced: "N requests had no price; totals
   exclude them."
6. Footer, separated by a `BORDER` line: `cost_history_btn` and `run_log_btn` as two link buttons on
   one row.
Escape or a click outside closes it. Focus goes to the first limit field when it opens from the
keyboard, and returns to the chip when it closes. An edit in progress is committed on close
through `editingFinished`, as on the rail today.

**Status chip:** an 8 px dot, the state word, and a count badge when model updates are waiting.

| Worst state wins (top first) | Word | Dot |
|---|---|---|
| System summary red | "Machine stressed" | `DANGER` |
| Any API key "Check failed" (`ApiKeysStatusCard` tone `warning`; "Not configured" is normal, not a problem) | "Key check failed" | `WARNING_DOT` |
| System summary yellow | "Machine busy" | `WARNING_DOT` |
| A request is running | "Working" | `INFO` |
| Otherwise | "Ready" | `ACCENT` |

The count badge is a pill after the word, for example "Ready · 3", with `ACCENT_WASH` fill and
`TEXT` digits. It shows the number of waiting model updates from the same source as
`model_updates_section`'s title ("Model updates · 3 new"). Zero means no badge. That keeps
`model-updates-visibility`'s promise: updates are visible without opening anything. Accessible
name: "Status: Ready. 3 model updates waiting." The dot is never the only signal, because the
word always says the state in full form and the tooltip and accessible name say it in compact
form.

**Status popover** (`Qt.Popup` frame, 340 px, under the chip, right-aligned, scrolls past 70 % of
the window height): heading "Status", then the four `CollapsibleSection`s in today's order:
System, Chat routing, API keys, Model updates. Each still shows its one-word summary while
closed. A section whose state is the chip's state opens expanded, so the reason is the first thing
seen; the rest open collapsed. "Model updates" opens expanded whenever the badge shows.

### S7. History drawer
- Opened by `history_btn` or ⌘Y; closed by ⌘Y, Escape, the drawer's close button, a click on the
  dimmed content, or opening a chat.
- A 320 px panel over the left of the content column (it does not cover the icon rail), full height
  below the top bar, `SURFACE` with `BORDER` on its right and a 12 % `TEXT` scrim over the rest of
  the content. It overlays and does not reflow the panel, so nothing being typed moves (D5).
- Contents top to bottom: a heading row "Chats" with `new_chat_btn` ("New chat", quiet style) and a
  close button (×, accessible name "Close history"); `history_search` and `history_agent_filter` on
  one row; `history_list`, taking the rest of the height. Day groups, the context menu, Delete,
  Backspace and double-click to rename are unchanged.
- Focus goes to `history_search` on open and returns to `history_btn` on close. Tab order: New
  chat, close, search, filter, list. The drawer keeps focus inside itself while open.
- Kernel uses the same drawer in slice 1; its inline list (mockup B-Kernel) is slice 4.
- Help lessons that point at `history_list` or `new_chat_btn` open the drawer first; the same goes
  for popover targets (`session_budget_input`, `daily_budget_input`) and "?" menu targets
  (`learn_btn`). Architect picks the mechanism (a "reveal" hook per target in `help_map.json`);
  each lesson is checked in Build.

### S8. Light palette (fourth theme) and Settings
**Tokens.** These are the light values of every token the dark palettes theme today, plus the tokens
the dark themes keep fixed and that fail on white (borders and semantic colours). The values come
from the mockups where they pass, and were changed where they do not. Contrast was computed with
the WCAG 2.x relative-luminance formula on 2026-11-25; "worst" is the lowest result against `BG`,
`SURFACE`, `ELEVATED` and `SUNKEN`.

| Token | Light value | Use | Worst contrast | Note |
|---|---|---|---|---|
| `BG` | `#f4f5f7` | window, content background | | mockup |
| `SURFACE` | `#ffffff` | rail, top bar, cards, popovers, drawer | | mockup |
| `ELEVATED` | `#eef0f3` | hover, selected rail button | | mockup |
| `SUNKEN` | `#ffffff` | text fields (the field is marked by its border, not a darker well) | | mockup |
| `SUNKEN_LIT` | per accent: green `#e8f3ee`, rose `#fbe9ed`, teal `#e6f3f6` | focused field | `TEXT` 15.7:1 | |
| `TEXT` | `#14181f` | primary text | 15.59:1 | mockup |
| `TEXT_DIM` | `#5b6472` | labels, secondary text, chips | 5.24:1 | mockup |
| `TEXT_MUTE` | `#636b78` | placeholders, section headers | 4.71:1 | mockup's `#6b7482` fails (4.14:1 on `ELEVATED`, 4.33:1 on `BG`) |
| `BORDER` | `#e1e4ea` | card and bar hairlines (decorative only) | 1.12:1 | mockup; never the only edge of a control |
| `BORDER_STRONG` | `#7a8290` | control borders: fields, chips, selector, ghost buttons | 3.39:1 | mockup's `#d5d9e0` and `#e1e4ea` fail 1.4.11 (3:1 for control edges), so fields read slightly firmer than drawn |
| `ACCENT` green, rose, teal | `#0b7a55`, `#be123c`, `#0e7490` | primary buttons, selected marks, focus rings, links | 4.68:1, 5.51:1, 4.69:1 | mockup's three accents; all pass as text too |
| `ACCENT_DIM` | `#086446`, `#9f1239`, `#155e75` | pressed primary, accent text on `ACCENT_WASH` | 6.30:1, 7.02:1, 6.36:1 | |
| `ACCENT_TEXT` | `#ffffff` | text on an accent fill | 5.34:1, 6.29:1, 5.36:1 on the fill | dark themes use near-black here; light uses white (mockup) |
| `ACCENT_WASH` | accent at 0.10 alpha | selected rows, count badge | `TEXT` on the wash ≥ 15:1 | |
| `ACCENT_LINE` | accent at 0.45 alpha | accent outlines that are decoration only | | not a focus ring (the ring is solid `ACCENT`) |
| `PHOSPHOR` | = `ACCENT_DIM` per accent | typed glyphs and the underscore caret | ≥ 6.30:1 | dark's `#00ff41` is 1.4:1 on white. On light the "you wrote this" colour is the deep accent, which is calmer and readable |
| `PHOSPHOR_LINE` | `ACCENT_DIM` at 0.45 alpha | | | |
| `DANGER` | `#b91c1c` | destructive, over-limit | 5.67:1 | dark's `#f87171` is about 2.7:1 on white |
| `WARNING` | `#92400e` | warning text | 6.21:1 | dark's `#fbbf24` is about 1.7:1 on white |
| `WARNING_DOT` (new) | `#b45309` | stale dot, warning dots (non-text) | 4.40:1 (3.54:1 on the `TEXT` app mark) | |
| `INFO` | `#1d4ed8` | neutral emphasis, "Working" dot | 5.87:1 | |
| `*_WASH`, `*_LINE` for `DANGER`, `WARNING`, `INFO` | the colour at 0.10 and 0.40 alpha | | text on a wash uses `TEXT` or the colour itself (≥ 5:1) | |

The dark palettes keep their values. `WARNING_DOT` in dark is today's `WARNING`. **For Architect:**
`ui/theme.py` themes only the accent, the phosphor and the greys, by swapping the green palette's
literals (`_SWAP`), and its docstring says semantic colour "does not change". Light breaks that,
because `BORDER`, `BORDER_STRONG` and the semantic colours need light values. The mechanism (extra
palette keys and the literals they swap, or a second semantic table) and that docstring change go
in the slice-1 ADR. The contrast test (measure 6) checks every text and indicator token above
against every background it is used on, in all six combinations (light × 3 accents, dark × 3),
following the `git_autosync/tests/test_header_fit.py` pattern (playbook).

**Fonts in the shell:** the system font (D11) at the `docs/gui_redesign.md` type scale: chips and
selector 13 px, the agent name 14 px weight 600, the drawer heading 14 px weight 600. No bundled
font in slice 1.

**Settings > General** (`ui/dialogs.py`, today's `ThemePick` combo at 425-450):
- **Look**: a two-segment control, Light | Dark. Light is the default (D4).
- **Accent**: `theme_dots`, the existing widget, showing three dots (green, rose, teal). It is
  painted in the accents of the selected Look. Arrow keys and click work as today; the preview
  applies live and reverts on Cancel, as `preview_theme` and `restore_theme` already do.
- Labels: "Light" and "Dark"; accents "Green", "Rose", "Teal". Dark's teal is today's
  "Blue (Cyberpunk)" (`#22d3ee`) and dark's rose is today's "Red" (`#f43f5e`); dark's values do not
  change. `THEMES` grows from 3 to 6 combinations, or becomes Look × Accent. Architect decides how,
  and `dialogs.py:51-60`'s count sentence follows `THEMES` as it does now.
- **Show tooltips**: a toggle bound to `tooltips_toggle_btn`'s state.
- **About**: "Imprint `<version string>`", with a stale note when stale.
- Switching the look while Booth plays must not hit the 2026-10-05 `QComboBox.setStyle` deadlock
  (spec Risks). This is Architect's to solve; Design only asks that the switch be instant, with no
  transition.

### S9. Keyboard access
| Keys | Action |
|---|---|
| ⌘1 to ⌘8 | Workspace 1 to 8 in rail order (Assistant is ⌘8) |
| ⌘[ and ⌘] | The other agent in a two-agent workspace (Quill ↔ Press, Booth ↔ Label) |
| ⌘Y | History drawer open and close |
| ⌘, | Settings (macOS standard) |
| F1 | Learning Centre (unchanged, `main.py:433`) |
| ⌘? (⌘⇧/) | "?" menu |
| Escape | Close the open popover, menu or drawer; with none open it does nothing new |

- Today no shortcut except F1 exists in the window (`main.py:433`), so none of these collides.
  Architect checks each agent panel's own shortcuts.
- Tab order: rail (mark, eight workspaces, ?, gear), then top bar left to right, then the panel.
  Inside the rail, Up and Down move between buttons, and Return or Space activates.
- Every icon-only control has an accessible name: the rail buttons, ?, gear, `history_btn`,
  `project_menu_btn` and the drawer's close button. Both chips have the full-sentence names given
  in S6. The selected workspace sets the accessible state "selected".
- A focus ring is never hidden under the drawer or a popover (2.4.11): the scrim takes no focus,
  and focus stays inside the drawer or popover while it is open.
- Before the owner sees the slice, Verify does a five-minute VoiceOver pass over the rail, the top
  bar, both popovers and the drawer (playbook).

### S10. Motion (D5) and Reduce Motion
In slice 1 only two things can move, and both answer the user's own click:

| What | Motion | Reduce Motion on |
|---|---|---|
| History drawer open and close | 160 ms slide and scrim fade, ease-out, no loop | appears and disappears at once |
| Popovers and menus | none (they appear at once, like macOS menus) | none |
| Theme switch | none (instant) | none |
| Rail selection, chip state changes | none (instant) | none |

Nothing animates while a text field in the content has focus: the drawer opens over the panel
and takes focus itself, and it does not move any field. "Reduce motion" is honoured when either
macOS's setting is on (Architect picks how to read it; the radar found no Qt API) or the new
Settings > General toggle "Reduce motion" is on. That toggle is off by default, and on whenever
macOS's setting is on. Measure 7's test covers the drawer timer.

### S11. States to check in Build and Verify
- No project: the selector says "All projects", the project menu has no header, and the spend
  popover has no Project row.
- No chats: the drawer's list shows "No saved chats yet." in `TEXT_DIM`, and New chat is still
  there.
- No limit, over the limit, unknown price: S6 table, each one tested.
- Model updates 0, 1 and 12: the badge is absent, then shows "1" and "12", and the compact chip
  still shows the badge.
- Stale build: the dot is on the mark, and both the tooltip and the About line say it.
- 1000 × 600, 1440 × 900, 1500 × 950 in light green and dark green: no clipped text
  (`clipped_text` empty) and every rail button visible. Native (cocoa) renders go beside
  `B-Press` and `B-Booth` for the owner (measure 8).

### Open points for the owner (Design)
Decided 2026-11-25, owner: "Approve as recommended". Each point below is decided as its
*Recommended* text says.

- **O1. Where the live estimate sits in slice 1.** *Recommended:* one caption under the composer's
  model row, the one small touch to the composer, until slice 2's ask bar takes it (D3). The
  number then stays visible while typing, not behind a popover. *Alternative:* in the spend
  popover only until slice 2; this touches nothing in the composer, but the estimate is one click
  away for one slice.
- **O2. Existing installs that saved a dark theme.** *Recommended:* the first launch of slice 1
  switches them once to Light with the same accent (green stays green, Red becomes rose, Blue
  becomes teal) and shows "Imprint has a new light look. Dark is in Settings > General." once. A
  later choice is never overridden. *Alternative:* keep their saved dark theme, so only new
  installs start light.
- **O3. Project budget in two places.** D2 puts `project_meter` in the project menu and D3 puts a
  project row in the spend popover. *Recommended:* both. The bar stays in the menu (D2), and the
  popover shows one read-only line (S6 item 3), so all money is also in one place.
- **Mockups:** none made for this phase. The B mockups already show the rail, bar and chips. A
  mockup of the popovers, drawer and the 1000 px collapse can go on the canvas if the owner wants
  one (only with the owner's OK).

## Architecture (slice 1)
Phase 3, `architect`, 2026-11-25. Input: "Design (slice 1)" as approved (S1–S11, O1–O3); nothing
in it is redesigned here. The decisions, their evidence and the alternatives are in
`docs/adr/0006-manuscript-shell.md` (Accepted 2026-11-25). Radar note:
`docs/foundry/radar-notes/2026-11-25-stack-manuscript-shell.md`. Legal consult skipped: slice 1
adds no data flow, processor, dependency or bundled asset (S2's icons are drawn in-repo as SVG).

**A1. Light palette.** Every palette gains the border and semantic tokens (`BORDER`,
`BORDER_STRONG`, `DANGER`/`WARNING`/`INFO` with their washes and lines) and the new `WARNING_DOT`.
Dark palettes keep today's values; light palettes take S8's. `global_stylesheet()` and
`recolour()` work unchanged. `WARNING_DOT` is painter-only (`theme.token(...)`), because its dark
value equals `WARNING` and a literal swap cannot tell them apart; `_SWAP` raises on any such
ambiguity. The 48 colour literals outside the tokens (ADR context) are replaced by tokens in this
slice, guarded by a test, because light becomes the default for every panel. The docstring and
`appearance_intro()` change from "semantic colour never changes" to "semantic meaning never
changes; light needs darker values".

**A2. Theme model.** Look × Accent with one stored key, `ui_theme`: six keys `light-green`,
`light-rose`, `light-teal`, `green`, `red`, `blue` (dark keys unchanged, so no saved value breaks).
Helpers `look`, `accent_of`, `compose`, `themes_for`; labels "Light · Green" … "Dark · Teal".
Default `light-green`. O2: `theme.adopt_light_once()` moves a saved dark key to light with the same
accent once, writes `ui_light_adopted`, and returns whether to show the one-time note (a
dismissible line at the top of the content column). The count sentence is built from `LOOKS` and
`ACCENTS`.

**A3. `workspace_tabs`.** `WorkspaceRail` (`ui/shell/icon_rail.py`) is the handle, implementing
the `QTabBar` subset in use (`count`, `tabText`, `currentIndex`, `setCurrentIndex`,
`currentChanged`, `elideMode`, `isTabVisible`, tab tooltips). `header_fit.py`, `header_fitter` and
`workspace_more_btn` are deleted; `TopBarFitter` applies S3's collapse steps from measured hints.

**A4. Popovers and menus.** Spend and status: `Popover`, a `Qt.Popup` frame parented to the
window. Project and "?": `QMenu` with `exec()`, under the process-wide `appkit_guard`; the project
menu's header is a `QWidgetAction`. Limit fields commit on close through a deferred
`_commit_budget_limits`; popovers also close on app deactivation. Known macOS limit: no right-click
menu in the limit fields (QTBUG-133560); keyboard copy and paste work.

**A5. Unknown-price count (state change).** Today an unpriced cloud request is stored as
`cost_eur = 0.0` with nothing marking it (`services/usage_tracker.py:133-134`). Smallest additive
change: `cost_type = "unpriced"` for those rows (and for callers passing the new
`price_known=False`), `cost_eur` still `0.0`, so every total and guard path is unchanged;
`get_unpriced_requests_today()` feeds the chip. No schema change. Agent callers that turn an
unknown per-unit price into `0.0` (`agents/creator/panel.py:1734,1769,1846`) are a separate
follow-up, not slice 1.

**A6. Reveal hooks.** `spotlight.reveal()` asks any ancestor with `reveal_for_lesson()` (the drawer,
the popovers) to show itself first. A `QAction` target (`learn_btn`, `agent_docs_btn`,
`new_project_btn`) rings the button that opens its menu, named by the action's `lessonAnchor`
property; menus are not opened by a lesson. This also fixes today's crash on "Show me" for
`new_project_btn` (`spotlight()` calls `window()` on a `QAction`). `help_map.json` keeps every key.

**A7. Reduce Motion.** `ui/motion.py`: `system_reduce_motion()` reads
`NSWorkspace.accessibilityDisplayShouldReduceMotion` through `ctypes` (no PyObjC), False off macOS
or offscreen, re-read when the app becomes active; `reduced()` adds the in-app setting
`reduce_motion`. `motion.animate()` is the only animation entry point: at most 300 ms, no loops,
none at all when reduced, stopped on hide and in `shutdown()`, tracked in `motion.running()`.

**A8. Theme switch while Booth plays.** No new `setStyle` call; the switch stays
`set_current()` + `apply_global_style()`. A regression test switches all six themes with a live
player under a 30 s timeout. Fallback if it ever hangs: release the player (saves the playhead),
restyle, reload.

**A9. Window-owned controls.** `tooltips_toggle_btn`: a checkable `QAction` on the window, bound to
Settings' "Show tooltips". `agent_docs_btn`, `learn_btn`: `QAction`s in the "?" menu; F1 unchanged.
`settings_btn`: the rail gear. `agent_status_pill`: the `StatusChip`. `live_estimate_label`: a
caption under `normal_panel`'s model row, its updater untouched (O1).

**A10. Boundaries.** New `ui/shell/` (`icon_rail`, `top_bar`, `chips`, `popover`, `drawer`) and
`ui/motion.py` import Qt, `ui.style`, `ui.theme` and `ui.motion` only. `main.py` still builds every
existing control with its handler and places it in these containers. Chip text and status state
are pure functions (`spend_chip_text`, `status_state`), fed from values the window already holds;
nothing new fetches on the UI thread and no `QThread` is added.

### Test plan (measures 2, 4, 6, 7 at this slice)
| Measure | Test (new unless marked) | Passes when |
|---|---|---|
| 2 Nothing lost | `test_shell_inventory.py`: Build's first commit writes `tests/data/shell_controls_before.json`, every action button, field, checkable and menu action reachable from `build_header_bar`, `build_left_panel`, `build_right_panel` before any change, by attribute name. The test resolves each through `_find_control` after the change and checks it is visible, or one click away (inside a `Popover`, the drawer or a `QMenu` whose opener is visible), with the same handler connected and the same tooltip. | every name passes, except the S4 removals listed in the test with this spec as the owner line |
| 4 Fit | Rewrite of `test_panel_layout.py:843-888`: at 1000 × 600, 1440 × 900, 1500 × 950, in `light-green` and `green`, every rail button is inside the rail and visible; the top bar's children are inside the bar with S3's long values (project name, "€1234.56 of €5000 today", the unknown form, "Key check failed · 12"); `clipped_text` is empty for the bar, the open spend and status popovers and the open drawer; S3's collapse steps happen in order as width falls. | no overlap, no clipping, money figure always visible |
| 6 Readable | `test_contrast.py`: every text and indicator token in S8 against `BG`, `SURFACE`, `ELEVATED`, `SUNKEN` (washes composited over `SURFACE`), WCAG 2.x formula, 4.5:1 text and 3:1 indicators and control borders, in all six themes. | all pass in the three light themes; dark `TEXT_MUTE` see owner point AO2 |
| 7 Motion | `test_motion.py`: opening the drawer starts exactly one animation (≤ 300 ms, loop count 1) and none when `reduced()`; `motion.running()` is empty after it finishes, when the drawer is hidden mid-slide, and while a text field in the content has focus; `system_reduce_motion()` is False offscreen and never raises. | as stated |
| guard | `test_usage_unpriced.py`: an unpriced cloud request stores `unpriced` and `0.0`; totals unchanged; the count is right; `spend_chip_text` never says "€0.00" when the count is over 0 (every S6 row). Existing request-guard tests pass unchanged. | as stated |
| theme | `test_theme.py` restated per look; `adopt_light_once` cases (saved dark, fresh install, second launch, later dark choice kept); the Booth switch test (A8). | as stated |
| lessons | every `help_map.json` key and every `show:` link resolves and rings a visible widget after `reveal()` (extends the existing lesson tests). | no "That control has moved" |

### Build task order
1. Snapshot for measure 2 (before any chrome change), committed alone.
2. `usage_tracker`: `unpriced` cost type, `price_row_found`, count query, tests (A5).
3. `ui/theme.py`: new palette keys, six themes, helpers, `token`, `_SWAP` ambiguity check,
   `adopt_light_once`, docstring; `ui/style.py` unchanged values; contrast test (A1, A2).
4. Literal sweep plus its guard test (A1).
5. `ui/motion.py` and its tests (A7).
6. `ui/shell/`: rail, top bar with fitter and agent switch, chips with their pure functions,
   popover, drawer (A3, A4, A10).
7. `main.py`: build the shell, re-home every control per S4, delete the header, strip and rails,
   retire `header_fit.py`; move and rewrite the named tests (A3, A9).
8. Reveal hooks and the `QAction` anchor fix; lesson tests (A6).
9. Settings > General: Look, Accent, Show tooltips, Reduce motion, About; O2 note (A2, A9).
10. Shortcuts (S9), accessibility names, Booth switch test (A8); full suite shuffled; native renders
    at 1000 × 600 and 1440 × 900 for the owner (measure 8).

### Open points for the owner (Architect)
Decided 2026-11-25, owner: "Approve as recommended". Each point below is decided as its
*Recommended* text says.

- **AO1. Unknown-price tally (A5).** A new `cost_type` value in the usage table is a state change.
  *Recommended:* approve as described (no schema change, totals unchanged). *Alternative:* the chip
  shows no unknown form until a later spec, which breaks S6 and measure 5.
- **AO2. Dark `TEXT_MUTE` fails AA today.** Measured 3.44:1 (red) to 3.77:1 (blue) against the
  dark surfaces; S8 says dark values do not change, and S8's test covers all six themes.
  *Recommended:* in slice 1 the test asserts dark `TEXT_MUTE` with `xfail(strict=True)` and a TODO
  row, and a later small change lightens it per accent. *Alternative:* lighten dark `TEXT_MUTE` in
  slice 1 (a visible change to the dark looks).
- **AO3. "Show tooltips" across launches.** Today the toggle resets to On at every launch
  (`main.py:428`). In Settings that reads as broken. *Recommended:* remember it (setting
  `show_tooltips`, additive). *Alternative:* keep today's behaviour exactly.

## Relation to other specs
- `side-rails-redesign` (released) and `rails-rebalance` (verify done 2026-11-25, not released)
  arrange the same two rails this spec removes. Not the same change: they sort the rails; this
  replaces the window's chrome. Their accepted behaviours (chat day groups, limit fields that save
  on commit, summary pills, the project more menu) move into the drawer and popovers unchanged.
- `model-updates-visibility` (verify done): its visibility promise is kept by the status chip's
  count (D3).
- `docs/gui_redesign.md`: type scale, spacing scale, dropdown component and decision tables stay;
  the run-bar decision is the one reversed (D10). The doc is updated at Document.
- No in-flight spec is this change (`session_start.py --inflight`, 2026-11-25).

## Out of scope
- Directions A and C, and their gimmicks (command palette, agent dock), unless the owner asks.
- Any change to what an agent does, sends, stores or costs; any new paid call; any new provider.
- Rendering parsed sections as cards (`docs/gui_redesign.md`), which is separate work.
- The mockups' placeholder content (dropdown options, palettes, platforms, Kernel chips, sample
  manuscript text, "€5" as a limit value).
- EU AI Act Art. 50: the redesign does not change how generated content is published or marked;
  the existing disclosure and marking paths stay as they are.
- Sentinel and the other lab apps; Lab Hub's launcher.

## Risks
- **Qt rules (lab `AGENTS.md`):** animations run on the UI thread (`QTimer` or `QPropertyAnimation`),
  never wait on a lock or a fetch there, stop when hidden and in tests; no `QThread.terminate()`;
  `shutdown()` still names every QThread (the redesign should add none). Do not "fix" a hanging Qt
  test by raising a wait.
- **Theme switching and audio threads:** a full run once deadlocked on `QComboBox.setStyle` while
  FFmpeg audio threads ran (2026-10-05, app-context). Switching palettes while Booth plays is that
  path; Architect must keep restyling off the combos' `setStyle` or stop playback first.
- **macOS 27 menus:** any new popover or menu built on `QMenu` must follow the `appkit_guard` rules
  (`docs/conventions/macos-environment.md`).
- **Offscreen is not cocoa:** the test suite runs offscreen, which does not reproduce cocoa font
  metrics or native control sizes. Each slice needs a native render (live launcher) at 1000 × 600
  and 1440 × 900 before the owner sees it; the 1000 px minimum leaves 928 px beside the icon rail,
  less than Quill's three columns in the mockup (about 1,010 px with gaps), so a collapse rule is
  needed (Design).
- **Request guard:** chips and popovers must not become a second place that spends or a place that
  shows €0.00 for an unpriced call. Measure 5 and the existing guard tests cover it.
- **Breadth:** `main.py` is about 7,000 lines and the header and rails are wired into it; tests
  reach `workspace_tabs`, `theme_dots`, `settings_btn`, `header_fitter` and `history_list`
  (six test files for the last). Slices keep these handles or move tests with them; never weaken a
  test to get green.
- **Help lessons:** `docs/learn/help_map.json` points at widgets by name; every moved widget keeps
  its entry or the lesson is updated in the same slice.
- **Testing phase:** building during the owner's test campaign would change the app under test.
  Build starts only when the owner asks, after testing (TODO.md).
- **Scope size:** five slices across ten agents; the estimate is set at Plan, not here.

## Open questions for the owner
None at Define (D1 to D12 decided 2026-11-25). Design will raise the layout questions the
mockups leave open, such as the collapse rule at the 1000 px minimum.
