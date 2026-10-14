# Code review: deps-security-upgrade-2026-10 (code-reviewer, 2026-10-14)

Scope: `git diff origin/main -- requirements.txt`. Result: no P0-P2.

- P3: httpx2 2.12.0 / httpcore2 2.12.0 pins are needed and sensible. anthropic requires `httpx2>=2.0.0`; httpx2 requires `httpcore2==2.12.0` and `idna>=3.18`. openai/google-genai stay on `httpx` 0.28.1; both families coexist. anyio 4.14.2 satisfies `anyio>=4.10`.
- P3: `truststore` (new transitive of httpx2) is unpinned. Optional.
- P3: code touching upgraded libs: pypdf `services/narrator/converter.py:413-417` (covered by `tests/test_book_pipeline.py:171-174`, `test_narrator_converter.py`); bs4 uses `html.parser`, not lxml/soupsieve selectors (`converter.py:433`); Pillow in `agents/manuscript/quote_graphics.py:10`, `vidforge/vidforge/*`, `scripts/make_icon.py`. No direct urllib3/anyio/lxml/httpx2 use. `anthropic` SDK now runs on httpx2 (`services/anthropic_client.py:6`, `vidforge/vidforge/llm.py:76`); no httpx-based Anthropic mock found.

Not verified: runtime behaviour changes in pypdf 6.19, Pillow 12.3, lxml 6.1 (suite decides); drift of unpinned PySide6/anthropic.
