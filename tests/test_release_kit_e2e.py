"""Release kit end to end on the real window, offscreen (spec SM1, SM3, SM5, SM6).

Fakes: the local model (run_backend), the graphic and Short renderers and the
keep-awake holder. The EPUB is the real EbookLib export. Temp database, no
network, no real keys. The driver runs inline, so no thread is left behind.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from services import database

SENTENCES_PER_PARAGRAPH = 6


def _sentence(p: int, s: int) -> str:
    return f"Line {p}-{s} keeps the tide of the salt road in its mouth."


def _body(paragraphs: int = 160) -> str:
    return "\n\n".join(" ".join(_sentence(p, s) for s in range(SENTENCES_PER_PARAGRAPH))
                       for p in range(paragraphs))


class FakeAwake:
    def __init__(self):
        self.acquired = self.released = 0
        self.held = False

    def acquire(self):
        self.acquired += 1
        self.held = True
        return True

    def release(self):
        if self.held:
            self.released += 1
        self.held = False


class Killed(BaseException):
    """Stands in for the process dying mid-item: not an Exception, so the
    driver's error handling never sees it."""


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def kit(app, tmp_path, monkeypatch):
    import main
    from PySide6.QtWidgets import QDialog, QMessageBox
    from services.project_manuscripts import approve
    from ui.release_kit import confirm_dialog
    from ui.release_kit.confirm_dialog import MakeReleaseKitDialog

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "imprint.db")
    monkeypatch.setattr(confirm_dialog, "user_data_base", lambda: tmp_path / "out")
    database.init_db()

    dialogs = []
    for name in ("warning", "information", "question", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda *a, _n=name, **k: dialogs.append(_n) or QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: dialogs.append("QMessageBox.exec") or 0)
    monkeypatch.setattr(QDialog, "exec",
                        lambda self: dialogs.append(type(self).__name__) or 0)

    def confirm(self):
        dialogs.append("MakeReleaseKitDialog")
        self._start()
        return QDialog.Accepted if self.approved else QDialog.Rejected
    monkeypatch.setattr(MakeReleaseKitDialog, "exec", confirm)

    window = main.GodAI()
    # Flush queued launch timers, this window's and any earlier test's, so a
    # stale `_resume_provider_jobs` cannot fire in the middle of a kit.
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    window.registry.upsert_project("book-a", "Salt Road project", kind="book",
                                   work_title="The Salt Road", byline="A. Writer")
    body = _body()
    approve("book-a", body, title="The Salt Road", byline="A. Writer")
    window._refresh_history_project_filter()
    window.history_project_filter.setCurrentIndex(
        window.history_project_filter.findData("book-a"))
    window.manuscript_panel.refresh_project_versions()
    monkeypatch.setattr(window, "_installed_local_models",
                        lambda: [("ollama", "fake-local:1b")])

    calls = {"backend": [], "graphic": [], "short": [], "epub": 0}

    def open_job_token(stage):
        open_ = [ctx for ctx in window._pending_requests.values()
                 if ctx.get("job_stage") == stage]
        assert len(open_) == 1, f"{stage}: no single open job token"
        assert open_[0]["job_id"] and open_[0]["project"] == "book-a"
        return open_[0]

    def run_backend(provider, model, messages, prompt):
        assert (provider, model) == ("ollama", "fake-local:1b")
        user = messages[-1]["content"]
        if "quotable" in user:
            ctx = open_job_token("quotes")
            calls["backend"].append(("quotes", ctx["job_item"]))
            # 20 real sentences from the passages it was sent, one per
            # paragraph, then an invented line and one over 280 characters.
            seen, picks = set(), []
            for match in re.finditer(r"Line (\d+)-2 [^.]*\.", user):
                if match.group(1) not in seen and len(picks) < 20:
                    seen.add(match.group(1))
                    picks.append(match.group(0))
            picks += ["An invented line that is not in the book.", "x" * 300]
            return json.dumps(picks)
        ctx = open_job_token("captions")
        calls["backend"].append(("captions", ctx["job_item"]))
        items = json.loads(user)
        return json.dumps([f"Caption {i} for {it['platform']}"
                           for i, it in enumerate(items)])

    def graphic(quote, path, attribution):
        calls["graphic"].append(quote)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG " + quote.encode())
        return path

    def short(grant, quote, image, path, voice):
        grant.check()
        ctx = window._pending_requests[grant.token]
        assert ctx["job_stage"] == "shorts" and ctx["job_id"] == grant.job_id
        assert grant.provider == "system" and voice == "Samantha"
        assert image.is_file()
        calls["short"].append(path.name)
        if calls.get("kill_at") == len(calls["short"]):
            raise Killed()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"mp4 " + quote.encode())
        return path

    window.run_backend = run_backend
    driver = window.release_kit_driver_instance()
    driver.run_inline = True
    driver.keep_awake = FakeAwake()
    driver.render.update(graphic=graphic, short=short)
    real_epub = driver.render["epub"]

    def epub(*args):
        calls["epub"] += 1
        return real_epub(*args)
    driver.render["epub"] = epub

    yield window, driver, dialogs, calls
    # The suite's own teardown pattern (as tests/test_chat_projects.py): close
    # and deleteLater, no forced flush. Destroying a GodAI synchronously here
    # (sendPostedEvents(DeferredDelete)) left app-wide state pointing at its
    # dead widgets, and test_fiverr_orders' qWait then segfaulted every time.
    window.author_panel._project_save_timer.stop()
    window.resource_timer.stop()
    if window.release_kit_window is not None:
        window.release_kit_window.close()
    app.removeEventFilter(window)
    window.close()
    window.deleteLater()


def _artifact_paths():
    from services.project_artifacts import list_for_project
    return {Path(a["path"]) for a in list_for_project("book-a")}


def test_one_click_makes_every_output_after_exactly_one_dialog(kit):
    from services.release_kit import ledger
    from services.project_publication import list_exports
    window, driver, dialogs, calls = kit
    panel = window.manuscript_panel
    assert panel.release_kit_btn.isEnabled()
    assert panel.release_kit_btn.text() == "Make Release Kit…"

    panel.start_release_kit()

    assert dialogs == ["MakeReleaseKitDialog"]          # SM1: exactly one
    (job,) = ledger.list_jobs("book-a")
    assert job["status"] == "made", job["pause_detail"]
    out = Path(job["output_dir"])

    # EPUB matches its receipt.
    (receipt,) = list_exports("book-a")
    epub = Path(receipt["path"])
    assert epub.parent == out and epub.suffix == ".epub"
    assert ledger.file_sha256(epub) == receipt["sha256"]

    quotes = ledger.stage(job["id"], "quotes")["result"]
    assert len(quotes["quotes"]) == 20
    assert (quotes["not_found"], quotes["too_long"]) == (1, 1)
    pngs = sorted((out / "graphics").glob("*.png"))
    mp4s = sorted((out / "shorts").glob("*.mp4"))
    assert len(pngs) == len(set(quotes["quotes"])) == 20       # one per unique quote
    assert len(mp4s) == 22                                     # one per Short slot
    rows = list(csv.reader((out / "calendar.csv").open(encoding="utf-8")))
    assert rows[0][-1] == "AI used" and len(rows) == 57        # 56 posts
    assert all(r[4].startswith("Caption ") for r in rows[1:])
    assert rows[1][5].startswith(("caption: written by fake-local:1b",
                                  "voice: synthetic (macOS Samantha)"))

    # Every file is linked to the Project, plus the report and provenance.
    linked = _artifact_paths()
    for path in [epub, *pngs, *mp4s, out / "calendar.csv",
                 out / "release-kit-report.md", out / "provenance.json"]:
        assert path.resolve() in linked, path
    report_text = (out / "release-kit-report.md").read_text(encoding="utf-8")
    assert "· Made" in report_text
    assert report_text.rstrip().endswith("Nothing was posted, scheduled or submitted.")

    # Usage and Run Log rows carry the job id; local items cost nothing.
    with database.get_connection() as conn:
        usage = conn.execute("SELECT agent, job_item, cost_eur FROM usage "
                             "WHERE job_id = ? ORDER BY id", (job["id"],)).fetchall()
        runs = conn.execute("SELECT status FROM runs WHERE job_id = ?",
                            (job["id"],)).fetchall()
    assert [(r["agent"], r["job_item"], r["cost_eur"]) for r in usage] == [
        ("manuscript", "quotes:request#1", 0.0),
        ("manuscript", "captions:request#1", 0.0)]
    assert len(runs) == 2 + 22 and {r["status"] for r in runs} == {"success"}
    assert not any(ctx.get("job_id") for ctx in window._pending_requests.values())
    assert not any(t for q in window._pending_by_agent.values() for t in q
                   if window._pending_requests.get(t, {}).get("job_id"))

    # Keep-awake held for the run and released by the exit hook.
    assert (driver.keep_awake.acquired, driver.keep_awake.released) == (1, 1)
    assert calls["backend"] == [("quotes", "quotes:request#1"),
                                ("captions", "captions:request#1")]
    # The window shows the result; the Press button now offers a new kit.
    assert window.release_kit_window.isVisible()
    assert "Made" in window.release_kit_window.headline.text()
    assert panel.release_kit_btn.text() == "Make Release Kit…"


def test_killed_after_graphics_resumes_at_the_next_item_without_rerunning(kit):
    from services.release_kit import ledger
    from ui.release_kit.driver import ReleaseKitDriver
    window, driver, dialogs, calls = kit
    calls["kill_at"] = 5
    with pytest.raises(Killed):
        window.manuscript_panel.start_release_kit()
    (job,) = ledger.list_jobs("book-a")
    assert job["status"] == "running"                      # the process "died"
    assert ledger.item(job["id"], "shorts", "short:s05")["state"] == "intent"

    # Next launch: a new driver, recovery, then Resume.
    window.release_kit_driver = None
    window._recover_release_kits()
    job = ledger.get_job(job["id"])
    assert (job["status"], job["pause_reason"]) == ("paused", "interrupted")
    assert ledger.item(job["id"], "shorts", "short:s05")["state"] == "planned"
    assert window.release_kit_window.isVisible()           # D4: opened once
    assert window.manuscript_panel.release_kit_btn.text() == "Open Release Kit…"

    fresh = window.release_kit_driver_instance()
    assert isinstance(fresh, ReleaseKitDriver) and fresh is not driver
    fresh.run_inline = True
    fresh.keep_awake = FakeAwake()
    fresh.render.update(driver.render)
    calls["kill_at"] = None
    graphics_before, epub_before = len(calls["graphic"]), calls["epub"]
    window.release_kit_window.kits.setCurrentRow(0)
    window.release_kit_window.resume()

    job = ledger.get_job(job["id"])
    assert job["status"] == "made", job["pause_detail"]
    by = {s["stage"]: s["status"] for s in ledger.stages(job["id"])}
    assert by["epub"] == by["quotes"] == by["calendar"] == by["graphics"] == \
        "done_verified"
    assert calls["epub"] == epub_before == 1               # not re-run
    assert len(calls["graphic"]) == graphics_before == 20
    assert [c for c in calls["backend"] if c[0] == "quotes"] == [
        ("quotes", "quotes:request#1")]                    # no second request
    # s01–s04 made, s05 killed mid-item, then s05–s22 after Resume.
    assert calls["short"][:5] == [f"s{i:02d}.mp4" for i in range(1, 6)]
    assert calls["short"][5:] == [f"s{i:02d}.mp4" for i in range(5, 23)]
    assert len(list((Path(job["output_dir"]) / "shorts").glob("*.mp4"))) == 22
    assert dialogs == ["MakeReleaseKitDialog"]


def test_stop_pauses_after_the_current_item_and_releases_keep_awake(kit):
    from services.release_kit import ledger
    window, driver, dialogs, calls = kit
    original = driver.render["graphic"]

    def graphic_then_stop(quote, path, attribution):
        result = original(quote, path, attribution)
        if len(calls["graphic"]) == 3:
            driver.stop()
        return result
    driver.render["graphic"] = graphic_then_stop
    window.manuscript_panel.start_release_kit()
    (job,) = ledger.list_jobs("book-a")
    assert (job["status"], job["pause_reason"]) == ("paused", "user_stop")
    assert "Resume continues from Quote graphics." in job["pause_detail"]
    assert len(calls["graphic"]) == 3 and calls["short"] == []
    assert driver.keep_awake.released == 1 and not driver.keep_awake.held
    assert "Paused" in (Path(job["output_dir"]) / "release-kit-report.md").read_text()


def test_a_local_model_that_does_not_answer_pauses_without_a_dialog(kit):
    from services.release_kit import ledger
    window, driver, dialogs, calls = kit

    def down(*args):
        raise ConnectionError("connection refused")
    window.run_backend = down
    window.manuscript_panel.start_release_kit()
    (job,) = ledger.list_jobs("book-a")
    assert (job["status"], job["pause_reason"]) == ("paused", "route_unavailable")
    assert job["pause_detail"] == (
        "Paused during Quotes: Ollama did not answer (connection refused). "
        "Nothing more was sent. Start it, then resume.")
    assert dialogs == ["MakeReleaseKitDialog"]
    assert ledger.item(job["id"], "quotes", "quotes:request#1")["state"] == "failed"
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM usage WHERE job_id = ?",
                            (job["id"],)).fetchone()[0] == 0


@pytest.mark.parametrize("where", ["quotes_result", "graphic_output"])
def test_an_error_inside_a_step_pauses_the_kit_instead_of_stranding_it(
        kit, monkeypatch, where):
    """Review P1-1: an exception in a result callback (after the reply was
    billed, or a graphic that wrote no file) pauses with `item_failed`,
    releases keep-awake, closes no grant twice and frees the one-kit slot."""
    from services.release_kit import ledger
    import ui.release_kit.driver as driver_mod
    window, driver, dialogs, calls = kit
    if where == "quotes_result":
        def parse(*args, **kwargs):
            raise ValueError("bad reply shape")
        monkeypatch.setattr(driver_mod, "parse_verified_quotes", parse)
        stage, label = "quotes", "Quotes"
    else:
        def graphic(quote, path, attribution):      # "succeeds", writes nothing
            calls["graphic"].append(quote)
            return path
        driver.render["graphic"] = graphic
        stage, label = "graphics", "Quote graphics"

    window.manuscript_panel.start_release_kit()

    (job,) = ledger.list_jobs("book-a")
    assert (job["status"], job["pause_reason"]) == ("paused", "item_failed")
    assert job["pause_detail"].startswith(f"Paused during {label}: ")
    assert ledger.stage(job["id"], stage)["status"] == "paused"
    assert not driver.is_running() and ledger.running_job() is None
    assert driver.keep_awake.released == 1 and not driver.keep_awake.held
    assert not any(ctx.get("job_id") == job["id"]
                   for ctx in window._pending_requests.values())
    report = (Path(job["output_dir"]) / "release-kit-report.md").read_text()
    assert "Paused" in report
    if where == "quotes_result":
        with database.get_connection() as conn:     # billed once, not twice
            assert conn.execute("SELECT COUNT(*) FROM usage WHERE job_id = ?",
                                (job["id"],)).fetchone()[0] == 1


def test_a_paid_route_is_refused_by_the_guard_without_a_dialog(kit):
    """SM3 (slice-1 form): the job entry point issues no token for a paid
    provider, so no fake provider can be called."""
    from services.release_kit import ledger
    from services.release_kit.grant import JobRefusal
    from services.release_kit.plan import KitPlan, Route
    window, driver, dialogs, calls = kit
    plan = KitPlan("book-a", "Salt Road", 1, "T", "B", "s", 1, 1,
                   str(Path(window.release_kit_driver_instance().__class__.__module__)),
                   quotes=Route("ollama", "fake-local:1b"),
                   captions=Route("ollama", "fake-local:1b"))
    job_id = ledger.create_job(plan, plan_json={"kit": plan.to_json()},
                               start_label="Start")
    before = dict(window._pending_requests)
    refusal = window.authorize_job_item(job_id, "quotes", "quotes:request#1",
                                        provider="anthropic", model="claude-x",
                                        messages=[{"role": "user", "content": "x"}])
    assert isinstance(refusal, JobRefusal) and not refusal
    assert refusal.scope == "not_in_this_version"
    assert window._pending_requests == before
    assert dialogs == [] and calls["backend"] == []
    ledger.set_job_status(job_id, "paused", reason="user_stop")
    refusal = window.authorize_job_item(job_id, "quotes", "quotes:request#2",
                                        provider="ollama", model="m")
    assert refusal.scope == "not_active"


def test_the_job_entry_point_grants_only_the_approved_route_and_step(kit):
    """Review P2-1 and P2-2 (ADR 0005 §2): a local route on another machine,
    a model or step other than the approved one, an unknown step or item:
    each is refused and leaves no open token."""
    from services.release_kit import ledger
    from services.release_kit.grant import JobGrant
    from services.release_kit.plan import KitPlan, Route
    window, driver, dialogs, calls = kit
    plan = KitPlan("book-a", "Salt Road", 1, "T", "B", "s", 1, 1, "out",
                   quotes=Route("ollama", "fake-local:1b"),
                   captions=Route("ollama", "fake-local:1b"))
    job_id = ledger.create_job(plan, plan_json={"kit": plan.to_json()},
                               start_label="Start")
    ledger.set_stage(job_id, "quotes", status="running")
    ledger.ensure_item(job_id, "quotes", "quotes:request#1")
    before = dict(window._pending_requests)

    def ask(stage="quotes", item="quotes:request#1", provider="ollama",
            model="fake-local:1b"):
        return window.authorize_job_item(job_id, stage, item,
                                         provider=provider, model=model)

    assert ask(model="bigger-local:70b").scope == "route"
    assert ask(provider="lmstudio").scope == "route"
    assert ask(stage="captions", item="captions:request#1").scope == "not_active"
    assert ask(stage="nonsense").scope == "route"
    assert ask(item="quotes:request#9").scope == "route"
    real_url = window.ollama.base_url
    try:
        window.ollama.base_url = "http://192.168.1.20:11434"
        far = ask()
        assert far.scope == "route" and "not this Mac" in far.reason
    finally:
        window.ollama.base_url = real_url
    assert window._pending_requests == before and calls["backend"] == []

    grant = ask()                                # the approved route: granted
    assert isinstance(grant, JobGrant)
    window.close_job_item(grant, "cancelled")
    ledger.set_job_status(job_id, "paused", reason="user_stop")


def test_the_confirmation_disables_start_when_no_local_model_answers(kit, monkeypatch):
    from ui.release_kit.confirm_dialog import MakeReleaseKitDialog
    window, driver, dialogs, calls = kit
    monkeypatch.setattr(window, "_installed_local_models", lambda: [])
    dialog = MakeReleaseKitDialog(window, "book-a", 1)
    assert not dialog.start_btn.isEnabled()
    assert dialog.blocking.text().startswith("Cannot start: No local model answered")
    assert dialog.check_again.isVisibleTo(dialog)
    assert dialog.figure.text() == "Cannot start"
    monkeypatch.setattr(window, "_installed_local_models",
                        lambda: [("ollama", "fake-local:1b")])
    dialog.check_again.click()
    assert dialog.start_btn.isEnabled() and dialog.figure.text() == "No charge"
    rows = {dialog.table.item(i, 0).text(): dialog.table.item(i, 3).text()
            for i in range(dialog.table.rowCount())}
    assert rows["2  Audiobook"] == "—"
    assert rows["6  Shorts"] == "local, no charge"
    dialog.reject()
    assert dialog.approved is None


def test_press_entry_notes_follow_the_project_state(kit):
    from services.release_kit import ledger
    from services.release_kit.plan import KitPlan
    window, driver, dialogs, calls = kit
    panel = window.manuscript_panel
    window.registry.upsert_project("book-b", "Other book", kind="book")
    plan = KitPlan("book-b", "Other book", 1, "T", "B", "s", 1, 1, "/tmp/x")
    ledger.create_job(plan, plan_json={"kit": plan.to_json()}, start_label="Start")
    panel.refresh_release_kit_entry()
    assert not panel.release_kit_btn.isEnabled()
    assert panel.release_kit_note.text() == (
        "A release kit is running for Other book. One kit runs at a time.")
    assert panel.release_kit_btn.accessibleDescription() == \
        panel.release_kit_note.text()


def test_the_threaded_driver_runs_each_item_on_a_worker_and_leaves_none(kit):
    """The real path: one StageItemWorker per item, results back on the GUI
    thread through queued signals. Every worker is waited for."""
    import time
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication
    from services.release_kit import ledger
    window, driver, dialogs, calls = kit
    driver.run_inline = False
    gui_thread = QThread.currentThread()
    seen_threads = set()
    original = driver.render["graphic"]

    def graphic(quote, path, attribution):
        seen_threads.add(QThread.currentThread() is gui_thread)
        return original(quote, path, attribution)
    driver.render["graphic"] = graphic

    window.manuscript_panel.start_release_kit()
    deadline = time.monotonic() + 60
    while driver.is_running() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)
    (job,) = ledger.list_jobs("book-a")
    assert job["status"] == "made", job["pause_detail"]
    assert seen_threads == {False}             # never on the GUI thread
    assert window.release_kit_worker is None
    assert len(calls["short"]) == 22


@pytest.mark.parametrize("exit_path,expected", [
    ("made", ("made", "")),
    ("made_check", ("made_check", "")),
    ("user_stop", ("paused", "user_stop")),
    ("route_unavailable", ("paused", "route_unavailable")),
    ("item_failed", ("paused", "item_failed")),
    ("no_quotes", ("paused", "no_quotes")),
    ("quit", ("paused", "quit")),
])
def test_every_exit_from_running_releases_keep_awake_and_writes_the_report(
        kit, exit_path, expected):
    from services.release_kit import ledger
    window, driver, dialogs, calls = kit
    backend = window.run_backend

    if exit_path == "made_check":          # captions cut short → Incomplete
        def short_captions(provider, model, messages, prompt):
            reply = backend(provider, model, messages, prompt)
            return reply if "quotable" in messages[-1]["content"] else '["only one"]'
        window.run_backend = short_captions
    elif exit_path == "user_stop":
        driver.render["epub"] = (lambda f: lambda *a: (driver.stop(), f(*a))[1])(
            driver.render["epub"])
    elif exit_path == "route_unavailable":
        window.run_backend = lambda *a: (_ for _ in ()).throw(OSError("refused"))
    elif exit_path == "item_failed":
        driver.render["graphic"] = lambda *a: (_ for _ in ()).throw(
            RuntimeError("no font"))
    elif exit_path == "no_quotes":
        window.run_backend = lambda *a: '["Nothing like the book."]'
    elif exit_path == "quit":
        driver.render["graphic"] = (lambda f: lambda *a: (
            driver.stop_now("quit"), f(*a))[1])(driver.render["graphic"])

    window.manuscript_panel.start_release_kit()
    (job,) = ledger.list_jobs("book-a")
    assert (job["status"], job["pause_reason"]) == expected, job["pause_detail"]
    assert driver.keep_awake.acquired == 1
    assert driver.keep_awake.released == 1 and not driver.keep_awake.held
    assert not driver.is_running()
    report_path = Path(job["output_dir"]) / "release-kit-report.md"
    assert report_path.is_file()
    assert not any(ctx.get("job_id") for ctx in window._pending_requests.values())
    if exit_path == "made_check":
        assert "Captions and CSV: 55 of 56 posts have no caption." in \
            report_path.read_text(encoding="utf-8")


def test_quitting_while_a_kit_runs_asks_once_and_keep_running_keeps_it(
        kit, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox
    from services.release_kit import ledger
    from services.release_kit.plan import KitPlan
    window, driver, dialogs, calls = kit
    plan = KitPlan("book-a", "Salt Road", 1, "T", "B", "s", 1, 1, "")
    job_id = ledger.create_job(plan, plan_json={"kit": plan.to_json()},
                               start_label="Start")
    driver.job_id = job_id                   # as if mid-run
    driver.keep_awake.acquire()
    choice = {}

    def pick(self):
        dialogs.append(self.text())
        wanted = choice["button"]
        choice["clicked"] = next(b for b in self.buttons() if b.text() == wanted)
        return 0
    monkeypatch.setattr(QMessageBox, "exec", pick)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: choice.get("clicked"))

    choice["button"] = "Keep Running"
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert ledger.get_job(job_id)["status"] == "running"
    assert dialogs == ["A release kit is running"]

    choice["button"] = "Quit and Pause"
    window.closeEvent(QCloseEvent())
    job = ledger.get_job(job_id)
    assert (job["status"], job["pause_reason"]) == ("paused", "quit")
    assert driver.keep_awake.released == 1
