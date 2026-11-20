"""D2: "Make Release Kit", the kit's one confirmation (spec D2, slice-1 form).

The only modal a kit ever shows. Slice 1 offers local routes only: the Quotes
and Captions combos list local models, the Shorts voice is on-device, and the
Audiobook row is visible but "Not included". Escape cancels; nothing is
reserved or written until Start.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from services.release_kit import plan as kitplan
from services.release_kit.plan import (
    NOTICES, PLATFORMS, DEFAULT_SYSTEM_VOICE, KitPlan, Route)
from services.runtime_paths import user_data_base
from ui.forms import MD, SM, field, micro, primary, section, toggle_chip

ROW_OF = {s.key: i for i, s in enumerate(kitplan.STAGES)}


class MakeReleaseKitDialog(QDialog):
    def __init__(self, host, project_id: str, version: int, *,
                 base_dir=None, today: date | None = None):
        super().__init__(host)
        from services.project_manuscripts import get_version
        self.host = host
        self.approved = None          # (plan, plan_json, start_label) on Start
        self.setWindowTitle("Make Release Kit")
        self.setMinimumWidth(720)
        self._today = today or date.today()
        source = get_version(project_id, version)
        project = host.registry.get_project(project_id) or {"name": project_id}
        body = source["body"] if source else ""
        self.plan = KitPlan(
            project_id=project_id, project_name=project.get("name") or project_id,
            version=version, title=(source or {}).get("title", ""),
            byline=(source or {}).get("byline", ""),
            source_sha256=(source or {}).get("sha256", ""),
            words=len(body.split()), characters=len(body),
            output_dir=str(kitplan.default_output_dir(
                base_dir or user_data_base(), (source or {}).get("title", ""),
                version, self._today)),
            start_date=self._today,
            project_instructions=project.get("instructions", "") or "")
        self._build()
        self._load_local_models()
        self._refresh()

    # ── layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(MD)
        figure_box = QWidget()
        figure_layout = QVBoxLayout(figure_box)
        figure_layout.setContentsMargins(0, 0, 0, 0)
        figure_layout.setSpacing(0)
        self.figure = QLabel("Estimating…")
        self.figure.setObjectName("StatValue")
        self.figure_caption = micro("Total maximum for this kit")
        figure_layout.addWidget(self.figure)
        figure_layout.addWidget(self.figure_caption)
        layout.addWidget(figure_box)

        self.source = QLabel(
            f"From {self.plan.project_name}, approved version {self.plan.version}"
            f" · {self.plan.words:,} words · {self.plan.title} by {self.plan.byline}")
        self.source.setWordWrap(True)
        layout.addWidget(self.source)

        folder_row = QHBoxLayout()
        self.folder = QLabel(self.plan.output_dir)
        self.folder.setWordWrap(True)
        self.folder_btn = QPushButton("Change…")
        self.folder_btn.setAccessibleName("Change output folder")
        self.folder_btn.clicked.connect(self._choose_folder)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.folder_btn)
        folder_box = QWidget()
        folder_box.setLayout(folder_row)
        layout.addWidget(field("Output folder", folder_box))
        layout.addWidget(QLabel("A new folder. Nothing in it is overwritten."))

        layout.addWidget(section("Steps"))
        self.table = QTableWidget(len(kitplan.STAGES), 4)
        self.table.setHorizontalHeaderLabels(["Step", "Route", "Basis", "Maximum"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.quotes_model = QComboBox()
        self.quotes_model.setAccessibleName("Quotes model")
        self.captions_model = QComboBox()
        self.captions_model.setAccessibleName("Captions model")
        self.shorts_voice = QComboBox()
        self.shorts_voice.setAccessibleName("Shorts voice")
        self.shorts_voice.addItem(f"On-device voice (macOS) · {DEFAULT_SYSTEM_VOICE}",
                                  ("system", DEFAULT_SYSTEM_VOICE))
        self.table.setCellWidget(ROW_OF["quotes"], 1, self.quotes_model)
        self.table.setCellWidget(ROW_OF["captions"], 1, self.captions_model)
        self.table.setCellWidget(ROW_OF["shorts"], 1, self.shorts_voice)
        layout.addWidget(self.table, 1)
        self.slice_note = QLabel(
            "This version runs local steps only. Cloud models and ElevenLabs "
            "are not offered here.")
        self.slice_note.setWordWrap(True)
        layout.addWidget(self.slice_note)
        self.n2_note = QLabel(NOTICES["N2"])
        self.n2_note.setWordWrap(True)
        self.n2_note.setAccessibleName("Shorts voice notice")
        layout.addWidget(self.n2_note)

        cal_row = QHBoxLayout()
        cal_row.setSpacing(SM)
        self.start_date = QDateEdit(QDate(self._today.year, self._today.month,
                                          self._today.day))
        self.start_date.setCalendarPopup(True)
        self.start_date.setAccessibleName("Calendar start date")
        cal_row.addWidget(field("Calendar start date", self.start_date))
        self.platform_chips = {}
        for name in PLATFORMS:
            chip = toggle_chip(name, checked=True)
            chip.setAccessibleName(f"{name} in the calendar")
            self.platform_chips[name] = chip
            cal_row.addWidget(chip)
        cal_row.addStretch()
        layout.addLayout(cal_row)

        self.check_again = QPushButton("Check again")
        self.check_again.clicked.connect(self._recheck_models)
        self.check_again.setVisible(False)
        layout.addWidget(self.check_again, 0, Qt.AlignLeft)

        for note in (
                "Steps run one at a time, in this order.",
                "Imprint keeps this Mac awake until the kit finishes or pauses. "
                "The display may sleep. Keep the Mac plugged in with the lid open.",
                "If a route would change, the kit pauses and waits for you. It "
                "never switches route by itself and never asks during the night.",
                "Nothing is posted, scheduled or submitted. The calendar is a "
                "CSV file."):
            label = micro(note)
            label.setText(note)
            label.setWordWrap(True)
            layout.addWidget(label)

        self.blocking = QLabel("")
        self.blocking.setObjectName("FieldNote")
        self.blocking.setWordWrap(True)
        layout.addWidget(self.blocking)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.start_btn = primary("Start")
        self.start_btn.setDefault(True)
        self.start_btn.setAutoDefault(True)
        self.start_btn.clicked.connect(self._start)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.start_btn)
        layout.addLayout(buttons)

        for box in (self.quotes_model, self.captions_model, self.shorts_voice):
            box.currentIndexChanged.connect(self._refresh)
        self.start_date.dateChanged.connect(self._refresh)
        for chip in self.platform_chips.values():
            chip.toggled.connect(self._refresh)
        self.setTabOrder(self.folder_btn, self.quotes_model)
        self.setTabOrder(self.quotes_model, self.shorts_voice)
        self.setTabOrder(self.shorts_voice, self.captions_model)
        self.setTabOrder(self.captions_model, self.start_date)
        self.setTabOrder(self.cancel_btn, self.start_btn)

    def _load_local_models(self) -> None:
        models = list(self.host._installed_local_models())
        for box in (self.quotes_model, self.captions_model):
            box.blockSignals(True)
            box.clear()
            for provider, model in models:
                runtime = {"ollama": "Ollama", "lmstudio": "LM Studio"}.get(
                    provider, provider)
                box.addItem(f"{runtime} · {model}", (provider, model))
            box.blockSignals(False)
        self.check_again.setVisible(not models)
        self.quotes_model.setFocus()

    def _recheck_models(self) -> None:
        self._load_local_models()
        self._refresh()

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Release kit folder", self.plan.output_dir)
        if path:
            self.plan.output_dir = path
            self.folder.setText(path)
            self._refresh()

    # ── estimate ─────────────────────────────────────────────────────────────

    def _read_controls(self) -> None:
        q = self.quotes_model.currentData() or ("", "")
        c = self.captions_model.currentData() or ("", "")
        voice = self.shorts_voice.currentData() or ("system", DEFAULT_SYSTEM_VOICE)
        self.plan.quotes = Route(q[0], q[1])
        self.plan.captions = Route(c[0], c[1])
        self.plan.shorts = Route(voice[0], "", voice[1])
        self.plan.start_date = self.start_date.date().toPython()
        self.plan.platforms = [p for p in PLATFORMS
                               if self.platform_chips[p].isChecked()]

    def _blocking_reason(self, estimate) -> str:
        reason = kitplan.blocking_sentence(estimate)
        if not reason:
            problem = kitplan.output_dir_problem(self.plan.output_dir)
            reason = f"Cannot start: {problem}" if problem else ""
        return reason

    def _refresh(self, *_args) -> None:
        self._read_controls()
        self.estimate = kitplan.estimate(self.plan)
        for i, row in enumerate(self.estimate.rows):
            self.table.setItem(i, 0, QTableWidgetItem(f"{i + 1}  {row.label}"))
            if self.table.cellWidget(i, 1) is None:
                self.table.setItem(i, 1, QTableWidgetItem(row.route))
            basis = QTableWidgetItem(row.basis)
            basis.setToolTip(row.basis)
            self.table.setItem(i, 2, basis)
            self.table.setItem(i, 3, QTableWidgetItem(row.maximum))
            self.table.item(i, 0).setData(Qt.AccessibleTextRole, row.accessible)
        self.table.resizeRowsToContents()
        reason = self._blocking_reason(self.estimate)
        self.figure.setText(self.estimate.figure if reason else "No charge")
        self.figure_caption.setText(self.estimate.caption)
        self.blocking.setText(reason)
        self.start_btn.setEnabled(not reason)
        self.start_btn.setText(self.estimate.start_label)
        self.start_btn.setAccessibleDescription(
            "Starts all 8 steps. No charge: every step runs on this Mac.")
        self._shown = self.estimate.signature()

    def _start(self) -> None:
        shown = self._shown
        self._refresh()
        if self.estimate.signature() != shown:
            self.blocking.setText(
                "Caps or prices changed since this screen opened. Check the "
                "figures, then press Start again.")
            return
        if self._blocking_reason(self.estimate):
            return
        plan_json = {
            "slice": 1,
            "kit": self.plan.to_json(),
            "rows": [{"stage": r.stage, "route": r.route, "basis": r.basis,
                      "maximum": r.maximum, "notices": r.notices}
                     for r in self.estimate.rows],
            "notices": {n: NOTICES[n] for n in self.estimate.notices_shown()},
            "figure": "No charge",
        }
        self.approved = (self.plan, plan_json, self.estimate.start_label)
        self.accept()
