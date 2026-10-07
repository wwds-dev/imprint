# BRAND & LOGO DESIGNER — client identity studio

`key: fiverr` · agent: `agents.fiverr.FiverrAgent` · workspace owner: `agents.fiverr.FiverrPanel`

## What it does
End-to-end logo-gig assistant. Unlike a prompt-only helper, it **actually generates the logo images** — through OpenAI, Gemini or Qwen, whichever owns the selected image model — saves them locally, and also writes the Fiverr gig description and the client delivery message. One brief → concepts + copy.

## Inputs (panel controls)
| Control | Purpose |
|---|---|
| Business Name, Industry / Niche | Core brief. |
| Style | Minimalist / bold / vintage / tech / etc. |
| Primary Colors, Notes | Palette + tagline/mood/competitors to avoid. |
| # Concepts (1–4) | How many logos to generate. |
| Text Provider / Model | LLM for the image prompt + copy. |
| Image Model | See the table below. The model's provider is the one that is billed and needs a key. |
| Generate Logos / Delivery Msg / Gig Description / Stop | The three actions. |
| Save All Images / Clear | Export / reset. |

## Image models
| Provider | Model | Per-image reserve (`config/pricing.json`) | Key |
|---|---|---|---|
| OpenAI | `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare`, `gpt-image-2` | $0.06 (token-billed; conservative) | `OPENAI_API_KEY` |
| Gemini | `gemini-nano-banana-2.1` (Nano Banana 2.1) | $0.04 (about $0.034 at 1K) | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| Gemini | `gemini-3-pro-image` (Nano Banana Pro — Gemini's model for legible text in the image) | $0.14 (about $0.134) | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| Qwen | `qwen-image-3.0`, `qwen-image-3.0-pro` | $0.03, $0.04 | `DASHSCOPE_API_KEY` |

Every logo request is **assessed before approval** across the image models that can run (key and permission present), each priced for the number of concepts. A switch is offered only when another model wins by at least one point; **Apply** switches the model and asks again for the images — the prompt is already written and paid for.

## Outputs
Tabs: **Logo Preview** (generated images, 280×280 thumbnails), **Delivery Message** (streamed), **Gig Description** (streamed), and **Orders**. The cost shown is a conservative per-image budget reserve. Images save to `data/fiverr_output/<timestamp>/logo_N.png`.

## How it works
Two-step logo flow: a `ChatWorker` runs `FiverrAgent.build_image_prompt_request()` to craft a clean image prompt, then `FiverrImageWorker` calls `services/image_generation.generate_image()` with the selected model and displays the returned image. Stamp authorizes the image model's own provider, and checks that provider's key before the paid prompt step, so a missing key costs nothing (it used to demand `OPENAI_API_KEY` whatever the model). Each image request is sent exactly once: a paid image is never retried automatically. Delivery/gig use `FiverrAgent.build_messages(task, brief)`.

## Under the hood — files & functions
| Location | Role |
|---|---|
| `agents/fiverr/agent.py` | `FiverrAgent` — delivery / gig / image-prompt roles. |
| `agents/fiverr/panel.py` | Owns the layout and all guarded text/image request, result, Stop, save and order-log lifecycles. |
| `ui/workers.py: FiverrImageWorker` | Threaded image generation + local save, one concept at a time. |
| `services/image_generation.py: generate_image()` | The one place a model id becomes a request: OpenAI through `services/openai_client.py`, Gemini through the Interactions API with its own retry switched off, Qwen through DashScope. |
| `services/media_catalog.py` | The image models offered, with their providers and notes. |
| `main.py` compatibility entries | Delegate older umbrella call sites to the owned panel; they contain no Client Gigs implementation. |

## Extend it
- **Other gig types**: generalise the brief + add roles to `FiverrAgent` (business cards, thumbnails, banners).
- **Vector export**: post-process PNGs (e.g. trace to SVG) after download.
- **Another image provider**: add its request to `services/image_generation.py`, a `scene_images` entry to `services/media_catalog.py` and a per-image rate to `config/pricing.json`, rather than placing a model with no execution path in the menu.

## Requirements
The **API key of the selected image model's provider** (OpenAI, Gemini or Qwen) and its permission box. GPT Image uses token-based image pricing, so Imprint reserves a conservative amount against the budget before rendering; the Nano Banana reserves round Google's list prices up, and Qwen's are Alibaba's list prices. Text copy can use any provider. Fiverr seller account to sell.

DALL·E 2 and 3 are intentionally not offered: OpenAI retired and removed both APIs.

## Before you run

Use the client's exact business name, industry, deliverable count, colour
constraints, and prohibited references. Keep trademarked competitors in
“avoid” notes, not as imitation targets. Confirm the image model, its
provider's key, concept count, estimated reserve, and remaining session budget
before generating. Nano Banana Pro is Gemini's model for legible text in the
image, which matters for a wordmark. Delivery and gig copy can use a different
text provider.

## Verify the result

- Inspect every logo at full size; the preview thumbnail can hide malformed
  lettering and small artefacts.
- Confirm spelling, contrast, simple-size legibility, and transparent/background
  expectations against the client brief.
- Run a trademark and originality check before commercial delivery. A generated
  PNG is not automatically a vector master or an exclusive mark.
- Edit gig claims, turnaround, revisions, and package terms so they match the
  service you will actually provide.

## Storage, cost, and privacy

Generated working images first land under
`data/fiverr_output/<timestamp>/`. **Save All Images** copies the current set to
a folder you choose; it does not transfer files to Fiverr. Brief text and image
prompts are sent to the selected cloud providers. Image generation is paid per
request and each concept consumes a separate generation call.

## Common failures

| Symptom | Check |
|---|---|
| Generate Logos is blocked | Required brief fields, the image model's provider key and permission, a per-image rate on file, and budget reserve. |
| Copy appears but no image | The text prompt stage succeeded; inspect the image-stage status and Run Log. |
| Save All Images is disabled | No complete images are held in the current result set. |
| Text in the logo is wrong | Regenerate with a simpler mark or add lettering manually in a design tool. |
