"""The spend and status chips' text (Design S6; spec measure 5).

Pure functions, so every row of S6's tables is one case. The rule that matters
most: when any request today had no price, the chip never says "€0.00".
"""

import pytest

from ui.shell.chips import (COMPACT, FULL, SHORT, format_limit,
                            spend_chip_text, status_state)


@pytest.mark.parametrize("spent,limit,unpriced,text,tone", [
    (1.20, 5, 0, "€1.20 of €5 today", "normal"),
    (0.0, 5, 0, "€0.00 of €5 today", "normal"),             # truly nothing
    (1.20, 0, 0, "€1.20 today · no limit", "normal"),
    (4.10, 5, 0, "€4.10 of €5 today", "warning"),           # 80 % to < 100 %
    (4.00, 5, 0, "€4.00 of €5 today", "warning"),           # exactly 80 %
    (5.10, 5, 0, "€5.10 of €5 today", "danger"),
    (5.00, 5, 0, "€5.00 of €5 today", "danger"),            # at the limit
    (1.20, 5, 2, "€1.20 + unknown of €5 today", "unknown"),
    (0.0, 5, 3, "Unknown of €5 today", "unknown"),
    (1.5, 1.5, 0, "€1.50 of €1.5 today", "danger"),
    (1234.56, 5000, 0, "€1234.56 of €5000 today", "normal"),
])
def test_every_s6_row(spent, limit, unpriced, text, tone):
    state = spend_chip_text(spent, limit, unpriced)
    assert (state.text, state.tone) == (text, tone)


@pytest.mark.parametrize("form", [FULL, SHORT, COMPACT])
@pytest.mark.parametrize("spent", [0.0, 0.004, 1.2])
@pytest.mark.parametrize("limit", [0, 5])
def test_an_unpriced_day_never_reads_as_zero(form, spent, limit):
    state = spend_chip_text(spent, limit, 1)
    assert "€0.00" not in state.text
    assert "unknown" in state.text.lower()
    assert "unknown" in state.accessible
    assert "had no price" in state.tooltip


def test_the_unknown_tooltip_counts_the_requests():
    one = spend_chip_text(1.2, 5, 1).tooltip
    many = spend_chip_text(1.2, 5, 4).tooltip
    assert "1 request today had no price" in one
    assert "4 requests today had no price, so the real total is more than €1.20." in many


def test_over_the_limit_says_so():
    assert "Daily limit reached." in spend_chip_text(5.1, 5, 0).tooltip


@pytest.mark.parametrize("form,text", [
    (FULL, "€12.34 of €50 today"),
    (SHORT, "€12.34 of €50"),                    # S3 step 2
    (COMPACT, "€12.34"),                         # S3 step 5
])
def test_the_collapse_forms(form, text):
    state = spend_chip_text(12.34, 50, 0, form=form)
    assert state.text == text
    if form == COMPACT:
        assert "€50" in state.tooltip            # the limit moves to the tooltip


def test_the_compact_unknown_form_keeps_its_word():
    assert spend_chip_text(12.34, 50, 2, form=COMPACT).text == "€12.34 + unknown"
    assert spend_chip_text(0, 50, 2, form=COMPACT).text == "Unknown"


def test_the_accessible_name_is_a_sentence():
    assert spend_chip_text(1.2, 5, 1).accessible == (
        "Spent today: 1.20 euros, plus an unknown amount of a 5 euro limit")
    assert spend_chip_text(1.2, 0, 0).accessible == (
        "Spent today: 1.20 euros, no daily limit")


def test_limits_read_like_the_fields():
    assert format_limit(5) == "€5"
    assert format_limit(1.5) == "€1.5"
    assert format_limit(0.25) == "€0.25"


# ── status ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("system,keys,busy,word,dot", [
    ("red", "warning", True, "Machine stressed", "DANGER"),
    ("yellow", "warning", True, "Key check failed", "WARNING_DOT"),
    ("yellow", None, True, "Machine busy", "WARNING_DOT"),
    ("green", None, True, "Working", "INFO"),
    ("green", None, False, "Ready", "ACCENT"),
    (None, "neutral", False, "Ready", "ACCENT"),     # "Not configured" is normal
])
def test_the_worst_state_wins(system, keys, busy, word, dot):
    state = status_state(system, keys, busy, 0)
    assert (state.word, state.dot) == (word, dot)


@pytest.mark.parametrize("count,accessible", [
    (0, "Status: Ready."),
    (1, "Status: Ready. 1 model update waiting."),
    (12, "Status: Ready. 12 model updates waiting."),
])
def test_the_badge_counts_waiting_updates(count, accessible):
    state = status_state("green", None, False, count)
    assert state.count == count
    assert state.accessible == accessible
