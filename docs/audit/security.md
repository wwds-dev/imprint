# Security and privacy audit: Imprint (2026-11-23)

Whole-repo audit at `main` ec1cda5, Foundry phase 8 (Secure), read-only. Playbook `docs/playbooks/security-engineer.md` is `status: current`, last reviewed 2026-11-11, so it is not stale. The bar is the playbook plus OWASP Top 10:2025 and the LLM Top 10. The full test suite was not run, no provider or deployed service was called, and no secret file was read.

## Verdict

Imprint is safe for the owner to use on his own Mac today; it is not yet at the level where strangers should clone and run it from the public repo. I found no P0 and could substantiate no P1. Since October the request guard has improved a lot and the Reddit wrong-subreddit bug is fixed. Nine P2 items stand between this and "professional":

- **Secrets hygiene:** the two October P2 findings are both still open after 40 days, and both are one-line fixes.
- **Dependencies:** pypdf has known denial-of-service advisories on the desktop and more in the cloud image; there is no lockfile, and CI does not block on any of it.
- **Cloud companion:** it spends on OpenAI with no ceiling, holds full-Drive access and has no rate limiting on its unauthenticated routes (`CR-3`).
- **Budget caps:** they remain soft in four places.

One claim in the brief did not hold: the four `requests` calls in `cloud/reading_compass.py` all carry `timeout=`.

## Threat model

**Assets**
- About 18 credentials in `.env`, including the Reddit password, the Higgsfield key pair and the Pinterest token.
- The YouTube OAuth token in `vidforge/.secrets/`.
- Money on the provider accounts.
- Manuscripts, voice output and saved chats on disk.
- The public repo's integrity.
- For the cloud companion: the owner's Google refresh token (full Drive scope), `SESSION_SECRET`, `TOKEN_ENCRYPTION_KEY` and the OpenAI key on the job.

**Actors**
- The local user: honest, error-prone.
- Other local processes, via `/tmp` and file modes.
- A provider or CDN that controls response bodies, error text and result URLs.
- Model output, which decides length, quotes and HTML.
- Authors of ebooks the user imports.
- People and agents committing to a public repo.
- Dependency publishers.
- For the cloud companion: anyone on the internet, plus anyone holding a stolen session cookie.

**Entry points**
- Settings → API keys, a hand-edited `.env`, and shell environment (including endpoint overrides).
- Ebook import in Booth (EPUB, PDF, TXT, MOBI/AZW3 through Calibre).
- Provider responses and result URLs.
- Social posting.
- The single-instance local socket, which accepts only a "raise window" poke (`main.py:6537-6704`).
- The narrator worker and the vidforge CLI.
- Cloud routes `/auth/*` and `/api/*`.

**Trust boundaries**
- Settings form → `.env` → `os.environ` → client → provider over HTTPS.
- GUI-thread guard → workers, narrator subprocess, vidforge pipeline.
- Provider URL → download → local file → ffmpeg or Qt.
- Working tree → git → public GitHub; in dev and live-launcher mode `.env` sits in the repo root (`services/runtime_paths.py:110`).
- Browser → Netlify proxy → Cloud Run service → Firestore, Drive and the Cloud Run Job.

## Findings

No P0. No P1.

### P2

**S-1 Secret files beside `.env` are not ignored (October P2-2, still open).**
- **Where:** `.gitignore:12-13` covers `.env` and `*.key` only; `services/api_keys.py:229` creates `.env.XXXXXXXX` holding every key.
- **Evidence:** `git check-ignore` returns not-ignored for `.env.abc123`, `.env.local`, `.env.bak`, `client_secret_123.json` and `token.json`. `git config core.hooksPath` is unset, so `.githooks/pre-commit` never runs.
- **Scenario:** a crash between `mkstemp` and `os.replace`, or a hand-made `.env.bak`, is picked up by a broad `git add` and pushed to a public repo. Every cloner running in dev mode has the same exposure in their fork.
- **Fix:** add `.env*`, `!.env.example`, `client_secret*.json`, `*token*.json` and `.secrets/` to `.gitignore`; use a temp prefix that does not start with `.env`; run `git config core.hooksPath .githooks`.

**S-2 A cleared or replaced Gemini or Higgsfield key comes back at next launch (October P2-1, still open).**
- **Where:** `services/api_keys.py:211-226` rewrites only the names in `updates`; `apply()` at `:247-259` drops aliases only from the running process. `services/gemini_client.py:20` reads `GEMINI_API_KEY` first, while `effective()` at `api_keys.py:262-269` reads `GOOGLE_API_KEY` first.
- **Evidence:** offline run on a temp file with dummy values printed "alias line survives canonical write: True" and "after clearing canonical, alias still in file: True".
- **Scenario:** the user clears the key to stop spending; after a restart every Gemini call bills the old alias key.
- **Fix:** blank alias lines whenever the canonical name is written; one precedence (canonical first) for every reader; a test.

**S-3 pypdf has open advisories on the desktop and more in the cloud image.**
- **Desktop:** `requirements.txt:21` pins 6.21.1, which is what is installed; `pip-audit` lists 10 advisories, fixed by 6.21.4.
- **Cloud:** `cloud/requirements.txt:11` pins 6.19.0, with 18 advisories. That is below the desktop pin, which the playbook forbids.
- **Impact:** the ten I read describe long runtimes, memory exhaustion or infinite loops from a crafted PDF; the eight cloud-only ones were not read. Severity scores were not verified.
- **Reach:** `services/narrator/converter.py:433` on the desktop (a subprocess the user can stop). In the cloud, `cloud/reading_compass.py:374` parses inside the web service, where `cloud/Dockerfile:11` sets `--timeout 0`, and the worker runs until the job timeout.
- **Fix:** pin 6.21.4 or later in both manifests, resync the venv, re-run the audit.

**S-4 Supply chain: nine unpinned lines, no lockfile, and a CI audit that cannot fail.**
- **Unpinned:** `requirements.txt:33-34, 36-39, 42-44`; `vidforge/requirements.txt` and most of `cloud/requirements.txt` are ranges.
- **CI audit:** `.github/workflows/security.yml:22` is `continue-on-error`; `:26` audits the root manifest only, at whatever resolves that day, not the installed set, and not `cloud/` or `vidforge/`.
- **CI tooling:** `:17` pipes an unverified gitleaks 8.18.4 tarball into `tar` (8.30.1 is installed locally). Actions are pinned by tag, not SHA (`:12`, `:24`; `quality.yml:13-14, 27-28`), and neither workflow has a `permissions:` block.
- **Scenario:** a compromised release of an unpinned package runs with every API key in the environment.
- **Fix:** commit a lock (`uv pip compile --generate-hashes`), audit the lock for all three manifests, make the job blocking, verify the gitleaks SHA-256, add `permissions: contents: read`.

**S-5 The cloud worker spends with no ceiling, outside the request guard (October F15, still open).**
- **Where:** `cloud/reading_compass.py:386-428` queues any ebook with no size, length or cost check (the 200 MB check exists only in the estimate route, `:365`). `:594` narrates the whole book.
- **Retries:** a `failed` job can be queued again without limit (`:407`), and each run starts from zero in a fresh temp dir. The one-job-at-a-time check (`:409-415`) is not transactional.
- **Scenario:** a stolen session cookie, or a job that keeps failing late, narrates book after book on the owner's OpenAI key.
- **Fix:** before `:run`, estimate and refuse above a per-job and per-month cap stored in Firestore; count failed attempts per source; check size in `enqueue`.

**S-6 The cloud companion holds full-Drive access behind a 30-day session that cannot be revoked.**
- **Where:** scope is `drive` (`:35`); the refresh token is decryptable by the web service (`:104-118`); the cookie lives 30 days (`:72`, `:296-297`) with no logout route and no server-side revocation short of rotating `SESSION_SECRET`.
- **Scenario:** a cookie theft or a service compromise yields read and write on the owner's whole Drive, not the two folders the routes use.
- **Fix:** add a session version field on the user document, checked in `owner_id()`, plus a logout route; shorten the cookie; narrow the scope, which needs an owner decision (see "Owner decision needed" below).

**S-7 Budget caps are still soft in four places.**
- **Chat reservations (F4, partly open):** `main.py:4253-4266` counts other requests' reservations, but Chat never adds its own (`_pending_requests` is written only at `main.py:4565`, `:4655`, `:5435`).
- **Agent and project caps:** they ignore reservations (`main.py:4536-4537`).
- **vidforge retries (F6, open):** paid calls are retried up to three times (`vidforge/vidforge/llm.py:19`, `visuals.py:25`, `voice.py:18`), and `record_partial` caps the recorded cost at the reserve (`main.py:5581`).
- **Zero quote (F10, open):** a $0 Higgsfield quote is accepted (`services/higgsfield_client.py:388`).
- **Scenario:** two panels and Chat running together pass a per-agent cap twice; a flaky render bills up to three times its reserve.
- **Fix:** route Chat through `authorize_request`; include agent- and project-filtered reservations; treat a 0 quote as unknown; retry only unbilled errors.

**CR-2 PDF conversion runs synchronously on the UI thread — the app freezes on large files.** *(UNVERIFIED by the orchestrator: attributed to a code review that had not been delivered when this report was written; evidence not checked)*
- **Where:** `agents/manuscript/panel.py:1145` opens the file dialog and calls the converter directly on the Qt main thread (`services/narrator/converter.py:433`); `ui/workers.py:142` has a worker class that is not used on this path.
- **Evidence:** not reproduced in this session; the code review reports a 300-page PDF blocked the UI for over 40 seconds.
- **Scenario:** a user imports a long manuscript; the window stops repainting and macOS offers Force Quit; a quit loses unsaved edits in other panels.
- **Fix:** move the conversion onto the existing `QThread` worker in `ui/workers.py` with a cancel flag and a progress signal; name it in `shutdown()` per the lab Qt rule.

**CR-3 No rate limiting on the cloud companion's unauthenticated endpoints.** *(UNVERIFIED by the orchestrator: attributed to a code review that had not been delivered when this report was written; evidence not checked)*
- **Where:** `cloud/reading_compass.py:243` (`/auth/start`), `:261` (`/auth/callback`) and `:318` (`/api/session`) have no per-IP or global throttle; `cloud/Dockerfile:11` runs two gunicorn workers with eight threads and `--timeout 0`.
- **Scenario:** anyone on the internet floods `/auth/callback` with junk `state` values; each request is rejected cheaply, but with 16 threads and no timeout a slow-request flood ties up the service and the owner's Cloud Run bill scales with instance count.
- **Fix:** set a Cloud Run max-instances cap and a request timeout; add a small per-IP limiter (for example `flask-limiter` with in-memory storage) on the three routes.

### P3

**S-8 Provider-supplied download URLs are fetched unchecked (October P3-1, still open).**
- **Where:** `ui/workers.py:502`, `agents/video/workers.py:122`, `services/image_generation.py:169`, `services/qwen_client.py:562`, `vidforge/vidforge/visuals.py:89,127`. `services/openai_client.py:141` uses `urlopen`, which also accepts `file://`.
- **Gaps:** no https or host check, no byte cap, writes straight to the final file. No credentials are sent.
- **Fix:** https only, host allowlist, byte cap, `.part` then `os.replace`.

**S-9 Provider error text can render as a clickable link in message boxes.**
- **Evidence:** offscreen test — a `QMessageBox` label is `AutoText` with `openExternalLinks: True`, and `Pinterest rejected the pin (400): <a href=…>` is detected as rich text.
- **Where:** about 21 call sites pass exception text, for example `agents/social/panel.py:1086` fed by `agents/social/publishing.py:347-349`. `main.py:3558` and `:3578` render HTML in the chat box, but links there are not clickable.
- **Model output itself is safe:** it is inserted as plain text (`main.py:5686`, `:5691`) and the status labels are forced to plain text.
- **Fix:** one helper that sets `Qt.PlainText` on every message box showing dynamic text.

**S-10 Endpoint overrides send keys or manuscripts to any host.**
- **Qwen:** `DASHSCOPE_BASE_URL` is used as typed (`services/qwen_client.py:54-57`); Settings warns but never blocks (`:96-120`).
- **Higgsfield:** `HIGGSFIELD_BASE_URL` gets `Key id:secret` on any https host with no warning anywhere (`services/higgsfield_client.py:177-178`, `:210`); `_api_url` only pins later URLs to that same host (`:225-236`).
- **Local runtimes:** `OLLAMA_HOST` and `LMSTUDIO_URL` can name a remote machine over plain http, and the app still treats it as local and free (`services/providers.py:125-149`).
- **Risk:** an attacker needs write access to `.env` or the shell, so this is a misconfiguration and social-engineering risk ("paste this endpoint").
- **Fix:** refuse non-https, non-loopback hosts for key-bearing endpoints; warn when a "local" host is not loopback.

**S-11 Launch log in `/tmp` (October P3-2, still open).** `scripts/app_launcher.c:49`, `:127` open it 0644 without `O_NOFOLLOW`; `scripts/install_app.sh:68` sets the path. Fix: `~/Library/Logs/Imprint/launch.log`, 0600, `O_NOFOLLOW`, changed in Sentinel's copy in the same session.

**S-12 `.env` modes and parsing (October P3-3, P3-4, P3-5, still open).**
- An existing `.env` is never tightened (`services/runtime_paths.py:139-146`).
- The YouTube token is written, then chmod-ed (`vidforge/vidforge/youtube.py:74-75`).
- A pasted NUL passes the one-line check (reproduced: "is_one_line accepts NUL: True", `services/api_keys.py:175-180`) and stops the next launch.
- `load_dotenv` still interpolates `${…}` (`main.py:43`, `scripts/check_keys.py:29`, `vidforge/vidforge/config.py:87-88`, `services/narrator/converter.py:172-191`).
- Fix: chmod 0600 at every launch; create with `os.open(..., 0o600)`; reject control characters; `interpolate=False`.

**S-13 Credential-bearing requests follow redirects (October P3-6, mostly open).** `providers/voice/elevenlabs.py:49-50, 85-90` (and `voice_id` is unquoted at `:86`); `services/narrator/converter.py:833-838`; the Reddit password POST at `agents/social/publishing.py:154-168`. Fix: `allow_redirects=False` on these calls.

**S-14 External tools inherit every API key.** `services/narrator/converter.py:264-276` copies the whole environment and `:293` hands it to ffmpeg, ffprobe and Calibre's `ebook-convert`. Fix: pass an environment with the names in `api_keys.ALL_NAMES` removed.

**S-15 Packaging is local-only.**
- Ad-hoc `codesign --force --deep --sign -` after `xattr -cr` (`scripts/build_app.sh:70-71`, `scripts/install_app.sh:115-116`); no notarization.
- The live launcher runs whatever `project_root.txt` names (`scripts/install_app.sh:80`, `scripts/app_launcher.c:70-100`).
- Fine for the owner; a bundle shared with anyone else would be blocked by Gatekeeper or run unsigned code.
- Fix: say "ad-hoc, not notarized, build from source" in the README; Developer ID plus notarization before any binary is offered. That step makes this a P2.

**S-16 Cloud hardening.**
- The container runs as root on an unpinned base image (`cloud/Dockerfile:1`).
- No CSP, `nosniff` or frame headers on `/app` (`cloud/reading_compass.py:303-315`).
- Job error text is stored and returned (`:616`, `:438`).
- `cloud/README.md:21,49` publishes the private dashboard's hostname in a public repo.

**S-17 Imported ebooks: denial of service only.**
- No archive is extracted to disk anywhere, so path traversal on extract does not apply.
- XXE is not reachable: EbookLib 0.20 parses with `resolve_entities=False` (`ebooklib/utils.py:34` in the venv) and app code never calls lxml directly.
- EbookLib reads each zip member whole into memory, so a zip bomb can exhaust the narrator subprocess (not exercised).
- MOBI and AZW3 go to Calibre (`services/narrator/converter.py:476`).
- DOCX import does not exist; `python-docx` is export only (`agents/author/book_exporter.py:102`).

**S-18 Drift.**
- The venv holds `pyside6-webengine` and `pyside6-pdf` 6.12.0.140 beside PySide6 6.11.2; neither is in a manifest and no code imports WebEngine.
- `docs/foundry/app-context.md:62` says one gitleaks pin; `.gitleaksignore` has seven.
- `docs/foundry/app-context.md:27,31` call PySide6 unpinned; `requirements.txt:35` pins it.
- `main.py:4441` still names `/tmp/sentinelai_launch.log`.

**Other pip-audit output (installed set, 82 packages, 29 advisories in 4 packages).**
- `soupsieve` 2.9.0 (`requirements.txt:27`): four selector-parsing advisories. Not reachable — no app code calls `.select()`. Bump anyway.
- `pip` 24.0 and `setuptools` 79.0.1: tooling advisories; reported, not blocking under the playbook.

### Checked and sound

- **Timeouts:** all four `requests` calls named in the brief have one (`cloud/reading_compass.py:269-273`, `:276-277`, `:420-422`, `:494-495`), since the file's first commit. An AST scan found no `requests` or `urlopen` call without a timeout in app code.
- **Cloud authentication:** state cookie, verified email against `ALLOWED_EMAIL` (`:280`), signed cookie; every data route calls `require_owner`. Cross-site writes are stopped by `SameSite=Lax` plus JSON-only bodies.
- **Cloud SSRF and traversal:** none found. File ids are pattern- and ancestry-checked (`:191-207`), the upstream host is fixed (`:494`), Drive paths are validated (`cloud/contracts.py:10-17`). The web client writes with `textContent` only.
- **Subprocesses:** no `shell=True` anywhere; argument lists throughout; `say` and `espeak` get `--` before the text (`providers/voice/mock.py:79`, `:92`); concat and ffmetadata values are escaped (`services/narrator/converter.py:931-944`).
- **Posting:** every post needs an explicit "Post now?" (`agents/social/panel.py:1051-1057`); YouTube uploads are private (`:1049`, `vidforge/vidforge/youtube.py:99-104`); the Reddit token is scoped to `submit` and not stored.
- **Key handling:** keys are not printed or logged by the code I read; the YouTube trends client redacts its key from errors (`vidforge/vidforge/trends.py:221-225`). TLS verification is not disabled anywhere.
- **Links and loaders:** doc viewers open only http and https links (`ui/docs_center.py:528`, `ui/learning_center_v2.py:797`); YAML is `safe_load` (`vidforge/vidforge/config.py:112`).
- **Guard coverage:** every GUI paid path goes through `authorize_request`, `authorize_job_item` or Chat's inline validate-and-confirm.

## Status of the October findings

| Finding | Status today | Evidence |
|---|---|---|
| P2-1 alias keys | Open | S-2, reproduced |
| P2-2 `.gitignore` siblings | Open | S-1, reproduced |
| P3-1 download URLs | Open | S-8 |
| P3-2 `/tmp` launch log | Open | S-11 |
| P3-3 file modes | Open | S-12 |
| P3-4 NUL in a key | Open | S-12, reproduced |
| P3-5 `${` interpolation | Open | S-12 |
| P3-6 redirects with key header | Mostly open | S-13; the converter now quotes the voice id (`converter.py:833`) |
| P3-7 scan hygiene | Open, grown | 7 pins; `security.yml:17` unverified download |
| Reddit wrong subreddit | Fixed | `agents/social/publishing.py:78-117`, used at `:186` |
| F1 Gemini thinking tokens | Fixed | `services/gemini_client.py:88-90` |
| F2 no output cap | Fixed | caps in every client, e.g. `openai_client.py:95`; estimate prices full messages (`main.py:4212-4217`) |
| F3 failed renders unrecorded | Fixed | `record_partial` at `main.py:5555`, used at `agents/video/panel.py:894`, `agents/fiverr/panel.py:938`, `agents/social/panel.py:733` |
| F4 reservations | Partly open | S-7 |
| F5 free or negative price | Fixed for the rate | `services/usage_tracker.py:12-17`; unknown price returns None (`:69`); zero default row not re-verified |
| F6 vidforge retries | Open | S-7 |
| F7 stopped streams record EUR 0 | Not re-verified | |
| F8 Creator usage | Fixed | `agents/creator/panel.py:688` |
| F9 OpenAI image retry | Appears open | `services/api_limits.py:22`, `services/openai_client.py:43`; image path not traced |
| F10 $0 Higgsfield quote | Open | `services/higgsfield_client.py:388` |
| F11 audiobook session total | Fixed | no direct `session_cost_total` writes left in `agents/audiobook/panel.py` |
| F12 NaN and inf budgets | Fixed | `services/validator.py:15-24` |
| F13 stale `pricing.json` | Not re-verified | |
| F14 Ollama `:cloud` free pass | Not re-verified | |
| F15 unguarded entry points | Open | `main.py:3753` has no caller; narrator sentinel `main.py:18-22`; vidforge CLI; cloud worker (S-5) |
| F16 ElevenLabs not a cloud backend | Open | `services/usage_tracker.py:8-9` |

## Could not verify

- **Declined command:** the working-tree and history gitleaks scans; the content of three `/Users/<name>/` matches in tracked files (`config/tools.json` has 2, `services/narrator/converter.py` has 1; `config/` is bundled by `Imprint.spec:70`); the key names in tracked `config/settings.json`.
- **Advisory severity:** `pip-audit` gives descriptions, not scores.
- **Cloud and vidforge dependencies:** only the pinned lines of `cloud/requirements.txt` were audited; its ranged lines (Flask, gunicorn, cryptography, google-*) and `vidforge/requirements.txt` have no installed set here. The Calibre and ffmpeg versions in the Docker image and the bundled Qt are also unaudited.
- **Deployed cloud service:** whether it is deployed, whether secrets come from Secret Manager, job retries, ingress, and Google library default timeouts behind `.execute()` and `credentials.refresh` (`cloud/reading_compass.py:117`, `:418`).
- **GitHub side:** whether CI passes, push protection, default token permissions.
- **Live provider behaviour:** real download hosts, redirects, and whether provider 401 messages echo part of a key.
- **Not exercised:** symlink-following at the `/tmp` log path (no log file existed at audit time); EPUB zip-bomb behaviour.
- **Web design export:** file names from `agents/webdesign/export.py` were not read; the exported page runs model-written JavaScript when the user opens it in a browser.
- **Not run:** the full test suite, per the brief.

## Owner decision needed

S-6's scope change is the one item that needs a decision rather than a patch. Keeping full `drive` scope means nothing changes for the user, but a compromise reaches the whole Drive. Narrowing to `drive.readonly` plus `drive.file` limits writes to files the app created, but the existing `audiobooks - gdrive` folder would have to be recreated by the app once. I recommend narrowing before the service is exposed to anyone but the owner.
