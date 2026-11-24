# Audit summary: Imprint Studio, whole app (2026-11-23)

Scope `all`, read-only on production code. Started on `main` at `ec1cda5`; `main` moved to `45f705d`
during the audit (the Imprint Studio rename and the model-updates change were merged by other
sessions) and every report re-checked its citations there. Nothing was fixed by this audit.

Owner's question: is the code at a professional level and ready to be used?

**Answer: not yet.** The owner can use it on his own Mac, knowing the open money bugs. It is not
ready for the QA campaign, for a release, or for anyone else. Nine reports agree on that and on why:
three known money bugs are still open, two new Quill data-loss paths were found, a class of
thread crashes is reachable with ordinary clicks, CI has not been green on `main` since 2026-10-19,
and the release gate is blocked on a legal sign-off. None of this needs a redesign.

## Reports

| Report | Role | P0 | P1 | Verdict |
|---|---|---|---|---|
| [code-review.md](code-review.md) | code-reviewer | 2 | 2 | not yet; gap narrow and mostly mechanical |
| [architecture.md](architecture.md) | architect | 0 | 4 | not yet; no split of `main.py` needed first |
| [qa.md](qa.md) | qa-engineer | 3 | 6 | FAIL |
| [security.md](security.md) | security-engineer | 0 | 0 | safe for the owner; 9 P2 before strangers run it |
| [ux.md](ux.md) | ux-designer | 2 | 9 | not yet |
| [operations.md](operations.md) | sre-release | 2 | 6 | not ready for a `public` release |
| [docs.md](docs.md) | tech-writer | 1 | 6 | user docs good; state docs stale |
| [legal.md](legal.md) | legal-compliance | 0 | 6 | gate BLOCKED; report only, no opinion |
| [support.md](support.md) | customer-support | 0 | 2 | tier requirements met; two gaps |

Not run: `business` (the `public` tier marks Case "no"), `marketing` (Launch is optional for
`public`; not requested), `model-validator` and domain specialists (not installed). The legal audit
was report-only: it did not create or edit anything under `docs/legal/`, because another session
was preparing the legal pack for a release at the same time.

## P0 (deduped)

| # | Finding | Where | Reports | Status |
|---|---|---|---|---|
| 1 | Booth authorizes only the remaining share after the source text changed; the converter re-narrates the whole book | `agents/audiobook/panel.py:706-749`, `conversions.py:39-44`, `converter.py:656-697` | code-review P0-1, qa P0-1 | known (QB-2), `TODO.md` row open, no test |
| 2 | A Herald clip is authorized as `openai` whatever provider draws its images | `agents/social/panel.py:616-619` | code-review P0-2, qa P0-2 | known (QB-3), row open, no test |
| 3 | Stop on a Gemini Omni render discards the paid clip | `ui/workers.py:405-409`, `services/gemini_client.py:416-419` | qa P0-3, code-review (stands) | known (QH-2), row open, no test |
| 4 | A Quill draft written without a Project is never saved; quitting discards it silently | `agents/author/panel.py:881-887`, `main.py:6483` | ux UX-01 | **new**; `_persist_project_state` returns when no project is set (confirmed by reading) |
| 5 | Quill's Clear erases Draft, Outline, Characters, World Notes, Sources and Title with no confirmation and no undo; with a Project active the empty state autosaves | `agents/author/panel.py:449-451`, `:1403-1417` | ux UX-02 | **new**; confirmed by reading |
| 6 | `quality` has not been green on `main` since 2026-10-19 (lint 44 of 44 runs red; tests red in 17 of 44, four of six sampled are segfaults) | `.github/workflows/quality.yml`, `docs/foundry/tooling/baseline.json` | operations P0-2, qa | rows open as P1; a month older than those rows say |
| 7 | The legal gate is BLOCKED: the pack changed after the 2026-11-21 sign-off | `release_check.py .` | operations P0-1, legal | owner's step; never an agent's |
| 8 | The hand-test script sends the tester into the paid Booth resume and Reel Stop cases that hit findings 1 and 3, with no warning | `tests/manual_test_cases.md:608-613`, `:688-696` | docs D-1 | **new** |

## P1 (deduped)

**Crashes and freezes**
- Replacing a running `QThread` aborts the app. Herald needs two ordinary clicks (Write Posts, then Make a Clip: `agents/social/panel.py:476`, `:565`); seven more panels after Stop. Quill and Reel already carry the guard. Reproduced as an isolated pattern, not in the app. (code-review P1-1; includes the old QM-12)
- Herald's Post Now runs the upload and the Google consent wait on the UI thread with no timeout (`agents/social/panel.py:1072`, `vidforge/vidforge/youtube.py:73`). (code-review P1-2)
- `closeEvent` does not name `music_worker` and `webdesign_worker`, and waits only 2 s for the rest (`main.py:6502-6527`). (architecture A-1, code-review P2-1)
- One truncated `settings.json` stops every later launch; the file is rewritten in place at three sites (`main.py:509-515`, `:3579`, `:3963`, `:5170`). (architecture A-3, code-review P2-5)

**State and recoverability**
- Writable state follows the launch method: the packaged build and the live launcher keep two databases, two key files and two spend ledgers, and the installed app switched between them on 2026-11-23. `config/settings.json` is tracked in a public repo. (architecture A-2, operations P1-3)
- The database is migrated in place on every launch with no backup and no schema version (`services/database.py:735-759`). (operations P1-2)
- No log file and no crash handler; the only launch log is truncated by the next launch. (operations P1-4)

**Release and dependencies**
- Nothing enforces the release gate: `build_app.sh` does not call `release_check.py`, there is no `release.yml`, `main` is unprotected, and a `v2.398` tag is on origin although `CHANGELOG.md` says there are no tags. (operations P1-1)
- `pypdf` 6.21.1 (desktop) and 6.19.0 (`cloud/`) have published advisories; the CI audit job cannot fail and Dependabot alerts are off. (operations P1-5, security S-3)
- Nine runtime packages are unpinned and there is no lock file, so the only public install path is not reproducible. (architecture A-4, operations P1-6, security S-4)

**Money, outside the three P0s**
- The Reading Compass cloud worker narrates whole books with no cap, no acknowledged estimate and no usage record; no test covers it. (known QH-1; security S-5, qa P1-4)
- Press Ask claims store access it does not have, and Connections says "connected" for a key that was only typed in. (known QH-5; ux UX-07)

**Tests**
- CI failure 1 is a state leak through the shared test database: a Booth test leaves a `running` conversion row and later windows start on Gemini voices. Reproduced with three tests in fixed order. (qa P1-1)
- CI failure 2 is most likely a fixed 600 ms wait on a 400 ms timer (`tests/test_settings_keys.py:293`); not reproduced. (qa P1-2)
- CI does not print the random seed or skip reasons, has no per-test timeout and produces no coverage report; 27 tests skip on CI against 2 locally. (qa P1-3)
- The test plan's two P0 tests do not exist (`test_no_paid_path_outside_guard.py`, `test_crash_recovery.py`). (qa P1-6)
- The mutation check and the live eval were not done; no eval budget is defined. (qa P1-5)

**What the user sees**
- The first cloud request from any agent is refused with a pointer to an "API Permissions panel" that exists only on the Kernel screen. (ux UX-04)
- Booth reports a deliberate Stop as "[Error] Conversion failed." (ux UX-03; known QH-6)
- Press: the Period selector does nothing and Refresh Data freezes the window; "Publishing todos" is seeded with developer tasks and the owner's own content. (ux UX-05, UX-06)
- The Model Guide documents another product (Chat, Writing, Coding, OSINT agents). (ux UX-08)
- Accessibility: keyboard focus is invisible on every button, chip and tab; 94 of 95 inputs have no accessible name; label and cost-line colour is below 4.5:1 in two themes. Measured offscreen. (ux UX-09 to UX-11)

**Docs and support**
- The open money defects are in no support-facing list, and two lessons state the opposite (`docs/learn/modules/24-video.md:208-216`, `22-audiobooks.md:203-207`). (support S-1)
- `SUPPORT.md` names no diagnostic to attach and does not warn that the database, chats and launch log hold manuscript text; the tracker is public. (support S-2)
- State-of-the-app docs are stale: suite run time written five ways (`CLAUDE.md` says about 90 s; it is 40 to 60 min), `app-context.md` names a constants file as the request guard, the `TODO.md` header says "feature-complete" and "every paid path guarded". (docs D-2 to D-4)
- "Start here" recommends `deepseek-r1:8b`, which `scripts/check_setup.py` calls unsuitable. (docs D-5)
- `CHANGELOG.md` has no entry between 2026-10-14 and 2026-11-20. (docs D-6)
- `vidforge/README.md` recommends a paid command-line run without saying it has no budget check. (docs D-7)

**Legal (for the owner or a lawyer to judge; no opinion is given here)**
- The pack to be signed contradicts the repo and carries stray tool markup in all six signed files. (legal L-01)
- No third-party notices file; the bundle contains EbookLib (AGPL) and Qt Virtual Keyboard (GPL) under an MIT label. (legal L-02)
- No machine-readable AI marking, and two calls send `"watermark": False` (`services/image_generation.py:150`, `services/qwen_client.py:493`). Lawyer trigger T1 is dated 2026-12-02. (legal L-03)
- A reported AI Act change has no lawyer trigger, and only the Higgsfield route refuses prompts locally. Not verified at the primary text. (legal L-04)
- The privacy note is published nowhere and omits recipients the code calls. (legal L-05)
- The name is not cleared (19 empty search rows) and the rename is already merged. (legal L-06)

## Top-10 fix order

1. **Get `main` green and keep it readable.** Clear the 43 new ruff findings with ruff pinned; add the teardown to the `booth` test fixture; replace the four fixed waits; print the seed and skip reasons in CI. Nothing below can be trusted on a red branch.
2. **Close the three money bugs, each with a test that fails first** (P0 1 to 3), and add the guard-sweep test the plan already names.
3. **Stop Quill losing work** (P0 4 and 5): save or warn when there is no Project; confirm before Clear.
4. **Remove the crash class:** one host helper that refuses to start over a running worker, a worker registry that `closeEvent` iterates, and Herald's Post Now in a worker with a bounded consent wait.
5. **Make launch and failure recoverable:** atomic settings write and a tolerant load; a database backup before migration with a schema version; a rotating log file and a crash handler.
6. **Decide the one state directory** (owner: which database is the real one), then an ADR and a migration; untrack `config/settings.json`.
7. **Dependencies and secrets:** bump `pypdf` and `soupsieve`; pin the nine lines and commit a lock; make the audit job blocking; add the secret file patterns to `.gitignore`, activate the pre-commit hook, fix the alias-key return.
8. **Make the surface honest:** a known-issues list in `SUPPORT.md` and the warning in the hand-test script until 2 is done; correct the two lessons; Press "connected" and Ask claims; the Model Guide; the seeded todos; the first-cloud-request dead end; Booth's Stop message.
9. **Release gate:** correct the legal pack, add third-party notices, drop the two `watermark: False` flags, publish the privacy note; then the owner signs. Wire `release_check.py` into `build_app.sh` and protect `main`. The lawyer question T1 is dated 2026-12-02.
10. **Then:** cap or scope out the cloud companion; the three accessibility fixes; refresh the state docs and the changelog gap.

## Corrections to the reports

- [security.md](security.md) lists CR-2 and CR-3 as "merged from the code review". No code review had been delivered when it was written. The code review later confirmed both locations (book parsing on the UI thread; no throttle on the cloud login routes) and rated them P2 and P3; the "over 40 seconds" figure has no source.
- The security brief said four `requests` calls in `cloud/reading_compass.py` lack a timeout. That was wrong: all four have one.

## Could not verify

- Any live provider behaviour: no key works and no paid call was made.
- The crash findings inside the running app; only the isolated thread pattern was run.
- The second CI failure's cause, the CI random seed, and why 27 tests skip on CI.
- All eight prepared mutants: the runs were declined at the permission prompt.
- Whether the Reading Compass service is deployed.
- The AI Act texts at the primary source; advisory severity scores.
- Native macOS rendering and VoiceOver; the UX probes ran offscreen.
- Which of the two databases holds the owner's real data.

One full local suite run on `ec1cda5` during the audit: 2596 passed, 2 skipped, 31 xfailed, 0 failed,
45 min 40 s, random order.
