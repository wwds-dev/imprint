# ADR 0001: Model-watch state grows additively under VERSION 1

Status: accepted (2026-10-14, owner, at the Architect gate; proposed by architect the same day). Spec: `docs/specs/model-watch-media.md`.

## Context
`services/model_watch.py` persists `data/model_watch.json` (frozen: Application Support). It holds chat baselines (`providers`), undismissed notices (`pending`) and `last_checked`. `_load` treats any file whose `version != 1` as empty, and `_save` writes the whole loaded dict back.

The media watch needs per-provider media baselines, a miss counter for removals, a removals list, and stored Higgsfield probe results. Losing the file is cheap in data but costly in signal: pending chat notices vanish, and every lane re-baselines.

## Decision
- Keep `VERSION = 1`. Add only new top-level keys (`media`, `pending_media`, `removals`, `probes`, and `probe_day` for the once-a-day probe limit added in review fix round 1) and a `missing` map inside each chat provider record. `_load` fills each one with `setdefault`.
- Never rename or reinterpret an existing key.
- Baselines are **per lane**: a provider with a chat baseline and no `media[p]` gets a silent media baseline at its first media look.
- Removal counters start empty and need two misses on two UTC days from Model updates scans.
- A future incompatible change (renaming a key or changing a value's meaning) is the point to bump to 2. That bump must ship a migration from 1, plus a test that loads a v1 fixture.

## Consequences
- Upgrading keeps chat baselines and pending notices, and nothing is re-announced.
- Rolling back keeps the media keys. Older builds accept version 1 and round-trip unknown keys, so they survive a downgrade-then-upgrade.
- The schema version no longer tells you which keys exist. Readers must use `.get`/`setdefault` for every key added after 1. A unit test pins this by loading a minimal v1 file (`{"version": 1, "providers": {...}, "pending": [...]}`).
- The file grows by about one id list per media provider plus a handful of probe entries, which is negligible.
- Reversing this later (splitting media into its own file) needs a one-time copy-out migration. That is why this is recorded as an ADR.
