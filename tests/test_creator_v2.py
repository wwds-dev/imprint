"""
Imprint — Muse agent, second arc
================================
Type: Unit + panel tests for voice, character, media and records.

Covers the three things v1 left thin — an unused media column, a Higgsfield
submit with no polling behind it, and untested panel handlers.

The earnings, pricing, segment and agency tests were removed on 2026-09-30
with the code they covered; Backstage owns that work now.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A real schema in a throwaway file — these are SQL-shaped behaviours."""
    import services.database as database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()

    import agents.creator.profile as profile
    monkeypatch.setattr(profile, "get_connection", database.get_connection)

    conn = database.get_connection()
    conn.execute(
        "INSERT INTO creator_accounts (handle, account_type, created_at) "
        "VALUES ('@a', 'own', ?)", (datetime.now().isoformat(),))
    conn.commit()
    account_id = conn.execute(
        "SELECT id FROM creator_accounts WHERE handle='@a'").fetchone()[0]
    return database, account_id


# ── Voice ────────────────────────────────────────────────────────────────────
def test_voice_block_is_empty_when_nothing_is_recorded(db):
    from agents.creator.profile import voice_block
    _, account_id = db
    assert voice_block(account_id) == ""


def test_voice_block_carries_the_samples(db):
    """Samples are what the model imitates — the rules only stop it drifting."""
    from agents.creator.profile import save_voice, voice_block
    _, account_id = db
    save_voice(account_id, samples="first post\nsecond post", tone="dry")
    block = voice_block(account_id)
    assert "first post" in block and "second post" in block
    assert "dry" in block


def test_voice_samples_are_capped(db):
    """Beyond a handful the marginal value drops and the prompt just costs more."""
    from agents.creator.profile import MAX_SAMPLES, save_voice, voice_block
    _, account_id = db
    save_voice(account_id, samples="\n".join(f"post {i}" for i in range(30)))
    assert voice_block(account_id).count("  — ") == MAX_SAMPLES


def test_saving_voice_twice_updates_rather_than_duplicates(db):
    from agents.creator.profile import load_voice, save_voice
    database, account_id = db
    save_voice(account_id, tone="first")
    save_voice(account_id, tone="second")
    assert load_voice(account_id)["tone"] == "second"
    count = database.get_connection().execute(
        "SELECT COUNT(*) FROM creator_voice").fetchone()[0]
    assert count == 1


def test_voice_reaches_the_draft_prompt(db):
    """The point of the whole feature: it has to be in the prompt."""
    from agents.creator import CreatorAgent
    from agents.creator.profile import save_voice
    _, account_id = db
    save_voice(account_id, samples="a line only this creator would write")
    messages = CreatorAgent().build_draft_prompt(
        {"id": account_id, "handle": "@a", "account_type": "own"},
        "post", "brief")
    assert "a line only this creator would write" in messages[-1]["content"]


# ── Character ────────────────────────────────────────────────────────────────
def test_character_reaches_any_account_that_has_one(db):
    """It used to be gated on an account type that no longer exists. A
    recorded character is itself the signal that one should be kept
    consistent; an account without a record gets nothing extra."""
    from agents.creator import CreatorAgent
    from agents.creator.profile import save_persona
    _, account_id = db
    save_persona(account_id, appearance="silver hair", backstory="from Lisbon")

    with_record = CreatorAgent().build_draft_prompt(
        {"id": account_id, "handle": "@a"}, "post", "x")
    assert "silver hair" in with_record[-1]["content"]

    without = CreatorAgent().build_draft_prompt(
        {"id": account_id + 999, "handle": "@b"}, "post", "x")
    assert "silver hair" not in without[-1]["content"]


def test_persona_seed_is_kept_for_consistent_renders(db):
    from agents.creator.profile import persona_seed, save_persona
    _, account_id = db
    save_persona(account_id, appearance="x", seed=4821)
    assert persona_seed(account_id) == 4821


def test_persona_appearance_is_reused_in_video_prompts(db):
    """Without it every render is a different character."""
    from agents.creator import CreatorAgent
    from agents.creator.profile import save_persona
    _, account_id = db
    save_persona(account_id, appearance="silver hair, green coat")
    prompt = CreatorAgent().build_video_prompt(
        {"id": account_id, "handle": "@a"}, "rooftop")
    assert "silver hair" in prompt


# ── Panel handlers (the gap v1 left) ─────────────────────────────────────────
@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main
    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        w = main.GodAI()
        yield w
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


def test_creator_panel_has_every_tab(window):
    titles = [window.creator_panel.creator_tabs.tabText(i)
              for i in range(window.creator_panel.creator_tabs.count())]
    for expected in ("Draft", "Calendar", "Voice", "Media"):
        assert any(expected in t for t in titles), f"missing {expected} tab"
    # Earnings and Agency moved to Backstage on 2026-09-30. A tab left behind
    # would read as the feature still being here.
    for gone in ("Earnings", "Agency", "Trends"):
        assert not any(gone in t for t in titles), f"{gone} tab is back"


def test_higgsfield_has_an_explicit_api_permission(window):
    window.allow_higgsfield_checkbox.setChecked(False)
    assert not window.current_api_permissions()["allow_higgsfield"]
    window.allow_higgsfield_checkbox.setChecked(True)
    assert window.current_api_permissions()["allow_higgsfield"]
    window.allow_higgsfield_checkbox.setChecked(False)


def test_video_job_schema_preserves_cost_and_lifecycle(db):
    database, _ = db
    columns = {
        row["name"] for row in database.get_connection().execute(
            "PRAGMA table_info(creator_video_jobs)")
    }
    assert {
        "request_id", "endpoint", "prompt_version", "estimated_credits",
        "estimated_usd", "actual_usd", "status", "policy_result",
        "local_path", "correlation_id",
    } <= columns


def test_channel_shows_only_for_off_platform_promo(window):
    window._creator_kind_changed("bio")
    assert not window.creator_panel.creator_channel_box.isVisible()
    window._creator_kind_changed("promo")
    assert window.creator_panel.creator_channel_box.isVisibleTo(window.creator_panel)


def test_drafting_without_an_account_does_not_crash(window):
    window.creator_panel.creator_account_box.clear()
    window.creator_generate()          # warns and returns


def test_media_kind_is_inferred_from_the_extension(window, tmp_path):
    import services.database as database
    conn = database.get_connection()
    conn.execute("INSERT OR IGNORE INTO creator_accounts (handle, account_type,"
                 " created_at) VALUES ('@paneltest','own',?)",
                 (datetime.now().isoformat(),))
    conn.commit()
    account_id = conn.execute(
        "SELECT id FROM creator_accounts WHERE handle='@paneltest'").fetchone()[0]

    window._creator_store_media(account_id, str(tmp_path / "clip.mp4"))
    window._creator_store_media(account_id, str(tmp_path / "shot.jpg"))
    rows = dict(database.get_connection().execute(
        "SELECT path, kind FROM creator_media WHERE account_id = ?",
        (account_id,)).fetchall())
    assert rows[str(tmp_path / "clip.mp4")] == "video"
    assert rows[str(tmp_path / "shot.jpg")] == "image"

    conn = database.get_connection()
    conn.execute("DELETE FROM creator_media WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM creator_accounts WHERE id = ?", (account_id,))
    conn.commit()


# ── Higgsfield worker ────────────────────────────────────────────────────────
def test_worker_reports_a_failed_render_rather_than_hanging(app, tmp_path):
    """v1 submitted and told the user to go look elsewhere. The worker has to
    finish, one way or the other."""
    from ui.workers import HiggsfieldWorker
    from services.higgsfield_client import VideoJob

    class FailingClient:
        def generate_video(self, prompt, **kwargs):
            return VideoJob("job-1", status="queued")

        def wait(self, job, **kwargs):
            return VideoJob("job-1", status="failed", error="render failed")

    worker = HiggsfieldWorker(FailingClient(), "a teaser", tmp_path / "out.mp4")
    errors = []
    worker.error_signal.connect(errors.append)
    worker.run()                      # synchronous: exercise the body directly
    assert errors and "render failed" in errors[0]


def test_estimate_worker_prepares_before_pricing(app):
    from services.higgsfield_client import PreparedVideoRequest, VideoEstimate
    from ui.workers import HiggsfieldEstimateWorker

    events = []

    class Client:
        def prepare_video(self, prompt, **kwargs):
            events.append(("prepare", prompt, kwargs))
            return PreparedVideoRequest("/model/video", {"prompt": prompt})

        def estimate(self, request):
            events.append(("estimate", request))
            return VideoEstimate(credits=2, usd=1)

    worker = HiggsfieldEstimateWorker(Client(), "safe teaser", duration=6)
    results = []
    worker.done_signal.connect(lambda request, estimate: results.append(
        (request, estimate)))
    worker.run()

    assert [event[0] for event in events] == ["prepare", "estimate"]
    assert results[0][1].usd == pytest.approx(1)


def test_worker_cancels_a_queued_remote_render(app, tmp_path):
    from services.higgsfield_client import VideoJob
    from ui.workers import HiggsfieldWorker

    cancelled = []

    class Client:
        def generate_video(self, prompt, **kwargs):
            return VideoJob("job-cancel", status="queued")

        def wait(self, job, *, should_cancel, **kwargs):
            assert should_cancel()
            cancelled.append(job.job_id)
            return VideoJob(job.job_id, status="canceled")

    worker = HiggsfieldWorker(Client(), "teaser", tmp_path / "out.mp4")
    errors = []
    worker.error_signal.connect(errors.append)
    worker.cancel()
    worker.run()

    assert cancelled == ["job-cancel"]
    assert errors == ["Render canceled"]


def test_worker_passes_the_seed_through(app, tmp_path):
    """A persona's locked seed has to reach the API or renders drift."""
    from ui.workers import HiggsfieldWorker
    from services.higgsfield_client import VideoJob

    seen = {}

    class RecordingClient:
        def generate_video(self, prompt, **kwargs):
            seen.update(kwargs)
            return VideoJob("job-1")

        def wait(self, job, **kwargs):
            return VideoJob("job-1", status="failed", error="stop here")

    worker = HiggsfieldWorker(RecordingClient(), "teaser",
                              tmp_path / "out.mp4", seed=4821)
    worker.error_signal.connect(lambda _: None)
    worker.run()
    assert seen.get("seed") == 4821


def test_deleting_project_unfiles_creator_work_but_keeps_the_account(db):
    from services.registry import Registry

    database, account_id = db
    registry = Registry()
    registry.upsert_project("creator-work", "Creator campaign")
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO creator_content "
            "(account_id, project_id, created_at, body) VALUES (?,?,?,?)",
            (account_id, "creator-work", datetime.now().isoformat(), "A draft"))
        conn.execute(
            "INSERT INTO creator_video_jobs "
            "(request_id, account_id, project_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?)",
            ("creator-job", account_id, "creator-work", "now", "now"))
    registry.delete_project("creator-work")
    with database.get_connection() as conn:
        content = conn.execute(
            "SELECT project_id, body FROM creator_content").fetchone()
        job = conn.execute(
            "SELECT project_id FROM creator_video_jobs WHERE request_id=?",
            ("creator-job",)).fetchone()
        account = conn.execute(
            "SELECT handle FROM creator_accounts WHERE id=?",
            (account_id,)).fetchone()
    assert (content["project_id"], content["body"]) == (None, "A draft")
    assert job["project_id"] is None
    assert account["handle"] == "@a"


def test_existing_creator_tables_gain_optional_project_columns(tmp_path, monkeypatch):
    import sqlite3
    from services import database

    path = tmp_path / "legacy.db"
    legacy_schema = database.SCHEMA.replace(
        "    project_id   TEXT REFERENCES projects(id) ON DELETE SET NULL,\n",
        "", 1).replace(
        "    project_id       TEXT REFERENCES projects(id) ON DELETE SET NULL,\n",
        "", 1)
    with sqlite3.connect(path) as conn:
        conn.executescript(legacy_schema)
        conn.execute(
            "INSERT INTO creator_accounts (handle, created_at) "
            "VALUES ('@legacy', 'yesterday')")
        conn.execute(
            "INSERT INTO creator_content (account_id, created_at, body) "
            "VALUES (1, 'yesterday', 'Keep this draft')")
    monkeypatch.setattr(database, "DB_PATH", path)
    database.init_db()
    with database.get_connection() as conn:
        content_columns = {row["name"] for row in conn.execute(
            "PRAGMA table_info(creator_content)")}
        job_columns = {row["name"] for row in conn.execute(
            "PRAGMA table_info(creator_video_jobs)")}
        draft = conn.execute(
            "SELECT project_id, body FROM creator_content").fetchone()
    assert "project_id" in content_columns & job_columns
    assert (draft["project_id"], draft["body"]) == (None, "Keep this draft")


def test_creator_schedule_and_teaser_keep_origin_project_and_account(
        window, db, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from services.registry import Registry
    from services.project_artifacts import list_for_project

    database, account_id = db
    registry = Registry()
    registry.upsert_project("creator-first", "First campaign")
    registry.upsert_project("creator-second", "Second campaign")
    panel = window.creator_panel
    panel.refresh_accounts()
    panel.creator_output.setPlainText("A campaign draft")
    panel._draft_origin = ("creator-first", account_id)
    monkeypatch.setattr(
        window, "_active_project",
        lambda: registry.get_project("creator-second"))
    monkeypatch.setattr(
        panel, "_ask_schedule_datetime", lambda *a, **k: "2026-10-02T18:00")
    panel.schedule()
    with database.get_connection() as conn:
        content = conn.execute(
            "SELECT id, account_id, project_id FROM creator_content "
            "ORDER BY id DESC LIMIT 1").fetchone()
    assert (content["account_id"], content["project_id"]) == (
        account_id, "creator-first")

    with database.get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO creator_accounts (handle, account_type, created_at) "
            "VALUES ('@other', 'own', ?)", (datetime.now().isoformat(),))
        other_account_id = cursor.lastrowid
    panel.refresh_accounts()
    panel.creator_account_box.setCurrentIndex(
        panel.creator_account_box.findData(other_account_id))
    panel.schedule()  # Must refuse to put the first account's draft in @other.
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM creator_content").fetchone()[0] == 1

    panel.creator_account_box.setCurrentIndex(0)
    panel._video_context = {
        "account_id": account_id, "content_id": content["id"],
        "project_id": "creator-first", "prompt": "A safe teaser",
        "request_token": None, "job_id": "", "estimated_usd": 1.0,
    }
    panel._video_job_update(SimpleNamespace(
        job_id="job-project", status="completed", endpoint="/video",
        error="", correlation_id=""))
    clip = tmp_path / "teaser.mp4"
    clip.write_bytes(b"clip")
    panel._video_done(account_id, str(clip))
    with database.get_connection() as conn:
        job = conn.execute(
            "SELECT project_id, local_path FROM creator_video_jobs "
            "WHERE request_id='job-project'").fetchone()
        media = conn.execute(
            "SELECT account_id FROM creator_media WHERE path=?",
            (str(clip),)).fetchone()
    assert (job["project_id"], job["local_path"]) == (
        "creator-first", str(clip))
    assert media["account_id"] == account_id
    assert list_for_project("creator-first", kinds=("creator_video",))[0]["path"] == \
        str(clip)
    assert list_for_project("creator-second") == []


def test_creator_calendar_and_media_keep_all_and_project_views(
        window, db, tmp_path, monkeypatch):
    from services.project_artifacts import record
    from services.registry import Registry

    database, account_id = db
    Registry().upsert_project("creator-campaign", "Campaign")
    with database.get_connection() as conn:
        for title, project_id in (("Linked post", "creator-campaign"),
                                  ("Unfiled post", None)):
            conn.execute(
                "INSERT INTO creator_content "
                "(account_id, project_id, created_at, scheduled_for, kind, "
                "title, body, price_usd, status) "
                "VALUES (?, ?, ?, ?, 'post', ?, 'body', 0, 'draft')",
                (account_id, project_id, datetime.now().isoformat(),
                 datetime.now().isoformat(), title))
    panel = window.creator_panel
    linked = tmp_path / "linked.jpg"
    other = tmp_path / "unfiled.jpg"
    linked.write_bytes(b"linked")
    other.write_bytes(b"other")
    panel._store_media(account_id, str(linked))
    panel._store_media(account_id, str(other))
    record("creator-campaign", "creator", "creator_image", linked)
    monkeypatch.setattr(window, "_active_project", lambda: {
        "id": "creator-campaign", "name": "Campaign"})
    try:
        def calendar_items():
            from PySide6.QtCore import Qt as _Qt
            found = []
            grid = panel.creator_calendar_table
            for r in range(grid.rowCount()):
                for c in range(grid.columnCount()):
                    item = grid.item(r, c)
                    if item is not None and item.data(_Qt.UserRole) is not None:
                        found.append(item)
            undated = panel.creator_calendar_undated_table
            for r in range(undated.rowCount()):
                item = undated.item(r, 0)
                if item is not None and item.data(_Qt.UserRole) is not None:
                    found.append(item)
            return found

        panel.refresh_accounts()
        # An earlier test's schedule() legitimately jumped the view to its
        # item's week; this test's rows are dated today.
        from datetime import date, timedelta
        panel._calendar_week_start = (
            date.today() - timedelta(days=date.today().weekday()))
        panel.creator_calendar_scope.setCurrentIndex(0)
        panel.creator_media_scope.setCurrentIndex(0)
        panel.refresh_calendar()
        panel.refresh_media()
        assert len(calendar_items()) == 2
        assert panel.creator_media_table.rowCount() == 2
        panel.creator_calendar_scope.setCurrentIndex(1)
        panel.creator_media_scope.setCurrentIndex(1)
        scoped = calendar_items()
        assert len(scoped) == 1
        assert "Linked post" in scoped[0].text()
        assert panel.creator_media_table.rowCount() == 1
        assert panel.creator_media_table.item(0, 0).text() == "linked.jpg"
    finally:
        panel.creator_calendar_scope.setCurrentIndex(0)
        panel.creator_media_scope.setCurrentIndex(0)


# ── The ampersand trap ───────────────────────────────────────────────────────
def test_no_button_text_has_a_bare_ampersand():
    """Qt reads a lone '&' in button text as a mnemonic and swallows it, so
    "Publish & Market" renders as "Publish_Market". This has now happened
    twice — once on the author panel, once on "Save Voice & Character" — so it
    gets a test rather than a third fix."""
    import re
    source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
    offenders = []
    for match in re.finditer(r'QPushButton\("([^"]*)"\)', source):
        text = match.group(1)
        # A single & that is not part of an escaped && pair.
        if re.search(r'(?<!&)&(?!&)', text):
            offenders.append(text)
    assert not offenders, (
        "button labels with an unescaped '&' (use '&&'): " + repr(offenders))
