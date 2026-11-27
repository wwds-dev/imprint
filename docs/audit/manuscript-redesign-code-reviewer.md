# Code review: Manuscript redesign slice 1 (PR #30)

- **Reviewed commit:** `63354f1b7bdf3eef38c03c67f987647e61914b24`, branch `claude/manuscript-shell-slice1`, `git diff main...HEAD` (51 files, +5207/−995).
- **Date:** 2026-11-26.
- **Role:** `code-reviewer`, phase 6, read-only. Nothing was edited. This agent is a different one from the author.
- **Playbook:** `docs/playbooks/code-reviewer.md` has `last-reviewed: 2026-10-14` (43 days) and `status: current`, so it is not stale. It adds only the lint-ratchet rule, which does not apply here.
- **Evidence:**
  - Targeted tests: `test_usage_unpriced`, `test_shell_chips`, `test_motion`, `test_theme`, `test_contrast`, `test_colour_literals`. Result: 241 passed, 8 xfailed.
  - The full suite was not run by the reviewer. The author reports it green with seed 3219827553: 3350 passed.
  - Throwaway probe scripts, run offscreen against the real classes; they never touch `data/imprint.db`.
  - A dark-sheet comparison of `global_stylesheet()` on `main` and on HEAD.

Report written to this file by the orchestrator from the reviewer's output.

## P0

None.

## P1

### P1-1. Unknown-price requests still read "€0.00" in the spend popover and Cost History
- **Where:**
  - `main.py:6242` (`Last request`)
  - `main.py:6257-6258` (`session_meter` and `daily_meter`)
  - `ui/dialogs.py:140` (Cost History cost column)
- **What is wrong:**
  - Only the chip (`ui/shell/chips.py`) and the one `unpriced_note` line know about `unpriced`. The rest of the same popover is fed from `cost_eur`, which stays `0.0` for an unpriced row.
  - The spec's risk section says popovers must not "show €0.00 for an unpriced call".
- **Failure scenario:**
  - A cloud request on a model with no price row is logged as `cost_type="unpriced"`, `cost_eur=0.0`.
  - Open the chip: the popover shows `Last request  €0.00`, a Today bar at 0, and the note "1 request had no price".
  - Cost History renders `€0.00` for that row. Only the `cost_type` column says "unpriced".
- **Why P1:** it breaks the "zero means unknown, not free" rule on the new surface. The guard, totals and chip are correct, so the defect is display only. Spec A5 lists `last_request_stat` and the meters as "unchanged", so the owner may defer it.
- **Fix direction:**
  - Return the `cost_type` from `log_request` into a `last_request_unpriced` flag, and show "Unknown" in `last_request_stat` when it is set.
  - Render a Cost History row with `cost_type == "unpriced"` as "unknown".
  - Add a test for each.

## P2

### P2-1. The History drawer is left half-open after the window is hidden and shown
- **Where:** `ui/shell/drawer.py:210-215` (`hideEvent`).
- **What is wrong:**
  - `hideEvent` treats any Hide event as "hidden from outside": it sets `_open=False`, `progress=0` and hides the scrim.
  - A parent hide (window hide, minimise, Cmd+H) also sends a Hide event to the drawer, but the drawer is not `isHidden()`. When the parent shows again, the drawer reappears.
- **Probe:** open without animation, then `host.hide()`, then `host.show()`.
  - After the hide: `open False scrim False`.
  - After the show: `open False drawer visible True scrim visible False`, geometry `(0,0,320,600)`.
  - `close_drawer()` then returns early on `not self._open`, so the drawer stays visible.
- **Failure scenario:**
  - The user opens History, hides the app, and comes back.
  - The drawer is stuck on screen with no scrim. The close button, Esc and a click outside do nothing.
  - `history_btn` stays checked, because `closed` was never emitted.
  - Only pressing ⌘Y twice recovers it.
- **Not verified:** cocoa's behaviour on minimise.
- **Fix direction:** in `hideEvent`, ignore spontaneous and parent-driven hides (test `self.isHidden()`), or make `close_drawer` and `toggle` work from the real visibility. Add a test: open, `host.hide()`, `host.show()`, then assert the state is consistent.

### P2-2. A theme switch cancels the Booth sleep timer without telling the user
- **Where:** `agents/audiobook/audio_player.py:207-239` (`suspend` and `resume`), which call `load()` at `:169`.
- **What is wrong:**
  - `suspend` captures only path, title, position and playing.
  - `resume` goes through `load()`, which sets `sleep_box.setCurrentIndex(0)` and stops `_sleep_timer`.
- **Probe:** real mp3, offscreen.
  - Before: `sleep idx 1 (15 min), timer active True, rate 1.5`.
  - After suspend and resume: `sleep idx 0, timer active False`. The rate 1.5 survived.
- **Failure scenario:** the user sets "30 min" to fall asleep to a book, then changes the accent or look. The sleep timer silently becomes "Off" and the audio plays all night.
- **Not verified:** position and playing state. Offscreen, `position()` read 0 after 1.8 s of "playing", so the saved position could not be exercised.
- **Fix direction:** capture `sleep_box.currentIndex()` and the remaining timer time in `suspend`, and restore them in `resume` after `load()`. Alternatively, skip the `load()` reset when resuming.

### P2-3. The suspend and resume branches in `apply_global_style` are barely tested
- **Where:** `tests/test_shell.py:552-575` and `:504-538`.
- **What is wrong:**
  - Position is never asserted. `resume_ms` is recorded by the monkeypatch but never compared.
  - The playing state is never asserted. The test comment says "same book, playing", but only `_path` and `audioOutput()` are checked.
  - No case has `setStyleSheet` or `theme.repaint` raising, so the `finally` path is untested.
  - There is no sleep-timer case.
- **Failure scenario:** a `suspend()` that forgets the position, or a `resume()` that never calls `play()`, passes both tests. P2-2 passes through them too.
- **Fix direction:**
  - Assert `resume_ms == position`.
  - Assert the playing state after resume.
  - Add a case that monkeypatches `theme.repaint` to raise, and check that the player is still reloaded and the exception still propagates.

### P2-4. The spend chip hides "limit reached" when any request today was unpriced
- **Where:** `ui/shell/chips.py:80-85` (tone) and `:98-104` (tooltip).
- **What is wrong:** `if unpriced: tone = "unknown"` comes before the `danger` and `warning` branches.
- **Probe:** `spend_chip_text(6.0, 5.0, 1)` returns `tone='unknown'`, the tooltip "…the real total is more than €6.00.", and an accessible name with no "Daily limit reached".
- **Failure scenario:** €6 is spent against a €5 daily limit, and one earlier request had no price. The chip shows neutral text and no red border.
  - The guard still blocks requests, so this is display only. The user sees the limit only when the guard refuses.
  - The S6 table in the spec does not define this combination.
- **Fix direction:** compute the limit tone from the known spend first, and add "unknown" as a second signal: for example, the text plus a danger border, with both tooltips. Add a test row.

## P3

- **P3-1. `ui/theme.py:379-390`, `adopt_light_once`.**
  - The docstring says "Never raises", but `set_current` (which calls `save_setting`) runs outside the `try`. A write failure on the third database call would escape from `GodAI.__init__`.
  - A user who never picked a theme (the old default was an unsaved dark green) moves to light with no note, because nothing is saved to detect.
  - Fix: wrap the call, and document that the note shows only for a saved dark key.
- **P3-2. `main.py:3849-3867`, `apply_global_style`.** If `player.resume()` raises inside `finally` while `setStyleSheet` also raised, the original exception is masked. Wrap `resume` in its own `try` and log through `_note_failure`.
- **P3-3. `main.py:2763-2764`.** `Ctrl+?` and `Ctrl+Shift+/` are both bound to `_open_help_menu`.
  - On macOS they may match the same event. Qt then reports an ambiguous shortcut and fires neither.
  - Not verified: offscreen delivers neither shortcut for a Cmd+Shift+/ key event.
  - Check on cocoa, and keep one binding if it is ambiguous.
- **P3-4. `ui/tooltips.py:39,41`.** Stale copy overwrites the new tooltips.
  - `agent_title_label` reads "Click an agent in the left sidebar to switch", and that text stays.
  - `agent_status_pill` reads "●  READY = idle; flips colour…". `StatusChip._tip()` replaces it within a second.
  - The docstring at `ui/tooltips.py:11-12` ("chip in the header bar") is also stale.
  - Fix: update the copy and the docstring.
- **P3-5. Dead code left behind.** Nothing outside their definitions uses these:
  - `ui/forms.py:511-513` (`HEADER_HEIGHT`, `RAIL_LEFT_WIDTH`, `RAIL_RIGHT_WIDTH`) and `ui/forms.py:616` (`rail()`);
  - `ui/rail.py:379` (`nav_row`) with its `QPushButton#RailNav` rules at `ui/style.py:926-936`;
  - orphaned comment blocks in `ui/style.py`: "Overflow for workspaces that do not fit…", "The version beside the wordmark…", and the "Navigation, not action" lead-in.
- **P3-6. Stale docs and lessons.** These still describe the left and right rails and the header bar:
  - README §2 (lines 213-221), and lines 41, 431, 496, 2712, 2721, 2869, 3372 and 3653;
  - `docs/learn/modules/10-navigate.md`, `11-projects.md` and `13-access-privacy.md`.

  The TODO row "Document phase for the Manuscript shell" already covers this, so it is not a blocker. Close it before the owner sees a native render.
- **P3-7. `ui/dialogs.py:387,401`.** Cancel in Settings restores the theme but not "Show tooltips" or "Reduce motion", which save as soon as they are toggled. Decide whether that is intended, and if so say it in the dialog.
- **P3-8. `services/usage_tracker.py:154`.** No production caller passes `price_known=False` (grep), so only the token path flags unknown prices. Per-unit paths with an unknown price are the deferred follow-up named in ADR decision 5; track it.
- **P3-9. `main.py:3776,3792`.** `top_bar.fitter.fit()` runs on every 1 s resource tick through `refresh_status_chip`. It re-sets the bar's margins and re-measures six levels each time. Guard it on a changed state or width.
- **P3-10. `tests/test_shell_inventory.py` `_home`.** A control that is hidden inside a popover still counts as "one click away" whenever the opener is visible. The test does not check that the control would actually show.
- **P3-11. `tests/test_routing_phase1.py:_amber_pixels`.** The detector was widened from one RGB box to hue 15-50, saturation > 0.45 and value > 0.3. The light look justifies it, but it is looser and can pass on orange pixels that are not the tag. Tighten it with a negative control.
- **P3-12. `ui/learning_center_v2.py:561` and `ui/docs_center.py:391`.** `Qt.gray` is a fixed colour outside the tokens, about 2.6:1 on white. `test_colour_literals` does not catch named colours.
- **P3-13. `main.py:2742-2747` and `ui/status_cards.py`.** `refresh_status_chip` reads the private `resource_status_card._summary`. Expose a `summary()` method, as `ApiKeysStatusCard` already has.

## Checked, no finding

- **Dark looks unchanged.** `global_stylesheet()` for green, red and blue, `main` against HEAD:
  - No rule changed except the two asset URL paths in the scratch copy.
  - 22 rules were removed and 43 added: retired chrome and new shell rules.
- **Theme swap:**
  - `_build_swap` raises on an ambiguous authored literal, and it imports cleanly, so none exists.
  - `recolour` is single-pass, longest literal first.
  - `WARNING_DOT` is excluded from the swap and read only through `token()`.
  - The contrast tests cover all six palettes. The dark gaps are `xfail(strict=True)` and listed in TODO.
- **Money:**
  - `cost_eur` is unchanged for unpriced rows; totals, caps and the guard are untouched.
  - `price_row_found` uses the same `resolve_price_row` as `calculate_cost_eur`, which already excludes zero-rate rows.
  - `CLOUD_BACKENDS` covers every cloud entry in `providers.REGISTRY`.
  - The `capped` update in `record_job_item` cannot overwrite an unpriced row, because that row's cost is 0.
  - `test_usage_unpriced` and `test_shell_chips` pass.
- **Budget commit on close:**
  - `_commit_budget_limits` is idempotent and guarded by `_committing_budget`.
  - Both `editingFinished` and the popover's `closed` call it; the second call is a no-op.
- **Motion rules:**
  - All motion goes through `ui/motion.animate`: at most 300 ms, one loop, and applied at once under Reduce Motion or while someone types elsewhere.
  - A reopen in the middle of a close leaves the drawer open.
  - Stopped animations leave `running()`.
  - The diff adds no `setStyle`, no `QThread.terminate` and no new `QThread`.
  - The `ctypes` read of macOS Reduce Motion ran on this Mac without raising and returned False. The True case is not verified.
- **Keyboard:**
  - With real `QTest` Tab events, focus stayed inside the drawer over eight Tabs.
  - Esc in the search field closed the drawer.
  - The tests call `focusNextPrevChild` directly, but the real path works too.
- **Popover lifetime:**
  - Its `applicationStateChanged` connections are bound methods of QObjects, so they disconnect when the popover is destroyed.
  - It is parented to the window.
  - The conftest fixture closes leftover popups and stops animations.
- **Conftest retirement fixture:**
  - It runs at module start, before the module's own fixtures.
  - There is no session-scoped `GodAI`, so it cannot retire a window that is still in use.
  - It catches `RuntimeError`.
- **Re-homing:**
  - Handlers and attribute names resolve.
  - `help_map` targets and Show me links resolve (`test_learning_center`).
  - `QAction` anchors work.
  - `tooltips_toggle_btn` as a `QAction` keeps `isChecked`, `setText` and `toggled`.
- **No new xfail** outside the documented dark-contrast gaps. The skips are for missing ffmpeg or a missing price row.

## Verdict

**One P1 (P1-1), no P0.**

- P1-1 is display only, but it sits in a risk the spec names. Under the Definition of Done it must be fixed, or explicitly deferred by the owner, before merge.
- The four P2s should be fixed in this PR or carried as TODO rows.
- P2-2 and P2-3 belong together as one change: fix the sleep-timer loss, and add assertions for position, playing state and the exception path.
