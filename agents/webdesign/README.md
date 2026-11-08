# Sitebuilder

Owns responsive HTML, CSS and JavaScript generation plus front-end layout and
accessibility guidance. Imprint imports `WebdesignAgent` from
`agents.webdesign`. The package also owns the `WebdesignPanel` workspace and
its local export actions (a single `.html` file, or a project folder with
pre-export HTML/accessibility checks); Imprint still supplies provider execution, spending
authorization and run history. Live preview remains future work.

## Files

- **`__init__.py`** — package surface. Re-exports `WebdesignAgent` and lazily
  exposes `WebdesignPanel` so non-GUI imports do not initialize Qt.

- **`panel.py`** — the brief form, model pair, output indicators and read-only
  HTML/CSS/JS tabs, plus the guarded generation lifecycle, **Copy All**,
  **Save .html** (single file) and **Export Project…** (2026-10-05,
  `435eb14`). Both export paths first run `_passes_preflight()`, which calls
  `export.validate()` on the full HTML: no findings → "Checks passed."; any
  findings → a dialog listing up to 12 (`[error]` / `[warning]`) with
  "Export anyway?", so the user always decides. **Export Project…** then asks
  for a folder and writes `site_<timestamp>/` with the files from
  `export.split_project()`. Save, Export and Copy enable only after a
  successful generation; Clear disables them again. A denied paid request
  leaves Generate available. Host-control aliases were retired 2026-09-21:
  shared wiring resolves controls through `host._find_control()`, and
  `HOST_CONTROLS` stays as the published contract of what the panel owns.
  The Provider menu offers Ollama, LM Studio, OpenAI, DeepSeek, Kimi,
  Gemini, Anthropic (default) and Qwen. Since 2026-10-21 (`44c6b18`)
  **Generate** passes `resume=self.generate` and the messages it will send
  to `host.authorize_request()`: the guard prices all of them, and the
  routing advisor (`ui/panel_routing.py`) may hold the job on an advice
  banner at the top of the panel; an answer puts the chosen model in the
  Provider and Model boxes and runs Generate again, so the paid-request
  dialog and caps still decide. A failed run passes its error to
  `abandon_request(error=…)` for the advisor's failover offer. Since the
  audit P1 fixes (`12604e9`) the status line wraps, and a reply cut at the
  8,192-token length limit shows the `[Cut off] … the result is incomplete`
  notice from `services/output_limits.result_notice()` instead of
  "Generation complete."

- **`export.py`** — Qt-free structured export and pre-export validation.
  `split_project(full_html)` returns `{filename: content}`: inline `<style>`
  blocks move to `styles.css` (a `<link>` is injected before `</head>`),
  inline `<script>` blocks move to `script.js` (a deferred `<script src>` is
  injected before `</body>`), a `<script src=…>` stays where it is, and
  empty CSS/JS files are not written; `index.html` is always present.
  `validate(html)` returns `Finding(level, message)` records from text
  heuristics, not a browser — errors for a missing doctype, `<html>` without
  `lang`, missing/empty `<title>`, `<img>` without `alt`, form controls with
  neither a `<label for>` nor `aria-label(ledby)`, and duplicate ids;
  warnings for no viewport meta, empty links without `aria-label`, no `<h1>`
  and heading-level jumps. The panel's wording says "checks", never
  "compliance".

- **`agent.py`** — the agent itself. `WebdesignAgent` is a thin wrapper
  (`name = "webdesign"`) whose `build_messages(prompt)` returns the
  `[system, user]` message pair Imprint sends to the model. Nearly all of the
  behaviour lives in the module-level `SYSTEM_PROMPT` string, which instructs
  the model to:
  - clarify purpose/audience, palette and style before generating when the
    request is underspecified, defaulting to vanilla HTML/CSS/JS unless a
    framework is named;
  - output complete, self-contained, semantic, mobile-first responsive
    markup with hover/focus states and basic accessibility (aria labels, alt
    text, tab order), briefly commenting non-obvious CSS/JS;
  - prefer CSS custom properties over inline styles, vanilla ES6+ over
    jQuery, and placeholder/inline-SVG assets when none are supplied;
  - lead with code and keep explanations short.

- **`recommendations.py`** — routing metadata, not agent logic. Defines
  `RECOMMENDATION_PROFILE`, an `AgentProfile` (from
  `services.recommendations`) that tells Imprint's model/provider selector how
  to weight this agent: task tags `("code", "structured", "analysis")`,
  `quality_weight=.45`, `reliability_weight=.25`, and a `provider_affinity`
  table ranking providers for this agent's work (openai .98, anthropic .96,
  kimi .94, deepseek .92, qwen .88, gemini .86, ollama .70, lmstudio .70). Imprint reads this
  to pick a backing model per provider availability/preference, independent of
  the `WebdesignAgent` class itself.

User guidance: `docs/agents/webdesign.md`. Run focused coverage with
`pytest tests/test_agents_scenarios.py -k webdesign` and
`pytest tests/test_webdesign_export.py tests/test_webdesign_panel.py`.
