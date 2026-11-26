# QA verify: Manuscript redesign slice 1, the shell (PR #30)

- **Commit:** f37aa8d, branch `claude/manuscript-shell-slice1`
- **Date:** 2026-11-26
- **Role:** `qa-engineer`, phase 7. Read-only. Every planted mutation was reverted; `git status --short` afterwards shows only the orchestrator's `docs/foundry/activity.jsonl`.
- **Playbook:** `docs/playbooks/qa-engineer.md` (`last-reviewed: 2026-10-14`, current).
- **Scope:** measures 2, 4, 5, 6, 7 and 9 for slice 1. Measure 8 is recorded as seen by the owner. Measures 1 and 3 belong to slice 2.
- **Full suite** (measure 9, added by the orchestrator): green on f37aa8d. Command: `.venv/bin/python -m pytest -q -p randomly --randomly-seed=3219827553`. Result: 3363 passed, 17 skipped, 25 xfailed, 0 failed, in 14 min.
- **Not verified:**
  - Branch coverage of changed lines: `coverage` is not in the worktree venv. Mutation testing stands in.
  - Mutation of measure 2 and of the rail-fit assertions.

This file was written by the orchestrator from the agent's report.

## Targeted shuffled runs

| Modules | Seeds | Result |
|---|---|---|
| shell, inventory, chips, motion, contrast, theme, usage_unpriced, colour_literals | 11, 222 | 298 passed, 8 xfailed each |
| learning_center, side_rails, panel_layout, cost_and_limits, partial_billing, local_only_guard | 77 | 562 passed |
| shell, motion, learning_center, side_rails, panel_layout | 3333, 91 | 490 passed each |

- **No order dependence** showed in any of these runs.
- **Guard tests:** `test_cost_and_limits.py`, `test_partial_billing.py` and `test_local_only_guard.py` are unchanged by the branch and pass.
- **Expected failures:** the 8 xfails are all `strict=True` in `tests/test_contrast.py`:
  - dark `TEXT_MUTE` in all three dark themes (owner decision AO2);
  - dark `BORDER_STRONG` in all three dark themes;
  - dark rose `ACCENT_DIM`;
  - dark rose `PHOSPHOR`.

  All 8 are listed in TODO.md.
- **Skips** are environmental only: ffmpeg missing, no focus offscreen, no priced openai row, vidforge unavailable.

## Measures

| # | Measure | Test | Result | Catches a break? |
|---|---|---|---|---|
| 1 | Navigation depth | — | out of scope (slice 2) | — |
| 2 | Nothing lost | `test_shell_inventory.py`, against the snapshot taken before Build (713e67c) | pass | Yes, by design: it compares handler and tooltip, and the one removal has an owner line. Not mutated by QA. |
| 3 | One primary action | — | out of scope (slice 2) | — |
| 4 | Fit | `test_shell.py::test_the_shell_fits_at_every_size` (3 sizes × 2 themes × 3 agents) and `test_the_collapse_steps_happen_in_order`; rewrites in `test_panel_layout.py` and `test_side_rails.py` | fit passes; the collapse test passes vacuously | Fit: yes. Collapse order: **no** (F1) |
| 5 | Money | `test_shell_chips.py`, `test_usage_unpriced.py`, `test_the_popover_figures_say_unknown`, `test_cost_history_reads_unknown_for_an_unpriced_row`, the unchanged guard tests | pass | Yes. M1–M6 and M18–M22 killed |
| 6 | Readable | `test_contrast.py`, six themes | pass, plus 8 strict xfails | Yes. A light `TEXT_MUTE` mutation was killed |
| 7 | Motion | `test_motion.py` and the drawer tests in `test_shell.py` | pass | Yes. M10–M13 killed |
| 8 | Seen by the owner | the native renders | seen | — |
| 9 | Full suite green, shuffled | orchestrator's full run (above) | pass | — |

## Mutation check

31 mutants: 27 killed, 4 survived. Three of the four survivors are one gap (F1).

| # | Mutant | Result |
|---|---|---|
| M1–M4 | `ui/shell/chips.py` danger and warning thresholds, the unknown tone, the sub-cent case | killed |
| M5–M6 | `status_state` order | killed |
| M7–M9 | `ui/shell/top_bar.py` level thresholds (spend compact, status compact, selector shrink) | **survived** (F1) |
| M30 | `TopBarFitter.fit()` always picks level 0 | **survived** (F1) |
| M10–M13 | `ui/motion.py`: the reduced guard, the typing guard, `MAX_MS`, the loop guard | killed |
| M14 | `theme._build_swap` ambiguity check | killed |
| M15–M17, M31 | `adopt_light_once` (flag, look, accent); light `TEXT_MUTE` | killed |
| M18–M20 | `usage_tracker` unpriced marking, the price-row check, the count query | killed |
| M21–M22 | `BudgetRow.set` unknown, the sub-cent case | killed |
| M23 | drawer `hideEvent` parent-hide branch | killed |
| M24 | drawer `hideEvent` no longer emits `closed` on a direct hide | **survived** (F2) |
| M25–M27 | `AudiobookPlayer.resume`: sleep index, remaining time, play | killed |
| M28–M29 | `spotlight.anchor_for` | killed |

## Design S11 states

| State | Test | Verdict |
|---|---|---|
| No project | `test_no_project` | covered |
| No chats | `test_no_chats_says_so` | partly: the assertions are conditional (F4) |
| No limit, over the limit, unknown price | `test_every_s6_row` | covered |
| Model updates 0, 1 and 12 | `test_the_model_updates_badge` | partly: the painted digits are not asserted (F6) |
| Stale build | `test_version.py::…stale…` | gap: depends on the repo's real staleness (F3) |
| Three sizes, light and dark, no clipping, rail visible | `test_the_shell_fits_at_every_size` | covered; the bar is checked by geometry (F5) |
| Native renders | owner | seen |

## Findings

### P2
- **F1. The top bar's collapse levels 1–5 are never exercised.**
  - Where: `tests/test_shell.py:149-176` and `ui/shell/top_bar.py:127-200`.
  - Evidence: at every width from 1500 down to 1000 px, with the long values, the level stays 0. The minimum window width is 1000 px. M7–M9 and M30 survive.
  - Effect: the test-plan row "S3's collapse steps happen in order as width falls" is not demonstrated.
  - Fix direction: drive a standalone `TopBar` at widths narrow enough to reach every level, or force levels and assert the visible forms. Alternatively, record that level 0 always fits at the minimum width.

### P3
- **F2. M24 survived.** No test hides the open drawer directly and then checks that `closed` is emitted and `history_btn` is unchecked. Location: `ui/shell/drawer.py:228`.
- **F3. The stale-build test depends on the environment.** It reads the real `app_version.staleness()`. Fix: monkeypatch it to cover both states.
- **F4. `test_no_chats_says_so` is conditional.** Its assertions run only when the list is empty, and it does not check the `TEXT_DIM` colour.
- **F5. The bar is checked by geometry, not by `clipped_text`.** The chips are checked through `width_for`, which is a fair proxy, but the S11 wording ("no clipped text") is met only for the drawer and the popovers.
- **F6. The badge digits are not asserted.** The test checks the width change and the accessible name, not the painted "1" and "12".
- **F7. The routing tag detector was loosened** to a hue test. It is justified in its docstring. That it still fails on a wrongly coloured tag is not verified.

## Manual checklist for the owner (needs a person or cocoa)
1. **VoiceOver, five minutes (Design S9).** Go through the rail, the top bar and its chips, both popovers, the History drawer, and the project and "?" menus. Check that every icon-only control has a spoken name, that "selected" is announced, and that the chips read as full sentences. Check that focus returns to the chip when a popover closes.
2. **Real Reduce Motion.** Turn on Reduce motion in System Settings and relaunch: the drawer must appear with no slide. Turn it off, switch back to Imprint: the slide must return.
3. **Cocoa shortcuts.** Check ⌘?, F1, ⌘Y, and Esc in each popover and the drawer. In the limit fields there is no right-click menu (QTBUG-133560), but ⌘C and ⌘V must work.
4. **Hide and minimise.** With History open, press ⌘H and come back, then minimise and come back. The drawer must still be open with its scrim, and Esc must close it.
5. **Theme switch while Booth plays.** Set a sleep timer, then switch through the six looks. Playback must stay at the same position and the timer must keep its time left.
6. **Stale build.** With an installed bundle older than the code, check the dot on the app mark, its tooltip and the About line.

## Verdict
**Nothing blocks Release on the QA gate.** There is no P0 and no P1.

- Measures 2, 5, 6, 7 and 9 are demonstrated.
- Measure 4 is shown for fit, but not for its collapse order (F1, P2). Close F1 before Release, ideally with F2 and F3, which are cheap, or the owner defers it explicitly.
