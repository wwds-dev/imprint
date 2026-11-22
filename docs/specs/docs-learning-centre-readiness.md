# Spec: documentation and Learning Centre ready for the hand test

Status: DRAFT, awaiting owner approval (Define gate). Priority: P1 (two P0 and fourteen P1 findings in
`docs/audit/docs-learning-centre-readiness-tech-writer.md`, 2026-11-22). Type: documentation, plus
tests that keep it correct. No app behaviour changes. Written 2026-11-22 at `134365a` (v2.407).

## Problem
The owner is about to test the app by hand and wants the documentation and the in-app Learning Centre
to be right. Checked on 2026-11-22 (findings `DL-1` to `DL-37` in the audit):
- The Learning Centre is structurally sound: 26 of 26 lessons listed, 127 help-map targets and 67
  "Show me" links resolve, and 187 of 200 quoted labels match the code with no real mismatch. Tests
  already guard this.
- The README's sections 6, 7, 9 and 13 describe the app of September: seven agents in a left panel
  under retired names (DL-1), a Booth that needs a sibling project at a path on the owner's Mac
  (DL-2), a five-tab Settings dialog (DL-3), three of eight permission boxes (DL-4).
- Names disagree across the three places a tester reads: the contents list says "Quill", the lesson
  is headed "Draft", the sheet "BOOK AUTHOR" (DL-9, DL-18).
- The two newest features are missing from the lessons and the hand-test script: Quill's Draft
  safety (DL-10, DL-12) and Make Release Kit (DL-11, DL-12).
- No document tells a new tester how to add a key and reach a first result (DL-13).
- A hidden chapter of earnings figures is still in the public README source (DL-7); one package
  README describes payout projections the prompt forbids (DL-8).
- Nothing tests the README, the sheets' labels or the names, which is why these drifted while the
  lessons did not.

## Goal and success measure
A tester who reads only the README's first screen and the Learning Centre can install, add a key,
produce a first result with each agent and find every control the docs name. Demonstrated by:
1. **A docs integrity test passes** (`tests/test_docs_integrity.py`, new; checks T1 to T10 below) and
   runs in the normal suite. It must fail on today's tree before the fixes (run once to show it).
2. **Zero open P0 and P1 findings**: every `DL-` item of those severities is fixed, or deferred by
   the owner by name. The audit file gets a closing table (finding, commit, or "deferred: owner").
3. **Label hit rate**: 100% of the phrases on the control list (T4) are found in the code; today's
   baseline is 5 README mismatches and 4 in the Stamp sheet.
4. **A reviewer pass by name**: `code-reviewer` reads the docs diff against the code (read-only);
   `qa-engineer` does a fresh-reader walk on a build with an empty
   `~/Library/Application Support/Imprint/`: the README "Start here", lesson 01, then every recipe's
   Show me steps, and records the result in `docs/audit/docs-learning-centre-readiness-qa-engineer.md`.
5. The existing guards stay green (182 passed, 2 skipped today) and the full suite is green.

## Owner decisions
- **D1 Delete the hidden income chapter** (`README.md:3448-3739`, 292 lines). Recommended: delete;
  git history keeps it. Alternative: move to a private note outside the public repo.
- **D2 Delete the seven legacy Learning pages** (`docs/learn/01` to `07`, 1,279 lines; not shown in
  the app, shipped in the bundle). Recommended: delete before the rename, so 40 old names are never
  rewritten. Needs one line of code removed (`ui/learning_center.py:45-57`), an engineer's task.
- **D3 Screenshots.** They were removed on 2026-11-05. Recommended: none for this test (Show me
  points at the real control); correct the three passages that say otherwise. Alternative:
  regenerate after the rename, about 14 images, and reference them from the lessons.
- **D4 README shape.** Recommended: keep one file; add "Start here" at the top and mark two parts,
  "Using the app" (sections 1 to 13, 20, 21) and "Engineering reference" (14 to 19). Alternative:
  split into `README.md` and `docs/reference.md` (larger; every `§` reference moves).
- **D5 CHANGELOG headings.** Recommended: keep grouping by date (the header explains why), add
  `## Unreleased` and one sentence that this is not semantic versioning. Alternative: version headings
  as the playbook describes, from this release on.
- **D6 Two new lessons**, "Troubleshooting" and "Glossary" (26 becomes 28; the curriculum test pins
  26 and needs an engineer's one-line change). Alternative: sections inside lessons 15 and 00.
- **D7 If the rename is not merged when the hand test starts:** do package 5's name work for the
  seven agents whose labels do not change and leave Chat, Stamp and Muse as they are until it lands.

## Work packages, in order
Sizes are files and changed lines, from the audit's line references. "Docs" is the tech-writer;
"engineer" marks anything that is code or a test.

### Before the rename
**1. Guard tests first** (engineer; closes nothing alone, makes 2 to 7 provable).
New `tests/test_docs_integrity.py`, about 250 lines, plus `tests/docs_controls.txt` (the control
list). Checks T1 to T10 below, each marked expected-fail where a later package fixes it, so the
suite stays green and the mark comes off with the fix.

**2. README: facts that do not involve a changing name** (docs). One file, about 45 passages:
roughly 260 lines changed, 292 deleted (D1), 70 added.
DL-2 Booth requirements and the `/Users/...` path · DL-3 Settings tabs, Docs dialog · DL-4 permission
boxes, five provider subsections · DL-5 labels · DL-6 contents · DL-7 hidden chapter · DL-13 "Start
here" · DL-19 test counts · DL-20 screenshot passage (after D3) · DL-22 section references ·
DL-23 section 1 · DL-32, DL-33 · DL-1 for the seven sections whose agents keep their names
(Quill, Press, Booth, Label, Sitebuilder, Reel, Herald). Depends on: D1, D3, D4.

**3. Learning Centre: content that does not involve a changing name** (docs, with one engineer line).
About 8 files, 330 lines added or changed, 1,279 deleted (D2).
DL-10 Quill lesson (about 40 lines) · DL-11 Press lesson section and `help_map.json` entry (about 50) ·
DL-13 "Add a key" in lesson 13, links from 00, 01, 10 (about 35) · DL-21 Troubleshooting lesson
(about 120) · DL-26 Glossary lesson (about 80) and first-use links · DL-17 delete legacy pages ·
DL-25 `updated_at`. Depends on: D2, D6. Engineer: manifest count in the curriculum test, dead page table.

**4. Sheets, package READMEs and test docs: content that does not involve a changing name** (docs).
About 16 files, 330 lines.
DL-14 "Deliberate limitations" in nine sheets (author, manuscript, audiobook, music, video, social,
webdesign, router, overview; 8 to 15 lines each, rows from the 2026-11-18 audit) · DL-11 Press sheet
(about 30) · DL-8 Label README (10) · DL-16 Herald sheet (after the QH-3 decision) · DL-24 Reel sheet ·
DL-12 two hand-test cases (about 60) and the date · DL-15 banners on the gate and the plan (10) ·
DL-27 app-context (6) · DL-28 CHANGELOG header (after D5) · DL-34, DL-35, DL-37.
This package closes `TODO.md:65` (QB-5) for nine of twelve sheets.

### With the rename (`docs/specs/rename-imprint-studio.md`)
**5. Every passage that carries a name** (docs; one pass, in the rename's branch or straight after
it, never before). About 45 files; 247 "Imprint", 50 "Muse", 41 "Stamp" and about 46 agent-"Chat"
occurrences (table in the audit), of which the CHANGELOG's history (27) and the gate snapshot (15)
stay as written.
- Display name "Imprint" to "Imprint Studio" in prose. Unchanged: `~/Library/Application
  Support/Imprint/`, `data/imprint.db`, the repo name, and whatever the rename spec says about
  `Imprint.app` and `Imprint.spec`. "Muse Glimmer" (Meta's model, 6 places) keeps its name.
- Chat to Kernel, Muse to Nova, Stamp to Vector: README 7.1, 7.2 and 7.11, lessons 19, 27, 28, the
  three sheets and package READMEs, both manifests' titles, the hand-test table at
  `tests/manual_test_cases.md:147-156`, `tests/TEST_PLAN.md:39-40`.
- DL-9 all ten lesson titles and the eight body uses; DL-18 all twelve sheet titles and the four
  Stamp labels; DL-1 the remaining three README sections; DL-14 "Deliberate limitations" for the
  chat, creator and fiverr sheets; DL-25 Chat's manifest section.
- DL-31: the Vector sheet and lesson 27 say in their first paragraph that the output is PNG, not a
  vector file. The prompt's own "vector" promise is audit QM-18 (`TODO.md:79`), a code change.
- One `CHANGELOG.md` entry under the rename's date.
The retired-names check (T5) switches its list to include the three old labels in this package.

### After the rename
**6. Reviewer pass and close** (code-reviewer, qa-engineer, then docs). Success measures 2 to 5;
screenshots if D3 chose them; DL-30 single-home rule written into `docs/agents/overview.md`'s
documentation contract; closing table in the audit; `TODO.md` rows ticked.

### With model-updates (`docs/specs/model-updates.md`)
**7. Reserved places; no text written here.** The feature's Document phase owns:
- `README.md:435-630`, "### Model updates" under section 5 (replace in place; keep the anchor
  `#model-updates`, linked from `10-navigate.md`).
- A lesson: either the section `docs/learn/modules/12-best-fit.md:97` ("## New models"), or a new
  `modules/16-model-updates.md` (id `model-updates`, section `foundations`, order 16, free slot).
- `help_map.json`: the existing key `model_updates_card` (today `best-fit#new-models`) and one key per
  new control.
- `docs/agents/overview.md:99-111`, including the Veo sentence of DL-24.
- One hand-test case in `tests/manual_test_cases.md` Part A.
Packages 2 to 5 leave these passages untouched except for the display name.

### With their code fixes (not this spec's commits)
DL-29: QM-18 (Stamp prompt; `agents/fiverr/README.md:86`, `tests/manual_test_cases.md:804`), QH-4
(`.env.example:76`), QH-5 (Press "connected"), QM-16 (vidforge README). DL-16 if QH-3 is fixed in code.

## Checks that become tests (package 1)
| | Check | Fails today on |
|---|---|---|
| T1 | Every relative link and `#anchor` in `README.md`, `SUPPORT.md`, `agents/**/README.md`, `docs/agents`, `docs/learn`, `tests/*.md` resolves, ignoring HTML comments | DL-6 |
| T2 | Every "§N" or "Section N" in those files names an existing README heading | DL-22 |
| T3 | Every `.md` under `docs/learn/` is in the manifest | DL-17 |
| T4 | Every phrase in `tests/docs_controls.txt` (the controls the docs quote) is a string literal in the app; every bold phrase in a lesson's control atlas is on the list or on its allow-list | DL-5, DL-18 |
| T5 | Retired names do not appear in user docs: "Atelier", "Maestro", "Publisher Agent", "Narrator Agent", "Left-panel button", "Client Gigs", "Site Builder" (extends `tests/test_retired_names.py`) | DL-1, DL-9 |
| T6 | Each lesson's and sheet's first heading starts with its catalog label; both manifests' titles equal the catalog labels | DL-9, DL-18 |
| T7 | No income wording in any tracked doc, comments included: money per month, "passive income", "realistic earnings", "top sellers" (extends the existing lesson-only test) | DL-7, DL-8 |
| T8 | No `/Users/` path in a tracked doc | DL-2 |
| T9 | Every sheet has a "Deliberate limitations" heading | DL-14 |
| T10 | The Settings tabs and permission boxes the README lists equal the ones the dialog builds | DL-3, DL-4 |
Not worth a test: test counts (state the command, not the number), reading level, screenshots.

## Non-goals
Any change to app code, prompts or labels (QM-18, QH-3 to QH-5 stay with their own items). Rewriting
the README from scratch or moving it to a docs site. Translating anything. Back-filling the
CHANGELOG. The model-updates text. `vidforge/README.md`, `cloud/README.md`, `FORK_PLAN.md`. Rewriting
the October readiness gate (it gets a banner). A numeric reading-level target.

## Scope
Docs: `README.md`, `SUPPORT.md`, `CHANGELOG.md` (header and one entry per package), `.env.example`
(one comment), `agents/README.md`, `agents/*/README.md`, `docs/agents/*.md`, `docs/agents/manifest.json`,
`docs/learn/modules/*.md`, `docs/learn/manifest.json`, `docs/learn/help_map.json`,
`tests/manual_test_cases.md`, `tests/TEST_PLAN.md`, `tests/READINESS_GATE.md`,
`docs/foundry/app-context.md`. Tests (engineer): `tests/test_docs_integrity.py`,
`tests/docs_controls.txt`, small edits in `tests/test_learning_center.py`, `tests/test_retired_names.py`;
one deletion in `ui/learning_center.py`.
Phases: Design and Architect skipped (no controls, state or boundaries). Secure not required (no
network, secret, input or file-write change; DL-2 removes a local path from a public file). Comply:
DL-7 removes public income claims and DL-27 touches tier evidence, so `legal-compliance` checks the
diff against the claims list; no sign-off is prepared or recorded by an agent. Launch skipped.

## Risks
- The rename lands late and the test starts first: D7.
- A label check that is too strict gets switched off. T4 uses an explicit list, so a new bold word in
  a lesson needs one line, not a code change.
- Deleting the legacy pages removes the only long troubleshooting text; package 3 writes its
  replacement in the same commit.
- Two sessions edit the README at once (rename, model-updates, this). Packages 2 and 5 are one
  owner session each; package 7's line ranges are reserved above.

## Proposed `TODO.md` rows (for the owner to add; not added by this spec)
- [ ] `P1` `testing` `@ai` **Docs integrity test (`tests/test_docs_integrity.py`): links, section references, orphan lessons, quoted controls, retired names, titles, income wording, local paths, limitation sections, Settings tabs.** Spec `docs/specs/docs-learning-centre-readiness.md` package 1; expected-fail marks come off as packages 2 to 5 land.
- [ ] `P0` `docs` `@ai` **README sections 6, 7, 9 and 13 describe September's app: seven agents in a left panel, a Booth that needs a sibling project at a local path, five Settings tabs, three permission boxes.** Audit DL-1 to DL-6, DL-13, DL-19 to DL-23; spec package 2. Before the rename.
- [ ] `P1` `docs` `@me` **Decide D1 to D7 in `docs/specs/docs-learning-centre-readiness.md`** (delete the hidden income chapter and the legacy Learning pages, screenshots, README shape, CHANGELOG headings, two new lessons, what to do if the rename is late).
- [ ] `P1` `docs` `@ai` **Remove the hidden earnings chapter from the public README (`README.md:3448-3739`) and correct Label's package README on payout projections.** Audit DL-7, DL-8; needs D1.
- [ ] `P1` `docs` `@ai` **Learning Centre: Quill's Draft safety, Make Release Kit with its help-map entry, "Add a key", a Troubleshooting lesson and a Glossary; delete the seven legacy pages.** Audit DL-10, DL-11, DL-13, DL-17, DL-21, DL-26; spec package 3.
- [ ] `P1` `docs` `@ai` **Hand-test script: add cases for Quill's Draft safety and Make Release Kit; banner on the readiness gate and test plan naming the 2026-11-18 audit as the current verdict.** Audit DL-12, DL-15; spec package 4.
- [ ] `P1` `docs` `@ai` **With the rename: one pass over every name (Imprint Studio, Kernel, Nova, Vector), lesson and sheet titles equal to the catalog labels, the Vector sheet says PNG.** Audit DL-9, DL-18, DL-31 and the occurrence table; spec package 5. Do not start before `docs/specs/rename-imprint-studio.md` is built.
- [ ] `P2` `docs` `@ai` **Small doc drift: Veo in the Reel sheet, Chat's place in the sheet manifest, app-context's four stale facts, CHANGELOG `## Unreleased`, SUPPORT's list of work.** Audit DL-24, DL-25, DL-27, DL-28, DL-34; spec package 4.
- [ ] `P2` `docs` `@ai` `agent:social` **Herald's sheet says Pinterest can post; it cannot from the panel.** Audit DL-16, the doc side of QH-3: change the sheet, lesson and catalog line when QH-3 is decided.
- [ ] `P2` `testing` `@ai` **Reviewer pass on the docs: code-reviewer on the diff, qa-engineer fresh-reader walk on an empty Application Support folder.** Spec package 6, after the rename.
- [ ] `P3` `docs` `@ai` **Model-updates docs: replace `README.md:435-630`, `12-best-fit.md` "New models", `overview.md:99-111` and the `model_updates_card` help-map entry in that feature's Document phase.** Spec package 7; reserved, not written here.

The existing row `TODO.md:65` (QB-5, "Deliberate limitations") stays as it is; packages 4 and 5 close it.
