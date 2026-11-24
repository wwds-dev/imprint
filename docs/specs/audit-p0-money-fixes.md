# Spec: audit P0 money fixes QB-2, QB-3, QH-2

Needs: build, review, secure, verify, docs

Status: Built 2026-11-24 (`2a66694`). Priority: P0 (`docs/audit/SUMMARY.md` findings 1–3).
Type: bug fix on paid paths, restoring promised behaviour; no new feature, so no Define gate
(the owner's brief of 2026-11-24 asks for review and security passes instead). Owner session:
`claude/angry-matsumoto-ac520a`.

## Problems and fixes
- **QB-2 Booth.** After the book's text changed, Start authorized only the unpaid share of the
  estimate (`conversions.remaining_fraction`), while the converter discards its cache on a
  `text_sha256` mismatch and narrates the whole book. Fix (panel side; the shared converter is
  untouched): the conversion row stores the sha256 of the extracted text (`source_sha256`, new
  column with migration). A different hash, or for a row from before the column a file modified
  after the row was last touched, asks "Book changed since the interrupted run" and, on Yes,
  starts fresh at full cost; No sends nothing.
- **QB-3 Herald.** A clip was authorized as `openai` whatever drew its scene images; Apply could
  pick Gemini or Qwen with that provider unticked. Fix: the Video tab's key and permission check
  is now `agents/video/panel.py:scene_provider_refused`, used by both, before the clip's
  confirmation and authorization.
- **QH-2 Reel.** Gemini Omni renders in one synchronous call. Stop returned before the paid clip
  was written, and the next launch could not resume Omni, so the row failed every launch. Fix:
  Stop is not offered once an Omni render is submitted (the status says why); a shutdown cancel
  still writes the returned clip; the next launch settles an Omni row without a worker: a saved
  clip lands and bills once, a completed clip that never reached the disk bills and says so, and
  anything else releases its reservation.

## Success measure
Tests that fail on `776828d` and pass after: `tests/test_booth_source_changed.py`,
`tests/test_herald_clip_provider.py`, `tests/test_reel_omni_stop.py` (fakes only; no network or
key). Full suite green.

Skipped phases: Define and Design (restores the behaviour the UI already promised), Architect
(one additive column, no thread or boundary change), Comply and Launch (no legal or public-claim
change).
