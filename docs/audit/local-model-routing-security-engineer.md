# Security review: local-model-routing (phases 0 to 4 and the panel advisor), 2026-11-24

Role: security-engineer (read-only on code and tests; did not write the code). Playbook `last-reviewed: 2026-11-11`, `status: current`.

Scope: commits `d4d39c1`, `0c0efcb`, `96a51dd`, `74436b4`, `95747d3`, `45fb54a`, `44c6b18` and later commits on the same files
(`84855ba`, `f9eba6d`, `2c6a61b`, `365f300`, `3a2e017`, `7e6f182`), reviewed at `3dd09f9` on `claude/happy-dubinsky-48c27c`. No spec
file exists; intent taken from ADR 0002 to 0004, README §6.2.1 and §6.2.2 (`docs/local_model_routing_plan.html` is in the lab root, not
in this repo, and was not read). The release kit's own local path was reviewed on 2026-11-21
(`docs/audit/one-click-release-security-engineer.md`, S-1 to S-12) and is not repeated here.

Shared files: `services/providers.py`, `services/lmstudio_client.py`, `services/local_models.py`, `services/local_ratings.py`,
`config/local_rating_prompts.json`, `ui/local_models_page.py`, `ui/routing_advice.py`, `ui/routing_page.py` are byte-identical
with Sentinel's checkout today (`cmp`); `services/routing_advisor.py` is not (P3-7). A fix in any of them lands in both repos.
Imprint-only: `main.py`, `services/local_endpoint.py`, `services/ollama_client.py`, `ui/panel_routing.py`, `ui/dialogs.py`,
`services/api_keys.py`.

## Verdict
**Fix first.** No P0. One P1, three P2, seven P3.
- **Holds:** no key goes to a local endpoint. A failover or a remembered rule that points at a paid model still meets the
  permission chips, the budget caps and the paid-request dialog. Model names reach SQL only as bound parameters and never a file path.
- **P1-1:** a local runtime set to another machine is treated as "on this Mac": no warning, no permission, no dialog, plain HTTP.
- **P2:** Local only does not stop cloud traffic for three agents or for the automatic measurement; the automatic measurement
  spends outside `authorize_request` and counts its cost from visible text; the uncensored tag is worded as a fact and "always
  tagged" cannot be backed.

## Threat model
| Asset | Threat | Control today | Evidence |
|---|---|---|---|
| Manuscript and prompt text | Leaves the Mac through a "local" route | Defaults are loopback (`providers.py:41-42`); Ollama calls and the LM Studio stream pass no proxies (`ollama_client.py:69-249`, `local_endpoint.py:81-82`) | Gap: **P1-1** (address override), P3-2, P3-3 |
| Manuscript and prompt text | Sent to a cloud provider the user did not permit | Cloud candidates need the chip (`main.py:1991-1994`, `:4015-4016`); every send passes `Validator` step 6 (`validator.py:121-128`) and the paid dialog (`main.py:4252-4277`, `:4524-4557`) | Probes; `tests/test_routing_panels.py` passed. Gap: **P2-1** (the mode's own promise) |
| Money | Spend without the request guard | Failover only offers (`routing_advisor.py:584-610`); Kernel resend goes through `_send_chat` (`main.py:4142-4152`); panels re-run their action through `authorize_request` (`panel_routing.py:240-247`) | Gap: **P2-2** (measurement) |
| API keys | Sent to a local or typed endpoint, or logged | Local specs have no key name (`providers.py:64-67`); local clients send no auth header (`lmstudio_client.py:266-287`, `ollama_client.py:186-250`); Settings probes for local build keyless clients (`api_keys.py:328-333`); in `services/*.py`, `api_key=` appears only in the six cloud clients (grep) | No finding |
| Transport | TLS off, hangs, redirects | No `verify=False` in `services/` or `main.py` (grep); timeouts 3 s / 300 s (LM Studio), 5 s / 300 s (Ollama); pull has none by design | Gap: P3-3 (redirects) |
| UI text | Model names, tags and error text from a runtime shown as markup | Picker rows are painted as plain text (`ui/widgets.py`); table cells are plain items | Gap: P3-1 (banner, tooltips) |
| SQL and paths | Model id used in a query or a path | Usage rows use bound parameters (`usage_tracker.py:174-178`); ids are JSON keys only (`local_ratings.py:246-251`) | No finding |
| Ratings | A model raises its own rating | Placed below the reference, never above (`local_ratings.py:225-235`); judged in both orders | Gap: P3-5 |
| Measurement prompt set | User data in it, or sent somewhere unexpected | 80 fixed, made-up prompts (20 per kind); sent to the local model, the reference provider and the judge provider; the local model's answers also go to the judge | Regex scan: one `.example` address, two made-up phone numbers, no keys or URLs |
| State files | Written non-atomically or published | Rules and savings: `mkstemp` + `os.replace` (`routing_advisor.py:633-648`); ratings: temp file + replace (`local_ratings.py:279-289`) | Gap: P3-6 |

## Findings

### P1
**P1-1 A local runtime pointed at another machine is still "on this Mac".**
`services/providers.py:124-149` (shared): `OLLAMA_HOST` and `LMSTUDIO_URL` accept any host, and a bare host becomes `http://`.
`:95-97`: local is decided by the provider's name. `services/validator.py:121-128`: a local provider skips the permission check.
`main.py:4362-4363`: no dialog. `main.py:5625-5647`: sent. `main.py:43` loads `.env` into the environment, so one line there, or
a shell export, is enough; `OLLAMA_HOST` is Ollama's own documented variable for a second machine. The check exists
(`services/release_kit/plan.py:72-96`) but only the release kit calls it (`main.py:4617-4625`).
- Probe r1: `OLLAMA_HOST=203.0.113.9:11434` gives `http://203.0.113.9:11434`, `is_local: True`; with every cloud chip off and both
  budgets at €0, `authorize_request("author", "ollama", …)` returned a token with 0 dialogs. For the same address the release kit
  says "Ollama is set to 203.0.113.9, which is not this Mac, so the book would…".
- What the app says meanwhile: "On this Mac · Ollama" (`services/local_models.py:33-36`), "It runs on this machine and costs
  nothing" (`main.py:5378-5380`), "Local only: Nothing is sent to a cloud service" (`services/routing_advisor.py:83-84`), "scored
  as private" (README §6.2.1), and the status line "✓ Ran on … (local)".
- Impact: whole prompts and manuscript passages (Quill Write, Continue, Revise; Kernel chat; the measurement prompts) cross the
  network unencrypted to a host the app never names, with Local only on. On a shared or public network anyone on the path reads them.
- Fix (Imprint-only seam, no shared file needs to change): call `endpoint_problem(provider, client.base_url)` in
  `authorize_request`, `_send_chat` and `run_backend`. Either refuse as the release kit does, or ask once per address and then show
  the host in the section label, the banner and the status line instead of "On this Mac". Test with `OLLAMA_HOST` and `LMSTUDIO_URL` set.

### P2
**P2-1 Local only does not keep traffic or money on the Mac.**
(a) Automatic measurement ignores the mode: `main.py:1162-1172` and `:1204-1241` never read it. Probe r3: mode `local_only`, one
run started against `anthropic` and `gemini`, budget €1.05, 0 dialogs.
(b) Press, Nova and Music are never advised (`ui/panel_routing.py:36-37`, `:59-67`), yet Settings → Models offers each a mode
(`ui/dialogs.py:694-700`, from `main.py:184-193`), and the chip note says "Ignored while Mode is Local only" (`main.py:989-995`)
while the guard reads the ticks as they are (`main.py:4450-4460`). Probe r2: under Local only, `manuscript`, `music` and `creator`
were each authorised to `openai`. The paid-request dialog still appeared each time, so nothing is sent silently; the claim is what fails.
Claim: `services/routing_advisor.py:83-84` (shared with Sentinel). Fix: in `authorize_request`, refuse a cloud provider (text and
per-unit) when `routing_mode(agent)` is Local only, for every agent; make `maybe_measure_local_models` and the Measure button
respect it; or reword the hint and the chip note to say exactly what the mode covers.

**P2-2 The automatic measurement spends outside `authorize_request`.** The owner's decision (ADR 0003, status "proposed") covers
running it once per new model within permissions and caps, and Settings says so (`ui/local_models_page.py:56-61`). Not covered:
(a) No reservation. `_reserved_in_flight_eur` counts `_pending_requests` only (`main.py:5411-5414`); a run never enters it
(probe r3: `0`). A request sent during a run is checked against the full remaining budget, so together they can pass a cap by
the run's ceiling.
(b) Cost is counted from visible text at four characters per token. `_measure_ask` joins the stream and drops its usage
(`main.py:1287-1291`); the bill is logged without `usage` (`main.py:1297-1302`; probe r6: `usage: None`). Reasoning tokens of the
reference model are neither counted towards the stop (`services/local_ratings.py:658-668`) nor recorded, so a run can cost more
than the "at most ~€" figure it was authorised for (`main.py:1237`) and the caps undercount. The size of the gap was not measured.
(c) The trigger is a name in a runtime's model list (`local_ratings.py:461-477`, `main.py:1129-1131`): one run per new
provider, id and quant, with no limit per day. Whoever answers on port 11434 or 1234, or at the address in P1-1, can add names.
After the first run the reference answers are cached (`local_ratings.py:690-696`), so each further run costs the judge calls only.
(d) A failed write of `data/local_ratings.json` is swallowed (`local_ratings.py:279-289`), so "measured once" is forgotten and
the run repeats on the next launch.
Fix: give the run a token so it reserves its ceiling and closes like any request; pass real usage to the stop check and the
bill; cap automatic runs per day; show a failed save. `local_ratings.py` is shared with Sentinel; (a) and (b) are in `main.py`.

**P2-3 The uncensored tag is worded as a fact, and "always tagged" cannot be backed.** The tag comes from a name pattern and four
publishers (`services/providers.py:172-199`, shared). The notes say "this model's refusal behaviour was removed. It will answer
requests a standard model declines" (`ui/widgets.py:57-62`), the banner says "its safety tuning was removed"
(`routing_advisor.py:536-537`), and README §6.2.1 says such models are "always tagged". Probe r5: `josiefied-qwen3-8b` and
`tiger-gemma-9b-v3` get no tag, although `local_ratings.py:122-125` lists both words as modified weights;
`dolphin-safety-classifier` is tagged UNCENSORED; a model copied under a neutral name gets nothing. The picker reads the name
without the publisher (`ui/widgets.py:110`, `:155`, `:167`, `:240`) while the table uses it (`services/local_models.py:64-66`), so
the two can disagree. Local first and a remembered rule can run a job on a tagged model with a status line only
(`routing_advisor.py:432-436`). Impact: a user who reads "no pill" as "standard model" for client work gets no warning, and the
public wording claims more than the code knows. Fix: one word list for both modules; wording such as "its name says…"; README
"tagged when its name or publisher says so"; add the sentence to the checked claims list. For legal-compliance to word; no legal
opinion here.

## P3
1. **Model names and runtime error text render as rich text.** The banner's two labels keep Qt's automatic format
   (`ui/routing_advice.py:44-52`, shared) and show the model label and the error (`:91-92`, `routing_advisor.py:613-621`,
   `main.py:4134-4135`, `ui/panel_routing.py:231-232`); tooltips carry the id (`ui/local_models_page.py:88`, `main.py:1357-1358`).
   Probe r4: a model id `<h1>Free and private</h1>` and an error holding `<b>` are both treated as rich text. A runtime can
   restyle or crowd out the line that names the paid alternative and its price. No script runs in Qt rich text; whether a label
   fetches a remote image was not tested. Fix: `setTextFormat(Qt.PlainText)` on both labels; escape tooltip text.
2. **LM Studio discovery and the non-stream chat still use the environment's proxy.** `services/lmstudio_client.py:174-175`,
   `:200-201`, `:271-274`, `:284-287` (shared). Imprint's run path uses the proxy-free stream, so no manuscript goes that way;
   a proxy can answer the model list instead, which feeds P2-2(c) and P3-1. The AST test covers two files only
   (`tests/test_release_kit_security_fixes.py:93`).
3. **Redirects are followed on local POSTs** (`ollama_client.py:245-250`, `local_endpoint.py:81-82`). S-7 of the release-kit
   review, still open: a process holding the port can pass the request body on to any host.
4. **`lms` is looked up on `PATH` and run during discovery, with no click** (`lmstudio_client.py:135-139`, `:153-154`,
   `:258-259`, shared). A writable folder early on `PATH` runs a planted binary. Prefer `~/.lmstudio/bin/lms`.
5. **The local model's answer is pasted into the judge's prompt** (`local_ratings.py:562-575`, `:697-700`, shared). An answer
   that addresses the judge can win in both orders. The rating stops at the reference's, which is still inside the band, and Local
   first then runs jobs on that model without asking. Fix: fence the answers, tell the judge to ignore instructions inside them,
   and do not auto-route to a model whose only evidence is a measurement that swept the reference.
6. **New state files are not git-ignored in a public repo.** `data/local_ratings.json` (and `.tmp`), `data/routing_rules.json`,
   `data/routing_savings.json` (`main.py:124-131`): `git check-ignore` matches none. In the everyday install they are written
   into the working tree; they name the models on this Mac and daily spend. None exists in the main checkout yet. Add them to `.gitignore`.
7. **`services/routing_advisor.py` has drifted from Sentinel's** (Sentinel `0023a14`, 2026-11-23, adds `HYBRID_MODE`; same
   behaviour today). The drift test skips in this worktree because the folder is not named `imprint`
   (`tests/test_providers_drift.py:27-29`, `:38-44`; 11 skipped). Port it before Release.

## Not verified
- Any live run: no model server was contacted and no network call was made. P1-1 was shown at the guard and by reading
  `run_backend`, not by sending.
- A real proxy or redirect (P3-2, P3-3); remote image loading in a label (P3-1); the real cost gap from reasoning tokens (P2-2b).
- Sentinel's side of the shared files beyond `cmp` and one `diff`. The lab-root plan document. The packaged (frozen) app.
- Dependency audit: not run, because this task allowed no network calls. The seven commits change no requirements file
  (`git diff --stat d4d39c1^..44c6b18 -- requirements.txt requirements-dev.txt` is empty). The playbook asks for an audit of the
  installed set before Release.
- Full suite not run (a run was in progress). Ran: `tests/test_author_draft_safety.py`, `tests/test_release_kit_security_fixes.py`,
  `tests/test_providers_drift.py`, `tests/test_routing_panels.py`: 70 passed, 11 skipped (76 s).
- Whether the wording in P1-1, P2-1 and P2-3 is acceptable as a public statement, and whether the made-up phone numbers in the
  prompt set need changing: for the owner or a lawyer.

Probes (read-only, temp DB via `tests/conftest.py`, fake workers, no network): session scratchpad `sec_probe/probe_routing.py`
and `probe_routing2.py`; 7 passed (one first-pass probe had an error in the probe itself and was re-run).
