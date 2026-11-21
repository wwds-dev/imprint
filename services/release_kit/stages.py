"""One Qt-free function per release-kit item (spec A4, A6).

These run on a worker thread (or inline in tests). They never touch the
database or the request guard: the driver does both on the GUI thread before
and after. Every provider or voice call sits behind `grant.check()`
(contract: tests/test_release_kit_contract.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agents.manuscript.agent import CALENDAR_CAPTION_PROMPT
from services.chat_projects import with_project_instructions
from services.release_kit.grant import JobGrant
from services.release_kit.plan import CAPTION_OUTPUT_TOKENS, CAPTION_SLOT_CHARS

QUOTES_BOUND_MARGIN = 500            # characters over the largest request
CAPTION_PROMPT_CHARS = len(CALENDAR_CAPTION_PROMPT)


class BoundExceeded(ValueError):
    """A request is larger than its approved bound; nothing was sent."""


@dataclass
class TextReply:
    text: str
    usage: dict | None


def quotes_input_bound() -> int:
    """The largest quote request the plan allows, derived from the prompt so
    growing it cannot silently exceed the bound (review P3-4): the request
    with no passages, plus every window at full size and its label."""
    from agents.manuscript import quote_finder as qf
    base = sum(len(m["content"]) for m in qf.build_quote_messages([], qf.MAX_QUOTES))
    return (base + qf.WINDOW_COUNT * (qf.WINDOW_CHARS + 80) + QUOTES_BOUND_MARGIN)


def check_quote_bound(messages: list[dict]) -> None:
    size = sum(len(str(m.get("content") or "")) for m in messages)
    bound = quotes_input_bound()
    if size > bound:
        raise BoundExceeded(
            f"the quote request is {size:,} characters, above its "
            f"{bound:,}-character bound")


def check_caption_bound(messages: list[dict], slots: int) -> None:
    bound = slots * CAPTION_SLOT_CHARS + CAPTION_PROMPT_CHARS + 500
    size = sum(len(str(m.get("content") or "")) for m in messages)
    if size > bound:
        raise BoundExceeded(
            f"the caption request is {size:,} characters, above its "
            f"{bound:,}-character bound")


def ask_text(grant: JobGrant, run_backend, messages: list[dict],
             prompt: str, project_instructions: str = "",
             max_tokens: int = CAPTION_OUTPUT_TOKENS) -> TextReply:
    """Send one text request on the granted local route and collect the reply.

    Mirrors ChatWorker's three result shapes (stream, (text, usage), text)
    without its signals; the job's frozen project instructions go in once.
    The reply is capped at `max_tokens`, the figure the confirmation shows.
    """
    grant.check()
    sent = with_project_instructions(messages, project_instructions)
    result = run_backend(grant.provider, grant.model, sent, prompt,
                         max_tokens=max_tokens)
    if isinstance(result, tuple):
        text, usage = result
        return TextReply(str(text or ""), usage)
    if isinstance(result, str):
        return TextReply(result, None)
    if hasattr(result, "__iter__") and not isinstance(result, dict):
        parts = [str(token) for token in result]
        usage = getattr(result, "usage", None)
        stop = getattr(result, "stop_reason", None)
        if stop:
            usage = {**(usage or {}), "stop_reason": stop}
        return TextReply("".join(parts), usage)
    return TextReply(str(result or ""), None)


def make_epub(project_id: str, version: int, path: Path) -> dict:
    """Stage 1: export the approved version with its SHA-256 receipt."""
    from services.project_publication import export_approved
    return export_approved(project_id, version, "epub", path)


def render_graphic(quote: str, path: Path, attribution: str) -> Path:
    """Stage 5: one square PNG per unique quote (Pillow, no provider)."""
    from agents.manuscript.quote_graphics import render_quote_graphic
    return render_quote_graphic(quote, path, attribution=attribution)


def render_short_item(grant: JobGrant, quote: str, image: Path, path: Path,
                      voice: str) -> Path:
    """Stage 6: one Short per Short slot, voice named by the job (legal L1)."""
    grant.check()
    from agents.manuscript.shorts_generator import render_short
    from providers.voice.mock import MockVoiceProvider
    if grant.provider != "system":
        raise ValueError(f"Shorts voice route {grant.provider!r} is not in "
                         "this version")
    return render_short(quote, image, path, voice_id=voice or "default",
                        voice_provider=MockVoiceProvider())


def caption_messages(items_json: str) -> list[dict]:
    from agents.manuscript.agent import ManuscriptAgent
    return ManuscriptAgent().build_calendar_caption_messages(items_json)


def slots_to_json(slots) -> list[dict]:
    return [{"day": s.day.isoformat(), "platform": s.platform,
             "format": s.format, "quote": s.quote, "caption": s.caption}
            for s in slots]


def slots_from_json(data: list[dict]):
    from datetime import date
    from agents.manuscript.content_calendar import CalendarSlot
    return [CalendarSlot(day=date.fromisoformat(d["day"]), platform=d["platform"],
                         format=d["format"], quote=d["quote"],
                         caption=d.get("caption", "")) for d in data]


def dumps(data) -> str:
    return json.dumps(data, ensure_ascii=False)
