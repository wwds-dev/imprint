# Spec: Rails rebalance (what each side rail carries)

Needs: design, build, review, verify, docs

Status: **Owner approved option B 2026-11-24 ("B (recommended)"); built same day, review and
verify pending.** Model updates start collapsed (open question 2 answered by the pick); Chat
routing stays right. Priority: P2. Type: user-visible layout change, no new capability, no change to
what is stored. Follow-up to `side-rails-redesign.md` (merged, 46c65fa); it keeps that spec's
accepted parts: project rail B (project dropdown with "more" button, search with filter, chats by
day, full-width New Chat), spend rail A (Session and Today rows with the limit as the field,
Reset session spend link), and the summary pill on a collapsed section.

## Problem
Owner feedback after first real use: the right rail is overloaded, the left rail is nearly empty.
Counting what `build_right_panel` and `build_left_panel` (`main.py`) put on screen at rest:

| Rail | Rows at rest | What |
|---|---|---|
| Left | 4 fixed + the chat list | Project + more, Search + filter, New Chat; the list takes all spare height |
| Right | about 24 | Spend heading, Session, Today (+ Project when active), 4 figures, estimate line, Activity heading + 3 links, Status heading + 4 sections (Model updates open by default, about 6 more rows) |

Right needs scrolling at the 600px minimum window; left never does. Everything the right rail
shows is about cost or machine state, so the left rail holds no secondary information at all.

## Principle for sorting
- **Left rail = what you work on and where you go:** projects, chats, and the places that open a
  window (navigation).
- **Right rail = what the work costs and how the machine is doing:** spend, limits, system and
  provider state.
- An item about the *current project* sits with the project (left); an item about the *session or
  provider* sits right. A link that opens a window is navigation (left), not status.
- The chat list stays the hero: it must still show at least 8 rows at 950px window height and keep
  a usable minimum (about 5 rows) at 600px; the left rail scrolls below that, as the right does.

## Per-item placement
Current rail in brackets. "Recommended" = Option B below.

| Item | Now | Recommended | Why |
|---|---|---|---|
| Project dropdown, more, Working in, Search, filter, chats, New Chat | L | L | accepted (rail B) |
| Project budget meter (shown only with a project) | R | **L**, under "Working in" | it measures the project; appears with it |
| Spend: Session, Today, Reset link | R | R | accepted (rail A) |
| Requests, Last request, Saved by local, Advice spent | R | R | session figures, read with spend |
| Live estimate line | R | R | belongs to the pending request's cost |
| Activity: Cost History | R | **L** (below New Chat) | opens a window; navigation |
| Activity: Run Log | R | **L** | same |
| Activity: Learning Centre | R | **L** | same; not about cost at all |
| System (summary pill) | R | R | machine state |
| Chat routing (summary pill) | R | R | provider state, tied to the spend decision |
| API keys (summary pill) | R | R | provider state |
| Model updates (open by default) | R | R, **collapsed** with its count as pill | owner asked for visibility in `model-updates-visibility`; the pill keeps it visible, so open-by-default is no longer needed once the rail has room. Owner may keep it open (open question 2) |

## Options (owner picks one)
Rows are approximate: one row is one line or one link.

**A. Navigation moves left (smallest change).** Left gains Activity (3 links) and the project
meter. Right loses 3 links and the heading. Left about 7 fixed rows, right about 20.
Right is still the heavier rail; the left is no longer empty.

**B. Navigation and project cost left, Model updates collapsed (recommended).** A, plus Model
updates starts collapsed. Left about 7 fixed rows, right about 14 at rest. The right rail fits at
the 600px minimum without scrolling in the common case; the chat list keeps most of the height.

**C. Setup also left.** B, plus API keys and Chat routing move under the chat list as "Providers"
sections. Left about 11 fixed rows (chat list drops to about 12 rows at 950px), right about 10.
The weights are closest, but it separates spend from the routing and key state that explain it,
and puts collapsible status under a list that scrolls, which is the pattern the redesign removed.
Not recommended.

```
        A                    B (recommended)             C
 LEFT        RIGHT       LEFT        RIGHT         LEFT         RIGHT
 Project +…  Spend       Project +…  Spend         Project +…   Spend
 Working in  Session     Working in  Session       Working in   Session
 Proj budget Today       Proj budget Today         Proj budget  Today
 Search +F   Requests    Search +F   Requests      Search +F    Requests
 chats…      Last req    chats…      Last req      chats…       Last req
 chats…      Saved       chats…      Saved         chats…       Saved
 chats…      Advice      chats…      Advice        New Chat     Advice
 New Chat    estimate    New Chat    estimate      Cost History estimate
 Cost Hist   Status      Cost Hist   Status        Run Log      Status
 Run Log     System      Run Log     System        Learning     System
 Learning    Routing     Learning    Routing       Providers    Model upd.
             API keys                API keys      Routing
             Model upd.              Model upd.    API keys
             (open)                  (collapsed)
```

## Goal and success measure (for the chosen option)
1. No rail control ends outside its rail at any tested window size (existing test, both rails).
2. Right rail at rest needs no scrollbar at 1500x950 and, for B, none at 1100x700.
3. Chat list shows at least 8 rows at 950px and 5 at 600px; `history_list.count()` unchanged.
4. Every moved control keeps its attribute name (`cost_history_btn`, `run_log_btn`, `learn_btn`,
   `project_meter`, `model_updates_section`), its handler, its tooltip and its `help_map.json`
   entry; tests and help lessons that reach them keep passing.
5. The project meter appears and hides with the active project exactly as before.
6. Native render of both rails (cocoa, via the live launcher) at 1500x950 and 1100x700 shown to
   the owner with the build; no clipped text (`ui.text_fit.clipped_text` empty).
7. Full suite green (shuffled).

## Out of scope
New controls, new content, any stored-data change, resizing the rail widths (184 / 204 px), the
shuffled-run segfault tracked in TODO.md.

## Design notes (Architect: skipped, no state, concurrency or boundary change)
- A move is re-parenting widgets in `build_left_panel` / `build_right_panel`; the widgets keep
  their names, so `main.py` code that refreshes them is untouched.
- The Activity links on the left use the existing `nav_row` style (chevron rows).
- Left rail's body already sits in `scrollable()`; the list needs a minimum height so the new
  rows do not squeeze it to nothing.

## Open questions for the owner
1. Option A, B or C?
2. Model updates: collapsed with a count pill (B) or keep open?
3. Should Chat routing's "last provider" pill stay on the right (recommended) or move with C?

## Review and Verify (2026-11-25)
- Review: `docs/audit/rails-rebalance-review.md`; no P0/P1, P2 and two P3 fixed, one P3 deferred.
- Native render (cocoa) at 1500x950, 1100x700, 1000x600: neither rail scrolls; chat list about
  12 / 9 / 6 rows; no clipped text. Run against a data folder with one chat, not the owner's 743.
- Full suite on 9037611, shuffled `--randomly-seed=424242`: 3033 passed, 17 skipped, 17 xfailed,
  1 failed: `test_release_kit_security_fixes.py::test_say_speaks_a_dash_quote_and_writes_nothing_else`
  (macOS `say` timed out after 60 s on a loaded machine; unrelated to the rails; passes alone,
  23 passed). Suite then ran before ab1fca3 (docs and two tests added, both pass).
