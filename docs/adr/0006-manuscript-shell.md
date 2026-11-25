# ADR 0006: The Manuscript shell (icon rail, top bar, popovers, light look)

Status: **Accepted** by the owner at the Architect gate, 2026-11-25 ("Approve as recommended",
including AO1 to AO3 as recommended); proposed by architect the same day. Spec: `docs/specs/manuscript-redesign.md`, sections "Design (slice 1)" (S1–S11,
approved 2026-11-25) and "Architecture (slice 1)" (A1–A10, this ADR's summary and test plan).

## Context
Slice 1 replaces the window's chrome. Today that chrome is built in `main.py`: `build_header_bar`
(`:2499`, a `QTabBar` of workspaces with `HeaderFitter`'s More overflow, `ui/header_fit.py`),
`build_workspace_description` (`:2479`), `build_left_panel` (`:2619`) and `build_right_panel`
(`:3502`). The approved Design moves every control in those into an icon rail, a top bar, two
popovers, one menu and a drawer, keeps every attribute name, handler, tooltip and help entry, and
adds a light look as the default.

Facts this decision rests on (read 2026-11-25):
- **Theme mechanism.** `ui/style.py` holds the authored dark-green values as module constants.
  `global_stylesheet()` formats the template with those constants overlaid by
  `ui.theme.palette()` (`ui/style.py:1036-1057`), so any token present in a palette is themed in
  the main sheet. Hand-built sheets and painter code go through `theme.recolour()`, which swaps
  the authored green literals (`_SWAP`, `ui/theme.py:126-133`); `themed()`/`repaint()` re-apply
  them on a change. `BORDER`, `BORDER_STRONG`, `DANGER`, `WARNING`, `INFO` and their washes and
  lines are in no palette, so they never change, and the module docstring says so.
- **Literals outside the tokens.** 48 colour literals sit outside `ui/style.py`/`ui/theme.py`
  (`ui/widgets.py:568-599`, `ui/status_cards.py:87`, `ui/dialogs.py:274-277`,
  `ui/routing_advice.py:19-22`, `agents/manuscript/panel.py:476,537,678,974`, `main.py:1031,
  6578-6677`). On a dark window they pass; on white they are dark boxes or invisible lines.
- **Unpriced requests.** `UsageTracker.calculate_cost_eur` returns `0.0` when no price row
  resolves (`services/usage_tracker.py:133-134`) and `log_request` stores that `0.0` with the
  token `cost_type` (`exact`, `mixed`, `estimated`). Nothing records that the price was unknown,
  so "€0.00 today" can hide a paid request today. The spend chip may not infer "unknown" from a
  zero (Design S6, app invariant).
- **Help lessons.** `spotlight.reveal()` (`ui/spotlight.py:31`) switches stacks and tabs above a
  target and scrolls to it. It knows nothing of popovers or drawers. `spotlight()` calls
  `target.window()`, so a `QAction` target (today `new_project_btn`, linked from
  `docs/learn/modules/19-assistant.md:113`) raises `AttributeError`: a pre-existing bug.
- **Reduce Motion.** Qt has no API for it (QTBUG-133042). PyObjC is not installed; `ui/appkit_guard.py`
  already reaches AppKit through `ctypes` and `libobjc`. The value is
  `NSWorkspace.sharedWorkspace.accessibilityDisplayShouldReduceMotion` (macOS 10.12+) and can be
  stale unless re-read (radar note `docs/foundry/radar-notes/2026-11-25-stack-manuscript-shell.md`).
- **Popovers on macOS.** A `Qt.Popup` widget takes all mouse and key input while open; a
  `QLineEdit` inside one gets no right-click menu on macOS (QTBUG-133560). `QLineEdit` does not
  reliably emit `editingFinished` when its popup closes. `appkit_guard.install()` swizzles
  `-[NSEvent clickCount]` process-wide (`main.py:6965`), so every `QMenu` is covered once it runs.
- **The 2026-10-05 deadlock.** `QComboBox.setStyle()` blocked in `QObject::disconnect` against
  FFmpeg threads that leaked from unreleased players (`agents/audiobook/README.md:95-101`).
  `polish_combo` calls `setStyle` once per combo, guarded by a property (`ui/widgets.py:346-348`);
  a theme change calls `setStyleSheet` on the window and `repaint()` on registered widgets, never
  `setStyle`. The header dots have switched themes while Booth plays since 2026-10-06 with no
  report of a hang.
- **Shortcuts.** The window has F1 only (`main.py:433`). Booth's player binds Space, Left, Right
  with `WidgetWithChildrenShortcut` (`agents/audiobook/audio_player.py:149-154`); the release kit
  binds Escape and Ctrl+. in its own window. None collides with S9.

## Decision
1. **Light is a palette, and semantics become palette keys.** Every palette gains `BORDER`,
   `BORDER_STRONG`, `DANGER`, `DANGER_WASH`, `DANGER_LINE`, `WARNING`, `WARNING_WASH`,
   `WARNING_LINE`, `INFO`, `INFO_WASH`, `INFO_LINE` and the new `WARNING_DOT`. The three dark
   palettes carry today's values (so nothing dark changes, and `_SWAP` holds no pair for them);
   the three light palettes carry Design S8's values. `ui/style.py` keeps its constants as the
   authored values, so `global_stylesheet()` and `recolour()` need no new code path.
   - **`WARNING_DOT` is painter-only.** Its dark value equals `WARNING` (`#fbbf24`), so a literal
     swap cannot tell them apart. It is not added to `ui/style.py`, it is excluded from `_SWAP`,
     and painter code reads it as `theme.token("WARNING_DOT")` (new helper: one token of the
     current palette). The main sheet may still name `{WARNING_DOT}` because the template is
     formatted, not swapped.
   - **`_SWAP` refuses ambiguity.** Building it raises at import if one authored literal would map
     to two values in one palette. That makes a future collision a test failure, not a wrong colour.
   - **Literal sweep.** Every colour literal outside `ui/style.py`, `ui/theme.py` and
     `ui/vibe.py`'s `PHOSPHOR` is replaced by a token (through `recolour`, `themed` or the sheet),
     colour only, no layout change. A guard test fails on a new literal outside an allow-list
     (`webdesign_palette_input`'s placeholder text is data, not a colour). The Markdown viewer in
     `main.py:6578-6677` uses tokens too, as it is a window the user reads in either look.
   - **Docstring.** `ui/theme.py`'s "Semantic colour does not change" paragraph becomes: semantic
     colour keeps its *meaning* in every theme and its *value* within a look; light needs darker
     values to stay readable on white. Settings' `appearance_intro()` says the same.
2. **Theme model: Look × Accent, one stored key.** `LOOKS = (LIGHT, DARK)`,
   `ACCENTS = ("green", "rose", "teal")`. `THEMES` stays the tuple of every stored key, now six, in
   display order: `light-green`, `light-rose`, `light-teal`, `green`, `red`, `blue`. The dark keys
   keep today's strings, so a saved value never becomes invalid. Helpers: `look(key)`,
   `accent_of(key)`, `compose(look, accent)`, `themes_for(look)`. `LABELS` maps each key to
   "Light · Green" … "Dark · Teal"; `LOOK_LABELS` and `ACCENT_LABELS` give "Light", "Dark",
   "Green", "Rose", "Teal". `current()` falls back to `light-green`. The setting stays `ui_theme`.
   - **O2, once.** `theme.adopt_light_once() -> bool`, called in `GodAI.__init__` before
     `build_ui`: if the setting `ui_light_adopted` is absent, then a saved dark key moves to the
     light key with the same accent and the function returns True (show the note); no saved key
     means a fresh install, which already gets light and no note. Either way it writes
     `ui_light_adopted = 1` first, so the switch and the note happen at most once and a later
     choice is never overridden. The note ("Imprint has a new light look. Dark is in Settings >
     General.") is a dismissible line at the top of the content column, not a modal.
   - **Count sentence.** `appearance_intro()` counts `LOOKS` and `ACCENTS` ("two looks, Light and
     Dark, each in three accents: Green, Rose and Teal"), still derived, never typed.
3. **The rail owns `workspace_tabs`.** A new `WorkspaceRail(QFrame)` (`ui/shell/icon_rail.py`) is
   assigned to `self.workspace_tabs`. It implements the part of `QTabBar`'s API the app, tests and
   lessons use: `count()`, `tabText(i)`, `currentIndex()`, `setCurrentIndex(i)`, the
   `currentChanged(int)` signal (emitted only on a change, like `QTabBar`), `elideMode()`
   (`ElideNone`), `isTabVisible(i)` (always True), `setTabToolTip`/`tabToolTip`. The buttons are
   checkable `QToolButton`s in an exclusive `QButtonGroup`. A hidden `QTabBar` driving the buttons
   was rejected: help lessons ring `workspace_tabs`, and a hidden widget has no geometry to ring.
   `_workspace_changed` and `_sync_workspace_navigation` keep their code; the
   `workspace_description_label` write becomes `workspace_tabs.set_description(index, text)`.
   `ui/header_fit.py` and `header_fitter`/`workspace_more_btn` are deleted; the top bar's collapse
   rule (Design S3) lives in `TopBarFitter` (`ui/shell/top_bar.py`), driven by measured size hints
   on `resizeEvent`, like `HeaderFitter` was.
4. **Popovers are `Qt.Popup` frames; menus stay `QMenu`.** `Popover(QFrame)` (`ui/shell/popover.py`,
   window flags `Qt.Popup | Qt.FramelessWindowHint`, parented to the window so `findChild` and
   `_find_control` reach their contents) holds the spend and status content. The project menu and
   the "?" menu are `QMenu`s opened with `exec()`, covered by the process-wide `appkit_guard`; the
   project menu's header is a `QWidgetAction` whose widget holds `active_project_label` and
   `project_meter`, rebuilt only on project change. Popover rules:
   - **Limits commit on close.** `Popover.hideEvent` schedules `_commit_budget_limits` with
     `QTimer.singleShot(0, …)`, so the existing guard against re-entry applies and the invalid-value
     warning never opens inside a hide. `editingFinished` stays connected as today.
   - **Closing.** Escape, a click outside (Qt.Popup does that), and window deactivation
     (`QApplication.applicationStateChanged`), because macOS may not close a popup on a click into
     another window's title bar (QTBUG-30312).
   - **Known limit.** The limit fields have no right-click menu on macOS (QTBUG-133560); ⌘C, ⌘V and
     ⌘A still work. Accepted.
   - **Tests.** A fixture closes `QApplication.activePopupWidget()` after each test, so an open
     popup never captures a later test's input.
5. **Unpriced requests get their own `cost_type`.** `log_request` stores `cost_type = "unpriced"`
   when the backend is a cloud backend and no price row resolved (token path), or when a caller
   passes the new keyword `price_known=False` (default True, so no existing caller changes). `cost_eur` stays `0.0`, so every sum, cap and guard path is byte-for-byte unchanged.
   `UsageTracker.get_unpriced_requests_today()` counts those rows. No schema change: `cost_type` is
   free text, Cost History already shows it as a column, and the database migration test is
   unaffected. `calculate_cost_eur` gains a sibling `price_row_found(backend, model) -> bool` so
   the decision is made once, from the same `resolve_price_row`. Per-unit callers that coerce an
   unknown price to `0.0` today (`agents/creator/panel.py:1734,1769,1846` with `or 0.0`) are
   recorded as a separate P2 follow-up, not changed here: they are agent behaviour, outside slice 1.
6. **Reveal hooks.** `spotlight.reveal()` gains one rule: while walking a target's ancestors, any
   ancestor with a callable `reveal_for_lesson()` is asked to show itself first (outermost first).
   `HistoryDrawer` and `Popover` implement it (open without animation, no focus steal from the
   lesson's callout). `QAction` targets resolve to an anchor widget: the "?" menu's and project
   menu's actions carry `setProperty("lessonAnchor", "<attribute>")` naming the button that opens
   their menu (`help_btn`, `project_menu_btn`); `spotlight()` rings that button and its callout
   reads "In this menu: <action text>". Menus are not opened by a lesson, because `QMenu.exec` is
   modal and would swallow the callout. `help_map.json` keeps every key; no per-target data is
   added.
7. **Motion.** New `ui/motion.py`:
   - `system_reduce_motion()` reads `accessibilityDisplayShouldReduceMotion` through `ctypes`
     (same loader pattern as `appkit_guard`; checks `respondsToSelector:` first; returns False off
     macOS, under `QT_QPA_PLATFORM=offscreen`, or on any failure). It is re-read on
     `applicationStateChanged` to Active, never cached beyond that.
   - `reduced()` = system setting or the in-app setting `reduce_motion` (database, default off).
     Settings shows the in-app toggle checked and disabled, with "macOS Reduce Motion is on",
     while the system setting is on.
   - `animate(target, prop, start, end, ms)` is the only way the shell starts an animation. It
     refuses `ms > 300` and loops, returns None and sets the end value at once when `reduced()`,
     keeps each live `QVariantAnimation` in a registry (`motion.running()`), and stops it on the
     target's `hideEvent` and on `GodAI.shutdown()`. No `QThread`, no `QTimer` loop; the drawer's
     160 ms slide is one `QVariantAnimation` on its x position and the scrim's opacity.
8. **Theme switch with Booth playing.** No new `setStyle` call anywhere in the shell; the switch
   stays `theme.set_current()` then `apply_global_style()`. `polish_combo`'s once-only guard stays.
   A regression test switches through all six themes while an `AudioPlayer` holds a source and is
   playing (or paused, if offscreen cannot play), under a 30 s `pytest.mark.timeout`, so a
   deadlock fails fast instead of wedging the run. If that test or a native check ever hangs, the
   fallback is already a method: `release()` the player (it saves the playhead), restyle, reload
   at the saved position. It is not built pre-emptively.
9. **Window-owned controls.** `tooltips_toggle_btn` becomes a checkable `QAction` owned by the
   window (`toggled` drives `_toggle_tooltips`, which keeps reading `isChecked()` and setting the
   text); Settings' "Show tooltips" toggle binds both ways to it. `agent_docs_btn` and `learn_btn`
   become `QAction`s in the "?" menu with their handlers (`show_agent_docs`,
   `show_learning_center`); `agent_docs_btn`'s text follows the open agent ("Press docs"). F1 keeps
   its `QShortcut`. `settings_btn` is the rail's gear `QToolButton`. `agent_status_pill` becomes
   the `StatusChip` (a `QToolButton`); `update_agent_ui`'s `setText("●  Ready")` becomes
   `refresh_status_chip()`. `live_estimate_label` moves, unchanged, into `normal_panel` as a
   caption under the provider/model row (O1); `update_live_cost_estimate` is untouched.
10. **Module boundaries.** New package `ui/shell/`: `icon_rail.py` (`WorkspaceRail`, app mark,
    stale dot, "?" and gear), `top_bar.py` (`TopBar`, `AgentSwitch`, `TopBarFitter`), `chips.py`
    (`SpendChip`, `StatusChip`, and the pure functions `spend_chip_text(...)` and
    `status_state(...)`), `popover.py`, `drawer.py` (`HistoryDrawer`). They import `ui.style`,
    `ui.theme`, `ui.motion` and Qt only, never `main` or `services`; `main.py` builds the existing
    widgets with their handlers (as today) and places them into these containers. The status
    chip's inputs are values the window already holds (system summary level, API-key card tone,
    a request running, the model-updates count), passed in on the existing 1 s resource tick and
    on each change; nothing new fetches on the UI thread.

## Alternatives considered
- **A second semantic table beside the palettes.** Rejected: two lookups for one token, and
  `recolour` would need a second swap list anyway.
- **Two settings (`ui_look`, `ui_accent`).** Clearer names, but a migration of `ui_theme` and two
  writes per change; one key with dark keys unchanged needs no migration at all.
- **A hidden `QTabBar` behind the rail.** Rejected: lessons ring `workspace_tabs`, and it would be
  two sources of truth for the current workspace.
- **`QMenu` for the spend popover.** Rejected by Design (text fields in a menu), and a `QMenu`
  closes on the first key that is not navigation.
- **A schema column `price_known`.** Rejected: a migration for a value `cost_type` can carry.
- **PyObjC for Reduce Motion.** Rejected: a large new dependency for one boolean that `ctypes`
  reads with the pattern already in the repo.
- **Pause or release Booth on every theme switch.** Rejected as the default: it interrupts
  listening for a hazard that has not been seen outside leaked players; kept as the fallback.

## Consequences
- `ui/theme.py`'s promise changes from "semantic colour never changes" to "semantic meaning never
  changes"; the dark looks are unchanged pixel for pixel.
- Tests that pin the old chrome are rewritten in the Build PR, each named there, none deleted
  silently: `test_panel_layout.py:843-888` (header overflow) becomes the rail and top-bar fit
  tests; `test_side_rails.py`'s placement tests (`:303-340`, `:500-528`) assert the new homes
  (drawer, popovers, menus); `test_version.py:164-167` reads the app mark's tooltip and the About
  line; `test_theme.py` restates "every themed colour differs" and "semantic colour survives" per
  look, and the dots tests open Settings first.
- Every new interactive piece is checked in six palettes; the contrast test is the cost D4 named.
- A pre-existing crash is fixed on the way: "Show me" for a `QAction` target.
- `header_fit.py` is gone; nothing else imports it.
- Reverting slice 1 is a code revert plus deleting the setting `ui_light_adopted`; the `unpriced`
  rows stay valid data (they read as €0.00 with a truthful `cost_type`).
