# Security review: quill-draft-safety (Quill never loses the Draft, audit QB-1), 2026-11-24

Role: security-engineer (read-only on code and tests; did not write the code). Playbook `last-reviewed: 2026-11-11`, `status: current`.

Scope: spec `docs/specs/quill-draft-safety.md`; commits `67f35ad`, `0ac4cbc`, `5aea8ec` (`git diff 67f35ad^..5aea8ec -- agents/author/panel.py`);
later commits on `agents/author`: `4c926c3` (merged by `a4b6da8`) gives the Sources box a parent, four lines, no draft
logic; `1cabc65` is docs. Reviewed at `3dd09f9` on
`claude/happy-dubinsky-48c27c`. The change adds no snapshot or backup file: the Draft lives in one SQLite row
(`project_workspaces.state_json`, `services/project_workspaces.py:41-48`), so the review covers that row, the paths that write it,
and the one file write the change does add (Saved Chats, P2-6). No earlier `quill-draft-safety-*` report exists.

## Verdict
**Fix first.** No P0. One P1, six P2, four P3.
- The spec's own cases hold: `tests/test_author_draft_safety.py` passes (part of 70 passed, 11 skipped over four files), and a
  refused, held, failed or stopped Write leaves the earlier text in place.
- **P1-1 is a path the tests do not cover:** a Revise whose reply carries a section marker replaces the text with only part of it and
  reports "[Done] Revised". It is reachable from normal use (Stop a Write, then Revise).
- P2-1 to P2-5 are losses outside the Write/error/Stop cases the spec set as its goal, but inside its title. Most are older than this
  change. They need an owner decision before the app says the Draft cannot be lost.
- The spec skipped this phase because it saw "no new file write". That is not exact: Revise now puts the manuscript passage into a
  Saved Chat file (P2-6).

## Threat model
| Asset | Threat | Control today | Evidence |
|---|---|---|---|
| Manuscript (Draft) | Reply overwrites or truncates it | Prose appends; notes stay off the Draft; Revise replaces only the sent text, in one undo step; length guards | `panel.py:1189-1221`, `:1262-1288`, `:1444-1451`. Gap: **P1-1** |
| Manuscript on disk | Lost by a failed or misdirected save | One transaction per save; flush on quit and before Publish | `project_workspaces.py:37-55`, `main.py:6475-6479`. Gaps: **P2-1, P2-2, P2-3** |
| Notes tabs (Outline, Characters, World, Sources) | Overwritten by model output or one click | None | **P2-4, P2-5** |
| Where it is written | Path steered outside the data folder | The Draft goes into SQLite with bound parameters; no path is built from a title or project name. Save Draft and Export use the system save dialog; the suggested name strips everything but word characters, spaces and `-` | `project_workspaces.py:41-55`, `panel.py:1358-1365`, `:1384-1396` |
| App bundle | Writes inside it | Data base is `user_data_base()`: `~/Library/Application Support/Imprint/` when frozen, the source tree when run from source (`data/` git-ignored for `*.db` and `data/chats/`) | `database.py:9-10`, `runtime_paths.py:102-116`, `.gitignore:21-23,58` |
| Other local users | Read the manuscript | Parent folders are `drwx------` (`~/Documents`, `~/Library`); the DB itself is `-rw-r--r--` | `stat` on the main checkout. P3-4 |
| Untrusted input | Manuscript or reply text run as markup or code | Draft text is inserted as plain text; the status line is `Qt.PlainText`; section markers are the only parsed syntax | `panel.py:692`, `:1244-1246`, `:1485-1496`. Gap: **P1-1** |
| Personal data in drafts | Kept longer than the user expects | Project delete cascades the workspace row | `database.py:84-91`. Gaps: **P2-6**, P3-3 |
| Money | A run that is paid but not recorded | Token kept per run | Gap: P3-1 |

## Findings

### P1
**P1-1 Revise can still drop manuscript text: a section marker in the reply decides what replaces it.**
`agents/author/panel.py:1269-1271` (`revised = sections["draft"]` as soon as any marker is found), `:1485-1496` (markers matched
anywhere in the text, any case), `:1275` (the guard only asks for half the length, a quarter for Tighten Structure),
`:1431-1436` (the other sections go to their tabs). Stop and error leave the raw stream in the Draft, marker included
(`:1314-1322`, `:1326-1340`), and the system prompt tells the model to head a draft with `**[DRAFT]**` (`agents/author/agent.py:20-30`).
- Scenario A (probe r0, normal use): the Draft holds a short hand-written opening. Write Scene streams `**[DRAFT]**` plus a long
  scene; the user presses Stop. The marker is now in the Draft. Later: Revise with nothing selected. A reply that returns the text
  faithfully contains the marker, so only the text after it is used. Result: the opening is gone, status "[Done] Revised". Probe:
  `marker left in Draft after Stop: True`, `intro still in Draft after Revise: False`.
- Scenario B (probe q5): a reply `[DRAFT] <first 60%> [WORLD] <rest>` replaces a 1,000-character selection with 599 characters;
  the rest lands in the World tab, replacing the user's notes there.
- Scenario C: a manuscript that itself contains `[outline]` or `[world]` (any case), or imported text that asks the model to add one.
- Impact: part of the manuscript is removed, the status says done, and the autosave stores it 700 ms later. Ctrl+Z brings the Draft
  back only while the panel is open and only if the user notices; the overwritten tab has no undo. When the surviving part is under
  half, the run is refused with "[Incomplete?]" on every attempt until the user finds and deletes the marker.
- Fix: do not parse sections for a Revise reply: use the whole reply, and strip only a marker that is the first line. Never write
  tabs from a Revise. Remove markers from a stream that ends by Stop or error. Add tests for A and B.

### P2
**P2-1 A failed autosave is silent.** `panel.py:143-146`, `:888-896`; `services/project_workspaces.py:32-55`; `main.py:6475-6479`.
With a full disk, a read-only folder or a locked database, `save()` raises inside the timer slot: the traceback goes to stderr, the
status line does not change (probe q1: `'status-before'`), and every later autosave fails the same way. On quit the error is caught,
printed and the window closes. Everything typed since the last good save is lost with no message. Fix: catch in
`_persist_project_state`, show "[Not saved]" with the reason and retry; on quit, ask before closing and offer Save Draft to a file.

**P2-2 A failed project switch can save Book A into Book B.** `panel.py:934-936` sets `_project_id` before `load()` runs;
`main.py:5986-5996` catches only `RuntimeError`. If `load()` raises (`sqlite3.OperationalError`), the panel still shows Book A but
is filed under Book B. Probe q2: the next save went to `project-B` with `'!BOOK A manuscript'`, and with an empty title and
byline. Book B's only copy is replaced. Related: a workspace row that cannot be parsed loads as an empty Draft
(`project_workspaces.py:25-29`) and the next keystroke overwrites the damaged row. Fix: load and apply first, switch the id last;
catch database errors in `_switch_project` and put the selector back; keep an unreadable row aside instead of overwriting it.

**P2-3 With no project selected, the Draft is never saved.** `panel.py:884-886` and `:889-890` return when `_project_id` is empty;
the text is held in memory (`:932-933`), and the quit path calls the same function (`main.py:6476-6477`). "All projects" and
"Unfiled" are normal selector states (`README.md:333-336`). Quit, crash or restart loses the whole Draft without a warning. Read
from the code, not probed. Fix: persist the unfiled workspace too, or warn on quit and on first keystroke that nothing is saved.

**P2-4 A reply section replaces a whole notes tab, with no undo.** `panel.py:1431-1436` (`setPlainText`). Any prose Write or
Revise whose reply holds `[OUTLINE]`, `[CHARACTER]` or `[WORLD]` replaces that tab. Probe q4: a hand-written character bible
became `'Mira: (model text)'`, undo available `False`, and the autosave stored it. The spec keeps this "as today"; it is the same
kind of loss as QB-1, for the notes. Owner decision. Fix: replace inside one edit block (undoable), or add after the existing notes.

**P2-5 Clear wipes the Draft, four tabs and the title in one click.** `panel.py:452-454`, `:1406-1420`. No confirmation
(probe q3: 0 dialogs), no undo (`False`), and the autosave then stores the empty state and writes an empty title to the project
row (`work_title: ''`, `project_workspaces.py:49-55`). There is no other copy. Fix: confirm, keep it undoable, leave the project's
title alone.

**P2-6 Revise now writes the manuscript passage into Saved Chats, and those outlive the project.** New with this change.
`panel.py:1153-1157` puts the text in `prompt` (probe q7); `main.py:5519-5530` saves prompt and reply as a chat;
`services/history_store.py:24`, `:40-41` (one new JSON file per request, default file mode, written in place). Up to 20,000
characters per run, including revisions that were then discarded (the record is made at `panel.py:1260`, before the checks at
`:1275-1288`). Deleting a project keeps its chats (`history_store.py:50-65`); removal is one chat at a time (`main.py:6217-6229`).
Also by design: a cloud Revise now sends up to 20,000 characters where it sent the last 3,000. Drafts can name real people, so
this belongs in the privacy note and needs a qualified person's view; this report gives no legal opinion. Fix options: do not
store the source text of a Revise in the chat; or offer to delete a project's chats with the project; state how long chats are kept.

## P3
1. **Signals are not tied to their worker** (`panel.py:1108-1112`, `:1314-1318`). Probe q6: the late error of a stopped run
   abandoned the next run's token (`['tok-1', 'tok-2']`), switched its stream off and dropped its tokens, so the second paid run
   finishes unrecorded (`:1259-1260`). The timing with real threads was not reproduced. Fix: ignore a signal whose sender is not
   `host.author_worker`.
2. **A failed record leaves a Revise stuck** (`panel.py:1260-1261`: `record_request` runs before `_end_stream`). Probe q8, disk
   full: Draft read-only, Write disabled, status "[Working…]", the paid revision not applied. Stop recovers. Fix: end the stream in
   a `finally`, then report the failure.
3. **One copy, no history.** Each save overwrites the row (`project_workspaces.py:41-48`); undo ends when the project is
   reloaded (spec, Risks). A few earlier states per project would turn P1-1 and P2-2 to P2-5 into an inconvenience. The other
   side: deleted or overwritten text stays in SQLite's free pages and the `-wal` file until reused (the connection sets only WAL
   and foreign keys, `database.py:665-670`), which matters for any "deleted means erased" statement.
4. **File modes.** `data/imprint.db` is `-rw-r--r--` and `data/chats/` is `drwxr-xr-x`; the protection is the parent folder.
   Fine on a single-user Mac; copies made by backup or sync tools carry the open mode.

## Not verified
- Scenario A with a live model (whether a given model repeats the marker); the probes use a fake worker and the real handlers.
- P3-1's timing with real `QThread`s; a real full disk or read-only volume; the packaged (frozen) app's paths, read from the code only.
- P2-3 was read from the code, not run.
- Dependency audit: not run, because this task allowed no network calls. The three commits change no requirements file
  (`git diff --stat 67f35ad^..5aea8ec -- requirements.txt` is empty). The playbook asks for an audit of the installed set before Release.
- Full suite not run (a run was in progress). Ran: `tests/test_author_draft_safety.py`, `tests/test_release_kit_security_fixes.py`,
  `tests/test_providers_drift.py`, `tests/test_routing_panels.py`: 70 passed, 11 skipped (76 s).
- Whether the retention in P2-6 and P3-3 meets any legal duty: for the owner or a lawyer.

Probes (read-only, temp DB via `tests/conftest.py`, fake worker, no network): session scratchpad `sec_probe/probe_quill.py`,
`probe_quill2.py`, and `test_r0` in `probe_routing.py`; 9 passed.
