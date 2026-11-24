# Re-review: ai-act-safeguards fixes (f80f9fc)

Reviewer: `code-reviewer`, read-only, independent of the author (saved by the orchestrator).
Ran: `pytest -q -p no:randomly tests/test_content_policy.py tests/test_image_routes.py
tests/test_herald_clip_provider.py tests/test_media_generation.py` → 77 passed; about 100 prompts
through `refused_key` at f80f9fc and 9a1d8e5.

## Earlier P1s
| Finding | Status | Evidence |
|---|---|---|
| CR P1-1 / QA P1-2 / Sec P1-1 vidforge OpenAI scenes and topic | Fixed | `vidforge/vidforge/visuals.py:66-71` checks the sent string before both routes; topic checked before `authorize_request` (`agents/video/panel.py:525-534`, `agents/social/panel.py:606-614`); tests |
| CR P1-2 / QA P1-1 watermark test | Fixed | `tests/test_media_generation.py:162,188` expects `True` |
| CR P1-3 README/CHANGELOG | Fixed, small leftover (P3-1) | `README.md:2330-2342`, `CHANGELOG.md:33-38` |
| Sec P1-2 word forms | Fixed | every security-report case refused, plus "deep fakes", "faceswapped", fullwidth, U+200D/200B/00AD |

## New findings
**P0:** none. **P1:** none.

**P2-1. Tighter negation refuses ordinary safe-for-work wording, Higgsfield included.** "no gore or
nudity", "without text or nudity", "nothing explicit or sexual", "avoid nudity and explicit scenes",
"no explicit/sexual content", "free of any nudity" and others passed at 9a1d8e5 and are refused at
f80f9fc (`services/content_policy.py:72-77`). No Imprint-written prompt is affected
(`agents/creator/agent.py:147-152`, `agents/fiverr/agent.py:36-39`, `vidforge/config.yaml:40-42`,
`vidforge/vidforge/script.py:75-92`). Fix: allow a coordinated list after a negation and a filler
after a negation phrase; keep "no watermark nude photo", "no captions, nude model", "not shy and
naked" refused.

**P3-1.** README/CHANGELOG say "before anything is reserved" for the Herald clip topic and Vector's
logo prompt, whose text call is already billed. **P3-2.** `sexual\w*`, `nude\w*`, `naked\w*` refuse
"sexuality", "sexually transmitted", "nakedness" in newly checked topics. **P3-3.** "non-explicit",
"no-nudity" refused (`[a-z-]+` tokenising; predates the commit). **P3-4.** Creator Higgsfield route
sets no status line and has no panel test. **P3-5.** An empty narrated-video topic skips the entry
check (vidforge picks one; scene check only).

## Checked and found correct
vidforge refusals are always caught (`render_scenes`, `thumbnail.render`, pipeline); the ImportError
guard skips only standalone vidforge. `VideoPanel.render`, social `_on_clip_brief` and Fiverr
`_on_prompt_ready` leave tokens, buttons and workers consistent; the already-paid text calls are
recorded before the check, correctly; Apply recursions do not double-bill.

## Not verified
Full suite; ruff ratchet; the author's mutant claim; live UI and providers; the watermark's look.

## Orchestrator's follow-up (2026-11-24, next commit)
P2-1 fixed: a negation reaches across a list of up to three items joined by or/nor/slash, and by
"and" only when the dropped item is itself a refused term (so "not shy and naked" stays refused);
one filler is allowed after a negation phrase. P3-1 reworded; P3-2 narrowed to `nudes?`, `naked`,
`sexual`; P3-3 fixed (a hyphen ends a word); P3-4 status line and panel test added. P3-5 stays in
the TODO P3 row. Trade-off: "no text or nude photo" reads as negated.
