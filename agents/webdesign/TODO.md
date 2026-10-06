# Sitebuilder — TODO

> **Legend** — priority `P0` critical · `P1` high · `P2` normal · `P3` low
> categories `security` `bug` `feature` `performance` `design` `docs` `testing` `infra` `research`
> owner `@me` (needs you — accounts, keys, money, judgement) · `@ai` (Claude can do this)
> agent `agent:<key>` (optional; only meaningful in a parent project's shared TODO.md — not needed here, this file already belongs to Site Builder alone)

---

## v1 — current

- [x] `P1` Site Builder's panel, guarded generation lifecycle, output parsing, copy and export now live in `panel.py`.
- [x] `P2` Retire temporary host-control aliases after recommendation and tooltip bindings use the panel contract directly. Done 2026-09-21, in the sweep that finished the pattern music started: the panel no longer mirrors its widgets onto the host, every shared consumer (tooltips, recommendation installs, context watchers, panel_base lookup) resolves through `GodAI._find_control()`, and the ownership test asserts the absence of aliases.
- [x] `P2` Export structured multi-file projects, not only one response blob. Done 2026-10-05: **Export Project…** writes `index.html` + extracted `styles.css`/`script.js` into a timestamped folder — inline assets move out with references injected (`<link>` into head, deferred `<script src>` before `</body>`), a `<script src=…>` stays where it is, and empty asset files are not written. `agents/webdesign/export.py`, Qt-free.
- [x] `P2` Add automated HTML and accessibility validation before export. Done 2026-10-05: static checks (doctype, html lang, title, viewport, img alt, labeled form controls, empty links, duplicate ids, heading-order jumps) run before BOTH export paths; findings list in a dialog where the user decides — export anyway is always available, and the wording says "checks", never "compliance", because these are text heuristics, not a browser. 15 tests incl. one mutation per rule.
- [ ] `P3` Add safe local preview with explicit external-resource controls.
- [ ] `P3` `bug` `@ai` `_passes_preflight()` sets the status to "Exported with N open finding(s)." as soon as the user answers Yes to "Export anyway?" — before the save/folder dialog. Cancelling that dialog (or a failed write) leaves a status claiming an export that never happened; set it after the files are written instead.
- [ ] `P3` `docs` `@ai` Retake `docs/learn/img/agent-webdesign.png` (captured 2026-09-30): the action row now has an **Export Project…** button (added 2026-10-05) that the screenshot does not show.
