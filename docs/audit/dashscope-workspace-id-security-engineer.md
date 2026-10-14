# Security review: DashScope workspace ID (2026-10-13)

Role: security-engineer. Scope: uncommitted diff implementing `docs/specs/dashscope-workspace-id.md`.
Playbook `status: baseline` (last-reviewed 2026-10-10). No dependency added; `pip-audit` not run (UNVERIFIED).

## Verdict
No P0, P1 or P2. The host that receives the DashScope key cannot be redirected through `DASHSCOPE_WORKSPACE_ID`.
Five P3 items. The pre-existing leak (blank `DASHSCOPE_BASE_URL` made the OpenAI SDK fall back to api.openai.com and
send the DashScope key there) is confirmed fixed.

## Method
STRIDE on the resolver, Settings dialog, `.env` write path and Test-key probe. Hostile inputs run through the resolver
(no network, no key). The URL is built only from `https://` + a `fullmatch` ASCII DNS label + constant suffix/path
(`services/qwen_client.py:49-55`).

Rejected (fall back to intl default): `a.evil.com`, `evil.com/`, `x@evil.com`, `x#.`, `x?`, `ws1:443`, spaces,
underscores, `%2f`, backslash, leading/trailing hyphen, trailing dot, empty, Cyrillic/full-width/zero-width lookalikes,
64-char label. Accepted and normalised to ASCII: case/whitespace variants, 63-char label, `xn--` punycode label,
Kelvin sign (lowercases to `k`). Null byte never reaches the resolver (`os.environ` raises). Blank, whitespace-only and
newline-only `DASHSCOPE_BASE_URL` resolve to the intl default. Video and image paths take no ID branch.

## Findings (all P3)
- **F-1** `qwen_client.py:82-85` `workspace_auth_hint` host check: `https://evil.com\@a.maas.aliyuncs.com/` gets the hint.
  Message accuracy only (constant string). Fix: compare hostname suffix and reject backslash. Optional.
- **F-2** `qwen_client.py:50-52`, `:94`: an explicit `DASHSCOPE_BASE_URL` / `DASHSCOPE_VIDEO_BASE_URL` is unvalidated
  (http, any host). Same trust model as before; not made worse. Optional hardening: https-only (allow localhost) and a
  Settings warning for non-aliyuncs hosts.
- **F-3** `qwen_client.py:68` `on_legacy_endpoint` uses a substring match; use `urlparse(...).hostname`. Cosmetic.
- **F-4** `services/api_keys.py:346-347` probe failure note passes the first 90 chars of the provider error (pre-existing
  generic branch). The new workspace-host 401 branch (`:342-345`) is clean. Option: drop the message on 401/403 everywhere.
- **F-5** `.env` write path (`api_keys.py:211-224`): mkstemp 0600, chmod, atomic replace: fine. No fsync (availability
  only); a raw newline in a value would split the line (unreachable from a `QLineEdit`). Defence in depth: reject `\n`/`\r`
  in `write_values`.
- **F-6** `qwen_client.py:45` `strip().lower()` accepts Kelvin sign / Unicode whitespace; output label is ASCII, no
  security effect. Optional `isascii()` check.

## Informational
No log/print writes the ID, base URL or key (grepped `services`, `scripts`, `ui`, `agents`, `main.py`). The probe swaps
typed values into `os.environ` on the main thread only while the client is built, then restores them. Tests:
`tests/test_voice_and_rates.py:121+`, `tests/test_settings_keys.py:219-235`; `tests/conftest.py:95` scrubs the new var.

## Recommended before merge
Nothing blocking. Optional and cheap: F-2 (https-only + warning, 2 tests) and F-1/F-3 (hostname comparison).

## Correction (2026-10-14, orchestrator)
The verdict line above overstates the pre-existing bug. Verified offline with openai 2.31.0: `OpenAI(base_url="")` keeps `""`
(the SDK only defaults when the value is `None`) and `models.list()` raises `APIConnectionError` before any request; the video
path's `requests` call raised `MissingSchema`. A blank `DASHSCOPE_BASE_URL` made Qwen calls fail; the key was not sent to
api.openai.com. The fix (blank counts as unset) stands; only the severity of the old bug is corrected.
