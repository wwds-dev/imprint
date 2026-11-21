"""D3 and D4: the non-modal "Release Kits" window.

Shows the running kit's progress, every unfinished kit with what is done and
what is left, and the report. Closing it never stops a kit; Escape closes,
Cmd-period stops. The only dialog here is Discard's own question, which the
owner opens by pressing Discard.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

from services.release_kit import ledger, report, runner
from services.release_kit.plan import NOTICES, STAGE_BY_KEY
from ui.forms import MD, SM, micro, primary, section

STATE_WORDS = report.STAGE_WORDS
REASON_ACTION = {
    # D5: one action per pause; slice 1 has no paid step, so every pause
    # it can reach resumes with one click.
    "user_stop": "Resume", "quit": "Resume", "interrupted": "Resume",
    "route_unavailable": "Resume", "item_failed": "Resume",
    "no_quotes": "Resume", "over_line": "Resume", "cap_refused": "Resume",
}


def _when(stamp: str) -> str:
    try:
        moment = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return stamp or ""
    return f"{moment.day} {moment:%b}, {moment:%H:%M}"


def summary_line(job: dict | None) -> str:
    """The Press and Project Overview status line (D1)."""
    if job is None:
        return "Release kit: none"
    v = f"v{job['version']}"
    if job["status"] == "running":
        step, count, _key = runner.progress(ledger.stages(job["id"]))
        return f"Release kit: {v} running, step {step} of {count}"
    if job["status"] == "paused":
        return f"Release kit: {v} paused, needs you"
    if job["status"] in ("made", "made_check"):
        when = datetime.fromisoformat(job["ended_at"]) if job["ended_at"] else None
        return f"Release kit: {v} made {when.day} {when:%b}" if when else \
            f"Release kit: {v} made"
    return f"Release kit: {v} discarded"


class ReleaseKitsWindow(QWidget):
    def __init__(self, host):
        super().__init__(host, Qt.Window)
        self.host = host
        self.driver = host.release_kit_driver_instance()
        self.setWindowTitle("Release Kits")
        self.resize(820, 560)
        self.project_id = None
        self.note_text = ""
        self._build()
        self.driver.changed.connect(self._on_changed)
        self.driver.progress.connect(self._on_progress)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)
        QShortcut(QKeySequence("Ctrl+."), self, activated=self.stop)

    def _build(self) -> None:
        outer = QHBoxLayout(self)
        outer.setSpacing(MD)
        self.kits = QListWidget()
        self.kits.setAccessibleName("Release kits")
        self.kits.setMinimumWidth(240)
        self.kits.currentItemChanged.connect(lambda *_: self._show_selected())
        outer.addWidget(self.kits)
        right = QVBoxLayout()
        right.setSpacing(SM)
        self.headline = section("")
        self.caption = micro("")
        self.step_progress = QLabel("")
        self.step_progress.setAccessibleName("Release kit progress")
        right.addWidget(self.headline)
        right.addWidget(self.caption)
        right.addWidget(self.step_progress)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Step", "State", "Spent", "Line"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right.addWidget(self.table, 1)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        right.addWidget(self.detail)
        self.note = QLabel("")
        self.note.setObjectName("FieldNote")
        self.note.setWordWrap(True)
        right.addWidget(self.note)
        buttons = QHBoxLayout()
        self.stop_btn = primary("Stop")
        self.stop_btn.clicked.connect(self.stop)
        self.resume_btn = primary("Resume")
        self.resume_btn.clicked.connect(self.resume)
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.clicked.connect(self.discard)
        self.folder_btn = QPushButton("Show Folder")
        self.folder_btn.clicked.connect(self.show_folder)
        self.report_btn = QPushButton("Show Report")
        self.report_btn.clicked.connect(self.show_report)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        for button in (self.stop_btn, self.resume_btn, self.discard_btn,
                       self.folder_btn, self.report_btn):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        right.addLayout(buttons)
        outer.addLayout(right, 1)

    # ── data ─────────────────────────────────────────────────────────────────

    def _name(self, project_id) -> str:
        project = self.host.registry.get_project(project_id or "") or {}
        return project.get("name") or project_id or "a deleted Project"

    def show_kits(self, project_id=None, job_id=None) -> None:
        self.project_id = project_id
        self._reload(select=job_id)
        self.show()
        self.raise_()
        self.activateWindow()

    def selected_id(self) -> str | None:
        item = self.kits.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _reload(self, select=None) -> None:
        select = select or self.selected_id()
        jobs = ledger.list_jobs(self.project_id)
        self.kits.blockSignals(True)
        self.kits.clear()
        for job in jobs:
            stage_rows = ledger.stages(job["id"])
            where = ""
            if job["status"] == "paused":
                key = next((s["stage"] for s in stage_rows
                            if s["status"] not in runner.TERMINAL_STAGE), "")
                where = f" · paused at {STAGE_BY_KEY[key].label}" if key else " · paused"
            item = QListWidgetItem(
                f"{self._name(job['project_id'])} v{job['version']} · started "
                f"{_when(job['started_at'] or job['created_at'])}"
                f"{where or ' · ' + report.STATE_WORDS.get(job['status'], job['status'])}")
            item.setData(Qt.UserRole, job["id"])
            self.kits.addItem(item)
            if job["id"] == select:
                self.kits.setCurrentItem(item)
        if self.kits.currentItem() is None and self.kits.count():
            self.kits.setCurrentRow(0)
        self.kits.blockSignals(False)
        self._show_selected()

    def _show_selected(self) -> None:
        job_id = self.selected_id()
        job = ledger.get_job(job_id) if job_id else None
        if job is None:
            self.headline.setText("No release kits yet")
            self.caption.setText("")
            self.table.setRowCount(0)
            self.detail.setText("")
            for button in (self.stop_btn, self.resume_btn, self.discard_btn,
                           self.folder_btn, self.report_btn):
                button.setVisible(False)
            return
        stage_rows = ledger.stages(job_id)
        running = job["status"] == "running" and self.driver.job_id == job_id
        step, count, key = runner.progress(stage_rows)
        label = STAGE_BY_KEY[key].label if key else ""
        if job["status"] == "running":
            self.headline.setText(f"Step {step} of {count}: {label}")
        else:
            self.headline.setText(report.STATE_WORDS.get(job["status"], job["status"]))
        self.caption.setText(f"{self._name(job['project_id'])} v{job['version']} · started "
                             f"{_when(job['started_at'] or job['created_at'])}")
        if not running:
            self.step_progress.setText("")
        self.table.setRowCount(len(stage_rows))
        for i, st in enumerate(stage_rows):
            line = ("—" if st["route_kind"] == "not_included"
                    else "local, no charge")
            spent = ("—" if st["route_kind"] == "not_included"
                     else "local, no charge")
            cells = (STAGE_BY_KEY[st["stage"]].label,
                     STATE_WORDS.get(st["status"], st["status"]), spent, line)
            for c, text in enumerate(cells):
                self.table.setItem(i, c, QTableWidgetItem(text))
        done = [STAGE_BY_KEY[s["stage"]].label for s in stage_rows
                if s["status"] in ("done", "done_verified")]
        left = [STAGE_BY_KEY[s["stage"]].label for s in stage_rows
                if s["status"] not in runner.TERMINAL_STAGE]
        lines = []
        if job["status"] in ledger.UNFINISHED:
            lines.append("Done: " + (", ".join(done) or "nothing yet") + ".")
            lines.append("Left: " + (", ".join(left) or "nothing") + ".")
            lines.append("Left to spend: nothing, every remaining step is local.")
        if job["status"] == "paused" and job["pause_detail"]:
            lines.append(job["pause_detail"])
        if running:
            lines.append("Closing this window does not stop the kit.")
            lines.append("This Mac stays awake while the kit runs. The display "
                         "may sleep.")
        elif job["status"] in ("paused", "made", "made_check"):
            lines.append("This Mac may sleep again.")
        if job["status"] in ("made", "made_check"):
            lines.append(NOTICES["N5"])
        self.detail.setText("\n".join(lines))
        self.note.setText(self.note_text)
        self.stop_btn.setVisible(running)
        self.resume_btn.setVisible(job["status"] == "paused")
        self.resume_btn.setText(REASON_ACTION.get(job["pause_reason"], "Resume"))
        self.discard_btn.setVisible(job["status"] == "paused")
        self.folder_btn.setVisible(True)
        self.report_btn.setVisible(
            (Path(job["output_dir"]) / report.REPORT_NAME).is_file())
        focus = self.stop_btn if running else self.resume_btn \
            if job["status"] == "paused" else self.close_btn
        focus.setFocus()

    def _on_changed(self, job_id: str) -> None:
        if self.isVisible():
            self._reload(select=job_id)

    def _on_progress(self, job_id: str, text: str) -> None:
        if job_id == self.selected_id():
            self.step_progress.setText(text)

    # ── actions ──────────────────────────────────────────────────────────────

    def stop(self) -> None:
        if self.driver.is_running() and self.driver.job_id == self.selected_id():
            self.driver.stop()
            self.step_progress.setText("Stopping after the current item…")

    def resume(self) -> None:
        job_id = self.selected_id()
        if not job_id:
            return
        self.note_text = "Checking finished files…"
        self.note.setText(self.note_text)
        running = ledger.running_job()
        if self.driver.is_running() or (running and running["id"] != job_id):
            other = running or {}
            self.note_text = (
                f"Cannot resume yet: a release kit is running for "
                f"{self._name(other.get('project_id'))}. One kit runs "
                "at a time.")
            self.note.setText(self.note_text)
            return
        try:
            reopened = self.driver.resume(job_id)
        except ledger.KitBusy as exc:
            self.note_text = f"Cannot resume yet: {exc} One kit runs at a time."
            self.note.setText(self.note_text)
            return
        notes = [f"{STAGE_BY_KEY[key].label} will run again: {len(keys)} of its "
                 "files are missing or changed." for key, keys in reopened.items()
                 if key != "link"]
        self.note_text = " ".join(notes)
        self._reload(select=job_id)

    def discard(self) -> None:
        job_id = self.selected_id()
        job = ledger.get_job(job_id) if job_id else None
        if not job or job["status"] != "paused":
            return
        box = QMessageBox(self)
        box.setWindowTitle("Discard this release kit?")
        box.setText("Discard this release kit?")
        box.setInformativeText(f"Nothing more will run for it. Files already made stay in "
                    f"{job['output_dir']} and stay linked to "
                    f"{self._name(job['project_id'])}. Spending already recorded stays "
                    "recorded.")
        discard = box.addButton("Discard", QMessageBox.DestructiveRole)
        cancel = box.addButton("Cancel", QMessageBox.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() is discard:
            self.driver.discard(job_id)
            self._reload(select=job_id)

    def show_folder(self) -> None:
        job = ledger.get_job(self.selected_id() or "")
        if job:
            QDesktopServices.openUrl(QUrl.fromLocalFile(job["output_dir"]))

    def show_report(self) -> None:
        job = ledger.get_job(self.selected_id() or "")
        if job:
            QDesktopServices.openUrl(QUrl.fromLocalFile(
                str(Path(job["output_dir"]) / report.REPORT_NAME)))
