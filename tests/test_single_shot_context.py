"""Every `QTimer.singleShot` in the app names a context object.

Without one, Qt calls the function even after the widget it touches is
deleted. AuthorPanel's deferred `_adapt_layout` did that once a test deleted
its window: the lambda raised "Internal C++ object already deleted", the
error was still set when the next Python application event filter ran
(`ui/text_fit.py`), and Shiboken segfaulted inside `QTest.qWait`
(2026-11-27, `tests/test_release_kit_e2e.py` then
`tests/test_fiverr_orders.py`, every run). With a context, Qt drops the
call when the context is destroyed.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [ROOT / "main.py", *sorted((ROOT / "ui").rglob("*.py")),
           *sorted((ROOT / "agents").rglob("*.py")),
           *sorted((ROOT / "services").rglob("*.py"))]


def _calls_without_context(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "singleShot" and len(node.args) == 2
                and not node.keywords):
            yield f"{path.relative_to(ROOT)}:{node.lineno}"


def test_every_single_shot_names_a_context():
    missing = [hit for path in SOURCES for hit in _calls_without_context(path)]
    assert not missing, ("QTimer.singleShot(ms, fn) without a context object; "
                         "pass the widget or window it touches: "
                         "singleShot(ms, context, fn): " + ", ".join(missing))


def test_a_deleted_context_drops_the_call():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])
    calls = []
    gone, kept = QWidget(), QWidget()
    QTimer.singleShot(0, gone, lambda: calls.append("gone"))
    QTimer.singleShot(0, kept, lambda: calls.append("kept"))
    gone.deleteLater()
    QCoreApplication.sendPostedEvents(gone, QEvent.Type.DeferredDelete)
    for _ in range(3):
        app.processEvents()
    kept.deleteLater()
    QCoreApplication.sendPostedEvents(kept, QEvent.Type.DeferredDelete)
    assert calls == ["kept"]
