"""Unpriced requests are recorded as such (ADR 0006, decision 5; spec
manuscript-redesign, measure 5).

A cloud request with no price row costs "unknown", not "€0.00": it is stored
with cost_type "unpriced" and cost_eur still 0.0, so every total and guard
path is unchanged, and today's count of them feeds the spend chip.
"""

import pytest

from services import pricing_catalog
from services.database import get_connection
from services.usage_tracker import UsageTracker


@pytest.fixture
def no_price(monkeypatch):
    """Every price lookup misses, as for a model with no pricing row."""
    monkeypatch.setattr(pricing_catalog, "resolve_price_row",
                        lambda conn, provider, model: (None, "unknown"))


def _row(usage_id):
    with get_connection() as conn:
        return dict(conn.execute(
            "SELECT cost_eur, cost_type FROM usage WHERE id = ?",
            (usage_id,)).fetchone())


def test_a_cloud_request_without_a_price_row_is_stored_unpriced(no_price):
    tracker = UsageTracker()
    entry = tracker.log_request(
        "chat", "openai", "gpt-unknown-9", "hello", "world",
        usage={"input_tokens": 10, "output_tokens": 20})
    assert entry["cost_type"] == "unpriced"
    assert entry["cost_eur"] == 0.0
    assert _row(entry["usage_id"]) == {"cost_eur": 0.0,
                                       "cost_type": "unpriced"}


def test_a_local_request_is_free_not_unpriced(no_price):
    entry = UsageTracker().log_request(
        "chat", "ollama", "llama3", "hello", "world",
        usage={"input_tokens": 10, "output_tokens": 20})
    assert entry["cost_type"] == "exact"
    assert entry["cost_eur"] == 0.0


def test_a_priced_request_keeps_its_token_cost_type():
    tracker = UsageTracker()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT backend, model FROM pricing WHERE input_per_1m_usd > 0 "
            "AND output_per_1m_usd > 0 AND backend = 'openai' LIMIT 1"
        ).fetchone()
    if row is None:
        pytest.skip("no priced openai row in the test database")
    assert tracker.price_row_found(row["backend"], row["model"])
    entry = tracker.log_request(
        "chat", row["backend"], row["model"], "hello", "world",
        usage={"input_tokens": 1000, "output_tokens": 1000})
    assert entry["cost_type"] == "exact"
    assert entry["cost_eur"] > 0


def test_a_caller_can_say_the_price_was_unknown():
    entry = UsageTracker().log_request(
        "creator", "higgsfield", "seedance-2.5", "a clip", "",
        flat_cost_eur=0.0, price_known=False)
    assert entry["cost_type"] == "unpriced"
    assert entry["cost_eur"] == 0.0


def test_existing_callers_are_unchanged_by_default():
    entry = UsageTracker().log_request(
        "creator", "higgsfield", "seedance-2.5", "a clip", "",
        flat_cost_eur=0.4)
    assert entry["cost_type"] == "per_unit"
    assert entry["cost_eur"] == 0.4


def test_price_row_found_agrees_with_calculate_cost(no_price):
    tracker = UsageTracker()
    assert tracker.price_row_found("openai", "gpt-unknown-9") is False
    assert tracker.calculate_cost_eur("openai", "gpt-unknown-9", 10, 10) == 0.0
    assert tracker.price_row_found("ollama", "anything") is True


def test_the_count_and_the_totals(no_price):
    tracker = UsageTracker()
    before_count = tracker.get_unpriced_requests_today()
    before_total = tracker.get_today_total()
    before_requests = tracker.get_total_requests_today()
    for _ in range(3):
        tracker.log_request("chat", "deepseek", "ds-unknown", "a", "b",
                            usage={"input_tokens": 5, "output_tokens": 5})
    tracker.log_request("chat", "ollama", "llama3", "a", "b")
    assert tracker.get_unpriced_requests_today() == before_count + 3
    # Totals are byte-for-byte what they were: the unpriced rows add 0.0.
    assert tracker.get_today_total() == before_total
    assert tracker.get_total_requests_today() == before_requests + 4
