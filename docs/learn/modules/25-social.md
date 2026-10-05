# Social

> **Outcome:** move one reviewed campaign asset from brief to a traceable draft,
> schedule state, and supported/manual posting decision.

![Social workspace](../img/agent-social.png)

## Prerequisites

- One project/campaign, audience, offer, and measurable next action.
- Rights for source media and factual support for public claims.
- Account/API readiness checked separately from drafting readiness.

## Control atlas

| Area/tab | Purpose | Important boundary |
|---|---|---|
| Campaign selector / New Campaign / Save Campaign | Reusable campaign context | One campaign should not mix unrelated offers |
| Brief and route | Generates bounded platform variants | Best Fit is production guidance, not channel evidence |
| Make a Clip | Hands source/context to video production | Inspect cost and actual output before scheduling |
| Schedule Drafts / Stop | Prepares calendar rows or requests local cancellation | Scheduled is not necessarily posted |
| Draft | Editable generated variants; Save to Schedule | Review length, links, claims, tone, and platform fit |
| Schedule | Copy Text, Mark Posted, Post Now | Direct posting exists only for configured supported accounts |
| Analytics | Record metrics for a selected posted item; compare observed reach, clicks, and click rate | Source and measurement window are required; clicks do not prove sales |
| Accounts | Shows connection/readiness and platform limits | Status is not a guarantee that current rules permit content |

## Worked run

1. Create a campaign named for one offer and observation window.
2. Set the audience, promise, source facts, destination/CTA, platforms, cadence,
   and approval rule; save it.
3. Generate a small set. In Draft, remove unsupported claims and ensure every
   variant preserves the same offer while adapting format.
4. Save only approved variants to Schedule. Check date/time, destination,
   character limits, media, and link/source tag.
5. In Accounts, distinguish **drafting available** from **posting ready**.
6. Use Post Now only on a supported, authorised integration. Otherwise Copy Text
   and publish manually, then Mark Posted with the real state.
   - **Retry available** means the platform definitely rejected the earlier
     attempt before accepting content; correct the cause and retry.
   - **Verify platform** means the result is unknown, commonly after a timeout
     or app close. Check the account first. If the post exists, choose **Mark
     Posted**. Use **Retry After Checking** only when it is definitely absent.
7. Select the posted item in Schedule and use **Record metrics**. Copy reach and
   link clicks from the platform's own report, naming the report and time window.
   The Analytics tab shows the post's saved angle and click-through rate.
   “Posted” alone is not reach or sale.

## How to read the output

Draft and scheduled have not crossed a publishing boundary. Queued has a
durable delivery record but has not started. Posting means a network attempt is
in progress. Retry available is a known rejection. Verify platform is an
ambiguous result and deliberately blocks automatic retry. Posted records a
completed API delivery or your manual verification. None of these proves
impressions, qualified visits, purchases, or contribution. Keep the platform's
owned report and destination analytics for those outcomes.

## Acceptance checklist

- [ ] Copy/media rights and factual claims are approved.
- [ ] Each post names one destination action and source tag.
- [ ] Platform length, format, accessibility, disclosure, and community fit pass.
- [ ] Posting state reflects what actually happened, including failures.
- [ ] No private API or browser-automation workaround bypasses platform rules.

## Cost, cancellation, and gates

Include text, clip, image, scheduling, paid promotion, correction, and moderation
time. Humans approve public posting, replies, claims, sensitive targeting, and
account connection.

## Verification

Confirm the actual platform/manual state, destination/source tag, and later
owned report row; a Schedule row alone does not complete verification.

## Common failures

**Post Now disabled:** the account is not supported/ready; use the explicit
manual path.  
**Verify platform:** do not press retry first. Open the platform, search the
account/board/channel, and resolve the row based on what actually exists.  
**Generic variants:** add one audience problem, proof boundary, CTA, and channel
constraint.  
**Likes rise but sales do not:** diagnose the full funnel instead of producing
more posts.

## Done when

One approved asset has an accurate state, destination/source tag, known cost,
and a later outcome record—not merely a generated caption.

## Next action

Build the measurement chain in [Funnels, attribution, and cohorts](34-funnels-attribution.md).

## Recipe: run one small campaign, brief to measured post

You will run one small campaign for a novel called *The Salt Road*: two
X / Twitter variants drafted from one brief, both given dates, one posted by
hand and marked posted, and its real reach and clicks recorded. Copy the
example inputs exactly the first time, then swap in your own. Each **Show me**
closes this lesson, opens the control it names and rings it; **Back to lesson**
in the callout brings you back to that step.

**Time:** about 15 minutes in Imprint, plus the minute on the platform when you
post, and a short return visit later for the numbers. **Cost:** one text
request in Imprint — you see its estimate and approve it before anything is
sent (free with a local Ollama model). Posting by hand costs nothing. **Make a
Clip** starts a paid video render with its own cost confirmation; this recipe
never touches it.

### Step 1 — Create the campaign

Fill in the Campaign fields. They are sent with every drafting request this
campaign makes, so each variant keeps the same subject, goal and audience.

```
Subject:       The Salt Road
Subject is a:  book
Goal:          launch week sales
Audience:      literary fiction readers
Link:          https://yoursite.example/the-salt-road
```

Click **New Campaign**: the campaign appears in the selector, named after its
subject. **Save Campaign** writes later edits back into whichever campaign is
selected.

[Show me](show:social_new_campaign_btn)

### Step 2 — Aim the post

Set the Compose row. One platform at a time — the drafter writes *for* a
platform, not once for everywhere. Two variants gives you a real choice without
doubling the review work.

```
Platform:   X / Twitter
Angle:      launch
Variants:   2
Specifics:  out Tuesday; paperback and ebook; first chapter free on the site
```

Below the row, pick a provider and model for the writing. Choose Ollama if the
request should stay on your Mac and cost nothing.

[Show me](show:social_platform_box)

### Step 3 — Write the variants

Click **Write Posts**. Imprint shows the estimate; approve it. After a few
seconds the Draft tab fills with two variants separated by a long dash line.

**Good result:** two genuinely different openings on the same offer, each
within the limit, and no invented reviews, quotes or figures — the drafter is
instructed never to make those up, but check anyway and delete any that slip
through. **Weak result:** the same post reworded twice — add one concrete
specific and write again.

[Show me](show:social_write_btn)

### Step 4 — Edit against the counter, then save

The drafts are fully yours to edit. The counter under the box counts live
against the platform's ceiling — for X / Twitter it reads `… / 280 characters`
and says how far over you are, because an over-length post is a rejected call
at the worst moment. Keep the dash separator line while you edit: it is what
splits the box into separate posts. Click **Save to Schedule** — each variant
becomes its own row and the panel switches to the Schedule tab.

[Show me](show:social_save_draft_btn)

### Step 5 — Give the rows dates

Click **Schedule Drafts**. Every undated draft in the campaign gets a date
spread across the coming weeks at its platform's own cadence — spaced out on
purpose, because bunched posting is the pattern that reads as a bot. The rows
now say scheduled. That is a plan in your calendar, nothing more: no post has
crossed into any platform yet.

[Show me](show:social_schedule_btn)

### Step 6 — Read what connecting grants

Open the **Accounts** tab. Drafting works for every platform listed; posting
from Imprint works only for the ones marked **ready**. For a connectable
platform the entry states what connecting grants — Reddit's, for example, says
it can submit posts as your user and nothing else, and that the script-app flow
keeps your Reddit password in the `.env` — *before* the numbered setup steps.
Read the grants before you paste any secret, and if a grant is more than you
want to give, post by hand instead. X / Twitter is marked **drafting only**
(its API requires a paid tier), so this recipe posts it by hand. **Re-check**
re-reads the statuses after you change credentials.

[Show me](show:social_accounts_box)

### Step 7 — Post by hand, then mark it

Select the first row in Schedule and click **Copy Text**. Open X in your
browser, paste, read it once as a stranger would, and post it yourself. Back in
Imprint, click **Mark Posted**. That records your own verification that the
post exists — a statement you make, not an API receipt — so make it true.
(**Post Now** exists only for configured, ready integrations, and even there it
confirms each single post before publishing from your account.)

[Show me](show:social_mark_posted_btn)

### Step 8 — Record what actually happened

A day or a week later, select the posted row and click **Record metrics**.
Imprint asks four things, and refuses to save without the source and window:

```
Unique accounts reached:   412
Link clicks:               9
Platform report or export: X analytics — post detail
Measurement window:        2026-10-06 to 2026-10-13
```

Copy reach and clicks from the platform's own report. These numbers are
self-reported — you typed them — so the Analytics tab labels every row with its
source and window, and computes click rate as clicks ÷ reach for that one post
and window. Clicks are visits, not sales, and one post's rate does not fairly
compare different audiences; what a click is worth is a question for your
funnel, not this tab.

[Show me](show:social_metrics_btn)
