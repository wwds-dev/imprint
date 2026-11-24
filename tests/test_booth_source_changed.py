"""
Booth: a book whose text changed is authorized at full cost (audit QB-2)
=======================================================================
Type: window-level, run headless. The converter subprocess is never started
(run_conversion is replaced) and no key is real.

The narrator converter keeps a chunk cache per book and throws all of it away
when the book's text changes (services/narrator/converter.py,
load_or_create_manifest compares text_sha256). Booth used to authorize only
the unpaid share of the estimate on a resume, whatever happened to the text:
stop at 180 of 200 chunks, edit the book, press Start, and the guard confirmed
10% while the converter narrated 100%. The row now stores the text's hash, and
a mismatch is a fresh start at full cost, asked first.

Run with:  pytest tests/test_booth_source_changed.py -v
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.audiobook import conversions  # noqa: E402
from services.database import get_connection  # noqa: E402


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


def _clear_rows():
    with get_connection() as conn:
        conn.execute("DELETE FROM audiobook_conversions")


@pytest.fixture
def booth(app, window, tmp_path, monkeypatch):
    """Booth on the OpenAI route with one book selected, the guard's caps out
    of the way, the converter replaced by a recorder and every authorization
    recorded (then passed to the real guard)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem
    _clear_rows()
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    window.allow_openai_checkbox.setChecked(True)
    monkeypatch.setattr(window, "session_budget_eur", 1000.0)
    monkeypatch.setattr(window, "daily_budget_eur", 1000.0)
    monkeypatch.setattr(window.usage_tracker, "get_agent_today_total",
                        lambda agent: 0.0)
    monkeypatch.setattr(window.usage_tracker, "get_today_total", lambda: 0.0)
    panel = window.audiobook_panel
    panel._switch_route("openai")
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
    monkeypatch.setattr(panel, "run_conversion",
                        lambda config: started.append(config))
    authorized = []
    real_authorize = window.authorize_request

    def recording_authorize(*args, **kwargs):
        authorized.append(kwargs.get("flat_cost_eur"))
        return real_authorize(*args, **kwargs)

    monkeypatch.setattr(window, "authorize_request", recording_authorize)
    yield panel, book, started, authorized
    window.allow_openai_checkbox.setChecked(False)
    for token in list(window._pending_requests):
        window.abandon_request(token)
    panel._request_token = None
    panel._conversion_job_id = None
    _clear_rows()


def _answers(monkeypatch, *answers):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    queue = list(answers)

    def question(parent, title, text, *rest, **kw):
        shown.append((title, text))
        return queue.pop(0) if queue else QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return shown


def _interrupted_row(panel, book, *, done=7, total=10, source_sha256=None):
    """A run that stopped at done/total under the panel's current settings."""
    expected = panel._converted_output(
        book, Path(panel.audiobook_output_path.text()), "mp3")
    if source_sha256 is None:
        source_sha256 = conversions.text_sha256(panel._text(book))
    row = conversions.open_job(
        source_path=str(book), output_path=str(expected),
        voice=panel.audiobook_voice_box.currentText(),
        chunk_tokens=int(panel.audiobook_chunk_input.text() or 1400),
        estimate_eur=1.0, provider="openai",
        model=panel._route_model("openai"), source_sha256=source_sha256)
    conversions.update_progress(row["id"], done, total)
    conversions.settle(row["id"], status="interrupted")
    return row


def _cache(panel, book, count):
    """`count` narrated chunk files where the converter keeps them."""
    from services.narrator.converter import TEMP_DIRNAME
    expected = panel._converted_output(
        book, Path(panel.audiobook_output_path.text()), "mp3")
    temp = expected.parent / TEMP_DIRNAME
    temp.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (temp / f"chunk_{i}.mp3").write_bytes(b"audio")
    return temp


def _full_estimate(panel, book):
    return panel._estimate(book, "openai")["eur"]


# ── the panel: what the guard is asked to authorize ─────────────────────────

def test_changed_text_is_authorized_at_full_cost(booth, monkeypatch):
    panel, book, started, authorized = booth
    row = _interrupted_row(panel, book, done=7, total=10)
    book.write_text("A completely different opening line. " * 400)
    shown = _answers(monkeypatch)
    panel.start_conversion()
    assert authorized, "Start never reached the guard"
    assert authorized[0] == pytest.approx(_full_estimate(panel, book))
    assert "changed" in shown[0][0].lower()
    assert started, "the confirmed run did not start"
    resumed = conversions.get_job(row["id"])
    # A fresh start: the counts restart, and the new text's hash is stored.
    assert (resumed["chunks_done"], resumed["run_baseline"]) == (0, 0)
    assert resumed["source_sha256"] == conversions.text_sha256(
        panel._text(book))


def test_unchanged_text_still_resumes_at_the_remaining_fraction(
        booth, monkeypatch):
    panel, book, started, authorized = booth
    _interrupted_row(panel, book, done=7, total=10)
    _cache(panel, book, 7)
    shown = _answers(monkeypatch)
    panel.start_conversion()
    assert authorized[0] == pytest.approx(
        round(_full_estimate(panel, book) * 0.3, 6))
    assert not any("changed" in title.lower() for title, _ in shown)
    assert started


def test_declining_the_fresh_start_sends_nothing(booth, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    panel, book, started, authorized = booth
    row = _interrupted_row(panel, book, done=7, total=10)
    book.write_text("A completely different opening line. " * 400)
    _answers(monkeypatch, QMessageBox.No)
    panel.start_conversion()
    assert authorized == [] and started == []
    assert "[Cancelled]" in panel.audiobook_status_label.text()
    kept = conversions.get_job(row["id"])
    assert (kept["chunks_done"], kept["status"]) == (7, "interrupted")


def test_a_row_from_before_the_hash_counts_an_edited_file_as_changed(
        booth, monkeypatch):
    """Rows written by an older Imprint carry no hash; an edit after the run
    last touched the row is the only evidence, and it means full cost."""
    panel, book, started, authorized = booth
    _interrupted_row(panel, book, done=7, total=10, source_sha256="")
    later = time.time() + 120
    os.utime(book, (later, later))
    _answers(monkeypatch)
    panel.start_conversion()
    assert authorized[0] == pytest.approx(_full_estimate(panel, book))


def test_a_finished_run_with_its_cache_deleted_is_not_authorized_at_zero(
        booth, monkeypatch):
    """Code review P1-1: done == total with no chunk files on disk
    authorized €0, and the converter narrated every chunk again."""
    panel, book, started, authorized = booth
    row = _interrupted_row(panel, book, done=10, total=10)
    _answers(monkeypatch)
    panel.start_conversion()
    assert authorized[0] == pytest.approx(_full_estimate(panel, book))
    resumed = conversions.get_job(row["id"])
    # The run is measured from what is really cached, so it bills in full.
    assert (resumed["chunks_done"], resumed["run_baseline"]) == (0, 0)


def test_a_partly_deleted_cache_authorizes_the_missing_chunks(
        booth, monkeypatch):
    panel, book, started, authorized = booth
    row = _interrupted_row(panel, book, done=7, total=10)
    _cache(panel, book, 4)
    _answers(monkeypatch)
    panel.start_conversion()
    assert authorized[0] == pytest.approx(
        _full_estimate(panel, book) * 0.6)
    resumed = conversions.get_job(row["id"])
    assert (resumed["chunks_done"], resumed["run_baseline"]) == (4, 4)


# ── the ledger helper ───────────────────────────────────────────────────────

def test_source_changed_rules(tmp_path):
    book = tmp_path / "b.txt"
    book.write_text("x")
    now = datetime.now()
    assert conversions.source_changed(None, "h", str(book)) is False
    assert conversions.source_changed(
        {"source_sha256": "h"}, "h", str(book)) is False
    assert conversions.source_changed(
        {"source_sha256": "h"}, "other", str(book)) is True
    # No hash: the file's mtime against the row's last update.
    after = (now + timedelta(hours=1)).isoformat(timespec="seconds")
    before = (now - timedelta(hours=1)).isoformat(timespec="seconds")
    assert conversions.source_changed(
        {"source_sha256": "", "updated_at": after}, "h", str(book)) is False
    assert conversions.source_changed(
        {"source_sha256": "", "updated_at": before}, "h", str(book)) is True
    # Unknown (missing file, unreadable date) reads as changed.
    assert conversions.source_changed(
        {"source_sha256": "", "updated_at": after}, "h",
        str(tmp_path / "gone.txt")) is True
    assert conversions.source_changed(
        {"source_sha256": "", "updated_at": ""}, "h", str(book)) is True


def test_open_job_keeps_a_stored_hash_when_none_is_given():
    _clear_rows()
    try:
        row = conversions.open_job(
            source_path="/b/x.txt", output_path="/o/x.mp3", voice="alloy",
            chunk_tokens=1400, estimate_eur=1.0, provider="openai",
            model="gpt-4o-mini-tts", source_sha256="abc")
        again = conversions.open_job(
            source_path="/b/x.txt", output_path="/o/x.mp3", voice="alloy",
            chunk_tokens=1400, estimate_eur=1.0, provider="openai",
            model="gpt-4o-mini-tts")
        assert again["id"] == row["id"] and again["source_sha256"] == "abc"
    finally:
        _clear_rows()
