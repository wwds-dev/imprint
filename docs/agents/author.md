# BOOK AUTHOR — Long-form writing studio

`key: author` · class: `agents/author/agent.py → AuthorAgent` · panel: `build_author_panel()` · handlers: `author_write()`, `author_continue()`, `author_pub_generate()`, `author_mkt_generate()`

> Hands off where this agent's Publish/Market modes stop short (real sales data, quote content, launch checklist): see the **Press**, `key: manuscript` — [manuscript.md](manuscript.md).

## What it does
A three-mode writing workspace for novelists and non-fiction authors alike:
1. **Write** — draft prose, outlines, characters, and world-building into separate editable tabs (fiction) or chapters/arguments (non-fiction, toggled via **Type**); every generation call auto-injects established Characters/World, recent draft text, and the Book Profile for continuity; a live **Chapters** tab navigates the draft; export to formatted EPUB, DOCX, or PDF.
2. **Publish** — generate query letters, synopses, blurbs, KDP metadata, and full KDP listing packages (categories, backend keywords, pricing).
3. **Market** — generate launch posts, ARC outreach, newsletter/press copy across 15 platforms.

All three modes read from one **Book Profile** (Title, Author, Content Type, Genre, Hook, Target Reader, Comp Titles, Publishing Path) — set it once, save it, and stop re-explaining the book on every request.

## Inputs (panel controls)
| Control | Purpose |
|---|---|
| Title / Author / **Type** (Fiction/Non-Fiction) | Project Bar — Type switches the Write-mode system prompt and Task list. |
| **Book Profile** (collapsible) | Hook, Target Reader, Comp Titles, Publishing Path, **Save Profile** — persisted, auto-loads next launch. |
| Task / mode | Options depend on Type — fiction: Write Scene / Develop Characters / Build World / etc.; non-fiction: Write Chapter / Strengthen Argument / Tighten Structure / etc. |
| Direction / instruction box | What to write next. |
| Provider / Model | Large-context model recommended. |
| Write / Continue / Stop / Save / Clear | Drafting lifecycle. |
| Author name / Format / **Export Book** | Renders the Draft tab to EPUB, DOCX, or PDF with a title page and detected chapter breaks. |
| Publish + Market sub-panels | Their own generate / copy / save buttons. |

## Outputs
Write mode tabs: **Draft**, **Outline**, **Characters**, **World**, **Chapters** (read-only navigator) — all editable except Chapters. Sidebar: word count, scene count, exported book file. Publish/Market render generated documents into their own areas with copy/save.

## How it works
`AuthorAgent.build_messages()` selects `SYSTEM_PROMPT` (fiction) or `SYSTEM_PROMPT_NONFICTION` based on `content_type`; both use structured markers — fiction adds `[CHARACTER]`/`[WORLD]` on top of the `[DRAFT]`/`[OUTLINE]` markers non-fiction also uses. `_parse_author_sections()` routes each marked block to the right tab, handling missing markers gracefully (non-fiction output just never populates Characters/World). `author_continue()` resends the current draft as context to keep going.

**Draft safety** (audit QB-1, 2026-11-20): Write never clears the Draft. Prose tasks (Write Scene / Chapter / Dialogue, Add Case Study / Example, Continue Draft) add their text after the existing Draft; Generate Outline, Develop Characters and Build World write only to their tab; Revise / Improve, Tighten Structure and Strengthen Argument revise the Draft selection, or the whole Draft when nothing is selected, and replace exactly that text as one edit (⌘Z in the Draft brings the earlier version back). An error or Stop never removes Draft text, so the workspace autosave cannot store a loss. **Deliberate limit:** Revise works on up to 20,000 characters (about 3,300 words) per run, because one reply is capped at 8,192 tokens — 6,000 characters (about 1,000 words) with a local model (Ollama, LM Studio), whose context holds the text and its revision together; for more, select a chapter or passage. A revision cut off at the length limit, or under half the length of its text (a quarter for Tighten Structure; a local model can silently drop part of a long prompt), leaves the Draft unchanged; the Draft is read-only while a revision runs.

**Book Profile**: `_author_build_book_profile_block()` formats the profile fields into a "BOOK CONTEXT" system-prompt block, appended in all three modes (`build_messages()`, `build_publish_messages()`, `build_market_messages()` all accept `book_profile_context`). Verified: profile fields (hook, target reader, comp titles) show up organically in generated Publish/Market copy without being re-typed into those modes' own per-request fields. Persisted via `services/database.py`'s generic `settings` table (`author_book_profile` key, JSON) — no new table needed.

**Consistency memory**: `_author_build_consistency_context()` reads the Characters and World tabs (and, for prose and notes Write calls only, a bounded 3,000-char tail of the current Draft as continuity context — Continue already sends the full draft another way, and Revise tasks send the whole text they revise in the prompt, so it's skipped there) and prepends them to the system prompt as a "CONTINUITY CONTEXT" block, after the Book Profile block. Empty tabs produce an empty context string — zero prompt overhead for a fresh project. Verified: injected details (e.g. which hand a scar is on) are respected in generated scenes.

**Chapters tab**: not a separate stored model — chapters are parsed live from the Draft text on every tab-switch via `agents/author/book_exporter.py: split_into_chapters()` / `find_chapter_offsets()`, so there's never a second source of truth to drift from the actual draft. Double-clicking a chapter moves the Draft cursor to that heading and switches tabs.

Export (`AuthorPanel.export_book()`) hands the raw Draft text to `agents/author/book_exporter.py`, which splits it into chapters by detecting `Chapter N` / `Part N` / `Prologue` / `Epilogue` heading lines (falls back to one unlabeled chapter if none are found — export always works, headings just improve structure) and renders a title page + chapters via EbookLib (EPUB), python-docx (DOCX), or reportlab (PDF, built directly — no DOCX→PDF conversion step, so no LibreOffice dependency).

With a named Project selected, **Save Draft** and each successful export also
record a durable Project link to the chosen file. Deleting the Project removes
that link but never deletes the external file. Press can copy the
current working draft into Quote Finder via **Use Project Draft**; check and
approve the text yourself before treating it as publication-ready.

## Deliberate limitations
What Quill does not do, on purpose or not yet. Rows marked *open* are known gaps with a `TODO.md` item; the code audit of 2026-11-18 (`docs/audit/code-readiness-audit-2026-11-18.md`) is the source.

- **Revise works on up to 20,000 characters per run** (6,000 with a local model), because one reply is capped at 8,192 tokens. Above that nothing is sent; select a chapter instead.
- **Write never replaces the Draft.** Prose is added after it; only a revise task replaces text, and only the selection (or the whole Draft) it was given. There is no version history beyond **⌘Z** in the Draft and the autosave.
- **Publish and Market output is a draft to check.** KDP categories, keywords, price guidance and comp titles are model suggestions; nothing marks them "verify" yet (*open*, audit QM-18).
- **Export finds chapters from heading lines only** (`Chapter …`, `Part …`, `Prologue`, `Epilogue`). A prose line that starts with "Part" or "Chapter" also becomes a chapter. DOCX and PDF get a title page; EPUB carries the title and author as metadata only.
- **No grammar checker, plagiarism check or fact check.** Non-Fiction's `[UNSOURCED]` marks flag claims the listed sources do not cover; they do not verify the sources.

## Under the hood — files & functions
| Location | Role |
|---|---|
| `agents/author/agent.py` | `AuthorAgent` — `SYSTEM_PROMPT`/`SYSTEM_PROMPT_NONFICTION` craft prompts + markers; all three `build_*_messages()` accept `book_profile_context`; `build_messages()` also takes `content_type`. |
| `agents/author/book_exporter.py` | `split_into_chapters()`, `find_chapter_offsets()`, `export_epub()/export_docx()/export_pdf()`, `export_book()`. |
| `main.py: author_write()/author_continue()` | Write mode. |
| `main.py: _author_on_content_type_changed()` | Swaps the Task list to match Fiction/Non-Fiction. |
| `main.py: _author_get_book_profile()/_author_build_book_profile_block()` | Book Profile → system-prompt block. |
| `main.py: author_save_profile()/_author_load_profile()` | Profile persistence via `services/database.py` settings table. |
| `main.py: _author_build_consistency_context()/_author_start_worker()` | Continuity injection. |
| `main.py: _author_refresh_chapters()/_author_jump_to_chapter()` | Chapters navigator. |
| `agents/author/panel.py: AuthorPanel.export_book()` | Export handler — chapter detection + file dialog + format dispatch. |
| `main.py: author_pub_generate()/_copy()/_save()` | Publish mode. |
| `main.py: author_mkt_generate()/_copy()/_save()` | Market mode. |
| `main.py: _parse_author_sections()/_populate_author_tabs()` | Marker routing. |

## Extend it
- **Structured chapter model**: Chapters is currently a *view* derived from the Draft text, not a stored model — a real `Book`/`Chapter` data model (mirroring `agents/course/models.py`) would additionally enable per-chapter regeneration, status tracking, and reordering.
- **Editing pass**: nothing currently re-reads a full draft for continuity/pacing/repetition — an "Editor" mode is the natural next addition.
- **Autonomous drive loop**: seed a premise → auto-expand outline → auto-draft each chapter → auto-compile, using the Book Profile, consistency context, and chapter navigator now in place as the foundation.
- **BookProfile auto-fill**: Publish/Market's own per-mode Hook/Comp-Titles fields aren't yet pre-filled from the Book Profile — they're independent fields you can still override per document, but nothing copies the Book Profile's Hook/Comps into them automatically.

## Requirements
Provider key. Large-context model (`claude-sonnet`/`gpt-4o`) for long manuscripts. Export needs `python-docx` and `reportlab` (both in `requirements.txt`); EPUB export uses `EbookLib`, already a dependency.
