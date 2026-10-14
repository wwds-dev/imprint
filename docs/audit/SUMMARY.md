# Audit summary: Imprint security (2026-10-14)

Scope: request guard and budget logic; key handling (`.env`, `.gitleaksignore`, Settings write path); Higgsfield, Gemini
and ElevenLabs download paths. Report: [security.md](security.md) (part 1 keys and downloads, part 2 budget).
The DashScope Workspace ID change has its own reviews (`dashscope-workspace-id-*.md`). Nothing was fixed by this audit.

## P0
None.

## P1 (deduped)
| ID | Finding | Where |
|---|---|---|
| B-F1 | Gemini thinking tokens never billed; Gemini spend under-recorded (example x5.8), caps trip late | `services/gemini_client.py:185`, `:396` |
| B-F2 | Pre-flight estimate assumes ≤ `max(250, 1.2×input)` output while 5 of 6 text clients send no output limit; system prompt/context not estimated; one request can overshoot a cap 30×+ | `main.py:503-504`, `:1508`; `services/{openai,deepseek,kimi,qwen,gemini}_client.py` |
| B-F3 | Paid stages of a failed or user-stopped render, and partial Fiverr image batches, record EUR 0; retries re-spend in full | `agents/video/panel.py:867-869`, `agents/social/panel.py:682-690`, `agents/fiverr/panel.py:540-546` |
| X-1 | Reddit posts go to the wrong subreddit for any name starting with "r" (`lstrip("r/")`: rust → ust, r/rpg → pg). Outside the audit scope, proposed P1; verified | `agents/social/publishing.py:151` |

P2s worth scheduling with them: B-F4 reservations miss Chat/agent/project caps (verified on the real window); B-F5 unknown
price or `eur_per_usd` ≤ 0 makes calls free or negative; B-F6 vidforge retries and scene count overshoot the reserve;
B-F7 stopped streams and ambiguous media creates record EUR 0; B-F8 Creator drafts never get provider usage;
K-P2-1 cleared Gemini/Higgsfield keys return at next launch via alias lines; K-P2-2 `.gitignore` misses `.env.*`,
root `client_secret*.json`/`token.json`, and the pre-commit gitleaks hook is inactive.

## Top-10 fix order
1. X-1 Reddit `removeprefix("r/")` + test with "rust" (one line, public-facing harm).
2. B-F1 add `thoughts_token_count` (and cached tokens) to Gemini usage + test.
3. B-F2 explicit output cap on every text client; reserve at the cap; estimate from the full `messages`.
4. B-F5 refuse unknown prices; validate `eur_per_usd` finite > 0 through one reader; budgets finite ≥ 0 (with P3 F12).
5. B-F4 route Chat through `authorize_request`; count agent/project reservations.
6. B-F3 + B-F7 record partial/actual cost on error, cancel and partial batches (one `record_request` override serves both).
7. K-P2-2 widen `.gitignore`, rename the `.env.` temp prefix, activate `.githooks` in the main checkout.
8. K-P2-1 one key precedence for all readers; writing a canonical key removes its alias lines.
9. B-F6 vidforge `max_retries=0`, enforce scene count, include quality/models in the estimate, record `max(reserve, actual estimate)`.
10. B-F8 wire Creator `usage_signal` + a static test that every chat worker wires usage.

Then the P3s: Higgsfield download host allowlist and byte cap (K-P3-1, also Qwen/OpenAI `file://`), NUL and control
characters in `.env` values (K-P3-4), `load_dotenv(interpolate=False)` (K-P3-5), `/tmp` launch log (K-P3-2, shared with
Sentinel), 0600 on existing secret files (K-P3-3), ElevenLabs redirects (K-P3-6), gitleaks pins and checksum (K-P3-7),
B-F9 to B-F16.

## Gitleaks
History 0 findings (257 commits); all 4 `.gitleaksignore` pins verified as SQL settings-key names, not secrets.

## Could not verify
- Live provider billing: cancelled/timed-out streams and media creates, real Gemini thinking ratio, Higgsfield $0
  quotes, Ollama `:cloud` metering, OpenAI image double-billing on retry.
- Real Higgsfield/Qwen download hosts and redirects (needed for an allowlist); partial keys in provider 401 text.
- Symlink-follow at `/tmp/imprint_launch.log`; quit during a stalled download (inferred).
- Dependency CVEs (`pip-audit` not in venv, no network); CI on GitHub and GitHub push protection.
- Playbook `security-engineer.md` was `status: baseline` in this worktree, so no radar-verified practice was applied.
