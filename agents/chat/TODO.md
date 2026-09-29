# Studio Assistant — TODO

> **Legend** — priority `P0` critical · `P1` high · `P2` normal · `P3` low
> categories `security` `bug` `feature` `performance` `design` `docs` `testing` `infra` `research`
> owner `@me` (needs you — accounts, keys, money, judgement) · `@ai` (Claude can do this)
> agent `agent:<key>` (optional; only meaningful in a parent project's shared TODO.md — not needed here, this file already belongs to Studio Assistant alone)

---

## v1 — current

- [x] `P2` `@ai` Stream responses instead of wait-then-dump. Done 2026-09-30 — and the survey found six of seven providers already streamed end-to-end (run_backend prefers stream_chat, ChatWorker drains iterators with UsageStream billing, the UI appends per token); the one wait-then-dump holdout was **ollama**, the slowest responder in the app, whose dispatch branch called the blocking chat() first while a fully implemented stream_chat sat unused. The branch now prefers the stream, and ollama's stream gained the UsageStream wrap the cloud clients have — the daemon's done-frame prompt_eval_count/eval_count become exact token stats instead of the chars/4 estimate. Four contract tests (tests/test_chat_streaming.py) pin: every backend streams, ollama usage is real, ChatWorker delivers incrementally, and a cancelled stream is neither billed nor saved. Suite 848. *(moved from imprint/TODO.md)*
- [x] `P1` Studio Assistant is a visible workspace using the shared normal panel.
- [x] `P2` Its creative-studio scope, checks and recovery path are in the Learning Centre and Docs.
- [x] `P2` The registry no longer removes the chat agent, and the hidden selector now exists only to carry the active agent key for the shared panel.
