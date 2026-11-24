# QA report: documentation and Learning Centre readiness (Verify, 2026-11-24)

Role: qa-engineer, read-only on code, tests and docs. Worktree `claude/happy-dubinsky-48c27c` at `d6b72b6`
(contains `origin/main`). Imprint venv, Python 3.11, `QT_QPA_PLATFORM=offscreen` (forced by `tests/conftest.py`).
Playbook `docs/playbooks/qa-engineer.md`: `status: current`, `last-reviewed: 2026-10-14` (41 days, not stale); its
model-testing paragraph is still marked "baseline 2026-11-11, not yet verified by a radar run".
Spec: `docs/specs/docs-learning-centre-readiness.md`. Reviews read: `docs/audit/docs-learning-centre-readiness-code-reviewer.md`,
`docs/audit/docs-learning-centre-readiness-tech-writer.md`. The app makes model calls, but this change is docs and
tests only: no test here calls a model or the network (`tests/test_docs_integrity.py` reads files and runs `git ls-files`).

## Verdict: PASS with gaps
The guard tests are real: they fail on a wrong documented label, a wrong control-list entry, a renamed panel
label and a renamed Settings tab (6 of 7 mutants caught), and five button labels spot-checked in the docs match
the panels' source. Two success measures are not demonstrated yet (2 and 4, ranked P1 below), so the spec is
not done until they are.

## Success measures
| # | Measure | Status | Evidence |
|---|---|---|---|
| 1 | `tests/test_docs_integrity.py` (T1 to T10) passes, runs in the normal suite, failed on the tree before the fixes | Met | Collected by the default `pytest -q` (flat `tests/test_*.py`). Passes in both random orders below. Fail-first recorded by the author in `fdf8e78`'s message ("On today's tree: 20 failed, 250 passed, 30 xfailed"); not rerun by QA. |
| 2 | Zero open P0/P1 `DL-` findings, or deferred by the owner by name; closing table in the audit | **Not demonstrated** | `docs/audit/docs-learning-centre-readiness-tech-writer.md` has no closing table (its headings end at "Model updates: where the docs live today"). DL-9 (P1): 16 lesson/sheet titles still differ from the catalog label (16 strict xfails, `TODO.md:111`); the move out of package 5 names the owner, but no record of the owner's words exists (`docs/foundry/approvals.jsonl` has only the Define gate; also recheck RR-5). DL-16 (P1): README and sheet fixed; the catalog line and Accounts tab stay with `TODO.md:117` (`@me`). |
| 3 | 100% of `tests/docs_controls.txt` phrases found in the code | Met, with a caveat | 358 of 358 controls found (`_controls()` / `_in_app()`, 0 missing); T4 green. Caveat: four bold label-like phrases the docs show are not labels in the app and are parked in `_T4_SUSPECTED_DRIFT` (`tests/test_docs_integrity.py:316-321`: "BEST AVAILABLE", "Free-form", "Last decision", "Publishing Todos"), held by a strict xfail. |
| 4 | Reviewer pass by name: code-reviewer on the diff; qa-engineer fresh-reader walk on a build with an empty `~/Library/Application Support/Imprint/` | **Half met** | Code-reviewer report exists. The fresh-reader walk (README "Start here", lesson 01, every recipe's Show me) was **not done**: this Verify was told not to start the app. Still open as `TODO.md:125`. |
| 5 | Existing guards green; full suite green | Met for the guards | Guard files: 459 passed, 2 skipped, 17 xfailed in both orders. Full suite: not run here (orchestrator: 2877 passed, 0 failed on `2d427e2` today; `2d427e2..d6b72b6` changes README, TODO and a spec only, and the README is covered by the runs below). |

## Spot check: five documented button labels against the panels' source
| Documented (bold) | Where documented | Source |
|---|---|---|
| Save Limits | `README.md:428`, `:2607` | `main.py:3497` `QPushButton("Save Limits")` |
| Export Approved… | `docs/agents/manuscript.md:40` | `agents/manuscript/panel.py:367` |
| Make Release Kit… | `README.md`, `docs/agents/manuscript.md`, `docs/learn/modules/21-publish.md` | `agents/manuscript/panel.py:375` |
| Start | `docs/learn/modules/21-publish.md:248,250` | `ui/release_kit/confirm_dialog.py:167` `primary("Start")` |
| Approve Write Draft… | `README.md`, `21-publish.md`, `manuscript.md` | `agents/manuscript/panel.py:346` |
Also matched: Reset session spend (`main.py:3501`), Save All (`ui/dialogs.py:342`), Test (`ui/dialogs.py:539`). 8 of 8 match.

## Mutation check
Each file was copied to the session scratchpad, changed in one place, the test file run, and the copy put back
(`git diff --quiet` on the file after each). Command per mutant:
`.venv/bin/python -m pytest -q -p no:cacheprovider -p no:randomly -x tests/test_docs_integrity.py`.

| ID | File:line | Change | Caught | By |
|---|---|---|---|---|
| D1 | `README.md:428` | "**Save Limits**" to "**Save Budget Limits**" (the DL-5 error) | yes | `test_t4_label_like_bold_phrases_are_app_labels` |
| D2 | `tests/docs_controls.txt:287` | "Save Limits" to "Save Budget Limits" | yes | `test_t4_every_listed_control_is_a_label_in_the_app` |
| D3 | `main.py:3497` | button label "Save Limits" to "Save Limit" (code drifts from docs) | **no** | survives: `_in_app` is a substring match over every string literal, and "press Save Limits." in `services/validator.py:176` keeps it found |
| D4 | `docs/agents/manuscript.md:40` | "**Export Approved…**" to "**Export Aproved Book…**" | yes | `test_t4_label_like_bold_phrases_are_app_labels` |
| D5 | `docs/learn/modules/21-publish.md:250` | "**Start**" to "**Begin Kit**" | yes | `test_t4_label_like_bold_phrases_are_app_labels` |
| D6 | `agents/manuscript/panel.py:367` | button label "Export Approved…" to "Export Final…" | yes | `test_t4_every_listed_control_is_a_label_in_the_app` |
| D7 | `ui/dialogs.py:777` | Settings tab "Tools" to "Utilities" | yes | `test_t10_readme_lists_the_settings_tabs_the_dialog_builds` |

6 of 7 caught. The three mutants that survived the 2026-11-22 review (R-3: D1, D4, D5) are now caught.

## Random order
```
.venv/bin/python -m pytest -q -p no:cacheprovider -p randomly --randomly-seed=21 tests/test_docs_integrity.py tests/test_learning_center.py tests/test_docs_center.py tests/test_env_template.py tests/test_learning_shots.py tests/test_retired_names.py
459 passed, 2 skipped, 17 xfailed, 1 warning in 21.80s
(same, --randomly-seed=22)
459 passed, 2 skipped, 17 xfailed, 1 warning in 20.23s
```
The 2 skips are the HeyGen and Synthesia env-template skips. The 17 strict xfails are 16 title/retired-name cases
of agents whose label did not change (DL-9/DL-18, `TODO.md:111`) and `test_t4_suspected_label_drift_is_fixed`.
The warning is `PytestRemovedIn10Warning` from the installed `anyio` pytest plugin (`CallSpec2`), not from these tests.

## Ranked gaps
1. **P1: success measure 2 is not demonstrated.** No closing table in the tech-writer audit; DL-9's remainder has
   no recorded owner words for its deferral. Fix: add the table (finding, commit or "deferred: owner" with the
   owner's words recorded via `record_approval.py` or quoted).
2. **P1: success measure 4's fresh-reader walk has not happened** (`TODO.md:125`). It needs a launched build with an
   empty Application Support folder, which this Verify was not allowed to do. The owner's hand test may cover it
   if its result is written to this file.
3. **P2: a label renamed in the code is not caught when the old label also appears inside any other string**
   (mutant D3). `_in_app` (`tests/test_docs_integrity.py:253-255`) is substring-over-all-literals. Fix: for the
   control list, match a whole literal (as `_is_app_label` does for bold phrases), or restrict to widget-label
   call arguments.
4. **P2: four documented label-like phrases are not app labels** (`_T4_SUSPECTED_DRIFT`), so a tester reading
   lessons 12, 18 or README 5 / 7.4 / 7.5 looks for a control that does not exist under that name. Tracked only by
   the strict xfail; no TODO row was found for it.
5. **P3: `tests/docs_controls.txt` still contains substring-only entries** ("Centre", "Text", "Cost"; `TODO.md:119`).
6. **P3: T8, T9, T2, T1 limits from review R-8 and R-11 remain** (T8 skips `TODO.md` and `config/`; T9 passes on an
   empty section; T2 misses plural "sections"; T1 accepts either anchor algorithm).
7. **P3: the anyio plugin raises `PytestRemovedIn10Warning`.** Under the playbook's
   `-W error::pytest.PytestDeprecationWarning` it would turn into an error; not checked whether CI sets that flag.

## Not verified
- The fresh-reader walk and anything on screen ("Show me", F1); the app was not started.
- The fail-first run of measure 1 on the pre-fix tree (taken from the commit message).
- The full suite (not run, by instruction).
- Branch coverage of changed lines: the change is docs plus test code; no production line changed except the
  deletion in `ui/learning_center.py`, so no coverage was measured.
- CI status on GitHub; ruff (not run).
- Live model evals: not applicable (no model call in this change).
- Process note: another agent ran mutations on `main.py` in this worktree at the same time as this Verify. None of
  the runs above overlapped with it (see `docs/audit/model-updates-visibility-qa-engineer.md`).
