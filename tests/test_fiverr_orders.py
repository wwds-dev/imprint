"""Client Gigs orders are one durable record per client.

Contract: the brief and brand kit live on an open order that a returning
client reuses (a new round is a revision event, not a new order); produced
artifacts attach to it; the order log reads the rows, so it survives
restarts; empty fields auto-fill from the client's stored preferences; and
the brand kit reaches both prompt builders only when it has content.

Two more since 2026-10-09 (agents/fiverr/TODO.md, the two P2 cards): an order
can be CLOSED with an outcome — delivered, accepted or cancelled — and a
closed order is never reused, so a returning client's next job is a new
record rather than a "revision" of a finished one; and the text the user
edits in the Delivery Message / Gig Description tabs is what the order
holds, not the raw draft that happened to stream in.
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


def test_closing_an_order_ends_its_reuse():
    """A returning client's next job after a close is a NEW order."""
    first = orders.open_order(BRIEF)
    closed = orders.close_order(first["id"], "delivered")
    assert closed["status"] == "delivered"
    kinds = [e["kind"] for e in json.loads(closed["history_json"])]
    assert kinds == ["order delivered"]
    again = orders.open_order(BRIEF)
    assert again["id"] != first["id"], "a closed order was folded into"
    assert again["status"] == "open"
    # the closed record is untouched by the new round
    assert orders.get_order(first["id"])["status"] == "delivered"


@pytest.mark.parametrize("outcome", orders.CLOSED_STATUSES)
def test_every_outcome_closes(outcome):
    order = orders.open_order(BRIEF)
    assert orders.close_order(order["id"], outcome)["status"] == outcome


def test_close_refuses_an_unknown_outcome_and_a_missing_order():
    order = orders.open_order(BRIEF)
    with pytest.raises(ValueError):
        orders.close_order(order["id"], "lost")
    assert orders.get_order(order["id"])["status"] == "open"
    assert orders.close_order(99999, "delivered") is None


def test_reopen_restores_reuse():
    order = orders.open_order(BRIEF)
    orders.close_order(order["id"], "cancelled")
    reopened = orders.reopen_order(order["id"])
    assert reopened["status"] == "open"
    assert orders.open_order(BRIEF)["id"] == order["id"]
    kinds = [e["kind"] for e in json.loads(
        orders.get_order(order["id"])["history_json"])]
    assert kinds == ["order cancelled", "order reopened"]


def test_status_changes_only_through_close_and_reopen():
    """attach() used to accept status, which is how a close could happen
    with no event in the history. One path now."""
    order = orders.open_order(BRIEF)
    with pytest.raises(ValueError):
        orders.attach(order["id"], status="delivered")


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



def _load_first_order(panel):
    panel.refresh_orders()
    panel.fiverr_order_table.setCurrentCell(0, 0)


def test_close_order_button_closes_the_loaded_order(window):
    panel = window.fiverr_panel
    panel.clear()
    order = orders.open_order(BRIEF)
    _load_first_order(panel)
    assert panel._order_id == order["id"]
    assert panel.fiverr_close_btn.isEnabled()
    assert not panel.fiverr_reopen_btn.isEnabled()
    panel.fiverr_outcome_box.setCurrentText("Accepted")
    panel.fiverr_close_btn.click()
    assert orders.get_order(order["id"])["status"] == "accepted"
    assert panel.fiverr_order_table.item(0, 2).text() == "accepted"
    assert "accepted" in panel.fiverr_status_label.text().lower()
    # the loaded order stays loaded for viewing, but can only be reopened
    assert panel._order_id == order["id"]
    assert not panel.fiverr_close_btn.isEnabled()
    assert panel.fiverr_reopen_btn.isEnabled()
    panel.fiverr_reopen_btn.click()
    assert orders.get_order(order["id"])["status"] == "open"
    assert panel.fiverr_close_btn.isEnabled()


def test_a_draft_after_a_close_opens_a_new_order(window, monkeypatch):
    """The held id must not route a new job onto a finished record."""
    panel = window.fiverr_panel
    panel.clear()
    _fill_brief(panel)
    first = orders.open_order(BRIEF)
    _load_first_order(panel)
    orders.close_order(first["id"], "delivered")
    panel.refresh_orders()
    monkeypatch.setattr(window, "record_request", lambda *a, **k: None)
    panel._prompt_token = "tok"
    panel.fiverr_delivery_box.setPlainText("Second job, new delivery.")
    panel._on_delivery_done("Second job, new delivery.")
    assert panel._order_id != first["id"]
    assert orders.get_order(panel._order_id)["status"] == "open"
    assert orders.get_order(first["id"])["delivery_text"] == ""
    assert orders.get_order(panel._order_id)["delivery_text"] == (
        "Second job, new delivery.")


def test_close_buttons_are_disabled_with_no_order_loaded(window):
    panel = window.fiverr_panel
    panel.clear()
    assert panel._order_id is None
    assert not panel.fiverr_close_btn.isEnabled()
    assert not panel.fiverr_reopen_btn.isEnabled()


def test_edits_to_the_delivery_text_reach_the_order(window):
    """What the user corrects is what the record holds."""
    panel = window.fiverr_panel
    panel.clear()
    order = orders.open_order(BRIEF)
    orders.attach(order["id"], delivery_text="Dear client, here it is.",
                  gig_text="I will design a logo.")
    _load_first_order(panel)
    panel.fiverr_delivery_box.setPlainText("Dear Sam, here is the final set.")
    panel.fiverr_gig_box.setPlainText("I will design a logo you can trust.")
    panel._flush_order_edits()
    stored = orders.get_order(order["id"])
    assert stored["delivery_text"] == "Dear Sam, here is the final set."
    assert stored["gig_text"] == "I will design a logo you can trust."
    kinds = [e["kind"] for e in json.loads(stored["history_json"])]
    assert kinds == ["delivery edited", "gig listing edited"]
    # reloading the order shows the edit, not the draft
    panel.clear()
    _load_first_order(panel)
    assert panel.fiverr_delivery_box.toPlainText() == "Dear Sam, here is the final set."


def test_loading_an_order_is_not_an_edit(window):
    panel = window.fiverr_panel
    panel.clear()
    order = orders.open_order(BRIEF)
    orders.attach(order["id"], delivery_text="Dear client.")
    _load_first_order(panel)
    panel._flush_order_edits()
    assert json.loads(orders.get_order(order["id"])["history_json"]) == []


def test_edits_flush_before_the_workspace_switches_order(window):
    from PySide6.QtCore import Qt
    panel = window.fiverr_panel
    panel.clear()
    first = orders.open_order(BRIEF)
    orders.attach(first["id"], delivery_text="First draft.")
    second = orders.open_order({**BRIEF, "business_name": "Other Co"})
    panel.refresh_orders()
    table = panel.fiverr_order_table
    row_first = next(r for r in range(table.rowCount())
                     if table.item(r, 0).data(Qt.UserRole) == first["id"])
    row_second = next(r for r in range(table.rowCount())
                      if table.item(r, 0).data(Qt.UserRole) == second["id"])
    table.setCurrentCell(row_first, 0)
    panel.fiverr_delivery_box.setPlainText("First draft, corrected.")
    table.setCurrentCell(row_second, 0)          # switch without waiting
    assert orders.get_order(first["id"])["delivery_text"] == "First draft, corrected."
    assert orders.get_order(second["id"])["delivery_text"] == ""


def test_edit_autosave_timer_flushes_on_its_own(window, app):
    from PySide6.QtTest import QTest
    panel = window.fiverr_panel
    panel.clear()
    order = orders.open_order(BRIEF)
    _load_first_order(panel)
    panel.fiverr_gig_box.setPlainText("Typed by hand.")
    QTest.qWait(panel.EDIT_SAVE_DELAY_MS + 200)
    assert orders.get_order(order["id"])["gig_text"] == "Typed by hand."
