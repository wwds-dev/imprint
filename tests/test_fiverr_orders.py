"""Client Gigs orders are one durable record per client.

Contract: the brief and brand kit live on an open order that a returning
client reuses (a new round is a revision event, not a new order); produced
artifacts attach to it; the order log reads the rows, so it survives
restarts; empty fields auto-fill from the client's stored preferences; and
the brand kit reaches both prompt builders only when it has content.
"""

import json
import os

import pytest

from agents.fiverr import orders
from agents.fiverr.agent import FiverrAgent
from services.database import get_connection


@pytest.fixture(autouse=True)
def clean_table():
    yield
    with get_connection() as conn:
        conn.execute("DELETE FROM fiverr_orders")


BRIEF = dict(business_name="Acme Soap", industry="cosmetics",
             style="Minimal", colors="sage, cream", notes="no mascots",
             brand_fonts="Lato", brand_voice="warm", brand_rules="no drop shadows")


def test_returning_client_reuses_the_open_order():
    first = orders.open_order(BRIEF)
    orders.record_event(first["id"], "logos requested", "4 concept(s)")
    again = orders.open_order({**BRIEF, "notes": "rounder shapes"})
    assert again["id"] == first["id"]          # a revision, not a new order
    assert again["notes"] == "rounder shapes"  # newest instructions win
    orders.record_event(first["id"], "logos requested", "revision round")
    history = json.loads(orders.get_order(first["id"])["history_json"])
    assert [event["kind"] for event in history] == [
        "logos requested", "logos requested"]


def test_artifacts_attach_to_the_one_record():
    order = orders.open_order(BRIEF)
    orders.attach(order["id"], image_paths_json=json.dumps(["a.png"]),
                  delivery_text="Dear client…", gig_text="I will design…")
    stored = orders.get_order(order["id"])
    assert json.loads(stored["image_paths_json"]) == ["a.png"]
    assert stored["delivery_text"].startswith("Dear")
    assert stored["gig_text"].startswith("I will")
    with pytest.raises(ValueError):
        orders.attach(order["id"], client="smuggled")


def test_latest_for_client_is_the_reusable_preference_source():
    orders.open_order(BRIEF)
    assert orders.latest_for_client("acme soap")["brand_fonts"] == "Lato"
    assert orders.latest_for_client("Unknown Co") is None
    assert orders.latest_for_client("") is None


def test_brand_kit_reaches_prompts_only_when_present():
    agent = FiverrAgent()
    with_kit = agent.build_messages("delivery", BRIEF)[1]["content"]
    assert "Brand fonts: Lato" in with_kit
    assert "Brand rules: no drop shadows" in with_kit
    bare = {k: v for k, v in BRIEF.items()
            if not k.startswith("brand_")}
    without = agent.build_messages("delivery", bare)[1]["content"]
    assert "Brand fonts" not in without
    image_prompt = agent.build_image_prompt_request(BRIEF)[1]["content"]
    assert "Brand rules: no drop shadows" in image_prompt


# ── panel wiring ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question,
             QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved


def _fill_brief(panel):
    panel.fiverr_name_input.setText(BRIEF["business_name"])
    panel.fiverr_industry_input.setText(BRIEF["industry"])
    panel.fiverr_colors_input.setText(BRIEF["colors"])
    panel.fiverr_notes_input.setPlainText(BRIEF["notes"])
    panel.fiverr_brand_fonts_input.setText(BRIEF["brand_fonts"])
    panel.fiverr_brand_voice_input.setText(BRIEF["brand_voice"])
    panel.fiverr_brand_rules_input.setText(BRIEF["brand_rules"])


def test_order_log_reads_durable_rows_and_reloads_a_record(window):
    panel = window.fiverr_panel
    order = orders.open_order(BRIEF)
    orders.attach(order["id"], delivery_text="Dear client, here it is.")
    panel.refresh_orders()
    table = panel.fiverr_order_table
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "Acme Soap"
    table.setCurrentCell(0, 0)
    assert panel._order_id == order["id"]
    assert panel.fiverr_brand_fonts_input.text() == "Lato"
    assert "Dear client" in panel.fiverr_delivery_box.toPlainText()


def test_known_client_autofills_empty_fields_only(window):
    panel = window.fiverr_panel
    orders.open_order(BRIEF)
    panel.clear()
    panel.fiverr_industry_input.clear()
    panel.fiverr_brand_fonts_input.clear()
    panel.fiverr_brand_voice_input.setText("already typed")
    panel.fiverr_name_input.setText("Acme Soap")
    panel._autofill_client_preferences()
    assert panel.fiverr_industry_input.text() == "cosmetics"
    assert panel.fiverr_brand_fonts_input.text() == "Lato"
    assert panel.fiverr_brand_voice_input.text() == "already typed"


def test_delivery_attaches_even_without_a_logo_run(window, monkeypatch):
    panel = window.fiverr_panel
    panel._order_id = None
    _fill_brief(panel)
    monkeypatch.setattr(window, "record_request", lambda *a, **k: None)
    panel._prompt_token = "tok"
    panel.fiverr_delivery_box.setPlainText("Here is your delivery.")
    panel._on_delivery_done("Here is your delivery.")
    (stored,) = orders.list_orders()
    assert stored["delivery_text"] == "Here is your delivery."
    kinds = [event["kind"] for event in json.loads(stored["history_json"])]
    assert kinds == ["delivery written"]
