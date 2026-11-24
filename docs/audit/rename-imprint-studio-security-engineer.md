# Security review: rename-imprint-studio, 2026-11-24

Role: security-engineer (read-only on code). Playbook `docs/playbooks/security-engineer.md`: `status: current`, `last-reviewed: 2026-11-11` (13 days, not stale).

## Scope
Spec `docs/specs/rename-imprint-studio.md`; commits `git log --oneline e538ff4..785610b` plus `a24b2fd`, `bc8f310`, `753ca9b`; reviewed on branch `claude/happy-dubinsky-48c27c` at `d6b72b6` (the scripts, router, `runtime_paths.py` and `Imprint.spec` are as in `785610b`). Surfaces: deleting the old bundle (`scripts/retire_old_bundle.sh`, `scripts/install_app.sh`, `scripts/build_app.sh`), packaging and identity (`Imprint.spec`, the launcher `scripts/app_launcher.c`), the router's codename guard (`agents/router/agent.py`), keys and settings storage. Builds on `docs/audit/rename-imprint-studio-code-reviewer-recheck.md` (RR-1 to RR-6); those findings are referenced, not repeated.

## Verdict
**No P0 or P1.** The removal script can only delete the literal `/Applications/Imprint.app`, only a real directory carrying bundle id `com.netrunner3000.imprint`, and `rm -rf` does not follow symlinks. Nothing under `~/Library/Application Support/Imprint/` or the project folder is touched by any of the three scripts. `APP_NAME`, the bundle id, `QSettings("Imprint", "Imprint")`, the single-instance key and the `.env` path are unchanged, and the app uses no Keychain item, so no key is lost or duplicated. Pasted or manuscript text can at most switch the visible workspace on an explicit Route click; it cannot change the provider or send anything. Five P3 points remain.

**Counts:** P0: 0 · P1: 0 · P2: 0 · P3: 5

## Threat model

Assets: the user's manuscripts, database and spend ledger (project folder for the live launcher, `~/Library/Application Support/Imprint/` for the frozen build); API keys in `.env`; the user's money at paid providers; the installed app's identity (what the Dock, Spotlight and Lab Hub launch).
Trust boundaries: install scripts (run as the owner, write `/Applications`) to the file system; `/Applications` (`drwxrwxr-x root admin`, owner is in `admin`) shared with every admin-user process; app input box (pasted or imported text, untrusted) to the router; app to paid providers (request guard).
Entry points: `./scripts/install_app.sh`, `./scripts/build_app.sh` (also run by Lab Hub), the Route button (`main.py:2883`), Launch Services and the Dock.

| Asset | Threat (STRIDE) | Control | Evidence |
|---|---|---|---|
| User data folder and project | Tampering / deletion by the removal step | Only `rm` is a literal path; symlink and missing-dir early return; bundle-id check | `scripts/retire_old_bundle.sh:21-30`, `:49`; `rm -rf` on a path without a trailing slash removes a link, not its target |
| User data folder | Moved by the rename | `APP_NAME = "Imprint"` kept; display name is a separate constant used in no path | `services/runtime_paths.py:27`, `:32`, `:80`, `:112`; grep of `APP_DISPLAY_NAME`: titles, tray, wordmark, version line only |
| API keys | Lost or duplicated under a new name | Keys live in `.env` from `user_data_base()`, not in the Keychain; no `keyring`/`security` use anywhere | `services/api_keys.py:128-129`; grep for `keyring`, `Keychain`, `find-generic`: no hit in code or `requirements*.txt` |
| Settings and single instance | Split state between old and new name | `QSettings("Imprint", "Imprint")`, `SINGLE_INSTANCE_KEY = "imprint.single-instance"` unchanged | `ui/docs_center.py:141`, `ui/learning_center_v2.py:314`, `main.py:6710` |
| Unrelated app named `Imprint.app` | Deleted by mistake (Tampering) | Bundle id must equal `com.netrunner3000.imprint`; no other lab app uses that id | `scripts/retire_old_bundle.sh:25-30`; grep over `active/*` scripts and specs: only Imprint |
| Running old copy, unsaved text | Bundle removed under it (Denial of service, data loss) | Polite quit via `NSRunningApplication.terminate`, 20 s wait, return 1 before `rm` | `scripts/retire_old_bundle.sh:33-46`; limits in RR-3 and S-1 |
| App identity | Spoofing via a stale Dock pin or Login Item at the old path | `/Applications` writable only by admin-user processes; no Dock pin to either name; Lab Hub launches `/Applications/Imprint Studio.app` | `ls -ld /Applications`; `defaults read com.apple.dock persistent-apps` filtered for "imprint": no line; `lab_hub/apps.toml:40` |
| Launcher | Drift from the shared copy | Byte-identical to Sentinel's copy | `cmp scripts/app_launcher.c ../sentinel/scripts/app_launcher.c`: identical (the drift test skips in a worktree: `tests/test_app_launcher.py:55`) |
| Money at paid providers | Untrusted text routes to another agent and a paid call | Router runs only on the Route button; it selects an agent and changes no provider, model or send | `main.py:3935-3953`, `:3726-3734`, `:3776-3820`; `resolve_backend_model` reads the current boxes (`:3955-3995`) |
| Bundle signature | Gatekeeper / quarantine | Local build, `xattr -cr`, ad-hoc `codesign --force --deep --sign -`; local-only by construction | `scripts/install_app.sh:115-116`, `scripts/build_app.sh:70-71`; unchanged by the rename |

## Findings

### P0
None.

### P1
None.

### P2
None.

### P3

**S-1 · The removal treats any `pgrep` failure as "not running".**
- Where: `scripts/retire_old_bundle.sh:33`, `:40`, `:43`.
- Evidence: `pgrep` exits 1 for no match, 2 for a bad pattern, 3 when it cannot read the process list. Line 33 (`|| true`) then asks no process to quit, line 40 (`|| break`) stops waiting, and line 43 (`if pgrep`) is false, so line 49 deletes. Checked here: `pgrep -f "("` gives exit 2; no match gives exit 1. The pattern itself is a fixed valid literal, so only exit 3 is reachable (a restricted environment, for example a sandboxed caller).
- Scenario: the old frozen `Imprint.app` is open with an unsaved Quill draft; the install runs where `pgrep` cannot list processes; the bundle is deleted without the app being asked to quit; its next lazy import fails and `closeEvent` (where the manuscript is saved) never runs. Data in Application Support is not touched; the SQLite WAL survives a crash. A one-time migration, so likelihood is low. The same window exists, for milliseconds, between the last `pgrep` (`:43`) and the `rm` (`:49`) if the user relaunches the old copy then.
- Fix: distinguish exit 1 from other codes (`pgrep ...; rc=$?; [ "$rc" -le 1 ] || return 1`), so an error stops the removal instead of allowing it.

**S-2 · Only the literal path is retired; moved or renamed old copies keep the same bundle id.**
- Where: `scripts/retire_old_bundle.sh:17`; `scripts/build_app.sh:86`.
- Evidence: by design the script never touches `~/Applications/Imprint.app`, `/Applications/Imprint 2.app` or a copy elsewhere. In the main checkout `dist/Builds.noindex/Imprint/` (an old PyInstaller onedir from 2026-11-22 02:29, executable `Imprint`) is still present; `build_app.sh:86` removes only the new `Imprint Studio.app`.
- Scenario: a stale copy with id `com.netrunner3000.imprint` is what Launch Services opens for `open -b` or a document handler; if it is a frozen build it reads and writes `~/Library/Application Support/Imprint/`, not the live launcher's project data, which feeds the known two-database problem (TODO P1 "Decide which database is the real one", architecture A-2), including two separate spend ledgers.
- Fix: no code change needed for the literal-path design (it is the safety property). Have the install scripts list, not delete, any other registered bundle with this id and print it; delete `dist/Builds.noindex/Imprint/` by hand once.

**S-3 · Untrusted text still addresses an agent through more joiners (extends RR-2); no cost path.**
- Where: `agents/router/agent.py:110-115`.
- Evidence (probe with `RouterAgent().route`): `"use nova​ voice"` (zero-width space) and `"use vector—raster"` (em dash) are addressed to creator and fiverr; a pasted chapter containing `She said: open Nova. Then she left.` routes to creator. `"use nova voice"` and a full-width `Ｎova` fall back to chat. A 2.1 M-character paste routes in 0.15 s (no regex blow-up).
- Scenario: the user pastes a manuscript and clicks Route; the workspace switches to Nova. Nothing is sent and the provider and model boxes do not change (`main.py:3946-3947`, `:3726-3734`, `:3776-3820`); a paid call still needs Send and the request guard. Impact is confusion only.
- Fix: as RR-2 (end a guarded name only on end of text or `[,.!?;:]` followed by space or end); also treat any non-space, non-ASCII-punctuation character as joining.

**S-4 · The launcher log at `/tmp/imprint_launch.log` follows a planted symlink and truncates its target (known, unchanged).**
- Where: `scripts/app_launcher.c:49`, `:127` (`open(LOG_PATH, O_WRONLY | O_CREAT | O_TRUNC, 0644)`); `scripts/install_app.sh:70`.
- Evidence: already recorded as `docs/audit/operations.md:296` P3-6. The rename recompiled the launcher with the same path; not made worse.
- Scenario: on a Mac with a second local account, that account links `/tmp/imprint_launch.log` to a file the owner can write (for example the project's `data/imprint.db`); the next Dock launch truncates it and writes the app's stdout and stderr there, readable by all (0644).
- Fix: as P3-6, log under `~/Library/Logs/...` with `O_NOFOLLOW` and 0600, in both copies of the shared launcher in one session (drift test).

**S-5 · Stale-path hygiene: no executed test of the foreign-id and error branches, and one doc still names the old bundle.**
- Where: `tests/test_display_names.py:327-348` (text checks only, as RR-4); `ui/app_identity.py:3` ("`/Applications/Imprint.app` runs the ...").
- Scenario: a later edit to `retire_old_bundle.sh` breaks the bundle-id or still-running branch with no failing test.
- Fix: a test that sources the script with `old` pointed at a temp directory (a parameter defaulting to the literal), runs the foreign-id, symlink, and `pgrep`-error branches, and asserts nothing outside the temp directory changed; update the docstring.

Related, already open and not repeated: RR-3 (running copy detected by command line only), RR-6 (`build_app.sh:64` stops the app with `pkill`, skipping `closeEvent`; same unsaved-text risk as S-1).

## Checked and found sound
- `rm` targets in the three scripts: `rm -rf -- "/Applications/Imprint.app"` (literal), `rm -rf "$INSTALLED"` (constant, quoted, contains the space correctly), `rm -rf "$DIST_APP"` (under the project's `dist/`), `rm -rf "$STAGE"` (from `mktemp -d`); `set -euo pipefail` in both entry scripts. `bash -n` passes on all three.
- Missing `/Applications`: `retire_old_bundle.sh:21` returns 0; the install's own `cp` fails first under `set -e`.
- Order: the old bundle is removed only after the new one is copied, signed and registered (`install_app.sh:113-124`, `build_app.sh:66-93`); a non-quitting old copy stops the script with the new app already in place.
- Multi-user Mac: a copy of `Imprint.app` run by another user is matched by `pgrep`, cannot be terminated from this session, and the script stops after 20 s (fail closed).
- `${pid}` in the JXA string comes from `pgrep` output (digits); no injection path.
- Bundle id `com.netrunner3000.imprint` unchanged (`Imprint.spec:154`, `install_app.sh:84`), so TCC and Launch Services keep one identity; the ad-hoc signature's designated requirement changes on every install anyway (not changed by the rename).

## Tests run
- `.venv/bin/python -m pytest -q -p no:randomly tests/test_display_names.py tests/test_app_launcher.py`: 200 passed, 1 skipped (Sentinel drift check: "sentinel checkout not present" in a worktree; checked by hand with `cmp`, identical).
- `.venv/bin/python -m pytest -q tests/test_agents_scenarios.py -k "rout or address or ordinary"`: 59 passed.
- Router probes quoted in S-3; `pgrep` exit-code probes quoted in S-1.

## Not verified
- Running `install_app.sh`, `build_app.sh` or `retire_old_bundle` (not allowed): the quit path, the foreign-id branch, the still-running branch.
- The installed bundle's signature, Gatekeeper assessment and quarantine state (`/Applications` not touched).
- Login Items and background items pointing at `/Applications/Imprint.app` (needs `sfltool`/System Settings); Launch Services registrations for the old path (`lsregister -dump` returned nothing in this environment).
- Whether macOS asks for Files and Folders (Documents) or other privacy permission again for the renamed bundle.
- That the data in `~/Library/Application Support/Imprint/` is intact after the real install (`TODO.md` lists it as open).
- Dependency audit (`pip-audit`/OSV): no network allowed. The range changes no dependency manifest (only `Imprint.spec`, for names).
- shellcheck (not installed). Full suite. CI status.
