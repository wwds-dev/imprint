# Spec: Quill never loses the Draft (audit QB-1)

Status: Define approved by the owner 2026-11-20 ("Yes, as recommended": D1–D3 as recommended). Built 2026-11-20. Priority: P0 (audit blocker QB-1,
`docs/audit/code-readiness-audit-2026-11-18.md`). Type: user-visible bug fix. Owner session:
`claude/quill-draft-qb1-5d96fa`.

## Problem
Quill's Draft is the manuscript, and every change to it is autosaved to the project workspace
(`agents/author/panel.py:672-677`). Checked against the code on 2026-11-20 (lines unchanged from the audit):
- `write()` clears the Draft before sending (`panel.py:1073-1074`) and streams the reply into the
  empty box. Only a refused or held request puts it back (`:1043-1051`).
- An error (`_on_error`, `:1151`) or Stop (`stop`, `:1160`) leaves the Draft empty or holding a
  fragment; the autosave then stores that. The book is gone.
- Generate Outline, Develop Characters and Build World stream into the Draft too; the reply is
  copied to its tab at the end (`:1263-1268`) but also replaces the manuscript.
- Revise / Improve, Tighten Structure and Strengthen Argument run through `write()`, which sends
  the draft only as context, cut to its last 3,000 characters (`:983-985`). The reply then
  replaces the whole manuscript: revising a 50,000-word book leaves about 500 revised words.

## Goal and success measure
No Write, error or Stop can remove text the Draft held before the click, and the autosave never
stores a state that lost it. Measured by offscreen tests with a fake worker (no model call, no
cost) that stream tokens through the real `token_signal` / `finished_signal` / `error_signal`
handlers and then run the project autosave:
1. Write Scene on a non-empty Draft, finished: the old text is still there, the new scene follows it.
2. Same, then error: old text intact; then Stop: old text intact. Autosave after each holds it.
3. Generate Outline / Develop Characters / Build World: the Draft is unchanged during and after the
   run; the reply lands only in its tab. Error or Stop leaves the tab as it was.
4. Revise with nothing selected: the prompt carries the whole Draft (no `[-3000:]` cut); the reply
   replaces the Draft as one undoable edit. With a selection: only the selection is sent and replaced.
5. Revise on more than the limit (D2): no request is sent, the status says why and what to do.
6. Revise whose reply stopped at the length limit, errored or was stopped: the Draft is unchanged.
7. A refused or held Write leaves the Draft exactly as it was.
8. The full suite stays green; `tests/test_author_continuity.py` (the 3,000-character continuity tail
   for prose Write) passes unchanged.

## Behaviour (proposed; D1–D3 need the owner)
Tasks fall into three kinds:
- **Prose** (Write Scene, Write Chapter, Write Dialogue, Add Case Study / Example, Continue Draft):
  the reply streams in **after** the existing Draft, separated by a blank line, as Continue already
  does. On finish the streamed part is swapped for its clean `[DRAFT]` section, and `[OUTLINE]` /
  `[CHARACTER]` / `[WORLD]` sections go to their tabs (as today). On error or Stop the text written
  so far stays after the old Draft, as Continue already behaves. **(D1)**
- **Notes** (Generate Outline, Develop Characters, Build World): the reply is collected off-screen
  (the status line counts characters received) and goes to its tab on finish. The Draft is never touched.
- **Revise** (Revise / Improve, Tighten Structure, Strengthen Argument): works on the Draft
  selection, or the whole Draft when nothing is selected, sent in full in the prompt. The reply is
  collected off-screen and, on a complete finish, replaces exactly that text as one edit, so
  Ctrl+Z in the Draft brings the earlier version back. A cut-off, failed or stopped revision changes
  nothing. **(D2, D3)**

## Owner decisions
- **D1 Prose Write adds, it no longer replaces.** Recommended: add after the Draft. Alternative:
  replace as today but as one undoable edit. Adding is the only form in which a successful Write
  cannot lose text; with an empty Draft it is identical to today.
- **D2 Revise size limit: 20,000 characters (about 3,300 words) per run.** Every reply is capped at
  8,192 tokens (`services/output_limits.MAX_OUTPUT_TOKENS`), roughly 30,000 characters of English;
  a revision runs a little longer than its source, so 20,000 leaves margin. Above it the Write is
  refused before any request: "Revise works on up to 20,000 characters (about 3,300 words) at a
  time, because a reply is limited to 8,192 tokens. Select a chapter or passage in the Draft and
  press Write again." Alternative: no limit, rely on D3.
- **D3 A cut-off revision is discarded.** The Draft stays as it was and the status says so (the
  partial reply was paid for; the request is still recorded). Alternative: add it after the Draft
  under a heading for the user to merge by hand.

## Non-goals
Continue's behaviour (already appends). A chapter model or per-chapter revise. Undo across an
app restart. Changes to the request guard, pricing or the routing banner.

## Scope
`agents/author/panel.py` (`write`, `continue_draft`, `_start_worker`, `_on_token`, `_on_finished`,
`_on_error`, `stop`, `_populate_tabs`); new `tests/test_author_draft_safety.py`;
`agents/author/README.md`, `docs/agents/author.md`, `CHANGELOG.md`, `TODO.md`.
No new dependency, network surface, secret or file write: Secure is not required. Comply skipped
(no legal surface changes). Launch skipped (no public claim changes).

## Risks
- The user types in the Draft while a prose reply streams: positions are tracked with a
  `QTextCursor`, which Qt moves with edits, so the user's text is not overwritten.
- Undo after a Revise holds only while the panel lives; reloading the project resets Qt's undo stack.

## As built (2026-11-20)
`agents/author/panel.py`: `NOTES_TASKS`, `REVISE_TASKS`, `REVISE_MAX_CHARS` / `REVISE_TOO_LONG` at
module top; `_begin_stream` runs only after the guard authorizes (so a refused or held run touches
nothing); `_on_token` ignores tokens once a run is stopped or failed; `_replace_streamed` swaps the
raw streamed part for its clean `[DRAFT]` text; revise replaces through the saved selection cursor
in one edit block. Continue's separator also moved after authorization (a refused Continue no
longer leaves a stray blank line). Tests: `tests/test_author_draft_safety.py` (20, fake worker, real
signal handlers, autosave after each case). Mutation check (6 planted): limit off-by-one, late-token guard and cut-off
guard killed; one did not apply; splitting the revise edit block survived as equivalent (Qt still
undoes it in one step); dropping the blank-line removal when a prose reply holds only notes survived,
got a test, and is now killed.
Review (code-reviewer, 2026-11-20): no P0; two P1 and three P2, all fixed in the follow-up
commit with tests: (P1) a revision under half the length of its source is not applied, because
a local model can drop the start of a long prompt and neither local server reliably reports a
cut-off (`REVISE_MIN_RATIO`); (P1) the Draft is read-only while a revision runs, so typed text is
never swallowed by the replace; (P2) a finish that races Stop is ignored; (P2) the Task is read
when the run starts, so switching it mid-run cannot reroute the reply; (P2) a revised selection
keeps its own leading and trailing whitespace.
Skipped phases: Design (no new controls), Architect (no state, thread or boundary change), Secure
(no network, secret, input or file-write change), Comply and Launch (no legal or public-claim change).
