"""Whole-book quote sampling for the release kit (spec one-click-release, A5 E1).

Qt-free. Press's own Quote Finder still sends `text[:30000]`; moving it to
windows is a separate, user-visible change, so only the release kit uses this.

Windowing (owner decision 3, Architect A5):
- a body of at most 30,000 characters is one window, the whole text;
- otherwise K = 12 windows of up to W = 2,500 characters. The ideal start of
  window i is floor(i·(L−W)/(K−1)). It snaps forward to the next paragraph
  start within 400 characters, else to the next sentence start within 200.
  The window ends at the last sentence end before start + W, keeping at least
  1,500 characters, and never runs into the next window's start.

Deterministic: no randomness, so tests and resumes see the same passages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agents.manuscript.agent import QUOTE_SUGGESTION_PROMPT
from agents.manuscript.llm_parsing import parse_string_list

WHOLE_TEXT_LIMIT = 30_000
WINDOW_COUNT = 12
WINDOW_CHARS = 2_500
MIN_WINDOW_CHARS = 1_500
PARAGRAPH_SNAP = 400
SENTENCE_SNAP = 200
MAX_QUOTE_CHARS = 280
MAX_QUOTES = 20

# A sentence ends at . ! ? or … plus any closing quote or bracket, followed by
# whitespace (or the end of the text).
_SENTENCE_END = re.compile(r"[.!?…][\"'”’)\]]*(?=\s|$)")


@dataclass(frozen=True)
class Window:
    index: int          # 1-based
    count: int
    start: int
    end: int
    text: str
    percent: int        # how far into the book the window starts

    @property
    def label(self) -> str:
        return (f"[Passage {self.index} of {self.count}, "
                f"about {self.percent}% into the book]")


@dataclass
class ParsedQuotes:
    quotes: list[str] = field(default_factory=list)
    too_long: int = 0       # longer than MAX_QUOTE_CHARS: dropped, never cut
    not_found: int = 0      # not verbatim in any passage
    duplicates: int = 0
    over_limit: int = 0     # valid but past MAX_QUOTES


def _skip_space(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _snap_start(text: str, s: int) -> int:
    if s <= 0:
        return 0
    if text[s - 1] == "\n":
        return _skip_space(text, s)
    newline = text.find("\n", s, s + PARAGRAPH_SNAP)
    if newline != -1:
        snapped = _skip_space(text, newline + 1)
        if snapped < len(text):
            return snapped
    match = _SENTENCE_END.search(text, s, s + SENTENCE_SNAP)
    if match:
        snapped = _skip_space(text, match.end())
        if snapped < len(text):
            return snapped
    return s


def _end_for(text: str, start: int, limit: int) -> int:
    floor = start + MIN_WINDOW_CHARS
    last = None
    for match in _SENTENCE_END.finditer(text, floor, limit):
        last = match.end()
    return last if last is not None else limit


def sample_windows(text: str, k: int = WINDOW_COUNT,
                   w: int = WINDOW_CHARS) -> list[Window]:
    """The passages a kit sends for quote suggestions (see module docstring)."""
    length = len(text)
    if not text.strip():
        return []
    if length <= WHOLE_TEXT_LIMIT:
        return [Window(1, 1, 0, length, text, 0)]
    starts = []
    for i in range(k):
        ideal = (i * (length - w)) // (k - 1)
        starts.append(_snap_start(text, ideal))
    # Snapping only moves forward; keep starts strictly increasing.
    for i in range(1, k):
        if starts[i] <= starts[i - 1]:
            starts[i] = starts[i - 1] + 1
    windows = []
    for i, start in enumerate(starts):
        limit = min(start + w, length)
        if i + 1 < k:
            limit = min(limit, starts[i + 1])
        end = _end_for(text, start, limit)
        windows.append(Window(
            index=i + 1, count=k, start=start, end=end,
            text=text[start:end], percent=(100 * start) // length))
    return windows


def build_quote_messages(windows: list[Window], count: int = MAX_QUOTES) -> list[dict]:
    """One request over every passage, with the Quote Finder's own prompt."""
    passages = "\n\n".join(f"{w.label}\n{w.text}" for w in windows)
    return [
        {"role": "system", "content": QUOTE_SUGGESTION_PROMPT},
        {"role": "user", "content": (
            f"Extract the {count} most quotable lines from these passages "
            f"of one book:\n\n{passages}")},
    ]


_QUOTE_MARKS = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'",
                              "’": "'", "‚": "'"})


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(_QUOTE_MARKS)).strip()


def parse_verified_quotes(reply: str, windows: list[Window], *,
                          max_chars: int = MAX_QUOTE_CHARS,
                          limit: int = MAX_QUOTES) -> ParsedQuotes:
    """Keep only verbatim quotes of at most `max_chars`, in reply order.

    Longer quotes are dropped, never truncated, so every kept quote is the
    author's exact words. A quote is verbatim when it appears in one of the
    passages sent, after whitespace and curly quotes are normalised.
    """
    result = ParsedQuotes()
    sources = [_normalise(w.text) for w in windows]
    seen: set[str] = set()
    for raw in parse_string_list(reply or ""):
        quote = raw.strip()
        if not quote:
            continue
        if len(quote) > max_chars:
            result.too_long += 1
            continue
        normalised = _normalise(quote)
        if not any(normalised in source for source in sources):
            result.not_found += 1
            continue
        key = normalised.casefold()
        if key in seen:
            result.duplicates += 1
            continue
        seen.add(key)
        if len(result.quotes) >= limit:
            result.over_limit += 1
            continue
        result.quotes.append(quote)
    return result
