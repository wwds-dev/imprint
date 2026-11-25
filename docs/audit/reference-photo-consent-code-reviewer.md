# Review: reference-photo-consent (D2, option A′)

Reviewed commit `4296091` on 2026-11-24 by a separate `code-reviewer` agent (read-only; transcribed here by the build
session). No P0/P1. Every photo-sending path (Higgsfield estimate worker, the direct `VideoGenerationWorker`, the
applied-assessment re-entry) is checked before any key, budget, estimate or job-row step; resumes send no photos.

| # | Finding | Disposition |
|---|---|---|
| P2-1 | `test_the_direct_route_checks_the_record_itself` failed in 3 of 5 early runs; no dialog assertion | Cause: the build session's mutation run edited `panel.py` in the same worktree while the reviewer ran tests (mutation M5 removed exactly that check). Not reproduced in 3 seeded runs after (340 passed each). Dialog and status assertions added. |
| P2-2 | A hidden character bible's appearance still goes into every teaser prompt | Fixed differently: the bible is shown for every account (gating the prompt on type would undo `test_character_reaches_any_account_that_has_one`, an earlier decision). |
| P3-1 | Blank `account_type` passes without a record | Fixed: only `own`, `persona` and a missing column pass. |
| P3-2 | Save not all-or-nothing | Partly: validation runs before any write, and a failure in the voice/photo write is reported instead of "Saved". The unsaved-form check then refuses a teaser. Not one transaction (separate helpers own their connections). |
| P3-3 | No warning when saving an incomplete record | Fixed: the status line says the record is incomplete. |
| P3-4 | Future dates accepted | Fixed on save and in the gate. |
| P3-5 | No test that switching to Me clears the record | Added (`test_switching_to_me_clears_the_record`; mutation M7 now caught). |
| P3-6 | Docs not updated | Done: README Nova section, Learning Centre lesson 28, `agents/creator/README.md`. |

Security findings and their fixes: `docs/audit/reference-photo-consent-security-engineer.md` (P2-1 path check, P2-2 unsaved
form, P2-3 docs, P3-4/5/6: all fixed in the same follow-up commit).
