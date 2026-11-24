# Operations audit: build, packaging, CI, release readiness, logging, recoverability

Role `sre-release`, audit (read-only), 2026-11-22 to 2026-11-23. Tier `public`.
Started on `main` at `ec1cda5`; `main` moved to `f69176e` during the audit (the Imprint Studio
rename and the model-updates change were merged by other sessions). File:line references were
re-read at `f69176e`. CI history was read with `gh` up to 2026-11-23 01:40Z.

Playbook `docs/playbooks/sre-release.md`: `status: current`, `last-reviewed: 2026-10-14` (40 days,
not stale).

Not run, by instruction: `scripts/build_app.sh`, `scripts/install_app.sh`, the full test suite,
`legal_gate.py sign`. Also not run: `scripts/check_setup.py` (it writes and deletes a probe file
in the data directory, so it is not strictly read-only; the tools it looks for were checked with
`which` instead) and `--selftest` (it runs `init_db()` on the live database, `main.py:6592`).

## Verdict

Imprint is usable by the owner on this Mac as a daily tool, and the code shows real care in the
places that have already hurt (state directory rename, per-unit pricing after upgrade, key file
permissions on write, a graceful quit in the live installer, a packaged self-test). It is **not at
a professional level operationally and not ready for a `public` release**. Release cannot start:
the legal gate is BLOCKED and CI has not been green on `main` since 2026-10-19. Behind those two
gates sit four operational gaps that matter for anyone relying on it: the release gate is not
wired into the build script or CI, the database is migrated in place on every launch with no
backup and no schema version, the app has no log file or crash handler, and the two install paths
keep two different sets of user data and switch between them silently. For `public`, the honest
description today is "source-only, built and run by the owner"; the source install is not
reproducible (no lock file) and no bundle can pass Gatekeeper on another Mac (ad-hoc signature).
None of the findings is an active data-loss or secret-leak incident: no key material was found in
any log, and both databases are intact.

Counts: 2 P0 (release blockers under the app's own definition of done), 6 P1, 9 P2, 12 P3.

## Release gate status (what the release role must report first)

| Check | Result | Evidence |
|---|---|---|
| `release_check.py .` | **BLOCKED**, exit 1 | `release check: BLOCKED: legal gate: legal pack changed since the last sign-off (wwds-dev, 2026-11-21)` / `release check: BLOCKED: do not build or publish` (run at `ec1cda5` and again at `f69176e`) |
| Release script calls the gate first | **no** | `grep -rn release_check` over `*.sh`, `*.py`, `*.yml`: only the Foundry tooling itself and the unused template `docs/foundry/tooling/common/release.yml:25` |
| `.github/workflows/release.yml` with `needs: release-gate` | **missing** | `ls .github/workflows` prints `quality.yml security.yml` |
| CI green on `main` | **no** | section P0-2 |
| Signing | ad-hoc only | `codesign -dv "/Applications/Imprint Studio.app"`: `Signature=adhoc`, `TeamIdentifier=not set`; `spctl -a -vv`: `rejected` |

I did not sign anything and did not run `legal_gate.py sign`. Wiring the gate is `/harden`'s job;
proposed below, not done here.

## Findings

### P0: release blockers

**P0-1. The legal gate is BLOCKED; no packaged build may be made.**
Evidence: the two `release_check.py` lines above. TODO row added in `f69176e` records the pack hash
moved from the signed `8b0becd4a572` to `051b81981cf7` and that three lawyer triggers (name, T1,
T2) are still listed.
Scenario: `./scripts/build_app.sh` is run for a hand-off build while the pack that was signed is no
longer the pack on disk; the build succeeds because nothing in the script checks (see P1-1).
Smallest fix: owner runs `/legal-check` to see what changed, then signs in a terminal. Not an
agent's step.

**P0-2. `quality` has not been green on `main` for 35 days; the signal is void.**
Evidence: `gh run list --workflow quality.yml --branch main`: the last success on `main` is run
39253423273 (2026-10-19). Of 198 `quality` runs since 2026-10-13, 7 succeeded, 2 of them on `main`.
The 44 completed `main` runs from 2026-10-21 to 2026-11-22 21:01Z are all failures: `lint` failed
44 of 44; `test` failed 17 of 44 (13 of the last 30). Two more runs on 2026-11-23 (45090214787,
45091207893) also failed. Run 45069135153: `ruff: 232 findings, baseline 189: the count rose`
(`docs/foundry/tooling/baseline.json` holds `189`) and
`2 failed, 2569 passed, 27 skipped, 31 xfailed ... in 2373.27s (0:39:33)`.
The test job is not deterministically red: at `148f462` it failed, at the next commit `e538ff4`
(a review report only) it passed. Six failed test jobs sampled: four are
`Fatal Python error: Segmentation fault`, exit 139 (runs 43990478536, 44853814267, 44981693926,
44959523020); two are assertions in `tests/test_settings_keys.py` (44986563316, 44736686346).
Scenario: because `lint` is always red, a red run carries no information, so a real regression or
a segfault in the test job is not noticed. This already happened: tag `v2.398` (`451ed53`) is on
origin and its own `quality` run 44960870462 failed. The definition of done ("CI green") has not
been met by any change merged since 2026-10-19. TODO rows 63 and 64 date the problem as "found
2026-11-22"; it is a month older.
Smallest fix, in order: (1) clear the 43 new ruff findings (mostly unused imports and import
order; do not raise the baseline, `ratchet.py --update` refuses to); (2) treat the segfault as the
P1 it is in CI terms (TODO rows 69, 154, 395 hold the diagnosis: module-scoped `GodAI` windows
freed by `gc.collect()`); (3) fix or quarantine-with-owner-approval the two timing-dependent
tests; (4) then protect `main` (P1-1).

### P1

**P1-1. The release gate is advisory: nothing enforces it.**
Evidence: `scripts/build_app.sh` has no `release_check` call (first action is
`stamp_version.py`, line 45, then PyInstaller, line 50). No `release.yml`. `main` is unprotected:
`gh api repos/{owner}/{repo}/branches/main/protection` returns `404 Branch not protected`. A
`v2.398` tag was pushed (`git ls-remote --tags origin`) although `CHANGELOG.md:15` says "There are
no git tags" and the last line of `docs/audit/one-click-release-sre-release.md` says "Nothing is
tagged"; who pushed it is not recorded.
Scenario: any session can build, tag and push with the legal gate blocked and CI red, and nothing
stops or records it.
Smallest fix: run `/harden` (copies `docs/foundry/tooling/common/release.yml` to
`.github/workflows/release.yml`, adds `python3 docs/foundry/tooling/release_check.py . || exit 1`
as the first step of `build_app.sh`). Note the template's own caveat: the legal pack lives in the
Foundry HQ (`.gitignore:61`), so the CI job fails by design in a clone and the real gate is the
build script on the owner's machine. Then add a branch rule on `main` requiring `quality` once
P0-2 is fixed. Do not wire it during a release.

**P1-2. The database is migrated in place on every launch, with no backup and no schema version.**
Evidence: `services/database.py:735-759` (`init_db`): `executescript(SCHEMA)`, then
`ALTER TABLE ... ADD COLUMN` (`:832`), then twelve correction passes including deletes
(`_purge_non_token_pricing_rows` `:904`, `_purge_split_agents` `:915`,
`_drop_empty_creator_earnings` `:944`). `grep -i "backup\|VACUUM INTO\|integrity_check\|user_version"`
over `main.py services ui agents`: no match. The file's own comment at `:769-777` records a
migration that was dead code and stranded paid renders because "the migration path was the
untested one".
Scenario: the installed app is now the live launcher (see P1-3), so it runs whatever commit is
checked out in a worktree that several agent sessions commit to, on a `main` that is red, and each
launch rewrites the only copy of `data/imprint.db` (spend ledger, projects, conversions, runs). A
wrong correction pass or an older build opened against a newer schema (a stale bundle from
`dist/`, P3-3) has no undo. The only backup found is a manual one made by a previous release
session (`~/Documents/lab/backups/imprint_pre_install_20261121`).
Smallest fix: in `init_db`, before `executescript`, when the build number differs from the one
stored in `PRAGMA user_version` (or a `settings` row), copy the database with
`sqlite3.Connection.backup()` to `data/backups/imprint-<build>-<date>.db`, keep the last 5, then
store the new build. Refuse to open (with a dialog naming the backup) when the stored build is
higher than the running one. One test in `tests/test_database_migrations.py`.

**P1-3. Two install paths, two sets of user data, switched silently.**
Evidence: frozen build writes to `~/Library/Application Support/Imprint/`
(`services/runtime_paths.py:102-115`); the live launcher writes into the checkout
(`install_app.sh` header: "Data lives in the project (data/, config/, .env)"). README section 18:
"the last one you ran wins". On 2026-11-22 22:05 the installed app was the frozen v2.406
(`/Applications/Imprint.app`, no `project_root.txt`, running as pid 58394); by 2026-11-23 00:40 it
was the live launcher `/Applications/Imprint Studio.app` (`project_root.txt` present). The two
databases are different files with different content:
`shasum -a 256 data/imprint.db "~/Library/Application Support/Imprint/data/imprint.db"` gives
`74a93790...` and `7c5899a3...` (both 360448 bytes; mtimes 2026-11-23 00:39 and 2026-11-21 22:42).
The App Support `.env` has 7 assignments, none filled; the project `.env` is the one with keys.
The TODO row from `dbefc25` still lists "check `Imprint Studio.app` opens with your data" as open.
Scenario: the owner did UAT and real work in the frozen build on 2026-11-21 and 2026-11-22; after
the rename install the app shows the project's database instead. It looks like lost projects and
lost spend history, and nothing on screen says which folder is in use. The reverse switch loses
the keys (App Support `.env` is empty).
Smallest fix: (1) owner decides which database is the real one now and the other is archived, not
merged by an agent; (2) show the data directory in the version badge tooltip
(`services/version.py:185`, one line) and in Settings; (3) one runbook line: "which data am I
looking at" (`ls "/Applications/Imprint Studio.app/Contents/Resources/project_root.txt"`).
Longer term, one canonical state directory for both paths is an Architect decision (state
boundary), not a quick fix.

**P1-4. No log file, no crash handler; the only launch log is erased by the next launch.**
Evidence: `grep -rn "RotatingFileHandler\|FileHandler\|basicConfig\|excepthook\|faulthandler\|qInstallMessageHandler"`
over the app code: no match. Diagnostics are 87 bare `print(` calls (7 in `main.py`, 80 in
`services ui agents providers`). Frozen build: `Imprint.spec` has `console=False`, so stdout and
stderr go nowhere when launched from Finder. Live launcher: output goes to `/tmp/imprint_launch.log`
opened with `O_TRUNC` (`scripts/app_launcher.c:127`), so each launch overwrites the previous one;
`/tmp` is also cleared on reboot. `ensure_seeded` creates `data/logs` (`runtime_paths.py:140`) and
nothing writes there: `~/Library/Application Support/Imprint/data/logs` is empty; `README.md:157`
says logs live there.
Scenario: the app aborts (the CI segfaults show the process can die inside Qt). The owner
relaunches, which truncates the only evidence. A stranger filing the bug report that `SUPPORT.md`
asks for has nothing to attach. An unhandled exception in a Qt slot prints to a discarded stream
and the UI simply does not react.
Smallest fix (about 30 lines at the top of `main.py`, after `ensure_seeded()`): a
`RotatingFileHandler` at `user_data_base()/data/logs/imprint.log` (1 MB x 5), `sys.excepthook` and
`threading.excepthook` that log the traceback, `faulthandler.enable()` into
`data/logs/crash.log`, and a `qInstallMessageHandler` forwarding Qt warnings. In
`app_launcher.c`, rename the existing log to `.1` before truncating (the file is shared with
Sentinel: change both copies in one session, the drift test enforces it). Write a header line with
version, commit, frozen or live, and data directory.
Keys in logs: none found. No key is placed in a URL (`grep "?key=\|&key="`: no match),
`services/api_keys.py:24` states that nothing logs a key, and a scan of the current launch log for
key-shaped tokens found 0. Residual, not verified: `services/narrator/converter.py:756-801` prints
provider exception text verbatim, and some SDKs echo a partly masked key in an authentication
error. When the log file is added, pass messages through one redaction filter for the names in
`.env.example`.

**P1-5. Known-vulnerable PDF parser on the untrusted-input path, and the check that says so is invisible.**
Evidence: `security.yml:22` `continue-on-error: true`. Run 45075043612 shows `success`, but its
`dependencies` job concluded `failure`: `Found 14 known vulnerabilities in 2 packages`, `pypdf
6.21.1` (10 CVE ids, fixed in 6.21.2 to 6.21.4) and `soupsieve 2.9` (fixed in 2.10.0).
`requirements.txt:21` pins `pypdf==6.21.1`. Manuscript and PDF import is listed as untrusted input
in app-context. Dependabot alerts are off: `gh api .../dependabot/alerts` returns
`403 Dependabot alerts are disabled for this repository`. No Dependabot PR proposes the pypdf
bump for the root; the root `pip` ecosystem has exactly five open PRs (#6, #8, #9, #26, #27), which
is Dependabot's default open-PR limit, so it has probably stopped proposing (not verified in the
Dependabot log).
Scenario: a crafted PDF opened in the app hits a published pypdf flaw. I have not assessed
exploitability; that is the security-engineer's call. The operational failure is that the weekly
audit found it and nothing told the owner.
Smallest fix: bump `pypdf` and `soupsieve` as one dependency change through Review and Secure;
enable Dependabot alerts in the repo settings (owner); close or merge the 17 open Dependabot PRs
(oldest 2026-10-13; #9 is obsolete, PySide6 is pinned now); decide TODO row 169 (make the job
blocking). Until it blocks, make the job post its count as a run annotation so a green tick does
not hide it.

**P1-6. The only public install path (from source) is not reproducible.**
Evidence: no lock file (`ls *.lock uv.lock pyproject.toml`: none). `requirements.txt:33-44` has nine
unpinned lines (`anthropic`, `python-pptx`, `google-genai`, `psutil`, `python-docx`, `reportlab`,
`PyYAML`, `google-api-python-client`, `google-auth-oauthlib`). The venv holds 82 distributions
against 42 requirement lines, so about 40 transitive packages are chosen at install time.
`requirements-dev.txt` pins nothing, and `pyinstaller` (6.22.3 in the venv), `coverage` and `ruff`
are in no requirements file, so a fresh clone cannot run `build_app.sh` and CI lints with whatever
ruff is newest. CI installs with `pip install -r requirements.txt` (`quality.yml:18`), so CI and
the owner's venv test different sets. TODO row 137 records that an unpinned PySide6 6.12.0
segfaulted the suite. TODO row 171 ranks this P3 and says ten lines; PySide6 has been pinned
since, nine remain.
Scenario: `SUPPORT.md` says the app is "published as source, with no binary release". A stranger
clones today and gets an `anthropic` or `google-genai` major the suite never ran against; a bug
report cannot be reproduced because no one knows what they installed.
Smallest fix: `uv pip compile requirements.txt -o requirements.lock` (and the same for dev,
including pyinstaller, coverage, ruff), install from the lock in CI and in the README's install
line, and point Dependabot at it. pip-audit can then audit everything (today it cannot see
transitive packages).

### P2

**P2-1. No bundle can be given to another Mac.** `build_app.sh:71` and `install_app.sh:116` sign
with `codesign --force --deep --sign -`; `Imprint.spec:129-130` has no identity and no
entitlements; no hardened runtime, no notarization. `spctl -a -vv` on the installed bundle:
`rejected`. The live launcher is not distributable at all: it holds an absolute path to this
checkout (`install_app.sh:80`) and links the venv's libpython. For `public` this is acceptable
only because nothing is offered for download, and `SUPPORT.md` says so. The playbook rule stands:
distribution outside this Mac waits for Developer ID plus notarization, and release notes must
state the signing level. Fix when a download is wanted: Developer ID, `--options runtime`, an
entitlements file, `notarytool`, `stapler`; that is a Secure and Comply change, and a tier
question if the owner's `commercial` intent proceeds.

**P2-2. `build_app.sh` can lose work and can replace a good app with a bad one.** Line 64
`pkill -f` sends SIGTERM; `install_app.sh:93-95` explains that SIGTERM skips `closeEvent`, "where
the manuscript is saved". Line 66 `rm -rf "$INSTALLED"` runs before the new bundle has been
checked; `--selftest` is never run on the built bundle. Line 45 `stamp_version.py || true` hides a
failed stamp, and `Imprint.spec:66` then bakes whatever stale `_build_info.json` is on disk. The
script builds from a dirty tree without saying so. Fix: reuse the graceful-quit block from
`install_app.sh`; run `"$DIST_APP/Contents/MacOS/Imprint Studio" --selftest` with a scratch `HOME`
and stop on failure before the `rm`; fail on a failed stamp; print a warning when
`git status --porcelain` is not empty.

**P2-3. User state sits inside the git worktree for the installed app, with no backup or restore
procedure.** The live launcher keeps `data/imprint.db`, `data/chats`, `.env` and outputs in the
checkout; they are ignored (`.gitignore:21-23, 12`), so git does not protect them and
`git clean -fdx` or removing the folder deletes them. No document describes backup or restore;
the lab's Backup Control Center may cover the folder (not verified). Fix: RUNBOOK section below;
confirm the lab backup includes `active/imprint/data`, `.env` and
`~/Library/Application Support/Imprint`.

**P2-4. CI configuration is behind the playbook.** `quality.yml:11,25` and `security.yml` use
`macos-latest` and `ubuntu-latest` (playbook: pin images). `actions/checkout@v4`,
`setup-python@v5`: every run carries `Node.js 20 is deprecated` (playbook: the release check fails
on a deprecation annotation); Dependabot PRs #16 and #17 have been open since 2026-10-13. No
`timeout-minutes` and no `concurrency` group: completed `main` runs took 1 to 114 minutes and
bursts of pushes stack several 40-minute macOS jobs. Coverage is collected and never reported
(`quality.yml:22`, no `coverage report`, no floor). No job builds the bundle or runs `--selftest`
(`tests/TEST_PLAN.md:134` already says "The packaged build is not smoke-tested"). Fix: one
`/harden` pass: pin images, merge #16 and #17, `timeout-minutes: 75`,
`concurrency: {group: quality-${{ github.ref }}, cancel-in-progress: true}`, `coverage report`,
and a weekly `build --no-install` plus selftest job.

**P2-5. Nothing tells the owner when something is wrong.** CI was red for a month before a TODO
row was written. pip-audit failures show as green. The app has no log (P1-4). Dependabot alerts
are off. `.githooks/pre-commit` exists but is not active (`git config core.hooksPath` is empty),
so the local lint and secret gate does not run on commit. Fix: see Monitoring.

**P2-6. No runbook.** `docs/RUNBOOK.md` does not exist. Proposed outline below.

**P2-7. The release smoke checklist is still not one list.** `app-context.md:41` says UNVERIFIED;
`tests/manual_test_cases.md` is 1,026 lines of UAT, not a ten-minute smoke test. Proposed list
below, to go into app-context once the owner agrees.

**P2-8. The bundle identifier carries the retired handle into a public repo.**
`Imprint.spec:154`, `scripts/install_app.sh:84`, `scripts/retire_old_bundle.sh:29`:
`com.netrunner3000.imprint`. The workspace rule is to use `wwds-dev` and never hardcode a handle.
Changing it resets macOS privacy grants and saved window state and breaks
`retire_old_bundle.sh`'s identity check. Already raised in the 2026-11-21 release report and still
open. Owner decision; if changed, do it once, before any signed distribution.

**P2-9. `--selftest` writes to the live database and misses the common breakages.** It calls
`init_db()` (`main.py:6592`), so "checking" an install runs every migration pass on real data. It
does not check `ffmpeg` or `ffprobe` (required per `scripts/check_setup.py:131-134`), `.env`
permissions, that a version stamp exists, or that the database is writable. Fix: after P1-2 the
migration run is backed up; add the four checks; print the data directory and version first.

### P3

- **P3-1. `_to_delete/` is tracked in the public repo.** `git ls-files _to_delete` lists three
  stale lock files although `.gitignore:53` ignores the folder (they were added before the rule).
  On disk there are six files, including `claude_probe_tmp_1791300109`. Fix:
  `git rm --cached -r _to_delete`, then delete the folder.
- **P3-2. `_run_checks.command` no longer exists**, but `app-context.md:42` still tells agents to
  ignore it.
- **P3-3. `build/` (63 MB) and `dist/` (791 MB) hold old bundles**, including
  `dist/Create & Publish` and `dist/Imprint` from September, outside the `.noindex` folder.
  `build_app.sh:81-86` explains why a stale bundle that Spotlight can launch is dangerous; these
  two predate that fix. Launched, an old frozen build would run old migrations against the App
  Support database. Fix: delete both folders (owner or with the owner's word; they are generated).
- **P3-4. App Support `.env` is mode 0644.** `stat`: `-rw-r--r--`. `ensure_seeded` sets 0600 only
  when it first creates the file (`runtime_paths.py:149`); Settings sets it on save
  (`services/api_keys.py:233,241`); a file edited by hand, as `build_app.sh:98` suggests, stays
  world-readable. It holds no keys today. Fix: `chmod 0600` on every launch.
- **P3-5. A stray 0-byte `imprint.db`** sits at the top of
  `~/Library/Application Support/Imprint/` (2026-09-27), left by a connect with a relative path.
  Harmless; delete it when the state question in P1-3 is settled.
- **P3-6. `/tmp/imprint_launch.log` has a fixed name, mode 0644, and is opened with `O_TRUNC`**
  (`app_launcher.c:49,127`), which follows a symlink planted by another local account. Low on a
  single-user Mac. Fix with P1-4: log under `~/Library/Logs/Imprint Studio/`.
- **P3-7. `security.yml:17` downloads the gitleaks binary with `curl` and no checksum**, at
  8.18.4 while the baseline was measured with 8.30.1. Fix: pin the version used locally and verify
  the published SHA-256.
- **P3-8. The live launcher's `Info.plist` has no version.**
  `defaults read ".../Imprint Studio.app/Contents/Info" CFBundleShortVersionString`: key not
  found. Finder shows none; the header badge is the only place. Fix: write it from
  `_build_info.json` in `install_app.sh`.
- **P3-9. `LSMinimumSystemVersion` is `12.0`** (`Imprint.spec:162`); nothing below macOS 27 and
  the CI runner's macOS is tested. The playbook asks app-context to record which macOS CI tests
  against the one users run; it does not.
- **P3-10. State-directory adoption fails quietly.** `runtime_paths.py:81`: any file in the target,
  including a `.DS_Store`, cancels the adoption; the failure message at `:94` is a `print` that a
  frozen build discards.
- **P3-11. `CHANGELOG.md:15` says there are no git tags**; `v2.398` exists locally and on origin.
- **P3-12. `app-context.md` is out of date** in ways that mislead a release: lines 27 and 31 list
  PySide6 as unpinned (it is `==6.11.2`, `requirements.txt:35`); line 69 records 1,820 tests (CI
  ran 2,569 passing); line 71 says whether CI passes is UNVERIFIED (it does not); the build and
  bundle names changed with the rename. I may not edit it; listed for the owner or the tech-writer.

## Failure modes, and what would tell the owner today

| Failure | What tells the owner today | Gap |
|---|---|---|
| App will not open (checkout or venv moved) | `/tmp/imprint_launch.log`, one line | good, but in `/tmp` and overwritten |
| Crash or abort during use | macOS crash report only (`~/Library/Logs/DiagnosticReports`) | no app log, no traceback (P1-4) |
| Exception in a button handler | nothing; the UI does not react | P1-4 |
| Bad migration or wrong build against the DB | nothing until data looks wrong | P1-2 |
| Wrong data directory after reinstall | nothing | P1-3 |
| Provider error, auth failure, budget refusal | in-app message naming the provider; run log dialog | adequate |
| Stale packaged build | header badge tooltip (`services/version.py:154`) | good |
| Test or lint regression | a red CI run among 44 red runs | P0-2 |
| Vulnerable dependency | nothing (green tick) | P1-5 |
| Secret committed | `security.yml` gitleaks job, blocking; 199 of 203 runs green | adequate; local hook inactive |
| Disk loss | not known | P2-3 |

## Proposed monitoring (smallest set)

1. `main` protected, `quality` required: a red merge becomes impossible instead of unnoticed.
2. pip-audit blocking, or at least annotated; Dependabot alerts on, with email to the owner.
3. App log plus crash log (P1-4); a "Reveal logs" button in Settings so a report can include them.
4. A start-up line in the log and the badge tooltip: version, commit, frozen or live, data path.
5. `git config core.hooksPath .githooks` on this machine, so the ratchet and gitleaks run before a
   commit, not 40 minutes after a push.
6. A weekly scheduled `quality` run, so a runner image or dependency change that breaks the suite
   shows up without a push.

## Proposed `docs/RUNBOOK.md` (one page; not written, the brief allowed one file)

1. **Which app and which data am I running?** `project_root.txt` test; badge tooltip; the two
   state folders.
2. **It will not open.** Read the launch log; venv or checkout moved: re-run `install_app.sh`.
3. **It crashed.** Where the logs are; what to copy before relaunching.
4. **Back up.** Quit the app; copy `data/`, `config/`, `.env` (live) or
   `~/Library/Application Support/Imprint/` (frozen), including `imprint.db-wal` and `-shm` when
   present. Never copy a database while the app is open.
5. **Restore.** Quit; move the current folder aside; copy the backup in; start; check projects
   and spend history.
6. **Roll back a bad build.** Live: `git checkout <last good commit>`, relaunch, restore the
   pre-migration backup when the schema moved. Frozen: rebuild from that commit.
7. **Rotate a key.** Settings, API keys; file mode 0600; revoke at the provider first.
8. **Release.** `release_check.py .`, CI green on the exact commit, build `--no-install`,
   selftest with scratch `HOME`, smoke list, install, owner approval, then tag. Never `sign`.
9. **CI is red.** How to read `gh run view --log-failed`; segfault versus assertion; who decides.

## Proposed release smoke checklist (to replace "UNVERIFIED" in app-context)

1. `release_check.py .` exits 0. 2. `quality` and `security` green on the commit being built.
3. `git status` clean; note the commit. 4. `build_app.sh --no-install`. 5. `codesign --verify
--deep --strict` on the bundle; record the signing level. 6. `--selftest` with a scratch `HOME`:
"all checks passed". 7. Back up the state folder. 8. Install. 9. Launch from Finder: window
opens, badge equals `v<VERSION>.<git count>`, tooltip says "packaged build". 10. Projects and
spend history from before the install are present. 11. One free agent action on a local model
completes. 12. One paid action is stopped by the request guard's confirmation. 13. Quit from the
menu bar item; relaunch; state intact. 14. Log file has a start-up line and no traceback.

## Could not verify

- A build or install of the current tree, and a selftest of a fresh frozen bundle (not run, by
  instruction). The last recorded ones are in `one-click-release-sre-release.md` (v2.398) and the
  TODO row for the rename (`8489269`).
- Whether a frozen build's stdout and stderr are discarded on macOS 27 exactly as described
  (reasoned from `console=False` and Finder launch; no frozen build was run).
- Whether the two databases differ in user data or only in seed rows: I compared checksums and did
  not open either file.
- Whether the lab backup covers `active/imprint/data`, `.env` and the App Support folder.
- Whether the owner receives GitHub failure emails for this repo.
- Why Dependabot has no root PR for pypdf (open-PR limit is an inference).
- Exploitability of the 14 advisories in this app.
- Whether any SDK error text printed by `services/narrator/converter.py` can contain part of a key.
- The CI results for `f69176e`, `67b8472`, `a6878ba` and `77466c6`: queued or running when the
  audit ended.
- `scripts/check_setup.py` output (not run; `ffmpeg`, `ffprobe`, `ebook-convert`, `gitleaks`, `uv`
  are on the PATH under `/opt/homebrew/bin`).
- Who pushed tag `v2.398`, and whether an owner approval covers it.
