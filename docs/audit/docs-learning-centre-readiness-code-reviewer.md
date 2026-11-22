# Review: documentation and Learning Centre readiness, packages 1 to 4 (code-reviewer)

Date: 2026-11-22. Reviewer: code-reviewer agent, independent of the author; read-only.
Reviewed: branch `claude/practical-jang-8f286e` at `6d67642` against `main` at `cfe17b6`
(`git diff main...claude/practical-jang-8f286e`: 6 commits, 47 files, +1,915/-1,856), read in the
worktree `.claude/worktrees/one-click-release-slice1-599646` (clean before and after).
Spec: `docs/specs/docs-learning-centre-readiness.md`. Audit: `docs/audit/docs-learning-centre-readiness-tech-writer.md`.
Playbook: `docs/playbooks/code-reviewer.md`, `status: current`, `last-reviewed: 2026-10-14`
(39 days, inside the 90-day limit; not stale).

**Verdict: merge after fixes** (R-1, R-2; R-3 and R-4 are cheap and worth doing in the same commit).
Counts: P0 0 · P1 1 · P2 5 · P3 8.

## Method

1. Read the playbook, app-context, spec, audit, and the full diff of every code, test, manifest and
   config file; read the added lines of the README, the new and changed lessons, the nine sheets'
   new sections, the hand-test cases, CHANGELOG, TODO.
2. **Claims against code.** 81 new or rewritten factual claims were sampled (README 29, lessons 37,
   sheets and hand test 15) and each looked up with `grep` in the worktree's Python and config
   (`main.py`, `ui/`, `agents/`, `services/`, `vidforge/`, `config/`, `scripts/`). Result below.
3. **Guard tests.** Read `tests/test_docs_integrity.py` whole. Ran, from the worktree, with
   `PYTHONDONTWRITEBYTECODE=1 ... -p no:cacheprovider -p no:randomly`:
   `tests/test_docs_integrity.py tests/test_learning_center.py tests/test_docs_center.py
   tests/test_env_template.py tests/test_learning_shots.py tests/test_retired_names.py`:
   **442 passed, 2 skipped, 30 xfailed** (17 s). The 2 skips are the pre-existing HeyGen and
   Synthesia env-template skips.
4. **Mutations.** In a throwaway copy outside the repo (scratchpad, `git init` so T7 runs), seven
   mutations were planted at once and the two docs test files re-run: 4 caught, 3 survived (R-3).
5. **Deletions.** `grep` for the seven legacy filenames, `PAGES`, `LearnPage` and every import of
   `ui.learning_center` across code, tests, scripts and `Imprint.spec`.
6. **Rules.** `git diff --stat` on `docs/legal`, `docs/playbooks` and the shared copied files (empty);
   `grep` of the added lines for `/Users/`, handles, and the future names (none).

### Claim check: hit rate

**76 of 81 match the code (94%).** The five mismatches are R-1 (two claims), R-2 and R-4 (two
claims); R-7 is a partial one, counted as a match with a caveat. Confirmed examples: rail widths 216/244
(`ui/forms.py:502-503`); eight permission chips and both row names (`main.py:2687-2718`), greyed
under Local only (`main.py:994-996`); Settings tabs (`ui/dialogs.py:452-777`, and T10); Test /
Save All / one-line refusal / owner-only `.env` (`ui/dialogs.py:342,539,620,1015`,
`services/api_keys.py:233-241`); Save Limits, Reset session spend (`main.py:3398,3402`); F1 and the
rail button (`main.py:411,3420`); all fifteen Booth Convert labels, default 1400, both formats
(`agents/audiobook/panel.py:177-281`); ffmpeg, ffprobe and Calibre messages
(`services/narrator/converter.py:304-336`); Gemini key order (`converter.py:60`); Veo and TTS dates
(`services/media_catalog.py:67`, `converter.py:47`); Quill limits 20,000 / 6,000 / 8,192
(`agents/author/panel.py:54,65`, `services/output_limits.py:20`); every quoted status in the
Troubleshooting lesson except two (R-4); every Release Kit label, file name, count and behaviour
(`agents/manuscript/panel.py:346-378`, `ui/release_kit/confirm_dialog.py:81,228,245`,
`ui/release_kit/window.py:73,101,117-123,295-300`, `services/release_kit/plan.py:43,60,303`,
`agents/manuscript/quote_finder.py:25-32`, `main.py:6468-6469`); Press and Muse have no local
provider (`agents/manuscript/panel.py:235`, `agents/creator/panel.py:175`); router keywords
(`agents/router/agent.py:44-60`); section 9.6 keys, defaults and URL.

### Not verified

- The app was not launched; nothing was checked on screen. "Show me" and F1 behaviour rest on the
  existing tests.
- The full suite was not run (author reports 2,578 passed, 17 skipped, 30 xfailed; only the
  arithmetic 2,578 + 17 + 30 = 2,625 was checked).
- `ruff` is not installed in `.venv`, so the lint ratchet was not run on the two changed `.py` files.
- Claims taken from open `TODO.md` audit rows (QB-2, QH-6, QM-5, QM-6, QM-8, QM-10, QM-13, QM-14) were
  matched to their TODO row, not re-derived from code. "Permission boxes are not saved" and "Test
  bills nothing" rest on the dialog's own text, not a trace.
- Booth's "daily cap ships at EUR 10": `config/registry.json:23` says 10.0 but the seed row in
  `services/database.py:1264` says `None`; which one a fresh install gets was not traced.
- Prices, and the unchanged parts of the README (sections 2 to 5, 8, 10 to 12, 14 to 19).
- Whether lessons 24 and 25 cover the video and posting failures the deleted legacy page listed.

## Findings

### P1

**R-1. The docs now say both that Herald posts to Pinterest and that it cannot (DL-16 still open, and made worse).**
`README.md:135` (new text) "publish to Reddit, YouTube and Pinterest"; `docs/agents/social.md:43`
"| Pinterest | **Can post.**"; the new bullet at `docs/agents/social.md:56` "Pinterest posting does
not work from the panel yet". Code: `agents/social/publishing.py:340-343` sends the file as
`image/png`; `TODO.md:86` (QH-3). A tester who reads the README or the table tries a Pinterest post
and fails; one who reads the bullet finds the sheet contradicting itself. DL-16 is a P1 in the audit
and the spec's success measure 2 needs it fixed or deferred by the owner by name.
Fix: change `social.md:43` to "Connection only; posting does not work yet (QH-3)" and README:135 to
"publish to Reddit and YouTube", or get the owner's named deferral.

### P2

**R-2. `docs/agents/music.md:31` states a limitation that is not true.** "Label and Muse both
authorize as "music"". Both call sites are Label's own (`agents/music/panel.py:211`,
`agents/music/suno_panel.py:208`); Muse authorizes as "creator" (`agents/creator/panel.py:666`).
The wording was copied from `TODO.md:99`, which misnames the panel. Fix: "Label's plan and Suno tabs
both authorize as "music"; two Label runs at once can bill each other's usage".

**R-3. T4 does not guard the README, the sheets or lesson text outside a control atlas, so DL-5 and DL-18 can recur unnoticed.**
`tests/test_docs_integrity.py:265-290`: the first test checks only that each line of
`tests/docs_controls.txt` occurs in the app; the second checks bold phrases only inside a lesson's
"Control atlas" (9 lessons). Nothing ties a quote in the README or a sheet to the list. Mutations
that survived: README "**Save Limits**" to "**Save Budget Limits**" (the exact DL-5 error);
`docs/agents/manuscript.md` "**Export Approved…**" to "**Export Aproved Book…**";
`21-publish.md` "**Start**" to "**Begin Kit**". Caught: a broken lesson anchor (T1), a wrong `§`
(T2), a renamed Settings tab heading (T10), a money-per-month phrase (T7). Also `_in_app`
(`:239-241`) is a substring match over every string literal, docstrings included: "Begin",
"Publish", "Send" all pass, and "too big right now" passes on a docstring (R-4). The file header's
"the test names every doc line that has to follow" is not what the test does.
Fix: add a test that every bold phrase in README sections 3 to 7 and 13 and in each sheet's control
table is on the list or the allow-list; match whole literals (allowing a trailing ellipsis or colon).

**R-4. Two Troubleshooting entries do not start with the text the app shows, though the lesson says each does.**
`docs/learn/modules/17-troubleshooting.md:11-12` promises it; `:81` is headed ""Select a passage"",
but the status starts "[Too long] Revise works on up to 20,000 characters" and the cloud wording is
"Select a chapter or passage" (`agents/author/panel.py:66-74`); a search for "Too long" finds
nothing. `:45` quotes "too big right now", which exists only in a docstring
(`services/providers.py:220`); the app shows "too big now" (`services/local_models.py:44`) and
"<model> needs ~X GB; Y GB free." (`main.py:780`). Same heading at `20-draft.md:98`.
Fix: head the entries "[Too long] Revise works on up to ..." and "too big now" / "needs ~... GB".

**R-5. At least 16 of the 30 strict xfails are not about the rename, though all carry the reason "names change with the rename".**
T6: lessons 20 to 26 and sheets author, manuscript, audiobook, music, video, social, webdesign,
router (15) belong to agents whose label does not change; T5 `26-site-builder.md` likewise; T9's
three are missing sections, not names. None hides a failure outside what spec package 5 defers
(each was read), so they are justified by the spec, but for the hand test it means: the contents
list says "Quill" and the page is headed "Draft" (lesson) or "BOOK AUTHOR" (sheet). Spec D7 covers
exactly this case. Fix: owner decides D7 now; give the non-rename cases their own xfail reason.

**R-6. Audit findings assigned to packages 1 to 4 that are not closed.**
DL-16 (R-1). DL-26: sheets' developer sections were not moved under one "For developers" heading
(`grep "For developers" docs/agents/*.md`: none). DL-27: app-context still says "it has no
`LICENSE`" (left for the owner, stated in TODO) and "Last recorded (2026-10-19 ...): 1820 passed"
beside the new pointer to README 16.1. DL-25: Chat's manifest section (moved to package 5 by the
author; the spec lists it in both). Deferred by the spec, not defects: DL-9, DL-18, DL-14 for three
sheets, README 7.1, 7.2, 7.11 (`README.md:1008`, `:1082` still say "Left-panel button").
Fix: close DL-26 and the app-context line, or record each in the audit's closing table as deferred.

### P3

**R-7.** "A revision ... under half the length of its text leaves the Draft unchanged"
(`README.md:1329`, `20-draft.md:38`, hand-test case): for Tighten Structure the threshold is a
quarter (`agents/author/panel.py:60`). Fix: "under half (a quarter for Tighten Structure)".

**R-8.** T8 is narrower than the spec's "a tracked doc": it skips `TODO.md`, where `:102` carries a
`/Users/...` path, as do `config/tools.json:5-6` and two older audits. All pre-existing on `main`;
this branch adds none. The same hard-coded folder is Booth's default input on a tester's Mac
(TODO:102). Fix: widen T8 with an allow-list, or note the exclusion in its docstring.

**R-9.** `tests/docs_controls.txt` holds non-controls: 36 of 357 lines match only as substrings,
among them "Centre", "Dev", "Tab", "Text", "Time", "Stack", "Input", "Cost". The `[not controls]`
list has one entry. Fix: prune; they make the list look more checked than it is.

**R-10.** `ui/learning_center.py`: the deletion is safe. The legacy `show_learning_center`
(`:80-349`) and `LearnPage` (`:34`) are shadowed by the re-export at `:355-360`, and `PAGES` now
exists only through that import; `main.py:409,6431`, `ui/docs_center.py:516` and the tests import
the v2 names. But about 270 lines of dead dialog code remain. Fix: delete in a follow-up.
`Imprint.spec:82` still comments "pages + their screenshots".

**R-11.** Smaller test gaps: T2 misses the plural ("sections 11 and 12"); T1 accepts either of two
anchor algorithms for any file, so a README anchor valid only under the Learning Centre's rule
passes; T9 passes on an empty section; T7 reads `.md` only.

**R-12.** The deleted legacy troubleshooting page had entries the new lesson lacks: video stuck or
Stop ineffective, social cannot post, audiobook finds no books, what to put in a bug report. The
page was never shown in the app, so nothing visible is lost. Fix: add one line each pointing to
lessons 22, 24, 25.

**R-13.** `SUGGESTIONS.md:55` still names `docs/learn/02-agents.md` (a historical row). No action
unless the row is edited.

**R-14.** Existing tests: only `tests/test_learning_center.py:191` changed (26 to 28, with the
reason, spec D6). No test skipped, removed or loosened. `updated_at` was dropped from both
manifests; both loaders default it to "" and hide the "Updated" label
(`ui/learning_center_v2.py:94,682`, `ui/docs_center.py:79,456`). Recorded as checked, no fix.

## Rules checked (all pass unless a finding says otherwise)

No income or results wording added (T7 green; `agents/music/README.md` item 5 now matches the
prompt). No `/Users/` path, handle or future name ("Imprint Studio", Kernel, Nova, Vector) in any
added line. `docs/legal`, `docs/playbooks`, `services/benchmarks.py`, the narrator converter,
`app_launcher.c` and `appkit_guard.py` untouched. `.env.example`: one comment line, no value.
`TODO.md` rows keep the format. CHANGELOG has `## Unreleased` with the entry. Both manifests and
`help_map.json` parse and pass their tests; `release_kit_btn` resolves to
`publish#make-a-release-kit`. Manifest title "Router" became "Intent Router" to equal the catalog
label (`agents/catalog.py:89`).
