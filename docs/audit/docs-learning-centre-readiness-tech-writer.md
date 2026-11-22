# Audit: documentation and Learning Centre readiness (tech-writer)

Date: 2026-11-22. Commit: `134365a` (`main`, v2.407). Author: tech-writer agent. Read-only: no
existing doc, code or test was changed. Fix plan: `docs/specs/docs-learning-centre-readiness.md`.
Playbook: `docs/playbooks/tech-writer.md`, `status: current`, `last-reviewed: 2026-10-14` (39 days,
inside the 90-day limit).

Severity: **P0** would mislead a tester or blocks testing; **P1** wrong or missing; **P2** unclear
or stale; **P3** polish.

## Summary by area

| Area | Files, lines | P0 | P1 | P2 | P3 | State in one line |
|---|---|---|---|---|---|---|
| `README.md` | 1 file, 3,740 | 2 | 5 | 5 | 3 | Sections 5, 12, 18, 19, 20 are current; sections 6, 7, 9 and 13 describe the app of September 2026 |
| Learning Centre (`docs/learn/modules`, manifests, `help_map.json`) | 26 lessons, 3,753 | 0 | 4 | 3 | 1 | Structurally sound and well guarded by tests; names, two new features and key entry are missing |
| Legacy Learning pages (`docs/learn/01` to `07`) | 7 files, 1,279 | 0 | 0 | 1 | 0 | Not shown in the app, still shipped in the bundle |
| Agent sheets (`docs/agents`) | 12 sheets, 1,181 | 0 | 2 | 3 | 0 | Accurate on prices and files; no "Deliberate limitations", a third set of names |
| Agent READMEs (`agents/*/README.md`, `agents/README.md`) | 12 files, 1,399 | 0 | 1 | 1 | 0 | Mostly current (9 of 11 touched in November); one income statement contradicts the prompt |
| Test docs (`tests/*.md`) | 3 files, 1,758 | 0 | 2 | 0 | 1 | UAT script lacks the two newest features; gate and plan are October snapshots |
| `CHANGELOG.md` header, `SUPPORT.md`, `.env.example`, app-context | 4 files | 0 | 0 | 2 | 1 | Sound; small drift |
| **Total: 37 findings** | | **2** | **14** | **15** | **6** | |

A finding that spans areas is counted once, under the area where the fix is largest.

## Method

All commands were run from the repo root on 2026-11-22; scripts were throwaway and are not in the repo.

1. **Manifests against files.** `docs/learn/manifest.json` (26 entries) and `docs/agents/manifest.json`
   (12 entries) compared with the `.md` files on disk, both directions; prerequisites checked against ids.
2. **Links and anchors.** Every Markdown link in the 60 in-scope files outside code fences: relative
   file exists; `#anchor` resolves against the target's headings (the app's own `_document_sections`
   and `_anchor` from `ui/learning_center_v2.py`, plus GitHub-style slugs). 233 links checked.
   `show:` links (67) were left to the existing test, which resolves them against the built window.
3. **Agent coverage.** For each of the 11 entries in `agents/catalog.py`: sheet, package README,
   `TODO.md`, `SUGGESTIONS.md`, a lesson whose manifest `agent` is that key, count of `Step N` headings
   and `show:` links in it.
4. **Quoted labels against code.** Every bold phrase of up to five words (`**Label**`) in the docs was
   looked up in the set of all string literals in the app's Python (parsed with `ast`; tests, `.venv`,
   `cloud/` excluded) and in `config/*.json`. Exact match, substring match, or miss; every miss was
   read by hand and sorted into "not a label" (emphasis, a template such as `Keep <model>`) or
   "mismatch". Hit rates are in the table below. The method cannot see a label that exists in code but
   on a different screen from the one the doc describes.
5. **Behaviour claims.** Sampled by `grep` and by reading code: Settings tabs, permission chips,
   budget buttons, Docs and Learning Centre wiring, chunk default, length limit, Run Log size, window
   minimum, rail widths, 12 token prices against `config/pricing.json`, the Veo shutdown date, version.
6. **Counts.** `pytest --collect-only -q` (2,337 tests); `VERSION` and `git rev-list --count HEAD` (2, 407).
7. **Known findings.** `TODO.md` lines 59 to 86 ("Audit Q…") and `tests/READINESS_GATE.md` read first;
   where a finding here is the doc side of one of those, it says so.
8. **Income and results claims.** `grep` for money ranges, "per month", "passive", "guarantee",
   "realistic", "top sellers", "5-star" across every in-scope file, including HTML comments.
9. **Existing guard tests run.** `tests/test_learning_center.py`, `test_docs_center.py`,
   `test_env_template.py`, `test_learning_shots.py`: 182 passed, 2 skipped (16 s).

### Label check: hit rate

| Docs | Distinct bold phrases | Exact | Substring | Miss | Real mismatches among the misses |
|---|---|---|---|---|---|
| Learning Centre lessons | 200 | 173 | 14 | 13 | 0 (templates and section names) |
| Agent sheets | 108 | 69 | 15 | 24 | 0 as bold; 4 plain-text labels wrong (DL-18) |
| Agent READMEs | 59 | 51 | 3 | 5 | 0 |
| `README.md` | 428 | 255 | 49 | 124 | 5 labels (DL-5); about 60 misses sit in the hidden legacy chapter (DL-7) |
| `tests/manual_test_cases.md` | 76 | 55 | 4 | 17 | 0 (case titles) |

### Structure check: result

| Check | Result |
|---|---|
| Every Learning manifest entry has a file | 26 of 26 |
| Every lesson file under `modules/` has an entry | 26 of 26 |
| Every `.md` under `docs/learn/` has an entry | 26 of 33: the seven legacy pages do not (DL-17) |
| Sheet manifest against `docs/agents/*.md` | 12 of 12, both directions |
| `help_map.json` targets (127) resolve to a lesson and anchor | pass (existing test, run today) |
| `help_map.json` keys and `show:` paths name real controls | pass (existing test, run today) |
| Links and anchors | 232 of 233 resolve; 1 hard failure plus 4 that resolve only to headings inside an HTML comment (DL-6) |
| Visible agent has sheet, README and recipe | 10 of 10; `router` has sheet and README, no lesson (DL-35) |
| Images referenced / present | 0 referenced, folder `docs/learn/img/` does not exist (DL-20) |

### Not verified

- Nothing was checked on screen: the app was not launched by hand, so layout, wording in dialogs that
  is built at run time, and the recipes' "Show me" behaviour rest on the existing tests.
- No paid or network call was made; provider prices were compared with `config/pricing.json`, not with
  the providers' current price pages.
- Agent behaviour claims in the lessons were sampled (Quill, Press, Booth, Reel, Herald), not read
  line by line against every panel. The 2026-11-18 code audit is the deeper source for behaviour.
- Reading level was judged by reading, not measured with a tool.
- `CHANGELOG.md` entries below the header, `vidforge/README.md`, `cloud/README.md`, `FORK_PLAN.md`,
  `docs/readme.md`, `docs/audiobooks-iphone-manual.md` and the agents' `TODO.md` files were out of scope.
- Rail widths (DL-32): not verified whether the README's figures include margins.

## Findings

### P0

**DL-1. README sections 6 and 7 name agents and navigation that no longer exist.**
`README.md:914` says "7 first-party GUI agents" in a "left-panel navigator" with "three collapsible
categories — General, Creative, Gigs"; `:918`, `:992`, `:1119`, `:1389`, `:1505`, `:1613`, `:1778` each
start "**Left-panel button:**"; headings `:990` "Atelier Agent", `:1117` "Manuscript Agent" (it is
Quill), `:1387` "Maestro Agent", `:1503` "Site Builder Agent", `:1611` "Narrator Agent", `:1776`
"Publisher Agent"; `:764-770` lists seven panels by those names; table of contents `:31-41` repeats
them. Code: ten agents in eight header tabs, labels Quill, Press, Booth, Label, Reel, Herald,
Sitebuilder, Stamp, Muse, Chat (`agents/catalog.py:28-93`); `README.md:258` itself says "Agent
navigation lives in the header". Partly known: `TODO.md:86` ("README's old agent names").
Fix: head each section with the catalog label and workspace, delete the "Left-panel button" lines,
state ten agents in eight workspaces.

**DL-2. README tells the reader Booth needs a sibling project at a path on the owner's Mac, and that it narrates with OpenAI only.**
`README.md:1695`: "The **`narrator/` sibling project** must be installed … See
`/Users/as/Documents/lab/active/narrator/`"; `:1694` lists an OpenAI key as the requirement; `:1615`
"using OpenAI's Text-to-Speech API"; `:914` "Narrator … only ever calls OpenAI TTS (§5.6)"; `:2247`
OpenAI is "the only provider for Audiobook TTS". Code: the converter is in the app
(`services/narrator/converter.py`), with three routes (`README.md:1625` in the same section,
`.env.example:42-47`). The path also publishes a local user folder in a public repo, against the
workspace rule on `/Users/...` paths. Partly known: `TODO.md:86` ("OpenAI-only Booth text"),
`TODO.md:153` (fixed in four other places on 2026-10-09).
Fix: replace the requirements list with ffmpeg, one of three narrator keys and, for MOBI/AZW3, Calibre; delete the path.

### P1

**DL-3. README describes a Settings dialog with five tabs and a Docs button that opens the README.**
`README.md:2519`: "five tabs: General, Agents, Tools, Pricing and Projects". Code: eight
(`ui/dialogs.py:452`, `:662` API keys, `:686` Local models, `:701` Models, `:740`, `:777`, `:946`,
`:967`). `README.md:2594`: Docs "Renders this file (`README.md`)"; code opens the reference centre from
`docs/agents/manifest.json` (`main.py:6417-6421`, `:6451-6455`). `README.md:810` repeats it.
Fix: list the eight tabs with one line each; describe the Docs centre and its two entry points.

**DL-4. README lists three provider permission boxes and five providers; the app has eight and ten.**
`README.md:846-850` (OpenAI, DeepSeek, Gemini); code: OpenAI, DeepSeek, Kimi, Gemini, Anthropic, Qwen,
Higgsfield, ElevenLabs (`main.py:2687-2713`). `README.md:4`, `:82` and section 9 (`:2204-2282`) cover
Ollama, Anthropic, OpenAI, DeepSeek and Gemini only; LM Studio, Kimi, Qwen, Higgsfield and ElevenLabs
have no section, though `README.md:796` names them in the Provider menu.
Fix: complete the permission list; add the five missing provider subsections, or one table that points to the Model Guide.

**DL-5. Five button labels in the README are not the labels in the app.**
`README.md:2479` "Save Budget Limits": `main.py:3398` "Save Limits". `:2481` "Reset Session Spend":
`main.py:3402` "Reset session spend". `README.md:1224` "Clear All": `agents/author/panel.py:449`
"Clear". `:1223` "Format + Export Book": `agents/author/panel.py:445` "Export Book" beside a separate
format menu. `:1220` "Scenes / Chapters": no such literal found. Fix: quote the code's labels.

**DL-6. The README table of contents links to a chapter that is hidden.**
`README.md:68-72` link to "21. Earning Income with Imprint" and its four subsections; the only headings
with those names are inside the HTML comment at `:3448-3739`. `#21-earning-income-with-imprint` matches
nothing; the other four match only commented text, so they are dead when rendered. The visible
"21. Income experiments with Imprint" (`:3421`) and "Housekeeping" (`:3439`) are not in the contents.
Fix: point the entry at `#21-income-experiments-with-imprint` and drop the four sub-entries.

**DL-7. Income and results claims: a hidden chapter of earnings figures is still in the public README source.**
`README.md:3448-3739` is commented out, so it does not render, but the repo is public and the raw file
shows it. It states earnings as fact: `:3493-3495` ("Month 3 … **$375–$1,350**", "Top sellers:
$3k–$10k/month"), `:3528-3530`, `:3573-3576`, `:3585` ("assets that generate passive income"),
`:3620-3623`, `:3650-3652`, `:3715-3727` ("Realistic Earnings Expectations" table) and `:3729`
("most successful Imprint users **stack 2–4 income paths**"; the app has no user data to show this).
The comment at `:3449-3453` says the text was kept "temporarily". It contradicts `README.md:3423`,
`SUPPORT.md:22` and the app-context invariant on income claims.
Fix: delete lines 3448 to 3739; git history keeps them. Needs the owner's yes (spec D1).
Other income wording found and judged sound: `README.md:3421-3437`, `docs/learn/modules/30` to `36`,
`docs/agents/music.md:56`, `:74`, `SUPPORT.md:22`, `CHANGELOG.md:21-23`. See also DL-8 and DL-31.

**DL-8. Label's package README says the Income Roadmap projects streaming payouts; the prompt forbids it.**
`agents/music/README.md:44-45`: "streaming payout math at $0.003–$0.005/stream projected at
1k/10k/100k streams … a Month 1/3/6 priority list". Code: `agents/music/agent.py:71` "Do not forecast
earnings or quote a universal per-stream payout"; `README.md:1403` describes user-supplied, labelled
scenarios. Fix: rewrite item 5 from the current prompt.

**DL-9. Eight agent lessons carry a title that differs from the one in the Learning Centre's contents list.**
First line of `docs/learn/modules/20-draft.md` "# Draft", `21` "# Publish", `22` "# Audiobooks",
`23` "# Music", `24` "# Video", `25` "# Social", `26` "# Site Builder", `27` "# Client Gigs";
`manifest.json` titles: Quill, Press, Booth, Label, Reel, Herald, Sitebuilder, Stamp. Body text uses the
old names as agent names: `01-first-result.md:9`, `:65-66` ("appears in Draft", "Draft Agent Academy
lesson"), `14-costs-limits.md:46` ("in Draft … in the Assistant"), `:52` ("Client Gigs logo batch"),
`02-choose-path.md` and `26-site-builder.md` ("Site Builder", "Client Gigs"; 8 occurrences in all).
A tester who clicks "Quill" reads a page headed "Draft".
Fix: make each H1 the catalog label and replace the eight body uses. Three of the ten change again in the rename: do it once, with the rename.

**DL-10. The Quill lesson does not teach what Write and Revise do since 2026-11-20.**
`docs/learn/modules/20-draft.md` (last changed 2026-11-08) has no mention of: Write adds after the
existing Draft; outline, character and world replies go only to their tabs; Revise replaces the
selection or the whole Draft as one undoable edit; the 20,000-character limit (6,000 with a local
model). `:216` advises "tighten World Notes and the Direction, then write again", which now adds a
second version under the first. Source of truth: `docs/agents/author.md:33`,
`agents/author/README.md:91-112`, `docs/specs/quill-draft-safety.md`.
Fix: add a "What Write changes" table to the control atlas and correct step 7.

**DL-11. Make Release Kit (shipped 2026-11-21) is in neither the Press sheet, the Press lesson nor the help map.**
Button: `agents/manuscript/panel.py:375` "Make Release Kit…". Documented only in `README.md:1815-1825`
and `agents/manuscript/README.md`. `docs/agents/manuscript.md` was last changed 2026-09-30;
`docs/learn/modules/21-publish.md` and `docs/learn/help_map.json` have no entry, so F1 on the button
opens no lesson section. Fix: add a sheet section, a lesson section with an anchor, and a `release_kit_btn` help-map entry.

**DL-12. The hand-test script has no case for the two newest user-visible features, and its date is wrong.**
`tests/manual_test_cases.md`: no hit for "Release Kit", "Draft safety", "20,000" or "never clears".
`:9` says "Last revised: 2026-10-05"; git shows 2026-10-19. The owner is about to test from this file.
Fix: add a Quill case (Write keeps the Draft; Revise limit) and a Press case (Release Kit, free path); correct the date.

**DL-13. Neither the README nor the Learning Centre gives a new tester the first-run path.**
README: section 1 (`:76-94`) is fork history; installing is section 18 (`:3032`), keys section 19
(`:3201`), and "First-Run" (`:3004`) is about database migration. Learning Centre:
`01-first-result.md:9` assumes "at least one eligible provider/model appears"; `10-navigate.md:36` and
`13-access-privacy.md:25` say the API keys card "is not a place to paste secrets", and no lesson step
says where to paste one. **Settings → API keys** (paste, Test, Save All; `ui/dialogs.py:479-662`,
`README.md:3205`) appears in the lessons only as the home of the Qwen workspace ID
(`13-access-privacy.md:50`); `:51-53` sends the reader to a terminal script instead.
Fix: a "Start here" block at the top of the README (install, open, add one key or use Ollama, first result, where files are), and a "Add a key" walkthrough in lesson 13 linked from lessons 00, 01 and 10.

**DL-14. No agent sheet has the promised "Deliberate limitations" section (known: audit QB-5).**
`docs/agents/overview.md:48-49` promises it; `grep -i "deliberate limit" docs/agents/*.md` finds no
heading in any of the twelve. Open as `TODO.md:65` and `tests/READINESS_GATE.md:79-80`.
Fix: as `TODO.md:65`; rows from the 2026-11-18 audit's Narrower and Stub findings.

**DL-15. The readiness gate and the test plan still give the October verdicts.**
`tests/READINESS_GATE.md:3` "audit, 2026-10-09 at `e23f3cd`"; `:25`, `:27`, `:29` mark Quill, Booth and
Reel "✅ ready"; the 2026-11-18 audit left P0 items open on Booth, Herald and Reel (`TODO.md:61`, `:62`,
`:67`). `:29` says Veo "retire[s] 2026-10-22 — inside any realistic test window" (past).
`tests/TEST_PLAN.md:3` has the same baseline.
Fix: a dated banner at the top of both files that names `docs/audit/code-readiness-audit-2026-11-18.md` as the current verdict; do not rewrite the snapshot.

**DL-16. The Herald sheet says Pinterest can post; the panel cannot (doc side of audit QH-3).**
`docs/agents/social.md:43` "| Pinterest | **Can post.** …"; `TODO.md:69`: no image picker, and the clip
is sent as `image/png` (`agents/social/publishing.py:340-343`). The catalog line
(`agents/catalog.py:60`) and `SUPPORT.md:30` repeat the promise.
Fix: when QH-3 is decided, either fix the code or say "Pinterest: connection only, posting not working" in the sheet, lesson and catalog line.

### P2

**DL-17. Seven legacy Learning pages are shipped but never shown.**
`docs/learn/01-getting-started.md` to `07-troubleshooting.md` (1,279 lines) are not in
`docs/learn/manifest.json`; the app loads the manifest only (`ui/learning_center_v2.py:74-98`,
`:177`). They still travel in the bundle (`Imprint.spec` copies `docs/learn` whole) and are listed in a
dead table at `ui/learning_center.py:45-57`. `test_no_orphan_pages_on_disk` looks only inside
`modules/` (`tests/test_learning_center.py:51-56`). They hold 30 "Imprint", 7 "Muse", 3 "Stamp".
Fix: delete the seven files before the rename (spec D2); the dead table is an engineer's one-line removal.

**DL-18. Agent sheets use a third set of names, and the Stamp sheet's control names differ from the panel.**
H1 of `docs/agents/author.md` "BOOK AUTHOR", `manuscript.md` "PUBLISHING MANAGER", `audiobook.md`
"AUDIOBOOK PRODUCER", `music.md` "MUSIC ARTIST GENERATOR", `video.md` "VIDEO & AD GENERATOR",
`social.md` "SOCIAL MEDIA CAMPAIGN MANAGER", `webdesign.md` "WEB DEVELOPER", `fiverr.md` "BRAND & LOGO
DESIGNER", `chat.md` "STUDIO ASSISTANT"; the Docs contents list shows Quill, Press, and so on.
`docs/agents/fiverr.md:12-17`: "Business Name", "Primary Colors", "# Concepts", "Delivery Msg"; panel:
"Business name", "Primary colours", "Concepts", "Delivery Message" (`agents/fiverr/panel.py:109-116`,
`:184`). This breaks the sheet's own contract (`overview.md:169-170`: "named exactly as they appear").
Fix: H1 = catalog label plus the descriptive subtitle; correct the four labels. With the rename.

**DL-19. Test counts and run times are stale in four places.**
`README.md:2832` "~1,000 tests"; `:2882-2885` "1,605 tests are collected (2026-10-14)";
`tests/TEST_PLAN.md:198`, `:530` "the ~90 s run"; `docs/foundry/app-context.md:36`, `:68-69` "1826".
Today: 2,337 collected (`pytest --collect-only -q`); last recorded full run 2,191 passed, 17 skipped in
24 min 35 s (`docs/specs/quill-draft-safety.md:110`). CLAUDE.md's "about 90 s" is known (`TODO.md:86`).
Fix: state the command and the last dated measurement once (README section 16.1) and point the other places at it.

**DL-20. The Learning Centre has no screenshots, and three passages say it has.**
`docs/learn/img/` was deleted on 2026-11-05 (`62c9ec4`, "Remove app GUI screenshots"); no lesson or
sheet references an image. Still stated: `README.md:3394-3412` ("Screenshots are generated … commit
what moves"), `docs/agents/overview.md:9` ("step-by-step teaching, screenshots"), `TODO.md:186-187`
(regenerate them). `test_screenshot_generator_covers_the_referenced_images` now passes on an empty set.
Fix: owner decides (spec D3) between no screenshots and regenerating after the rename; then align the three passages.

**DL-21. Common failures a first tester will meet have no troubleshooting entry.**
The v2 curriculum has no troubleshooting lesson (the old one is orphaned, DL-17). Each lesson has
"Common failures", and `15-files-recovery.md` covers the launcher. Not covered anywhere in
`docs/learn/modules/`: a rejected key (no hit for "401" or "rejected" in that sense), Ollama not
running (no hit), ffmpeg missing for Booth (`ffmpeg` appears only in `24-video.md`), a provider box left
unticked, a budget refusal ("Not sent: …").
Fix: one "Troubleshooting" lesson in Foundations, symptom to cause to fix, searchable by the exact status text.

**DL-22. Seven section references point at the wrong section.**
`README.md:808` "Section 12.4" (Model Guide is 13.4), `:810` "Section 12.5" (13.5), `:914` "§5.6",
`:920` "Section 4" (the chat panel is section 6), `:1936` "§5.3", `:2188` "Section 12.3" (13.3);
`docs/agents/music.md:37` "README §18" (section 18 is Installing). No test resolves "§" references.
Fix: correct the seven; turn them into links so the link test covers them.

**DL-23. README section 1 misstates where data lives and what the app is.**
`README.md:95`: "no server, no web interface … All data is stored in … `data/imprint.db`". The
packaged app writes to `~/Library/Application Support/Imprint/` (`services/runtime_paths.py:100-107`;
correct at `README.md:3015` and in lesson 15); the repo also holds a hosted web companion (`cloud/`).
`:78-82` opens with fork history instead of what the app does.
Fix: rewrite section 1 as "what it is, who it is for, what it never does", with both data locations.

**DL-24. Veo is described as still offered.**
`docs/agents/video.md:44` "Veo 4/6/8s (until 22 October 2026)"; `docs/agents/overview.md:107-109`
"shutdown dates such as Veo 3.1's earliest shutdown on 22 October 2026". The date passed a month ago
and the code removes Veo from menus from that day (`services/media_catalog.py:67`, `:80-83`). The Reel
lesson is already right (`24-video.md:17-19`).
Fix: past tense in the sheet; the overview sentence belongs to the model-updates feature (spec, "With model-updates").

**DL-25. The sheet manifest files Chat under "Advanced: compatibility and command-line capabilities".**
`docs/agents/manifest.json:22`: summary "General chat compatibility capability", section `advanced`.
Chat is a visible workspace (`agents/catalog.py:82-87`). Also: `updated_at` in
`docs/learn/manifest.json` differs from the file's last commit date for 25 of 26 lessons (for example
`21-publish.md`: manifest 2026-09-15, git 2026-11-05), and the sheet manifest says 2026-10-07 while
sheets changed up to 2026-11-20.
Fix: move Chat to a user section with a plain summary; either derive `updated_at` in a test or remove the field.

**DL-26. Lessons and sheets use terms they never define, and sheets mix user and developer content.**
Undefined on first use: "eligible route" (`01-first-result.md:9`), "preflight" and "reserve"
(`14-costs-limits.md:17`), "setup target" (`12-best-fit.md`), "evidence passport" (`manifest.json`,
lesson 30), "denominator" and "contribution" (`00-home.md:41`), "frozen app" and "live launcher"
(`15-files-recovery.md:14`). There is no glossary. Every sheet has "Under the hood — files &
functions" and "Extend it" (`docs/agents/fiverr.md:38-51`) in a dialog a user opens from the header.
`README.md:110-119` explains a past `QSplitter` decision in the layout chapter.
Fix: a one-page glossary lesson; first use of each term links to it; move developer sections of the sheets under one "For developers" heading at the end.

**DL-27. `docs/foundry/app-context.md` carries four stale facts.**
`:45` README "3,435 lines" (3,740); `:47` `main.py` "about 4,400 lines" (known, `TODO.md:86`); `:36`,
`:68` "1826" tests (2,337); `:16` "it has no `LICENSE`" (MIT `LICENSE` added 2026-11-21,
`CHANGELOG.md:28`). Fix: correct the four; the tier evidence line needs the owner's eye because it is tier evidence.

**DL-28. The CHANGELOG header departs from the playbook in three ways, two of them unexplained.**
Playbook (`docs/playbooks/tech-writer.md:16`): an `## Unreleased` section first, `## v2.340 - date`
headings, and a statement that the project does not use semver. `CHANGELOG.md:14-20` explains why
entries are grouped by date with no build number (a reasoned deviation). There is no `## Unreleased`
section, and the header does not say "not semver" (`README.md:3103` does). `:10` says the build number
is "never typed by hand", correct.
Fix: add `## Unreleased` and one "not semantic versioning" sentence; keep date grouping unless the owner decides otherwise (spec D5).

**DL-29. Doc statements that depend on open code findings (reference, not rediscovery).**
QM-18 (`TODO.md:79`): `agents/fiverr/README.md:86` describes the prompt as "a 5-star Fiverr
freelancer"; `tests/manual_test_cases.md:804` checks that the prompt appends "vector logo".
QH-4 (`TODO.md:70`): `.env.example:76` says "the `client_secret*.json`"; the uploader needs
`client_secret.json`. QH-5 (`TODO.md:68`): Press "connected" wording. QM-16 (`TODO.md:84`): vidforge
README. Fix: each doc line changes in the same commit as its code fix; listed in the spec so none is forgotten.

**DL-30. The same facts are written in four places and already disagree.**
Booth narrator prices and dates: `README.md:1625`, `:1703`, `docs/agents/audiobook.md`, lesson 22,
`.env.example:42-47`, and (wrongly, DL-2) `README.md:1694`. Model updates: `README.md:435-630`,
`docs/agents/overview.md:99-111`, `12-best-fit.md:97`, `10-navigate.md:36-40`. Settings tabs:
`README.md:2519` (wrong), `tests/manual_test_cases.md:312-324` (right).
Fix: one home per fact (prices: Model Guide and sheet; operating steps: lesson; README links to both), stated in the sheet's documentation contract.

**DL-31. `agents/fiverr/README.md:86` and `README.md:1088-1094` on vector files.**
The README and the sheet (`docs/agents/fiverr.md:75`) correctly say the output is a raster PNG. The
prompt still promises otherwise (QM-18). No doc fix now; the rename spec requires the Vector sheet to
say "PNG" in its first paragraph, because the new name invites the opposite reading.
Fix: with the rename, first paragraph of the sheet and lesson 27: "Vector makes PNG images, not vector files".

### P3

**DL-32. Rail widths.** `README.md:106`, `:108` say 236 px and 268 px; `ui/forms.py:502-503`:
`RAIL_LEFT_WIDTH = 216`, `RAIL_RIGHT_WIDTH = 244`. Not verified whether margins make up the
difference. Fix: quote the constants or drop the numbers.

**DL-33. Version examples are 295 builds old.** `README.md:3087` "`v2.112` at the time of writing";
`CHANGELOG.md:8` "for example `v2.248`"; `:478-479` "As of the 2026-10-13 build (248 commits)". Today
v2.407. Fix: say "for example" without "at the time of writing"; drop the commit tally.

**DL-34. `SUPPORT.md:3` lists five kinds of work and omits brand design and web pages.** Fix: name
all eight workspaces or say "writing, publishing, audio, video, social, brand and web work".
Also `.env.example` does not mention that `GEMINI_API_KEY` is accepted in place of `GOOGLE_API_KEY`
(`README.md:3242`). Fix: one comment line.

**DL-35. Coverage notes.** `router` has a sheet and a README and no lesson; that is right (it has no
panel) but written nowhere. `26-site-builder.md` has nine `Step` headings and eight Show me links.
Fix: one sentence in `docs/agents/router.md`; add the ninth link or say why the step has none.

**DL-36. Label case.** Covered in DL-5 ("Reset Session Spend"); `README.md:207` "Tooltips: On/Off" is
two states of one button (`main.py:464`), fine. No fix beyond DL-5.

**DL-37. `tests/manual_test_cases.md:964`** keeps "944 tests, 90s" as a dated observation
(2026-10-05); correct as history, confusing beside DL-19. Fix: add "(then)" or the current figure.

## Rename: occurrences of the old names (for sizing)

Counted with word-boundary regular expressions on 2026-11-22. "Imprint" excludes "Imprint Studio",
`Imprint.app`, `Imprint.spec` and `Imprint/` in paths. "Muse" excludes "Muse Glimmer" (Meta's local
model, which keeps its name: 2 in README, 1 in CHANGELOG, 2 in the legacy pages, 1 in the gate).
"Chat" is every capitalised use; the last column is how many of those are control or tool names that
do not change ("New Chat", "Remove Chat", "General Chat", "Chat routing", "Chat agent" class names).

| Area | Imprint | Muse | Stamp | Chat | of which not the agent |
|---|---|---|---|---|---|
| `README.md` | 58 | 5 | 7 | 36 | 22 |
| `CHANGELOG.md` (history: leave as written) | 10 | 5 | 7 | 5 | 0 |
| `agents/README.md` | 7 | 0 | 0 | 0 | 0 |
| `agents/*/README.md` | 16 | 6 | 2 | 6 | 1 |
| `docs/agents/*.md` | 25 | 3 | 4 | 4 | up to 4 |
| `docs/agents/manifest.json` | 1 | 1 | 1 | 1 | 0 |
| `docs/learn/modules/*.md` | 81 | 7 | 1 | 10 | 4 |
| `docs/learn/manifest.json`, `help_map.json` | 1 | 1 | 1 | 1 | 0 |
| `docs/learn/01` to `07` (legacy; delete first, DL-17) | 30 | 7 | 3 | 0 | 0 |
| `tests/manual_test_cases.md` | 9 | 7 | 7 | 7 | 0 |
| `tests/TEST_PLAN.md` | 4 | 4 | 4 | 1 | 0 |
| `tests/READINESS_GATE.md` (snapshot: banner only) | 1 | 4 | 4 | 6 | 0 |
| `SUPPORT.md`, `.env.example` | 4 | 0 | 0 | 0 | 0 |
| **Total** | **247** | **50** | **41** | **77** | **about 31** |

Older names that should already be gone (not part of the rename, part of DL-1 and DL-9): README
"Atelier" 7, "Maestro" 7, "Narrator" 17, "Publisher" 5, "Site Builder" 9; lessons "Client Gigs" 5,
"Site Builder" 2. "Stamp" at the start of a sentence can be the verb (build stamping): read each hit.

## Model updates: where the docs live today

The feature already has documentation; the new spec (`docs/specs/model-updates.md`) should replace
these in place: `README.md:435-630` ("### Model updates" under section 5), `docs/agents/overview.md:99-111`,
`docs/learn/modules/12-best-fit.md:97` ("## New models"), `10-navigate.md:36-40`, and the help-map
entry `"model_updates_card": "best-fit#new-models"`. No finding; the reservation is in the spec.
