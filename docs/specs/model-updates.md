# Spec: Model updates, closing the gap to Sentinel

Status: DRAFT, awaiting owner approval (Define gate)

Defined 2026-11-22. Priority: P2 (feature; slices below carry their own). Tier: `public`.
Owner's request, 2026-11-21: the app "needs also a model updating feature like sentinel has".
Product-manager playbook: `status: current`, last-reviewed 2026-10-14 (39 days, not stale).
Not run by this session (no shell): `session_start.py --inflight`, `log_activity.py`, `/radar-check`.
The orchestrator runs them before the gate. Written as "Imprint"; nothing here depends on the rename.

## Challenge: the feature already exists
Imprint has had Model updates since October 2026 (`TODO.md:178`, `:177`, `:121`, all done;
`README.md:435-545`). It is not a copy of Sentinel's: it was rebuilt on Imprint's own ranking, and in
most respects it does more. A port of Sentinel's `ui/model_updates.py` would **remove** function
(removed-model warnings, the video and image section, shutdown dates) and is not proposed.

What the request can still mean is narrower: three things Sentinel's does that Imprint's does not
(G1, G2, G3 below), one promise neither app keeps (G6), and the fact that Imprint's tile is easy to
miss: it sits in a section that is collapsed by default (`main.py:3495-3496`), while Sentinel's is an
always-visible card in the left rail (`../sentinel/main.py:3203-3207`). Question 1 asks which of these
the owner meant. The smaller version proposed here is slice 1, not a new feature.

## What Sentinel has
**As the user sees it** (`../sentinel/docs/training/api_keys.md:115-216`, `README.md:97-103`):
a MODEL UPDATES card in the left rail showing the last check, which ratings are in use, and one row
per new model. A check runs 4 s after every start (`../sentinel/main.py:477`) and on **Check now**.
It asks only providers with a key **and** a ticked permission box, and none in Local only
(`services/model_watch.py:130-149`). Rows are clicked to mark them; **Update N** brings in exactly
those. **Review details** opens a dialog with, per model, what adopting would change (which agents'
BEST FIT moves, from which model, why) and **Adopt** / **Dismiss** (`ui/model_updates.py:277-377`).
New models wear a NEW badge in the dropdowns. Cost: nothing; listing is free and sends no prompt.
Never without the user: no BEST FIT or selection moves until Update or Adopt
(`ui/model_updates.py:3-6`); "newer counts for nothing" (`:295-296`).

**As code:** `services/model_watch.py` (616 lines: `list_live` :152, `infer_profile` :203, `beats`
:303, `assess` :342, `ModelWatch.record_scan` :471, `adopt` :552, `install` :566);
`ui/model_updates.py` (card and dialog); `ui/workers.py:882-923` `ModelScanWorker`, one `QThread`,
providers one after another, then the ratings refresh; `main.py:1600-1814` wiring. State:
`data/model_watch.json` (`seen`, `new`, `adopted`, `dismissed`, `last_scan`, `last_notes`) and the
ratings cache. Network: each provider's model-list endpoint, and
`datasets-server.huggingface.co/rows` (`services/benchmarks.py:54`). Shutdown names the worker
(`main.py:5972-5982`). Tests: `tests/test_model_watch.py` (34), `tests/test_benchmarks.py`.

## What Imprint has
`services/model_watch.py` (508 lines, a different class with the same name: `observe` :224,
`observe_media` :244, removals :302-357, `acknowledge` :407), `services/model_watch_digest.py`,
`ui/status_cards.py:384-604` (`ModelUpdatesCard`), `ui/workers.py:652-741` (`ModelScanWorker`,
`RatingsWorker`, both Python daemon threads, `:132-179`), `main.py:4793-5310`. State:
`data/model_watch.json` (ADR 0001, additive v1). Tests: `tests/test_model_watch.py` (43),
`tests/test_model_watch_media.py` (71). Same two network targets as Sentinel
(`services/benchmarks.py:62`). `closeEvent` names `model_scan_worker` (`main.py:6506`).

## Gap table
| Capability | Sentinel | Imprint |
|---|---|---|
| Check at start and on Check now, off the UI thread | `main.py:477`, `ui/workers.py:882` | has: `main.py:443-444`, `ui/workers.py:652`; plus a switch to turn the start check off (`main.py:5163`), which Sentinel lacks |
| New-model rows, mark, Update N | `ui/model_updates.py:57-255` | has: `ui/status_cards.py:509-588`, `main.py:5096-5161` |
| NEW badge in dropdowns | `main.py:1578-1587` | has: `main.py:5221-5227` |
| Ratings line with credit | `main.py:1679-1689` | has: `ui/status_cards.py:474-478`, `:600` |
| Value, not novelty | `services/model_watch.py:303-330` | has, stricter: a lead of one point or nothing (`main.py:5126-5139`); unrated and unpriced are said so on the row (`ui/status_cards.py:341-359`) |
| Removed models, video and image lane, shutdown dates, Seedance path check | missing | has (spec `model-watch-media.md`) |
| **G1 Review every new model, one at a time, with the evidence** (what it would replace, why, Adopt/Dismiss each) | `ui/model_updates.py:277-377`, `services/model_watch.py:342-388` | **missing.** The tile paints 5 rows (`ui/status_cards.py:393`, `:528`); the rest are "+N more" (`:537-542`) and cannot be marked. Dismiss is all-or-nothing (`main.py:5081-5087`), although the state already supports pairs (`services/model_watch.py:407-427`). A row says "Best choice for Quill" but not which model it would replace or at what price. |
| **G2 The check contacts a provider only when a request could** | `services/model_watch.py:130-149`, `main.py:1609-1618` | **missing.** Every provider with a key is asked 4 s after launch, in every mode (`main.py:4911-4918`), although the mode box and permission chips exist (`main.py:2678`, `:4243-4250`) |
| **G3 Switch off the public ratings fetch** | `main.py:136`, `:1591-1598` | **missing**: fetched whenever the cache is a day old (`main.py:4958-4977`) |
| G4 Why a provider was not checked, kept across launches | `services/model_watch.py:484-515`, `ui/model_updates.py:41-54` | partial: this session only (`main.py:4925-4926`) |
| G5 Says so in the status line when a check finds something | `main.py:1648-1652` | partial: a count in a collapsed section's title (`main.py:5267-5272`) |
| G6 Give a new model its own price | not possible in the UI (`../sentinel/docs/qa_audit/shared.md:106`, PARTIAL) | the tile tells the user to do it (`ui/status_cards.py:356-358`), but Settings → Pricing lists only shipped ids and existing rows (`services/pricing_catalog.py:91-92`). Whether a live-only id can get a row: **not verified** end to end |
| Adoption registry, first-check "newer release of a known family" rule | `services/model_watch.py:238-249`, `:552-596` | not needed, not proposed: Imprint ranks every listed model already (`main.py:5076-5078`), and its first check is silent by design |

## Problem
Who: the owner, the app's one user, deciding whether a newly listed chat model is worth moving an
agent to. How it hurts: (1) with more than five new models, the sixth onward cannot be marked or
judged, and the only way to clear one notice is to clear them all; (2) the tile gives a verdict
without the comparison behind it, so the owner has to trust "Best choice for" or open three places
(the agent's model menu, Settings → Pricing, the ratings) to check it; (3) in **Local only** the app
still contacts every cloud provider with a key at launch; (4) the tile's own advice on an unpriced
model may not be followable (G6). Evidence: the file:line references in the table. No usage data
exists; the app has one user and no telemetry.

## Target user and question
The owner, after a check reports news: "Is this model better value than what each agent uses now,
on what evidence, and what exactly changes if I say yes?"

## What the user sees (plain words; Design refines)
- The tile gains **Review details**. It opens a window listing **every** new chat model.
- Each entry shows: provider and id; first seen; for each agent it would change, the model the agent
  is on now and the two compared (rating for that kind of work, or "Not rated yet"; price per 1M
  tokens with its source: own rate, a dated snapshot's rate, the provider's default, or "unknown");
  and one sentence: "Would move Quill and Press from X" or "Would change nothing: current picks are
  as good for less, or better."
- Per entry: **Update** (moves only the agents listed, exactly as Update selected does today) and
  **Dismiss** (clears that one notice; the model stays in the menus).
- In **Local only** the check asks no cloud provider and the tile says so.
- Nothing is ever switched by a check, by opening the window, or by a model being newer.

## Goal and success measure
Every new chat model can be judged and decided on its own, with the comparison in view, and no
check or review ever changes a selection. Measured by offscreen tests with fake clients (no network,
no key, no paid call), in a new `tests/test_model_review.py`:
1. **8 of 8, today 5 of 8.** With eight pending models, the review lists eight, each with its own
   Update and Dismiss. Dismissing one leaves seven pending and clears that model's NEW badge only.
2. **Evidence is complete and honest.** Each entry carries a rating or "Not rated yet" and a price
   with its source. A price of zero or a missing row reads "unknown", never "free" or 0.
3. **One verdict.** For the same fixture, the review, the tile row and the BEST FIT badge name the
   same agents (asserted equal; they come from one call).
4. **Nothing moves by itself.** Every agent's provider and model box is identical before and after:
   a check, opening and closing the review, a Dismiss. Update moves only the listed agents.
5. **No recency.** Two candidates equal in rating and price, differing only in version number and
   first-seen date: neither displaces the other, and the incumbent keeps its pick.
6. **Local only.** With the mode on Local only, every fake cloud client records zero calls from a
   check, at start and on Check now (if question 2 is approved).
7. **No fetch, no spend.** Building and using the review calls no client method (fakes raise) and
   `authorize_request` zero times.
8. The 114 existing tests in `tests/test_model_watch.py` and `tests/test_model_watch_media.py` pass
   with no assertion changed.

## Non-goals
- Porting Sentinel's `ui/model_updates.py`, `services/model_watch.py`, its adoption registry or its
  first-check rule. Automatic switching of any model, in any slice. A "newer wins" tie-break.
- New providers, new endpoints, any billed test or probe call.
- Adding newly found image or video models to the Video menus: `services/media_catalog.py` stays the
  only source of what can run (owner decision, `model-watch-media.md`). Music: there is no model
  call to watch (Suno is a link, `docs/foundry/app-context.md:97-98`).
- Moving the tile or redesigning the rail (`SUGGESTIONS.md` #82 covers that question).
- Adding a model id by hand (`SUGGESTIONS.md` #56, still CONSIDERING).
- EU AI Act Art. 50: out of scope, this generates and publishes no content. CRA: no change to
  commercial availability.

## Slices
**Slice 1 (P2): Review details, and Local only is honoured.** Chat models only: the one kind with a
ranking and an Update today. G1 in full, G2 for Local only, G5 as one status-line sentence.
- New `services/model_review.py` (Qt-free: builds the entries from the existing engine results,
  prices and ratings; all copy lives here so each line is a unit test).
- New `ui/model_review.py` (the window; paints, decides nothing).
- Edit `ui/status_cards.py` (the Review details control), `main.py` (open it, per-model dismiss
  through the existing `acknowledge(pairs)`, the Local only gate in `check_for_new_models`).
- New `tests/test_model_review.py`. Docs: `README.md` §Model updates, the Learning Centre page,
  `CHANGELOG.md`, `TODO.md`.
- Size: 2 new modules, 1 new test file, 2 edited modules, 4 docs. No new state key, no new thread,
  no new dependency, no new endpoint, no change in Sentinel.

**Slice 2 (P2 for G6, P3 for the rest): a price for a new model, and two small parities.** First
verify G6; if confirmed it is a promise the app does not keep, which is this app's current goal.
Then: a live-listed id can be given its own rates from the review (it opens Settings → Pricing on
that row); a switch for the ratings fetch, default on (G3); the reason a provider was not checked is
kept across launches (G4, one additive state key under ADR 0001). Size: about 4 edited modules
(`services/pricing_catalog.py`, `ui/dialogs.py`, `main.py`, `services/model_watch.py`), tests.

**Slice 3 (P3, useful before 2027-01-06): speech routes in the tile.** Speech models are not
watched (`SUGGESTIONS.md` Done #60). The default narration model is removed by OpenAI on 2027-01-06
and the default moves by itself that day (`services/narrator/converter.py:38-47`, `:62-72`); the
tile says nothing. Show narration routes' removal dates as it shows Veo's, read from the converter's
own table, with no network call. Size: `services/model_watch_digest.py`, `ui/status_cards.py`, tests.

Later, not planned: image and video models as Update candidates (needs a per-unit price row and a
tested run path per model, `services/per_unit_pricing.py`).

## Constraints
- **Shared copies.** `services/benchmarks.py` is not touched in slice 1 or 2: Imprint's refresh is
  driven from `services/recommendations/ratings.py` and `main.py`. If a later change needs it, it
  lands in both repos in one session (`tests/test_benchmarks_drift.py`). The eleven files in
  `tests/test_providers_drift.py:30-35` are not touched. Slice 3 reads the converter's table and does
  not edit the converter (`tests/test_converter_drift.py`).
- **No new shared copy.** The two apps' `ModelWatch` classes, ranking engines and card widgets
  differ, so a byte-identical review module is not possible without replacing Imprint's watch with
  Sentinel's, which loses function. Imprint-only modules are the better choice; no drift test.
- **Value, not novelty; zero is unknown.** Measures 2 and 5. The review reads the same engine call
  as the badge, so it cannot introduce a second rule.
- **Request guard.** The feature makes no paid call (measure 7). Update changes a selection only;
  the next request still passes the guard. `config/pricing.json` gains no id in slice 1; its
  every-offline-id test is unaffected.
- **Qt.** No new thread. The review reads caches only and must not fetch on the UI thread
  (measure 7). No `QThread.terminate()`. `RatingsWorker` is not in `closeEvent`'s list
  (`main.py:6498-6507`); it is a daemon thread, not a `QThread`, and documents why (`ui/workers.py:719-728`).
- **Network.** New endpoints: **none**, in all three slices. Slice 1 reduces contacts (Local only).

## Phases required
Design: yes (new window, new control). Architect: yes, short; a gate only if slice 2's state key
goes in. Review, Verify (mutation targets: the unknown-price wording, the Local only gate, the
per-model dismiss, the one-point lead): yes. Secure: yes, short for slice 1 (provider-supplied ids
are painted in a new window; the id filter at `services/model_watch.py:109-117` already bounds them;
when the app contacts providers changes) and full for slice 2 (writes prices the guard's estimates
read). Document: yes. Comply: the privacy note and README must say when providers and Hugging Face
are contacted, so their wording changes with G2 and G3; the licence inventory does not change (no
new dependency), and the ratings credit (CC BY 4.0) must appear wherever the review shows a rating.
Launch: no public claim changes.

## Open questions (owner)
1. **What is missing for you?** The tile exists but is collapsed in the right rail. Is the request
   (a) the review window, (b) that you did not see the tile, or (c) something else, such as updating
   the local models on this Mac? Recommendation: (a) as slice 1, plus the status-line sentence for
   (b); leave the rail layout to #82.
2. **Should a check follow the mode and the permission chips, as Sentinel's does?** Recommendation:
   Local only asks no cloud provider (slice 1). Do not also gate on the chips yet: whether Imprint's
   chips start unticked at launch is **not verified**, and if they do the start check would ask
   nobody and the tile would look dead.
3. **Keep Imprint's Update rule** (move an agent only on a one-point lead, across permitted
   providers), rather than Sentinel's adoption? Recommendation: keep.
4. **Keep the silent first check?** Sentinel's first check announces newer releases of families it
   knows. Recommendation: keep silent; version order should not decide what is shown.
5. **Slice 2: may the review lead to a price entry for a new model**, and is a ratings switch wanted
   (default on)? Recommendation: yes to both, after G6 is verified.
6. **When?** `TODO.md:3` puts testing first and starts no feature unless you ask; you asked on
   2026-11-21. Recommendation: slice 1 after your hand test, since it blocks no test; say if you
   want it first.
7. **Slice 3 before 2027-01-06?** Recommendation: yes, as a P3 once slice 1 is in.

## Risks
- The review and the tile disagree. Mitigation: one engine call feeds both (measure 3).
- Computing eight entries on the UI thread is slow. The tile already does this per repaint
  (`main.py:5244-5262`, one database read per row at `:5211-5219`); Architect decides whether the
  review computes once on open. That `_text_recommendations` never fetches is **not verified**.
- The Local only gate leaves dropdowns on shipped lists until the mode changes, as in Sentinel
  (`../sentinel/README.md:101`). The tile must say why it did not check.
- Scope creep toward a port. Mitigation: the non-goals; a slice is done when its measures pass.
- The request meant something else (question 1), and slice 1 answers the wrong question.
