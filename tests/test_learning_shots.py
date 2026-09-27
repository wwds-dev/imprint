"""
Imprint — Learning Centre screenshot generator tests
=====================================================
Type: Wiring tests, run headless.

`scripts/make_learning_shots.py` drives the real window through a list of
setup lambdas, and nothing else runs them. When the 2026-09-21 panel
extractions moved `video_tabs` off the window, the script crashed partway
through — and only whoever next regenerated the screenshots found out. Worse
drift is silent: Social gained an Analytics tab ahead of Accounts, and the
index-based setup kept producing a screenshot, of the wrong page.

This runs every SHOTS entry against a real window, so a renamed attribute or a
missing tab caption fails the suite instead.

Run with:  pytest tests/test_learning_shots.py -v
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_generator():
    # scripts/ is not a package; load the file the way the command line would.
    path = PROJECT_ROOT / "scripts" / "make_learning_shots.py"
    spec = importlib.util.spec_from_file_location("make_learning_shots", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    """One window for the module, stubbed the way the generator stubs it."""
    from PySide6.QtWidgets import QMessageBox
    import main

    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        w = main.GodAI()
        w.show()
        app.processEvents()
        yield w
    finally:
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


@pytest.mark.parametrize(
    "filename, agent, setup", GENERATOR.SHOTS,
    ids=[shot[0] for shot in GENERATOR.SHOTS])
def test_every_shot_setup_runs_against_the_window(app, window, filename, agent, setup):
    if agent == "video" and setup is not None and not window.video_panel._available:
        # The panel builds only a notice without vidforge; the generator
        # refuses to run in that state, so there is nothing to drift.
        pytest.skip("vidforge is not importable in this checkout")
    window.select_agent(agent)
    app.processEvents()
    if setup is not None:
        setup(window)
        app.processEvents()


def test_show_tab_refuses_a_missing_caption(app):
    from PySide6.QtWidgets import QTabWidget, QWidget

    tabs = QTabWidget()
    tabs.addTab(QWidget(), "Draft")
    tabs.addTab(QWidget(), "Accounts")
    GENERATOR._show_tab(tabs, "Accounts")
    assert tabs.currentIndex() == 1
    with pytest.raises(LookupError, match="Analytics"):
        GENERATOR._show_tab(tabs, "Analytics")
