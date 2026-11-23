# Code review: model-updates-visibility

Reviewed 2026-11-23 by the `code-reviewer` agent (read-only, not the author). Branch
`claude/model-updates-visible`, commit `0ca683f` on `ec1cda5`. Scope: the visibility part (G5) of
`docs/specs/model-updates.md`: the Model updates section open by default, and one status-line
sentence when a check finds something. Playbook `code-reviewer.md`: `status: current`,
last-reviewed 2026-10-14 (40 days, not stale).

**Verdict: merge after fixes.** 0 P0, 2 P1, 4 P2, 7 P3. The section-open change is correct and the
diff is safe (no new thread, no UI-thread fetch, nothing switches a model), but the status-line
sentence does not reach the user in the two most common startup situations, and the docs say it does.

Run by the reviewer: `tests/test_model_watch.py` under `--randomly-seed` 1, 2 and 3 (47 passed
each), plus read-only probe scripts outside the repo. Not verified: ruff and the ratchet (ruff is
not in the venv); the full suite (not run, by instruction).

## P0
None.

## P1

**P1-1. The sentence is written to a label the user cannot see at startup.** `main.py:5111`,
`main.py:433`, `main.py:3698`
- `chat_status_label` lives in `normal_panel`, which is hidden for every workspace with its own
  panel, and the app always starts with `select_agent("author")`.
- The startup check, the main trigger, therefore writes to an invisible line.
- Probe on a fresh window after a find: `normal_panel visible: False`, `label isHidden: False
  label isVisible: False`; after `select_agent("chat")` it is `True`, back on author `False`.
- The new test asserts `not isHidden()` (`tests/test_model_watch.py:276`), which passes while the
  label is invisible.
- Fix: put the sentence somewhere visible in every workspace, or scope the README and CHANGELOG
  claim to Chat. Either way assert `isVisible()` with Chat selected, plus the other-workspace case.

**P1-2. A model that a panel's own fetch sees first is never announced.** `main.py:4929`,
`main.py:4788`, `main.py:439-441`
- The snapshot is "everything pending when the check begins". The comment at 439-441 says the
  startup check deliberately runs after the panels' own fetches, and those call
  `_observe_live_models`. For any provider selected in a panel, the new model is already pending
  and lands in `known`.
- Probe: baseline, add `qwen4-max`, call `_on_models_listed("qwen", ...)`, then run a check:
  `PENDING after panel fetch: ['qwen4-max']`, `STATUS after scan: ''`.
- With the startup check switched off nothing is ever announced, although `README.md:518` says
  news still arrives that way.
- Fix: track "already announced" separately from "pending" (a set of announced keys, or announce
  from `_on_models_listed` when `observe` returns news). Add a test for panel-fetch-then-scan.

## P2

**P2-1. An announcement suppressed by a running request is dropped, not deferred.** `main.py:5100`,
`main.py:5110`. `_model_scan_known` is cleared before the guard, and the next check treats the
model as known. Probe: after the request ends the line still reads `Processing... elapsed 00:00`;
the next check gives `''`. `README.md:524` is literally true but does not say the news is lost
from the line. Fix: keep the text and show it from `stop_chat_timer`, or say so in the README.

**P2-2. The sentence goes stale and is never cleared.** `main.py:5113` (`dismiss_new_models`).
Probe: after `dismiss_new_models()` the label still reads `New models available: ...`. Fix: clear
the line on dismiss if it still holds the announcement.

**P2-3. `chat_timer.isActive()` covers only chat requests; other writers are clobbered.**
`main.py:5109-5111`. One-shot lines that would be replaced: `Measured ...` / `... stays unrated`
(`main.py:1319-1322`), `Muse Glimmer installed` / `download failed` (`main.py:1087`, `1102`), and
the post-reply `_job_status_line` (`main.py:5765`). In the other direction, the next Muse pull
progress tick (`main.py:1069`) overwrites the announcement. Not verified by running; read from the
code. Fix as P2-1 (defer or queue), or accept and document.

**P2-4. A long sentence is clipped, and the clipped part is the instruction.** `main.py:2867`. The
label has no word wrap. Probe with three long ids plus "and 1 more": the label needs 1009 px and is
640 px wide in the 796 px test window; the tail "See Model updates in the side rail." is cut. The
single-model sentence was not measured; the real window width is not verified. Fix: put the
pointer first, shorten, or enable wrap.

## P3
- **"Side rail" is ambiguous.** `services/model_watch_digest.py:220`. The app has a left project
  rail and a right rail; the README says "right rail" elsewhere (`README.md:37`, `2750`, `3528`).
- **Repeats every launch on a disk error.** `main.py:4810-4816`. With `_save` raising `OSError` the
  model is pending in memory and announced, but nothing is stored, so the next launch announces it
  again.
- **Possible lost announcement on a quick second check.** `main.py:4909-4911`, `5099-5100`. If
  `check_for_new_models` runs after the worker thread has exited but before its queued `finished`
  is delivered, the snapshot is retaken with scan 1's finds in it. Narrow window; not verified.
- **Snapshot left set on the no-keys early return.** `main.py:4948-4950`. Harmless today, but the
  state is not initialised in `__init__` and is read with `getattr`.
- **Panel fetch during a running scan is credited to "that check".** `main.py:4788` with
  `5104-5108`. Harmless, but "names only what that check found" is not strictly true.
- **Test relies on private state.** `tests/test_model_watch.py:260` reads `section._expanded`; the
  `header_btn` and `content` assertions already cover the behaviour.
- **Copy function.** Pluralisation and the "and N more" boundary are right for 1, 2, 3 and 5; 4 is
  untested but right by inspection.

## Tests: order and leftover state
- Order-independent as far as the reviewer could tell: each status-line test resets the line
  itself, and no other test in the module starts the chat timer or toggles the section.
- Left on the shared (module-scoped) window: a stopped `chat_timer`, `chat_started_at`, and, from
  the older scan tests that now announce, a leftover "New model available..." text.
- The running-request test would pass trivially if the scan found nothing; add an assertion that
  `qwen4-max` is pending.

## The one-off segfault
Cannot tell for certain; nothing in this diff points that way. The lazily created `QTimer(self)`
is stopped in `finally` and is one more child of a window that already owns timers;
`tests/test_chat_streaming.py` and `tests/test_request_estimate.py` already call
`start_chat_timer` on `main`; `expanded=True` and a label text add no reference cycle the reviewer
could identify. The TODO's next step (several recorded seeds on the branch and on `main`) is the
right way to settle it.

## Docs against code
- `README.md:518-524` and `CHANGELOG.md:32-38`: "a check that finds something says so in the chat
  status line" is not true in the P1-1 and P1-2 cases.
- "Up to three and counts the rest", "not announced again at the next start" and "open by default"
  match the code. The `TODO.md` entries are accurate.
