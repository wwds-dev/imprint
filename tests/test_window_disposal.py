"""conftest files each GodAI window under the scope that built it.

A window from a function-scoped fixture or the test body is deleted at the
test's teardown; one from a module-scoped fixture lives until the module
ends, even when a test first asks for it through request.getfixturevalue
(code review of PR #32, P3-4)."""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _conftest():
    return next(module for name, module in sys.modules.items()
                if name.endswith("conftest") and hasattr(module, "_TEST_WINDOWS"))


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def module_window(app):
    import main
    return main.GodAI()


@pytest.fixture
def test_window(app):
    import main
    return main.GodAI()


def test_a_module_window_asked_for_late_is_not_the_tests(request):
    window = request.getfixturevalue("module_window")
    conftest = _conftest()
    assert any(w is window for w in conftest._SCOPED_WINDOWS)
    assert not any(w is window for w in conftest._TEST_WINDOWS)


def test_a_function_window_is_the_tests(test_window):
    conftest = _conftest()
    assert any(w is test_window for w in conftest._TEST_WINDOWS)
    assert not any(w is test_window for w in conftest._SCOPED_WINDOWS)
