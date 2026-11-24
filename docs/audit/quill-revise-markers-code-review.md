# Code review: Quill Revise markers (security P1-1 of quill-draft-safety), 2026-11-24

Reviewer: code-reviewer (read-only, not the author), on `89ff751` (now `5220db9` on
`claude/angry-matsumoto-ac520a`). Saved by the author session; resolution is the author's.
Finding fixed: P1-1 of `docs/audit/quill-draft-safety-security-engineer.md` (on
`claude/happy-dubinsky-48c27c`, `fb6a0c4`), assigned to this session by the owner.

**P0: 0. P1: 0.** Scenarios A, B and C of P1-1 closed; Revise guards (cut-off, under-ratio,
read-only, one undo block, selection edges) kept; non-revise paths unchanged; mutants of the
new tests killed. Targeted tests 57 passed.

## P2
1. The leading `[DRAFT]` pattern's `\s*` crossed newlines and took the first line's own
   asterisks: `*Prologue*` became `Prologue*`, `* bullet` lost its bullet.
2. The Scenario B test did not catch truncation (`"y"*400 in` a 600-y run).

## P3
1. Stream cleanup removed spaces, line breaks and `**` around inline markers (fused words).
2. Comment and CHANGELOG claimed "a later Revise never meets a marker"; a successful Continue still
   leaves raw markers, and older drafts may hold them.
3. A preamble before `[DRAFT]` is pasted into the manuscript with no notice.
4. With open security P3-1, a late error from a stopped run reset the next run's stream, so its
   reply was added twice.

## Resolution (author session, 2026-11-24, `823ad5f`)
- P2-1: asterisks count only when balanced around the marker, no newline crossed; tests for
  `*Prologue*`, `**Chapter One**`, `* first bullet`, `*She ran.*`.
- P2-2: the test asserts the exact Draft.
- P3-1: `strip_section_markers` drops a marker line with its line and turns an inline marker into
  one space (nothing at a line edge); test.
- P3-2: wording narrowed ("a marker in the manuscript no longer changes what a Revise keeps").
  Continue's leftover markers are not cleaned (harmless now; not changed).
- P3-3: a revision that still holds a marker adds "[Check] … it is in the Draft as text" to the
  status.
- P3-4: `_on_token`, `_on_finished`, `_on_error` ignore signals from a worker that is no longer
  `host.author_worker` (also closes security P3-1); test fails without the guard.
