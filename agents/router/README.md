# Router

Internal intent classifier used by the umbrella runtime.  It is infrastructure,
not a visible creative workspace.  Its public API is
`agents.router.RouterAgent` and the `RouteDecision` it returns; the umbrella's
**Auto Route** button (`GodAI.auto_route_agent()` in `main.py`) calls
`RouterAgent().route()`, switches to the decided agent, and puts the
decision's confidence tier and reason in the **Chat routing** card's tooltip.

Routing should return stable agent keys from `agents.catalog`; it must never
execute provider calls or bypass the shared request guard.

## Files

- `__init__.py` — public surface of the package: re-exports `ROUTES`,
  `RouteDecision` and `RouterAgent` from `agent.py`.
- `agent.py` — the whole implementation. `ROUTES` is an ordered tuple of
  `(agent_key, keyword_tuple)` pairs covering nine modes —
  `video`, `social`, `audiobook`, `music`, `webdesign`, `fiverr`, `creator`,
  `manuscript`, `author` — each matched against a handful of lowercase
  trigger phrases (e.g. `video` matches "video", "youtube", "shorts",
  "reel", "storyboard", "sora"; `manuscript` matches "query letter",
  "synopsis", "kdp", "goodreads", "book marketing"; `author` matches "write
  a chapter", "novel", "manuscript", "book outline").

  `RouterAgent.route(text)` case-folds the input and returns a frozen
  `RouteDecision(key, confidence, reason, matches)` (added 2026-09-30,
  `cb8e99f`). `confidence` is one of three named tiers, not a probability:
  - `"addressed"` — the text named an agent (see below); reason
    `addressed by name ("<Codename>")`.
  - `"intent"` — at least one keyword is a substring of the text. The key is
    still the first route in `ROUTES` order that matched, so ordering matters,
    but `matches` now carries every `(agent_key, keyword)` hit and the
    reason reads `matched "<keyword>"`, adding `— but also matched <other
    codenames>` when several agents hit. The `ambiguous` property is true
    when more than one agent matched. Since `4570784` those reasons name the
    catalog codenames, not internal keys.
  - `"fallback"` — nothing matched; the key is the literal `"chat"` (not an
    entry in `ROUTES`) and the reason says Chat is the default rather than
    claiming a verdict.

  `RouterAgent.classify(text)` stays as `route(text).key` for call sites that
  only need the key. There is no numeric scoring, no ML model and no external
  call — keyword matching is plain substring search.

  Before that table runs, `classify()` checks whether the text **addresses**
  an agent by name. The 2026-09-30 rename gave the agents codenames, and
  "open Booth" routed to Chat because the router only ever knew intent words.
  The names are read from `agents.catalog.AGENT_SPECS`, not copied here, so a
  relabel cannot leave the router answering to a name that no longer exists —
  a test asserts `classify(f"open {spec.label}") == spec.key` for every agent
  with a workspace.

  Addressing is narrow on purpose. Half the codenames are ordinary English, so
  a bare token match would send "press release" to `manuscript`, "white label"
  to `music` and "stamp the document" to `fiverr`. A codename therefore routes
  only after an opening verb (`open`, `use`, `switch to`, `go to`,
  `take me to`) or when the whole message is the name. Addressing wins over
  the keyword table when both match: naming a tool is the more explicit act.
  This is the one part of the router that is anchored rather than substring —
  `agent.py` uses `re.fullmatch`/`\b` for it.
