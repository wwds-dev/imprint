# Secure: reference-photo-consent (D2, option A′)

Reviewed commit `4296091` on `claude/silly-raman-4ddd34`, 2026-11-24, by the `security-engineer` agent (read-only;
transcribed here by the build session). No P0/P1. No dependency audit (no manifest changed).

Coverage: `reference_images` is used only in `agents/creator/panel.py`. The Higgsfield gate runs before key, permission,
prompt check and the estimate worker's upload; the Gemini/Wan gate before `VideoGenerationWorker`, and again on the
assessment re-entry. Resumes (`VideoResumeWorker`) send no photos. `current_account()` re-reads the row on each call.
`consent_holder` and `consent_note` never reach a prompt (`agents/creator/agent.py:51`, `:127`) or a log. Deleting an
account deletes the record and the photo list.

## P2
1. **Any local file can be sent as a "photo".** Wan and Gemini read whatever path is listed and send its bytes
   (`services/qwen_client.py:195-204`, `services/gemini_client.py:119-134`); no extension or magic-byte check, symlinks
   followed; Higgsfield checks the extension only (`services/higgsfield_client.py:250-257`). A mistyped or pasted line
   such as `.env` goes to the provider. New exposure: this commit adds the first editor for the list. Fix: absolute
   path, regular file, not a symlink, image extension and image magic bytes, on save and before sending.
2. **The gate reads the saved subject, not the form.** Photos saved under Me, picker switched to Someone else and not
   saved: the teaser sends them while the form shows empty consent fields. Fix: refuse while the Reference photos group
   has unsaved changes, or gate on the form's values too.
3. **Docs contradict the code.** `docs/learn/modules/28-creator.md:13,128` and `agents/creator/README.md:7` say
   consent records live in Backstage; spec measure 3 not met yet.

## P3
4. `NO_RECORD_NEEDED` lets `""` and `None` through (`agents/creator/profile.py`), against its own fail-closed docstring;
   only a hand edit can reach it (column `NOT NULL DEFAULT 'own'`). Allow only `own` and `persona`.
5. Any non-blank name counts; a future date is accepted; a hand-edited date is not re-parsed by the gate.
6. Wording: "Sent to the video service with every teaser" is not true for Veo (refuses photos). T5's note for the
   lawyer should say the record is the user's statement, not a check (no change under `docs/legal` here).

## Disposition (build session)
See the review report `docs/audit/reference-photo-consent-code-reviewer.md` for what was fixed in which commit.
