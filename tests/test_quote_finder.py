"""Release kit quote sampling (spec one-click-release, A5 E1). Pure, no Qt."""

from __future__ import annotations

import json

from agents.manuscript import quote_finder as qf
from agents.manuscript.agent import QUOTE_SUGGESTION_PROMPT


def _book(paragraphs: int = 400) -> str:
    out = []
    for p in range(paragraphs):
        out.append(" ".join(
            f"Sentence {p}-{s} walks the long salt road home." for s in range(5)))
    return "\n\n".join(out)


def test_a_short_book_is_one_window_the_whole_text():
    text = "One line. Two lines.\n\nThree." * 10
    (window,) = qf.sample_windows(text)
    assert (window.index, window.count, window.text) == (1, 1, text)
    assert window.label == "[Passage 1 of 1, about 0% into the book]"


def test_exactly_the_limit_is_still_one_window():
    text = "a" * qf.WHOLE_TEXT_LIMIT
    assert len(qf.sample_windows(text)) == 1
    assert len(qf.sample_windows(text + ".")) == 12


def test_empty_text_has_no_windows():
    assert qf.sample_windows("   \n ") == []


def test_long_book_gets_twelve_ordered_bounded_windows_across_the_book():
    text = _book()
    assert len(text) > qf.WHOLE_TEXT_LIMIT
    windows = qf.sample_windows(text)
    assert len(windows) == 12
    assert [w.index for w in windows] == list(range(1, 13))
    for a, b in zip(windows, windows[1:]):
        assert a.start < b.start
        assert a.end <= b.start
    for w in windows:
        assert qf.MIN_WINDOW_CHARS <= len(w.text) <= qf.WINDOW_CHARS
        assert w.text == text[w.start:w.end]
        # Snapped to a paragraph start, ends at a sentence end.
        assert w.start == 0 or text[w.start - 1] == "\n"
        assert w.text.rstrip().endswith(".")
    # Spread across the whole book, not the first 30,000 characters.
    assert windows[0].start == 0
    assert windows[-1].end > len(text) - qf.WINDOW_CHARS - qf.PARAGRAPH_SNAP
    assert windows[-1].percent >= 90
    total = sum(len(w.text) for w in windows)
    assert total <= 12 * qf.WINDOW_CHARS


def test_windows_are_deterministic():
    text = _book()
    assert qf.sample_windows(text) == qf.sample_windows(text)


def test_without_paragraphs_a_window_snaps_to_a_sentence():
    text = " ".join(f"Line {i} is here." for i in range(4000))
    windows = qf.sample_windows(text)
    for w in windows[1:]:
        assert text[w.start - 2:w.start] == ". "


def test_messages_use_the_quote_finder_prompt_and_label_each_passage():
    windows = qf.sample_windows(_book())
    messages = qf.build_quote_messages(windows, 20)
    assert messages[0] == {"role": "system", "content": QUOTE_SUGGESTION_PROMPT}
    user = messages[1]["content"]
    assert user.startswith("Extract the 20 most quotable lines")
    assert user.count("[Passage ") == 12
    assert "[Passage 12 of 12, about" in user
    # Input bound from A1: at most 32,000 characters in all.
    assert sum(len(m["content"]) for m in messages) <= 32_000


def test_parser_keeps_verbatim_quotes_and_drops_the_rest():
    windows = qf.sample_windows(
        "The sea keeps what it takes.\n\nShe said “come home” twice.\n\n"
        "Nothing else.")
    long_line = "word " * 70
    reply = json.dumps([
        "The sea keeps what it takes.",
        "She said \"come home\" twice.",   # straight vs curly quotes: kept
        "The sea keeps what it takes. ",   # duplicate (whitespace aside)
        "the sea keeps what it takes.",    # not verbatim: case differs
        "The sea gives back nothing.",     # invented: dropped
        long_line.strip(),                 # > 280: dropped, never cut
    ])
    parsed = qf.parse_verified_quotes(reply, windows)
    assert parsed.quotes == ["The sea keeps what it takes.",
                             'She said "come home" twice.']
    assert (parsed.duplicates, parsed.not_found, parsed.too_long) == (1, 2, 1)


def test_parser_limit_and_exact_length_boundary():
    quote = "x" * 279 + "."
    assert len(quote) == qf.MAX_QUOTE_CHARS
    windows = qf.sample_windows(quote + " " + "y" * 10 + ".")
    parsed = qf.parse_verified_quotes(json.dumps([quote, quote + "z"]), windows)
    assert parsed.quotes == [quote]
    assert parsed.too_long == 1

    lines = [f"Line {i}." for i in range(30)]
    windows = qf.sample_windows(" ".join(lines))
    parsed = qf.parse_verified_quotes(json.dumps(lines), windows)
    assert len(parsed.quotes) == qf.MAX_QUOTES
    assert parsed.over_limit == 10


def test_parser_survives_an_unparseable_reply():
    windows = qf.sample_windows("Alpha beta.")
    assert qf.parse_verified_quotes("", windows).quotes == []
    assert qf.parse_verified_quotes(None, windows).quotes == []
