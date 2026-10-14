# Code review: DASHSCOPE_WORKSPACE_ID (2026-10-13)

Role: code-reviewer (read-only). Scope: uncommitted diff in `imprint-harden-ship` against `docs/specs/dashscope-workspace-id.md`.
Playbook `status: baseline`. Ran `tests/test_voice_and_rates.py`, `tests/test_settings_keys.py`, `tests/test_image_routes.py`
with `-p no:randomly`: 54 passed. Full suite and random ordering not run by the reviewer.

## Verdict
No P0 or P1. Matches the spec and owner decisions. Two P2, five P3.

## Verified clean
- Single resolver: only `services/qwen_client.py` reads `DASHSCOPE_BASE_URL`, `DASHSCOPE_VIDEO_BASE_URL`, `DASHSCOPE_WORKSPACE_ID`
  (`_base_url` :46-54, `video_base_url` :93-94). `services/image_generation.py:_qwen_endpoint` calls `video_base_url()`; the second
  copy of the default is gone. `ui/dialogs.py` and `scripts/check_keys.py` only consume results.
- Precedence explicit URL > valid ID > INTL; blank counts as unset (real fix for `.env.example`'s blank lines; CHANGELOG accurate).
- Chat only: `video_base_url()` has no ID branch; test asserts it.
- Host injection: `fullmatch` + `re.ASCII`; URL built from constants plus one validated label.
- 401 hint only when `status_code == 401` and host ends `.maas.aliyuncs.com`; key not echoed.
- `prepare_probe` env swap on main thread, restored in `finally`.
- Docs consistent; "maintenance mode" removed except the CHANGELOG line describing the removal.

## P2
1. `ui/dialogs.py:600-606`: probe host label can be wrong. With `DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
   (mainland host) the row says "via standard host", which is false for any custom URL. Fix: derive the label from the resolver:
   workspace label when hostname ends `.maas.aliyuncs.com`; "standard host" only when base URL equals `INTL_BASE_URL`; otherwise
   show the hostname or no suffix. Add a test for the explicit-URL case (`test_key` has no direct test).
2. `ui/dialogs.py:601`: label uses substring `".maas.aliyuncs.com" in base_url`, while `workspace_auth_hint` uses
   `urlparse().hostname.endswith`. `https://x.maas.aliyuncs.com.evil.com/v1` shows "via workspace host". Fix: export one
   `is_workspace_host(url)` from `services/qwen_client.py` and use it in both places.

## P3
3. `qwen_client.py:41-43`: `"wsK".lower()` (Kelvin sign) becomes `wsk`; not a host escape but conflicts with "strict" and the
   spec's "non-ASCII rejected". Fix: `isascii()` before `.lower()`; add `"wsK"` to `_HOSTILE_IDS`.
4. `qwen_client.py:51-54`: a hand-edited bad ID falls back silently; `endpoint_note()` and `scripts/check_keys.py` say
   "Set DASHSCOPE_WORKSPACE_ID" even though it is set but invalid. Add a "set but invalid" branch + test.
5. `services/api_keys.py:307-321`: `prepare_probe` mutates process env; a background thread building a `QwenClientWrapper` in
   that instant would see typed values. Pre-existing, tiny window; add a comment.
6. `tests/test_voice_and_rates.py:142-153`: `""`/`"   "` hostile cases vacuous; 401 test uses a hand-rolled `Boom`, not a real
   `openai.AuthenticationError` built from a fake `httpx.Response`; no test for a typed blank ID masking an env-set ID.
7. `ui/dialogs.py:577-583`: status label stale up to 400 ms after typing; as designed.

No findings on SQL, state files or paid-call guards. The spec's "no GATE" holds.

---

# Loop 1 re-review (2026-10-14), also the Secure re-check

Full suite `-p no:randomly`: 1491 passed, 6 skipped, 6 subtests (17 min; reviewer's logging plugin made `load_dotenv` a no-op).
Targeted files in random order x3: 128 passed, 2 skipped each.

## Verdict
No P0 or P1. All loop-0 code-review P2/P3, security F-1/F-2/F-3/F-6 and QA gaps 1-4 fixed (file:line verified). Every host
decision goes through `url_host`/`is_workspace_host` except one string compare (P3-4). `url_host` vs `httpx.URL().host` on 17
tricky URLs: no case where `url_host` says Alibaba while httpx would connect elsewhere. Warnings never block a URL and never echo it
or the raw ID.

## P2 (pre-existing, not caused by this diff)
- **P2-1** `tests/test_settings_keys.py:151-169`, `:182-191`, `tests/test_api_keys.py:124-130`: Save/`apply` deletes ~20 conftest ""
  placeholders (incl. `DASHSCOPE_API_KEY`, `OPENAI_API_KEY`) for the rest of the session. `vidforge/vidforge/config.py:80-89`
  calls `load_dotenv(override=False)` during tests, searching upward, so in the main checkout a real `.env` could refill them.
  Fix: `_restore_env_after_save(monkeypatch)` in both tests (or module autouse), restore the Google placeholder, and set
  `vidforge.config._env_loaded = True` in conftest. Test: autouse teardown asserting every `_CREDENTIAL_ENV` name is still present.

## P3
1. `ui/dialogs.py:557-574`: `refresh_workspace_status()` overwrites the "set by the shell" row text; with shell `ws2` + file `ws1`
   the row names ws1 while the process uses ws2.
2. `services/qwen_client.py:134-145`: explicit `DASHSCOPE_BASE_URL` = intl host + an ID still says "Set DASHSCOPE_WORKSPACE_ID to use it".
3. `main.py:3035` then `:333`: `_seed_tooltips` overwrites the Qwen status tooltip at startup, so the new warning shows only on the dot.
4. `ui/dialogs.py:618`: `base == INTL_BASE_URL` string compare; use `url_host(base) in LEGACY_HOSTS`.
5. Security F-5 reachable: `QLineEdit.paste()` keeps `\n`; pasting `ws1\nDASHSCOPE_BASE_URL=https://evil.example/v1` then a second
   Save writes a real `DASHSCOPE_BASE_URL` line (verified). Fix: reject `\r`/`\n` in `write_values`/`save_all`.
6. Security F-4 open (pre-existing): `services/api_keys.py:348-349` passes the provider's first error line; drop it on 401/403.
7. Fixed `qWait(600)` sleeps (`tests/test_settings_keys.py:241,245,248,268`); untested `and not _env("DASHSCOPE_BASE_URL")` guard
   (`qwen_client.py:137`) and `on_probe_result` failure path.

Item (c) `http://localhost` warning: not a defect; keep.
