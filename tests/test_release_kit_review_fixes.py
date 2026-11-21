"""Regression tests for the slice-1 code-review findings (P2-4, P2-5, P3-x).

docs/audit/one-click-release-code-reviewer.md. The fixture and helpers come
from the e2e and core test modules.
"""

from __future__ import annotations

import csv
import threading
import time

import pytest

from services import database
from services.release_kit import ledger
from tests.test_release_kit_core import _job, db  # noqa: F401  (fixture)
from tests.test_release_kit_e2e import app, kit  # noqa: F401  (fixtures)


# ── P3-1: CSV guard covers tab and carriage return ───────────────────────────

@pytest.mark.parametrize("lead", ["\t", "\r", "=", "+", "-", "@"])
def test_csv_cells_starting_with_a_formula_trigger_stay_text(tmp_path, lead):
    from agents.manuscript.calendar_export import write_calendar_csv
    from tests.test_calendar_export import _slots
    slots = _slots()
    slots[0].caption = lead + "cmd"
    path = write_calendar_csv(slots, tmp_path / "c.csv")
    rows = list(csv.reader(path.open(encoding="utf-8", newline="")))
    assert rows[1][4] == "'" + lead + "cmd"


# ── P3-7: ledger column allow-list ───────────────────────────────────────────

def test_set_stage_and_mark_item_refuse_unknown_columns(db):
    job = _job(db)
    with pytest.raises(ValueError):
        ledger.set_stage(job, "quotes", **{"status = 'x', job_id": "y"})
    ledger.ensure_item(job, "quotes", "quotes:request#1")
    with pytest.raises(ValueError):
        ledger.mark_item(job, "quotes", "quotes:request#1", "done",
                         **{"state = 'x' --": 1})
    ledger.set_stage(job, "quotes", status="running")        # still works
    ledger.mark_item(job, "quotes", "quotes:request#1", "failed")


# ── P3-2: the report only offers actions that exist ──────────────────────────

def test_incomplete_captions_do_not_promise_a_rerun(db):
    from services.release_kit import report
    job = _job(db)
    ledger.set_stage(job, "captions", status="incomplete",
                     result={"blank": [1, 2], "slots": 56, "why": "Cut off."})
    ledger.set_stage(job, "quotes", status="done", result={})
    text = report.build(job)
    assert "2 of 56 posts have no caption" in text
    assert "run this step again" not in text


# ── P3-3: keep-awake that is not held is not claimed ─────────────────────────

def test_the_window_only_claims_awake_when_it_is_held():
    from ui.release_kit.window import awake_line
    assert "stays awake" in awake_line(True)
    assert "stays awake" not in awake_line(False)
    assert "sleep" in awake_line(False).lower()


# ── P3-4: the quote bound follows the prompt ─────────────────────────────────

def test_quote_bound_leaves_room_when_the_prompt_grows(monkeypatch):
    from agents.manuscript import quote_finder as qf
    from services.release_kit import stages
    monkeypatch.setattr(qf, "QUOTE_SUGGESTION_PROMPT",
                        qf.QUOTE_SUGGESTION_PROMPT + "x" * 3000)
    windows = [qf.Window(index=i + 1, count=qf.WINDOW_COUNT, start=0, end=0,
                         text="w" * qf.WINDOW_CHARS, percent=i)
               for i in range(qf.WINDOW_COUNT)]
    stages.check_quote_bound(qf.build_quote_messages(windows, qf.MAX_QUOTES))
    windows[0] = qf.Window(index=1, count=qf.WINDOW_COUNT, start=0, end=0,
                           text="w" * (qf.WINDOW_CHARS + 5000), percent=0)
    with pytest.raises(stages.BoundExceeded):
        stages.check_quote_bound(qf.build_quote_messages(windows, qf.MAX_QUOTES))


# ── P3-5: resume reports an unexpected error instead of raising ──────────────

def test_resume_that_fails_unexpectedly_leaves_a_readable_note(kit, monkeypatch, tmp_path):
    window, driver, dialogs, calls = kit
    window_tmp = lambda: tmp_path
    job = ledger.get_job(_job(window_tmp(), project_id="book-a"))
    ledger.set_job_status(job["id"], "paused", reason="user_stop")
    win = window.show_release_kits(job_id=job["id"])
    win._reload(select=job["id"])

    def boom(job_id):
        raise OSError("disk went away")
    monkeypatch.setattr(driver, "resume", boom)
    win.resume()                                   # must not raise
    assert "disk went away" in win.note.text()
    assert "Checking finished files" not in win.note.text()


# ── P2-5: quit while a local request is in flight ────────────────────────────

def test_quitting_mid_quotes_with_a_slow_model_pauses_and_ignores_the_late_reply(kit):
    from PySide6.QtWidgets import QApplication
    window, driver, dialogs, calls = kit
    driver.run_inline = False
    gate, entered = threading.Event(), threading.Event()
    fast = window.run_backend

    def slow(provider, model, messages, prompt):
        entered.set()
        gate.wait(10)
        return fast(provider, model, messages, prompt)
    window.run_backend = slow

    window.manuscript_panel.start_release_kit()
    deadline = time.monotonic() + 10
    while not entered.is_set() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)
    assert entered.is_set()

    t0 = time.monotonic()
    driver.stop_now("quit")
    assert time.monotonic() - t0 < 4                # bounded, never terminate()
    (job,) = ledger.list_jobs("book-a")
    assert (job["status"], job["pause_reason"]) == ("paused", "quit")
    assert not driver.is_running() and not driver.keep_awake.held
    assert ledger.running_job() is None
    worker = window.release_kit_worker
    assert worker is not None and worker.isRunning()   # still referenced for the sweep

    gate.set()
    worker.wait(5000)
    for _ in range(50):
        QApplication.processEvents()
        time.sleep(0.005)
    (job,) = ledger.list_jobs("book-a")
    assert (job["status"], job["pause_reason"]) == ("paused", "quit")
    with database.get_connection() as conn:         # a late reply is never billed
        assert conn.execute("SELECT COUNT(*) FROM usage WHERE job_id = ?",
                            (job["id"],)).fetchone()[0] == 0
    assert not any(ctx.get("job_id") == job["id"]
                   for ctx in window._pending_requests.values())
