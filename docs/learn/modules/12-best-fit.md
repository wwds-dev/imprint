# Providers, models, and Best Fit

> **Outcome:** choose an eligible route and explain what the recommendation
> optimises, how confident it is, and why an override might be reasonable.

## Prerequisites

- Open a dedicated agent that exposes provider/model selectors.
- Define the task or format first where possible; recommendations recalculate
  when those requirements change.

## The two recommendations

**Provider BEST FIT** marks the provider containing the highest-scoring eligible
model for the current agent and task. **Model BEST FIT** marks the best eligible
model *inside the provider currently selected*. If you manually choose another
provider, the model menu still gives useful guidance within that choice.

**BEST AVAILABLE** or setup-target wording means the ideal route is not fully
ready under current keys, permissions, capability, or budget. It is a setup
recommendation, not proof that pressing the action will work now.

## How ranking works

Imprint first removes incompatible, retired, unavailable, disallowed, and
over-budget candidates. It then scores the remaining routes against the agent's
maintained quality, reliability, cost, speed, context, and privacy priorities.
The process is deterministic and local; opening a menu does not make a paid call.

Three rules keep the ranking honest:

- **Cost is the real price.** Text routes are scored on the per-token rates in
  Settings → Pricing; a model without its own row is priced at the provider's
  dearest current rate, so it is never ranked as cheaper than it is.
- **Being new earns nothing.** A newer model is often dearer and says nothing
  about fit for your task, so it is scored on the same evidence as every other
  model and wins only where that evidence says so.
- **A switch needs a visible lead.** The badge, the paid-request dialog and
  Update selected all need a lead of at least one point on the 0–100 fit
  scale. When your selection is within a point of the top, it keeps the badge
  and the tooltip says why.

## Walkthrough

1. Select the task, format, duration, or aspect controls that affect capability.
2. Open the provider menu and locate the recommendation badge.
3. Read the provider tooltip: task, strongest dimensions, score, confidence,
   availability, and setup-target caveat should be visible.
4. Select a different provider deliberately. Open the model menu and note that
   its badge now identifies the best model within your selected provider.
5. Check the API-key/status and permission state before treating any route as
   executable.
6. For a meaningful override, compare the same small input and acceptance
   checklist. Record pass/fail, correction minutes, latency, retries, and cost.
7. Press a paid action. Read the assessment in the confirmation before you
   accept it: either your route is the best fit for this request, or the
   better one is named with both fit scores and both estimates.
8. If you press **Apply**, nothing is sent. Read the new route's own estimate
   and confirm again.

## Before a paid request

Every paid request — text, image, video or speech — is assessed again at the
moment you send it, for **that** request: its length, its shape, its number of
images or minutes. The confirmation compares every route you have a key for and
have permitted, priced for exactly what you asked.

- **Your route is the best fit:** the dialog says so and you confirm as usual.
- **Another route fits better by at least one point:** it is named beside
  yours with fit scores and cost estimates. **Apply** switches the agent to it
  and stops; the panel then asks again with the new route's estimate. A paid
  request is never re-routed behind your back.
- **Not compared (no key, or not permitted):** a route that exists but cannot
  run in your setup. Add the key or the permission first if you want it
  weighed.

Image, video and speech routes are the most expensive, so their cost is scored
**relative to each other**: the cheapest route for this request scores best,
one at twice the price half as well. A route that cannot make what you asked —
a 30-second clip on a model that stops at 10 seconds — is left out rather than
compared at a different length. Each agent sheet under **Docs** lists the
routes its paid actions compare.

## New models

**Model updates**, under **API keys** in the right rail, lists models the
providers behind your keys have released since Imprint last looked. It checks a
few seconds after start-up and on **Check now**; model lists are free, so the
check costs nothing. The first list from a provider is a silent baseline, and
only chat models are announced.

A new model appears at once in every model menu that offers its provider, with
a quiet **NEW** badge. It is ranked like every other model. The tile says
**Best choice for …** only where it is an agent's best option across your
permitted providers, and notes when it has no price of its own yet.

To move agents to new models, click the rows to mark them and press
**Update N selected**. Each agent is assessed for its current task and moves to
a marked model only where that model wins by at least one point; a marked model
that wins nowhere stays in the menus and nothing switches. **Dismiss** clears
the notices without switching anything.

## Confidence does and does not mean

Recommendation confidence describes the completeness and separation of local
capability evidence. It is not confidence that the output will sell, comply
with every current platform rule, or outperform on your specific material.

## Sensible overrides

- local privacy or offline operation;
- a required media capability, context size, latency, or format;
- measured lower effective cost after retries and correction time;
- temporary provider reliability;
- an approved client/account restriction.

“Strongest model” or “cheapest token” alone is not a complete decision.

## Verification

- [ ] I can distinguish provider-best overall from model-best within provider.
- [ ] I checked eligibility and setup-target wording.
- [ ] Any override has a measurable reason and a small comparison plan.
- [ ] I did not interpret recommendation confidence as market evidence.
- [ ] I read the paid-request assessment before confirming, and confirmed
      again after any **Apply**.
- [ ] I did not switch to a model only because it is new.

## Common failures

**No badge:** the catalog may lack comparable eligible candidates; inspect the
tooltip/status rather than assuming the first item is best.  
**A text provider appears absent from video:** text models can write a script but
are not automatically video-rendering endpoints.  
**The route changed after a control:** this is expected when task capability,
budget, permission, duration, or aspect requirements change.
**Apply did not send anything:** by design. Apply only switches the route;
read the new estimate and confirm again.  
**A NEW model has no BEST FIT badge:** it was assessed and did not lead by a
point for this agent and task. That is the answer, not a fault.  
**Update selected switched nothing:** none of the marked models won for any
agent's current task; they stay selectable in the menus.  

## Next action

Confirm [Access, permissions, and privacy](13-access-privacy.md), then compare
effective cost in [Unit economics](33-unit-economics.md).
