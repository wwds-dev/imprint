# Secure: one-click-release, slice 1 (free path)

Role: `security-engineer`, read-only on code and tests. Did not write the code. 2026-11-21.
Spec `docs/specs/one-click-release.md`, ADR 0005, review `docs/audit/one-click-release-code-reviewer.md`,
QA `docs/audit/one-click-release-qa-engineer.md`. Branch `claude/one-click-release-slice1-599646`,
scope `git diff 3e0a761..HEAD` at **bf006a7**. No third-party network calls, no paid calls, no `.env` read.
Probe scripts ran from the session scratchpad with the main checkout's `.venv` (Python 3.11, requests 2.33.1).

## Verdict
**Updated after the re-check of 7e6f182 (see "Re-check" at the end): ready for Comply: yes.**
S-1 to S-4 are fixed and each fix is killed by a mutation. No P0 or P1 is open. The P3s stand.

Original verdict at bf006a7: **Ready for Comply: no.** One **P1** (S-1): with a proxy configured, the "on this Mac" model calls go
to the proxy, so the book can leave the Mac while the screen, report and provenance say it did not.
Three P2s, several P3s. The money guard holds for slice 1: no path reaches a paid provider.
Comply can start once S-1 is fixed, or once the owner defers it in writing.

## Findings

### P1

**S-1. Proxy settings route the "local" requests off this Mac.**
`services/ollama_client.py:244` and `services/lmstudio_client.py:294` call `requests.post` with default
`trust_env=True`. Nothing in `services/`, `ui/`, `agents/` or `main.py` sets `trust_env`, `proxies=` or
`NO_PROXY` (grep: no hits). `endpoint_problem` (`services/release_kit/plan.py:72`) checks only the URL's
host. Evidence (scratchpad `proxy_probe.py`):
```
HTTP_PROXY set: http://127.0.0.1:11434/api/chat bypass= False -> {'http': 'http://proxy.example:8080'}
HTTP_PROXY set: http://localhost:1234/v1/chat/completions bypass= False -> {'http': 'http://proxy.example:8080'}
HTTP_PROXY set: http://[::1]:11434/api/chat bypass= False -> {'http': 'http://proxy.example:8080'}
```
A macOS system proxy has the same effect: `getproxies()` reads it, and with this Mac's default exception
list (`scutil --proxy`: `*.local`, `169.254/16`) `_proxy_bypass_macosx_sysconf` returns `False` for
`127.0.0.1`, `localhost` and `::1`. No system proxy is on now, so the live path is **not verified** end to
end. The test was a direct call, not a request.
Impact: the 12 quote passages (about 31,000 characters of the book) and every caption request go to the
proxy host in clear HTTP. Meanwhile D2 (`confirm_dialog.py:250`: "every step runs on this Mac"), the report (`report.py:122`: "Every step ran on this Mac")
and `provenance.json` (`provenance.py:24`: "on this Mac") say they did not. This is realistic on this owner's machines (VPN and proxy
tools, debugging proxies). It is the slice's main privacy promise and goes to Comply as a claim.
Fix: give the local clients a `requests.Session()` with `trust_env = False`, or pass
`proxies={"http": None, "https": None}`, for every local call (or at least the kit's path). Add a test
that sets `HTTP_PROXY` and asserts the request is sent without a proxy.

### P2

**S-2. A URL parser mismatch gets past `endpoint_problem`.** `url_host` uses `urllib.parse.urlparse`
(`services/providers.py:154`), but requests dials what `urllib3.util.parse_url` returns. They disagree on
a backslash before `@` (scratchpad `endpoint_probe.py`):
```
'http://evil.com\\@127.0.0.1:11434'   urlparse='127.0.0.1'   requests_dials='evil.com'   allowed=True
```
`ollama_host()` passes such an `OLLAMA_HOST` through unchanged, and `LMSTUDIO_URL` is passed through
as is. The attacker must control the environment, which limits the risk. The control still fails open.
Fix: parse with `urllib3.util.parse_url` (the same parser requests uses), and refuse any URL with
userinfo, a backslash or a percent-encoded host. A test should cover this input.
Other inputs held: `127.0.0.1@evil.com`, `#@`, `%2f@`, `localhost.`, `*.nip.io`, decimal or hex IPs and
`0.0.0.0` on LM Studio are refused. `[::1]`, `127.x`, `[::ffff:127.0.0.1]` and `OLLAMA_HOST=0.0.0.0` /
`:port` (rewritten to 127.0.0.1) are allowed, and all of them are loopback.

**S-3. `say` reads a quote that starts with `-` as options (argument injection).**
`providers/voice/mock.py:85` runs `["say", "-v", voice, "-r", rate, "-o", aiff_path, text]` with no `--`.
`parse_verified_quotes` accepts any substring of a passage (`quote_finder.py:162`), so a quote may start
with `-`. Checked: `-f ~/notes.txt and the forty`, `-year-old man laughed.` and `- Run, she said.` are all
kept from one sample sentence. Measured on this Mac (scratchpad):
- `say … -o a.aiff "-f<path>"` exits 0 and speaks **the file's contents** into the audio (76 KB AIFF from
  a 20-byte file). The Short would then narrate a local file.
- `say … -o a2.aiff "-o<path>/b.aiff"` writes `b.aiff` **outside the kit folder**, and `a2.aiff` is not
  written. The item then fails, and the stray file stays.
- `say … "- Hello, she said."` gives `say: invalid option`, exit 1. The kit pauses with `item_failed` and
  Resume fails again, because the quote is fixed.

The first two need the manuscript to contain such text verbatim (a technical book, or an imported client
file). The third happens with ordinary dialogue in the hyphen style.
Fix: put `"--"` before `text` (checked: `say -o c.aiff -- "-o…"` and `-- "- Run…"` both exit 0, the
text is spoken and no stray file is written). Do the same for `espeak` (`mock.py:96`). Add a test.

**S-4. In the everyday install, the default kit folder is inside the public repo's working tree.**
`default_output_dir(user_data_base(), …)` (`ui/release_kit/confirm_dialog.py:46`). `user_data_base()` is
the project root when not frozen (`services/runtime_paths.py:97-102`), and the owner's everyday app is the
live launcher running this source tree (app-context, Commands). Measured: the default is
`<repo>/My_Novel_v3_2026-11-21`, and `git check-ignore` reports it **not ignored**. The folder holds the
full EPUB of an unpublished book, its quotes and Shorts. `git_autosync` is `push-only` for imprint
(`autosync_repos.txt:18`), so nothing commits it on its own. One `git add -A` by a person or an agent, or a
switch to `sweep`, would publish it to `wwds-dev/imprint` (public). Existing Press files have the same
issue (`data/shorts/`, `data/projects/` not ignored; the Shorts folder predates this change).
Fix: when not frozen, default to an ignored folder (`output/release_kits/`) or `~/Documents/Imprint/`,
or add the kit folder pattern to `.gitignore`. The kit folder is the new exposure.

### P3
- **S-5. Bare command names on `PATH`.** `say`, `ffmpeg` (`shorts_generator.py:20`, `mock.py:85,104`)
  and `caffeinate` (via `shutil.which`, `power.py:32`) are looked up on `PATH`. A writable directory
  earlier on `PATH` could run a planted binary. Use `/usr/bin/say` and `/usr/bin/caffeinate`, and give
  ffmpeg's path once.
- **S-6. No timeout on `say` or ffmpeg** (`subprocess.run` without `timeout=`). A hung encoder holds the
  single running kit. Stop and Quit cannot interrupt a render. A child process outlives Imprint if it quits
  mid-render. Add a timeout, and treat it as `item_failed`.
- **S-7. Redirects and port squatting.** requests follows 307/308 with the body to any host
  (`allow_redirects` not set). A process that took 11434 or 1234 while Ollama or LM Studio was down could
  receive the book or redirect it. Low risk on a single-user Mac. Pass `allow_redirects=False` on the
  local POSTs.
- **S-8. `localhost` is trusted by name.** `is_loopback_host` accepts `localhost` without resolving it.
  `/etc/hosts` could point it elsewhere, but that needs root. Note only, or resolve it and check every
  address.
- **S-9. Personal data in shareable files.** `provenance.json` and `release-kit report` list absolute
  output paths, which carry the macOS user name (`report.py:158`, `provenance.py:66`). They are meant to
  travel with the kit. Use paths relative to the kit folder. The ledger keeps the frozen project
  instructions, quotes and captions in `imprint.db` (local, ignored), and Discard does not delete them:
  for the privacy note in Comply.
- **S-10. Runtime error text goes into the report.** `pause_detail` includes the local runtime's error
  string (`lmstudio_client.py`, "stopped mid-reply: {error}"), which `report.py:109` writes into Markdown
  unescaped. Low impact: local server, local file. No model output (quotes, captions) goes into the
  report: checked.
- **S-11. Contract test coverage.** `GUARDED_MODULES` (`test_release_kit_contract.py:22`) leaves out
  `subprocess`, `urllib3`, `http.client`. The mint test matches the name `JobGrant(` only, so an alias
  would pass it. In-process Python is not a security boundary, so `_MINT` and the AST walk are hygiene,
  not enforcement. The enforcement is `authorize_job_item` refusing non-local routes, plus `run_backend`
  refusing a capped request on a non-local spec (`main.py:5639-5642`). Both hold.
- **S-12. Long titles.** `safe_name` (`plan.py:278`) keeps Unicode `\w` with no length cap. A title over
  255 bytes makes the folder or EPUB name fail with `OSError`. That is availability only, not traversal.

## Checks requested, result
| Area | Result |
|---|---|
| Loopback-only enforcement | URL check correct for the usual forms, enforced at `estimate()` (plan.py:218) and at grant time against the client's own `base_url` (main.py:4624). LM Studio's `server_up` only re-points to `localhost:<port>`. Gaps: **S-1** proxy, **S-2** parser mismatch, S-7, S-8. DNS rebinding: an inbound-attack class aimed at the runtime, not this client. The installed Ollama 0.40.17 is past the known fixes (radar below) |
| Money guard | Holds. `authorize_job_item` refuses non-local first (main.py:4618), then the endpoint, job running, stage running, route = approved stage row, item exists. Child tokens are €0, never enter `_pending_by_agent` (test), closed by `record_job_item` / `close_job_item` (pop), so a grant cannot be replayed after it closes (`check()` → `GrantClosed`). A grant can be reused while open, but no code path does. Forging: `_MINT` is importable (main.py:4614). See S-11 |
| Untrusted model output | Quotes: verbatim substring, ≤280 characters, ≤20, so no oversize. Captions: total reply capped at 8,192 tokens (`num_predict` / `max_tokens`). Filenames never come from model output (`q01`, `s01`, `safe_name(title)` strips `/` and `.`), so no traversal. CSV: guard covers `= + - @ \t \r` on every cell including the AI column (`calendar_export.py:22-27`, tests pass), matching current OWASP guidance. JSON: `json.dumps`. Report: no model text. ffmpeg: model text never reaches its arguments. **`say`: S-3** |
| File writes | The folder must be new or empty and writable, checked at Start (`output_dir_problem`, confirm_dialog.py:226). EPUB name collision bumps `-n`. Outputs stay inside the folder. Writes follow symlinks inside a folder the owner chose (P3 only: needs a local attacker). **S-4** default location; S-3 `-o` write outside the folder |
| Subprocesses | `caffeinate -i -w <pid>` uses a fixed argv, is released in `_leave`'s `finally`, and `-w` is the crash backstop (QA measured it). P1-1's `_guarded` wrapper now reaches `_leave` on handler errors. S-5, S-6 |
| SQLite | All values are parameterised. `set_stage` / `mark_item` column names pass an allow-list (`ledger.py:213-221`). Migration DDL is static strings. `list_jobs` builds only fixed clauses |
| Secrets and privacy | No `os.environ` or `.env` reads in `services/release_kit` or `ui/release_kit` (grep). Usage rows store token counts, not prompt text. `runs.prompt_summary` = item key. No keys in the report or provenance. S-9 |

## Tests run
`pytest -q -p no:randomly tests/test_release_kit_contract.py tests/test_release_kit_review_fixes.py
tests/test_calendar_export.py tests/test_local_reply_cap.py tests/test_quote_finder.py`: **42 passed** (15 s).
Full suite not rerun (QA ran it on 274092e, and bf006a7 adds only the QA report).

## Radar check (scope `security`; the last security note, 2026-10-14, is over 30 days old)
3 searches. Web content was treated as data. Nothing installed. Not written as a separate note, so that this
phase commits only its report.
| Finding | Source | Impact | Rec. |
|---|---|---|---|
| Pillow 13.0.0 fixes a batch of 2026 CVEs (TIFF/JPEG heap overflows, EPS filename injection CVE-2026-112900, CVE-2026-128066/128067). The repo pins `pillow==13.0.0`. The kit only renders text onto new images | ox.security / corgea write-ups, 2026-10/11 (secondary; GitHub advisories not opened) | none at the pin | keep the pin at ≥13.0.0 |
| Ollama 2026 CVEs: "Bleeding Llama" CVE-2026-7482 (fixed 0.17.1), Pull-API SSRF CVE-2026-108836 (≤0.34.1). DNS rebinding in 2026 was NemoClaw's 0.0.0.0 bind (CVE-2026-65105), not core Ollama. Installed: 0.40.17 server, 0.40.6 client | Red Hat CVE pages, csoonline 2026 | none at the installed version | watch. Never bind Ollama to 0.0.0.0 |
| CSV injection: OWASP list now includes tab and CR, with a `'` prefix | OWASP CSV Injection page; Symfony CVE-2021-41270 note | already done | none |

## Not verified
A real system-proxy run (S-1 live). A real Ollama model run (no model installed, as QA found). Excel and
Numbers behaviour on the guarded CSV. Behaviour with a symlinked kit folder. App Nap. The packaged
(frozen) app's default folder: it is under Application Support per the code, but was not run.

## Re-check of the fix commit 7e6f182 (2026-11-21)
Same role. I did not write 7e6f182 (the build session did). Read-only on code. Probes ran from the
scratchpad. Mutations ran on a `git archive` copy of 7e6f182, never in this worktree.

| Finding | Fix in 7e6f182 | Re-check evidence | Status |
|---|---|---|---|
| S-1 proxy | `services/local_endpoint.py` `NO_PROXIES = {"http","https","all": None}` on every Ollama call (`ollama_client.py`, 7 sites) and on `LocalLMStudioClient.stream_chat`. `main.py` now builds `self.lmstudio = LocalLMStudioClient()`. The shared `lmstudio_client.py` and `providers.py` are back to Sentinel's bytes | With `HTTP_PROXY`/`ALL_PROXY` set to a dead port, a local fake server received both streams ("direct"). Mutations M2 (drop it on the Ollama stream) and M3 (drop it on the LM Studio stream) are killed | **Fixed** |
| S-2 parser mismatch | `url_host` now uses urllib3's `parse_url`. `is_plain_endpoint` refuses userinfo, `\`, `%` and parser disagreement, and runs before the loopback check (`plan.py:81`) | 16 inputs re-run. `evil.com\@127.0.0.1`, `evil.com@127.0.0.1`, tab or newline in the host, `[::1%25en0]`, `0177.0.0.1` are refused. `127.0.0.1`, `localhost`, `LOCALHOST`, `[::1]`, `127.1.2.3`, `HTTP://127.0.0.1` are allowed. `OLLAMA_HOST=http://evil.com\@127.0.0.1:11434` is refused. M4 (skip the check) is killed | **Fixed** |
| S-3 `say` options | `"--"` before the text for `say` and `espeak` (`mock.py:78,92`) | Measured earlier: `say -- "-o…"` and `-- "- Run…"` exit 0 with no stray file. New test `test_say_speaks_a_dash_quote_and_writes_nothing_else`. M1 (drop `--`) is killed | **Fixed** |
| S-4 default folder | `default_kit_base`: from source, `output/release_kits/`; frozen, the app's data folder (`plan.py:289`, `confirm_dialog.py:47`) | The default is now `<repo>/output/release_kits/My_Novel_v3_2026-11-21`. `git check-ignore -v` gives `.gitignore:25:output/`. M5 (repo root again) is killed | **Fixed** |

Tests at 7e6f182: `pytest -q -p no:randomly` on the release-kit suites (`security_fixes`, `contract`,
`review_fixes`, `core`, `e2e`), `calendar_export`, `local_reply_cap`, `quote_finder`, `chat_streaming`,
`providers_registry`, `voice_and_rates` and the three drift tests gave **275 passed, 13 skipped** (105 s).
The 13 skips are the drift tests: "sentinel/lab_hub is not checked out beside this repository" in a
nested worktree. I compared the files by hand instead: `services/providers.py` and
`services/lmstudio_client.py` are byte-equal to `active/sentinel`'s copies (`cmp`).
`services/benchmarks.py` differs from Sentinel's working copy, but this branch does not touch it
(not in `3e0a761..HEAD`): flagged for the drift owner, outside this scope. Full suite not run.

Left (P3, not blocking):
- LM Studio's non-stream calls (`chat`, model listing) still honour proxies. Nothing in the app calls
  `lmstudio.chat(` (grep), and `run_backend` always takes `stream_chat` when it exists, so no book text
  goes that way. Model listing sends no user content.
- S-5 to S-12 as above, unchanged.
