# Spec: Quill keeps an unfiled Draft and asks before Clear (audit UX-01, UX-02)

Needs: build, review, verify, docs

Status: Define approved by the owner 2026-11-24 ("Yes, as recommended": D1–D3 as recommended). Priority: P0 (audit
`docs/audit/SUMMARY.md` findings 4 and 5, `docs/audit/ux.md` UX-01, UX-02). Type: user-visible
bug fix. Owner session: `claude/angry-matsumoto-ac520a`. Not covered by `quill-draft-safety`
(QB-1: Write, error and Stop), which is on `main`.

## Problem
Checked against the code on 2026-11-24 (`776828d`):
- **UX-01.** With no Project selected, Quill's workspace lives only in memory
  (`agents/author/panel.py:141`, `_unfiled_state`). `_schedule_project_save` and
  `_persist_project_state` return when `_project_id` is unset (`:881-887`), and the quit handler
  calls the same no-op (`main.py:6483`). A first launch opens Quill with no Project; the banner
  sends the author to Save Profile, which reports "[Saved] Book profile." (`:967-976`) but saves
  only the profile, never the Draft. Quit, reopen: the Draft is empty.
- **UX-02.** Clear (`:449-451`, `clear` at `:1403-1417`) empties Draft, Outline, Characters,
  World Notes, Sources, Direction and Title in one click, with no question. `QTextEdit.clear()`
  drops the undo history, so Cmd-Z restores nothing, and with a Project active the empty state is
  autosaved 0.7 s later, so the stored copy goes too. Clearing Title with a Project active also
  writes an empty work title to that Project.

## Goal and success measure
No quit, relaunch or single click loses manuscript text without the author saying so. Measured
by offscreen tests (temp database, no model call):
1. No Project: type a Draft (and notes), let the save timer fire, open a second window on the
   same database: the Draft and notes are there. Same after the quit handler runs without the
   timer having fired.
2. No Project → select a Project → back to no Project: the unfiled Draft comes back unchanged;
   the Project's own Draft is untouched by it.
3. A Project active: behaviour unchanged (its workspace saves and restores as today).
4. Clear with text present shows a confirmation naming what goes; Cancel (the default, and Esc)
   changes nothing and saves nothing.
5. Clear confirmed: the writing boxes are empty; Cmd-Z in the Draft brings its text back (D2);
   Title and the Book Profile are unchanged (D3).
6. Clear when every box is already empty asks nothing.
7. The full suite stays green; `tests/test_author_draft_safety.py` passes unchanged.

## Behaviour (proposed; D1–D3 need the owner)
- **Unfiled work is saved like a Project's (D1).** With no Project, the same 700 ms autosave
  writes the whole workspace (Draft, Outline, Characters, World Notes, Sources, Tone, POV,
  profile fields) to one setting in the local database, and the quit handler flushes it. Launching
  with no Project, or switching back to no Project, restores it. Selecting a Project does not move
  the unfiled text into that Project; it stays unfiled and returns when no Project is selected.
- **Clear asks first (D2, D3).** "Clear the Draft and notes? This empties the Draft, Outline,
  Characters, World Notes, Sources and Direction{ for “<title>”}. Title and the Book Profile stay."
  Buttons: **Clear** and **Cancel**; Cancel is the default and Esc. Confirmed, each box is emptied
  as one undoable edit, so Cmd-Z in that box restores it while the panel is open. Title is no
  longer cleared.

## Owner decisions
- **D1 Save unfiled work, rather than only warn at quit.** Recommended: save it (above).
  Alternative: keep it in memory and ask at quit ("Your Draft is not in a Project and will be
  lost. Quit anyway?"). Saving needs no extra click and also survives a crash; the warning alone
  loses the Draft on any crash.
- **D2 Clear is confirmed and undoable.** Recommended: both. Alternative: confirmation only (as
  today, Cmd-Z would still restore nothing).
- **D3 Clear leaves Title (and the Book Profile) alone.** Recommended: yes, because Title is the
  Project's work title and clearing it renames the Project. Alternative: keep clearing Title
  after the confirmation.

## Non-goals
The first-run banner wording and a guided start (UX-04). Moving unfiled text into a Project.
Undo across an app restart. Write, Stop and error behaviour (QB-1, done). Any paid path.

## Scope
`agents/author/panel.py` (`_schedule_project_save`, `_persist_project_state`, `activate_project`,
startup restore, `clear`, `_clear_displays`); `main.py` only if the quit flush needs it; new
`tests/test_author_unfiled_and_clear.py`; `agents/author/README.md`, `docs/agents/author.md`,
`CHANGELOG.md`, `TODO.md`. No network, secret or dependency change: Secure not required (one new
local setting key, written only with the author's own text). Comply and Launch skipped (no legal
surface or public claim changes). Design: the dialog text above; no new control.

## Risks
- A large manuscript in one settings row: SQLite holds it; the write is the same size and rhythm
  as a Project's workspace save today.
- The older `author_book_profile` setting (Save Profile with no Project) stays; the unfiled
  workspace, when present, is restored after it and wins.

Verify (2026-11-24): full suite on `7041255` plus the two test-isolation commits from `claude/happy-dubinsky-48c27c` (`4c926c3` segfault fix, `836ca99` Booth row leak; not on this branch, they reach `main` with that branch): 2875 passed, 17 skipped, 17 xfailed, 6 subtests passed in 58 min 35 s, `-p randomly`. On `7041255` alone the run hit the known full-suite segfault at 74% (`tests/test_settings_keys.py:410`, no failures before it); on `68010c8` alone: 2 failed, 2865 passed (one docs label, fixed in `7041255`; the known Booth row leak).
