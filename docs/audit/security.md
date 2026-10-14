# Security audit: Imprint (2026-10-14)

Scope (owner, step 4): request guard and budget logic; key handling (`.env`, `.gitleaksignore`, Settings write path);
Higgsfield, Gemini and ElevenLabs download paths. Out of scope: the DashScope Workspace ID resolver (own review,
`docs/audit/dashscope-workspace-id-security-engineer.md`); converter/benchmarks files (shared with Sentinel).
Worktree `imprint-audit-security` at 9c2051d. Two read-only security-engineer passes. Playbook `status: baseline`
(2026-10-10), so the bar is the role prompt plus OWASP.

---

## Part 1: key handling and download paths

### Threat model
- **Assets:** ~18 credentials in `.env` (incl. Higgsfield key ID + secret, Reddit client secret + password, Pinterest
  token); YouTube OAuth refresh token (`vidforge/.secrets/youtube_token.json`); money; integrity of the public repo.
- **Actors:** the local user; other local accounts/processes (via `/tmp`); a misbehaving provider or CDN (controls
  response bodies and URLs); a network attacker (stopped by TLS except on plain http); people and agents committing to
  the public repo.
- **Trust boundaries:** Settings form → `.env` → `os.environ` → client → provider (HTTPS). Provider-supplied URL →
  `requests.get` → local file → ffmpeg / Qt. Working tree → git → public GitHub; in dev and live-launcher mode (how the
  owner runs it) `.env` sits in the repo root. App stdout/stderr → `/tmp/imprint_launch.log`.
- **Entry points:** Settings → API keys (paste, Test, Save All); hand-edited `.env` and shell env; `scripts/check_keys.py`;
  Higgsfield `video_url`/`status_url`, Gemini SDK file download, ElevenLabs response body; vidforge OAuth flow.

### Findings (no P0/P1 in this part)

**P2-1 Cleared or replaced Gemini/Higgsfield key returns at next launch; Gemini can bill a different key than Settings shows.**
`services/api_keys.py:183-242` `write_values` rewrites only the canonical name, leaving alias lines; `:247-259` `apply`
drops aliases only from the running process. `services/gemini_client.py:15-19`, `services/narrator/converter.py:58`,
`services/recommendations/catalog.py:41` prefer `GEMINI_API_KEY` over `GOOGLE_API_KEY`; `services/api_keys.py:262-281`
(`effective`, `overridden_by_environment`) use the opposite order; `ui/dialogs.py:516-517`, `:951-968` show/write
`GOOGLE_API_KEY`. Scenario: `.env` (or the shell) has `GEMINI_API_KEY=old`; user saves a new key; this run uses it; after a
restart every Gemini call bills the old key while the row says "set". Clearing a Gemini or Higgsfield key to stop spending
is undone at next launch. Evidence: offline script on dummy values ("gemini client picks OLD (alias): True",
"effective picks: NEW", "overridden_by_environment flags it: False"). The owner's `.env` has no alias names (names checked
only): latent. Fix: drop/blank alias lines when writing a canonical name; one shared precedence (canonical first) for all
readers; `overridden_by_environment` compares what the client reads; test.

**P2-2 `.gitignore` covers `.env` exactly, not its siblings, root-level OAuth files or tokens (public repo, live `.env` in root).**
`.gitignore:12`; `services/api_keys.py:229` `mkstemp(prefix=".env.")` creates `.env.XXXXXXXX` holding every key.
Scenario: crash/power loss between `mkstemp` and `os.replace`, a hand-made `.env.bak`/`.env.local`, Google's default
`client_secret_<id>.apps.googleusercontent.com.json` or a `token.json` at the root → committed by a broad `git add` and
pushed. The pre-commit gitleaks hook is not active (`core.hooksPath` unset in the main checkout); CI gitleaks runs after
the push; autosync is push-only. Evidence: `git check-ignore` NOT-IGNORED for `.env.abc123`, `.env.local`, `.env.bak`,
`client_secret_123.json`, `token.json`, `data/logs/*`. Fix: add `.env*`, `!.env.example`, `client_secret*.json`,
`*token*.json`, `.secrets/` to root `.gitignore`; temp prefix not starting with `.env`; `git config core.hooksPath .githooks`.

**P3-1 Higgsfield download accepts any URL, no limits, non-video saved as success.** `ui/workers.py:481-490`,
`agents/video/workers.py:113-127`. No scheme/host check (http, loopback, link-local, any redirect); no byte cap
(`timeout=120` is per read); loop never checks `_cancel_requested` (quit waits 2 s, `main.py:~5300`; inferred); writes
straight to the final `.mp4` (truncated file on failure); any content reported done and later opened by Qt/FFmpeg. No
credentials are sent to the download host. Evidence: offline harness with `requests.get` stubbed fetched
`http://169.254.169.254/latest/meta-data` and `http://127.0.0.1:11434/api/tags`; `<html>not a video</html>` saved as
`hf_out.mp4`, `done: True`. Fix: https + host allowlist (hosts from a live run), validate redirects, byte cap, total
deadline, cancel check, `.part` + `ftyp` check + `os.replace`. Same class elsewhere: `services/qwen_client.py:463-470`,
`services/image_generation.py:169` (no URL check, body in memory); `services/openai_client.py:133`
`urllib.request.urlopen(url)` also accepts `file://`; `vidforge/vidforge/visuals.py:89,127`.
Gemini (`files.download` reduces the URI to `[a-z0-9]+`, inline base64 for images) and ElevenLabs (audio in the POST body,
partial file + `os.replace`) are sound. No TLS verification disabled anywhere.

**P3-2 `/tmp/imprint_launch.log` is world-readable and symlink-hijackable.** `scripts/app_launcher.c:49`, `:127`
(`O_WRONLY|O_CREAT|O_TRUNC, 0644`, no `O_NOFOLLOW`); `scripts/install_app.sh:68`. Holds all stdout/stderr incl. full
exception text (`main.py:3711-3726`, whose docstring still names `/tmp/sentinelai_launch.log`). File is `-rw-r--r--`;
count-only key-pattern scan: 0. Symlink-follow on macOS not tested. Fix: `~/Library/Logs/Imprint/launch.log`, 0600,
`O_NOFOLLOW`. The launcher is shared with Sentinel: change both together.

**P3-3 Existing secret files not tightened to 0600.** `services/runtime_paths.py:137-146` chmods only a new `.env`;
`~/Library/Application Support/Imprint/.env` is `-rw-r--r--` (all values empty; `~/Library` is 0700).
`vidforge/vidforge/youtube.py:74-75` writes the OAuth token then chmods; `.secrets` is 0755. Fix: chmod 0600 every launch
and after adoption; `os.open(..., 0o600)` and `mkdir(mode=0o700)`.

**P3-4 A pasted NUL passes the one-line rule and stops the app starting.** `services/api_keys.py:175-180`. `QLineEdit`
keeps a NUL; `write_values` writes it; `apply()` raises (embedded null byte) and Settings says "could not write" though the
file was written; next launch `load_dotenv` (`main.py:35`) raises at import. Evidence: "NUL written: True / load_dotenv
raised ValueError / apply raised ValueError". Fix: reject all C0/C1 controls; tolerate a bad line at startup.

**P3-5 Settings and runtime disagree when a value contains `${`.** Quoted values are expanded by `load_dotenv`
(`main.py:35`, `scripts/check_keys.py:29`, converter, vidforge) but not by `read_values`; e.g. a Reddit password with
`${...}` changes at next launch. Fix: `load_dotenv(..., interpolate=False)` everywhere.

**P3-6 ElevenLabs key header forwarded on cross-host redirects.** `providers/voice/elevenlabs.py:47-52, 85-90` (requests
strips only `Authorization`, not `xi-api-key`); `services/narrator/converter.py:812-819` (urllib copies headers). Needs
`api.elevenlabs.io` itself to redirect cross-host. `voice_id` unquoted in the URL path (`elevenlabs.py:86`). Fix:
`allow_redirects=False` / no-redirect opener; `quote(voice_id, safe="")`.

**P3-7 Secret-scan hygiene.** The 4 pins are genuine false positives, but the same SQL literals still trip `--no-git` scans
and will on any commit touching them. Fix: bind the settings key as an SQL parameter (or one narrow allowlist regex), then
drop the pins. `.github/workflows/security.yml:17` downloads gitleaks with no checksum: pin a SHA-256.

### Gitleaks (8.30.1, `--redact -c .gitleaks.toml`)
- History: 257 commits, **0 findings** (same with `--all --full-history`).
- History with pins disabled (`--no-checkout` clone): 240 commits, **4 findings** = exactly the 4 pinned fingerprints.
- Working tree `--no-git`: **3 findings**, all `generic-api-key`, all SQL settings-key literals: `services/database.py:894`,
  `:1030`, `tests/test_settings_pricing.py:178`.
- No `.env`, `client_secret*`, token or `.secrets` file has ever been tracked; only the two `.env.example` files.

| Pin | Line | Verdict |
|---|---|---|
| `83343104…:tests/test_settings_pricing.py:178` | `DELETE FROM settings WHERE key='pricing_correction_2026_10'` | Not a secret; undocumented in the file |
| `83343104…:services/database.py:1022` | `SELECT value FROM settings WHERE key = 'pricing_correction_2026_10'` | Not a secret; undocumented |
| `315882ef…:services/database.py:198` | `SELECT value FROM settings WHERE key = 'pricing_correction_2026_08'` | Not a secret |
| `5f0664cb…:.gitleaksignore:2` | comment quoting the same SQL line | Not a secret |

### Checked and sound
Key writes: temp 0600 in the same dir, `os.replace`, chmod 0600; a symlinked `.env` is replaced, not followed; the
one-line error names the variable only. Keys never reach the DB, `runs` table or exports; Settings uses password echo;
`check_keys.py` prints presence only. `Imprint.spec` bundles only `.env.example`; no secret files in `dist/` or
`/Applications/Imprint.app`. Reddit password goes only to `https://www.reddit.com/api/v1/access_token`, token not stored.
Higgsfield presigned upload strips `Authorization`; `status_url` held to the API host. vidforge trends redacts the key.
The owner's repo-root `.env`, `vidforge/.env` and App Support `vidforge/.env` are 0600.

### Outside this scope, needs the owner
**Reddit posts land in the wrong subreddit (proposed P1).** `agents/social/publishing.py:151`
`subreddit.lstrip("r/")` strips every leading `r` and `/` character. Verified by the orchestrator:
`["rust","r/rpg","books","r/books"]` → `['ust', 'pg', 'books', 'books']`. A public post goes to a subreddit the user did
not choose. `tests/test_social.py:378` only uses "books". Fix: `removeprefix("r/")` plus a test with "rust".

### Could not verify (part 1)
Real Higgsfield/Qwen download hosts and redirects (needed for the allowlist); whether provider 401 messages carry partial
keys; symlink-follow at the `/tmp` log path; dependency CVEs (`pip-audit` not in venv, no network); CI on GitHub and GitHub
push protection; the quit-during-download behaviour (inferred).

Doc drift: `docs/company/app-context.md` says `.gitleaksignore` has "one documented false positive"; it has 4 pins, 2 undocumented.

---

## Part 2: request guard and budget logic

### Bottom line
No paid call reachable from the GUI skips authorization: each goes through `authorize_request()` (`main.py:3751`) or the
main Chat's inline validate-and-confirm. But the caps are soft: the checked and the recorded cost both run low, and several
failure/cancel paths record EUR 0 for money already billed. There is no monthly cap anywhere (caps: per-call estimate,
session in memory, daily from DB, per-agent daily, per-project daily). All authorization runs on the GUI thread, so no
true thread race; the concurrency gaps are about which caps reservations cover (F4).

### Threat model (budget)
- **Assets:** paid provider accounts and keys; the `usage` table (sole source for daily/agent/project caps);
  `session_cost_total` (memory); `settings` (budgets, `eur_per_usd`); `pricing` table, per-unit overrides and both
  `config/pricing.json` copies; vidforge `config.yaml`; durable job rows carrying reservations across restarts.
- **Actors:** the local user (honest, error-prone: typos, Stop and retry, several panels at once); provider APIs (return
  usage, zero, or time out after accepting a job); model output (decides length and scene count, so cost is untrusted).
  No remote actor reaches the guard (only listener: single-instance `QLocalServer`).
- **Trust boundaries:** GUI-thread guard → QThread workers, narrator subprocess, vidforge pipeline (many paid calls after
  one authorization); workers → provider HTTPS; user-editable config/DB → guard (unvalidated); outside the guard: `cloud/`
  companion and the vidforge/narrator CLIs.
- **Mechanics:** estimate = chars/4 input, `max(250, 1.2×input)` output, or a flat per-unit cost; `services/validator.py:96-143`
  checks agent/project/session/daily caps; in-flight reservations count toward session and daily only (`main.py:3782-3794`);
  `record_request()` (`main.py:4372`) bills real token usage or the flat estimate; `abandon_request()` (`main.py:4420`) bills nothing.

### P1
**F1 Gemini thinking tokens are never billed.** `services/gemini_client.py:185`, `:396` set `output_tokens` from
`candidates_token_count` only; `thoughts_token_count` (billed at the output rate) is dropped (orchestrator confirmed both
lines). Scenario: `gemini-3.1-pro-preview` answers 800 visible + 6,000 thinking tokens → recorded EUR 0.0206, billed
EUR 0.1200 (x5.8). Every Gemini text request is under-recorded, so daily/agent/project caps trip late. Evidence:
`verify_a.py` [1] with a mock client; field exists in google-genai 2.21.0; real ratio not measured. Fix: add
`thoughts_token_count`, map `cached_content_token_count` to cached input, unit test with fake `usage_metadata`.

**F2 Estimate assumes ≤ `max(250, 1.2×input)` output while 5 of 6 text clients send no output limit.** `main.py:503-504`
(orchestrator confirmed; also `:1508`); no limit in `services/openai_client.py:87,145`, `deepseek_client.py:67,92`,
`kimi_client.py:63,89`, `qwen_client.py:269,294`, `gemini_client.py:174,383`; Anthropic sends 8096. Panels estimate from the
user prompt only, not system prompt or injected context (e.g. `agents/author/panel.py:1017-1035`,
`agents/manuscript/panel.py:815-821`). Scenario: session cap EUR 1.00, EUR 0.99 spent, "write chapter 3, ~5,000 words" on
gpt-6-astra: estimate EUR 0.0116 passes, ~EUR 0.31 billed (31× remaining). Evidence: `verify_a.py` [4] (Opus est
EUR 0.0046 vs EUR 0.1490 at max_tokens, x32; gpt-6-astra 32k answer x127). Fix: explicit output cap on every client, reserve
at that cap, estimate from the full `messages` sent; optionally stop a stream past the remaining budget.

**F3 Paid stages of a failed/cancelled render or a partial image batch are never recorded.** `agents/video/panel.py:867-869`
(error or user Stop → `abandon_request`), `agents/social/panel.py:682-690`, `agents/fiverr/panel.py:540-546` (comment admits
it). Scenario: default 8-min render reserves $2.30; script → TTS → Whisper → 35 images ($2.10) → local ffmpeg; assemble fails
or user stops during motion → ~EUR 2.1 paid, EUR 0 recorded. GUI never passes `resume_slug`, so each retry is a full re-spend
with the caps unmoved. Fiverr 4 logos, #4 fails → 3 paid, EUR 0 recorded. Evidence: code paths; `verify_c.py` pre-estimate
breakdown; not run end-to-end. Fix: `record_request` accepts an actual/partial cost; bill completed stages from
`build.manifest["stages"]`; Fiverr bills `len(paths) × reserve`.

### P2
- **F4 In-flight reservations miss main Chat, per-agent and per-project caps.** `main.py:3536-3637` (`send_prompt` never adds to
  `_pending_requests`), `:3561`, `:3793`, `:3741-3749`. Evidence `verify_b.py` (real window, offscreen, temp DB): two EUR 0.80
  requests both pass a EUR 1.00 agent cap and a EUR 1.00 project cap; Chat's EUR 0.60 in flight not counted. Fix: route
  `send_prompt` through `authorize_request`; include agent/project-filtered reservations.
- **F5 Unknown token price or `eur_per_usd` ≤ 0 makes requests free or negative.** `services/usage_tracker.py:66`, `:73-74`;
  Settings accepts any float (`ui/dialogs.py:976-981`), blank price → 0.0 (`:1025`); contradicts "'Unknown' never means free"
  (`ui/dialogs.py:738`). Evidence `verify_a.py` [2][3]: unknown backend 0.0; blanked default row 0.0; `eur_per_usd=-0.92`
  → -22.08. Fix: unknown price → None and refuse; `eur_per_usd` finite > 0 via one reader; refuse a zero default row.
- **F6 vidforge reservation ≠ spend, never reconciled.** App-level `RETRIES=3` on any exception incl. billed failures
  (`vidforge/vidforge/llm.py:19,129-159`), images and TTS 3× (`visuals.py:72-99`, `voice.py:41-64`), SDK default
  `max_retries=2`; estimate ignores `image_quality`, models (`agents/video/studio.py:265-324`); scene count not enforced
  (`script.py:113`); post-run estimate (`pipeline.py:285`) unused; guard authorizes provider "openai"
  (`agents/video/panel.py:503`) even when config uses Anthropic. Evidence `verify_c.py`: 50-scene plan $3.28 vs $2.30 reserved.
  Fix: `max_retries=0`, retry only unbilled errors, truncate scenes or re-authorize, include quality/models, record
  `max(reserve, manifest estimate)`, validate the provider used.
- **F7 Stopped/errored streams and ambiguous media submissions record EUR 0.** `main.py:4590-4618`, panels' `_on_error`/`stop()`
  (e.g. `agents/author/panel.py:1139-1155`), Wan/Veo/Omni create timeouts (`ui/workers.py:407-412`,
  `agents/video/panel.py:851-869`, `agents/creator/panel.py:1471-1492`), ElevenLabs Short when ffmpeg fails after TTS
  (`agents/manuscript/panel.py:1108-1109`). Code only; provider billing of cancelled work not verified live. Fix: partial
  cost when `response_parts` non-empty; keep ambiguous creates reserved; record a Short once `synthesize()` returns.
- **F8 Creator drafts never receive provider usage.** `agents/creator/panel.py:675-679` doesn't connect `usage_signal` (grep:
  only panel without it); billed on chars/4 of the last message, system prompt and reasoning uncounted. Fix: connect it; static
  test that every `_new_chat_worker` site wires usage.

### P3
- **F9** OpenAI images can be sent twice: `services/openai_client.py:39-43,123` `MAX_RETRIES=1`, contradicting
  `services/image_generation.py:10-13`. Fix: images/TTS client with `max_retries=0`.
- **F10** Higgsfield $0 quote accepted (`services/higgsfield_client.py:386` rejects only < 0). Treat 0 as unknown.
- **F11** Audiobook partial spend bypasses `session_cost_total` (`agents/audiobook/panel.py:1019`, `:1059`).
- **F12** Budgets accept NaN (every authorize raises `InvalidOperation`; panels can stick) and inf (cap removed)
  (`main.py:711-712`, `ui/dialogs.py:977-978`). Require finite ≥ 0.
- **F13** Stale Application Support `pricing.json` shadows corrected bundled rates in frozen builds
  (`services/per_unit_pricing.py:35-55,100-114`); token rows `INSERT OR IGNORE` (`services/database.py:746-799`).
- **F14** Every Ollama model is a free pass incl. `:cloud` models proxied to ollama.com (`services/validator.py:84-143`,
  `main.py:507-508`, `usage_tracker.py:61-62`); metering not verified.
- **F15** Latent unguarded entry points: dead `main.py:3366` `run_audiobook_live`, `services/tool_runner.py:14`; the
  `--narrator-worker` sentinel, vidforge CLI (incl. `trends.py:428`) and cloud worker (`cloud/reading_compass.py:387-430,594`,
  no cap) spend outside the guard; HeyGen/Synthesia unwired. Delete or authorize.
- **F16** `elevenlabs` missing from `CLOUD_BACKENDS` (`services/usage_tracker.py:7-8`); Social clips booked to agent "video"
  (`agents/social/panel.py:593-596`); `pre_estimate` substitutes default rates for unknown ones (`agents/video/studio.py:298,303-307`).

Checked, no defect: local-day boundaries consistent; session cap resets as documented (README:2255); single-instance lock
(`main.py:5474`); narrator checks ffmpeg before spending and disables Gemini TTS retry; Higgsfield sends an Idempotency-Key;
resume workers only poll and download. Existing tests: `tests/test_request_guard.py tests/test_cost_and_limits.py
tests/test_settings_pricing.py` → 127 passed; none cover F1-F8.

### Paid call sites
| # | Call | Reached from | Guarded |
|---|---|---|---|
| 1-5 | OpenAI, Anthropic, DeepSeek, Kimi, Qwen chat (`services/*_client.py`) | `main.py:4447` ← Chat `send_prompt` / panel ChatWorkers | Yes (Chat inline, no reservation: F4) |
| 6 | Gemini chat `services/gemini_client.py:174,383` | same | Yes, under-recorded (F1) |
| 7 | Ollama `services/ollama_client.py:151-235` | same | Free by design (F14) |
| 8 | OpenAI images `services/openai_client.py:123` | Fiverr worker | Yes, flat (F3, F9) |
| 9-10 | Gemini / Qwen images `services/image_generation.py:103,142` | Fiverr; vidforge | Yes |
| 11 | Gemini Omni/Veo `services/gemini_client.py:275,294` | video, creator panels | Yes, flat (F7) |
| 12 | Wan `services/qwen_client.py:388` | same | Yes, flat (F7) |
| 13 | Higgsfield `services/higgsfield_client.py:411` | video, creator panels | Yes, provider quote (F10) |
| 14 | ElevenLabs `providers/voice/elevenlabs.py:85` | manuscript Shorts | Yes, flat |
| 15 | Narrator TTS `services/narrator/converter.py:729,818,876` | audiobook panel subprocess | Yes, flat; CLI/dead paths unguarded (F15) |
| 16 | vidforge LLM/images/TTS/captions | video, social panels | Once per render (F3, F6); CLI unguarded |
| 17 | HeyGen/Synthesia `providers/avatar/*` | none | Unwired |
| 18 | Cloud Run narrator `cloud/reading_compass.py:420,594` | hosted web app | Outside guard, no cap |

Free: `models.list`, key probe, Higgsfield estimate/upload, ElevenLabs voice list, resume polls, LMArena ratings.

### Could not verify (part 2)
Live provider billing of cancelled/timed-out work; real Gemini thinking ratio; whether Higgsfield quotes $0; Ollama `:cloud`
metering; OpenAI image double-billing; google-genai text client retry default; dependency CVEs. Reproduction scripts (read-only,
temp DB, sockets blocked): session scratchpad `budget_audit/verify_{a,b,c}.py`.
