"""Music release plans are records, and the next plan learns from reality.

Contract: every generated plan persists with its inputs, parsed sections
and owning Project; outcomes are self-reported and attach to the artist's
most recent stored plan; the next analyse() prompt carries a compact
past-performance block — and only when outcomes actually exist.
"""

import json
import os
import types

import pytest

from agents.music import plans
from services.database import get_connection


@pytest.fixture(autouse=True)
def clean_table():
    yield
    with get_connection() as conn:
        conn.execute("DELETE FROM music_release_plans")


def _save(**overrides):
    fields = dict(artist="Nova Drift", genre="Lo-fi", release_type="EP",
                  distributor="DistroKid", audience="18-25",
                  description="dark trap with melodic hooks",
                  plan_text="1. ARTIST PROFILE\nx\n2. RELEASE SETUP\ny",
                  sections={"profile": "x", "release": "y"}, project=None)
    fields.update(overrides)
    return plans.save_plan(**fields)


def test_plan_round_trip_keeps_inputs_sections_and_project():
    plan_id = _save(project="music-proj")
    stored = plans.get_plan(plan_id)
    assert stored["artist"] == "Nova Drift"
    assert stored["project"] == "music-proj"
    assert json.loads(stored["sections_json"])["release"] == "y"
    assert stored["outcome_recorded_at"] == ""
    listed = plans.list_plans(artist="nova drift")   # case-insensitive
    assert [row["id"] for row in listed] == [plan_id]


def test_outcome_attaches_and_reads_back():
    plan_id = _save()
    plans.record_outcome(plan_id, streams=120000, revenue_usd=340.5,
                         notes="playlists carried it")
    stored = plans.get_plan(plan_id)
    assert stored["outcome_streams"] == 120000
    assert stored["outcome_revenue_usd"] == pytest.approx(340.5)
    assert stored["outcome_recorded_at"] != ""


def test_outcomes_context_only_speaks_from_recorded_reality():
    assert plans.outcomes_context("Nova Drift") == ""
    first = _save()
    # A stored but unreleased plan still says nothing.
    assert plans.outcomes_context("Nova Drift") == ""
    plans.record_outcome(first, streams=120000, revenue_usd=340.5,
                         notes="playlists carried it")
    context = plans.outcomes_context("Nova Drift")
    assert "120,000 streams" in context
    assert "$340.50 revenue" in context
    assert "playlists carried it" in context
    assert "self-reported" in context
    assert plans.outcomes_context("Someone Else") == ""


# ── the panel wiring ─────────────────────────────────────────────────────────

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


def test_finished_plan_is_stored_with_the_active_project(window, monkeypatch):
    panel = window.music_panel
    panel.music_artist_input.setText("Nova Drift")
    panel.music_query_input.setPlainText("dark trap")
    monkeypatch.setattr(window, "_active_project",
                        lambda: {"id": "music-proj", "name": "Music"})
    monkeypatch.setattr(window, "record_request", lambda *a, **k: None)
    panel._on_finished(
        "1. ARTIST PROFILE\nprofile text\n2. RELEASE SETUP\nsetup text")
    (stored,) = plans.list_plans(artist="Nova Drift")
    assert stored["project"] == "music-proj"
    assert json.loads(stored["sections_json"])["profile"] == "profile text"
    assert "stored" in panel.music_status_label.text()


def test_analyse_prompt_carries_recorded_outcomes(window, monkeypatch):
    panel = window.music_panel
    plan_id = _save(artist="Nova Drift")
    plans.record_outcome(plan_id, streams=5000, revenue_usd=12.0, notes="")

    panel.music_artist_input.setText("Nova Drift")
    panel.music_query_input.setPlainText("a follow-up single")
    captured = []

    def fake_authorize(agent, provider, model, prompt, **kwargs):
        captured.append(prompt)
        return False   # stop before any worker spawns
    monkeypatch.setattr(window, "authorize_request", fake_authorize)
    panel.analyse()
    assert captured, "authorize_request was not reached"
    assert "Past releases and measured outcomes" in captured[0]
    assert "5,000 streams" in captured[0]


def test_analyse_prompt_stays_clean_without_outcomes(window, monkeypatch):
    panel = window.music_panel
    panel.music_artist_input.setText("Fresh Face")
    panel.music_query_input.setPlainText("a debut")
    captured = []
    monkeypatch.setattr(
        window, "authorize_request",
        lambda agent, provider, model, prompt, **k:
        captured.append(prompt) or False)
    panel.analyse()
    assert captured and "Past releases" not in captured[0]
