# Code review recheck: rename-imprint-studio, 2026-11-24

Role: code-reviewer (read-only), a different session from the author. Playbook `docs/playbooks/code-reviewer.md`: `status: current`, `last-reviewed: 2026-10-14` (41 days, not stale).

Scope: is each finding of `docs/audit/rename-imprint-studio-code-reviewer.md` fixed, deferred in writing or still open, and did the fix commits (`f1352fe`, `28a38fb`, `83d9243`, `6e5dce2`, `cd88010`, `d3a6973`, with `e4dc7f7` before them) add anything new. Special attention to the router guard, `scripts/retire_old_bundle.sh` and the `APP_NAME` invariant. Not a new review of the whole rename.

Reviewed: branch `claude/happy-dubinsky-48c27c` at `e79f696`. `git diff 785610b..HEAD` is empty for `agents/router`, `scripts`, `services/runtime_paths.py`, `Imprint.spec`, `tests/test_display_names.py` and `tests/test_agents_scenarios.py`, so the reviewed files are as the fix round left them.

The earlier report lists R-1 to R-11. There is no R-12 for this spec (an R-12 exists only in the docs-learning-centre-readiness review).

## Verdict

**No fix needed before release from this review.** The one P1 and the three P2 are fixed, R-3 with a limit that is written down. All seven P3 are fixed or recorded. The old-bundle removal can only delete `/Applications/Imprint.app`, only with this app's bundle id, and stops when a copy is seen running. `APP_NAME` and the data folder are unchanged. Open: Verify and Secure have not run for this spec (RR-1), and five small P3 points.

**Counts:** P0: 0 · P1: 0 · P2: 1 · P3: 5

## Findings

### RR-1 · P2 · Merged and installed before Verify and Secure ran
- **Where:** `docs/specs/rename-imprint-studio.md:3` ("Needs: design, architect, build, review, verify, secure, docs, comply, release"); `docs/foundry/activity.jsonl:128-147`; `docs/audit/`.
- **Evidence:** the activity log holds define, build and review entries for this spec and no verify or secure entry. `ls docs/audit | grep rename` lists the code-reviewer report only. The fix commits are on `main`, and `TODO.md:81` records the real install on 2026-11-23.
- **Why it matters:** the change adds a script that deletes an app bundle and changes packaging; AGENTS.md asks for Secure on file writes and packaging, and the Definition of done asks for the suite in every mode and a mutation check. The removal logic has no executed test (RR-4), so the QA and security passes are the only place it would be exercised.
- **Fix:** run Verify and Secure on today's tree before Release; both reports go to `docs/audit/`.

### RR-2 · P3 · The guard still takes a name as an address when other punctuation joins it to the next word
- **Where:** `agents/router/agent.py:110-114`.
- **Evidence:** probe run on this branch (`RouterAgent().route`):

  | Input | Result |
  |---|---|
  | "use vector/raster formats" | fiverr, addressed |
  | "use vector (svg) files" | fiverr, addressed |
  | "use vector+raster" | fiverr, addressed |
  | "use vector: svg" / "use vector, files" | fiverr, addressed |
  | "use kernel/module docs" | chat, addressed |
  | "use nova… voice" / "use nova`s voice" | creator, addressed |

  Line 110 treats only `-`, `'`, `’` and `.` followed by a word character as part of a longer word; line 113 lets any other non-space character end the name.
- **Why it matters:** the same class as R-3 (a file-format or voice question switches the workspace), in rarer spellings. No money moves: the request still goes through the guard. `docs/agents/router.md:35` says "nothing, or punctuation" ends the name, so the sheet matches the code.
- **Fix:** end the name only on end of text or on `[,.!?;:]` followed by a space or the end; treat `/`, `+`, `(` and a backtick followed by a word character like the hyphen. Add the rows above to `test_an_ordinary_word_is_not_an_address`.

### RR-3 · P3 · "Not running" is decided from the command line only
- **Where:** `scripts/retire_old_bundle.sh:18`, `:33`, `:40`, `:43`.
- **Evidence:** `pgrep -f "/Applications/Imprint\.app/Contents/MacOS/"` matches the text of a process's arguments. A copy started through a relative path (`cd …/MacOS && ./Imprint`) is not matched, and macOS `pgrep` leaves out its own ancestors, so a script started from inside the old app would not see it. No such caller exists today (grep for `install_app`, `build_app`, `retire_old` in `main.py`, `ui/`, `services/`, `agents/`: only a hint text in `services/version.py:181`). The pattern is not anchored, so a copy under another folder that ends in `/Applications/Imprint.app` is asked to quit as well.
- **Failure:** old app started by relative path, then `install_app.sh`: the bundle is removed while that copy runs. For the live launcher this is harmless (the bundle holds only the launcher); for an old frozen bundle the running copy can fail on its next lazy import. User data is outside the bundle in both cases.
- **Fix:** none required for this one-time migration; if wanted, also ask `lsappinfo` or `NSRunningApplication` for bundle id `com.netrunner3000.imprint` with the old bundle path.

### RR-4 · P3 · The removal helper is tested as text, never executed
- **Where:** `tests/test_display_names.py:327-348`.
- **Evidence:** the test asserts the one `rm` line, the bundle id string, the `-L` check and the call order. The branches "foreign bundle id: leave in place" (`scripts/retire_old_bundle.sh:27-30`) and "still running: return 1, delete nothing" (`:43-46`) are not run by any test. The real run of 2026-11-23 (`TODO.md:81`; `/Applications` holds only `Imprint Studio.app` today) exercised the plain path once.
- **Fix:** acceptable as is, because the fixed path is the safety property and a test cannot run it without touching `/Applications`. QA can run the two branches by hand with a dummy `/Applications/Imprint.app` that carries another bundle id.

### RR-5 · P3 · R-10's deferral names the owner, but no record of the owner's words was found
- **Where:** `TODO.md:78-79` ("the owner moved them out of package 5 … review R-10, 2026-11-22").
- **Evidence:** `docs/foundry/approvals.jsonl` has one entry for this spec (the Define gate, line 7). Nothing else quotes the owner on this point.
- **Fix:** the owner confirms once, or the row says who decided.

### RR-6 · P3 · `build_app.sh` still stops a running copy with a kill (older than the rename)
- **Where:** `scripts/build_app.sh:64` (`pkill -f "${APP_BUNDLE}/Contents/MacOS"`).
- **Evidence:** `scripts/install_app.sh:93-97` explains why it asks the app to quit instead: "closeEvent is where the manuscript is saved and the worker threads are stopped, and a SIGTERM skips it." `main.py` installs no SIGTERM handler (grep). The rename only changed the pattern through `APP_BUNDLE`. Whether unsaved text is in fact lost was not run.
- **Fix:** use the same quit loop as `install_app.sh:98-111` in `build_app.sh`.

## Earlier finding -> status

| ID | Was | Status | Where it is fixed | Test |
|---|---|---|---|---|
| R-1 | P1, `TODO.md` conflict with `main` | fixed (`f1352fe`) | `TODO.md:117` keeps `testing` with "Sitebuilder and Vector"; no conflict markers; merged to `main` | n/a |
| R-2 | P2, guard dropped addressing for every codename | fixed (`28a38fb`) | `agents/router/agent.py:83-85`, `:95`: only `chat`, `creator`, `fiverr` are guarded; `docs/agents/router.md:30-44` describes the rule | `tests/test_agents_scenarios.py:217-230` (Booth, Quill, Herald, Press, Reel, Sitebuilder with a trailing word) |
| R-3 | P2, modifier uses pass via punctuation and connectors | fixed for `-`, `'`, `’`, `.`; connectors written down as an accepted limit; other joiners open (RR-2) | `agents/router/agent.py:105-115`; `docs/agents/router.md:46-50` | `tests/test_agents_scenarios.py:172-176`, `:199-207`, `:209-215` |
| R-4 | P2, README promised a vector-like transparent logo | fixed (`83d9243`) | `README.md:1192` | docs integrity suite passes |
| R-5 | P3, damaged "ordinary word" example | fixed | `docs/agents/router.md:21`; `agents/router/README.md:56`; `tests/manual_test_cases.md:204` | n/a |
| R-6 | P3, "raster PNG" not shown by the code | fixed | `docs/agents/fiverr.md:43` ("a raster image (saved as `.png`)"); `agents/fiverr/panel.py:206-207` | n/a |
| R-7 | P3, vector-file ban only in the gig section | fixed | `agents/fiverr/agent.py:7` (persona line) | `tests/test_agents_scenarios.py:531`, `:540` |
| R-8 | P3, `build_app.sh` skipped its cleanup on a quit timeout | fixed (`6e5dce2`) | `scripts/build_app.sh:86` before `:92-93` | `tests/test_display_names.py:344-348` |
| R-9 | P3, leftover names | fixed | `docs/learn/modules/12-best-fit.md:157-159`; `SUGGESTIONS.md` and `TODO.md` (no hit left); `tests/READINESS_GATE.md:13-14` marks it a dated record; `docs/projects_roadmap.md` (no hit); `agents/creator/calendar.py:1`; `agents/catalog.py:98` | `tests/test_docs_integrity.py:460` matches names across line breaks |
| R-10 | P3, package 5 ticked with scope moved out | reworded and deferred in writing; owner's words not found (RR-5) | `TODO.md:78-79`; helpers renamed at `tests/test_docs_integrity.py:42`, `:494` | 17 strict xfails remain, with their own reason |
| R-11 | P3, sub-window titles checked statically | fixed | `tests/test_display_names.py:49-50` (`rglob`), `:98-111` (three live titles) | same. Note: the rename-note exemption at `:286` grew by two phrases ("was called", "until 2026-11-22") instead of shrinking |
| `cd88010` | tooltip named the retired "Client Gigs" | fixed | n/a | `tests/test_display_names.py:127-134` |

Router behaviour that stays, by decision in the sheet (`docs/agents/router.md:39`): Kernel, Nova and Vector do not address when a word outside the 13 connectors follows. Probe: "open Nova again", "use Kernel today", "go to Vector first" -> chat, fallback. No test pins this direction.

## Checked and found sound

1. **Router guard.** Only the three keys in `_GUARDED_KEYS` (`agents/router/agent.py:95`) go through `_ends_the_name`; every other codename addresses after an opener as before. Probe: "use vector files", "use the nova voice", "kernel panic on my Mac", "open kernel.log", "use nova's voice", "use vector-based artwork", "use VECTOR FILES", "use vector\nfiles", "use vectors", "use kernel 6.1" are all not addressed. "open Nova", "use Vector", "Nova", "vector!", "open Kernel please", "open Nova and draft a campaign" are addressed. "open Muse", "use Stamp", "open Chat" are not addressed (no aliases, spec D4).
2. **Old-bundle removal** (`scripts/retire_old_bundle.sh`).
   - Exact path: the only `rm` is `rm -rf -- "/Applications/Imprint.app"` at `:49`, a literal. No variable, glob or computed path reaches it.
   - Symlinks: `:21` returns early for a symlink or a missing directory. If the path became a symlink between the check and the `rm`, `rm -rf` on a path without a trailing slash removes the link, not its target, and never follows links inside a tree.
   - Bundle id: `:25-30` reads `CFBundleIdentifier` with PlistBuddy; an unreadable plist gives an empty id, which is not `com.netrunner3000.imprint`, so the bundle is left in place.
   - Running copy: `:33-37` asks each match to quit through `NSRunningApplication.terminate` (the app's own Quit path, not a signal); `:39-46` waits 20 s and returns 1 before the `rm` if one is still there. Limits in RR-3.
   - Quoting: `$old`, `$running`, `$lsreg` are quoted at every use; `${pid}` comes from `pgrep` (digits). `bash -n` passes on all three scripts.
   - Order: `scripts/install_app.sh:113-124` and `scripts/build_app.sh:66-93` remove the old bundle only after the new one is copied, signed and registered; under `set -e` a failed install stops first. `build_app.sh --no-install` exits before it.
   - Other deletions in the two scripts: `rm -rf "$INSTALLED"` (a constant path, quoted), `rm -rf "$DIST_APP"` (under the project's `dist/`), `rm -rf "$STAGE"` (from `mktemp -d`). `set -u` is on.
3. **`APP_NAME` and state.** `services/runtime_paths.py:27` is still `"Imprint"`; the only change to that file in the range is the new `APP_DISPLAY_NAME` at `:32`. The data folder is built from `APP_NAME` (`:80`, `:112`). `APP_DISPLAY_NAME` is used for titles, the tray, the wordmark, the menu-bar name and the version line only (grep: `main.py:247`, `:2387`, `:6565`, `:6662`; `ui/tray.py`; three dialogs; `services/version.py:188`), never in a path. No `setApplicationName`, `setOrganizationName` or `QStandardPaths` call exists. `QSettings("Imprint", "Imprint")` (`ui/docs_center.py:141`, `ui/learning_center_v2.py:314`), `SINGLE_INSTANCE_KEY` (`main.py:6525`) and the bundle id (`Imprint.spec:154`, `scripts/install_app.sh:84`) are unchanged. Pinned by `tests/test_display_names.py:149-163`. `APP_NAME="Imprint"` in `scripts/build_app.sh` is used only to print the `.env` path.
4. **Repo rules.** No `/Users/` path in the three scripts. Nothing under `docs/legal` was read or touched by this recheck.

## Tests run (this worktree, main checkout's venv)

- `tests/test_display_names.py`, `tests/test_agents_scenarios.py`, `tests/test_docs_integrity.py`: 583 passed, 17 xfailed.
- Router probe through `RouterAgent().route` (read-only, results quoted above).
- `bash -n` on `scripts/retire_old_bundle.sh`, `scripts/install_app.sh`, `scripts/build_app.sh`: no errors.
- The worktree was unchanged after the runs (`git status`: only `docs/foundry/activity.jsonl`, modified before this recheck started).

## Not verified

- The full suite (a full run was in progress in this worktree; not started here).
- Running `install_app.sh`, `build_app.sh` or `retire_old_bundle` (not allowed in this recheck): the quit-and-remove path, the foreign-bundle-id branch, the still-running branch, and a PyInstaller build with `name="Imprint Studio"`.
- Dock, Cmd-Tab and Activity Monitor names; the macOS permission prompt after the bundle path changed; that the data in `~/Library/Application Support/Imprint/` is intact after the real install (`TODO.md:81` lists that check as still open).
- shellcheck (not installed).
- Lab Hub's side of the rename.
- Whether a kill of the running app loses unsaved text (RR-6).
- R-4, R-6 and R-9 beyond the lines cited; no new scan for old names was written, the existing tests were relied on.
- CI status on GitHub.
