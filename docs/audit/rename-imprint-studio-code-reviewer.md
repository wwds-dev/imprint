# Code review: rename-imprint-studio

**Verdict: merge after fixes.** The rename is correctly scoped and no state moves. One mechanical merge blocker (R-1), one router regression that affects every codename (R-2), and one stale README claim (R-4) should be fixed first.

**Counts:** P0: 0 · P1: 1 · P2: 3 · P3: 7

Reviewed: Imprint `claude/rename-imprint-studio-2e6787` at `e4dc7f7` (6 commits, 98 files, base `main`); Lab Hub `claude/rename-imprint-studio` at `9e12b33`. Playbook `docs/playbooks/code-reviewer.md`: `status: current`, `last-reviewed: 2026-10-14` (39 days, not stale). Read-only; both worktrees were clean after the test runs.

Worktrees:
- `/Users/as/Documents/lab/active/imprint/.claude/worktrees/nostalgic-ellis-342115`
- `/Users/as/Documents/lab/active/lab_hub/.claude/worktrees/rename-imprint-studio`

## Findings

### R-1 · P1 · `TODO.md` conflicts with `main`
- **Where:** `TODO.md:110` on the branch (conflict at line 112 of the merged file).
- **Evidence:** `git merge-tree --write-tree main HEAD` reports `CONFLICT (content): Merge conflict in TODO.md`. `main` moved on by three commits (`d948f6e`, `376616b`, `148f462`). Commit `376616b` changed this row's category from `test` to `testing`; the branch changed "Stamp" to "Vector" on the same line.
- **Why it matters:** The branch cannot merge cleanly. Taking the branch side brings back the off-legend category `test`, which the Lab Monitor reads.
- **Fix:** Merge or rebase onto `main`; resolve the one line as `` `P1` `testing` `@me` … Sitebuilder and Vector … ``.

### R-2 · P2 · The router guard drops addressing for every codename, not just the three new ones
- **Where:** `agents/router/agent.py:92-104` (`_CONNECTORS`, `_ends_the_name`).
- **Evidence:** A name followed by any word outside the 13-word allow-list is no longer an address. The same probe run on `main` (old names) and on the branch:

  | Input | `main` | Branch |
  |---|---|---|
  | "open Booth again" | audiobook, addressed | chat, fallback |
  | "use Quill on chapter 3" | author, addressed | chat, fallback |
  | "use Herald today" | social, addressed | chat, fallback |
  | "go to Press first" | manuscript, addressed | chat, fallback |
  | "open Nova mode" / "again" / "quickly" | creator, addressed (as Muse) | chat, fallback |
  | "use nova what should I post on reddit" | creator, addressed (as Muse) | **social**, intent |

- **Why it matters:** The spec allows "no behaviour change except one router guard (R3)", and R3 only lists sentences that must stay unaddressed. The guard regresses explicit addressing for the ten agents whose names did not change. No test pins an unchanged codename with a trailing word. `docs/agents/router.md:23-27` still says an opening verb is enough.
- **Fix:** Widen `_CONNECTORS` with common followers ("again", "on", "today", "first", "mode", "about", "in", "what", "quickly", "my", "a"). Add positive tests for Booth, Quill, Herald and Press with trailing words. Add one sentence to `router.md` describing the rule. Alternatively, invert the guard to a short deny-list of nouns (voice, file, files, graphics, extension, panic).

### R-3 · P2 · The guard still lets through modifier uses via punctuation and connectors
- **Where:** `agents/router/agent.py:102` (any non-space character ends the name) and `:92-95` (the connector list).
- **Evidence:** These all return `addressed` on the branch:
  - "use vector-based artwork", "use vector and raster formats", "use vector for print, not png", "use vector to scale without loss", "switch to vector for the logo files" → fiverr
  - "use nova-voice for the narration", "use nova's voice" → creator
  - "open kernel.log", "use kernel to manage memory" → chat
- **Why it matters:** This is the same class R3 was written to stop ("use vector files"). Auto Route switches the workspace to Vector or Nova for a file-format or voice question.
- **Fix:** In `_ends_the_name`, accept end of text or sentence punctuation (`[,.!?;:]` followed by space or end), and treat `-`, `'` and `.` followed by a word character as part of a longer word. Add these sentences to `test_an_ordinary_word_is_not_an_address`. The "and/for/to" cases are an accepted trade-off of the connector list, or covered by the deny-list in R-2.

### R-4 · P2 · README still says the prompt asks for a vector-like, transparent logo
- **Where:** `README.md:1190` (section 7.2, Tips & Limitations).
- **Evidence:** It reads "The image prompt asks for a vector-like logo, transparent background and no text". The prompt now says "flat logo, clean edges, plain white background, no text" (`agents/fiverr/agent.py:39`), and `docs/agents/fiverr.md:44` says "No transparent background".
- **Why it matters:** The user doc contradicts the code and the sheet on the exact claim QM-18 was closed for.
- **Fix:** Replace the line with the sheet's wording (flat logo on a plain background; raster output; trace before delivery).

### R-5 · P3 · The "ordinary word" example was damaged by the replacement
- **Where:** `docs/agents/router.md:21`, `agents/router/README.md:56`, `tests/manual_test_cases.md:204-206`.
- **Evidence:** `router.md` now says a bare match would send `"stamp the document" to Vector`. "Stamp" is no longer a codename, so the example illustrates nothing. Manual Test E expects "stamp the document and send it" not to go to Vector.
- **Fix:** Use a sentence with the new word, such as "vector graphics for the flyer" or "kernel panic on my Mac", in all three places.

### R-6 · P3 · "Every image route returns a raster PNG" is not shown by the code
- **Where:** `docs/agents/fiverr.md` (Deliberate limitations); comment at `agents/fiverr/panel.py:206-207`.
- **Evidence:** The `generate_image` docstring at `services/image_generation.py:74` says "encoded bytes (PNG or JPEG)". The Gemini and Qwen routes return whatever the provider sends. `ui/workers.py:288` writes the bytes to `logo_N.png` without checking.
- **Why it matters:** "Not vector files" holds. "PNG" is only guaranteed by the file name.
- **Fix:** Say "raster images (saved as .png)" in the sheet, or convert to PNG on save in a later change.

### R-7 · P3 · The vector-file ban only sits inside the gig description
- **Where:** `agents/fiverr/agent.py:29` (item 4 of GIG DESCRIPTION); the DELIVERY MESSAGE section at `:15` has no such line.
- **Evidence:** A delivery message describing "what was delivered" can still promise SVG or source files. The test only checks that the phrase exists somewhere in the system prompt.
- **Fix:** Move "The images are PNG files: never promise vector files" to the persona line at the top, beside the no-invented-record sentence.

### R-8 · P3 · `build_app.sh` skips its own cleanup when the old app will not quit
- **Where:** `scripts/build_app.sh:80-90`.
- **Evidence:** `retire_old_bundle` returns 1 on a quit timeout. Under `set -e` the script exits before `lsregister -u "$DIST_APP"` and `rm -rf "$DIST_APP"`. The script's own comment (`:85-89`) says that leftover copy is what Spotlight keeps offering.
- **Fix:** Call `retire_old_bundle` after `rm -rf "$DIST_APP"`.
- **Related:** Neither script checks that the new bundle launches before removing the old one (no `--selftest`); acceptable, since the old one can be rebuilt from git.

### R-9 · P3 · Leftover and half-renamed names
- `docs/learn/modules/12-best-fit.md:158-159`: "Vector (Client / Gigs)" keeps the retired name. The T5 check misses it because the name wraps across two lines.
- `SUGGESTIONS.md:22` (#65, open): title says Nova, body still says "Muse exports … hand Muse a".
- `TODO.md:137` (open): "miss main Kernel (Assistant) … Chat's in-flight request".
- `tests/READINESS_GATE.md:19,38,39,65,94`: untouched, still has **Stamp** and **Muse** rows. The spec counted `tests/*.md` (gate included) in scope. Either rename it or record it as a dated document.
- `docs/projects_roadmap.md:194`: "Muse's Calendar and Media tabs".
- `agents/creator/calendar.py:1`: "the Nova's content plan" (grammar); `agents/catalog.py:98` comment still lists "Muse".
- **Fix:** Edit each; make T5 collapse whitespace before matching.

### R-10 · P3 · Package 5 is ticked done with part of its scope moved out
- **Where:** `TODO.md:74` (ticked) and `TODO.md:75` (new open P2 row); `tests/test_docs_integrity.py:34-43`.
- **Evidence:** The ticked row's text includes "lesson and sheet titles equal to the catalog labels". Sixteen titles still fail that and stay as strict xfails.
- **Why it matters:** It is disclosed, and the xfail reasons are accurate, but deferring part of an approved package is the owner's call.
- **Fix:** Owner confirms the deferral. Rename the helpers still called `_package5` and `_T5_PACKAGE_5_FILES`, which now mark non-rename cases.

### R-11 · P3 · Measure 1(a) is checked statically for the sub-windows
- **Where:** `tests/test_display_names.py:47-74`.
- **Evidence:** The Documentation, Learning Centre and Income Lab titles and the menu-bar name are only checked for "no literal old name" by an AST scan. A title that dropped the app name would pass. `_NAME_SOURCES` uses `ui/*.py`, not `rglob`. `_RENAME_NOTE` (`:226`) exempts any line containing "renamed" or "formerly"; today it only exempts `README.md:1086,2205`.
- **Fix:** Assert `APP_DISPLAY_NAME in dialog.windowTitle()` for the three dialogs (offscreen); use `rglob`.

## Checked and found sound

1. **Scope.**
   - Unchanged: `APP_NAME`, `DB_PATH`, `SINGLE_INSTANCE_KEY`, both `QSettings("Imprint", "Imprint")`, the bundle id (`Imprint.spec:154`, `install_app.sh:84`), catalog keys, package names and the launch-log path. No schema or settings-key change.
   - `APP_DISPLAY_NAME` (`services/runtime_paths.py:32`) feeds the window title, wordmark, tray, version tooltip, menu-bar name, three sub-window titles, the self-test line and the bundle keys. No remaining `"Imprint"` literal on a name surface. There is no About dialog.
   - "Open in Imprint" and "Chat routing" are kept under D2 and logged at `TODO.md:78`.
2. **Labels.**
   - The catalog, three recommendation profiles, DB seed, `registry.json`, both manifests and `main.py:2607` (now read from the catalog) agree.
   - `_sync_agent_labels` (`services/database.py:966`, not changed by this branch) runs after table creation and seeding (`:755-757`). It is idempotent and makes about ten keyed UPDATEs. It is the only writer of `label`, so there is no user data to overwrite.
   - "Publisher" → "Press" in the seed is correct: the catalog says Press, and existing databases already had it from the sync.
3. **Router tests.** Both directions are covered for the new names. No router test was deleted or loosened; the D4 no-alias test was added.
4. **Old-bundle removal.**
   - The only `rm` is the literal `rm -rf -- "/Applications/Imprint.app"`.
   - A symlink or a missing directory returns early. An unreadable plist or a foreign bundle id leaves the bundle in place.
   - A quit timeout returns 1 before the `rm`.
   - It runs after `cp`, `codesign` and `lsregister` of the new bundle, so a failed install exits first under `set -e`.
   - Quoting is correct with the space in the name. `bash -n` passes on all three scripts.
   - The bundle on this Mac has id `com.netrunner3000.imprint`, so the check will match.
5. **Vector prompt.** The removal of "5-star" and fixed prices is accurate. The panel line equals `PNG_NOTE` (test passes). The sheet, lesson 27 and README 7.2 carry the PNG sentence. See R-4, R-6 and R-7 for the gaps.
6. **Tests.**
   - No test file or function was deleted.
   - The 14 removed xfails are 3 T9, 5 T5, 4 T6, 1 T4 and 1 README test. All now pass for real.
   - The 17 remaining are 15 T6, 1 T5 and 1 T4 (R-3 drift), with reasons that match.
   - The `test_app_launcher.py` assertion is the same strength; only the variable name changed.
7. **"Muse Glimmer".** Intact: 29 occurrences on `main`, 30 on the branch (the extra one is in the new test). No user-doc hit for `Muse` or `Stamp` outside the two "named … until 2026-11-22" lines.
8. **Repo rules.** No `/Users/` path added. Nothing under `docs/legal`, `vidforge/` or the shared copies was touched (converter, `services/benchmarks.py`, `app_launcher.c`, `appkit_guard.py`, `app_identity.py`, routing files). No secret pattern in the diff.
9. **Lab Hub.** The only change is `lab_hub/apps.toml:40` name → "Imprint Studio". Every use of `app.name` in a path or shell command is quoted. `tests/test_launcher.py` passes (123).

**Tests run** (Imprint worktree, main checkout's venv):
- `test_display_names`, `test_docs_integrity`, `test_agents_scenarios`, `test_app_launcher`, `test_tray`, `test_retired_names`, `test_benchmarks_drift`, `test_database_migrations`, `test_cost_and_limits`: 601 passed, 2 skipped, 17 xfailed.
- Three `test_panel_layout` cases (title and wordmark, PNG note, Assistant title): 3 passed.
- `test_check_setup`, `test_runtime_paths`, `test_api_keys`, `test_creator_calendar`, `test_env_template`: 93 passed, 2 skipped.

## Not verified
- The full Imprint suite and the full Lab Hub suite; the rest of `test_panel_layout.py`; `test_converter_drift.py` and `test_providers_drift.py` (their files are untouched).
- Running `install_app.sh`, `build_app.sh` or `retire_old_bundle` for real: the launcher compile with the spaced name, a PyInstaller build with `name="Imprint Studio"`, the quit-and-remove path, Dock, Cmd-Tab and Activity Monitor names, and the macOS permission re-prompt.
- shellcheck (not installed).
- The new "Deliberate limitations" rows for Kernel and Nova against the code (they cite audits QM-2, QM-4 and QM-9).
- Learning Centre modules other than 02, 12, 17, 18, 19, 26, 27 and 28, beyond the leftover-name greps.
- Whether other lab tools (Lab Monitor, Backup Control Center) reference `/Applications/Imprint.app`.
- CI status on GitHub.
