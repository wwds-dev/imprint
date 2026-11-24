# Comply: November release train, Imprint Studio (2026-11-24)

Role: `legal-compliance` (Comply phase). **Not legal advice. Not a sign-off.** The agent is not a
lawyer. `legal_gate.py sign` was not run and `signoff.jsonl` was not touched. Nothing was
committed.

Playbook: `docs/playbooks/legal-compliance.md`, `status: current`, `last-reviewed: 2026-11-11`
(13 days old, not stale). Its "Current practices" intro still calls itself an unverified
baseline, so every rule below carries its source and date, or "not verified". Radar note reused:
`docs/foundry/radar-notes/2026-11-21-legal.md` (3 days old).

## Scope

- Code: branch `claude/happy-dubinsky-48c27c` at `80fc7f0`, read from the main checkout with
  `git show` (18 commits ahead of `origin/main`). Specs on the branch: audit-p1-billing,
  dashscope-workspace-id, deps-security-upgrade-2026-10, quill-draft-safety,
  docs-learning-centre-readiness, local-model-routing (retroactive), rename-imprint-studio, and
  model-updates-visibility (part of `docs/specs/model-updates.md`; no file of its own).
- New since the last sign-off (2026-11-21 22:00, pack `8b0becd4a572`, commit `0f0c0de`): the
  rename, the local-model routing fixes (`e57644a`, `ba870c4`, `2d427e2`), the docs readiness
  work, and the README/CHANGELOG/SUPPORT text. `git diff 0f0c0de origin/claude/happy-dubinsky-48c27c
  -- requirements*.txt vidforge/requirements.txt cloud/requirements.txt pyproject.toml` is
  **empty**: this train changes no dependency.
- Pack: `docs/legal/` in the main checkout is a symlink to `foundry/audits/imprint/legal`; the
  worktree has no `docs/legal`, so the pack was edited at that resolved path (same files).
  Foundry `git status`: 8 pack files modified, uncommitted.
- Also read: `docs/foundry/app-context.md`, `docs/audit/legal.md` (on `main`, 2026-11-23, L-01 to
  L-20), the branch's security, QA and review reports for local-model-routing and the rename.

## Pack files changed, and why

- `register.md`: facts block corrected (tier confirmed, MIT, SUPPORT/SECURITY, vulnerability
  reporting on, display name, live launcher); rows 1, 2, 3, 4, 8, 10, 11, 13, 16, 20 updated;
  rows 23-27 added (remote runtime, measurement calls, Art. 5 safeguards, rename, claims); name
  trigger amended to cover "Imprint Studio"; T1 and T2 evidence updated; **T5 added**; open
  items re-statused. Resolves L-01, L-04 (trigger) and L-06 (trigger wording) in the documents.
- `privacy.md`: data map gains the remote runtime, measurement prompts, Whisper captions, Pexels,
  PublishDrive, YouTube OAuth and Hugging Face rows; DashScope location from the code
  (Singapore-routed); §6 draft notice rewritten (L-05 a-d, local routing, measurement); §8 added.
- `licences.md`: Imprint row now MIT; EbookLib and PySide6 rows updated; §4 rewritten for the
  MIT choice (the TODO item that it still claimed no licence); §8 adds the method, the
  deps-security-upgrade-2026-10 versions with their licences, and "no dependency change in this
  train".
- `terms.md`: §1 records what changed (income chapter gone, two lessons deleted, MIT replaces
  D1, SUPPORT.md disclaimers, Vector fixed); §5 **checked claims list** C1-C18 added.
- `ai-act.md`: cites Reg. 2024/1689 as amended by Reg. 2026/1744; Art. 2(12) note updated for
  MIT; Art. 5 screen reopened; §8 per-output Art. 50(2) table (Booth, Shorts, release kit,
  images, video, text); §9 Art. 5(1)(ba)/(bb) safeguards table.
- `name.md`: names now in use (Imprint Studio display, Imprint short form), the UK applicant
  fact, trigger amended.
- `name-candidate-imprint-studio.md`: status line: adopted, trigger amended, rows still empty.
- `name-candidate-fusion-studio.md`: status line: dropped candidate (L-16 left to the owner).
- The six files signed on 2026-11-21: stray tool markup (`</content>`, `</invoke>`) removed (L-01).

## Findings

### P0 (blocks release)
None found. This rests on: no binary release (`gh release list -R wwds-dev/imprint`: empty,
2026-11-24); the installed `/Applications/Imprint Studio.app` is the 35,792-byte live launcher
that runs the source tree and contains no third-party code; no payment code; no telemetry. **If a
frozen `.app` is given to anyone, R-P1-2 becomes P0.**

### P1 (owner decision before release)

**R-P1-1. The legal gate is BLOCKED; the pack changed and needs a fresh sign-off.**
`python3 docs/foundry/tooling/legal_gate.py status .` (2026-11-24, after the edits, exit 0):
`pack: 8 file(s), hash 9cfeafbeef47`; `last sign-off: wwds-dev (owner) 2026-11-21T22:00:27 pack
8b0becd4a572 [STALE: pack changed]`; four open lawyer triggers (name, T1, T2, T5);
`legal gate: BLOCKED: legal pack changed since the last sign-off (wwds-dev, 2026-11-21)`. An owner
sign-off with open triggers needs `--accept-risk` in writing. Rule: AGENTS.md "Legal sign-off";
tier `public`, sign-off by the owner.

**R-P1-2. MIT source, AGPL EbookLib, no notices (audit L-02, unchanged in code).**
`LICENSE` is MIT; `requirements.txt` pins `EbookLib==0.20` (metadata "GNU Affero General Public
License", `importlib.metadata`, 2026-11-24); `git ls-tree -r` on the branch shows no notices file;
`Imprint.spec:105-108` still excludes only pytest, pip, setuptools, so a frozen bundle would carry
GPL-3.0 Qt Virtual Keyboard. Rule: LGPL-3.0 §4 (gnu.org, read 2026-11-22 by `docs/audit/legal.md`);
Qt 6.12 licensing page (doc.qt.io, read 2026-11-22 by the same audit; the 6.11 page not read);
AGPL text not read: not verified. Exposed: anyone who receives a bundle labelled MIT. Decision:
the owner, whether an MIT repo with an AGPL dependency is acceptable as it stands, and EbookLib's
future. Fix: `THIRD_PARTY_NOTICES.md` plus a README line naming the LGPL and AGPL dependencies;
before any `.app` leaves the owner's machines, the bundle steps in `licences.md` §3.

**R-P1-3. No AI marking anywhere, two provider watermarks switched off; T1's date is 2 Dec 2026
(8 days away) (audit L-03, unchanged in code).** `services/image_generation.py:150` and
`services/qwen_client.py:493` send `"watermark": False`; audiobook M4B metadata holds title and
chapters only (`services/narrator/converter.py:980-990`, `:1012-1024`); Shorts get none
(`agents/manuscript/shorts_generator.py:47-60`); the release kit records but embeds nothing.
Rule: Reg. (EU) 2024/1689 Art. 50(2) and Art. 111(4), as amended by Reg. (EU) 2026/1744; dates
from euaiact.com/digital-omnibus-ai and Steptoe / White & Case / Cuatrecasas via search,
2026-11-24; EUR-Lex returned empty pages: **primary text not verified**. One source (Goodwin) is
summarised as giving 2 Dec 2027. Exposed: the owner if a provider; users who publish unmarked
output. Decision: lawyer (T1); owner (mechanism). Step that needs no legal answer: remove both
`"watermark": False` lines or make the watermark a default-on setting (`ai-act.md` §8).

**R-P1-4. New Art. 5(1)(ba)/(bb) prohibition from 2 Dec 2026; one of four image/video routes has
a local safeguard (audit L-04). Lawyer trigger T5 added.** Higgsfield route: `check_prompt`
(`services/higgsfield_client.py:80,152`; `agents/creator/panel.py:1121`). Wan/Omni teaser from a
person's reference photos: no local check (`agents/creator/panel.py:1190,1249-1298`). Image
generation: none (`services/image_generation.py`). Consent columns unread
(`services/database.py:253-256`). Rule: playbook "EU AI Act" (conditions "reasonably
foreseeable", "adequate technical safeguards"); date from euaiact.com, 2026-11-24; conditions
**not verified**. Exposed: any real person whose photo is used; the owner. Fix (engineering, no
legal answer needed): apply `check_prompt` to the Wan, Omni and image routes.

**R-P1-5. The privacy notice is still unpublished (audit L-05).** The draft is now corrected
(`privacy.md` §6) and covers the remote runtime and measurement prompts, but the branch README has
no privacy section and `docs/learn/modules/13-access-privacy.md` has no recipient list. Rule:
AGENTS.md tier table (`public` needs a privacy note); GDPR Arts. 13 and 44-46 not re-read: not
verified. Exposed: users who send clients' or third parties' data without knowing where it goes.
Fix: the owner places §6 (README "Start here" or §1, and the access-and-privacy lesson).

**R-P1-6. The name is not cleared, and this train ships "Imprint Studio" (audit L-06).** The
display name is live on the branch (`services/runtime_paths.py:32`, `main.py:263`,
`Imprint.spec:120-157`, README, SUPPORT.md, SECURITY.md). All 19 owner-run register rows
(`name.md` §4, `name-candidate-imprint-studio.md` §5) are empty. The trigger now covers both
names. Rule: playbook "Name" (not cleared until the owner-run rows are filled; hits are facts;
conflict is a lawyer's call). Exposed: the owner, to an objection from an earlier IMPRINT or
IMPRINT STUDIOS holder. Decision: the owner runs the rows; a lawyer decides the trigger, or the
owner accepts the risk in writing.

### P2

**R-P2-1. Public copy says local models are free and on this Mac; the code can do otherwise.**
README Start here step 3 "run one on this Mac for free", README §1 "Local models ... run on this
Mac and cost nothing", lesson `13-access-privacy.md:39` "Local models cost nothing". A new local
model is measured once with paid cloud calls, automatically (`main.py:1180-1269`), and a runtime
may be on another machine (`services/providers.py:124-149`). README §1 "asks before anything is
sent" does not hold for that automatic run. (`terms.md` §5 C2, C3.) Fix: the wording in
`terms.md` §5.

**R-P2-2. "On this Mac" label for a remote runtime after the user says yes (RC-6,
`TODO.md:68`).** CHANGELOG claim C6 holds for the question, but the picker then says "On this
Mac"; the dialog itself admits it. Fix: show the host (security P1-1's original fix).

**R-P2-3. "Always tagged" for uncensored models does not hold (security P2-3).** README `:891`.
Suggested wording in `terms.md` §5 C8.

**R-P2-4. Gemini "free tier available" tooltip (audit L-10).** `ui/tooltips.py:27`, unchanged.
Gemini API Additional Terms (effective 2026-03-23, read by the audit 2026-11-22): only Paid
Services for API clients made available to users in the EEA. Fix: drop the phrase; place D6.

**R-P2-5. General rights-and-disclosure text is gone from the Learning Centre.**
`docs/learn/05-best-practices.md` was deleted by the docs readiness work; only per-lesson
checklists remain (`24-video.md:57,62`, `25-social.md:61`, `28-creator.md:11,73`). Booth still
shows no OpenAI listener-disclosure notice and Press offers the macOS voice with no notice
(audit L-08; T2). Fix: place `terms.md` D3 and the kit's voice notices in Booth and Press.

**R-P2-6. App-context `## Models used` lists Ollama and LM Studio as "local, yes" only.** The
code lets either point at another machine (register row 23). Not a new provider, so not the P1
processor rule; the orchestrator should add a note in app-context (this agent does not edit it).

**R-P2-7. Still open from the 2026-11-23 audit, unchanged by this train:** L-07 (Quill Market:
"market size", a specific price, launch-team review exchange, `agents/author/agent.py:117,155,182`;
the Vector part is fixed), L-09 (YouTube ToS and privacy links), L-11 (`cloud/` full Drive scope),
L-12 (release check not wired into the build), L-13 (provider terms not on file).

### P3

- R-P3-1. Bundle id `com.netrunner3000.imprint` (`Imprint.spec:154`) and owner paths `/Users/...`
  (`services/narrator/converter.py:30`, `config/tools.json:5-6`) in the public source (audit
  L-14; lab AGENTS.md forbids that handle and hardcoded paths).
- R-P3-2. `data/local_ratings.json`, `data/routing_rules.json`, `data/routing_savings.json` are
  not git-ignored in a public repo (security P3-6).
- R-P3-3. CHANGELOG "costs what it said it would" (C7): accurate as "no more than the ceiling it
  was authorised for"; a thinking judge can spend its cap (RC-13).
- R-P3-4. `name-candidate-fusion-studio.md` (dropped) is hashed into the pack (audit L-16).
- R-P3-5. `licences.md` §1-3 still describe build 302; §8 states the current versions. A fresh
  bundle listing is needed before any distribution (and after the pending PySide6 upgrade,
  audit L-18).

## Lawyer triggers

| Trigger | Status 2026-11-24 | Evidence |
|---|---|---|
| Name (Imprint / Imprint Studio, trademark conflict) | **Open, amended** to cover the display name now in use and the IMPRINT STUDIOS filing | `services/runtime_paths.py:32`; `name-candidate-imprint-studio.md` §2 |
| T1: provider role under Art. 50(2), marking measures, 2 Dec 2026 date | **Open**, unchanged in substance; evidence widened to images and video (watermark off) | `services/image_generation.py:150`, `services/qwen_client.py:493`, converter, Shorts |
| T2: macOS System Voices in published Shorts (EA2005 §2F) | **Open**; evidence widened to Press's "System (Free)" voice outside the kit | `agents/manuscript/panel.py:1040-1052` |
| T5: Art. 5(1)(ba)/(bb) safeguards (new) | **Opened 2026-11-24** from audit L-04, under the playbook rule "treat a gap as a lawyer trigger" | `ai-act.md` §9 |
| T3, T4 (release-kit slice 3 routes) | Not opened: the kit still has no paid step | `services/release_kit/plan.py` |

No trigger was closed. Considered and not raised: the remote runtime (the user's own choice, told
before sending) and the measurement calls (no user content); both are matters for the claims and
the privacy notice (`register.md` rows 23-24).

## Cross-check with `docs/audit/legal.md` (2026-11-23)

| Finding | This pack update | What stays, and for whom |
|---|---|---|
| L-01 pack contradicts the repo; gate BLOCKED | **Resolved in the documents**: tier, MIT, SUPPORT/SECURITY, vulnerability reporting, income chapter, PySide6 version, deleted-lesson references and stray markup corrected | Gate stays BLOCKED until the **owner** signs the new pack (hash `9cfeafbeef47`) |
| L-02 no notices; copyleft in bundle vs MIT | Documented (`licences.md` §4, §8; register row 2) | **Owner** decision (EbookLib, notices) and an engineering fix; not resolved |
| L-03 no AI marking; watermarks off; T1 | Documented per output (`ai-act.md` §8); T1 evidence widened | **Lawyer** (T1) and **owner** (mechanism); code unchanged |
| L-04 Art. 5 prohibition, uneven safeguards, no trigger | **Trigger T5 added**; register row 25; `ai-act.md` §9 | **Lawyer** (T5); engineering fix (`check_prompt` on three routes) |
| L-05 privacy note unpublished and inaccurate | **Draft corrected** on (a)-(d), plus remote runtime and measurement (`privacy.md` §6, §8) | **Owner** publishes it |
| L-06 name not cleared; rename approved with trigger open | **Trigger amended** to name both; `name.md` records the names in use | **Owner** runs 19 rows; **lawyer** decides, or the owner accepts the risk |

## Claims check

Full table: `terms.md` §5 (C1-C18). Every user-facing claim in README "Start here" (and §1, which
it leads into), CHANGELOG Unreleased, SUPPORT.md and SECURITY.md on the branch is now on the
checked list. None was on a list before except the release-kit claims (register row 22), so all
are new to the list. Results:
- **Needs a change:** C2 (local "free" / "on this Mac" / "cost nothing"), C3 ("asks before
  anything is sent"), C8 ("always tagged").
- **Holds with a caveat:** C5 (Local only: holds for paths through `authorize_request` and
  `_send_chat`; keep "no agent", do not widen to "nothing leaves"), C6 (holds; the "On this Mac"
  label after a yes is R-P2-2), C7 (wording), C14 (true only while no `.app` is shared), C15
  ("free, open-source": true for the source; the AGPL dependency is unstated).
- **Holds:** C1 (fact; name not cleared), C4, C9, C10, C11 (per the rename QA and security
  reports), C12, C13, C16. C17 is an owner promise. C18 not verified by this agent.
No income, sales or results claim was found in the new text.

## What changed since the last sign-off (2026-11-21, pack `8b0becd4a572`)

- Pack: two name-candidate files added on 2026-11-22 (pack `051b81981cf7`); this update edited all
  eight files (pack `9cfeafbeef47`): register rows 23-27, trigger T5, the amended name trigger,
  the corrected privacy notice, the claims list, the AI Act tables, the licence inventory update.
- Repo: MIT `LICENSE` (`9f656a1`, after the sign-off); SUPPORT.md and SECURITY.md edited; rename
  to "Imprint Studio"; local-model routing fixes; docs readiness (income chapter and seven legacy
  lessons deleted); no dependency change.

## Residual risks if signed now

- T1 and T5 dates fall on **2 Dec 2026**; no output is marked, two provider watermarks are off,
  and three of four image/video routes have no local safeguard.
- The name in public use is not cleared.
- The privacy notice is drafted but not published.
- Three public sentences (C2, C3, C8) say more than the code does.
- A frozen bundle would carry AGPL and GPL-3.0 code with no notices; today none is distributed.

## Sign command (for the owner only, in a terminal at the app root, after reading the pack)

With triggers open, an owner sign-off needs the risk accepted in writing:

```
python3 docs/foundry/tooling/legal_gate.py sign . --by wwds-dev --role owner --accept-risk "<why the name, T1, T2 and T5 triggers are accepted until a lawyer decides>"
```

A lawyer's sign-off (no `--accept-risk` needed):

```
python3 docs/foundry/tooling/legal_gate.py sign . --by "<lawyer's name>" --role lawyer
```

Flags read from the source, `legal_gate.py:261-265` (`--by`, `--role`, `--scope`,
`--accept-risk`); the agent did not run `sign` or its help.

## Not verified

- AI Act primary text: EUR-Lex returned empty pages for Reg. 2024/1689 and Reg. 2026/1744
  (2026-11-24). Arts. 5, 50, 111(4) and 2(12) rest on a secondary site, commentary and the
  playbook. Commission guidelines C(2026) 5054 and the code of practice: not read.
- GDPR, Data Protection Act 2018, Consumer Protection Act 2007, CRRA 2000, CRA, PLD: not re-read.
- AGPL-3.0 text; Qt 6.11 licensing page; provider terms other than those cited from the
  2026-11-22 audit (not re-read today).
- Every send path under Local only (only the guard and its tests were read); no network capture.
- Name registers (EUIPO, TMview, Irish IPO, CRO, WIPO): not queryable by the agent; no new web
  searches for the name were run today.
- Whether any frozen `.app` was ever given to anyone; whether `cloud/` is deployed.
- README "boxes start unticked at every launch" (C18).
- No test suite or model call was run.

Sources read on 2026-11-24: [euaiact.com, Digital Omnibus on AI](https://www.euaiact.com/digital-omnibus-ai);
search results naming [Steptoe](https://www.steptoe.com/en/news-publications/steptechtoe-blog/eu-ai-act-amendments-enter-into-force.html),
[White & Case](https://www.whitecase.com/insight-alert/eu-ai-omnibus-enters-force-amending-ai-act),
[Cuatrecasas](https://www.cuatrecasas.com/en/spain/intellectual-property/art/digital-omnibus-ai-has-been-published),
[Goodwin](https://www.goodwinlaw.com/en/insights/publications/2026/08/alerts-technology-dpc-eu-ai-act-transparency-obligations-now-in-force).
