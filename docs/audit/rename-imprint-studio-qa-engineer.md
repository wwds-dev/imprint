# QA report: rename to "Imprint Studio"; Kernel, Nova, Vector (Verify, 2026-11-24)

Role: qa-engineer, read-only on code, tests and docs. Worktree `claude/happy-dubinsky-48c27c` at `d6b72b6`
(contains `origin/main`). Imprint venv, Python 3.11, offscreen Qt. Playbook `docs/playbooks/qa-engineer.md`:
`status: current`, `last-reviewed: 2026-10-14` (41 days, not stale); its model-testing paragraph is still marked
"baseline 2026-11-11". Spec: `docs/specs/rename-imprint-studio.md`. Reviews read:
`docs/audit/rename-imprint-studio-code-reviewer.md`, `docs/audit/rename-imprint-studio-code-reviewer-recheck.md`.
No build, install or retire script was run; the app was not started. No test here calls a model or the network.

## Verdict: PASS with gaps
The automated measures (1, 2, 4 and the test half of 3) hold, and 10 of 11 planted bugs were caught: window
titles, the router guard, the installer's bundle name and the `APP_NAME` / `QSettings` invariants all fail a test
when broken. Not demonstrated: the owner's launch on existing data and the measure-5 screenshots (`TODO.md:113`,
open), and Secure (a security-engineer report appeared in the worktree during this Verify, from another session;
not read here). The one survivor is `scripts/build_app.sh`'s bundle name, which no test reads.

## Success measures
| # | Measure | Status | Evidence |
|---|---|---|---|
| 1a | Window title, tray tooltip and actions, menu-bar name, version tooltip, Documentation / Learning Centre / Income Lab titles show "Imprint Studio" | Met (menu-bar name by static scan only) | `tests/test_panel_layout.py:1409` (title and wordmark on the live window); `tests/test_display_names.py:34-44` (tray, version), `:98-111` (three sub-windows built offscreen), `:68-74` (no literal old name in any `setWindowTitle` / `setAccessibleName` / `setToolTip` / `name_in_menu_bar` argument in `main.py` and `ui/`). `main.py:6847` passes `APP_DISPLAY_NAME`; no test asserts the value it passes. |
| 1b | `APP_NAME == "Imprint"`, `imprint.db`, `SINGLE_INSTANCE_KEY`, both `QSettings("Imprint", "Imprint")` unchanged | Met | `tests/test_display_names.py:148-163`; mutants N7, N8 caught. |
| 1c | Recommendation profile, DB seed, registry and both manifests equal the catalog label | Met | `tests/test_display_names.py:179-246` (incl. an old database relabelled by `init_db`); mutant N9 caught. |
| 1d | No old codename in user-visible strings and user docs | Met | `tests/test_display_names.py:299-322`; the rename-note exemption (`:286`) is broad (any line with "formerly", "renamed", "was called", "until 2026-11-22" is skipped). |
| 2 | Router: "open Kernel", "switch to Nova", "Vector." route; R3 sentences do not; `test_codenames_come_from_the_catalog` unchanged | Met | `tests/test_agents_scenarios.py:138-235`; mutants N2, N3, N4, N10 caught. Known limit RR-2 (joiners `/`, `+`, `(`, `:` still address) stays open, P3. |
| 3 | Rename migration and DB migration tests pass unchanged; a launch on the owner's data shows the same projects, chats and keys | Tests met; launch **not demonstrated** | `tests/test_cost_and_limits.py`, `tests/test_database_migrations.py` pass in both orders below. The data check is open in `TODO.md:113` (`@me`). |
| 4 | Drift tests pass with no edit to a shared file | Met | In this worktree the drift tests skip (no `sentinel` / `lab_hub` beside a worktree). The shared files and drift tests are byte-identical to the main checkout (`cmp`, 11 files), and there they pass: `tests/test_benchmarks_drift.py tests/test_converter_drift.py tests/test_providers_drift.py tests/test_app_launcher.py` -> `18 passed, 1 warning in 1.93s` (0 skipped). `git log --since=2026-11-21` on the shared files: only `45f705d` (a Sentinel sync of `routing_advisor.py`), no rename commit. |
| 4 | Full suite green | Not run here | Orchestrator: 2877 passed, 0 failed on `2d427e2` today; `2d427e2..d6b72b6` changes README, TODO and one spec only. |
| 5 | Screenshot checklist from the installed app (owner) | **Not demonstrated** | Open in `TODO.md:113`. |

## Mutation check
Each file was copied to the session scratchpad, changed in one place, the tests run with
`-p no:cacheprovider -p no:randomly -x`, and the copy put back (`git diff --quiet` on the file after each).
Test set "rename files" = `tests/test_display_names.py tests/test_app_launcher.py tests/test_tray.py tests/test_agents_scenarios.py tests/test_retired_names.py`.

| ID | File:line | Change | Tests run | Caught | By |
|---|---|---|---|---|---|
| N1a | `main.py:263` | main window title `APP_DISPLAY_NAME` to `APP_DISPLAY_NAME + " app"` | `test_display_names.py` + `test_panel_layout.py::test_window_title_and_wordmark_show_the_display_name` | yes | the panel-layout title test (the static scan alone would not catch it) |
| N1b | `ui/income_worksheets.py:57` | sub-window title drops the app name | `test_display_names.py` | yes | `test_sub_window_titles_carry_the_display_name[income-...]` |
| N2 | `agents/router/agent.py:95` | `_GUARDED_KEYS` without `"fiverr"` | `test_agents_scenarios.py` | yes | `test_an_ordinary_word_is_not_an_address[use vector files]` |
| N3 | `agents/router/agent.py:110-111` | joined-word branch (`-`, `'`, `.` + word) removed | `test_agents_scenarios.py` | yes | `...[use vector-based artwork]` |
| N4 | `agents/router/agent.py:115` | `_ends_the_name` returns True for any following word | `test_agents_scenarios.py` | yes | `...[use the nova voice]` |
| N10 | `agents/router/agent.py:100` | "and" removed | `test_agents_scenarios.py` | yes | `test_a_name_followed_by_a_connector_still_addresses[open Nova and draft a campaign-creator]` |
| N5 | `scripts/install_app.sh:44` | `APP_DISPLAY_NAME="Imprint Studio"` to `"Imprint"` | rename files | yes | `test_bundle_metadata_names_imprint_studio` |
| N6 | `scripts/build_app.sh:33` | `APP_BUNDLE="Imprint Studio.app"` to `"Imprint.app"` | rename files | **no** | 329 passed; no test reads `build_app.sh`'s bundle name |
| N7 | `services/runtime_paths.py:27` | `APP_NAME = "Imprint"` to `"Imprint Studio"` | rename files | yes | `test_state_names_do_not_change` |
| N8 | `ui/docs_center.py:141` | `QSettings("Imprint", "Imprint")` to `("Imprint Studio", "Imprint")` | rename files | yes | `test_state_names_do_not_change` |
| N9 | `agents/creator/recommendations.py:4` | profile label "Nova" to "Muse" | rename files | yes | `test_recommendation_profiles_carry_the_catalog_label` |

10 of 11 caught.

## Random order
```
.venv/bin/python -m pytest -q -p no:cacheprovider -p randomly --randomly-seed=21 -rs tests/test_display_names.py tests/test_app_launcher.py tests/test_tray.py tests/test_agents_scenarios.py tests/test_retired_names.py tests/test_cost_and_limits.py tests/test_database_migrations.py tests/test_benchmarks_drift.py tests/test_converter_drift.py tests/test_providers_drift.py "tests/test_panel_layout.py::test_window_title_and_wordmark_show_the_display_name"
396 passed, 14 skipped, 1 warning in 7.87s
(same, --randomly-seed=22)
396 passed, 14 skipped, 1 warning in 7.38s
```
The 14 skips are the sibling-checkout drift cases (11 providers, 1 benchmarks, 1 converter, 1 launcher); they pass
from the main checkout (measure 4). The warning is `PytestRemovedIn10Warning` from the installed `anyio` plugin.

## Ranked gaps
1. **P1: measures 3 (launch on the owner's data) and 5 (screenshots) are not demonstrated** (`TODO.md:113`, `@me`).
   They need the installed app and the owner; Release should wait for them.
2. **P1: Secure has not finished as far as this Verify can see.** The spec requires it (the install scripts delete a
   bundle). `docs/audit/rename-imprint-studio-security-engineer.md` appeared untracked during this run from another
   session; its verdict was not read here.
3. **P2: `scripts/build_app.sh`'s `APP_BUNDLE` is not pinned** (mutant N6). A mismatch with `Imprint.spec`'s
   `name="Imprint Studio.app"` would show only at build time; `INSTALLED` would then point at
   `/Applications/Imprint.app`, the path the retire helper also handles. Fix: assert
   `APP_BUNDLE="Imprint Studio.app"` (or that it equals the spec's `name=`) in `test_bundle_metadata_names_imprint_studio`.
4. **P3: the retire helper's "foreign bundle id" and "still running" branches are never executed** (recheck RR-4);
   only text assertions exist (`tests/test_display_names.py:327-348`). A test could run the function with `old`
   pointed at a temp directory if the path were injectable; today it is a literal by design.
5. **P3: router joiners `/`, `+`, `(`, `:` still address a guarded name** (recheck RR-2); not pinned either way.
6. **P3: the menu-bar name has no value assertion** (only the old-literal scan); a change to another wrong literal
   that contains "Imprint Studio" would pass.
7. **P3: the rename-note exemption skips whole lines** (`tests/test_display_names.py:286`); an old name on a line that
   also says "renamed" is never flagged.

## Not verified
- Any build, install or the retire script (not allowed); Dock, Cmd-Tab, Activity Monitor names; the macOS permission
  prompt; data in `~/Library/Application Support/Imprint/` after the real install.
- The full suite (not run, by instruction). CI on GitHub. ruff.
- Branch coverage of changed lines (not measured; the router guard's branches are each hit by the mutants above).
- Live model evals: not applicable (no model call in this change).
- Lab Hub's side of the rename.
