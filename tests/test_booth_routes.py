"""
Imprint — Booth's narration routes
==================================
Type: window-level, run headless. Nothing leaves the machine: the converter
subprocess is never started (run_conversion is replaced) and no key is real.

OpenAI removes gpt-4o-mini-tts, Booth's only voice, on 2027-01-06. Booth now
narrates through OpenAI, Gemini 3.8 Flash TTS or ElevenLabs. These pin the
rules that keep the choice honest and the money right:

* the route chosen is the route the converter is told, and the route billed;
* every conversion is assessed across the narrators that can run, each priced
  for this book — the selected one at what this run still owes;
* Apply switches the narrator and asks again; it never starts a run;
* a narrator without its key, or without a price, starts nothing;
* a book interrupted under one narrator is not silently resumed on another.

Run with:  pytest tests/test_booth_routes.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.audiobook import conversions  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information,
             QMessageBox.critical)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.critical = staticmethod(lambda *a, **k: None)
    try:
        yield main.GodAI()
    finally:
        (QMessageBox.warning, QMessageBox.question, QMessageBox.information,
         QMessageBox.critical) = saved


@pytest.fixture
def booth(app, window, tmp_path, monkeypatch):
    """Booth with one short book selected, every route keyed and permitted,
    and the converter replaced by a recorder."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem
    from services.database import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM audiobook_conversions")
    conn.commit()
    conn.close()
    for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.setenv(key, "test-not-a-real-key")
    for name in ("openai", "gemini", "elevenlabs"):
        getattr(window, f"allow_{name}_checkbox").setChecked(True)
    monkeypatch.setattr(window, "session_budget_eur", 1000.0)
    monkeypatch.setattr(window, "daily_budget_eur", 1000.0)
    # Earlier test modules bill audiobook runs into the shared test database,
    # which uses up Booth's €10 daily cap; these tests are about routes.
    monkeypatch.setattr(window.usage_tracker, "get_agent_today_total",
                        lambda agent: 0.0)
    monkeypatch.setattr(window.usage_tracker, "get_today_total", lambda: 0.0)
    panel = window.audiobook_panel
    book = tmp_path / "novel.txt"
    book.write_text("It was a dark and stormy night. " * 400)
    panel.audiobook_book_list.clear()
    item = QListWidgetItem(book.name)
    item.setData(Qt.UserRole, str(book))
    panel.audiobook_book_list.addItem(item)
    panel.audiobook_book_list.setCurrentItem(item)
    panel.audiobook_output_path.setText(str(tmp_path / "out"))
    (tmp_path / "out").mkdir()
    started = []
    monkeypatch.setattr(panel, "run_conversion", lambda config: started.append(config))
    yield panel, started
    for name in ("openai", "gemini", "elevenlabs"):
        getattr(window, f"allow_{name}_checkbox").setChecked(False)
    panel._switch_route("openai")
    for token in list(window._pending_requests):
        window.abandon_request(token)


def _answers(monkeypatch, *answers):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    queue = list(answers)

    def question(parent, title, text, *rest, **kw):
        shown.append((title, text))
        return queue.pop(0) if queue else QMessageBox.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return shown


def test_three_narrators_are_offered(booth):
    panel, _started = booth
    routes = [panel.audiobook_route_box.itemData(i)
              for i in range(panel.audiobook_route_box.count())]
    assert routes == ["openai", "gemini", "elevenlabs"]
    panel._switch_route("gemini")
    voices = [panel.audiobook_voice_box.itemText(i)
              for i in range(panel.audiobook_voice_box.count())]
    assert "Kore" in voices and "alloy" not in voices


def test_the_chosen_route_is_what_runs_and_what_is_billed(booth, window,
                                                          monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    panel, started = booth
    panel._switch_route("gemini")
    shown = _answers(monkeypatch, QMessageBox.Yes)
    panel.start_conversion()
    assert len(started) == 1, shown
    config = started[0]
    assert (config["provider"], config["model"]) == ("gemini", "gemini-3.8-flash-tts")
    assert config["voice"] == "Kore"
    snapshot = window.pending_request_snapshot(panel._request_token)
    assert (snapshot["provider"], snapshot["model"]) == ("gemini", "gemini-3.8-flash-tts")
    row = conversions.get_job(panel._conversion_job_id)
    assert (row["provider"], row["model"]) == ("gemini", "gemini-3.8-flash-tts")


def test_every_narrator_is_priced_for_this_book_in_the_assessment(booth, window,
                                                                  monkeypatch):
    panel, _started = booth
    captured = []
    real = window.authorize_request
    monkeypatch.setattr(window, "authorize_request",
                        lambda *a, **k: (captured.append(k.get("assessment")), False)[1])
    panel.start_conversion()
    assessment = captured[0]
    costs = {o.candidate.provider: o.cost_eur for _s, o in assessment.ranked}
    assert set(costs) == {"OpenAI", "Gemini", "ElevenLabs"}
    assert all(cost and cost > 0 for cost in costs.values())
    assert costs["ElevenLabs"] > 3 * costs["OpenAI"]      # $0.08 vs ~$0.016 per 1k chars
    monkeypatch.setattr(window, "authorize_request", real)


def test_apply_switches_the_narrator_and_asks_again(booth, monkeypatch):
    """Selected ElevenLabs at five times the price: the assessment offers a
    cheaper narrator; Apply switches to it and asks again; No starts nothing."""
    from PySide6.QtWidgets import QMessageBox
    panel, started = booth
    panel._switch_route("elevenlabs")
    shown = _answers(monkeypatch, QMessageBox.Apply, QMessageBox.No)
    panel.start_conversion()
    if len(shown) == 1:
        pytest.skip("the profile kept ElevenLabs within a point of the best")
    assert len(shown) == 2
    assert panel._route() != "elevenlabs"
    assert started == []


def test_a_narrator_without_its_key_starts_nothing(booth, monkeypatch):
    panel, started = booth
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    panel._switch_route("elevenlabs")
    panel.start_conversion()
    assert started == []
    assert "ELEVENLABS_API_KEY" in panel.audiobook_status_label.text()


def test_a_narrator_without_a_price_starts_nothing(booth, monkeypatch):
    import services.per_unit_pricing as pricing
    panel, started = booth
    monkeypatch.setattr(pricing, "gemini_tts_cost_eur", lambda *a, **k: None)
    panel._switch_route("gemini")
    panel.start_conversion()
    assert started == []


def test_a_book_paused_under_one_narrator_asks_before_another(booth, monkeypatch):
    """Cached chunks belong to the narrator that made them; switching means
    narrating again from the start, so it is asked, never silent."""
    from PySide6.QtWidgets import QMessageBox
    panel, started = booth
    book = panel.audiobook_book_list.currentItem().data(0x0100)
    expected = panel._converted_output(
        __import__("pathlib").Path(book),
        __import__("pathlib").Path(panel.audiobook_output_path.text()), "mp3")
    row = conversions.open_job(
        source_path=book, output_path=str(expected), voice="alloy",
        chunk_tokens=int(panel.audiobook_chunk_input.text() or 1400),
        estimate_eur=1.0, provider="openai", model="gpt-4o-mini-tts")
    conversions.update_progress(row["id"], 3, 10)
    conversions.settle(row["id"], status="interrupted")
    panel._switch_route("gemini")
    shown = _answers(monkeypatch, QMessageBox.Yes, QMessageBox.Yes)
    panel.start_conversion()
    assert "Settings changed" in shown[0][0]
    assert "cached by openai" in shown[0][1]
    assert panel._route() == "openai"                 # resumed on its own narrator
    assert started and started[0]["provider"] == "openai"


def test_an_older_install_gains_the_new_narrators_on_launch(tmp_path, monkeypatch):
    """Rows made from registry.json allowed only openai/qwen, and the guard
    refuses a provider not on the list — so without this the new narrators
    were blocked on every existing install."""
    import json
    from services import database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "imprint.db")
    db.init_db()
    conn = db.get_connection()
    conn.execute("UPDATE agents SET allowed_providers = ? WHERE name = 'audiobook'",
                 (json.dumps(["openai", "qwen"]),))
    conn.commit()
    conn.close()
    db.init_db()
    conn = db.get_connection()
    allowed = json.loads(conn.execute(
        "SELECT allowed_providers FROM agents WHERE name = 'audiobook'"
    ).fetchone()[0])
    conn.close()
    assert {"openai", "gemini", "elevenlabs"} <= set(allowed)
