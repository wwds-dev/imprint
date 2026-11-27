# GUI redesign — direction

The colours are right. What is wrong is **hierarchy, density, and the fact that
structure is computed and then thrown away.** Three measurements say it better
than opinion does.

## Diagnosis

**1. There is no type scale.** `ui/style.py` uses `10px · 11px · 12px · 13px ·
22px`. Four of those five are visually identical at normal viewing distance, so
nothing on screen reads as more important than anything else. Every label,
value, heading and hint arrives with the same weight.

**2. Structure is parsed, then discarded.** There are **12 `_parse_*_sections`
methods** that turn each agent's response into labelled sections — and **70
`QTextEdit`/`QTextBrowser` panes** that render the result as flat text. The app
already knows the answer has parts; it just doesn't show them as parts.

**3. The input is buried behind a form.** The chat panel stacks three control
rows (Tool/Command · Provider/Model/Refresh/Guide/Docs · Mode + five provider
checkboxes) before you reach the box you type in. That is a settings dialog
wearing the costume of a workspace.

**4. The right rail states numbers as sentences.** "Used: 11.3 GB · Free: 9.4 GB",
"Session Cost: €0.00". Six cards of small grey text, no figure anywhere, so
nothing can be read at a glance — which is the only thing a status rail is for.

## Direction

### A real type scale

| role | size | weight |
|---|---:|---:|
| display (agent title) | 22px | 500 |
| title (card + section headings) | 14px | 600 |
| body / control | 13px | 400 |
| caption (units, hints, metadata) | 11px | 400 |
| field label | 10px | 700 |

Only field labels use tracked uppercase. Section headings use normal title case
and a larger semibold face; using the same tiny uppercase style for both made
headings such as “Conversion settings” look like misplaced form labels.

### One run bar instead of three rows

> **Decided 2026-10-08: the aligned form, not the run bar.** Two mockups were
> drawn — this run bar (routing in the composer's footer, permissions behind a
> popover) and an aligned form that keeps every control visible on one grid.
> The aligned form was chosen and applied app-wide: one label idiom
> (`forms.field`, label above), equal-column grids (`FieldGridLayout`, with
> `add_field(span=…, new_row=…)` for rows that mean something), toggle chips
> for permissions (`forms.toggle_chip`), field-level utilities in the label row
> (`forms.link_button`) or as an icon beside the control (`forms.icon_button`),
> and FlowLayout rows that sit buttons on the controls' line. The section below
> is kept as the alternative that was considered.
>
> **Reversed for the ask bar only, 2026-11-25** (spec `manuscript-redesign`,
> decision D10, approved by the owner). The Manuscript redesign's single ask bar
> with a model chip is this run bar: the chip shows provider and model with BEST
> FIT, and its popover holds provider, model, refresh, Tool, the provider
> permission chips and Auto-Apply. Forms inside stages keep the aligned form. The
> ask bar arrives in slice 2; until then the composer is the aligned form
> described above. Nothing in slice 1 touches it, except one caption line (see
> "The shell" below).

Collapse the three control rows into a single bar: **agent chip · provider ·
model · live cost · Run**. Everything else — execution mode, the five provider
checkboxes, auto-apply — moves behind one settings affordance on that bar.

Those toggles are set once a week; they currently occupy the most valuable
real estate on the screen, permanently. The cost readout belongs here because
it is the one number that changes with every keystroke and should be visible at
the moment you decide to spend it.

### Render the sections that already exist

This is the highest-value change and it needs no new parsing. Feed the output of
each `_parse_*_sections` into a card list: a heading per section, metrics as
figures, and the raw response collapsed behind a disclosure at the bottom.

The parsers already exist for osint, osint_heavy, health, nfl_bet, roi, author,
music, inv and more. The work is a renderer, not an analysis.

### Figures, not sentences, in the right rail

> **Update (slice 1, 2026-11-25):** the right rail no longer exists. These
> figures now live in the spend popover and the status popover (see "The shell"
> below); the principle (bars with the number beside them, no prose around
> them) is unchanged.

Memory, swap and budget are all "x of y" — draw them as bars. A budget that is
84% spent should be visible without reading. Keep the numeric value next to the
bar; drop the prose around it.

### The shell (Manuscript redesign, slice 1)

Slice 1 of the Manuscript redesign (`docs/specs/manuscript-redesign.md`, ADR
0006) replaced the window's chrome. The header row, the workspace description
strip and both side rails are gone. What stands in their place:

| Piece | What it is |
|---|---|
| Icon rail | 72 px wide, full height. App mark (its tooltip is the version; an amber dot means a stale build), one icon per workspace, **?** (agent Docs, Learning Centre, Keyboard shortcuts) and the Settings gear. |
| Top bar | 56 px tall, over the content. Agent switch (or the agent's name), project selector with its **Project actions** menu, History (a drawer: search, agent filter, saved chats, New Chat), spend chip, status chip. |
| Spend chip and popover | Today against the daily limit; the popover holds Session and Today with their limit fields, the project line, the figures, Reset session spend, Cost History and Run Log. A request with no price reads "unknown", never €0.00. |
| Status chip and popover | The worst of: machine stressed, key check failed, machine busy, working, ready, with a count of waiting model updates. The popover holds System, Chat routing, API keys and Model updates. |

The chips shorten as the window narrows (spend chip drops "today", then shows
the amount only; status chip shows the dot and count) and nothing goes into an
overflow menu. The look is Light by default, with Dark as the alternative, each
in three accents, chosen in Settings → General → Appearance. The rail and top
bar use the same type scale and spacing scale below; chips and the project
selector are 13 px, the agent name and the drawer heading 14 px at weight 600.

Motion: the History drawer slides open for 160 ms and nothing else moves. Under
Reduce Motion (macOS's setting, or the in-app switch) it appears at once. This
is the one exception to "Animation" in the list at the end of this page.

The one change inside the centre panel: the live cost estimate ("Next request:
…") is a caption line under the composer's request setup.

### One spacing scale

`setContentsMargins` appears 75 times with ad-hoc values. Pick 4 / 8 / 16 / 24
and use nothing else. Most of the "not quite right" feeling in a dense UI is
inconsistent gaps rather than wrong colours.

### Dropdown component

Imprint uses one custom dropdown system rather than the macOS native combo
menu. The native path ignores Qt row styling and reduces every selector to a
plain checkmarked text list.

| State | Visual treatment |
|---|---|
| Default | Recessed field, quiet chevron, full-width popup |
| Hover | Raised row surface without changing the text colour |
| Selected | Emerald wash, leading rail and circular check |
| Recommended | Emerald text with a compact `BEST FIT` badge |
| Disabled | Muted text; selection remains readable |

Popup rows are 42 px high, show at most nine items before scrolling, and keep
standard keyboard behavior: arrows move, Return chooses and Escape closes.
`ui.widgets.install_dropdown_system()` also catches selectors created later by
dialogs, so the component does not depend on individual panels remembering to
opt in. Popup width follows the visible field, may expand for a longer option,
and is capped at 480 logical pixels; Qt's pre-layout 640px placeholder is never
used as a design measurement.

BEST FIT is semantic data rather than a text-colour convention. Dedicated item
roles carry its explanation, score and confidence; this prevents a grey
oversized local model from being mistaken for a recommendation. Provider menus
show the best eligible provider overall, while model menus show the best option
inside the currently selected provider. See `docs/recommendation_system.md`.

### Decision tables and explanation cards

Wide analytical tables show only the fields needed to compare rows. Evidence,
freshness, proposed actions and caveats move into a selected-row detail card or
tooltip. Decision-oriented tabs begin with a short “how to use this” card and
end in a concrete action or stop/continue rule.

## Order of work

1. Type scale + spacing scale in `ui/style.py` — one file, immediately visible,
   trivially revertible.
2. Right-rail figures — small, self-contained, high perceived payoff. (Done, then
   moved into the spend and status popovers by the shell, slice 1.)
3. Run bar — restructures the chat panel only.
4. Section renderer — build it for one agent (osint has the smallest vertical at
   227 lines), then reuse for the other 11.

Steps 1–2 are safe now. Steps 3–4 touch panel structure, so they are cheaper
after the refactor's phase 4, when each panel is its own module.

## Deliberately not proposed

- **A new colour palette.** The greens and greys work; changing them would spend
  goodwill on the one thing that is not broken.
- **A command palette.** Tempting, but the sidebar is not the bottleneck — the
  control rows are. Revisit once the run bar exists.
- **Animation.** Nothing here is slow enough to need it. (Slice 1's History
  drawer slide is the single, user-triggered exception; it respects Reduce
  Motion.)
