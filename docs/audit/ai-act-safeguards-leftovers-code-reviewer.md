# Code review: ai-act-safeguards leftovers (Review, 2026-11-24)

Role: code-reviewer (read-only; a different agent from the author). Scope: the uncommitted diff of the leftovers pass on
`claude/practical-dhawan-a2226d`: refused scene and thumbnail images not billed, the creator backstop row, the worker
test. Playbook `code-reviewer.md` `last-reviewed: 2026-10-14` (not stale). The reviewer had no write tool; the author
saved this report and added the dispositions. Tests at review time: 135 passed (three files, `-p no:randomly`).

## Findings and what was done

| # | Sev | Finding | Disposition |
|---|---|---|---|
| P2-1 | P2 | A refused **thumbnail** prompt (`vidforge/thumbnail.py`) is caught and drawn as a gradient but never counted, so a finished render still bills that image and a failed one after the thumbnail stage bills it too. | **Fixed.** `thumbnail.render(..., reporter)`, called with the pipeline's reporter; the refusal is counted in the same `refused` key. Tests: `test_a_refused_thumbnail_prompt_is_counted_too`, `test_the_thumbnail_stage_gets_the_reporter`. |
| P3-1 | P3 | `record_request(bill_flat_eur=NaN)` billed €0 (`min(flat, max(0, nan))`), the opposite of `record_partial`. No live path found. | **Fixed.** A non-finite or non-numeric figure bills the confirmed flat; the panels pass a credit only when the estimate total and rate are above 0. Test: `test_record_request_bills_the_confirmed_flat_for_a_figure_that_is_not_a_number`. |
| P3-2 | P3 | Copy says refused scenes are listed in the log and off the cost "on success and on failure"; Social has no log pane and the failure notice did not name them. | **Fixed.** `partial_render_notice` appends the refused-scenes note; Social shows it in the status tooltip. Test: `test_the_failure_log_names_the_refused_scenes`. |
| P3-3 | P3 | The creator panel detects the backstop refusal by the prefix "Not sent: ", which `services/validator.py:51` also uses for budget refusals (not reachable in `_video_error` today). | **Fixed.** `VideoGenerationWorker.refused` is set only by the content-policy backstop; the panel keys on it. Tests pin the flag on the worker and in the panel. |
| P3-4 | P3 | `note_refused` ran before the gradient card was written (a failed card would be counted as a refusal); a host reporter that raises would abort the render; a future resume would count a cached refused gradient card as a saved image. | **Partly fixed.** Counted after the card is drawn, host failures swallowed (`visuals.note_refused`). The resume case is not reachable (no panel passes `resume_slug`) and is left as a TODO row. |
| P3-5 | P3 | The exception was matched by exact class name. | **Fixed.** Matched over the class's MRO (`visuals.is_policy_refusal`); by name because vidforge cannot import Imprint's class when it runs alone. |
| P3-6 | P3 | No panel-level test of `_on_pipeline_error` / `_on_clip_render_error` with a refused count; no test that a second render does not inherit the last trace. | **Deferred (TODO P3).** The pure functions and both success paths are tested; the lifecycle was read and found correct (the trace is popped in `_on_done` and the error handlers and reset at each start). |

## Checked and found correct (reviewer)
No double billing (the credit applies only when a refusal was counted; a trace without one bills the confirmed flat
as before); rounding and caps (`record_request` takes the lower of confirmed and credited); `per_image == 0`
(pexels, gradient) credits nothing; the external Video paths reach `_on_done` with `_active_kind != "pipeline"`, so
no credit; the trace is sent before done and error on the same thread; `_refused` is written on the worker thread
only; vidforge standalone: no Imprint import, `note_refused` is a no-op on the base reporter, no other copy of
vidforge needs a drift test; the creator row query no longer picks up a `released` + `failed` row.

## Verify notes (author)
Mutation check, 17 mutants over the new lines (file:line by name in the commit message): 17 of 17 killed after two
tests were added (the worker's real `refused` flag; the pipeline passing its reporter to the thumbnail). Not verified:
a live render with a refused scene (needs provider keys and spends money).
