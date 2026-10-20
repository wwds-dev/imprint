# App context

The only app-specific file the company agents read. Fill it in once; keep it short and
true. Agents treat the **Invariants** as hard rules.

## Product
Imprint: a macOS desktop app (PySide6) that bundles ten creative/publishing AI agents (chat, author, manuscript/Press, audiobook/Booth, music, video, social/Herald, creator, fiverr, webdesign; roster in `agents/catalog.py`) for one author/creator user. Forked from `sentinel_ai` (see `FORK_PLAN.md`). It calls local (Ollama) and paid cloud models, so it must never spend money outside the request guard, never claim income or results it cannot show, and never post/publish without the user's action. Current goal (CLAUDE.md): agents deliver what they promise, then a QA campaign.

## Stack
- Python 3.11 (`.venv` is 3.11.15); PySide6 (unpinned) GUI; SQLite (WAL) in `services/database.py`.
- Providers: Ollama, Anthropic (unpinned), openai 2.31.0, DeepSeek, Gemini (google-genai), Kimi, Qwen/DashScope, Higgsfield, ElevenLabs; httpx 0.28.1, requests 2.33.1, pydantic 2.13.0, tiktoken 0.12.0.
- Docs/export: python-docx, reportlab, python-pptx, pypdf, EbookLib, lxml. Video: nested `vidforge/` (PyYAML, google-api-python-client).
- Tests: pytest, pytest-timeout, pytest-randomly. Packaging: PyInstaller (`Imprint.spec`) or live launcher (`scripts/install_app.sh`, `scripts/app_launcher.c`).
- Most `requirements.txt` lines are pinned, but PySide6, anthropic, python-pptx, google-genai, psutil, python-docx, reportlab, PyYAML, google-api-python-client are not.

## Commands
- Install deps: `uv pip install -r requirements.txt -r requirements-dev.txt`
- Run app: `.venv/bin/python main.py`
- Run tests: `.venv/bin/python -m pytest -q` (1512 collected via `--collect-only`, 2026-10-14; a full run takes 13 to 17 minutes, README §16.1; `tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen` and a temp DB; 300 s thread timeout in `pytest.ini`). No other test mode is documented.
- Lint / types: `ruff.toml` (E4, E7, E9, F, B) with a CI ratchet against `docs/company/tooling/baseline.json`; no type checker.
- Setup checks: `scripts/check_setup.py`, `scripts/check_keys.py`.
- Build: `./scripts/build_app.sh [--no-install]` (PyInstaller, ad-hoc codesign, installs to /Applications); everyday: `./scripts/install_app.sh` (launcher into this source tree, edits live on relaunch).
- Release smoke checklist: UNVERIFIED as a single list; use `tests/manual_test_cases.md` (UAT) plus launch, one agent action, quit, relaunch with DB/projects intact, header version badge matches `v<VERSION>.<git count>`.
- Ignore `_run_checks.command` (temporary diagnostic).

## Docs and process files
- `README.md` (3,435 lines, numbered sections; section 18.1 Versioning), `TODO.md`, `SUGGESTIONS.md`, `FORK_PLAN.md`, `AGENTS.md` (pipeline), `CLAUDE.md`, `agents/README.md` and per-agent READMEs, `docs/agents/*.md`, `docs/learn/` (Learning Centre, `help_map.json`), `tests/TEST_PLAN.md`, `tests/READINESS_GATE.md`, `tests/manual_test_cases.md`, `CHANGELOG.md` (Keep a Changelog, grouped by date; how versions are numbered is in its header). `docs/specs` and `docs/audit` hold feature specs and review reports; `docs/adr` holds decision records (first: `0001-model-watch-state-additive-v1.md`, 2026-10-14).
- Version is derived, never typed: `VERSION` (major) + `git rev-list --count HEAD`.
- GUI entry: `main.py` (about 4,400 lines per TODO); widgets in `ui/` (`forms.py`, `panels/`, `theme.py`).
- Invariant from CLAUDE.md: `TODO.md` and `SUGGESTIONS.md` feed the Lab Projects Monitor; keep their format exactly. TODO line: `- [ ] \`P1\` \`bug\` \`@me\` Text` (P0-P3; category from the legend at top; owner `@me` or `@ai`; done = `- [x]`; long reasoning under **Detail**). SUGGESTIONS tags: IDEA, CONSIDERING, PLANNED, DONE, REJECTED.
- After code changes, list out-of-date README/TODO/SUGGESTIONS entries; update only if told.

## Architecture hot spots
- `main.py` monolith (`GodAI` window); `ui/panels`, `agents/*` (each with panel), `services/*` (clients, database, usage, pricing).
- Request guard in `main.py`/`services/api_limits.py` gates every paid call, including per-unit billing; `services/per_unit_pricing.py`, `config/pricing.json` (every offline model id needs a row, tested).
- Paths: `services/runtime_paths.py`. Dev = project root; frozen = `~/Library/Application Support/Imprint/` (DB, chats, logs, `.env`, config), seeded on first launch; `adopt_previous_app_dir()` migrates the old "Create & Publish" dir. Changing `APP_NAME` strands state.
- SQLite WAL (`-wal`/`-shm` move with the DB); migrations tested in `tests/test_database_migrations.py`. `data/` and `config/*.json` are state.
- Qt threads: a full run once deadlocked (QComboBox.setStyle vs. FFmpeg audio threads, 2026-10-05). Keep players/workers stopped in tests; `ui/workers.py`, `ui/appkit_guard.py`.
- Narrator conversion runs in a subprocess via the `--narrator-worker` sentinel (`services/narrator/converter.py`).
- Nested: `vidforge/` (own README, requirements, config; imported by `agents/video/studio.py`), `cloud/` (hosted Reading Compass web companion, own Dockerfile and requirements; contract tests). `build/`, `dist/` are generated; `_to_delete/` holds stale git lock files only.
- Concurrency across sessions: stale `.git` lock files have occurred; check `git status` before assuming a clean tree. UNVERIFIED whether a file lock guards the DB beyond SQLite's.

## Security surface
- Secrets: `.env` (gitignored; packaged app uses Application Support copy). Keys: OpenAI, DeepSeek, Kimi, Google, Anthropic, DashScope, ElevenLabs, Higgsfield, PublishDrive, Reddit (includes password), Pinterest. Settings -> API keys writes this file. Never print values. `.env.example` is the template (`tests/test_env_template.py`). `.gitleaksignore` has one documented false positive.
- Network: outbound only to provider APIs, YouTube/Reddit/Pinterest posting, PublishDrive, LMArena ratings fetch; local Ollama. Repo is public (cloud/README says so): no account IDs or tokens in tracked files.
- Untrusted input: user manuscripts/PDF/EPUB/DOCX import, model output rendered in the GUI, web scraping (beautifulsoup/lxml), `vidforge` OAuth `client_secret*.json` in its secrets folder.
- Packaging: ad-hoc signed only (no notarization found); the live launcher executes this source tree. Dependencies: `requirements.txt` has several unpinned packages. `pip-audit` runs in `.github/workflows/security.yml` (non-blocking); it cannot audit the unpinned lines.

## Test bar
- Layout: flat `tests/test_*.py` (1512 collected), shared `tests/conftest.py`; `tests/TEST_PLAN.md` defines tiers T0-T6. Suite runs in an isolated DB; no test may touch `data/imprint.db`.
- Last recorded (2026-10-14, full run with `-p no:randomly`): 1506 passed, 6 skipped.
- Coverage target: none found. Flaky = any order-dependent hang or failure under `pytest-randomly`; a wedge is a bug, not a retry. No xdist (Qt).
- CI: `.github/workflows/quality.yml` (tests with coverage on macOS; ruff lint ratchet on Ubuntu), `.github/workflows/security.yml` (gitleaks secret scan, blocking; pip-audit, not blocking; also weekly), `.github/dependabot.yml` (weekly: pip for root, `vidforge/`, `cloud/`; GitHub Actions). Whether runs pass on GitHub: UNVERIFIED.

## Invariants
- No paid call outside the request guard; new per-unit paid paths must be added to it.
- Never print, copy or commit `.env` values or keys; no secrets in this public repo.
- Do not rename `APP_NAME` or move writable state without a migration.
- Tests must stay offscreen and use the temp DB; do not add real-network or real-key tests to the default suite.
- Version is derived; never hand-type it. Keep TODO.md/SUGGESTIONS.md formats exact.
- Edit narrowly; no whole-file regeneration; state scope before big refactors.
- Do not claim income, sales or publishing results the app cannot verify (PublishDrive endpoint is untested against a live account).

## Optional roles installed
none
