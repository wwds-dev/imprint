"""Narrow-rail status components stay structured and readable."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_routing_card_separates_decision_evidence_and_readiness(app):
    from ui.status_cards import RoutingStatusCard

    card = RoutingStatusCard()
    labels = [label.text() for label in card.findChildren(type(card.route_value))]
    assert card.accessibleName().startswith("Chat routing")
    assert "Last Chat request" in labels
    assert "Best fit for Chat prompt" in labels
    card.set_route("author", "anthropic", "claude-sonnet")
    card.set_recommendation(
        "ollama", "deepseek-r1:8b",
        "Best match for Draft (writing): local privacy and cost efficiency. "
        "Fit score 74/100. It is available in the current setup.",
        74, "medium", False,
    )
    assert "Author" in card.route_value.text()
    assert card.recommendation_value.text() == "ollama · deepseek-r1:8b"
    assert card.score_badge.text() == "74/100 · Medium"
    assert card.reason_label.text() == "Local privacy and cost efficiency."
    assert card.availability_label.text() == "Ready in current setup"


def test_api_key_card_uses_individual_semantic_rows(app):
    from ui.status_cards import ApiKeysStatusCard

    card = ApiKeysStatusCard(("OpenAI", "Gemini"))
    card.set_status("OpenAI", "available")
    card.set_status("Gemini", "not set")
    assert card.status_labels["openai"].text() == "Configured"
    assert card.status_labels["openai"].property("status") == "ready"
    assert card.status_labels["gemini"].text() == "Not configured"


def test_shared_recommendation_refresh_updates_chat_card(app):
    from types import SimpleNamespace
    from main import AGENT_SETUP_WIDGETS, GodAI

    refreshed = []
    host = SimpleNamespace(
        recommendation_engine=object(),
        recommendation_label=object(),
        update_recommendation_label=lambda: refreshed.append("chat card"),
        refresh_recommendation_marks=lambda agent: refreshed.append(agent),
        refresh_video_recommendations=lambda: None,
        _refresh_fiverr_image_recommendation=lambda: None,
    )
    GodAI.refresh_all_recommendations(host)

    assert refreshed.count("chat card") == 1
    assert "chat" not in refreshed
    assert set(refreshed) == (set(AGENT_SETUP_WIDGETS) - {"chat"}) | {"chat card"}


def test_collapsible_header_uses_readable_sentence_case(app):
    from ui.widgets import CollapsibleSection

    section = CollapsibleSection("API keys", expanded=True)
    assert "API keys" in section.header_btn.text()
    assert "API KEYS" not in section.header_btn.text()
    assert section.header_btn.accessibleDescription()
