# Router — TODO

> **Legend** — priority `P0` critical · `P1` high · `P2` normal · `P3` low
> categories `security` `bug` `feature` `performance` `design` `docs` `testing` `infra` `research`
> owner `@me` (needs you — accounts, keys, money, judgement) · `@ai` (Claude can do this)
> agent `agent:<key>` (optional; only meaningful in a parent project's shared TODO.md — not needed here, this file already belongs to Router alone)

---

## v1 — current

- [x] `P1` Remove stale Sentinel/security keyword routes.
- [x] `P1` Validate every returned key against `agents.catalog`.
- [x] `P2` Make confidence and fallback behavior explicit. Done 2026-09-30: `route()` returns a `RouteDecision` with three honest tiers — `addressed` (named the tool: certain), `intent` (keyword hit; `matches` carries every (agent, keyword) pair so an ambiguous request is visible instead of silently first-match-wins, and the reason says "also matched …"), `fallback` (nothing matched; the reason says Chat is the default rather than pretending a verdict). `classify()` stays the decision's key for existing call sites; the umbrella's Route button shows where on the card and why/how-sure in its tooltip. Five decision tests. Follow-up in `4570784`: ambiguity reasons name catalog codenames rather than internal keys, and the tooltip is cleared on every route update so it cannot describe an older decision.
- [ ] `P3` `design` `@me` Decide whether an ambiguous `intent` decision (`RouteDecision.ambiguous`) should still switch workspaces silently. Today Auto Route takes the first match in `ROUTES` order and only the Chat routing card's tooltip mentions the other candidates; asking the user to pick would be safer but adds a click.
