"""The window owns every widget it builds.

A widget built without a parent and never put in a layout is a top-level
widget: it outlives the window, becomes cyclic garbage and is freed by the
collector at an arbitrary later point. In the full suite that was a
segfault (`_DropdownPolisher` filtering the events of a combo being
destroyed, 2026-11-20 to -22). This guard fails as soon as a new one
appears, naming it.
"""

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox



@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _describe(widget):
    return f"{type(widget).__name__}({widget.objectName() or widget.windowTitle()!r})"


def test_building_the_window_leaves_no_parentless_widget(app, monkeypatch):
    import main

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    before = set(app.topLevelWidgets())
    window = main.GodAI()
    try:
        strays = [w for w in app.topLevelWidgets()
                  if w not in before and w is not window and w.parent() is None]
        assert not strays, (
            "parentless widgets built by the window (give each a parent): "
            + ", ".join(sorted(_describe(w) for w in strays)))
    finally:
        # The suite's own window teardown (tests/test_chat_projects.py): no
        # forced flush, which crashed a later module for a whole GodAI.
        window.author_panel._project_save_timer.stop()
        window.resource_timer.stop()
        app.removeEventFilter(window)
        window.close()
        window.deleteLater()
