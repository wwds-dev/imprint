# Code review: GodAI window leak (PR #32)

Reviewer: `code-reviewer` agent (read-only, not the author), 2026-11-27. Reviewed commit `9192cd7`;
`aa38397` landed during the review. Playbook `docs/playbooks/code-reviewer.md` current (last reviewed
2026-10-14).

Result: 0 P0, 0 P1, 2 P2, 4 P3.

| # | Sev | Where (at 9192cd7) | Finding | Status |
|---|---|---|---|---|
| 1 | P2 | `tests/qt_teardown.py:60` | `stop_all()`'s still-running workers were ignored and their windows deleted; a context-less worker-signal lambda (e.g. `agents/music/suno_panel.py:217`) could then run against a deleted host. | Fixed in `aa38397`: windows retired, not deleted, with a warning. |
| 2 | P2/P3 | `agents/manuscript/panel.py:916` | A checklist tick was written only in the deferred call, which the new context drops if the panel is deleted first. | Fixed in `aa38397`: written at once, only the reload deferred; `tests/test_manuscript_todo_toggle.py`. |
| 3 | P3 | `tests/conftest.py:211-219` | Peak sampled at the test body's start, so windows the body built were missed; the "1 window" figure in `9192cd7`'s message was low (a test with two windows exists). | Fixed in `aa38397`: sampled at teardown. |
| 4 | P3 | `tests/conftest.py:203-207` | A module-scoped window first built through `request.getfixturevalue` inside a function fixture or test would be filed as the test's and deleted early. Safe today (no such call site). | Fixed in the follow-up commit: wider-scoped fixtures' windows are recorded and excluded; `tests/test_window_disposal.py` (mutation-checked). |
| 5 | P3 | `tests/qt_teardown.py:62-74` | One `try` around every step: a failing step skipped `deleteLater()`, and a non-`RuntimeError` aborted the loop. | Fixed in the follow-up commit: each step guarded and warned; deletion always attempted. |
| 6 | P3 | `tests/test_single_shot_context.py:17-27` | Scanned only `main.py`, `ui/`, `agents/`, `services/`; starred arguments not flagged. Context-less lambdas on long-lived signals are the same hazard and unguarded. | Scan widened to every Python file outside `tests/`, starred calls flagged. The signal-lambda hazard is left as a TODO row. |

Checked clean: fixture-teardown ordering, no window escapes, `dispose_windows` never terminates a thread
or adds a wait, every timer context is the right object (spotlight `_back` correctly uses the window,
not the marker that deletes itself), no single-window behaviour change. Not verified by the reviewer:
the segfault root-cause story, random order, the full suite (all run by the author, see the PR).
