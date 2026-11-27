# Security review (Secure): Manuscript redesign slice 1, the shell (PR #30)

- **Commit:** ef1f9af, branch `claude/manuscript-shell-slice1` (includes the merge of `origin/main`)
- **Date:** 2026-11-27
- **Scope:** `git diff origin/main...HEAD`, 54 files. The security-relevant ones:
  - `ui/motion.py`, `ui/spotlight.py`, `ui/dialogs.py`, `ui/theme.py`, `ui/shell/*`
  - `services/usage_tracker.py`, `main.py`
  - `Imprint.spec`, `assets/shell/*.svg`
- **Role:** `security-engineer`, phase 8, read-only. The orchestrator wrote this file from the agent's report.
- **Playbook:** `docs/playbooks/security-engineer.md` (`last-reviewed: 2026-11-11`, current).
- **Not run:** the full suite, `pip-audit`, gitleaks (CI's gitleaks job is blocking), and a live launch.

## Threat summary
The spec's expectation holds: this slice adds no new network, secrets, auth or untrusted input. What changed:

- **No new endpoints or clients.** The only new URLs are two PR links in docs.
- **No new key handling.**
- **No dependency added.** No requirements, `pyproject` or workflow change.
- **One new native call:** a read-only `ctypes` message to `NSWorkspace` for macOS Reduce Motion (`ui/motion.py`).
- **New settings:**
  - `ui_theme`, `ui_light_adopted` and `reduce_motion` are stored in SQLite with parameterised SQL.
  - `show_tooltips` is stored in `config/settings.json`.
- **New rendered content:** theme tokens interpolated into HTML and CSS, and bundled SVG icons drawn by `QSvgRenderer`.
- **Money:** a new `cost_type = "unpriced"` label. The cost arithmetic and the request guard are unchanged.

Threat model:
- **Assets:** provider keys in `.env`, the user's manuscripts and project database, the spend caps and the request guard, and `config/settings.json`.
- **Trust boundaries:**
  - user to GUI;
  - GUI to provider APIs (unchanged);
  - bundled files (`docs/agents`, `docs/learn`, `assets/`) to the renderer, which are trusted because they ship in the bundle;
  - process to `libobjc` and AppKit (new).
- **Entry points touched:** Settings › Appearance, the Docs viewer, Cost History and the Run log, the "Show me" spotlight, and usage logging.

## Findings

**P0, P1 and P2:** none.

### P3-1. The Docs viewer puts unescaped Markdown into HTML, with external links enabled
This is pre-existing and recorded as a trust note.

- **Location:**
  - `main.py:6817` (`<p>{line}</p>`);
  - `:6796-6808` (headings, list items and blockquotes use the raw line);
  - `:6826` (inline regex) and `:6854` (`setHtml`), followed by `setOpenExternalLinks(True)`.
- **Already on main:** `git show origin/main:main.py` has the same unescaped paragraph and `setOpenExternalLinks(True)`. This slice only swapped hard-coded colours for theme tokens.
- **The new interpolation is safe.** `theme.palette()` returns static values, and `theme.current()` accepts only a key in `THEMES` (`ui/theme.py:345-349`).
- **The source is trusted.** The text comes from bundled `docs/agents/*.md` and `agents/<name>/README.md`.
- **Impact:** none today. If agent docs ever carry model or user text, a raw `<a href>` or `<img src>` could fetch remotely or open a link.
- **Fix direction:** run `html.escape` on each line in `md_to_html` before the inline substitutions, or drop `setOpenExternalLinks(True)`.

### P3-2. `reduce_motion` is read on every animation, as a free string
- **Location:** `ui/motion.py:96-101`.
- **Behaviour:** any value other than `"1"`, including a corrupt one, reads as off, and exceptions are caught.
- **Impact:** a tampered value only allows motion that is already capped at 300 ms, with no loop and no motion in a typing field. The macOS setting is still honoured on its own.
- **Fix direction:** optional. Caching the value would be a performance gain, not a security one.

### P3-3. `show_tooltips` is coerced with `bool()` without a type check
This is pre-existing in pattern.

- **Location:** `main.py:450`, `516`, `2599`.
- **Behaviour:** a hand-edited `"false"` string reads as true.
- **Impact:** cosmetic. The file is local and owned by the user.
- **Fix direction:** check `isinstance(v, bool)`.

## Checked, no finding

1. **`ctypes` and Objective-C** (`ui/motion.py`)
   - The three `CFUNCTYPE` prototypes are built over `objc_msgSend`'s address. Each matches its selector's signature: `sharedWorkspace` is `id (id, SEL)`; `accessibilityDisplayShouldReduceMotion` is `BOOL (id, SEL)`; `respondsToSelector:` is `BOOL (id, SEL, SEL)`.
   - None of them is variadic, so the arm64 variadic-ABI hazard does not apply.
   - No buffers, no writes, no retain or release.
   - `respondsToSelector:` is checked first, which avoids an unrecognised-selector abort.
   - Python exceptions fall back to False.
   - Off macOS and offscreen, it returns before any library load. This was read in the code, not run.
   - `appkit_guard` swizzles only `NSEvent clickCount` and `type` and sets its own `restype` on the shared symbol. The motion code uses separate prototypes, so the two do not interfere. `ui/app_identity.py:75-76` uses the same pattern.
   - Library paths are absolute or come from `find_library`.
   - **Not verified:** a run in a real macOS 27 desktop session.
2. **HTML in the dialogs**
   - Cost History and the Run log escape every user- or model-derived field through `_cell()` (`html.escape`).
   - `_cost_cell` returns the word "unknown" or a float formatted to two decimals.
   - Status colours come from theme tokens.
   - The status cards pin `PlainText` for provider-derived ids.
3. **Settings writes**
   - `set_current` refuses any key outside `THEMES` before saving, and `current()` validates again on read.
   - `adopt_light_once` runs once, and a database error returns False.
   - `save_setting` is parameterised.
   - Cancel in Settings restores the previous theme.
4. **Money and the request guard**
   - Only `log_request`'s cost-type label changed. Cost stays 0.0, so the totals, caps and guard are unchanged.
   - `price_row_found` uses the same `resolve_price_row` as before.
   - The new count query is read-only and parameterised.
   - The diff touches no guard or provider-client file.
   - `ui/shell/` calls no provider.
   - **Not verified:** a hand trace of every `log_request` caller. QA's `tests/test_usage_unpriced.py` covers it.
5. **Packaging and SVG**
   - `Imprint.spec` adds a data tuple only.
   - Grepping `assets/shell/*.svg` for `<script`, `href`, `<image`, `<foreignObject` and `<use` finds 0 matches.
   - The `currentColor` replacement inserts theme tokens only.
   - `QSvgRenderer` runs no script and fetches nothing external. The icons are bundled.
6. **Lesson spotlight**
   - `lessonAnchor` is set only in code, to fixed names (`help_btn`, `project_menu_btn`). It is never read from `docs/learn` or `help_map.json`.
   - `anchor_for` returns a value only if it is a `QWidget`.
   - The pre-existing `_find_control` lookup only rings a widget. At worst it raises an error; it cannot run code.
7. **Secrets and personal data**
   - The added lines of the diff were grepped for keys, tokens, `sk-` patterns, email addresses, `/Users/` paths, "password", "canvas", "figma" and "claude.ai". None was found.
   - The added URLs are the SVG namespace and two PR links. The owner's design canvas link is not present.
8. **Dependencies**
   - None added. `PySide6.QtSvg` ships with PySide6.
   - CI's pip-audit findings for `pypdf` and `soupsieve` are pre-existing and tracked in `TODO.md` (P1 row). The CVE ids were not re-verified here.

## Verdict
**Nothing blocks Release from the security side.** There are no P0, P1 or P2 findings, and the three P3s are optional hardening. The one new native call is read-only, guarded by `respondsToSelector:`, and falls back to False.
