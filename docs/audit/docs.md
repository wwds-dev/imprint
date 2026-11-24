# Audit: documentation against the code (tech-writer)

Date: 2026-11-22 to 2026-11-24. Commit: `45f705d` (`main`, v2.460). Author: tech-writer agent.
Read-only: no code, test or existing doc was changed; this file is the only one written.
Playbook: `docs/playbooks/tech-writer.md`, `status: current`, `last-reviewed: 2026-10-14`
(41 days, inside the 90-day limit).

`main` moved three times during the audit (`ec1cda5`, then `f69176e` when the rename to
"Imprint Studio" and docs package 5 merged, then `45f705d`). Every file:line below was
re-read on `45f705d`. The earlier audit, `docs/audit/docs-learning-centre-readiness-tech-writer.md`
(2026-11-22, DL-1 to DL-37), was not redone: its P0 and P1 findings are checked for status
in the table below, and this audit covers what it left out.

Severity, as in the earlier audit: **P0** would mislead a tester or blocks testing; **P1** wrong
or missing on something that matters (money, setup, first run, readiness, where the guard is);
**P2** unclear or stale; **P3** polish.

## Verdict

Not yet at a professional level, and not ready to be used without the owner's own caution. The
user-facing half is in good shape: the README's "Using the app" sections, the 28 Learning Centre
lessons and the twelve agent sheets were brought up to the code on 2026-11-22, 14 of the earlier
audit's 16 P0 and P1 findings are fixed and 2 are partly fixed, `tests/test_docs_integrity.py`
now guards them (267 passed, 17 expected failures), and `SUPPORT.md`, `SECURITY.md` and `LICENSE`
exist and agree with the repository's settings. The other half is not accurate. The hand-test
script sends the tester into paid Stop and resume cases that hit open money bugs without a
warning (one P0). The files that tell people and agents the state of the app (`CLAUDE.md`,
`docs/foundry/app-context.md`, the `TODO.md` header, the README's engineering sections 14 to 19,
`vidforge/README.md`) carry facts from September and October: a suite that takes "about 90 s"
(it takes 29 to 59 minutes), a request guard in a file that holds only timeouts, "feature-complete
for hand testing" above three open P0 bugs, two service files that do not exist, and a changelog
with no entry between 2026-10-14 and 2026-11-20. Counts: **1 P0, 6 P1, 14 P2, 5 P3.** The app's
own backlog also says it is not ready (three open P0 money bugs, CI red on `main`); that is
outside this audit, but the docs must stop saying the opposite.

## Findings

### P0

**D-1. The hand-test script sends the tester into paid Stop and resume cases that hit open money bugs, with no warning.**
Doc: `tests/manual_test_cases.md:608` ("A source file changed since the last run is noticed and
said so"), `:612` ("**Stop** mid-run: completed chunks survive on disk"), `:613` ("Resuming bills
only the chunks it actually narrates"), all in B3 Booth, marked `PAID-UNIT`; `:688-696` B5 Reel
Test C, "the direct-provider Stop contract", `PAID-UNIT`, introduced at `:689` with "This is the
case most recently fixed — check it closely". A search of the file for QB-2, QB-3, QH-2 and QH-6
finds nothing.
Code and backlog: `TODO.md:61` (QB-2, open P0: after a source change Booth authorizes only the
remaining share while the converter narrates the whole book), `TODO.md:96` (QH-2, open P0: stopping
a Gemini Omni render discards the paid clip; `ui/workers.py:405-409` returns after a cancel without
emitting or saving the job), and QH-6 (Stop loses the paid chunks in flight). The agent sheets
already say so: `docs/agents/audiobook.md:48` and `docs/agents/video.md:113` ("Deliberate
limitations"). The script the owner tests from does not. I read the code fragment named above and
did not re-prove the three defects; the 2026-11-18 code audit is their source.
Smallest fix: a short "Known open money bugs" box at the top of Part B that names QB-2, QH-2 and
QH-6 with their `TODO.md` rows, and one line on each of the three cases: skip the step, or run it
with the cheapest model and expect the loss, until the row is closed. Delete "most recently fixed"
at `:689`.

### P1

**D-2. The suite's run time is written five ways, and the file every session reads says 90 seconds.**
Docs: `CLAUDE.md:21` "about 90 s"; `pytest.ini:13` "the whole suite is ~90s";
`tests/manual_test_cases.md:1025` "Both halves pass in about 110 seconds combined";
`docs/foundry/app-context.md:69` "1820 passed … (7 min 39 s)" (2026-10-19), against its own `:36`
and `:68`, which say README section 16.1 is the one place; `README.md:3043-3045` "2,625 collected …
28 min 57 s. A full run takes about 15 to 30 minutes".
Measured: `pytest --collect-only -q` gives 2,863 tests on `45f705d`. CI's `test` job, when it
passes, took 43 min (run 45090214787) and 59 min (run 45069741534). The coordinator reports a
local full run of 45 min 40 s under load (2,596 passed); I did not run it. `app-context.md:37`
sets Lab Hub's test timeout to 60 min, which a 59-minute run nearly reaches.
Why P1: an agent that trusts 90 seconds sets a short timeout, kills the run and reports a hang.
Known since 2026-11-18 (`TODO.md:115`, rated P3) and still open.
Smallest fix: `CLAUDE.md:21` and `pytest.ini:13` say "30 to 60 minutes; see README §16.1";
`manual_test_cases.md:1025` drops the figure; delete `app-context.md:69`; re-measure README 16.1
after the rename and widen its range.

**D-3. app-context names a file of timeouts as the request guard and says the guard covers every paid call.**
Doc: `docs/foundry/app-context.md:53` "Request guard in `main.py`/`services/api_limits.py` gates
every paid call, including per-unit billing".
Code: `services/api_limits.py` is 23 lines and holds `REQUEST_TIMEOUT_SECONDS`, `REQUEST_TIMEOUT_MS`
and `MAX_RETRIES` only. The guard is `GodAI.authorize_request` (`main.py:4479`), `record_request`
(`:5495`) and `abandon_request` (`:5550`), with the eleven checks in `services/validator.py:92-195`
and the host protocol in `ui/host.py:49-73`. "Every paid call" is contradicted by open rows:
`TODO.md:95` (QH-1, the cloud worker narrates outside any guard), `:101` (QM-1, paid measurement
calls without a confirmation), `:62` (QB-3, a clip authorized under the wrong provider), and by
`docs/agents/video.md:122` (the vidforge command line has no budget check).
Why P1: app-context is the one app file every Foundry agent reads; a reviewer or security engineer
sent to `api_limits.py` reviews the wrong file. Known (`TODO.md:115`), still open.
Smallest fix: name the three methods and `services/validator.py`; replace "gates every paid call"
with "is meant to gate every paid call; open exceptions: QH-1, QM-1, QB-3, the vidforge CLI".

**D-4. The `TODO.md` header says the app is feature-complete and fully guarded; the rows under it say otherwise.**
Doc: `TODO.md:12` "State, October 2026"; `:15-20` "Every paid path in the GUI goes through the
request guard … every paid path now goes through the guard"; `:21-23` "1826 collected on
2026-10-19"; `:24-25` "`main.py` is 4,384 lines"; `:28-29` "Feature-complete for hand testing as of
2026-10-05. Every v2 item above P3 is closed"; `:31-33` "no `.env` exists … the only local models
pulled are `deepseek-r1` variants"; `:3` and `:65` say one-click release slice 1 is paused and
"the branch stays unmerged".
Facts: three open P0 bug rows in the same section (`TODO.md:61`, `:62`, `:96`) and "Verdict: not
ready" at `:59`; 2,863 tests collected; `main.py` is 6,725 lines; a `.env` exists in the repository
root (checked for presence only, not read); slice 1 was merged on 2026-11-21 (`0f0c0de`), its
Release gate approved (`8c73a9a`) and it has a dated section at `CHANGELOG.md:103`.
Why P1: this header feeds the Lab Projects Monitor, the owner's status view.
Smallest fix: replace lines 12 to 33 with five dated lines: verdict (not ready, with the open P0
rows), tests (pointer to README 16.1), `main.py` size, setup state, slice 1 merged. Close or
reword row `:65`. Keep the file's format.

**D-5. "Start here" tells a new user to pull the one local model the app's own checks call unsuitable.**
Doc: `README.md:34` and `docs/learn/modules/13-access-privacy.md:38`: `ollama pull deepseek-r1:8b`.
Code and other docs: `scripts/check_setup.py:98` recommends `ollama pull llama3.1:8b`, and `:100-103`
flags a machine with only `deepseek-r1` models ("all reasoning models; pull a general instruct
model"); `tests/manual_test_cases.md:50-53` says such a model "emits its `<think>` monologue into
the output box and will make half the `FREE` cases below unreadable"; `TODO.md:32-33` says the same.
No code strips the block from an agent's output (the only `<think>` handling is the ratings judge,
`services/local_ratings.py:583`). `README.md:1060` already says `ollama pull llama3.1`.
Smallest fix: `llama3.1:8b` in both places, with one sentence on why not a reasoning model.

**D-6. The changelog has no entry between 2026-10-14 and 2026-11-20.**
Doc: `CHANGELOG.md` headings run `## 2026-11-21` (`:103`), `## 2026-11-20` (`:174`), then
`## 2026-10-14` (`:191`).
`git log`, last 30 days (2026-10-23 on; 113 commits that are not merges or autosync), user-visible
and missing: `SUPPORT.md` and `SECURITY.md` added (`1e20ce0`, `c5d26e6`, 2026-11-11); eleven lessons
and seven agent READMEs revised (`7b41c33`, 2026-11-08). The removal of the screenshots (`62c9ec4`,
2026-11-05) appears only as an aside under Unreleased. November's other commits before the 20th are
process files and need no entry.
Just outside the window, in the same gap, and larger: local-model routing phases 0 to 4, that is
LM Studio as a second local provider, Settings → Local models, measured ratings and the routing
advisor with five modes (`d4d39c1`, `0c0efcb`, `74436b4`, `95747d3`, `45fb54a`, `44c6b18`,
2026-10-19 to 10-21); the PySide6 pin after a crash (`7754eec`); the pillow 13.0.0 and pypdf 6.21.1
security bump (`2c7c2aa`); the packaged-build fix (`7c7241d`). A search of the changelog for
"advis", "Local models", "provider registry" and "PySide6" finds no entry.
Smallest fix: three dated sections (2026-10-19 to 10-22, 2026-11-05, 2026-11-11), one line per
user-visible change, each checked against the code.

**D-7. vidforge's README recommends a paid command-line run without saying it has no budget check, and lists a removed command.**
Doc: `vidforge/README.md:52-54` describes "the shared budget approval in front of every paid
request" (true of the Reel panel); `:151-154` calls the removed scheduler "a paid path outside
Imprint's request guard, which is the thing that guard exists to prevent" and then says "Run
`python -m vidforge.cli run` yourself"; `:95` prices a video at "$1.50–2.50"; `:84` lists
`schedule --at 03:30` in the command table.
Code: `vidforge/vidforge/cli.py:378-429` defines `run`, `topics`, `list`, `upload`, `scan`, `course`
and `doctor`; there is no `schedule`. `cmd_run` calls the pipeline directly, with no authorize
step. `docs/agents/video.md:122` already says the command line "has no budget check or
confirmation".
Why P1: it concerns spend. Known as audit QM-16 (`TODO.md:113`, rated P3), still open.
Smallest fix: delete the `:84` row; add one sentence under "CLI": "The command line is outside the
app's request guard: no estimate, no cap, no confirmation. Use the Reel panel for anything paid."

### P2

**D-8. README section 14 lists two service files that do not exist and miscounts the validator.**
`README.md:2767` `agent_factory.py` / `AgentFactory` and `:2777` `model_router.py` / `ModelRouter`
(also in the tree at `:2972`): neither file is in `services/`, and the README says so itself for
the first (`:2822`, `:2974`). `:2764` "Ten-check", `:2964` "10-check", `:3063` "ten rules":
`services/validator.py:92-195` has eleven (the per-project cap at `:151` is the eighth).
`:2782` "ChatWorker (main.py)": the class is `ui/workers.py:21`. `:2776` says `tool_runner.py` loads
"paths, venv, defaults": there is no venv (D-9). `:2940` names `SubprocessWorker`, which does not
exist. The table covers 19 of about 45 modules; `api_keys.py`, `providers.py`, `pricing_catalog.py`,
`per_unit_pricing.py`, `runtime_paths.py` and `version.py` are absent.
Fix: delete the two rows and the tree entry, say eleven, move the heading to `ui/workers.py`, add
the six modules.

**D-9. README "Audiobook Tool Configuration" describes a subprocess and a separate virtual environment that are gone.**
`README.md:3522-3530` lists `working_dir`, `venv_python` and `script_path` ("Path to
`ebook_to_audiobook.py`"). Code: `config/tools.json` has `name`, `module`, `default_input`,
`default_output`, `default_voice`, `default_chunk_tokens`; `services/tool_runner.py:14-16` runs the
converter "in-process (no subprocess, no separate venv)".
Fix: list the six real keys.

**D-10. README says the split-agent purge runs at every launch and cannot delete a user's agent; the code says it runs once because that claim was false.**
`README.md:3184-3189`. Code: `services/database.py:915-942` returns early when the setting
`split_agents_purged` is present, and its docstring records that the every-launch version "was
silently delet[ing]" an agent later created under a reserved name.
Fix: "Once, recorded in the `split_agents_purged` setting."

**D-11. README section 15 documents 10 of 37 tables and gives one database location.**
`README.md:2804` "stored at `data/imprint.db`": a frozen build keeps it under
`~/Library/Application Support/Imprint/` (`services/database.py:8-10`). Sections `:2808-2900` cover
`agents`, `tools`, `usage`, `runs`, `pricing`, `settings` and the four release tables;
`services/database.py` creates 37 (projects, manuscripts, audiobook, creator, social, video,
music, fiverr). The `usage` table at `:2840-2854` omits `project`, `job_id` and `job_item`
(`database.py:58-62`); `runs` omits `job_id` (`:168`).
Fix: both locations; one table of the 37 names with a line each; add the missing columns.

**D-12. README 16.1's "last measurement" predates the rename, and the tree gives the old size of `main.py`.**
`README.md:3043-3044` "2,625 collected … 30 expected failures (the docs checks that wait for the
rename)": today 2,863 collected and 17 expected failures in the docs checks, none waiting for the
rename. `README.md:2908` "`main.py` … (~4,400 lines": 6,725 (`app-context.md:47` says about 6,700).
Fix: re-measure once and update; "about 6,700".

**D-13. PySide6 is listed as unpinned in three places; it is pinned.**
`README.md:3121`, `docs/foundry/app-context.md:27` and `:31`. Code: `requirements.txt:35`
`PySide6==6.11.2` (pinned on 2026-10-22, `7754eec`, after 6.12.0 crashed the suite). Fix: remove it
from the three lists and say why it is pinned.

**D-14. app-context carries four more stale facts.**
`:16` "it has no `LICENSE`" (MIT `LICENSE` since 2026-11-21; left for the owner because it is tier
evidence, `TODO.md:83`). `:71` "Whether runs pass on GitHub: UNVERIFIED": the `quality` workflow
failed on all four completed `main` runs I looked at, 2026-11-22 to 11-23 (runs 45069135153,
45069741534, 45090214787, 45091207893; the lint job in each; `TODO.md:63-64`). `:7`, `:30`
and `:40` do not mention the display name "Imprint Studio" or the bundle
`/Applications/Imprint Studio.app` (`scripts/install_app.sh:45`, `Imprint.spec:152`). `:69`: see D-2.
Fix: four line edits; `:16` needs the owner's eye.

**D-15. The changelog says the release kit is "merged into local `main`, not yet pushed or released".**
`CHANGELOG.md:107-108`. `git status -sb` shows `main` level with `origin/main`, and `e9405fd`
records "main pushed". Fix: delete the parenthesis.

**D-16. vidforge's README describes a Scanner tab and a Produce tab, and an old default model.**
`vidforge/README.md:159` "Available as the **Scanner** tab", `:183-192` (sorting columns, "Send
suggestion to queue", "the Produce tab"): Reel has two tabs, Render and Library
(`agents/video/panel.py:188`, `:237`), and the same README says the standalone app's tabs were
removed (`:57-59`). `:111` "`openai` (default, `gpt-4o`)": `vidforge/config.yaml:17` is
`gpt-5.6-terra`. The layout at `:238-256` omits `fonts.py` and `history.py`.
Fix: "command line only" for the Scanner; correct the model; add the two files.

**D-17. The cloud README points at files that are not in this repository and is silent about cost.**
`cloud/README.md:46-51` tells the reader to package a dashboard with `READING_COMPASS_API_URL`,
include `cloud_dashboard.js` and deploy `deploy/netlify/`: none exists here (`git ls-files` has no
match) and the README does not name the project that holds them. `:3-6` sends the reader to a note
under `~/Documents/lab/_Admin/`, which a reader of the public repo cannot open. Nothing says that
the worker spends on OpenAI narration with no cap, no stored estimate and no usage record
(`cloud/reading_compass.py:573-618`; an estimate route exists at `:357-383` but queuing at
`:386-428` does not require it): open bug QH-1 (`TODO.md:95`), stated in
`docs/agents/overview.md:173`. The rest matches the code where I checked it (routes, the
environment variable names, the two Drive folders, the worker command, the Dockerfile).
Fix: name the dashboard's project; add a "Cost" paragraph that states the exception.

**D-18. `SUPPORT.md` still lists Pinterest among the posting connectors.**
`SUPPORT.md:30` "Posting and store connectors (YouTube, Reddit, Pinterest, PublishDrive)".
`docs/agents/social.md:43` and the README say Pinterest does not post yet; the code half is the
catalog line `agents/catalog.py:60` ("publish to Reddit, YouTube and Pinterest"), which waits for
the owner (`TODO.md:84`). Fix: "(YouTube, Reddit, PublishDrive; Pinterest does not post yet)".

**D-19. Three more lines in the hand-test script do not match today's app.**
`tests/manual_test_cases.md:45` requires that `pytest -q` passes and gives no duration: the run
takes 30 to 60 minutes (D-2) and CI's `quality` is red on `main` (`TODO.md:63-64`). `:972` "No paid
workflow exists outside the GUI's guard" is a box the tester ticks, while `docs/agents/video.md:122`
and `docs/agents/overview.md:173` name two. `:1025`: see D-2.
Fix: state the duration and the two known CI failures; reword `:972` to "none except the two listed
in the sheets".

**D-20. The README never names the licence and does not link `LICENSE`, `SUPPORT.md` or `SECURITY.md`.**
A search of `README.md` for the three file names and "MIT" finds nothing. The three files exist,
are tracked and agree with each other and with GitHub (licence detected as MIT, issues on, private
vulnerability reporting on, no release). Fix: three lines at the end of "Start here".

**D-21. A new engineer has no short way in.**
There is no `CONTRIBUTING.md`; the path is README sections 14 to 19 (about 850 lines) plus
`AGENTS.md`. Missing: the local lint command (CI runs
`python docs/foundry/tooling/ratchet.py ruff ruff check …`, `.github/workflows/quality.yml`; README
`:3141` describes the job, not the command); how to run one test file while the full run takes 30
to 60 minutes; that CI is red today and where that is tracked; where the request guard lives (D-3).
Fix: a ten-line "For engineers" block under "Start here": install both requirements files, run one
file, lint, where the guard is, where open defects are.

### P3

**D-22. Four docs point outside the public repository.** `README.md:3364` ("the workspace
`AGENTS.md`"), `:897` and `:903` (`docs/local_model_routing_plan.html` "in the lab root"),
`cloud/README.md:4`, `vidforge/README.md:23` (`~/Documents/lab/archive/…`). Fix: say "kept outside
this repository" or copy the three packaging notes in.

**D-23. Small inaccuracies in README sections 16 to 19.** `:2916` `CLAUDE.md` "Local (untracked)":
it is tracked (`git ls-files CLAUDE.md`). `:3358` "every agent in `CUSTOM_PANELS`": the self-test
reads `WORKSPACES` (`main.py:6594`), and also checks three imports, the tray glyph and the AppKit
guard, which the README omits. `:3501` "(see §14)": the function is described in section 15.
`:3108-3111`: the snippet uses `python3`, not `.venv/bin/python`, and builds 7 of 10 panels.
`:3508`: the example `default` row (2.50 / 10.00) is not the shipped one (10.0 / 50.0,
`config/pricing.json`). `:3254` "for example `v2.112`" (today v2.460; earlier audit DL-33).

**D-24. Terms used without a definition.** "WAL" (`README.md:2804`); `GodAI`, the main window's
class, first used at `README.md:317` and never introduced; audit codes such as "QB-2" in sheets a
user opens from the header (each section explains "open" but not the code); "under-reserved"
(`docs/agents/video.md`, Deliberate limitations). Fix: one clause each, or a glossary entry in
`docs/learn/modules/18-glossary.md`.

**D-25. `SECURITY.md:29` leaves `cloud/` out of scope by omission.** It names `vidforge/` and the
narrator converter; `cloud/` handles Google sign-in and stored refresh tokens. Fix: add it or
exclude it in words.

**D-26. Changelog structure.** The header (`CHANGELOG.md:26-27`) says work stays under Unreleased
"until it ships", but there are no releases (`SECURITY.md`: "no binary releases"), so nothing says
when an entry moves to a date. Work committed on 2026-10-19 (`12604e9`) sits under `## 2026-10-14`
(`:191`), which also repeats the Fixed and Changed sub-headings. The playbook's `## v2.340 - date`
headings are not used: a recorded owner decision (D5 of the docs spec), not a finding.

## Status of the 2026-11-22 P0 and P1 findings

Checked on `45f705d`. "Guard" is the test in `tests/test_docs_integrity.py` that now holds the fix.

| Finding | Status | Evidence |
|---|---|---|
| DL-1 old agent names and left-panel navigation (P0) | Fixed | No hit for "Left-panel button", "Atelier", "Maestro Agent" in `README.md`; `README.md:1012` "7.1 Kernel (Assistant)"; guard T5 |
| DL-2 Booth sibling project at a local path, OpenAI only (P0) | Fixed | No hit for "sibling project" or `/Users/` in `README.md`; guard T8 |
| DL-3 five Settings tabs, Docs opens the README | Fixed | Guard T10 passes against `ui/dialogs.py` |
| DL-4 three permission boxes, five providers | Fixed | `README.md` section 6.3 lists eight boxes; section 9.6 added; guard T10 |
| DL-5 five wrong button labels | Fixed | No hit for the five; four other suspected labels remain (`TODO.md:85`, P3, one expected failure) |
| DL-6 contents link to a hidden chapter | Fixed | Contents link `#21-income-experiments-with-imprint`; guard T1 |
| DL-7 hidden earnings chapter | Fixed | No hit for "passive income", "Top sellers"; guard T7 |
| DL-8 Label README projects payouts | Fixed | `agents/music/README.md` item 5 "no forecast"; guard T7 |
| DL-9 lesson titles differ from the contents list | Partly | Vector, Nova, Kernel fixed; lessons 20 to 26 still open with "# Draft", "# Publish", "# Audiobooks", "# Music", "# Video", "# Social", "# Site Builder" (`TODO.md:78`, rated P2; 15 expected failures in T6, 1 in T5) |
| DL-10 Quill lesson lacks Draft safety | Fixed | `docs/learn/modules/20-draft.md:23-35` |
| DL-11 Make Release Kit missing from sheet, lesson, help map | Fixed | `docs/agents/manuscript.md:39`, `21-publish.md:223`, help-map entry |
| DL-12 hand test lacks the two newest features | Fixed | `tests/manual_test_cases.md:9`, B1 Test G, B2 Test G |
| DL-13 no first-run path | Fixed, one flaw | `README.md:15-51` "Start here"; `13-access-privacy.md` "Add a key"; the model it recommends is D-5 |
| DL-14 no "Deliberate limitations" sections | Fixed | 12 of 12 sheets; open audit items are named in them; guard T9 |
| DL-15 readiness gate and test plan give October verdicts | Fixed | Dated banners at `tests/READINESS_GATE.md:5` and `tests/TEST_PLAN.md:5` |
| DL-16 Herald sheet says Pinterest can post | Partly | Sheet, README and hand test fixed; `agents/catalog.py:60` waits for the owner (`TODO.md:84`); `SUPPORT.md:30` is D-18 |

The rename's name occurrences (package 5) were checked only through the guard tests, which pass
for Imprint Studio, Kernel, Nova and Vector; I did not recount them by hand.

## Could not verify

- Nothing was checked on screen; the app was not launched.
- No full test run. The 45 min 40 s local figure is the coordinator's; the CI durations are from
  `gh run view`.
- The three money defects behind D-1 (QB-2, QH-2, QH-6) were not re-proved in code.
- Whether `cloud/` is deployed (`README.md:2980` says "not deployed"; `cloud/README.md:3-6` keeps
  the status in a private note).
- vidforge's cost and time figures (`vidforge/README.md:95`): no paid call was made.
- `TODO.md:32` on which Ollama models are pulled: `ollama list` printed no models on 2026-11-23,
  which may mean none or a stopped daemon.
- The legal pack (`docs/legal`, a link into the private Foundry repository): whether the notices
  and privacy note that the `public` tier needs are visible to a reader of the public repo is for
  legal-compliance. `SUPPORT.md`, `SECURITY.md` and `LICENSE` are the only such files in this repo.
- `README.md` sections 1 to 13, 20 and 21, the lessons and `docs/agents/*.md` bodies were not
  re-audited (earlier audit); only the P0 and P1 statuses above.
- The four other audits written on 2026-11-23 (`docs/audit/operations.md`, `support.md`,
  `security.md`, `legal.md`, `architecture.md`) were not read; overlaps are possible.
- The Foundry activity log was not written (`log_activity.py`): the brief allowed one file.

## Found along the way (not documentation; not yet in `TODO.md`)

- `config/tools.json:5-6` holds two `/Users/…/Documents/Files/Narrator/…` paths in a public
  repository, against the lab rule on hard-coded paths. `TODO.md` has a row for the same path in
  `services/narrator/converter.py:30` and none for this file.
- `config/commands.json:7` still ships an "OSINT Brief" command from the security fork.
- `cloud/requirements.txt:11` pins `pypdf==6.19.0`; the root file has 6.21.1 after the 2026-10-22
  security bump, and `pip-audit` does not read the cloud file (`README.md:3147`).
- CI's `test` job failed after 14 minutes on run 45091207893 and passed on the runs either side;
  cause not looked at.
