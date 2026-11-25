# Spec: Manuscript redesign (new look, direction B)

Needs: design, architect, build, review, verify, docs

Status: **Define approved by the owner 2026-11-25 ("do as recommended"): D1 to D12 are decided
as recommended, alternatives not taken.** No Design, Architect or Build has started; they start
only when the owner asks, after testing. Priority: P3 (TODO.md: testing comes first; no redesign row
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
