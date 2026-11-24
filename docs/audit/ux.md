# UX audit: whole app

- Role: ux-designer (read-only on code; this file is the only repo file written).
- Date: 2026-11-22 to 2026-11-24.
- Tree: started on `main` at `ec1cda5`; `main` moved four times during the audit (the agent
  relabel to Vector / Nova / Kernel and the display-name change landed). Every file:line below
  was re-checked at `45f705d`; the three later commits up to `e0035f6` are audit reports and
  change no cited file.
- Playbook: `docs/playbooks/ux-designer.md`, `status: current`, `last-reviewed: 2026-11-11`
  (13 days old, not stale).
- Out of scope by instruction: the app's own name.
- The Foundry activity log was not written (`log_activity.py` writes a second repo file).

## How this was audited

From the code and from rendered screens. A throwaway pytest file kept outside the repo built the
real `main.GodAI` window under `QT_QPA_PLATFORM=offscreen` with `-p tests.conftest` (temp DB,
blanked credentials, no ratings network, stubbed local discovery, temp settings file) plus a temp
data folder. It grabbed all ten agent screens at 1400x900 and 1000x600, every inner tab, Settings
(all tabs), Cost History, Run Log and the Model Guide; dumped every visible string; walked the
focus chain; and measured focus visibility, accessible names, target sizes and three behaviours
(unfiled draft, Clear, the guard's refusal). No request was sent, `data/imprint.db` was not
touched, `git status` stayed clean of my changes. Contrast ratios are WCAG relative-luminance
figures computed from the tokens in `ui/theme.py`.

"Measured" below means one of those runs produced the number. "From code" means read, not run.

## Verdict

Not yet at a professional level, and not ready to be handed to a user who is not the owner. The
shell is in good shape: the aligned form is applied consistently across all ten panels, the look
is calm, tab order is logical on every screen, spending is guarded with honest wording, and
Herald and Reel handle their awkward states (uncertain post outcome, stop that cannot cancel)
better than most shipped apps. What blocks the answer "yes" is concentrated in three places.
First, the main flow loses work: a Quill draft written before a Project exists is never saved
and quitting discards it without a word, and one click on Clear erases the whole manuscript with
no confirmation and no undo. Second, the first-run path dead-ends: the first cloud request from
any agent is refused with a pointer to a panel that does not exist, because the permission chips
live on a different screen and reset at every launch. Third, parts of the surface still describe
another product or promise more than the code does: Press shows a dead Period control, a
developer backlog as the user's todo list and "connected" for a key nobody has tested; the Model
Guide documents OSINT and Manager agents; Booth reports a deliberate Stop as a failed conversion.
Accessibility is below the playbook's bar on three measured counts: buttons, chips and tabs show
no keyboard focus, 94 of 95 inputs have no accessible name, and the colour that carries every
field label and every cost line is under 4.5:1. Two P0 and nine P1 findings; none needs a
redesign, most are a few lines each.

## What holds up

- Aligned form: every panel uses `field()` labels above inputs on the shared grid; no stray
  group-box forms were found on the ten agent screens (rendered).
- Tab order: 0 backward jumps on 8 of 10 screens, 1 on Press and Nova (measured).
- Money wording: "Up to €0.44; you pay for what it writes", "under €0.01", "no price on file for
  this narrator", "0 means unknown, not free" (`services/money_text.py`,
  `agents/audiobook/panel.py:637`, `:692-699`). "free" appears only for local models and
  on-device routes (`main.py:676`, `main.py:1835`).
- Honest limits: Herald "Nothing is sent until you press Post", Reel "Stopped watching. The …
  render continues at the provider" (`agents/video/panel.py:1196`), Booth resume wording.
- Empty states exist and say what to do on Booth, Press royalties, Reel log, Cost History, Run Log.

## Findings

Priority: P0 loses work or money, or blocks the main flow. P1 misleads, dead-ends or fails the
accessibility bar on a main flow. P2 friction or inconsistency. P3 polish.

### P0

**UX-01. A Quill draft written without a Project is never saved; quitting discards it silently.**
[error prevention, data loss]
`agents/author/panel.py:881-887` (`_schedule_project_save` and `_persist_project_state` return
when there is no project), `:141` (`_unfiled_state` is memory only), `main.py:6483` (the close
handler calls the same no-op), `main.py:3155` (the first-run banner).
Experience: a first launch opens Quill with "No project context". The banner says to fill in
Title, Author and Type and press Save Profile; nothing mentions a Project. The author writes or
generates a chapter, quits, and reopens to an empty Draft. Save Profile reports "[Saved] Book
profile." (`:967-976`), which reads as if the book were saved. Measured: draft set with no
project, close-handler save called, second window on the same database shows an empty Draft.
Smallest fix: persist the unfiled state the way the project state is persisted (one settings key,
same 700 ms timer), restore it in `activate_project(None)`. Until then, at minimum ask before
quit when the unfiled Draft is not empty.

**UX-02. "Clear" erases the whole manuscript with no confirmation and no undo.**
[error prevention, user control]
`agents/author/panel.py:449-451` (button), `:1403-1417` (`clear`, `_clear_displays`).
Experience: Clear sits in the document bar beside Save Draft and Export Book. One click empties
Draft, Outline, Characters, World Notes, Sources, Direction and Title. `QTextEdit.clear()` drops
the undo history, so Cmd-Z does nothing; with a Project active the empty state is autosaved
0.7 s later (`:719-731`, `:881`), so the stored copy goes too. Measured: no dialog shown, Draft
empty, `isUndoAvailable()` false, undo restores nothing.
Smallest fix: a confirmation naming what goes ("Clear the Draft and all notes for <title>? This
cannot be undone.") with Cancel as the default; better, clear with one undoable edit block and
leave Title alone.

### P1

**UX-03. Booth reports a deliberate Stop as a failed conversion.** [state honesty, error wording]
`agents/audiobook/panel.py:1133-1142` (Stop kills the process and writes "[Stopped]"),
`:937-945` (the finish handler then sees a crash exit, overwrites the status with
"[Error] Conversion failed." and opens "Audiobook Conversion Failed"), `:842-856`
(`errorOccurred(Crashed)` can add "The converter process crashed." as a second critical dialog).
Nothing records that the user asked for the stop. From code; not run, since it needs a paid
conversion.
Experience: the user presses Stop and is told twice that something broke, with no mention that
finished chapters are cached and will not be paid for again.
Smallest fix: set a `_stop_requested` flag in `stop_conversion`; in `handle_finished` and
`handle_error` branch on it first: status "Stopped. Chapters already made are kept; press Convert
audiobook to resume.", no dialog.

**UX-04. The first cloud request from any agent is refused with a pointer to a panel that does
not exist.** [first run, recovery from errors]
`services/validator.py:127` ("Enable it in the API Permissions panel."), `main.py:2690-2722`
(the chips exist only inside the Kernel screen of the Assistant workspace, unchecked at every
launch; nothing restores them), `main.py:4547` (shown as "Request Blocked"),
`agents/video/panel.py:510`, `:621`, `:678` and `agents/creator/panel.py:1113`, `:1242`
("the API permissions row").
Experience: Quill preselects anthropic. The user adds a key in Settings, presses Write and reads
"API access for 'anthropic' is not enabled. Enable it in the API Permissions panel." No screen
has that name; the control is "Cloud text models" on another workspace tab, and it must be
re-ticked after every relaunch. Measured: zero chips checked at launch; exact text above.
Already on the backlog as `TODO.md:90` at P3; ranked P1 here because it stops the main flow on
day one.
Smallest fix: reword to "Anthropic is not allowed yet. Open Assistant and tick Anthropic under
Cloud text models." and add an "Allow Anthropic and send" button to the refusal. Deciding whether
the ticks persist across launches is an owner decision (it is a consent control).

**UX-05. Press: the Period selector does nothing, and Refresh Data freezes the window and prints
raw JSON.** [control that lies, system status]
`agents/manuscript/panel.py:128-130` (the box is built and never read anywhere in the repo),
`:728-743` (`get_last_30_days()` whatever is selected; the network call runs on the GUI thread, so
"[Fetching…]" never paints; the result is `json.dumps(data, indent=2)`; a failure shows the raw
exception).
Experience: choosing "Last 7 days" or "All time" changes nothing; Refresh hangs the app for the
length of the request and fills "publishing metrics" with a JSON dump.
Smallest fix: remove the Period field until it is wired (or pass it to the client); move the
fetch to a worker; render a short summary with the JSON behind a disclosure.

**UX-06. Press shows a developer backlog and the owner's own niche as every user's "Publishing
todos".** [match to the real world, leftover content]
`agents/manuscript/kdp_csv_parser.py:25` (`INITIAL_TODOS`, seeded on first open of Press),
`:59-81` (eight "(Dev) …" engineering items: "Structured Book/Chapter data model", "Multi-book
support", …), `:49` ("dating/astrology-niche creators"), `:36` and `:55-58` ("paste into .env …
then restart", "the 🔌 Connections panel"), `:39` ("the Manuscript agent's Market mode").
Measured: 24 rows in the list on a fresh database, shown as "[kdp] Upload to Amazon KDP" etc.
Smallest fix: drop the "(Dev)" rows and the niche sentence from the seed; point key setup to
Settings → API keys; use the catalog names.

**UX-07. Press says "connected" for a key that has only been typed in.** [promise beyond the code]
`agents/manuscript/panel.py:658-674`: "PublishDrive — connected" is `bool(os.environ[...])`, in
the accent colour. `app-context.md` records the PublishDrive endpoint as untested against a live
account; the same check labels ElevenLabs, Anthropic, OpenAI, DeepSeek and Gemini.
Smallest fix: "key saved, not tested"; say "connected" only after a successful fetch (the sync
state at `:699-726` already knows).

**UX-08. The Model Guide documents another product.** [help and documentation]
`ui/dialogs.py:1231` (window title "Model & Agent Control Panel"), `:1240` (search hint "…
coding, osint, cost, routing"), `:1304-1326` (Agents tab: Chat, Writing, Coding, OSINT, Audiobook
and Manager agents; "OpenAI TTS only" at `:1322`; "The Manager Agent writes the code and DB entry
automatically"), `:1352` ("OSINT / analysis"). Rendered: none of Quill, Press, Booth, Label,
Reel, Herald, Sitebuilder, Vector or Nova appears. The guide is one click from the Model field
on Kernel.
Smallest fix: build the Agents tab from `agents/catalog.py` (label and description), title the
window "Model Guide", delete the OSINT and Manager text.

**UX-09. Keyboard focus is invisible on every button, chip and tab, and no main action has a
keyboard path.** [accessibility, WCAG 2.4.7 and 2.4.11]
`ui/style.py:295-317` (QPushButton rules, no `:focus`), `:588-602` (workspace tabs, none),
`ui/style.py:653-695` (chips, none). Only inputs and combos have a focus rule (`:183`, `:225`).
Measured: focusing Send, Auto Route, Estimate Cost, Settings, New Chat, a permission chip, the
Model Guide link, the refresh icon and the workspace tab bar changes 0 pixels; a combo changes
664, a text field all of its area. The only shortcut in the main window is F1
(`main.py:413`); there is no menu bar, no Cmd-Return for Send or Write, no Cmd-, for Settings.
On a Mac with default keyboard settings Tab skips buttons altogether, so Write, Stop and
Convert audiobook are mouse-only.
Smallest fix: one sheet rule, `QPushButton:focus, QCheckBox:focus, QTabBar::tab:focus,
QToolButton:focus { border: 1px solid ACCENT }` at full strength; add Cmd-Return to each panel's
primary action, Cmd-. to its Stop, Cmd-, to Settings.

**UX-10. 94 of 95 inputs on the ten agent screens have no accessible name.** [accessibility,
playbook rule on accessible names]
`ui/forms.py:65-109`: `field()` puts a label above the widget and links nothing; no `setBuddy`
exists in the repo. Measured per screen (unnamed / inputs): Quill 14/14, Press 8/8, Booth 7/8,
Label 9/9, Reel 4/4, Herald 14/14, Sitebuilder 8/8, Vector 13/13, Nova 11/11, Kernel 6/6; rails
7/7. VoiceOver would announce "text field", "pop-up button" with no name.
Smallest fix: in `field()`, `if not widget.accessibleName(): widget.setAccessibleName(label)`,
recursing one level for wrapped rows (Model plus its refresh button). One edit covers almost
every screen.

**UX-11. The colour that carries every field label and every cost line fails 4.5:1, and no test
guards contrast.** [accessibility, WCAG 1.4.3; playbook rule on a contrast test]
`ui/style.py:49` and `ui/theme.py:63`, `:83`, `:109` (`TEXT_MUTE`); used by `ui/forms.py:468-473`
(field labels, 10 px bold), `ui/style.py:543` (estimate lines such as "34 scenes · budget
reserve ≈ €2.12" and "Estimated cost: not calculated", 11 px), `:494` (page subtitle), `:733`
(field notes), `:588-590` (unselected workspace tabs). Computed: green 4.16 on the page, 3.85 on
cards, 3.58 on raised surfaces; red 3.99 / 3.70 / 3.44; blue 4.73 / 4.18 / 3.77. Placeholders
measure 4.15 from the render. `tests/` has no contrast test.
Smallest fix: lift `TEXT_MUTE` to about `#8791a0` (5.9:1 on the page) in the green set and the
matching step in the other two, keep the present value for disabled text only, and add the
token-pair test the playbook names.

### P2

**UX-12. Tooltips: 72 of the 160 names in `ui/tooltips.py` point at controls that no longer
exist, and live ones are out of date.** [help, consistency]
Dead blocks: `ui/tooltips.py:44-60` (agent buttons: osint, wifi, bug_bounty, nfl_bet, health,
manager), `:104-138`, `:168-178`, `:192-228`, `:244-255`, `:146` ("Maestro"). Stale and live:
`:234` and `:237` ("via OpenAI TTS", "OpenAI TTS voice" with three narrators and M4B on offer),
`:93-98` ("Set OPENAI_API_KEY in .env or ~/.zshrc" although Settings → API keys exists), `:27`
("Gemini (free tier available)", a price claim the app cannot check). Coverage is thin where it
matters: Render Video, Write Posts, Ask, Refresh Data, Ingest KDP CSV, Export Book and both
Booth folder buttons have none (rendered dump). Fix: delete the dead blocks, correct the four
lines, add one tooltip per primary action.

**UX-13. "Realtime Monitor" is a button that can never be pressed.** [dead control]
`main.py:3444-3446` (created disabled, no handler), `ui/tooltips.py:76` ("(Coming soon) …").
Fix: remove the button and the tooltip line.

**UX-14. The paid-request confirmation reads like a debug prompt.** [plain language]
`main.py:4400` (title "Confirm External API Request"), `:4391` (Yes / No / Apply), `:4385-4386`
(raw provider and model ids), `:4372-4373` (per-unit work shows "Approx tokens: 0" and
"Estimated cost/quota impact: ~€2.12"). Measured text in the method run. Also `main.py:605`: a
text model with no price row and a blanked provider default still shows "Up to €0.00" (known,
`TODO.md:144`, B-F5). Fix: title "Send this paid request?"; buttons "Send" / "Cancel" /
"Switch to <model>"; drop the tokens line when `flat`; "About €2.12" instead of "cost/quota
impact"; for an unknown price say "price unknown" and refuse, as Booth does.

**UX-15. Errors are raw exception text behind log-style prefixes, and the vocabulary differs per
panel.** [error wording, consistency]
`f"[Error] {error}"` at `agents/author/panel.py:1320`, `:1401`, `:1646`, `:1767`;
`agents/manuscript/panel.py:742`, `:751`, `:871`; `agents/social/panel.py:499`, `:756`;
`agents/video/panel.py:898`, `:961`; `agents/creator/panel.py:713`. `agents/music/panel.py:270`
replaces the Artist Profile text with the error. States are spelled "[Stopped]", "Stopped.",
"Idle", "[Done]", "Saved", "[Library] …" (`agents/audiobook/panel.py:1365`), "[Error] Please
select a book first." (`:646`) for a missing selection. Fix: one helper that maps the common
failures (no key, refused, timeout, offline) to a sentence plus a next step, keeps the raw text in
the tooltip, and one set of state words without brackets.

**UX-16. Herald: Stop leaves "Writing for YouTube…" on screen; deleting a post asks nothing.**
`agents/social/panel.py:507-514` with `:473` and `:502-505` (no status after Stop);
`:976-982` (`delete_post` removes the row at once, while deleting a campaign confirms at `:403`).
Fix: set "Stopped. Nothing was saved." in `stop`; confirm the delete, or refuse it for posted rows.

**UX-17. Booth's messages name a button that is not on the screen and give a stale instruction.**
"click Start" at `agents/audiobook/panel.py:292`, `:917`, `:921`, `:927`, `:933`, `:954`, `:1114`
(the button reads "Convert audiobook"); `:676` "Add your key in Settings, then restart" while
Settings says keys apply at once. At 1400x900 the primary button is below the fold under the
settings block (rendered). Fix: one wording, drop "restart", move the action row above
Conversion settings or pin it.

**UX-18. Messages point to places under old names.** [naming consistency]
"the Write sidebar": `agents/author/panel.py:1569`, `:1691`, `main.py:3180`. "the Video tab":
`agents/social/panel.py:636`, `agents/social/publishing.py:267`. "the Creator workspace",
"Manuscript shorts": `main.py:2714`, `:2718`. "Imprint's private .env file":
`agents/video/panel.py:505`, `:616`, `:673`. Old agent names survive only in comments and in the
dead tooltip line above, not on screen. Fix: use catalog labels ("Reel", "Nova", "Press") and
"Settings → API keys".

**UX-19. Navigation is four levels deep and two of them rename the same thing.** [hierarchy]
`main.py:2419-2437` (workspace tabs), `:2587-2602` (tool switch), panel mode switch, inner tabs.
In Author the eye passes "Author" → "Quill | Press" → title "Quill" → "Write | Publish & Market"
→ "Draft | Outline | …" before reaching content, and "Publish & Market" inside Quill overlaps
Press. The Assistant tab opens a page titled "Kernel". Providers appear as raw ids
("anthropic", `main.py:2659`) on some screens and as names ("OpenAI") on Reel. Fix: drop the
page title where the tool switch already shows it; show provider labels from `PROVIDER_LABELS`
everywhere; decide where publishing copy lives.

**UX-20. At the minimum window size the left rail and Quill grow horizontal scrollbars.**
`main.py:256` (1000x600). Rendered: a horizontal scrollbar under the left rail and under Quill's
project bar, with the third column cut ("Third Pers"). Fix: turn the horizontal bar off on the
left rail as the right rail already does (`main.py:3341`), and let the Quill grid fold at that
width.

**UX-21. Targets under 24 px, and text that cannot be scaled.** [WCAG 2.5.8, 1.4.4]
Measured: "Model Guide" 71x12 and "Get Muse Glimmer" 104x12 (`ui/forms.py:112-122`,
`ui/style.py:703`), "Check when … starts" 174x17 (`ui/status_cards.py:499`). All sizes are fixed
pixels (`ui/style.py:98`, `ui/forms.py:470`: 10, 11, 12, 13 px) with no setting. Fix: minimum
height 24 on link buttons and that checkbox; a text-size setting that scales the sheet's sizes.

**UX-22. Focus rings and control edges are below 3:1.** [WCAG 1.4.11]
`ui/style.py:60` and `:183-185`, `:225` (ring at 35 % accent): 2.11:1 against the page in green,
1.55:1 in red, 2.19:1 in blue. `ui/style.py:52` (field border): 1.2:1. Fix: full-strength accent
for focus; `BORDER_STRONG` for field edges.

**UX-23. Example text in fields looks like filled-in values.** [recognition]
`agents/social/panel.py:89-92` ("The Salt Road", "launch week sales", "literary fiction
readers") render in the typed-text colour at half strength. Fix: phrase as hints ("Book or
product name") or prefix "e.g.".

**UX-24. Press: Ask cannot be stopped; "Ingest KDP CSV" opens nothing.**
`agents/manuscript/panel.py:821-852` (paid request, button disabled, no Stop);
`:138` and `:745-761` (reads `data/kdp_reports/`, which the screen never names; "[Info] No new
KDP reports found."). Fix: add Stop; make the button a file picker or name the folder.

### P3

- **UX-25.** Kernel's Command list offers "OSINT Brief", "Explain Code", "Debug Python"
  (`config/commands.json:7`).
- **UX-26.** Right rail: "SAVED LOCAL" and "ADVICE SPENT" need the tooltip to be understood
  (`main.py:3362-3363`); "LAST REQUEST €0.00" before any request (`main.py:5861`, the initial
  "—" is overwritten).
- **UX-27.** Hard-coded colours outside the theme: `agents/manuscript/panel.py:476`, `:537`,
  `:653` (#666 and #777, 3.97:1 on a card), `main.py:6394`, `:6403`.
- **UX-28.** Settings → Tools: five checkboxes with no accessible name (`ui/dialogs.py:751`
  area), while the Agents table names its own.
- **UX-29.** The header pill only ever reads "Ready" (`main.py:2454`); a running or failed
  request does not change it. Remove it or drive it.
- **UX-30.** Theme labels "Green (Matrix)" and "Blue (Cyberpunk)" (`ui/theme.py:47-49`) carry the
  sibling app's character into a calm tool; plain "Green", "Blue" would match.
- **UX-31.** Saved-chat controls (New Chat, Remove Chat, agent filter) stay in the left rail on
  screens that have no chat (`main.py:2529-2574`).

## The brief's questions, answered

| Question | Answer |
|---|---|
| Does the UI show "free" or €0 for an unknown price? | Not for per-unit work: Booth, Vector and Press refuse with "No Price Configured". For text, only in the narrowed B-F5 case (UX-14, `main.py:605`). "free" is used for local and on-device routes only. |
| Booth Stop shows "[Error] Conversion failed."? | Yes, plus one or two error dialogs (UX-03). |
| Disabled or "coming soon" controls? | One: Realtime Monitor (UX-13). Other disabled buttons enable with state. |
| "connected" for an unverified key? | Yes, six providers including PublishDrive (UX-07). |
| Old names on screen? | Maestro, Narrator, Site Builder and Atelier are not on screen. The Model Guide's agent list, 72 dead tooltips and several location names are stale (UX-08, UX-12, UX-18). |
| Aligned form and calm? | Yes on all ten panels. No gimmick beyond the theme dots and underscore caret the owner chose. |
| First run? | No guided start. The banner sends the user to Save Profile, not to a Project (UX-01), and the first paid request is refused (UX-04). |

## Could not verify

- **Native rendering.** Everything was rendered offscreen (Fusion), not under cocoa. Checkbox
  clipping, the native focus ring and exact font metrics may differ; UX-09's zero-pixel result
  should be re-checked once on a real window.
- **VoiceOver.** The five-minute pass per screen the playbook asks for was not done (no
  interactive session). UX-10 is from `accessibleName()` values, not from listening.
- **Running, error and success states of paid flows.** No request was sent, so Quill, Press Ask,
  Booth, Reel and Herald in flight, on provider error and on success were read from code, not
  seen. UX-03 in particular is from code.
- **Booth with books, Listen tab with audio, Reel Library with videos, Herald with a campaign and
  posted rows.** Only empty states were rendered.
- **Learning Centre and Docs.** Opened from code only; their content and the F1 targets were not
  walked.
- **Project Manager, Project Overview, release-kit window, tray menu, Local-models measuring.**
  Not rendered.
- **Red and blue themes on screen.** Contrast is computed for all three; only green was rendered.
- **Text scaling under macOS "larger text" and HiDPI.** Not run.
