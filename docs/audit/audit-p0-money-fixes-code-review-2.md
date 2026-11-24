# Code review 2: commit fdc30ff (Quill UX-01/UX-02 and the money-fix round)

Reviewer: code-reviewer (read-only, not the author), 2026-11-24, diff `81f9917..fdc30ff`. Saved by
the author session from the reviewer's returned report; the resolution is the author's.
Targeted tests: 77 + 104 passed. Full suite not run by the reviewer.

**P0: 0. P1: 0.** Both earlier P1s (Booth cache gone; Reel Omni quit) closed; spec measures for
UX-01/UX-02 met; the conftest fixture is safe for the rest of the suite.

## P2
- **P2-1. Clear stays enabled during a Write** (pre-existing). Mid-stream it moves the anchor past
  the document (the reply comes back duplicated); mid-revise it empties the read-only Draft and the
  incomplete-revision guard compares against 0. Fix: disable Clear while a run is active and
  return early from `clear()` while `_stream_mode` is set.
- **P2-2. Creator's Gemini Omni teaser still releases an interrupted call as free**
  (`agents/creator/panel.py:1598-1625`), and quitting does not ask; Reel now counts it. Owner to
  pick one rule.

## P3
1. The Cmd-Z promise is broader than the code: a Project switch or a notes Write calls
   `setPlainText`, which drops undo.
2. The quit questions run in an order that can leave a release kit paused after Keep Running.
3. Herald's check reads a missing `visuals.source` as not-AI; vidforge reads it as `"ai"`.
4. The normal-path Omni write in `ui/workers.py` is still not atomic.
5. The CHANGELOG headline "not thrown away by ... a quit" overclaims.
6. New branches without tests: the quit question, `activate_project`'s except branch, startup
   with both the old profile and an unfiled row.
7. `_clear_displays(undoable=False)` is a dead parameter.

## Resolution (author session, 2026-11-24)
- **P2-1 fixed:** Clear is disabled from authorization to finish and `clear()` refuses while a run
  streams. Tests: `test_clear_is_unavailable_while_a_write_runs`,
  `test_the_clear_button_is_disabled_once_a_write_is_authorized`.
- **P2-2:** `TODO.md` row, `@me` (needs the owner's rule).
- **P3-1** dialog, docs and CHANGELOG now say "until you switch Project or Write again".
  **P3-2** the Omni question is asked before the release-kit one. **P3-3** missing source reads as
  `"ai"`. **P3-4** both worker writes go through one atomic `_save()`. **P3-5** headline corrected.
  **P3-6** quit-question test added (`test_quitting_during_an_omni_render_asks_and_keep_running_stays`);
  the other two branches are left untested (an except path and a load-order case the reviewer
  checked by reading). **P3-7** parameter removed.
