# Spec: Side rails redesign (project rail B, spend rail A)

Needs: build, review, verify, docs

Status: Define and Design approved by the owner 2026-11-24 ("fit the dropdown text into the
textfield box. center the icons inside dropdown menus, then go ahead and implement Left B and
Right A"), after four mockups shown in chat. Priority: P2. Type: user-visible layout change, no
new capability. Owner session: `claude/side-rails`. Phases skipped: Case (tier `public`),
Architect (no state, concurrency or boundary change), Secure (no network, secrets, auth,
untrusted input, file writes or packaging logic; three static SVGs are added to the bundle list).

## Problem
The two rails grew by accretion (`main.py` `build_left_panel`, `build_right_panel`):
- Left: eleven saved chats read "audiobook: novel.epub" with no date; the list scrolls sideways;
  New Chat, the most used action, is a quiet link at the bottom; Remove Chat is a permanent button.
- Right: six equal-weight numbers, two budget bars and then the same two limits again as fields
  with their own Save button; collapsed sections say nothing until opened.

## Goal and success measure
Same functions, fewer controls, nothing clipped. Measured by offscreen tests and a native render:
1. Every rail control ends inside its rail at every tested window size (existing test, both rails).
2. No dropdown or field in either rail shows a cut-off value at rest (`ui.text_fit.clipped_text`
   is empty); icon-only buttons draw their icon centred (no menu-indicator offset).
3. Saved chats are grouped Today / Yesterday / Earlier, newest first, title elided, agent beside
   it; the list never shows a horizontal scrollbar; `history_list.count()` is still the chat count.
4. A limit typed into a budget row and committed (Enter or leaving the field) is validated and
   saved exactly as Save Limits did; an invalid value is refused, reported and put back; an
   unchanged value saves nothing and shows nothing.
5. A limit with decimals (1.5) is shown as typed, not truncated to 1.
6. Collapsed System, Chat routing, API keys and Model updates show a one-word state.
7. Full suite green.

## Behaviour
**Left rail (B).** Project dropdown with a "more" button beside it (New Project, Project Overview,
Save Current Setup; the last two disabled without a project). The "Working in …" line shows only
while a project is active. Search field with a filter button beside it (agents that have chats;
the button is marked while a filter is on). Chats grouped by day. Right-click keeps Rename and
Assign to project and gains Remove Chat; Delete on a selected chat does the same. New Chat is a
full-width button under the list.

**Right rail (A).** Spend: Session and Today rows, each "€used of € [limit]" over its bar; the
limit is the field. Reset session spend is a link in the heading row. Requests, Last request,
Saved by local and Advice spent are one plain list. Activity rows carry a chevron. Status
sections show a summary pill: System OK / Busy / Stressed (worst of memory, processor, swap),
Chat routing the last provider, API keys "n of 6", Model updates its count.

## Out of scope
Left-hand icons on Activity rows (the app has no icon set for them); chat rows with a hover
remove button; any change to what is stored.

## Design notes
- Icon buttons open their menu on click instead of `setMenu`, so Qt draws no menu indicator and
  the icon stays centred.
- The agent filter keeps the combo's `currentText` / `setCurrentText` / `currentTextChanged`
  surface, so `load_history_list` and its tests are unchanged.
- Day headings are painted by the row delegate above the first row of a day (the dropdown
  delegate's section pattern), not inserted as list items.
- The refusal text in `services/validator.py` that sent the user to "press Save Limits" changes
  with the control.

## Review (2026-11-24, `code-reviewer`, read-only, on the uncommitted diff)
All six findings fixed in the same change:
- P1 `docs/learn/help_map.json` still mapped `delete_chat_btn` and `save_budget_btn`: the budget
  entries now point at the two limit fields; the chat one is dropped (`history_list` has the lesson).
- P2 `format_limit` rounded to six significant digits, and committing one field saves both, so
  1234.567 would have become 1234.57: now lossless.
- P2 a long summary pill covered the end of its title in the 204px header: the pill is fitted
  ("1 new · 1 warning" becomes "1 new +1", whole on hover).
- P3 "1 warning" wore the accent tone: warning tone now. P3 README still named Save Limits.
- P3 a click on a day heading opened the chat under it: `ChatList` swallows it.
Not verified by the reviewer or by tests: the real modal warning box on a refused limit (stubbed
in tests); the re-entrancy guard is covered by code reading only.

## Verify (2026-11-24)
- `tests/test_side_rails.py`: 28 tests, three shuffled runs green.
- Mutation check, seven planted faults (unchanged-limit guard, restore on refusal, day grouping,
  heading click, pill fit, system summary repeat, dropdown minimum width): all seven caught.
- Native render (cocoa, not shown on screen) of both rails at 1500x950: no control past the rail
  edge, no cut-off dropdown or field text, icons centred.
- Full suite: see the commit that follows this one in `git log` for the run on the final tree.
