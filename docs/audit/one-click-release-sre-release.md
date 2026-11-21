# Release report: one-click release, slice 1 (free path)

Role `sre-release`, phase Release, 2026-11-21, tier `public`. Spec `docs/specs/one-click-release.md`. Tested commit `0f0c0de` (merge of `claude/one-click-release-slice1-599646` into local `main`). Nothing was installed, tagged, pushed or merged.

## Verdict
**Release is not approved and should not start.** Technically the build, selftest and suite are green. Blocked by: legal sign-off not valid (see 1), no `LICENSE`, `main` unpushed, and the open items in "Owner decisions".

## State confirmed (not assumed)
| Item | Result | Evidence |
|---|---|---|
| Slice 1 in local `main` | yes | `git branch --contains claude/one-click-release-slice1-599646 --list main` prints `* main`; HEAD of this branch is `0f0c0de` |
| Local `main` vs origin | **26 ahead, 0 behind, not pushed** | `git rev-list --left-right --count origin/main...main` prints `0 26` |
| Legal gate, main checkout | prints "legal gate: clear" | `legal_gate.py check` run in `~/Documents/lab/active/imprint` |
| Legal gate, this worktree | BLOCKED: no `docs/legal` link here | `release_check.py .` here: "legal pack is kept in the Foundry HQ ... run this check on the owner's machine" |
| `release_check.py .` in main checkout | clear: "Release may start" | "release check: legal gate clear (tier public)" |
| Unmerged branch in flight | `claude/one-click-release-slice1-fixes2` (+1: `adb0d86`, a TODO note about the full-suite segfault); not slice code | `git log main..` |

## 1. The legal gate "clear" is not a real sign-off (owner question)
Last row of `docs/legal/signoff.jsonl` (2026-11-21T21:24:20): `"by": "<your name>"`, `"risk_accepted": "<why>"`, `"role": "owner"`, `"commit": "41fd58f"`, and `open_triggers` lists the name conflict, **T1** (AI Act Art. 50(2)) and **T2** (macOS `say` voices in public Shorts). Both `by` and `risk_accepted` are literal template placeholders, so the row names no person and gives no reason, yet the gate passes. Comply's report (59b00d2) says the gate was BLOCKED with "no legal sign-off recorded". I did not edit `signoff.jsonl` and did not run `legal_gate.py sign`. Who wrote that row, and was it meant as a sign-off, is for the owner. The gate treats a placeholder row as clear, which is a gate defect to fix in Foundry (not here).

## 2. Definition of done
| Item | Status | Evidence |
|---|---|---|
| Suite green | **pass** | `.venv/bin/python -m pytest -q -p no:cacheprovider` in this worktree: `2321 passed, 16 skipped, 1 warning, 6 subtests passed in 1653.48s (0:27:33)`, rc 0. Single mode only (none other documented). The known intermittent full-suite segfault (TODO, adb0d86) did not occur this run |
| Mutation check of new logic | done in Verify (bf006a7); survivors M20-M24, M32, M43, M44 are on record in `one-click-release-qa-engineer.md` | not re-run here |
| Reviewer P0/P1 | fixed (P1-1 `_guarded`, 17408bf); QA re-confirmed | code-reviewer and QA reports |
| Secure | P1 S-1 and P2 S-2..S-4 fixed, re-check "ready for Comply: yes" (403385f, 0285166); P3 S-5..S-12 open in TODO | security report |
| Success measures 2 and 4 (money cap, caps) | **not verified**: slice 2 (paid path) | QA report |
| Real Ollama / LM Studio run, real `say` plus ffmpeg Shorts | **not verified**: no local model installed | QA, Secure |
| CI green | **not verified**: 26 commits are unpushed, so CI has not seen them; `ruff` is not in the venv and the ratchet was not run | `ruff` missing |
| Tooling baseline not regressed | not verified (same reason) | |
| `release_check.py .` | passes in main checkout, but see section 1 | |
| CHANGELOG entry | present (`CHANGELOG.md:28`, "Make Release Kit"), but **stale**: it says "on branch ..., not yet merged or released"; slice 1 is merged to local `main` | |
| Version | derived, not typed: `VERSION`=2, `git rev-list --count HEAD`=393 at `0f0c0de`, baked into the bundle as `{"major":"2","build":393,"commit":"0f0c0de"}`. Committing this report makes the next build 394 | `_build_info.json` |
| `SUPPORT.md`, private security contact | **present** (Comply's "missing" is out of date): `SUPPORT.md` (1e20ce0), `SECURITY.md` (c5d26e6, both 2026-11-11); GitHub private vulnerability reporting enabled: `gh api repos/wwds-dev/imprint/private-vulnerability-reporting` returns `{"enabled":true}` | |
| `LICENSE` | **missing**, and the GitHub repo reports no licence. A public repo without one grants no reuse rights. Not written by me: the choice is the owner's | `git ls-files`, `gh api` |
| Claims on the checked list | not verified by me | |

## 3. Build without install
`./scripts/build_app.sh --no-install` (PyInstaller 6.22.3, ad-hoc signature): `✓ Built: dist/Builds.noindex/Imprint.app`. `codesign --verify --deep --strict` printed nothing (no error); `Signature=adhoc`, `TeamIdentifier=not set`, so it will not pass Gatekeeper on another Mac without the quarantine bypass. The bundle contains `services.release_kit` (stages, runner, ledger, plan, power, grant, provenance, report in `build/Imprint/PYZ-00.toc`).

`Imprint --selftest` on the built bundle, run with `HOME` pointed at a scratch folder so the owner's real `~/Library/Application Support/Imprint` was not touched: rc 0, "all checks passed" (data directory, registry, vidforge, resources, ratings snapshot, AppKit guard). The selftest does not exercise Release Kit.

Headless launch (`QT_QPA_PLATFORM=offscreen`, scratch `HOME`): process alive after 15 s, then killed. The launch printed two start-up model-list failures (Anthropic 401, Gemini 400): the process inherited credential environment variables from my shell, so those two requests went out and were rejected. This is existing start-up behaviour, not Release Kit.

Not done (needs the installed app or a person at the screen): header version badge, relaunch with DB and projects intact, one agent action, `tests/manual_test_cases.md` UAT, Make Release Kit end to end on a real manuscript. The checklist in `app-context.md` is itself marked UNVERIFIED as a single list.

Side note for the owner: the bundle identifier is `com.netrunner3000.imprint`, which carries the old handle into a public project; changing it would strand state under the old identifier. Not touched.

## 4. Radar
`docs/foundry/radar-notes/2026-11-21-release.md`. Nothing blocks. Qt 6.11.2 (the pinned PySide6) fixes three 2026 Qt advisories; Imprint does not use QDom or NTLM. PyInstaller 6.22.3 is past the fix for CVE-2025-59042; OSV PYSEC-2026-1813 was unreadable (unverified). Owner: check notification settings for GitHub security alerts on `wwds-dev/imprint`.

## Owner decisions needed
1. **Legal gate row.** Is the 2026-11-21T21:24:20 `signoff.jsonl` row yours? It has placeholder `by` and `risk_accepted`. If it is not a real sign-off, who corrects it (not an agent)?
2. **T1 and T2** (and the name trigger): lawyer or your decision. T1's commentary date is 2026-12-02, 11 days away. Is "free, source-only, on this Mac" enough to ship slice 1 before then, or hold?
3. **`LICENSE`**: which licence? (I will not pick one.)
4. **Push `main`** (26 commits, so CI can run) and **merge** this report's branch: yours.
5. **Install** to `/Applications` and UAT on the installed app: do you want a build from the final HEAD, after the above?
6. **CHANGELOG** "not yet merged" wording: update on your word.
7. **Release gate.** Not asked for approval until 1 to 4 are settled. No approval recorded.

## Update 2026-11-21 (owner answer to decision 1)
Asked whether the `signoff.jsonl` row of 2026-11-21T21:24:20 is theirs, the owner answered: "Yes, mine". The row still has the placeholders `by: "<your name>"` and `risk_accepted: "<why>"`, and T1, T2 and the name trigger are still listed open, so it names no signer and gives no reason. An agent cannot fix that: the owner re-signs in a terminal with the real values (or a lawyer closes the triggers). Decisions 2 to 7 are still open and no Release approval is recorded.

## Update 2026-11-21, later (legal sign-off replaced)
The owner removed the placeholder rows. I re-ran the gate myself in the main checkout: `legal_gate.py check .` prints "legal gate: clear"; `release_check.py .` prints "legal gate clear (tier public)" and "clear: Release may start". `docs/legal/signoff.jsonl` now has one row: `by` `wwds-dev`, role owner, 2026-11-21T22:00:27, scope "whole pack", commit `0f0c0de`, hash `8b0becd4a572...`, with risk accepted in writing for the name, T1 and T2 triggers (the owner's own decision; I did not write or edit it). Section 1 above is resolved. The still-open blocker is `LICENSE` (owner's choice), then pushing `main`; no Release approval is recorded.

## Update 2026-11-21, later (LICENSE, CHANGELOG, rebuild)
Owner: "Use MIT, fix the CHANGELOG, then build". Done in `9f656a1`: `LICENSE` (MIT, "Copyright (c) 2026 wwds-dev"; the holder name is my choice from the commit identity, the owner may change it), CHANGELOG slice-1 wording corrected plus an MIT line. Rebuilt with `./scripts/build_app.sh --no-install`: rc 0, bundle baked as v2.397 (`commit 9f656a1`), `codesign --verify --deep --strict` ok, `--selftest` (scratch `HOME`) "all checks passed". The full suite was not re-run: the only changes since the 2321-pass run are docs, `LICENSE` and the CHANGELOG. Not installed. Open: push `main` (26 commits), install and UAT, then the Release gate.

## Update 2026-11-21, later (install and UAT)
Owner: "Install it and run the UAT". **Installed** `/Applications/Imprint.app` with `./scripts/build_app.sh` from `451ed53`: v2.398, `_build_info.json` `{"build":398,"commit":"451ed53"}`, `codesign --verify --deep --strict` ok. It replaced the frozen build of 2026-11-21 02:14. Before installing I copied `~/Library/Application Support/Imprint` (496 KB) to `~/Documents/lab/backups/imprint_pre_install_20261121/` (ignored snapshot; delete once nothing needs it).

UAT result: **partial**.
- A1 launch, from a terminal (`Imprint.app/Contents/MacOS/Imprint`, real data dir): `--selftest` on the installed app "all checks passed". Output had no `resume`/`pending`/column warnings; one `[warn] models: anthropic: RuntimeError: Connection error.` (start-up model-list fetch, existing behaviour, not release kit).
- A1 visible: header opens, version badge reads `v2.398`, status pill `Ready`, workspace tabs (Author, Audio + Music, Video + Ads, Social, Web, Brand Design, Brand Content, Assistant) intact, Spend panel and Limits (€1 session, €5 daily) shown, Quill panel loads. Seen in one screenshot only; not resized, no tooltip check.
- **Not run:** everything else, including Press, Quote Finder, **Make Release Kit** and the **Release Kits** window. The app's window sits on a full-screen Space and the background tool could not click into it (clicks had no effect). Make Release Kit end to end also needs a local model (Ollama or LM Studio, none installed) and a manuscript, so it could not complete here anyway.
- The installed app is still running (started by me).
