# Quill — TODO

> **Legend** — priority `P0` critical · `P1` high · `P2` normal · `P3` low
> categories `security` `bug` `feature` `performance` `design` `docs` `testing` `infra` `research`
> owner `@me` (needs you — accounts, keys, money, judgement) · `@ai` (Claude can do this)
> agent `agent:<key>` (optional; only meaningful in a parent project's shared TODO.md — not needed here, this file already belongs to Draft alone)

---

## v1 — current

- [x] `P1` Move the Draft panel and handlers from `main.py` into this package. Done 2026-09-21, the last panel of Phase 4: `panel.py` owns the project bar, book profile, the Write page (compose deck, manuscript tabs, chapters, document bar) and the Publish & Market pages, with all three flows keeping per-flow request tokens and the still-running-worker guard. The responsive footer moved into the panel's own resizeEvent (the app-level event filter now only handles tooltips); the next-step advisor stays on the umbrella because Press shares its banner; save/export dialog defaults moved onto the writable base.
- [x] `P1` Bind drafts, profiles and exports to the shared Project record. Done 2026-09-23: named projects isolate and restore Book Profile plus all four manuscript editors, autosave and flush on close, and share title/byline with the Project record. Save Draft and EPUB/DOCX/PDF export now record durable project artifact links without taking ownership of the external files. Press can explicitly load the current working draft; an approval/version workflow remains on its own card.
- [x] `P2` Add continuity tests across long chapter-generation sessions. Done 2026-10-06 (tests/test_author_continuity.py): a simulated three-chapter session asserts every successive generation's system context carries the established characters, world rules and the previous chapter's ending; the recent-draft tail is pinned as a 3000-char window (not the whole book, and ordered after the RECENT STORY TEXT header); empty notes impose no context.
- [x] `P2` Add evidence/citation controls for non-fiction drafting. Done 2026-10-06: a Sources tab exists only in Non-Fiction mode; when sources are declared, the EVIDENCE RULES block restricts factual claims to what they support, requires inline citation of the supporting source, forbids inventing sources, and marks everything else [UNSOURCED] — and the finish status counts the marks ("N claim(s) marked [UNSOURCED]: verify or cut before publishing"). No sources, no rules: an empty tab must not teach the model to decorate.
