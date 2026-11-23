# Architecture and tech-debt audit (2026-11-23)

Role: architect (Foundry audit, read-only on code). Playbook `docs/playbooks/architect.md`:
`status: current`, `last-reviewed: 2026-10-14` (40 days, not stale).

Base: the brief named `main` at `ec1cda5`. `main` moved to `f69176e` while the audit ran (the
Imprint Studio rename and the Model updates change merged). **Every file:line below is at
`f69176e`.** Nothing in the code was changed, no provider was called, the full suite was not run.
Run here: the five copy and launcher test modules only (23 passed, 0 skipped, 2.5 s).

The owner's question: is this code at a professional level and ready to be used?

## Verdict

Not yet, and no new P0. The structure is better than a 6,725-line `main.py` suggests: the agent
panels already live in `agents/*/panel.py`, `services/` imports no Qt, workers never call
`terminate()`, the request guard is keyed by token, migrations have their own tests, and the
copies shared with other lab apps are in step today. What keeps it below a professional level is
four things at the edges of that structure, none of them in the earlier audit: quitting while
Label or Sitebuilder is working aborts the process (A-1); where the database, the keys and the
spend ledger live depends on how the app was launched, and two separate ledgers exist on this Mac
now (A-2); one truncated config file stops the app from starting (A-3); and a rebuilt environment
installs whatever nine unpinned packages are current that day (A-4). The owner can use it today,
knowing these. It is not ready for the QA campaign or for anyone else until A-1 to A-4 are fixed
and the money blockers still open from the 2026-11-18 audit are closed (`TODO.md:61-62, 96`:
QB-2, QB-3 and QH-2, not re-verified here). A full split of `main.py` is not what stands between
this code and "ready"; see the last section.

## Findings

Severity: **P0** data loss or unguarded spend on a normal action. **P1** fix before the QA
campaign. **P2** fix before a `public` packaged release. **P3** debt, schedule it.

### P0

None found by this audit. The open P0 items from `code-readiness-audit-2026-11-18.md` are tracked
in `TODO.md:61-62, 96` and were not re-verified.

### P1

**A-1. Shutdown does not name every QThread, and its wait is not a join.**
`main.py:6502-6511` lists the workers `closeEvent` cancels and waits for. `music_worker` and
`webdesign_worker` (declared `main.py:365-366`, set at `agents/music/panel.py:224`,
`agents/music/suno_panel.py:216`, `agents/webdesign/panel.py:205`) are missing, although
`stop_current_task` knows both (`main.py:5798`). `KeyProbeWorker` (`ui/dialogs.py:644`) is held
in a local list only. For the workers that are listed, the wait is `worker.wait(2000)`
(`main.py:6516, 6521, 6524`) followed by `event.accept()` (`:6527`).
Scenario: the user quits while Label drafts a plan, or while a non-streaming call (an image
batch, a Shorts render) is blocked in HTTP for more than two seconds. The QThread is destroyed
while running and Qt aborts the process, as `ui/workers.py:136-138` itself records. The request
stays in the in-memory `_pending_requests` only (`main.py:325`), so a paid call leaves no usage
row and the daily cap under-counts. The lab rule is "`shutdown()` must name every QThread".
Not reproduced live.
Smallest fix: add the two attributes; keep a host-level registry that every `QThread` start goes
through, so the sweep iterates the registry rather than a typed list; add a test that fails when
a `QThread` subclass instance is stored outside it. While any paid request is open, ask before
quitting (as the release kit already does at `main.py:6462-6480`) and wait for the worker without
a two-second limit, or write a "sent, outcome unknown" usage row before accepting the close.

**A-2. Writable state follows the launch method, so there are two ledgers.**
`services/runtime_paths.py:108-115`: a PyInstaller build writes to
`~/Library/Application Support/Imprint/`; everything else, including the everyday live launcher
(`scripts/app_launcher.c` runs `<checkout>/main.py`, and `is_frozen()` is false), writes into the
git checkout: `data/imprint.db` (`services/database.py:10`), `.env`, `config/settings.json`,
`data/chats`. On this Mac both exist: `data/imprint.db` in the checkout (modified 2026-11-23) and
the Application Support copy (2026-11-21).
Scenario 1: the owner uses the packaged build one day and the launcher the next. Each has its own
usage rows, so each enforces its own daily cap, its own keys and its own Saved Chats. The guard
invariant holds per install, not per user. Scenario 2: the user's manuscripts database and keys
sit in ignored files inside a working tree; `git clean -fdx`, a re-clone or running from one of
the four worktrees under `.claude/worktrees/` gives an empty app or deletes the data.
Scenario 3: `config/settings.json` is tracked and rewritten by every dev run
(`main.py:3579, 3963, 5170`), so personal settings reach a public repo through autosync.
Smallest fix: one rule in `user_data_base()`: the launcher-installed app uses Application Support
too (the launcher sets one environment variable; a plain `python main.py` keeps the checkout
unless that variable is set). Migrate once by copying the newer database with its `-wal` and
`-shm`. This moves writable state, so it needs an ADR and a migration test (app-context
invariant). Untrack `config/settings.json` and ship a `settings.default.json`.

**A-3. One unreadable config file stops the app from starting.**
`GodAI.load_json` (`main.py:509-515`) calls `json.load` with no error handling, and `__init__`
reads four files through it before any window exists (`main.py:265-273`); `window = GodAI()` is
unguarded (`main.py:6686`). `settings.json` is written in place with `open(..., "w")` at
`main.py:3579, 3963, 5170`, while every other state file in the app uses a temp file and
`os.replace` (for example `services/model_watch.py:211-215`, `services/routing_advisor.py:638-642`).
Scenario: the disk fills, or the process dies between truncate and write (A-1 makes that more
likely). `settings.json` is left empty, and every later launch raises `JSONDecodeError` in
`__init__`. The user must find and delete a file by hand.
Smallest fix: `load_json` catches `ValueError`/`OSError`, renames the bad file to
`<name>.corrupt-<date>` and returns the default with a visible notice; one `save_settings()`
helper that writes atomically replaces the three sites.

**A-4. A rebuilt environment or bundle is not reproducible.**
`requirements.txt:33-44` leaves nine runtime packages unpinned: `anthropic`, `python-pptx`,
`google-genai`, `psutil`, `python-docx`, `reportlab`, `PyYAML`, `google-api-python-client`,
`google-auth-oauthlib`. There is no lock file, `requirements-dev.txt:7-9` is unpinned, and
PyInstaller (6.22.3 in `.venv`) is declared nowhere. The file is a partial freeze: the transitive
pins cover `openai` but not `anthropic` or `google-genai` (`httpx2` is pinned, its `truststore`
dependency is not).
Scenario: `_Admin/rebuild_envs.sh` or a clean build installs a new major of `google-genai` (now
3.0.0) or `anthropic` (now 2.6.0). The suite uses fakes, so it stays green while a provider
client breaks in the shipped app; `pip-audit` cannot audit the unpinned lines (app-context says
so).
Smallest fix: pin the nine lines to the versions in `.venv` today, add `pyinstaller` to
`requirements-dev.txt` pinned, and generate a hash-locked file with `uv pip compile`. Dependabot
already proposes the bumps.

Carried, not new: CI `quality` is red on `main` (`TODO.md:63`, ruff ratchet 232 against 189). A
red default branch hides every regression these fixes could introduce; it belongs in the same
batch.

### P2

**B-1. The request guard is window code, and its check and its reservation are separated by a
modal dialog.** `authorize_request` validates (`main.py:4529-4542`), opens the confirmation
(`QMessageBox.question`, `main.py:4399-4404`, a nested event loop) and only then reserves
(`main.py:4569`). Work that needs no click runs inside that loop: the automatic local-model
measurement validates against the same totals and never reserves its ceiling
(`main.py:1211-1236`), and startup resumes re-mint reservations (`main.py:5427-5453`). Two runs
can each pass against the full remainder. The agent and project checks still ignore in-flight
reservations (`main.py:4540-4541`): QM-1 and QM-2 of the earlier audit **still stand** at these
lines. The by-name lookup (`_resolve_request`, `main.py:5455-5476`) is still used by Label, the
Suno panel and Sitebuilder (QM-15 still stands: `agents/music/panel.py:240`,
`agents/music/suno_panel.py:225`, `agents/webdesign/panel.py:222`).
Smallest fix: reserve before the dialog and release on "No"; put the measurement ceiling in
`_pending_requests`; pass tokens in the three panels and delete the by-name branch.

**B-2. The panel boundary is nominal.** `ui/host.py:17` declares an `AgentHost` protocol of 19
members ("Nothing else is fair game"). Code in `agents/` and `ui/` reads or writes 105 distinct
attributes of the host, 88 of them undeclared, 16 private, and assigns 38 onto it (worker
handles, `validator`, `registry`, `daily_budget_eur`). `ui/dialogs.py` uses 25,
`agents/manuscript/panel.py` 23, `agents/creator/panel.py` and `agents/video/panel.py` 22 each.
The window is a shared attribute bag, which is why A-1's sweep must guess attribute names.
Smallest fix: no rewrite. Add the members panels really use to the protocol, in groups (guard,
projects, workers), and add a test that fails when a panel touches a host attribute the protocol
does not declare. The count then only goes down.

**B-3. `ui/` imports the entry script.** `ui/dialogs.py:665, 691` and `ui/panel_routing.py:53`
do `from main import ...`. Under `python main.py` and the launcher, the running module is
`__main__`, so this executes `main.py` a second time as module `main`: `ensure_seeded()`,
`os.chdir` and `load_dotenv` run again (`main.py:36, 41, 45`) and a second `GodAI` class exists.
Harmless today because `main.py` holds no module-level mutable state; any singleton added later
is silently duplicated. Whether the frozen bundle resolves `main` was not verified (see below).
Smallest fix: move `AGENT_SETUP_WIDGETS`, `AGENT_CONTEXT_WIDGETS` and `AGENT_PRETTY_NAMES`
(`main.py:189-209`) into `agents/catalog.py` or a new `ui/agent_widgets.py`; add a test that no
module under `ui/`, `agents/` or `services/` imports `main`.

**B-4. The copy guards protect one machine.** All four drift tests skip when the sibling repo is
not beside this one (`tests/test_benchmarks_drift.py:75`, `tests/test_converter_drift.py:85`,
`tests/test_providers_drift.py:51`, `tests/test_app_launcher.py:55`), which is always the case in
GitHub CI. `ui/appkit_guard.py` has no drift test at all in this repo, and its text differs from
all six other copies in the lab (against Sentinel's the difference is the docstring only, lines
23-35; the others were not analysed). The shared converter also runs in three places with
different dependency sets: here (`pypdf==6.21.1`, `requirements.txt:21`), Lab Hub, and the
`cloud/` image, which copies `services/narrator` (`cloud/Dockerfile:10`) and pins `pypdf==6.19.0`
(`cloud/requirements.txt:11`). The arrangement holds 14 files by copy (converter, benchmarks,
eleven routing and local-model files, the launcher).
Smallest fix: commit a `tests/shared_copies.sha256` manifest with each copy's normalised hash, so
CI fails when a copy changes without the manifest and the review asks "was the sibling changed
too"; add `appkit_guard.py` to it. Decide by ADR whether 14 files still justify copies over one
local package (ADR 0002 rejected a package for two consumers; the converter now has three).

**B-5. The narrator subprocess reports spend through a regex over merged output.** The panel
merges stderr into stdout (`agents/audiobook/panel.py:823`) and derives progress, and from it the
recorded spend, from `re.findall(r"(\d+(?:\.\d+)?)%\s+\((\d+)/(\d+)\)", data)` on each
`readAll()` chunk (`:861-879`). Any library line of that shape moves the ledger, and a progress
line split across two reads is dropped. This is the mechanism under QH-6 (still open,
`TODO.md:100`).
Smallest fix: the worker prints one JSON line per event with a fixed prefix; the panel buffers to
newlines and parses only prefixed lines. The converter is a shared copy, so all copies change in
one session.

**B-6. The schema has no version.** `init_db` (`services/database.py:735-759`) runs the schema
script and twelve repair passes on every launch; nothing reads or writes `PRAGMA user_version`,
no copy of the database is taken before `ALTER TABLE` (`:762-845`), and an older build opening a
newer database is undefined. The dict-literal bug recorded at `:769-777` shows the cost of an
unversioned path. `get_connection` (`:665-670`) opens a connection per call with
`check_same_thread=False`; 125 `with get_connection()` sites commit but never close (CPython's
refcount closes them, which is an accident, not a design); six sites bypass it and its pragmas
(`agents/manuscript/kdp_csv_parser.py:174, 211`, `agents/manuscript/panel.py:880, 899, 954`,
`main.py:3211`).
Smallest fix: set `user_version` after the passes; refuse, with a message, a database whose
version is newer than the build; copy the file to `imprint.db.bak-<version>` before a pass adds a
column; make `get_connection` a context manager that closes.

**B-7. A fetch on the GUI thread in the send path.** `assess_local_model` falls back to
`self.ollama.model_size_bytes(model)` (`main.py:754`), a `requests.get` with a 10 s timeout
(`services/ollama_client.py:86`), when the model is not in the cached inventory. It is reached
from `check_memory_before_request` (`main.py:801`) on every local send (`main.py:4288`). A busy
Ollama daemon freezes the window for up to ten seconds. QM-11 of the earlier audit (Press Refresh
and Herald posting on the GUI thread) was not re-verified.
Smallest fix: on the GUI thread, answer from the inventory only and return `None` when unknown;
the worker-side check at `main.py:5642` already covers the hard floor.

**B-8. Qt is off the lab's line with no ADR.** `requirements.txt:35` pins `PySide6==6.11.2`; the
architect playbook says GUI apps share the current LTS (6.12) and a non-LTS Qt needs an ADR.
App-context still says PySide6 is unpinned. Smallest fix: an ADR that either moves to 6.12 (the
`appkit_guard` and the 2026-10-05 combo-box deadlock need a retest) or records why 6.11.2 stays.

**B-9. The bundle identifier carries a handle the workspace rules ban.**
`Imprint.spec:154`: `bundle_identifier="com.netrunner3000.imprint"`, in a public repo. Changing
it resets macOS privacy grants and saved window state, so it is an owner decision, best taken
before the first public build. Not a secret; an identity rule.

**B-10. The process changes directory at import to keep relative paths working.**
`main.py:41` (`os.chdir`) exists because some services still use relative paths:
`services/report_exporter.py:6` (`"data/reports"`), and every agent row stores
`log_path` `data/logs/runs.jsonl` (`services/database.py:1206-1318`). Anything that imports
`main` (33 test modules do) has its working directory moved, and the narrator worker and vidforge
inherit it. Smallest fix: anchor those two on `user_data_base()` and delete the `chdir`.

### P3

- **Dead code in `main.py`.** 65 `GodAI` methods have no caller in tracked Python (name search;
  the eight `build_<agent>_panel` methods reached through `main.py:2891` are excluded), and 11
  more are called only from tests. They are the two-line pass-throughs left by the panel move
  (`main.py:2914-3314`, `3730-3773`), `_show_agent_docs_legacy` (`main.py:6260-6419`, 160 lines)
  and `show_docs` (`:6455`). Section comments for Sentinel features remain (`main.py:2936-2938`).
- **Dead code elsewhere, still as the earlier audit found it.** `providers/avatar/` (279 lines,
  imported nowhere); `PublishDriveClient.get_catalog`, `get_distribution_status`,
  `update_metadata` (`agents/manuscript/publishdrive_client.py:36-44`; the last one writes to a
  live account if ever wired); `ToolRunner.run_audiobook` (`services/tool_runner.py:14`).
  `services/narrator/converter.py:30` still hard-codes `/Users/as/...`.
- **Dependency direction.** `services` imports `agents` in ten places:
  `services/database.py:5` (`agents.catalog`), `services/release_kit/plan.py:17-18`,
  `services/release_kit/stages.py:16, 59, 131, 139, 149, 161`,
  `services/project_publication.py:15`; `ui` imports `agents` in seven
  (`ui/release_kit/driver.py:20-23`, `ui/workers.py:586, 611, 620`, `ui/project_manager.py:13`).
  The release kit's stage logic is domain code that sits in `services/` and reaches back into
  Press. Move the pure Press helpers it needs into `services/`, or the kit into `agents/`.
- **Nested `vidforge/` is neither a package nor a copy.** It is put on `sys.path` at run time
  (`agents/video/studio.py:87`), imports back into the app (`vidforge/vidforge/visuals.py:48`)
  and keeps its own `requirements.txt` with lower bounds only, which nothing installs for the
  app.
- **Two settings stores.** `config/settings.json` (model defaults, routing) and the `settings`
  table (`services/database.py:673-685`, budgets). `services/tool_runner.py:10` reads
  `config/tools.json` from the read-only resources, not from the seeded user copy.
- **Dialogs are never freed.** `ui/dialogs.py:72, 220, 314, 1230` create `QDialog(app)` on each
  open with no `deleteLater`; `show_settings` is one function of about 830 lines
  (`ui/dialogs.py:313-1145`) built from closures.
- **Decision records.** `docs/adr/0002-provider-registry.md` is headed "ADR 0001"; 0002 and 0003
  are still "proposed" although the code shipped; ADR 0005 names `services/job_reservation.py`,
  which does not exist yet (slice 2). `docs/refactor_plan.md` (2026-08-17) describes an 11,902-
  line file and Sentinel's verticals. No ADR covers the choices in A-2, B-4 and B-8.
- **Repo hygiene.** `_to_delete/` is ignored (`.gitignore`) but three stale lock files in it are
  tracked. App-context `## Stack` is out of date on the PySide6 pin.

## What a split of `main.py` would look like, and whether to do it before the QA campaign

`main.py` is no longer the tangle its size suggests. The agent verticals are gone; what remains
is the shared core of one window. By region (approximate, at `f69176e`):

| Region | Lines | About | Natural home |
|---|---|---:|---|
| Recommendation and assessment | `1346-2306` | 960 | `ui/recommendation_controller.py` |
| Window construction | `2310-2897`, `3317-3527` | 800 | stays (the shell) |
| Chat send, handlers, Saved Chats, projects | `4194-4350`, `5662-5832`, `5893-6254` | 690 | `agents/chat/panel.py` |
| Model updates and ratings | `4774-5334` | 560 | `ui/model_watch_controller.py` |
| Request guard | `4424-4720`, `5417-5617` | 500 | `services/request_guard.py` |
| Dead pass-throughs and legacy docs | see P3 | 470 | delete |
| Routing advisor glue | `3914-4184` | 270 | `ui/panel_routing.py` (exists) |
| Local models and measurement | `1110-1344` | 235 | `ui/local_models_controller.py` |

The result would be a shell of about 1,500 lines and six collaborators holding their own state.

Recommendation: **do not split before the campaign, with two exceptions.**

1. Before the campaign, as plain deletions and moves with unchanged behaviour (half a day,
   Foundry phases skipped as a dependency-free refactor): delete the dead methods (P3), and move
   the three constant tables out of `main.py` (B-3). About 470 lines go and `ui/` stops importing
   the entry script.
2. Before release-kit slice 2 (ADR 0005's money side), not before the campaign: extract the
   guard into a Qt-free `RequestGuard` in `services/`, owning `_pending_requests`, the reserved
   total, the session total and the validator call, with the confirmation dialog injected as a
   callable. Every money finding of both audits lives in these 500 lines, they are the only part
   of `main.py` whose rules are an app invariant, and ADR 0005 already requires a Qt-free
   `ReservationBook` beside them. This changes where money state lives, so it needs its own ADR
   and the Architect gate.

Everything else waits until after the campaign. Moving 2,500 lines of working UI glue while
testers file bugs against it invalidates their results and makes regressions hard to bisect, and
none of A-1 to A-4 is fixed by it. The cheaper lever for the campaign is B-2's test: stop the
host surface from growing, then shrink it as each region moves.

## Could not verify

- **The frozen bundle.** `build/Imprint` holds no analysis output and no bundle was run, so
  whether `from main import` resolves inside the PyInstaller app (B-3) is not verified.
  `--selftest` (`main.py:6551`) does not open Settings, which is where it would fail.
- **The abort on quit (A-1)** was not reproduced. The evidence is the code path, the app's own
  note at `ui/workers.py:136-138` and its regression test for the daemon workers.
- **The full suite and CI.** Not run by instruction; GitHub was not contacted. CI status is
  quoted from `TODO.md:63`.
- **The earlier audit's findings.** Re-read here: QM-1, QM-2, QM-15, the dead code and
  `converter.py:30` (all still stand). QB-1 is ticked in `TODO.md:60`; QB-2, QB-3, QH-1, QH-2,
  QH-6 are open there. None of those was re-verified in code.
- **Dead-method list.** Name-based over tracked Python. Confirm by deleting on a branch and
  running the suite.
- **Not read:** the internals of `services/validator.py`, `services/usage_tracker.py`, the
  provider clients, `services/release_kit/runner.py` and `ledger.py`, `ui/release_kit/driver.py`,
  `vidforge/` beyond its imports, `cloud/` beyond its imports and Dockerfile,
  `tests/test_database_migrations.py`.
- **Whether the per-launch pricing passes** (`services/database.py:748-754`) overwrite a price
  the user edited in Settings.
- **Which copy of the database is the owner's real one** (A-2): only file dates were read, not
  contents. `.env` was not opened.
- **The other `appkit_guard.py` copies** beyond Sentinel's: line counts of the difference only.
- **Activity log.** No entry was written: `log_activity.py` has no audit phase, and this audit
  was limited to writing this file.
