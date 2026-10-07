# MUSE — shared identity and content production

`key: creator` · class: `agents/creator/agent.py → CreatorAgent` · panel: `build_creator_panel()` · handler: `creator_generate()`

## What it does
Creates concepts, captions, campaigns, posting plans, promotional asset briefs,
and calendars for every Imprint venture. A profile records its platform or
venture, so books and publishing, music, AltMerch, and future work can
share one production tool without sharing business-specific assumptions.

## What it deliberately does not do
**It does not publish unattended, and it has no direct send path.**

Imprint has no authorised platform posting integration. It does not use browser
automation or a private endpoint. Platform rules change and may only be
available inside a logged-in creator account, so this agent produces drafts
you review and publish manually rather than claiming an unverified rule allows
automation.

It also will not write a message posing as a specific real person in a live
conversation. The drafts are captions, promos and starting points in your
voice — not a stand-in for you.

## What moved to Backstage
On 30 September 2026 the account-type and consent model, the platform-policy
record, statement import, per-asset revenue and outcomes, fan segments, the
`ppv` and `welcome` kinds, pricing fields and the agency view were removed from
here. **Backstage** (`active/backstage`) already owned all of it, and keeping
two implementations of the same records is how they drift apart.

Muse keeps what Backstage does not have: drafting, the plan calendar, voice
profiles, the media library, teaser rendering, and the written-character record
behind them. The two apps share no code and no data, and a test enforces it.

## Characters
An account may carry a written character — appearance, backstory, personality,
boundaries, a locked generation seed, and reference images. It exists so
successive drafts and renders stay the same character rather than becoming a
new one each time, and it applies to any account that has one; there is no
account type gating it. It is a consistency record, not a claim that the
character is a real person.

## Inputs (panel controls)
| Control | Purpose |
|---|---|
| Profile / Handle or project / Platform or venture | What is being created for and where it will be used. |
| Draft | post · caption · campaign · posting plan · promo assets · hooks · bio · promo. |
| Campaign | Attach an asset to a test for later comparison. |
| Channel | The `promo` kind only — the off-platform funnel the post is written for. |
| Brief | What it is about. Concrete briefs give non-generic drafts. |
| Provider / Model | Routed through the normal budget guard. |
| Teaser route | Higgsfield · Seedance 2.5, Gemini · Omni 1.1 Flash or Qwen · Wan 3.0, beside Generate Teaser. Remembered. |

## Outputs
The **Draft** tab has editable output; **Calendar** is a week view of the
items you post by hand — one column per day, ‹/› and This week to navigate,
each cell one planned item. Scheduling uses a real date-and-time picker (or
"no date yet"); **Reschedule…** (or double-click) moves an item and follows it
to its new week, and it is also how legacy free-text entries — kept visible in
the Undated lane rather than guessed at — get their first real date.
**Export…** writes the plan as an `.ics` calendar (dated items, importable
into any calendar app for posting reminders) or CSV (everything, raw text
preserved). Voice and Media remain separate tabs.

With a named Project selected, a generated draft carries that Project and its
content profile into Calendar when you schedule it. If you switch to another
profile before scheduling, Imprint refuses the cross-account save rather than
silently filing someone else's copy there. Teaser jobs and finished or imported
media can also be linked to the Project active at approval or import. The
profile and its voice, character and media records remain account-owned:
deleting a Project unfiles its content and teaser jobs but does not delete
those records or media files. Calendar and Media currently show everything for the selected account,
not just the active Project; hover a Calendar title to see its Project.

## Promo teaser video
`Generate Teaser` sends a safe-for-work prompt for a promo clip aimed at the
off-platform funnels where traffic actually originates, through the route
chosen in the teaser-route menu. Each route uses the account's character
reference images:

| Route | Reference images | Clip | Key |
|---|---|---|---|
| Higgsfield · Seedance 2.5 | Image-to-video from the first image (text-to-video without one) | 5 s | `HF_API_KEY_ID` + `HF_API_KEY_SECRET` |
| Gemini · Omni 1.1 Flash | Reference-to-video, up to 3 images sent inline | 5 s vertical | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| Qwen · Wan 3.0 | Reference-to-video, up to 10 images | 5 s vertical | `DASHSCOPE_API_KEY` |

Each route also needs its box in the API permissions row. Every teaser is
**assessed before approval** across the three routes: Omni and Wan are priced
from their per-second rates, while Higgsfield prices only through its estimate
call, so unless it is the selected route it is listed without a price and never
recommended on a guess. A switch is offered only when another route wins by at
least one point; **Apply** switches the route and asks again.

An Omni or Wan teaser's job row is written in `creator_video_jobs` under a
local id **before** the paid request, with the provider's job id stored beside
it when it arrives. After a crash, an interrupted Wan task is watched again
from its task id on the next launch and saved. An interrupted Omni render is
one synchronous call with nothing to look up, so it — like a Wan submission
whose id never came back — is marked lost, its reservation released and the
loss surfaced, never billed on a guess. Omni is posted exactly once: the
Gemini client's own retry is switched off. **Cancel Teaser** applies to
Higgsfield; an Omni or Wan teaser runs to completion once submitted.

Imprint uses Higgsfield's current request contract: a key ID + secret pair,
model-specific endpoints, presigned reference-image uploads, and the returned
status/cancel URLs. Add `HF_API_KEY_ID` and `HF_API_KEY_SECRET` to the private
`.env`, then enable **Higgsfield** in the API permissions row. The Muse panel
asks the official estimate endpoint for the exact request, shows that quote in
the normal budget approval, and only then submits the paid render.

Higgsfield renders can be canceled while queued. Once processing begins
Higgsfield cannot cancel them, so Imprint keeps watching and saves the finished
file. Job state,
price, policy outcome and correlation ID are stored in `creator_video_jobs`, and
the output is copied into the Media library because hosted output URLs are not
permanent. Since 2026-09-28 the ledger also settles the money: each render is
`reserved` until it is billed or released, and a Higgsfield render that
outlives the app
is resumed on the next launch — re-polled, downloaded, billed once and saved —
with timeouts and local errors retried rather than written off. Select a
Calendar row before clicking `Generate Teaser` to attach the finished video
directly to that item.

Higgsfield's Terms of Use prohibit **sexually explicit material** and
**unauthorised images of other people**, and moderate prompts, reference images
*and* outputs; circumventing moderation is itself a violation, and breaching it
terminates the account. `services/higgsfield_client.check_prompt()` refuses
those requests locally, before the spend, with a reason — negated mentions
("no nudity") are allowed, since those are instructions to the model rather
than requests for it.

Its role here is the safe-for-work promotional teaser.

## Under the hood — files & functions
| Location | Role |
|---|---|
| `agents/creator/agent.py` | `CreatorAgent` and prompt construction. |
| `agents/creator/profile.py` | Voice profiles and the written-character record. |
| `agents/creator/calendar.py` | Qt-free week arithmetic and `.ics` / CSV export. |
| `services/higgsfield_client.py` | Official video API lifecycle, upload, estimate, cancellation and content-policy guard. |
| `services/gemini_client.py` / `services/qwen_client.py` | Omni and Wan 3.0 reference-to-video submission (`create_video(reference_images=...)`). |
| `agents/creator/panel.py` | Account section, compose section, four tabs; `TEASER_ROUTES`, the teaser assessment and the startup reconciliation of Omni/Wan teasers. |
| `main.py: creator_generate()/creator_schedule()` | Lifecycle. |
| `creator_accounts` / `creator_content` / `creator_persona` | Tables. |

## Notes
- Nothing here touches the platform. Removing an account removes it from
  Imprint only.
- Platforms have their own rules about AI-assisted material, and they change.
  Read them; this app does not track them for you.
