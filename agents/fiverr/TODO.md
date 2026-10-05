# Stamp — TODO

> **Legend** — priority `P0` critical · `P1` high · `P2` normal · `P3` low
> categories `security` `bug` `feature` `performance` `design` `docs` `testing` `infra` `research`
> owner `@me` (needs you — accounts, keys, money, judgement) · `@ai` (Claude can do this)
> agent `agent:<key>` (optional; only meaningful in a parent project's shared TODO.md — not needed here, this file already belongs to Client Gigs alone)

---

## v1 — current

- [x] `P1` Move the Client Gigs panel and handlers from `main.py` into this package. Done 2026-09-21 (commit c4b9cf5, two sessions jointly): `panel.py` owns the layout, all four guarded flows with per-flow request tokens, and the order log; the umbrella keeps thin compatibility delegates and the workers for its global Stop/shutdown sweeps.
- [x] `P2` Store briefs, revisions and deliveries as one client order record. Done 2026-10-05: `fiverr_orders` (agents/fiverr/orders.py, Qt-free) holds the brief, brand kit, an event history (a returning client's new round is a revision event on the same open order — newest instructions win, history keeps the past), the generated image paths, the delivery text and the gig listing. The Orders tab reads these rows — it survives restarts — and selecting an order reloads the whole record into the workspace.
- [x] `P2` Add brand-kit inputs and reusable client preferences. Done 2026-10-05: Brand fonts / voice / rules inputs join the brief; they persist on the client's order and reach BOTH prompt builders — only when non-empty ('Fonts: N/A' teaches the model nothing). Typing a known client's name auto-fills their stored preferences into EMPTY fields only, so typed-in changes always win.
- [ ] `P3` Add marketplace-policy reminders before listing export.
