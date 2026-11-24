# Spec: Consent record before a person's reference photos are sent (D2)

Needs: define (owner gate), then architect (small), build, review, verify, secure, docs

Status: **Define approved 2026-11-24 (option A); Build on `claude/silly-raman-4ddd34`.** Owner's words: "D2: A, own accounts need no record, include it in the next release. Titles deferred: yes. Walk: a later session. ADR 0002, 0003 and the Define: approved as built." (`docs/foundry/approvals.jsonl`). Deferred as D2 of `docs/specs/ai-act-safeguards.md`; TODO.md P2 `security` `@me`. Not started by any
other session (`session_start.py --inflight`, 2026-11-24).

## Problem
The Nova teaser sends an account's reference photos to Wan, Gemini Omni or Higgsfield
(`agents/creator/panel.py:1132` Higgsfield, `:1260` Wan and Omni; `ui/workers.py:410-412`;
`services/qwen_client.py:471`, `services/gemini_client.py:328`). Nothing checks whose face is in the photos or
whether that person agreed. The accounts table has `account_type` (`own`, `managed`, `persona`) and
`consent_holder`, `consent_date`, `consent_note` (`services/database.py:244-255`); its comment says the panel
refuses to work for a managed account until consent is filled in. **No code reads those columns.** Lawyer trigger
T5 (`docs/legal/register.md`) asks whether "the unused consent fields matter" for the AI Act Art. 5(1)(ba)/(bb)
safeguards (reported to apply from 2 Dec 2026).

## What is true today (verified 2026-11-24 in this tree)
- The only place photos come from is `creator_persona.reference_images`, one path per line
  (`agents/creator/profile.py:154-156`). `save_persona` accepts the field, but **no panel field edits it**
  (`profile.py:108` says "reference_images has no editor yet"; the persona form saves only the text fields,
  `panel.py:1838-1845`).
- The Creator panel creates accounts with the table default `account_type = 'own'` and has **no control** for the
  type or for the consent fields (`panel.py:570-590` inserts handle and platform only).
- So a photo reaches a provider today only if it was written into the database by hand or by an older build, and
  the account is then an `own` one. The exposure is latent, not a path a normal user walks. That is also why the
  consent check cannot simply "read the fields": there is nothing to read until the panel can set them.

## Options (recommendation first)
**A. Gate on `managed`, add the missing controls (recommended; about 2 h).**
1. The account form gets an account-type box (own / managed / persona) and, for managed, the three consent
   fields; the persona form gets a reference-photo list.
2. Before a teaser sends photos: type `managed` with an empty `consent_holder` or `consent_date` refuses with a
   dialog naming the missing field ("Not sent: consent record missing"), reserves nothing and writes no job row
   (same place and pattern as the content policy check, `services/content_policy.py`). Types `own` and `persona`
   send as today. A refusal row is not written to `creator_video_jobs`.
3. The consent record is stored per account only; the job row gains no copy (a later change of the record would
   then rewrite history). Tests: refusal per missing field, pass when both set, no gate for own and persona, no
   reservation on refusal, the form saves and reloads the fields.

**B. Attest on every send (about 3 h).** Every teaser that includes photos asks once per send: "The person in
these photos is me, or agreed to this use" and stores the answer and time on the job row. Covers `own` too, at
the cost of a dialog on every teaser, and the user can click through.

**C. Keep it a TODO.** No change; T5 goes to the lawyer with "the consent fields exist but nothing reads them".
Honest, cheapest, and the exposure is latent today (above). It leaves the safeguard story at "prompt words only".

## Owner's choice: A′ (2026-11-24)
While building A, the build session found that on 30 Sep 2026 the owner moved the account-type and consent model
out of Nova into Backstage (`README.md` "What moved to Backstage", `agents/creator/agent.py:24`), and that
Backstage shares no data with Imprint. Asked, the owner chose **A′** ("Build A′", `approvals.jsonl`, decision):
- No account-type model in the profile form. On Voice → **Reference photos** (shown for every account, since
  every teaser route sends the photos) the user lists the photos and says **who is in them**: Me, A made-up
  character, or Someone else. Someone else shows **Who agreed**, **Date they agreed** (year-month-day,
  validated) and an optional **Note**.
- Stored in the existing columns, no schema change: `account_type` `own` / `persona` / `managed`,
  `consent_holder`, `consent_date`, `consent_note`; the photos in `creator_persona.reference_images`. Choosing
  Me or a character clears the record. A value no build writes counts as Someone else (fails closed).
- The character bible shows for A made-up character (as before for `persona`); hidden is not deleted.
- The check (`agents/creator/profile.py` `photo_consent_refusal`, called by `CreatorPanel._photo_consent_ok`)
  runs in `generate_video` before any key, permission, estimate or budget step (Higgsfield uploads the photo
  while it prepares its estimate), and again in `_generate_direct_teaser`. A refusal shows "Consent record
  missing", sets "Not sent: consent record missing.", authorises nothing, writes no job row and starts no worker.
  Resumes of an interrupted render send no photos and are not gated. No architect phase: no new state, thread
  or boundary.

## Success measures (for A, kept for A′)
1. A managed account with a missing consent field cannot send a photo: tested, no provider call, no reservation.
2. Own and persona accounts are unchanged (existing teaser tests green).
3. The README's Nova section and the Learning Centre say what the record is for; it claims no more than the
   check does (it records that the user says consent exists; it verifies nothing about the photos).

## Not in scope
- Checking the photos' content (faces, age, nudity) or whose face it is: needs a classifier and a lawyer's view;
  the content policy deliberately stays a narrow word list.
- Anything in `docs/legal`: a change there needs a fresh owner sign-off; this spec edits none.

## Owner decision (Define gate; the owner decides, an agent records the words, never earlier)
1. **Which option: A (recommended), B or C?**
2. If A: should `own` accounts also need `consent_holder` set (the user's own name)? Recommended: no, own and
   persona accounts send without a record.
3. If A or B: does the 2 Dec 2026 date make this part of the release after v2.509, or can it wait for T5's answer
   from a lawyer first? (T5 is open; this spec does not close it.)
