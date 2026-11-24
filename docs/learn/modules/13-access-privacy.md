# Access, permissions, and privacy

> **Outcome:** distinguish credentials from permission and send data only to
> providers you intentionally allow.

## Prerequisites

- Know whether you are running the live project launcher or a frozen app.
- Obtain provider credentials only from the provider's official account flow.
- Never paste a secret into a prompt, project, screenshot, or bug report.

## Three separate states

| State | Meaning |
|---|---|
| Credential exists | Imprint Studio may be able to authenticate to that provider. |
| Provider is permitted | The current execution policy allows that provider to be used. |
| Route is eligible | Credential, permission, capability, availability, and budget checks passed. |

The **API keys** rail card reports detected readiness. It is not the secret editor: keys are pasted in **Settings → API keys** ([Add a key](#add-a-key)).
The generic Chat exposes local/hybrid/cloud execution policy and
provider permission controls; dedicated agent selectors expose only their real
implemented routes and recommendations.

## Storage boundary

Development/live-launcher mode loads the project environment. A frozen build
uses its seeded writable data area under `~/Library/Application Support/Imprint/`.
Real operating-system environment variables can override file values. Diagnose
which build is running before changing a file.

## Where your data goes

Its author receives nothing from Imprint Studio: no account, no analytics, no
crash reporting. A request sends what it needs (text, a chapter or book you
narrate, a reference image or photo) only to the provider you picked:

| Recipient | What it gets |
|---|---|
| OpenAI, Anthropic, Google (Gemini), DeepSeek, Moonshot (Kimi), Alibaba (Qwen and Wan, Singapore endpoint by default) | The request you send to that provider, with your key |
| ElevenLabs | Text you narrate with its voices |
| Higgsfield | Your prompt and reference image, uploaded to a public link it fetches |
| OpenAI (captions) | The generated narration of a video |
| YouTube, Reddit, Pinterest | The post or video you publish |
| PublishDrive | Book data from the store connector |
| Pexels | Search words for video visuals |
| Hugging Face | Nothing about you; the app downloads public model ratings |
| A machine named in `OLLAMA_HOST` or `LMSTUDIO_URL` | Your text, after you agree once per address; refused under **Local only** |
| Two cloud providers you already allowed | 80 fixed practice prompts when a new local model is measured; never under **Local only** |

These providers are outside the EU and their own terms apply; some use what
you send to improve their models unless you pay or opt out. Do not send
other people's personal data, clients' manuscripts or photos of real people
unless you are allowed to. The full note is the README's *Privacy* section.

## Add a key

Imprint runs without any key on a local model. A cloud provider needs its key,
pasted once, and its permission box, ticked each session.

**No key: use a local model.** Install Ollama and pull a model
(`ollama pull deepseek-r1:8b`), or load one in LM Studio and start its server.
Local models cost nothing, need no permission box, and appear under *On this
Mac* in the model menus. Settings → **Local models** shows what Imprint found.

**One cloud key:**

1. Get the key from the provider's own account page (for example
   console.anthropic.com or platform.openai.com). Never paste it into a
   prompt, a project or a chat.
2. Click **Settings** in the header and open the **API keys** tab.
3. Paste the key into that provider's field. Every value is one line; a
   two-line paste is refused with "must be one line only" and nothing is
   saved.
4. Click **Test** on that row. It asks the provider for its model list, which
   bills nothing, and reports *reachable* or the provider's own refusal.
5. Click **Save All**. The key is written to the `.env` the app reads,
   readable by your user only, and the app rebuilds its connections at once:
   no restart. Nothing on this page reaches the database, the run log or
   history.
6. Open the **Assistant** workspace and tick the provider's box under
   **Cloud text models** (or **Paid media** for Higgsfield and ElevenLabs).
   The boxes start unticked at every launch and apply to every agent.
7. Check the **API keys** card in the right rail: the provider now shows
   **Configured**.

Where the `.env` lives: in the project folder when Imprint runs from a
checkout or the live launcher; in `~/Library/Application Support/Imprint/` for
a frozen build. A key already set in your shell before launch wins over the
file, and its row says so.

## Walkthrough

1. Open **API keys** and list only status—not secret values.
2. Identify the selected provider and whether the action sends prompt text,
   source files, images, voice references, identity data, or media to it.
3. Keep unused provider permissions off where the control exists.
4. Use local routes when privacy or offline operation is a hard requirement;
   verify the selected model is actually local.
5. Remove secrets and private source data from screenshots/logs before sharing.
6. Treat platform account connection and AI-provider access separately. A model
   can draft a post without possessing a platform publishing token.

## How to read the result

A **Configured** badge (drawn in the theme's accent colour) shows detected
configuration, not policy approval, account quota, current provider health, or
rights to the submitted content. Hover the dot at the start of the Qwen row
for its caveat: it says when requests still go to DashScope's standard
international host. Alibaba recommends your own workspace host instead, but the
standard one still works; to switch, enter your workspace ID under Settings →
API keys → Qwen workspace ID. To learn whether a key is actually
accepted, press **Test** on its row in Settings → API keys, or run
`scripts/check_keys.py` from the project folder; both ask the provider for its
model list, bill nothing and never show a key.

## Verification

- [ ] I know which provider receives each input type.
- [ ] Only intended providers are permitted.
- [ ] Secrets remain outside prompts, projects, exports, and reports.
- [ ] Identity, consent, client, and unreleased data have an explicit handling rule.

## Common failures

**Key exists but route is missing:** permission, capability, a second secret, or
budget may still block it. Tick the provider's box in the Assistant workspace.  
**Test says "unreachable":** the provider refused the key or could not be reached; copy it again from
the provider's account page (no spaces, one line) and test before saving.  
**A frozen app ignores the project `.env`:** use the frozen data location; do
not assume launcher and packaged builds share configuration.  
**Social drafts work but posting does not:** AI generation and platform OAuth/
API approval are separate integrations.

## Next action

Set spend guardrails with [Costs, estimates, and limits](14-costs-limits.md).
