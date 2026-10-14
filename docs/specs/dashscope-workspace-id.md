# Spec: DashScope Workspace ID in Settings

Status: Define, 2026-10-13. Priority: P2 (feature, TODO.md line ~86). Radar: `docs/company/radar-notes/2026-10-13-feature.md`. Product-manager playbook is `status: baseline` (last-reviewed 2026-10-10, within 90 days but not yet verified by a radar run).

## Problem
Who: an Imprint user with a Singapore Model Studio key who wants Qwen chat and Wan video. Today the only way to leave the `dashscope-intl` host is to hand-type two full URLs (`DASHSCOPE_BASE_URL`, `DASHSCOPE_VIDEO_BASE_URL`) with the right paths. Evidence: the Settings hints (`services/api_keys.py:85-91`) and `endpoint_note()` ask for exactly that; Alibaba docs recommend the workspace host. Typo risk is real and the API key is sent to whatever is typed.

Challenge: the "maintenance mode since 2026-09-30" premise is not verified (radar: docs say the old host stays fully functional). The need is still real (recommended host, better limits) but it is a convenience and honesty fix, not an outage. Smaller version below: one field, derived URLs, no auto-migration.

## Target user
The single author/creator owner with one Alibaba workspace in Singapore.

## Goal and success measure
Entering one ID replaces two hand-typed URLs. Testable (offscreen, no network):
1. With `DASHSCOPE_WORKSPACE_ID=ws1` and both URL vars unset, `qwen_client._base_url()` is exactly `https://ws1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`, `endpoint_note()` is `""`.
2. 100% of a table of hostile IDs (see Validation) never appear in any returned URL; the default falls back and Settings shows an error.
3. With no ID, `_base_url()` and `endpoint_note()` output is byte-identical to today (existing test in `tests/test_voice_and_rates.py` passes unchanged except any copy softening agreed in Q2).
4. Explicit non-empty env vars win over the ID in every combination.
5. The Settings Test-key probe uses the typed ID (as it does for the typed base URL, `ui/dialogs.py:549`).

## Non-goals
Auto-discovering the ID; other regions (Beijing, Tokyo, Frankfurt, Virginia, Hong Kong); changing the China default; model-list or pricing changes; touching the converter/benchmarks files shared with Sentinel; moving any other provider.

## Scope
- `services/qwen_client.py`: single resolver functions for chat and video base; `on_legacy_endpoint()` stays on the resolved URL.
- `services/image_generation.py:127`: Qwen Image reads its base through the resolver (it has its own copy of the default today).
- `services/api_keys.py`: new non-secret credential `DASHSCOPE_WORKSPACE_ID` (ENDPOINTS group); update hints.
- `ui/dialogs.py` (:549 probe values, :1031 label text): field, inline validation message.
- `.env.example`, README (section near lines 412 and 2949-2959), `ui/tooltips.py:98`, `tests/conftest.py:95` env scrub list, tests.

## URL derivation (precedence)
Chat base:
1. `DASHSCOPE_BASE_URL` set and non-empty after strip: use as-is (today's behaviour).
2. Else `DASHSCOPE_WORKSPACE_ID` valid: `https://{id}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`.
3. Else `INTL_BASE_URL` (today's default).

Video base (subject to Q1):
1. `DASHSCOPE_VIDEO_BASE_URL` set and non-empty: use as-is, trailing `/` stripped.
2. Else valid ID: `https://{id}.ap-southeast-1.maas.aliyuncs.com/api/v1`.
3. Else `INTL_VIDEO_BASE_URL`.

Note: setting only `DASHSCOPE_BASE_URL` does not alter the video base, and vice versa. Empty string counts as unset (the `.env.example` ships blank values; today `os.getenv(..., default)` returns `""` for a blank var, which is a latent bug the resolver fixes).

## Validation of the ID (the key goes to this host)
Strip surrounding whitespace, lower-case, then require the full match `[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?` (one DNS label, at most 63 chars, ASCII only, no leading/trailing hyphen). Official grammar is not documented (not verified), so this is deliberately strict; if Alibaba IDs contain other characters the field will reject them visibly, not silently.
Rejected: dots, slashes, `@`, `:`, `?`, `#`, `\`, `%`, spaces, underscores, non-ASCII/punycode lookalikes, empty after strip, a pasted full URL or hostname. Cases to test: `a.evil.com`, `evil.com/`, `x@evil.com`, `x#.`, `ws1:443`, `ws 1`, `ws_1`, `ws1%2f`, `ws1\n`, `xn--`-style input is allowed only as plain ASCII label (acceptable, it stays under `.maas.aliyuncs.com`). The resulting URL is assembled from the validated label plus constants only, never by interpolating raw input. Invalid ID: ignored (falls to step 3), Settings shows "Workspace ID not used: letters, digits and hyphens only", never written to `.env` as valid.

## Storage
`.env` key `DASHSCOPE_WORKSPACE_ID` (plain text, non-secret like the URL fields; written by Settings -> API keys). Tracked files carry only the empty key in `.env.example`; no real ID in the public repo or in tests (use `ws1`/`test-ws`). Never logged with the key.

## Open questions for the owner
1. Does Wan video / Qwen Image work on the workspace host's `/api/v1`? Docs do not say (not verified). Options: (a) apply the ID to chat only, video stays on `INTL_VIDEO_BASE_URL` (recommended until you confirm with one real call); (b) apply to both as briefed.
2. Soften the "maintenance mode since 2026-09-30" copy (code, hints, `endpoint_note()`, `database.py` comment) since no primary source was found? Recommended yes; the pinned test only needs "ap-southeast-1" and the phrase changed.
3. Should a valid ID with a key from a different workspace be detected? Alibaba returns 401 on mismatch; recommend only a clearer 401 hint in the key check.
4. Region: Singapore only now, OK?

## Risks
- Wrong ID or cross-workspace key gives 401 on every Qwen call; mitigate with Test-key and the hint.
- Video not served on the workspace host (Q1) would break Wan if applied blindly.
- Host injection via the ID: mitigated by strict label validation and constant assembly.
- Paid-call invariant: no new paid path; the request guard is untouched. Tests stay offscreen, no network, no real key.

## Owner decisions (2026-10-13, "whatever is best": recommendations accepted)
1. Workspace ID applies to **chat only** (DASHSCOPE_BASE_URL). Video (DASHSCOPE_VIDEO_BASE_URL) keeps its current default until one real video call on the workspace host is confirmed.
2. Soften the "maintenance mode since 2026-09-30" copy (qwen_client, Settings hints, endpoint_note, .env.example, README, docs/learn) to what the docs support: migration recommended, old host still works.
3. Add a clearer 401 hint when a workspace-host call fails (key belongs to another workspace/region).
4. Singapore (`ap-southeast-1`) only.

## Design
Playbook `ux-designer.md` is `status: baseline` (last-reviewed 2026-10-10, under 90 days, not yet radar-verified); this section follows AGENTS.md rules. No redesign: the field is one more row in the existing Settings -> API keys grid (`ui/dialogs.py` ~500-535: label, QLineEdit, `SettingsHelp` status label, optional button), in the ENDPOINTS group, placed directly above "Qwen chat endpoint" because the ID is the easier choice and the URL is the override.

**User's question:** "My Alibaba key gives errors or I want the recommended host: what do I type, and did it work?" **Primary figure:** the one-line status next to the field (blank = default host; valid = "Using your workspace host"; invalid = error). Everything else is secondary.

**Row**
- Label: `Qwen workspace ID` (non-secret, plain text, like the URL rows; not a password field).
- Placeholder: `leave blank for the default` (same wording as the other ENDPOINTS rows, line ~514).
- Help text (`cred.help`, also the tooltip on label and field): "Optional. Your Alibaba Model Studio workspace ID, e.g. ws1 (not a web address). With it, Qwen chat uses your workspace host, which Alibaba recommends. Leave blank and the standard international host is used; it still works. Video is not affected."
- Order in the grid: Qwen workspace ID, then Qwen chat endpoint, then Wan video endpoint. Chat endpoint help adds: "If filled, this overrides the workspace ID."

**Status text (right column, `SettingsHelp`; property `status` as `on_probe_result` does)**
- Empty: nothing (no "optional" repetition). Never disabled; no empty-state error.
- Valid, not yet tested: "Chat will use <id>.ap-southeast-1.maas.aliyuncs.com" (neutral). If the chat endpoint field is non-empty: "Not used: the chat endpoint below takes priority" (warning style, so the user is not surprised).
- Invalid: "Workspace ID not used: letters, digits and hyphens only" (warning style, `status=warning`). Shown on text change after a short pause or on focus-out, never while the first character is typed. Pasted full URL or host gets the same message plus "paste just the ID, not the address". Nothing invalid is saved as valid; Save still works (the field is ignored, not blocking), so a typo never traps the dialog.
- Color is never the only signal: the text carries the meaning; warning uses the existing `warning` property, no new colors, so existing contrast is kept.

**Test key (existing "Test" button on the Qwen key row; keep its label and tooltip, add one sentence: "Uses the workspace ID and endpoint shown in the boxes.")**
- Probe uses the typed ID (spec goal 5), same as the typed base URL; a typed endpoint still wins.
- States, written to the key row status: "Checking…" (button disabled, as today); success "reachable — <n> models via workspace host" or "reachable — standard host" so the user sees which host answered; failure "unreachable — " + note.
- No key typed: existing prepare_probe note, unchanged. Invalid ID while testing: test runs on the default host and the line says "reachable — standard host (workspace ID ignored)". Never fail silently.
- Free metadata call only; wording must keep "bills nothing".

**Clearer 401 hint (workspace host only)**
"unreachable — rejected (401). This key may belong to a different workspace or region. Check that the key and the workspace ID come from the same Model Studio workspace (Singapore)." On the standard host 401 keeps today's text. No raw response body, no key echoed.

**Softened endpoint note** (replaces "maintenance mode since 2026-09-30" in hints, `endpoint_note()`, `.env.example`, README; keep the substring `ap-southeast-1` for the pinned test)
"Alibaba recommends a workspace host (https://<WorkspaceId>.ap-southeast-1.maas.aliyuncs.com/...) for better limits. The standard international host still works, so switching is optional." No date, no "maintenance". Guide tab line (~1031): "DASHSCOPE_WORKSPACE_ID or DASHSCOPE_BASE_URL switches to your workspace host; prices differ by region."

**Keyboard and focus**
- Tab order follows the grid: key, its Test button, workspace ID, chat endpoint, video endpoint (rows top to bottom; Test sits in column 3 of its own row, as today). Enter in the field does not submit the dialog if it currently does not for sibling fields; no new shortcut.
- Field has an accessible name equal to its label; status label is `setWordWrap(True)` so long text does not clip at 125-200% scaling.

**Tooltips (`ui/tooltips.py:98`, `qwen_key_label`)**
"Whether an Alibaba Model Studio (Qwen) key is configured. Set DASHSCOPE_API_KEY in .env or ~/.zshrc. Optional: DASHSCOPE_WORKSPACE_ID (or DASHSCOPE_BASE_URL) uses your workspace host." Add a tooltip for the new row via `cred.help` only; no second tooltip system.

**Not designed here (flag):** a post-save toast, region picker, auto-fill from the key (all out of scope per Non-goals).

## Architecture
Playbook `architect.md` is `status: baseline` (last-reviewed 2026-10-10, under 90 days, not radar-verified). Radar note reused (2026-10-13). **Gate: none needed** (see Gate).

**Approach.** All URL logic lives in `services/qwen_client.py` (Qt-free, no I/O). Replace line 25-26 and 54-55 with:
- `valid_workspace_id(raw) -> str | None`: strip, lower, `re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", s)` (ASCII only: use `re.ASCII`, no `$` newline slack, so `ws1\n` is stripped then valid, `ws1%2f` fails). Returns the label or None.
- `_env(name)`: `os.environ.get(name, "").strip()`; blank = unset.
- `_base_url()` (name kept, callers and test unchanged): `_env("DASHSCOPE_BASE_URL")` as-is, else `"https://" + id + ".ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"` from the validated label plus module constants (`WORKSPACE_HOST_SUFFIX`, `WORKSPACE_CHAT_PATH`), else `INTL_BASE_URL`. Never interpolates raw input.
- `video_base_url()` (renamed from `_video_base_url`, `_video_base_url` kept as alias): `_env("DASHSCOPE_VIDEO_BASE_URL").rstrip("/")` else `INTL_VIDEO_BASE_URL`. **No ID branch** (owner decision 1).
- `endpoint_note()` / `on_legacy_endpoint()` unchanged in shape, evaluate the resolved chat URL; copy softened (no date, no "maintenance"); `LEGACY_SINCE` removed (grep first: database.py comment only).
- `workspace_auth_hint(base_url) -> str`: the 401 text from Design, returned only when the base host ends with `.maas.aliyuncs.com`.
`services/image_generation.py:127` deletes its literal and calls `qwen_client.video_base_url()` (lazy import inside `_qwen_endpoint`); one copy of each default remains. Image therefore follows video (unchanged behaviour).

**Alternatives rejected.** (a) Resolver in `api_keys.py`: wrong direction, qwen_client would import the credential/UI-adjacent module. (b) New `services/dashscope_endpoints.py`: extra module for ~25 lines; revisit if a second region lands. (c) Write derived URLs into `DASHSCOPE_BASE_URL` on Save: two sources of truth, stale after ID edit, and defeats "URL overrides ID". (d) Accept full hostnames and parse: widens the host-injection surface for no gain.

**Settings / storage.** Add `Credential("DASHSCOPE_WORKSPACE_ID", "Qwen workspace ID", ENDPOINTS, help, secret=False)` in `services/api_keys.py` immediately before `DASHSCOPE_BASE_URL` (~line 83); no probe key. The existing Save path (`dialogs.py:889-890`: `write_values` then `apply`) iterates `CREDENTIALS`, so the field is saved with the atomic temp-file + `os.replace` + chmod 0600 already there; no new write code. Saved text is the stripped value; the resolver, not the file, is the gate (invalid text is stored but ignored, Save never blocked). `tests/test_env_template.py` forces the name into `.env.example` (add `DASHSCOPE_WORKSPACE_ID=` there). Existing files lacking the key: `write_values` appends it under the "Added from Settings" header; nothing to migrate. Existing users with URL vars set see no change (URL wins).

**Probe with unsaved ID.** `dialogs.py:548-549` `typed_values_for("qwen")` adds `values["DASHSCOPE_WORKSPACE_ID"] = key_fields[...].text().strip()`. `prepare_probe` already swaps these into `os.environ` on the main thread only while `QwenClientWrapper()` is built (`qwen_client.py:108` resolves the base at construction) and restores them; the worker then uses the already-built client. Status label (:~505-520): connect `textChanged` on the ID and chat-endpoint fields to one `refresh_workspace_status()` using `valid_workspace_id` (pause via a 400 ms single-shot QTimer, plus focus-out is optional). `on_probe_result` appends the host label ("via workspace host" / "standard host") from `client.base_url`; `run_probe` (api_keys.py ~327) on `qwen` + status 401 adds `workspace_auth_hint(client.base_url)` instead of the generic note; never the response body.

**Security: key sent to wrong host.** The key goes to whatever `_base_url()` returns, so: (1) the only new input is validated to one DNS label and concatenated between constants, so the host is always `<label>.ap-southeast-1.maas.aliyuncs.com`, scheme https; (2) validation runs in the resolver, not only in the UI, so `.env` hand-edits and shell vars get the same check; (3) explicit URL vars remain the user's own, unchanged trust model; (4) video/image never take the ID, so the key cannot reach the workspace host for those calls; (5) the ID is never logged and no raw input is echoed in errors. Residual: a valid label for someone else's workspace sends the key to Alibaba's own host, which answers 401; accepted.

**Failure modes.** Blank/whitespace vars: treated unset (fixes the latent `""` base URL bug; correction 2026-10-14: verified with openai 2.31.0 that `OpenAI(base_url="")` keeps `""` and fails with a connection error before any request, so the key was never sent to api.openai.com, calls just failed). Invalid ID: default host plus visible warning. ID plus URL: URL wins, status says so. Env var from the shell overrides file (existing `overridden_by_environment` handles the label).

**Tests (offscreen, no network, no key; `ws1`/`test-ws` only).** Add `DASHSCOPE_WORKSPACE_ID` to `tests/conftest.py:95` scrub list. In `tests/test_voice_and_rates.py` (next to the existing endpoint test, ~line 103):
1. `test_workspace_id_derives_chat_url`: ID=`ws1`, URLs unset: `_base_url()` exact string; `endpoint_note() == ""`.
2. `test_hostile_workspace_ids_never_reach_a_url` (parametrized: `a.evil.com`, `evil.com/`, `x@evil.com`, `x#.`, `ws1:443`, `ws 1`, `ws_1`, `ws1%2f`, `-ws`, `ws-`, 64-char, `wsа`, full URL, empty): `_base_url() == INTL_BASE_URL`, `valid_workspace_id` is None, input text absent from result. Also `"ws1\n"` and `" WS1 "` accepted as `ws1`.
3. `test_no_id_is_byte_identical`: env scrubbed: `_base_url()`, `video_base_url()` equal the constants; note contains `ap-southeast-1` and not `maintenance`.
4. `test_explicit_urls_win_and_blank_is_unset`: matrix of {ID valid/none} x {URL set/blank/whitespace}; video base never changes with the ID; blank `DASHSCOPE_VIDEO_BASE_URL` gives the default, trailing `/` stripped.
5. `test_probe_uses_typed_workspace_id`: `api_keys.prepare_probe("qwen", {"DASHSCOPE_API_KEY": "k", "DASHSCOPE_WORKSPACE_ID": "ws1"})` returns a client whose `.base_url` is the ws1 URL, and `os.environ` is restored afterwards.
6. `test_image_endpoint_uses_the_video_resolver`: monkeypatch `DASHSCOPE_VIDEO_BASE_URL`, `_qwen_endpoint()` follows it; with only the ID set it stays `INTL_VIDEO_BASE_URL`-based.
7. `test_workspace_401_hint`: `workspace_auth_hint` returns the text for a `.maas.aliyuncs.com` base, `""` for intl; plus `run_probe` with a fake client raising an exception with `status_code=401` and `base_url` on the workspace host contains "different workspace"; no key in the note.
8. Update the existing test (:103-110): drop `"maintenance mode"`, assert `"maintenance" not in note`. Add a Credential test: `write_values({"DASHSCOPE_WORKSPACE_ID": "ws1"}, tmp)` keeps mode 0600 and other lines (tmp path, not the real `.env`).
Optional offscreen UI check: build the dialog, type a bad ID, assert status text contains "letters, digits and hyphens only" (only if an existing dialog fixture is cheap).

**Files to touch.** `services/qwen_client.py` 20-55, 106-115 (comment block 28-33 rewritten); `services/image_generation.py` 126-129; `services/api_keys.py` ~83 (credential, hints at 83-91 softened), ~327-335 (`run_probe` 401 branch); `ui/dialogs.py` 548-549, 505-535 (placeholder/status), ~1031 (guide text), `on_probe_result` ~552; `ui/tooltips.py:98`; `.env.example` (29, 34 comments, new key); README ~412, 2949-2959; `tests/conftest.py:95`; `services/database.py:~987` comment (copy only); tests above. Not touched: request guard, pricing, converter/benchmarks, vidforge.

**Gate.** No GATE: no schema/state-file change (one new optional `.env` key via the existing atomic writer), no new threads or locks (probe env swap is the existing main-thread pattern), no module boundary moved (qwen_client already owns endpoints; image_generation gains a lazy import of it, no cycle: qwen_client does not import image_generation). No ADR: every choice is cheap to reverse. Only watch item for Review: the sweep for other readers of `DASHSCOPE_BASE_URL` (`grep -rn "DASHSCOPE_" --include='*.py'` excluding `.venv`) before merging, so no third copy of a default survives.
