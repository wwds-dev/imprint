# Spec: dependency security upgrade, 2026-10

Status: Define, 2026-10-14. Priority: P1 (blocks PR wwds-dev/imprint#23). Radar: `docs/company/radar-notes/2026-10-14-upgrade.md`.

## Problem
`pip-audit -r requirements.txt` (security.yml, CI run 38592945994) reports 97 advisories in 9 packages. pypdf, lxml, pillow and soupsieve handle untrusted manuscripts and scraped pages.

## Goal and success measure
After the change, `pip-audit -r requirements.txt` reports 0 findings for these 9 packages; the full suite and the lint ratchet pass unchanged; no behaviour change.

## Changes (minimum fixed versions)
pypdf 6.10.0 -> 6.19.0; urllib3 2.6.3 -> 2.8.0; soupsieve 2.8.3 -> 2.9.0; pillow 12.2.0 -> 12.3.0; lxml 6.0.4 -> 6.1.0; anyio 4.13.0 -> 4.14.2; idna 3.11 -> 3.18 (httpx2 2.12.0 requires idna>=3.18); add pins httpx2==2.12.0 and httpcore2==2.12.0 (httpx2 2.12.0 requires exactly that) (transitive via unpinned `anthropic`, currently unpinned and floating).

## Non-goals
Latest versions; pinning other unpinned lines; making the audit job blocking; touching app code.

## Phases
Design skipped (no UI). Architect skipped (no state, concurrency or module change). Define gate not required (not user-visible).
