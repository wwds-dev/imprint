"""Audiobook conversions survive a restart and bill honestly across runs.

Contract: one row per book remembers how far the converter got and how
much of the flat estimate has been billed; each run authorizes only the
remaining fraction; an interrupted run — including one whose process
died with the app — bills exactly the chunks it generated; the sum over
any number of interruptions converges on one estimate, never more.
"""

import os

import pytest

from agents.audiobook import conversions
from services.database import get_connection


@pytest.fixture(autouse=True)
def clean_table():
    yield
    with get_connection() as conn:
        conn.execute("DELETE FROM audiobook_conversions")


def _open(**overrides):
    fields = dict(source_path="/books/novel.epub",
                  output_path="/out/novel.mp3", voice="alloy",
                  chunk_tokens=1200, estimate_eur=10.0, project=None)
    fields.update(overrides)
    return conversions.open_job(**fields)


# ── the Qt-free ledger ──────────────────────────────────────────────────────

def test_open_job_reuses_the_books_row_and_keeps_billed():
    first = _open()
    conversions.update_progress(first["id"], 40, 100)
    conversions.settle(first["id"], status="interrupted", billed_add=4.0)

    resumed = _open(voice="verse")          # same book, new run
    assert resumed["id"] == first["id"]
    assert resumed["voice"] == "verse"
    assert resumed["billed_eur"] == pytest.approx(4.0)
    assert resumed["status"] == "running"
    # The new run's spend is measured from where it started.
    assert resumed["run_baseline"] == 40

    completed = conversions.get_job(first["id"])
    conversions.settle(first["id"], status="completed", billed_add=6.0)
    # A completed book does not get reused; a new Start opens a new row.
    fresh = _open()
    assert fresh["id"] != first["id"]
    assert completed is not None


def test_remaining_fraction_and_run_spend_math():
    row = _open()
    assert conversions.remaining_fraction(row) == 1.0      # nothing known yet
    conversions.update_progress(row["id"], 40, 100)
    row = conversions.get_job(row["id"])
    assert conversions.remaining_fraction(row) == pytest.approx(0.6)
    # This run started at baseline 0 and produced 40 of 100 chunks.
    assert conversions.run_spend_eur(row) == pytest.approx(4.0)

    resumed = _open()                        # baseline moves to 40
    conversions.update_progress(resumed["id"], 70, 100)
    resumed = conversions.get_job(resumed["id"])
    assert conversions.run_spend_eur(resumed) == pytest.approx(3.0)


def test_dead_runs_are_only_the_running_ones():
    running = _open()
    other = _open(source_path="/books/b.epub", output_path="/out/b.mp3")
    conversions.settle(other["id"], status="interrupted")
    assert [row["id"] for row in conversions.dead_runs()] == [running["id"]]


# ── the panel settlement and startup scan ───────────────────────────────────

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


def test_interrupted_run_bills_only_what_it_generated(window):
    panel = window.audiobook_panel
    row = _open()
    conversions.update_progress(row["id"], 25, 100)
    token = window.restore_request(
        "audiobook", "openai", "gpt-4o-mini-tts", "novel.epub",
        label="audiobook", flat_cost_eur=10.0)
    panel._request_token = token
    panel._conversion_job_id = row["id"]

    before = window.usage_tracker.get_agent_today_total("audiobook")
    panel._close_request(success=False)

    after = window.usage_tracker.get_agent_today_total("audiobook")
    assert after == pytest.approx(before + 2.5)   # 25 of 100 chunks
    settled = conversions.get_job(row["id"])
    assert settled["status"] == "interrupted"
    assert settled["billed_eur"] == pytest.approx(2.5)
    assert token not in window._pending_requests


def test_completed_run_bills_the_authorized_remainder(window):
    panel = window.audiobook_panel
    row = _open()
    conversions.update_progress(row["id"], 25, 100)
    conversions.settle(row["id"], status="interrupted", billed_add=2.5)
    resumed = _open()                        # baseline 25, billed 2.5
    remaining = 10.0 * conversions.remaining_fraction(resumed)
    token = window.restore_request(
        "audiobook", "openai", "gpt-4o-mini-tts", "novel.epub",
        label="audiobook", flat_cost_eur=remaining)
    panel._request_token = token
    panel._conversion_job_id = resumed["id"]

    before = window.usage_tracker.get_agent_today_total("audiobook")
    panel._close_request(success=True)

    after = window.usage_tracker.get_agent_today_total("audiobook")
    assert after == pytest.approx(before + 7.5)
    settled = conversions.get_job(resumed["id"])
    assert settled["status"] == "completed"
    # Across both runs the book billed exactly its one estimate.
    assert settled["billed_eur"] == pytest.approx(10.0)
    assert token not in window._pending_requests


def test_startup_scan_settles_a_dead_run_and_surfaces_it(window):
    panel = window.audiobook_panel
    row = _open()
    conversions.update_progress(row["id"], 30, 100)   # died at 30%

    before = window.usage_tracker.get_agent_today_total("audiobook")
    panel._resume_scan_done = False
    panel.resume_pending_conversions()

    after = window.usage_tracker.get_agent_today_total("audiobook")
    assert after == pytest.approx(before + 3.0)
    settled = conversions.get_job(row["id"])
    assert settled["status"] == "interrupted"
    assert settled["billed_eur"] == pytest.approx(3.0)
    status = panel.audiobook_status_label.text()
    assert "[Interrupted]" in status and "novel.epub" in status
    assert "30 of 100" in status

    # Idempotent: a second scan finds nothing still 'running'.
    panel._resume_scan_done = False
    panel.resume_pending_conversions()
    assert conversions.get_job(row["id"])["billed_eur"] == pytest.approx(3.0)


def test_startup_scan_runs_once_per_process(window, monkeypatch):
    panel = window.audiobook_panel
    calls = []
    monkeypatch.setattr(conversions, "dead_runs",
                        lambda: calls.append(1) or [])
    panel._resume_scan_done = False
    panel.resume_pending_conversions()
    panel.resume_pending_conversions()
    assert len(calls) == 1
