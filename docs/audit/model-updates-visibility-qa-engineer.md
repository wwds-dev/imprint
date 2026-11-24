# QA report: Model updates section open by default (Verify, 2026-11-24)

Role: qa-engineer, read-only on code, tests and docs. Worktree `claude/happy-dubinsky-48c27c` at `d6b72b6`
(contains `origin/main`). Imprint venv, Python 3.11, offscreen Qt. Playbook `docs/playbooks/qa-engineer.md`:
`status: current`, `last-reviewed: 2026-10-14` (41 days, not stale); its model-testing paragraph is still marked
"baseline 2026-11-11". Scope: the visibility part (G5) of `docs/specs/model-updates.md` as approved on 2026-11-22
("go", `docs/foundry/approvals.jsonl:8`) and as left after the owner dropped the status-line sentence: commits
`0ca683f`, `805ddf7`. Review read: `docs/audit/model-updates-visibility-code-reviewer.md`.
Net change against its base `ec1cda5`: `main.py:3596` `expanded=False` to `expanded=True`, one test
(`tests/test_model_watch.py:258-261`), README, CHANGELOG, TODO. No existing assertion changed.

## Verdict: PASS with gaps
A test proves the section is open when the window is built, and it fails when the section starts closed, is closed
after construction, or is closed by the title refresh (3 of 3 behavioural mutants caught). Gap: it checks the
section's own open state, not that the section is visible in the shown window (mutant V6 survives).

## Success measure
| Measure | Status | Evidence |
|---|---|---|
| The Model updates section is open at start | Met | `test_the_model_updates_section_is_open_at_start` asserts `header_btn.isChecked()` and `not content.isHidden()` on a real `GodAI` window built offscreen (module fixture `window`, `tests/test_model_watch.py:170`). Mutants V1, V4, V5 fail it. |
| Docs say so | Met | `README.md:436` "**Model updates is open by default** (since 2026-11-22)"; CHANGELOG entry in `805ddf7`. The dropped status-line claim is gone from both (review "Resolution"). |
| Existing model-watch tests pass unchanged | Met | `git diff ec1cda5 805ddf7 -- tests/` adds one test, removes nothing; 136 passed in both orders below. |
| No model call, no network in the tests | Met | The test builds the window only; the module's other tests use fake clients (`_FakeQwen`). |

## Mutation check
Each file was copied to the session scratchpad, changed in one place, the test run, and the copy put back
(`git diff --quiet` on the file after each). Command:
`.venv/bin/python -m pytest -q -p no:cacheprovider -p no:randomly -x "tests/test_model_watch.py::test_the_model_updates_section_is_open_at_start"`.
All rows below are the reruns on a quiet tree (see "Incident").

| ID | File:line | Change | Caught | Note |
|---|---|---|---|---|
| V1 | `main.py:3596` | `expanded=True` to `expanded=False` | yes | also caught with the two whole model-watch files |
| V4 | `main.py:3618` | `_toggle()` right after the section is added (closed after construction) | yes | |
| V5 | `main.py:5454` | the title refresh (`set_title`) closes an open section | yes | |
| V6 | `main.py:3618` | `setVisible(False)` on the whole section | **no** | the test checks `content.isHidden()` and the button, not the section's visibility in a shown window |
| V2 | `ui/widgets.py:609` | `content.setVisible(expanded)` to `setVisible(True)` | no (equivalent) | no behaviour change for a section built with `expanded=True` |
| V3 | `ui/widgets.py:594` | `header_btn.setChecked(expanded)` to `setChecked(False)` | no (equivalent) | `_update_header()` at `:608` sets it again from `_expanded` |

Behavioural mutants: 3 of 4 caught (V1, V4, V5; V6 survived). V2 and V3 are equivalent mutants, not counted.

## Random order
```
.venv/bin/python -m pytest -q -p no:cacheprovider -p randomly --randomly-seed=21 tests/test_model_watch.py tests/test_model_watch_media.py
136 passed, 1 warning in 14.41s
(same, --randomly-seed=22)
136 passed, 1 warning in 14.28s
```
The warning is `PytestRemovedIn10Warning` from the installed `anyio` plugin.

## Incident during this Verify (no lasting change)
Another agent ran its own mutations on `main.py` in this worktree at the same time, with its backups in the same
scratchpad (`orig/main.py`, `main_mutants.log`). Its backup was taken at 10:55:46 while mutant V1 was in place, so its
restores wrote `expanded=False` back into `main.py` (its M1 to M7). A first seed-22 run here failed 1 test for that
reason. Its backup was replaced with `git show HEAD:main.py` at about 10:58 (it differed from HEAD only at line
3596); its later restores were clean. After it finished, `git status` showed no change to `main.py`, and every result
in this report was rerun. Its own results from about 10:55 to 10:58 may be wrong in the other direction too: a
restore here could have removed one of its mutants while its tests ran; its M3b survivor (`main.py:1281`) should be
rerun before it is reported.

## Ranked gaps
1. **P2: visibility in the shown window is not asserted** (V6). Fix: `window.show()` offscreen and assert
   `section.isVisible()` and `section.content.isVisible()`, with the workspace the app starts in.
2. **P3: the test reads a module-scoped window others have used**, so it checks "open after the module's earlier
   tests", not strictly "open at start". Nothing in the module toggles the section today (review), and random order
   is green; a fresh-window assertion would remove the dependence.
3. **P3: G5's status-line sentence stays open** in `docs/specs/model-updates.md` by the owner's choice; not a defect
   of this change.

## Not verified
- On screen: whether the right rail that holds the section is visible at launch (the app was not started).
- The full suite after `805ddf7` (its commit says it was not rerun; orchestrator: 2877 passed on `2d427e2` today).
- Branch coverage: the change has no branch (one constant); not measured.
- CI on GitHub; ruff.
- Live model evals: not applicable (no model call in this change).
