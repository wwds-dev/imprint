# Legal and compliance audit: Imprint (tier `public`, EU/Ireland focus)

Role: `legal-compliance`, read-only audit. Run 2026-11-22/23 on `main` at `ec1cda5`.
**Not legal advice. Not a sign-off.** The agent is not a lawyer. Nothing under `docs/legal/` was
created or edited (another session is preparing the pack), `legal_gate.py sign` was not run and
`signoff.jsonl` was not touched. This file is the only file written.

Playbook: `docs/playbooks/legal-compliance.md`, `status: current`, `last-reviewed: 2026-11-11`
(12 days, not stale). Its "Current practices" intro still calls itself an unverified baseline, so
every rule relied on below was checked against the source named, or is marked "not verified".

Method: read `docs/foundry/app-context.md`, the pack (`docs/legal/` is a symlink to
`foundry/audits/imprint/legal`), `LICENSE`, `SUPPORT.md`, `SECURITY.md`, the two one-click-release
legal reports, the code paths cited, the three requirements files, licence metadata of the
installed set (`.venv/bin/python -I` with `importlib.metadata`; no licence tool is installed, no
lockfile exists) and a listing of the installed bundle `/Applications/Imprint.app` (build 406,
commit `6967c8a`). Read-only `gh` calls on the repo's own host for visibility, licence detection,
releases and private vulnerability reporting. Web lookups for rule sources only.

## Summary

The repo is public, source-only, under an MIT `LICENSE` added on 2026-11-21 at 22:36, after the
22:00 sign-off. No binary has been released (`gh release list`: empty; `SUPPORT.md:27`). I found
no P0 on that evidence. Six P1 items stand between today and a signable pack: (1) the gate is
BLOCKED and the pack's facts contradict the repo (it still says there is no licence, and the tier
is unconfirmed); (2) there is no third-party notices file, and the PyInstaller bundle carries
AGPL EbookLib and GPL-3.0 Qt Virtual Keyboard with no licence texts, which rules out handing the
`.app` to anyone under an MIT label; (3) no synthetic output is marked and two calls ask the
provider for unwatermarked output, with lawyer trigger T1's 2 December 2026 date nine days away;
(4) the new AI Act prohibition on non-consensual intimate imagery is reported to apply from the
same date and only one of four generation routes has a local safeguard, with no lawyer trigger
recorded; (5) the privacy note is a draft that is published nowhere and is inaccurate in places;
(6) the name is not cleared, the owner-run register searches are empty and a rename to
"Imprint Studio" is approved while the trigger is open. Three lawyer triggers are open (name, T1,
T2). The 2026-11-21 sign-off is stale because two name-candidate files were added to the pack.

## Findings

### P0
None found. This rests on: no release (`gh release list -R wwds-dev/imprint`: empty), "published
as source, with no binary release" (`SUPPORT.md:27`), no payment code, no telemetry. If a copy of
`Imprint.app` has been given to anyone, L-02 becomes P0.

### P1

**L-01. The gate is BLOCKED and the pack to be signed contradicts the repo.**
- Evidence: `legal_gate.py status .` (below): pack 8 files, hash `051b81981cf7`, last sign-off
  pack `8b0becd4a572` "STALE". Pack text that is no longer true:
  `register.md:13-14` "tier ... proposed by an agent and not confirmed by the owner"
  (`app-context.md:12` says confirmed 2026-11-11); `register.md:16-19` and row 1 (`:40`) "no
  `LICENSE`", `licences.md:31` "none", `licences.md:81-93` (repo: MIT, `LICENSE:1`, commit
  `9f656a1`, `gh api .../license` returns MIT); `register.md:18-19` "no `SUPPORT.md` or
  `SECURITY.md`", private vulnerability reporting disabled (both files exist; reporting is
  `{"enabled":true}`); `register.md:47`, `:82` and `terms.md:23-27`, `:76` cite a hidden income
  chapter at `README.md:3424-3715` (README has 3,586 lines and no HTML comment; the chapter is
  gone); `licences.md:18-20`, `:33-36` describe build 302 with PySide6 6.12.0 and libavcodec 63
  (installed bundle is build 406 with PySide6 6.11.2, `requirements.txt:35`, and libavcodec 61);
  `terms.md:16`, `ai-act.md:59` cite `docs/learn/05-best-practices.md`, which does not exist.
  All six signed files end their first section with stray tool markup (`</content>`,
  `</invoke>`: `register.md:104-105`, `licences.md:119-120`, `privacy.md:87-88`,
  `ai-act.md:88-89`, `name.md:86-87`, `terms.md:90-91`).
- Rule: AGENTS.md "Legal sign-off" and tier table (`public`: LICENSE, notices, disclaimers,
  privacy note, name check; sign-off by the owner). A sign-off binds the pack's bytes
  (`legal_gate.py:99-108`).
- Decision for a person: the owner signs only a pack whose facts match `main`.
- Smallest fix: the Comply session corrects those rows and removes the stray lines, then the
  owner signs after the last edit.

**L-02. No third-party notices; the bundle's copyleft contents do not fit the MIT label.**
- Evidence: `git ls-files | grep -i -E "licen|notice|third.?party|copying|credits"` returns only
  `LICENSE`. `EbookLib==0.20` (`requirements.txt:7`, `cloud/requirements.txt:3`), metadata
  "GNU Affero General Public License v3 or later"; imported at
  `agents/author/book_exporter.py:70`, `services/narrator/converter.py:18`; in the bundle's
  Python archive (`pyi-archive_viewer -l -r .../MacOS/Imprint`: `ebooklib`, `ebooklib.epub`,
  `ebooklib.utils`). Bundle also holds `QtVirtualKeyboard.framework`,
  `QtVirtualKeyboardQml.framework` and `plugins/platforminputcontexts/libqtvirtualkeyboardplugin.dylib`;
  `Imprint.spec:105-108` excludes only pytest, pip, setuptools. PySide6, shiboken6 6.11.2
  (metadata: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only); FFmpeg libs (`strings
  libavcodec.61.dylib`: "LGPL version 2.1 or later"). Licence texts in the bundle outside
  `dist-info`: only `anthropic/_vendor/httpx_aiohttp/LICENSE` and `NOTICE.md`; none for Qt,
  PySide6, FFmpeg, EbookLib, Python. No About box or licence screen in `ui/` or `main.py`
  (grep for `aboutQt|LGPL|third.party|open.source`: no hit). `vidforge/` and `cloud/` have no
  licence file of their own; they are in-tree, so the root `LICENSE` reaches them.
- Rule: LGPL-3.0 section 4 (gnu.org/licenses/lgpl-3.0.html, read 2026-11-22): a combined work
  may be conveyed under terms of your choice if they do not restrict modifying the library or
  reverse engineering to debug such modifications, and you (a) give prominent notice that the
  library is used and is under the LGPL, (b) include the GPL and LGPL texts, (c) show the
  library's copyright notice wherever the app shows copyright notices, (d) convey the library's
  source and relinkable application code, or use a shared-library mechanism that works with a
  modified compatible version, (e) give installation information where GPL section 6 requires.
  Qt licensing page (doc.qt.io/qt-6/licensing.html, Qt 6.12, read 2026-11-22): Qt Virtual
  Keyboard is listed under "Modules available under GNU General Public License v3", not LGPL;
  the 6.11 page was not read. EbookLib README (github.com/aerkalov/ebooklib, read 2026-11-22):
  "EbookLib is licensed under the AGPL license"; no dual licence mentioned. AGPL-3.0 sections 5,
  6 and 13: text not read this session (gnu.org returned HTTP 429), not verified.
- What a PyInstaller build needs for PySide6 as far as the sources above go: the LGPL-3.0 and
  GPL-3.0 texts in the bundle; a prominent notice naming Qt and PySide6 and their licence; their
  copyright notice in an About box if the app shows one; Qt and PySide6 kept as separate
  replaceable `.framework`/`.dylib` files (they are; `Imprint.spec:124,138` UPX off); the source
  of the exact Qt and PySide6 version shipped, or a written offer for it; nothing in the app's
  terms that forbids modifying Qt or reverse engineering to debug that (MIT does not); the same
  notice and source duty for the LGPL FFmpeg libraries; Qt Virtual Keyboard left out of the
  bundle. Ad-hoc signing (`codesign -dv`: `Signature=adhoc`) may stop a user running a replaced
  library; whether that matters under 4(e) is a person's call.
- Who is exposed: the owner, as the one who would convey the bundle; anyone told the app is MIT
  who receives AGPL and GPL-3.0 code inside it.
- Decision for a person: whether an MIT source repo that imports an AGPL library is acceptable as
  it stands; under which licence a bundle may be conveyed; replace EbookLib or relicense.
- Smallest fix: add `THIRD_PARTY_NOTICES.md` (generated from the metadata listing) and say in
  the README that the app is MIT and which dependencies are LGPL and AGPL. Before any `.app`
  leaves the owner's machines: exclude Qt Virtual Keyboard in `Imprint.spec`, copy licence texts
  into `Contents/Resources/licenses/`, add a `--selftest` check for them, and decide EbookLib.

**L-03. No machine-readable AI marking, and two calls switch the provider watermark off; T1's
date is 2 December 2026.**
- Evidence: `services/image_generation.py:150` and `services/qwen_client.py:493` send
  `"watermark": False`. Audiobook metadata holds title and chapters only and the merge
  re-encodes (`services/narrator/converter.py:984-986,1015-1022`); Shorts get no metadata
  (`agents/manuscript/shorts_generator.py:49-59`); the YouTube upload body carries no
  synthetic-content field (`vidforge/vidforge/youtube.py:106-117`). Grep for
  `c2pa|synthid|AI-narrated|comment=` outside `services/release_kit`: no hit. The release kit
  records AI facts in a report and `provenance.json` and embeds nothing (`ai-act.md:94`).
- Rule: Reg. (EU) 2024/1689 Art. 50(2), as amended by Reg. (EU) 2026/1744. Commentary read
  2026-11-22 (Cuatrecasas legal flash, July 2026; search summaries of A&O Shearman, Steptoe,
  White & Case): the Omnibus was published 24 July 2026 and entered into force 27 July 2026;
  Art. 50 applies from 2 August 2026; providers whose systems were on the market before that
  date have until 2 December 2026 for the labelling duty. One source (Goodwin) is summarised as
  saying 2 December 2027. **Primary text not read**: both EUR-Lex URLs returned an empty page to
  the fetch tool. `ai-act.md:6` still cites the unamended regulation.
- Who is exposed: the owner if he is a provider; users who publish unmarked output as deployers.
- Decision for a person: lawyer trigger T1 (is Imprint placed on the market or put into service;
  which marking measures; which date). The owner decides the mechanism.
- Smallest fix that needs no legal answer: remove `"watermark": False` from both calls, or make
  it a default-on setting. Everything else waits for T1.

**L-04. The reported new Art. 5 prohibition (2 December 2026) has no lawyer trigger and uneven
safeguards.**
- Evidence: the only local prompt refusal is on the Higgsfield route
  (`services/higgsfield_client.py:74-85`, called at `agents/creator/panel.py:1117`). The Wan and
  Gemini Omni teaser route goes from permission to `authorize_request` with no check
  (`agents/creator/panel.py:1231-1251`), and takes reference images
  (`:1245`, `:1294`; `services/qwen_client.py:471-477`). `services/image_generation.py` has no
  local check. Reference images are uploaded to a public URL for Higgsfield
  (`services/higgsfield_client.py:279-321`). The consent columns are in the schema
  (`services/database.py:253-256`) and no code reads them (`ai-act.md:59`, `register.md:50`).
  No route lowers a provider safety setting (grep `moderation|safety|person_generation`: no hit).
  `ai-act.md:33-37` screens Art. 5 as it stood before the amendment.
- Rule: playbook, "EU AI Act": from 2 December 2026 Art. 5(1)(ba), (bb) and (1a) prohibit a
  system that can generate realistic intimate imagery of an identifiable person without consent,
  or CSAM, where that output is foreseeable and the system lacks adequate technical safeguards;
  record safeguards with file:line and treat a gap as a lawyer trigger. The date and subject are
  confirmed by commentary read 2026-11-22 (Cuatrecasas; A&O Shearman per search summary); the
  conditions ("foreseeable", "safeguards") were **not verified** at the primary text.
- Who is exposed: the owner as provider of a system with image-to-video from reference photos;
  any real person whose photo is used.
- Decision for a person: a lawyer, on whether provider-side filters count as adequate safeguards
  for a bring-your-own-key desktop app, and whether the missing consent step matters.
- Smallest fix: the Comply session adds a `- [ ] LAWYER:` line with the evidence above; an
  engineer applies `check_prompt` to the Wan, Omni and image routes.

**L-05. The privacy note is published nowhere and the draft is inaccurate against the code.**
- Evidence: `README.md` has no privacy section (grep `privacy`: lines 727, 786, 3526 only, none a
  notice); no first-run notice in `main.py` or `ui/`. The draft at `privacy.md:71-82`:
  (a) says data stays in `~/Library/Application Support/Imprint/`, which holds only for a frozen
  build; a checkout or the live launcher uses the project folder (`app-context.md:54`), and
  narration output goes to a path under Documents (`services/narrator/converter.py:30`,
  `config/tools.json:5-6`); (b) omits recipients the code calls: PublishDrive
  (`agents/manuscript/publishdrive_client.py:30`), Pexels (`vidforge/vidforge/visuals.py`),
  OpenAI transcription of generated narration (`vidforge/vidforge/captions.py:63-64`), Hugging
  Face for ratings (`services/benchmarks.py`), Google for the YouTube OAuth
  (`vidforge/vidforge/youtube.py:23`), and KDP sales rows sent to a text model
  (`privacy.md:37`); (c) does not say that reference images go to a public URL (L-04), that
  ElevenLabs uses content for training unless the user opts out, or that Google uses unpaid
  Gemini content to improve its products; (d) `privacy.md:46-47` calls the DashScope location
  "not verified" while the code names Singapore (`services/qwen_client.py:29`,
  `services/database.py:1114`). Every provider in `## Models used` is covered by the data map;
  no provider called by the code is missing from `## Models used` (host list from a grep over
  `agents services providers ui main.py vidforge/vidforge cloud`). The Ollama and LM Studio rows
  are local as far as the code shows (`services/providers.py:41-42`, loopback hosts,
  `NO_PROXIES`); no network capture was made.
- Rule: tier table, `public` needs a privacy note (AGENTS.md). GDPR Arts. 13 and 44-46
  (Reg. (EU) 2016/679): not re-read, not verified; whether the owner is a controller at all for
  a source-only app is the pack's own open reading. ElevenLabs Terms of Use, last updated
  2026-10-09, read 2026-11-22: training use with an opt-out in "Data use". Gemini API Additional
  Terms, effective 2026-03-23, read 2026-11-22: unpaid content is used to improve products.
- Who is exposed: users who send clients' or third parties' data without knowing where it goes.
- Decision for a person: the owner accepts the wording and where it appears.
- Smallest fix: correct the draft on points (a) to (d) and put it in the README and the
  Learning Centre's access-and-privacy lesson.

**L-06. The name is not cleared and a rename is approved while the trigger is open.**
- Evidence: open `LAWYER:` line at `register.md:65`. `name.md:77-85`: all nine owner-run rows
  (EUIPO, TMview, Irish IPO, CRO, WIPO, WHOIS, App Store) are empty.
  `name-candidate-imprint-studio.md:164-173`: rows 10-19 empty; it records a US filing reported
  as IMPRINT STUDIOS (serial 88877738) and proposes new trigger wording (`:142-144`) that has
  not been applied. The rename spec is approved (`docs/specs/rename-imprint-studio.md:5`) and
  itself says Release stays stopped (`:199-201`). On `main` the name is still "Imprint"
  (`services/runtime_paths.py:27`, `Imprint.spec:156-157`).
- Rule: playbook, "Name": a name is not cleared until the owner-run rows are filled in; a working
  name blocks tier `public` and above. Hits are facts; conflict is a lawyer's call.
- Who is exposed: the owner, to an objection from an earlier mark's holder once the name is
  public and later paid.
- Decision for a person: the owner runs the 19 searches; a lawyer decides the trigger for both
  names.
- Smallest fix: run the rows; apply the proposed trigger wording so the lawyer sees both names.

### P2

**L-07. Stamp's persona and Quill's market output can put unverifiable claims into published copy.**
`agents/fiverr/agent.py:3` gives the model "a 5-star reputation built on fast turnarounds";
`:20-28` asks for a first-person gig description with "Why choose this gig" and
Basic/Standard/Premium "with prices"; `:35` promises "vector logo" while the pipeline makes
raster PNGs (audit QM-18, `docs/audit/code-readiness-audit-2026-11-18.md:80`; open at
`TODO.md:102`). `agents/author/agent.py:117` asks for "market size", `:153-155` for real
categories, keywords and a specific price, with no "verify" line; `:182` frames a launch-team
email as an ARC and bonuses in return for a review "posted on launch day". Rule: app-context
invariant (`app-context.md:108`); Consumer Protection Act 2007 and Directive 2005/29/EC on
misleading practices, and Amazon's and Fiverr's review rules: none read this session, not
verified. Not run live, so no output was observed. Exposed: Fiverr buyers and readers; the
user's accounts. Fix: remove the reputation sentence and the fixed prices, add a "check before
you publish" line to Publish and Market output, reword the review exchange.

**L-08. Voice terms are surfaced only inside the release kit.**
- macOS `say`: Press Shorts, Quote Finder and the calendar use it by default
  (`providers/voice/mock.py:69,78`; `agents/manuscript/panel.py:1086,1511,1704`) with no notice
  (grep `non-commercial|N2` in `agents/manuscript`, `providers/voice`: no hit). The kit shows N2
  (`services/release_kit/plan.py:59-60`) and `README.md:1923` says "for testing only". Rule:
  macOS licence EA2005 section 2F, read on this Mac 2026-11-22: System Voices for "personal,
  non-commercial use"; no "publishing or redistribution ... in a profit, non-profit, public
  sharing or commercial context". Lawyer trigger T2 covers it.
- ElevenLabs "Rachel" is the default (`providers/voice/elevenlabs.py:70`,
  `services/narrator/converter.py:50-53`); the app cannot see the plan. Terms of Use, last
  updated 2026-10-09, read 2026-11-22: free users "may only use the Services for non-commercial
  purposes"; paid users may use them commercially. The Voice Library Addendum, which may govern
  premade voices, was not read.
- OpenAI narration is the default route (`converter.py:45,66`). TTS guide, read 2026-11-22:
  "provide a clear disclosure to end users that the TTS voice they are hearing is AI-generated
  and not a human voice"; `gpt-4o-mini-tts` shuts down 2027-01-06. Booth shows no such notice
  (grep `disclos|AI voice|not a human` in `agents/audiobook`, `services/narrator`: no hit). The
  Service Terms and Usage Policies were not read.
- Gemini narration (`converter.py:59`): the Additional Terms (effective 2026-03-23) hold no
  disclosure duty; 18+; EEA rule in L-10.
- Audiobook stores: `docs/learn/modules/22-audiobooks.md:88` points to ACX's rules; ACX's page
  was not read.
Decision: owner, plus T2. Fix: show the same three notices in Booth and Press that the kit shows.

**L-09. Platform terms for posting are unread, and one YouTube requirement is visibly unmet.**
YouTube API Services Developer Policies (developers.google.com/youtube/terms/developer-policies,
undated, read 2026-11-22): III.A.1 an API client displays a link to YouTube's Terms of Service;
III.A.2 it requires users to agree to a privacy policy that links to Google's; III.E.3.d and
III.I.2 express consent before uploads. The app has no such link or policy (grep
`youtube.com/t/terms|policies.google.com/privacy`: no hit). Consent is met by design: private by
default and a two-key guard for public (`vidforge/vidforge/youtube.py:95-104`), nothing posts
without a click (`agents/social/publishing.py:8-9`). Reddit uses the password grant on the
user's own script app with scope `submit` (`agents/social/publishing.py:154-166`), password kept
in `.env`; Reddit's Data API Terms could not be fetched. Pinterest (`:336`): developer
guidelines not read. Whether the user, who registers the OAuth client, or the owner, who
publishes the client software, is the "API client" is a person's call. Fix: add the two links
and read the three terms before the next Comply.

**L-10. A tooltip steers users to Gemini's free tier.** `ui/tooltips.py:27`: "Allow this request
to use Google Gemini (free tier available)." Gemini API Additional Terms, effective 2026-03-23,
read 2026-11-22: "You may use only Paid Services when making API Clients available to users" in
the EEA, Switzerland and the UK; unpaid content is used to improve Google's products. Fix: drop
"free tier available" and place draft D6 (`terms.md:62-66`).

**L-11. `cloud/reading_compass.py` requests the full Drive scope and has no privacy policy.**
`cloud/reading_compass.py:35,252` (`openid email` plus `auth/drive`), owner-only by
`ALLOWED_EMAIL` (`:280`), refresh token encrypted in Firestore; ebook text from Drive goes to
OpenAI for narration (`:595`, `cloud/README.md:41-43`); `cloud/web/` has no privacy or terms
text. Google API Services User Data Policy, last updated 2024-02-15, read 2026-11-22: "You must
publish a privacy policy"; transfers of user data are limited; restricted scopes need an annual
security assessment unless the app is used only within the developer's own domain. Whether full
Drive is a restricted scope is defined on another Google page, not read. The hosted worker runs
EbookLib (`cloud/requirements.txt:3`); AGPL section 13 not read. Whether the service is deployed
is tracked outside the repo. Decision: owner, before any production OAuth publishing. Fix:
narrow to `drive.file` if the folder design allows, or record owner-only testing mode in the pack.

**L-12. The release check is not wired into the build.** `grep release_check|legal_gate
scripts/*.sh .github/workflows/*.yml`: no hit. The installed bundle is build 406 with files
dated 2026-11-22 02:29 to 04:38, after the pack went stale at 00:54. It was a local install, not
a distribution. Rule: AGENTS.md, "Release starts only when `release_check.py .` passes". Fix:
`/harden` wires it into `scripts/build_app.sh` and CI.

**L-13. Provider terms are not on file.** `ai-act.md:82-87` lists them as "not yet collected".
Read today: OpenAI TTS guide, ElevenLabs Terms, Gemini Additional Terms. Never read by an agent:
OpenAI Service Terms and Usage Policies, Anthropic, DeepSeek, Moonshot, Alibaba, Higgsfield,
Pexels, PublishDrive. Fix: a person saves each with its effective date.

### P3

- **L-14.** The owner's macOS user name and a second handle are in the public source:
  `services/narrator/converter.py:30`, `config/tools.json:5-6` (`/Users/...` paths, also a lab
  hard rule), and the bundle id `com.netrunner3000.imprint` (`Imprint.spec:154`,
  `scripts/install_app.sh:82`; open at `TODO.md:69`). Owner's own data; his decision.
- **L-15.** Dead table `OSINT_TOOLS` in `main.py:3604-3622` names breach-data services
  (DeHashed, Snusbase, LeakCheck, IntelligenceX). No other reference to it (`grep OSINT_TOOLS`:
  one hit). Left from the Sentinel fork; delete it so the repo does not suggest the feature.
- **L-16.** `name-candidate-fusion-studio.md` is hashed into the pack although the approved
  rename is "Imprint Studio". The owner decides whether a dropped candidate stays in what he signs.
- **L-17.** Fonts: Georgia rasterised into posted graphics (`licences.md:125`, consult L12)
  still unchecked; EA2005 section 2E read 2026-11-22 (embedding per the font's own restrictions).
- **L-18.** `.venv` holds `PySide6_Pdf` and `PySide6_WebEngine` 6.12.0.140 beside PySide6
  6.11.2. QtWebEngine is not in the bundle; `QtPdf.framework` is. Recheck the bundle listing
  against the Qt GPL-only list after the pending PySide6 upgrade.
- **L-19.** Seller and business-name identification (register row 9) stays "unclear"; not
  triggered while nothing is sold. S.I. 68/2003 and RBNA 1963 not read.
- **L-20.** The playbook's body calls itself an unverified baseline while its header says
  `current`. A Foundry matter, not this app's.

## Gate status

`python3 docs/foundry/tooling/legal_gate.py --help` lists `status`, `check`, `sign`; `status` and
`check` are read-only. Output of `python3 docs/foundry/tooling/legal_gate.py status .`
(2026-11-22, exit 0):

```
tier: public
pack: 8 file(s), hash 051b81981cf7
last sign-off: wwds-dev (owner) 2026-11-21T22:00:27 pack 8b0becd4a572 [STALE: pack changed]
open lawyer trigger: Decide whether using "Imprint" as the name of public (and later paid) creative/publishing software conflicts with prior IMPRINT marks in classes 9/42 (US reg. 6673504 Imprint Payments; US reg. 8152294 Polywise "Imprint: Learn Visually"; US reg. 5858561 iRobot; pending US 98485147 Imprint Labs; UK application of 1 May 2025 in classes 9/41/42/others, per aggregators and the UK journal) and with any EU/Irish mark the owner's searches in `name.md` §4 turn up; and whether "Imprint" is registrable at all for publishing goods and services, where it is a descriptive industry term. Trigger: trademark conflict. Rule and register entries not verified at source.
open lawyer trigger: T1. Whether Imprint is "placed on the market" or "put into service", so that the owner is a provider under AI Act Art. 50(2) for synthetic audio and text, which marking measures would meet it, and whether the 2 Dec 2026 date in Art. 111(4) applies. Evidence: `services/narrator/converter.py:984-986,1015-1022`, `agents/manuscript/shorts_generator.py:49-59`, `services/release_kit/provenance.py`. Slice 1 only records AI facts. Commission guidelines C(2026) 5054 not read by an agent.
open lawyer trigger: T2. Whether publishing Shorts narrated with macOS System Voices on TikTok or Instagram to promote a book is outside EA2005 §2F. Evidence: `providers/voice/mock.py:69,76`, `services/release_kit/plan.py:59-60`.
legal gate: BLOCKED: legal pack changed since the last sign-off (wwds-dev, 2026-11-21)
```

`legal_gate.py check .`: same BLOCKED line, exit 1. `release_check.py .`: "BLOCKED: legal gate:
legal pack changed since the last sign-off (wwds-dev, 2026-11-21)", "do not build or publish",
exit 1.

**Open lawyer triggers (3):** the name; T1 (AI Act Art. 50(2) role, marking and date); T2 (macOS
System Voices in published Shorts). Proposed and not in the register: the Art. 5 trigger in
L-04; the amended name wording in L-06. T3 and T4 from the consult open with slices 2 and 3.

**What changed in the pack since the 2026-11-21 22:00 sign-off** (Foundry repo,
`git log -- audits/imprint/legal` and `git diff --stat cdd387a HEAD`): two files added,
`name-candidate-fusion-studio.md` (`6487043`, 2026-11-22 00:54) and
`name-candidate-imprint-studio.md` (`801596c`, 2026-11-22 03:43). The six signed files are
byte-for-byte unchanged; the pack went from 6 to 8 files. No uncommitted pack change was present
when checked. Outside the pack since the sign-off: `LICENSE` (MIT) added at 22:36 (`9f656a1`);
`SUPPORT.md` and `SECURITY.md` edited 2026-11-22 (`1cabc65`); the rename spec approved
2026-11-22.

**Residual risks if the pack is signed as it stands:** it would record "no licence" and an
unconfirmed tier (L-01); T1 and the Art. 5 date fall on 2 December 2026 (L-03, L-04); the name
searches are empty (L-06).

**The sign command** (the owner, in a terminal at the app root, after the Comply session's last
edit; it asks him to type the app's folder name). With triggers open, an owner sign-off needs
the risk accepted in writing:

```
python3 docs/foundry/tooling/legal_gate.py sign . --by wwds-dev --role owner --accept-risk "<why the open triggers are accepted until a lawyer decides>"
```

A lawyer's sign-off, which needs no `--accept-risk`:

```
python3 docs/foundry/tooling/legal_gate.py sign . --by "<lawyer's name>" --role lawyer
```

## Could not verify

- Reg. (EU) 2026/1744 and the consolidated AI Act at the primary source: EUR-Lex returned an
  empty page to the fetch tool. Arts. 5, 50, 111(4) and 113 rest on commentary; one source gives
  a different date. Commission guidelines C(2026) 5054 and the code of practice: not read.
- AGPL-3.0 text (HTTP 429), the Qt 6.11 licensing page, per-module Qt licences, PSF licence text.
- OpenAI Service Terms and Usage Policies, ElevenLabs Voice Library Addendum, Anthropic,
  DeepSeek, Moonshot, Alibaba, Higgsfield, Pexels, PublishDrive terms; ACX, KDP, Fiverr and
  Amazon review rules; Reddit Data API Terms (fetch refused); Pinterest developer guidelines;
  Google's list of restricted scopes.
- GDPR, Data Protection Act 2018, Consumer Protection Act 2007, Consumer Rights Act 2022,
  S.I. 336/2011, S.I. 68/2003, RBNA 1963, CRA, PLD, EAA: not re-read; the register's rows on
  them were not re-tested.
- EUIPO, TMview, Irish IPO, CRO, WIPO: not queryable by the agent; rows are for the owner.
- Whether a copy of `Imprint.app` was ever given to anyone; whether `cloud/` is deployed;
  whether any provider embeds a watermark or C2PA data that the app's re-encoding removes.
- "Nothing leaves this Mac" for local routes: from the code only, no network capture.
- No model was called and the test suite was not run, so no agent output was observed (L-07).
- Provenance of `assets/icon_source.png`; contents of `vidforge/assets/music/` on other machines
  (the installed bundle holds only its `README.md`).
