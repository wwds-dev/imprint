"""Compact, structured status cards for Imprint's narrow utility rail.

The rail is only 244 pixels wide.  Long prose labels turn it into a wall of
text, so these widgets use the same information hierarchy as the rest of the
app: a small label, a primary value, then optional evidence or state.
"""

from __future__ import annotations

import re

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ui.forms import SM, XS
from ui.theme import recolour
from ui.style import (
    ACCENT, ACCENT_LINE, ACCENT_WASH, BORDER, ELEVATED, SUNKEN, TEXT,
    TEXT_DIM, TEXT_MUTE, WARNING, WARNING_LINE, WARNING_WASH,
)


def _label(text: str, object_name: str) -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(object_name)
    widget.setWordWrap(True)
    return widget


class RailCard(QFrame):
    """Base surface used inside a collapsed rail section."""

    def __init__(self, accessible_name: str):
        super().__init__()
        self.setObjectName("RailStatusCard")
        self.setAccessibleName(accessible_name)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)


class ResourceStatusCard(RailCard):
    """Four live resource readings arranged for quick scanning."""

    def __init__(self):
        super().__init__("Live system resources")
        layout = QGridLayout(self)
        layout.setContentsMargins(SM, SM, SM, SM)
        layout.setHorizontalSpacing(SM)
        layout.setVerticalSpacing(SM)
        self.values: dict[str, QLabel] = {}
        self.details: dict[str, QLabel] = {}
        for row, (key, title) in enumerate((
            ("ram", "Memory"), ("cpu", "Processor"),
            ("swap", "Swap"), ("battery", "Battery"),
        )):
            name = _label(title, "RailFieldName")
            value = _label("—", "RailMetricValue")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            detail = _label("", "RailDetail")
            layout.addWidget(name, row * 2, 0)
            layout.addWidget(value, row * 2, 1)
            layout.addWidget(detail, row * 2 + 1, 0, 1, 2)
            self.values[key] = value
            self.details[key] = detail
        layout.setColumnStretch(0, 1)

    @staticmethod
    def _tone(level: str) -> str:
        """The colour for one reading, under the current theme.

        Resolved per snapshot rather than once, so a theme change reaches these
        on the next refresh without the cards being rebuilt.
        """
        return recolour({"green": ACCENT, "yellow": WARNING,
                         "red": "#f87171"}.get(level, TEXT_DIM))

    def set_snapshot(self, stats: dict) -> None:
        readings = {
            "ram": (
                f"{stats['ram_percent']:.0f}%", stats["ram_level"],
                f"{stats['ram_used_gb']:.1f} GB used · {stats['ram_available_gb']:.1f} GB free",
            ),
            "cpu": (
                f"{stats['cpu_percent']:.0f}%", stats["cpu_level"],
                stats.get("cpu_trend", ""),
            ),
            "swap": (
                f"{stats['swap_percent']:.0f}%", stats["swap_level"],
                f"{stats['swap_used_gb']:.1f} of {stats['swap_total_gb']:.1f} GB used",
            ),
            "battery": (
                "—" if stats["battery_percent"] is None else
                f"{stats['battery_percent']:.0f}%",
                stats["battery_level"], stats["battery_note"],
            ),
        }
        for key, (value, level, detail) in readings.items():
            self.values[key].setText(value)
            self.values[key].setStyleSheet(f"color: {self._tone(level)};")
            self.details[key].setText(detail)


class RoutingStatusCard(RailCard):
    """Last Chat route and recommendation for the current Chat prompt."""

    def __init__(self):
        super().__init__("Chat routing and recommendation for the current prompt")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SM, SM, SM, SM)
        layout.setSpacing(XS)

        layout.addWidget(_label("Last Chat request", "RailFieldName"))
        self.route_value = _label("Not computed", "RailPrimaryValue")
        layout.addWidget(self.route_value)

        divider = QFrame()
        divider.setObjectName("RailCardDivider")
        divider.setFrameShape(QFrame.HLine)
        layout.addWidget(divider)

        heading = QHBoxLayout()
        heading.setSpacing(XS)
        heading.addWidget(_label("Best fit for Chat prompt", "RailFieldName"))
        heading.addStretch()
        self.score_badge = _label("—", "RailScoreBadge")
        self.score_badge.setAlignment(Qt.AlignCenter)
        heading.addWidget(self.score_badge)
        layout.addLayout(heading)

        self.recommendation_value = _label("Not calculated", "RailPrimaryValue")
        layout.addWidget(self.recommendation_value)
        self.reason_label = _label(
            "Type a Chat prompt to refine this recommendation.", "RailDetail")
        layout.addWidget(self.reason_label)
        self.availability_label = _label("", "RailAvailability")
        layout.addWidget(self.availability_label)

    def reset_route(self) -> None:
        self.route_value.setText("Not computed")
        self.route_value.setToolTip("No request has been routed in this session.")

    def set_route(self, agent: str, provider: str, model: str) -> None:
        pretty_agent = str(agent or "Unknown").replace("_", " ").title()
        self.route_value.setText(f"{pretty_agent}\n{provider} · {model}")
        self.route_value.setToolTip(
            f"Last request route: {agent} · {provider} · {model}")

    @staticmethod
    def _concise_reason(reason: str) -> str:
        text = re.sub(r"^Best match for [^:]+:\s*", "", reason).strip()
        text = re.sub(r"\s*Fit score \d+/100\..*$", "", text).strip()
        return text[:1].upper() + text[1:] if text else "Best eligible match."

    def set_recommendation(self, provider: str, model: str, reason: str,
                           score: int | None = None,
                           confidence: str = "",
                           setup_needed: bool = False) -> None:
        self.recommendation_value.setText(f"{provider} · {model}")
        score_text = f"{score}/100" if score is not None else "Best fit"
        if confidence:
            score_text += f" · {confidence.title()}"
        self.score_badge.setText(score_text)
        self.reason_label.setText(self._concise_reason(reason))
        self.reason_label.setToolTip(reason)
        if setup_needed:
            self.availability_label.setText("Setup needed")
            self.availability_label.setProperty("status", "warning")
        else:
            self.availability_label.setText("Ready in current setup")
            self.availability_label.setProperty("status", "ready")
        self.availability_label.style().unpolish(self.availability_label)
        self.availability_label.style().polish(self.availability_label)


class ApiKeysStatusCard(RailCard):
    """Provider key availability as individual rows, not one text paragraph."""

    def __init__(self, providers: tuple[str, ...]):
        super().__init__("Cloud provider key status")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SM, XS, SM, XS)
        layout.setSpacing(0)
        self.status_labels: dict[str, QLabel] = {}
        self.dot_labels: dict[str, QLabel] = {}
        for provider in providers:
            row = QWidget()
            row.setObjectName("RailKeyRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 7, 0, 7)
            row_layout.setSpacing(XS)
            dot = _label("●", "RailStatusDot")
            dot.setFixedWidth(11)
            name = _label(provider, "RailKeyName")
            status = _label("Checking…", "RailKeyStatus")
            status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_layout.addWidget(dot)
            row_layout.addWidget(name)
            row_layout.addStretch()
            row_layout.addWidget(status)
            layout.addWidget(row)
            self.status_labels[provider.casefold()] = status
            self.dot_labels[provider.casefold()] = dot

    def set_status(self, provider: str, status: str) -> None:
        label = self.status_labels.get(provider.casefold())
        if label is None:
            return
        normalized = status.casefold().strip()
        if normalized == "available":
            display, tone = "Configured", "ready"
        elif normalized == "not set":
            display, tone = "Not configured", "unset"
        else:
            display, tone = "Check failed", "warning"
        label.setText(display)
        label.setProperty("status", tone)
        dot = self.dot_labels.get(provider.casefold())
        for widget in (label, dot):
            if widget is not None:
                widget.setProperty("status", tone)
                widget.style().unpolish(widget)
                widget.style().polish(widget)


class ElidedLabel(QLabel):
    """One line that elides to its width and shows the whole text on hover.

    A model id has no spaces to wrap at, so a word-wrapped QLabel holding
    "qwen3.8-max-preview-2026-10-01" would demand more than the rail's 244px
    and be clipped by the rail's no-horizontal-scroll rule instead.
    """

    def __init__(self, text: str = "", object_name: str = "RailDetail"):
        super().__init__()
        self.setObjectName(object_name)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._full = ""
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self._elide()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        shown = self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideMiddle, max(0, self.width()))
        self.setText(shown)
        self.setToolTip(self._full if shown != self._full else "")


@dataclass(frozen=True)
class ModelNotice:
    """One new model, as the tile shows it."""
    provider_label: str
    model_id: str
    best_for: tuple[str, ...] = ()   # agent labels it is now the best pick for
    exact_price: bool = True


class ModelUpdatesCard(RailCard):
    """New models from the configured providers, and the control to look.

    Lives under API keys because the two answer the same question from either
    end: which providers can I use, and what have they shipped since I last
    looked. The section is collapsed like its neighbours; the host puts the
    count in the section title so news is visible without opening it.
    """

    SHOWN = 5

    def __init__(self):
        super().__init__("New AI models from configured providers")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SM, SM, SM, SM)
        layout.setSpacing(XS)

        self.headline = _label("Not checked yet", "RailPrimaryValue")
        layout.addWidget(self.headline)
        self.rows_box = QVBoxLayout()
        self.rows_box.setContentsMargins(0, 0, 0, 0)
        self.rows_box.setSpacing(XS)
        layout.addLayout(self.rows_box)

        divider = QFrame()
        divider.setObjectName("RailCardDivider")
        divider.setFrameShape(QFrame.HLine)
        layout.addWidget(divider)

        self.checked_label = _label("", "RailDetail")
        layout.addWidget(self.checked_label)
        self.skipped_label = _label("", "RailDetail")
        self.skipped_label.hide()
        layout.addWidget(self.skipped_label)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, XS, 0, 0)
        buttons.setSpacing(XS)
        self.check_btn = QPushButton("Check now")
        self.check_btn.setObjectName("RailCardButton")
        self.check_btn.setToolTip(
            "Ask each provider with a key for its model list. Free: model "
            "lists are not billed.")
        self.dismiss_btn = QPushButton("Dismiss")
        self.dismiss_btn.setObjectName("RailCardButton")
        self.dismiss_btn.setToolTip(
            "Clear these notices. The models stay in the menus and are not "
            "announced again.")
        self.dismiss_btn.hide()
        buttons.addWidget(self.check_btn)
        buttons.addWidget(self.dismiss_btn)
        layout.addLayout(buttons)

        self.startup_checkbox = QCheckBox("Check when Imprint starts")
        self.startup_checkbox.setObjectName("RailCardCheck")
        layout.addWidget(self.startup_checkbox)

    def set_checking(self, checking: bool) -> None:
        self.check_btn.setEnabled(not checking)
        self.check_btn.setText("Checking…" if checking else "Check now")

    def set_notices(self, notices: list[ModelNotice]) -> None:
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        count = len(notices)
        self.headline.setText(
            "No new models" if count == 0 else
            "1 new model" if count == 1 else f"{count} new models")
        self.dismiss_btn.setVisible(count > 0)
        for notice in notices[:self.SHOWN]:
            self.rows_box.addWidget(self._row(notice))
        if count > self.SHOWN:
            self.rows_box.addWidget(_label(
                f"+{count - self.SHOWN} more — all are in the model menus, "
                "marked NEW.", "RailDetail"))

    def set_footer(self, checked: str, skipped: str = "") -> None:
        self.checked_label.setText(checked)
        self.skipped_label.setText(skipped)
        self.skipped_label.setVisible(bool(skipped))

    @staticmethod
    def _row(notice: ModelNotice) -> QWidget:
        row = QWidget()
        row.setObjectName("RailModelRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, XS, 0, XS)
        layout.setSpacing(2)
        layout.addWidget(_label(notice.provider_label, "RailKeyName"))
        layout.addWidget(ElidedLabel(notice.model_id, "RailModelId"))
        if notice.best_for:
            fit = _label(
                f"Best {notice.provider_label} pick for "
                + ", ".join(notice.best_for), "RailAvailability")
            fit.setProperty("status", "ready")
        else:
            fit = _label(f"Added to the {notice.provider_label} model menus",
                         "RailDetail")
        layout.addWidget(fit)
        if not notice.exact_price:
            price = _label(
                f"No price on file — estimated at {notice.provider_label}'s "
                "default rate", "RailAvailability")
            price.setProperty("status", "warning")
            price.setToolTip(
                "Add its real rates in Settings → Pricing so budget caps "
                "count it exactly.")
            layout.addWidget(price)
        return row


STATUS_CARD_STYLES = f"""
    QFrame#RailStatusCard {{ background: {SUNKEN}; border: 1px solid {BORDER};
        border-radius: 9px; }}
    QLabel#RailFieldName {{ color: {TEXT_MUTE}; font-size: 10px;
        font-weight: 700; letter-spacing: .7px; text-transform: uppercase; }}
    QLabel#RailPrimaryValue {{ color: {TEXT}; font-size: 12px; font-weight: 600; }}
    QLabel#RailMetricValue {{ color: {TEXT}; font-size: 13px; font-weight: 700; }}
    QLabel#RailDetail {{ color: {TEXT_DIM}; font-size: 11px; }}
    QFrame#RailCardDivider {{ color: {BORDER}; margin: 5px 0; }}
    QLabel#RailScoreBadge {{ color: {ACCENT}; background: {ACCENT_WASH};
        border: 1px solid {ACCENT_LINE}; border-radius: 7px; padding: 3px 6px;
        font-size: 9px; font-weight: 700; }}
    QLabel#RailAvailability {{ border-radius: 6px; padding: 5px 7px;
        font-size: 10px; font-weight: 650; }}
    QLabel#RailAvailability[status="ready"] {{ color: {ACCENT};
        background: {ACCENT_WASH}; border: 1px solid {ACCENT_LINE}; }}
    QLabel#RailAvailability[status="warning"] {{ color: {WARNING};
        background: {WARNING_WASH}; border: 1px solid {WARNING_LINE}; }}
    QWidget#RailKeyRow {{ border-bottom: 1px solid {BORDER}; }}
    QLabel#RailKeyName {{ color: {TEXT}; font-size: 11px; font-weight: 600; }}
    QLabel#RailKeyStatus, QLabel#RailStatusDot {{ color: {TEXT_MUTE}; font-size: 10px; }}
    QLabel#RailKeyStatus[status="ready"], QLabel#RailStatusDot[status="ready"] {{
        color: {ACCENT}; }}
    QLabel#RailKeyStatus[status="warning"], QLabel#RailStatusDot[status="warning"] {{
        color: {WARNING}; }}
    QWidget#RailModelRow {{ border-bottom: 1px solid {BORDER}; }}
    QLabel#RailModelId {{ color: {TEXT}; font-size: 11px;
        font-family: "SF Mono", Menlo, monospace; }}
    QPushButton#RailCardButton {{ min-height: 26px; max-height: 26px;
        font-size: 11px; padding: 0 8px; }}
    QCheckBox#RailCardCheck {{ color: {TEXT_DIM}; font-size: 11px; }}
"""
