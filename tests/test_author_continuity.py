"""Continuity across long chapter sessions, and non-fiction evidence rules.

The continuity card is tests-first: the machinery existed, unpinned. A
simulated multi-chapter session asserts every successive generation
carries the established characters, world and the tail of the recent
draft — and that the tail is windowed, not the whole book.
"""

import os

import pytest


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
def author(window):
    panel = window.author_panel
    panel.author_characters_box.setPlainText(
        "MIRA — the cartographer; one glass eye; never lies.")
    panel.author_world_box.setPlainText(
        "Rule: maps drawn at night come true.")
    yield panel
    panel.author_characters_box.clear()
    panel.author_world_box.clear()
    panel.author_sources_box.clear()
    panel.author_content_type_box.setCurrentText("Fiction")


def _system_of(messages):
    return next(m["content"] for m in messages if m["role"] == "system")


def test_every_chapter_in_a_long_session_carries_the_continuity(
        window, author):
    agent = window.agent_instances["author"]
    draft = ""
    for chapter in range(1, 4):
        context = author._build_consistency_context(draft)
        messages = agent.build_messages(
            f"Write chapter {chapter}", consistency_context=context,
            content_type="Fiction")
        system = _system_of(messages)
        assert "MIRA" in system, f"chapter {chapter} lost the characters"
        assert "maps drawn at night" in system, \
            f"chapter {chapter} lost the world rules"
        if draft:
            assert f"chapter {chapter - 1} ending" in system, \
                f"chapter {chapter} lost the recent draft"
        draft += (f"\n\nCHAPTER {chapter} text… "
                  + "x" * 2500 + f" chapter {chapter} ending")


def test_recent_draft_context_is_windowed_not_the_whole_book(author):
    long_draft = "A" * 10_000 + " THE ACTUAL ENDING"
    context = author._build_consistency_context(long_draft)
    assert "THE ACTUAL ENDING" in context
    assert len(context) < 5_000          # the 3000-char tail, not the book
    assert context.index("RECENT STORY TEXT") < context.index(
        "THE ACTUAL ENDING")


def test_empty_notes_impose_no_context(author):
    author.author_characters_box.clear()
    author.author_world_box.clear()
    assert author._build_consistency_context("") == ""


# ── non-fiction evidence controls ────────────────────────────────────────────

def test_sources_tab_exists_only_in_nonfiction(author):
    tabs = author.author_tabs
    author.author_content_type_box.setCurrentText("Non-Fiction")
    assert tabs.indexOf(author.author_sources_box) >= 0
    author.author_content_type_box.setCurrentText("Fiction")
    assert tabs.indexOf(author.author_sources_box) == -1


def test_declared_sources_impose_the_evidence_rules(author):
    author.author_content_type_box.setCurrentText("Non-Fiction")
    author.author_sources_box.setPlainText(
        "Smith (2024), The Atlas Problem\nField interview, 2026-03-02")
    block = author._build_evidence_block()
    assert "[UNSOURCED]" in block
    assert "Do not invent sources" in block
    assert "Smith (2024)" in block
    # No sources, no rules — decoration is not evidence.
    author.author_sources_box.clear()
    assert author._build_evidence_block() == ""
    # Fiction never gets evidence rules.
    author.author_content_type_box.setCurrentText("Fiction")
    author.author_sources_box.setPlainText("Smith (2024)")
    assert author._build_evidence_block() == ""


def test_finished_draft_counts_unsourced_marks(window, author, monkeypatch):
    monkeypatch.setattr(window, "record_request", lambda *a, **k: None)
    author._write_token = "tok"
    author._on_finished(
        "The market doubled [UNSOURCED]. Growth continued [UNSOURCED].")
    status = author.author_status_label.text()
    assert "2 claim(s) marked [UNSOURCED]" in status
    assert "verify or cut" in status


# ── wave-two hardening: sources are project state, counts cover the draft ───

def test_sources_travel_with_the_project_state(author):
    author.author_content_type_box.setCurrentText("Non-Fiction")
    author.author_sources_box.setPlainText("Smith (2024), The Atlas Problem")
    state = author._capture_project_state()
    assert state["sources"] == "Smith (2024), The Atlas Problem"
    # Another project's empty state must not inherit the bibliography —
    # Book A's sources in Book B's prompt is fabricated authority.
    author._apply_project_state({})
    assert author.author_sources_box.toPlainText() == ""
    author._apply_project_state(state)
    assert author.author_sources_box.toPlainText() == \
        "Smith (2024), The Atlas Problem"


def test_source_edits_schedule_a_project_save(author):
    saved_id = author._project_id
    author._project_id = 4242
    try:
        author._project_save_timer.stop()
        author.author_sources_box.setPlainText("New citation")
        assert author._project_save_timer.isActive(), \
            "editing sources did not schedule a workspace save"
    finally:
        author._project_save_timer.stop()
        author._project_id = saved_id


def test_sources_survive_the_profile_round_trip(author):
    from services.database import get_setting, save_setting
    author.author_content_type_box.setCurrentText("Non-Fiction")
    author.author_sources_box.setPlainText("Field interview, 2026-03-02")
    saved_id = author._project_id
    saved_profile = get_setting("author_book_profile", "")
    author._project_id = None          # the profile path, not a project
    try:
        author.save_profile()
        author.author_sources_box.clear()
        author._load_profile()
        assert "Field interview" in author.author_sources_box.toPlainText()
    finally:
        author._project_id = saved_id
        # The shared settings row must not leak this Non-Fiction profile
        # into every later test's window.
        save_setting("author_book_profile", saved_profile)


def test_unsourced_count_covers_the_whole_draft_not_just_the_chunk(
        window, author, monkeypatch):
    monkeypatch.setattr(window, "record_request", lambda *a, **k: None)
    author.author_draft_box.setPlainText("Chapter one claim [UNSOURCED].")
    author._write_token = "tok"
    # A Continue streams its chunks into the draft box; the finish handler
    # only gets the new text — which here carries no marks of its own.
    author._is_continuing = True
    try:
        author._on_finished("A clean continuation with no new marks.")
    finally:
        author._is_continuing = False
    status = author.author_status_label.text()
    assert "1 claim(s) marked [UNSOURCED]" in status, \
        "a clean Continue hid chapter one's unverified claim"
    author.author_draft_box.clear()


def test_unsourced_count_sees_marks_routed_to_other_tabs(
        window, author, monkeypatch):
    monkeypatch.setattr(window, "record_request", lambda *a, **k: None)
    author.author_draft_box.clear()
    saved_task = author.author_task_box.currentText()
    author.author_task_box.setCurrentText("Generate Outline")
    author._write_token = "tok"
    try:
        author._on_finished("1. The market doubled [UNSOURCED]\n2. More")
    finally:
        author.author_task_box.setCurrentText(saved_task)
    assert "1 claim(s) marked [UNSOURCED]" in \
        author.author_status_label.text(), \
        "a mark routed to the Outline tab escaped the count"
    author.author_outline_box.clear()
