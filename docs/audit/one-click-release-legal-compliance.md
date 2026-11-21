# Comply: one-click-release, slice 1 (free path)

Role: `legal-compliance`. 2026-11-21. Spec `docs/specs/one-click-release.md`, tier `public`
(`docs/foundry/app-context.md:10`), branch `claude/one-click-release-slice1-599646` at 403385f.
**Not legal advice. Not a sign-off.** No agent has signed; `legal_gate.py sign` was not run and
`signoff.jsonl` was not touched. Rules were taken from `docs/audit/one-click-release-legal-consult.md`
(read there 2026-11-18) and a 2026-11-21 radar search (`docs/foundry/radar-notes/2026-11-21-legal.md`,
commentary only); I did not re-read primary texts.

## Verdict
- **Slice 1's claims match the code** (table below). Nothing in slice 1 sends data off this Mac, charges, or posts.
- **Pack updated** (Foundry HQ, `audits/imprint/legal/`): register rows 19-22, lawyer triggers **T1** and **T2**, new sections in `privacy.md`, `ai-act.md`, `licences.md`. All still `DRAFT`.
- **The gate is BLOCKED** and must stay so until a person signs. Open lawyer triggers: name (earlier), T1, T2.
- **Coordination:** Secure's verdict is "ready for Comply: yes" (re-check 403385f). `git log --all` since 20:30 shows no newer Secure commit. The second `secure start` (21:02:05) has no `done` and no report; if that session commits a different verdict, this report must be redone.

## What the owner must decide or sign
1. **Sign-off** of the pack (owner, in a terminal; lawyer if a trigger stays open). Not done by me.
2. **T1** (lawyer): Is Imprint placed on the market or put into service, and what marking does AI Act Art. 50(2) then need? Commentary (not verified) puts 2 Dec 2026 as the end of the grace for systems already on the market; that is 10 days away. Slice 1 only records AI facts.
3. **T2** (lawyer): are macOS `say` voices allowed for Shorts posted publicly (EA2005 §2F)? Slice 1 posts nothing; decide before any kit Short is posted.
4. **N5 wording** (owner): see below.
5. Release blockers outside this feature, still open from the earlier pack: no `LICENSE`, no `SUPPORT.md`, no private security contact (`ls LICENSE* SUPPORT.md SECURITY.md`: no match).

## Claims against the code
| Claim | Where it is made | Evidence | Result |
|---|---|---|---|
| "On this Mac" | `plan.py:176-180,209,231`, `report.py:49,122`, `confirm_dialog.py:251` | `endpoint_problem` rejects any non-loopback host (`plan.py:72-100`); local clients pass `proxies=NO_PROXIES` (`ollama_client.py:69,86,124,160,198,220,249`), so S-1 is closed; voice is `say`; no other network call in `services/release_kit/*.py` (grep `requests.|urlopen|smtplib|webbrowser|publish|post(`: none). Residual: `localhost` trusted by name (security S-8, P3). | Matches |
| "No charge" / "local, no charge" | `plan.py:54,176`, `report.py:64-70`, `window.py:204-206`, `confirm_dialog.py:245-251` | Slice 1 has no paid route; Security says the money guard holds (`one-click-release-security-engineer.md`, "Re-check"). Means no money to a provider. It does not say the model or voice licences allow every use (T2). | Matches; keep wording as is |
| "Nothing was posted, scheduled or submitted." | `report.py:163` (hard-coded last line) | No posting code in `services/release_kit` or `ui/release_kit` (same grep). Text is constant, so it would stay true only while no posting is added. | Matches today; a future posting slice must change this line |
| "AI used in this kit" | `report.py:74-87,152`, `provenance.py:27-46`, CSV `provenance.py:49-58` | Quotes and captions flagged AI; Shorts "synthetic voice"; EPUB and graphics "without an AI model" (Pillow, `quote_graphics.py:74-118`). Facts only, no claim of marking. | Matches the draft N4 wording |

## Items checked
- **N5** (`plan.py:61`, shown at `window.py:228`): reads "This kit contains AI-generated captions and quote choices. See the report." The consult draft (`legal-consult.md:58`) said "AI-generated narration and captions". Build dropped narration (none in slice 1) and added quote choices. It appears only in the Release Kits window, not in the report. It states a fact and makes no legal claim; I flag it as a wording change for the owner to accept, not as cleared. A narration route (slice 2) needs the wording changed again.
- **N2** (`plan.py:59-60,255`, `confirm_dialog.py:119`, `report.py:154`): shows on the confirmation screen and, always, in the report. It restates §2F accurately per the consult. The report prints it even when Shorts are skipped (minor, P3).
- **AI-use facts and marking:** recorded in three places; nothing is embedded in MP4, PNG, EPUB or CSV metadata. Embedded marking waits for T1 (spec A10 item 7, owner-approved 2026-11-18). Art. 50(4) duties sit with whoever posts; commentary says provider marking does not discharge them.
- **Personal data:** ledger in `imprint.db` holds quotes, captions, the frozen project instructions and output paths (`ledger.py:80-85`). **Discard keeps them** (`driver.py:153-156`; `ledger.py:29-32` has no delete). `report.py:158` and `provenance.py:66` write absolute paths with the macOS user name (S-9, P3 open). Recorded in `privacy.md` §7. Nothing leaves the Mac. Whether a delete option is needed is the owner's call; I suggest a TODO.
- **Licence inventory:** no new dependency (`git diff 3e0a761..HEAD -- requirements*.txt pyproject.toml`: empty). New entries: macOS voices (§2F) and Georgia (§2E, embedding limits not checked) in `licences.md` §7.
- **Marketing claims** (consult L11): none added; README and spec wording stays factual. Keep "overnight" and "make everything I need" out of public copy.
- **Not in scope for slice 1:** L3, L4, L6, L7, L8 and T3/T4 (paid narration, ElevenLabs, cloud chat routes); recorded for slices 2 and 3.

## Open items
| Item | P | Who |
|---|---|---|
| Sign-off of the pack; pack sections are `DRAFT` | gate | owner / lawyer |
| T1 AI Act marking role and date | P1 | lawyer |
| T2 macOS voices posted publicly | P1 | lawyer + owner |
| Name trigger (earlier) | P1 | lawyer |
| `LICENSE`, `SUPPORT.md`, security contact | P1 for Release | owner |
| N5 wording after slice 2 | P3 | owner |
| Discard keeps ledger text; absolute paths (S-9) | P3 | owner / engineer |

## `legal_gate.py check` (run in the main checkout, whose `docs/legal` points at the pack)
```
legal gate: BLOCKED: no legal sign-off recorded
tier: public
pack: 6 file(s), hash c3de3f079085
last sign-off: none
open lawyer trigger: (name) ...
open lawyer trigger: T1. Whether Imprint is "placed on the market" ...
open lawyer trigger: T2. Whether publishing Shorts narrated with macOS System Voices ...
```
(Full text of the three triggers is in the HQ `register.md`. From this worktree the gate says "no legal pack" because `docs/legal` does not exist here; the pack hash changes with every edit, so a sign-off must follow my last edit.)

Stopped at the sign-off gate.
