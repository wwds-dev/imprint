# Audit tier-1 fixes (2026-10-12)

Source: `software_company/audits/imprint/` (code-review.md P1-1 and P3-8, qa.md P0, security.md P3-1).
Phases skipped: Define/Design/Architect gates (test additions plus two tiny defensive changes, no new
behaviour); Document (no user-visible change).

## Problem
1. `runtime_paths.adopt_previous_app_dir()` has no tests, and its `source.rename(target)` is
   unguarded: an `OSError` there (permissions, cross-volume, locked file) propagates out of
   `user_data_base()` and the frozen app cannot start.
2. `database._adopt_previous_db()` moves the `-wal`/`-shm` sidecars after the main file with no
   test; it is unknown whether an uncheckpointed write survives the rename.
3. The `.env` seeded into Application Support gets the default umask (0644) until the first
   Settings save.
4. `tests/test_retired_names.py` scans `git ls-files` only, so an untracked new file can carry a
   retired name unnoticed until it is added.

## Fixes
1. Tests for the five cases (old dir only, new dir empty, new dir populated, both populated, rename
   raising OSError). Code: catch `OSError` around the rename, print a `[Paths]` line (the module
   has no logger; `services/database.py` uses `print("[DB] ...")`), return `None`.
2. Tests with a real WAL-mode database holding an uncheckpointed write. Production code unchanged;
   a failing assertion is recorded as `xfail(strict=True)` and reported.
3. `chmod 0o600` on the seeded `.env`, tested in a tmp dir.
4. The retired-names scan also covers `git ls-files -o --exclude-standard`.

## Result notes
Fix 2: no data loss. `_has_tables(old)` opens and closes the legacy file before the move, which
checkpoints the -wal into the main file, so the uncheckpointed row survives; no xfail was needed.
The sidecar move itself is therefore a no-op in practice (a hard-killed process's WAL is folded
in by that check); it is kept as is.

## Success measure
The new targeted tests pass; `tests/test_cost_and_limits.py`, `tests/test_retired_names.py`,
`tests/test_database_migrations.py` still pass.

## Non-goals
`services/narrator/converter.py`, billing/cancel/flat-estimate logic, conftest isolation,
dependencies, music token handling, directory chmod 0700 (security P3-1 second half: later round).

## Deferred decision: both directories populated
Current behaviour, now pinned by a test: if the new `Imprint` directory already has any content,
the old `Create & Publish` directory is left untouched and unread. A user who launched the new
build once before adoption (it creates an empty-ish dir and seeds `config/`, `data/`, `.env`)
would see the old state silently ignored. The `target` dir is only "empty" before the first
`ensure_seeded()`. Options for a later, owner-gated round: (a) merge selectively (never overwrite
newer files), (b) show a one-time notice pointing at the old directory. Not decided here; the skip
is left as is so newer state is never overwritten.
