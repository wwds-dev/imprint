# Router

Internal intent classifier used by the umbrella runtime.  It is infrastructure,
not a visible creative workspace.  Its public API is
`agents.router.RouterAgent`.

Routing should return stable agent keys from `agents.catalog`; it must never
execute provider calls or bypass the shared request guard.

## Files

- `__init__.py` — public surface of the package: re-exports `ROUTES` and
  `RouterAgent` from `agent.py`.
- `agent.py` — the whole implementation. `ROUTES` is an ordered tuple of
  `(agent_key, keyword_tuple)` pairs covering nine modes —
  `video`, `social`, `audiobook`, `music`, `webdesign`, `fiverr`, `creator`,
  `manuscript`, `author` — each matched against a handful of lowercase
  trigger phrases (e.g. `video` matches "video", "youtube", "shorts",
  "reel", "storyboard", "sora"; `manuscript` matches "query letter",
  "synopsis", "kdp", "goodreads", "book marketing"; `author` matches "write
  a chapter", "novel", "manuscript", "book outline"). `RouterAgent.classify(
  text)` case-folds the input and returns the key of the first route whose
  any keyword is a substring of it; ordering in `ROUTES` therefore matters
  whenever two routes' keyword lists could both match the same input. If no
  route matches, it falls back to the literal key `"chat"` (not itself an
  entry in `ROUTES`). There is no scoring, no ML model and no external call
  — it is a pure substring matcher.

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
