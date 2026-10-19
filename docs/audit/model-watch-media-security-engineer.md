# Security review: model-watch-media (branch feature/model-watch-media, uncommitted), 2026-10-14

Reviewer: security-engineer (read-only). Playbook status: baseline (2026-10-10). pip-audit not installed; no new dependencies.
Verdict: **no P0/P1**; 1 P2, 4 P3. Key handling, billing gate and state file sound. Radar: docs/company/radar-notes/2026-10-14-security.md.

## Findings
- **P2-1 Probe calls never counted by the guard and not throttled.** `main.py:3970-3990, 4026-4031`; `services/higgsfield_client.py:392-424`. Once enabled, every scan (startup and Check now) sends 4 POSTs to an undocumented endpoint; nothing reaches `usage_tracker`; validator budget checks pass against a zero estimate. If Higgsfield ever bills `/estimate` (or 400/422), spend happens with no record or budget stop — only the off switch protects. Fix: at most one probe per UTC day (last probe day in `probes`); optionally a zero-cost usage row per probe.
- **P3-1 Provider ids reach auto-format QLabels (Qt rich text).** `ui/status_cards.py:554` (`ElidedLabel(row.model_id)`), `:357-358` (`_build_removed`), footer tooltips in `main.py`. Hostile/MITM provider ids like `<span style=...>` spoof tile content (no link opening, no remote images). Pre-existing for chat lane. Fix: `setTextFormat(Qt.TextFormat.PlainText)` in `_label`/`ElidedLabel`; validate ids at client edge (e.g. `^[A-Za-z0-9._:/@-]{1,128}$`).
- **P3-2 State-file growth / GUI stalls from huge lists.** `services/model_watch.py:218` (`observe_media`), `:256` (`seen` only grows), unbounded `pending_media`; `services/qwen_client.py:268,289-305` (20-page cap, no per-page/size/id-length cap; Gemini pager unbounded). `json.dump` of whole state on GUI thread per observe. Fix: cap ids per list (~2,000), drop over-long ids, cap `pending_media`; check cancel between Qwen pages.
- **P3-3 DashScope bearer key sent unprompted to an owner-set base URL without HTTPS check.** `services/qwen_client.py:164-167, 286-292`. An `http://` override leaks the key on every launch. Higgsfield `_api_url` already enforces HTTPS + same host. Fix: refuse non-HTTPS `video_base_url` (except localhost).
- **P3-4 Probe switch enabled by any truthy value.** `main.py:3970` `settings.get(..., False)`; `"false"`/`"0"` strings turn it on. Fix: `is True`.

## Checked, sound
Keys only in headers (Gemini `x-goog-api-key`, Qwen Bearer, Higgsfield `Authorization: Key`); probe returns status strings only; state stores ids/timestamps/paths; requests 2.33.1 strips Authorization on cross-host redirects. Probe: no upload/prepare/submit/retry, paths only from `SEEDANCE_ENDPOINTS` for offered models, HTTPS/same-host enforced. State writes atomic (`mkstemp` + `os.replace`, 0600), single GUI-thread writer. Chat menus filtered (`main.py` ~3880, ~4083; `ui/panels/base.py:155-161`).

## STRIDE
Spoofing P3-1, P3-3 · Tampering: atomic state, local only · Repudiation P2-1 · Info disclosure: clean except P3-3 · DoS P3-2 · EoP: none.
