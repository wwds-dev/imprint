# Code review: worker-crash-class (diff `839836c..031e3ca`)

Reviewer: `code-reviewer` agent (read-only, not the author), 2026-11-25. Saved by the author
session, which the reviewer's role does not allow it to do itself. Playbook
`docs/playbooks/code-reviewer.md`: current (last reviewed 2026-10-14).

## P0 / P1
None.

## P2
**P2-1. A Short cancelled at quit is cancelled after the paid narration.** `render_short` checked
`should_stop` after `provider.synthesize`, so ElevenLabs was paid, the `.mp3` deleted and the request
closed at €0 (or not at all). Fix: check before the paid call; after it, let the free ffmpeg step
finish. Pre-existing and related: an ffmpeg failure after a paid narration is also closed at €0.

**P2-2. Delete, Delete campaign and Mark Posted still act on an uploading post.** Same as the
security review's P2-1. `_on_published` then raised `QueueError` in the slot and lost the permalink.

**P2-3. Most start sites had no refuse-before-approval test.** Covered: Herald write and clip,
Label, Sitebuilder, Vector delivery and gig, chat, the three Shorts. Missing: Quill write, publish,
market (publish and market were re-ordered in this commit); Press Ask, Quote Finder, calendar
captions; Vector logos; Nova draft and video; Reel render.

## P3
- **P3-1.** `timeout_seconds` bounds only the wait for the redirect connection; `fetch_token` has
  no timeout; `YouTubeConsentError`'s text names "5 minutes or refused" for every cause.
- **P3-2.** A model download cancelled at quit may show "Download Failed".
- **P3-3.** `test_the_process_leaves_before_qt_can_destroy_a_running_worker` runs the real
  `logging.shutdown()` and its first check depends on test order.
- **P3-4.** CHANGELOG says quit waits at most 3 s; with a release kit, `driver.stop_now` waits up
  to 2 s first.
- **P3-5.** The Post Now test does not assert the result slots run on the GUI thread, nor the
  button afterwards.
- **P3-6.** Quit spends its budget on model-list `DaemonWorker`s that are abandoned anyway.

## Checked and found fine
- Registry: a worker is stored before `QThread.start`; pruning is GUI-thread only, on
  `isFinished`. 2000 chained starts pruning a finished sender in its own slot: no crash.
- All 28 `start_in_slot` sites check before `authorize_request` (AST scan). Chained starts clear or
  pre-check their target slot, so `WorkerSlotBusy` cannot follow an approval.
- Post Now: queue transitions unchanged; button disabled during upload; a quit mid-upload ends as
  `needs_review` at next launch. Slots verified to run on the main thread.
- Release kit calls `render_short` without `should_stop`: unaffected.
- No `terminate()`; every quit path goes through `close()`; the `test_routing_phase3.py` edit does
  not weaken it.

## Commands run
- `pytest tests/test_worker_crash_class.py tests/test_routing_phase3.py`: 54 passed.
- 22 related files: 452 passed in 6 min 43 s. Crash-class file under seeds 1, 7, 4242: passed.

## Not verified
Full suite; ruff; the 25-of-30-fail-on-main claim; delivery of queued signals during shutdown; a
real Google consent flow.

## Author's disposition (2026-11-25)
- P2-1 fixed: the stop check runs before the paid call; once narration is paid, the render
  finishes. P2-2 fixed in 14074a3. P2-3 fixed: the listed sites added to the refusal test.
- P3-2, P3-3, P3-4, P3-5, P3-6 fixed. P3-1: message made neutral; the token-exchange timeout is
  inside google_auth_oauthlib's `run_local_server` and cannot be passed without reimplementing it,
  so it is recorded in `TODO.md` as a follow-up together with the security review's P3-1.
