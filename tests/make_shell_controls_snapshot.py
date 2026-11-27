"""Write tests/data/shell_controls_before.json (spec manuscript-redesign, measure 2).

Not collected by the suite (no ``test_`` prefix). Run once, before slice 1
changes any chrome, so the conftest's temporary DB and settings apply:

    IMPRINT_WRITE_SHELL_SNAPSHOT=1 .venv/bin/python -m pytest -q \\
        tests/make_shell_controls_snapshot.py -p no:randomly

It records every action button, field, checkable, list, tab bar and menu
action that today's header and both rails hold, by attribute name, with its
kind, tooltip and the signals that have a receiver. A composite widget's own
interactive attributes are recorded as ``parent.child``.
``tests/test_shell_inventory.py`` walks the file after the change.
"""

import json
import os
from pathlib import Path

import pytest

SNAPSHOT = Path(__file__).parent / "data" / "shell_controls_before.json"

# Signals a control's handler hangs on, by kind. Only the ones with a
# receiver are recorded.
SIGNALS = {
    "menu_action": ("triggered", "toggled"),
    "button": ("clicked", "toggled", "pressed"),
    "checkable": ("clicked", "toggled"),
    "field": ("editingFinished", "textChanged", "returnPressed",
              "valueChanged"),
    "combo": ("currentIndexChanged", "currentTextChanged", "activated"),
    "list": ("itemClicked", "itemDoubleClicked",
             "customContextMenuRequested"),
    "tabs": ("currentChanged",),
    "picker": (),
}


def _kind(obj):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox,
                                   QComboBox, QLineEdit, QListWidget, QTabBar)
    from ui.widgets import ThemeDots
    if isinstance(obj, QAction):
        return "menu_action"
    if isinstance(obj, QAbstractButton):
        return "checkable" if obj.isCheckable() else "button"
    if isinstance(obj, (QLineEdit, QAbstractSpinBox)):
        return "field"
    if isinstance(obj, QComboBox):
        return "combo"
    if isinstance(obj, QListWidget):
        return "list"
    if isinstance(obj, QTabBar):
        return "tabs"
    if isinstance(obj, ThemeDots):
        return "picker"
    return None


def connected_signals(obj, kind):
    """Names of `kind`'s handler signals that have at least one receiver."""
    meta = obj.metaObject()
    found = []
    for name in SIGNALS[kind]:
        for index in range(meta.methodCount()):
            method = meta.method(index)
            if bytes(method.name()).decode() != name:
                continue
            if obj.isSignalConnected(method):
                found.append(name)
                break
    return found


def _inside(obj, container):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QWidget
    if isinstance(obj, QWidget):
        return obj is container or container.isAncestorOf(obj)
    if isinstance(obj, QAction):
        parent = obj.parent()
        while parent is not None:
            if parent is container:
                return True
            parent = parent.parent()
    return False


def _record(obj, kind, where):
    return {
        "kind": kind,
        "class": type(obj).__name__,
        "where": where,
        "tooltip": obj.toolTip(),
        "signals": connected_signals(obj, kind),
    }


def collect(window):
    from PySide6.QtWidgets import QFrame, QWidget
    containers = {}
    for name in ("AppHeader", "RailLeft", "RailRight"):
        found = [w for w in window.findChildren(QFrame)
                 if w.objectName() == name]
        assert len(found) == 1, name
        containers[name] = found[0]

    controls = {}
    for attr, obj in sorted(vars(window).items()):
        if attr.startswith("_"):
            continue
        where = next((n for n, c in containers.items() if _inside(obj, c)),
                     None)
        if where is None:
            continue
        kind = _kind(obj)
        if kind is not None:
            controls[attr] = _record(obj, kind, where)
            continue
        if not isinstance(obj, QWidget):
            continue
        # A composite (a card, a meter): its own interactive attributes.
        for sub, child in sorted(vars(obj).items()):
            if sub.startswith("_"):
                continue
            sub_kind = _kind(child)
            if sub_kind is not None and _inside(child, containers[where]):
                controls[f"{attr}.{sub}"] = _record(child, sub_kind, where)
    return controls


@pytest.mark.skipif(not os.environ.get("IMPRINT_WRITE_SHELL_SNAPSHOT"),
                    reason="one-off snapshot writer")
def test_write_snapshot():
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    import main

    saved = (QMessageBox.warning, QMessageBox.question,
             QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        w = main.GodAI()
        w.resize(1280, 820)
        w.show()
        for _ in range(6):
            app.processEvents()
        controls = collect(w)
        w.resource_timer.stop()
        app.removeEventFilter(w)
        w.close()
    finally:
        (QMessageBox.warning, QMessageBox.question,
         QMessageBox.information) = saved

    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps({
        "spec": "docs/specs/manuscript-redesign.md, measure 2",
        "taken_before": "slice 1 (Shell) changed any chrome",
        "containers": ["AppHeader", "RailLeft", "RailRight"],
        "controls": controls,
    }, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    assert controls
