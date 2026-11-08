# Reel — Suggestions

Status: `IDEA` · `CONSIDERING` · `PLANNED` · `DONE` · `REJECTED`

---

## Open

| Suggestion | Status |
|---|---|
| Shot timeline with replaceable clips before final assembly | IDEA |
| Cost/quality presets spanning script, visuals, voice and render | PLANNED |
| Automatic short-form derivatives from a finished long video | IDEA |
| Keep a provider-compatibility matrix in the panel, so a deprecation is visible before it lands | IDEA |
| Add a new OpenAI direct-video model only if OpenAI publishes a supported successor to Sora with a documented API, pricing and lifecycle | IDEA |
| Kling 3.0 through Higgsfield, without Kling's $700 API minimum (research 2026-09-20; the Seedance half of this card shipped, see Done) | IDEA |
| Local zero-cost render tier behind the "Local" provider slot: LTX-2.3/2.5 open weights run fully on Apple Silicon (M1+, MPS, ProRes out) — a real offline renderer instead of gradient cards, and the natural budget-cap fallback | IDEA |
| MiniMax Hailuo as a premium/budget pair: H3 at $0.13/s is the best 2K-with-stereo-audio value (async job API via OpenRouter fits the job model); Hailuo 2.3 (~$0.01–0.08/s) for high-volume cheap B-roll. Note: H3 open weights are license-blocked in the EU/US — API only | IDEA |
| gpt-image-2.5-sunburst for thumbnails (same token rates as flare, quality-optimized); Gemini 3.1 Flash TTS (70+ languages, steerable audio tags) as a second narrator source | IDEA |
| gemini-omni-1.1-flash multi-turn video *editing* via the Interactions API — the one capability nothing in the catalog exposes; conversational fix-ups of a rendered clip instead of a full re-render | IDEA |

## Done

| Suggestion | Status |
|---|---|
| Upgrade the Higgsfield slot from seedance-1.0-lite to Seedance 2.5, keeping 2.0 as fallback — shipped 2026-09-21 (`bc8d9d7`): `seedance-2.5` default and `seedance-2.0` in `services/media_catalog.py` | DONE |
