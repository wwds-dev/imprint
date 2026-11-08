# Costs, estimates, and limits

> **Outcome:** bound a paid action, interpret its estimate honestly, and include
> retries and human correction in the cost of an accepted output.

## Prerequisites

- The provider/model and unit of work are selected.
- You know the current session and daily caps, plus any active project cap.
- For media, you know quantity, duration, aspect, resolution, and route.

## Cost states

| Label | Meaning | Decision allowed |
|---|---|---|
| Estimated request cost | Local preflight/reserve using known pricing inputs | Decide whether the attempt fits the cap |
| Last request cost | Best locally recorded post-request amount | Reconcile, but do not treat as provider invoice automatically |
| Session / daily / project | Recorded usage against guardrails | Stop or reduce scope before another request |
| Unpriced / unknown | No trustworthy local rate for this action | Investigate externally; never interpret as zero |

## Walkthrough

1. Set both session and daily caps before starting a long or batched job. If a
   named project is active, set its optional daily cap in **Settings → Projects**.
2. Select the final provider, model, quantity, duration, and format first.
3. Read the visible estimate or automatic reserve. If unpriced, stop and obtain
   a current provider quote/rate before authorising the work.
4. Start with one representative unit: short text, one image, one narration
   sample, or minimum practical video.
5. After completion, record retries, discarded generations, correction minutes,
   provider cost, and any external platform/fulfilment cost.
6. Reconcile material differences through **Cost History**, **Run Log**, and the
   provider's own record.

Project instructions add input tokens to each request and are included in the
preflight estimate. The project cap only counts locally recorded spend tagged
to that project; it is not a separate provider account or a provider invoice.

## Text requests: the most a reply can cost

Every text reply stops at a length limit of 8,192 tokens. The paid-request
dialog shows the most the request can cost — *Up to €X; you pay for what it
writes* — priced from everything that will be sent plus a full-length reply,
and the caps reserve that amount. A reply that reaches the limit is
incomplete, and the status line says so instead of *Done*: **[Cut off]**,
with **Press Continue to write more** in Draft, *send "continue"* in the
Assistant, or *ask for less or split the task* elsewhere. A Gemini model
can spend part of the limit thinking; if it spends all of it, the line reads
**[No answer]** and the request is still billed.

## Renders and image batches that fail or stop

A video render (Reel, or Herald's **Make a Clip**) and a Client Gigs logo
batch say in their approval that the paid steps already done are recorded if
the job fails or you stop it. They are: each started render stage at its
confirmed line and each image actually made at the confirmed per-image rate,
never more than the amount you confirmed, and nothing if no paid step had
started. The status line gives both figures (*€x of €y recorded*); Reel's log
itemises them. A new render starts from the beginning and is paid again.

## Effective accepted-output cost

```text
Effective cost = API/media spend + retry spend
                 + correction hours × chosen hourly value
                 + other direct fulfilment cost

Effective cost per accepted output = Effective cost ÷ accepted outputs
```

A cheaper request can be the expensive workflow if its correction or failure
rate is higher. A stronger model is wasteful when a smaller one passes the same
acceptance checklist.

## Verification

- [ ] Both caps are set and the request fits with margin for one recovery step.
- [ ] Unknown pricing is visibly unresolved.
- [ ] Failed attempts and human correction are included.
- [ ] Material totals are reconciled with the provider/account source.

## Common failures

**Budget blocks the action:** reduce duration, quantity, input, or model cost;
do not remove the guardrail reflexively.  
**Stop was pressed but a charge remains:** accepted asynchronous jobs may be
non-cancellable, and a stopped render or batch records the steps it finished;
Stop is not a refund.  
**A reply ends mid-sentence:** it reached the 8,192-token limit; the status
line says **[Cut off]**. Continue, or ask for less.  
**Token cost looks complete:** image, speech, video, acquisition, platform,
contractor, refund, and human-time costs may still dominate.

## Next action

Learn route-specific cost/cancellation in the relevant Agent Academy lesson,
then calculate complete economics in [Unit economics](33-unit-economics.md).
