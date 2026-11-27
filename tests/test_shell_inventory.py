"""Nothing lost (spec manuscript-redesign, measure 2; ADR 0006).

``tests/data/shell_controls_before.json`` was written by the first Build
commit, before slice 1 changed any chrome: every action button, field,
checkable, list, tab bar and menu action the header and both rails held, by
attribute name, with its tooltip and the signals its handler hangs on. Each
must still exist, keep its tooltip and handler, and be visible or one click
away: in a popover under a visible chip, in the History drawer under the
visible History button, in a menu under its visible button, or in Settings
under the visible gear.
"""

import json
from pathlib import Path

import pytest

SNAPSHOT = Path(__file__).parent / "data" / "shell_controls_before.json"

#: Removed with the owner's approval of Design S4 (2026-11-25, "Approve as
#: recommended"), the owner line measure 2 asks for.
REMOVED = {
    "workspace_more_btn": "overflow chrome: the icon rail never overflows (S2, S4)",
}

#: Set once, in Settings > General (D2, S8): one click on the rail's gear.
IN_SETTINGS = {"theme_dots", "tooltips_toggle_btn"}

#: Tooltips Design S3 gives a new text on purpose.
TOOLTIP_BY_DESIGN = {
    "history_project_filter": "S3 #2: it shows the project now and takes over "
                              "the retired project pill's tooltip",
}

#: A button that became a menu action, or a toggle that became a checkable
#: action, keeps its handler on the action's signal.
EQUIVALENT = {
    "clicked": {"clicked", "triggered", "toggled"},
    "pressed": {"pressed", "triggered"},
}


@pytest.fixture(scope="module")
def snapshot():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["controls"]


@pytest.fixture(scope="module")
def window(qapp):
    from PySide6.QtWidgets import QMessageBox
    import main

    saved = (QMessageBox.warning, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        built = main.GodAI()
        built.resize(1440, 900)
        built.show()
        for _ in range(6):
            qapp.processEvents()
        yield built
    finally:
        QMessageBox.warning, QMessageBox.information = saved
        built.resource_timer.stop()
        qapp.removeEventFilter(built)
        built.hide()


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _connected(control) -> set[str]:
    """Every signal of `control` that has a receiver, by name."""
    meta = control.metaObject()
    names = set()
    for index in range(meta.methodCount()):
        method = meta.method(index)
        if method.methodType() == method.MethodType.Signal and \
                control.isSignalConnected(method):
            names.add(bytes(method.name()).decode())
    return names


def _resolve(window, name):
    first, _, rest = name.partition(".")
    value = window._find_control(first)
    for part in filter(None, rest.split(".")):
        value = getattr(value, part, None) if value is not None else None
    return value


def _home(window, control) -> str | None:
    """Where `control` is reachable from: "visible", or the container whose
    visible opener is one click away; None when neither."""
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu
    from ui.spotlight import anchor_for

    if isinstance(control, QAction):
        anchor = anchor_for(control)
        menus = [w for w in control.associatedObjects() if isinstance(w, QMenu)]
        if anchor is not None and anchor.isVisible() and menus:
            return "menu"
        return None
    if control.isVisible():
        return "visible"
    for container, opener, label in (
            (window.spend_popover, window.spend_chip, "spend popover"),
            (window.status_popover, window.agent_status_pill, "status popover"),
            (window.history_drawer, window.history_btn, "drawer")):
        if container.isAncestorOf(control) and opener.isVisible():
            return label
    return None


def test_the_snapshot_is_the_one_taken_before_the_change(snapshot):
    assert len(snapshot) >= 30
    assert {"history_list", "session_budget_input", "workspace_tabs",
            "settings_btn", "new_project_btn", "cost_history_btn",
            "model_updates_card.update_btn"} <= set(snapshot)


def test_every_control_is_still_reachable_with_its_handler_and_tooltip(
        qapp, window, snapshot, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from ui import dialogs

    problems = []
    for name, before in snapshot.items():
        if name in REMOVED:
            assert _resolve(window, name) is None, f"{name} is listed as removed"
            continue
        if name in IN_SETTINGS:
            continue                       # checked in the Settings test below
        control = _resolve(window, name)
        if control is None:
            problems.append(f"{name}: gone")
            continue
        if _home(window, control) is None:
            problems.append(f"{name}: not visible and not one click away")
        if control.toolTip() != before["tooltip"] and name not in TOOLTIP_BY_DESIGN:
            problems.append(f"{name}: tooltip {control.toolTip()!r} "
                            f"was {before['tooltip']!r}")
        signals = _connected(control)
        for signal in before["signals"]:
            if not signals & EQUIVALENT.get(signal, {signal}):
                problems.append(f"{name}: {signal} handler is gone")
    assert not problems, "\n".join(problems)

    # Settings: the theme dots and the tooltip toggle (D2).
    assert window.settings_btn.isVisible()
    opened = []
    monkeypatch.setattr(QDialog, "exec", lambda self: opened.append(self) or 0)
    dialogs.show_settings(window)
    try:
        assert opened[0].isAncestorOf(window.theme_dots)
        from PySide6.QtWidgets import QCheckBox
        box = opened[0].findChild(QCheckBox, "ShowTooltips")
        assert box is not None
        assert window.tooltips_toggle_btn.toolTip() == \
            snapshot["tooltips_toggle_btn"]["tooltip"]
        assert "toggled" in _connected(window.tooltips_toggle_btn)
    finally:
        opened[0].reject()


def test_the_removed_list_names_only_snapshot_controls(snapshot):
    assert set(REMOVED) <= set(snapshot)
    assert set(IN_SETTINGS) <= set(snapshot)
    assert set(TOOLTIP_BY_DESIGN) <= set(snapshot)
