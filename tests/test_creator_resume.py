"""Creator teaser renders survive a restart: the settled delivery ledger
and the startup reconciliation, reusing the Video workspace's pattern.

Contract under test (mirrors tests/test_video_jobs.py):
  * every new teaser row carries spend_state 'reserved' plus the facts a
    resume needs (flat cost, output path, run id) from its first upsert;
  * pre-feature rows (spend_state '') are never reconciled;
  * a reserved row left by a dead process is re-polled, downloaded into
    the media library, billed exactly once and settled 'billed';
  * a local timeout or exception keeps the row reserved for the next
    launch; a provider verdict releases it.
"""

import os
import types
from datetime import datetime
from pathlib import Path

import pytest

from services.database import get_connection


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


@pytest.fixture()
def account():
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO creator_accounts (handle, created_at) "
            "VALUES ('resume-test', '2026-09-28T00:00:00')")
        row = conn.execute(
            "SELECT id FROM creator_accounts WHERE handle = 'resume-test'"
        ).fetchone()
    yield row["id"]
    with get_connection() as conn:
        conn.execute("DELETE FROM creator_video_jobs")
        conn.execute("DELETE FROM creator_media")


def _insert_job(account_id, *, request_id="req-1", spend_state="reserved",
                status="running", output_path="", flat_cost_eur=0.5,
                estimated_usd=0.6):
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO creator_video_jobs
                 (request_id, account_id, created_at, updated_at, endpoint,
                  prompt, status, spend_state, flat_cost_eur, output_path,
                  estimated_usd)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (request_id, account_id, now, now, "/bytedance/x",
             "a teaser", status, spend_state, flat_cost_eur, output_path,
             estimated_usd))
    return request_id


def _job_row(request_id):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM creator_video_jobs WHERE request_id = ?",
            (request_id,)).fetchone()


def test_creator_video_jobs_schema_gained_settlement_fields():
    with get_connection() as conn:
        columns = {row["name"] for row in
                   conn.execute("PRAGMA table_info(creator_video_jobs)")}
    assert {"spend_state", "flat_cost_eur", "output_path",
            "run_id"} <= columns


def test_live_upsert_reserves_and_carries_resume_facts(window, account):
    panel = window.creator_panel
    panel._video_context = {
        "account_id": account, "content_id": None, "project_id": None,
        "prompt": "a teaser", "output_path": "/tmp/teaser.mp4",
        "request_token": "tok", "job_id": "", "provider_completed": False,
        "cancel_requested": False, "endpoint": "/bytedance/x",
        "estimated_credits": 5.0, "estimated_usd": 0.6,
        "estimated_eur": 0.51, "run_id": "run-77",
    }
    job = types.SimpleNamespace(
        job_id="req-live", status="queued", error="", endpoint="/bytedance/x",
        correlation_id="")
    try:
        panel._video_job_update(job)
    finally:
        panel._video_context = {}
    row = _job_row("req-live")
    assert row["spend_state"] == "reserved"
    assert row["flat_cost_eur"] == pytest.approx(0.51)
    assert row["output_path"] == "/tmp/teaser.mp4"
    assert row["run_id"] == "run-77"


def test_reconciliation_finishes_and_bills_a_stranded_teaser(
        window, account, tmp_path, monkeypatch):
    output_path = tmp_path / "teaser-1.mp4"
    request_id = _insert_job(account, request_id="req-9",
                             output_path=str(output_path),
                             flat_cost_eur=0.44)

    completed = types.SimpleNamespace(
        status="completed", error="",
        video_url="https://api.higgsfield.ai/v.mp4")
    fake_client = types.SimpleNamespace(
        configured=True,
        wait=lambda job, timeout, on_progress, should_cancel: completed)
    from agents.creator import panel as creator_panel_module
    monkeypatch.setattr(creator_panel_module, "HiggsfieldClient",
                        lambda: fake_client)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        @staticmethod
        def iter_content(chunk_size):
            yield b"teaser-bytes"

    import requests

    def fake_get(url, *args, **kwargs):
        # Only the teaser download is faked; anything else (e.g. the
        # Ollama client refreshing during record_request's UI update)
        # behaves like an offline network.
        if "higgsfield" in url:
            return FakeResponse()
        raise requests.exceptions.ConnectionError("test: no network")

    monkeypatch.setattr(requests, "get", fake_get)
    from agents.video import workers
    monkeypatch.setattr(workers.VideoResumeWorker, "start",
                        workers.VideoResumeWorker.run)
    monkeypatch.setattr(window.creator_panel, "refresh_media", lambda: None)

    before = window.usage_tracker.get_agent_today_total("creator")
    window.creator_panel._resume_started = False
    window.creator_panel.resume_pending_teasers()

    assert output_path.read_bytes() == b"teaser-bytes"
    row = _job_row(request_id)
    assert (row["status"], row["spend_state"]) == ("completed", "billed")
    assert row["local_path"] == str(output_path)
    assert row["actual_usd"] == pytest.approx(0.6)
    after = window.usage_tracker.get_agent_today_total("creator")
    assert after == pytest.approx(before + 0.44)
    assert not window._pending_requests
    with get_connection() as conn:
        media = conn.execute(
            "SELECT source, job_id FROM creator_media WHERE account_id = ?",
            (account,)).fetchone()
    assert media["source"] == "higgsfield"
    assert media["job_id"] == "req-9"


def test_pre_feature_rows_are_never_reconciled(window, account, monkeypatch):
    _insert_job(account, request_id="req-old", spend_state="")
    spawned = []
    monkeypatch.setattr(window.creator_panel, "_spawn_teaser_resume",
                        spawned.append)
    window.creator_panel._resume_started = False
    window.creator_panel.resume_pending_teasers()
    assert spawned == []


def test_timeout_and_local_exceptions_keep_the_row_reserved(
        window, account, tmp_path, monkeypatch):
    request_id = _insert_job(account, request_id="req-slow",
                             output_path=str(tmp_path / "t.mp4"))

    stalled = types.SimpleNamespace(
        status="failed", error="Timed out after 900s", video_url="")
    fake_client = types.SimpleNamespace(
        configured=True,
        wait=lambda job, timeout, on_progress, should_cancel: stalled)
    from agents.creator import panel as creator_panel_module
    monkeypatch.setattr(creator_panel_module, "HiggsfieldClient",
                        lambda: fake_client)
    from agents.video import workers
    monkeypatch.setattr(workers.VideoResumeWorker, "start",
                        workers.VideoResumeWorker.run)

    window.creator_panel._resume_started = False
    window.creator_panel.resume_pending_teasers()
    row = _job_row(request_id)
    # The local deadline was not persisted as a verdict, spend stays open
    # for the next launch, and no reservation is left in this session.
    assert row["spend_state"] == "reserved"
    # Non-terminal: the rebuilt poll stub ('queued') or the last live
    # status — never the local deadline's bogus 'failed'.
    assert row["status"] in ("queued", "running")
    assert not window._pending_requests


def test_provider_verdict_releases_the_row(window, account, tmp_path,
                                           monkeypatch):
    request_id = _insert_job(account, request_id="req-nsfw",
                             output_path=str(tmp_path / "n.mp4"))
    rejected = types.SimpleNamespace(
        status="nsfw", error="moderation", video_url="")
    fake_client = types.SimpleNamespace(
        configured=True,
        wait=lambda job, timeout, on_progress, should_cancel: rejected)
    from agents.creator import panel as creator_panel_module
    monkeypatch.setattr(creator_panel_module, "HiggsfieldClient",
                        lambda: fake_client)
    from agents.video import workers
    monkeypatch.setattr(workers.VideoResumeWorker, "start",
                        workers.VideoResumeWorker.run)

    before = window.usage_tracker.get_agent_today_total("creator")
    window.creator_panel._resume_started = False
    window.creator_panel.resume_pending_teasers()
    row = _job_row(request_id)
    assert (row["status"], row["spend_state"]) == ("nsfw", "released")
    assert row["policy_result"] == "provider-rejected"
    # Nothing was billed for a rejected render.
    assert window.usage_tracker.get_agent_today_total(
        "creator") == pytest.approx(before)
    assert not window._pending_requests
