# Verify: reference-photo-consent (D2, option A′)

2026-11-25, build session (an agent; not the owner's verdict). Tests: `tests/test_reference_photo_consent.py`, 33 tests.

## Success measures
1. **Someone else's photos without a record cannot be sent:** met. Per route (Higgsfield, Gemini, Qwen): dialog,
   status, no authorisation, no worker, no job row (`test_someone_elses_photos_without_a_record_are_not_sent`,
   `test_the_direct_route_checks_the_record_itself`). Also stray files, unsaved edits, invalid and future dates.
2. **Me and made-up character unchanged:** met. `test_a_teaser_with_a_record_or_no_need_for_one_goes_ahead`;
   `tests/test_teaser_routes.py`, `tests/test_creator_v2.py`, `tests/test_creator_resume.py` green.
3. **Docs say what the record is for, claiming no more than the check:** met in README, lesson 28, the creator README.

## Mutation check (each mutation reverted after)
15 of 15 caught: managed exempt, blank exempt, no date check in the gate, future dates, no photo shortcut, gate removed
from `generate_video`, gate removed from the direct route, no date validation on save, stale record kept, consent fields
always shown, symlinks allowed, no image-bytes check, no unsaved-form check, no path check before sending, no path
check on save. A first round found one survivor (stale record kept); the test was added.

## Suite
Focused files green under seeds 11, 22, 33 (340 passed, 17 xfailed). Full suite on `b4f0eef`, seed 424242, `SIBLING_REPO_DIR` set: **3077 passed, 6 skipped, 17 xfailed, 0 failed** (50 min).

## Not verified
On screen in the launched app (layout of the new group, the file picker). Not run against a provider.
