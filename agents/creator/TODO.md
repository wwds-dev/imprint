# Brand Creator — TODO

> **Legend** — priority `P0` critical · `P1` high · `P2` normal · `P3` low
> categories `security` `bug` `feature` `performance` `design` `docs` `testing` `infra` `research`
> owner `@me` (needs you — accounts, keys, money, judgement) · `@ai` (Claude can do this)
> agent `agent:<key>` (optional; only meaningful in a parent project's shared TODO.md — not needed here, this file already belongs to Creator alone)

---

## v1 — current

- [x] `P1` Move the Creator panel and handlers from `main.py` into this package. Done 2026-09-21: `panel.py` owns the profile form, consent-aware compose controls, all six tabs (Draft, Calendar, Earnings, Voice, Media, Agency) and every handler, with the drafting token on the panel and the Higgsfield teaser token in its job context — nothing resolves by the shared "creator" name (the teaser's old `or "creator"` record fallback is gone). The umbrella keeps thin delegates for tests, and the worker attributes its shutdown sweep watches; the teaser output dir moved off BASE_DIR onto the writable base.
- [x] `P1` Associate Creator work with a shared Project without changing account ownership. Done 2026-09-23: scheduled content and teaser job rows carry optional Project IDs; the draft's Project/account provenance is captured at approval, and scheduling refuses a different account. Uploaded media and successful teaser clips gain Project artifact links. Deleting a Project unfiles content/jobs but preserves accounts, consent, results and external media. Calendar/Media default to all account work and can filter to the current Project.
- [ ] `P1` Finish the calendar as a real week view with rescheduling and export.
- [ ] `P2` Turn revenue attribution into shared charts and drafting signals.
- [ ] `P2` Define a stable handoff contract for every venture using Creator.
- [x] `P2` Reuse the Video workspace's resume pattern (2026-09-22, `agents/video/jobs.py` + `VideoResumeWorker` + `restore_request()`) for `creator_video_jobs`: the table records every teaser transition but nothing reads it back, so a teaser render still dies with the process. Done 2026-09-28: the ledger gained spend_state/flat_cost_eur/output_path/run_id (pre-feature rows keep '' and are never reconciled), every new teaser row is 'reserved' from its first upsert and settled 'billed'/'released' beside record/abandon, and `resume_pending_teasers()` (startup, one pass per process) re-polls reserved rows with the shared `VideoResumeWorker`, lands the clip in the media library, bills once through `restore_request()`, and applies the same honesty rules — timeouts and local exceptions keep the row reserved, provider verdicts release it, provider-completed-but-unsaved is billed. Six focused tests incl. full reconciliation billing. Known limit: a crash between the create POST and the provider's reply leaves no request_id and therefore no row (the ledger is keyed by request_id).
