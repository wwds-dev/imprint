"""Muse workspace and its guarded drafting/teaser lifecycles.

Phase 4 extraction: the profile form, compose controls and the four tabs
(Draft, Calendar, Voice, Media) and every
handler moved here from main.py. The host supplies shared budget
authorization, usage records, the chat-worker factory, `_note_failure`
and the Higgsfield permission checkbox; the workers stay host attributes
so the umbrella's shutdown sweep keeps seeing them.

Request tokens live on this panel: "creator" is shared by the text
drafting flow and the Higgsfield teaser (whose token rides in its own
job context), so nothing here resolves a request by agent name.
"""

import types
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
    QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSizePolicy, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from agents.creator import PROMO_CHANNELS
from agents.creator import calendar as content_calendar
from agents.creator.profile import (
    load_persona, load_voice, reference_images, save_persona, save_voice,
)
from services.database import get_connection
from services.higgsfield_client import (
    ContentPolicyError, HiggsfieldClient, check_prompt,
)
from services.runtime_paths import user_data_base

# Teaser routes. Each takes the persona's reference images: Higgsfield
# Seedance as image-to-video, Gemini Omni and Wan 3.0 as reference-to-video.
# Every teaser is assessed across the routes that can run before approval.
TEASER_ROUTES = {
    "higgsfield": {"label": "Higgsfield · Seedance 2.5", "provider": "Higgsfield",
                   "model": "seedance-2.5"},
    "gemini": {"label": "Gemini · Omni 1.1 Flash", "provider": "Gemini",
               "model": "gemini-omni-1.1-flash"},
    "qwen": {"label": "Qwen · Wan 3.0", "provider": "Qwen",
             "model": "wan3.0-video"},
}
TEASER_SECONDS = 5          # the length Higgsfield's teaser has always been
TEASER_ASPECT = "9:16"      # vertical: teasers go to social feeds
TEASER_ROUTE_KEY = "creator_teaser_route"
from ui.forms import LG, MD, SM, combo, field, line_edit, primary, quiet, section
from ui.panels.base import AgentPanel
from ui.widgets import scrollable


class CreatorPanel(QWidget):
    """Content profiles, drafting, the plan calendar and the media around them."""

    HOST_CONTROLS = (
        "creator_account_box", "creator_handle_input", "creator_platform_box",
        "creator_save_account_btn", "creator_delete_account_btn",
        "creator_kind_box", "creator_channel_box",
        "creator_campaign_input", "creator_channel_field",
        "creator_campaign_field", "creator_compose_grid", "creator_kind_field",
        "creator_brief_input", "creator_panel_base", "creator_provider_box",
        "creator_model_box", "creator_generate_btn", "creator_schedule_btn",
        "creator_video_btn", "creator_video_cancel_btn", "creator_stop_btn",
        "creator_status_label", "creator_video_status", "creator_tabs",
        "creator_output", "creator_calendar_scope", "creator_calendar_table",
        "creator_calendar_prev_btn", "creator_calendar_today_btn",
        "creator_calendar_next_btn", "creator_calendar_week_label",
        "creator_calendar_undated_table", "creator_calendar_reschedule_btn",
        "creator_calendar_export_btn", "creator_voice_tab",
        "creator_media_scope", "creator_media_table", "creator_add_media_btn",
        "creator_voice_samples", "creator_voice_tone", "creator_voice_emoji",
        "creator_voice_length", "creator_voice_banned",
        "creator_persona_group", "creator_persona_appearance",
        "creator_persona_backstory", "creator_persona_personality",
        "creator_persona_boundaries", "creator_persona_seed",
    )

    def __init__(self, host):
        super().__init__()
        self.host = host
        self._draft_token = None
        self._draft_origin = None  # (project_id, account_id) captured at approval
        self._last_generation_cost_eur = 0.0
        self._calendar_week_start: date = (
            date.today() - timedelta(days=date.today().weekday()))
        self._video_context: dict = {}
        self.setObjectName("CreatorPanel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        content.setObjectName("Transparent")
        outer.addWidget(scrollable(content))
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LG)

        # ── Account ─────────────────────────────────────────────────────
        layout.addWidget(section("Content profile"))

        self.creator_account_box = QComboBox()
        self.creator_account_box.currentIndexChanged.connect(self._account_changed)
        self.creator_handle_input = line_edit("@handle")
        self.creator_platform_box = combo([
            "General", "Writing / Publishing", "Music",
            "AltMerch", "Instagram", "TikTok", "X / Twitter", "Reddit",
            "YouTube", "Other",
        ], "General")
        account = QGridLayout()
        account.setHorizontalSpacing(MD)
        account.setVerticalSpacing(MD)
        account.addWidget(field("Profile", self.creator_account_box), 0, 0, Qt.AlignTop)
        account.addWidget(field("Handle / project", self.creator_handle_input), 0, 1, Qt.AlignTop)
        account.addWidget(field("Platform / venture", self.creator_platform_box), 0, 2, Qt.AlignTop)
        for column in range(3):
            account.setColumnStretch(column, 1)
        layout.addLayout(account)

        account_actions = QHBoxLayout()
        account_actions.setSpacing(SM)
        self.creator_save_account_btn = QPushButton("Save Profile")
        self.creator_save_account_btn.clicked.connect(self.save_account)
        account_actions.addWidget(self.creator_save_account_btn)
        self.creator_delete_account_btn = quiet("Remove profile")
        self.creator_delete_account_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.creator_delete_account_btn.clicked.connect(self.delete_account)
        account_actions.addWidget(self.creator_delete_account_btn)
        account_actions.addStretch()
        layout.addLayout(account_actions)

        # ── Compose ─────────────────────────────────────────────────────
        layout.addWidget(section("Compose"))

        self.creator_kind_box = combo(
            ["post", "caption", "campaign", "posting_plan", "promo_assets",
             "hooks", "bio", "promo"])
        self.creator_kind_box.currentTextChanged.connect(self._kind_changed)
        self.creator_channel_box = combo(list(PROMO_CHANNELS))
        for _extra_channel in ("Website", "Email", "Other"):
            self.creator_channel_box.addItem(_extra_channel)
        self.creator_campaign_input = line_edit("Campaign or test name")

        self.creator_channel_field = field("Channel", self.creator_channel_box)
        self.creator_campaign_field = field("Campaign", self.creator_campaign_input)

        # The grid is re-packed when the kind changes rather than hiding a
        # cell in place: hiding one leaves a hole in the row — the same
        # "nothing lines up" complaint, produced by an empty cell instead of
        # a misplaced one.
        self.creator_compose_grid = QGridLayout()
        self.creator_compose_grid.setHorizontalSpacing(MD)
        self.creator_compose_grid.setVerticalSpacing(MD)
        self.creator_kind_field = field("Kind", self.creator_kind_box)
        for column in range(3):
            self.creator_compose_grid.setColumnStretch(column, 1)
        layout.addLayout(self.creator_compose_grid)

        self.creator_brief_input = QTextEdit()
        self.creator_brief_input.setPlaceholderText(
            "What is this about? The more concrete, the less generic the draft.")
        self.creator_brief_input.setFixedHeight(70)
        layout.addWidget(field("Brief", self.creator_brief_input))

        self.creator_panel_base = AgentPanel(
            host, "creator",
            providers=("anthropic", "openai", "deepseek", "kimi", "gemini", "qwen"),
            default_provider="anthropic")
        self.creator_provider_box = self.creator_panel_base.provider_box
        self.creator_model_box = self.creator_panel_base.model_box

        models = QGridLayout()
        models.setHorizontalSpacing(MD)
        models.setVerticalSpacing(MD)
        models.addWidget(field("Provider", self.creator_provider_box), 0, 0, Qt.AlignTop)
        models.addWidget(field("Model", self.creator_model_box), 0, 1, Qt.AlignTop)
        for column in range(3):
            models.setColumnStretch(column, 1)
        layout.addLayout(models)

        actions = QHBoxLayout()
        actions.setSpacing(SM)
        self.creator_generate_btn = primary("Draft")
        self.creator_generate_btn.setMinimumWidth(160)
        self.creator_generate_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.creator_generate_btn.clicked.connect(self.generate)
        actions.addWidget(self.creator_generate_btn)

        self.creator_schedule_btn = QPushButton("Add to Calendar")
        self.creator_schedule_btn.clicked.connect(self.schedule)
        actions.addWidget(self.creator_schedule_btn)

        self.creator_video_route_box = QComboBox()
        self.creator_video_route_box.setObjectName("CompactCombo")
        for key, route in TEASER_ROUTES.items():
            self.creator_video_route_box.addItem(route["label"], key)
        self.creator_video_route_box.setToolTip(
            "Who renders the teaser from the persona's reference images. Each "
            "teaser is assessed across the routes you have a key for and "
            "have permitted before it is approved.")
        from services.database import get_setting
        saved = get_setting(TEASER_ROUTE_KEY, "higgsfield")
        index = self.creator_video_route_box.findData(saved)
        if index >= 0:
            self.creator_video_route_box.setCurrentIndex(index)
        self.creator_video_route_box.currentIndexChanged.connect(
            self._teaser_route_changed)
        actions.addWidget(self.creator_video_route_box)

        self.creator_video_btn = QPushButton("Generate Teaser")
        self.creator_video_btn.setToolTip(
            "Render a promo teaser. Paid, and subject to the provider's "
            "content rules.")
        self.creator_video_btn.clicked.connect(self.generate_video)
        actions.addWidget(self.creator_video_btn)

        self.creator_video_cancel_btn = QPushButton("Cancel Teaser")
        self.creator_video_cancel_btn.setObjectName("DangerAction")
        self.creator_video_cancel_btn.clicked.connect(self.cancel_video)
        self.creator_video_cancel_btn.hide()
        actions.addWidget(self.creator_video_cancel_btn)

        self.creator_stop_btn = QPushButton("Stop")
        self.creator_stop_btn.setObjectName("DangerAction")
        self.creator_stop_btn.clicked.connect(self.stop)
        self.creator_stop_btn.hide()
        actions.addWidget(self.creator_stop_btn)

        actions.addStretch()
        self.creator_status_label = QLabel("")
        self.creator_status_label.setObjectName("EstimateLine")
        actions.addWidget(self.creator_status_label)
        layout.addLayout(actions)

        self.creator_video_status = QLabel("")
        self.creator_video_status.setObjectName("EstimateLine")
        self.creator_video_status.setWordWrap(True)
        layout.addWidget(self.creator_video_status)

        # ── Tabs ────────────────────────────────────────────────────────
        self.creator_tabs = QTabWidget()

        self.creator_output = QTextEdit()
        self.creator_output.setPlaceholderText(
            "Drafts appear here, fully editable. Nothing is sent anywhere — "
            "review it, then post it yourself.")
        self.creator_tabs.addTab(self.creator_output, "Draft")

        self.creator_calendar_scope = self._library_scope(
            "Calendar scope", self.refresh_calendar)
        calendar_page = QWidget()
        calendar_layout = QVBoxLayout(calendar_page)
        calendar_layout.setContentsMargins(MD, MD, MD, MD)
        calendar_layout.setSpacing(SM)

        nav = QHBoxLayout()
        nav.setSpacing(SM)
        self.creator_calendar_prev_btn = quiet("‹")
        self.creator_calendar_prev_btn.setToolTip("Previous week")
        self.creator_calendar_prev_btn.clicked.connect(
            lambda: self._shift_week(-1))
        self.creator_calendar_today_btn = quiet("This week")
        self.creator_calendar_today_btn.clicked.connect(
            lambda: self._shift_week(0))
        self.creator_calendar_next_btn = quiet("›")
        self.creator_calendar_next_btn.setToolTip("Next week")
        self.creator_calendar_next_btn.clicked.connect(
            lambda: self._shift_week(1))
        self.creator_calendar_week_label = QLabel("")
        self.creator_calendar_week_label.setObjectName("SectionLabel")
        for widget in (self.creator_calendar_prev_btn,
                       self.creator_calendar_today_btn,
                       self.creator_calendar_next_btn,
                       self.creator_calendar_week_label):
            nav.addWidget(widget)
        nav.addStretch()
        self.creator_calendar_reschedule_btn = quiet("Reschedule…")
        self.creator_calendar_reschedule_btn.setToolTip(
            "Pick a new date and time for the selected item — undated "
            "items get their first real date here.")
        self.creator_calendar_reschedule_btn.clicked.connect(
            self.reschedule_selected)
        self.creator_calendar_export_btn = quiet("Export…")
        self.creator_calendar_export_btn.setToolTip(
            "Save the plan as an .ics calendar (dated items) or CSV "
            "(everything).")
        self.creator_calendar_export_btn.clicked.connect(self.export_calendar)
        nav.addWidget(self.creator_calendar_reschedule_btn)
        nav.addWidget(self.creator_calendar_export_btn)
        nav.addWidget(self.creator_calendar_scope)
        calendar_layout.addLayout(nav)

        # One column per weekday; each cell is one planned item carrying
        # its content id as item data — the social panel's UserRole idiom
        # replaces the old row-order ids list.
        self.creator_calendar_table = QTableWidget(0, 7)
        self.creator_calendar_table.setEditTriggers(
            QTableWidget.NoEditTriggers)
        self.creator_calendar_table.setSelectionMode(
            QTableWidget.SingleSelection)
        self.creator_calendar_table.verticalHeader().setVisible(False)
        header = self.creator_calendar_table.horizontalHeader()
        for column in range(7):
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        self.creator_calendar_table.doubleClicked.connect(
            lambda *_: self.reschedule_selected())
        self.creator_calendar_table.itemSelectionChanged.connect(
            lambda: self._calendar_selection_changed(
                self.creator_calendar_table))
        calendar_layout.addWidget(self.creator_calendar_table, 3)

        # Legacy free-text entries cannot be placed on a grid without
        # guessing; they stay visible here until they get a real date.
        self.creator_calendar_undated_table = QTableWidget(0, 3)
        self.creator_calendar_undated_table.setHorizontalHeaderLabels(
            ["When (as written)", "Kind", "Title"])
        self.creator_calendar_undated_table.setEditTriggers(
            QTableWidget.NoEditTriggers)
        self.creator_calendar_undated_table.setSelectionMode(
            QTableWidget.SingleSelection)
        self.creator_calendar_undated_table.verticalHeader().setVisible(False)
        self.creator_calendar_undated_table.horizontalHeader(
            ).setSectionResizeMode(2, QHeaderView.Stretch)
        self.creator_calendar_undated_table.doubleClicked.connect(
            lambda *_: self.reschedule_selected())
        self.creator_calendar_undated_table.itemSelectionChanged.connect(
            lambda: self._calendar_selection_changed(
                self.creator_calendar_undated_table))
        calendar_layout.addWidget(self.creator_calendar_undated_table, 1)
        self.creator_tabs.addTab(calendar_page, "Calendar")

        self.creator_voice_tab = self._build_voice_tab()
        self.creator_tabs.addTab(self.creator_voice_tab, "Voice")

        self.creator_media_scope = self._library_scope(
            "Media scope", self.refresh_media)
        media_body = QWidget()
        media_layout = QVBoxLayout(media_body)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.addWidget(self.creator_media_scope, 0, Qt.AlignRight)
        self.creator_media_table = QTableWidget(0, 4)
        self.creator_media_table.setHorizontalHeaderLabels(
            ["File", "Kind", "Source", "Caption"])
        self.creator_media_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        media_layout.addWidget(self.creator_media_table, 1)
        self.creator_add_media_btn = QPushButton("Add Media")
        self.creator_add_media_btn.clicked.connect(self.add_media)
        self.creator_media_tab = self._tab_with_actions(
            media_body, [self.creator_add_media_btn])
        self.creator_tabs.addTab(self.creator_media_tab, "Media")

        layout.addWidget(self.creator_tabs, 1)

        # Aliases retired 2026-09-21: shared wiring resolves controls
        # through host._find_control(); HOST_CONTROLS stays as the
        # published contract of what this panel owns.
        host.creator_panel = self
        host.creator_resume_workers = []
        self._resume_started = False
        host.creator_worker = None
        host.creator_video_estimate_worker = None
        host.creator_video_worker = None
        self.hide()
        self._kind_changed(self.creator_kind_box.currentText())
        self.refresh_accounts()

    @staticmethod
    def _library_scope(name: str, refresh) -> QComboBox:
        scope = QComboBox()
        scope.addItem("All account work", "all")
        scope.addItem("Current Project", "project")
        scope.setAccessibleName(name)
        scope.setMinimumWidth(180)
        scope.currentIndexChanged.connect(refresh)
        return scope

    @staticmethod
    def _tab_with_actions(body: QWidget, buttons: list) -> QWidget:
        """A tab page: its content, and the buttons that act on that content.

        Putting "Add Media" next to the media table is the difference between
        a button you can find and one of eight in a column labelled nothing.
        """
        page = QWidget()
        page.setObjectName("Transparent")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(MD, MD, MD, MD)
        page_layout.setSpacing(MD)
        page_layout.addWidget(body, 1)
        row = QHBoxLayout()
        row.setSpacing(SM)
        row.addStretch()
        for button in buttons:
            row.addWidget(button)
        page_layout.addLayout(row)
        return page

    def _build_voice_tab(self) -> QWidget:
        """Voice profile, and the persona bible for persona accounts.

        Voice is the single biggest lever on how the drafts read: samples of
        the creator's own writing are what the model imitates, and without them
        every draft starts from nothing.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel(
            "Paste a few of this account's own posts. The model imitates these "
            "— it is what stops drafts reading like generic AI copy."))
        self.creator_voice_samples = QTextEdit()
        self.creator_voice_samples.setPlaceholderText(
            "One post per line — five or six is plenty.")
        layout.addWidget(self.creator_voice_samples, 1)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.addWidget(QLabel("Tone:"), 0, 0)
        self.creator_voice_tone = QLineEdit()
        self.creator_voice_tone.setPlaceholderText("dry, warm, a bit deadpan")
        grid.addWidget(self.creator_voice_tone, 0, 1)
        grid.addWidget(QLabel("Emoji:"), 0, 2)
        self.creator_voice_emoji = QLineEdit()
        self.creator_voice_emoji.setPlaceholderText("sparse — one at most")
        grid.addWidget(self.creator_voice_emoji, 0, 3)
        grid.addWidget(QLabel("Length:"), 1, 0)
        self.creator_voice_length = QLineEdit()
        self.creator_voice_length.setPlaceholderText("1–2 short sentences")
        grid.addWidget(self.creator_voice_length, 1, 1)
        grid.addWidget(QLabel("Never say:"), 1, 2)
        self.creator_voice_banned = QLineEdit()
        self.creator_voice_banned.setPlaceholderText("babe, hun, 🔥")
        grid.addWidget(self.creator_voice_banned, 1, 3)
        layout.addLayout(grid)

        # Persona bible — shown only for persona accounts.
        self.creator_persona_group = QGroupBox("Character bible (persona accounts)")
        pg = QGridLayout(self.creator_persona_group)
        pg.setSpacing(6)
        pg.addWidget(QLabel("Appearance:"), 0, 0)
        self.creator_persona_appearance = QLineEdit()
        self.creator_persona_appearance.setPlaceholderText(
            "Locked description — reused in every render so it stays the same character")
        pg.addWidget(self.creator_persona_appearance, 0, 1, 1, 3)
        pg.addWidget(QLabel("Backstory:"), 1, 0)
        self.creator_persona_backstory = QLineEdit()
        pg.addWidget(self.creator_persona_backstory, 1, 1, 1, 3)
        pg.addWidget(QLabel("Personality:"), 2, 0)
        self.creator_persona_personality = QLineEdit()
        pg.addWidget(self.creator_persona_personality, 2, 1, 1, 3)
        pg.addWidget(QLabel("Never does:"), 3, 0)
        self.creator_persona_boundaries = QLineEdit()
        pg.addWidget(self.creator_persona_boundaries, 3, 1, 1, 3)
        pg.addWidget(QLabel("Seed:"), 4, 0)
        self.creator_persona_seed = QLineEdit()
        self.creator_persona_seed.setPlaceholderText("e.g. 4821 — keeps renders on-model")
        self.creator_persona_seed.setMaximumWidth(120)
        pg.addWidget(self.creator_persona_seed, 4, 1)
        layout.addWidget(self.creator_persona_group)

        save_btn = QPushButton("Save Voice && Character")
        save_btn.setObjectName("PrimaryAction")
        save_btn.clicked.connect(self.save_voice)
        layout.addWidget(save_btn)
        return page

    # ── profile form ────────────────────────────────────────────────────
    def load_models(self) -> None:
        self.creator_panel_base.load_models()

    def _kind_changed(self, kind: str):
        # Which fields apply, in the order they should appear. Kind is always
        # shown; the other three depend on it.
        wanted = [
            (self.creator_kind_field, True),
            (self.creator_campaign_field, True),
            # Channel is the off-platform funnel, so it only applies to promo.
            (self.creator_channel_field, kind == "promo"),
        ]
        self._reflow_compose(wanted)

    def _reflow_compose(self, wanted: list) -> None:
        """Re-pack the compose grid so only applicable fields take a cell.

        Visibility is passed in rather than read back off the widgets: a widget
        that has never been shown reports isHidden() as True, so asking the
        widgets themselves emptied the grid on the first call.
        """
        grid = self.creator_compose_grid
        index = 0
        for widget, visible in wanted:
            grid.removeWidget(widget)
            widget.setVisible(visible)
            if not visible:
                continue
            grid.addWidget(widget, index // 3, index % 3, Qt.AlignTop)
            index += 1

    # ── accounts ────────────────────────────────────────────────────────
    def refresh_accounts(self):
        self.creator_account_box.blockSignals(True)
        self.creator_account_box.clear()
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, handle, platform FROM creator_accounts "
                    "ORDER BY handle").fetchall()
            for row in rows:
                self.creator_account_box.addItem(
                    f"{row['handle']}  ({row['platform']})", row["id"])
        except Exception as exc:
            self.host._note_failure("creator: load accounts", exc)
        self.creator_account_box.blockSignals(False)
        if self.creator_account_box.count():
            self._account_changed(self.creator_account_box.currentIndex())

    def _account_changed(self, index: int):
        account = self.current_account()
        if not account:
            return
        self.creator_handle_input.setText(account.get("handle", ""))
        platform = account.get("platform", "General") or "General"
        platform_index = self.creator_platform_box.findText(
            platform, Qt.MatchFixedString)
        self.creator_platform_box.setCurrentIndex(max(0, platform_index))
        self.refresh_calendar()
        self.load_voice_tab()
        self.refresh_media()

    def current_account(self) -> dict | None:
        account_id = self.creator_account_box.currentData()
        if account_id is None:
            return None
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM creator_accounts WHERE id = ?",
                    (account_id,)).fetchone()
            return dict(row) if row else None
        except Exception as exc:
            self.host._note_failure("creator: read account", exc)
            return None

    def save_account(self):
        handle = self.creator_handle_input.text().strip()
        if not handle:
            QMessageBox.warning(
                self, "No Profile", "Enter a handle or project name first.")
            return
        platform = self.creator_platform_box.currentText().strip() or "General"
        try:
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO creator_accounts
                      (handle, platform, created_at)
                    VALUES (?,?,?)
                    ON CONFLICT(handle) DO UPDATE SET
                      platform=excluded.platform
                """, (handle, platform,
                      datetime.now().isoformat(timespec="seconds")))
                conn.commit()
        except Exception as exc:
            self.host._note_failure("creator: save account", exc,
                                    self.creator_status_label)
            return
        self.creator_status_label.setText(f"Saved {handle}.")
        self.refresh_accounts()

    def delete_account(self):
        account = self.current_account()
        if not account:
            return
        open_renders = 0
        try:
            with get_connection() as conn:
                open_renders = conn.execute(
                    "SELECT COUNT(*) FROM creator_video_jobs "
                    "WHERE account_id = ? AND spend_state = 'reserved'",
                    (account["id"],)).fetchone()[0]
        except Exception as exc:
            self.host._note_failure("creator: count open renders", exc)
        message = (
            f"Remove {account['handle']} and its drafts and performance from "
            "Imprint?\n\nThis only affects this app — nothing on the platform "
            "is touched.")
        if open_renders:
            message += (
                f"\n\n{open_renders} teaser render(s) are still open at "
                "Higgsfield. Deleting removes their record, so any charge "
                "can no longer be reconciled in Imprint — check the "
                "provider console first.")
        confirm = QMessageBox.question(self, "Remove Profile", message)
        if confirm != QMessageBox.Yes:
            return
        if open_renders:
            # The erasure of open money rows is deliberate and recorded.
            self.host._note_failure(
                "creator: delete account", RuntimeError(
                    f"{account['handle']} deleted with {open_renders} "
                    "reserved teaser render(s); their charges are written "
                    "off unreconciled"))
        try:
            with get_connection() as conn:
                conn.execute(
                    "DELETE FROM creator_variants WHERE content_id IN "
                    "(SELECT id FROM creator_content WHERE account_id = ?)",
                    (account["id"],))
                for table in (
                        "creator_video_jobs", "creator_media", "creator_voice",
                        "creator_persona", "creator_content"):
                    conn.execute(f"DELETE FROM {table} WHERE account_id = ?",
                                 (account["id"],))
                conn.execute("DELETE FROM creator_accounts WHERE id = ?",
                             (account["id"],))
                conn.commit()
        except Exception as exc:
            self.host._note_failure("creator: delete account", exc)
            return
        self.refresh_accounts()

    # ── drafting ────────────────────────────────────────────────────────
    def generate(self):
        account = self.current_account()
        if not account:
            QMessageBox.warning(self, "No Profile",
                                "Add a content profile before drafting.")
            return

        agent = self.host.agent_instances["creator"]
        kind = self.creator_kind_box.currentText()
        brief = self.creator_brief_input.toPlainText().strip()
        try:
            messages = agent.build_draft_prompt(
                account, kind, brief,
                channel=self.creator_channel_box.currentText())
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot Draft", str(exc))
            return

        provider = self.creator_provider_box.currentText()
        model = self.creator_model_box.currentText()
        if not model:
            QMessageBox.warning(self, "No Model", "Select a model first.")
            return
        # Keep the token: "creator" is shared with the Higgsfield teaser
        # flow, and resolving by name can bill the teaser's flat cost
        # against this text response (and leave the render unbilled).
        token = self.host.authorize_request("creator", provider, model,
                                            messages[-1]["content"], label=kind)
        if not token:
            return
        self._draft_token = token
        snapshot = self.host.pending_request_snapshot(token)
        self._draft_origin = (snapshot.get("project"), account["id"])

        self.creator_generate_btn.setEnabled(False)
        self._last_generation_cost_eur = 0.0
        self.creator_stop_btn.setEnabled(True)
        self.creator_stop_btn.show()
        self.creator_status_label.setText(f"Drafting {kind}…")
        self.creator_output.clear()

        worker = self.host._new_chat_worker(provider, model, messages, "")
        self.host.creator_worker = worker
        worker.finished_signal.connect(self._on_finished)
        worker.error_signal.connect(self._on_error)
        worker.start()

    def _on_finished(self, response: str):
        self.creator_output.setPlainText(response)
        token, self._draft_token = self._draft_token, None
        if token:
            self.host.record_request(token, response)
        self._last_generation_cost_eur = float(self.host.last_request_cost or 0)
        self.creator_generate_btn.setEnabled(True)
        self.creator_stop_btn.setEnabled(False)
        self.creator_stop_btn.hide()
        self.creator_status_label.setText("Draft ready — review before posting.")

    def _on_error(self, error: str):
        token, self._draft_token = self._draft_token, None
        self._draft_origin = None
        if token:
            self.host.abandon_request(token)
        self.creator_generate_btn.setEnabled(True)
        self.creator_stop_btn.setEnabled(False)
        self.creator_stop_btn.hide()
        self.creator_status_label.setText(f"[Error] {error}")

    def stop(self):
        # cancel(), never terminate(): killing a QThread that is inside a
        # Python call or holds the GIL is a crash/deadlock, and the worker
        # checks its flag at the next safe point anyway.
        worker = self.host.creator_worker
        if worker is not None and worker.isRunning():
            worker.cancel()
        token, self._draft_token = self._draft_token, None
        self._draft_origin = None
        if token:
            self.host.abandon_request(token, reason="stopped")
        self.creator_generate_btn.setEnabled(True)
        self.creator_stop_btn.setEnabled(False)
        self.creator_stop_btn.hide()
        self.creator_status_label.setText("Stopped.")

    # ── calendar ────────────────────────────────────────────────────────
    def schedule(self):
        account = self.current_account()
        body = self.creator_output.toPlainText().strip()
        if not account or not body:
            QMessageBox.warning(self, "Nothing to Schedule",
                                "Draft something first.")
            return
        if self._draft_origin and self._draft_origin[1] != account["id"]:
            QMessageBox.warning(
                self, "Different profile",
                "This draft was generated for another content profile. "
                "Select that profile before adding it to the calendar.")
            return
        if self._draft_origin is not None:
            project_id = self._draft_origin[0]
        else:
            project = self.host._active_project()
            project_id = project["id"] if project else None
        # A Project may have been deleted while a long draft was running.
        if project_id and not self.host.registry.get_project(project_id):
            project_id = None
        when = self._ask_schedule_datetime("Add to Calendar")
        if when is None:
            return
        try:
            with get_connection() as conn:
                # price_usd and revenue_usd still exist on the table and are
                # deliberately not written: dropping the columns would be a
                # migration on a live database, and the money side of this
                # work moved to Backstage.
                conn.execute("""
                    INSERT INTO creator_content
                      (account_id, project_id, created_at, scheduled_for, kind, title,
                       body, status, campaign, channel,
                       generation_cost_eur)
                    VALUES (?,?,?,?,?,?,?,'draft',?,?,?)
                """, (account["id"],
                      project_id,
                      datetime.now().isoformat(timespec="seconds"),
                      when,
                      self.creator_kind_box.currentText(),
                      body.splitlines()[0][:80] if body else "",
                      body,
                      self.creator_campaign_input.text().strip(),
                      self.creator_channel_box.currentText(),
                      float(self._last_generation_cost_eur)))
                conn.commit()
        except Exception as exc:
            self.host._note_failure("creator: schedule", exc,
                                    self.creator_status_label)
            return
        # Land on the week that now holds the item — a correct empty
        # current week reads as "scheduling failed" and invites a
        # duplicate.
        self._show_week_of(when)
        self.refresh_calendar()
        self.creator_tabs.setCurrentIndex(1)

    def _calendar_rows(self, *, full_detail: bool = False):
        """The scoped plan rows, or None when nothing should show."""
        account = self.current_account()
        if not account:
            return None
        project = self.host._active_project()
        scope = self.creator_calendar_scope
        scope.setItemText(1, f"Project: {project['name']}" if project else
                          "Select a Project")
        project_only = scope.currentData() == "project"
        if project_only and not project:
            return None
        columns = ("c.id, c.scheduled_for, c.kind, c.title, "
                   "c.status, c.channel, c.campaign, "
                   + ("c.body, " if full_detail else "")
                   + "p.name AS project_name")
        try:
            with get_connection() as conn:
                return [dict(row) for row in conn.execute(
                    f"SELECT {columns} "
                    "FROM creator_content c LEFT JOIN projects p "
                    "ON p.id = c.project_id WHERE c.account_id = ? "
                    + ("AND c.project_id = ? " if project_only else "")
                    + "ORDER BY c.scheduled_for = '' ASC, c.scheduled_for "
                    "ASC, c.id ASC",
                    (account["id"], project["id"]) if project_only else
                    (account["id"],)).fetchall()]
        except Exception as exc:
            self.host._note_failure("creator: load calendar", exc)
            return None

    @staticmethod
    def _calendar_cell(row, when, has_time) -> QTableWidgetItem:
        # "—" for date-only entries: showing midnight would invent a time
        # the user never chose.
        time_part = when.strftime("%H:%M") if has_time else "—"
        item = QTableWidgetItem(
            f"{time_part}  {row['kind']}: {row['title'] or '(untitled)'}")
        item.setData(Qt.UserRole, row["id"])
        details = [f"Project: {row['project_name'] or 'Unfiled'}",
                   f"Status: {row['status']}"]
        details.append(f"Scheduled: {row['scheduled_for'] or '(undated)'}")
        item.setToolTip("\n".join(details))
        return item

    def refresh_calendar(self):
        grid = self.creator_calendar_table
        undated_table = self.creator_calendar_undated_table
        start = self._calendar_week_start
        self.creator_calendar_week_label.setText(
            content_calendar.week_label(start))
        grid.setRowCount(0)
        grid.setHorizontalHeaderLabels(content_calendar.day_headers(start))
        undated_table.setRowCount(0)
        rows = self._calendar_rows()
        if rows is None:
            undated_table.setVisible(False)
            return
        end = start + timedelta(days=7)
        by_day: dict[int, list] = {i: [] for i in range(7)}
        undated = []
        for row in rows:
            parsed = content_calendar.parse_scheduled(row["scheduled_for"])
            if parsed is None:
                undated.append(row)
                continue
            when, has_time = parsed
            if start <= when.date() < end:
                by_day[(when.date() - start).days].append(
                    (when, has_time, row))
        depth = max((len(items) for items in by_day.values()), default=0)
        grid.setRowCount(depth)
        for day, items in by_day.items():
            for slot, (when, has_time, row) in enumerate(sorted(
                    items, key=lambda entry: (entry[0], entry[2]["id"]))):
                grid.setItem(slot, day,
                             self._calendar_cell(row, when, has_time))
        for row in undated:
            r = undated_table.rowCount()
            undated_table.insertRow(r)
            first = QTableWidgetItem(row["scheduled_for"] or "(no date)")
            first.setData(Qt.UserRole, row["id"])
            undated_table.setItem(r, 0, first)
            undated_table.setItem(r, 1, QTableWidgetItem(row["kind"]))
            undated_table.setItem(
                r, 2, QTableWidgetItem(row["title"] or "(untitled)"))
        undated_table.setVisible(bool(undated))

    def _shift_week(self, weeks: int) -> None:
        if weeks == 0:
            self._calendar_week_start = (
                date.today() - timedelta(days=date.today().weekday()))
        else:
            self._calendar_week_start += timedelta(weeks=weeks)
        self.refresh_calendar()

    def _calendar_selection_changed(self, source) -> None:
        """Selections in the grid and the undated lane are exclusive.

        Judged by the selection model, not by items: clicking an EMPTY
        grid cell is a selection with no QTableWidgetItem behind it, and
        it must still clear the other lane — otherwise a stale hidden
        selection there feeds selected_content_id() and money or paid
        media attaches to an item the user believes they deselected.
        """
        other = (self.creator_calendar_undated_table
                 if source is self.creator_calendar_table
                 else self.creator_calendar_table)
        if (source.selectionModel().hasSelection()
                and other.selectionModel().hasSelection()):
            other.blockSignals(True)
            other.clearSelection()
            other.blockSignals(False)

    def selected_content_id(self):
        """The content id behind the current calendar selection, if any."""
        for table in (self.creator_calendar_table,
                      self.creator_calendar_undated_table):
            for item in table.selectedItems():
                content_id = item.data(Qt.UserRole)
                if content_id is None and item.column() != 0:
                    content_id = (table.item(item.row(), 0) or item).data(
                        Qt.UserRole)
                if content_id is not None:
                    return content_id
        return None

    def _ask_schedule_datetime(self, title: str, *, initial: str = ""):
        """ISO minute-precision text, '' for deliberately undated, or None.

        A panel method so tests can stub the dialog the way they stub
        QInputDialog today.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        prompt = QLabel("When should this go out? Nothing posts itself — "
                        "this is your own plan.")
        prompt.setWordWrap(True)
        layout.addWidget(prompt)
        picker = QDateTimeEdit()
        picker.setCalendarPopup(True)
        picker.setDisplayFormat("yyyy-MM-dd HH:mm")
        parsed = content_calendar.parse_scheduled(initial)
        if parsed:
            picker.setDateTime(QDateTime(parsed[0]))
        else:
            upcoming = datetime.now().replace(
                minute=0, second=0, microsecond=0) + timedelta(hours=1)
            picker.setDateTime(QDateTime(upcoming))
        layout.addWidget(field("Date and time", picker))
        whole_day = QCheckBox("Whole day — no specific time")
        whole_day.setChecked(bool(parsed) and not parsed[1])
        layout.addWidget(whole_day)
        undated = QCheckBox("No date yet — keep it in the Undated list")
        layout.addWidget(undated)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        if undated.isChecked():
            return ""
        if whole_day.isChecked():
            return picker.dateTime().toString("yyyy-MM-dd")
        return picker.dateTime().toString("yyyy-MM-ddTHH:mm")

    def _show_week_of(self, when: str) -> None:
        """Point the visible week at a stored schedule string, if dated."""
        parsed = content_calendar.parse_scheduled(when)
        if parsed:
            self._calendar_week_start = (
                parsed[0].date()
                - timedelta(days=parsed[0].date().weekday()))

    def reschedule_selected(self) -> None:
        content_id = self.selected_content_id()
        if content_id is None:
            QMessageBox.warning(
                self, "Nothing Selected",
                "Select a calendar item first — undated items count too.")
            return
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT scheduled_for, title FROM creator_content "
                    "WHERE id = ?", (content_id,)).fetchone()
        except Exception as exc:
            self.host._note_failure("creator: read schedule", exc)
            return
        if row is None:
            return
        when = self._ask_schedule_datetime(
            f"Reschedule — {row['title'] or 'untitled'}",
            initial=row["scheduled_for"])
        if when is None:
            return
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE creator_content SET scheduled_for = ? "
                    "WHERE id = ?", (when, content_id))
                conn.commit()
        except Exception as exc:
            self.host._note_failure("creator: reschedule", exc,
                                    self.creator_status_label)
            return
        self._show_week_of(when)
        self.refresh_calendar()

    def export_calendar(self) -> None:
        rows = self._calendar_rows(full_detail=True)
        if not rows:
            QMessageBox.warning(
                self, "Nothing to Export",
                "The calendar is empty for this scope.")
            return
        path, chosen_filter = QFileDialog.getSaveFileName(
            self, "Export Calendar",
            str(user_data_base() / "creator_calendar.ics"),
            "Calendar (*.ics);;CSV (*.csv)")
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() not in (".ics", ".csv"):
            # An unrelated suffix ("october.plan") is part of the name,
            # not a format choice — the filter the user picked decides.
            destination = Path(
                str(destination)
                + (".csv" if "CSV" in chosen_filter else ".ics"))
        try:
            if destination.suffix.lower() == ".csv":
                written = content_calendar.export_csv(rows, destination)
                note = f"[Done] Exported {written} items to {destination.name}"
            else:
                written, skipped = content_calendar.export_ics(
                    rows, destination)
                note = (f"[Done] Exported {written} dated items to "
                        f"{destination.name}")
                if skipped:
                    note += (f" — {skipped} undated item(s) skipped; "
                             "use CSV for those.")
        except Exception as exc:
            self.host._note_failure("creator: export calendar", exc,
                                    self.creator_status_label)
            return
        self.creator_status_label.setText(note)

    # ── promo video ─────────────────────────────────────────────────────
    def _teaser_route(self) -> str:
        return self.creator_video_route_box.currentData() or "higgsfield"

    def _teaser_route_changed(self, *_args) -> None:
        from services.database import save_setting
        try:
            save_setting(TEASER_ROUTE_KEY, self._teaser_route())
        except Exception as exc:
            self.host._note_failure("creator: save teaser route", exc)

    def _switch_teaser_route(self, route: str) -> None:
        index = self.creator_video_route_box.findData(route)
        if index >= 0:
            self.creator_video_route_box.setCurrentIndex(index)

    def _teaser_assessment(self, selected_route: str, selected_cost_eur,
                           prompt: str):
        """Every teaser route priced for this teaser. Higgsfield prices only
        through its estimate call, so unless it is the selection it is listed
        without a price and is never recommended on a guess."""
        from services.media_catalog import VERTICAL, direct_video_cost_usd, find_model
        from services.per_unit_pricing import eur_per_usd
        options = []
        for key, route in TEASER_ROUTES.items():
            model = find_model(route["provider"], route["model"])
            if model is None:
                continue
            if key == selected_route:
                cost = selected_cost_eur
            elif key == "higgsfield":
                cost = None
            else:
                try:
                    cost = direct_video_cost_usd(route["model"], TEASER_SECONDS) \
                        * eur_per_usd()
                except ValueError:
                    continue
            options.append(self.host.media_option(
                model, cost, duration=TEASER_SECONDS,
                apply=lambda r=key: self._switch_teaser_route(r)))
        return self.host.assess_media_request(
            "creator", options, TEASER_ROUTES[selected_route]["model"],
            # The catalogue's own label for the shape ("Vertical 9:16"): the
            # bare ratio matched no route's aspects, so every route but the
            # selected one was silently ruled out.
            task=f"promo teaser {prompt[:120]}", aspect=VERTICAL,
            duration=TEASER_SECONDS)

    def generate_video(self):
        from ui.workers import HiggsfieldEstimateWorker

        account = self.current_account()
        if not account:
            QMessageBox.warning(self, "No Account", "Add an account first.")
            return
        agent = self.host.agent_instances["creator"]
        prompt = agent.build_video_prompt(
            account, self.creator_brief_input.toPlainText().strip())
        if self._teaser_route() != "higgsfield":
            self._generate_direct_teaser(account, prompt)
            return

        client = HiggsfieldClient()
        if not client.configured:
            QMessageBox.information(
                self, "Higgsfield Key Needed",
                "Set both HF_API_KEY_ID and HF_API_KEY_SECRET in Imprint's "
                "private .env file to generate promo video.")
            return
        if not self.host.allow_higgsfield_checkbox.isChecked():
            QMessageBox.warning(
                self, "Higgsfield Not Enabled",
                "Enable Higgsfield in the API permissions row before sending "
                "a prompt or reference image to the service.")
            return
        try:
            check_prompt(prompt)
        except ContentPolicyError as exc:
            QMessageBox.warning(self, "Higgsfield Content Policy", str(exc))
            return

        # Reference media is uploaded during preparation because Higgsfield's
        # estimate endpoint accepts the exact generation payload, including its
        # public image URL. No paid generation starts until the estimate is
        # shown and the normal budget/approval guard accepts it.
        references = reference_images(account["id"])

        output_dir = user_data_base() / "output" / "creator" / str(account["id"])
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = output_dir / f"teaser-{stamp}.mp4"

        content_id = self.selected_content_id()

        self._video_context = {
            "account_id": account["id"],
            "content_id": content_id,
            "project_id": None,
            "prompt": prompt,
            "output_path": str(output_path),
            "request_token": None,
            "job_id": "",
            "provider_completed": False,
            "cancel_requested": False,
        }

        self.creator_video_btn.setEnabled(False)
        self.creator_video_cancel_btn.setEnabled(True)
        self.creator_video_cancel_btn.show()
        self.creator_video_status.setText("Preparing Higgsfield estimate…")

        estimate_worker = HiggsfieldEstimateWorker(
            client, prompt, reference_image=references[0] if references else None)
        self.host.creator_video_estimate_worker = estimate_worker
        estimate_worker.status_signal.connect(self.creator_video_status.setText)
        estimate_worker.done_signal.connect(
            lambda request, estimate, c=client:
            self._video_estimated(c, request, estimate))
        estimate_worker.error_signal.connect(self._video_error)
        estimate_worker.start()

    def _video_estimated(self, client, request, estimate):
        """Show the provider's exact price before authorising generation."""
        from services.per_unit_pricing import eur_per_usd
        from ui.workers import HiggsfieldWorker

        context = self._video_context
        if not context:
            return
        if context.get("cancel_requested"):
            self._video_reset("Cancelled.")
            return
        cost_eur = round(estimate.usd * eur_per_usd(), 6)
        context.update({
            "endpoint": request.endpoint,
            "estimated_credits": estimate.credits,
            "estimated_usd": estimate.usd,
            "estimated_eur": cost_eur,
        })
        self.creator_video_status.setText(
            f"Estimated by Higgsfield: ${estimate.usd:.2f} "
            f"({estimate.credits:g} credits). Awaiting approval…")

        # Assessed across every teaser route, this one at Higgsfield's own quote.
        assessment = self._teaser_assessment("higgsfield", cost_eur,
                                             context["prompt"])
        token = self.host.authorize_request(
            "creator", "higgsfield", request.endpoint,
            context["prompt"], label="promo teaser", flat_cost_eur=cost_eur,
            assessment=assessment)
        if not token:
            self._video_reset("Render not approved.")
            if (assessment is not None
                    and self.host.last_applied_assessment is assessment):
                self.generate_video()      # the route Apply chose, asked again
            return
        context["request_token"] = token
        snapshot = self.host.pending_request_snapshot(token)
        context["project_id"] = snapshot.get("project")
        context["run_id"] = snapshot.get("run_id", "")

        render_worker = HiggsfieldWorker(
            client, context["prompt"], context["output_path"],
            prepared_request=request)
        self.host.creator_video_worker = render_worker
        render_worker.status_signal.connect(self.creator_video_status.setText)
        render_worker.job_signal.connect(self._video_job_update)
        render_worker.done_signal.connect(
            lambda path, aid=context["account_id"]:
            self._video_done(aid, path))
        render_worker.error_signal.connect(self._video_error)
        render_worker.start()

    def _generate_direct_teaser(self, account: dict, prompt: str) -> None:
        """A teaser from Gemini Omni or Wan 3.0, with the reference images.

        The job row is written under a local id *before* the paid request,
        and the provider's own job id is stored beside it when it arrives. A
        render the app died during is then never invisible: a Wan task is
        resumed from its id on the next launch, and an Omni render (one
        synchronous call, no job to look up) is marked lost and surfaced —
        never silently billed, the Video workspace's rule.
        """
        import uuid
        from services.gemini_client import GeminiClientWrapper
        from services.media_catalog import direct_video_cost_usd
        from services.per_unit_pricing import eur_per_usd
        from services.qwen_client import QwenClientWrapper
        from services.recommendations.catalog import provider_configured
        from ui.workers import VideoGenerationWorker

        route = self._teaser_route()
        spec = TEASER_ROUTES[route]
        if not provider_configured(route):
            QMessageBox.information(
                self, f"{spec['provider']} Key Needed",
                f"{spec['label']} needs a {spec['provider']} key in Imprint's "
                "private .env file.")
            return
        if not self.host._provider_permission(route):
            QMessageBox.warning(
                self, f"{spec['provider']} Not Enabled",
                f"Enable {spec['provider']} in the API permissions row before "
                "sending a prompt or reference image to the service.")
            return
        references = reference_images(account["id"])
        usd = direct_video_cost_usd(spec["model"], TEASER_SECONDS)
        cost_eur = round(usd * eur_per_usd(), 6)
        assessment = self._teaser_assessment(route, cost_eur, prompt)
        token = self.host.authorize_request(
            "creator", route, spec["model"], prompt, label="promo teaser",
            flat_cost_eur=cost_eur, assessment=assessment)
        if not token:
            if (assessment is not None
                    and self.host.last_applied_assessment is assessment):
                self.generate_video()
            return

        output_dir = user_data_base() / "output" / "creator" / str(account["id"])
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = output_dir / f"teaser-{stamp}.mp4"
        local_id = f"{route}-{uuid.uuid4().hex[:16]}"
        snapshot = self.host.pending_request_snapshot(token)
        self._video_context = {
            "account_id": account["id"],
            "content_id": self.selected_content_id(),
            "project_id": snapshot.get("project"),
            "run_id": snapshot.get("run_id", ""),
            "prompt": prompt,
            "output_path": str(output_path),
            "request_token": token,
            "job_id": local_id,
            "fixed_request_id": local_id,
            "route": route,
            "endpoint": f"{route}:{spec['model']}",
            "estimated_usd": usd,
            "estimated_eur": cost_eur,
            "provider_completed": False,
            "cancel_requested": False,
        }
        # Before the paid request: a submission that never comes back is
        # still a row the next launch reconciles.
        self._video_job_update(types.SimpleNamespace(
            job_id=local_id, status="submitted", error="",
            endpoint=self._video_context["endpoint"], correlation_id=""))

        self.creator_video_btn.setEnabled(False)
        self.creator_video_cancel_btn.setEnabled(False)
        self.creator_video_status.setText(f"Submitting to {spec['provider']}…")
        client = (GeminiClientWrapper() if route == "gemini"
                  else QwenClientWrapper())
        worker = VideoGenerationWorker(
            client, prompt, output_path, provider=spec["provider"],
            model=spec["model"], seconds=TEASER_SECONDS,
            aspect_ratio=TEASER_ASPECT, reference_images=references)
        self.host.creator_video_worker = worker
        worker.status_signal.connect(self.creator_video_status.setText)
        worker.job_signal.connect(self._direct_teaser_update)
        worker.done_signal.connect(
            lambda path, aid=account["id"]: self._video_done(aid, path))
        worker.error_signal.connect(self._video_error)
        worker.start()

    def _direct_teaser_update(self, job) -> None:
        """A Gemini/Wan job update, filed under the local id; the provider's
        job id is kept as the correlation id the resume reads."""
        context = self._video_context
        if not context:
            return
        self._video_job_update(types.SimpleNamespace(
            job_id=context["fixed_request_id"], status=job.status,
            error=getattr(job, "error", "") or "",
            endpoint=context["endpoint"],
            correlation_id=getattr(job, "job_id", "") or ""))

    def cancel_video(self):
        """Cancel preparation, or ask Higgsfield to cancel a queued render."""
        if self._video_context:
            self._video_context["cancel_requested"] = True
        estimate_worker = self.host.creator_video_estimate_worker
        render_worker = self.host.creator_video_worker
        if estimate_worker is not None and estimate_worker.isRunning():
            estimate_worker.cancel()
            self.creator_video_status.setText("Cancelling estimate…")
        elif render_worker is not None and render_worker.isRunning():
            render_worker.cancel()
            self.creator_video_status.setText(
                "Cancellation requested. If rendering already began, "
                "Higgsfield will finish and Imprint will save the result.")
        self.creator_video_cancel_btn.setEnabled(False)

    def _video_job_update(self, job):
        """Persist every provider state transition for recovery and support."""
        context = self._video_context
        if not context:
            return
        context["job_id"] = job.job_id
        if job.status == "completed":
            context["provider_completed"] = True
        now = datetime.now().isoformat(timespec="seconds")
        policy_result = ("provider-rejected" if job.status == "nsfw"
                         else "local-approved")
        actual_usd = (context.get("estimated_usd")
                      if job.status == "completed" else None)
        cost_basis = ("provider preflight estimate; render completed"
                      if actual_usd is not None else "")
        try:
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO creator_video_jobs
                      (request_id, account_id, content_id, project_id,
                       created_at, updated_at,
                       endpoint, prompt, prompt_version, estimated_credits,
                       estimated_usd, actual_usd, cost_basis, status,
                       policy_result, error, correlation_id,
                       spend_state, flat_cost_eur, output_path, run_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                            'reserved',?,?,?)
                    ON CONFLICT(request_id) DO UPDATE SET
                      updated_at=excluded.updated_at,
                      project_id=COALESCE(creator_video_jobs.project_id,
                                          excluded.project_id),
                      actual_usd=COALESCE(excluded.actual_usd,
                                          creator_video_jobs.actual_usd),
                      cost_basis=CASE WHEN excluded.cost_basis != ''
                                      THEN excluded.cost_basis
                                      ELSE creator_video_jobs.cost_basis END,
                      status=excluded.status,
                      policy_result=excluded.policy_result,
                      error=excluded.error,
                      correlation_id=CASE WHEN excluded.correlation_id != ''
                                          THEN excluded.correlation_id
                                          ELSE creator_video_jobs.correlation_id END
                """, (
                    job.job_id, context["account_id"], context.get("content_id"),
                    context.get("project_id"),
                    now, now,
                    getattr(job, "endpoint", "") or context.get("endpoint", ""),
                    context["prompt"], "creator-video-v1",
                    context.get("estimated_credits", 0.0),
                    context.get("estimated_usd", 0.0), actual_usd, cost_basis,
                    job.status, policy_result, job.error,
                    getattr(job, "correlation_id", "") or "",
                    context.get("estimated_eur", 0.0),
                    context.get("output_path", ""),
                    context.get("run_id", ""),
                ))
                conn.commit()
        except Exception as exc:
            self.host._note_failure("creator: track Higgsfield job", exc,
                                    self.creator_video_status)

    def _video_done(self, account_id: int, path: str):
        """Store the render in the media library rather than leaving it on disk."""
        context = self._video_context
        # Only ever by the token this flow authorized — never by the shared
        # "creator" name, which the drafting flow also uses.
        token = context.get("request_token")
        route = context.get("route", "higgsfield")
        self._store_media(account_id, path, source=route,
                          job_id=context.get("job_id", ""),
                          caption=f"{TEASER_ROUTES[route]['provider']} teaser")
        self._link_project_media(context.get("project_id"), path, "creator_video")
        # Settle before billing: a crash between the two must resolve as a
        # one-time undercount (the row still carries actual_usd), never as
        # a double-bill when the next launch resumes a still-reserved row.
        self._settle_teaser_job(context.get("job_id", ""), "billed")
        if token:
            self.host.record_request(token, f"teaser: {Path(path).name}")
        attached = False
        if context.get("content_id"):
            try:
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE creator_content SET media_path = ? WHERE id = ?",
                        (path, context["content_id"]))
                    conn.execute(
                        "UPDATE creator_video_jobs SET local_path = ? "
                        "WHERE request_id = ?",
                        (path, context.get("job_id", "")))
                    conn.commit()
                attached = True
            except Exception as exc:
                self.host._note_failure("creator: attach teaser", exc,
                                        self.creator_video_status)
        elif context.get("job_id"):
            try:
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE creator_video_jobs SET local_path = ? "
                        "WHERE request_id = ?",
                        (path, context["job_id"]))
                    conn.commit()
            except Exception as exc:
                self.host._note_failure("creator: save teaser path", exc,
                                        self.creator_video_status)
        note = f"Saved: {Path(path).name}"
        if attached:
            note += " · attached to the selected calendar item"
        self._video_reset(note)
        self.refresh_media()
        if attached:
            self.refresh_calendar()

    def _settle_teaser_job(self, job_id: str, spend_state: str) -> None:
        """Close the delivery row's money state; billed rows also settle
        actual cost from the preflight estimate."""
        if not job_id:
            return
        try:
            with get_connection() as conn:
                if spend_state == "billed":
                    conn.execute(
                        """UPDATE creator_video_jobs
                              SET spend_state = 'billed',
                                  actual_usd = COALESCE(actual_usd,
                                                        estimated_usd),
                                  cost_basis = CASE WHEN cost_basis = ''
                                       THEN 'provider preflight estimate; render completed'
                                       ELSE cost_basis END,
                                  updated_at = ?
                            WHERE request_id = ?""",
                        (datetime.now().isoformat(timespec="seconds"), job_id))
                else:
                    conn.execute(
                        """UPDATE creator_video_jobs
                              SET spend_state = ?, updated_at = ?
                            WHERE request_id = ?""",
                        (spend_state,
                         datetime.now().isoformat(timespec="seconds"), job_id))
                conn.commit()
        except Exception as exc:
            self.host._note_failure("creator: settle teaser job", exc)

    def _video_error(self, error: str):
        context = self._video_context
        token = context.get("request_token") if context else None
        # Same honesty rule as the Video workspace: neither a local poll
        # deadline nor a local exception is a provider verdict — the render
        # may still finish and be charged, so the row stays 'reserved' for
        # the next launch. Both flags are gated on this flow's own token so
        # a stale worker from an earlier render cannot mislabel an
        # estimate-stage failure.
        provider_completed = bool((context or {}).get("provider_completed"))
        timed_out = (bool(token) and not provider_completed
                     and getattr(self.host.creator_video_worker,
                                 "timed_out", False))
        retryable = (bool(token) and not provider_completed
                     and bool(context.get("job_id"))
                     and getattr(self.host.creator_video_worker,
                                 "retryable", False))
        keep_open = timed_out or retryable
        if token:
            if provider_completed:
                # A completed render is charged even if the local download
                # later fails; keep spend accounting honest — settle first
                # so a crash mid-handler can never double-bill on resume.
                self._settle_teaser_job(context.get("job_id", ""), "billed")
                self.host.record_request(
                    token, f"render completed; local error: {error}")
            elif keep_open:
                self.host.abandon_request(
                    token, reason="timeout" if timed_out else "error")
            else:
                self.host.abandon_request(token)
                self._settle_teaser_job(context.get("job_id", ""), "released")
        self._video_reset(f"[Error] {error}")
        if keep_open:
            provider = TEASER_ROUTES[(context or {}).get(
                "route", "higgsfield")]["provider"]
            self.creator_video_status.setText(
                f"{provider} may still finish this render — the next launch "
                "checks and saves the result.")

    def _video_reset(self, status: str):
        self.creator_video_btn.setEnabled(True)
        self.creator_video_cancel_btn.setEnabled(False)
        self.creator_video_cancel_btn.hide()
        self.creator_video_status.setText(status)

    # ── startup reconciliation of teasers that outlived the process ─────
    def resume_pending_teasers(self) -> None:
        """Finish Higgsfield teaser renders a previous process left open.

        Only rows this feature wrote are considered: spend_state '' marks a
        pre-feature delivery record with no settlement contract, and those
        are never reconciled. Same honesty rules as the Video workspace —
        the money was approved before the restart, so nothing re-asks; a
        local deadline or local exception keeps the row reserved for the
        next launch.
        """
        if self._resume_started:
            # One pass per process: a second would double-reserve and
            # double-bill.
            return
        self._resume_started = True
        try:
            with get_connection() as conn:
                rows = [dict(row) for row in conn.execute(
                    """SELECT * FROM creator_video_jobs
                        WHERE spend_state = 'reserved'
                        ORDER BY created_at""").fetchall()]
        except Exception as exc:
            self.host._note_failure("creator: read pending teasers", exc)
            return
        for row in rows:
            self._spawn_teaser_resume(row)

    def _spawn_teaser_resume(self, row: dict) -> None:
        # The resume worker is the Video workspace's: rebuild-poll-download
        # is provider logic, not workspace logic, and agents may depend on
        # sibling agents (the social publishers already lean on video).
        from agents.video.workers import VideoResumeWorker

        endpoint = row.get("endpoint") or ""
        if endpoint.startswith(("gemini:", "qwen:")):
            self._resume_direct_teaser(row)
            return
        client = HiggsfieldClient()
        if not client.configured:
            # The render may still be live at the provider; without keys
            # there is no way to look, so the row stays reserved.
            self.host._note_failure(
                "creator: resume teaser", RuntimeError(
                    f"teaser job {row['request_id']} from a previous "
                    "session is waiting, but the Higgsfield keys are not "
                    "configured"))
            return
        if not row.get("output_path"):
            # Defensive: a reserved row always carries its target path.
            self.host._note_failure(
                "creator: resume teaser", RuntimeError(
                    f"teaser job {row['request_id']} has no output path"))
            return
        token = self.host.restore_request(
            "creator", "higgsfield", row.get("endpoint") or "higgsfield",
            row.get("prompt", ""), label="promo teaser (resumed)",
            flat_cost_eur=row.get("flat_cost_eur") or 0.0,
            project=row.get("project_id"), run_id=row.get("run_id", ""))
        worker = VideoResumeWorker(
            client, "higgsfield", job_id=row["request_id"],
            model=row.get("endpoint", ""), seconds=0, aspect_ratio="",
            status_url="", output_path=row["output_path"])
        self.host.creator_resume_workers.append(worker)
        worker.job_signal.connect(
            lambda job, r=row["request_id"]:
            self._resume_teaser_update(r, job))
        worker.done_signal.connect(
            lambda path, r=row, t=token, w=worker:
            self._resume_teaser_done(r, t, w, path))
        worker.error_signal.connect(
            lambda err, r=row, t=token, w=worker:
            self._resume_teaser_error(r, t, w, err))
        worker.start()
        if not self._video_context:
            self.creator_video_status.setText(
                "Resuming a teaser render from the previous session…")

    def _resume_direct_teaser(self, row: dict) -> None:
        """Reconcile a Gemini/Wan teaser a previous process left reserved.

        Wan is a task with an id: watch it again and save the result, as the
        Video workspace does. Omni is one synchronous call with nothing to
        look up afterwards, and a Wan submission that never got its id back
        is in the same position: marked lost, released, and surfaced —
        never billed on a guess.
        """
        from agents.video.workers import VideoResumeWorker
        from services.qwen_client import QwenClientWrapper

        route, _sep, model = (row.get("endpoint") or "").partition(":")
        task_id = row.get("correlation_id") or ""
        if route != "qwen" or not task_id:
            self._settle_teaser_job(row["request_id"], "released")
            try:
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE creator_video_jobs SET status = 'lost', "
                        "error = ? WHERE request_id = ?",
                        ("interrupted before the result came back",
                         row["request_id"]))
                    conn.commit()
            except Exception as exc:
                self.host._note_failure("creator: mark lost teaser", exc)
            provider = TEASER_ROUTES.get(route, {}).get("provider", route)
            self.host._note_failure("creator: resume teaser", RuntimeError(
                f"a {provider} teaser was interrupted before its result came "
                "back; it was not billed here. Check the provider's usage "
                "page if it may have run."))
            if not self._video_context:
                self.creator_video_status.setText(
                    f"A {provider} teaser from the last session was "
                    "interrupted and could not be recovered; it was not "
                    "billed here.")
            return
        client = QwenClientWrapper()
        if not client.key_available():
            self.host._note_failure("creator: resume teaser", RuntimeError(
                f"Wan teaser {task_id} is waiting, but DASHSCOPE_API_KEY is "
                "not configured"))
            return
        token = self.host.restore_request(
            "creator", "qwen", model, row.get("prompt", ""),
            label="promo teaser (resumed)",
            flat_cost_eur=row.get("flat_cost_eur") or 0.0,
            project=row.get("project_id"), run_id=row.get("run_id", ""))
        worker = VideoResumeWorker(
            client, "qwen", job_id=task_id, model=model,
            seconds=TEASER_SECONDS, aspect_ratio=TEASER_ASPECT, status_url="",
            output_path=row["output_path"])
        self.host.creator_resume_workers.append(worker)
        worker.done_signal.connect(
            lambda path, r=row, t=token, w=worker:
            self._resume_teaser_done(r, t, w, path))
        worker.error_signal.connect(
            lambda err, r=row, t=token, w=worker:
            self._resume_teaser_error(r, t, w, err))
        worker.start()

    def _resume_teaser_update(self, request_id: str, job) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """UPDATE creator_video_jobs
                          SET status = CASE WHEN ? != '' THEN ? ELSE status END,
                              error = ?,
                              policy_result = CASE WHEN ? = 'nsfw'
                                   THEN 'provider-rejected'
                                   ELSE policy_result END,
                              updated_at = ?
                        WHERE request_id = ?""",
                    (job.status or "", job.status or "", job.error or "",
                     job.status or "",
                     datetime.now().isoformat(timespec="seconds"),
                     request_id))
                conn.commit()
        except Exception as exc:
            self.host._note_failure("creator: track resumed teaser", exc)

    def _resume_teaser_done(self, row: dict, token, worker, path: str) -> None:
        route = (row.get("endpoint") or "").partition(":")[0]
        route = route if route in TEASER_ROUTES else "higgsfield"
        self._store_media(row["account_id"], path, source=route,
                          job_id=row["request_id"],
                          caption=f"{TEASER_ROUTES[route]['provider']} teaser")
        self._link_project_media(row.get("project_id"), path, "creator_video")
        # Settle before billing (see _video_done for why).
        self._settle_teaser_job(row["request_id"], "billed")
        try:
            self.host.record_request(
                token, f"teaser (resumed): {Path(path).name}")
        except Exception as exc:
            self.host._note_failure("creator: bill resumed teaser", exc)
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE creator_video_jobs SET local_path = ? "
                    "WHERE request_id = ?", (path, row["request_id"]))
                if row.get("content_id"):
                    conn.execute(
                        "UPDATE creator_content SET media_path = ? "
                        "WHERE id = ?", (path, row["content_id"]))
                conn.commit()
        except Exception as exc:
            self.host._note_failure("creator: attach resumed teaser", exc)
        if not self._video_context:
            self.creator_video_status.setText(
                f"Resumed teaser saved: {Path(path).name}")
        self.refresh_media()
        if row.get("content_id"):
            self.refresh_calendar()

    def _resume_teaser_error(self, row: dict, token, worker,
                             error: str) -> None:
        if worker.provider_completed:
            # Charged and rendered; only the local save failed. Settle
            # first so a crash mid-handler can never double-bill.
            self._settle_teaser_job(row["request_id"], "billed")
            self.host.record_request(
                token, f"resumed render completed; local error: {error}")
        elif worker.timed_out or worker.retryable:
            # Not a provider verdict — the row stays reserved and the next
            # launch resumes again; only this session's reservation ends.
            self.host.abandon_request(
                token, reason="timeout" if worker.timed_out else "error")
        else:
            self.host.abandon_request(token)
            self._settle_teaser_job(row["request_id"], "released")
        if not self._video_context:
            self.creator_video_status.setText(
                f"[Resume] {error}")

    # ── voice and character ─────────────────────────────────────────────
    def save_voice(self):
        account = self.current_account()
        if not account:
            QMessageBox.warning(self, "No Account", "Select an account first.")
            return
        save_voice(
            account["id"],
            samples=self.creator_voice_samples.toPlainText(),
            tone=self.creator_voice_tone.text(),
            emoji_style=self.creator_voice_emoji.text(),
            banned_words=self.creator_voice_banned.text(),
            typical_length=self.creator_voice_length.text(),
        )
        if account.get("account_type") == "persona":
            try:
                seed = int(self.creator_persona_seed.text().strip() or 0) or None
            except ValueError:
                seed = None
            save_persona(
                account["id"],
                appearance=self.creator_persona_appearance.text(),
                backstory=self.creator_persona_backstory.text(),
                personality=self.creator_persona_personality.text(),
                boundaries=self.creator_persona_boundaries.text(),
                seed=seed,
            )
        self.creator_status_label.setText("Voice saved — drafts will use it.")

    def load_voice_tab(self):
        account = self.current_account()
        if not account:
            return
        voice = load_voice(account["id"])
        self.creator_voice_samples.setPlainText(voice.get("samples", ""))
        self.creator_voice_tone.setText(voice.get("tone", ""))
        self.creator_voice_emoji.setText(voice.get("emoji_style", ""))
        self.creator_voice_banned.setText(voice.get("banned_words", ""))
        self.creator_voice_length.setText(voice.get("typical_length", ""))

        is_persona = account.get("account_type") == "persona"
        self.creator_persona_group.setVisible(is_persona)
        if is_persona:
            persona = load_persona(account["id"])
            self.creator_persona_appearance.setText(persona.get("appearance", ""))
            self.creator_persona_backstory.setText(persona.get("backstory", ""))
            self.creator_persona_personality.setText(persona.get("personality", ""))
            self.creator_persona_boundaries.setText(persona.get("boundaries", ""))
            seed = persona.get("seed")
            self.creator_persona_seed.setText(str(seed) if seed else "")

    # ── media library ───────────────────────────────────────────────────
    def add_media(self):
        account = self.current_account()
        if not account:
            QMessageBox.warning(self, "No Account", "Select an account first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Media", "",
            "Media (*.png *.jpg *.jpeg *.webp *.mp4 *.mov *.m4a *.mp3)")
        if not paths:
            return
        project = self.host._active_project()
        project_id = project["id"] if project else None
        for path in paths:
            if self._store_media(account["id"], path, source="upload"):
                kind = ("creator_video" if Path(path).suffix.lower() in
                        (".mp4", ".mov") else
                        "creator_audio" if Path(path).suffix.lower() in
                        (".mp3", ".m4a") else "creator_image")
                self._link_project_media(project_id, path, kind)
        self.refresh_media()
        self.creator_tabs.setCurrentWidget(self.creator_media_tab)

    def _store_media(self, account_id: int, path: str,
                     *, source: str = "upload", job_id: str = "",
                     caption: str = ""):
        suffix = Path(path).suffix.lower()
        kind = ("video" if suffix in (".mp4", ".mov")
                else "audio" if suffix in (".mp3", ".m4a") else "image")
        try:
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO creator_media
                      (account_id, path, kind, caption, source, job_id, added_at)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(account_id, path) DO UPDATE SET
                      caption=excluded.caption, source=excluded.source,
                      job_id=CASE WHEN excluded.job_id != '' THEN excluded.job_id
                                  ELSE creator_media.job_id END
                """, (account_id, path, kind, caption, source, job_id,
                      datetime.now().isoformat(timespec="seconds")))
                conn.commit()
            return True
        except Exception as exc:
            self.host._note_failure("creator: store media", exc)
            return False

    def _link_project_media(self, project_id, path: str, kind: str) -> None:
        """Project association is a link, not ownership of account media."""
        if not project_id:
            return
        from services.project_artifacts import record

        try:
            media = Path(path)
            record(project_id, "creator", kind, media, media.name)
        except Exception as exc:
            self.host._note_failure("creator: link project media", exc)

    def refresh_media(self):
        from services.project_artifacts import list_for_project

        account = self.current_account()
        self.creator_media_table.setRowCount(0)
        if not account:
            return
        project = self.host._active_project()
        scope = self.creator_media_scope
        scope.setItemText(1, f"Project: {project['name']}" if project else
                          "Select a Project")
        project_only = scope.currentData() == "project"
        if project_only and not project:
            return
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT path, kind, source, caption FROM creator_media "
                    "WHERE account_id = ? ORDER BY id DESC",
                    (account["id"],)).fetchall()
        except Exception as exc:
            self.host._note_failure("creator: load media", exc)
            return
        if project_only:
            paths = {row["path"] for row in list_for_project(
                project["id"], kinds=("creator_video", "creator_audio",
                                      "creator_image"))}
            rows = [row for row in rows
                    if str(Path(row["path"]).expanduser().resolve()) in paths]
        for row in rows:
            r = self.creator_media_table.rowCount()
            self.creator_media_table.insertRow(r)
            for col, value in enumerate([Path(row["path"]).name, row["kind"],
                                         row["source"], row["caption"]]):
                self.creator_media_table.setItem(r, col, QTableWidgetItem(str(value)))

    # ── revenue attribution ─────────────────────────────────────────────
