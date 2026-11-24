# Code review: local-model-routing (2026-11-24)

Role: Foundry code-reviewer, independent of the author. Read-only on code; this file is the only one written.

**Verdict: fix first.** No path was found where a routing answer (Switch, Always, Keep, a rule, Local first, a failover offer) sends a paid request without the budget check and the paid-request dialog, and an unknown price is never read as free by the advisor. Three things should be settled before a release: the automatic measurement can spend more than was authorised and records less than it spent (L-1); a judge that fails makes a local model look as good as the best cloud model (L-2); and "Local only" does not do what its own text says for most agents (L-3).

**Counts:** P0: 0 · P1: 3 · P2: 8 · P3: 9

## Scope reviewed

- Commits `d4d39c1`, `0c0efcb`, `96a51dd`, `74436b4`, `95747d3`, `45fb54a`, `44c6b18`, `5547805`, docs `70dc209`, read as they stand today on `claude/happy-dubinsky-48c27c`. Review started at `e79f696`; other sessions committed `3dd09f9` and `fb6a0c4` (audit files and `TODO.md` only) while it ran. None of the files below changed.
- Files: `services/providers.py`, `lmstudio_client.py`, `local_models.py`, `local_ratings.py`, `local_endpoint.py`, `routing_advisor.py`; `ui/local_models_page.py`, `routing_advice.py`, `routing_page.py`, `panel_routing.py`; the routing regions of `main.py` (`:170-181`, `:725-800`, `:948-970`, `:1101-1361`, `:1906-2004`, `:3900-4342`, `:4346-4586`, `:5330-5414`, `:5489-5551`, `:5613-5653`, `:5693-5776`, `:6455-6519`); `ui/workers.py:784-845`; the four advised panels' `authorize_request` calls; Booth's route table and the converter's default route.
- Reference for intended behaviour: `docs/local_model_routing_plan.html` in the lab root (the path in the brief, inside this repo, does not exist), ADRs 0002 to 0004, `README.md:897-909`, `docs/learn/modules/12-best-fit.md:153-176`, the routing rows in `TODO.md`.
- Playbook `docs/playbooks/code-reviewer.md`: `status: current`, `last-reviewed: 2026-10-14` (41 days, not stale).
- Process facts: there is no spec in `docs/specs/` and no row for this change in `docs/foundry/approvals.jsonl`. ADRs 0002 and 0003 still say "proposed"; `docs/adr/0002-provider-registry.md:1` is headed "ADR 0001".
- Earlier reports that touch this area: `docs/audit/code-readiness-audit-2026-11-18.md` (QM-1 to QM-4) and, on `origin/main` only, the 2026-11-23 audit (`code-review.md`, `security.md` S-10, `architecture.md` B-1). That code review lists `ui/panel_routing.py` as not read. Where a finding below repeats one of theirs, it says so.

**Shared copies.** `services/providers.py`, `lmstudio_client.py`, `local_models.py`, `local_ratings.py`, `routing_advisor.py`, `ui/local_models_page.py`, `routing_advice.py`, `routing_page.py`, `config/local_rating_prompts.json`, `tests/test_local_ratings.py` and `tests/test_routing_advisor.py` are byte-for-byte copies shared with Sentinel. A fix in any of them must land in both repositories in one session. Each finding names which side it touches.

## Findings

### L-1 · P1 · The measurement run can spend more than the guard authorised, records less than it spent, and starts without a click

- **Where:** `services/local_ratings.py:56`, `:578-580`, `:601-619`, `:658-668`; `main.py:1162-1172`, `:1204-1241`, `:1264-1265`, `:1287-1291`, `:1297-1307`, `:1319`.
- **Already recorded** as QM-1 (P2 in `TODO.md` on `main`): no confirmation, ceiling not reserved, billed on chars/4. The points below are new and are why this is rated higher here.
- **Evidence:**
  - The authorised amount is `1.5 × estimate + €0.01`. The estimate assumes 350 output tokens per reference answer and 4 per verdict (`local_ratings.py:578-580`).
  - The calls are sent with no output limit: `_measure_ask` calls `run_backend(provider, model, messages, prompt)` with no `max_tokens` (`main.py:1289-1290`), so each cloud client uses its normal 8,192-token cap.
  - For every other text request the guard reserves the full cap, plus 65,536 thinking tokens for DeepSeek, because the cap may not bound thinking (`services/output_limits.py:20`, `:37-48`). The measurement reserves 4.
  - The run stops "when it spends past what was authorised", but spend is counted as characters ÷ 4 of the visible prompt and reply (`main.py:1199-1201`, `local_ratings.py:663-667`). The provider's real usage is on the stream object and is thrown away: `_measure_ask` joins the text and returns a string (`main.py:1291`). The bill written to the usage table uses the same guess (`main.py:1300-1302`, no `usage=`).
  - `services/gemini_client.py:92-96` says a thinking model can come back "short or empty and is billed anyway".
  - The ceiling is checked once and never enters `_pending_requests` (`main.py:1217-1229` against `:5411-5414`). After one model finishes the next starts by itself (`main.py:1319`), each with its own ceiling.
- **Failure scenario:** a key and its permission tick exist; five local models are found at first launch. The judge is the cheapest priced cloud model. If it thinks before answering "A", the provider bills the thinking tokens for 160 verdicts per model. The app counts one token per verdict, never reaches its stop, and writes a few cents to the ledger. The caps then judge later requests against a total that is too low. Nobody clicked anything. Not run against a real provider.
- **Why P1 and not P0:** the validator is asked, the permission tick is required, and the owner decided on 2026-10-19 that the run starts by itself (plan section 7). If "no paid call outside the request guard" is read strictly, this is the one path in the feature that meets it.
- **Fix:** send a hard output limit (a verdict needs under 16 tokens; cap answers too) and price the estimate on that limit, as the guard does elsewhere. Bill and count from the stream's `usage`. Put the ceiling in `_pending_requests` for the length of the run. Until then, set `AUTOMATIC = False` so only the Measure button, which asks, starts a run.
- **Copies:** `local_ratings.py` is shared (limits, estimate, usage); the `main.py` part is Imprint's.

### L-2 · P1 · A judge that fails reads as a draw, and twenty draws rate the local model equal to the best cloud model

- **Where:** `services/local_ratings.py:592-598` (`parse_verdict`), `:690-708`, `:218-235`.
- **Evidence** (probe, pure Python, 20 prompts per kind, reference rated 1350):

  | Judge behaviour | Result stored |
  |---|---|
  | returns an empty reply | `measured`, every kind 1350.0 (0 wins, 20 ties, 0 losses) |
  | always answers "A" (position bias) | `measured`, every kind 1350.0 |
  | refuses ("I can't help with that.") | `measured`, every kind 1350.0 |

  `parse_verdict("This is a tie")` and `parse_verdict("Both are a good fit, B is better")` both return `A`, because the article "a" is the first matching word. An empty reference answer is stored and reused for every later model (`:690-696`: the cache test is `is None`, and an empty string is not None).
- **Why it matters:** 1350 is the cap, the best rating a local model can get. The picker then shows "measured writing 1350", BEST FIT moves to it at €0, *Local, advise per job* never raises a quality banner, the status line says "within 0 of best", and *Local first* runs it in place of the selected cloud model without asking (`services/routing_advisor.py:430-436`). The judge is by design the cheapest model available, and several of this Mac's models are abliterated, so a refusing or biased judge is a likely case, not a rare one.
- **Fix:** an unreadable verdict is no verdict, not a tie. Match the whole reply against `A`, `B`, `TIE`. Require a minimum of valid pairs per kind (for example 15 of 20), otherwise leave the kind unrated with the reason. Fail the run when both orders return the same letter for most pairs. Reject an empty reference answer and do not cache it. Add tests for each row of the table.
- **Copies:** shared with Sentinel (`local_ratings.py`, `tests/test_local_ratings.py`).

### L-3 · P1 · "Local only" does not stop cloud requests for most agents, and the advised ones fail open

- **Where:** `services/routing_advisor.py:29`, `:83-84`, `:143-145`; `main.py:170-181`, `:979-995`, `:4054-4058`, `:4506-4510`; `ui/panel_routing.py:36-37`, `:59-67`, `:107-111`; `ui/dialogs.py:694-700`; `README.md:903`, `:907`.
- **What the copy says:** "Nothing is sent to a cloud service. If no local model can do a job, it stops and says why." Settings → Models shows that hint with an override row for all eight agents.
- **Evidence (probes on an offscreen window):**
  - App mode and every override set to Local only: `authorize_request` for `manuscript`, `creator` and `music` on Anthropic returned a token each time. The advisor is only asked when a panel passes `resume=` and the request is not per-unit, and only for four agents. Press, Nova, Label, Booth narration, images and video are never asked.
  - Sitebuilder with a cloud model under Local only is refused while the advisor works. When `_advisor_context` returns nothing or raises, `advise` returns True "so advice never blocks a run", and the same request went to Anthropic.
  - An agent's override beats the Mode box. With Kernel's override on *Suggest local* and the box on "Local only": advisor mode `suggest_local`, run path "Hybrid allowed", while the chips still read "Ignored while Mode is Local only". `README.md:903` says the box "still limits the job, whatever the saved mode", and ADR 0004 calls the box a hard limit.
  - A job held on Kernel's banner stays held when the box is moved to Local only; pressing Switch then sent it to Anthropic. A failover offer behaves the same way.
- **Money:** every one of these still showed the paid-request dialog, so nothing was spent unconfirmed. This is a privacy promise the code does not keep.
- **Fix:** enforce it in `authorize_request` and in `_send_chat`, after any override is applied: when the effective mode is Local only, refuse every non-local provider, for every agent and for per-unit requests, and do so even when the advisor fails. Let the box's Local only win over an override, or show the override beside the box. Clear a held job or offer when the mode changes. If the owner prefers the narrow meaning, change the hint to name the agents it covers.
- **Copies:** the enforcement is Imprint's (`main.py`, `ui/panel_routing.py`); a change to `effective_mode` or the hint text is shared with Sentinel.

### L-4 · P2 · On the four panels "Switch for this job" moves the agent to the paid model for good, also when the dialog is declined

- **Where:** `ui/panel_routing.py:120-125`, `:144-166`, `:169-183`; button text `services/routing_advisor.py:544`; `docs/adr/0004-hybrid-routing.md:16`.
- **Evidence (probe, Sitebuilder):** boxes before: `lmstudio · deepseek-r1-distill-qwen-14b`. After one "Switch for this job": `anthropic · claude-sonnet-5-5`. The next job ran on Sonnet with no banner (the dialog did ask). After Switch and then "No" on the dialog the boxes were also left on Sonnet. `_point` writes the boxes and nothing restores them. A rule and *Local first* move them the same way.
- **Why it matters:** the button says one job. ADR 0004 says the selection "is never changed by the advisor, a rule or Local first". README and the Learning Centre do say the panel's boxes are changed, so the behaviour is disclosed, but the button and the ADR say the opposite. Every later job from that panel is a paid one until the user notices. `_point` also blocks the boxes' signals (`:149-150`), so whatever follows a provider change in the panel does not run.
- **Fix:** keep the earlier pair and restore it after the resumed action has been authorised or refused; or pass the override to the panel's action instead of writing the boxes. If the sticky behaviour is wanted, rename the button on panels and correct the ADR.
- **Copies:** Imprint only, unless the label changes (shared).

### L-5 · P2 · A declined switch leaves a job record behind; the agent's next unrelated request is counted as "advice spent" or gets a failover offer

- **Where:** `ui/panel_routing.py:99`, `:132-135`, `:178`, `:220-238`, `:249-261`; `main.py:5512`, `:5550-5551`.
- **Evidence (probe):** Switch, then "No" on the dialog: `panel_routing.jobs == {'webdesign': (anthropic, claude-sonnet-5-5, accepted=True)}`. A following per-unit request of €0.25 for the same agent, recorded normally, turned the tally into `spent: 0.25, accepted: 1`. In a second run the per-unit request failed instead, and the panel showed "claude-sonnet-5-5 could not finish this job … Or try dolphin3.0-llama3.1-8b (local), free."
- **Cause:** `_start` stores the job before the guard has answered, the record is keyed by agent name only, and `finished` and `offer_failover` take whatever is stored. The realistic case is Vector: its image request follows its text request under the same agent key. Two flows of one agent (Quill's write, publish and market) overwrite each other's record at `:99`.
- **Fix:** store the job under the request token once `authorize_request` has minted it, and drop it on any refusal.
- **Copies:** Imprint only.

### L-6 · P2 · "Saved" is the most a cloud request could have cost, not what it would have cost

- **Where:** `main.py:1922-1924`, `:3991`, `:4044`, `:3356`; `services/usage_tracker.py:46-73`; `services/routing_advisor.py:438-440`, `:494-504`, `:564-567`; `README.md:907`.
- **Evidence:** candidates are priced with `max_cost_eur`: the input plus the full 8,192-token output reserve. `saved_by_local` returns that figure and the tally adds it for every local run. Measured in the test database for 400 input tokens on claude-sonnet-5-5: tallied saving €0.0761; a 300-token reply would have cost €0.0035. That is 22 times too high. *Suggest local* shows the same ceiling as "saves about €…".
- **Why it matters:** the Spend rail's "saved local" and the status line state a euro amount the app cannot show. The window tests replace `_text_candidates_for` with fixed costs (`tests/test_routing_phase4.py:130-142`), so the real figure is never exercised.
- **Fix:** after a local run, price the saving from the tokens the run really used, on the cloud model the value rule would have picked. Or label the figure "up to".
- **Copies:** the pricing is Imprint's; any wording change in `routing_advisor.py` is shared.

### L-7 · P2 · The context limit is checked against too little text, and for Ollama not at all

- **Where:** `main.py:3999`, `:4030`; `ui/panel_routing.py:104-106`; `services/local_models.py:162-167`, `:185-189`; `services/lmstudio_client.py:220`; `services/routing_advisor.py:325-330`.
- **Evidence:** the job's size is `len(billable_prompt) // 4` (`main.py:4030`), although the full count of what the worker sends is already computed four lines above it for pricing (`:3999`). Panels pass only their prompt as `billable_prompt`; Quill adds book profile and consistency context in `messages` (`agents/author/panel.py:1068-1078`). Ollama models are built without `max_context`, so the test at `routing_advisor.py:325` can never be true for them. For LM Studio the value is `max_context_length`, the most the model supports; the plan and README promise the loaded context.
- **Failure scenario:** a Quill request whose messages total 40k tokens on a model with a 32k window passes as "good enough" and runs locally, where it is cut or fails. The same on any Ollama model at any length.
- **Fix:** use `in_tokens` for `Job.context_tokens`. Read the loaded context where LM Studio reports one (field name not verified on a live server). Treat an unknown window as unknown and say so, instead of as no limit.
- **Copies:** `main.py` is Imprint's; `local_models.py` and `lmstudio_client.py` are shared.

### L-8 · P2 · Two calls to the Ollama daemon still run on the UI thread

- **Where:** `main.py:948-963` (called from the BEST FIT repaint, `:2101-2104`); `main.py:744-747` (called from `check_memory_before_request`, `:794`, on Send); `services/ollama_client.py:86` (10 s timeout).
- **Evidence:** `mark_oversized_models` calls `self.ollama.model_details()` on every repaint when the agent's provider is Ollama. `assess_local_model` falls back to `self.ollama.model_size_bytes(model)` when the model is not in the cached inventory. Both are HTTP requests. The phase 2 `TODO.md` row says the GUI "reads the cache only".
- **Why now:** phase 1 made the address configurable (`OLLAMA_HOST`). A dead loopback port refuses at once; an address that does not answer blocks the window for up to 10 seconds per repaint. The lab rule is that nothing on the UI thread fetches.
- **Fix:** read sizes from `local_inventory.snapshot()` only, and return "unknown" when the model is not in it.
- **Copies:** Imprint only.

### L-9 · P2 · Quitting during a measurement waits two seconds for work that takes far longer

- **Where:** `main.py:6505-6510`; `ui/workers.py:813-845`; `services/local_ratings.py:682`.
- **Evidence:** `cancel()` is only looked at once per prompt, before four model calls (one local, up to three cloud). `closeEvent` waits 2,000 ms and accepts. The worker's docstring says a quit "does not abandon a call that has been made but not billed".
- **Failure scenario:** the user quits while the local model is answering. The wait times out, the window closes with the QThread still running, the cloud call in flight is never billed in the app, and Qt may abort on "destroyed while thread is still running". Not run. This is the test `TODO.md` already lists as unstable (`test_closing_the_window_cancels_a_running_measurement`).
- **Fix:** check `cancelled` before each call and close the open stream on cancel, so the thread ends promptly. Do not lengthen the wait. Decide whether a cancelled run counts as the model's one automatic attempt (`main.py:1309-1311` records it as one if the signal arrives).
- **Copies:** `local_ratings.py` is shared; the worker and `closeEvent` are Imprint's.

### L-10 · P2 · This branch lacks nine commits from `origin/main`, and its advisor differs from Sentinel's without any test noticing

- **Where:** `tests/test_providers_drift.py:27-29`, `:38-45`.
- **Evidence:** `git log HEAD..origin/main` lists nine commits, among them `45f705d` "Routing advisor: sync with Sentinel (HYBRID_MODE …)". `SIBLING_REPO_DIR=<sentinel checkout> pytest tests/test_providers_drift.py`: 9 passed, 2 failed (`services/routing_advisor.py`, `tests/test_routing_advisor.py`). `origin/main`'s two files are identical to Sentinel's (`diff`, no output). The difference is a renamed constant with the same value, so the findings here hold for `main` too.
- **Why the guard was silent:** it takes the repo name from the folder (`happy-dubinsky-48c27c` becomes "happy") and skips when no sibling folder is found. That is every Claude worktree and, as far as this review can see, CI. "Drift-tested" is only true in the main checkout on this Mac.
- **Fix:** merge `origin/main` before anything from this branch is released. In the drift test, find the main checkout through `git rev-parse --git-common-dir`, and fail instead of skipping unless a variable says the sibling is knowingly absent.
- **Copies:** the test file is not on the shared list; Sentinel's copy has the same weakness (not read).

### L-11 · P2 · A "local" runtime on another machine is still shown as on this Mac, free and private (recorded as S-10; confirmed for routing)

- **Where:** `services/providers.py:124-149`; `main.py:43` (the app's `.env` is loaded into the environment); `services/local_models.py:33-36`; `services/release_kit/plan.py:72-98`.
- **Evidence:** `is_local` is decided by the provider's name. With `OLLAMA_HOST` or `LMSTUDIO_URL` set to another host, the picker still says "On this Mac", the price is €0, no dialog appears, Local only allows it, and manuscript text goes there over plain http. The release kit refuses such an address (`endpoint_problem`); Kernel, the four panels and the measurement run do not use that check. `lmstudio_client.py:15` says "Only localhost is contacted".
- **Also still open** (`TODO.md`, P2 security): the shared LM Studio client's `chat`, `generate`, `_answers` and `model_details` honour proxy settings. Kernel's content goes through `LocalLMStudioClient.stream_chat`, which does not (`main.py:271`, `services/local_endpoint.py:68-108`), so today only discovery and the key probe (`services/api_keys.py:333`) pass a proxy.
- **Fix:** run `endpoint_problem` once where the clients are built and again in `run_backend`; label a non-loopback runtime "another machine" and ask before the first send.
- **Copies:** the check is Imprint's (`local_endpoint.py`); the proxy fix is in the shared client.

### L-12 · P3 · The uncensored tag is missing in several places that name a model

- `services/routing_advisor.py:613-621` (failover text), `:425-427` and `:434-436` (rule and Local first messages), `:469-471`, `:554` (status line). Probe output: "Or try dolphin3.0-llama3.1-8b (local), free." with no tag.
- The picker pill is drawn from the name alone (`ui/widgets.py:110`, `:155`, `:167`, `:240`); `apply_picker_roles` drops the publisher-aware `row["tag"]` (`main.py:1350-1358`). `uncensored_tag("samantha-mistral-7b")` is None; with publisher `cognitivecomputations` it is "uncensored". Settings → Local models shows the tag, the picker does not.
- The owner's rule (plan section 2) is that the tag shows wherever a model is named. **Fix:** store the tag in an item role and append it in the four texts. The advisor file is shared.

### L-13 · P3 · A ratings file that cannot be written or read leads to paid runs being repeated

- `services/local_ratings.py:279-289` swallows `OSError` on save; `:270-277` reads an unreadable file as empty. Either way the model counts as never tried and the automatic run starts again at the next launch. **Fix:** report the failed write and do not start automatic runs while the store cannot be saved. Shared.

### L-14 · P3 · A damaged savings file breaks the spend labels

- `services/routing_advisor.py:625-630` checks only that the file holds an object. With one day stored as a string, `SavingsTally.summary()` raises `AttributeError: 'str' object has no attribute 'get'` (run in a script). `update_usage_labels` calls it after every request (`main.py:5857-5866`). **Fix:** skip rows that are not objects. Shared.

### L-15 · P3 · Taking a failover offer in Kernel replaces whatever was typed meanwhile

- `main.py:4149` sets the message box back to the failed job's text (probe: new text gone). `_resume_held` and `_resend_failed` also send under the agent and tool selected now, not the held job's (`main.py:4193`, `:4204`). **Fix:** keep the typed text, and drop a held job when the agent or tool changes.

### L-16 · P3 · A model can be given another download's file size

- `services/lmstudio_client.py:228-239` takes the first file on disk whose squashed id contains the server's id. With a plain `Qwen3-8B` (5 GB) and `Qwen3-8B-abliterated` (9 GB) on disk, the server id `qwen3-8b` got 9 GB (script, made-up ids; not checked against a live server). The fit check then calls a model too big, or fine, on the wrong number. **Fix:** prefer an exact repo-name match, then the shortest hit. Shared.

### L-17 · P3 · After 2027-01-06, resuming a paused OpenAI book still asks for a paid confirmation for a model that is gone

- `agents/audiobook/panel.py:727-729`, `:770-774`; `services/narrator/converter.py:42-44`. The route menu is also built once (`:210`), so a session left open over the date keeps offering OpenAI. **Fix:** say in the resume question that the model was removed and what the choices are. What OpenAI returns after the date was not checked. The converter is shared with Lab Hub.

### L-18 · P3 · A stopped or failed measurement starts from nothing, and an old rating is never questioned

- `services/local_ratings.py:673-719`: only reference answers are cached (`:690-696`); verdicts for finished kinds are paid again on the next Measure. `set_version` and the reference are stored (`:713-719`) but never compared when the rating is read (`:373-380`), so a rating survives a new prompt set or a reference model that has since been re-rated. Shared.

### L-19 · P3 · The banner says "about €X" for the figure the dialog calls "Up to"

- `services/routing_advisor.py:527-535`, `:616` against `main.py:4370`. Same ceiling as L-6. Shared.

### L-20 · P3 · Tests missing for the branches above

- No test gives the judge an empty, biased or refusing reply (`tests/test_local_ratings.py:245`, `:284` cover a split and clean words only).
- No test reads the panel's boxes after a switch; `tests/test_routing_panels.py:102-105` resets them by hand.
- No test sends an unadvised agent under Local only, or makes the advisor fail under it.
- The window tests stub `_text_candidates_for` and `resolve_backend_model` (`tests/test_routing_phase4.py:126-142`), so real prices never reach the advisor or the tally.
- The automatic run is tested with a fake worker and fake clients; no test checks an output limit or real usage on a measurement call.

## Checked and found sound

1. **A paid switch is authorised and priced again.** Kernel: `_send_chat` estimates on the final route, runs the validator and opens the dialog for any non-local route, override or not (`main.py:4237-4277`). Panels: an answer re-runs the panel's action, which calls `authorize_request` again; only the advice is skipped (`ui/panel_routing.py:94-96`, `:179-183`; `main.py:4506-4557`). Failover is an offer; taking it goes the same way (`main.py:4123-4152`; `ui/panel_routing.py:220-247`). A rule's paid target meets the dialog each time; *Local first* only ever picks a local model (`services/routing_advisor.py:430-436`).
2. **Unknown price is not free in the advisor.** Only positive price rows count (`services/pricing_catalog.py:140-155`); `max_cost_eur` returns None otherwise (`services/usage_tracker.py:69-70`). None sorts last (`routing_advisor.py:371-373`), is left out of the saving (`:498`), and "free" is printed only for a cost of exactly 0, which only a local candidate carries (`main.py:3991`; `routing_advisor.py:534`). An unknown price does pass the budget filter (`:402`, `:607-608`) and the guard then estimates €0: that is QM-3, already recorded.
3. **Value, not recency.** `_cheapest_fit` orders by price known, price, rating, name (`routing_advisor.py:372-373`); `_best` by rating then cheaper (`:358`); the engine's tie-break is cheaper, better rated, fixed id order (`services/recommendations/engine.py`, phase 3 diff). No date or "newer" field exists on a candidate.
4. **Qt.** No `QThread.terminate()` in these files. `local_measure_worker` is named in `closeEvent` (`main.py:6505`). Discovery and `lms server start` run on daemon workers (`ui/workers.py:784-810`). The inventory lock is held for an assignment only (`services/local_models.py:223-242`). The advisor reads caches only.
5. **Local endpoints by default.** Defaults are loopback (`services/providers.py:41-42`); the port correction only ever writes `localhost` and never overrides a set address (`services/lmstudio_client.py:165-192`). No key or header is sent. Timeouts: 3 s connect, 300 s read, 5 s and 60 s on the two `lms` calls, which use argument lists, not a shell.
6. **Registry.** An unknown provider is neither local nor cloud (`providers.py:95-102`); `expand_allowed` never widens a cloud entry.
7. **Rules and tally files** are written through a temp file and `os.replace` (`routing_advisor.py:633-648`); a corrupt rules file reads as empty.
8. **Measurement, the parts that hold.** A result is never placed above the reference; a refused run leaves the model unrated with a Measure button; the Measure button names the models and the ceiling before it starts (`main.py:1230-1240`).
9. **Narration route.** Booth and the converter carry the same date; the default moves on that date; a new job without a route gets the current default.

**Tests run** (this worktree, main checkout's venv, while a full run was going):
- `test_routing_advisor`, `test_local_ratings`, `test_routing_phase1` to `4`, `test_routing_panels`, `test_narration_route_retirement`, `test_providers_registry`, `test_local_fallback_lmstudio`: 326 passed in 238 s.
- `test_providers_drift` with `SIBLING_REPO_DIR` set: 9 passed, 2 failed (L-10).
- Eleven probe tests and two scripts, kept outside the repo in the session scratchpad; their output is quoted in the findings.

## Not verified

- Anything against a live LM Studio or Ollama server, a real judge or a real provider bill. No network call was made.
- The full suite, lint (ruff is not installed in the venv; no ratchet comparison was made) and CI on GitHub.
- Whether Qt really aborts in L-9; the LM Studio field for the loaded context in L-7; LM Studio's real ids in L-16; OpenAI's answer after the retirement date in L-17.
- Sentinel's side beyond the byte comparison of the shared files.
- `ui/widgets.py` painting beyond the tag; the tag in the usage log and in BEST FIT reasons.
- Phase 0's "one price source" (`tests/test_settings_pricing.py` was not run).
- `services/api_keys.py`'s LM Studio probe and its environment swap.
- The Learning Centre lessons other than module 12, and the agent READMEs from `70dc209` beyond the routing sentences.
