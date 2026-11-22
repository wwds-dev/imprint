# Spec: the app is shown as "Imprint Studio"; three agents become Kernel, Nova and Vector

Status: DRAFT, awaiting owner approval (Define gate). Written 2026-11-22. Priority: P1 (below the
open P0 billing bugs QB-2 and QB-3, `TODO.md:61-62`). Type: user-visible rename, no behaviour
change except one router guard (R3). Slug: `rename-imprint-studio`. Product-manager playbook:
`status: current`, last-reviewed 2026-10-14 (39 days). Not run by this session (no shell):
`session_start.py --inflight`, `log_activity.py`, `/radar-check`; the orchestrator runs them.

## Decisions already made by the owner (2026-11-21/22; recorded, not reopened)
1. The display name becomes **Imprint Studio**. "Muse" and "Fusion Studio" were dropped (the latter
   after the name check found an identical Blackmagic product).
2. Display name only. The repo `wwds-dev/imprint`, the package layout, `APP_NAME` and
   `~/Library/Application Support/Imprint/`, and the database stay "Imprint".
3. Three codename labels change; catalog keys do not: `chat` "Chat" becomes **Kernel**, `creator`
   "Muse" becomes **Nova**, `fiverr` "Stamp" becomes **Vector**. Quill, Press, Booth, Label, Reel,
   Herald, Sitebuilder, Primer and Intent Router stay.
4. This lands before `docs-learning-centre-readiness` and before the hands-on test campaign.

## Problem
Who: the owner, and anyone who opens the public repo. The app shows "Imprint" and the agents
"Chat", "Muse", "Stamp", names the owner has decided to replace. Evidence that a rename done by
search-and-replace would break things:
- **The tray menu takes its text from the path constant.** `ui/tray.py:28,63,67,72` shows
  `APP_NAME`, the same constant that names the writable folder (`services/runtime_paths.py:27,75,107`).
  Changing it strands the database, chats and `.env` (app-context invariant).
- **Labels are not single-sourced.** Besides `agents/catalog.py:71,77,83` the three labels are
  typed again in `agents/{chat,creator,fiverr}/recommendations.py:4` (shown to the user as
  "Best match for {label}", `services/recommendations/engine.py:307-337`), `services/database.py:1200,1244,1293`
  (seed; corrected at launch by `_sync_agent_labels`, `:966-980`), `config/registry.json:4,40`,
  `main.py:2605` (`QLabel("Chat")`), `docs/agents/manifest.json:19-21` and `docs/learn/manifest.json:21,29,30`.
- **"Muse" is also a model.** 25 of the 130 "Muse" hits are Meta's "Muse Glimmer" (`main.py:934-1102`,
  `services/ollama_client.py:12,29,152`) and must not change. "Stamp" is also a verb
  (`ui/workers.py:737`, `vidforge/vidforge/pipeline.py:131`). "Chat" is a key, a job type in files
  shared byte for byte with Sentinel (`services/routing_advisor.py`), and an ordinary word.

Challenge (product): the rename answers no user question and adds no capability. It touches about
60 files days before the test campaign, with two P0 billing bugs open. It is the owner's decision,
so this spec proposes the **smaller version**: change every place that *names* the app, keep
"Imprint" as the short form inside sentences (D2), and do not touch one-click-release files.

## Target user
The owner at the start of the test campaign, asking: "Does the app call itself Imprint Studio and
its agents Kernel, Nova and Vector everywhere I look, and is all my data still there?"

## Goal and success measure
Every name surface shows "Imprint Studio", the three agents show their new codenames, and no state
moves. Demonstrated by:
1. New `tests/test_display_names.py` (offscreen, no network): (a) the window title, tray tooltip
   and both tray actions, menu-bar name, version tooltip, and the Documentation, Learning Centre
   and Income Lab window titles equal or contain `APP_DISPLAY_NAME == "Imprint Studio"`;
   (b) `runtime_paths.APP_NAME == "Imprint"`, `DB_PATH.name == "imprint.db"`,
   `SINGLE_INSTANCE_KEY` and both `QSettings("Imprint", "Imprint")` unchanged; (c) for every
   `AgentSpec`, the recommendation profile label, the seeded DB label and both manifest titles
   equal `spec.label`; (d) a scan of user-visible sources (string literals in `main.py`, `ui/`,
   `agents/*/panel.py`, `agents/*/agent.py`; `docs/learn/**`, `docs/agents/**`, `README.md`,
   agent READMEs) finds no `\bMuse\b` not followed by " Glimmer", no `\bStamp\b` as a name, and
   no agent titled "Chat", outside a short allow-list kept in the test.
2. `tests/test_agents_scenarios.py`: "open Kernel", "switch to Nova", bare "Vector." route to
   `chat`, `creator`, `fiverr`; the R3 sentences do not; `test_codenames_come_from_the_catalog`
   passes unchanged (`:170-178`).
3. `tests/test_cost_and_limits.py` (rename migration) and `tests/test_database_migrations.py` pass
   unchanged; a launch on the owner's existing data shows the same projects, chats and keys.
4. Full suite green (`.venv/bin/python -m pytest -q`); drift tests for the converter, benchmarks,
   providers, launcher and appkit guard pass with **no** edit to a shared file.
5. Screenshot checklist, taken from the installed app by the owner: window title; header
   wordmark; Dock label, Cmd-Tab and Activity Monitor name; menu-bar application menu; tray menu;
   version tooltip; the Assistant, Brand Content and Brand Design workspaces showing Kernel, Nova,
   Vector; the Vector panel stating PNG output; Learning Centre and Documentation windows; Lab
   Hub's tile launching the renamed app.

## Findings: the display name (grep, 2026-11-22)
`Imprint` occurs 734 times in 225 tracked files (excluding `.claude/`, `build/`, `dist/`). About
169 are in app Python; about 70 of those are text a user can read; about 16 are name surfaces.

| Surface | Where | Change? | Why |
|---|---|---|---|
| Window title | `main.py:252` | change | name surface |
| Header wordmark `IMPRINT` | `main.py:2391` | change (Design: does "IMPRINT STUDIO" fit?) | name surface |
| Menu-bar app name (terminal run) | `main.py:6664`, `ui/app_identity.py` | change the argument only | the module is a copy of Sentinel's; the name is passed in |
| Tray tooltip, Open/Quit | `ui/tray.py:63,67,72`; test `tests/test_tray.py:43` | change, via a new `APP_DISPLAY_NAME` | must stop reading `APP_NAME` |
| Version tooltip, self-test line | `services/version.py:188`, `main.py:6567` | change | name surface |
| Sub-window titles and accessible names | `ui/docs_center.py:146,149`; `ui/learning_center.py:108,121`; `ui/learning_center_v2.py:321,324`; `ui/income_worksheets.py:56` | change | name surface |
| About dialog | none found (`About` grep: 0 hits in `main.py`, `ui/`) | none | does not exist |
| Bundle display keys | `Imprint.spec:156-157`; `scripts/install_app.sh:80-81` | change | Dock, Finder |
| Bundle file and executable name | `Imprint.spec:120,140,152`; `install_app.sh:42-43,66,83`; `build_app.sh:30-36` | **D1** | see below |
| Sentences naming the app in dialogs and errors | about 54 literals in 27 files (e.g. `ui/dialogs.py:57,329`, `agents/video/panel.py:505-955`, `services/release_kit/*`) | **D2** (recommended: keep) | short form reads correctly; avoids one-click-release files |
| Info.plist usage strings | `Imprint.spec:166-167` | D2 | sentence |
| Exported text | `.env` header `services/api_keys.py:206` (`tests/test_api_keys.py:84,88`); `services/release_kit/provenance.py:76`; iCalendar `PRODID` `agents/creator/calendar.py:106` | PRODID changes (it also holds "Muse"); others D2 | |
| Prompt sent to a model | `agents/manuscript/agent.py:6`; `agents/music/suno_panel.py:204` | D2 | no effect on output expected; not verified |
| Web companion brand | `cloud/web/index.html:8,13` | change; "Imprint Narrator" (`:17,70`) stays | sub-product name |
| Docs | `README.md` 65; `docs/learn/**` 116 in 26 files; `docs/agents/*` 26; agent `*.md` 28; `docs/audiobooks-iphone-manual.md` 22; `tests/*.md` 17; `SUPPORT.md` 3; `SECURITY.md` 2 | titles and first mention per file; rest D2 | |
| `APP_NAME`, support folder | `services/runtime_paths.py:27,75,107` | **keep** | invariant: strands state |
| DB file, instance key, QSettings | `services/database.py:10`; `main.py:6527`; `ui/docs_center.py:140`; `ui/learning_center_v2.py:313` | **keep** | state |
| Drive folder "Imprint Progress" | `agents/audiobook/audiobook_library.py:32`; `cloud/reading_compass.py:216,456` | **keep** | shared with the phone companion |
| Bundle id, launch log, User-Agent | `install_app.sh:68,82`; `Imprint.spec:154`; `services/benchmarks.py:337` | **keep** | identifiers; benchmarks is a shared copy |
| `Imprint.spec` filename, object names | read by 6 tests (e.g. `tests/test_tray.py:76`); `ui/widgets.py:353` | **keep** | identifiers |
| Comments, docstrings, `vidforge/`, tests' headers | about 100 in code, 94 in 52 test files | keep | not shown; `vidforge` has no user-visible hit |
| `CHANGELOG.md` (9), specs, audits, ADRs, history | | **keep** | history stays as written |

## Findings: the three codenames (word-boundary grep)
| Area | Muse (130 in 45 files) | Stamp (79 in 36) | Chat as a label |
|---|---|---|---|
| Label sources (catalog, recommendations, DB seed, registry, manifests) | 5 | 6 | 7 (incl. `main.py:2605`) |
| Other app code | 32, of which 17 "Muse Glimmer" (keep); user-visible: `api_keys.py:77`, `calendar.py:106`; rest comments | 8, of which 2 verbs (keep); user-visible: `api_keys.py:61`, `ui/dialogs.py:1223`; rest comments | prose in comments only |
| Tests (`*.py`) | 14; label asserted in `test_agents_scenarios.py:141,151` | 10; asserted at `:153` | `test_panel_layout.py:898` |
| `README.md` | 7 (2 Glimmer) | 7 | 8 by pattern, not all the agent |
| `docs/learn/**` | 16 | 5 | module `19-assistant.md:137`, `12-best-fit.md:41` |
| `docs/agents/*` | 4 | 5 | `manifest.json:21`, `router.md:15` |
| Agent READMEs, TODO, SUGGESTIONS | 10 | 4 | 3 |
| `tests/*.md` (manual cases, gate, plan) | 16 | 15 | 3 |
| Root `TODO.md` / `SUGGESTIONS.md` | 10 / 3 | 8 / 1 | 4 / 0 |
| `CHANGELOG.md`, audits, other specs (keep) | 6 + 9 | 7 + 5 | 2 + 5 |

`docs/learn/help_map.json` holds none of the three names and no "Imprint". "Chat" cannot be
counted exactly by grep: a name pattern finds 66 hits in 38 files, most of them the activity or
the Sentinel-shared job type, which stay.

## Owner decisions needed
- **D1 Bundle name.** Lab Hub builds the path from the tile name: `/Applications/<name>.app`
  (`../lab_hub/lab_hub/launcher/state.py:50,1086`; `registry.py:214`; `apps.toml:40`).
  - **A, keep `/Applications/Imprint.app`**, change only the two display keys. Cost: 2 files. Risk:
    the Dock label, Cmd-Tab and Activity Monitor take the name Launch Services read from the
    bundle and executable (`ui/app_identity.py:31-36`), so they would probably still say
    "Imprint". Not verified on macOS 27.
  - **B, `/Applications/Imprint Studio.app` with executable "Imprint Studio" (recommended).** It is
    the only option that meets the lab rule "apps carry their own name". Cost: both install
    scripts and `Imprint.spec` (the `.spec` filename stays); the scripts must quit and remove the
    old `Imprint.app` or two apps exist (`build_app.sh:79-82`; `install_app.sh:96,111` match only
    the new path); `README.md:3049,3054,3187`, `main.py:6556`, `tests/TEST_PLAN.md`; Lab Hub
    `apps.toml:40` name becomes "Imprint Studio" and Lab Hub is rebuilt (lab rule; `apps.toml:3-6`
    says a Refresh is enough when its checkout is present, so the rebuild covers the bundled
    copy); the owner re-pins the Dock icon. macOS may ask again for Desktop and Documents access
    (not verified).
- **D2 Sentences.** Recommended: "Imprint" stays the short form inside sentences ("Imprint will
  not retry automatically"); only name surfaces, document titles and the first mention per
  document change. Alternative: replace all of about 70 literals and about 280 doc mentions; about
  70 more files, including six one-click-release files.
- **D3 "Nova Drift".** Recommended: change the two examples a user sees (`agents/music/panel.py:56`,
  `README.md:1413`) to another artist name, so Label does not appear to reference Nova; leave the
  test fixtures (`tests/test_music_plans.py`, 12 uses) as data.
- **D4 Old names.** Recommended: "open Muse" and "open Stamp" stop routing (no aliases).

## Requirements that are not optional
- **R1 Vector says PNG.** Vector produces raster PNG files, and audit QM-18 is open because the
  agent promises vector files (`TODO.md:79`; `agents/fiverr/agent.py:24,35`). With this name the
  promise gets louder. The Vector panel, `docs/agents/fiverr.md` and its Learning Centre page each
  state, where the user starts a logo: "Vector makes PNG images, not vector files. Trace them to
  SVG in a vector tool before client delivery." QM-18's prompt and claims fix ships with or before
  this change.
- **R2 One source for labels.** The copies listed under Problem are derived from the catalog or
  pinned to it by measure 1(c).
- **R3 Router.** Codenames are addressable names read from the catalog, not intent keywords
  (`agents/router/agent.py:68-83`); no entry is added to `ROUTES` (`:44-60`), and none of its
  keywords contains "kernel", "nova" or "vector". The addressing rule matches an opener plus the
  name, so "use the nova voice" (an OpenAI voice, `vidforge/config.yaml:29`) would go to Nova and
  "use vector files" to Vector. These join `test_an_ordinary_word_is_not_an_address` (`:158-168`)
  and must stay unaddressed, with "kernel panic on my Mac".
- **R4 No retired-name ban.** `tests/test_retired_names.py` bans one moved venture's name in every
  tracked file, history included. Adding "Muse", "Stamp" or "Chat" there would fail on Muse
  Glimmer, the verb and the common word, and would force rewriting the CHANGELOG. The scoped scan
  in measure 1(d) replaces it.

## Non-goals
Renaming the repo, package, `APP_NAME`, support folder, database, bundle id or `Imprint.spec`.
A new icon. An About dialog. Aliases for old codenames. Rewriting history files. `vidforge/`.
The Learning Centre content work (`docs-learning-centre-readiness`). Any change to a file copied
between apps (`services/narrator/converter.py`, `services/benchmarks.py`, `scripts/app_launcher.c`,
`ui/appkit_guard.py`, the routing files). EU AI Act Art. 50 and CRA: no generated content, no
change to commercial availability.

## Scope and size (files touched, recommended options D1-B, D2 short form)
1. Name surfaces: new `APP_DISPLAY_NAME` beside `APP_NAME`; 13 code and packaging files; 4 tests.
2. Codenames: `agents/catalog.py`, 3 recommendation profiles, DB seed, `registry.json`, `main.py`,
   3 other UI strings, the Vector PNG statement; 2 manifests; about 30 doc files; 2 tests; comments
   and docstrings naming the agent in `agents/{creator,fiverr,chat}/`.
3. Backlog: open rows in `TODO.md` and `SUGGESTIONS.md` use the new names; done rows stay.
4. Outside this repo (owner's OK needed, separate commits): Lab Hub `apps.toml` and rebuild; Lab
   Project Monitor regenerated. Foundry `apps.md:9` lists the folder `imprint` and needs no edit.
   Sentinel mentions "Imprint" 56 times in 31 files, all code comments, history or its own
   backlog: no edit.
Total: about 60 files here, 1 in Lab Hub. With D2's alternative: about 130.

## Phases
Design: one question only (the wordmark and Dock label; `ux-designer`, short). Architect: skipped
if D1-A; with D1-B a short note on removing the old bundle, no ADR (no state, thread or boundary
change). Secure: required with D1-B (install scripts delete a bundle). Review, Verify (measures
1-5), Document: required. **Comply: required and a gate**: tier `public` needs the name check and
the owner's sign-off; `docs/legal/name-candidate-imprint-studio.md` is a draft with the EUIPO,
Irish, CRO and WIPO searches unrun, and it proposes amending the open IMPRINT `LAWYER:` line in
`docs/legal/register.md`. That line stays open, so Release stays stopped until a qualified person
decides it. Launch: skipped (no announcement).

## Risks
- **In-flight work.** Branches `claude/one-click-release-slice1-fixes2`, `-599646` and
  `claude/nostalgic-ellis-342115` exist with worktrees under `.claude/worktrees/`; whether they are
  merged is not verified here (`TODO.md:63` and `:332` disagree). Sequence: the owner first merges
  or parks `fixes2`; this rename then lands as two small commits (name surfaces, then codenames)
  on one branch, and any parked branch rebases onto it. With D2's short form the rename touches no
  `release_kit` file, so conflicts are limited to `main.py`, `README.md` and `TODO.md`.
- **Name not cleared.** The build can finish and still not be releasable; a second rename would
  repeat the name-surface commit (13 files), which is why the name sits in one constant.
- **Two apps in /Applications** after D1-B if the old bundle survives; measure 5 checks it.
- **Shared copies.** A blanket replace would edit copied files and fail five drift tests, or pass
  them by breaking the pair. Measure 4 forbids it.

## Open questions
1. D1 to D4 above.
2. Does the QM-18 fix ship inside this change or just before it?
3. The bundle id is `com.netrunner3000.imprint` (`install_app.sh:82`, `Imprint.spec:154`) in a
   public repo. It stays here by decision 2; should a later change with a migration replace it?
