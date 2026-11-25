# Secure phase: worker crash class (network, auth and file-write parts)

- Spec slug: `worker-crash-class`
- Commit reviewed: `031e3ca` (diff `git diff 839836c 031e3ca`), worktree `wizardly-hertz-78be15`,
  branch `claude/worker-crash-class-bf3d5f`.
- Role: security-engineer, read-only (this report is the only file written). Date: 2026-11-25.
- Playbook: `docs/playbooks/security-engineer.md`, `status: current`, `last-reviewed: 2026-11-11`
  (14 days; not stale).
- Verdict: **no P0, no P1.** One P2 (actions that change a post's record are not blocked while its
  delivery is in flight, a race the old blocking click handler made impossible) and two P3s. The
  confirmation-before-network, one-at-a-time and GUI-thread-only queue rules hold.

## Threat model (scope of this diff)

- **Assets:** the user's social accounts (Reddit password-grant credentials and Pinterest token in
  `.env`; the YouTube OAuth token in vidforge's `.secrets/youtube_token.json`); the duplicate-safe
  delivery ledger (`social_publish_jobs`, `social_posts`), which decides whether a public post can be
  sent again; the user's reputation (a duplicate or unwanted public post cannot be taken back).
- **Trust boundaries:** GUI thread and the `PublishWorker` daemon thread (results cross by queued
  signal); the app and the platform APIs (responses and errors are untrusted text); the app and other
  local processes (the OAuth loopback redirect server on `localhost`, random port); the app and its
  own state on disk (SQLite WAL, `.env`, token file), same-user, so tampering is not an attacker
  boundary here.
- **Entry points touched:** Herald Post Now (`agents/social/panel.py:1066` `post_selected`,
  `:1178` `_on_published`, `:1184` `_on_publish_failed`), `PublishWorker.run`
  (`agents/social/workers.py:39-45`), the consent wait (`vidforge/vidforge/youtube.py:78-95`), the
  consent error mapping (`agents/social/publishing.py:300-305`), the quit path
  (`main.py:6743` `closeEvent`, `main.py:7017-7020`, `ui/worker_registry.py:110-141`).

STRIDE in short. **Spoofing:** the OAuth redirect is bound to `localhost` and checked with state and
PKCE (library default). **Tampering / Repudiation:** the delivery ledger is the real risk class; a
lost or overwritten record leads to a duplicate public post or an unrecorded one (P2-1).
**Information disclosure:** exception text shown and stored (no token found in any path).
**DoS:** the consent wait (P3-1). **Elevation:** a post without the user's "Post now?" yes (none
found).

## Findings

### P2-1: Delete, Delete campaign and Mark Posted still act on a post whose delivery is in flight

- **Where:** `agents/social/panel.py:1058-1064` (`delete_post`, no status check, no question),
  `agents/social/panel.py:402-414` (`delete_campaign`), `agents/social/panel.py:1041-1056`
  (`mark_posted`); `agents/social/store.py:123-128`, `:82-91`, `:154-166`; the result slots
  `agents/social/panel.py:1178-1182` and `:1184-1199`; `agents/social/queue.py:173-216`
  (`mark_posted` / `_mark_problem` raise `QueueError` for a missing job and update any status
  unconditionally). `_update_publish_action` (`panel.py:926-937`) disables only Post Now.
- **Why it is new:** before this diff `publish()` ran in the click handler, so no other button could
  be clicked during a delivery. Now the window stays live for the whole upload (and up to 5 minutes
  of consent), which is the point of the change, but these three actions were not fenced.
- **Scenario A (lost record of a real public post):** the user clicks Post Now on a Reddit or
  YouTube item, then Delete on the same row while it reads "Posting…". `store.delete_post` removes
  the job and the post. The upload succeeds; `_on_published` calls `queue.mark_posted(job_id, …)`,
  which raises `QueueError: That publish job no longer exists.` inside the Qt slot. The status line
  never changes from "Posting…", the permalink is never shown, and nothing records that a public post
  exists. On the failure side the same exception fires before `QMessageBox.warning`, so the
  "Result unknown — check the platform" warning, the one guard against a duplicate after an
  ambiguous result, is never shown. Delete campaign does the same for every post in it.
- **Scenario B (manual "posted" overwritten):** the user clicks Mark Posted while the API call is in
  flight (for example after posting by hand in the browser). If the API call then fails,
  `_on_publish_failed` calls `queue.mark_retryable`, which sets both rows back to `retryable`; the
  button turns into "Retry Post" with no warning, and a retry duplicates the hand-made post.
- **Evidence:** reproduced against a temporary DB (`init_db` on a temp path, no Qt, no network) by
  calling the same functions in the same order the GUI would:
  `case1 mark_posted raised QueueError: That publish job no longer exists.` and
  `case2 status after: retryable retryable`. Not reproduced by clicking in a running app.
- **Impact:** integrity of the duplicate-safety ledger and of what the user is told about a public
  post. Requires the user's own click on the item being posted, hence P2, not P1.
- **Fix (test first, one test per scenario):**
  - Disable Delete and Mark Posted for a selected post whose status is `publishing`, and Delete
    campaign while `host.social_publish_worker` is running; refuse the same in the handlers (a
    disabled button is not a guard).
  - In `store.delete_post` / `delete_campaign`, refuse rows whose job is `publishing`.
  - Make `queue.mark_posted`, `mark_retryable` and `mark_uncertain` transition only
    `WHERE status = 'publishing'` (check `rowcount`), so a result never overwrites a state the user
    set meanwhile.
  - In `_on_published` / `_on_publish_failed`, catch `QueueError` and still tell the user what
    happened (the permalink, or the "check the platform" warning) before anything else.

### P3-1: The consent timeout bounds only the wait for a connection; an idle loopback connection holds the worker indefinitely

- **Where:** `vidforge/vidforge/youtube.py:81-83`; library
  `google_auth_oauthlib/flow.py:466-467` (1.5.0: `local_server.timeout = timeout_seconds` then a
  single `handle_request()`); `_WSGIRequestHandler` (`flow.py:558`) sets no socket timeout.
- **Scenario:** any local process (or, not verified, a browser's speculative pre-connect) opens a TCP
  connection to the redirect port and sends nothing. `handle_request` accepts it and blocks reading
  the request line for as long as the connection stays open; `timeout_seconds` no longer applies.
- **Evidence:** offline probe (browser opening stubbed, fake client secret, `CONSENT_TIMEOUT_S`
  patched to 2 s, never reaches `fetch_token`): with no connection, `YouTubeConsentError` (cause
  `WSGITimeoutError`) after 2.1 s; with an idle connection held 8 s, the same error only after 8.0 s.
  In both runs the server socket was closed afterwards and no token file was written.
- **Impact:** small. The wait is now off the UI thread, so the window stays live; the
  `PublishWorker` stays alive, Post Now answers "[Busy]" until restart, and the job is then marked
  `needs_review` at the next launch although nothing was uploaded. Needs a local process on the
  user's account, which could do worse anyway.
- **Fix:** give the request read a timeout, for example run the consent wait through a small local
  wrapper that uses `flow.authorization_url()` and its own `wsgiref` server whose handler sets
  `timeout = 30` and loops `handle_request()` until an overall monotonic deadline; or, smaller but
  touching a private class, set `timeout` on a subclass of `_WSGIRequestHandler`. Keep the
  `except Exception` mapping to `YouTubeConsentError`.

### P3-2: The YouTube token is written non-atomically and is created with the umask before `chmod 0600`

- **Where:** `vidforge/vidforge/youtube.py:94-95` (`write_text`, then `chmod`); read back at
  `:72` outside the consent `try`, so a broken file surfaces as an ordinary `PublishError`
  (`publishing.py:304`, `safe_to_retry=False`).
- **Scenario:** the lines are unchanged, but their reach is wider: the write now runs on the
  `PublishWorker` daemon thread (consent completion or a token refresh), and a quit abandons daemon
  threads at interpreter exit, or ends the process with `os._exit(0)` when another worker outlived
  the 3 s budget (`ui/worker_registry.py:120-141`). A quit inside that write leaves a truncated
  token. Every later Post Now to YouTube then fails at `from_authorized_user_file`, is classed
  "Result unknown — check the platform" (`needs_review`) although nothing was uploaded, and keeps
  doing so until the user deletes the file. Separately, on first creation the file exists for a
  moment with the umask mode (typically 0644) before `chmod`, and stays so if the process ends
  between the two calls.
- **Evidence:** code reading. The window is microseconds; not reproduced.
- **Impact:** availability of YouTube posting and a misleading "check the platform" state; brief
  token readability by other local users (macOS home folders usually block them). No duplicate risk.
- **Fix:** write as `services/api_keys.py:228-240` already does for `.env`: `mkstemp` in the same
  folder (or `os.open(..., O_CREAT | O_EXCL | O_WRONLY, 0o600)`), write, `os.replace`. Treat an
  unreadable token file as "consent needed" (ignore it and run the consent flow), so the failure
  stays in the safe-to-retry branch.

## Checked and found fine

- **"Post now?" precedes every network call.** The only `publish()` call is
  `agents/social/workers.py:40`; the only `PublishWorker` is built at `panel.py:1170`, after the
  "Post now?" yes (`:1142-1148`), the Reddit subreddit check (`:1120-1124`) and the atomic claim
  (`:1150-1158`). A `needs_review` retry needs an extra explicit warning first (`:1093-1102`), then
  "Post now?" again. `post_selected` is reached only from the button (`panel.py:269`; grep).
- **No double post from one process.** Busy slot refused before any dialog (`:1079-1081`); the
  button is disabled at start (`:1167`) and stays disabled for `publishing` (`:933-937`);
  `queue_post` refuses a `publishing` job and `claim` is an atomic `UPDATE … WHERE status='queued'`
  with a `rowcount` check (`queue.py:152-166`), which also holds across two app instances. The
  dialogs are modal, so a second click cannot re-enter during the questions. In the gap where the
  thread has ended but its result signal is still queued, the DB still reads `publishing`
  (`_selected_post` re-reads the DB, `panel.py:1025-1032`), so a click is refused.
- **Delivery queue written on the GUI thread only.** `PublishWorker.run` does nothing but
  `publish()`; `queue.mark_*` run in slots bound to the panel (a GUI-thread QObject), so the
  connection is queued; `DaemonWorker._emit` swallows the `RuntimeError` of a destroyed receiver
  (`ui/workers.py:168-173`). Covered by `test_a_failed_post_is_classified_on_the_ui_thread`. The
  panel is built once (`main.py:3147`), so `host.social_publish_worker = None` (`panel.py:324`) and
  `recover_interrupted` (`:327`) cannot run during a delivery.
- **No token in exception text.** The only new text is `YouTubeConsentError`'s fixed message; the
  `__cause__` is not shown. All credentials travel in headers or form bodies (Reddit
  `publishing.py:154-167, 190-197`; Pinterest `:341-342`; Google credentials as an Authorization
  header), so `requests` and `HttpError` messages carry URLs and statuses, not secrets. Pinterest
  echoes 200 characters of the server response (pre-existing). The exception object (and its
  traceback frames) lives only until the slot returns and is not logged. Not verified against live
  error responses.
- **Loopback server closed on timeout, no token on failure.** `server_close()` is in a `finally`
  (`flow.py:483-484`); the probe above confirmed the port refuses connections afterwards and no token
  file exists. `youtube.py:94-95` is after the `try` whose `except` raises. Bound to `localhost`;
  state and PKCE are on (`autogenerate_code_verifier=True`, `flow.py:104, 244-252`), so a local
  process cannot inject an authorization code.
- **"Safe to retry" cannot duplicate an upload.** The `except` wraps only `run_local_server`
  (including its `fetch_token`); `_service()` runs at `youtube.py:139`, before `MediaFileUpload` and
  `videos().insert`. `publishing.py:302-303` marks only that class safe. A retry needs a click and
  "Post now?"; there is no scheduler. Uploads are `private` (`panel.py:1140`), and `public` needs
  vidforge's two-key guard (`youtube.py:119-124`).
- **Token permissions unchanged.** Still `chmod 0o600` after a fresh consent; the refresh path
  rewrites an existing file, which keeps its mode (see P3-2 for the creation window).
- **Quit path.** `leave_if_workers_alive()` runs only after `app.exec()` returns (`main.py:7017-7020`),
  so no GUI-thread write is in progress. `.env` is written only from the Settings dialog on the GUI
  thread (`ui/dialogs.py:1018`), atomically and at 0600 (`services/api_keys.py:228-240`). Each
  `queue.mark_*` / `claim` is one SQLite transaction; a process exit (not a power loss) keeps
  committed WAL frames and rolls back an open transaction. No `atexit` handler in app code (grep).
  `PublishWorker` is a `DaemonWorker`, not in the registry: it neither triggers `os._exit` nor is
  waited for, and its job stays `publishing`, which `recover_interrupted` (`queue.py:219-245`)
  turns into `needs_review` at the next launch; retrying it needs the explicit warning. An
  interrupted synchronous Omni render is excluded from `sweep_lost` (`agents/video/jobs.py:129-134`)
  and its clip is saved atomically (`ui/workers.py:405-411`): not made worse than the old abort.
  Quitting during a post without being asked is out of scope by the spec. `os._exit(0)` reports a
  forced exit as success: informational only.
- **Dependencies.** The diff changes no manifest. `google-auth-oauthlib` is unpinned in
  `requirements.txt:44` (installed 1.5.0; `vidforge/requirements.txt:15` asks `>=1.2`, which has
  `timeout_seconds`); an older version without it would raise `TypeError`, caught and reported as a
  consent failure, so still no upload.

## Commands run

- `.venv/bin/python -m pytest -q -p no:randomly tests/test_worker_crash_class.py`: 30 passed.
- `.venv/bin/python -m pytest -q tests/test_social.py tests/test_social_onboarding.py`: 86 passed.
- Offline consent probe (scratchpad `consent_probe.py`, browser stubbed, loopback only): results
  under P3-1.
- Temp-DB race repro (scratchpad `delete_race.py`): results under P2-1.

## Not verified

- A real Google consent page, any live platform call, or network of any kind.
- The packaged app, and the races above by clicking in a running app.
- The full suite (only the three files above were run).
- A CVE audit: `pip-audit` is not installed in the venv and OSV was not queried (no network used);
  the diff changes no dependency.
- Whether a browser's pre-connect can trigger P3-1 without a local attacker.
