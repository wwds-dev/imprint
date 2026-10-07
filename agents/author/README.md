# Quill agent (`agents.author`)

Owns long-form ideation, outlining, character and world development, drafting,
continuation and revision for fiction and non-fiction.  Imprint imports
`AuthorAgent` from `agents.author`; the private implementation is `agent.py`.

This package owns the editor and its project-scoped working state. The umbrella
owns project selection, provider execution and the request guard. Book export
lives in this package's `book_exporter.py`; Save Draft and EPUB/DOCX/PDF export
record project artifact links when a named Project is selected. The files
remain at the location chosen by the user, including after Project deletion.

## Files

- `__init__.py` — public interface; re-exports `AuthorAgent` from `agent.py`.
- `agent.py` — the `AuthorAgent` implementation plus its four system prompts:
  - `SYSTEM_PROMPT` / `SYSTEM_PROMPT_NONFICTION` — drafting personas for
    fiction and non-fiction respectively, with a structured
    `[DRAFT]`/`[OUTLINE]`/`[CHARACTER]` response format and genre/voice/
    argument guidance.
  - `PUBLISH_SYSTEM_PROMPT` — publishing-document specialist (synopses, query
    letters, book proposals, back-cover blurbs, author bios, chapter
    breakdowns) with separate fiction vs. non-fiction document standards and
    comp-title strategy.
  - `MARKET_SYSTEM_PROMPT` — marketing copywriter covering per-platform copy:
    Amazon description, a full KDP listing package, Goodreads blurb,
    Instagram, X/Twitter thread, TikTok/BookTok caption, newsletter, press
    release, book club questions, ARC outreach, podcast pitch, author website
    bio, Pinterest pin description, YouTube description and launch-team email.
  - `AuthorAgent.build_messages(prompt, consistency_context, book_profile_context,
    content_type)` — builds the chat payload for drafting, selecting the
    fiction or non-fiction system prompt by `content_type` and appending
    book-profile / consistency context when supplied.
  - `AuthorAgent.build_publish_messages(prompt, book_profile_context)` /
    `build_market_messages(prompt, book_profile_context)` — same pattern using
    `PUBLISH_SYSTEM_PROMPT` / `MARKET_SYSTEM_PROMPT`.
- `panel.py` — `AuthorPanel`, the manuscript workbench: the project bar and
  Book Profile, the Write page (compose deck, manuscript/outline/characters/
  world tabs, chapters tab, a Sources tab in Non-Fiction mode only, document
  bar), and the Publish & Market sub-pages. The whole panel scrolls below its
  minimum height (a `ScrollContent` in `ui/widgets.scrollable()`) instead of
  squeezing the editor; nothing inside it scrolls on its own,
  each of the three flows (write/continue, publish, market) keeping its own
  request token and running-worker guard so Stop only ever cancels its own
  flow. Save Draft and EPUB/DOCX/PDF export record project artifact links
  without taking ownership of the files on disk. Non-fiction evidence
  controls: the **Sources** tab (one source per line) is added when Type
  switches to Non-Fiction and removed otherwise; when it holds anything,
  `_build_evidence_block()` appends an EVIDENCE RULES block to the
  consistency context sent with Write/Continue — assert only what the
  declared sources support, cite the source inline, never invent sources,
  mark every other factual claim `[UNSOURCED]`. An empty tab (or fiction
  mode) adds no rules. The finish status counts `[UNSOURCED]` marks across
  the whole draft, not just the new chunk ("N claim(s) marked [UNSOURCED]:
  verify or cut before publishing"). Sources travel with the project
  workspace state (and with the unscoped Book Profile setting when no
  Project is selected), schedule the workspace autosave when edited and are
  cleared with the other editors, so one book's bibliography never reaches
  another's prompt. The chapter-stats and status labels are styled through
  `ui.theme.themed()` so they re-colour on a theme switch. Host-control aliases were
  retired 2026-09-21: the panel no longer mirrors its widgets onto the
  umbrella (`HOST_CONTROLS` stays only as the published contract of what it
  owns); the next-step advisor now reads this panel directly, with a `None`
  guard for when it has not been built yet.
- `book_exporter.py` — chapter detection (`split_into_chapters()`,
  `find_chapter_offsets()`) and EPUB/DOCX/PDF export (`export_book()`).
- `recommendations.py` — exports `RECOMMENDATION_PROFILE` (an `AgentProfile`)
  tagged `creative`, `longform`, `editing`, weighted heavily toward quality
  (0.48) and context (0.16) over cost (0.08), with affinity across most
  providers (Anthropic 1.0, OpenAI 0.86, Gemini 0.82, Qwen 0.82, Kimi 0.80,
  DeepSeek 0.74, Ollama 0.66). Discovered by
  `agents.recommendation_profiles.profile_for("author")`.

User guidance: `docs/agents/author.md`.

Run focused coverage with `pytest tests/test_agents_scenarios.py tests/test_book_pipeline.py tests/test_author_continuity.py`
(the last pins multi-chapter continuity context and the Sources/evidence rules).
