# Imprint — QA Test Plan

**Status:** draft for review · **Revised:** 2026-10-09 · **Baseline commit:** `e23f3cd`
**Owner:** `@me` decides scope and budget; `@ai` writes and runs tests, same tags as `TODO.md`.
**Companions:** `tests/manual_test_cases.md` (the hand-driven UAT script),
`tests/conftest.py` (what every automated run guarantees), `TODO.md` (where
findings are filed).

This document says **what** gets tested, **how deep**, **when**, and **to what
bar** before a build is called good. The UAT script is the hand-driven half of
that; the pytest suite is the regression floor underneath it. Neither is
repeated here — where they already cover something, this plan points at them.

---

## Table of contents

1. [Scope](#1-scope)
2. [Where we stand — baseline](#2-where-we-stand--baseline)
3. [Risk model and severity](#3-risk-model-and-severity)
4. [Strategy — the test tiers](#4-strategy--the-test-tiers)
5. [Gap-closure backlog](#5-gap-closure-backlog)
6. [Non-functional testing](#6-non-functional-testing)
7. [Environments and test data](#7-environments-and-test-data)
8. [Cadence — what runs when](#8-cadence--what-runs-when)
9. [Entry and exit criteria](#9-entry-and-exit-criteria)
10. [Defects, flakes and the failing-first rule](#10-defects-flakes-and-the-failing-first-rule)
11. [Metrics](#11-metrics)
12. [Tooling to add](#12-tooling-to-add)
13. [Risks to this plan](#13-risks-to-this-plan)
- [Appendix A — coverage map including the untested modules](#appendix-a--coverage-map-including-the-untested-modules)
- [Appendix B — commands](#appendix-b--commands)

---

## 1. Scope

**In scope**

- The desktop app: ten agents in eight workspaces (Quill, Press · Booth, Label ·
  Reel · Herald · Sitebuilder · Stamp · Muse · Chat) plus the Intent Router,
  as `agents/catalog.py` lists them. If this plan and the catalog disagree, the
  catalog is right.
- The shared systems every agent routes through: the spend guard
  (`authorize_request` / `record_request` / `abandon_request` /
  `restore_request` in `main.py`), the validator and budget caps, pricing and
  per-unit pricing, model assessment (BEST FIT, Model updates, ratings),
  projects and artifacts, history and the run log, Settings, Learning Centre,
  themes, layout at every supported window size, restart recovery.
- Persistence: `data/imprint.db`, its schema and its migrations.
- The six provider clients and the voice providers; the Herald publishers.
- Packaging: `Imprint.spec`, `scripts/build_app.sh`, `app_launcher.c`,
  `--selftest`, `runtime_paths`.
- `vidforge` as consumed by Reel, and `cloud/` (Reading Compass).

**Out of scope**

- `sentinel` and `lab_hub` themselves — only the drift guards that compare
  shared modules against them.
- `providers/avatar/` until it is wired (TODO P3); the guard that it stays
  unwired is in scope.
- Earning-income content in README §21 — documentation, not behaviour.

---

## 2. Where we stand — baseline

Measured on the checkout at `e23f3cd` (2026-10-09).

| Measure | Value |
|---|---|
| Test files | 60 (`tests/test_*.py`) + `conftest.py` |
| Collected | **1 377** (seed-1 randomised run, 2026-10-09 16:08: 1 370 passed, 5 failed, 2 skipped) |
| Suite wall time | ~100 s in file order; **194 s** under `--randomly-seed=1` (2026-10-09) — the shuffle defeats module-scoped window reuse; budget in §6 raised to 240 s for randomised runs |
| Files that build the whole window (`GodAI(`) | 24 of 60 |
| Source modules under `services/ agents/ ui/ providers/ cloud/ vidforge/` | 150 |
| Modules **no test file names** | 14 (see §5 and Appendix A) |
| `main.py` | 5 464 lines, one class, 277 methods |
| CI | none — the suite runs only when someone runs it |
| Coverage measurement | none (`pytest-cov` not installed) |
| Markers in use | `parametrize`, `skipif` (darwin-only ×2, vidforge deps ×1); `pytest-randomly` pinned in `requirements-dev.txt` since 2026-10-09 |

### What is already strong — keep it

- **Isolation is unconditional, not a convention.** `conftest.py` forces
  `QT_QPA_PLATFORM=offscreen` before any Qt import, points `DB_PATH` at a
  temp database, and scrubs all 24 credential/endpoint names so the
  developer's `.env` cannot reach a test. The 2026-10-06 incident (a live key
  one unmocked call from spending) is closed by construction.
- **A wedged run fails instead of sitting.** `pytest.ini` sets a 300 s
  per-test timeout with `timeout_method = thread`, which is the only method
  that can end a Qt mutex wait and dumps every thread's stack on the way out.
- **Mutation-verified fixes are the house habit.** Nearly every closed card in
  `TODO.md` names the test, then the mutation that fails it. This plan makes
  that a stated rule (§10).
- **Layout is tested at sizes, not eyeballed.** `test_panel_layout.py` (1 347
  lines) checks every panel and sub-page at every supported size: no field
  under the text floor, no row crushed below its minimum, no nested scroller.
- **Drift guards** pin `services/benchmarks.py` to Sentinel's copy and the
  narrator converter to lab_hub's, skipping cleanly when the sibling checkout
  is absent.
- **The UAT script** separates `FREE` / `PAID` / `PAID-UNIT`, orders shared
  systems before agents, has a "must not happen" part, and tells the tester
  how to recognise a wedged run.

### Gaps this plan closes

1. **No CI.** A green suite is a claim about one machine at one moment.
2. **No coverage numbers.** "A test file names the module" is the best proxy
   available today; it is weak (it counts a mention in a docstring).
3. **Fourteen modules nobody tests directly**, two of which sit under money
   or the frozen build: `services/runtime_paths.py` (where the writable data
   directory goes — the thing `--selftest` exists to check) and the two
   untested clients (`deepseek_client.py`, `kimi_client.py`).
4. **Most of vidforge** (`trends`, `cli`, `courses`, `ffmpeg_utils`, `llm`,
   `ideation`) has no direct tests; `test_vidforge_contract.py` skips when its
   dependencies are missing, so it can be silently absent from a run.
5. **The migration path had zero coverage until 2026-10-06** and the one
   defect it hid was a paid render never resumed. There is now one synthetic
   "older database" test; there are no real historical snapshots.
6. **Crash-and-resume is manual-only** (UAT A11). The promise — authorized
   money is never lost and never billed twice — is the app's most important
   one and the suite cannot currently kill the process to check it.
7. **No live-provider contract tier.** Every provider is mocked. Providers
   change (Veo's shutdown, google-genai's TTS surface, LMArena's table);
   `scripts/check_keys.py` is a hand step, not a test.
8. **The packaged build is not smoke-tested.** `--selftest` exists;
   nothing runs it against a fresh `Imprint.app`.
9. **Order-dependent Qt deadlocks have happened twice** (57 min, 25 min). Both
   root causes are fixed, but nothing runs the suite in randomised order or
   repeatedly to prove the class is closed.
10. **No non-functional tests at all** — startup time, memory under a long
    narration, large-manuscript handling, provider timeouts/429s per client.
11. **`main.py` is a 5 464-line god object.** 24 test files pay the cost of
    building it; its 277 methods are tested through the window, never in
    isolation. Not a QA gap to fix with tests — a refactor risk the plan has
    to stay alert to (see `docs/refactor_plan.md`).

---

## 3. Risk model and severity

Imprint spends the user's money on their behalf and keeps the only copy of
their creative work. Severity follows from that, not from how visible a bug is.

| Sev | Definition | Examples | Response |
|---|---|---|---|
| **S0** | Money moves without approval, or moves twice | A paid call outside the guard; a resumed job re-billed; a cap not enforced; the free-local offer sending to a cloud model | Stop the line. Fix before any other work. Failing-first test + mutation check mandatory |
| **S1** | Work or state lost; app cannot start; wrong bill recorded | Migration leaves a column missing; a crash mid-render is never resumed; a project deletion takes another project's artifacts; `[warn]` at launch | Fix in the current session; UAT A1/A4/A11 re-run |
| **S2** | Wrong result, misroute, misleading figure | Router sends "press release" to Press; BEST FIT picks an unpriced or unrated model over a rated one; an estimate that differs from the bill | Fix before the next release |
| **S3** | Layout, wording, cosmetic | A field under the text floor at 1000 px; a tooltip left over; theme colour off | Batch; must not block |

### Risk register — what can hurt, and what already holds it

| Area | Failure that matters | Sev | Automated today | Gap |
|---|---|---|---|---|
| Spend guard (authorize / record / abandon / restore) | Paid call bypasses the dialog; reservation leaks; double record | S0 | `test_request_guard.py` (834 lines), `test_cost_and_limits.py` | No cross-agent sweep that **every** Send path hits the guard; no property-based money maths; no mutation tooling |
| Budget caps + free-local offer | Cap not applied by scope; offer names a model that is not pulled | S0 | `TestLocalFallbackOffer`, scope-aware `ValidationResult` | Fine. Keep the daemon stub autouse |
| Per-request assessment / Model updates / ratings | Unrated or unpriced model wins; silent switch | S2 | `test_model_watch.py` (868), `test_model_ratings.py`, `test_media_assessment.py`, `test_recommendations.py` | Ratings snapshot staleness is a hand check; dated price changes are time-dependent — freeze the clock |
| Pricing tables | A model offered with no price row; a rate stale after an announced change | S1 | `test_settings_pricing.py`, `test_voice_and_rates.py`, "every KNOWN_MODEL has a price row" | Live price drift (provider page vs `pricing.json`) is manual |
| Persistence and migrations | Older DB missing a column; startup reconciler swallows it | S1 | `test_database_migrations.py` (7) | One synthetic older DB; no real snapshots; no concurrent-writer test; no backup/restore |
| Crash and resume of paid per-unit jobs (Booth, Reel, Muse, Stamp) | Job neither resumed nor settled; or resumed **and** re-billed | S0 | Resume logic unit-tested; `test_video_jobs.py`, `test_creator_resume.py` | Process is never actually killed. UAT A11 only |
| Intent Router | Wrong agent, hidden ambiguity, stale WHY | S2 | `TestRouterAgent` | Good. Add a corpus file so new phrasings are one line, not one test |
| Projects / artifacts / deletion | Cross-project leakage; orphaned files | S1 | `test_agent_projects.py`, `test_chat_projects.py` (757) | Disk-vs-DB consistency after delete is UAT A4 only |
| Booth (narration, converter, player) | Chunking drift breaks resume; failed chunk continues; player threads leak | S1 | `test_narrator_converter.py` (841), `test_audiobook_*`, `test_booth_routes.py`, `test_converter_drift.py` | No real ffmpeg round-trip; no awkward-EPUB corpus; M4B chapter markers unchecked |
| Reel / vidforge | ffmpeg missing or wrong; YouTube OAuth path; pre-estimate vs render | S1 | `test_video_jobs.py` (709), `test_media_generation.py`, `test_vidforge_contract.py` (skips without deps) | Six vidforge modules untested; the contract test can vanish silently |
| Herald publishers (Reddit, Pinterest, YouTube) | Token expiry, rate limit, duplicate post | S1 | `test_social.py`, `test_social_onboarding.py` | No live contract; idempotency on retry not pinned |
| Press exports (DOCX / PDF / KDP) | Unreadable file; malformed KDP CSV crashes the parser | S2 | `test_book_pipeline.py`, `test_manuscript_charts.py` | Export validity (reopen with `python-docx` / `pypdf`); KDP fuzz corpus |
| Sitebuilder export | Broken local refs, invalid HTML | S2 | `test_webdesign_export.py`, `test_webdesign_panel.py` | Parse the export; check every `href`/`src` resolves |
| Stamp / Muse image & teaser routes | Wrong provider key checked; render posted twice | S0/S1 | `test_image_routes.py`, `test_higgsfield_client.py`, `test_teaser_routes.py`, `test_creator_*` | Covered; keep under the guard sweep |
| Provider clients ×6 | Error mapping, timeout, 429, usage parsing differ by client | S1 | Anthropic, Gemini (one attempt), Higgsfield tested individually | **DeepSeek and Kimi have no tests.** No uniform client contract |
| Layout / themes / header | Overlap, crushed rows, header shedding order | S3 | `test_panel_layout.py`, `test_agent_panel.py`, `test_theme.py`, `test_vibe.py` | `ui/header_fit.py` and `ui/tooltips.py` have no direct tests; header shedding is UAT A1 only; no keyboard-navigation test |
| Packaging / frozen build | Data dir inside the bundle; resource missing; `.env` baked in | S1 | `test_app_launcher.py`, `test_app_identity.py`, `test_appkit_guard.py`, `test_version.py` | `runtime_paths.py` untested; `--selftest` never run against a built `.app` by anything automated |
| Secrets | Key in run log, DB, history or tooltip | S0 | env scrub, `test_env_template.py`, password fields never revealed, gitleaks locally | No assertion that persisted rows and logs are key-free after a full request cycle |
| `cloud/` Reading Compass | Web half drifts from its contracts | S2 | `test_reading_compass_contracts.py` | `reading_compass.py` (625 lines) untested; Dockerfile unbuilt |
| Learning Centre / Docs | Stale screenshots; broken recipe | S3 | `test_learning_center.py`, `test_learning_shots.py`, `test_docs_center.py` | Fine |

---

## 4. Strategy — the test tiers

Six automated tiers plus the hand-driven one. Each tier has a marker, a time
budget and a trigger. Anything not marked is Tier 1 or 2 and runs on every
commit. The tiers are additive: a release runs all of them.

| Tier | Marker | What belongs here | Budget | Runs |
|---|---|---|---|---|
| **T0 Static & guards** | *(none — plain tests)* | Drift guards; `.env.example` vs code; retired names; catalog ↔ docs roster; "no paid path outside the guard" AST sweep; gitleaks; `ruff` | < 10 s | every commit |
| **T1 Unit** | *(none)* | Pure logic with no window: validator, pricing, per-unit pricing, router, ratings/recommendation engine, converters, exporters, clients against recorded responses | < 20 s | every commit |
| **T2 Component (offscreen window)** | *(none)* | Builds `GodAI` offscreen: guard dialogs, panel state, layout at sizes, themes, streaming, projects | ~70 s | every commit |
| **T3 Integration & recovery** | `@pytest.mark.recovery` | Real SQLite with historical snapshots; subprocess kill-and-relaunch; real ffmpeg round-trip; export reopen | ~2 min | pre-merge, nightly |
| **T4 Live contract** | `@pytest.mark.live` | One **free** metadata call per keyed provider; one minimal paid call per per-unit route under a hard cap; publisher auth checks | varies; **≤ €0.50 per run** | weekly, pre-release, opt-in only |
| **T5 Build smoke** | `@pytest.mark.build` | `build_app.sh` → `Imprint.app --selftest`; version badge derived; data dir outside bundle; no `.env` in the bundle | ~5 min | pre-release |
| **T6 Non-functional** | `@pytest.mark.soak` / `perf` | Randomised-order ×3 and repeat runs; startup and narration budgets; memory ceiling; provider failure-mode matrix | 10–20 min | nightly |
| **UAT** | `tests/manual_test_cases.md` | Everything a human has to judge | FREE pass ~2 h; PAID pass budgeted | pre-release; after any S0/S1 fix in that area |

`pytest.ini` gains `addopts = -m "not live and not build and not soak"` so a
bare `pytest -q` stays the ~90 s run it is today, and the markers are
registered so a typo in one fails collection instead of silently selecting
nothing.

**Rules that hold across tiers**

- Nothing in T0–T3 or T6 may reach the network. The `conftest.py` env scrub
  already guarantees no credential is present; add a `socket`-level tripwire
  so an unmocked call fails with a clear message rather than a timeout.
- T4 reads keys from `.env.test`, never `.env`, and sets Settings' daily cap to
  the run's budget before the first paid call. A T4 run that cannot read a cap
  does not start.
- Every test that pins a defect names the `TODO.md` card in its docstring and
  records the mutation that fails it. (This is already the habit; it is now the
  rule — §10.)
- A test that builds `GodAI` must release it: `closeEvent` sweeps workers and
  players, and the fixture must call it. The two deadlocks came from the
  exception.

---

## 5. Gap-closure backlog

Ordered by severity of the risk each one closes, then by cost. Each item is
sized for one session. File cards in `TODO.md` under `testing` / `infra` as
they are picked up.

### P0 — money and recovery

1. **Guard sweep: no Send path reaches a client without `authorize_request`.**
   `tests/test_no_paid_path_outside_guard.py`. Two halves. *(a)* Dynamic: an
   autouse fixture monkeypatches every network method on all six clients, the
   voice providers, image generation and Higgsfield to raise `PaidCallWithoutGuard`;
   for every agent, drive its Send/Render/Convert/Publish entry with a guard
   stubbed to **refuse**, assert nothing raised and nothing recorded.
   *(b)* Static: walk `main.py` and `agents/*/panel.py` with `ast` and list
   every call into a client module; assert each is inside a method that is on
   an allowlist of guarded entry points. A new call site fails until it is
   reviewed and added. Mutation: delete one `authorize_request` call — both
   halves must go red.
2. **Kill-and-resume, for real.** `tests/test_crash_recovery.py`
   (`@recovery`). A subprocess launches a headless harness that: creates a
   temp DB, authorizes a fake per-unit job (Booth chunking, Reel render, Muse
   teaser, Stamp images — parametrized), marks it in flight, then is
   `SIGKILL`ed at three points (before first write, mid-run, after output but
   before settlement). Relaunch the reconciler (`resume_pending_*`) in a
   second subprocess; assert: exactly one of {resumed to completion, settled
   as abandoned}; spend recorded once; `reserved` returned to zero; run log
   closed; no `[warn]` on stderr. Run against a DB built from `SCHEMA` **and**
   against each historical snapshot in item 3.
3. **Historical database snapshots.** `tests/fixtures/db/`: dump the schema
   (not data) of `data/imprint.db` as it stood at each tagged release and at
   `a8235bb` (pre-P2) and before the `creator_video_jobs` duplicate-key fix.
   Extend `test_database_migrations.py` to parametrize over every snapshot:
   `init_db()` heals it, every panel's own queries run, idempotent on a second
   pass. Add a snapshot each time `SCHEMA` changes (a T0 test fails if `SCHEMA`
   changed and no new snapshot was added).
4. **Property-based money maths.** `hypothesis` over `Validator.validate`,
   `pricing_catalog`, `per_unit_pricing`: estimate ≤ cap never refused, > cap
   always refused, at exactly the cap behaves as documented; Decimal rounding
   never drops below the per-request minimum; EUR formatting round-trips;
   per-unit cost is monotone in units. Mutation: flip one comparison.
5. **Secrets never persist.** After a full mocked request cycle per agent
   (authorize → stream → record), scan every row of every table, the run log,
   the chat history files and `data/reports/` for the sentinel key values
   the test injected. Also assert `.env` is created `0600` by the setup path
   and that the frozen build's data dir contains no `.env`.

### P1 — state, clients, build

6. **Uniform client contract test.** `tests/test_client_contract.py`
   parametrized over all six clients (`anthropic, openai, deepseek, gemini,
   kimi, qwen`) and the voice providers against **recorded** responses in
   `tests/fixtures/http/`: `list_models` shape; usage/token parsing; error
   mapping for 401 / 404 / 429 / 5xx / timeout / truncated stream; retry
   policy (Gemini: exactly one attempt — already pinned, fold it in); a
   model id not in KNOWN_MODELS still bills at its base model's rate. This is
   what gives DeepSeek and Kimi their first tests.
7. **`runtime_paths` under both run modes.** Checkout vs frozen (`sys.frozen`
   and `sys._MEIPASS` monkeypatched): data dir is writable and outside the
   bundle; log, DB, reports and `.env` locations resolve where README §19
   says; a read-only bundle path never receives a write. Then make
   `--selftest` call the same function so the two cannot disagree.
8. **Build smoke** (`@build`). `scripts/build_app.sh` into a temp prefix,
   then run `Imprint.app/Contents/MacOS/Imprint --selftest`; assert exit 0,
   the version in `_build_info.json` matches the badge logic in
   `services/version.py`, every `datas` entry in `Imprint.spec` exists in the
   bundle, and `grep -r` finds no provider key pattern inside it.
9. **Header shedding and tooltips, automated.** Extend `test_panel_layout.py`
   with `ui/header_fit.py`: at descending widths assert the status pill, then
   the version badge, disappear before any workspace tab; overflow tabs land
   in **More ▾** and nothing is clipped. For `ui/tooltips.py`: Tooltips Off
   hides help but a cut-off value still shows on hover; a password field never
   does (the UAT checks exist — pin them).
10. **vidforge direct tests.** `ffmpeg_utils` (command construction, never
    `shell=True`, failure surfaces as an exception with stderr attached);
    `trends`/`ideation`/`llm` against recorded responses; `cli` argument
    parsing; `courses` plan shape. Make `test_vidforge_contract.py`'s skip
    **loud**: a T0 test asserts the vidforge dependencies import in the
    dev venv so the contract test cannot be silently absent.
11. **Export validity.** Press DOCX/PDF: reopen with `python-docx` / `pypdf`,
    assert chapter headings, page count > 0, metadata set. Sitebuilder: parse
    with `lxml`, every local `href`/`src` resolves inside the export, no
    inline provider key, no absolute path from the dev machine. Booth M4B:
    `ffprobe` shows one chapter marker per chapter in order.
12. **Publisher idempotency.** Herald: a retry after a network error does not
    post twice (dedupe key honoured); an expired token surfaces as "reconnect"
    not as a traceback; a 429 backs off and keeps the queue intact.

### P2 — breadth

13. **Router corpus.** Move the phrasing cases into
    `tests/fixtures/router_corpus.yaml` (`input → agent, confidence, must
    mention`), one parametrized test reads it. UAT A3's seven cases are the
    first rows; every misroute found in use adds a row.
14. **KDP report fuzz.** A corpus of malformed CSVs (BOM, semicolon locale,
    missing columns, thousands separators, empty file, 100 k rows); parser
    never raises past its boundary; charts render with partial data.
15. **Awkward-EPUB corpus** for Booth: images-only chapter, nested TOC, no
    TOC, one 2 MB chapter, RTL text, a DRM'd file (refused with a message).
16. **`cloud/reading_compass.py`** unit tests against its contracts; build
    the Dockerfile in T5 and hit `/health`.
17. **Concurrent writers.** Two worker threads writing the run log and usage
    tracker while the UI reads: no `database is locked` reaches the user;
    WAL mode or the retry wrapper holds.
18. **Keyboard path.** Tab order through each panel's control bar reaches
    Send; Esc closes the paid dialog as **Cancel**, never as Approve.

---

## 6. Non-functional testing

### Stability (soak) — the Qt deadlock class

Both wedges were order- and timing-dependent, so one green run proves little.
Nightly, `@soak`:

- Full suite with `pytest-randomly`, three different seeds, each under the
  300 s per-test timeout. A wedge now dumps stacks and fails.
- `tests/test_audiobook_player.py` ×10 with `pytest-repeat`, then assert no
  `QMediaPlayer` or FFmpeg thread survives the module (count threads before
  and after).
- Record the seed of any failure in the card; replay it before closing.

### Performance budgets

Measured on the dev Mac; CI numbers are recorded, not gated, until there is
a baseline.

| What | Budget | How |
|---|---|---|
| Cold start to `● Ready` (checkout) | ≤ 4 s | `--selftest` wall time + a window-built timer in T2 |
| Cold start, frozen `.app` | ≤ 6 s | T5 |
| Suite, bare `pytest -q` | ≤ 120 s (≤ 240 s randomised) | CI step timeout; investigate above 100 s in order |
| Narrator chunking of a 1 MB EPUB | ≤ 5 s | T3, no network |
| UI stays responsive during a long job | event loop never blocked > 250 ms | a watchdog `QTimer` in T2 jobs tests |
| Memory after a 50-chunk mock narration | no growth > 50 MB run-to-run | `services/resource_monitor.py` readings in T3 |
| `imprint.db` after 1 000 run-log rows | < 20 MB; `VACUUM` path works | T3 |

### Security checks (every release)

- Secrets-never-persist test (item 5) green.
- `gitleaks detect` clean on the tree **and** on the built bundle.
- `.env` and `.env.test` `0600`; both gitignored (already pinned).
- No `subprocess(..., shell=True)` with user-controlled text anywhere under
  `vidforge/`, `services/narrator/`, `scripts/` — an AST test.
- Password fields never revealed by the text-fit hover (pinned).
- Dependency audit: `pip-audit` on `requirements*.txt`; PySide6 and the
  provider SDKs pinned to tested versions (`google-genai` TTS note in TODO).

### Resilience matrix — provider failure modes × clients

Run in T1 against recorded responses; the matrix is the parametrization of
item 6. Every cell must end in one of: a clear user-facing message, a retry
that is bounded, or an abandoned request with its reservation released.
Never: a traceback, a silent partial result billed as full, a hang.

| Failure | Text clients | TTS routes | Image / video routes | Publishers |
|---|---|---|---|---|
| 401 bad key | message names the provider; key check offered | same | same | "reconnect" |
| 404 model gone | model removed from live list; BEST FIT re-ranks | route marked unavailable | same | n/a |
| 429 | bounded backoff; estimate unchanged | chunk retried, run not duplicated | job not re-submitted | queue intact |
| 5xx / timeout | abandon → reservation released | failed chunk **stops** the run (pinned) | Stop contract honoured | retry once |
| Truncated stream | partial shown, billed on actual usage | chunk rejected | n/a | n/a |
| Network down | local-only offer where it applies | refused before spend | refused before spend | queued |

---

## 7. Environments and test data

**Dev Mac (primary).** Python 3.11+ in `.venv`, PySide6, ffmpeg on PATH,
Ollama with a general instruct model (`llama3.1:8b` — never a reasoning model
for UAT), `.env` for use and `.env.test` for T4 with its own small caps.
Everything in §4 runs here. The Cowork Linux VM that mounts this folder cannot
run the suite (no Mac venv, Python 3.10) — it is for reading and editing only.

**CI (to add).** GitHub Actions, two jobs:
- `macos-latest` (arm64): full T0–T2 on every push and PR; T3 on PR; T6 soak
  nightly. Install ffmpeg via brew. Darwin-only tests run here.
- `ubuntu-latest`: T0–T1 only, as a fast early signal (darwin-only tests
  skip; Qt offscreen works for T2 but is not required on this job).
- Secrets: none in CI by default. T4 runs from a manually-triggered workflow
  that reads an `IMPRINT_TEST_ENV` secret with the tiny-cap keys.

**Test data** (`tests/fixtures/`, all committed, none containing a secret):
- `db/` — schema snapshots per release (item 3).
- `http/` — recorded provider responses per client and failure mode (item 6).
- `epub/` — the awkward-EPUB corpus (item 15); files small enough to commit.
- `kdp/` — malformed report corpus (item 14).
- `router_corpus.yaml` (item 13).

**Disposable state.** UAT creates and deletes `UAT <date>`; automated runs
use `tmp_path`. Nothing writes to `data/imprint.db` — `conftest.py` makes
that impossible; keep it that way.

---

## 8. Cadence — what runs when

| When | What | Who |
|---|---|---|
| Every commit (local pre-commit hook) | `ruff`, `gitleaks protect`, T0 | `@ai` / `@me` |
| Every push / PR (CI) | T0–T2; T3 on PR | CI |
| Before merging to `main` | T0–T3 green; any new behaviour has a failing-first test; UAT section for the touched area re-run if it is `FREE` | `@ai` proposes, `@me` merges |
| Nightly (CI) | T6 soak (randomised ×3, player ×10); perf numbers recorded | CI |
| Weekly | T4 live contract (free metadata calls only unless a per-unit route changed); `pip-audit`; price table vs provider pages (hand check until item 6's recorded fixtures are refreshed) | `@ai` |
| Pre-release | Everything above + T5 build smoke + full UAT `FREE` pass + budgeted `PAID`/`PAID-UNIT` pass on a fresh `.app` | `@me` drives UAT |
| After any S0/S1 fix | The pinning test, its mutation, and the UAT section that would have caught it by hand | `@ai` |
| Quarterly | Re-record provider fixtures; refresh LMArena snapshot and `pricing.json`; review the risk register in §3; re-capture Learning Centre screenshots if a layout pass happened | `@ai` + `@me` |

---

## 9. Entry and exit criteria

**Entry to UAT**

- [ ] `pytest -q` green three times with different `-p randomly` seeds, none
      exceeding 120 s, none hitting the per-test timeout
- [ ] Launch from a terminal prints only Qt's FFmpeg line — no `[warn]`
- [ ] `main.py --selftest` passes
- [ ] `scripts/check_keys.py` green for every provider the PAID pass will use
- [ ] Settings daily cap set to the session budget; `UAT <date>` project
      does not already exist

**Exit — a build may ship**

- [ ] No open S0 or S1 in `TODO.md`
- [ ] UAT Part A and Part C fully ticked; Part B ticked for every agent
      shipping in this build
- [ ] T5 build smoke green on the exact artifact being shipped
- [ ] T4 run within the last 7 days with no contract break, or the break is
      filed and worked around in-app
- [ ] Line coverage not below the recorded baseline (ratchet, never regress —
      §11)
- [ ] `agents/catalog.py`, README §2 table and `manual_test_cases.md` A2
      agree on the roster (T0 test)
- [ ] `VERSION` / `_build_info.json` stamped; badge reads `v2.<build>`

A release that fails one exit criterion ships only with a written waiver in
the release card naming the criterion and the compensating control.

---

## 10. Defects, flakes and the failing-first rule

**Filing.** Every finding is a `TODO.md` card with the existing tags
(`P0`–`P3`, category, `@me`/`@ai`, `agent:<key>` when scoped). Severity from
§3 maps to priority: S0→P0, S1→P1, S2→P2, S3→P3. The card records: commit
observed, steps or test, expected vs actual, and — when closed — the pinning
test and the mutation that fails it.

**Failing-first.** A fix is not done until a test that failed on the old code
passes on the new one. Write the test, watch it fail, then fix. A test that
passes on both sides is vacuous (the last adversarial review found four) and is
rewritten or deleted.

**Mutation-verified.** For S0/S1 fixes, revert the fix (or break one line of
it) and confirm the test goes red; name the mutation in the card. For money
maths and the guard, run `mutmut` on the module (§12) and keep surviving
mutants under 10 %.

**Flakes.** A test that fails and then passes with no code change is a defect
in the test or a race in the app — never "just a flake". Mark it
`@pytest.mark.flaky_quarantine` with the card number, keep it running (not
skipped) so the failure rate is known, and fix or delete within two working
sessions. More than three quarantined tests at once blocks merging new ones.

**A wedge is a failure.** Under `-q` a hung run prints nothing. If a run is
silent past three minutes, it has not slowed down — sample or let the
300 s timeout dump stacks, and file it.

---

## 11. Metrics

Recorded per run in CI (a small JSON appended to an artifact), reviewed
weekly. Numbers, not targets, until a month of baseline exists.

| Metric | Source | Why |
|---|---|---|
| Line and branch coverage, total and for `services/validator.py`, `services/*pricing*.py`, the guard methods in `main.py`, `services/database.py` | `pytest-cov` | The money and persistence modules should be near 100 %; the total should ratchet up, never down |
| Modules with zero direct coverage | coverage report | Today 14; target 0 by the end of the backlog |
| Suite wall time (bare run) | CI | Above 120 s, split or mark |
| Flake rate (fails-then-passes / runs) | CI history | Above 1 % means a race is open |
| Surviving mutants in money modules | `mutmut` | Under 10 % |
| Defects found by UAT that an automated tier could have caught | card review | Each one becomes a backlog item in §5 |
| Live contract breaks per quarter | T4 | Tells us how often fixtures must be re-recorded |

---

## 12. Tooling to add

Append to `requirements-dev.txt`, pinned once the first run is green:

```
pytest-cov          # coverage; the first measurement sets the ratchet baseline
pytest-randomly     # randomised order — the only honest test for order-dependent hangs
pytest-repeat       # ×N runs of the player module in the soak job
hypothesis          # property-based money maths (backlog item 4)
mutmut              # mutation testing on validator / pricing / guard
ruff                # lint + import rules (an agent must not import another's agent.py)
pip-audit           # dependency CVEs, weekly
```

Deliberately **not** added: `pytest-xdist`. Qt offscreen tests in parallel
processes work in principle, but the suite's fixtures share one `DB_PATH`
and one Qt application per process; the 90 s run does not justify the new
failure class. Revisit if the bare run passes 150 s.

`pytest.ini` additions:

```ini
addopts = -m "not live and not build and not soak"
markers =
    live: reaches a real provider; needs .env.test and a cap; opt-in
    build: builds and smoke-tests the frozen .app; macOS only
    soak: repeated / randomised stability runs; nightly
    recovery: subprocess kill-and-relaunch; slower
    flaky_quarantine: known-unstable; still runs; see the TODO card
```

---

## 13. Risks to this plan

- **One machine.** Until CI exists, every criterion in §9 is self-reported.
  Standing up the macOS job is the first infra card.
- **`main.py` coupling.** 24 files build the whole window; a refactor of
  `GodAI` (see `docs/refactor_plan.md`) will churn those tests. Prefer tests
  against the guard's and panels' public methods over tests that reach into
  window internals, so the refactor moves code, not assertions.
- **Live tiers cost money and drift.** T4 is capped and opt-in, and fixtures
  are re-recorded quarterly; the alternative — trusting mocks indefinitely —
  is how the Veo shutdown and the google-genai TTS surface were found late.
- **Darwin-only behaviour.** AppKit guard, app identity and the tray have no
  Linux equivalent; the Linux CI job is a fast signal, not a substitute.
- **Sibling-checkout drift guards skip silently** when `sentinel` or
  `lab_hub` is absent. In CI, check out both read-only so the guards run; a
  skip there is a configuration failure and should be asserted against.
- **Budget for the PAID UAT pass.** It is the only place image, video and TTS
  routes are exercised end to end with real bills. Set the daily cap first,
  every time; a mistake there is the one S0 this plan cannot pin with a mock.

---

## Appendix A — coverage map including the untested modules

Extends the appendix of `manual_test_cases.md`. "Named" means a test file
mentions the module; it is not a coverage number until `pytest-cov` runs.

| Module | Lines | Named by a test? | Plan item |
|---|---|---|---|
| `cloud/reading_compass.py` | 625 | no (contracts yes) | 16 |
| `vidforge/vidforge/trends.py` | 550 | no | 10 |
| `vidforge/vidforge/cli.py` | 440 | no | 10 |
| `ui/tooltips.py` | 255 | no | 9 |
| `vidforge/vidforge/courses.py` | 216 | no | 10 |
| `vidforge/vidforge/ffmpeg_utils.py` | 173 | no | 10, security AST |
| `vidforge/vidforge/llm.py` | 168 | no | 10 |
| `ui/header_fit.py` | 159 | no | 9 |
| `services/runtime_paths.py` | 133 | no | **7** |
| `services/kimi_client.py` | 122 | no | **6** |
| `services/deepseek_client.py` | 121 | no | **6** |
| `vidforge/vidforge/ideation.py` | 107 | no | 10 |
| `services/api_limits.py` | 22 | no | 6 |
| `services/report_exporter.py` | 19 | no | 11 |

Everything else under `services/`, `agents/`, `ui/`, `providers/` is named by
at least one test; see the UAT appendix for the area → file table.

## Appendix B — commands

```bash
# the regression floor (T0–T2), as today
.venv/bin/python -m pytest -q

# if it goes silent for > 3 min it has wedged, not slowed:
.venv/bin/python -m pytest -q --ignore=tests/test_audiobook_player.py
.venv/bin/python -m pytest -q tests/test_audiobook_player.py

# randomised order, three seeds (soak, by hand)
for s in 1 2 3; do .venv/bin/python -m pytest -q --randomly-seed=$s; done

# coverage baseline
.venv/bin/python -m pytest -q --cov=. --cov-report=term-missing --cov-report=html

# recovery tier
.venv/bin/python -m pytest -q -m recovery

# live contract tier — reads .env.test only; set the cap first
# (IMPRINT_ENV_FILE is proposed in item 6/T4, not yet read by main.py)
IMPRINT_ENV_FILE=.env.test .venv/bin/python -m pytest -q -m live

# build smoke
.venv/bin/python -m pytest -q -m build
/Applications/Imprint.app/Contents/MacOS/Imprint --selftest

# mutation run on the money modules
.venv/bin/mutmut run --paths-to-mutate services/validator.py,services/pricing_catalog.py,services/per_unit_pricing.py

# before any UAT session
.venv/bin/python main.py --selftest
.venv/bin/python scripts/check_keys.py
```
