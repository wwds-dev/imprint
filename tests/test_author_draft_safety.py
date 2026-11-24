"""Quill never loses the Draft (audit QB-1, docs/specs/quill-draft-safety.md).

Every test streams a reply through the panel's real signal handlers with a
fake worker (no model call, no cost), then runs the project autosave so a
loss that would be persisted is caught, not just a loss on screen.
"""

import os

import pytest

OLD = "Chapter 1\n\nMira drew the coast at night. " + "The ink ran. " * 400


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


class Harness:
    """Fakes the host's request plumbing and records what was sent/saved."""

    def __init__(self, window, monkeypatch):
        from PySide6.QtCore import QObject, Signal

        class FakeWorker(QObject):
            finished_signal = Signal(str)
            error_signal = Signal(str)
            usage_signal = Signal(dict)
            token_signal = Signal(str)

            def __init__(self):
                super().__init__()
                self.running = False
                self.cancelled = False

            def start(self):
                self.running = True

            def isRunning(self):
                return self.running

            def cancel(self):
                self.cancelled = True

        self.FakeWorker = FakeWorker
        self.window = window
        self.panel = window.author_panel
        self.worker = None
        self.sent = []          # messages of every request started
        self.saved = []         # every autosaved workspace state
        self.authorized = []
        self.abandoned = []
        self.token = "tok"
        self.stop_reason = None

        def new_worker(provider, model, messages, prompt):
            self.worker = FakeWorker()
            self.sent.append(messages)
            return self.worker

        def authorize(*a, **k):
            self.authorized.append(k.get("messages"))
            return self.token

        def record(token, response, messages=None):
            return {"stop_reason": self.stop_reason, "backend": "openai"}

        monkeypatch.setattr(window, "_new_chat_worker", new_worker)
        monkeypatch.setattr(window, "authorize_request", authorize)
        monkeypatch.setattr(window, "record_request", record)
        monkeypatch.setattr(
            window, "abandon_request",
            lambda token, **k: self.abandoned.append((token, k)))
        monkeypatch.setattr(window, "note_request_usage", lambda *a: None)
        monkeypatch.setattr(window, "_refresh_next_step_tip", lambda: None)
        monkeypatch.setattr(self.panel.author_model_box, "currentText",
                            lambda: "m")
        import services.project_workspaces as workspaces
        monkeypatch.setattr(
            workspaces, "save",
            lambda pid, agent, state, **k: self.saved.append(dict(state)))
        monkeypatch.setattr(self.panel, "_project_id", "qb1-project")
        window.author_worker = None

    def setup(self, task, draft=OLD, direction="Write the next scene."):
        p = self.panel
        p.author_content_type_box.setCurrentText(
            "Non-Fiction" if task in {"Strengthen Argument",
                                      "Tighten Structure",
                                      "Write Chapter"} else "Fiction")
        p.author_task_box.setCurrentText(task)
        assert p.author_task_box.currentText() == task
        for box in (p.author_draft_box, p.author_outline_box,
                    p.author_characters_box, p.author_world_box):
            box.clear()
        p.author_draft_box.setPlainText(draft)
        p.author_outline_box.setPlainText("OLD OUTLINE")
        p.author_direction_input.setText(direction)

    def stream(self, *tokens):
        for t in tokens:
            self.worker.token_signal.emit(t)

    def autosave(self) -> str:
        self.panel._persist_project_state()
        return self.saved[-1]["draft"]

    @property
    def draft(self):
        return self.panel.author_draft_box.toPlainText()


@pytest.fixture()
def h(window, monkeypatch):
    harness = Harness(window, monkeypatch)
    yield harness
    p = harness.panel
    p._project_save_timer.stop()
    window.author_worker = None
    for box in (p.author_draft_box, p.author_outline_box,
                p.author_characters_box, p.author_world_box,
                p.author_sources_box):
        box.clear()
    p.author_direction_input.clear()
    p.author_content_type_box.setCurrentText("Fiction")


# ── prose Write: adds after the Draft (D1) ──────────────────────────────

def test_write_keeps_the_draft_and_adds_the_new_scene(h):
    h.setup("Write Scene")
    h.panel.write()
    assert h.draft.startswith(OLD.strip()), "Write cleared the Draft"
    assert h.autosave().startswith(OLD.strip())
    h.stream("[DRAFT]\nThe tide ", "came in.")
    assert h.autosave().startswith(OLD.strip()), "mid-stream autosave lost it"
    h.worker.finished_signal.emit("[DRAFT]\nThe tide came in.")
    assert h.draft == OLD.strip() + "\n\nThe tide came in."
    assert "[DRAFT]" not in h.draft
    assert h.autosave() == h.draft


def test_write_on_an_empty_draft_fills_it_as_before(h):
    h.setup("Write Scene", draft="")
    h.panel.write()
    h.stream("Once.")
    h.worker.finished_signal.emit("Once.")
    assert h.draft == "Once."


def test_write_error_keeps_the_old_draft(h):
    h.setup("Write Scene")
    h.panel.write()
    h.stream("The tide ")
    h.worker.error_signal.emit("HTTP 500")
    assert h.draft.startswith(OLD.strip())
    assert h.autosave().startswith(OLD.strip())
    assert h.abandoned and h.abandoned[-1][0] == "tok"
    assert h.panel.author_write_btn.isEnabled()


def test_write_stop_keeps_the_old_draft(h):
    h.setup("Write Scene")
    h.panel.write()
    h.stream("The tide ")
    h.panel.stop()
    assert h.worker.cancelled
    assert h.draft.startswith(OLD.strip())
    assert h.autosave().startswith(OLD.strip())
    # Late tokens from the cancelled worker must not land anywhere.
    before = h.draft
    h.stream("late")
    assert h.draft == before


def test_refused_write_leaves_the_draft_exactly(h):
    h.setup("Write Scene")
    h.token = None
    h.panel.write()
    assert h.draft == OLD
    assert h.autosave() == OLD
    assert h.panel.author_write_btn.isEnabled()


def test_user_typing_during_a_stream_is_kept(h):
    from PySide6.QtGui import QTextCursor
    h.setup("Write Scene", draft="Start.")
    h.panel.write()
    h.stream("New ")
    cursor = QTextCursor(h.panel.author_draft_box.document())
    cursor.insertText("Edited. ")
    h.stream("scene.")
    h.worker.finished_signal.emit("[DRAFT]\nNew scene.")
    assert h.draft == "Edited. Start.\n\nNew scene."


# ── notes tasks: never touch the Draft ──────────────────────────────────

@pytest.mark.parametrize("task,box,marker", [
    ("Generate Outline", "author_outline_box", "[OUTLINE]"),
    ("Develop Characters", "author_characters_box", "[CHARACTER]"),
    ("Build World", "author_world_box", "[WORLD]"),
])
def test_notes_tasks_land_only_in_their_tab(h, task, box, marker):
    h.setup(task)
    h.panel.write()
    h.stream(marker, "\nThe notes")
    assert h.draft == OLD, "notes streamed into the Draft"
    h.worker.finished_signal.emit(f"{marker}\nThe notes")
    assert h.draft == OLD
    assert getattr(h.panel, box).toPlainText() == "The notes"
    assert h.autosave() == OLD


@pytest.mark.parametrize("end", ["error", "stop"])
def test_notes_task_error_or_stop_changes_nothing(h, end):
    h.setup("Generate Outline")
    h.panel.write()
    h.stream("[OUTLINE]\nhalf")
    if end == "error":
        h.worker.error_signal.emit("boom")
    else:
        h.panel.stop()
    assert h.draft == OLD
    assert h.panel.author_outline_box.toPlainText() == "OLD OUTLINE"


# ── Revise: whole text or selection, never a silent cut (D2, D3) ────────

def test_revise_sends_the_whole_draft_and_replaces_it_undoably(h):
    marker_start = "Chapter 1"
    h.setup("Revise / Improve")
    h.panel.write()
    sent = "\n".join(m["content"] for m in h.sent[-1])
    assert OLD.strip() in sent, "Revise did not send the whole Draft"
    assert marker_start in sent
    revised = OLD.strip().replace("ink ran", "ink bled")
    h.stream("Revised ", "book.")
    assert h.draft == OLD, "the revision streamed over the Draft"
    h.worker.finished_signal.emit(revised)
    assert h.draft == revised + " "     # the Draft's own trailing space stays
    assert h.autosave() == revised + " "
    h.panel.author_draft_box.undo()
    assert h.draft == OLD, "Ctrl+Z does not bring the earlier Draft back"


def test_revise_works_on_the_selection_only(h):
    from PySide6.QtGui import QTextCursor
    h.setup("Revise / Improve", draft="Keep A. Fix this bit. Keep B.")
    box = h.panel.author_draft_box
    cursor = box.textCursor()
    start = box.toPlainText().index("Fix this bit.")
    cursor.setPosition(start)
    cursor.setPosition(start + len("Fix this bit."), QTextCursor.KeepAnchor)
    box.setTextCursor(cursor)
    h.panel.write()
    sent = "\n".join(m["content"] for m in h.sent[-1])
    assert "Fix this bit." in sent
    assert "Keep A." not in sent.split("TEXT TO REVISE")[-1]
    h.worker.finished_signal.emit("Fixed this bit.")
    assert h.draft == "Keep A. Fixed this bit. Keep B."


def test_revise_over_the_limit_sends_nothing_and_says_why(h):
    from agents.author.panel import REVISE_MAX_CHARS
    h.setup("Tighten Structure", draft="x" * (REVISE_MAX_CHARS + 1))
    h.panel.write()
    assert h.sent == [] and h.authorized == []
    status = h.panel.author_status_label.text()
    assert "20,000 characters" in status and "Select" in status
    assert h.draft == "x" * (REVISE_MAX_CHARS + 1)


def test_revise_at_the_limit_is_sent(h):
    from agents.author.panel import REVISE_MAX_CHARS
    assert REVISE_MAX_CHARS == 20_000
    h.setup("Strengthen Argument", draft="y" * REVISE_MAX_CHARS)
    h.panel.write()
    assert len(h.sent) == 1


def test_cut_off_revision_leaves_the_draft(h):
    h.setup("Revise / Improve")
    h.stop_reason = "length"
    h.panel.write()
    h.stream("Half a revis")
    h.worker.finished_signal.emit("Half a revis")
    assert h.draft == OLD
    assert h.autosave() == OLD
    status = h.panel.author_status_label.text()
    assert "Draft unchanged" in status


@pytest.mark.parametrize("end", ["error", "stop"])
def test_revise_error_or_stop_leaves_the_draft(h, end):
    h.setup("Revise / Improve")
    h.panel.write()
    h.stream("Half")
    if end == "error":
        h.worker.error_signal.emit("boom")
    else:
        h.panel.stop()
    assert h.draft == OLD
    assert h.autosave() == OLD


# ── Continue is unchanged: appends, refused run leaves no separator ─────

def test_continue_appends_and_a_refused_continue_changes_nothing(h):
    h.setup("Write Scene", draft="Start.")
    h.token = None
    h.panel.continue_draft()
    assert h.draft == "Start."
    h.token = "tok"
    h.panel.continue_draft()
    h.stream("More.")
    h.worker.finished_signal.emit("More.")
    assert h.draft == "Start.\n\nMore."


def test_prose_reply_with_only_notes_leaves_the_draft_as_it_was(h):
    h.setup("Write Scene")
    h.panel.write()
    h.stream("[OUTLINE]\nPlan")
    h.worker.finished_signal.emit("[OUTLINE]\nPlan")
    assert h.draft == OLD.strip()
    assert h.panel.author_outline_box.toPlainText() == "Plan"


# ── review fixes (code review of 67f35ad) ───────────────────────────────

def test_a_revision_under_half_its_source_is_not_applied(h):
    # A local model can drop the start of a long prompt without saying so.
    h.setup("Revise / Improve")
    h.panel.write()
    h.worker.finished_signal.emit("Only the last paragraph, revised.")
    assert h.draft == OLD
    assert h.autosave() == OLD
    assert "Draft unchanged" in h.panel.author_status_label.text()


def test_the_draft_is_read_only_while_a_revision_runs(h):
    h.setup("Revise / Improve", draft="Old book")
    h.panel.write()
    assert h.panel.author_draft_box.isReadOnly()
    h.worker.finished_signal.emit("New book")
    assert not h.panel.author_draft_box.isReadOnly()
    assert h.draft == "New book"


@pytest.mark.parametrize("end", ["error", "stop"])
def test_read_only_ends_with_the_run(h, end):
    h.setup("Revise / Improve", draft="Old book")
    h.panel.write()
    if end == "error":
        h.worker.error_signal.emit("boom")
    else:
        h.panel.stop()
    assert not h.panel.author_draft_box.isReadOnly()


@pytest.mark.parametrize("task", ["Revise / Improve", "Generate Outline"])
def test_a_finish_that_races_stop_is_ignored(h, task):
    h.setup(task, draft="Old book")
    h.panel.write()
    h.panel.stop()
    h.worker.finished_signal.emit("[OUTLINE]\nNew book")
    assert h.draft == "Old book"
    assert h.panel.author_outline_box.toPlainText() == "OLD OUTLINE"


def test_switching_the_task_mid_run_does_not_reroute_the_reply(h):
    h.setup("Generate Outline")
    h.panel.write()
    h.panel.author_task_box.setCurrentText("Write Scene")
    h.worker.finished_signal.emit("An unmarked outline")
    assert h.panel.author_outline_box.toPlainText() == "An unmarked outline"
    assert h.draft == OLD


def test_a_revised_selection_keeps_its_edge_line_breaks(h):
    from PySide6.QtGui import QTextCursor
    h.setup("Revise / Improve", draft="Para one.\n\nPara two.\n\nPara three.")
    box = h.panel.author_draft_box
    text = box.toPlainText()
    start = text.index("Para two.")
    cursor = box.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + len("Para two.\n\n"), QTextCursor.KeepAnchor)
    box.setTextCursor(cursor)
    h.panel.write()
    h.worker.finished_signal.emit("Paragraph 2.")
    assert h.draft == "Para one.\n\nParagraph 2.\n\nPara three."


@pytest.mark.parametrize("provider", ["ollama", "lmstudio"])
def test_local_models_revise_at_most_6000_characters(h, provider):
    from agents.author.panel import REVISE_MAX_CHARS_LOCAL
    assert REVISE_MAX_CHARS_LOCAL == 6_000
    h.setup("Revise / Improve", draft="z" * (REVISE_MAX_CHARS_LOCAL + 1))
    h.panel.author_provider_box.setCurrentText(provider)
    try:
        h.panel.write()
        assert h.sent == []
        assert "6,000 characters" in h.panel.author_status_label.text()
        h.setup("Revise / Improve", draft="z" * REVISE_MAX_CHARS_LOCAL)
        h.panel.write()
        assert len(h.sent) == 1
    finally:
        h.panel.author_provider_box.setCurrentText("anthropic")


def test_a_cloud_model_may_revise_more_than_the_local_limit(h):
    from agents.author.panel import REVISE_MAX_CHARS_LOCAL
    h.panel.author_provider_box.setCurrentText("anthropic")
    h.setup("Revise / Improve", draft="z" * (REVISE_MAX_CHARS_LOCAL + 1))
    h.panel.write()
    assert len(h.sent) == 1


def test_tighten_structure_may_cut_below_half(h):
    h.setup("Tighten Structure", draft="w " * 100)
    h.panel.write()
    h.worker.finished_signal.emit("w " * 30)          # 30% of the source
    assert h.draft.strip() == ("w " * 30).strip()


# ── section markers never decide what a Revise keeps (security P1-1) ────
# docs/audit/quill-draft-safety-security-engineer.md, 2026-11-24.

def test_a_stopped_write_leaves_no_marker_in_the_draft(h):
    h.setup("Write Scene", draft="My hand-written opening.")
    h.panel.write()
    h.stream("**[DRAFT]**\n", "The tide came in, ")
    h.panel.stop()
    assert "[DRAFT]" not in h.draft.upper()
    assert h.draft.startswith("My hand-written opening.")
    assert "The tide came in," in h.draft


def test_a_failed_write_leaves_no_marker_in_the_draft(h):
    h.setup("Write Scene", draft="My hand-written opening.")
    h.panel.write()
    h.stream("[DRAFT]\nThe tide ", "[CHARACTER]\nMira: ")
    h.worker.error_signal.emit("HTTP 500")
    assert "[DRAFT]" not in h.draft and "[CHARACTER]" not in h.draft
    assert h.draft.startswith("My hand-written opening.")
    assert "Mira:" in h.draft


def test_scenario_a_revise_keeps_text_before_a_marker(h):
    """Stop a Write, then Revise the whole Draft: a faithful reply repeats
    whatever marker survived. Only the text after it used to be kept."""
    opening = "My hand-written opening, which matters. " * 5
    scene = "The tide came in over the drawings. " * 5
    draft = opening + "\n\n**[DRAFT]**\n" + scene
    h.setup("Revise / Improve", draft=draft)
    h.panel.write()
    reply = draft.replace("matters", "counts")
    h.worker.finished_signal.emit(reply)
    assert "which counts" in h.draft, "the text before the marker was dropped"
    assert "The tide came in" in h.draft
    assert h.panel.author_outline_box.toPlainText() == "OLD OUTLINE"


def test_scenario_b_a_section_in_a_revise_reply_never_writes_a_tab(h):
    from PySide6.QtGui import QTextCursor
    passage = "x" * 1000
    h.setup("Revise / Improve", draft="Keep A. " + passage + " Keep B.")
    h.panel.author_world_box.setPlainText("MY WORLD NOTES")
    box = h.panel.author_draft_box
    cursor = box.textCursor()
    start = box.toPlainText().index(passage)
    cursor.setPosition(start)
    cursor.setPosition(start + len(passage), QTextCursor.KeepAnchor)
    box.setTextCursor(cursor)
    h.panel.write()
    reply = "[DRAFT] " + "y" * 600 + " [WORLD] " + "y" * 400
    h.worker.finished_signal.emit(reply)
    assert h.panel.author_world_box.toPlainText() == "MY WORLD NOTES"
    assert "y" * 600 in h.draft and "y" * 400 in h.draft
    assert h.draft.startswith("Keep A. ") and h.draft.endswith(" Keep B.")


def test_a_leading_draft_heading_is_not_put_into_the_manuscript(h):
    h.setup("Revise / Improve", draft="The ink ran. " * 20)
    h.panel.write()
    h.worker.finished_signal.emit("**[DRAFT]**\n" + "The ink bled. " * 20)
    assert "[DRAFT]" not in h.draft
    assert h.draft.strip() == ("The ink bled. " * 20).strip()


def test_revise_text_rules():
    from agents.author.panel import revise_text
    assert revise_text("**[DRAFT]**\nBody") == "Body"
    assert revise_text("[draft] Body on the same line") == "Body on the same line"
    assert revise_text("Intro\n[DRAFT]\nBody") == "Intro\n[DRAFT]\nBody"
    assert revise_text("Plain reply") == "Plain reply"
