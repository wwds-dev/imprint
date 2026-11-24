"""
Imprint — consent record before someone else's reference photos are sent
=========================================================================
Type: unit + window-level, offline. No worker starts; nothing is sent.

Spec `docs/specs/reference-photo-consent.md` (D2, owner's option A′,
2026-11-24): beside an account's reference photos the user says whose they
are: "Me", "A made-up character" or "Someone else". A teaser that would send
the photos of someone else with no name or date of their agreement is
refused before any key, permission, estimate or budget step: no request is
authorised, no job row is written, no worker starts. "Me" and "A made-up
character" send as before. The record says what the user states; it verifies
nothing about the photos.

Run with:  pytest tests/test_reference_photo_consent.py -v
"""

import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

HANDLE = "reference-photo-consent-test"


# ── the rule ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("holder,date_,missing", [
    ("", "", ["their name", "the date they agreed"]),
    ("", "2026-11-20", ["their name"]),
    ("Sam Example", "", ["the date they agreed"]),
    ("   ", "2026-11-20", ["their name"]),
])
def test_someone_elses_photos_need_a_name_and_a_date(holder, date_, missing):
    from agents.creator.profile import photo_consent_refusal
    reason = photo_consent_refusal(
        {"account_type": "managed", "consent_holder": holder,
         "consent_date": date_}, ["/photos/a.png"])
    assert reason.startswith("Not sent: consent record missing")
    for label in missing:
        assert label in reason
    for label in {"their name", "the date they agreed"} - set(missing):
        assert label not in reason


def test_a_complete_record_sends():
    from agents.creator.profile import photo_consent_refusal
    assert photo_consent_refusal(
        {"account_type": "managed", "consent_holder": "Sam Example",
         "consent_date": "2026-11-20"}, ["/photos/a.png"]) == ""


@pytest.mark.parametrize("subject", ["own", "persona", "", None])
def test_me_and_a_made_up_character_need_no_record(subject):
    from agents.creator.profile import photo_consent_refusal
    assert photo_consent_refusal(
        {"account_type": subject, "consent_holder": "", "consent_date": ""},
        ["/photos/a.png"]) == ""
    assert photo_consent_refusal({}, ["/photos/a.png"]) == ""


def test_an_unknown_subject_is_treated_as_someone_else():
    """A value no build writes (a hand edit, a typo) fails closed."""
    from agents.creator.profile import photo_consent_refusal
    assert photo_consent_refusal(
        {"account_type": "agency", "consent_holder": "", "consent_date": ""},
        ["/photos/a.png"])


def test_no_photos_means_nothing_to_refuse():
    from agents.creator.profile import photo_consent_refusal
    assert photo_consent_refusal(
        {"account_type": "managed", "consent_holder": "",
         "consent_date": ""}, []) == ""


# ── in the window ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
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
        yield main.GodAI()
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


@pytest.fixture
def account():
    """A real account row (the job table's account_id is a foreign key),
    removed afterwards with everything filed under it."""
    from services.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM creator_accounts WHERE handle = ?", (HANDLE,))
        cursor = conn.execute(
            "INSERT INTO creator_accounts (handle, created_at) VALUES (?, ?)",
            (HANDLE, datetime.now().isoformat(timespec="seconds")))
        conn.commit()
        account_id = cursor.lastrowid
    yield account_id
    with get_connection() as conn:
        for table in ("creator_video_jobs", "creator_persona", "creator_voice"):
            conn.execute(f"DELETE FROM {table} WHERE account_id = ?",
                         (account_id,))
        conn.execute("DELETE FROM creator_accounts WHERE id = ?", (account_id,))
        conn.commit()


def _set_record(account_id, subject, holder="", date_=""):
    from services.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "UPDATE creator_accounts SET account_type = ?, consent_holder = ?, "
            "consent_date = ? WHERE id = ?", (subject, holder, date_, account_id))
        conn.commit()


def _job_rows(account_id) -> int:
    from services.database import get_connection
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM creator_video_jobs WHERE account_id = ?",
            (account_id,)).fetchone()[0]


@pytest.fixture
def armed(window, account, monkeypatch, tmp_path):
    """Every route able to run: keys, permissions, budget, one photo. Records
    each dialog, each authorisation and each worker start instead of sending."""
    import agents.creator.panel as creator_panel
    from PySide6.QtWidgets import QMessageBox
    photo = tmp_path / "them.png"
    photo.write_bytes(b"\x89PNG them")
    for name in ("GEMINI_API_KEY", "DASHSCOPE_API_KEY", "HF_API_KEY_ID",
                 "HF_API_KEY_SECRET"):
        monkeypatch.setenv(name, "test-not-a-real-key")
    window.allow_gemini_checkbox.setChecked(True)
    window.allow_qwen_checkbox.setChecked(True)
    window.allow_higgsfield_checkbox.setChecked(True)
    monkeypatch.setattr(window, "session_budget_eur", 1000.0)
    monkeypatch.setattr(window, "daily_budget_eur", 1000.0)
    monkeypatch.setattr(creator_panel, "reference_images",
                        lambda account_id: [str(photo)])
    seen = {"dialogs": [], "authorised": [], "started": []}
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda _parent, title, text, *a, **k: seen["dialogs"].append((title, text))))
    real = window.authorize_request
    monkeypatch.setattr(window, "authorize_request", lambda *a, **k: (
        seen["authorised"].append(a[:3]), real(*a, **k))[1])
    monkeypatch.setattr("ui.workers.VideoGenerationWorker.start",
                        lambda worker: seen["started"].append(worker))
    monkeypatch.setattr("ui.workers.HiggsfieldEstimateWorker.start",
                        lambda worker: seen["started"].append(worker))
    panel = window.creator_panel
    monkeypatch.setattr(panel, "current_account", lambda: _account(account))
    try:
        yield panel, account, seen
    finally:
        window.allow_gemini_checkbox.setChecked(False)
        window.allow_qwen_checkbox.setChecked(False)
        window.allow_higgsfield_checkbox.setChecked(False)
        for token in list(window._pending_requests):
            window.abandon_request(token)
        panel._video_context = {}
        panel._switch_teaser_route("higgsfield")
        panel.creator_video_btn.setEnabled(True)


def _account(account_id) -> dict:
    from services.database import get_connection
    with get_connection() as conn:
        return dict(conn.execute("SELECT * FROM creator_accounts WHERE id = ?",
                                 (account_id,)).fetchone())


@pytest.mark.parametrize("route", ["higgsfield", "gemini", "qwen"])
def test_someone_elses_photos_without_a_record_are_not_sent(armed, route):
    panel, account, seen = armed
    _set_record(account, "managed", holder="", date_="2026-11-20")
    panel._switch_teaser_route(route)
    panel.generate_video()
    assert seen["dialogs"] and seen["dialogs"][-1][0] == "Consent record missing"
    assert "their name" in seen["dialogs"][-1][1]
    assert seen["authorised"] == []
    assert seen["started"] == []
    assert _job_rows(account) == 0
    assert panel.creator_video_status.text() == "Not sent: consent record missing."


@pytest.mark.parametrize("route", ["gemini", "qwen"])
def test_the_direct_route_checks_the_record_itself(armed, route):
    """The direct route is also entered after an applied assessment; the
    check does not rely on generate_video having run first."""
    panel, account, seen = armed
    _set_record(account, "managed")
    panel._switch_teaser_route(route)
    panel._generate_direct_teaser(_account(account), "a teaser")
    assert seen["authorised"] == [] and seen["started"] == []
    assert _job_rows(account) == 0


@pytest.mark.parametrize("subject,holder,date_", [
    ("own", "", ""),
    ("persona", "", ""),
    ("managed", "Sam Example", "2026-11-20"),
])
def test_a_teaser_with_a_record_or_no_need_for_one_goes_ahead(
        armed, subject, holder, date_):
    panel, account, seen = armed
    _set_record(account, subject, holder, date_)
    panel._switch_teaser_route("gemini")
    panel.generate_video()
    assert not [d for d in seen["dialogs"] if d[0] == "Consent record missing"]
    assert seen["authorised"][-1] == ("creator", "gemini", "gemini-omni-1.1-flash")
    assert len(seen["started"]) == 1
    assert len(seen["started"][0].reference_images) == 1  # sent as before
    assert _job_rows(account) == 1


def test_the_higgsfield_estimate_waits_for_the_record(armed):
    """Higgsfield uploads the photo while preparing its estimate, so the
    check must come before the estimate worker, not only before payment."""
    panel, account, seen = armed
    _set_record(account, "managed", "Sam Example", "2026-11-20")
    panel._switch_teaser_route("higgsfield")
    panel.generate_video()
    assert len(seen["started"]) == 1
    assert type(seen["started"][0]).__name__ == "HiggsfieldEstimateWorker"


# ── the form ────────────────────────────────────────────────────────────────

def _select(panel, account_id):
    panel.refresh_accounts()
    index = panel.creator_account_box.findData(account_id)
    assert index >= 0
    panel.creator_account_box.setCurrentIndex(index)
    panel._account_changed(index)


def test_the_form_saves_and_reloads_photos_subject_and_record(
        window, account, tmp_path):
    from agents.creator.profile import reference_images
    panel = window.creator_panel
    _select(panel, account)
    photos = [str(tmp_path / "a.png"), str(tmp_path / "b.jpg")]
    panel.creator_reference_photos.setPlainText("\n".join(photos))
    panel.creator_photo_subject.setCurrentIndex(
        panel.creator_photo_subject.findData("managed"))
    assert not panel.creator_consent_fields.isHidden()
    panel.creator_consent_holder.setText("Sam Example")
    panel.creator_consent_date.setText("2026-11-20")
    panel.creator_consent_note.setText("Signed release, email of 20 Nov")
    panel.save_voice()

    stored = _account(account)
    assert (stored["account_type"], stored["consent_holder"],
            stored["consent_date"], stored["consent_note"]) == (
        "managed", "Sam Example", "2026-11-20",
        "Signed release, email of 20 Nov")
    assert reference_images(account) == photos

    panel.creator_reference_photos.clear()
    panel.creator_consent_holder.clear()
    _select(panel, account)
    assert panel.creator_reference_photos.toPlainText().splitlines() == photos
    assert panel.creator_photo_subject.currentData() == "managed"
    assert panel.creator_consent_holder.text() == "Sam Example"
    assert panel.creator_consent_date.text() == "2026-11-20"


def test_the_record_fields_show_only_for_someone_else(window, account):
    panel = window.creator_panel
    _select(panel, account)
    box = panel.creator_photo_subject
    for subject, shown in (("own", False), ("persona", False), ("managed", True)):
        box.setCurrentIndex(box.findData(subject))
        assert panel.creator_consent_fields.isHidden() is (not shown)
    box.setCurrentIndex(box.findData("persona"))
    assert not panel.creator_persona_group.isHidden()
    box.setCurrentIndex(box.findData("own"))
    assert panel.creator_persona_group.isHidden()


def test_a_date_that_is_not_a_date_is_not_saved(window, account, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    panel = window.creator_panel
    _select(panel, account)
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda _p, title, text, *a, **k: warned.append(title)))
    box = panel.creator_photo_subject
    box.setCurrentIndex(box.findData("managed"))
    panel.creator_consent_holder.setText("Sam Example")
    panel.creator_consent_date.setText("last Tuesday")
    panel.save_voice()
    assert warned
    assert _account(account)["consent_date"] == ""
    assert _account(account)["account_type"] == "own"


def test_saving_the_voice_keeps_the_persona_bible_of_a_character(
        window, account):
    from agents.creator.profile import load_persona
    panel = window.creator_panel
    _select(panel, account)
    box = panel.creator_photo_subject
    box.setCurrentIndex(box.findData("persona"))
    panel.creator_persona_appearance.setText("silver hair, green coat")
    panel.save_voice()
    assert load_persona(account)["appearance"] == "silver hair, green coat"
    box.setCurrentIndex(box.findData("own"))
    panel.save_voice()
    # Hidden is not deleted: switching back shows the same character.
    assert load_persona(account)["appearance"] == "silver hair, green coat"
