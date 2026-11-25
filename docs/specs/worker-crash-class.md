# Spec: Worker crash class (audit fix-order step 4)

Needs: architect (GATE: concurrency and shutdown state), build, review, verify, secure, docs

Status: **Owner approved the architecture 2026-11-25 ("Approve as written (Recommended)"); Build in progress.** Priority: P1. Type: bug
fix, no new capability, no change to what is stored. Source: audit 2026-11-23
(`docs/audit/SUMMARY.md`, step 4), `docs/audit/code-review.md` P1-1 and P1-2,
`docs/audit/architecture.md` A-1 (code-review P2-1 is the same finding). `TODO.md` rows "Replacing a
running `QThread` aborts the app", "Herald's Post Now runs the upload…", "`closeEvent` does not name
`music_worker`…".

## Problem
Three ways an ordinary action ends in a macOS abort or a frozen window:

1. **A running worker is replaced.** Many start sites do `host.<slot> = worker` with no check. If
   the previous worker in that slot is still running, the only Python reference to it drops, the
   `QThread` is destroyed while running and Qt aborts the process (`QThread: Destroyed while thread
   is still running`, exit 134). Herald needs no Stop for it: Write Posts, then Make a Clip while it
   writes (both use `host.social_worker`). Seven more sites are reachable after Stop, because Stop
   only asks the worker to cancel and a non-streaming call cannot see the request for up to 120 s
   (cloud) or 300 s (cold Ollama). Press's three Shorts entry points share `host.shorts_worker`
   but only two check a busy flag, and the first one never sets it. Quill, Reel and the Suno panel
   already refuse (`[Busy] The previous request is still finishing`).
2. **Herald's Post Now blocks the UI thread.** `publisher.publish()` runs in the click handler. For
   YouTube that includes the Google consent wait (`flow.run_local_server(port=0)`, no timeout):
   closing the consent tab freezes the window until force-quit. Even on the happy path the window is
   frozen for the whole upload. Lab rule: nothing on the UI thread may fetch.
3. **Quit does not stop every worker.** `closeEvent` sweeps a hand-written list that misses
   `music_worker` and `webdesign_worker` (and `KeyProbeWorker`, held in a dialog's local list), waits
   2 s per worker, then accepts regardless. `ShortsWorker` and `ModelPullWorker` have no `cancel`, so
   quitting during a Short or a model download always outlives the wait and aborts.

## Success measure
- Each defect has a test that fails on `main` and passes on the branch:
  1. starting a second job into a busy slot is refused (no replacement, the old worker object stays
     referenced), at every site in the table below; Press's three Shorts entry points refuse each
     other;
  2. Post Now returns to the event loop before `publish()` runs, and the consent wait passes a
     timeout to `run_local_server`; a consent timeout is reported as "safe to retry";
  3. `closeEvent` cancels and waits for a worker it was never told about by name (any running
     `TrackedThread`), and a worker still alive after the budget does not reach Qt's destructor.
- A source test fails if any class in the app subclasses `QThread` directly instead of
  `TrackedThread`.
- Full suite green; ruff at or under the baseline (150).

What the tests do not prove: the abort itself is a process-level Qt behaviour. The tests prove the
precondition is gone (no running worker is unreferenced, no slot is overwritten while running, no
running worker is left at quit). They do not launch the packaged app, and they do not run a real
Google consent.

## Scope
In: the start sites below; `PublishWorker` for Post Now; a bounded consent wait in
`vidforge/vidforge/youtube.py`; the shutdown sweep; `cancel()` on `ShortsWorker` and
`ModelPullWorker`.

Out (follow-ups, not started here): audit step 5 (atomic `settings.json`, database backup, log file,
crash handler); a split of `main.py`; recording an open paid request as "sent, outcome unknown" when
the user quits mid-call (A-1's last sentence; today's behaviour is unchanged, not made worse);
asking before quitting while a post is publishing (the queue's `recover_interrupted` already marks
such a job for review at the next launch); the other UI-thread fetches in code-review P2-2.

## Sites (defect 1)
Every place that stores a worker in a host slot goes through the helper. Sites with no guard today
are marked **new**; the rest already refuse and are moved onto the helper so there is one rule.

| Panel | Slot | Where | Today |
|---|---|---|---|
| Herald write | `social_worker` | `agents/social/panel.py` `write` | **new** |
| Herald clip brief | `social_worker`, `_social_clip_worker` | `make_clip` | **new** |
| Herald clip render | `_social_clip_worker` | `_on_clip_brief` | **new** |
| Press Shorts (3 entry points) | `shorts_worker` | `generate_short`, `quote_finder_generate_short`, calendar Short | **new** (one busy rule) |
| Press manuscript, Quote Finder, calendar text | `manuscript_worker`, `quote_finder_worker`, `calendar_worker` | `agents/manuscript/panel.py` | **new** |
| Kernel chat | `chat_worker` | `main.py` send path | **new** |
| Label | `music_worker` | `agents/music/panel.py` | **new** |
| Sitebuilder | `webdesign_worker` | `agents/webdesign/panel.py` | **new** |
| Vector text (3 flows), images | `fiverr_text_worker`, `fiverr_image_worker` | `agents/fiverr/panel.py` | **new** |
| Nova draft, video estimate, render, resume | `creator_*` | `agents/creator/panel.py` | checked per site in Build |
| Quill write, publish, market | `author_*` | `agents/author/panel.py` | guarded |
| Reel | `video_worker`, `video_estimate_worker` | `agents/video/panel.py` | guarded |
| Suno | `music_worker` | `agents/music/suno_panel.py` | guarded |

Host-owned workers in `main.py` (Muse pull, model scan, ratings, local measure) already check
`isRunning()` before starting; they get `TrackedThread` (or are `DaemonWorker`s) and need no other
change. The release kit driver keeps its own one-item-at-a-time loop.

## Architecture (author: this session, 2026-11-25; GATE)

**A1. `TrackedThread` and the live-worker registry** (`ui/worker_registry.py`, new, Qt-only, no
app imports). `TrackedThread(QThread)` overrides `start()` to add itself to a module-level list
before calling `QThread.start()`. `live_workers()` returns the started workers that are not
finished, and prunes finished ones. Every `QThread` subclass in the app derives from it
(`ChatWorker`, `ModelPullWorker`, `FiverrImageWorker`, `HiggsfieldEstimateWorker`,
`VideoGenerationWorker`, `HiggsfieldWorker`, `VideoWorker`, `KeyProbeWorker`, `LocalMeasureWorker`,
`StageItemWorker`, `ShortsWorker`, `VideoResumeWorker`).
- The list holds a strong reference until the thread has finished. That is the point: a running
  worker can then never be garbage-collected, whatever its slot does. Pruning happens only on the
  GUI thread (in `start()` and `live_workers()`), never from the worker's own `finished` signal,
  because dropping the last reference from inside the finishing thread is itself the crash.
- Rejected: a hand-kept list of attribute names (today's design; it went stale twice). Rejected:
  `findChildren(QThread)` (workers have no Qt parent). Rejected: parking a superseded worker and
  starting the new one anyway: its late `error_signal` would close the new run's token
  (`agents/fiverr/panel.py` `_on_text_error`).
- `DaemonWorker` (Python daemon threads for model lists, ratings, discovery) is not registered: the
  interpreter abandons those at exit and they hold no Qt objects, which is why they exist.

**A2. One slot rule** (same module): `refuse_if_busy(host, label, *slots) -> bool` sets the label
to `[Busy] The previous request is still finishing — one moment.` and returns True when any named
slot holds a running worker; `start_in_slot(host, slot, worker)` stores and starts the worker and
raises `WorkerSlotBusy` if the slot is still busy (a site that forgot the check fails loudly in a
test instead of aborting in use). The check runs **before** `authorize_request`, so a refused
start reserves nothing and shows no cost dialog. These are module functions taking the host, so
panels' fake hosts in tests work unchanged. Press's single busy rule is the `shorts_worker` slot
itself; `_quote_finder_busy` goes.

**A3. Post Now in a worker.** `PublishWorker` (a `DaemonWorker`: network only, holds no Qt
objects, writes nothing; the queue is updated on the GUI thread in its result slot) runs
`publisher.publish(...)`. The click handler keeps every dialog and the `queue_post`/`claim` step on
the GUI thread, disables Post Now, starts the worker and returns. `posted`/`failed` slots do exactly
what the handler does today (`mark_posted`, `mark_retryable`, `mark_uncertain`, the same messages).
One post at a time (slot `social_publish_worker`). Quitting mid-upload abandons the daemon thread;
the job stays `publishing` and `recover_interrupted` marks it for review at the next launch, as it
does for a crash today.

**A4. Bounded consent.** `vidforge/vidforge/youtube.py` passes `timeout_seconds=CONSENT_TIMEOUT_S`
(300) to `run_local_server` and turns its `WSGITimeoutError` (or any failure before a token exists)
into `YouTubeConsentError(YouTubeError)`. `YouTubePublisher.publish` maps that one class to
`PublishError(..., safe_to_retry=True)`: no upload was started. The status line tells the user that
a consent page may be open and how long Imprint waits.

**A5. Shutdown sweep.** `closeEvent` keeps its order (Omni and release-kit questions, project save,
audiobook process, player release), then: `cancel()` every `live_workers()` entry that has one;
wait for all of them against **one shared budget of 3 s** (today: 2 s each, up to 42 s); if any is
still running, log its class name, flush logging and leave with `os._exit(0)` instead of letting the
interpreter destroy a running `QThread` (the abort). The manuscript is saved before this point
(unchanged), SQLite commits are durable in WAL mode, so no data is lost. The exit call is an
attribute (`self._hard_exit`) so tests can observe it without ending the test process.
`ShortsWorker.cancel()` sets a flag checked before the ffmpeg step; `ModelPullWorker.cancel()` makes
the progress callback raise, which closes the streaming response (Ollama keeps the partial layers and
resumes the pull next time).

**ADR:** `docs/adr/0006-tracked-threads.md` records A1 and A5 as a rule (every QThread is a
`TrackedThread`; shutdown sweeps the registry, never a list of names).

**Risks.** `os._exit` skips `atexit` handlers and Qt's own teardown: checked that nothing in the app
relies on `atexit` for persistence (Build verifies with a grep). The 3 s budget is a UX choice
(quit must not hang); a worker that ignores cancel is cut off rather than waited for, which is what
happens today except that today it aborts.

## Build notes (2026-11-25)
Where Build differs from the approved text, and why. None changes what the owner approved: a busy
slot is refused, every QThread is tracked, Post Now runs off the UI thread with a 5-minute consent
limit, quit never aborts.
- **A5, where the hard exit lives.** The spec put `os._exit(0)` in `closeEvent` behind a
  `self._hard_exit` attribute for tests. Build moved it to `leave_if_workers_alive()`, called in
  `main.py` right after `app.exec()` returns. Reason: the registry is process-wide, so a test that
  closes a window while another test's worker runs would have ended the test process; after the
  event loop is the exact moment the interpreter would otherwise destroy a running `QThread`.
  `closeEvent` now cancels and waits (`stop_all`, one 3 s budget) and logs any survivor.
- **Reel's `video_estimate_worker`** was written and never read (Stop and the busy rule use
  `video_worker`); the alias is gone. The estimate handlers of Reel and Muse clear their estimate
  slot first, so the render after it, or a re-run after Apply, is not refused as busy while the
  estimate thread returns from `run()`.
- **Quill publish and market** checked the busy slot after clearing the output and disabling
  Generate, so a refused start stranded the panel. The check now runs first.
- **Herald** declares `_social_clip_worker` and `social_publish_worker` on the host with
  `social_worker`.
- **Known limit.** A worker emits its final signal from inside `run()`, so for a moment after it
  the thread still reports running. A click in that moment gets the busy notice and works on the
  next click; nothing is replaced. Chained starts (estimate to render) release their slot first.
